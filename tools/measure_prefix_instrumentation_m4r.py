"""Prospective instrumentation qualification; no predictor or effect fitting."""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import os
import random
import statistics as st
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("frozen_m3_instrument_dependencies", REPO / "tools/measure_prefix_memory_m3.py")
m3 = importlib.util.module_from_spec(s)
s.loader.exec_module(m3)
v = m3.v
ROOT = v.CACHE / "native-prefix-instrumentation-m4r"
CONFIG = REPO / "configs/native_prefix_instrumentation_m4r.json"
RECORDER = REPO / "benchmarks/native_m4r/prefix_instrumentation_episode_m4r.mjs"
SOURCES = ["tools/measure_prefix_instrumentation_m4r.py", "tools/build_prefix_instrumentation_m4r.py",
    "benchmarks/native_m4r/prefix_instrumentation_episode_m4r.mjs", "docs/NATIVE_PREFIX_INSTRUMENTATION_M4R_PLAN.md",
    "reports/native-prefix-instrumentation-m4r-runtime-preflight.json"]
SEED = 20261113
ENDPOINTS = (18000, 24000, 30000, 36000)


def inventory():
    result = m3.inventory()
    result.update({name: v.sha(REPO / name) for name in SOURCES})
    result.update({name: v.sha(REPO / name) for name in ["tools/measure_prefix_instrumentation_m4.py", "tools/build_prefix_instrumentation_m4.py", "benchmarks/native_m4/prefix_instrumentation_episode_m4.mjs", "docs/NATIVE_PREFIX_INSTRUMENTATION_M4_PLAN.md", "configs/native_prefix_instrumentation_m4.json", "reports/native-prefix-instrumentation-m4-closure.json"]})
    return result


def activate():
    v.core.source_inventory = inventory
    v.core.RECORDER = RECORDER


