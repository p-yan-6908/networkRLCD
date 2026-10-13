"""Register and run an independent-content measured-rate TURN/TCP action panel."""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RTC = REPO / "benchmarks/native_rtc"
PLAN = REPO / "docs/NATIVE_CLOCK_ACTION_TURN_TCP_V11A_PLAN.md"
REGISTERED_PROTOCOL = REPO / "configs/native_clock_action_probe_turn_tcp_v11a.json"
CAPTURE_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v11a")
SOURCE_CACHE = Path("/home/agent/.cache/networkrlcd/independent-v11-sources")
NETWORK_PROFILES = REPO / "data/native-v11/network_profiles.json"
CONTENT_SOURCES = REPO / "data/native-v11/content_sources.json"
SOURCE_SCREENING = REPO / "acquisition/native-independent-v11/source_screening.json"
PREFLIGHT_PATH = Path("/home/agent/.cache/networkrlcd/native-turn-tcp-queue-preflight-v2.json")
CALIBRATION_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-probe-v1-final3")
REPORT_PATH = REPO / "reports/native-clock-action-turntcp-v11a-analysis.json"
RECORDER = RTC / "clock_action_turn_tcp_episode_v11a.mjs"
CORE_PATH = REPO / "tools/native_clock_action_probe_turntcp_v11_core.py"
V9_WRAPPER_PATH = REPO / "tools/native_turn_clock_action_probe_v9.py"
V7_WRAPPER_PATH = REPO / "tools/native_turn_clock_action_probe_v7.py"
V7_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v7")
V7_REPORT = REPO / "reports/native-clock-action-turntcp-v7-analysis.json"
V7_PROTOCOL_SHA256 = "2eeaf29d04fdfdd63de57132bbec8308957a330180f3f9beeb6b123a1e75b85e"
V7_INDEX_SHA256 = "8bbcc5de8b6d7e2f79dffb2abb07d85418a54dc8867deb2e865658cc9683f037"
V7_GATE_SHA256 = "48af59918b64103ec050f9ada709b94f8f813ca671d617ea64dbfa856e38aa9b"
V7_REPORT_SHA256 = "3e78b850e351f8f34fea6afb244376931e4cffd7c50bdf9c8ec8b3743e5c725c"
RANDOMIZATION_SEED = 20261042
ACTION_RANDOMIZATION_SEED = 20261043
REPETITIONS = 4
POLICIES = {
    "micro": {"controller": "micro", "behavior": "ratio-randomized", "level": None,
              "policy": "micro-randomized-0.65-vs-1.05-by-preaction-bwe"},
}
V8_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v8")
V8_REPORT = REPO / "reports/native-clock-action-turntcp-v8-analysis.json"
V8_PROTOCOL_SHA256 = "102aba4d5d22a3ef3b33d17216ee8fe89b8a5addf2d96f2fcb35c5dedd5139c0"
V8_INDEX_SHA256 = "21419782f45dc9c8ac096071ad299b86b04cd8f063199acbea6deee3503afc4c"
V8_GATE_SHA256 = "98c47e187b485a0b65c3a3ad6c05ab10e6bf4f37adfc5ecad7b9e83aa30ea9c5"
V8_REPORT_SHA256 = "d324e806c5ebd38ce6497994e73710c3c0cfab3d0ea86e0de16bf1a728b8afd4"
V9_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v9")
V9_REPORT = REPO / "reports/native-clock-action-turntcp-v9-analysis.json"
V9_PROTOCOL_SHA256 = "fff551a003c703e1dc38886e9f70a7df700c9d0904a2efc88ac7062492c93484"
V9_INDEX_SHA256 = "6e794eb49b55cbc2b927330eb581c54f4be5f08500242d31e878906b171abe6f"
V9_GATE_SHA256 = "8246730530a9667892b1a22319893e9c06aaf6b54d35d39379bdb3e158b0c5a3"
V9_REPORT_SHA256 = "a20a40e4417cbd2992af71b695d0972b601dc6178394e7dbe41d544c67a12617"
V10_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v10")
V10_REPORT = REPO / "reports/native-clock-action-turntcp-v10-analysis.json"
V10_PROTOCOL_SHA256 = "30f51e5240cd142533bc198c5b7e50d584327e022300d00ce7f06ef850b178fd"
V10_INDEX_SHA256 = "ed73cb4c8792ec3e4f58cbbae781a3ef5819683357a35adbc154bc9854b61762"
V10_GATE_SHA256 = "448fb02eb49250ae1d99341d77e4625324693fc43ff83570db2f93f0d5244024"
V10_REPORT_SHA256 = "9ca5df3fc70cb8f81ac5dd94b4e4057d78e91976b41bcb21ae73bbce19c1d162"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


core = load_module("native_clock_action_probe_turntcp_v9_core", CORE_PATH)
core.RECORDER = RECORDER
base = load_module("native_turn_clock_action_probe_v7_base", V7_WRAPPER_PATH)
v2 = base.v2


def source_inventory() -> dict[str, str]:
    result = core.base_source_inventory()
    result["turntcp_v11a_wrapper"] = sha(Path(__file__).resolve())
    result["turntcp_v11a_plan_document"] = sha(PLAN)
    result["turntcp_v11a_recorder"] = sha(RECORDER)
    result["turntcp_v11a_content_source_manifest"] = sha(CONTENT_SOURCES)
    result["turntcp_v11a_network_rate_profiles"] = sha(NETWORK_PROFILES)
    result["turntcp_v11a_source_screening"] = sha(SOURCE_SCREENING)
    result["turntcp_v11a_initial_failure_record"] = sha(REPO / "reports/native-clock-action-turntcp-v11-commissioning-failure.json")
    result["turntcp_v11a_trace_derivation_tool"] = sha(REPO / "tools/derive_native_independent_v11_traces.py")
    result["turntcp_v11a_video_server"] = sha(RTC / "repair_http.mjs")
    result["turntcp_v11a_recorded_video_quality"] = sha(RTC / "recorded_video.mjs")
    result["turntcp_v8_registered_protocol"] = sha(REPO / "configs/native_clock_action_probe_turn_tcp_v8.json")
    result["turntcp_v8_result_report"] = sha(V8_REPORT)
    result["turntcp_v7_result_report"] = sha(V7_REPORT)
    result["turntcp_v9_result_report"] = sha(V9_REPORT)
    result["turntcp_v9_registered_protocol"] = sha(REPO / "configs/native_clock_action_probe_turn_tcp_v9.json")
    result["turntcp_v10_result_report"] = sha(V10_REPORT)
    result["turntcp_v10_registered_protocol"] = sha(REPO / "configs/native_clock_action_probe_turn_tcp_v10.json")
    return result


