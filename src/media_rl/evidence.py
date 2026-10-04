"""Read-only campaign status and audited, data-linked manuscript exports.

These utilities do not change training, calibration, or controller behavior.
"""

import csv
import gzip
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path

from .config import load_config
from .experiment import dump_json, sha256, validate_bundle
from .training import ModelBundle


def run_status(run):
    run = Path(run)
    config = load_config(run / "config.json")
    ready, errors = [], {}
    for seed in config.seeds:
        path = run / "models" / f"seed_{seed}.json"
        if not path.exists():
            continue
        try:
            bundle = ModelBundle.load(path)
            validate_bundle(bundle, config, seed)
            ready.append(seed)
        except (ValueError, KeyError, IndexError, OSError) as error:
            errors[str(seed)] = str(error)
    manifest_path = run / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except (ValueError, OSError):
            pass  # A status read may race a manifest write; never mutate the run.
    phase = "training"
    if len(ready) == len(config.seeds):
        phase = "trained"
    if (run / "steps.csv.gz").exists():
        phase = "evaluation"
    if (run / "episodes.csv").exists():
        phase = "reporting"
    if manifest.get("stage") == "complete":
        phase = "complete"
    return dict(
        run=str(run.resolve()),
        phase=phase,
        manifest_stage=manifest.get("stage"),
        model_seeds=config.seeds,
        completed_model_seeds=ready,
        checkpoint_errors=errors,
        models_complete=len(ready),
        models_expected=len(config.seeds),
        expected_evaluation_episodes=len(config.seeds)
        * len(config.test_seeds)
        * len(config.scenarios)
        * len(config.methods),
        step_log_bytes=(run / "steps.csv.gz").stat().st_size if (run / "steps.csv.gz").exists() else 0,
        integrity_checked=False,
        note="Filesystem progress, not process liveness. Incomplete may mean running or interrupted. Use audit for integrity.",
    )


def audit_complete_run(run):
    run = Path(run).resolve()
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest.get("stage") != "complete":
        raise ValueError("paper export requires a completed run; partial training/evaluation is not evidence")
    required = {
        "config.json",
        "episodes.csv",
        "summary.csv",
        "calibration_diagnostics.csv",
        "paired_differences.csv",
    }
    hashes = manifest.get("artifacts_sha256", {})
    if not required <= hashes.keys():
        raise ValueError("manifest is missing required paper evidence")
    for name, expected in hashes.items():
        path = (run / name).resolve()
        if not path.is_relative_to(run) or not path.is_file() or sha256(path) != expected:
            raise ValueError(f"artifact integrity check failed: {name}")
    config = load_config(run / "config.json")
    if not config.digest_matches(manifest["config_sha256"]):
        raise ValueError("resolved configuration hash mismatch")
    return config, manifest


def csv_rows(path):
    with Path(path).open() as file:
        return list(csv.DictReader(file))


def finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite paper estimate")
    return number


def matched_method_contrast(
    episodes, domain, candidate_method, reference_method, metric, samples=2000, seed=0
):
    """Bootstrap candidate-minus-reference means by independent training seed."""
    from .metrics import cluster_interval

    index = {(row["model_seed"], row["test_seed"], row["scenario"], row["method"]): row for row in episodes}
    grouped = defaultdict(list)
    for candidate in episodes:
        if candidate["domain"] != domain or candidate["method"] != candidate_method:
            continue
        key = (
            candidate["model_seed"],
            candidate["test_seed"],
            candidate["scenario"],
            reference_method,
        )
        reference = index.get(key)
        if reference is None:
            continue
        candidate_value, reference_value = candidate.get(metric), reference.get(metric)
        if candidate_value in (None, "") or reference_value in (None, ""):
            continue
        difference = float(candidate_value) - float(reference_value)
        if math.isfinite(difference):
            grouped[candidate["model_seed"]].append(difference)
    seed_means = [
        sum(values) / len(values) for _, values in sorted(grouped.items(), key=lambda item: int(item[0]))
    ]
    return cluster_interval(seed_means, samples, seed=seed)


def tex_table(headers, rows):
    bs = chr(92)
    lines = [
        "% Generated from audited evidence; do not hand-edit.",
        bs + "begin{tabular}{" + "l" * len(headers) + "}",
        bs + "toprule",
        " & ".join(headers) + " " + bs * 2,
        bs + "midrule",
    ]
    lines += [" & ".join(row) + " " + bs * 2 for row in rows]
    lines += [bs + "bottomrule", bs + "end{tabular}", ""]
    return "\n".join(lines)


