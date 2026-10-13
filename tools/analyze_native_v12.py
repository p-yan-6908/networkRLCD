"""Frozen finite-panel V12 summaries. No controller fit or population inference."""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import itertools
import json
import math
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("registered_v12", REPO / "tools/native_support_validation_v12.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
core = runner.core
STATES = runner.STATES
RATIOS = (.65, 1.05)
METRICS = ("mean_ontime_psnr_db", "on_time_fraction", "mean_guaranteed_wire_bytes_per_window", "mean_guaranteed_dropped_wire_bytes_per_window")


def load_hold(root, trial):
    directory = root / "sessions" / trial["id"]
    # Caller already verified every session's source, support, transport, clock,
    # trace, cleanup and count gates before any outcome file can be decoded.
    frame = runner.read(directory / "frame_events.json")
    sender = runner.read(directory / "sender_observations.json")
    holds = core.extract_holds(sender, frame["phase_windows"])
    if len(holds) != 1 or holds[0]["phase"] != "block_1":
        raise ValueError("registered single hold is not contained in the middle trace block")
    hold = holds[0]
    lo, hi = hold["window_start_ms"], hold["window_end_ms"]
    sources = {r["source_id"]: r for r in frame["sources"] if isinstance(r.get("source_id"), int)}
    observations = {}
    for row in frame["observations"]:
        if isinstance(row.get("source_id"), int) and row.get("known_source"):
            observations.setdefault(row["source_id"], []).append(row)
    selected = [r for r in sources.values() if lo <= r.get("capture_request_ms", -1) < hi]
    on_time, psnrs = 0, []
    for source in selected:
        valid = [r for r in observations.get(source["source_id"], []) if isinstance(r.get("readback_ms"), (float, int))
                 and 0 <= r["readback_ms"] - source["capture_request_ms"] <= core.DEADLINE_MS]
        if valid:
            on_time += 1
            value = (min(valid, key=lambda r: r["readback_ms"]).get("quality") or {}).get("psnr_db")
            if isinstance(value, (float, int)) and math.isfinite(value):
                psnrs.append(value)
    markers = core.load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
    if not core.validate_markers(markers, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])["passed"]:
        raise ValueError("actual-run clock alignment must pass before relay joins")
    origin, vertices = core.feasible_polygon(markers)
    if len(vertices) < 3:
        raise ValueError("actual-run clock map infeasible")
    relay = {"guaranteed_wire_bytes": 0, "guaranteed_dropped_wire_bytes": 0,
             "possible_wire_bytes": 0, "possible_dropped_wire_bytes": 0}
    with gzip.open(directory / "events.jsonl.gz", "rt") as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("kind") != "offer" or event.get("direction") != "a_to_b":
                continue
            low, high = core.mapped_browser_range(event["at_ms"], origin, vertices)
            for kind, included in (("guaranteed", low >= lo and high < hi), ("possible", high >= lo and low < hi)):
                if included:
                    relay[kind + "_wire_bytes"] += event["wire_bytes"]
                    if event.get("dropped"):
                        relay[kind + "_dropped_wire_bytes"] += event["wire_bytes"]
    return {"trial": trial["id"], "pair_id": trial["pair_id"], "profile_id": trial["network_profile_id"],
        "content_id": trial["content_id"], "network_family": trial["network_family"],
        "network_campaign_id": trial["network_campaign_id"], "cell": trial["cell_cluster"],
        "state": hold["assignment"]["state_bin"], "ratio": hold["assignment"]["ratio"],
        "window_ms": [lo, hi], "source_frames": len(selected), "on_time_frames": on_time,
        "psnr_frames": len(psnrs), "psnr_sum_db": sum(psnrs), "relay": relay}


def bucket(holds):
    sources = sum(r["source_frames"] for r in holds)
    on_time = sum(r["on_time_frames"] for r in holds)
    psnrs = sum(r["psnr_frames"] for r in holds)
    return {"hold_windows": len(holds), "source_frames": sources, "on_time_frames": on_time,
        "psnr_frames": psnrs, "on_time_fraction": on_time / sources if sources else None,
        "mean_ontime_psnr_db": sum(r["psnr_sum_db"] for r in holds) / psnrs if psnrs else None,
        "mean_guaranteed_wire_bytes_per_window": sum(r["relay"]["guaranteed_wire_bytes"] for r in holds) / len(holds) if holds else None,
        "mean_guaranteed_dropped_wire_bytes_per_window": sum(r["relay"]["guaranteed_dropped_wire_bytes"] for r in holds) / len(holds) if holds else None}


def contrast(groups, metric):
    effects = {}
    for state in STATES:
        lo, hi = groups[state]["0.65"][metric], groups[state]["1.05"][metric]
        effects[state] = hi - lo if hi is not None and lo is not None else None
    interaction = (effects[STATES[1]] - effects[STATES[0]]) if all(x is not None for x in effects.values()) else None
    return {"action_effect_1.05_minus_0.65": effects, "interaction_high_minus_low": interaction}