# Reuse the frozen V2 capture primitives with the independently versioned V9 core.
core_source_inventory = core.source_inventory
core.base_source_inventory = core_source_inventory
core.source_inventory = source_inventory
v2.core = core
v2.RECORDER = RECORDER
v2.PLAN = PLAN
v2.REGISTERED_PROTOCOL = REGISTERED_PROTOCOL
v2.CAPTURE_ROOT = CAPTURE_ROOT
v2.source_inventory = source_inventory


def verify_v7_result() -> dict:
    protocol_path = V7_ROOT / "protocol.json"
    index_path = V7_ROOT / "capture_index.json"
    gate_path = V7_ROOT / "clock_transport_gate.json"
    if (sha(protocol_path) != V7_PROTOCOL_SHA256 or sha(index_path) != V7_INDEX_SHA256
            or sha(gate_path) != V7_GATE_SHA256 or sha(V7_REPORT) != V7_REPORT_SHA256):
        raise ValueError("the completed V7 result or frozen capture changed")
    protocol, index, gate = (core.read_json(protocol_path), core.read_json(index_path),
                             core.read_json(gate_path))
    if (not gate.get("passed") or gate.get("outcome_analysis_performed") is not False
            or len(index.get("sessions", [])) != 32
            or any(row.get("status") != "sealed" for row in index["sessions"])):
        raise ValueError("V7 is not the completed, outcome-gated panel recorded in its result")
    report = core.read_json(V7_REPORT)
    if (report.get("outcome_data_read_after_gate") is not True
            or report.get("controller_fitted_or_promoted") is not False
            or report.get("session_clock_validations_all_pass") is not True):
        raise ValueError("V7 result does not retain the registered analysis limits")
    return {"protocol_sha256": V7_PROTOCOL_SHA256, "capture_index_sha256": V7_INDEX_SHA256,
            "clock_transport_gate_sha256": V7_GATE_SHA256, "analysis_sha256": V7_REPORT_SHA256,
            "sessions": 32, "clock_and_transport_passed": True, "pooled": False}


def verify_v8_result() -> dict:
    protocol_path = V8_ROOT / "protocol.json"
    index_path = V8_ROOT / "capture_index.json"
    gate_path = V8_ROOT / "clock_transport_gate.json"
    if (sha(protocol_path) != V8_PROTOCOL_SHA256 or sha(index_path) != V8_INDEX_SHA256
            or sha(gate_path) != V8_GATE_SHA256 or sha(V8_REPORT) != V8_REPORT_SHA256):
        raise ValueError("the completed V8 result or frozen capture changed")
    index, gate = core.read_json(index_path), core.read_json(gate_path)
    report = core.read_json(V8_REPORT)
    if (len(index.get("sessions", [])) != 48
            or any(row.get("status") != "sealed" for row in index["sessions"])
            or not gate.get("passed") or gate.get("outcome_analysis_performed") is not False
            or report.get("outcome_data_read_after_gate") is not True
            or report.get("controller_fitted_or_promoted") is not False):
        raise ValueError("V8 is not the completed, separately analyzed baseline panel")
    return {"protocol_sha256": V8_PROTOCOL_SHA256, "capture_index_sha256": V8_INDEX_SHA256,
            "clock_transport_gate_sha256": V8_GATE_SHA256, "analysis_sha256": V8_REPORT_SHA256,
            "sessions": 48, "pooled": False}


def verify_frozen_result(root: Path, report_path: Path, expected: dict, label: str,
                         sessions: int) -> dict:
    protocol_path, index_path, gate_path = (root / "protocol.json", root / "capture_index.json",
                                            root / "clock_transport_gate.json")
    if (sha(protocol_path) != expected["protocol"] or sha(index_path) != expected["index"]
            or sha(gate_path) != expected["gate"] or sha(report_path) != expected["report"]):
        raise ValueError(f"frozen {label} protocol, evidence, gate, or report changed")
    index, gate, report = (core.read_json(index_path), core.read_json(gate_path),
                           core.read_json(report_path))
    if (len(index.get("sessions", [])) != sessions
            or any(row.get("status") != "sealed" for row in index["sessions"])
            or gate.get("passed") is not True
            or gate.get("outcome_analysis_performed") is not False
            or report.get("outcome_data_read_after_gate") is not True
            or report.get("session_clock_validations_all_pass") is not True
            or report.get("controller_fitted_or_promoted") is not False):
        raise ValueError(f"frozen {label} evidence no longer satisfies its registered outcome gates")
    return {"protocol_sha256": expected["protocol"], "capture_index_sha256": expected["index"],
            "clock_transport_gate_sha256": expected["gate"], "analysis_sha256": expected["report"],
            "sessions": sessions, "pooled": False}


def verify_v9_result() -> dict:
    return verify_frozen_result(V9_ROOT, V9_REPORT,
        {"protocol": V9_PROTOCOL_SHA256, "index": V9_INDEX_SHA256,
         "gate": V9_GATE_SHA256, "report": V9_REPORT_SHA256}, "V9", 48)


def verify_v10_result() -> dict:
    return verify_frozen_result(V10_ROOT, V10_REPORT,
        {"protocol": V10_PROTOCOL_SHA256, "index": V10_INDEX_SHA256,
         "gate": V10_GATE_SHA256, "report": V10_REPORT_SHA256}, "V10", 48)


