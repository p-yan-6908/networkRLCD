"""Outcome-free V13/M1 development diagnosis, never a gate repair.

Project baseline sender statistics and pre-decision replay/queue timing only.
Quality, receiver feedback, frame events and per-hold outcomes stay unopened.
All session seals are verified before any permitted telemetry is decoded.
"""
from __future__ import annotations

import bisect
import gzip
import hashlib
import importlib.util
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("m2_v13_clock", REPO / "tools/design_native_v13.py")
v13 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v13)
OUTPUT = REPO / "reports/native-bwe-mechanisms-m2-diagnosis.json"
TRAIN, HOLDOUT = [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10]
WINDOWS = [(0, 3000), (3000, 6000), (6000, 12000), (12000, 16000), (16000, 18000)]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return v13.sha(path)


def stats(values):
    a = list(values)
    return {"n": len(a), "min": min(a), "mean": st.mean(a), "median": st.median(a),
        "p95": float(np.quantile(a, .95)), "max": max(a)} if a else None


def verify(root, receipt):
    r = read(REPO / "docs/storage-receipts" / receipt)
    assert r["remote_fresh_download_verified"] and r["archive_and_restored_file_checksums_verified"]
    assert sha(root / "protocol.json") == r["protocol_sha256"]
    assert sha(root / "capture_index.json") == r["capture_index_sha256"]
    assert sha(root / "support_clock_transport_gate.json") == r["gate_sha256"]
    protocol, index = read(root / "protocol.json"), read(root / "capture_index.json")
    assert index["protocol_sha256"] == sha(root / "protocol.json")
    assert [s["trial"] for s in index["sessions"]] == protocol["randomized_order"]
    count = 0
    for s in index["sessions"]:
        directory = root / "sessions" / s["trial"]
        assert sha(directory / "integrity.json") == s["integrity_manifest_sha256"]
        seal = v13.core.verify_directory(directory)
        count += seal["file_count"]
    for trial in protocol["trials"]:
        assert sha(root / trial["panel"]) == trial["panel_sha256"]
    return protocol, index, r, count


def window_sender(points, lo, hi):
    selected = [p for p in points if lo <= p["ms"] < hi]
    def mean(field):
        return st.mean(p[field] for p in selected if p[field] is not None) if any(p[field] is not None for p in selected) else None
    return {"samples": len(selected), "bwe_geo_bps": 500000 * 2 ** mean("x") if mean("x") is not None else None,
        "mean_x": mean("x"), "rtt_ms": mean("rtt"), "rtp_payload_mbps": mean("send_mbps"),
        "encoder_fps": mean("fps"), "encode_ms_per_frame": mean("encode_ms"),
        "packet_send_delay_ms": mean("packet_delay_ms"),
        "sample_gap_ms": stats(p["interval"] for p in selected if p["interval"] > 0)}