def prepare():
    m3.verify()
    assert not CONFIG.exists() and not ROOT.exists(), "preserve existing M4R"
    assets = v.verify_assets()
    parent = next(x for x in assets["network_profiles"] if x["profile_id"] == "att_lte_driving_2016-uplink-lower")
    profiles = m3.v.read(m3.CONFIG)["prefix_profiles"]
    rng, stages = random.Random(SEED), {}
    for stage, repetitions in (("feasibility", [0]), ("qualification", list(range(1, 8)))):
        root, trials = ROOT / stage, []
        for rep in repetitions:
            contents = list(enumerate(assets["content_sources"]))
            rng.shuffle(contents)
            for ci, content in contents:
                delay = 750 if rep == 0 or rep >= 5 else 0
                pair, bit = f"m4r-r{rep:02d}-c{ci:02d}", rng.getrandbits(1)
                for slot in (0, 1):
                    prefix = ("ascending_prefix", "descending_prefix")[slot ^ bit]
                    profile = profiles[prefix]
                    tid = f"{pair}-s{slot}-support"
                    panel = v.panel_for(tid, content, profile, pair, slot, SEED, True)
                    panel["episodes"][0].update({"support_initial_bwe_kbps": 1200, "setup_delay_ms": delay})
                    panel["measurement_recipe"].update({"scientific_role": "instrumentation-only; no later BWE comparisons", "instrumentation_version": "M4R"})
                    relative = f"panels/{tid}.json"
                    v.write(root / relative, panel)
                    trials.append({"id": tid, "condition": "micro", "panel": relative, "panel_sha256": v.sha(root / relative),
                        "pair_id": pair, "pair_slot": slot, "repetition": rep, "support_only": True,
                        "content_id": content["content_id"], "prefix": prefix, "setup_delay_ms": delay,
                        "network_family": profile["family_id"], "network_campaign_id": profile["campaign_id"],
                        "network_profile_id": profile["profile_id"], "cell_cluster": content["content_id"] + "__" + prefix})
        p = v.protocol_for(root, trials, "development", SEED)
        p.update({"abi": "native_prefix_instrumentation_m4r_v1", "anchor_commit": "472ed01", "stage": stage,
            "source_hashes": inventory(), "parent_profile": parent, "prefix_profiles": profiles,
            "clock_instrumentation": {"original_markers": 12, "extra_markers": 59, "training": 64, "holdouts": 7,
                "start_certificate_training": 35, "start_certificate_holdouts": 4, "legacy_clock_is_diagnostic": True,
                "coverage": 1.0, "max_interval_width_ms": 50, "timestamp_tolerance_ms": 1, "slope": [.98, 1.02]},
            "startup": {"initial_native_bwe_bps": 1200000, "tolerance_bps": 1, "encoder_cap_bps": 4000000,
                "inactive_during_ice_and_delay": True, "maximum_transport_readiness_ms": 2000, "maximum_active_initialization_ms": 100, "poll_ms": 25, "maximum_poll_gap_ms": 250,
                "observe_through_measurement_ms": 1500, "minimum_observed_postmeasurement_ms": 1000},
            "analysis": {"outcomes_read": False, "prefix_effects_estimated": False, "predictors_fitted": False,
                "controller_fitted": False, "no_later_bwe_distributions": True},
            "source_separation": "M4R reused-content/source instrumentation development; constructed prefixes, original common measured suffix; no action or independent-source inference."})
        v.seal(root, p)
        stages[stage] = {"root": str(root), "protocol_sha256": v.sha(root / "protocol.json"), "trials": len(trials)}
    prior = {name: v.sha(REPO / name) for name in subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "472ed01"], cwd=REPO, text=True).splitlines()}
    manifest = {"abi": "native_prefix_instrumentation_m4r_manifest_v1", "anchor_commit": "472ed01", "stages": stages,
        "source_hashes": inventory(), "prior_freeze_sha256": prior, "required_cells": [c["content_id"] + "__" + p for c in assets["content_sources"] for p in profiles],
        "required_sessions_per_cell": 8, "required_per_cell_delay": {"0": 4, "750": 4},
        "planning": {"m3_kampar_clock_failure_rate": 5 / 41, "kampar_sessions": 16,
            "probability_detecting_at_least_one_if_m3_rate_persists": 1 - (36 / 41) ** 16,
            "minimum_target": .8, "smallest_balanced_four_cell_two_delay_count": 32,
            "limits": "Finite technical screen; no assurance of rare startup failure rate or future 84-session completion. Actual future gates remain mandatory."},
        "fresh_validation_created": False, "predictors_fitted": False, "outcomes_read": False}
    v.write(CONFIG, manifest)
    v.write(ROOT / "registration.json", manifest)
    return verify()


def verify():
    m3.verify()
    p = v.read(CONFIG)
    assert p["source_hashes"] == inventory()
    for name, checksum in p["prior_freeze_sha256"].items():
        assert v.sha(REPO / name) == checksum, name
    for stage in p["stages"].values():
        root = Path(stage["root"])
        assert v.sha(root / "protocol.json") == stage["protocol_sha256"]
        protocol = v.read(root / "protocol.json")
        assert protocol["source_hashes"] == inventory()
        for t in protocol["trials"]:
            assert v.sha(root / t["panel"]) == t["panel_sha256"]
            panel = v.read(root / t["panel"])
            assert v.sha(Path(panel["video_source"]["path"])) == panel["video_source"]["sha256"]
    activate()
    return {"verified": True, "prior_files_unchanged": len(p["prior_freeze_sha256"]), "planned_sessions": 32,
        "fresh_validation_started": False, "outcomes_read": False}