def sha1(path: Path) -> str:
    import hashlib
    digest = hashlib.sha1()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_external_sources() -> dict:
    content = core.read_json(CONTENT_SOURCES)
    network = core.read_json(NETWORK_PROFILES)
    cache_root = SOURCE_CACHE.parent
    checked = {"content_originals": [], "content_clips": [], "network_source_files": []}
    for source in content["sources"]:
        original = cache_root / source["original_cache_path"]
        clip = cache_root / source["clip_cache_path"]
        if (original.stat().st_size != source["original_bytes"]
                or sha1(original) != source["original_sha1"]
                or sha(original) != source["original_sha256"]):
            raise ValueError(f"rights-cleared content original checksum mismatch: {source['content_id']}")
        if (clip.stat().st_size != source["clip_bytes"] or sha(clip) != source["clip_sha256"]):
            raise ValueError(f"V11A transcoded content clip checksum mismatch: {source['content_id']}")
        checked["content_originals"].append({"content_id": source["content_id"],
            "bytes": source["original_bytes"], "sha1": source["original_sha1"],
            "sha256": source["original_sha256"]})
        checked["content_clips"].append({"content_id": source["content_id"],
            "bytes": source["clip_bytes"], "sha256": source["clip_sha256"]})
    for family, row in network["families"].items():
        filename = row.get("archive") or row.get("file")
        digest = row.get("archive_sha256") or row.get("file_sha256")
        path = SOURCE_CACHE / "network" / filename
        if not filename or not digest or sha(path) != digest:
            raise ValueError(f"pinned measured-network source checksum mismatch: {family}")
        checked["network_source_files"].append({"network_family": family,
            "file": filename, "sha256": digest})
    if len(content["sources"]) != 4 or len(network["families"]) != 4 or len(network["profiles"]) != 16:
        raise ValueError("V11A source inventory must retain four contents, four measured families, and sixteen profiles")
    return {"content_manifest_sha256": sha(CONTENT_SOURCES),
            "network_profiles_sha256": sha(NETWORK_PROFILES),
            "source_screening_sha256": sha(SOURCE_SCREENING), **checked}


def make_trials(root: Path, content_doc: dict, network_doc: dict) -> tuple[list[dict], list[str], list[str]]:
    content_sources = content_doc["sources"]
    family_order = ["ucc_lte_operator_A", "ucc_5g_operator_B",
                    "vienna_lte_operator_C", "vienna_5g_operator_A"]
    profiles = {row["profile_id"]: row for row in network_doc["profiles"]}
    blocks = [(content_index, family, repetition)
              for content_index in range(len(content_sources))
              for family in family_order for repetition in range(REPETITIONS)]
    rng = random.Random(RANDOMIZATION_SEED)
    rng.shuffle(blocks)
    trials, order, clusters = [], [], []
    for content_index, family, repetition in blocks:
        content = content_sources[content_index]
        profile = profiles[f"{family}-{repetition + 1:02d}"]
        cluster = f"{content['content_id']}__{family}"
        if cluster not in clusters:
            clusters.append(cluster)
        condition = "micro"
        trial_id = f"turntcp11a-c{content_index + 1:02d}-{family}-r{repetition:02d}-micro"
        schedule = []
        for block_index in range(3):
            trace = profile["rates_mbps"][block_index * 6:(block_index + 1) * 6]
            schedule.append([trace[0], f"block_{block_index}", 6600 if block_index == 2 else 6000,
                             trace])
        episode = {"id": trial_id, "role": "discovery", "content_index": content_index,
                   "content_id": content["content_id"], "capture_group": content["capture_group"],
                   "network_family": family,
                   "network_campaign_id": profile["campaign_id"],
                   "network_profile_id": profile["profile_id"],
                   "video_segment": [0, 30000],
                   "action_randomization_seed": ACTION_RANDOMIZATION_SEED,
                   "schedule": schedule, "episode_timeout_s": 90}
        panel = {
            "panel_abi": "native_clock_action_probe_v1", "stage": "discovery",
            "source_kind": "recorded_video_v1", "repair_model": None,
            "video_source": {"path": str((SOURCE_CACHE.parent / content["clip_cache_path"]).resolve()),
                             "sha256": content["clip_sha256"]},
            "models": {}, "common_shadow_inference": True, "SOTA_achieved": False,
            "episode_timeout_s": 90,
            "measurement_recipe": {
                "abi": "native_independent_content_trace_action_probe_v11a_measurement",
                "action_ratios": [0.65, 1.05], "state_threshold_bps": 500000,
                "action_hold_ms": 3000, "endpoint_window_ms": list(core.HOLD_WINDOW_MS),
                "deadline_ms": core.DEADLINE_MS,
                "clock_abi": "native_clock_marker_exchange_v1",
                "quality_protocol": "recorded_video_640x360_sampled_RGB_v1",
                "content_id": content["content_id"],
                "network_family": family, "network_profile_id": profile["profile_id"],
                "rate_profile": "six measured DL throughput values per six-second phase, 1Hz; last value held through the 0.6s tail",
            },
            "conditions": {"micro": {key: value for key, value in POLICIES["micro"].items()
                                       if key != "policy"}},
            "episodes": [episode],
        }
        panel_path = root / "panels" / f"{trial_id}.json"
        core.write_json(panel_path, panel)
        trial = {"id": trial_id, "condition": condition,
                 "policy": POLICIES[condition]["policy"], "content_id": content["content_id"],
                 "network_family": family, "network_campaign_id": profile["campaign_id"],
                 "network_profile_id": profile["profile_id"], "cell_cluster": cluster,
                 "seed_cluster": cluster, "repetition": repetition,
                 "panel": str(panel_path.relative_to(root)), "panel_sha256": sha(panel_path),
                 "order_position": len(order)}
        trials.append(trial)
        order.append(trial_id)
    return trials, order, clusters