def project_session(root, trial, sequence):
    directory = root / "sessions" / trial["id"]
    sender = read(directory / "sender_observations.json")
    start = sender["measurement_start_ms"]
    q = sender["support_screen"]["qualification"]
    assert trial["support_only"] and q["passed"] and not sender["support_screen"]["action_assigned"]
    for d in sender["decisions"]:
        assert d["actuator_assignment"] is None
        assert d["actuation_readback"]["encoder_max_bitrate_bps"] == 4000000
        assert d["actuation_readback"]["receiver_jitter_buffer_target_ms"] == 0
    points = []
    for d in sender["decisions"]:
        if d["sample_ms"] - start > q["elapsed_ms"]:
            break
        f = d["policy_input"]["features"]
        points.append({"ms": d["sample_ms"] - start, "bwe": 4000000 * f[0],
            "x": math.log2(8 * f[0]) if f[9] == 1 and f[0] > 0 else None,
            "rtt": f[1] * 150 if f[10] else None, "send_mbps": f[3] * 4 if f[12] else None,
            "fps": f[4] * 30 if f[12] else None, "encode_ms": f[5] * (1000 / 30) if f[13] else None,
            "packet_delay_ms": f[6] * 150 if f[14] else None, "interval": f[15] * 100})
    markers = v13.core.load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
    clock = v13.core.validate_markers(markers, TRAIN, HOLDOUT)
    assert clock["passed"]
    origin, vertices = v13.core.feasible_polygon([markers[i] for i in TRAIN])
    def mapped(node):
        lo, hi = v13.core.mapped_browser_range(node, origin, vertices)
        return (lo + hi) / 2 - start, (hi - lo) / 2
    def node_at(elapsed):
        return st.mean(a * (start + elapsed - origin) + b for a, b in vertices)
    lo_node, hi_node = node_at(0), node_at(q["elapsed_ms"])
    replay, phases = [], []
    # Retain only permitted fields, and only events before the support decision.
    service, offers, forwards = defaultdict(list), defaultdict(list), defaultdict(list)
    earliest_service = None
    with gzip.open(directory / "events.jsonl.gz", "rt") as stream:
        for line in stream:
            e = json.loads(line)
            kind = e.get("kind")
            if kind == "phase":
                phases.append({k: e[k] for k in ("phase", "at_ms", "trace_mbps")})
            elif kind == "trace_capacity":
                replay.append({k: e[k] for k in ("phase", "sample_index", "at_ms", "capacity_mbps")})
            elif kind == "service" and e["from_ms"] < hi_node:
                service[e["direction"]].append({k: e[k] for k in ("from_ms", "at_ms", "capacity_mbps", "queue_before_wire_bytes", "queue_after_wire_bytes")})
                earliest_service = min(earliest_service, e["from_ms"]) if earliest_service is not None else e["from_ms"]
            elif kind == "offer" and e["at_ms"] <= hi_node:
                offers[e["direction"]].append({k: e[k] for k in ("at_ms", "wire_bytes", "dropped", "queue_before_wire_bytes", "queue_after_wire_bytes")})
            elif kind == "forward" and e["at_ms"] <= hi_node:
                forwards[e["direction"]].append({k: e[k] for k in ("at_ms", "serialization_done_ms")})
    assert len(phases) == 3 and len(replay) == 36
    jitter = [e["at_ms"] - next(p["at_ms"] for p in phases if p["phase"] == e["phase"]) - e["sample_index"] * 1000 for e in replay]
    assert max(abs(j) for j in jitter) <= 150
    ticks = [{**e, "elapsed_ms": mapped(e["at_ms"])[0], "clock_halfwidth_ms": mapped(e["at_ms"])[1]} for e in replay]
    area = 0.0
    rate, cursor = 5.0, 0.0
    for tick in ticks:
        if tick["elapsed_ms"] > q["elapsed_ms"]:
            break
        if tick["elapsed_ms"] > cursor:
            area += rate * (tick["elapsed_ms"] - cursor)
        rate, cursor = tick["capacity_mbps"], max(cursor, tick["elapsed_ms"])
    area += rate * (q["elapsed_ms"] - cursor)
    def queue_window(direction, lo, hi):
        a, b = node_at(lo), node_at(hi)
        area_q, elapsed = 0.0, b - a
        gaps, positive, maximum = [], 0.0, 0.0
        for e in service[direction]:
            u, v = max(a, e["from_ms"]), min(b, e["at_ms"])
            if v <= u:
                continue
            gaps.append(e["at_ms"] - e["from_ms"])
            rate = e["capacity_mbps"] * 125
            q0 = max(0, e["queue_before_wire_bytes"] - rate * (u - e["from_ms"]))
            t = min(v - u, q0 / rate) if rate > 0 else v - u
            area_q += q0 * t - rate * t * t / 2
            positive += t
            maximum = max(maximum, q0)
        selected = [e for e in offers[direction] if a <= e["at_ms"] < b]
        late = [e["at_ms"] - e["serialization_done_ms"] - 25 for e in forwards[direction] if a <= e["at_ms"] < b]
        return {"mean_queue_bytes": area_q / elapsed if elapsed else None,
            "positive_queue_fraction": positive / elapsed if elapsed else None, "maximum_service_start_queue_bytes": maximum,
            "offer_packets": len(selected), "offered_wire_bytes": sum(e["wire_bytes"] for e in selected),
            "overflow_wire_bytes": sum(e["wire_bytes"] for e in selected if e["dropped"]),
            "pump_gap_ms": stats(gaps), "forward_timer_lateness_ms": stats(late)}
    bootstrap_start_ms = mapped(earliest_service)[0]
    queues = {direction: {name: queue_window(direction, lo, hi) for name, lo, hi in
        [("bootstrap", bootstrap_start_ms, 0), ("startup_0_3s", 0, 3000), ("conditioning_3_12s", 3000, 12000),
         ("predecision_12_18s", 12000, 18000), ("all_predecision", 0, q["elapsed_ms"])]}
        for direction in ("a_to_b", "b_to_a")}
    first_change = next((p["ms"] for p in points if p["x"] is not None and abs(p["bwe"] - 300000) > 1), None)
    timeline = []
    for lo, hi in [(i * 1000, (i + 1) * 1000) for i in range(18)]:
        w = window_sender(points, lo, hi)
        timeline.append({"from_ms": lo, "to_ms": hi, **w})
    return {"trial": trial["id"], "content": trial["content_id"], "profile": trial["network_profile_id"],
        "family": trial["network_family"], "campaign": trial["network_campaign_id"], "repeat": trial["repetition"], "sequence": sequence,
        "x": q["continuous_log2_bwe"], "bwe_geo_bps": q["geometric_mean_bwe_bps"],
        "history_range_octaves": math.log2(max(q["bwe_history_bps"]) / min(q["bwe_history_bps"])),
        "first_bwe_bps": points[0]["bwe"], "first_sample_ms": points[0]["ms"], "first_departure_from_300k_ms": first_change,
        "startup_peak_x": max(p["x"] for p in points if p["ms"] < 3000 and p["x"] is not None),
        "support_elapsed_ms": q["elapsed_ms"], "sender_windows": {f"{lo}_{hi}": window_sender(points, lo, hi) for lo, hi in WINDOWS},
        "per_second_sender": timeline, "queues": queues,
        "replay": {"first_phase_elapsed_ms": ticks[0]["elapsed_ms"], "first_phase_clock_halfwidth_ms": ticks[0]["clock_halfwidth_ms"],
            "maximum_tick_abs_jitter_ms": max(abs(j) for j in jitter), "mean_tick_jitter_ms": st.mean(jitter),
            "capacity_exposure_mean_mbps": area / q["elapsed_ms"], "actual_ticks": ticks,
            "bootstrap_to_measurement_ms": -bootstrap_start_ms},
        "clock_max_heldout_width_ms": clock["max_held_out_width_ms"],
        "clock_join": "Training-marker feasible affine interval; window statistics use its center and preserve boundary uncertainty."}


