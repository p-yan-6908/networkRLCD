"""Locked evaluation of action-wise calibrated safety screening."""

import csv
import gzip
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from .config import load_config
from .experiment import dump_json, evaluate_experiment, manifest, sha256, source_files, write_csv
from .improvement import audit_directory, complete_evaluation
from .reporting import build_report, read_episodes
from .scenarios import SCENARIOS

REFERENCE_METHOD = "calibrated_v1"
CANDIDATE_METHOD = "shielded"
UNCERTAINTY_REFERENCE_METHOD = "shielded"
UNCERTAINTY_CANDIDATE_METHOD = "shielded_uncertainty"
UNCERTAINTY_TEST_METHODS = [
    "safe",
    "heuristic",
    "gcc",
    "rl",
    "calibrated",
    "uncalibrated",
    UNCERTAINTY_REFERENCE_METHOD,
    UNCERTAINTY_CANDIDATE_METHOD,
]
TEST_METHODS = [
    "safe",
    "heuristic",
    "gcc",
    "rl",
    REFERENCE_METHOD,
    "calibrated",
    CANDIDATE_METHOD,
    "uncalibrated",
]


@dataclass(frozen=True)
class ShieldProtocol:
    name: str
    model_seeds: list[int]
    validation_seeds: list[int]
    test_seeds: list[int]
    top_k: int
    threshold: float
    max_id_qoe_drop: float
    max_id_violation_increase: float
    max_stress_violation_increase: float
    max_stress_scenario_violation_increase: float
    risk_penalty: float
    minimum_score_gain: float
    max_ensemble_std: float = 0.5

    def validate(self):
        for values in [self.model_seeds, self.validation_seeds, self.test_seeds]:
            if (
                not values
                or len(set(values)) != len(values)
                or any(type(seed) is not int or seed < 0 for seed in values)
            ):
                raise ValueError("model and trace seed panels must be nonempty unique nonnegative integers")
        if set(self.validation_seeds) & set(self.test_seeds):
            raise ValueError("validation and fresh-test trace seeds overlap")
        if not self.name or type(self.top_k) is not int or self.top_k < 1:
            raise ValueError("campaign name and positive integer top_k are required")
        if not np.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("shield threshold must be a finite probability")
        if not np.isfinite(self.max_ensemble_std) or not 0 <= self.max_ensemble_std <= 0.5:
            raise ValueError("max_ensemble_std must be finite and in [0, 0.5]")
        tolerances = [
            self.max_id_qoe_drop,
            self.max_id_violation_increase,
            self.max_stress_violation_increase,
            self.max_stress_scenario_violation_increase,
            self.risk_penalty,
            self.minimum_score_gain,
        ]
        if any(not np.isfinite(value) or value < 0 for value in tolerances):
            raise ValueError("selection limits must be finite and nonnegative")
        return self


def _controller_metrics(rows, method):
    selected = [row for row in rows if row["method"] == method]
    if not selected:
        raise ValueError(f"validation data missing controller {method}")
    domains, scenarios = {}, {}
    for domain in ["id", "ood"]:
        group = [row for row in selected if row["domain"] == domain]
        if not group:
            raise ValueError(f"validation data missing {domain} domain for {method}")
        domains[domain] = {
            metric: float(np.mean([row[metric] for row in group])) for metric in ["qoe", "violation_rate"]
        }
    names = {row["scenario"] for row in selected}
    missing = set(SCENARIOS) - names
    if missing:
        raise ValueError(f"validation data missing scenarios for {method}: {sorted(missing)}")
    for name in names:
        group = [row for row in selected if row["scenario"] == name]
        scenarios[name] = {
            metric: float(np.mean([row[metric] for row in group])) for metric in ["qoe", "violation_rate"]
        }
    return dict(
        id_qoe=domains["id"]["qoe"],
        id_violation_rate=domains["id"]["violation_rate"],
        stress_qoe=domains["ood"]["qoe"],
        stress_violation_rate=domains["ood"]["violation_rate"],
        scenarios=scenarios,
    )