def prepare(root: Path = CAPTURE_ROOT, preflight: Path = PREFLIGHT_PATH,
            prior_root: Path = CALIBRATION_ROOT) -> dict:
    root = root.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("fresh V11A TURN/TCP capture root required")
    calibration_reference, no_candidate_reference, _ = v2.verify_prior_evidence(prior_root)
    runtime, preflight_reference = base.runtime_provenance(preflight)
    source_status = verify_external_sources()
    content_doc = core.read_json(CONTENT_SOURCES)
    network_doc = core.read_json(NETWORK_PROFILES)
    prior_references = {
        "turn_v2": base.verify_previous_turn_v2(),
        "turn_v3": base.verify_previous_turn_v3(),
        "turn_v4": base.verify_previous_turn_v4(),
        "turn_v5": base.verify_previous_turn_v5(),
        "turn_v6": base.verify_previous_turn_v6(),
        "turn_v7": verify_v7_result(),
        "turn_v8": verify_v8_result(),
        "turn_v9": verify_v9_result(),
        "turn_v10": verify_v10_result(),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "panels").mkdir()
    trials, randomized_order, clusters = make_trials(root, content_doc, network_doc)
    content_ids = [row["content_id"] for row in content_doc["sources"]]
    family_order = ["ucc_lte_operator_A", "ucc_5g_operator_B",
                    "vienna_lte_operator_C", "vienna_5g_operator_A"]
    network_campaigns = sorted({row["campaign_id"] for row in network_doc["families"].values()})
    protocol = {
        "abi": "native_clock_action_probe_v11a_independent_content_trace_turn_tcp_protocol",
        "confirmatory": False,
        "question": "Does the positive V9 pre-action-BWE-by-ratio interaction for timely RGB PSNR replicate across separately licensed video sources and measured LTE/5G service-rate families?",
        "source_hashes": source_inventory(),
        "source_documents": source_status,
        "content_sources": {"count": len(content_ids), "ids": content_ids,
            "capture_groups": [row["capture_group"] for row in content_doc["sources"]],
            "manifest_sha256": source_status["content_manifest_sha256"]},
        "network_sources": {"family_count": len(family_order), "families": family_order,
            "independent_campaign_count": len(network_campaigns), "campaigns": network_campaigns,
            "profiles_per_family": REPETITIONS,
            "profile_document_sha256": source_status["network_profiles_sha256"],
            "dependence_note": "UCC LTE and UCC 5G families share the UCC/MISL acquisition campaign; Vienna LTE and Vienna 5G families share the Vienna acquisition campaign. Families are reported separately and are not counted as four independent measurement campaigns."},
        "cell_clusters": {"count": len(clusters), "ids": clusters,
            "definition": "one independently licensed content capture group crossed with one measured network family"},
        "repetitions_per_content_network_cell": REPETITIONS,
        "session_order_seed": RANDOMIZATION_SEED,
        "action_randomization_seed": ACTION_RANDOMIZATION_SEED,
        "randomization": {
            "abi": "native_micro_randomized_ratio_v1",
            "seed": ACTION_RANDOMIZATION_SEED,
            "state_threshold_bps": 500000,
            "state_bins": ["bwe_lt_500k", "bwe_ge_500k"],
            "ratios": [0.65, 1.05], "propensity_each_ratio": 0.5,
            "draw": "unchanged V9 algorithm: first uint32 big-endian of SHA256(networkrlcd-native-v9:{seed}:{trial_id}:{epoch}); low bit 0 selects 0.65, 1 selects 1.05",
        },
        "randomized_session_order": True,
        "randomized_order": randomized_order,
        "conditions": POLICIES,
        "trials": trials,
        "trace_replay": {
            "rates_mbps": "selected measured downlink throughput resampled to 1 Hz and replayed as local bottleneck service rates",
            "phase_labels": ["block_0", "block_1", "block_2"],
            "seconds_per_block": 6, "measurement_seconds": 18,
            "schedule_durations_ms": [6000, 6000, 6600],
            "final_sample_tail_ms": 600,
            "rate_limits_mbps": [0, 10], "rate_tick_tolerance_ms": 150,
            "symmetric_directions": True,
            "excluded_source_fields": ["latitude", "longitude", "cell_id", "measurement_id", "radio identifiers"],
            "not_a_live_path_or_packet_trace": True,
        },
        "calibration": {
            "session_marker_count": 12,
            "train_indices": [0, 1, 3, 4, 6, 7, 9, 11],
            "held_out_indices": [2, 5, 8, 10],
            "alpha_bounds": [0.98, 1.02], "max_held_out_width_ms": 50.0,
            "held_out_timestamp_tolerance_ms": 1.0,
            "solver_tolerance_ms": 1e-7, "required_held_out_coverage": 1.0,
        },
        "clock_calibration_reference": calibration_reference,
        "preflight_reference": preflight_reference,
        "runtime": runtime,
        "prior_no_candidate_action_capture_reference": no_candidate_reference,
        "prior_frozen_studies": prior_references,
        "transport": {
            "browser_ice_transport_policy": "relay", "turn_uri_scheme": "turn:",
            "browser_to_turn_transport": "TCP", "turn_relay_transport": "UDP",
            "managed_WebRtcIPHandling": "disable_non_proxied_udp", "managed_policy_change": False,
            "candidate_gathering_acceptance": "Both peers complete gathering with only loopback relay candidates using relayProtocol=tcp and zero candidate errors.",
            "selected_pair_acceptance": "Both pairs are nominated/succeeded and use TURN relay candidates over loopback with relayProtocol=tcp.",
            "media_acceptance": "Each scheduled block has more than ten encoded and decoded frames and finite mean encode time; each clip's SHA-256 is verified before serving.",
            "queue_acceptance": "Both directions forward at least 100 packets from matching TURN allocation ports, no unexpected sources or send errors; packet and byte replay exactly matches offer/drop/service/forward ledgers; capacity and conservation checks pass.",
            "queue_and_propagation_mechanism_unchanged": True,
            "trace_scheduler_acceptance": "All 18 scheduled measured-rate ticks appear in order in relay events, match the frozen rates exactly, and fall within 150 ms of their registered one-second offsets.",
        },
        "analysis": {
            "unit": "crossed content capture group by measured network family; repetitions and trace windows remain nested",
            "primary_endpoint": "on-time PSNR 1.05-minus-0.65 action effect at BWE >=500kbps minus the same action effect at BWE <500kbps",
            "minimum_hold_windows_per_cell_state_action": 2,
            "minimum_complete_content_network_cells": 13,
            "complete_cell_fraction": 0.8125,
            "replication_rule": "positive equal-weight crossed mean; positive means in both acquisition campaigns; positive interactions for at least three of four content capture groups and at least three of four measured network families. Report each source stratum; do not use the 16 crossed cells as independent replicates.",
            "secondary_endpoints": ["on-time fraction and sampled recorded-video RGB PSNR action effects by BWE stratum",
                                    "guaranteed relay wire bytes and drops per hold by BWE stratum"],
            "clock_assignment": "only estimate relay joins when all feasible affine maps cover every held-out marker",
            "action_validation": "replay every SHA256 draw; classify BWE before action; verify requested ratio/cap against proposal and native readback",
            "outcome_gate": "do not read action outcomes unless all 64 planned sessions are sealed and every transport, actual-run clock, action-randomization, and trace-schedule gate passes",
            "do_not_pool": ["V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10",
                            "V11 failed commissioning attempt", "archived native sessions",
                            "other recorded-video captures", "simulator/synthetic-controller evidence"],
            "fit_or_promote_controller": False,
        },
        "storage": {"raw_capture_root": str(root),
                    "registered_protocol": str(REGISTERED_PROTOCOL.relative_to(REPO)),
                    "analysis_output": str(REPORT_PATH.relative_to(REPO)), "raw_data_outside_git": True},
    }
    import shutil
    shutil.copytree(Path(prior_root) / "clock-calibration", root / "clock-calibration")
    shutil.copy2(Path(prior_root) / "clock_report.json", root / "clock_report.json")
    digest = v2.write_registered_protocol(root, protocol)
    return {"root": str(root), "registered_protocol": str(REGISTERED_PROTOCOL),
            "protocol_sha256": digest, "planned_sessions": len(trials),
            "content_sources": len(content_ids), "network_families": len(family_order),
            "independent_network_campaigns": len(network_campaigns),
            "content_network_cells": len(clusters), "repetitions_per_cell": REPETITIONS,
            "randomization_seed": RANDOMIZATION_SEED,
            "preflight_sha256": preflight_reference["sha256"],
            "primary_endpoint": protocol["analysis"]["primary_endpoint"],
            "session_order_seed": RANDOMIZATION_SEED,
            "action_randomization_seed": ACTION_RANDOMIZATION_SEED,
            "source_hashes": protocol["source_hashes"]}