def predictors(r):
    sw = r["sender_windows"]
    ab = r["queues"]["a_to_b"]
    def val(stats, key):
        return stats[key] if stats else None
    return {
        "trace_replay.phase_onset_ms": r["replay"]["first_phase_elapsed_ms"],
        "trace_replay.tick_jitter_ms": r["replay"]["mean_tick_jitter_ms"],
        "trace_replay.exposure_log2": math.log2(r["replay"]["capacity_exposure_mean_mbps"]),
        "initial_observed.first_bwe_log2": math.log2(r["first_bwe_bps"] / 500000),
        "initial_observed.first_departure_ms": r["first_departure_from_300k_ms"],
        "initial_observed.startup_peak_x": r["startup_peak_x"],
        "conditioning.bwe_0_3s": sw["0_3000"]["mean_x"],
        "conditioning.bwe_3_6s": sw["3000_6000"]["mean_x"],
        "conditioning.bwe_6_12s": sw["6000_12000"]["mean_x"],
        "conditioning.bwe_12_16s": sw["12000_16000"]["mean_x"],
        "conditioning.bwe_16_18s": sw["16000_18000"]["mean_x"],
        "content_demand.send_0_3s_mbps": sw["0_3000"]["rtp_payload_mbps"],
        "content_demand.send_6_12s_mbps": sw["6000_12000"]["rtp_payload_mbps"],
        "content_demand.encode_0_3s_ms": sw["0_3000"]["encode_ms_per_frame"],
        "transport_queue.rtt_0_3s_ms": sw["0_3000"]["rtt_ms"],
        "transport_queue.rtt_6_12s_ms": sw["6000_12000"]["rtt_ms"],
        "transport_queue.bootstrap_ms": r["replay"]["bootstrap_to_measurement_ms"],
        "transport_queue.bootstrap_queue_bytes": ab["bootstrap"]["mean_queue_bytes"],
        "transport_queue.queue_0_3s_bytes": ab["startup_0_3s"]["mean_queue_bytes"],
        "transport_queue.queue_3_12s_bytes": ab["conditioning_3_12s"]["mean_queue_bytes"],
        "transport_queue.queue_12_18s_bytes": ab["predecision_12_18s"]["mean_queue_bytes"],
        "transport_queue.pump_gap_p95_ms": val(ab["all_predecision"]["pump_gap_ms"], "p95"),
        "transport_queue.forward_lateness_p95_ms": val(ab["all_predecision"]["forward_timer_lateness_ms"], "p95"),
        "run_timing.first_sample_ms": r["first_sample_ms"],
        "run_timing.qualification_ms": r["support_elapsed_ms"],
        "run_timing.sample_gap_0_3s_ms": val(sw["0_3000"]["sample_gap_ms"], "mean"),
        "run_timing.sample_gap_6_12s_ms": val(sw["6000_12000"]["sample_gap_ms"], "mean"),
    }


