"""Matched packet-v2 training study with validation-before-test recipe locking."""

import csv
import json
import math
import shutil
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .config import ExperimentConfig, GateConfig, SimulatorConfig, TrainingConfig
from .evidence import audit_complete_run
from .experiment import dump_json, evaluate_experiment, manifest, sha256, train_experiment
from .metrics import cluster_interval
from .reporting import build_report


def resolve_config(data):
    data = dict(data)
    for key, cls in [("simulator", SimulatorConfig), ("training", TrainingConfig), ("gate", GateConfig)]:
        data[key] = cls(**data.get(key, {}))
    return ExperimentConfig(**data).validate()


@dataclass(frozen=True)
class RealismStudy:
    name: str
    baseline: dict
    candidate: dict
    validation_seeds: list[int]
    test_seeds: list[int]
    development_seeds: list[int]
    max_id_qoe_drop: float = 0.03
    max_id_risk_increase: float = 0.002
    max_stress_risk_increase: float = 0.005
    min_stress_qoe_gain: float = 0.03
    min_score_gain: float = 0.01
    risk_penalty: float = 2.0

    def configs(self):
        base, candidate = resolve_config(self.baseline), resolve_config(self.candidate)
        if base.simulator.backend != "packet_v2" or base.simulator != candidate.simulator:
            raise ValueError("both recipes must use identical packet_v2 physics/action spaces")
        for key in ["seeds", "scenarios", "methods", "gate", "bootstrap_samples"]:
            if getattr(base, key) != getattr(candidate, key):
                raise ValueError(f"matched study differs in {key}")
        if not {"gcc", "heuristic", "rl", "calibrated"} <= set(base.methods):
            raise ValueError("study must include both conventional controls, ungated policy and RLCD")
        if base.training.episodes != candidate.training.episodes:
            raise ValueError("online RL episode budgets must match; extra demonstrations are disclosed")
        if (
            candidate.training.policy_features != "history_v2"
            or not candidate.training.demonstration_episodes
        ):
            raise ValueError("candidate requires explicit history/demonstration training")
        sets = []
        for seeds in [self.validation_seeds, self.test_seeds, self.development_seeds]:
            if not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int or s < 0 for s in seeds):
                raise ValueError("trace panels require unique nonnegative integers")
            sets.append(set(seeds))
        if any(a & b for i, a in enumerate(sets) for b in sets[i + 1 :]):
            raise ValueError("development/validation/test trace panels overlap")
        for value in [
            self.max_id_qoe_drop,
            self.max_id_risk_increase,
            self.max_stress_risk_increase,
            self.min_stress_qoe_gain,
            self.min_score_gain,
            self.risk_penalty,
        ]:
            if not math.isfinite(value) or value < 0:
                raise ValueError("selection bounds must be finite/nonnegative")
        if not self.name:
            raise ValueError("empty study name")
        return base, candidate


def read_episodes(run):
    with (Path(run) / "episodes.csv").open() as stream:
        return list(csv.DictReader(stream))


def domain_metrics(rows, method="calibrated"):
    result = {}
    for domain in ["id", "ood"]:
        group = [r for r in rows if r["method"] == method and r["domain"] == domain]
        if not group:
            raise ValueError("missing nominal/stress method observations")
        for metric in ["qoe", "violation_rate"]:
            result[f"{domain}_{metric}"] = float(np.mean([float(r[metric]) for r in group]))
    return result


def select_recipe(base_rows, candidate_rows, protocol):
    base, candidate = domain_metrics(base_rows), domain_metrics(candidate_rows)
    checks = dict(
        nominal_qoe=candidate["id_qoe"] >= base["id_qoe"] - protocol.max_id_qoe_drop,
        nominal_risk=candidate["id_violation_rate"]
        <= base["id_violation_rate"] + protocol.max_id_risk_increase,
        stress_risk=candidate["ood_violation_rate"]
        <= base["ood_violation_rate"] + protocol.max_stress_risk_increase,
        stress_quality=candidate["ood_qoe"] >= base["ood_qoe"] + protocol.min_stress_qoe_gain,
    )

    def score(values):
        return (
            values["id_qoe"]
            + values["ood_qoe"]
            - protocol.risk_penalty * (values["id_violation_rate"] + values["ood_violation_rate"])
        ) / 2

    gain = score(candidate) - score(base)
    checks["score_gain"] = gain > protocol.min_score_gain
    eligible = all(checks.values())
    return dict(
        selected_recipe="history_demo" if eligible else "baseline",
        candidate_eligible=eligible,
        checks=checks,
        baseline=base,
        candidate=candidate,
        score_gain=gain,
        selection_split="validation",
        scope="opt-in packet_v2 recipe only; V7/fluid-paper choice unchanged",
    )


def paired_estimates(base_rows, candidate_rows, samples):
    result = []
    for domain in ["id", "ood"]:
        comparisons = [
            ("calibrated", "baseline", "calibrated"),
            ("rl", "baseline", "rl"),
            ("calibrated", "candidate", "gcc"),
            ("calibrated", "candidate", "heuristic"),
            ("calibrated", "candidate", "rl"),
        ]
        for method, family, reference in comparisons:
            for metric in ["qoe", "violation_rate"]:

                def keyed(rows, selected):
                    filtered = [r for r in rows if r["domain"] == domain and r["method"] == selected]
                    keys = [(int(r["model_seed"]), int(r["test_seed"]), r["scenario"]) for r in filtered]
                    if len(keys) != len(set(keys)):
                        raise ValueError("duplicate paired observations")
                    return {key: float(row[metric]) for key, row in zip(keys, filtered)}

                left = keyed(candidate_rows, method)
                right = keyed(base_rows if family == "baseline" else candidate_rows, reference)
                if not left or left.keys() != right.keys():
                    raise ValueError("unmatched paired observations")
                means = [
                    float(np.mean([left[key] - right[key] for key in left if key[0] == seed]))
                    for seed in sorted({key[0] for key in left})
                ]
                result.append(
                    dict(
                        domain=domain,
                        method=method,
                        reference_family=family,
                        reference=reference,
                        metric=metric,
                        units="fraction" if metric == "violation_rate" else "QoE proxy",
                        **cluster_interval(means, samples, seed=1010),
                    )
                )
    return result