def clocks(directory):
    original = v.core.load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
    assert [x["marker_id"] for x in original] == [f"m{i:04d}" for i in range(1, 13)]
    browser, node = v.read(directory / "instrument_clock_browser.json"), v.read(directory / "instrument_clock_node.json")
    assert [x["marker_id"] for x in node] == [f"x{i:04d}" for i in range(1, 60)]
    assert [x["marker_id"] for x in browser] == [x["marker_id"] for x in node]
    extra = []
    for b, n in zip(browser, node, strict=True):
        assert all(b[k] == n[k] for k in ("marker_id", "browser_send_ms", "node_receive_ms", "node_send_ms", "role", "label"))
        extra.append({**n, "browser_receive_ms": b["browser_receive_ms"]})
    train = [original[i] for i in (0, 1, 3, 4, 6, 7, 9, 11)] + [x for x in extra if x["role"] == "train"]
    held = [original[i] for i in (2, 5, 8, 10)] + [x for x in extra if x["role"] == "holdout"]
    assert len(train) == 64 and len(held) == 7
    initial_labels = {name + suffix for name in ("session_open", "pre_sdp", "ready_inactive", "block_0") for suffix in ("_before", "_after")}
    start_train = [original[i] for i in (0, 1, 3)] + [x for x in extra if x["role"] == "train" and x["label"] in initial_labels]
    start_held = [original[2]] + [x for x in extra if x["role"] == "holdout"]
    assert len(start_train) == 35 and len(start_held) == 4
    def check(a, b):
        return v.core.validate_markers(a + b, list(range(len(a))), list(range(len(a), len(a) + len(b))))
    full, start = check(train, held), check(start_train, start_held)
    origin, vertices = v.core.feasible_polygon(train)
    return {"full": full, "beginning": start, "training_ids": [x["marker_id"] for x in train],
        "holdout_ids": [x["marker_id"] for x in held], "legacy_diagnostic": v.core.validate_markers(original, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])}, original, origin, vertices


def windows(sender, values=False):
    result, start = {}, sender["measurement_start_ms"]
    points = [{"ms": d["sample_ms"] - start, "bwe": d["policy_input"]["features"][0] * 4000000,
        "valid": d["policy_input"]["features"][9] == 1} for d in sender["decisions"]]
    for endpoint in ENDPOINTS:
        selected = None
        for i, x in enumerate(points):
            tail = points[max(0, i - 10):i + 1]
            if endpoint <= x["ms"] <= endpoint + 300 and len(tail) == 11 and tail[-1]["ms"] - tail[0]["ms"] >= 900 and all(0 < b["ms"] - a["ms"] <= 250 for a, b in zip(tail, tail[1:])) and all(q["valid"] and 240000 <= q["bwe"] <= 3800000 for q in tail):
                selected = tail
                break
        result[str(endpoint)] = {"passed": selected is not None}
        if values and selected:
            result[str(endpoint)].update({"x": st.mean(math.log2(x["bwe"] / 500000) for x in selected), "history_ms": [x["ms"] for x in selected], "history_bwe_bps": [x["bwe"] for x in selected]})
    return result


