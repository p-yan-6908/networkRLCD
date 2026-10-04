"""Frozen-policy-budget domain-randomization study with validation-locked promotion."""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from .config import load_config
from .experiment import (
    dump_json,
    evaluate_experiment,
    manifest,
    sha256,
    source_files,
    train_experiment,
)
from .improvement import audit_directory, complete_evaluation
from .reporting import build_report, read_episodes
from .scenarios import SCENARIOS

METHODS = ["safe", "heuristic", "gcc", "rl", "calibrated_v1", "calibrated", "uncalibrated"]
MODEL_METHODS = ["rl", "calibrated_v1"]
REFERENCE_METHOD = "calibrated_v1"
CANDIDATE_METHOD = "calibrated"


@dataclass(frozen=True)
class PolicyRandomizationProtocol:
    name: str
    base_config: str
    model_seeds: list[int]
    validation_seeds: list[int]
    test_seeds: list[int]
    policy_training_scenarios: list[str]
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
                or any(type(seed) is not int or seed < 0 for seed in values)
            ):
                raise ValueError("model and trace seed panels must be nonempty, unique nonnegative integers")
        if set(self.validation_seeds) & set(self.test_seeds):
            raise ValueError("validation and final-test trace seeds overlap")
        if not self.base_config or not self.name:
            raise ValueError("campaign and base-config names are required")
        if not self.policy_training_scenarios or any(
            not isinstance(name, str) or name not in SCENARIOS for name in self.policy_training_scenarios
        ):
            raise ValueError("policy-training schedule must contain known scenario names")
        if not any(SCENARIOS[name] == "id" for name in self.policy_training_scenarios) or not any(
            SCENARIOS[name] == "ood" for name in self.policy_training_scenarios
        ):
            raise ValueError("policy-training schedule must cover both ID and stress families")
        tolerances = [
            self.max_id_qoe_drop,
            self.max_id_violation_increase,
            self.max_stress_violation_increase,
            self.max_stress_scenario_violation_increase,
            self.risk_penalty,
            self.minimum_score_gain,
        ]
        if any(not np.isfinite(value) or value < 0 for value in tolerances):
            raise ValueError("selection tolerances must be finite and nonnegative")
        if type(self.bootstrap_samples) is not int or self.bootstrap_samples < 20:
            raise ValueError("bootstrap_samples must be at least 20")
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


def policy_score(metrics, penalty):
    return 0.5 * (metrics["id_qoe"] + metrics["stress_qoe"]) - penalty * metrics["stress_violation_rate"]