def association(pairs, key):
    selected = [p for p in pairs if p["deltas"][key] is not None]
    x, y = np.array([p["deltas"][key] for p in selected]), np.array([p["delta_x"] for p in selected])
    if len(x) < 4 or np.std(x) < 1e-12:
        return {"n": len(x), "correlation": None, "reason": "constant or insufficient predictor; no variance attribution"}
    correlation = float(np.corrcoef(x, y)[0, 1])
    sensitivities = []
    for profile in sorted({p["profile"] for p in selected}):
        keep = [i for i, p in enumerate(selected) if p["profile"] != profile]
        sensitivities.append(float(np.corrcoef(x[keep], y[keep])[0, 1]) if np.std(x[keep]) > 1e-12 else None)
    failed = [abs(p["deltas"][key]) for p in selected if not p["repeatability_passed"]]
    passed = [abs(p["deltas"][key]) for p in selected if p["repeatability_passed"]]
    return {"n": len(x), "correlation": correlation, "univariate_descriptive_r_squared": correlation ** 2,
        "leave_one_profile_correlations": sensitivities, "passing_absolute_delta": stats(passed),
        "failing_absolute_delta": stats(failed),
        "limits": "Exploratory paired association; eight nested profiles, shared content, collinear histories/mediators. Not an additive causal contribution or population estimate."}


