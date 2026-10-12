"""Export compact, verified synthetic acceptance and native observability tables."""

import argparse
import json
from pathlib import Path

import numpy as np

from media_rl.native_margin_pilot_report import compare
from media_rl.native_turn_probe import sha


def write_export(root, inputs, table):
    root = Path(root)
    if root.exists():
        raise ValueError("fresh paper export required")
    root.mkdir()
    (root / "table.tex").write_text(table)
    provenance = dict(
        abi="development_update_paper_export_v1",
        input_sha256={p: sha(p) for p in inputs},
        exporter_sha256=sha(__file__),
        table_sha256=sha(root / "table.tex"),
        no_capture_or_training_launched=True,
    )
    (root / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")


def export_native_action_diagnostic(root):
    diagnostic_root = Path("reports/native-turn-action-diagnostic-v1")
    report_path = diagnostic_root / "report.json"
    analysis_provenance_path = diagnostic_root / "provenance.json"
    spec_path = Path("configs/native_turn_action_diagnostic_v1.json")
    report = json.loads(report_path.read_text())
    analysis_provenance = json.loads(analysis_provenance_path.read_text())
    if (
        report.get("abi") != "native_turn_action_diagnostic_v1_report"
        or report.get("analysis_status") != "post_capture_exploratory"
        or report.get("native_factual_only") is not True
        or report.get("native_counterfactuals") is not False
        or report.get("controller_promoted") is not False
        or report.get("real_network_validation") is not False
        or report.get("raw_evidence_provenance", {}).get("capture_bytes_unmodified") is not True
        or sha(report_path) != analysis_provenance.get("report_sha256")
        or sha(spec_path) != analysis_provenance.get("config_sha256")
        or analysis_provenance.get("analysis_code_sha256") != report.get("analysis_code_sha256")
        or not report.get("reproduction", {}).get("exact_inventory_verified")
        or len(report.get("outcomes", [])) != 2
    ):
        raise ValueError("complete raw-replayed native action diagnostic required")

    payload, delivery = report["outcomes"]
    if payload["name"] != "actual_payload_ratio" or delivery["name"] != "on_time_share":
        raise ValueError("unexpected native diagnostic endpoints")
    arms = report["arms"]

    def p_text(value):
        return f"{value:.6f}"

    arm_rows = []
    for arm in arms:
        on_time_pct = 100 * arm["on_time_share_request_weighted"]
        arm_rows.append(
            f"{arm['ratio']:.2f} & {arm['holds']} & {arm['actual_payload_ratio_mean']:.3f} & "
            f"{arm['on_time_requests']} / {arm['capture_requests']} & {on_time_pct:.1f} \\\\\n"
        )
    arm_table = (
        "\\begin{tabular}{rrrrr}\n\\toprule\nAssigned BWE ratio & Holds & Actual payload / BWE & "
        "On-time / eligible requests & On time (\\%) \\\\\n\\midrule\n"
        + "".join(arm_rows)
        + "\\bottomrule\n\\end{tabular}\n"
    )

    contrast_rows = []
    for result in report["outcomes"]:
        on_time = result["name"] == "on_time_share"
        label = "On-time requests (pp)" if on_time else "Actual payload / assigned BWE"
        scale = 100 if on_time else 1
        for contrast in result["contrasts"]:
            estimate = contrast["estimate"] * scale
            low, high = contrast["ci95_low"] * scale, contrast["ci95_high"] * scale
            contrast_rows.append(
                f"{label} & {contrast['contrast']} & {estimate:+.3f} "
                f"[{low:+.3f}, {high:+.3f}] & {p_text(contrast['p_value_two_sided'])} & "
                f"{p_text(contrast['p_value_holm_all_six'])} \\\\\n"
            )
    contrast_table = (
        "\\begin{tabular}{llrrr}\n\\toprule\nOutcome & Contrast & Difference (95\\% CI) & "
        "$p$ & Holm $p$ \\\\\n\\midrule\n" + "".join(contrast_rows) + "\\bottomrule\n\\end{tabular}\n"
    )

    arm_macros = {
        "NativeTurnActionN": str(report["holds"]),
        "NativeTurnActionPeers": str(report["peer_clusters"]),
        "NativeTurnActionPayloadLow": f"{arms[0]['actual_payload_ratio_mean']:.3f}",
        "NativeTurnActionPayloadMid": f"{arms[1]['actual_payload_ratio_mean']:.3f}",
        "NativeTurnActionPayloadHigh": f"{arms[2]['actual_payload_ratio_mean']:.3f}",
        "NativeTurnActionOntimeLow": f"{100 * arms[0]['on_time_share_request_weighted']:.1f}",
        "NativeTurnActionOntimeMid": f"{100 * arms[1]['on_time_share_request_weighted']:.1f}",
        "NativeTurnActionOntimeHigh": f"{100 * arms[2]['on_time_share_request_weighted']:.1f}",
    }
    evidence = "".join(f"\\newcommand{{\\{name}}}{{{value}}}\n" for name, value in arm_macros.items())
    root = Path(root)
    if root.exists():
        raise ValueError("fresh action-diagnostic paper export required")
    root.mkdir(parents=True)
    outputs = {
        "table_arm_means.tex": arm_table,
        "table_contrasts.tex": contrast_table,
        "evidence.tex": evidence,
    }
    for name, contents in outputs.items():
        (root / name).write_text(contents)
    inputs = [
        report_path,
        analysis_provenance_path,
        spec_path,
        Path("src/media_rl/native_turn_action_diagnostic.py"),
    ]
    provenance = {
        "abi": "native_turn_action_paper_export_v1",
        "input_sha256": {str(path): sha(path) for path in inputs},
        "exporter_sha256": sha(__file__),
        "output_sha256": {name: sha(root / name) for name in outputs},
        "no_capture_or_training_launched": True,
    }
    (root / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")


def main(factual_out, native_out, action_out, action_only=False):
    if action_only:
        export_native_action_diagnostic(action_out)
        return
    factual_root = "reports/typed-factual-acceptance-v1/"
    factual = json.loads(Path(factual_root + "report.json").read_text())
    verification = json.loads(Path(factual_root + "verification.json").read_text())
    if verification["packaged_models_reproduced"] != 18 or verification["summaries_recomputed"] != 18:
        raise ValueError("complete factual reproduction required")
    rows = []
    labels = dict(
        training_families="Training families",
        read_population_r="Read unseen R",
        read_population_s="Read unseen S",
    )
    for row in factual["summaries"]:
        if row["selector"] != "point":
            continue
        mean = row["utility_vs_fixed"]["mean"]
        low, high = row["utility_vs_fixed"]["family_interval95"]
        rows.append(
            f"{row['blocks'] // 1000}k & {labels[row['panel']]} & {mean:+.5f} & "
            f"[{low:+.5f}, {high:+.5f}] & {100 * row['unsafe_vs_fixed']['mean']:+.3f} \\\\\n"
        )
    table = (
        "\\begin{tabular}{llrrr}\n\\toprule\nBlocks & Panel & Utility vs fixed & Family interval & Unsafe pp \\\\\n"
        "\\midrule\n" + "".join(rows) + "\\bottomrule\n\\end{tabular}\n"
    )
    write_export(
        factual_out,
        [
            factual_root + "report.json",
            factual_root + "verification.json",
            "configs/typed_factual_acceptance_v1.json",
        ],
        table,
    )
    native_root = "reports/native-turn-probe-v1/"
    native = json.loads(Path(native_root + "report.json").read_text())
    audit = json.loads(Path(native_root + "independent-audit.json").read_text())
    sessions = json.loads(Path(native_root + "sessions.json").read_text())
    if len(audit["sessions"]) != native["sessions"] or not audit["summaries_recomputed"]:
        raise ValueError("complete native audit required")
    cohorts = [c for s in sessions for c in s["cohorts"]]
    rows = []
    for ratio, level in native["levels"].items():
        own = [c for c in cohorts if c["ratio"] == float(ratio)]
        compare(len(own), level["assigned_holds"], "native counts")
        compare(
            float(np.mean([c["realized_ratio"] for c in own if c["window_complete"]])),
            level["mean_realized_ratio"],
            "native means",
        )
        rows.append(
            f"{ratio} & {level['assigned_holds']} & {level['complete_windows']} & "
            f"{level['aliased_holds']} & {level['mean_realized_ratio']:.3f} \\\\\n"
        )
    table = (
        "\\begin{tabular}{rrrrr}\n\\toprule\nRequested ratio & Assigned & Complete & Aliased & Realised ratio \\\\\n"
        "\\midrule\n" + "".join(rows) + "\\bottomrule\n\\end{tabular}\n"
    )
    write_export(
        native_out,
        [
            native_root + "report.json",
            native_root + "sessions.json",
            native_root + "independent-audit.json",
            "configs/native_turn_probe_v1.json",
        ],
        table,
    )
    export_native_action_diagnostic(action_out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factual-out", type=Path, default=Path("paper/generated-typed-factual-acceptance"))
    parser.add_argument("--native-out", type=Path, default=Path("paper/generated-native-turn-probe"))
    parser.add_argument(
        "--action-out", type=Path, default=Path("paper/generated-native-turn-action-diagnostic-v1")
    )
    parser.add_argument(
        "--action-only",
        action="store_true",
        help="export only the new native action diagnostic (useful when older exports already exist)",
    )
    args = parser.parse_args()
    main(args.factual_out, args.native_out, args.action_out, args.action_only)