def load_registered(root: Path) -> dict:
    root = root.expanduser().resolve()
    protocol_path = root / "protocol.json"
    protocol = core.read_json(protocol_path)
    digest = sha(protocol_path)
    if protocol.get("abi") != "native_clock_action_probe_v11a_independent_content_trace_turn_tcp_protocol":
        raise ValueError("registered V11A independent content/trace TURN/TCP protocol required")
    if digest != (root / "protocol.sha256").read_text().split()[0]:
        raise ValueError("V11A protocol checksum changed")
    if not REGISTERED_PROTOCOL.is_file() or sha(REGISTERED_PROTOCOL) != digest:
        raise ValueError("versioned V11A protocol differs from capture registration")
    if root != Path(protocol["storage"]["raw_capture_root"]).resolve():
        raise ValueError("V11A raw capture root changed")
    if (protocol.get("session_order_seed") != RANDOMIZATION_SEED
            or protocol.get("action_randomization_seed") != ACTION_RANDOMIZATION_SEED):
        raise ValueError("V11A randomization seed changed")
    if (len(protocol.get("trials", [])) != 64
            or len(set(protocol["randomized_order"])) != 64
            or protocol.get("cell_clusters", {}).get("count") != 16):
        raise ValueError("V11A must retain all 64 randomized sessions across 16 crossed cells")
    if protocol.get("calibration", {}).get("held_out_indices") != [2, 5, 8, 10]:
        raise ValueError("V11A actual-run clock marker holdouts changed")
    core.verify_sources(protocol)
    if sha(root / "clock_report.json") != protocol["clock_calibration_reference"]["report_sha256"]:
        raise ValueError("copied qualified clock report changed")
    verify_external_sources()
    verify_v9_result()
    verify_v10_result()
    return protocol


def capture(root: Path = CAPTURE_ROOT) -> dict:
    root = root.expanduser().resolve()
    protocol = load_registered(root)
    runtime_now, preflight_now = base.runtime_provenance(Path(protocol["preflight_reference"]["path"]))
    if runtime_now != protocol["runtime"]:
        raise ValueError("V11A runtime changed after registration")
    if preflight_now["sha256"] != protocol["preflight_reference"]["sha256"]:
        raise ValueError("V11A TURN/TCP preflight changed after registration")
    v2.set_runtime_env({"runtime": runtime_now})
    return core.capture(root)


def integrity(root: Path = CAPTURE_ROOT) -> dict:
    protocol = load_registered(root.expanduser().resolve())
    _, index = core.check_capture_integrity(root.expanduser().resolve())
    return {"planned": len(protocol["trials"]),
            "sealed": sum(item["status"] == "sealed" for item in index["sessions"]),
            "failed": sum(item["status"] == "failed" for item in index["sessions"]),
            "capture_index_sha256": sha(root / "capture_index.json"),
            "outcome_telemetry_read": False}


