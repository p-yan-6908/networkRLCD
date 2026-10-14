"""Preregistered prefix-only support experiment. No action/controller command."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import random
import statistics as st
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("m3_frozen_v13", REPO / "tools/design_native_v13.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
ROOT = v.CACHE / "native-prefix-memory-m3"
CONFIG = REPO / "configs/native_prefix_memory_m3.json"
RECORDER = REPO / "benchmarks/native_m2/bwe_mechanism_support_episode_m2.mjs"
N, SEED = 21, 20261108
ENDPOINTS = (18000, 24000, 30000, 36000)
REGISTRATION = ["tools/measure_prefix_memory_m3.py", "tools/analyze_prefix_memory_m3.py",
    "docs/NATIVE_PREFIX_MEMORY_M3_PLAN.md", "configs/native_prefix_memory_m3.json"]
EXTRA_FEATURE_NAMES = ["lag_3_to_2_log2_bwe", "lag_3_to_2_valid_fraction", "lag_2_to_1_log2_bwe", "lag_2_to_1_valid_fraction",
    "rtcp_rtt_normalized", "rtcp_rtt_valid_fraction", "rtcp_age_normalized", "rtcp_age_valid_fraction",
    "payload_send_normalized", "payload_send_valid_fraction", "packet_delay_normalized", "packet_delay_valid_fraction",
    "encoder_fps_normalized", "encoder_fps_valid_fraction", "encode_time_normalized", "encode_time_valid_fraction"]


def inventory():
    result = v.inventory()
    for name in [*REGISTRATION[:3], str(RECORDER.relative_to(REPO)), "tools/measure_bwe_mechanisms_m2.py",
        "configs/native_bwe_mechanisms_m2.json", "data/native-v13/sources.json",
        "reports/native-prefix-memory-m3-runtime-preflight.json"]:
        result[name] = v.sha(REPO / name)
    return result


def committed():
    for name in REGISTRATION:
        p = subprocess.run(["git", "show", f"HEAD:{name}"], cwd=REPO, capture_output=True)
        if p.returncode or hashlib.sha256(p.stdout).hexdigest() != v.sha(REPO / name):
            return False
    return True


def preserve_prior():
    v.core.source_inventory = v.inventory
    prior = v.verify()
    assert not prior["confirmatory_started"]
    assert not v.read(v.SUPPORT_ROOT / "support_clock_transport_gate.json")["passed"]
    reference = v.CACHE / "native-bwe-mechanisms-m2-instrument-check"
    main = v.read(REPO / "configs/native_bwe_mechanisms_m2.json")
    assert main["development_protocol_sha256"] == v.sha(reference / "protocol.json")
    g = v.read(reference / "mechanism_qualification_gate.json")
    assert g["passed"] and g["qualified_sessions"] == 2
    assert g["protocol_sha256"] == v.sha(reference / "protocol.json")
    assert g["capture_index_sha256"] == v.sha(reference / "capture_index.json")
    index = v.read(reference / "capture_index.json")
    for item in index["sessions"]:
        directory = reference / "sessions" / item["trial"]
        assert v.sha(directory / "integrity.json") == item["integrity_manifest_sha256"]
        v.core.verify_directory(directory)
    v.core.source_inventory = inventory
    v.core.RECORDER = RECORDER
    return {"reference_root": str(reference), "reference_gate_sha256": v.sha(reference / "mechanism_qualification_gate.json")}


def trial(content, profile, pair_id, rep, slot, prefix):
    tid = f"{pair_id}-s{slot}-support"
    panel = v.panel_for(tid, content, profile, pair_id, slot, SEED, True)
    panel["episodes"][0]["support_initial_bwe_kbps"] = 1200
    panel["measurement_recipe"].update({"initial_estimator_target_kbps": 1200,
        "history_kind": prefix, "scientific_role": "reused-source support-only prefix intervention"})
    relative = f"panels/{tid}.json"
    v.write(ROOT / relative, panel)
    return {"id": tid, "condition": "micro", "panel": relative, "panel_sha256": v.sha(ROOT / relative),
        "pair_id": pair_id, "pair_slot": slot, "repetition": rep, "support_only": True,
        "content_id": content["content_id"], "network_family": profile["family_id"],
        "network_campaign_id": profile["campaign_id"], "network_profile_id": profile["profile_id"],
        "cell_cluster": content["content_id"] + "__" + profile["family_id"], "prefix": prefix,
        "initial_bwe_kbps": 1200, "history_kind": prefix, "input_is_fully_measured": False}


def prepare():
    reference = preserve_prior()
    if ROOT.exists() or CONFIG.exists():
        raise ValueError("preserve any prior M3 registration/capture")
    sources = v.verify_assets()
    parent = next(p for p in sources["network_profiles"] if p["profile_id"] == "att_lte_driving_2016-uplink-lower")
    profiles = {}
    for prefix, reverse in (("ascending_prefix", False), ("descending_prefix", True)):
        rates = sorted(parent["rates_mbps"][:10], reverse=reverse) + parent["rates_mbps"][10:]
        profiles[prefix] = {**parent, "profile_id": prefix + "__" + parent["profile_id"],
            "family_id": "source_derived_prefix_intervention", "campaign_id": "reused_att_driving_2016_suffix",
            "rates_mbps": rates, "fully_measured_history": False}
    a, b = (profiles[x]["rates_mbps"] for x in ("ascending_prefix", "descending_prefix"))
    assert sorted(a[:10]) == sorted(b[:10]) == sorted(parent["rates_mbps"][:10])
    assert a[10:] == b[10:] == parent["rates_mbps"][10:]
    assert abs(sum(a[:10]) - 14.112) < 1e-10
    trials, rng = [], random.Random(SEED)
    for rep in range(N):
        contents = list(enumerate(sources["content_sources"]))
        rng.shuffle(contents)
        for ci, content in contents:
            bit = rng.getrandbits(1)
            pair = f"m3-r{rep:02d}-c{ci:02d}"
            for slot in (0, 1):
                prefix = ("ascending_prefix", "descending_prefix")[slot ^ bit]
                trials.append(trial(content, profiles[prefix], pair, rep, slot, prefix))
    p = v.protocol_for(ROOT, trials, "development", SEED)
    p.update({"abi": "native_prefix_memory_m3_protocol_v1", "anchor_commit": "7cf6ae5", "stage": "prefix_memory",
        "confirmatory": False, "source_hashes": inventory(), "source_separation": "Two reused clips and one reused LTE trace; constructed prefixes and common original measured suffix. Support-state development, no independent source or action evidence.",
        "parent_profile": parent, "prefix_profiles": profiles, "instrument_reference": reference,
        "randomization": {"seed": SEED, "namespace": "networkrlcd-prefix-memory-m3", "paired_slots": True, "marginal_propensity": .5},
        "replicas": {"pairs_per_content": N, "sessions": 4 * N, "require_all_original_attempts": True},
        "startup": {"target_kbps": 1200, "native_initial_bwe_tolerance_bps": 1, "preconnection_ceiling_bps": 4000000},
        "windows_ms": [[t, t + 300] for t in ENDPOINTS],
        "shared_suffix": {"starts_at_source_second": 10, "exposure_start_sender_ms": 11000, "maximum_pair_exposure_difference_octaves": .01},
        "convergence": {"maximum_full_repeat_spread_octaves": .25, "maximum_empirical_w_infinity_octaves": .25,
            "paired_mean_interval_bounds": [-.25, .25], "maximum_w1_upper_975_octaves": .25,
            "sustained_windows_ms": [30000, 36000], "both_contents_required": True},
        "analysis": {"outcomes_read": False, "controller_fitted": False, "primary_per_content_alpha": .025,
            "exact_pair_swaps": 2 ** N, "bootstrap_replicates": 10000, "bootstrap_seed": 20261109,
            "bootstrap_seed_derivation": "root + 10*lexical content index + endpoint order index",
            "secondary_gatekeeping": "Primary rejection before Holm across three later windows at local alpha .025",
            "state_prediction": {"enabled_only_after_qualified_primary_rejection": True, "transitions_ms": [[18000, 24000], [24000, 30000], [30000, 36000]],
                "cv_unit": "complete capture pair, leave one pair out", "content_models_separate": True,
                "raw_rbf_bandwidth_octaves": .25, "ridge": .1, "history_rbf_bandwidth": "sqrt(D), training-only feature standardization",
                "history_feature_names": EXTRA_FEATURE_NAMES, "augmented_kernel": "raw RBF plus history RBF",
                "bootstrap_seed": 20261110, "minimum_content_rmse_improvement": .20,
                "bootstrap_seed_derivation": "root + lexical content index",
                "maximum_transition_rmse_worsening": .10, "require_both_loss_difference_upper_975_below_zero": True,
                "causal_state_sufficiency_claim": False}},
        "prior_evidence_sha256": {name: v.sha(REPO / name) for name in subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "7cf6ae5"], cwd=REPO, text=True).splitlines()}})
    v.seal(ROOT, p)
    v.write(CONFIG, p)
    return verify()


def verify():
    reference = preserve_prior()
    p = v.read(CONFIG)
    assert p["instrument_reference"] == reference
    assert v.sha(CONFIG) == v.sha(ROOT / "protocol.json")
    assert (ROOT / "protocol.sha256").read_text().split()[0] == v.sha(CONFIG)
    v.core.verify_sources(p)
    for name, expected in p["prior_evidence_sha256"].items():
        assert v.sha(REPO / name) == expected, name
    assert len(p["trials"]) == 84 and p["support"] == v.read(v.CONFIG)["support"]
    assert [t["id"] for t in p["trials"]] == p["randomized_order"]
    groups = defaultdict(list)
    for t in p["trials"]:
        groups[t["pair_id"]].append(t)
        assert t["support_only"] and t["initial_bwe_kbps"] == 1200
        assert v.sha(ROOT / t["panel"]) == t["panel_sha256"]
        panel = v.read(ROOT / t["panel"])
        assert v.sha(Path(panel["video_source"]["path"])) == panel["video_source"]["sha256"]
        rates = [x for block in panel["episodes"][0]["schedule"] for x in block[3]]
        assert rates == p["prefix_profiles"][t["prefix"]]["rates_mbps"]
        assert rates[10:] == p["parent_profile"]["rates_mbps"][10:]
    assert len(groups) == 42 and all(len(g) == 2 and {t["prefix"] for t in g} == {"ascending_prefix", "descending_prefix"} for g in groups.values())
    return {"verified": True, "protocol_sha256": v.sha(CONFIG), "sessions": 84,
        "registration_matches_head": committed(), "started": (ROOT / "sessions").exists(), "v13_actions_started": False}


def support_windows(sender):
    start = sender["measurement_start_ms"]
    points = [{"ms": d["sample_ms"] - start, "bwe": d["policy_input"]["features"][0] * 4000000,
        "valid": d["policy_input"]["features"][9] == 1, "features": d["policy_input"]["features"]} for d in sender["decisions"]]
    windows = {}
    for endpoint in ENDPOINTS:
        selected = None
        for i, point in enumerate(points):
            if not endpoint <= point["ms"] <= endpoint + 300:
                continue
            tail = points[max(0, i - 10):i + 1]
            if (len(tail) == 11 and tail[-1]["ms"] - tail[0]["ms"] >= 900
                and all(0 < b["ms"] - a["ms"] <= 250 for a, b in zip(tail, tail[1:]))
                and all(p["valid"] and 240000 <= p["bwe"] <= 3800000 for p in tail)):
                selected = tail
                break
        if selected is None:
            windows[str(endpoint)] = {"passed": False}
            continue
        x = st.mean(math.log2(p["bwe"] / 500000) for p in selected)
        extra = []
        for lo, hi in ((endpoint - 3000, endpoint - 2000), (endpoint - 2000, endpoint - 1000)):
            lag = [p for p in points if lo <= p["ms"] < hi]
            valid = [p for p in lag if p["valid"] and p["bwe"] > 0]
            extra += [st.mean(math.log2(p["bwe"] / 500000) for p in valid) if valid else 0,
                len(valid) / len(lag) if lag else 0]
        for index, flag in ((1, 10), (2, 11), (3, 12), (6, 14), (4, 12), (5, 13)):
            values = [p["features"][index] for p in selected if p["features"][flag] == 1]
            extra += [st.mean(values) if values else 0, len(values) / len(selected)]
        windows[str(endpoint)] = {"passed": True, "x": x, "bwe_geo_bps": 500000 * 2 ** x,
            "elapsed_ms": selected[-1]["ms"], "sample_history_ms": [p["ms"] for p in selected],
            "history_bwe_bps": [p["bwe"] for p in selected], "state_extra": extra}
    q = sender["support_screen"]["qualification"]
    assert bool(q and q["passed"]) == windows["18000"]["passed"]
    if q:
        assert abs(windows["18000"]["x"] - q["continuous_log2_bwe"]) < 1e-10
    return windows


def exposure_bounds(directory, sender):
    markers = v.core.load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
    clock = v.core.validate_markers(markers, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])
    assert clock["passed"]
    origin, vertices = v.core.feasible_polygon([markers[i] for i in [0, 1, 3, 4, 6, 7, 9, 11]])
    ticks, services = [], defaultdict(list)
    with gzip.open(directory / "events.jsonl.gz", "rt") as stream:
        for line in stream:
            e = json.loads(line)
            if e.get("kind") == "trace_capacity":
                ticks.append({k: e[k] for k in ("at_ms", "capacity_mbps", "phase", "sample_index")})
            elif e.get("kind") == "service":
                services[e["direction"]].append({k: e[k] for k in ("from_ms", "at_ms", "capacity_mbps", "queue_before_wire_bytes", "queue_after_wire_bytes")})
    assert len(ticks) == 36
    start = sender["measurement_start_ms"]
    mapped = [[{**t, "ms": origin + (t["at_ms"] - beta) / alpha - start} for t in ticks] for alpha, beta in vertices]
    common_start = [series[10]["ms"] for series in mapped]
    exposures = {}
    for endpoint in ENDPOINTS:
        totals = []
        for series in mapped:
            rate, cursor, total = 5.0, 11000.0, 0.0
            for tick in series:
                if tick["ms"] <= 11000:
                    rate = tick["capacity_mbps"]
                    continue
                if tick["ms"] >= endpoint:
                    break
                total += rate * (tick["ms"] - cursor)
                rate, cursor = tick["capacity_mbps"], tick["ms"]
            total += rate * (endpoint - cursor)
            totals.append(total * 125)
        exposures[str(endpoint)] = [min(totals), max(totals)]
    def node_at(elapsed):
        return st.mean(alpha * (start + elapsed - origin) + beta for alpha, beta in vertices)
    queue_history = {}
    common_node = ticks[10]["at_ms"]
    for direction in ("a_to_b", "b_to_a"):
        records = services[direction]
        exact = [e for e in records if abs(e["at_ms"] - common_node) < 1e-6]
        assert len(exact) == 1
        empty = next((e["at_ms"] - common_node for e in records if e["at_ms"] >= common_node and e["queue_after_wire_bytes"] == 0), None)
        windows = {}
        for lo, hi in ((0, 10000), (10000, 18000), (18000, 24000), (24000, 30000), (30000, 36000)):
            a, b = node_at(lo), node_at(hi)
            area, positive, gaps = 0.0, 0.0, []
            for e in records:
                u, w = max(a, e["from_ms"]), min(b, e["at_ms"])
                if w <= u:
                    continue
                rate = e["capacity_mbps"] * 125
                q0 = max(0, e["queue_before_wire_bytes"] - rate * (u - e["from_ms"]))
                active = min(w - u, q0 / rate) if rate > 0 else w - u
                area += q0 * active - rate * active ** 2 / 2
                positive += active
                gaps.append(e["at_ms"] - e["from_ms"])
            windows[f"{lo}_{hi}"] = {"mean_queue_bytes": area / (b - a), "positive_queue_fraction": positive / (b - a),
                "mean_pump_gap_ms": st.mean(gaps) if gaps else None, "maximum_pump_gap_ms": max(gaps) if gaps else None}
        queue_history[direction] = {"queued_bytes_at_common_tick": exact[0]["queue_after_wire_bytes"],
            "first_empty_after_common_tick_ms": empty, "windows": windows}
    return {"common_input_started_ms_interval": [min(common_start), max(common_start)],
        "input_converged_before_exposure_start": max(common_start) <= 11000,
        "exposure_capacity_bytes_bounds": exposures, "actual_rate_ticks": ticks,
        "clock_max_heldout_width_ms": clock["max_held_out_width_ms"], "support_queue_history": queue_history}


def gate():
    verify()
    p, index = v.core.check_capture_integrity(ROOT)
    base = v.gate(ROOT)
    rows = []
    for raw, t in zip(base["sessions"], p["trials"], strict=True):
        assert raw["trial"] == t["id"]
        row = {**raw, "pair_id": t["pair_id"], "pair_slot": t["pair_slot"], "prefix": t["prefix"],
            "startup_passed": False, "readback_passed": False, "windows": {}}
        directory = ROOT / "sessions" / t["id"]
        if raw["capture_status"] == "sealed":
            startup = v.read(directory / "support_startup.json")
            actual = startup["initial_native_source"]["bwe_bps"]
            first = startup["first_measured_bwe_bps"]
            row["startup_passed"] = all([startup["requested_initial_bwe_bps"] == 1200000,
                startup["local_start_parameter"] == startup["remote_start_parameter"] == 1200,
                startup["preconnection_cap_readback_bps"] == 4000000,
                isinstance(actual, (int, float)) and abs(actual - 1200000) <= 1,
                isinstance(first, (int, float)) and abs(first - 1200000) <= 1])
            row["startup"] = startup
            sender = v.read(directory / "sender_observations.json")
            row["readback_passed"] = not sender["support_screen"]["action_assigned"] and all(
                d["actuator_assignment"] is None and d["actuation_readback"]["encoder_max_bitrate_bps"] == 4000000
                and d["actuation_readback"]["receiver_jitter_buffer_target_ms"] == 0 for d in sender["decisions"])
            row["windows"] = support_windows(sender)
            if raw["passed"]:
                row["suffix_fidelity"] = exposure_bounds(directory, sender)
        row["passed"] = raw["passed"] and row["startup_passed"] and row["readback_passed"]
        rows.append(row)
    pairs = defaultdict(list)
    for row in rows:
        pairs[row["pair_id"]].append(row)
    fidelity = {}
    for pair, members in pairs.items():
        assert len(members) == 2
        values = {}
        for endpoint in ENDPOINTS:
            available = all(r["passed"] and r.get("suffix_fidelity", {}).get("input_converged_before_exposure_start") for r in members)
            error = None
            if available:
                a, b = [r["suffix_fidelity"]["exposure_capacity_bytes_bounds"][str(endpoint)] for r in members]
                error = max(abs(math.log2(a[0] / b[1])), abs(math.log2(a[1] / b[0])))
            values[str(endpoint)] = {"passed": available and error <= .01, "maximum_exposure_log2_difference": error}
        fidelity[pair] = values
    result = {"abi": "native_prefix_memory_m3_qualification_v1", "stage": "prefix_memory",
        "passed": all(r["passed"] for r in rows), "qualified_sessions": sum(r["passed"] for r in rows),
        "planned_sessions": 84, "protocol_sha256": v.sha(CONFIG), "capture_index_sha256": v.sha(ROOT / "capture_index.json"),
        "base_gate_sha256": v.sha(ROOT / "support_clock_transport_gate.json"), "sessions": rows, "pair_suffix_fidelity": fidelity,
        "extra_state_feature_names": EXTRA_FEATURE_NAMES, "outcomes_read": False, "controller_fitted": False, "v13_reopened": False}
    v.write(ROOT / "mechanism_qualification_gate.json", result)
    return result


def capture():
    checked = verify()
    if not checked["registration_matches_head"]:
        raise ValueError("commit all M3 registration files before capture")
    p = v.read(CONFIG)
    current, _ = v.frozen.base.runtime_provenance(Path(p["preflight_reference"]["path"]))
    assert current == p["runtime"]
    v.frozen.v2.set_runtime_env(p)
    captured = v.core.capture(ROOT)
    g = gate()
    v.write(REPO / "reports/native-prefix-memory-m3-gate.json", g)
    return {"capture": captured, "qualified_sessions": g["qualified_sessions"], "gate_passed": g["passed"], "outcomes_read": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "verify", "capture", "analyze"])
    args = parser.parse_args()
    if args.command == "analyze":
        spec = importlib.util.spec_from_file_location("m3_registered_analysis", REPO / "tools/analyze_prefix_memory_m3.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.analyze()
    else:
        result = globals()[args.command]()
    print(json.dumps(result))
