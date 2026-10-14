"""Outcome-free diagnosis of M3 qualification failures; never changes its gates."""
from __future__ import annotations

import gzip
import importlib.util
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("m3_gate_diagnosis", REPO / "tools/measure_prefix_memory_m3.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)


def diagnose():
    m.verify()
    protocol, index = m.v.core.check_capture_integrity(m.ROOT)
    gate = m.v.read(m.ROOT / "mechanism_qualification_gate.json")
    assert gate["protocol_sha256"] == m.v.sha(m.CONFIG)
    assert gate["capture_index_sha256"] == m.v.sha(m.ROOT / "capture_index.json")
    rows, failed_clocks = [], []
    for position, row in enumerate(gate["sessions"]):
        trial = protocol["trials"][position]
        assert row["trial"] == trial["id"]
        result = {"trial": row["trial"], "content_id": row["content_id"], "prefix": row["prefix"],
            "original_order_position": position, "after_platform_recovery": position >= 50,
            "capture_status": row["capture_status"], "registered_session_passed": row["passed"]}
        if row["capture_status"] != "sealed":
            result["reason"] = "Interrupted original; no completed clock/startup/cleanup qualification asserted"
            rows.append(result)
            continue
        directory = m.ROOT / "sessions" / row["trial"]
        markers = m.v.core.load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
        clock = m.v.core.validate_markers(markers, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])
        assert {k: v for k, v in clock.items() if k != "checks"} == row["clock"]
        origin, vertices = m.v.core.feasible_polygon([markers[i] for i in (0, 1, 3, 4, 6, 7, 9, 11)])
        failures = []
        for i, check in zip((2, 5, 8, 10), clock["checks"], strict=True):
            if check["covered"]:
                continue
            marker = markers[i]
            receive = [origin + (marker["node_receive_ms"] - beta) / alpha for alpha, beta in vertices]
            send = [origin + (marker["node_send_ms"] - beta) / alpha for alpha, beta in vertices]
            failures.append({**check, "endpoint": marker["endpoint"], "phase": marker.get("phase"),
                "early_coverage_deficit_beyond_1ms": max(0, marker["browser_send_ms"] - 1 - min(receive)),
                "late_coverage_deficit_beyond_1ms": max(0, max(send) - marker["browser_receive_ms"] - 1)})
        # Existence with all markers is solely a geometry diagnosis. It cannot
        # replace the frozen out-of-sample, every-vertex coverage requirement.
        _, joint_vertices = m.v.core.feasible_polygon(markers)
        result["clock"] = {"registered_passed": clock["passed"], "coverage": clock["coverage"],
            "max_heldout_width_ms": clock["max_held_out_width_ms"], "failed_holdouts": failures,
            "all_12_marker_joint_affine_feasible": len(joint_vertices) >= 3,
            "joint_affine_vertex_count": len(joint_vertices), "requalifies_session": False}
        if failures:
            failed_clocks.append({"trial": row["trial"], **result["clock"]})
        startup = row["startup"]
        result["startup"] = {"registered_passed": row["startup_passed"],
            **{k: startup[k] for k in ("requested_initial_bwe_bps", "local_start_parameter", "remote_start_parameter",
                "first_measured_bwe_bps", "preconnection_cap_readback_bps", "negotiation_start_ms", "ice_gathering_complete_ms",
                "connection_qualified_ms", "initial_native_sample_ms", "measurement_start_ms")},
            "actual_initial_native_bwe_bps": startup["initial_native_source"]["bwe_bps"],
            "premeasurement_frames_encoded": startup["initial_native_source"]["frames_encoded"],
            "premeasurement_rtcp_measurements": startup["initial_native_source"]["rtcp_rtt_measurements"]}
        phases, ticks = [], []
        with gzip.open(directory / "events.jsonl.gz", "rt") as stream:
            for line in stream:
                event = json.loads(line)
                if event.get("kind") == "phase":
                    phases.append({k: event[k] for k in ("phase", "at_ms")})
                elif event.get("kind") == "trace_capacity":
                    ticks.append({k: event[k] for k in ("phase", "sample_index", "at_ms", "capacity_mbps")})
        phase_start = {x["phase"]: x["at_ms"] for x in phases}
        rates = [x["capacity_mbps"] for x in ticks]
        assert rates == protocol["prefix_profiles"][trial["prefix"]]["rates_mbps"]
        assert rates[10:] == protocol["parent_profile"]["rates_mbps"][10:]
        result["replay_node_domain"] = {"exact_36_registered_rates": len(ticks) == 36,
            "exact_common_suffix": True, "maximum_tick_error_ms": max(abs(x["at_ms"] - phase_start[x["phase"]] - x["sample_index"] * 1000) for x in ticks),
            "sender_alignment_asserted_for_failed_clock": False}
        rows.append(result)
    sealed = [r for r in rows if r["capture_status"] == "sealed"]
    result = {"abi": "native_prefix_memory_m3_gate_diagnosis_v1", "protocol_sha256": m.v.sha(m.CONFIG),
        "capture_index_sha256": m.v.sha(m.ROOT / "capture_index.json"),
        "gate_sha256": m.v.sha(m.ROOT / "mechanism_qualification_gate.json"),
        "diagnosis_tool_sha256": m.v.sha(Path(__file__).resolve()), "original_attempts": len(rows),
        "sealed_sessions": len(sealed), "qualified_sessions": gate["qualified_sessions"],
        "clock_failure_count": len(failed_clocks), "failed_clocks": failed_clocks,
        "native_initial_bwe_counts": dict(Counter(str(r["startup"]["actual_initial_native_bwe_bps"]) for r in sealed)),
        "all_sealed_replays_exact": all(r["replay_node_domain"]["exact_36_registered_rates"] and r["replay_node_domain"]["exact_common_suffix"] for r in sealed),
        "maximum_node_tick_error_ms": max(r["replay_node_domain"]["maximum_tick_error_ms"] for r in sealed),
        "maximum_original_clock_interval_width_ms": max(r["clock"]["max_heldout_width_ms"] for r in sealed),
        "sessions": rows, "source_scope": protocol["source_separation"], "outcomes_read": False,
        "later_bwe_effects_examined": False, "new_inferential_tests": 0, "sessions_requalified": 0,
        "clock_geometry_diagnostic_is_not_a_registered_gate_substitute": True}
    m.v.write(REPO / "reports/native-prefix-memory-m3-gate-diagnosis.json", result)
    m.v.write(m.ROOT / "gate_failure_diagnosis.json", result)
    return {k: result[k] for k in ("original_attempts", "sealed_sessions", "qualified_sessions", "clock_failure_count",
        "native_initial_bwe_counts", "all_sealed_replays_exact", "maximum_node_tick_error_ms", "sessions_requalified", "outcomes_read")}


if __name__ == "__main__":
    print(json.dumps(diagnose()))