def shield_score(metrics, risk_penalty):
    return 0.5 * (metrics["id_qoe"] + metrics["stress_qoe"]) - risk_penalty * metrics["stress_violation_rate"]


def select_shield_candidate(
    rows,
    protocol,
    reference_method=REFERENCE_METHOD,
    candidate_method=CANDIDATE_METHOD,
):
    """Apply the frozen promotion rule using validation rows only."""
    baseline = _controller_metrics(rows, reference_method)
    candidate = _controller_metrics(rows, candidate_method)
    stress_names = [name for name, domain in SCENARIOS.items() if domain == "ood"]
    deltas = {
        name: candidate["scenarios"][name]["violation_rate"] - baseline["scenarios"][name]["violation_rate"]
        for name in stress_names
    }
    feasible = (
        candidate["id_qoe"] >= baseline["id_qoe"] - protocol.max_id_qoe_drop
        and candidate["id_violation_rate"]
        <= baseline["id_violation_rate"] + protocol.max_id_violation_increase
        and candidate["stress_violation_rate"]
        <= baseline["stress_violation_rate"] + protocol.max_stress_violation_increase
        and all(delta <= protocol.max_stress_scenario_violation_increase for delta in deltas.values())
    )
    baseline_score = shield_score(baseline, protocol.risk_penalty)
    candidate_score = shield_score(candidate, protocol.risk_penalty)
    score_gain = candidate_score - baseline_score
    promoted = feasible and score_gain > protocol.minimum_score_gain
    return dict(
        selected_controller=candidate_method if promoted else reference_method,
        reference_method=reference_method,
        candidate_method=candidate_method,
        candidate_promoted=promoted,
        candidate_feasible=feasible,
        baseline_metrics=baseline,
        candidate_metrics=candidate,
        baseline_score=baseline_score,
        candidate_score=candidate_score,
        score_gain=score_gain,
        stress_scenario_violation_deltas=deltas,
        selection_split="validation",
        validation_seeds=protocol.validation_seeds,
        test_seeds=protocol.test_seeds,
        protocol=asdict(protocol),
    )


def _identity(protocol, settings_path, models, reference_models=None):
    trained = audit_directory(models, "trained")
    checkpoint_hashes = {
        str(seed): sha256(models / "models" / f"seed_{seed}.json") for seed in protocol.model_seeds
    }
    if any(
        trained["artifacts_sha256"].get(f"models/seed_{seed}.json") != digest
        for seed, digest in checkpoint_hashes.items()
    ):
        raise ValueError("candidate checkpoint integrity check failed")
    identity = dict(
        protocol=asdict(protocol),
        settings_sha256=sha256(settings_path),
        source_config_sha256=sha256(models / "config.json"),
        source_manifest_sha256=sha256(models / "manifest.json"),
        model_sha256=checkpoint_hashes,
        implementation_sha256={name: sha256(path) for name, path in sorted(source_files().items())},
    )
    if reference_models is not None and reference_models.resolve() != models.resolve():
        reference_models = reference_models.resolve()
        reference = audit_directory(reference_models, "trained")
        reference_hashes = {
            str(seed): sha256(reference_models / "models" / f"seed_{seed}.json")
            for seed in protocol.model_seeds
        }
        if any(
            reference["artifacts_sha256"].get(f"models/seed_{seed}.json") != digest
            for seed, digest in reference_hashes.items()
        ):
            raise ValueError("reference checkpoint integrity check failed")
        if (
            load_config(reference_models / "config.json").digest()
            != load_config(models / "config.json").digest()
        ):
            raise ValueError("reference and candidate simulator/configuration must match")
        identity.update(
            reference_model_sha256=reference_hashes,
            reference_manifest_sha256=sha256(reference_models / "manifest.json"),
            reference_config_sha256=sha256(reference_models / "config.json"),
        )
    return identity


def _evaluation_config(base, protocol, trace_seeds, stage, methods):
    return replace(
        base,
        name=f"{protocol.name}-{stage}",
        seeds=protocol.model_seeds,
        test_seeds=trace_seeds,
        methods=methods.copy(),
        gate=replace(base.gate, max_ensemble_std=protocol.max_ensemble_std),
    ).validate()


