"""Export compact, verified synthetic acceptance and native observability tables."""

import argparse
import json
from pathlib import Path

import numpy as np

from media_rl.native_margin_pilot_report import compare
from media_rl.native_turn_action_panel_v2 import verify_inventory
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


def export_native_turn_action_assay_v2b(root):
    report_root = Path("reports/native-turn-action-assay-v2b")
    analysis_root = Path("reports/native-turn-action-assay-v2b-analysis")
    spec_path = Path("configs/native_turn_probe_v2_action_assay_inventory_continuation.json")
    capture_report_path = report_root / "report.json"
    sessions_path = report_root / "sessions.json"
    inventory_path = report_root / "local-evidence-inventory.json"
    audit_path = report_root / "independent-audit.json"
    analysis_report_path = analysis_root / "report.json"
    analysis_provenance_path = analysis_root / "provenance.json"
    capture_report = json.loads(capture_report_path.read_text())
    sessions = json.loads(sessions_path.read_text())
    audit = json.loads(audit_path.read_text())
    report = json.loads(analysis_report_path.read_text())
    provenance = json.loads(analysis_provenance_path.read_text())
    spec = json.loads(spec_path.read_text())

    if (
        capture_report.get("abi") != "native_turn_probe_v2_action_assay_v1_report"
        or capture_report.get("sessions") != 64
        or capture_report.get("holds") != 384
        or capture_report.get("controller_promoted") is not False
        or capture_report.get("native_counterfactuals") is not False
        or report.get("abi") != "native_turn_probe_v2_action_assay_v1_action_diagnostic_report"
        or report.get("analysis_status") != "prospective_native_development"
        or report.get("native_factual_only") is not True
        or report.get("native_counterfactuals") is not False
        or report.get("controller_promoted") is not False
        or report.get("real_network_validation") is not False
        or report.get("primary_endpoints_qualified") is not True
        or report.get("all_assigned_rows_retained") is not True
        or report.get("holds") != 384
        or report.get("peer_clusters") != 64
        or report.get("complete_payload_windows") != 384
        or len(sessions) != 64
        or len(audit.get("sessions", [])) != 64
        or audit.get("summaries_recomputed") is not True
        or audit.get("native_factual_only") is not True
        or audit.get("registered_source_hashes_unchanged") is not True
        or audit.get("controller_promoted") is not False
        or audit.get("real_network_validation") is not False
        or report.get("spec_sha256") != sha(spec_path)
        or capture_report.get("spec_sha256") != sha(spec_path)
        or report.get("report_sha256") != sha(capture_report_path)
        or report.get("sessions_sha256") != sha(sessions_path)
        or report.get("inventory_sha256") != sha(inventory_path)
        or report.get("independent_audit_sha256") != sha(audit_path)
        or provenance.get("report_sha256") != sha(analysis_report_path)
        or provenance.get("analysis_code_sha256") != sha(Path("src/media_rl/native_turn_action_panel_v2.py"))
        or provenance.get("analysis_dependency_sha256") != sha(Path("src/media_rl/native_turn_action_diagnostic.py"))
        or provenance.get("registered_capture_sources_sha256") != spec.get("source_sha256")
    ):
        raise ValueError("complete matching V2b capture, independent audit, and analysis are required")

    capture = Path(spec["storage"]["raw_capture_root"]).expanduser().resolve()
    inventory_result = verify_inventory(capture, inventory_path)
    if (
        inventory_result.get("capture_bytes_unmodified") is not True
        or inventory_result.get("capture_file_count") != 323
        or inventory_result.get("inventory_sha256") != report.get("inventory_sha256")
        or inventory_result.get("capture_total_bytes") != report["raw_evidence_provenance"].get("capture_total_bytes")
    ):
        raise ValueError("the full unmodified V2b raw inventory must verify before export")

    outcomes = {row["name"]: row for row in report["outcomes"]}
    if set(outcomes) != {"actual_payload_ratio", "on_time_share"}:
        raise ValueError("unexpected V2b endpoint family")
    arms = report["arms"]
    if [arm["ratio"] for arm in arms] != [0.65, 0.85, 1.05]:
        raise ValueError("unexpected V2b action arms")

    arm_rows = []
    for arm in arms:
        share = 100 * arm["request_weighted_on_time_share"]
        arm_rows.append(
            f"{arm['ratio']:.2f} & {arm['holds']} & {arm['mean_actual_payload_ratio']:.3f} & "
            f"{arm['on_time_requests']} / {arm['capture_requests']} & {share:.1f} \\\\\n"
        )
    arm_table = (
        "\\begin{tabular}{rrrrr}\n\\toprule\nAssigned BWE ratio & Holds & Actual payload / BWE & "
        "On-time / eligible requests & On time (\\%) \\\\\n\\midrule\n"
        + "".join(arm_rows)
        + "\\bottomrule\n\\end{tabular}\n"
    )

    contrast_rows = []
    for name in ("actual_payload_ratio", "on_time_share"):
        result = outcomes[name]
        is_share = name == "on_time_share"
        label = "On-time requests (pp)" if is_share else "Actual payload / assigned BWE"
        scale = 100 if is_share else 1
        for contrast in result["contrasts"]:
            estimate = contrast["estimate"] * scale
            low = contrast["ci95_low"] * scale
            high = contrast["ci95_high"] * scale
            contrast_rows.append(
                f"{label} & {contrast['contrast']} & {estimate:+.3f} "
                f"[{low:+.3f}, {high:+.3f}] & {contrast['p_value_two_sided']:.6g} & "
                f"{contrast['p_value_holm_all_six']:.6g} \\\\\n"
            )
    contrast_table = (
        "\\begin{tabular}{llrrr}\n\\toprule\nOutcome & Contrast & Difference (95\\% CI) & "
        "$p$ & Holm $p$ \\\\\n\\midrule\n"
        + "".join(contrast_rows)
        + "\\bottomrule\n\\end{tabular}\n"
    )

    payload_105_065 = outcomes["actual_payload_ratio"]["contrasts"][1]
    delivery_105_085 = outcomes["on_time_share"]["contrasts"][2]
    macros = {
        "NativeActionVTwoPeers": str(report["peer_clusters"]),
        "NativeActionVTwoHolds": str(report["holds"]),
        "NativeActionVTwoPayloadLow": f"{arms[0]['mean_actual_payload_ratio']:.3f}",
        "NativeActionVTwoPayloadMid": f"{arms[1]['mean_actual_payload_ratio']:.3f}",
        "NativeActionVTwoPayloadHigh": f"{arms[2]['mean_actual_payload_ratio']:.3f}",
        "NativeActionVTwoOntimeLow": f"{100 * arms[0]['request_weighted_on_time_share']:.1f}",
        "NativeActionVTwoOntimeMid": f"{100 * arms[1]['request_weighted_on_time_share']:.1f}",
        "NativeActionVTwoOntimeHigh": f"{100 * arms[2]['request_weighted_on_time_share']:.1f}",
        "NativeActionVTwoPayloadContrast": f"{payload_105_065['estimate']:+.4f}",
        "NativeActionVTwoPayloadLowCI": f"{payload_105_065['ci95_low']:+.4f}",
        "NativeActionVTwoPayloadHighCI": f"{payload_105_065['ci95_high']:+.4f}",
        "NativeActionVTwoPayloadHolm": f"{payload_105_065['p_value_holm_all_six']:.3g}",
        "NativeActionVTwoDeliveryContrast": f"{100 * delivery_105_085['estimate']:+.3f}",
        "NativeActionVTwoDeliveryLowCI": f"{100 * delivery_105_085['ci95_low']:+.3f}",
        "NativeActionVTwoDeliveryHighCI": f"{100 * delivery_105_085['ci95_high']:+.3f}",
        "NativeActionVTwoDeliveryHolm": f"{delivery_105_085['p_value_holm_all_six']:.4f}",
    }
    evidence = "".join(f"\\newcommand{{\\{name}}}{{{value}}}\n" for name, value in macros.items())

    root = Path(root)
    if root.exists():
        raise ValueError("fresh V2b paper export directory required")
    root.mkdir(parents=True)
    outputs = {
        "table_arm_means.tex": arm_table,
        "table_contrasts.tex": contrast_table,
        "evidence.tex": evidence,
    }
    for name, contents in outputs.items():
        (root / name).write_text(contents)
    inputs = [
        capture_report_path,
        sessions_path,
        inventory_path,
        audit_path,
        analysis_report_path,
        analysis_provenance_path,
        spec_path,
        Path("src/media_rl/native_turn_probe_v2.py"),
        Path("src/media_rl/native_turn_action_panel_v2.py"),
        Path("tools/export_development_updates.py"),
    ]
    export_provenance = {
        "abi": "native_turn_action_assay_v2b_paper_export_v1",
        "input_sha256": {str(path): sha(path) for path in inputs},
        "raw_capture_inventory_verified": inventory_result,
        "v2b_outcome_summary_exposed_before_independent_audit": True,
        "v2b_claim_status": "exploratory_development_only",
        "exporter_sha256": sha(__file__),
        "output_sha256": {name: sha(root / name) for name in outputs},
        "no_capture_training_or_counterfactual_launched": True,
    }
    (root / "provenance.json").write_text(json.dumps(export_provenance, indent=2, sort_keys=True) + "\n")


