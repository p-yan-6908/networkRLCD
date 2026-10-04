"""Validation-only confidence-threshold selection with a locked fresh-trace test."""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from .config import load_config
from .experiment import dump_json, manifest, sha256
from .improvement import audit_directory, complete_evaluation
from .reporting import build_report, read_episodes
from .scenarios import SCENARIOS


@dataclass(frozen=True)
class ThresholdProtocol:
    name: str
    model_seeds: list[int]
    validation_seeds: list[int]
    test_seeds: list[int]
    thresholds: list[float]
    baseline_threshold: float
    max_id_qoe_drop: float
    max_id_violation_increase: float
    max_stress_violation_increase: float
    max_stress_scenario_violation_increase: float
    risk_penalty: float
    minimum_score_gain: float
    bootstrap_samples: int

    def validate(self):
        groups = [self.model_seeds, self.validation_seeds, self.test_seeds]
        for values in groups:
            if (
                not values
                or len(set(values)) != len(values)
                or any(type(x) is not int or x < 0 for x in values)
            ):
                raise ValueError("seed panels must be nonempty unique nonnegative integers")
        if set(self.validation_seeds) & set(self.test_seeds):
            raise ValueError("validation and fresh-test seeds overlap")
        if len(self.thresholds) < 2 or len(set(self.thresholds)) != len(self.thresholds):
            raise ValueError("threshold candidate grid must contain at least two unique values")
        if any(not np.isfinite(t) or not 0 <= t <= 1 for t in self.thresholds):
            raise ValueError("thresholds must be finite probabilities")
        if self.baseline_threshold not in self.thresholds:
            raise ValueError("baseline threshold must be evaluated in the candidate grid")
        if any(
            not np.isfinite(x) or x < 0
            for x in [
                self.max_id_qoe_drop,
                self.max_id_violation_increase,
                self.max_stress_violation_increase,
                self.max_stress_scenario_violation_increase,
                self.risk_penalty,
                self.minimum_score_gain,
            ]
        ):
            raise ValueError("selection tolerances must be finite and nonnegative")
        if type(self.bootstrap_samples) is not int or self.bootstrap_samples < 20:
            raise ValueError("bootstrap_samples must be at least 20")
        return self


def threshold_metrics(run):
    episodes = read_episodes(Path(run) / "episodes.csv")
    if not episodes:
        raise ValueError("empty validation run")
    domains, scenarios = {}, {}
    for domain in ["id", "ood"]:
        selected = [r for r in episodes if r["domain"] == domain]
        if not selected:
            raise ValueError(f"validation panel missing domain {domain}")
        domains[domain] = {
            metric: float(np.mean([r[metric] for r in selected])) for metric in ["qoe", "violation_rate"]
        }
    for scenario in SCENARIOS:
        selected = [r for r in episodes if r["scenario"] == scenario]
        if selected:
            scenarios[scenario] = {
                metric: float(np.mean([r[metric] for r in selected])) for metric in ["qoe", "violation_rate"]
            }
    if set(scenarios) != set(r["scenario"] for r in episodes):
        raise ValueError("validation includes unknown scenario names")
    return dict(
        id_qoe=domains["id"]["qoe"],
        id_violation_rate=domains["id"]["violation_rate"],
        stress_qoe=domains["ood"]["qoe"],
        stress_violation_rate=domains["ood"]["violation_rate"],
        scenarios=scenarios,
    )


def threshold_score(metrics, penalty):
    return 0.5 * (metrics["id_qoe"] + metrics["stress_qoe"]) - penalty * metrics["stress_violation_rate"]


def select_threshold(metrics_by_threshold, protocol):
    """Select from validation summaries only; never receives a final-test path."""

    def key(value):
        return f"{value:.2f}"

    baseline = metrics_by_threshold[key(protocol.baseline_threshold)]
    baseline_score = threshold_score(baseline, protocol.risk_penalty)
    stress_scenarios = [name for name, domain in SCENARIOS.items() if domain == "ood"]
    ranking = []
    for threshold in protocol.thresholds:
        current = metrics_by_threshold[key(threshold)]
        scenario_deltas = {
            name: current["scenarios"][name]["violation_rate"] - baseline["scenarios"][name]["violation_rate"]
            for name in stress_scenarios
        }
        feasible = (
            current["id_qoe"] >= baseline["id_qoe"] - protocol.max_id_qoe_drop
            and current["id_violation_rate"]
            <= baseline["id_violation_rate"] + protocol.max_id_violation_increase
            and current["stress_violation_rate"]
            <= baseline["stress_violation_rate"] + protocol.max_stress_violation_increase
            and all(
                delta <= protocol.max_stress_scenario_violation_increase for delta in scenario_deltas.values()
            )
        )
        ranking.append(
            dict(
                threshold=threshold,
                feasible=feasible,
                score=threshold_score(current, protocol.risk_penalty),
                score_gain=threshold_score(current, protocol.risk_penalty) - baseline_score,
                metrics=current,
                stress_scenario_violation_deltas=scenario_deltas,
            )
        )
    eligible = [row for row in ranking if row["feasible"] and row["score_gain"] > protocol.minimum_score_gain]
    selected = (
        max(eligible, key=lambda row: row["score"])["threshold"] if eligible else protocol.baseline_threshold
    )
    return dict(
        selected_threshold=selected,
        baseline_threshold=protocol.baseline_threshold,
        baseline_metrics=baseline,
        baseline_score=baseline_score,
        ranking=ranking,
        selection_split="validation",
        validation_seeds=protocol.validation_seeds,
        test_seeds=protocol.test_seeds,
        protocol=asdict(protocol),
    )


