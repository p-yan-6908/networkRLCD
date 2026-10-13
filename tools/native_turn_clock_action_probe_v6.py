"""Register and run a fresh TURN/TCP native 0.65/1.05 clock/action V6 panel."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import random
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
V2_PATH = REPO / "tools/native_turn_clock_action_probe_v2.py"
CORE_PATH = REPO / "tools/native_clock_action_probe_turntcp_v6_core.py"
RECORDER = REPO / "benchmarks/native_rtc/clock_action_turn_tcp_episode_v5.mjs"
PREFLIGHT_SCRIPT = REPO / "tools/native_turn_tcp_queue_preflight_v2.mjs"
PLAN = REPO / "docs/NATIVE_CLOCK_ACTION_TURN_TCP_V6_PLAN.md"
REGISTERED_PROTOCOL = REPO / "configs/native_clock_action_probe_turn_tcp_v6.json"
CAPTURE_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v6")
PREFLIGHT_PATH = Path("/home/agent/.cache/networkrlcd/native-turn-tcp-queue-preflight-v2.json")
DEFAULT_CALIBRATION = Path("/home/agent/.cache/networkrlcd/native-clock-action-probe-v1-final3")
V2_TURN_CAPTURE = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v2")
V2_TURN_PROTOCOL_SHA256 = "31b220e8904be3e900ebe6c21a5a0f4550e56db927fe223fee95a3a041f10beb"
V2_TURN_INDEX_SHA256 = "f54a6cd6a5d042bbeb14eb7b3e6e51c6f84fdeaa65e6d912be18e68aee830414"
V3_TURN_CAPTURE = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v3")
V3_TURN_PROTOCOL_SHA256 = "a599601b5182ca4e3de24ec3a93cd422f0afba11c7de613d7196433f2affd4d6"
V3_TURN_INDEX_SHA256 = "2fac8af41adcc378b63951f3e84b30919462abda5a28c779aa6ca120d96257d8"
V3_DIAGNOSTIC = REPO / "reports/native-clock-action-turntcp-v3-diagnostic-only.json"
V3_DIAGNOSTIC_SHA256 = "bce4517a5e6003516b01168eeb15c486e934acdd867185c2dcc26001e4b477e4"
V4_TURN_CAPTURE = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v4")
V4_TURN_PROTOCOL_SHA256 = "1937b2a88ca08f1a7d25382a09aacab36c80c28bcac79404add1f5346b739a2c"
V4_TURN_INDEX_SHA256 = "78221a758a856f05de66a49cd07bad9d38f9a5e35ae33f6f54fb29c513f0798a"
V4_TURN_GATE_SHA256 = "059933b7f0c1b37121b77adb2cf9358548c0cead861c569107a63a17e6e0abb0"
V4_DIAGNOSTIC = REPO / "reports/native-clock-action-turntcp-v4-gate-diagnostic-only.json"
V4_DIAGNOSTIC_SHA256 = "390bfb7fc961e7df30708e2a3b8cac123a71ad5067c815935f3895b820cf8ad5"
V5_TURN_CAPTURE = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v5")
V5_TURN_PROTOCOL_SHA256 = "394ae78949257e5ffb6f38a0802970c201e8b869bbb5a854dd505ea5bde9f7cb"
V5_TURN_INDEX_SHA256 = "1b2f6c59d369131ef9625c5be6c5546370bdfc274d2f3d326f4e175591223143"
V5_TURN_GATE_SHA256 = "632494e98c4c2906e61ec36b0a09f64ba363e3d85381490f4160033bec21e6b8"
V5_DIAGNOSTIC = REPO / "reports/native-clock-action-turntcp-v5-gate-diagnostic-only.json"
V5_DIAGNOSTIC_SHA256 = "05eae9136a0b19617847c030289eaa156639d04d35088c73f88c48949842ade0"
RANDOMIZATION_SEED = 20261017
SCENE_SEEDS = tuple(range(5000, 5008))
POLICY_PATH = Path("/etc/chromium/policies/managed/misc.json")
CHROMIUM_PATH = Path("/usr/bin/chromium")
COTURN_BINARY = Path("/home/agent/.cache/networkrlcd/turn-runtime/extracted/usr/bin/turnserver")
COTURN_PACKAGE = Path("/home/agent/.cache/networkrlcd/turn-runtime/coturn_4.6.1-2_amd64.deb")
COTURN_PACKAGE_SHA256 = "cb55194d0118d26035aa39aa7306fd810a47069643266724357e8da2a22612e0"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(Path(path).read_text())


def write_json(path: Path, value) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


core_spec = importlib.util.spec_from_file_location("native_clock_action_turntcp_v6_core", CORE_PATH)
if core_spec is None or core_spec.loader is None:
    raise RuntimeError("cannot load V6 clock/action analysis core")
core = importlib.util.module_from_spec(core_spec)
core_spec.loader.exec_module(core)
core.RECORDER = RECORDER
base_source_inventory = core.source_inventory

v2_spec = importlib.util.spec_from_file_location("native_turn_clock_action_probe_v2_base", V2_PATH)
if v2_spec is None or v2_spec.loader is None:
    raise RuntimeError("cannot load frozen TURN/TCP capture helpers")
v2 = importlib.util.module_from_spec(v2_spec)
v2_spec.loader.exec_module(v2)
v2.core = core
v2.__dict__["core"] = core
v2.RECORDER = RECORDER
v2.PLAN = PLAN
v2.REGISTERED_PROTOCOL = REGISTERED_PROTOCOL


def source_inventory() -> dict[str, str]:
    result = base_source_inventory()
    result["turntcp_v6_preflight_source"] = sha(PREFLIGHT_SCRIPT)
    result["turntcp_v6_action_wrapper"] = sha(Path(__file__).resolve())
    result["turntcp_v6_plan_document"] = sha(PLAN)
    result["turntcp_v6_clock_core"] = sha(CORE_PATH)
    return result


core.source_inventory = source_inventory
v2.source_inventory = source_inventory


def runtime_provenance(preflight_path: Path) -> tuple[dict, dict]:
    preflight_path = preflight_path.expanduser().resolve()
    preflight_hash = sha(preflight_path)
    if preflight_path != PREFLIGHT_PATH or preflight_hash != "a45a8e2a9fec3303a8c09afb8d44896b8b642692fbc43a37d9917e768c345061":
        raise ValueError("the successful queue-backed TURN/TCP preflight changed")
    preflight = read_json(preflight_path)
    if preflight.get("abi") != "native_turn_tcp_owned_queue_media_preflight_v2" or not preflight.get("passed"):
        raise ValueError("TURN/TCP owned-queue bidirectional media preflight did not pass")
    if not all(preflight.get("acceptance", {}).values()):
        raise ValueError("queue-backed TURN/TCP preflight acceptance evidence is incomplete")
    if preflight.get("source_sha256") != sha(PREFLIGHT_SCRIPT):
        raise ValueError("queue-backed preflight source differs from its recorded run")
    if preflight.get("managed_policy", {}).get("WebRtcIPHandling_before") != "disable_non_proxied_udp":
        raise ValueError("preflight did not use the registered managed Chromium policy")
    if not preflight.get("managed_policy", {}).get("unchanged"):
        raise ValueError("managed Chromium policy changed during preflight")
    queue = preflight.get("queue", {})
    for direction in ("a_to_b", "b_to_a"):
        link = queue.get(direction, {})
        if (
            link.get("forwarded_packets", 0) < 100
            or link.get("unexpected_sources") != 0
            or link.get("send_errors") != 0
            or link.get("overflow_packets") != 0
            or link.get("capacity_integral_upper_bound_ok") is not True
            or abs(link.get("conservation_error_bytes", float("inf"))) > 1e-6
        ):
            raise ValueError("queue-backed preflight did not satisfy both-direction packet and ledger checks")

    turn = preflight["turn"]
    if sha(COTURN_BINARY) != turn["binary_sha256"] or sha(COTURN_PACKAGE) != COTURN_PACKAGE_SHA256:
        raise ValueError("the pinned Coturn executable or package changed after preflight")
    library_dir = Path(turn["library_dir"])
    library_hashes = {}
    for name, expected in turn["library_sha256"].items():
        library_path = library_dir / name
        if not expected or sha(library_path) != expected:
            raise ValueError("a Coturn runtime library changed after preflight: " + name)
        library_hashes[name] = expected
    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = str(library_dir) + (
        os.pathsep + environment["LD_LIBRARY_PATH"] if environment.get("LD_LIBRARY_PATH") else ""
    )
    linked = subprocess.check_output(["ldd", str(COTURN_BINARY)], text=True, env=environment)
    if "not found" in linked:
        raise ValueError("the pinned Coturn runtime has an unresolved shared library")

    policy_bytes = POLICY_PATH.read_bytes()
    policy = json.loads(policy_bytes)
    policy_hash = hashlib.sha256(policy_bytes).hexdigest()
    if policy.get("WebRtcIPHandling") != "disable_non_proxied_udp":
        raise ValueError("managed Chromium policy no longer matches the preflight")
    if policy_hash != preflight["managed_policy"]["sha256_after"]:
        raise ValueError("managed Chromium policy differs from preflight")
    browser_hash = sha(CHROMIUM_PATH)
    if browser_hash != preflight["browser"]["sha256"]:
        raise ValueError("Chromium binary differs from preflight")
    runtime = {
        "coturn_version": turn["version"],
        "coturn_package_path": str(COTURN_PACKAGE),
        "coturn_package_sha256": COTURN_PACKAGE_SHA256,
        "coturn_binary_path": str(COTURN_BINARY),
        "coturn_binary_sha256": turn["binary_sha256"],
        "coturn_library_dir": str(library_dir),
        "coturn_library_sha256": library_hashes,
        "chromium_binary_path": str(CHROMIUM_PATH),
        "chromium_sha256": browser_hash,
        "chromium_version": preflight["browser"]["version"],
        "managed_policy_path": str(POLICY_PATH),
        "managed_policy_value": policy["WebRtcIPHandling"],
        "managed_policy_sha256": policy_hash,
        "network_policy": "TURN control TCP and relay/queue UDP are loopback-only",
    }
    reference = {
        "path": str(preflight_path),
        "sha256": preflight_hash,
        "source_sha256": preflight["source_sha256"],
        "passed": True,
        "turn_candidates": [
            len(preflight["ice"]["peer_a_candidates"]),
            len(preflight["ice"]["peer_b_candidates"]),
        ],
        "bidirectional_video_frames": [
            preflight["media"]["peer_a_to_peer_b"]["receiver"]["frames"],
            preflight["media"]["peer_b_to_peer_a"]["receiver"]["frames"],
        ],
        "queue_forwarded_packets": [
            queue["a_to_b"]["forwarded_packets"],
            queue["b_to_a"]["forwarded_packets"],
        ],
        "policy_sha256": policy_hash,
    }
    return runtime, reference


def verify_previous_turn_v2() -> dict:
    root = V2_TURN_CAPTURE
    protocol_path, index_path = root / "protocol.json", root / "capture_index.json"
    if sha(protocol_path) != V2_TURN_PROTOCOL_SHA256 or sha(index_path) != V2_TURN_INDEX_SHA256:
        raise ValueError("the preserved V2 TURN/TCP checker-abort capture changed")
    protocol, index = read_json(protocol_path), read_json(index_path)
    expected = {trial["id"] for trial in protocol["trials"]}
    if len(index.get("sessions", [])) != 32 or {item["trial"] for item in index["sessions"]} != expected:
        raise ValueError("the V2 TURN/TCP failure inventory is incomplete")
    if any(item.get("status") != "failed" for item in index["sessions"]):
        raise ValueError("the V2 TURN/TCP failure statuses changed")
    for item in index["sessions"]:
        directory = root / "sessions" / item["trial"]
        manifest = core.verify_directory(directory, "native_action_session_failed")
        if sha(directory / "integrity.json") != item["integrity_manifest_sha256"]:
            raise ValueError("a V2 TURN/TCP session seal changed")
        if (directory / "summary.json").exists() or (directory / "sender_observations.json").exists():
            raise ValueError("the preserved V2 checker abort unexpectedly contains sender outcomes")
    return {
        "protocol_sha256": V2_TURN_PROTOCOL_SHA256,
        "capture_index_sha256": V2_TURN_INDEX_SHA256,
        "attempted_sessions": 32,
        "failure_class": "selected local peer-reflexive classification rejected after TURN-backed ICE connection",
        "outcome_telemetry_read": False,
        "pooled": False,
    }


def verify_previous_turn_v3() -> dict:
    root = V3_TURN_CAPTURE
    protocol_path, index_path = root / "protocol.json", root / "capture_index.json"
    if sha(protocol_path) != V3_TURN_PROTOCOL_SHA256 or sha(index_path) != V3_TURN_INDEX_SHA256:
        raise ValueError("the preserved V3 TURN/TCP capture changed")
    if sha(V3_DIAGNOSTIC) != V3_DIAGNOSTIC_SHA256:
        raise ValueError("the V3 diagnostic-only marker/queue report changed")
    protocol, index = read_json(protocol_path), read_json(index_path)
    expected = {trial["id"] for trial in protocol["trials"]}
    if len(index.get("sessions", [])) != 32 or {item["trial"] for item in index["sessions"]} != expected:
        raise ValueError("the V3 TURN/TCP failure inventory is incomplete")
    if any(item.get("status") != "failed" for item in index["sessions"]):
        raise ValueError("the V3 TURN/TCP failed-session statuses changed")
    for item in index["sessions"]:
        directory = root / "sessions" / item["trial"]
        manifest = core.verify_directory(directory, "native_action_session_failed")
        if sha(directory / "integrity.json") != item["integrity_manifest_sha256"]:
            raise ValueError("a V3 TURN/TCP session seal changed")
        if (directory / "summary.json").exists():
            raise ValueError("the failed V3 acquisition unexpectedly has a qualified session summary")
        failure = (directory / "capture_stderr.log").read_text(errors="replace")
        if "media bypassed the selected TURN relay or did not progress through the owned queue" not in failure:
            raise ValueError("the preserved V3 collector failure class changed")
    diagnostic = read_json(V3_DIAGNOSTIC)
    if diagnostic.get("outcome_telemetry_read") is not False or diagnostic.get("per_hold_cost_qoe_estimated") is not False:
        raise ValueError("the V3 diagnostic report is not outcome-blind")
    return {
        "protocol_sha256": V3_TURN_PROTOCOL_SHA256,
        "capture_index_sha256": V3_TURN_INDEX_SHA256,
        "diagnostic_sha256": V3_DIAGNOSTIC_SHA256,
        "attempted_sessions": 32,
        "failed_sessions": 32,
        "clock_valid_sessions": diagnostic["clock_diagnostic"]["held_out_coverage_passed"],
        "clock_failed_trials": diagnostic["clock_diagnostic"]["failed_trials"],
        "failure_class": "phase-snapshot guard read an unrecorded remote_candidate_type field after the registered session schedule",
        "outcome_telemetry_read": False,
        "pooled": False,
    }


def verify_previous_turn_v4() -> dict:
    root = V4_TURN_CAPTURE
    protocol_path, index_path = root / "protocol.json", root / "capture_index.json"
    gate_path = root / "clock_transport_gate.json"
    if (
        sha(protocol_path) != V4_TURN_PROTOCOL_SHA256
        or sha(index_path) != V4_TURN_INDEX_SHA256
        or sha(gate_path) != V4_TURN_GATE_SHA256
        or sha(V4_DIAGNOSTIC) != V4_DIAGNOSTIC_SHA256
    ):
        raise ValueError("the preserved V4 TURN/TCP gate-failure evidence changed")
    protocol, index, gate = read_json(protocol_path), read_json(index_path), read_json(gate_path)
    expected = {trial["id"] for trial in protocol["trials"]}
    if len(index.get("sessions", [])) != 32 or {item["trial"] for item in index["sessions"]} != expected:
        raise ValueError("the V4 TURN/TCP capture inventory is incomplete")
    if any(item.get("status") != "sealed" for item in index["sessions"]):
        raise ValueError("the V4 TURN/TCP session statuses changed")
    if gate.get("passed") is not False or gate.get("outcome_analysis_performed") is not False:
        raise ValueError("the preserved V4 gate no longer records an outcome-blind failure")
    for item in index["sessions"]:
        directory = root / "sessions" / item["trial"]
        manifest = core.verify_directory(directory, "native_action_session")
        if sha(directory / "integrity.json") != item["integrity_manifest_sha256"]:
            raise ValueError("a V4 TURN/TCP session seal changed")
        if manifest.get("stage") != "native_action_session":
            raise ValueError("the V4 sealed-session inventory changed")
    diagnostic = read_json(V4_DIAGNOSTIC)
    if diagnostic.get("outcome_telemetry_read") is not False:
        raise ValueError("the V4 diagnostic is not outcome-blind")
    return {
        "protocol_sha256": V4_TURN_PROTOCOL_SHA256,
        "capture_index_sha256": V4_TURN_INDEX_SHA256,
        "gate_sha256": V4_TURN_GATE_SHA256,
        "diagnostic_sha256": V4_DIAGNOSTIC_SHA256,
        "sealed_sessions": 32,
        "clock_qualified_sessions": 29,
        "transport_qualified_sessions": 24,
        "failure_class": "three sessions missed held-out clock coverage; eight sessions violated V4's registered zero-overflow queue rule",
        "outcome_telemetry_read": False,
        "pooled": False,
    }


def verify_previous_turn_v5() -> dict:
    root = V5_TURN_CAPTURE
    protocol_path, index_path = root / "protocol.json", root / "capture_index.json"
    gate_path = root / "clock_transport_gate.json"
    if (
        sha(protocol_path) != V5_TURN_PROTOCOL_SHA256
        or sha(index_path) != V5_TURN_INDEX_SHA256
        or sha(gate_path) != V5_TURN_GATE_SHA256
        or sha(V5_DIAGNOSTIC) != V5_DIAGNOSTIC_SHA256
    ):
        raise ValueError("the preserved V5 TURN/TCP clock-gate evidence changed")
    protocol, index, gate = read_json(protocol_path), read_json(index_path), read_json(gate_path)
    expected = {trial["id"] for trial in protocol["trials"]}
    if len(index.get("sessions", [])) != 32 or {item["trial"] for item in index["sessions"]} != expected:
        raise ValueError("the V5 TURN/TCP capture inventory is incomplete")
    if any(item.get("status") != "sealed" for item in index["sessions"]):
        raise ValueError("the V5 TURN/TCP session statuses changed")
    if (
        gate.get("passed") is not False
        or gate.get("outcome_analysis_performed") is not False
        or gate.get("qualified_clock_sessions") != 30
        or gate.get("qualified_transport_sessions") != 32
        or gate.get("failed_capture_sessions") != 0
    ):
        raise ValueError("the preserved V5 gate no longer records its outcome-blind failure")
    for item in index["sessions"]:
        directory = root / "sessions" / item["trial"]
        manifest = core.verify_directory(directory, "native_action_session")
        if sha(directory / "integrity.json") != item["integrity_manifest_sha256"]:
            raise ValueError("a V5 TURN/TCP session seal changed")
        if manifest.get("stage") != "native_action_session":
            raise ValueError("the V5 sealed-session inventory changed")
    diagnostic = read_json(V5_DIAGNOSTIC)
    failed = diagnostic.get("failed_clock_trials", [])
    if (
        diagnostic.get("outcome_telemetry_read") is not False
        or diagnostic.get("per_hold_cost_qoe_estimated") is not False
        or len(failed) != 2
        or any(row.get("failed_markers") != ["m0002"] for row in failed)
    ):
        raise ValueError("the V5 diagnostic does not preserve the outcome-blind m0002 failures")
    return {
        "protocol_sha256": V5_TURN_PROTOCOL_SHA256,
        "capture_index_sha256": V5_TURN_INDEX_SHA256,
        "gate_sha256": V5_TURN_GATE_SHA256,
        "diagnostic_sha256": V5_DIAGNOSTIC_SHA256,
        "sealed_sessions": 32,
        "clock_qualified_sessions": 30,
        "transport_qualified_sessions": 32,
        "failed_trials": [row["trial"] for row in failed],
        "failure_class": "two sessions missed held-out coverage at the initial high-phase marker m0002",
        "outcome_telemetry_read": False,
        "pooled": False,
    }


def make_trials(root: Path) -> tuple[list[dict], list[str]]:
    levels = {"level065": (1, 0.65), "level105": (3, 1.05)}
    blocks = [(seed, rep) for seed in range(8) for rep in range(2)]
    rng = random.Random(RANDOMIZATION_SEED)
    rng.shuffle(blocks)
    flips = [False] * 8 + [True] * 8
    rng.shuffle(flips)
    trials, order = [], []
    for (cluster, repetition), flip in zip(blocks, flips):
        conditions = ["level065", "level105"]
        if flip:
            conditions.reverse()
        for condition_name in conditions:
            level_index, ratio = levels[condition_name]
            trial_id = f"turntcp6-scene{cluster:02d}-rep{repetition}-r{int(ratio * 100):03d}"
            episode = {
                "id": trial_id,
                "role": "discovery",
                "scene_seed": SCENE_SEEDS[cluster],
                "schedule": core.SCHEDULE,
                "episode_timeout_s": 90,
            }
            panel = {
                "panel_abi": "native_clock_action_probe_v1",
                "stage": "discovery",
                "source_kind": "generated_canvas_native_webrtc",
                "repair_model": None,
                "models": {},
                "common_shadow_inference": True,
                "SOTA_achieved": False,
                "episode_timeout_s": 90,
                "measurement_recipe": {
                    "abi": "native_clock_action_probe_v1_measurement",
                    "action_ratios": [0.65, 1.05],
                    "hold_ms": 3000,
                    "endpoint_window_ms": list(core.HOLD_WINDOW_MS),
                    "deadline_ms": core.DEADLINE_MS,
                    "clock_abi": "native_clock_marker_exchange_v1",
                    "clock_markers_per_session": 11,
                },
                "conditions": {
                    "level065": {"controller": "explore", "behavior": "level", "level": 1},
                    "level105": {"controller": "explore", "behavior": "level", "level": 3},
                },
                "episodes": [episode],
            }
            panel_path = root / "panels" / (trial_id + ".json")
            panel_bytes = (json.dumps(panel, indent=2, sort_keys=True) + "\n").encode()
            panel_path.write_bytes(panel_bytes)
            trials.append({
                "id": trial_id,
                "condition": condition_name,
                "ratio": ratio,
                "scene_seed": SCENE_SEEDS[cluster],
                "seed_cluster": cluster,
                "repetition": repetition,
                "panel": str(panel_path.relative_to(root)),
                "panel_sha256": hashlib.sha256(panel_bytes).hexdigest(),
                "order_position": len(order),
            })
            order.append(trial_id)
    return trials, order


def prepare(root: Path, preflight_path: Path, prior_root: Path) -> dict:
    root = root.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
            raise ValueError("fresh V6 TURN/TCP action root required")
    calibration_reference, no_candidate_reference, _ = v2.verify_prior_evidence(prior_root)
    runtime, preflight_reference = runtime_provenance(preflight_path)
    prior_v2 = verify_previous_turn_v2()
    prior_v3 = verify_previous_turn_v3()
    prior_v4 = verify_previous_turn_v4()
    prior_v5 = verify_previous_turn_v5()
    root.mkdir(parents=True, exist_ok=True)
    (root / "panels").mkdir()
    trials, randomized_order = make_trials(root)
    protocol = {
        "abi": "native_clock_action_probe_v6_turn_tcp_protocol",
        "confirmatory": False,
        "calibration": {
            "session_marker_count": 11,
            "train_indices": [0, 1, 3, 4, 6, 7, 9],
            "held_out_indices": [2, 5, 8, 10],
            "alpha_bounds": [0.98, 1.02],
            "max_held_out_width_ms": 50.0,
            "held_out_timestamp_tolerance_ms": 1.0,
            "solver_tolerance_ms": 1e-7,
            "required_held_out_coverage": 1.0,
        },
        "source_hashes": source_inventory(),
        "schedule": core.SCHEDULE,
        "action_levels": {
            name: {"index": value[0], "ratio": value[1]}
            for name, value in {"level065": (1, 0.65), "level105": (3, 1.05)}.items()
        },
        "seed_clusters": 8,
        "repetitions_per_level_per_seed": 2,
        "randomization_seed": RANDOMIZATION_SEED,
        "scene_seeds": list(SCENE_SEEDS),
        "balanced_within_block_order": True,
        "randomized_order": randomized_order,
        "trials": trials,
        "analysis": {
            "unit": "generated-scene seed cluster",
            "degrees_of_freedom": 7,
            "confidence": 0.95,
            "action_contrast": "0.65 minus 1.05",
            "relay_window_ms_after_ack": list(core.HOLD_WINDOW_MS),
            "frame_deadline_ms": core.DEADLINE_MS,
            "clock_assignment": "use a per-session join only if every feasible affine map covers all four held-out markers",
            "action_validation": "every assigned sender decision must match its registered ratio and cap readback; at least one complete hold window is required in each state per session",
            "do_not_pool": [
                "V3 result or diagnostic-only report",
                "V4 capture, gate, and diagnostic-only report",
                "V5 capture, gate, and diagnostic-only report",
                "V2 TURN/TCP checker-abort sessions",
                "archived native sessions",
                "recorded-video captures",
                "simulator or synthetic-controller results",
                "no-candidate native captures",
            ],
            "fit_or_promote_controller": False,
        },
        "transport": {
            "browser_ice_transport_policy": "relay",
            "turn_uri_scheme": "turn:",
            "browser_to_turn_transport": "TCP",
            "turn_relay_transport": "UDP",
            "managed_WebRtcIPHandling": "disable_non_proxied_udp",
            "managed_policy_change": False,
            "candidate_gathering_acceptance": "Both peers complete gathering with relay-only candidates and relayProtocol=tcp; candidate errors are zero.",
            "selected_pair_acceptance": "Both pairs are nominated and succeeded, use a remote TURN relay candidate, and expose local loopback with relayProtocol=tcp; the local candidate may be relay or peer-reflexive because the registered queue rewrites the remote relay endpoint.",
            "media_acceptance": "Each phase must show more than 10 encoded and decoded frames and a finite mean encode time; every phase snapshot must retain the loopback remote address and relay candidate type.",
            "queue_acceptance": "Each direction must forward at least 100 packets from the matching TURN allocation source port, with no unexpected sources or send errors. Event replay must exactly match offered, dropped, served, and forwarded packet and wire-byte totals in the ledger. Queue overflow drops are registered delivery outcomes. The capacity integral must be valid and byte conservation error no greater than 1e-6 bytes.",
            "listener_ip": "127.0.0.1",
            "relay_ip": "127.0.0.1",
            "allowed_peer_ip": "127.0.0.1",
            "queue_and_propagation_mechanism_unchanged": True,
        },
        "runtime": runtime,
        "preflight_reference": preflight_reference,
        "clock_calibration_reference": calibration_reference,
        "prior_no_candidate_action_capture_reference": no_candidate_reference,
        "prior_turn_v2_checker_abort_reference": prior_v2,
        "prior_turn_v3_failed_capture_reference": prior_v3,
        "prior_turn_v4_gate_failure_reference": prior_v4,
        "prior_turn_v5_gate_failure_reference": prior_v5,
        "storage": {
            "raw_capture_root": str(root),
            "registered_protocol": str(REGISTERED_PROTOCOL.relative_to(REPO)),
            "analysis_output": "reports/native-clock-action-turntcp-v6-analysis.json",
            "raw_data_outside_git": True,
        },
    }
    shutil.copytree(Path(prior_root) / "clock-calibration", root / "clock-calibration")
    shutil.copy2(Path(prior_root) / "clock_report.json", root / "clock_report.json")
    digest = v2.write_registered_protocol(root, protocol)
    return {
        "root": str(root),
        "registered_protocol": str(REGISTERED_PROTOCOL),
        "protocol_sha256": digest,
        "planned_sessions": len(trials),
        "scene_seeds": list(SCENE_SEEDS),
        "randomization_seed": RANDOMIZATION_SEED,
        "preflight_sha256": preflight_reference["sha256"],
        "prior_v3_diagnostic_sha256": prior_v3["diagnostic_sha256"],
        "prior_v4_diagnostic_sha256": prior_v4["diagnostic_sha256"],
        "prior_v5_diagnostic_sha256": prior_v5["diagnostic_sha256"],
        "source_hashes": protocol["source_hashes"],
    }


def load_registered(root: Path) -> dict:
    root = root.expanduser().resolve()
    protocol_path = root / "protocol.json"
    protocol = read_json(protocol_path)
    digest = sha(protocol_path)
    if protocol.get("abi") != "native_clock_action_probe_v6_turn_tcp_protocol":
        raise ValueError("registered V6 TURN/TCP protocol required")
    if digest != (root / "protocol.sha256").read_text().split()[0]:
        raise ValueError("V6 protocol checksum changed")
    if not REGISTERED_PROTOCOL.is_file() or sha(REGISTERED_PROTOCOL) != digest:
        raise ValueError("versioned V6 protocol differs from capture registration")
    if root != Path(protocol["storage"]["raw_capture_root"]).resolve():
        raise ValueError("frozen V6 raw capture path changed")
    if protocol.get("scene_seeds") != list(SCENE_SEEDS) or protocol.get("randomization_seed") != RANDOMIZATION_SEED:
        raise ValueError("V6 scene or assignment-order seed changed")
    calibration = protocol.get("calibration", {})
    if (
        calibration.get("session_marker_count") != 11
        or calibration.get("train_indices") != [0, 1, 3, 4, 6, 7, 9]
        or calibration.get("held_out_indices") != [2, 5, 8, 10]
    ):
        raise ValueError("V6 marker design or held-out assignment changed")
    if len(protocol.get("trials", [])) != 32 or len(set(protocol["randomized_order"])) != 32:
        raise ValueError("V6 must retain its complete 32-session panel")
    core.verify_sources(protocol)
    if sha(root / "clock_report.json") != protocol["clock_calibration_reference"]["report_sha256"]:
        raise ValueError("copied qualified clock report checksum changed")
    return protocol


def transport_checks(root: Path, trial_id: str, expected_turn_url: str) -> dict:
    directory = root / "sessions" / trial_id
    ice = read_json(directory / "ice_evidence.json")
    transport = read_json(directory / "transport_evidence.json")
    runtime = read_json(directory / "turn_runtime.json")
    policy = read_json(directory / "policy_check.json")
    queue = read_json(directory / "queue_evidence.json")
    candidates = ice.get("candidates", {})
    only_turn_tcp = all(
        isinstance(candidates.get(peer), list) and candidates[peer]
        and all(candidate.get("type") == "relay"
                and candidate.get("protocol") == "udp"
                and candidate.get("relayProtocol") == "tcp"
                and candidate.get("address") == "127.0.0.1"
                and candidate.get("url") == expected_turn_url
                for candidate in candidates[peer])
        for peer in ("a", "b")
    )

    def pair_ok(pair: dict) -> bool:
        local, remote, stats = pair.get("local", {}), pair.get("remote", {}), pair.get("pair", {})
        return (
            local.get("candidateType") in ("relay", "prflx")
            and local.get("relayProtocol") == "tcp"
            and local.get("address") == "127.0.0.1"
            and remote.get("candidateType") == "relay"
            and remote.get("address") == "127.0.0.1"
            and stats.get("state") == "succeeded"
            and stats.get("nominated") is True
            and stats.get("bytesSent", 0) > 0
            and stats.get("bytesReceived", 0) > 0
        )

    relay = queue.get("relay", {})
    link_checks = {}
    with gzip.open(directory / "events.jsonl.gz", "rt") as stream:
        transport_events = [json.loads(line) for line in stream if line.strip()]
    for direction, candidate_peer in (("a_to_b", "a"), ("b_to_a", "b")):
        link = relay.get(direction, {})
        direction_events = [event for event in transport_events if event.get("direction") == direction]
        offers = [event for event in direction_events if event.get("kind") == "offer"]
        drops = [event for event in offers if event.get("dropped") is True]
        services = [event for event in direction_events if event.get("kind") == "service"]
        forwards = [event for event in direction_events if event.get("kind") == "forward"]
        offered_event_bytes = sum(event.get("wire_bytes", 0) for event in offers)
        dropped_event_bytes = sum(event.get("wire_bytes", 0) for event in drops)
        served_event_bytes = sum(event.get("service_wire_bytes", 0) for event in services)
        forwarded_event_bytes = sum(event.get("wire_bytes", 0) for event in forwards)
        expected_port = candidates.get(candidate_peer, [{}])[0].get("port")
        expected_sources = queue.get("accepted_source_ports", {}).get(direction)
        unexpected = queue.get("unexpected_sources", {}).get(direction)
        ledger_replay_ok = (
            len(offers) == link.get("offered_packets")
            and abs(offered_event_bytes - link.get("offered_wire_bytes", float("inf"))) <= 1e-6
            and abs(dropped_event_bytes - link.get("dropped_wire_bytes", float("inf"))) <= 1e-6
            and len(drops) == link.get("overflow_packets")
            and abs(served_event_bytes - link.get("served_wire_bytes", float("inf"))) <= 1e-6
            and len(forwards) == link.get("served_packets")
            and abs(forwarded_event_bytes - link.get("forwarded_wire_bytes", float("inf"))) <= 1e-6
            and len(forwards) == link.get("forwarded_packets")
        )
        link_checks[direction] = (
            queue.get("abi") == "native_action_turn_tcp_v6_queue_evidence_v1"
            and expected_sources == expected_port
            and unexpected == 0
            and link.get("offered_wire_bytes", 0) > 0
            and link.get("forwarded_packets", 0) >= 100
            and link.get("send_errors") == 0
            and link.get("queue_limit_wire_bytes", 0) > 0
            and link.get("max_queue_wire_bytes", float("inf")) <= link.get("queue_limit_wire_bytes", 0) + 1e-6
            and link.get("queued_wire_bytes") == 0
            and link.get("capacity_integral_upper_bound_ok") is True
            and abs(link.get("conservation_error_bytes", float("inf"))) <= 1e-6
            and ledger_replay_ok
        )
    qualified = {
        "ice_complete": ice.get("gathering_state_a") == "complete" and ice.get("gathering_state_b") == "complete",
        "candidate_url_is_loopback_turn_tcp": expected_turn_url.startswith("turn:127.0.0.1:")
        and expected_turn_url.endswith("?transport=tcp") and ice.get("turn_url") == expected_turn_url
        and transport.get("turn_url") == expected_turn_url and runtime.get("turn_url") == expected_turn_url
        and runtime.get("control_transport") == "TCP",
        "only_turn_tcp_candidates": only_turn_tcp,
        "no_ice_candidate_errors": not ice.get("candidate_errors", {}).get("a") and not ice.get("candidate_errors", {}).get("b"),
        "nominated_turn_backed_pairs": pair_ok(transport.get("selected_a", {})) and pair_ok(transport.get("selected_b", {})),
        "both_connections_connected": transport.get("connection_a") == "connected" and transport.get("connection_b") == "connected",
        "bidirectional_queue_acceptance": all(link_checks.values()),
        "policy_unchanged": policy.get("unchanged") is True and policy.get("modified_by_runner") is False,
        "policy_value_preserved": policy.get("WebRtcIPHandling_before") == "disable_non_proxied_udp" and policy.get("WebRtcIPHandling_after") == "disable_non_proxied_udp",
        "turn_runtime_loopback": runtime.get("control_transport") == "TCP" and runtime.get("relay_transport") == "UDP"
        and runtime.get("server_config", {}).get("loopback_peers_only") is True,
    }
    return {
        "passed": all(qualified.values()),
        "checks": qualified,
        "queue_link_checks": link_checks,
        "candidate_count_a": len(candidates.get("a", [])),
        "candidate_count_b": len(candidates.get("b", [])),
        "candidate_errors_a": len(ice.get("candidate_errors", {}).get("a", [])),
        "candidate_errors_b": len(ice.get("candidate_errors", {}).get("b", [])),
    }


v2.load_registered = load_registered
v2.runtime_provenance = runtime_provenance
v2._transport_checks = transport_checks


def clock_gate(root: Path) -> dict:
    root = root.expanduser().resolve()
    protocol = load_registered(root)
    _, index = core.check_capture_integrity(root)
    results = []
    for item in index["sessions"]:
        result = {
            "trial": item["trial"],
            "capture_status": item["status"],
            "clock_passed": False,
            "transport_passed": False,
            "outcome_data_read": False,
        }
        if item["status"] != "sealed":
            result["reason"] = "session capture failed; excluded from treatment outcomes"
            results.append(result)
            continue
        directory = root / "sessions" / item["trial"]
        ice = read_json(directory / "ice_evidence.json")
        urls = {candidate.get("url") for peer in ("a", "b") for candidate in ice.get("candidates", {}).get(peer, [])}
        url = next(iter(urls)) if len(urls) == 1 else ""
        transport = transport_checks(root, item["trial"], url)
        markers = core.load_marker_pair(
            directory / "clock_markers_browser.json",
            directory / "clock_markers_node.json",
        )
        expected_ids = [f"m{number:04d}" for number in range(1, 12)]
        expected_endpoints = [
            "/clock-marker", "/clock-marker", "/phase", "/clock-marker",
            "/clock-marker", "/phase", "/clock-marker", "/clock-marker",
            "/phase", "/clock-marker", "/clock-marker",
        ]
        order_ok = (
            len(markers) == 11
            and [marker.get("marker_id") for marker in markers] == expected_ids
            and [marker.get("endpoint") for marker in markers] == expected_endpoints
            and [marker.get("phase") for marker in markers]
            == [None, None, "high", None, None, "collapse", None, None,
                "recovery", None, None]
        )
        clock = core.validate_markers(markers, [0, 1, 3, 4, 6, 7, 9], [2, 5, 8, 10]) if order_ok else {
            "passed": False,
            "reason": "eleven-marker order/count mismatch",
        }
        clock_ok = (
            order_ok
            and clock.get("passed") is True
            and clock.get("max_held_out_width_ms", float("inf")) <= core.MAX_CLOCK_WIDTH_MS
        )
        result.update({
            "transport_passed": transport["passed"],
            "transport": transport,
            "clock_passed": clock_ok,
            "clock": {key: value for key, value in clock.items() if key != "checks"},
            "marker_count": len(markers),
            "outcome_data_read": False,
        })
        if not clock_ok or not transport["passed"]:
            result["reason"] = "actual-session transport or clock acceptance failed"
        results.append(result)
    passed = (
        len(results) == len(protocol["trials"])
        and all(
            item["capture_status"] == "sealed"
            and item["clock_passed"]
            and item["transport_passed"]
            for item in results
        )
    )
    gate = {
        "abi": "native_turn_clock_action_v6_gate",
        "protocol_sha256": sha(root / "protocol.json"),
        "capture_index_sha256": sha(root / "capture_index.json"),
        "passed": passed,
        "planned_sessions": len(protocol["trials"]),
        "qualified_clock_sessions": sum(item["clock_passed"] for item in results),
        "qualified_transport_sessions": sum(item["transport_passed"] for item in results),
        "failed_capture_sessions": sum(item["capture_status"] != "sealed" for item in results),
        "outcome_analysis_performed": False,
        "sessions": results,
    }
    gate_path = root / "clock_transport_gate.json"
    write_json(gate_path, gate)
    return {
        "passed": passed,
        "planned_sessions": len(protocol["trials"]),
        "qualified_clock_sessions": gate["qualified_clock_sessions"],
        "qualified_transport_sessions": gate["qualified_transport_sessions"],
        "failed_capture_sessions": gate["failed_capture_sessions"],
        "gate_sha256": sha(gate_path),
        "outcome_analysis_performed": False,
    }


def analyze(root: Path, output: Path) -> dict:
    root, output = root.expanduser().resolve(), output.expanduser().resolve()
    protocol = load_registered(root)
    gate_result = clock_gate(root)
    _, index = core.check_capture_integrity(root)
    gate_path = root / "clock_transport_gate.json"
    gate = read_json(gate_path)
    if (
        not gate.get("passed")
        or gate.get("protocol_sha256") != sha(root / "protocol.json")
        or gate.get("capture_index_sha256") != sha(root / "capture_index.json")
        or len(index["sessions"]) != len(protocol["trials"])
        or any(item["status"] != "sealed" for item in index["sessions"])
    ):
        raise ValueError("all sessions must pass checksum, ledger-replayed queue-backed TURN, and actual-run clock gates before outcomes are read")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("fresh V6 action-analysis report path required")
    unpublished = root / "unpublished-v6-core-analysis.json"
    core.analyze(root, unpublished)
    report = read_json(unpublished)
    report["abi"] = "native_turn_clock_action_probe_v6_turn_tcp_report"
    report["transport"] = protocol["transport"]
    report["runtime"] = protocol["runtime"]
    report["preflight_reference"] = protocol["preflight_reference"]
    report["clock_calibration_reference"] = protocol["clock_calibration_reference"]
    report["prior_turn_v2_checker_abort_reference"] = protocol["prior_turn_v2_checker_abort_reference"]
    report["prior_turn_v3_failed_capture_reference"] = protocol["prior_turn_v3_failed_capture_reference"]
    report["prior_turn_v4_gate_failure_reference"] = protocol["prior_turn_v4_gate_failure_reference"]
    report["prior_turn_v5_gate_failure_reference"] = protocol["prior_turn_v5_gate_failure_reference"]
    report["actual_run_clock_transport_gate_sha256"] = sha(gate_path)
    report["outcome_data_read_after_gate"] = True
    report["controller_fitted_or_promoted"] = False
    write_json(output, report)
    return {
        "report": str(output),
        "report_sha256": sha(output),
        "sessions": report["sealed_sessions"],
        "actual_session_clocks_all_pass": report["session_clock_validations_all_pass"],
        "clock_gate_sha256": gate_result["gate_sha256"],
        "controller_fitted_or_promoted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--root", type=Path, default=CAPTURE_ROOT)
    prepare_parser.add_argument("--preflight", type=Path, default=PREFLIGHT_PATH)
    prepare_parser.add_argument("--prior-root", type=Path, default=DEFAULT_CALIBRATION)
    for name in ("capture", "integrity", "clock-gate"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, default=CAPTURE_ROOT)
    analyze_parser = commands.add_parser("analyze")
    analyze_parser.add_argument("--root", type=Path, default=CAPTURE_ROOT)
    analyze_parser.add_argument("--out", type=Path, default=REPO / "reports/native-clock-action-turntcp-v6-analysis.json")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.root, args.preflight, args.prior_root)
    elif args.command == "capture":
        result = v2.capture(args.root)
    elif args.command == "integrity":
        result = v2.integrity(args.root)
    elif args.command == "clock-gate":
        result = clock_gate(args.root)
    elif args.command == "analyze":
        result = analyze(args.root, args.out)
    else:
        raise RuntimeError("unsupported command")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