def export_native_turn_action_assay_v3(root):
    report_root = Path("reports/native-turn-action-assay-v3")
    analysis_root = Path("reports/native-turn-action-assay-v3-analysis")
    spec_path = Path("configs/native_turn_probe_v3_action_replication.json")
    capture_report_path = report_root / "report.json"
    sessions_path = report_root / "sessions.json"
    inventory_path = report_root / "local-evidence-inventory.json"
    audit_path = report_root / "independent-audit.json"
    analysis_report_path = analysis_root / "report.json"
    analysis_provenance_path = analysis_root / "provenance.json"
    capture_report = json.loads(capture_report_path.read_text())
    sessions = json.loads(sessions_path.read_text())
    audit = json.loads(audit_path.read_text())
    report = json.loads(analysis_report_path.read_text())
    provenance = json.loads(analysis_provenance_path.read_text())
    spec = json.loads(spec_path.read_text())

    if (
        capture_report.get("abi") != "native_turn_probe_v2_action_assay_v1_report"
        or capture_report.get("sessions") != 64
        or capture_report.get("holds") != 384
        or capture_report.get("controller_promoted") is not False
        or capture_report.get("native_counterfactuals") is not False
        or report.get("abi") != "native_turn_probe_v2_action_assay_v1_action_diagnostic_report"
        or report.get("analysis_status") != "prospective_native_development"
        or report.get("native_factual_only") is not True
        or report.get("native_counterfactuals") is not False
        or report.get("controller_promoted") is not False
        or report.get("real_network_validation") is not False
        or report.get("primary_endpoints_qualified") is not True
        or report.get("all_assigned_rows_retained") is not True
        or report.get("holds") != 384
        or report.get("peer_clusters") != 64
        or report.get("complete_payload_windows") != 384
        or len(sessions) != 64
        or len(audit.get("sessions", [])) != 64
        or audit.get("summaries_recomputed") is not True
        or audit.get("native_factual_only") is not True
        or audit.get("registered_source_hashes_unchanged") is not True
        or audit.get("controller_promoted") is not False
        or audit.get("real_network_validation") is not False
        or report.get("spec_sha256") != sha(spec_path)
        or capture_report.get("spec_sha256") != sha(spec_path)
        or report.get("report_sha256") != sha(capture_report_path)
        or report.get("sessions_sha256") != sha(sessions_path)
        or report.get("inventory_sha256") != sha(inventory_path)
        or report.get("independent_audit_sha256") != sha(audit_path)
        or provenance.get("report_sha256") != sha(analysis_report_path)
        or provenance.get("analysis_code_sha256") != sha(Path("src/media_rl/native_turn_action_panel_v2.py"))
        or provenance.get("analysis_dependency_sha256") != sha(Path("src/media_rl/native_turn_action_diagnostic.py"))
        or provenance.get("registered_capture_sources_sha256") != spec.get("source_sha256")
    ):
        raise ValueError("complete matching V3 capture, independent audit, and registered analysis are required")

    wire_rows = [row["wire"] for row in audit["sessions"]]
    if any(
        row.get("raw_evidence_modified") is not False
        or row.get("closing_ledger_precedes_raw_end") is not False
        or row.get("trailing_empty_service_events") != 0
        or row.get("fifo_capacity_accounting_verified") is not True
        for row in wire_rows
    ):
        raise ValueError("the V3 independent raw wire audit must pass for every peer")

    capture = Path(spec["storage"]["raw_capture_root"]).expanduser().resolve()
    inventory_result = verify_inventory(capture, inventory_path)
    if (
        inventory_result.get("capture_bytes_unmodified") is not True
        or inventory_result.get("capture_file_count") != 323
        or inventory_result.get("inventory_sha256") != report.get("inventory_sha256")
        or inventory_result.get("capture_total_bytes") != report["raw_evidence_provenance"].get("capture_total_bytes")
    ):
        raise ValueError("the full unmodified V3 raw inventory must verify before export")

    outcomes = {row["name"]: row for row in report["outcomes"]}
    if set(outcomes) != {"actual_payload_ratio", "on_time_share"}:
        raise ValueError("unexpected V3 endpoint family")
    arms = report["arms"]
    if [arm["ratio"] for arm in arms] != [0.65, 0.85, 1.05]:
        raise ValueError("unexpected V3 action arms")

    arm_rows = []
    for arm in arms:
        on_time_pct = 100 * arm["request_weighted_on_time_share"]
        arm_rows.append(
            f"{arm['ratio']:.2f} & {arm['holds']} & {arm['mean_actual_payload_ratio']:.3f} & "
            f"{arm['on_time_requests']} / {arm['capture_requests']} & {on_time_pct:.1f} \\\\\n"
        )
    arm_table = (
        "\\begin{tabular}{rrrrr}\n\\toprule\nAssigned BWE ratio & Holds & Actual payload / BWE & "
        "On-time / eligible requests & On time (\\%) \\\\\n\\midrule\n"
        + "".join(arm_rows)
        + "\\bottomrule\n\\end{tabular}\n"
    )

    contrast_rows = []
    for name in ("actual_payload_ratio", "on_time_share"):
        outcome = outcomes[name]
        is_share = name == "on_time_share"
        label = "On-time requests (pp)" if is_share else "Actual payload / assigned BWE"
        scale = 100 if is_share else 1
        for contrast in outcome["contrasts"]:
            estimate = contrast["estimate"] * scale
            low, high = contrast["ci95_low"] * scale, contrast["ci95_high"] * scale
            contrast_rows.append(
                f"{label} & {contrast['contrast']} & {estimate:+.3f} "
                f"[{low:+.3f}, {high:+.3f}] & {contrast['p_value_two_sided']:.6g} & "
                f"{contrast['p_value_holm_all_six']:.6g} \\\\\n"
            )
    contrast_table = (
        "\\begin{tabular}{llrrr}\n\\toprule\nOutcome & Contrast & Difference (95\\% CI) & "
        "$p$ & Holm $p$ \\\\\n\\midrule\n"
        + "".join(contrast_rows)
        + "\\bottomrule\n\\end{tabular}\n"
    )

    payload_high_low = outcomes["actual_payload_ratio"]["contrasts"][1]
    delivery_high_mid = outcomes["on_time_share"]["contrasts"][2]
    macros = {
        "NativeActionVThreePeers": str(report["peer_clusters"]),
        "NativeActionVThreeHolds": str(report["holds"]),
        "NativeActionVThreePayloadLow": f"{arms[0]['mean_actual_payload_ratio']:.3f}",
        "NativeActionVThreePayloadMid": f"{arms[1]['mean_actual_payload_ratio']:.3f}",
        "NativeActionVThreePayloadHigh": f"{arms[2]['mean_actual_payload_ratio']:.3f}",
        "NativeActionVThreeOntimeLow": f"{100 * arms[0]['request_weighted_on_time_share']:.1f}",
        "NativeActionVThreeOntimeMid": f"{100 * arms[1]['request_weighted_on_time_share']:.1f}",
        "NativeActionVThreeOntimeHigh": f"{100 * arms[2]['request_weighted_on_time_share']:.1f}",
        "NativeActionVThreePayloadContrast": f"{payload_high_low['estimate']:+.4f}",
        "NativeActionVThreePayloadLowCI": f"{payload_high_low['ci95_low']:+.4f}",
        "NativeActionVThreePayloadHighCI": f"{payload_high_low['ci95_high']:+.4f}",
        "NativeActionVThreePayloadHolm": f"{payload_high_low['p_value_holm_all_six']:.3g}",
        "NativeActionVThreeDeliveryContrast": f"{100 * delivery_high_mid['estimate']:+.3f}",
        "NativeActionVThreeDeliveryLowCI": f"{100 * delivery_high_mid['ci95_low']:+.3f}",
        "NativeActionVThreeDeliveryHighCI": f"{100 * delivery_high_mid['ci95_high']:+.3f}",
        "NativeActionVThreeDeliveryHolm": f"{delivery_high_mid['p_value_holm_all_six']:.4f}",
    }
    evidence = "".join(f"\\newcommand{{\\{name}}}{{{value}}}\n" for name, value in macros.items())

    root = Path(root)
    if root.exists():
        raise ValueError("fresh V3 paper export directory required")
    root.mkdir(parents=True)
    outputs = {
        "table_arm_means.tex": arm_table,
        "table_contrasts.tex": contrast_table,
        "evidence.tex": evidence,
    }
    for name, contents in outputs.items():
        (root / name).write_text(contents)
    inputs = [
        capture_report_path,
        sessions_path,
        inventory_path,
        audit_path,
        analysis_report_path,
        analysis_provenance_path,
        spec_path,
        Path("tools/native_turn_action_assay_v3.py"),
        Path("src/media_rl/native_turn_probe_v2.py"),
        Path("src/media_rl/native_turn_action_panel_v2.py"),
        Path("src/media_rl/native_turn_audit.py"),
        Path("tools/export_development_updates.py"),
    ]
    export_provenance = {
        "abi": "native_turn_action_assay_v3_paper_export_v1",
        "input_sha256": {str(path): sha(path) for path in inputs},
        "raw_capture_inventory_verified": inventory_result,
        "capture_stdout_stderr_suppressed": True,
        "capture_summary_not_viewed_before_independent_audit": True,
        "analysis_status": "prospective_independent_native_development_replication",
        "exporter_sha256": sha(__file__),
        "output_sha256": {name: sha(root / name) for name in outputs},
        "no_capture_training_or_counterfactual_launched": True,
    }
    (root / "provenance.json").write_text(json.dumps(export_provenance, indent=2, sort_keys=True) + "\n")