def _campaign_identity(protocol, models):
    data = json.loads((models / "manifest.json").read_text())
    checkpoint_hashes = {
        str(seed): sha256(models / "models" / f"seed_{seed}.json") for seed in protocol.model_seeds
    }
    if any(
        data["artifacts_sha256"].get(f"models/seed_{seed}.json") != digest
        for seed, digest in checkpoint_hashes.items()
    ):
        raise ValueError("source checkpoint integrity check failed")
    return dict(
        protocol=asdict(protocol),
        source_config_sha256=sha256(models / "config.json"),
        source_manifest_sha256=sha256(models / "manifest.json"),
        model_sha256=checkpoint_hashes,
        implementation_sha256={p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
    )


def run_threshold_selection(settings_path, models, out, plots=True):
    settings = json.loads(Path(settings_path).read_text())
    protocol = ThresholdProtocol(**settings).validate()
    models, out = Path(models).resolve(), Path(out)
    base = load_config(models / "config.json")
    if not set(protocol.model_seeds) <= set(base.seeds):
        raise ValueError("threshold selection requires existing checkpoints for every declared seed")
    if (set(protocol.validation_seeds) | set(protocol.test_seeds)) & set(base.test_seeds):
        raise ValueError("follow-up panels must not reuse the source evaluation seeds")
    identity = _campaign_identity(protocol, models)
    if out.exists():
        if json.loads((out / "campaign.json").read_text()) != identity:
            raise ValueError(
                "campaign settings/source/implementation changed; preserve it and use a new output"
            )
    else:
        out.mkdir(parents=True)
        dump_json(out / "campaign.json", identity)
    config = replace(
        base, name=protocol.name, seeds=protocol.model_seeds, bootstrap_samples=protocol.bootstrap_samples
    ).validate()
    metrics_by_threshold, validation_hashes = {}, {}
    for threshold in protocol.thresholds:
        label = f"{threshold:.2f}"
        variant = replace(
            config,
            name=f"validation-threshold-{label}",
            methods=["calibrated"],
            test_seeds=protocol.validation_seeds,
            gate=replace(
                config.gate,
                threshold=threshold,
                release_margin=min(config.gate.release_margin, 1 - threshold),
            ),
        ).validate()
        run = out / "validation" / f"threshold_{label.replace('.', 'p')}"
        complete_evaluation(variant, models, run, "validation", plots=False)
        metrics_by_threshold[label] = threshold_metrics(run)
        validation_hashes[label] = sha256(run / "manifest.json")
        print(f"validation threshold={label} complete", flush=True)
    selection = select_threshold(metrics_by_threshold, protocol)
    selection["validation_manifests_sha256"] = validation_hashes
    selection_path = out / "selection.json"
    if selection_path.exists():
        if json.loads(selection_path.read_text()) != selection:
            raise ValueError("locked threshold selection changed; do not overwrite it")
    else:
        dump_json(selection_path, selection)
    print(f"LOCKED threshold={selection['selected_threshold']:.2f} before fresh-test evaluation", flush=True)

    selected = float(selection["selected_threshold"])
    final_config = replace(
        config,
        name="rlcd-v3-fresh-test",
        test_seeds=protocol.test_seeds,
        methods=["safe", "heuristic", "gcc", "rl", "calibrated", "calibrated_090", "uncalibrated"],
        gate=replace(
            config.gate, threshold=selected, release_margin=min(config.gate.release_margin, 1 - selected)
        ),
    ).validate()
    final = out / "test"
    if final.exists():
        data = audit_directory(final, "complete")
        if not final_config.digest_matches(data["config_sha256"]) or data.get("evaluation_split") != "test":
            raise ValueError("final test directory does not match locked selection")
    else:
        from .experiment import evaluate_experiment

        evaluate_experiment(
            final_config,
            models,
            final,
            split="test",
            gate_overrides={"calibrated_090": protocol.baseline_threshold},
        )
        # Hash the locked validation choice into the immutable final-run manifest.
        (final / "selection.json").write_bytes(selection_path.read_bytes())
        build_report(final, plots=plots)
        manifest(final, final_config, "complete")
    dump_json(
        out / "status.json",
        dict(
            stage="complete",
            selected_threshold=selected,
            selection_sha256=sha256(selection_path),
            final_manifest_sha256=sha256(final / "manifest.json"),
        ),
    )
    return final