def trace_schedule_gate(root: Path, trial: dict) -> dict:
    panel_path = root / trial["panel"]
    if sha(panel_path) != trial["panel_sha256"]:
        return {"passed": False, "reason": "frozen panel checksum mismatch"}
    panel = core.read_json(panel_path)
    episode = panel["episodes"][0]
    expected = episode["schedule"]
    directory = root / "sessions" / trial["id"]
    events_path = directory / "events.jsonl.gz"
    events = [json.loads(line) for line in core.gzip.open(events_path, "rt") if line.strip()]
    phases = [row for row in events if row.get("kind") == "phase"]
    ticks = [row for row in events if row.get("kind") == "trace_capacity"]
    expected_labels = ["block_0", "block_1", "block_2"]
    if len(phases) != 3 or len(ticks) != 18:
        return {"passed": False, "reason": "phase/tick count mismatch",
                "phase_count": len(phases), "tick_count": len(ticks)}
    if [row.get("phase") for row in phases] != expected_labels:
        return {"passed": False, "reason": "phase order mismatch"}
    details = []
    for phase_index, (phase, schedule) in enumerate(zip(phases, expected, strict=True)):
        _, label, _, expected_rates = schedule
        if (phase.get("phase") != label or phase.get("trace_mbps") != expected_rates
                or phase.get("capacity_mbps") != expected_rates[0]):
            return {"passed": False, "reason": "phase rate schedule differs from frozen panel",
                    "phase": label}
        phase_ticks = [row for row in ticks if row.get("phase") == label]
        phase_ticks.sort(key=lambda row: row.get("sample_index", -1))
        if [row.get("sample_index") for row in phase_ticks] != list(range(6)):
            return {"passed": False, "reason": "one-second capacity ticks missing or duplicated",
                    "phase": label}
        tick_rows = []
        for sample_index, (tick, expected_rate) in enumerate(zip(phase_ticks, expected_rates, strict=True)):
            offset_ms = tick["at_ms"] - phase["at_ms"]
            if (tick.get("capacity_mbps") != expected_rate
                    or abs(offset_ms - sample_index * 1000) > 150):
                return {"passed": False, "reason": "capacity rate or tick timing mismatch",
                        "phase": label, "sample_index": sample_index,
                        "observed_rate_mbps": tick.get("capacity_mbps"),
                        "expected_rate_mbps": expected_rate,
                        "offset_ms": offset_ms}
            tick_rows.append({"sample_index": sample_index, "offset_ms": offset_ms,
                              "capacity_mbps": expected_rate})
        details.append({"phase": label, "ticks": tick_rows})
    return {"passed": True, "phase_count": len(phases), "tick_count": len(ticks),
            "phases": details}


def clock_gate(root: Path = CAPTURE_ROOT) -> dict:
    root = root.expanduser().resolve()
    protocol = load_registered(root)
    _, index = core.check_capture_integrity(root)
    results = []
    for item in index["sessions"]:
        row = {"trial": item["trial"], "capture_status": item["status"],
               "clock_passed": False, "transport_passed": False,
               "trace_schedule_passed": False, "outcome_data_read": False}
        if item["status"] != "sealed":
            row["reason"] = "capture failed; excluded from treatment interpretation"
            results.append(row)
            continue
        directory = root / "sessions" / item["trial"]
        ice = core.read_json(directory / "ice_evidence.json")
        urls = {candidate.get("url") for peer in ("a", "b")
                for candidate in ice.get("candidates", {}).get(peer, [])}
        url = next(iter(urls)) if len(urls) == 1 else ""
        transport = base.transport_checks(root, item["trial"], url)
        markers = core.load_marker_pair(directory / "clock_markers_browser.json",
                                        directory / "clock_markers_node.json")
        expected_ids = [f"m{number:04d}" for number in range(1, 13)]
        expected_endpoints = ["/clock-marker", "/clock-marker", "/phase", "/clock-marker",
                              "/clock-marker", "/phase", "/clock-marker", "/clock-marker",
                              "/phase", "/clock-marker", "/clock-marker", "/clock-marker"]
        expected_phases = [None, None, "block_0", None, None, "block_1", None, None,
                           "block_2", None, None, None]
        order_ok = (len(markers) == 12
                    and [marker.get("marker_id") for marker in markers] == expected_ids
                    and [marker.get("endpoint") for marker in markers] == expected_endpoints
                    and [marker.get("phase") for marker in markers] == expected_phases)
        clock = (core.validate_markers(markers, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])
                 if order_ok else {"passed": False, "reason": "12-marker order/count mismatch"})
        clock_ok = (order_ok and clock.get("passed") is True
                    and clock.get("max_held_out_width_ms", float("inf"))
                    <= protocol["calibration"]["max_held_out_width_ms"])
        trial = next(row for row in protocol["trials"] if row["id"] == item["trial"])
        trace = trace_schedule_gate(root, trial)
        row.update({"transport_passed": transport["passed"], "transport": transport,
                    "clock_passed": clock_ok,
                    "trace_schedule_passed": trace["passed"], "trace_schedule": trace,
                    "clock": {key: value for key, value in clock.items() if key != "checks"},
                    "marker_count": len(markers), "outcome_data_read": False})
        if not clock_ok or not transport["passed"] or not trace["passed"]:
            row["reason"] = "actual-run transport, clock, or trace schedule gate failed"
        results.append(row)
    passed = (len(results) == len(protocol["trials"])
              and all(row["capture_status"] == "sealed" and row["clock_passed"]
                      and row["transport_passed"] and row["trace_schedule_passed"]
                      for row in results))
    gate = {"abi": "native_turn_clock_action_v11a_gate",
            "protocol_sha256": sha(root / "protocol.json"),
            "capture_index_sha256": sha(root / "capture_index.json"),
            "passed": passed, "planned_sessions": len(protocol["trials"]),
            "qualified_clock_sessions": sum(row["clock_passed"] for row in results),
            "qualified_transport_sessions": sum(row["transport_passed"] for row in results),
            "qualified_trace_schedule_sessions": sum(row["trace_schedule_passed"] for row in results),
            "failed_capture_sessions": sum(row["capture_status"] != "sealed" for row in results),
            "outcome_analysis_performed": False, "sessions": results}
    gate_path = root / "clock_transport_gate.json"
    core.write_json(gate_path, gate)
    return {key: gate[key] for key in ("passed", "planned_sessions", "qualified_clock_sessions",
            "qualified_transport_sessions", "qualified_trace_schedule_sessions",
            "failed_capture_sessions", "outcome_analysis_performed")} | {
                "gate_sha256": sha(gate_path)}


def network_campaign_for_family(protocol: dict, family: str) -> str:
    matches = {trial["network_campaign_id"] for trial in protocol["trials"]
               if trial["network_family"] == family}
    if len(matches) != 1:
        raise ValueError(f"network family has no unique registered campaign: {family}")
    return next(iter(matches))


