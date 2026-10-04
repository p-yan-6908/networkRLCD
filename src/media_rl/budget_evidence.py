"""Audited budget tables, matched ablations and machine-readable paired estimates."""

import json

from .budget_shield import ABLATION_METHOD, CANDIDATE_METHOD, REFERENCE_METHOD
from .evidence import csv_rows, finite, matched_method_contrast, selected_action_calibration_table, tex_table
from .metrics import cluster_interval
from .scenarios import SCENARIOS


def budget_tables(
    run,
    config,
    selection,
    episodes,
    *,
    methods=(REFERENCE_METHOD, CANDIDATE_METHOD, ABLATION_METHOD),
    version="V8",
    extra_references=(),
):
    """Audited budget studies; the default preserves all V8 output semantics."""
    REFERENCE_METHOD, CANDIDATE_METHOD, ABLATION_METHOD = methods
    bootstrap_seed = 808 if version == "V8" else 909
    bs = chr(92)
    labels = {
        "shielded_uncertainty": "V7 disagreement screen",
        "shielded_budget": "V8 budget + confidence",
        "budget_only": "Budget without confidence",
        "shielded_delay_budget": "V9 delay budget + confidence",
        "delay_budget_only": "Delay budget without confidence",
        "gcc": "GCC-like",
    }
    summary = {
        (row["group"], row["method"], row["metric"]): row
        for row in csv_rows(run / "summary.csv")
        if row["scope"] == "domain"
    }
    rows = []
    for method, metrics, score, decision in [
        (REFERENCE_METHOD, selection["baseline_metrics"], selection["baseline_score"], "Reference"),
        (
            CANDIDATE_METHOD,
            selection["candidate_metrics"],
            selection["candidate_score"],
            "Promoted" if selection["candidate_promoted"] else "Not promoted",
        ),
    ]:
        rows.append(
            [
                labels[method],
                f"{finite(metrics['id_qoe']):.3f}",
                f"{finite(metrics['id_violation_rate']) * 100:.3f}",
                f"{finite(metrics['stress_qoe']):.3f}",
                f"{finite(metrics['stress_violation_rate']) * 100:.3f}",
                f"{finite(score):.4f}",
                decision,
            ]
        )
    outputs = {
        "table_budget_shield_selection.tex": tex_table(
            [
                "Validation controller",
                "ID QoE",
                "ID unsafe (pct)",
                "Stress QoE",
                "Stress unsafe (pct)",
                "Score",
                "Decision",
            ],
            rows,
        )
    }
    limit = finite(selection["protocol"]["max_stress_scenario_violation_increase"])
    outputs["table_budget_shield_families.tex"] = tex_table(
        ["Stress family", f"{version} minus V7 unsafe (pp)", "Maximum increase (pp)", "Constraint"],
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
    contrasts, contrast_rows = [], []
    for domain in ["id", "ood"]:
        for reference in [REFERENCE_METHOD, *extra_references, ABLATION_METHOD, "gcc"]:
            for metric, scale in [("qoe", 1), ("violation_rate", 100)]:
                result = matched_method_contrast(
                    episodes,
                    domain,
                    CANDIDATE_METHOD,
                    reference,
                    metric,
                    config.bootstrap_samples,
                    seed=bootstrap_seed,
                )
                if not result["n"]:
                    raise ValueError(f"missing {version} paired contrast: {domain}/{reference}/{metric}")
                contrasts.append(dict(domain=domain, reference=reference, metric=metric, **result))
                precision = (
                    (5 if metric == "qoe" else 4) if version == "V9" else (4 if metric == "qoe" else 3)
                )
                text = f"{result['mean'] * scale:+.{precision}f}"
                if result["low"] is not None:
                    text += (
                        f" [{result['low'] * scale:+.{precision}f}, {result['high'] * scale:+.{precision}f}]"
                    )
                contrast_rows.append(
                    [
                        "ID" if domain == "id" else "Stress",
                        labels[reference],
                        metric.replace("_", " "),
                        text,
                    ]
                )
    outputs["table_budget_shield_contrasts.tex"] = tex_table(
        ["Domain", "Reference", "Metric", f"{version} minus reference [model-seed interval]"], contrast_rows
    )
    diagnostic_rows, diagnostics = [], []
    for method, filename in [
        (CANDIDATE_METHOD, "shield_diagnostics.csv"),
        (ABLATION_METHOD, f"{ABLATION_METHOD}_diagnostics.csv"),
    ]:
        data = csv_rows(run / filename)
        for domain in ["id", "ood"]:
            for metric, label, scale in [
                ("budget_intervention_rate", "Budget changes eligible choice (pct)", 100),
                ("budget_abstention_rate", "Budget abstention (pct)", 100),
                ("intervention_rate", "Action replacement (pct)", 100),
                ("mean_action_budget_mbps", "Mean wire budget (Mbps)", 1),
            ]:
                values = [
                    finite(row[metric])
                    for row in data
                    if row["domain"] == domain and row.get(metric) not in {None, ""}
                ]
                estimate = cluster_interval(values, config.bootstrap_samples, seed=bootstrap_seed)
                diagnostics.append(dict(method=method, domain=domain, metric=metric, **estimate))
                text = "--" if estimate["mean"] is None else f"{estimate['mean'] * scale:.3f}"
                if estimate["low"] is not None:
                    text += f" [{estimate['low'] * scale:.3f}, {estimate['high'] * scale:.3f}]"
                diagnostic_rows.append(
                    [
                        "ID" if domain == "id" else "Stress",
                        labels[method],
                        label,
                        text,
                    ]
                )
    outputs["table_budget_shield_diagnostics.tex"] = tex_table(
        ["Domain", "Controller", "Step diagnostic", "Mean [model-seed interval]"], diagnostic_rows
    )
    scenario_summary = {
        (row["group"], row["method"], row["metric"]): row
        for row in csv_rows(run / "summary.csv")
        if row["scope"] == "scenario"
    }
    for reference in [REFERENCE_METHOD, *extra_references]:
        scenario_rows = []
        reference_version = "V7" if reference == REFERENCE_METHOD else "V8"
        for name in config.scenarios:
            row = ["ID" if SCENARIOS[name] == "id" else "Stress", name.replace("_", bs + "_")]
            for metric, scale in [("qoe", 1), ("violation_rate", 100)]:
                baseline = finite(scenario_summary[name, reference, metric]["mean"]) * scale
                candidate = finite(scenario_summary[name, CANDIDATE_METHOD, metric]["mean"]) * scale
                row.extend([f"{baseline:.3f}", f"{candidate:.3f}", f"{candidate - baseline:+.3f}"])
            scenario_rows.append(row)
        suffix = "" if reference == REFERENCE_METHOD else "_v8"
        outputs[f"table_budget_shield_scenarios{suffix}.tex"] = tex_table(
            [
                "Panel",
                "Scenario",
                f"{reference_version} QoE",
                f"{version} QoE",
                "Delta",
                f"{reference_version} unsafe (pct)",
                f"{version} unsafe (pct)",
                "Delta (pp)",
            ],
            scenario_rows,
        )
    outputs["table_budget_shield_calibration.tex"] = selected_action_calibration_table(
        run / "steps.csv.gz", config, method=CANDIDATE_METHOD
    )
    outputs["table_budget_only_calibration.tex"] = selected_action_calibration_table(
        run / "steps.csv.gz", config, method=ABLATION_METHOD
    )
    outputs["budget_results.json"] = (
        json.dumps(
            dict(
                selection=selection,
                contrasts=contrasts,
                diagnostics=diagnostics,
                domain_means=[
                    dict(domain=domain, method=method, metric=metric, mean=finite(row["mean"]))
                    for (domain, method, metric), row in sorted(summary.items())
                    if metric in {"qoe", "violation_rate", "fallback_rate"}
                ],
                units={"violation_rate": "fraction", "qoe": "synthetic reward per interval"},
                limitations=[
                    "Fixed known-family trace panel; model-seed bootstrap only.",
                    "Budget is a telemetry heuristic, not measured capacity or a safety certificate.",
                    "Budget-only retains Q ranking and the learned support guard.",
                ],
            ),
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    if version == "V9":
        outputs = {
            (
                "delay_budget_results.json"
                if name == "budget_results.json"
                else name.replace("budget_shield", "delay_budget").replace("budget_only", "delay_budget_only")
            ): text
            for name, text in outputs.items()
        }
    return outputs
