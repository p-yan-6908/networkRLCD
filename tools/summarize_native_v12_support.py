"""Summarize completed V12 support checks without opening outcome telemetry.

This is a post-census support diagnostic, outside the frozen collector and
analysis. It never changes a gate or searches for alternate windows/thresholds.
"""
from __future__ import annotations

import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("frozen_v12_support_report", REPO / "tools/native_support_validation_v12.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def candidate_checks(sender, target):
    # Explicit projection: sender time and BWE feature zero. No other feature
    # or encoder/delivery/quality measurement is accessed.
    points = [{"sample_ms": d["sample_ms"], "bwe_bps": d["policy_input"]["features"][0] * 4000000}
              for d in sender["decisions"]]
    result = []
    for i, point in enumerate(points):
        elapsed = point["sample_ms"] - sender["measurement_start_ms"]
        if not 9000 <= elapsed <= 9300:
            continue
        tail = points[max(0, i - 10):i + 1]
        bwes = [p["bwe_bps"] for p in tail]
        span = tail[-1]["sample_ms"] - tail[0]["sample_ms"]
        gaps = [b["sample_ms"] - a["sample_ms"] for a, b in zip(tail, tail[1:])]
        criteria = {
            "eleven_samples": len(tail) == 11,
            "span_at_least_900ms": span >= 900,
            "maximum_gap_at_most_250ms": bool(gaps) and all(0 < gap <= 250 for gap in gaps),
            "bwe_within_unclipped_action_bounds": all(math.isfinite(b) and 240000 <= b <= 3800000 for b in bwes),
            "all_samples_in_target_state": all(math.isfinite(b) and runner.STATES[int(b >= 500000)] == target for b in bwes),
        }
        result.append({"elapsed_ms": elapsed, "sample_count": len(tail), "span_ms": span,
            "maximum_sample_gap_ms": max(gaps) if gaps else None,
            "history_min_max_bwe_bps": [min(bwes), max(bwes)],
            "history_bwe_bps": bwes, "criteria": criteria, "all_criteria_met": all(criteria.values())})
    return result


def summarize():
    runner.verify_registration()
    main = runner.read(runner.CONFIG)
    root = Path(main["support_census_root"])
    protocol, index = runner.core.check_capture_integrity(root)
    gate = runner.read(root / "support_clock_transport_gate.json")
    if gate["protocol_sha256"] != runner.sha(root / "protocol.json") or gate["capture_index_sha256"] != runner.sha(root / "capture_index.json"):
        raise ValueError("support gate is not bound to the complete sealed census")
    trials = {t["id"]: t for t in protocol["trials"]}
    gate_rows = {r["trial"]: r for r in gate["sessions"]}
    rows = []
    for item in index["sessions"]:
        trial = trials[item["trial"]]
        directory = root / "sessions" / item["trial"]
        official = gate_rows[item["trial"]]
        row = {"trial": item["trial"], "content_id": trial["content_id"], "family": trial["network_family"],
            "campaign": trial["network_campaign_id"], "profile": trial["network_profile_id"],
            "cell": trial["cell_cluster"], "target_state": trial["target_state"],
            "capture_status": item["status"], "registered_check_passed": official["passed"],
            "support_qualified": False, "assigned_actions": 0}
        path = directory / "sender_observations.json"
        if path.exists():
            sender = runner.read(path)
            screen = sender["support_screen"]
            if not screen["config"]["support_only"] or screen["action_assigned"]:
                raise ValueError("support census contains a randomized treatment")
            row["support_qualified"] = bool(screen["qualification"] and screen["qualification"]["passed"])
            row["qualification"] = screen["qualification"]
            row["fixed_window_support_candidates"] = candidate_checks(sender, trial["target_state"])
            row["assigned_actions"] = sum(d.get("actuator_assignment") is not None for d in sender["decisions"])
            row["baseline_readback_matched_every_decision"] = all(
                d["proposed_action"]["encoder_max_bitrate_bps"] == 4000000
                and d["actuation_readback"]["encoder_max_bitrate_bps"] == 4000000 for d in sender["decisions"])
            if row["assigned_actions"]:
                raise ValueError("randomized action found in support-only capture")
            # Projection can diagnose state/range/gap failures; the registered
            # native sampler and frozen official gate retain final authority.
            if bool(any(c["all_criteria_met"] for c in row["fixed_window_support_candidates"])) != row["support_qualified"]:
                raise ValueError("BWE support projection does not replay the native qualification")
        for field in ("clock", "transport_passed", "trace_passed", "cleanup_passed", "media_passed"):
            if field in official:
                row[field] = official[field]
        if item["status"] != "sealed":
            error_path = directory / "capture_stderr.log"
            row["capture_error"] = error_path.read_text()[:2000] if error_path.exists() else item.get("error")
        rows.append(row)
    by_campaign, by_content, cells = {}, {}, {}
    for field, table in (("campaign", by_campaign), ("content_id", by_content), ("cell", cells)):
        for key in sorted({r[field] for r in rows}):
            selected = [r for r in rows if r[field] == key]
            table[key] = {"planned_checks": len(selected),
                "sealed_captures": sum(r["capture_status"] == "sealed" for r in selected),
                "capture_failures": sum(r["capture_status"] != "sealed" for r in selected),
                "native_bwe_support_qualified": sum(r["support_qualified"] for r in selected),
                "all_registered_gates_qualified": sum(r["registered_check_passed"] for r in selected),
                "by_target_state": {state: {
                    "planned_checks": sum(r["target_state"] == state for r in selected),
                    "support_qualified": sum(r["target_state"] == state and r["support_qualified"] for r in selected),
                    "all_gates_qualified": sum(r["target_state"] == state and r["registered_check_passed"] for r in selected)
                } for state in runner.STATES}}
    failures = Counter()
    for row in rows:
        if row["capture_status"] != "sealed":
            failures["capture_failed"] += 1
        elif not row["support_qualified"]:
            failures["native_bwe_support_unavailable"] += 1
        for field in ("transport_passed", "trace_passed", "cleanup_passed", "media_passed"):
            if field in row and not row[field]:
                failures[field] += 1
        if "clock" in row and not row["clock"]["passed"]:
            failures["clock_failed"] += 1
    qualified_cells = [key for key, value in cells.items() if all(
        value["by_target_state"][state]["all_gates_qualified"] == 2 for state in runner.STATES)]
    widths = [row["clock"]["max_held_out_width_ms"] for row in rows if row.get("clock", {}).get("passed")]
    output = REPO / "reports/native-v12-support-census-summary.json"
    if output.exists():
        raise ValueError("preserve the existing support summary")
    report = {"abi": "native_v12_support_census_summary_v1", "registration_commit": "aed3afa",
        "confirmatory_protocol_sha256": runner.sha(runner.CONFIG), "support_protocol_sha256": runner.sha(root / "protocol.json"),
        "capture_index_sha256": runner.sha(root / "capture_index.json"),
        "registered_gate_sha256": runner.sha(root / "support_clock_transport_gate.json"),
        "support_gate_passed": gate["passed"], "planned_checks": 24,
        "sealed_captures": sum(r["capture_status"] == "sealed" for r in rows),
        "qualified_registered_checks": gate["qualified_sessions"], "failures": dict(failures),
        "fully_supported_cells": qualified_cells, "fully_supported_cell_count": len(qualified_cells),
        "maximum_qualified_clock_width_ms": max(widths) if widths else None,
        "by_campaign": by_campaign, "by_content": by_content, "cells": cells, "sessions": rows,
        "treatment_capture_started": (runner.ROOT / "sessions").exists(),
        "randomized_actions_assigned_in_census": sum(r["assigned_actions"] for r in rows),
        "outcome_files_opened": False, "primary_conditional_action_effect_estimated": False,
        "controller_fit_or_promoted": False,
        "decoded_inputs": ["frozen protocols", "capture index and SHA-256 seals", "registered technical gate",
                           "sender timing/BWE feature zero, support qualification, cap assignment/readback", "capture failure log"],
        "interpretation": "Support/liveness qualification only. Failures are not bitrate treatment outcomes. No PSNR, on-time delivery fraction, or per-hold relay cost is examined; no trace/state/action/cell gate is changed."}
    runner.write(output, report)
    return {k: report[k] for k in ("support_gate_passed", "planned_checks", "sealed_captures", "qualified_registered_checks", "failures", "fully_supported_cell_count", "maximum_qualified_clock_width_ms", "by_campaign", "by_content")}


if __name__ == "__main__":
    print(json.dumps(summarize()))
