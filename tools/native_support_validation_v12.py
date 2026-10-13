"""Register V12 and qualify support before exposing confirmatory outcomes.

This tool has no outcome-analysis or controller-fitting command. It reuses
frozen V11D clock, transport, queue, trace and cleanup validators. Its own
validator projects sender support/assignment/readback fields only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import shutil
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RTC = REPO / "benchmarks/native_rtc"
ROOT = Path.home() / ".cache/networkrlcd/native-support-validation-v12"
DEVELOPMENT_ROOT = Path.home() / ".cache/networkrlcd/native-support-validation-v12-development"
CONFIG = REPO / "configs/native_support_validation_v12.json"
PLAN = REPO / "docs/NATIVE_SUPPORT_VALIDATION_V12_PLAN.md"
RECORDER = RTC / "clock_action_turn_tcp_episode_v12.mjs"
ORDER_SEED, ACTION_SEED, DEVELOPMENT_SEED = 20261081, 20261082, 20261083
STATES = ("bwe_lt_500k", "bwe_ge_500k")


def module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


frozen = module(REPO / "tools/native_turn_clock_action_probe_v11d.py", "frozen_v11d_support_dependencies")
core = frozen.core
core.RECORDER = RECORDER


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as s:
        for b in iter(lambda: s.read(4 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def inventory() -> dict:
    # Pin every inherited dependency as well as the new instrumentation.
    paths = {p.relative_to(REPO).as_posix(): p for p in RTC.glob("*.mjs")}
    for path in (REPO / "tools").glob("native_*clock*probe*.py"):
        paths[path.relative_to(REPO).as_posix()] = path
    paths["tools/native_support_validation_v12.py"] = Path(__file__).resolve()
    return {name: sha(path) for name, path in sorted(paths.items())}


core.source_inventory = inventory


def panel_for(trial_id, content, profile, pair_id, slot, seed, support_only=False):
    schedule = [[profile["rates_mbps"][i * 6], f"block_{i}", 6600 if i == 2 else 6000,
                 profile["rates_mbps"][i * 6:(i + 1) * 6]] for i in range(3)]
    episode = {"id": trial_id, "role": "discovery", "content_index": 0,
        "content_id": content["content_id"], "network_family": profile["family_id"],
        "network_profile_id": profile["profile_id"], "network_campaign_id": profile["campaign_id"],
        "video_segment": [0, 30000], "action_randomization_seed": seed,
        "schedule": schedule, "episode_timeout_s": 90,
        "support_config": {"target_state": profile["target_state"], "pair_id": pair_id,
                           "pair_slot": slot, "support_only": support_only}}
    return {"panel_abi": "native_clock_action_probe_v1", "stage": "discovery",
        "source_kind": "recorded_video_v1", "repair_model": None,
        "video_source": {"path": str(Path.home() / ".cache/networkrlcd" / content["clip_cache_path"]),
                         "sha256": content["clip_sha256"]},
        "models": {}, "common_shadow_inference": True, "SOTA_achieved": False,
        "episode_timeout_s": 90, "measurement_recipe": {
            "abi": "native_support_qualified_action_v12_measurement", "action_ratios": [.65, 1.05],
            "state_threshold_bps": 500000, "action_hold_ms": 3000,
            "endpoint_window_ms": list(core.HOLD_WINDOW_MS), "deadline_ms": core.DEADLINE_MS,
            "quality_protocol": "recorded_video_640x360_sampled_RGB_v1",
            "common_pre_treatment_cap_bps": 4000000, "support_only": support_only},
        "conditions": {"micro": {"controller": "micro", "behavior": "ratio-randomized", "level": None}},
        "episodes": [episode]}


def write_trial(root, content, profile, pair_id, slot, seed, support_only=False):
    trial_id = f"{pair_id}-s{slot}" + ("-support" if support_only else "")
    panel = panel_for(trial_id, content, profile, pair_id, slot, seed, support_only)
    relative = f"panels/{trial_id}.json"
    write(root / relative, panel)
    return {"id": trial_id, "condition": "micro", "panel": relative, "panel_sha256": sha(root / relative),
            "content_id": content["content_id"], "network_family": profile["family_id"],
            "network_campaign_id": profile["campaign_id"], "network_profile_id": profile["profile_id"],
            "target_state": profile["target_state"], "pair_id": pair_id, "pair_slot": slot,
            "cell_cluster": content["content_id"] + "__" + profile["family_id"], "support_only": support_only}


def common_protocol(root, trials, abi, seed):
    prior = read(REPO / "configs/native_clock_action_probe_turn_tcp_v11d.json")
    return {"abi": abi, "source_hashes": inventory(), "randomization": {"seed": seed},
        "calibration": prior["calibration"], "clock_calibration_reference": prior["clock_calibration_reference"],
        "preflight_reference": prior["preflight_reference"], "runtime": prior["runtime"],
        "trace_replay": prior["trace_replay"], "transport": prior["transport"],
        "storage": {"raw_capture_root": str(root)},
        "trials": trials, "randomized_order": [row["id"] for row in trials],
        "analysis": {"fit_or_promote_controller": False, "outcomes_read": False,
                     "minimum_hold_windows_per_cell_state_action": 2}}


def seal_protocol(root, protocol):
    write(root / "protocol.json", protocol)
    (root / "protocol.sha256").write_text(sha(root / "protocol.json") + "  protocol.json\n")
    source = Path.home() / ".cache/networkrlcd/native-clock-action-turntcp-v11d/clock_report.json"
    if sha(source) != protocol["clock_calibration_reference"]["report_sha256"]:
        raise ValueError("qualified reference clock report drift")
    shutil.copy2(source, root / "clock_report.json")


def verify_assets():
    cache = Path.home() / ".cache/networkrlcd"
    content = read(REPO / "data/native-v12/content_sources.json")
    network = read(REPO / "data/native-v12/network_profiles.json")
    for row in content["sources"]:
        for kind in ("original", "clip"):
            path = cache / row[f"{kind}_cache_path"]
            if path.stat().st_size != row[f"{kind}_bytes"] or sha(path) != row[f"{kind}_sha256"]:
                raise ValueError("V12 content checksum mismatch")
        if hashlib.sha1((cache / row["original_cache_path"]).read_bytes()).hexdigest() != row["original_sha1"]:
            raise ValueError("V12 Commons catalogue SHA-1 mismatch")
    for row in network["families"].values():
        path = cache / row["archive_cache_path"]
        if path.stat().st_size != row["archive_bytes"] or sha(path) != row["archive_sha256"]:
            raise ValueError("V12 measured-network archive checksum mismatch")
    return content, network


def development():
    if DEVELOPMENT_ROOT.exists():
        raise ValueError("preserve completed development capture; use the sealed report")
    content = read(REPO / "data/native-v11d/content_sources.json")["sources"][0]
    if sha(Path.home() / ".cache/networkrlcd" / content["clip_cache_path"]) != content["clip_sha256"]:
        raise ValueError("V11D development content drift")
    trials = []
    for state, rate in zip(STATES, (.35, 1.2), strict=True):
        profile = {"family_id": "development_constant_service", "profile_id": state,
                   "campaign_id": "development_synthetic_link_only", "rates_mbps": [rate] * 18,
                   "target_state": state}
        pair_id = f"v12-development-{state}"
        trials.append(write_trial(DEVELOPMENT_ROOT, content, profile, pair_id + "-census", 0, DEVELOPMENT_SEED, True))
        for slot in (0, 1):
            trials.append(write_trial(DEVELOPMENT_ROOT, content, profile, pair_id, slot, DEVELOPMENT_SEED))
    protocol = common_protocol(DEVELOPMENT_ROOT, trials, "native_v12_instrumentation_development_only", DEVELOPMENT_SEED)
    protocol["scientific_evidence"] = False
    protocol["source_note"] = "V11D cicada content reused for development; constant .35/1.2Mbps links are synthetic commissioning inputs, not independently measured validation evidence. Outcome telemetry remains unopened."
    seal_protocol(DEVELOPMENT_ROOT, protocol)
    frozen.v2.set_runtime_env(protocol)
    capture = core.capture(DEVELOPMENT_ROOT)
    result = gate(DEVELOPMENT_ROOT)
    write(REPO / "reports/native-v12-development-qualification.json", result)
    return {"capture": capture, "gate": {k: result[k] for k in ("passed", "planned_sessions", "qualified_sessions")}}


def sender_gate(directory: Path, trial: dict, protocol: dict):
    sender = read(directory / "sender_observations.json")
    screen = sender["support_screen"]
    cfg = screen["config"]
    passed = (cfg["target_state"] == trial["target_state"] and cfg["pair_id"] == trial["pair_id"]
              and cfg["pair_slot"] == trial["pair_slot"] and cfg["support_only"] == trial["support_only"])
    qualification = screen.get("qualification")
    if not qualification or qualification.get("passed") is not True:
        return {"passed": False, "reason": "prospective BWE support unavailable at the fixed decision window",
                "qualification": qualification, "assigned_holds": 0, "outcome_data_read": False}
    times, bwes = qualification["sample_history_ms"], qualification["bwe_history_bps"]
    elapsed = qualification["elapsed_ms"]
    passed &= (len(times) == len(bwes) == 11 and 9000 <= elapsed <= 9300
               and times[-1] - times[0] >= 900 and all(0 < b - a <= 250 for a, b in zip(times, times[1:]))
               and all(240000 <= v <= 3800000 and STATES[int(v >= 500000)] == trial["target_state"] for v in bwes))
    decisions = sender["decisions"]
    by_time = {row["sample_ms"]: row for row in decisions}
    passed &= all(t in by_time and abs(by_time[t]["policy_input"]["features"][0] * 4000000 - bwe) < .01
                  for t, bwe in zip(times, bwes, strict=True))
    assigned = [row for row in decisions if row.get("actuator_assignment") is not None]
    boundary = next((row for row in assigned if row["sample_ms"] == row["actuator_assignment"]["assignment_ms"]), None)
    ratio, ack, cap = None, None, None
    if trial["support_only"]:
        passed &= not assigned and screen["action_assigned"] is False
    else:
        seed = protocol["randomization"]["seed"]
        draw = int.from_bytes(hashlib.sha256(f"networkrlcd-native-v12:{seed}:{trial['pair_id']}".encode()).digest()[:4], "big")
        ratio = (0.65, 1.05)[(draw & 1) ^ trial["pair_slot"]]
        if boundary is None:
            passed = False
        else:
            a = boundary["actuator_assignment"]
            cap = math.floor(ratio * bwes[-1] + .5)
            ack = boundary["ack_ms"]
            passed &= (a["abi"] == "native_support_qualified_ratio_v12" and a["epoch"] == 0
                and a["draw_uint32"] == draw and a["ratio"] == ratio and a["state_bin"] == trial["target_state"]
                and a["base_bwe_bps"] == bwes[-1] and a["randomization_seed"] == seed
                and a["trial_id"] == trial["id"] and a["pair_id"] == trial["pair_id"] and a["pair_slot"] == trial["pair_slot"]
                and a["requested_bps"] == cap and a["assignment_ms"] == times[-1]
                and a["assignment_ms"] - sender["measurement_start_ms"] == elapsed
                and a["conditional_propensity_given_prior_pair_slot"] == (1 if trial["pair_slot"] else .5)
                and a["support_qualification"] == qualification and ack >= a["assignment_ms"]
                and ack + 3000 <= sender["measurement_cutoff_ms"] and len({r["actuator_assignment"]["epoch"] for r in assigned}) == 1)
            # Preserve the original [ack+1800, ack+2600] endpoint definition.
            passed &= ack + core.HOLD_WINDOW_MS[1] <= sender["measurement_cutoff_ms"]
    for row in decisions:
        a = row.get("actuator_assignment")
        expected_cap = a["requested_bps"] if a else 4000000
        passed &= (row["proposed_action"]["encoder_max_bitrate_bps"] == expected_cap
                   and row["actuation_readback"]["encoder_max_bitrate_bps"] == expected_cap
                   and row["proposed_action"]["receiver_jitter_buffer_target_ms"] == 0
                   and row["actuation_readback"]["receiver_jitter_buffer_target_ms"] == 0)
        if a and boundary:
            passed &= a == boundary["actuator_assignment"]
    passed &= not sender["sampling_errors"] and all(
        by_time[t].get("actuator_assignment") is None for t in times[:-1])
    return {"passed": bool(passed), "qualification": qualification, "ratio": ratio,
            "assigned_holds": int(bool(assigned)), "ack_ms": ack, "cap_bps": cap,
            "outcome_data_read": False}


def gate(root):
    protocol, index = core.check_capture_integrity(root)
    results, counts = [], Counter()
    for item in index["sessions"]:
        trial = next(t for t in protocol["trials"] if t["id"] == item["trial"])
        result = {"trial": trial["id"], "status": item["status"], "passed": False}
        if item["status"] == "sealed":
            directory = root / "sessions" / trial["id"]
            markers = core.load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
            order = [row["marker_id"] for row in markers] == [f"m{i:04}" for i in range(1, 13)]
            clock = core.validate_markers(markers, protocol["calibration"]["train_indices"], protocol["calibration"]["held_out_indices"]) if order else {"passed": False}
            ice = read(directory / "ice_evidence.json")
            urls = {c.get("url") for peer in ("a", "b") for c in ice.get("candidates", {}).get(peer, [])}
            transport = frozen.base.transport_checks(root, trial["id"], next(iter(urls)) if len(urls) == 1 else "")
            trace = frozen.trace_schedule_gate(root, trial)
            cleanup = frozen.terminal_cleanup_gate(root, trial, markers, protocol)
            support = sender_gate(directory, trial, protocol)
            summary = read(directory / "summary.json")
            media = (summary.get("connection") == "connected" and summary.get("native_rtc") is True
                and len(summary.get("snapshots", [])) == 3 and all(s.get("frames_encoded", 0) > 10
                    and s.get("frames_decoded", 0) > 10 and isinstance(s.get("mean_encode_s"), (float, int))
                    and math.isfinite(s["mean_encode_s"]) for s in summary["snapshots"]))
            result.update({"clock": {k: v for k, v in clock.items() if k != "checks"},
                "transport_passed": transport["passed"], "trace_passed": trace["passed"],
                "cleanup_passed": cleanup["passed"], "media_passed": bool(media), "support": support})
            result["passed"] = bool(clock["passed"] and transport["passed"] and trace["passed"] and cleanup["passed"] and support["passed"] and media)
            if result["passed"] and not trial["support_only"]:
                counts[trial["cell_cluster"], trial["target_state"], support["ratio"]] += 1
        results.append(result)
    confirmatory = protocol.get("confirmatory") is True
    complete_cells = []
    if confirmatory:
        complete_cells = [cell for cell in protocol["cell_ids"] if all(counts[cell, state, ratio] >= 2
                          for state in STATES for ratio in (.65, 1.05))]
    passed = all(row["passed"] for row in results) and len(results) == len(protocol["trials"])
    if confirmatory:
        passed &= len(complete_cells) == len(protocol["cell_ids"]) == 6
    report = {"abi": "native_v12_support_clock_transport_gate_v1", "protocol_sha256": sha(root / "protocol.json"),
        "capture_index_sha256": sha(root / "capture_index.json"), "passed": bool(passed),
        "planned_sessions": len(results), "qualified_sessions": sum(row["passed"] for row in results),
        "complete_cells": complete_cells, "hold_counts": [{"cell": c, "state": s, "ratio": r, "holds": n}
            for (c, s, r), n in sorted(counts.items())],
        "scope": "Technical support and liveness only; no frame quality, on-time delivery or per-hold relay outcomes read.",
        "outcome_telemetry_read": False, "sessions": results}
    write(root / "support_clock_transport_gate.json", report)
    return report


def prepare():
    if ROOT.exists() or CONFIG.exists():
        raise ValueError("a fresh confirmatory registration is required; preserve prior versions")
    content, network = verify_assets()
    development_report = read(REPO / "reports/native-v12-development-qualification.json")
    if not development_report["passed"]:
        raise ValueError("development instrumentation has not qualified")
    pairs = [(c, p) for c in content["sources"] for p in network["profiles"]]
    random.Random(ORDER_SEED).shuffle(pairs)
    trials, census = [], []
    support_root = ROOT.with_name(ROOT.name + "-support")
    for i, (c, p) in enumerate(pairs):
        pair_id = f"v12-p{i:02d}"
        census.append(write_trial(support_root, c, p, pair_id, 0, ACTION_SEED, True))
        for slot in (0, 1):
            trials.append(write_trial(ROOT, c, p, pair_id, slot, ACTION_SEED))
    protocol = common_protocol(ROOT, trials, "native_v12_independent_support_qualified_protocol", ACTION_SEED)
    protocol.update({"confirmatory": True, "anchor_commit": "92a6ae3", "session_order_seed": ORDER_SEED,
        "cell_ids": sorted({t["cell_cluster"] for t in trials}), "independent_content_groups": content["content_capture_groups"],
        "independent_network_campaigns": sorted({f["campaign_id"] for f in network["families"].values()}),
        "support_census_root": str(support_root),
        "development_report_sha256": sha(REPO / "reports/native-v12-development-qualification.json"),
        "preregistration_files": {p.relative_to(REPO).as_posix(): sha(p) for p in (
            PLAN, REPO / "data/native-v12/content_sources.json", REPO / "data/native-v12/network_profiles.json",
            REPO / "acquisition/native-independent-v12/source_screening.json")},
        "prior_evidence_sha256": {p.relative_to(REPO).as_posix(): sha(p) for directory in ("configs", "reports", "docs")
            for p in (REPO / directory).glob("*v*.json") if "v12" not in p.name},
        "support_contract": {"threshold_bps": 500000, "eligible_bwe_bounds_bps": [240000, 3800000],
            "baseline_cap_bps": 4000000, "decision_window_ms": [9000, 9300], "minimum_history_samples": 11,
            "minimum_history_span_ms": 900, "maximum_sample_gap_ms": 250,
            "minimum_complete_cells": 6, "minimum_holds_per_cell_state_action": 2,
            "fixed_total_sessions": 48, "failed_sessions_replaced": False,
            "new_sources_exposed_to_native_actions_before_registration": False},
        "outcome_contract": {"deadline_ms": 150, "window_after_ack_ms": [1800, 2600],
            "primary": "timely sampled RGB PSNR action effect (1.05 minus 0.65) at high BWE minus its effect at low BWE",
            "secondary": ["on-time fraction", "guaranteed offered relay wire bytes per hold", "guaranteed dropped relay wire bytes per hold"],
            "complete_primary_cells_required": 6, "missing_psnr_imputed": False,
            "summary": "same frame-weighted state/action bucket means and equal crossed-cell means as V11D; campaign/family/content strata remain explicit",
            "inferential_scope": "finite selected panel; directional stability check, no population CI or controller value claim",
            "decision_rules_authority": "docs/NATIVE_SUPPORT_VALIDATION_V12_PLAN.md"}})
    seal_protocol(ROOT, protocol)
    shutil.copy2(ROOT / "protocol.json", CONFIG)
    support_protocol = common_protocol(support_root, census, "native_v12_pre_treatment_support_census", ACTION_SEED)
    support_protocol["confirmatory_protocol_sha256"] = sha(CONFIG)
    seal_protocol(support_root, support_protocol)
    return {"protocol_sha256": sha(CONFIG), "planned_sessions": len(trials), "support_census_sessions": len(census),
            "cells": len(protocol["cell_ids"]), "outcomes_collected": False}


def verify_registration():
    protocol = read(CONFIG)
    core.verify_sources(protocol)
    verify_assets()
    if sha(ROOT / "protocol.json") != sha(CONFIG):
        raise ValueError("registered protocol differs from capture root")
    for name, expected in {**protocol["preregistration_files"], **protocol["prior_evidence_sha256"]}.items():
        if sha(REPO / name) != expected:
            raise ValueError(f"registered or frozen prior evidence changed: {name}")
    for trial in protocol["trials"]:
        if sha(ROOT / trial["panel"]) != trial["panel_sha256"]:
            raise ValueError("registered session panel drift")
    if len(protocol["trials"]) != 48 or len(protocol["cell_ids"]) != 6:
        raise ValueError("registered panel cardinality drift")
    for pair in {t["pair_id"] for t in protocol["trials"]}:
        rows = [t for t in protocol["trials"] if t["pair_id"] == pair]
        if len(rows) != 2 or sorted(t["pair_slot"] for t in rows) != [0, 1]:
            raise ValueError("balanced pair inventory drift")
    return {"verified": True, "protocol_sha256": sha(CONFIG), "planned_sessions": 48,
            "confirmatory_capture_started": (ROOT / "sessions").exists(),
            "support_census_started": (Path(protocol["support_census_root"]) / "sessions").exists()}


def run_registered(support_only=False):
    verify_registration()
    protocol = read(CONFIG)
    root = Path(protocol["support_census_root"]) if support_only else ROOT
    if not support_only:
        gate_path = Path(protocol["support_census_root"]) / "support_clock_transport_gate.json"
        # Recompute seals/support; a stale pass flag never authorizes capture.
        report = gate(Path(protocol["support_census_root"]))
        if not report["passed"] or read(Path(protocol["support_census_root"]) / "protocol.json")["confirmatory_protocol_sha256"] != sha(CONFIG):
            raise ValueError("all 24 registered support census sessions must qualify before any treatment capture")
        if not gate_path.is_file():
            raise ValueError("support census gate missing")
    current, _ = frozen.base.runtime_provenance(Path(protocol["preflight_reference"]["path"]))
    if current != protocol["runtime"]:
        raise ValueError("registered Chromium/TURN/policy runtime changed")
    frozen.v2.set_runtime_env(protocol)
    result = core.capture(root)
    return {"capture": result, "gate": gate(root)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("development", "prepare", "verify", "support-census", "capture", "gate"))
    args = parser.parse_args()
    function = {"development": development, "prepare": prepare, "verify": verify_registration,
                "support-census": lambda: run_registered(True), "capture": run_registered, "gate": lambda: gate(ROOT)}[args.command]
    result = function()
    print(json.dumps(result if args.command != "gate" else {k: result[k] for k in ("passed", "planned_sessions", "qualified_sessions", "complete_cells")}))