def main():
    if OUTPUT.exists():
        raise ValueError("preserve completed mechanism diagnosis")
    v13.verify()
    panels = {}
    roots = [("V13", v13.SUPPORT_ROOT, "native-continuous-validation-v13-support-20261014-01.json"),
        ("M1", v13.CACHE / "native-bwe-reliability-m1", "native-bwe-reliability-m1-20261014-01.json")]
    # Verify both entire inventories before the first expanded projection.
    checked = [(name, root, verify(root, receipt)) for name, root, receipt in roots]
    for name, root, (protocol, index, receipt, count) in checked:
        trials = {t["id"]: t for t in protocol["trials"]}
        rows = [project_session(root, trials[s["trial"]], i) for i, s in enumerate(index["sessions"])]
        panels[name] = {"registration_commit": receipt["scientific_registration_commit"], "archive_revision": receipt["revision"],
            "verified_session_files": count, "protocol_sha256": sha(root / "protocol.json"), "sessions": rows,
            "sources_pooled": False}
    rows = panels["V13"]["sessions"]
    groups = defaultdict(list)
    for row in rows:
        groups[row["content"], row["profile"]].append(row)
    pairs = []
    for (content, profile), group in sorted(groups.items()):
        a, b = sorted(group, key=lambda r: r["repeat"])
        pa, pb = predictors(a), predictors(b)
        pairs.append({"content": content, "profile": profile, "family": a["family"],
            "replicate_x": [a["x"], b["x"]], "delta_x": b["x"] - a["x"],
            "repeatability_passed": abs(b["x"] - a["x"]) <= .25,
            "per_second_delta_x": [wb["mean_x"] - wa["mean_x"] for wa, wb in zip(a["per_second_sender"], b["per_second_sender"], strict=True)],
            "deltas": {k: pb[k] - pa[k] if pa[k] is not None and pb[k] is not None else None for k in pa}})
    grand = st.mean(r["x"] for r in rows)
    contents = {c: st.mean(r["x"] for r in rows if r["content"] == c) for c in {r["content"] for r in rows}}
    profiles = {p: st.mean(r["x"] for r in rows if r["profile"] == p) for p in {r["profile"] for r in rows}}
    cp = {(c, p): st.mean(r["x"] for r in rows if r["content"] == c and r["profile"] == p) for c, p in groups}
    ss = {"content_main": 16 * sum((m - grand) ** 2 for m in contents.values()),
        "profile_main": 4 * sum((m - grand) ** 2 for m in profiles.values()),
        "content_profile_interaction": 2 * sum((m - contents[c] - profiles[p] + grand) ** 2 for (c, p), m in cp.items()),
        "within_context_repeats": sum((r["x"] - cp[r["content"], r["profile"]]) ** 2 for r in rows)}
    total = sum((r["x"] - grand) ** 2 for r in rows)
    assert abs(sum(ss.values()) - total) < 1e-10
    result = {"abi": "native_bwe_mechanisms_m2_diagnosis_v1", "anchor_commit": "7427f48",
        "tool_sha256": sha(Path(__file__).resolve()), "panels": panels, "v13_repeat_pairs": pairs,
        "v13_finite_panel_ss_decomposition": {k: {"sum_squares_octaves_squared": value, "fraction_of_total": value / total} for k, value in ss.items()},
        "v13_paired_associations": {k: association(pairs, k) for k in pairs[0]["deltas"]},
        "outcomes_read": False, "controller_fitted": False, "prior_gates_changed": False,
        "allowed_inputs": ["Sender baseline pre-decision BWE, linked RTCP RTT, RTP demand and encoding/poll timing", "Actual clock markers and measured-rate ticks", "Pre-decision queue service/arrival, bootstrap and forward timer timing"],
        "excluded": ["Frame events/quality/deadlines", "receiver feedback", "encoded-meter frame records", "post-decision delivery/QoE or per-hold relay costs"],
        "scope": "Development diagnosis of finite reused V13/M1 panels. Source/profile/content SS describes between-context structure; paired associations describe repeat deviations and cannot separate causal estimator/history/queue contributions."}
    v13.write(OUTPUT, result)
    ranked = sorted(result["v13_paired_associations"].items(), key=lambda x: abs(x[1]["correlation"] or 0), reverse=True)
    print(json.dumps({"verified_files": {n: p["verified_session_files"] for n, p in panels.items()},
        "v13_ss_fractions": {k: v["fraction_of_total"] for k, v in result["v13_finite_panel_ss_decomposition"].items()},
        "strongest_descriptive_associations": [{"variable": k, "correlation": v["correlation"]} for k, v in ranked[:15]]}))


if __name__ == "__main__":
    main()