def startup_check(directory, sender, trial):
    samples = v.read(directory / "startup_samples.json")
    original = v.read(directory / "instrumentation_m4r.json")["startup_timeline"]
    assert sorted(samples, key=lambda x: x["request_ms"]) == sorted(original, key=lambda x: x["request_ms"])
    p = v.read(directory / "support_startup.json")
    ordered = sorted(samples, key=lambda x: x["response_ms"])
    poll = sorted((x for x in samples if x["label"] == "poll"), key=lambda x: x["response_ms"])
    first = next((x for x in samples if x["label"] == "before_sdp"), None)
    init = next((x for x in reversed(samples) if x["label"] == "initialization"), None)
    inactive = next((x for x in samples if x["label"] == "inactive_ready"), None)
    beginning = next((x for x in samples if x["label"] == "measurement_start"), None)
    gaps = [b["response_ms"] - a["response_ms"] for a, b in zip(poll, poll[1:])]
    components = {"explicit_pre_sdp_observation": bool(first and first["response_ms"] <= p["sdp_call_ms"] and first["connection_state"] == "new"),
        "native_initialization_success": p["initialization_success"] is True,
        "native_initial_bwe_exact": abs(p["initial_native_source"]["bwe_bps"] - 1200000) <= 1,
        "native_first_measurement_bwe_exact": abs(p["first_measured_bwe_bps"] - 1200000) <= 1,
        "sdp_and_cap_readbacks": p["local_start_parameter"] == p["remote_start_parameter"] == 1200 and p["preconnection_cap_readback_bps"] == 4000000,
        "encoder_held_inactive": bool(inactive and inactive["encoder_active_readback"] is False and inactive["encoder_cap_bps"] == 4000000 and inactive["frames_encoded"] in (None, 0) and inactive["bytes_sent"] in (None, 0)),
        "initialization_observed_promptly": bool(init and init["encoder_active_readback"] is True and p["initialization_latency_ms"] <= 100),
        "media_activation_readback": p["activation_readback"] is True and beginning is not None and beginning["encoder_active_readback"] is True,
        "native_measurement_start_bwe_exact": bool(beginning and isinstance(beginning["bwe_bps"], (float, int)) and abs(beginning["bwe_bps"] - 1200000) <= 1),
        "same_selected_pair": bool(init and beginning and init["selected_pair_count"] == beginning["selected_pair_count"] == 1 and init["selected_pair_id"] == beginning["selected_pair_id"]),
        "fixed_delay_exercised": p["setup_delay_ms"] == trial["setup_delay_ms"] and trial["setup_delay_ms"] <= p["delay_end_ms"] - p["delay_start_ms"] <= trial["setup_delay_ms"] + 250,
        "startup_sample_gaps": bool(gaps and max(gaps) <= 250 and all(x["request_ms"] <= x["response_ms"] for x in ordered)),
        "observes_postactivation_evolution": bool(poll and poll[-1]["response_ms"] >= sender["measurement_start_ms"] + 1000),
        "no_stats_errors": all(x["error"] is None for x in samples),
        "strict_transport_readiness": 0 <= p["transport_readiness_wait_ms"] <= 2000 and p["transport_readiness_probes"] >= 1}
    return {"passed": all(components.values()), "components": components, "sample_count": len(samples),
        "maximum_poll_gap_ms": max(gaps, default=None), "native_initial_bwe_bps": p["initial_native_source"]["bwe_bps"],
        "first_measured_bwe_bps": p["first_measured_bwe_bps"], "initialization_success": p["initialization_success"]}


def gate(root, values=False):
    p, index = v.core.check_capture_integrity(root)
    rows = []
    for item, trial in zip(index["sessions"], p["trials"], strict=True):
        assert item["trial"] == trial["id"]
        row = {"trial": trial["id"], "content_id": trial["content_id"], "prefix": trial["prefix"], "pair_id": trial["pair_id"], "setup_delay_ms": trial["setup_delay_ms"], "capture_status": item["status"], "passed": False}
        if item["status"] == "sealed":
            directory = root / "sessions" / trial["id"]
            clock, original, _, _ = clocks(directory)
            ice = v.read(directory / "ice_evidence.json")
            urls = {c.get("url") for peer in ("a", "b") for c in ice.get("candidates", {}).get(peer, [])}
            transport = v.frozen.base.transport_checks(root, trial["id"], next(iter(urls)) if len(urls) == 1 else "")
            trace = v.trace_gate(root, trial)
            cleanup = v.frozen.terminal_cleanup_gate(root, trial, original, p)
            support = v.support_projection(directory, trial, p)
            sender = v.read(directory / "sender_observations.json")
            startup = startup_check(directory, sender, trial)
            readback = not sender["support_screen"]["action_assigned"] and all(d["actuator_assignment"] is None and d["actuation_readback"]["encoder_max_bitrate_bps"] == 4000000 and d["actuation_readback"]["receiver_jitter_buffer_target_ms"] == 0 for d in sender["decisions"])
            snapshots = v.read(directory / "summary.json").get("snapshots", [])
            media = len(snapshots) == 3 and all(x.get("frames_encoded", 0) > 10 and x.get("frames_decoded", 0) > 10 and isinstance(x.get("mean_encode_s"), (int, float)) and math.isfinite(x["mean_encode_s"]) for x in snapshots)
            media = media and all(snapshots[i][field] - snapshots[i - 1][field] > 10 for i in (1, 2) for field in ("frames_encoded", "frames_decoded"))
            history = windows(sender, values)
            row.update({"clock": clock, "startup": startup, "transport_passed": transport["passed"], "trace": trace,
                "cleanup_passed": cleanup["passed"], "media_passed": media, "readback_passed": readback,
                "support_passed": support["passed"], "windows": history})
            row["passed"] = all([clock["full"]["passed"], clock["beginning"]["passed"], startup["passed"], transport["passed"], trace["passed"], cleanup["passed"], media, readback, support["passed"], all(x["passed"] for x in history.values())])
        rows.append(row)
    result = {"abi": "native_prefix_instrumentation_m4r_qualification_v1", "stage": p["stage"], "protocol_sha256": v.sha(root / "protocol.json"),
        "capture_index_sha256": v.sha(root / "capture_index.json"), "planned_sessions": len(p["trials"]),
        "qualified_sessions": sum(x["passed"] for x in rows), "passed": len(rows) == len(p["trials"]) and all(x["passed"] for x in rows),
        "sessions": rows, "outcomes_read": False, "prefix_effects_estimated": False, "predictors_fitted": False, "controller_fitted": False}
    v.write(root / "support_clock_transport_gate.json", result)
    v.write(root / "mechanism_qualification_gate.json", result)
    return result


