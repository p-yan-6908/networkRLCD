"""Frozen support-only reliability diagnostic; no outcome or action commands."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import random
import statistics as st
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("m1_frozen_v13", REPO / "tools/design_native_v13.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
ROOT = runner.CACHE / "native-bwe-reliability-m1"
CONFIG = REPO / "configs/native_bwe_reliability_m1.json"
PLAN = REPO / "docs/NATIVE_BWE_RELIABILITY_M1_PLAN.md"
SEED = 20261104
RATE = 1.4523718338280722
REGISTRATION_FILES = (
    "tools/measure_bwe_reliability_m1.py",
    "docs/NATIVE_BWE_RELIABILITY_M1_PLAN.md",
    "configs/native_bwe_reliability_m1.json",
)


def inventory():
    result = runner.inventory()
    for name in (
        REGISTRATION_FILES[0], REGISTRATION_FILES[1],
        "data/native-v13/sources.json", "configs/native_continuous_validation_v13.json",
        "reports/native-v13-support-census-summary.json",
        "reports/native-v13-support-census-gate.json",
    ):
        result[name] = runner.sha(REPO / name)
    return result


def preserved_v13():
    # V13 verifies against its original inventory, never an expanded M1 set.
    runner.core.source_inventory = runner.inventory
    result = runner.verify()
    census = runner.read(runner.SUPPORT_ROOT / "support_clock_transport_gate.json")
    assert census["passed"] is False and not result["confirmatory_started"]
    assert census["protocol_sha256"] == runner.sha(runner.SUPPORT_ROOT / "protocol.json")
    assert census["capture_index_sha256"] == runner.sha(runner.SUPPORT_ROOT / "capture_index.json")
    return result


def registration_matches_head():
    for name in REGISTRATION_FILES:
        proc = subprocess.run(["git", "show", f"HEAD:{name}"], cwd=REPO, capture_output=True)
        if proc.returncode or hashlib.sha256(proc.stdout).hexdigest() != runner.sha(REPO / name):
            return False
    return True


def prepare():
    preserved_v13()
    if ROOT.exists() or CONFIG.exists():
        raise ValueError("preserve any existing M1 registration/capture")
    sources = runner.verify_assets()
    hint = next(p for p in sources["network_profiles"] if p["profile_id"] == "att_lte_driving_2016-uplink-lower")
    assert hint["conditioning_geometric_mean_hint_mbps"] == RATE
    profile = {"profile_id": "synthetic_constant_1.4523718338280722",
        "family_id": "synthetic_service_development", "campaign_id": "no_measured_campaign",
        "rates_mbps": [RATE] * 36}
    trials = []
    rng = random.Random(SEED)
    for rep in range(4):
        order = list(enumerate(sources["content_sources"]))
        rng.shuffle(order)
        for ci, content in order:
            pair = f"m1-c{ci:02d}-r{rep}"
            trials.append(runner.trial_for(ROOT, content, profile, pair, 0, SEED, True, rep))
    protocol = runner.protocol_for(ROOT, trials, "development", SEED)
    protocol.update({"abi": "native_bwe_reliability_m1_protocol_v1", "anchor_commit": "6b8471a",
        "source_hashes": inventory(), "confirmatory": False,
        "source_note": "V13 clips reused as development; constant synthetic service, no measured campaign or new independent evidence.",
        "scientific_evidence": "Outcome-free support reliability development only; no action-effect or population inference.",
        "service": {"kind": "synthetic_constant", "rate_mbps": RATE, "measured_trace": False,
            "chosen_from_frozen_input": "att_lte_driving_2016-uplink-lower conditioning_geometric_mean_hint_mbps",
            "source_manifest_sha256": runner.sha(REPO / "data/native-v13/sources.json")},
        "ordering": {"seed": SEED, "blocks": 4, "one_repeat_per_content_per_block": True,
            "within_block": "Python random.Random(seed).shuffle of the manifest content enumeration"},
        "reliability": {"repeats_per_content": 4, "maximum_full_repeat_spread_log2": .25,
            "require_all_original_sessions": True, "pairwise_differences_are_independent": False,
            "population_test_or_ci": False, "no_rate_or_window_search": True},
        "v13_action_stage_remains_closed": True})
    runner.seal(ROOT, protocol)
    runner.write(CONFIG, protocol)
    return verify()


def verify():
    v13 = preserved_v13()
    protocol = runner.read(CONFIG)
    assert runner.sha(CONFIG) == runner.sha(ROOT / "protocol.json")
    assert (ROOT / "protocol.sha256").read_text().split()[0] == runner.sha(CONFIG)
    runner.core.source_inventory = inventory
    runner.core.verify_sources(protocol)
    assert protocol["kind"] == "development" and protocol["confirmatory"] is False
    assert protocol["service"]["rate_mbps"] == RATE and protocol["service"]["measured_trace"] is False
    assert len(protocol["trials"]) == 8 and len(set(protocol["randomized_order"])) == 8
    assert protocol["randomized_order"] == [t["id"] for t in protocol["trials"]]
    counts = {}
    for trial in protocol["trials"]:
        counts[trial["content_id"]] = counts.get(trial["content_id"], 0) + 1
        assert trial["support_only"] and trial["network_family"] == "synthetic_service_development"
        assert trial["network_campaign_id"] == "no_measured_campaign"
        assert runner.sha(ROOT / trial["panel"]) == trial["panel_sha256"]
        panel = runner.read(ROOT / trial["panel"])
        assert runner.sha(Path(panel["video_source"]["path"])) == panel["video_source"]["sha256"]
        assert panel["episodes"][0]["support_config"]["support_only"]
        assert [s[2] for s in panel["episodes"][0]["schedule"]] == [12000, 12000, 12600]
        assert all(s[3] == [RATE] * 12 for s in panel["episodes"][0]["schedule"])
    assert len(counts) == 2 and set(counts.values()) == {4}
    assert protocol["support"] == runner.read(runner.CONFIG)["support"]
    return {"verified": True, "protocol_sha256": runner.sha(CONFIG), "sessions": 8,
        "registration_files_match_head": registration_matches_head(),
        "started": (ROOT / "sessions").exists(), "v13_action_panel_started": v13["confirmatory_started"]}


def capture():
    checked = verify()
    if not checked["registration_files_match_head"]:
        raise ValueError("commit the M1 plan, tool and protocol before capture")
    protocol = runner.read(CONFIG)
    current, _ = runner.frozen.base.runtime_provenance(Path(protocol["preflight_reference"]["path"]))
    assert current == protocol["runtime"]
    runner.frozen.v2.set_runtime_env(protocol)
    captured = runner.core.capture(ROOT)
    gate = runner.gate(ROOT)
    return {"capture": captured, "individual_gates_passed": gate["passed"],
        "outcomes_read": False, "v13_action_panel_started": False}


def summarize():
    verify()
    output = REPO / "reports/native-bwe-reliability-m1-summary.json"
    if output.exists():
        raise ValueError("preserve the completed M1 support diagnosis")
    protocol, index = runner.core.check_capture_integrity(ROOT)
    gate = runner.read(ROOT / "support_clock_transport_gate.json")
    assert gate["protocol_sha256"] == runner.sha(CONFIG)
    assert gate["capture_index_sha256"] == runner.sha(ROOT / "capture_index.json")
    trials = {t["id"]: t for t in protocol["trials"]}
    native = {r["trial"]: r for r in gate["sessions"]}
    rows = []
    verified_files = 0
    for item in index["sessions"]:
        trial = trials[item["trial"]]
        directory = ROOT / "sessions" / trial["id"]
        verified_files += runner.read(directory / "integrity.json")["file_count"]
        row = {"trial": trial["id"], "content": trial["content_id"], "repeat": trial["repetition"],
            "status": item["status"], "individual_gates_passed": native[trial["id"]]["passed"],
            "readback_and_zero_assignments": False, "qualified_census_x": None}
        path = directory / "sender_observations.json"
        if path.exists():
            sender = runner.read(path)
            assert sender["support_screen"]["config"]["support_only"] and not sender["support_screen"]["action_assigned"]
            assert all(d.get("actuator_assignment") is None
                and d["proposed_action"]["encoder_max_bitrate_bps"] == 4000000
                and d["actuation_readback"]["encoder_max_bitrate_bps"] == 4000000
                and d["actuation_readback"]["receiver_jitter_buffer_target_ms"] == 0 for d in sender["decisions"])
            row["readback_and_zero_assignments"] = True
            if native[trial["id"]]["passed"]:
                q = sender["support_screen"]["qualification"]
                history = q["bwe_history_bps"]
                x = st.mean(math.log2(b / 500000) for b in history)
                assert abs(x - q["continuous_log2_bwe"]) < 1e-10
                row.update({"qualified_census_x": x, "geometric_mean_bwe_bps": 500000 * 2 ** x,
                    "qualification_elapsed_ms": q["elapsed_ms"],
                    "history_range_octaves": math.log2(max(history) / min(history)),
                    "history_signed_drift_octaves": math.log2(history[-1] / history[0]),
                    "qualification": q})
        if item["status"] != "sealed":
            error = directory / "capture_stderr.log"
            row["capture_error"] = error.read_text()[:2000] if error.exists() else item.get("error")
        for key in ("clock", "transport_passed", "trace", "cleanup_passed", "media_passed"):
            if key in native[trial["id"]]:
                row[key] = native[trial["id"]][key]
        rows.append(row)
    contents = {}
    for content in sorted({r["content"] for r in rows}):
        selected = [r for r in rows if r["content"] == content]
        xs = [r["qualified_census_x"] for r in selected if r["qualified_census_x"] is not None]
        complete = len(xs) == 4 and all(r["readback_and_zero_assignments"] for r in selected)
        spread = max(xs) - min(xs) if complete else None
        contents[content] = {"original_repeats": 4, "qualified_repeats": len(xs), "replicate_x": xs,
            "full_spread_octaves": spread, "sample_sd_octaves": st.stdev(xs) if complete else None,
            "six_pairwise_absolute_differences": [abs(a - b) for a, b in itertools.combinations(xs, 2)] if complete else None,
            "descriptive_reliability_passed": complete and spread <= .25,
            "population_inference": False}
    result = {"abi": "native_bwe_reliability_m1_summary_v1", "protocol_sha256": runner.sha(CONFIG),
        "registration_commit": subprocess.check_output(["git", "log", "-1", "--format=%H", "--", *REGISTRATION_FILES], cwd=REPO, text=True).strip(),
        "capture_index_sha256": runner.sha(ROOT / "capture_index.json"), "gate_sha256": runner.sha(ROOT / "support_clock_transport_gate.json"),
        "tool_sha256": runner.sha(Path(__file__).resolve()), "verified_session_files": verified_files,
        "planned_sessions": 8, "sealed_sessions": sum(r["status"] == "sealed" for r in rows),
        "qualified_sessions": gate["qualified_sessions"], "individual_gates_passed": gate["passed"],
        "descriptive_reliability_passed": gate["passed"] and all(c["descriptive_reliability_passed"] for c in contents.values()),
        "service": protocol["service"], "content": contents, "sessions": rows,
        "outcomes_read": False, "actions_assigned": 0, "action_effects_estimated": False,
        "controller_fitted": False, "v13_reopened": False, "synthetic_sources_pooled": False,
        "limits": "Reused V13 content, one synthetic service level, finite repeated development only; no independent network, population or action-value evidence."}
    runner.write(output, result)
    runner.write(REPO / "reports/native-bwe-reliability-m1-gate.json", gate)
    return {k: result[k] for k in ("protocol_sha256", "sealed_sessions", "qualified_sessions", "individual_gates_passed", "descriptive_reliability_passed", "content", "outcomes_read")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "verify", "capture", "summarize"])
    args = parser.parse_args()
    print(json.dumps(globals()[args.command]()))