def main(
    factual_out,
    native_out,
    action_out,
    action_only=False,
    action_v2_out=None,
    action_v2_only=False,
    action_v3_out=None,
    action_v3_only=False,
):
    if action_v3_only:
        if action_v3_out is None:
            raise ValueError("the V3 paper export directory is required")
        export_native_turn_action_assay_v3(action_v3_out)
        return
    if action_v2_only:
        if action_v2_out is None:
            raise ValueError("the V2b paper export directory is required")
        export_native_turn_action_assay_v2b(action_v2_out)
        return
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
    parser.add_argument(
        "--action-v2-out",
        type=Path,
        default=Path("paper/generated-native-turn-action-assay-v2b"),
    )
    parser.add_argument(
        "--action-v2-only",
        action="store_true",
        help="export only the audited V2b native action-assay development results",
    )
    parser.add_argument(
        "--action-v3-out",
        type=Path,
        default=Path("paper/generated-native-turn-action-assay-v3"),
    )
    parser.add_argument(
        "--action-v3-only",
        action="store_true",
        help="export only the independently audited V3 native action-assay replication",
    )
    args = parser.parse_args()
    main(
        args.factual_out,
        args.native_out,
        args.action_out,
        args.action_only,
        args.action_v2_out,
        args.action_v2_only,
        args.action_v3_out,
        args.action_v3_only,
    )