def verify_matched_controls(base_run, candidate_run):
    base, candidate = read_episodes(base_run), read_episodes(candidate_run)
    for name in ["gcc", "heuristic", "safe"]:
        left = {(r["model_seed"], r["test_seed"], r["scenario"]): r for r in base if r["method"] == name}
        right = {
            (r["model_seed"], r["test_seed"], r["scenario"]): r for r in candidate if r["method"] == name
        }
        if left.keys() != right.keys():
            raise ValueError("control identities differ")
        for key in left:
            for metric in ["qoe", "violation_rate", "goodput_mbps", "latency_mean_ms", "deadline_miss"]:
                if left[key][metric] != right[key][metric]:
                    raise ValueError("conventional outcomes changed across recipes")
    for path in (Path(base_run) / "traces").glob("*.npz"):
        if sha256(path) != sha256(Path(candidate_run) / "traces" / path.name):
            raise ValueError("physical traces are not shared")
    return base, candidate


def run_realism_study(settings_path, out, plots=False):
    protocol = RealismStudy(**json.loads(Path(settings_path).read_text()))
    base, candidate = protocol.configs()
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"refusing completed/partial study overwrite: {out}")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings_path, out / "protocol.json")
    # Freeze executable source before fitting; no mid-run implementation drift.
    sources = {str(p): sha256(p) for p in Path(__file__).parent.glob("*.py")}

    def unchanged():
        if any(sha256(Path(path)) != digest for path, digest in sources.items()):
            raise ValueError("implementation changed during the locked study")

    dump_json(out / "implementation_sha256.json", sources)
    for name, config in [("baseline", base), ("candidate", candidate)]:
        dump_json(out / f"{name}_config.json", config.to_dict())
        train_experiment(config, out / name / "trained")
        unchanged()

    def evaluate(stage, seeds):
        for name, config in [("baseline", base), ("candidate", candidate)]:
            unchanged()
            cfg = replace(config, name=f"{protocol.name}-{name}-{stage}", test_seeds=seeds).validate()
            run = out / name / stage
            evaluate_experiment(cfg, out / name / "trained", run, split=stage)
            if stage == "test":
                shutil.copy2(out / "selection.json", run / "selection.json")
            build_report(run, plots=plots)
            manifest(run, cfg, "complete")
            audit_complete_run(run)
        return verify_matched_controls(out / "baseline" / stage, out / "candidate" / stage)

    base_validation, candidate_validation = evaluate("validation", protocol.validation_seeds)
    lock = select_recipe(base_validation, candidate_validation, protocol)
    lock["locked_utc"] = datetime.now(timezone.utc).isoformat()
    lock["validation_manifest_sha256"] = {
        name: sha256(out / name / "validation" / "manifest.json") for name in ["baseline", "candidate"]
    }
    lock["model_sha256"] = {
        name: {str(seed): sha256(out / name / "trained/models" / f"seed_{seed}.json") for seed in base.seeds}
        for name in ["baseline", "candidate"]
    }
    dump_json(out / "selection.json", lock)
    lock_hash = sha256(out / "selection.json")
    print(f"locked selected_recipe={lock['selected_recipe']} checks={lock['checks']}", flush=True)
    base_test, candidate_test = evaluate("test", protocol.test_seeds)
    unchanged()
    if sha256(out / "selection.json") != lock_hash:
        raise ValueError("selection changed after inspecting test")
    summary = dict(
        study=protocol.name,
        backend="packet_v2",
        selected_recipe=lock["selected_recipe"],
        selection_sha256=lock_hash,
        tests_predeclared=True,
        validation_episodes=len(base_validation) + len(candidate_validation),
        test_episodes=len(base_test) + len(candidate_test),
        test_steps=(len(base_test) + len(candidate_test)) * base.simulator.steps,
        means={
            name: {method: domain_metrics(rows, method) for method in base.methods}
            for name, rows in [("baseline", base_test), ("candidate", candidate_test)]
        },
        contrasts=paired_estimates(base_test, candidate_test, base.bootstrap_samples),
        limitations=[
            "Synthetic packet/frame/FEC/QoE proxies, not real-codec/network validation.",
            "Known families/new trace IDs, not unseen mechanisms.",
            "Intervals condition on this panel and independent model-seed clusters.",
            "Training data/encoder/teacher/target changes are bundled, not separately identified.",
            "Extra demonstration samples and optimizer updates are not matched compute.",
            "Terminal pending frames/labels are reported as censored, not successful decodes.",
        ],
    )
    dump_json(out / "results.json", summary)
    artifacts = {
        str(p.relative_to(out)): sha256(p)
        for p in out.rglob("*")
        if p.is_file() and p.name != "study_manifest.json"
    }
    dump_json(
        out / "study_manifest.json",
        dict(
            stage="complete",
            selection_sha256=lock_hash,
            implementation_sha256=sources,
            artifacts_sha256=artifacts,
        ),
    )
    print(f"completed matched packet study test_episodes={summary['test_episodes']}", flush=True)
    return out
