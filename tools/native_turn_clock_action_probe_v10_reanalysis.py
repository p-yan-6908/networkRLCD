"""Checksum-gated V10 action/readback replay with the post-action BWE drift check corrected."""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import native_turn_clock_action_probe_v10 as v10

ROOT = v10.CAPTURE_ROOT
OUTPUT = v10.REPORT_PATH
EXPECTED_GATE_SHA256 = "448fb02eb49250ae1d99341d77e4625324693fc43ff83570db2f93f0d5244024"


def install_corrected_registered_loader() -> str:
    """Patch only the in-memory epoch-input validation from the frozen V10 loader."""
    original = inspect.getsource(v10.core.load_session_v10)
    old = '''                or assignment.get("ratio") != ratio or observation_bwe is None
                or not isinstance(base_bwe, (int, float)) or abs(observation_bwe - base_bwe) > 0.01
'''
    new = '''                or assignment.get("ratio") != ratio or not valid_bwe
                or (decision.get("sample_ms") == assignment.get("assignment_ms")
                    and (observation_bwe is None or abs(observation_bwe - base_bwe) > 0.01))
'''
    if original.count(old) != 1:
        raise ValueError("registered V10 loader source no longer matches the reviewed correction point")
    corrected = original.replace(old, new, 1)
    exec(compile(corrected, str(v10.CORE_PATH), "exec"), v10.core.__dict__)
    return v10.sha(v10.CORE_PATH)


def analyze() -> dict:
    protocol = v10.load_registered(ROOT)
    _, index = v10.core.check_capture_integrity(ROOT)
    gate_path = ROOT / "clock_transport_gate.json"
    gate_sha = v10.sha(gate_path)
    gate = v10.core.read_json(gate_path)
    expected_count = len(protocol["trials"])
    if (gate_sha != EXPECTED_GATE_SHA256 or not gate.get("passed")
            or gate.get("outcome_analysis_performed") is not False
            or gate.get("qualified_clock_sessions") != expected_count
            or gate.get("qualified_transport_sessions") != expected_count
            or gate.get("failed_capture_sessions") != 0
            or len(index["sessions"]) != expected_count
            or any(row["status"] != "sealed" for row in index["sessions"])):
        raise ValueError("all V10 sessions must pass the unchanged checksum, clock, and transport gates before outcomes are read")
    original_loader_sha = install_corrected_registered_loader()
    unpublished = ROOT / "unpublished-v10-analysis-corrected.json"
    if unpublished.exists() or OUTPUT.exists():
        raise ValueError("fresh V10 corrected-analysis output path required")
    report = v10.core.analyze_v10(ROOT, unpublished)
    report["transport"] = protocol["transport"]
    report["runtime"] = protocol["runtime"]
    report["preflight_reference"] = protocol["preflight_reference"]
    report["clock_calibration_reference"] = protocol["clock_calibration_reference"]
    report["prior_frozen_studies"] = protocol["prior_frozen_studies"]
    report["policy_rule"] = protocol["policy_rule"]
    report["actual_run_clock_transport_gate_sha256"] = gate_sha
    report["maximum_actual_run_held_out_clock_width_ms"] = max(
        row["clock"]["max_held_out_width_ms"] for row in gate["sessions"])
    report["analysis_code_correction"] = {
        "kind": "post-capture validator correction; capture and registered protocol unchanged",
        "registered_core_sha256": protocol["source_hashes"]["analysis_tool"],
        "reanalysis_tool_sha256": v10.sha(Path(__file__).resolve()),
        "correction": "compare the saved pre-action BWE observation with the action assignment only at that epoch start; subsequent sender BWE samples may change during the three-second hold",
        "caps_still_replayed_for_every_decision": True,
        "all_48_sessions_rechecked_after_gate": True,
        "acceptance_criteria_changed": False,
        "original_loader_source_sha256": original_loader_sha,
    }
    report["outcome_data_read_after_gate"] = True
    report["controller_fitted_or_promoted"] = False
    v10.core.write_json(OUTPUT, report)
    return {"report": str(OUTPUT), "report_sha256": v10.sha(OUTPUT),
            "sessions": report["sealed_sessions"],
            "actual_session_clocks_all_pass": report["session_clock_validations_all_pass"],
            "clock_transport_gate_sha256": gate_sha,
            "action_validation": report["action_validation"],
            "primary_effect": report["primary_effect"],
            "controller_fitted_or_promoted": False}


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2, sort_keys=True))
