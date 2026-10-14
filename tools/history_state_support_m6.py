"""Finite observable-state matching; support BWE only, no action/QoE model.

All candidate calipers are physical constants. Centers use current/past fields,
never future BWE. Development alone selects a representation. Fresh validation
first freezes match membership, then opens the registered future BWE responses.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import math
import statistics as st
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("m6_frozen_m5_dependencies", REPO / "tools/measure_prefix_memory_m5.py")
m5 = importlib.util.module_from_spec(s)
s.loader.exec_module(m5)
v, r = m5.v, m5.r
TRANSITIONS = ((18000, 24000), (24000, 30000), (30000, 36000))
PREFIXES = ("ascending_prefix", "descending_prefix")
CALIPERS = {"x": .125, "trend": .125, "send": .125, "rtt": 10., "rtt_drift": 10.,
            "fps": 1.5, "encode": 1., "forward": .125, "queue": .1, "drop": .005}
CANDIDATES = {
    "b0_instantaneous": ["x"], "h01_bwe_trend": ["x", "trend"],
    "h02_send_rate": ["x", "send"], "h03_rtt_drift": ["x", "rtt_drift"],
    "h04_rtt_level": ["x", "rtt"], "h05_encode_history": ["x", "encode"],
    "h06_fps_history": ["x", "fps"], "h07_relay_forward": ["x", "forward"],
    "h08_relay_queue": ["x", "queue"], "h09_relay_drop": ["x", "drop"],
    "h10_trend_send": ["x", "trend", "send"],
    "h11_trend_rtt": ["x", "trend", "rtt_drift"],
    "h12_trend_queue": ["x", "trend", "queue"],
    "h13_forward_queue": ["x", "forward", "queue"],
}


def empirical_distances(a, b):
    a, b = np.sort(a), np.sort(b)
    assert len(a) and len(b)
    edges = np.unique(np.r_[a, b])
    w1 = float(np.sum(np.abs(np.searchsorted(a, edges[:-1], side="right") / len(a) -
                             np.searchsorted(b, edges[:-1], side="right") / len(b)) * np.diff(edges)))
    qs = np.unique(np.r_[np.arange(len(a) + 1) / len(a), np.arange(len(b) + 1) / len(b)])
    mid = (qs[:-1] + qs[1:]) / 2
    winf = float(np.max(np.abs(a[np.ceil(mid * len(a)).astype(int) - 1] -
                               b[np.ceil(mid * len(b)).astype(int) - 1])))
    return w1, winf


def beginning_polygon(directory, sender_start):
    original = v.core.load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
    browser = v.read(directory / "instrument_clock_browser.json")
    node = v.read(directory / "instrument_clock_node.json")
    labels = {name + suffix for name in ("session_open", "pre_sdp", "ready_inactive", "block_0")
              for suffix in ("_before", "_after")}
    extra = [{**n, "browser_receive_ms": b["browser_receive_ms"]} for n, b in zip(node, browser, strict=True)
             if n["role"] == "train" and n["label"] in labels]
    train = [original[i] for i in (0, 1, 3)] + extra
    assert len(train) == 35
    assert max(t["browser_receive_ms"] for t in train) < sender_start + 17900
    return v.core.feasible_polygon(train)


def sender_features(points, cutoff):
    current = next(p for p in reversed(points) if p["ms"] <= cutoff + 1e-5)
    groups = [[p for p in points if cutoff - hi < p["ms"] <= cutoff - lo]
              for lo, hi in ((0, 2000), (2000, 4000))]
    assert all(len(g) >= 17 and max(b["ms"] - a["ms"] for a, b in zip(g, g[1:])) <= 250 for g in groups)
    def mean(group, field):
        vals = [p[field] for p in group if p[field] is not None]
        return st.mean(vals) if len(vals) >= .8 * len(group) else None
    now, past = groups
    xn, xp = mean(now, "x"), mean(past, "x")
    rn, rp = mean(now, "rtt"), mean(past, "rtt")
    sent = mean(now, "send_bps")
    return {"x": current["x"], "trend": xn - xp if xn is not None and xp is not None else None,
            "send": math.log2(sent / 500000) if sent is not None and sent > 0 else None,
            "rtt": rn, "rtt_drift": rn - rp if rn is not None and rp is not None else None,
            "fps": mean(now, "fps"), "encode": mean(now, "encode")}


def project(root, gate, include_future):
    """Whitelist support fields; no receiver pixels/quality/action labels opened."""
    assert gate["passed"]
    v.core.check_capture_integrity(root)
    result = []
    for row in gate["sessions"]:
        directory = root / "sessions" / row["trial"]
        sender = v.read(directory / "sender_observations.json")
        start = sender["measurement_start_ms"]
        points = []
        for d in sender["decisions"]:
            assert d["actuator_assignment"] is None
            assert d["actuation_readback"]["encoder_max_bitrate_bps"] == 4000000
            f = d["policy_input"]["features"]
            points.append({"ms": d["sample_ms"] - start,
                           "x": math.log2(f[0] * 8) if f[9] == 1 and f[0] > 0 else None,
                           "send_bps": f[3] * 4000000 if f[12] == 1 else None,
                           "rtt": f[1] * 150 if f[10] == f[11] == 1 and f[2] * 1000 <= 2000 else None,
                           "fps": f[4] * 30 if f[12] == 1 else None,
                           "encode": f[5] * (1000 / 30) if f[13] == 1 else None})
        origin, vertices = beginning_polygon(directory, start)
        windows = {}
        for now, later in TRANSITIONS:
            cutoff = row["windows"][str(now)]["history_ms"][-1]
            lo = max(a * (start + cutoff - 2100 - origin) + b for a, b in vertices)
            hi = min(a * (start + cutoff - 100 - origin) + b for a, b in vertices)
            boundary_width = max(a * (start + cutoff - 100 - origin) + b for a, b in vertices) - hi
            assert hi > lo and boundary_width <= 50
            windows[now] = {"lo": lo, "hi": hi, "bytes": 0, "offered": 0, "dropped": 0,
                            "queue_area": 0., "service_ms": 0., "boundary_width_ms": boundary_width,
                            "cutoff": cutoff, "features": sender_features(points, cutoff)}
        # First-phase mapping uses only training already available before 18 s.
        # Full intervals only: no relay event beyond the conservative past bound.
        with gzip.open(directory / "events.jsonl.gz", "rt") as stream:
            for line in stream:
                e = json.loads(line)
                if e.get("direction") != "a_to_b" or e.get("kind") not in ("service", "offer", "forward"):
                    continue
                for w in windows.values():
                    if not w["lo"] <= e["at_ms"] <= w["hi"]:
                        continue
                    if e["kind"] == "forward":
                        w["bytes"] += e["wire_bytes"]
                    elif e["kind"] == "offer":
                        w["offered"] += e["wire_bytes"]
                        w["dropped"] += e["wire_bytes"] if e["dropped"] else 0
                    elif e["from_ms"] >= w["lo"]:
                        duration = e["at_ms"] - e["from_ms"]
                        rate, q = e["capacity_mbps"] * 125, e["queue_before_wire_bytes"]
                        positive = min(duration, q / rate) if rate > 0 else duration
                        w["queue_area"] += q * positive - rate * positive ** 2 / 2
                        w["service_ms"] += duration
        for now, later in TRANSITIONS:
            w = windows[now]
            duration = w["hi"] - w["lo"]
            forward_bps = w["bytes"] * 8000 / duration
            feature = {**w["features"], "forward": math.log2(forward_bps / 500000) if forward_bps > 0 else None,
                       "queue": w["queue_area"] / duration / 30000 if w["service_ms"] >= .99 * duration else None,
                       "drop": w["dropped"] / w["offered"] if w["offered"] > 0 else None}
            item = {"trial": row["trial"], "pair_id": row["pair_id"], "prefix": row["prefix"],
                    "content": row["content_id"], "now": now, "later": later, "cutoff_ms": w["cutoff"],
                    "features": feature, "relay_clock_boundary_width_ms": w["boundary_width_ms"],
                    "relay_complete_interval_coverage": w["service_ms"] / duration,
                    "encoder_cap_bps": 4000000, "receiver_target_ms": 0,
                    "elapsed_is_exact_landmark_stratum": True}
            if include_future:
                item["future_x"] = row["windows"][str(later)]["x"]
            result.append(item)
    return result


def near(row, center, names):
    return all(row["features"].get(k) is not None and abs(row["features"][k] - center[k]) <= CALIPERS[k] + 1e-12
               for k in names)


def grouped(rows):
    return {f"{content}__{now}": [x for x in rows if x["content"] == content and x["now"] == now]
            for content in sorted({x["content"] for x in rows}) for now, _ in TRANSITIONS}


def choose_centers(rows):
    centers = {name: {} for name in CANDIDATES}
    for key, items in grouped(rows).items():
        def counts(names, center):
            return [sum(x["prefix"] == p and near(x, center, names) for x in items) for p in PREFIXES]
        possible = [x for x in items if x["features"]["x"] is not None]
        baseline = min(possible, key=lambda x: (-min(counts(["x"], {"x": x["features"]["x"]})),
                                                -sum(counts(["x"], {"x": x["features"]["x"]})), x["trial"]))
        level = baseline["features"]["x"]
        centers["b0_instantaneous"][key] = {"x": level}
        for name, names in list(CANDIDATES.items())[1:]:
            proposals = [{k: (level if k == "x" else x["features"][k]) for k in names}
                         for x in sorted(items, key=lambda x: x["trial"])
                         if near(x, {"x": level}, ["x"]) and all(x["features"].get(k) is not None for k in names)]
            centers[name][key] = min(proposals, key=lambda c: (-min(counts(names, c)), -sum(counts(names, c)))) if proposals else None
    return centers


def memberships(rows, name, centers):
    return {key: [x for x in items if centers[key] is not None and near(x, centers[key], CANDIDATES[name])]
            for key, items in grouped(rows).items()}


def describe(items):
    a, b = [[x["future_x"] for x in items if x["prefix"] == p] for p in PREFIXES]
    if not a or not b:
        return None
    w1, winf = empirical_distances(a, b)
    return {"ascending_n": len(a), "descending_n": len(b), "ascending_full_spread": float(np.ptp(a)),
            "descending_full_spread": float(np.ptp(b)), "w1": w1, "winf": winf,
            "signed_mean": float(np.mean(b) - np.mean(a)), "ascending_values": a, "descending_values": b}


def select(rows):
    centers = choose_centers(rows)
    summaries = {}
    baseline_groups = memberships(rows, "b0_instantaneous", centers["b0_instantaneous"])
    for name in CANDIDATES:
        groups = memberships(rows, name, centers[name])
        cells = {}
        for key, items in groups.items():
            counts = [sum(x["prefix"] == p for x in items) for p in PREFIXES]
            base = [sum(x["prefix"] == p for x in baseline_groups[key]) for p in PREFIXES]
            retention = [n / b if b else 0. for n, b in zip(counts, base)]
            cells[key] = {"counts": counts, "baseline_counts": base, "retention": retention,
                          "coverage_passed": min(counts) >= 6 and min(retention) >= .8,
                          "future": describe(items)}
        valid = [x["future"] for x in cells.values() if x["future"] is not None]
        summaries[name] = {"dimensions": len(CANDIDATES[name]), "relay_assisted": any(x in CANDIDATES[name] for x in ("forward", "queue", "drop")),
                           "cells": cells, "coverage_cells": sum(x["coverage_passed"] for x in cells.values()), "valid_cells": len(valid),
                           "worst_future_spread": max((max(x["ascending_full_spread"], x["descending_full_spread"]) for x in valid), default=1e9),
                           "mean_future_w1_for_development_selection_only": st.mean(x["w1"] for x in valid) if len(valid) == 6 else 1e9}
    def rank(name):
        x = summaries[name]
        return (-x["coverage_cells"], -x["valid_cells"], x["worst_future_spread"], x["mean_future_w1_for_development_selection_only"], x["relay_assisted"], name)
    small = min((n for n in CANDIDATES if len(CANDIDATES[n]) == 2), key=rank)
    larger = min((n for n in CANDIDATES if len(CANDIDATES[n]) == 3), key=rank)
    a, b = summaries[small], summaries[larger]
    use_larger = (a["worst_future_spread"] > 1e-12 and b["coverage_cells"] >= a["coverage_cells"] and
                  b["valid_cells"] >= a["valid_cells"] and b["worst_future_spread"] <= .8 * a["worst_future_spread"])
    chosen = larger if use_larger else small
    return {"abi": "native_history_state_m6_development_selection_v1", "selected": chosen,
            "features": CANDIDATES[chosen], "relay_assisted": summaries[chosen]["relay_assisted"],
            "centers": {"b0_instantaneous": centers["b0_instantaneous"], chosen: centers[chosen]},
            "all_candidate_centers": centers, "development_candidates": summaries,
            "two_feature_winner": small, "three_feature_winner": larger, "third_dimension_20pct_rule_passed": use_larger,
            "development_pass_is_not_required_to_attempt_fresh_falsification": True,
            "candidate_is_qualified": False, "controller_fitted": False,
            "native_common_support_established": False, "delivery_qoe_action_outcomes_read": False}


def support_membership_gate(rows, selection):
    result, passed = {}, True
    groups = {name: memberships(rows, name, centers) for name, centers in selection["centers"].items()}
    for key in grouped(rows):
        baseline = groups["b0_instantaneous"][key]
        entries = {}
        for name in selection["centers"]:
            items = groups[name][key]
            counts = [sum(x["prefix"] == p for x in items) for p in PREFIXES]
            base = [sum(x["prefix"] == p for x in baseline) for p in PREFIXES]
            retention = [n / b if b else 0 for n, b in zip(counts, base)]
            ok = min(counts) >= 4 and min(retention) >= .8
            passed &= ok
            entries[name] = {"counts_by_prefix": dict(zip(PREFIXES, counts)), "retention_of_baseline": retention,
                             "passed": ok, "matched_trials": sorted(x["trial"] for x in items)}
        result[key] = entries
    return {"abi": "native_history_state_m6_membership_gate_v1", "passed": bool(passed), "cells": result,
            "future_bwe_used_for_matching": False, "required_matched_originals_per_prefix": 4,
            "required_fraction_of_original_prefix_attempts": .5, "minimum_baseline_retention": .8,
            "selected_state": selection["selected"], "controller_fitted": False}


def uncertainty(items, all_pairs, seed):
    rng = np.random.default_rng(seed)
    grouped_pairs = {p: [x for x in items if x["pair_id"] == p] for p in all_pairs}
    draws = rng.integers(0, len(all_pairs), (10000, len(all_pairs)))
    means, distances, failed = [], [], 0
    for draw in draws:
        sample = [x for i in draw for x in grouped_pairs[all_pairs[i]]]
        d = describe(sample)
        if d is None:
            failed += 1
        else:
            means.append(d["signed_mean"]); distances.append(d["w1"])
    return {"seed": seed, "planned_draws": 10000, "valid_draws": len(means), "empty_arm_draws": failed,
            "paired_cluster_bootstrap": True,
            "mean_95pct": np.quantile(means, [.025, .975]).tolist() if means else None,
            "w1_upper_975": float(np.quantile(distances, .975)) if distances else None,
            "limits": "Original capture pairs resampled; fixed centers/predicates; finite reused-source capture uncertainty, not a causal conditional-prefix test or population interval."}


def evaluate(rows, selection, membership):
    assert membership["passed"]
    results, success = {}, True
    for ni, (name, centers) in enumerate(selection["centers"].items()):
        cells = {}
        for ci, (key, items) in enumerate(memberships(rows, name, centers).items()):
            assert sorted(x["trial"] for x in items) == membership["cells"][key][name]["matched_trials"]
            all_pairs = sorted({x["pair_id"] for x in grouped(rows)[key]})
            d = describe(items)
            u = uncertainty(items, all_pairs, 20261120 + ni * 100 + ci)
            components = {"at_least_9500_valid_cluster_draws": u["valid_draws"] >= 9500,
                          "ascending_future_full_spread_at_most_025": d["ascending_full_spread"] <= .25,
                          "descending_future_full_spread_at_most_025": d["descending_full_spread"] <= .25,
                          "future_winf_at_most_025": d["winf"] <= .25,
                          "future_mean_interval_inside_025": u["mean_95pct"][0] >= -.25 and u["mean_95pct"][1] <= .25,
                          "future_w1_upper_975_at_most_025": u["w1_upper_975"] <= .25}
            cells[key] = {**d, "uncertainty": u, "components": components, "passed": all(components.values())}
        results[name] = {"cells": cells, "all_six_cells_repeatable": all(x["passed"] for x in cells.values())}
    selected = selection["selected"]
    improvement = {}
    for content in sorted({x["content"] for x in rows}):
        keys = [f"{content}__{now}" for now, _ in TRANSITIONS]
        b = [results["b0_instantaneous"]["cells"][k]["w1"] for k in keys]
        h = [results[selected]["cells"][k]["w1"] for k in keys]
        ratio = 1 - st.mean(h) / st.mean(b) if st.mean(b) > 0 else None
        components = {"mean_three_landmark_w1_reduction_at_least_20pct": ratio is not None and ratio >= .2,
                      "no_landmark_w1_worsens_more_than_10pct": all(hh <= 1.1 * bb + 1e-12 for bb, hh in zip(b, h))}
        improvement[content] = {"baseline_w1": b, "history_w1": h, "relative_reduction": ratio,
                                "components": components, "passed": all(components.values())}
        success &= improvement[content]["passed"]
    return {"state_results": results, "content_improvement": improvement,
            "history_state_qualified_for_this_support_screen": bool(success and results[selected]["all_six_cells_repeatable"]),
            "broad_native_common_support_established": False, "v13_reopened": False,
            "causal_markov_sufficiency_established": False, "action_values_estimated": False,
            "controller_fitted": False, "delivery_qoe_action_outcomes_read": False}