def capture_stage(stage):
    verify()
    for name in SOURCES + [str(CONFIG.relative_to(REPO))]:
        assert subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=REPO) == (REPO / name).read_bytes(), "commit registration before capture"
    if stage == "qualification":
        assert v.read(ROOT / "feasibility/mechanism_qualification_gate.json")["passed"], "feasibility must pass"
    root = ROOT / stage
    p = v.read(root / "protocol.json")
    current, _ = v.frozen.base.runtime_provenance(Path(p["preflight_reference"]["path"]))
    assert current == p["runtime"]
    v.frozen.v2.set_runtime_env(p)
    captured = v.core.capture(root)
    result = gate(root)
    v.write(REPO / f"reports/native-prefix-instrumentation-m4r-{stage}-gate.json", result)
    if stage == "qualification":
        overall()
    return {"capture": captured, "qualified": result["qualified_sessions"], "passed": result["passed"], "outcomes_read": False}


def overall():
    verify()
    stages = {name: v.read(ROOT / name / "mechanism_qualification_gate.json") for name in ("feasibility", "qualification")}
    rows = [r for stage in stages.values() for r in stage["sessions"]]
    counts = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["passed"]:
            counts[r["content_id"] + "__" + r["prefix"]][str(r["setup_delay_ms"])] += 1
    passed = all(x["passed"] for x in stages.values()) and len(rows) == 32 and all(dict(counts[c]) == {"0": 4, "750": 4} for c in v.read(CONFIG)["required_cells"])
    result = {"abi": "native_prefix_instrumentation_m4r_overall_v1", "passed": passed, "sessions": len(rows),
        "qualified_sessions": sum(r["passed"] for r in rows), "qualified_cell_delay_counts": dict(counts),
        "stage_gate_sha256": {name: v.sha(ROOT / name / "mechanism_qualification_gate.json") for name in stages},
        "registration_sha256": v.sha(CONFIG), "future_84_session_success_guaranteed": False,
        "all_success_binomial_one_sided_95_upper_failure_probability": 1 - .05 ** (1 / 32) if passed else None,
        "outcomes_read": False, "predictors_fitted": False, "controller_fitted": False}
    v.write(ROOT / "instrumentation_qualification.json", result)
    v.write(REPO / "reports/native-prefix-instrumentation-m4r-overall.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "verify", "capture", "overall"])
    parser.add_argument("--stage", choices=["feasibility", "qualification"])
    args = parser.parse_args()
    result = capture_stage(args.stage) if args.command == "capture" else globals()[args.command]()
    print(json.dumps(result))