def selected_action_calibration_table(steps_path, config, method="shielded"):
    """Report post-selection confidence against the one-step safety outcome."""
    from .metrics import calibration_metrics, cluster_interval

    data = defaultdict(lambda: {"p": [], "y": []})
    subsets = [
        ("proposal", "Greedy proposal"),
        ("accepted", "Screen-selected action"),
        ("replaced_proposal", "Proposal at replacements"),
        ("replacement", "Selected replacement action"),
    ]

    def binary(value):
        normalized = str(value).strip().lower()
        if normalized in {"true", "1"}:
            return 1.0
        if normalized in {"false", "0"}:
            return 0.0
        raise ValueError(f"invalid safety label in step log: {value!r}")

    def add(domain, seed, subset, probability, label):
        values = data[domain, seed, subset]
        values["p"].append(float(probability))
        values["y"].append(float(label))

    with gzip.open(steps_path, "rt", newline="") as stream:
        rows = csv.DictReader(stream)
        required = {
            "domain",
            "model_seed",
            "method",
            "confidence",
            "action_confidence",
            "reason",
            "proposal_safe",
            "safe",
        }
        if not required <= set(rows.fieldnames or []):
            raise ValueError("v5 step log is missing selected-action confidence or safety labels")
        for row in rows:
            if row["method"] != method:
                continue
            domain, seed = row["domain"], int(row["model_seed"])
            proposal_y, selected_y = binary(row["proposal_safe"]), binary(row["safe"])
            proposal_p = float(row["confidence"]) if row["confidence"] else None
            selected_p = float(row["action_confidence"]) if row["action_confidence"] else None
            if proposal_p is not None:
                add(domain, seed, "proposal", proposal_p, proposal_y)
            # Abstention records may describe a rejected candidate's probability,
            # not the fallback action. Never pair that score with fallback safety.
            if selected_p is not None and row["reason"] in {"accepted", "shielded_action"}:
                add(domain, seed, "accepted", selected_p, selected_y)
                if row["reason"] == "shielded_action":
                    add(domain, seed, "replacement", selected_p, selected_y)
                    if proposal_p is not None:
                        add(domain, seed, "replaced_proposal", proposal_p, proposal_y)

    def interval_text(values, multiplier=1.0):
        estimate = cluster_interval(values, config.bootstrap_samples, seed=505)
        if estimate["mean"] is None:
            return "--"
        mean = estimate["mean"] * multiplier
        if estimate["low"] is None:
            return f"{mean:.2f}"
        return f"{mean:.2f} [{estimate['low'] * multiplier:.2f}, {estimate['high'] * multiplier:.2f}]"

    table_rows = []
    for domain in ["id", "ood"]:
        for subset, label in subsets:
            seed_stats = []
            count = 0
            for seed in config.seeds:
                sample = data[domain, seed, subset]
                probabilities, outcomes = sample["p"], sample["y"]
                count += len(probabilities)
                if not probabilities:
                    continue
                scores = calibration_metrics(probabilities, outcomes)
                mean_confidence = sum(probabilities) / len(probabilities)
                observed_safe = sum(outcomes) / len(outcomes)
                seed_stats.append(
                    {
                        "confidence": mean_confidence,
                        "safe": observed_safe,
                        "overconfidence": mean_confidence - observed_safe,
                        "ece": scores["ece"],
                        "brier": scores["brier"],
                    }
                )
            row = ["ID" if domain == "id" else "OOD", label, f"{count:,}"]
            for metric, scale in [
                ("confidence", 100.0),
                ("safe", 100.0),
                ("overconfidence", 100.0),
                ("ece", 100.0),
                ("brier", 1.0),
            ]:
                row.append(interval_text([stats[metric] for stats in seed_stats], scale))
            table_rows.append(row)
    bs = chr(92)
    return tex_table(
        [
            "Domain",
            "Action subset",
            "Steps",
            "Mean confidence (" + bs + "%)",
            "Observed safe (" + bs + "%)",
            "Confidence minus safe (pp)",
            "ECE (pp)",
            "Brier",
        ],
        table_rows,
    )