def select_policy_candidate(rows, protocol):
    """Lock a single policy-mix candidate from validation results only."""
    baseline = _controller_metrics(rows, REFERENCE_METHOD)
    candidate = _controller_metrics(rows, CANDIDATE_METHOD)
    stress_names = [name for name, domain in SCENARIOS.items() if domain == "ood"]
    missing = set(stress_names) - candidate["scenarios"].keys()
    if missing or set(stress_names) - baseline["scenarios"].keys():
        raise ValueError(f"validation data missing stress families: {sorted(missing)}")
    deltas = {
        name: candidate["scenarios"][name]["violation_rate"] - baseline["scenarios"][name]["violation_rate"]
        for name in stress_names
    }
    baseline_score = policy_score(baseline, protocol.risk_penalty)
    candidate_score = policy_score(candidate, protocol.risk_penalty)
    feasible = (
        candidate["id_qoe"] >= baseline["id_qoe"] - protocol.max_id_qoe_drop
        and candidate["id_violation_rate"]
        <= baseline["id_violation_rate"] + protocol.max_id_violation_increase
        and candidate["stress_violation_rate"]
        <= baseline["stress_violation_rate"] + protocol.max_stress_violation_increase
        and all(delta <= protocol.max_stress_scenario_violation_increase for delta in deltas.values())
    )
    score_gain = candidate_score - baseline_score
    promote = feasible and score_gain > protocol.minimum_score_gain
    return dict(
        selected_controller=CANDIDATE_METHOD if promote else REFERENCE_METHOD,
        candidate_promoted=promote,
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


def _identity(protocol, settings_path, base_config_path, source_models):
    baseline_manifest = audit_directory(source_models, "trained")
    model_hashes = {
        str(seed): sha256(source_models / "models" / f"seed_{seed}.json") for seed in protocol.model_seeds
    }
    if any(
        baseline_manifest["artifacts_sha256"].get(f"models/seed_{seed}.json") != digest
        for seed, digest in model_hashes.items()
    ):
        raise ValueError("baseline checkpoint hashes do not match the audited source manifest")
    hashes = {name: sha256(path) for name, path in source_files().items()}
    return dict(
        protocol=asdict(protocol),
        settings_sha256=sha256(settings_path),
        base_config_sha256=sha256(base_config_path),
        baseline_config_sha256=sha256(source_models / "config.json"),
        baseline_manifest_sha256=sha256(source_models / "manifest.json"),
        baseline_model_sha256=model_hashes,
        source_sha256=hashes,
    )


def _evaluation_config(base, protocol, trace_seeds):
    return replace(
        base,
        name=protocol.name,
        seeds=protocol.model_seeds,
        test_seeds=trace_seeds,
        methods=METHODS.copy(),
        bootstrap_samples=protocol.bootstrap_samples,
    ).validate()


def run_policy_randomization(settings_path, source_models, out, plots=True):
    settings_path = Path(settings_path).resolve()
    settings = json.loads(settings_path.read_text())
    protocol = PolicyRandomizationProtocol(**settings).validate()
    base_config_path = (settings_path.parent / protocol.base_config).resolve()
    base = load_config(base_config_path)
    source_models, out = Path(source_models).resolve(), Path(out).resolve()
    if not set(protocol.model_seeds) <= set(base.seeds):
        raise ValueError("source baseline lacks one or more declared model seeds")
    if (set(protocol.validation_seeds) | set(protocol.test_seeds)) & set(base.test_seeds):
        raise ValueError("v4 validation/test panels must not reuse the v1 evaluation seeds")
    identity = _identity(protocol, settings_path, base_config_path, source_models)
    if out.exists():
        marker = out / "campaign.json"
        if not marker.is_file() or json.loads(marker.read_text()) != identity:
            raise ValueError(
                "campaign input/source changed or directory is partial; preserve it and use a new output"
            )
    else:
        out.mkdir(parents=True)
        dump_json(out / "campaign.json", identity)
        (out / "settings.json").write_bytes(settings_path.read_bytes())
        (out / "base_config.json").write_bytes(base_config_path.read_bytes())

    train_config = replace(
        base,
        name=f"{protocol.name}-training",
        seeds=protocol.model_seeds,
        policy_training_scenarios=protocol.policy_training_scenarios,
    ).validate()
    training = out / "training"
    if training.exists():
        data = audit_directory(training, "trained")
        if data["config_sha256"] != train_config.digest():
            raise ValueError("completed policy-mix training does not match the frozen config")
    else:
        train_experiment(train_config, training)
    baseline_map = {method: source_models for method in MODEL_METHODS}

    validation_config = _evaluation_config(base, protocol, protocol.validation_seeds)
    validation = out / "validation"
    complete_evaluation(
        validation_config, training, validation, "validation", plots=False, model_map=baseline_map
    )
    rows = read_episodes(validation / "episodes.csv")
    selection = select_policy_candidate(rows, protocol)
    selection["validation_manifest_sha256"] = sha256(validation / "manifest.json")
    selection["baseline_model_sha256"] = identity["baseline_model_sha256"]
    selection_path = out / "selection.json"
    if selection_path.exists():
        if json.loads(selection_path.read_text()) != selection:
            raise ValueError("locked v4 validation selection changed; do not overwrite it")
    else:
        dump_json(selection_path, selection)
    print(
        f"LOCKED v4 decision={selection['selected_controller']} "
        f"promote_candidate={selection['candidate_promoted']} before fresh-test evaluation",
        flush=True,
    )

    test_config = _evaluation_config(base, protocol, protocol.test_seeds)
    final = out / "test"
    if final.exists():
        data = audit_directory(final, "complete")
        if (
            not test_config.digest_matches(data["config_sha256"])
            or data.get("evaluation_split") != "test"
            or (final / "selection.json").read_bytes() != selection_path.read_bytes()
        ):
            raise ValueError("final v4 test does not match locked selection and frozen config")
    else:
        evaluate_experiment(test_config, training, final, split="test", model_map=baseline_map)
        (final / "selection.json").write_bytes(selection_path.read_bytes())
        build_report(final, plots=plots)
        manifest(final, test_config, "complete")
    dump_json(
        out / "status.json",
        dict(
            stage="complete",
            selected_controller=selection["selected_controller"],
            candidate_promoted=selection["candidate_promoted"],
            selection_sha256=sha256(selection_path),
            validation_manifest_sha256=sha256(validation / "manifest.json"),
            final_manifest_sha256=sha256(final / "manifest.json"),
        ),
    )
    return final
