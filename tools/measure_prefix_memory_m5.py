"""Fresh M5 prefix-memory validation after complete M4R qualification.

No predictor, controller-state redesign or action-value command exists.
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import random
import statistics as st
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("qualified_m4r_for_m5", REPO / "tools/measure_prefix_instrumentation_m4r.py")
r = importlib.util.module_from_spec(s)
s.loader.exec_module(r)
v = r.v
ROOT = v.CACHE / "native-prefix-memory-m5"
CONFIG = REPO / "configs/native_prefix_memory_m5.json"
SEED, N = 20261115, 21
ENDPOINTS = r.ENDPOINTS
REGISTRATION = ["tools/measure_prefix_memory_m5.py", "tools/analyze_prefix_memory_m5.py", "docs/NATIVE_PREFIX_MEMORY_M5_PLAN.md", "configs/native_prefix_memory_m5.json"]


def inventory():
    result = r.inventory()
    result.update({name: v.sha(REPO / name) for name in REGISTRATION[:-1] + ["configs/native_prefix_instrumentation_m4r.json", "reports/native-prefix-instrumentation-m4r-overall.json", "docs/NATIVE_PREFIX_INSTRUMENTATION_M4R_RESULTS.md"]})
    return result


def parent():
    r.verify()
    gate = v.read(r.ROOT / "instrumentation_qualification.json")
    assert gate["passed"] and gate["qualified_sessions"] == gate["sessions"] == 32
    assert gate["registration_sha256"] == v.sha(r.CONFIG)
    for stage in ("feasibility", "qualification"):
        root = r.ROOT / stage
        v.core.check_capture_integrity(root)
        assert gate["stage_gate_sha256"][stage] == v.sha(root / "mechanism_qualification_gate.json")
        assert v.read(root / "mechanism_qualification_gate.json")["passed"]
    return {"registration_sha256": v.sha(r.CONFIG), "overall_gate_sha256": v.sha(r.ROOT / "instrumentation_qualification.json"), "qualified_sessions": 32}


def activate():
    v.core.source_inventory = inventory
    v.core.RECORDER = r.RECORDER


def prepare():
    reference = parent()
    assert not ROOT.exists() and not CONFIG.exists(), "preserve an existing M5 registration"
    assets = v.verify_assets()
    source = v.read(r.ROOT / "feasibility/protocol.json")
    profiles = source["prefix_profiles"]
    rng, trials = random.Random(SEED), []
    for rep in range(N):
        contents = list(enumerate(assets["content_sources"]))
        rng.shuffle(contents)
        for ci, content in contents:
            bit, pair = rng.getrandbits(1), f"m5-r{rep:02d}-c{ci:02d}"
            for slot in (0, 1):
                prefix = ("ascending_prefix", "descending_prefix")[slot ^ bit]
                profile = profiles[prefix]
                tid = pair + f"-s{slot}-support"
                panel = v.panel_for(tid, content, profile, pair, slot, SEED, True)
                panel["episodes"][0].update({"support_initial_bwe_kbps": 1200, "setup_delay_ms": 0})
                panel["measurement_recipe"].update({"scientific_role": "fresh randomized prefix-memory validation; no bitrate actions or predictors", "instrumentation_version": "M4R"})
                relative = f"panels/{tid}.json"
                v.write(ROOT / relative, panel)
                trials.append({"id": tid, "condition": "micro", "panel": relative, "panel_sha256": v.sha(ROOT / relative),
                    "pair_id": pair, "pair_slot": slot, "repetition": rep, "support_only": True, "content_id": content["content_id"],
                    "prefix": prefix, "setup_delay_ms": 0, "network_family": profile["family_id"], "network_campaign_id": profile["campaign_id"],
                    "network_profile_id": profile["profile_id"], "cell_cluster": content["content_id"] + "__" + prefix})
    p = v.protocol_for(ROOT, trials, "development", SEED)
    p.update({"abi": "native_prefix_memory_m5_protocol_v1", "stage": "prefix_memory_validation", "anchor_commit": "4b09421",
        "source_hashes": inventory(), "parent_instrumentation": reference, "prefix_profiles": profiles, "parent_profile": source["parent_profile"],
        "scientific_role": "Prospective causal prefix test on fresh held-out captures of reused sources; no independent-source population claim.",
        "source_separation": "Two reused clips and one reused LTE source; constructed early permutations and common original measured suffix. All M2/M3/M4/M4R captures excluded from estimation.",
        "randomization": {"seed": SEED, "namespace": "networkrlcd-prefix-memory-m5", "paired_slots": True, "marginal_propensity": .5},
        "replicas": {"pairs_per_content": 21, "sessions": 84, "all_original_attempts": True},
        "clock_instrumentation": source["clock_instrumentation"], "startup": source["startup"],
        "support_windows_ms": [[t, t + 300] for t in ENDPOINTS], "global_gate_required_before_any_effect_estimate": True,
        "shared_suffix": {"starts_at_source_second": 10, "exposure_start_sender_ms": 11000, "maximum_pair_exposure_difference_octaves": .01},
        "convergence": {"maximum_full_repeat_spread_octaves": .25, "maximum_empirical_w_infinity_octaves": .25,
            "paired_mean_interval_bounds": [-.25, .25], "maximum_w1_upper_975_octaves": .25, "sustained_windows_ms": [30000, 36000], "both_contents_required": True},
        "analysis": {"primary": "exact paired W1 at 18 s, each content alpha .025", "exact_pair_swaps": 2 ** 21,
            "secondary": "per-content primary gate, then Holm three later W1 tests at local alpha .025", "bootstrap_replicates": 10000,
            "bootstrap_seed": 20261116, "bootstrap_seed_derivation": "root + 10*lexical content index + endpoint order index",
            "predictors_fitted": False, "controller_state_redesigned": False, "fit_or_promote_controller": False, "outcomes_read": False},
        "prior_freeze_sha256": {name: v.sha(REPO / name) for name in subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "4b09421"], cwd=REPO, text=True).splitlines()}})
    v.seal(ROOT, p)
    v.write(CONFIG, p)
    return verify()


def verify():
    reference = parent()
    p = v.read(CONFIG)
    assert p["parent_instrumentation"] == reference
    assert v.sha(CONFIG) == v.sha(ROOT / "protocol.json") == (ROOT / "protocol.sha256").read_text().split()[0]
    assert p["source_hashes"] == inventory()
    for name, expected in p["prior_freeze_sha256"].items():
        assert v.sha(REPO / name) == expected, name
    assert len(p["trials"]) == 84 and p["randomized_order"] == [t["id"] for t in p["trials"]]
    for t in p["trials"]:
        assert t["setup_delay_ms"] == 0 and t["support_only"]
        assert v.sha(ROOT / t["panel"]) == t["panel_sha256"]
        panel = v.read(ROOT / t["panel"])
        assert v.sha(Path(panel["video_source"]["path"])) == panel["video_source"]["sha256"]
        rates = [rate for block in panel["episodes"][0]["schedule"] for rate in block[3]]
        assert rates == p["prefix_profiles"][t["prefix"]]["rates_mbps"]
        assert rates[10:] == p["parent_profile"]["rates_mbps"][10:]
    activate()
    return {"verified": True, "parent_qualified_originals": 32, "planned_sessions": 84, "started": (ROOT / "sessions").exists(), "prior_files_unchanged": len(p["prior_freeze_sha256"]), "predictors_fitted": False}


def suffix(directory, sender):
    clock, original, origin, vertices = r.clocks(directory)
    assert clock["full"]["passed"] and clock["beginning"]["passed"]
    ticks = []
    with gzip.open(directory / "events.jsonl.gz", "rt") as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("kind") == "trace_capacity":
                ticks.append({k: event[k] for k in ("at_ms", "capacity_mbps", "phase", "sample_index")})
    assert len(ticks) == 36
    start = sender["measurement_start_ms"]
    mapped = [[{**t, "ms": origin + (t["at_ms"] - beta) / alpha - start} for t in ticks] for alpha, beta in vertices]
    common = [series[10]["ms"] for series in mapped]
    exposure = {}
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
        exposure[str(endpoint)] = [min(totals), max(totals)]
    return {"common_input_start_sender_ms_interval": [min(common), max(common)], "common_before_11000": max(common) <= 11000,
        "capacity_exposure_bytes_bounds": exposure, "actual_ticks": ticks}


def gate():
    verify()
    base = r.gate(ROOT, values=True)
    p, index = v.core.check_capture_integrity(ROOT)
    rows = base["sessions"]
    pairs = {}
    for row in rows:
        pairs.setdefault(row["pair_id"], []).append(row)
        if row["passed"]:
            directory = ROOT / "sessions" / row["trial"]
            row["suffix_fidelity"] = suffix(directory, v.read(directory / "sender_observations.json"))
    fidelity = {}
    for pair, members in pairs.items():
        assert len(members) == 2 and {x["prefix"] for x in members} == {"ascending_prefix", "descending_prefix"}
        fidelity[pair] = {}
        for endpoint in ENDPOINTS:
            available = all(x["passed"] and x["suffix_fidelity"]["common_before_11000"] for x in members)
            error = None
            if available:
                a, b = [x["suffix_fidelity"]["capacity_exposure_bytes_bounds"][str(endpoint)] for x in members]
                error = max(abs(math.log2(a[0] / b[1])), abs(math.log2(a[1] / b[0])))
            fidelity[pair][str(endpoint)] = {"passed": bool(available and error <= .01), "maximum_exposure_log2_difference": error}
    result = {**base, "abi": "native_prefix_memory_m5_qualification_v1", "sessions": rows, "pair_suffix_fidelity": fidelity,
        "base_gate_sha256": v.sha(ROOT / "support_clock_transport_gate.json"),
        "passed": base["passed"] and len(pairs) == 42 and all(q["passed"] for pair in fidelity.values() for q in pair.values()),
        "all_84_required_for_effect_analysis": True, "predictors_fitted": False}
    # Preserve the generic acquisition gate separately; never overwrite a seal
    # or the registered acquisition result with an effect-specific decision.
    v.write(ROOT / "prefix_memory_qualification_gate.json", result)
    v.write(REPO / "reports/native-prefix-memory-m5-gate.json", result)
    return result


def capture():
    verify()
    for name in REGISTRATION:
        assert subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=REPO) == (REPO / name).read_bytes(), "commit before capture"
    p = v.read(CONFIG)
    current, _ = v.frozen.base.runtime_provenance(Path(p["preflight_reference"]["path"]))
    assert current == p["runtime"]
    v.frozen.v2.set_runtime_env(p)
    captured = v.core.capture(ROOT)
    result = gate()
    return {"capture": captured, "qualified_sessions": result["qualified_sessions"], "full_gate_passed": result["passed"], "predictors_fitted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "verify", "capture", "analyze"])
    args = parser.parse_args()
    if args.command == "analyze":
        s = importlib.util.spec_from_file_location("registered_m5_analysis", REPO / "tools/analyze_prefix_memory_m5.py")
        a = importlib.util.module_from_spec(s)
        s.loader.exec_module(a)
        result = a.analyze()
    else:
        result = globals()[args.command]()
    print(json.dumps(result))