def export_paper(run, out, prefix="Evidence"):
    """Write generated LaTeX and a provenance sidecar; never modify source evidence."""
    if not prefix.isascii() or not prefix.isalpha():
        raise ValueError("macro prefix must contain only ASCII letters")
    run, out = Path(run).resolve(), Path(out).resolve()
    if out == run or out.is_relative_to(run):
        raise ValueError("paper export must be outside the immutable experiment directory")
    config, manifest = audit_complete_run(run)
    if (out / "provenance.json").exists():
        previous = json.loads((out / "provenance.json").read_text())
        if previous.get("manifest_sha256") != sha256(run / "manifest.json"):
            raise ValueError("refusing to mix evidence sources; select a new paper export directory")
    episodes = csv_rows(run / "episodes.csv")
    expected = len(config.seeds) * len(config.test_seeds) * len(config.scenarios) * len(config.methods)
    identities = {(r["model_seed"], r["test_seed"], r["scenario"], r["method"]) for r in episodes}
    if len(episodes) != expected or len(identities) != expected:
        raise ValueError("incomplete or duplicate evaluation episodes")
    summary = {
        (r["group"], r["method"], r["metric"]): r
        for r in csv_rows(run / "summary.csv")
        if r["scope"] == "domain"
    }
    diagnostics = {
        (r["domain"], r["kind"]): r
        for r in csv_rows(run / "calibration_diagnostics.csv")
        if r["method"] == "calibrated"
    }
    paired = {(r["domain"], r["reference"], r["metric"]): r for r in csv_rows(run / "paired_differences.csv")}

    def estimate(domain, method, metric):
        try:
            return finite(summary[domain, method, metric]["mean"])
        except KeyError as error:
            raise ValueError(f"missing paper estimate: {domain}/{method}/{metric}") from error

    def interval(row, scale=1):
        value = finite(row["mean"]) * scale
        if not row["low"] or not row["high"]:
            return f"{value:.3f}"
        return f"{value:.3f} [{finite(row['low']) * scale:.3f}, {finite(row['high']) * scale:.3f}]"

    selection_path = run / "selection.json"
    selection_data = json.loads(selection_path.read_text()) if selection_path.exists() else None
    selected_threshold = (
        finite(selection_data["selected_threshold"])
        if selection_data is not None and "selected_threshold" in selection_data
        else config.gate.threshold
    )
    macros = dict(
        EvidenceNumSeeds=str(len(config.seeds)),
        EvidenceNumTraceSeeds=str(len(config.test_seeds)),
        EvidenceNumEpisodes=f"{expected:,}",
        EvidenceNumSteps=f"{expected * config.simulator.steps:,}",
        EvidenceTrainEpisodes=str(config.training.episodes),
        EvidenceHorizon=str(config.simulator.steps),
        EvidenceHidden=str(config.training.hidden),
        EvidenceThreshold=f"{selected_threshold:.2f}",
        EvidenceLabel="Exploratory pilot" if len(config.seeds) < 10 else "Paper-scale descriptive follow-up",
    )
    if selection_data is not None and "selected_threshold" in selection_data:
        selection_protocol = selection_data["protocol"]
        validation_episodes = (
            len(selection_protocol["model_seeds"])
            * len(selection_protocol["validation_seeds"])
            * len(selection_protocol["thresholds"])
            * len(config.scenarios)
        )
        macros["EvidenceValidationEpisodes"] = f"{validation_episodes:,}"
    for domain in ["id", "ood"]:
        for method, label in [("rl", "RL"), ("calibrated", "RLCD"), ("gcc", "GCC")]:
            for metric, suffix, scale in [
                ("qoe", "QoE", 1),
                ("violation_rate", "UnsafePct", 100),
                ("fallback_rate", "FallbackPct", 100),
            ]:
                macros[f"Evidence{domain.upper()}{label}{suffix}"] = (
                    f"{estimate(domain, method, metric) * scale:.3f}"
                )
        if (domain, "calibrated_v1", "qoe") in summary:
            for metric, suffix, scale in [
                ("qoe", "QoE", 1),
                ("violation_rate", "UnsafePct", 100),
                ("fallback_rate", "FallbackPct", 100),
            ]:
                macros[f"Evidence{domain.upper()}Vone{suffix}"] = (
                    f"{estimate(domain, 'calibrated_v1', metric) * scale:.3f}"
                )
            for metric, suffix, scale in [("qoe", "QoE", 1), ("violation_rate", "UnsafePP", 100)]:
                key = (domain, "calibrated_v1", metric)
                if key in paired:
                    macros[f"Evidence{domain.upper()}DeltaVone{suffix}"] = interval(paired[key], scale)
        for kind, label in [("raw", "Raw"), ("reported", "Calibrated")]:
            if (domain, kind) not in diagnostics:
                raise ValueError(f"missing same-state calibration evidence: {domain}/{kind}")
            for metric in ["nll", "brier", "ece"]:
                macros[f"Evidence{domain.upper()}{label}{metric.upper()}"] = (
                    f"{finite(diagnostics[domain, kind][metric]):.5f}"
                )
    bs = chr(92)
    macro_text = "% Generated from a completed, hash-audited experiment.\n"
    macro_text += (
        "\n".join(
            bs + "newcommand{" + bs + key.replace("Evidence", prefix, 1) + "}{" + value + "}"
            for key, value in macros.items()
        )
        + "\n"
    )
    labels = {
        "safe": "Conservative",
        "heuristic": "Heuristic",
        "gcc": "GCC-like",
        "rl": "Double DQN",
        "calibrated": "RLCD",
        "uncalibrated": "Raw-confidence gate",
        "no_ood": "No support gate",
        "no_hysteresis": "No hysteresis",
        "single_model": "Single predictor",
        "shielded": "RLCD action shield",
        "shielded_uncertainty": "V7 disagreement screen",
        "shielded_budget": "V8 budget + confidence",
        "budget_only": "Budget without confidence",
        "shielded_delay_budget": "V9 delay budget + confidence",
        "delay_budget_only": "Delay budget without confidence",
    }
    labels.update(
        calibrated_v1="RLCD v1",
        calibrated_090="RLCD at 0.90",
        id_refit="ID-only refit",
        stress_safe="Stress + safe fallback",
    )
    followup = selection_data is not None

    def domain_label(domain):
        return "Stress" if followup and domain == "ood" else domain.upper()

    comparison = []
    for domain in ["id", "ood"]:
        for method in [
            "safe",
            "heuristic",
            "gcc",
            "rl",
            "calibrated_v1",
            "calibrated_090",
            "calibrated",
            "shielded",
            "shielded_uncertainty",
            "shielded_budget",
            "budget_only",
            "shielded_delay_budget",
            "delay_budget_only",
        ]:
            if method in config.methods:
                comparison.append(
                    [domain_label(domain), labels[method]]
                    + [
                        interval(summary[domain, method, metric], scale)
                        for metric, scale in [("qoe", 1), ("violation_rate", 100), ("fallback_rate", 100)]
                    ]
                )
    calibration = [
        [domain_label(domain), kind, diagnostics[domain, kind]["count"]]
        + [f"{finite(diagnostics[domain, kind][m]):.5f}" for m in ["ece", "brier", "nll"]]
        for domain in ["id", "ood"]
        for kind in ["raw", "reported"]
    ]
    ablations = [
        [labels[m]]
        + [
            f"{estimate(d, m, k) * scale:.3f}"
            for d in ["id", "ood"]
            for k, scale in [("qoe", 1), ("violation_rate", 100), ("fallback_rate", 100)]
        ]
        for m in [
            "calibrated_v1",
            "id_refit",
            "stress_safe",
            "calibrated",
            "uncalibrated",
            "no_ood",
            "no_hysteresis",
            "single_model",
            "shielded",
            "shielded_uncertainty",
            "shielded_budget",
            "budget_only",
            "shielded_delay_budget",
            "delay_budget_only",
        ]
        if m in config.methods
    ]
    contrasts = [
        [domain_label(domain), labels[reference], metric, interval(paired[domain, reference, metric], scale)]
        for domain in ["id", "ood"]
        for reference in ["calibrated_v1", "calibrated_090", "shielded", "rl", "gcc"]
        for metric, scale in [("qoe", 1), ("violation_rate", 100)]
        if (domain, reference, metric) in paired
    ]
    contrasts = [[cell.replace("_", bs + "_") for cell in row] for row in contrasts]
    out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "evidence.tex": macro_text,
        "table_comparison.tex": tex_table(
            ["Domain", "Controller", "QoE", "Unsafe (" + bs + "%)", "Fallback (" + bs + "%)"], comparison
        ),
        "table_calibration.tex": tex_table(
            ["Domain", "Score", "Proposals", "ECE", "Brier", "NLL"], calibration
        ),
        "table_ablations.tex": tex_table(
            [
                "Variant",
                "ID QoE",
                "ID unsafe (" + bs + "%)",
                "ID fallback (" + bs + "%)",
                "OOD QoE",
                "OOD unsafe (" + bs + "%)",
                "OOD fallback (" + bs + "%)",
            ],
            ablations,
        ),
        "table_contrasts.tex": tex_table(
            ["Domain", "Reference", "Metric", "RLCD minus reference"], contrasts
        ),
    }
    if followup:
        outputs["table_ablations.tex"] = outputs["table_ablations.tex"].replace("OOD ", "Stress ")
    if selection_data is not None and selection_data.get("candidate_method") == "shielded":
        selection = selection_data
        baseline = selection["baseline_metrics"]
        candidate = selection["candidate_metrics"]
        decision = "Promoted" if selection["candidate_promoted"] else "Not promoted"
        selection_rows = [
            [
                "RLCD v1 reference",
                f"{finite(baseline['id_qoe']):.3f}",
                f"{finite(baseline['id_violation_rate']) * 100:.3f}",
                f"{finite(baseline['stress_qoe']):.3f}",
                f"{finite(baseline['stress_violation_rate']) * 100:.3f}",
                f"{finite(selection['baseline_score']):.4f}",
                "Reference",
            ],
            [
                "Top-five action shield",
                f"{finite(candidate['id_qoe']):.3f}",
                f"{finite(candidate['id_violation_rate']) * 100:.3f}",
                f"{finite(candidate['stress_qoe']):.3f}",
                f"{finite(candidate['stress_violation_rate']) * 100:.3f}",
                f"{finite(selection['candidate_score']):.4f}",
                decision,
            ],
        ]
        outputs["table_action_shield.tex"] = tex_table(
            [
                "Validation controller",
                "ID QoE",
                "ID unsafe (" + bs + "%)",
                "Stress QoE",
                "Stress unsafe (" + bs + "%)",
                "Selection score",
                "Decision",
            ],
            selection_rows,
        )
        limit = finite(selection["protocol"]["max_stress_scenario_violation_increase"])
        family_rows = [
            [
                name.replace("_", bs + "_"),
                f"{finite(delta) * 100:+.3f}",
                f"{limit * 100:.3f}",
                "Pass" if finite(delta) <= limit else "Fail",
            ]
            for name, delta in sorted(selection["stress_scenario_violation_deltas"].items())
        ]
        outputs["table_action_shield_families.tex"] = tex_table(
            ["Stress family", "Shield minus v1 unsafe (pp)", "Maximum increase (pp)", "Constraint"],
            family_rows,
        )
        shield_contrasts = []
        for domain in ["id", "ood"]:
            for metric, scale in [("qoe", 1), ("violation_rate", 100)]:
                contrast = matched_method_contrast(
                    episodes,
                    domain,
                    "shielded",
                    "calibrated_v1",
                    metric,
                    config.bootstrap_samples,
                )
                if contrast["n"] == 0:
                    raise ValueError(f"missing shield paired contrast: {domain}/{metric}")
                shield_contrasts.append(
                    [domain_label(domain), metric.replace("_", " "), interval(contrast, scale)]
                )
        outputs["table_action_shield_contrasts.tex"] = tex_table(
            ["Domain", "Metric", "Shield minus v1"], shield_contrasts
        )
        from .scenarios import SCENARIOS

        scenario_summary = {
            (row["group"], row["method"], row["metric"]): row
            for row in csv_rows(run / "summary.csv")
            if row["scope"] == "scenario"
        }
        scenario_rows = []
        for name in config.scenarios:
            v1_qoe = scenario_summary[name, "calibrated_v1", "qoe"]
            shield_qoe = scenario_summary[name, "shielded", "qoe"]
            v1_unsafe = scenario_summary[name, "calibrated_v1", "violation_rate"]
            shield_unsafe = scenario_summary[name, "shielded", "violation_rate"]
            scenario_rows.append(
                [
                    domain_label(SCENARIOS[name]),
                    name.replace("_", bs + "_"),
                    f"{finite(v1_qoe['mean']):.3f}",
                    f"{finite(shield_qoe['mean']):.3f}",
                    f"{finite(shield_qoe['mean']) - finite(v1_qoe['mean']):+.3f}",
                    f"{finite(v1_unsafe['mean']) * 100:.3f}",
                    f"{finite(shield_unsafe['mean']) * 100:.3f}",
                    f"{(finite(shield_unsafe['mean']) - finite(v1_unsafe['mean'])) * 100:+.3f}",
                ]
            )
        outputs["table_action_shield_scenarios.tex"] = tex_table(
            [
                "Panel",
                "Scenario",
                "V1 QoE",
                "Shield QoE",
                "Delta",
                "V1 unsafe (" + bs + "%)",
                "Shield unsafe (" + bs + "%)",
                "Delta (pp)",
            ],
            scenario_rows,
        )
        if (run / "shield_diagnostics.csv").is_file():
            from .metrics import cluster_interval

            diagnostics = csv_rows(run / "shield_diagnostics.csv")
            diagnostic_rows = []
            metrics = [
                ("intervention_rate", "Action replacement"),
                ("no_safe_candidate_rate", "No-safe-action fallback"),
                ("proposal_violation_rate", "Greedy proposal unsafe"),
                ("executed_violation_rate", "Executed action unsafe"),
                ("intervention_proposal_violation_rate", "Replaced proposal unsafe"),
                ("intervention_executed_violation_rate", "Replacement action unsafe"),
            ]
            for domain in ["id", "ood"]:
                for metric, label in metrics:
                    values = [
                        finite(row[metric])
                        for row in diagnostics
                        if row["domain"] == domain and row[metric] not in {"", None}
                    ]
                    estimate = cluster_interval(values, config.bootstrap_samples, seed=505)
                    if estimate["mean"] is None:
                        formatted = "not triggered"
                    elif estimate["low"] is None:
                        formatted = f"{estimate['mean'] * 100:.2f}"
                    else:
                        formatted = (
                            f"{estimate['mean'] * 100:.2f} "
                            f"[{estimate['low'] * 100:.2f}, {estimate['high'] * 100:.2f}]"
                        )
                    diagnostic_rows.append([domain_label(domain), label, formatted])
            outputs["table_action_shield_diagnostics.tex"] = tex_table(
                ["Domain", "Step diagnostic", "Rate (" + bs + "%) [model-seed interval]"], diagnostic_rows
            )
            outputs["table_action_selection_calibration.tex"] = selected_action_calibration_table(
                run / "steps.csv.gz", config
            )
    if selection_data is not None and selection_data.get("candidate_method") == "shielded_uncertainty":
        selection = selection_data
        baseline, candidate = selection["baseline_metrics"], selection["candidate_metrics"]
        decision = "Promoted" if selection["candidate_promoted"] else "Not promoted"
        cutoff = finite(selection["protocol"]["max_ensemble_std"])
        outputs["table_uncertainty_shield_selection.tex"] = tex_table(
            [
                "Validation controller",
                "ID QoE",
                "ID unsafe (pp)",
                "Stress QoE",
                "Stress unsafe (pp)",
                "Score",
                "Decision",
            ],
            [
                [
                    "V6 selected-action screen",
                    f"{finite(baseline['id_qoe']):.3f}",
                    f"{finite(baseline['id_violation_rate']) * 100:.3f}",
                    f"{finite(baseline['stress_qoe']):.3f}",
                    f"{finite(baseline['stress_violation_rate']) * 100:.3f}",
                    f"{finite(selection['baseline_score']):.4f}",
                    "Reference",
                ],
                [
                    f"V7 disagreement <= {cutoff:.2f}",
                    f"{finite(candidate['id_qoe']):.3f}",
                    f"{finite(candidate['id_violation_rate']) * 100:.3f}",
                    f"{finite(candidate['stress_qoe']):.3f}",
                    f"{finite(candidate['stress_violation_rate']) * 100:.3f}",
                    f"{finite(selection['candidate_score']):.4f}",
                    decision,
                ],
            ],
        )
        limit = finite(selection["protocol"]["max_stress_scenario_violation_increase"])
        outputs["table_uncertainty_shield_families.tex"] = tex_table(
            ["Stress family", "V7 minus V6 unsafe (pp)", "Maximum increase (pp)", "Constraint"],
            [
                [
                    name.replace("_", bs + "_"),
                    f"{finite(delta) * 100:+.3f}",
                    f"{limit * 100:.3f}",
                    "Pass" if finite(delta) <= limit else "Fail",
                ]
                for name, delta in sorted(selection["stress_scenario_violation_deltas"].items())
            ],
        )
        contrasts = []
        for domain in ["id", "ood"]:
            for metric, scale in [("qoe", 1), ("violation_rate", 100)]:
                contrast = matched_method_contrast(
                    episodes,
                    domain,
                    "shielded_uncertainty",
                    "shielded",
                    metric,
                    config.bootstrap_samples,
                    seed=707,
                )
                if contrast["n"] == 0:
                    raise ValueError(f"missing V7 paired contrast: {domain}/{metric}")
                contrasts.append([domain_label(domain), metric.replace("_", " "), interval(contrast, scale)])
        outputs["table_uncertainty_shield_contrasts.tex"] = tex_table(
            ["Domain", "Metric", "V7 disagreement screen minus V6 screen"], contrasts
        )
        if (run / "shield_diagnostics.csv").is_file():
            from .metrics import cluster_interval

            diagnostics = csv_rows(run / "shield_diagnostics.csv")
            metrics = [
                ("intervention_rate", "Action replacement", 100),
                ("uncertainty_abstention_rate", "Uncertainty abstention", 100),
                ("no_safe_candidate_rate", "No probability-safe candidate", 100),
                ("proposal_violation_rate", "Greedy proposal unsafe", 100),
                ("executed_violation_rate", "Executed action unsafe", 100),
                ("mean_action_uncertainty", "Candidate disagreement", 100),
            ]
            diagnostic_rows = []
            for domain in ["id", "ood"]:
                for metric, label, scale in metrics:
                    values = [
                        finite(row[metric])
                        for row in diagnostics
                        if row["domain"] == domain and row.get(metric) not in {"", None}
                    ]
                    estimate = cluster_interval(values, config.bootstrap_samples, seed=707)
                    if estimate["mean"] is None:
                        formatted = "not triggered"
                    elif estimate["low"] is None:
                        formatted = f"{estimate['mean'] * scale:.2f}"
                    else:
                        formatted = (
                            f"{estimate['mean'] * scale:.2f} "
                            f"[{estimate['low'] * scale:.2f}, {estimate['high'] * scale:.2f}]"
                        )
                    diagnostic_rows.append([domain_label(domain), label, formatted])
            outputs["table_uncertainty_shield_diagnostics.tex"] = tex_table(
                ["Domain", "Step diagnostic", "Percent / disagreement points [model-seed interval]"],
                diagnostic_rows,
            )
    if selection_data is not None and selection_data.get("candidate_method") == "shielded_delay_budget":
        from .budget_evidence import budget_tables
        from .delay_budget import ABLATION_METHOD, CANDIDATE_METHOD, LOSS_BUDGET_METHOD, REFERENCE_METHOD

        outputs.update(
            budget_tables(
                run,
                config,
                selection_data,
                episodes,
                methods=(REFERENCE_METHOD, CANDIDATE_METHOD, ABLATION_METHOD),
                version="V9",
                extra_references=(LOSS_BUDGET_METHOD,),
            )
        )
    if selection_data is not None and selection_data.get("candidate_method") == "shielded_budget":
        from .budget_evidence import budget_tables

        outputs.update(budget_tables(run, config, selection_data, episodes))
    if (
        selection_data is not None
        and "candidate_promoted" in selection_data
        and selection_data.get("candidate_method")
        not in {"shielded", "shielded_uncertainty", "shielded_budget", "shielded_delay_budget"}
    ):
        selection = selection_data
        baseline = selection["baseline_metrics"]
        candidate = selection["candidate_metrics"]
        decision = "Promoted" if selection["candidate_promoted"] else "Not promoted"
        selection_rows = [
            [
                "RLCD v1 reference",
                f"{finite(baseline['id_qoe']):.3f}",
                f"{finite(baseline['id_violation_rate']) * 100:.3f}",
                f"{finite(baseline['stress_qoe']):.3f}",
                f"{finite(baseline['stress_violation_rate']) * 100:.3f}",
                f"{finite(selection['baseline_score']):.4f}",
                "Reference",
            ],
            [
                "Policy-randomized candidate",
                f"{finite(candidate['id_qoe']):.3f}",
                f"{finite(candidate['id_violation_rate']) * 100:.3f}",
                f"{finite(candidate['stress_qoe']):.3f}",
                f"{finite(candidate['stress_violation_rate']) * 100:.3f}",
                f"{finite(selection['candidate_score']):.4f}",
                decision,
            ],
        ]
        outputs["table_policy_randomization.tex"] = tex_table(
            [
                "Validation controller",
                "ID QoE",
                "ID unsafe (" + bs + "%)",
                "Stress QoE",
                "Stress unsafe (" + bs + "%)",
                "Selection score",
                "Decision",
            ],
            selection_rows,
        )
        limit = finite(selection["protocol"]["max_stress_scenario_violation_increase"])
        family_rows = [
            [
                name.replace("_", bs + "_"),
                f"{finite(delta) * 100:+.3f}",
                f"{limit * 100:.3f}",
                "Pass" if finite(delta) <= limit else "Fail",
            ]
            for name, delta in sorted(selection["stress_scenario_violation_deltas"].items())
        ]
        outputs["table_randomization_families.tex"] = tex_table(
            ["Stress family", "Candidate minus v1 unsafe (pp)", "Maximum increase (pp)", "Constraint"],
            family_rows,
        )
        from .scenarios import SCENARIOS

        scenario_summary = {
            (row["group"], row["method"], row["metric"]): row
            for row in csv_rows(run / "summary.csv")
            if row["scope"] == "scenario"
        }
        scenario_rows = []
        for name in config.scenarios:
            v1_qoe = scenario_summary[name, "calibrated_v1", "qoe"]
            v4_qoe = scenario_summary[name, "calibrated", "qoe"]
            v1_unsafe = scenario_summary[name, "calibrated_v1", "violation_rate"]
            v4_unsafe = scenario_summary[name, "calibrated", "violation_rate"]
            dq = finite(v4_qoe["mean"]) - finite(v1_qoe["mean"])
            du = (finite(v4_unsafe["mean"]) - finite(v1_unsafe["mean"])) * 100
            scenario_rows.append(
                [
                    domain_label(SCENARIOS[name]),
                    name.replace("_", bs + "_"),
                    f"{finite(v1_qoe['mean']):.3f}",
                    f"{finite(v4_qoe['mean']):.3f}",
                    f"{dq:+.3f}",
                    f"{finite(v1_unsafe['mean']) * 100:.3f}",
                    f"{finite(v4_unsafe['mean']) * 100:.3f}",
                    f"{du:+.3f}",
                ]
            )
        outputs["table_randomization_scenarios.tex"] = tex_table(
            [
                "Panel",
                "Scenario",
                "V1 QoE",
                "V4 QoE",
                "Delta",
                "V1 unsafe (" + bs + "%)",
                "V4 unsafe (" + bs + "%)",
                "Delta (pp)",
            ],
            scenario_rows,
        )
    if selection_data is not None and "selected_threshold" in selection_data:
        selection = selection_data
        baseline_score = finite(selection["baseline_score"])
        threshold_rows = []
        for item in selection["ranking"]:
            threshold = finite(item["threshold"])
            metrics = item["metrics"]
            score = finite(item["score"])
            decision = (
                "Retained"
                if threshold == selection["selected_threshold"]
                else ("Feasible" if item["feasible"] else "Infeasible")
            )
            threshold_rows.append(
                [
                    f"{threshold:.2f}",
                    decision,
                    f"{finite(metrics['id_qoe']):.3f}",
                    f"{finite(metrics['stress_qoe']):.3f}",
                    f"{finite(metrics['stress_violation_rate']) * 100:.3f}",
                    f"{score:.4f}",
                    f"{score - baseline_score:+.4f}",
                ]
            )
        outputs["table_thresholds.tex"] = tex_table(
            [
                "Gate threshold",
                "Validation decision",
                "ID QoE",
                "Stress QoE",
                "Stress unsafe (" + bs + "%)",
                "Selection score",
                "Score gain vs 0.90",
            ],
            threshold_rows,
        )
    if (run / "confidence_benchmark.csv").exists():
        benchmark = csv_rows(run / "confidence_benchmark.csv")
        benchmark_rows = []
        for domain in ["id", "ood"]:
            for predictor, label in [("v1", "V1"), ("id_refit", "ID refit"), ("stress_safe", "Stress refit")]:
                for kind in ["raw", "calibrated"]:
                    selected = [
                        r
                        for r in benchmark
                        if r["domain"] == domain and r["predictor"] == predictor and r["score"] == kind
                    ]
                    if len(selected) != len(config.seeds):
                        raise ValueError("incomplete same-state predictor benchmark")
                    benchmark_rows.append(
                        [domain_label(domain), label, kind]
                        + [
                            f"{sum(finite(r[k]) for r in selected) / len(selected):.5f}"
                            for k in ["brier", "nll", "ece"]
                        ]
                    )
        outputs["table_predictors.tex"] = tex_table(
            ["Domain", "Predictor", "Score", "Brier", "NLL", "ECE"], benchmark_rows
        )
    for name, text in outputs.items():
        (out / name).write_text(text)
    copied_figures = []
    for name in ["qoe_safety_tradeoff", "reliability", "trajectory_collapse"]:
        relative = f"figures/{name}.pdf"
        if relative in manifest["artifacts_sha256"]:
            (out / "figures").mkdir(exist_ok=True)
            shutil.copy2(run / relative, out / relative)
            copied_figures.append(relative)
    source_files = {
        name: manifest["artifacts_sha256"][name]
        for name in ["summary.csv", "episodes.csv", "calibration_diagnostics.csv", "paired_differences.csv"]
    }
    if (
        "table_action_selection_calibration.tex" in outputs
        or "table_uncertainty_shield_diagnostics.tex" in outputs
    ):
        source_files["steps.csv.gz"] = manifest["artifacts_sha256"]["steps.csv.gz"]
    if "table_uncertainty_shield_selection.tex" in outputs:
        for name in ["selection.json", "shield_diagnostics.csv"]:
            source_files[name] = manifest["artifacts_sha256"][name]
    if "table_budget_shield_selection.tex" in outputs:
        for name in [
            "selection.json",
            "shield_diagnostics.csv",
            "budget_only_diagnostics.csv",
            "steps.csv.gz",
        ]:
            source_files[name] = manifest["artifacts_sha256"][name]
    if "table_delay_budget_selection.tex" in outputs:
        for name in [
            "selection.json",
            "shield_diagnostics.csv",
            "delay_budget_only_diagnostics.csv",
            "steps.csv.gz",
        ]:
            source_files[name] = manifest["artifacts_sha256"][name]
    provenance = dict(
        source_run=str(run),
        macro_prefix=prefix,
        config_sha256=config.digest(),
        manifest_sha256=sha256(run / "manifest.json"),
        integrity_checked=True,
        verified_artifacts=len(manifest["artifacts_sha256"]),
        model_seeds=config.seeds,
        test_seeds=config.test_seeds,
        episodes=expected,
        steps=expected * config.simulator.steps,
        evidence_label=macros["EvidenceLabel"],
        source_files=source_files,
        generated_sha256={name: sha256(out / name) for name in [*outputs, *copied_figures]},
        limitations=[
            "Conditional training-seed bootstrap; fixed trace panel.",
            "No claim of real-network validation or untouched confirmatory data.",
        ],
    )
    dump_json(out / "provenance.json", provenance)
    return provenance