def analyze(output):
    if output.exists():
        raise ValueError("preserve existing analysis; never overwrite frozen results")
    runner.verify_registration()
    protocol = runner.read(runner.CONFIG)
    gate = runner.gate(runner.ROOT)
    if not gate["passed"] or len(gate["complete_cells"]) != 6 or gate["qualified_sessions"] != 48:
        raise ValueError("all 48 session and six-cell support gates must pass before any outcome file is opened")
    holds = [load_hold(runner.ROOT, trial) for trial in protocol["trials"]]
    cells = {}
    for cell in protocol["cell_ids"]:
        rows = [h for h in holds if h["cell"] == cell]
        groups = {state: {str(ratio): bucket([h for h in rows if h["state"] == state and h["ratio"] == ratio])
                         for ratio in RATIOS} for state in STATES}
        if any(groups[state][str(ratio)]["hold_windows"] < 2 for state in STATES for ratio in RATIOS):
            raise ValueError("registered hold count failed after outcome join")
        cells[cell] = {"content_id": rows[0]["content_id"], "network_family": rows[0]["network_family"],
            "campaign": rows[0]["network_campaign_id"], "state_action": groups,
            "metrics": {metric: contrast(groups, metric) for metric in METRICS}}
    summaries = {}
    for metric in METRICS:
        values = {cell: row["metrics"][metric]["interaction_high_minus_low"] for cell, row in cells.items()}
        complete = all(v is not None for v in values.values())
        strata = {}
        for field in ("content_id", "network_family", "campaign"):
            strata[field] = {}
            for name in sorted({row[field] for row in cells.values()}):
                rows = [values[cell] for cell, row in cells.items() if row[field] == name]
                strata[field][name] = {"estimable_cells": sum(x is not None for x in rows),
                    "registered_cells": len(rows), "mean_interaction": statistics.mean(rows) if all(x is not None for x in rows) else None}
        summaries[metric] = {"all_cells_estimable": complete, "cell_interactions": values,
            "crossed_mean": statistics.mean(values.values()) if complete else None, "strata": strata}
    # Four prospectively specified sensitivity combinations per cell: retain
    # one of two low profiles and one of two high profiles, never select a
    # combination based on its outcomes.
    sensitivities = {}
    for cell in cells:
        rows = [h for h in holds if h["cell"] == cell]
        profiles = {state: sorted({h["profile_id"] for h in rows if h["state"] == state}) for state in STATES}
        variants = []
        for low_profile, high_profile in itertools.product(profiles[STATES[0]], profiles[STATES[1]]):
            kept = {STATES[0]: low_profile, STATES[1]: high_profile}
            groups = {state: {str(ratio): bucket([h for h in rows if h["profile_id"] == kept[state] and h["ratio"] == ratio])
                             for ratio in RATIOS} for state in STATES}
            variants.append({"kept_profiles": kept, "primary_interaction": contrast(groups, METRICS[0])["interaction_high_minus_low"]})
        sensitivities[cell] = variants
    primary = summaries[METRICS[0]]
    sign = 1 if primary["crossed_mean"] is not None and primary["crossed_mean"] > 0 else -1 if primary["crossed_mean"] is not None and primary["crossed_mean"] < 0 else 0
    same_cells = sign != 0 and all(v is not None and sign * v > 0 for v in primary["cell_interactions"].values())
    strata_match = primary["all_cells_estimable"] and all(
        row["mean_interaction"] is not None and sign * row["mean_interaction"] >= .25
        for field in ("content_id", "campaign") for row in primary["strata"][field].values())
    robust = same_cells and all(v["primary_interaction"] is not None and sign * v["primary_interaction"] > 0
        for variants in sensitivities.values() for v in variants)
    report = {"abi": "native_v12_finite_panel_action_effect_report_v1", "protocol_sha256": runner.sha(runner.CONFIG),
        "capture_index_sha256": gate["capture_index_sha256"], "qualification_gate_sha256": runner.sha(runner.ROOT / "support_clock_transport_gate.json"),
        "source_campaigns": protocol["independent_network_campaigns"], "cells": cells, "metrics": summaries,
        "profile_sensitivities": sensitivities, "primary_direction": sign,
        "directional_stability_rule_passed": bool(primary["all_cells_estimable"] and same_cells and strata_match and robust),
        "population_estimate": False, "controller_fit_or_promoted": False, "pooled_prior_sources": False,
        "limitations": ["Selected finite panel, three campaigns and two shared content sources; cells and windows are not independent source replicates.",
            "Timely PSNR conditions on post-action successful delivery; it is a survivor quality proxy and is not complete QoE or policy value.",
            "BWE eligibility follows common conditioning and is not a randomized state intervention.",
            "Replayed measured application rates and local relay byte accounting do not reproduce live mobile paths.",
            "No population confidence interval, tuning, learned control, or renewed V10 threshold policy is authorized by this panel."]}
    runner.write(output, report)
    return {"all_primary_cells_estimable": primary["all_cells_estimable"], "directional_stability_rule_passed": report["directional_stability_rule_passed"], "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "reports/native-v12-analysis.json")
    args = parser.parse_args()
    print(json.dumps(analyze(args.out)))
