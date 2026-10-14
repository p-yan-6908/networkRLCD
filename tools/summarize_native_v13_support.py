"""Diagnose a complete V13 census using outcome-free support variables only.

This post-census tool is outside the frozen scientific instrumentation. It
does not select replacement sources, search alternative decision windows,
modify a gate, import the outcome analyzer or fit an action-effect model.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v13_census_diagnostic", REPO / "tools/design_native_v13.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def describe(points, start, cutoff):
    weighted = []
    for i, point in enumerate(points):
        end = points[i + 1]["ms"] if i + 1 < len(points) else cutoff
        duration = max(0, min(end, cutoff) - max(point["ms"], start))
        if duration:
            weighted.append((point, duration))
    total = sum(duration for point, duration in weighted)
    valid = [point["bwe"] for point, duration in weighted if point["valid"]]
    def fraction(test):
        return sum(duration for point, duration in weighted if test(point)) / total if total else None
    return {"covered_ms": total, "bwe_min_median_max_bps": [min(valid), st.median(valid), max(valid)] if valid else None,
        "eligible_time_fraction": fraction(lambda p: p["valid"] and 240000 <= p["bwe"] <= 3800000),
        "below_eligibility_time_fraction": fraction(lambda p: p["valid"] and p["bwe"] < 240000),
        "above_eligibility_time_fraction": fraction(lambda p: p["valid"] and p["bwe"] > 3800000),
        "invalid_time_fraction": fraction(lambda p: not p["valid"])}


def summarize(output):
    if output.exists():
        raise ValueError("preserve the completed census diagnosis")
    runner.verify()
    protocol, index = runner.core.check_capture_integrity(runner.SUPPORT_ROOT)
    assert protocol["kind"] == "support_census" and len(index["sessions"]) == 32
    gate_path = runner.SUPPORT_ROOT / "support_clock_transport_gate.json"
    gate = runner.read(gate_path)
    assert gate["protocol_sha256"] == runner.sha(runner.SUPPORT_ROOT / "protocol.json")
    assert gate["capture_index_sha256"] == runner.sha(runner.SUPPORT_ROOT / "capture_index.json")
    trials = {t["id"]: t for t in protocol["trials"]}
    official = {r["trial"]: r for r in gate["sessions"]}
    windows = protocol["support"]["decision_window_ms"]
    bounds = protocol["support"]["eligible_bwe_bounds_bps"]
    rows, verified_files = [], 0
    for item in index["sessions"]:
        trial = trials[item["trial"]]
        directory = runner.SUPPORT_ROOT / "sessions" / trial["id"]
        verified_files += runner.read(directory / "integrity.json")["file_count"]
        row = {"trial": trial["id"], "capture_status": item["status"],
            **{k: trial[k] for k in ("content_id", "network_family", "network_campaign_id", "network_profile_id", "cell_cluster", "repetition")},
            "all_session_gates_passed": official[trial["id"]]["passed"], "native_support_qualified": False,
            "assigned_actions": 0}
        path = directory / "sender_observations.json"
        if path.exists():
            sender = runner.read(path)
            assert sender["support_screen"]["config"]["support_only"] and not sender["support_screen"]["action_assigned"]
            assert all(d.get("actuator_assignment") is None for d in sender["decisions"])
            assert all(d["proposed_action"]["encoder_max_bitrate_bps"] == 4000000
                and d["actuation_readback"]["encoder_max_bitrate_bps"] == 4000000
                and d["actuation_readback"]["receiver_jitter_buffer_target_ms"] == 0 for d in sender["decisions"])
            start, cutoff = sender["measurement_start_ms"], sender["measurement_cutoff_ms"]
            points = [{"ms": d["sample_ms"] - start, "bwe": d["policy_input"]["features"][0] * 4000000,
                       "valid": d["policy_input"]["features"][9] == 1} for d in sender["decisions"]]
            candidates = []
            for i, point in enumerate(points):
                if not windows[0] <= point["ms"] <= windows[1]:
                    continue
                tail = points[max(0, i - 10):i + 1]
                checks = {"eleven_samples": len(tail) == 11,
                    "history_span_at_least_900ms": tail[-1]["ms"] - tail[0]["ms"] >= 900,
                    "gaps_positive_and_at_most_250ms": all(0 < b["ms"] - a["ms"] <= 250 for a, b in zip(tail, tail[1:])),
                    "native_bwe_valid": all(p["valid"] for p in tail),
                    "not_below_240kbps": all(p["bwe"] >= bounds[0] for p in tail),
                    "not_above_3800kbps": all(p["bwe"] <= bounds[1] for p in tail)}
                candidates.append({"elapsed_ms": point["ms"], "history_min_max_bwe_bps": [min(p["bwe"] for p in tail), max(p["bwe"] for p in tail)],
                    "sample_times_ms": [p["ms"] for p in tail], "bwe_history_bps": [p["bwe"] for p in tail], "checks": checks,
                    "passed": all(checks.values())})
            qualified = any(c["passed"] for c in candidates)
            stored = sender["support_screen"]["qualification"]
            assert qualified == bool(stored and stored["passed"])
            row.update({"native_support_qualified": qualified, "baseline_readback_passed": True,
                "registered_window_candidates": candidates,
                "continuous_log2_bwe": stored["continuous_log2_bwe"] if qualified else None,
                "geometric_mean_bwe_bps": stored["geometric_mean_bwe_bps"] if qualified else None,
                "by_time_window": {f"{lo}_{hi}s": describe(points, lo * 1000, min(hi * 1000, cutoff - start))
                    for lo, hi in [(0, 3), (3, 12), (12, 18), (18, 18.3), (18.3, 24), (24, 36.6)]}})
        for field in ("clock", "transport_passed", "trace", "cleanup_passed", "media_passed"):
            if field in official[trial["id"]]:
                row[field] = official[trial["id"]][field]
        if item["status"] != "sealed":
            error = directory / "capture_stderr.log"
            row["capture_error"] = error.read_text()[:2000] if error.exists() else item.get("error")
        rows.append(row)
    profiles = {}
    for cell, profile in sorted({(r["cell_cluster"], r["network_profile_id"]) for r in rows}):
        selected = [r for r in rows if r["cell_cluster"] == cell and r["network_profile_id"] == profile]
        assert len(selected) == 2
        qualified = [r["continuous_log2_bwe"] for r in selected if r["all_session_gates_passed"]]
        spread = max(qualified) - min(qualified) if len(qualified) == 2 else None
        key = cell + "::" + profile
        profiles[key] = {"cell": cell, "profile": profile, "content": selected[0]["content_id"],
            "family": selected[0]["network_family"], "campaign": selected[0]["network_campaign_id"],
            "all_session_qualified_repeats": len(qualified), "replicate_x": qualified,
            "repeat_log2_difference": spread, "repeat_bwe_ratio": 2 ** spread if spread is not None else None,
            "repeatability_passed": spread is not None and spread <= .25,
            "census_x": gate["census_states"].get(key, {}).get("x"),
            "registered_profile_passed": gate["census_states"].get(key, {}).get("passed", False)}
        assert profiles[key]["repeatability_passed"] == profiles[key]["registered_profile_passed"]
    cells = {}
    for cell, variation in sorted(gate["cells"].items()):
        selected = [r for r in profiles.values() if r["cell"] == cell]
        assert len(selected) == 4
        range_octaves = variation["x_min_max"][1] - variation["x_min_max"][0] if variation["x_min_max"] else None
        fully_supported = variation["passed"] and all(p["registered_profile_passed"] for p in selected)
        cells[cell] = {**variation, "content": selected[0]["content"], "family": selected[0]["family"], "campaign": selected[0]["campaign"],
            "observed_profile_range_octaves": range_octaves,
            "range_at_least_one_octave": len([p for p in selected if p["census_x"] is not None]) == 4 and range_octaves >= 1,
            "sd_at_least_035_octaves": variation["x_sample_sd"] is not None and variation["x_sample_sd"] >= .35,
            "qualified_repeatable_profiles": sum(p["registered_profile_passed"] for p in selected),
            "fully_supported": fully_supported,
            "scope": "The frozen variation-only cell field can include an incomplete/nonrepeatable profile; full qualification also requires all original session and repeatability gates."}
    strata = {}
    for field in ("content_id", "network_family", "network_campaign_id"):
        strata[field] = {}
        for value in sorted({r[field] for r in rows}):
            selected = [r for r in rows if r[field] == value]
            strata[field][value] = {"planned_checks": len(selected), "sealed_captures": sum(r["capture_status"] == "sealed" for r in selected),
                "native_support_qualified": sum(r["native_support_qualified"] for r in selected),
                "all_session_gates_qualified": sum(r["all_session_gates_passed"] for r in selected),
                "limits": "Describes selected repeats nested in existing profiles and one measurement program; no population or independent-program inference."}
    rejected = [r for r in rows if r["capture_status"] == "sealed" and not r["native_support_qualified"]]
    never = Counter()
    for row in rejected:
        for check in row["registered_window_candidates"][0]["checks"] if row["registered_window_candidates"] else []:
            if not any(c["checks"][check] for c in row["registered_window_candidates"]):
                never[check] += 1
    widths = [r["clock"]["max_held_out_width_ms"] for r in rows if r.get("clock", {}).get("passed")]
    result = {"abi": "native_v13_outcome_free_support_summary_v1", "registration_commit": "6b8471a",
        "confirmatory_protocol_sha256": runner.sha(runner.CONFIG), "support_protocol_sha256": runner.sha(runner.SUPPORT_ROOT / "protocol.json"),
        "capture_index_sha256": runner.sha(runner.SUPPORT_ROOT / "capture_index.json"), "official_gate_sha256": runner.sha(gate_path),
        "tool_sha256": runner.sha(Path(__file__).resolve()), "verified_session_files": verified_files,
        "support_gate_passed": gate["passed"], "checks_attempted": 32, "qualified_session_checks": gate["qualified_sessions"],
        "support_range_failures": len(rejected), "range_failure_components_never_met_in_registered_window": dict(never),
        "repeatability_failed_profiles": [key for key, p in profiles.items() if p["all_session_qualified_repeats"] == 2 and not p["repeatability_passed"]],
        "incomplete_profiles": [key for key, p in profiles.items() if p["all_session_qualified_repeats"] != 2],
        "fully_supported_cell_count": sum(c["fully_supported"] for c in cells.values()), "required_supported_cells": 4,
        "maximum_qualified_clock_width_ms": max(widths) if widths else None,
        "strata": strata, "profiles": profiles, "cells": cells, "sessions": rows,
        "assigned_randomized_actions": sum(r["assigned_actions"] for r in rows),
        "confirmatory_action_panel_started": (runner.ROOT / "sessions").exists(),
        "outcomes_opened": False, "action_effects_estimated": False, "controller_fitted": False,
        "binary_state_threshold_introduced": False, "substitutions_or_gate_changes": False,
        "decoded_inputs": ["frozen protocols/panels and inventory/seals", "official technical/support gate", "sender timing/BWE feature zero and validity, qualification, assignment/cap/jitter readback", "failed capture error if applicable"],
        "excluded": ["frame_events.json", "sender encoded meter and receiver feedback", "quality, timely-delivery and per-hold relay outcome telemetry"],
        "interpretation": "Registered support/variation/repeatability only. No alternative decision window, state split, eligibility bound, source, count or outcome estimate is introduced."}
    runner.write(output, result)
    return {k: result[k] for k in ("support_gate_passed", "checks_attempted", "qualified_session_checks", "support_range_failures", "repeatability_failed_profiles", "incomplete_profiles", "fully_supported_cell_count", "maximum_qualified_clock_width_ms", "cells")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "reports/native-v13-support-census-summary.json")
    args = parser.parse_args()
    print(json.dumps(summarize(args.out)))