def write_shield_diagnostics(run, method=CANDIDATE_METHOD, filename="shield_diagnostics.csv"):
    """Stream action replacements and one-step outcomes into model-seed summaries."""

    def unsafe(value):
        return str(value).strip().lower() not in {"true", "1"}

    grouped = defaultdict(
        lambda: dict(
            steps=0,
            interventions=0,
            no_safe_candidates=0,
            uncertainty_abstentions=0,
            budget_abstentions=0,
            budget_interventions=0,
            budget_rejections=0,
            budget_sum=0.0,
            budget_count=0,
            action_uncertainty_sum=0.0,
            action_uncertainty_count=0,
            proposal_unsafe=0,
            executed_unsafe=0,
            intervened_proposal_unsafe=0,
            intervened_executed_unsafe=0,
        )
    )
    with gzip.open(Path(run) / "steps.csv.gz", "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["method"] != method:
                continue
            counts = grouped[row["domain"], int(row["model_seed"])]
            proposal_unsafe, executed_unsafe = unsafe(row["proposal_safe"]), unsafe(row["safe"])
            counts["steps"] += 1
            counts["proposal_unsafe"] += proposal_unsafe
            counts["executed_unsafe"] += executed_unsafe
            if row["reason"] == "shielded_action":
                counts["interventions"] += 1
                counts["intervened_proposal_unsafe"] += proposal_unsafe
                counts["intervened_executed_unsafe"] += executed_unsafe
            if row["reason"] == "no_safe_candidate":
                counts["no_safe_candidates"] += 1
            if row["reason"] == "uncertainty_abstention":
                counts["uncertainty_abstentions"] += 1
            counts["budget_abstentions"] += row["reason"] == "budget_abstention"
            counts["budget_interventions"] += str(row.get("budget_intervention", "")).lower() in {"true", "1"}
            counts["budget_rejections"] += int(row.get("budget_rejections") or 0)
            budget = row.get("action_budget_mbps")
            if budget not in {None, ""} and np.isfinite(float(budget)):
                counts["budget_sum"] += float(budget)
                counts["budget_count"] += 1
            value = row.get("action_uncertainty")
            if value not in {None, ""} and np.isfinite(float(value)):
                counts["action_uncertainty_sum"] += float(value)
                counts["action_uncertainty_count"] += 1

    summaries = []
    for (domain, seed), counts in sorted(grouped.items()):
        steps, interventions = counts["steps"], counts["interventions"]
        if not steps:
            continue
        summaries.append(
            dict(
                domain=domain,
                model_seed=seed,
                steps=steps,
                intervention_rate=interventions / steps,
                no_safe_candidate_rate=counts["no_safe_candidates"] / steps,
                uncertainty_abstention_rate=counts["uncertainty_abstentions"] / steps,
                budget_abstention_rate=counts["budget_abstentions"] / steps,
                budget_intervention_rate=counts["budget_interventions"] / steps,
                mean_budget_rejections=counts["budget_rejections"] / steps,
                mean_action_budget_mbps=(
                    counts["budget_sum"] / counts["budget_count"] if counts["budget_count"] else None
                ),
                mean_action_uncertainty=(
                    counts["action_uncertainty_sum"] / counts["action_uncertainty_count"]
                    if counts["action_uncertainty_count"]
                    else None
                ),
                proposal_violation_rate=counts["proposal_unsafe"] / steps,
                executed_violation_rate=counts["executed_unsafe"] / steps,
                intervention_proposal_violation_rate=(
                    counts["intervened_proposal_unsafe"] / interventions if interventions else None
                ),
                intervention_executed_violation_rate=(
                    counts["intervened_executed_unsafe"] / interventions if interventions else None
                ),
                interventions=interventions,
            )
        )
    if not summaries:
        raise ValueError("final run has no shield-controller step diagnostics")
    write_csv(Path(run) / filename, summaries)


def run_safety_shield(settings_path, models, out, plots=True, reference_models=None):
    settings_path = Path(settings_path).resolve()
    protocol = ShieldProtocol(**json.loads(settings_path.read_text())).validate()
    models, out = Path(models).resolve(), Path(out).resolve()
    reference_models = Path(reference_models).resolve() if reference_models is not None else models
    base = load_config(models / "config.json")
    reference_config = load_config(reference_models / "config.json")
    if reference_config.digest() != base.digest():
        raise ValueError("reference and candidate model runs must use the same resolved experiment config")
    if not set(protocol.model_seeds) <= set(base.seeds):
        raise ValueError("source checkpoints are missing declared model seeds")
    if set(protocol.validation_seeds) & set(protocol.test_seeds):
        raise ValueError("validation and test trace panels overlap")
    if (set(protocol.validation_seeds) | set(protocol.test_seeds)) & set(base.test_seeds):
        raise ValueError("v5 panels must not reuse source-model test traces")
    if protocol.threshold != base.gate.threshold or protocol.top_k != base.gate.shield_top_k:
        raise ValueError("frozen screen threshold/top_k must match the source model configuration")
    identity = _identity(protocol, settings_path, models, reference_models)
    if out.exists():
        marker = out / "campaign.json"
        if not marker.is_file() or json.loads(marker.read_text()) != identity:
            raise ValueError(
                "campaign source/settings changed or output is partial; preserve it and use a new directory"
            )
    else:
        out.mkdir(parents=True)
        dump_json(out / "campaign.json", identity)
        (out / "settings.json").write_bytes(settings_path.read_bytes())
        (out / "base_config.json").write_bytes((models / "config.json").read_bytes())

    baseline_map = {REFERENCE_METHOD: reference_models}
    validation_config = _evaluation_config(
        base, protocol, protocol.validation_seeds, "validation", [REFERENCE_METHOD, CANDIDATE_METHOD]
    )
    validation = out / "validation"
    complete_evaluation(
        validation_config, models, validation, "validation", plots=False, model_map=baseline_map
    )
    selection = select_shield_candidate(read_episodes(validation / "episodes.csv"), protocol)
    selection["validation_manifest_sha256"] = sha256(validation / "manifest.json")
    selection["baseline_model_sha256"] = identity.get("reference_model_sha256", identity["model_sha256"])
    if reference_models != models:
        selection["candidate_model_sha256"] = identity["model_sha256"]
    selection_path = out / "selection.json"
    if selection_path.exists():
        if json.loads(selection_path.read_text()) != selection:
            raise ValueError("locked shield selection changed; do not overwrite it")
    else:
        dump_json(selection_path, selection)
    print(
        f"LOCKED shield decision={selection['selected_controller']} "
        f"promote_candidate={selection['candidate_promoted']} before fresh-test evaluation",
        flush=True,
    )

    final_config = _evaluation_config(base, protocol, protocol.test_seeds, "test", TEST_METHODS)
    final = out / "test"
    if final.exists():
        final_manifest = audit_directory(final, "complete")
        if not final_config.digest_matches(final_manifest["config_sha256"]):
            raise ValueError("final shield test does not match the locked protocol")
        if final_manifest.get("evaluation_split") != "test":
            raise ValueError("final shield run is not a fresh test evaluation")
        if sha256(final / "selection.json") != sha256(selection_path):
            raise ValueError("final test does not retain the locked validation selection")
    else:
        evaluate_experiment(
            final_config,
            models,
            final,
            split="test",
            model_map=baseline_map,
        )
        (final / "selection.json").write_bytes(selection_path.read_bytes())
        build_report(final, plots=plots)
        write_shield_diagnostics(final)
        manifest(
            final,
            final_config,
            "complete",
            extra={
                "selection_sha256": sha256(selection_path),
                "campaign_sha256": sha256(out / "campaign.json"),
            },
        )
    dump_json(
        out / "status.json",
        dict(
            stage="complete",
            selected_controller=selection["selected_controller"],
            selection_sha256=sha256(selection_path),
            final_manifest_sha256=sha256(final / "manifest.json"),
        ),
    )
    return final