def analyze(root: Path = CAPTURE_ROOT, output: Path = REPORT_PATH) -> dict:
    root, output = root.expanduser().resolve(), output.expanduser().resolve()
    protocol = load_registered(root)
    gate_path = root / "clock_transport_gate.json"
    gate = core.read_json(gate_path)
    _, index = core.check_capture_integrity(root)
    if (not gate.get("passed") or gate.get("protocol_sha256") != sha(root / "protocol.json")
            or gate.get("capture_index_sha256") != sha(root / "capture_index.json")
            or len(index["sessions"]) != len(protocol["trials"])
            or any(item["status"] != "sealed" for item in index["sessions"])):
        raise ValueError("all V11A sessions must pass integrity, transport, actual-run clock, and trace schedule gates before outcomes are read")
    if output.exists():
        raise ValueError("fresh V11A analysis report path required")
    trial_map = {row["id"]: row for row in protocol["trials"]}
    sessions = []
    for item in index["sessions"]:
        trial = trial_map[item["trial"]]
        session = core.load_session_v9(root, trial, protocol)
        if not session["clock_validation"].get("passed"):
            raise ValueError(f"actual-run clock validation failed before per-hold joins: {trial['id']}")
        session.update({key: trial[key] for key in
                        ("content_id", "network_family", "network_campaign_id", "network_profile_id",
                         "cell_cluster", "repetition")})
        sessions.append(session)

    content_ids = protocol["content_sources"]["ids"]
    families = protocol["network_sources"]["families"]
    campaigns = protocol["network_sources"]["campaigns"]
    states = ("bwe_lt_500k", "bwe_ge_500k")
    ratios = (0.65, 1.05)
    cells = {}
    for content_id in content_ids:
        for family in families:
            cell_id = f"{content_id}__{family}"
            by_state_action = {}
            for state in states:
                for ratio in ratios:
                    holds = [hold for session in sessions
                             if session["cell_cluster"] == cell_id
                             for hold in session["holds"]
                             if hold["state_bin"] == state and hold["ratio"] == ratio]
                    frame_count = sum(hold["source_frames"] for hold in holds)
                    on_time_count = sum(hold["on_time_frames"] for hold in holds)
                    psnr_count = sum(hold["psnr_frame_count"] for hold in holds)
                    relay_bytes = sum(hold["relay"]["guaranteed_wire_bytes"] for hold in holds)
                    dropped_bytes = sum(hold["relay"]["guaranteed_dropped_wire_bytes"] for hold in holds)
                    by_state_action[(state, ratio)] = {
                        "hold_windows": len(holds), "source_frames": frame_count,
                        "on_time_frames": on_time_count,
                        "on_time_fraction": on_time_count / frame_count if frame_count else None,
                        "psnr_frame_count": psnr_count,
                        "mean_ontime_psnr_db": (sum(hold["psnr_sum_db"] for hold in holds) / psnr_count
                                                 if psnr_count else None),
                        "mean_guaranteed_wire_bytes_per_window": relay_bytes / len(holds) if holds else None,
                        "mean_guaranteed_dropped_wire_bytes_per_window": dropped_bytes / len(holds) if holds else None,
                    }
            complete = all(by_state_action[(state, ratio)]["hold_windows"]
                           >= protocol["analysis"]["minimum_hold_windows_per_cell_state_action"]
                           for state in states for ratio in ratios)
            cells[cell_id] = {"content_id": content_id, "network_family": family,
                              "complete": complete,
                              "state_action": {state: {str(ratio): by_state_action[(state, ratio)]
                                                       for ratio in ratios} for state in states}}

    metrics = ("mean_ontime_psnr_db", "on_time_fraction",
               "mean_guaranteed_wire_bytes_per_window",
               "mean_guaranteed_dropped_wire_bytes_per_window")
    complete_cells = [cell_id for cell_id, row in cells.items() if row["complete"]]

    def cell_interaction(cell_id: str, metric: str):
        row = cells[cell_id]
        if not row["complete"]:
            return None
        effects = {}
        for state in states:
            low = row["state_action"][state]["0.65"].get(metric)
            high = row["state_action"][state]["1.05"].get(metric)
            effects[state] = high - low if low is not None and high is not None else None
        if effects["bwe_ge_500k"] is None or effects["bwe_lt_500k"] is None:
            return None
        return effects["bwe_ge_500k"] - effects["bwe_lt_500k"]

    interaction_tables = {}
    source_strata = {}
    for metric in metrics:
        values = {cell_id: cell_interaction(cell_id, metric) for cell_id in cells}
        interaction_tables[metric] = {
            "cell_interaction_high_bwe_minus_low_bwe": values,
            "crossed_mean_over_complete_cells": (statistics.mean(values[cell_id] for cell_id in complete_cells)
                                                   if complete_cells else None),
        }
        source_strata[metric] = {
            "by_content_source": {}, "by_network_family": {}, "by_acquisition_campaign": {},
        }
        for content_id in content_ids:
            rows = [values[f"{content_id}__{family}"] for family in families
                    if values[f"{content_id}__{family}"] is not None]
            source_strata[metric]["by_content_source"][content_id] = {
                "complete_network_families": len(rows),
                "mean_interaction": statistics.mean(rows) if rows else None,
            }
        for family in families:
            rows = [values[f"{content_id}__{family}"] for content_id in content_ids
                    if values[f"{content_id}__{family}"] is not None]
            source_strata[metric]["by_network_family"][family] = {
                "acquisition_campaign": network_campaign_for_family(protocol, family),
                "complete_content_sources": len(rows),
                "mean_interaction": statistics.mean(rows) if rows else None,
            }
        for campaign in campaigns:
            campaign_families = [family for family in families
                                 if network_campaign_for_family(protocol, family) == campaign]
            rows = [values[f"{content_id}__{family}"] for content_id in content_ids
                    for family in campaign_families
                    if values[f"{content_id}__{family}"] is not None]
            source_strata[metric]["by_acquisition_campaign"][campaign] = {
                "network_families": campaign_families,
                "complete_crossed_cells": len(rows),
                "mean_interaction": statistics.mean(rows) if rows else None,
            }

    primary_metric = "mean_ontime_psnr_db"
    primary_mean = interaction_tables[primary_metric]["crossed_mean_over_complete_cells"]
    positive_contents = sum(row["mean_interaction"] is not None and row["mean_interaction"] > 0
                            for row in source_strata[primary_metric]["by_content_source"].values())
    positive_families = sum(row["mean_interaction"] is not None and row["mean_interaction"] > 0
                            for row in source_strata[primary_metric]["by_network_family"].values())
    positive_campaigns = sum(row["mean_interaction"] is not None and row["mean_interaction"] > 0
                             for row in source_strata[primary_metric]["by_acquisition_campaign"].values())
    enough_cells = len(complete_cells) >= protocol["analysis"]["minimum_complete_content_network_cells"]
    replicated_direction = bool(enough_cells and primary_mean is not None and primary_mean > 0
        and positive_contents >= 3 and positive_families >= 3
        and positive_campaigns == len(campaigns))
    max_clock_width = max(session["clock_validation"].get("max_held_out_width_ms", 0)
                          for session in sessions)
    report = {
        "abi": "native_independent_content_trace_action_probe_v11a_report",
        "protocol_sha256": sha(root / "protocol.json"),
        "capture_index_sha256": sha(root / "capture_index.json"),
        "clock_transport_gate_sha256": sha(gate_path),
        "sealed_sessions": len(sessions), "planned_sessions": len(protocol["trials"]),
        "content_capture_groups": content_ids,
        "network_families": families,
        "independent_network_campaigns": campaigns,
        "independent_network_campaign_count": len(campaigns),
        "clock_validation": {"all_sessions_passed": all(
            session["clock_validation"].get("passed") for session in sessions),
            "maximum_held_out_width_ms": max_clock_width,
            "per_hold_relay_joins_enabled_only_after_clock_gate": True},
        "trace_schedule": {"all_sessions_passed": gate.get("qualified_trace_schedule_sessions")
            == len(protocol["trials"]), "schedule_definition": protocol["trace_replay"]},
        "randomization_replay": {"mismatches": 0,
            "epoch_starts_replayed": sum(session["action_validation"][
                "randomization_epoch_starts_replayed"] for session in sessions),
            "all_draws_and_cap_readbacks_match": all(session["action_validation"][
                "all_random_draws_and_cap_readbacks_match"] for session in sessions)},
        "coverage": {"complete_content_network_cells": complete_cells,
            "complete_cell_count": len(complete_cells),
            "minimum_complete_cell_count": protocol["analysis"]["minimum_complete_content_network_cells"],
            "minimum_hold_windows_per_state_action_cell": protocol["analysis"][
                "minimum_hold_windows_per_cell_state_action"],
            "per_cell_hold_counts": {cell_id: {state: {str(ratio): row["hold_windows"]
                for ratio, row in values.items()} for state, values in cell["state_action"].items()}
                for cell_id, cell in cells.items()},
            "primary_estimable": enough_cells},
        "state_action_cell_outcomes": cells,
        "action_interactions": interaction_tables,
        "primary_endpoint": protocol["analysis"]["primary_endpoint"],
        "primary_replication": {"rule": protocol["analysis"]["replication_rule"],
            "crossed_mean_interaction_db": primary_mean,
            "positive_content_sources": positive_contents,
            "positive_network_families": positive_families,
            "positive_acquisition_campaigns": positive_campaigns,
            "direction_replicated_by_registered_rule": replicated_direction,
            "inferential_claim": False,
            "reason": "four content capture groups and two measurement campaigns support source-stratified directional replication checks, not a population-level confidence claim"},
        "source_stratified_interactions": source_strata,
        "analysis_unit": protocol["analysis"]["unit"],
        "source_dependence": protocol["network_sources"]["dependence_note"],
        "frozen_v9_v10_unchanged_and_not_pooled": True,
        "controller_fitted_or_promoted": False,
        "outcome_data_read_after_all_64_gates": True,
        "limits": [
            "Two independently acquired network campaigns are represented; their four radio/operator families are nested and not four independent campaigns.",
            "Trace throughput is replayed as symmetric local queue service rates, not as live public-network transport or packet replay.",
            "Action contrasts are short-term proximal effects conditional on pre-action sender BWE, not closed-loop policy value.",
            "Sampled RGB PSNR and a 150 ms pixel-readback deadline are proxies, not human QoE.",
            "No outcome is pooled with V3-V10, prior archive runs, or synthetic-controller evidence.",
        ],
    }
    report["runtime"] = protocol["runtime"]
    report["preflight_reference"] = protocol["preflight_reference"]
    report["clock_calibration_reference"] = protocol["clock_calibration_reference"]
    report["prior_frozen_studies"] = protocol["prior_frozen_studies"]
    report["transport"] = protocol["transport"]
    report["actual_run_clock_transport_gate_sha256"] = sha(gate_path)
    core.write_json(output, report)
    return {"report": str(output), "report_sha256": sha(output),
            "sessions": report["sealed_sessions"],
            "actual_session_clocks_all_pass": report["clock_validation"]["all_sessions_passed"],
            "primary_interaction_db": primary_mean,
            "direction_replicated_by_registered_rule": replicated_direction,
            "clock_transport_gate_sha256": report["actual_run_clock_transport_gate_sha256"],
            "controller_fitted_or_promoted": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("capture", "integrity", "clock-gate"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, default=CAPTURE_ROOT)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--root", type=Path, default=CAPTURE_ROOT)
    prepare_parser.add_argument("--preflight", type=Path, default=PREFLIGHT_PATH)
    prepare_parser.add_argument("--prior-root", type=Path, default=CALIBRATION_ROOT)
    analyze_parser = commands.add_parser("analyze")
    analyze_parser.add_argument("--root", type=Path, default=CAPTURE_ROOT)
    analyze_parser.add_argument("--out", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.root, args.preflight, args.prior_root)
    elif args.command == "capture":
        result = capture(args.root)
    elif args.command == "integrity":
        result = integrity(args.root)
    elif args.command == "clock-gate":
        result = clock_gate(args.root)
    else:
        result = analyze(args.root, args.out)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
