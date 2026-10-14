"""Outcome-free V11D/V12 development diagnosis, without changing a freeze.

Only timing, native BWE validity/feature zero, assignments/cap readback, clock
markers and registered rate schedules are projected. Frame, queue, encoded
meter, feedback and outcome reports are not decoded. All raw bytes are hashed
before the permitted projections are opened.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache/networkrlcd"
spec = importlib.util.spec_from_file_location("v13_marker_math", REPO / "tools/native_clock_action_probe_turntcp_v11_core.py")
clock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clock)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify(root, protocol_sha, index_sha):
    assert sha(root / "protocol.json") == protocol_sha
    assert sha(root / "capture_index.json") == index_sha
    protocol, index = read(root / "protocol.json"), read(root / "capture_index.json")
    assert index["protocol_sha256"] == protocol_sha
    assert {t["id"] for t in protocol["trials"]} == {s["trial"] for s in index["sessions"]}
    assert len(index["sessions"]) == len(protocol["trials"])
    count = 0
    for session in index["sessions"]:
        directory = root / "sessions" / session["trial"]
        assert sha(directory / "integrity.json") == session["integrity_manifest_sha256"]
        seal = read(directory / "integrity.json")
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file() and p.name != "integrity.json"}
        assert actual == set(seal["files"])
        for name, checksum in seal["files"].items():
            assert sha(directory / name) == checksum, (session["trial"], name)
            count += 1
    return protocol, index, count


def bounds(values):
    return [min(values), st.median(values), max(values)] if values else None


def weighted_fraction(points, test):
    denominator = sum(p["dt_ms"] for p in points)
    return sum(p["dt_ms"] for p in points if test(p)) / denominator if denominator else None


def describe(points):
    valid = [p for p in points if p["valid"]]
    return {"samples": len(points), "valid_samples": len(valid),
        "observed_ms": sum(p["dt_ms"] for p in points),
        "bwe_min_median_max_bps": bounds([p["bwe_bps"] for p in valid]),
        "below_240k_time_fraction": weighted_fraction(points, lambda p: p["valid"] and p["bwe_bps"] < 240000),
        "eligible_range_time_fraction": weighted_fraction(points, lambda p: p["valid"] and 240000 <= p["bwe_bps"] <= 3800000),
        "low_eligible_time_fraction": weighted_fraction(points, lambda p: p["valid"] and 240000 <= p["bwe_bps"] < 500000),
        "high_eligible_time_fraction": weighted_fraction(points, lambda p: p["valid"] and 500000 <= p["bwe_bps"] <= 3800000),
        "near_500k_450_to_550k_time_fraction": weighted_fraction(points, lambda p: p["valid"] and 450000 <= p["bwe_bps"] <= 550000),
        "state_crossings": sum(a["valid"] and b["valid"] and (a["bwe_bps"] >= 500000) != (b["bwe_bps"] >= 500000) for a, b in zip(points, points[1:])),
        "invalid_time_fraction": weighted_fraction(points, lambda p: not p["valid"])}


def history_ok(tail, low=240000, high=3800000, target=None):
    return (len(tail) == 11 and tail[-1]["ms"] - tail[0]["ms"] >= 900
        and all(0 < b["ms"] - a["ms"] <= 250 for a, b in zip(tail, tail[1:]))
        and all(p["valid"] and low <= p["bwe_bps"] <= high and (target is None or int(p["bwe_bps"] >= 500000) == target) for p in tail))


def schedule_projection(directory, panel, start):
    markers = clock.load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
    assert len(markers) == 12
    validation = clock.validate_markers(markers, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])
    assert validation["passed"], directory
    origin, vertices = clock.feasible_polygon(markers)
    phases = [m for m in markers if m["endpoint"] == "/phase"]
    schedule = panel["episodes"][0]["schedule"]
    ticks = []
    for phase, (capacity, name, duration, rates) in zip(phases, schedule, strict=True):
        assert name == phase["phase"] and capacity == rates[0]
        for i, rate in enumerate(rates):
            lo, hi = clock.mapped_browser_range(phase["node_phase_ms"] + i * 1000, origin, vertices)
            # The already qualified scheduler permits 150 ms tick jitter.
            ticks.append({"ms": (lo + hi) / 2 - start, "uncertainty_ms": (hi - lo) / 2 + 150,
                "capacity_bps": rate * 1000000})
    return ticks, validation


def diagnose_panel(label, root, protocol_sha, index_sha):
    protocol, index, file_count = verify(root, protocol_sha, index_sha)
    trials = {t["id"]: t for t in protocol["trials"]}
    rows = []
    for session in index["sessions"]:
        trial = trials[session["trial"]]
        directory = root / "sessions" / session["trial"]
        assert sha(root / trial["panel"]) == trial["panel_sha256"]
        panel = read(root / trial["panel"])
        sender = read(directory / "sender_observations.json")
        start, cutoff = sender["measurement_start_ms"], sender["measurement_cutoff_ms"]
        points = []
        for decision in sender["decisions"]:
            points.append({"ms": decision["sample_ms"] - start,
                "bwe_bps": decision["policy_input"]["features"][0] * 4000000,
                "valid": decision["policy_input"]["features"][9] == 1,
                "cap_bps": decision["actuation_readback"]["encoder_max_bitrate_bps"],
                "assignment": decision.get("actuator_assignment")})
        for i, point in enumerate(points):
            point["dt_ms"] = (points[i + 1]["ms"] if i + 1 < len(points) else cutoff - start) - point["ms"]
            assert point["dt_ms"] > 0
        flat_runs, first_flat = [], 0
        for i in range(1, len(points) + 1):
            if i == len(points) or points[i]["bwe_bps"] != points[first_flat]["bwe_bps"]:
                flat_runs.append(points[i-1]["ms"] + points[i-1]["dt_ms"] - points[first_flat]["ms"])
                first_flat = i
        row = {"trial": trial["id"], "content_id": trial["content_id"], "campaign": trial["network_campaign_id"],
            "family": trial["network_family"], "profile": trial["network_profile_id"], "capture_status": session["status"],
            "measured_duration_ms": cutoff - start,
            "first_bwe_bps": points[0]["bwe_bps"], "first_bwe_valid": points[0]["valid"],
            "first_departure_from_300k_ms": next((p["ms"] for p in points if p["valid"] and abs(p["bwe_bps"] - 300000) > 1), None),
            "by_elapsed_window": {f"{lo}_{hi}s": describe([p for p in points if lo * 1000 <= p["ms"] < hi * 1000]) for lo, hi in [(0,3),(3,6),(6,9),(9,9.3),(9.3,12),(12,15),(15,18.6)]},
            "all_observed": describe(points), "capacity_bwe_join_qualified": False}
        row["maximum_unchanged_bwe_run_ms"] = max(flat_runs)
        rates = [rate for phase in panel["episodes"][0]["schedule"] for rate in phase[3]]
        row["registered_rate_diagnostics"] = {
            "screen_mean_seconds_3_to_12_bps": st.mean(rates[3:13])*1000000,
            "causal_history_mean_seconds_8_to_9_bps": st.mean(rates[8:10])*1000000,
            "initial_three_seconds_min_mean_max_bps": [min(rates[:3])*1000000,st.mean(rates[:3])*1000000,max(rates[:3])*1000000],
            "seconds_below_240kbps": sum(rate<.24 for rate in rates),
            "maximum_minimum_capacity_ratio": max(rates)/min(rates) if min(rates)>0 else None,
            "zero_capacity_seconds": sum(rate==0 for rate in rates),
            "scope": "Source rates are input design variables, not achieved goodput or sender BWE."}
        assignments = [(p["ms"], p["assignment"]) for p in points if p["assignment"] is not None]
        first_assignment_ms = assignments[0][0] if assignments else None
        row["earliest_treatment_ms"] = first_assignment_ms
        row["later_bwe_is_post_treatment"] = label == "V11D"
        if label == "V12":
            assert not assignments and all(p["cap_bps"] == 4000000 for p in points)
            target = int(trial["target_state"] == "bwe_ge_500k")
            row["target_state"] = trial["target_state"]
            checks = [(p["ms"], history_ok(points[max(0,i-10):i+1], target=target), history_ok(points[max(0,i-10):i+1])) for i,p in enumerate(points)]
            row["development_counterfactual_support_timings"] = {
                "scope": "Descriptive diagnosis only; no candidate changes V12 qualification or supplies new evidence.",
                "first_eligible_target_history_ms": next((t for t, ok, _ in checks if ok), None),
                "first_eligible_target_history_after_9300ms": next((t for t, ok, _ in checks if ok and t > 9300), None),
                "registered_window_target_passed": any(ok and 9000 <= t <= 9300 for t,ok,_ in checks),
                "registered_window_continuous_range_passed": any(ok and 9000 <= t <= 9300 for t,_,ok in checks),
                "eligible_target_history_fraction_after_9300ms": sum(ok for t,ok,_ in checks if t>9300) / sum(t>9300 for t,_,_ in checks),
            }
            stored = sender["support_screen"]["qualification"]
            assert row["development_counterfactual_support_timings"]["registered_window_target_passed"] == bool(stored and stored["passed"])
        # Failed capture has no qualified actual-run map: retain BWE only.
        if session["status"] == "sealed":
            ticks, validation = schedule_projection(directory, panel, start)
            row["capacity_bwe_join_qualified"] = True
            row["clock_max_held_out_width_ms"] = validation["max_held_out_width_ms"]
            row["trace_ticks"] = ticks
            joined = []
            for point in points:
                past = [t for t in ticks if t["ms"] <= point["ms"]]
                if not past or any(abs(point["ms"] - t["ms"]) <= t["uncertainty_ms"] for t in ticks):
                    continue
                p = {**point, "capacity_bps": past[-1]["capacity_bps"]}
                joined.append(p)
            row["capacity_join_samples_excluding_tick_uncertainty"] = len(joined)
            row["capacity_bwe_state_disagreement_fraction"] = weighted_fraction(joined, lambda p: p["valid"] and (p["bwe_bps"] >= 500000) != (p["capacity_bps"] >= 500000))
            row["bwe_capacity_ratio_min_median_max"] = bounds([p["bwe_bps"]/p["capacity_bps"] for p in joined if p["valid"] and p["capacity_bps"]>0])
            # Prespecified diagnostic bands, not a replacement state definition.
            bands = [(0,240000),(240000,500000),(500000,1000000),(1000000,2000000),(2000000,4000000),(4000000,10000001)]
            row["bwe_by_capacity_and_three_second_prior_bwe"] = {}
            for lo, hi in bands:
                groups = {"prior_low":[],"prior_high":[]}
                for p in joined:
                    prior = [q for q in points if q["ms"] <= p["ms"] - 3000]
                    if lo<=p["capacity_bps"]<hi and p["valid"] and prior and prior[-1]["valid"]:
                        groups["prior_high" if prior[-1]["bwe_bps"] >= 500000 else "prior_low"].append(p["bwe_bps"])
                row["bwe_by_capacity_and_three_second_prior_bwe"][f"{lo}_{hi}"] = {k:{"samples":len(v),"bwe_min_median_max_bps":bounds(v)} for k,v in groups.items()}
            # Response after a capacity threshold transition that persists >=2s.
            # Censor at next capacity-bin change, recording all episodes.
            episodes = []
            for i in range(1,len(ticks)):
                before, after = ticks[i-1], ticks[i]
                state = int(after["capacity_bps"]>=500000)
                if int(before["capacity_bps"]>=500000)==state:
                    continue
                end = next((t["ms"] for t in ticks[i+1:] if int(t["capacity_bps"]>=500000)!=state),cutoff-start)
                if end-after["ms"]<2000:
                    continue
                pre = [p for p in points if p["ms"] < after["ms"]-after["uncertainty_ms"]]
                pre_bwe = pre[-1]["bwe_bps"] if pre and pre[-1]["valid"] else None
                already = pre_bwe is not None and int(pre_bwe>=500000)==state
                instant = next((p["ms"] for p in points if after["ms"]+after["uncertainty_ms"] <= p["ms"] < end-150
                                and p["valid"] and int(p["bwe_bps"]>=500000)==state),None)
                first = next((p["ms"] for j,p in enumerate(points) if after["ms"]+after["uncertainty_ms"] <= p["ms"] < end-150
                              and history_ok(points[max(0,j-10):j+1],low=1,high=10000000,target=state)
                              and points[max(0,j-10)]["ms"] >= after["ms"]+after["uncertainty_ms"]),None)
                episodes.append({"capacity_transition_ms":after["ms"],"capacity_state":state,"capacity_episode_end_ms":end,
                    "pre_transition_bwe_bps":pre_bwe,"already_in_new_capacity_state":already,
                    "first_instantaneous_bwe_match_ms":instant,
                    "instantaneous_tracking_lag_ms":instant-after["ms"] if instant is not None and not already else None,
                    "first_one_second_bwe_history_ms":first,"response_lag_ms":first-after["ms"] if first is not None else None,
                    "right_censored":first is None,"note":"State-tracking latency, not GCC causal identification or steady-state validation."})
            row["capacity_bin_transition_responses"] = episodes
        # Permitted sender projection retained for reproducibility/figures only.
        row["sender_bwe_timeline"] = [{k:p[k] for k in ("ms","dt_ms","bwe_bps","valid","cap_bps")} for p in points]
        rows.append(row)
    campaigns = {}
    for campaign in sorted({r["campaign"] for r in rows}):
        selected = [r for r in rows if r["campaign"]==campaign]
        windows = {}
        for window in selected[0]["by_elapsed_window"]:
            values = [r["by_elapsed_window"][window] for r in selected]
            windows[window] = {k:bounds([v[k] for v in values if v[k] is not None]) for k in (
                "eligible_range_time_fraction","low_eligible_time_fraction","high_eligible_time_fraction","near_500k_450_to_550k_time_fraction","below_240k_time_fraction")}
        campaigns[campaign] = {"sessions":len(selected),"content_groups":len({r["content_id"] for r in selected}),
            "profiles":len({r["profile"] for r in selected}),"first_bwe_300k_count":sum(abs(r["first_bwe_bps"]-300000)<1 for r in selected),
            "first_departure_from_300k_ms_min_median_max":bounds([r["first_departure_from_300k_ms"] for r in selected if r["first_departure_from_300k_ms"] is not None]),
            "session_fraction_ranges_by_elapsed_window":windows,
            "dependence":"Each statistic describes existing sessions within this campaign; no pooled campaign effect, population interval or independent-source count is inferred."}
        if label == "V12":
            campaigns[campaign]["support_design_comparison"] = {
                "original_target_in_registered_window":sum(r["development_counterfactual_support_timings"]["registered_window_target_passed"] for r in selected),
                "continuous_range_in_same_registered_window":sum(r["development_counterfactual_support_timings"]["registered_window_continuous_range_passed"] for r in selected),
                "target_available_at_any_time_after_registered_close":sum(r["development_counterfactual_support_timings"]["first_eligible_target_history_after_9300ms"] is not None for r in selected)}
    return {"label":label,"development_only":True,"protocol_sha256":protocol_sha,"capture_index_sha256":index_sha,
        "verified_session_files":file_count,"sessions":rows,"campaigns":campaigns,
        "interpretation":"V11D later BWE is affected by prior caps. V12 keeps 4Mbps and has no treatment. Neither panel is an independent action-effect test here."}


def main(out):
    if out.exists():
        raise ValueError("preserve completed diagnosis")
    receipt = read(REPO / "docs/storage-receipts/native-support-validation-v12-support-20261014-01.json")
    prior = read(REPO / "reports/native-v11d-support-diagnosis.json")
    panels = [diagnose_panel("V12",CACHE / "native-support-validation-v12-support",receipt["protocol_sha256"],receipt["capture_index_sha256"]),
              diagnose_panel("V11D",CACHE / "native-clock-action-turntcp-v11d",prior["protocol_sha256"],prior["capture_index_sha256"])]
    result = {"abi":"native_bwe_dynamics_development_diagnosis_v13","anchor_commit":"a7ea1b0","tool_sha256":sha(Path(__file__).resolve()),
        "outcomes_accessed":False,"action_effect_estimated":False,"controller_fitted":False,"panels_pooled":False,
        "projection":["sender times/BWE feature zero and validity; assigned caps/native readback","registered content/profile/campaign IDs and rate schedules","standalone actual-run clock markers"],
        "excluded":["frame_events.json","summary.json","queue_evidence.json","events.jsonl.gz","sender encoded_meter and feedback_events","all prior outcome-analysis reports"],
        "support_counterfactuals_are_diagnostics_not_qualification_changes":True,"panels":panels}
    # Keep the allowed sample-level projection outside Git; commit a compact
    # diagnostic plus an immutable hash/path for reproduction and plotting.
    projection=CACHE/"native-bwe-dynamics-v13-projection.json"
    if projection.exists():raise ValueError("preserve completed sample projection")
    projection.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    compact={**result,"sample_projection":{"path":str(projection),"sha256":sha(projection)},"panels":[]}
    for panel in panels:
        compact["panels"].append({**panel,"sessions":[{k:v for k,v in row.items() if k not in ("sender_bwe_timeline","trace_ticks")} for row in panel["sessions"]]})
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(compact,sort_keys=True,indent=2)+"\n")
    return {p["label"]:p["campaigns"] for p in panels}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=REPO/"reports/native-v13-bwe-dynamics-diagnosis.json")
    args=parser.parse_args()
    print(json.dumps(main(args.out)))
