"""Freshly register and run the TURN/TCP native 0.65/1.05 action replication."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import shutil
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
V2_PATH = REPO / "tools/native_turn_clock_action_probe_v2.py"
RECORDER = REPO / "benchmarks/native_rtc/clock_action_turn_tcp_episode_v2.mjs"
PLAN = REPO / "docs/NATIVE_CLOCK_ACTION_TURN_TCP_V3_PLAN.md"
REGISTERED_PROTOCOL = REPO / "configs/native_clock_action_probe_turn_tcp_v3.json"
V3_CAPTURE_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v3")
PREVIOUS_TURN_CAPTURE = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v2")
PREVIOUS_TURN_PROTOCOL_SHA256 = "31b220e8904be3e900ebe6c21a5a0f4550e56db927fe223fee95a3a041f10beb"
PREVIOUS_TURN_INDEX_SHA256 = "f54a6cd6a5d042bbeb14eb7b3e6e51c6f84fdeaa65e6d912be18e68aee830414"
RANDOMIZATION_SEED = 20261014
SCENE_SEEDS = tuple(range(2000, 2008))


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


_v2_spec = importlib.util.spec_from_file_location("native_turn_clock_action_probe_v2_core", V2_PATH)
if _v2_spec is None or _v2_spec.loader is None:
    raise RuntimeError("cannot load the frozen TURN/TCP capture and analysis helpers")
v2 = importlib.util.module_from_spec(_v2_spec)
_v2_spec.loader.exec_module(v2)
v2.RECORDER = RECORDER
v2.PLAN = PLAN
v2.REGISTERED_PROTOCOL = REGISTERED_PROTOCOL
v2.core.RECORDER = RECORDER
_v2_source_inventory = v2.source_inventory


def source_inventory() -> dict[str, str]:
    result = _v2_source_inventory()
    result["turn_action_v3_wrapper"] = sha(Path(__file__).resolve())
    result["turn_v2_plan_document"] = sha(REPO / "docs/NATIVE_CLOCK_ACTION_TURN_TCP_V2_PLAN.md")
    return result


v2.core.source_inventory = source_inventory


def verify_previous_turn_capture() -> dict:
    root = PREVIOUS_TURN_CAPTURE
    protocol_path = root / "protocol.json"
    index_path = root / "capture_index.json"
    if sha(protocol_path) != PREVIOUS_TURN_PROTOCOL_SHA256:
        raise ValueError("the preserved TURN/TCP checker-abort protocol changed")
    if (root / "protocol.sha256").read_text().split()[0] != PREVIOUS_TURN_PROTOCOL_SHA256:
        raise ValueError("the preserved TURN/TCP checker-abort protocol receipt changed")
    if sha(index_path) != PREVIOUS_TURN_INDEX_SHA256:
        raise ValueError("the preserved TURN/TCP checker-abort inventory changed")
    protocol, index = read_json(protocol_path), read_json(index_path)
    trial_ids = {trial["id"] for trial in protocol["trials"]}
    if len(index.get("sessions", [])) != 32 or {item["trial"] for item in index["sessions"]} != trial_ids:
        raise ValueError("the preceding checker-abort inventory is incomplete")
    if any(item.get("status") != "failed" for item in index["sessions"]):
        raise ValueError("the preceding checker-abort run contains a nonfailed session")
    for item in index["sessions"]:
        directory = root / "sessions" / item["trial"]
        manifest = v2.core.verify_directory(directory, "native_action_session_failed")
        if sha(directory / "integrity.json") != item["integrity_manifest_sha256"]:
            raise ValueError("the preceding checker-abort session checksum changed")
        if (directory / "summary.json").exists() or (directory / "sender_observations.json").exists():
            raise ValueError("the preceding checker-abort run unexpectedly contains sender outcome artifacts")
        failure = (directory / "capture_stderr.log").read_text(errors="replace")
        if "selected ICE pair did not use TURN/TCP relay candidates" not in failure:
            raise ValueError("the preceding TURN/TCP checker-abort failure class changed")
    return {
        "root": str(root),
        "protocol_sha256": sha(protocol_path),
        "capture_index_sha256": sha(index_path),
        "attempted_sessions": 32,
        "sessions_with_checksum_verified_ICE_evidence": 32,
        "failure_class": "validation aborted on selected local prflx classification after relay-only candidate gathering and connected state",
        "sender_action_assignments": 0,
        "sender_observations_or_session_summaries": 0,
        "treatment_outcomes_read": False,
        "pooled": False,
    }


def _make_trials(root: Path) -> tuple[list[dict], list[str]]:
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
            trial_id = f"turntcp3-scene{cluster:02d}-rep{repetition}-r{int(ratio*100):03d}"
            episode = {
                "id": trial_id,
                "role": "discovery",
                "scene_seed": SCENE_SEEDS[cluster],
                "schedule": v2.core.SCHEDULE,
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
                    "endpoint_window_ms": list(v2.core.HOLD_WINDOW_MS),
                    "deadline_ms": v2.core.DEADLINE_MS,
                    "clock_abi": "native_clock_marker_exchange_v1",
                },
                "conditions": {
                    "level065": {"controller": "explore", "behavior": "level", "level": 1},
                    "level105": {"controller": "explore", "behavior": "level", "level": 3},
                },
                "episodes": [episode],
            }
            panel_path = root / "panels" / f"{trial_id}.json"
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
        raise ValueError("fresh V3 TURN/TCP action root required")
    calibration_reference, no_candidate_reference, _ = v2.verify_prior_evidence(prior_root)
    runtime, preflight_reference = v2.runtime_provenance(preflight_path)
    checker_failure = verify_previous_turn_capture()
    root.mkdir(parents=True, exist_ok=True)
    (root / "panels").mkdir()
    trials, randomized_order = _make_trials(root)
    protocol = {
        "abi": "native_clock_action_probe_v3_turn_tcp_protocol",
        "confirmatory": False,
        "calibration": {
            "marker_count": 120,
            "interval_ms": 500,
            "train_indices": "even",
            "held_out_indices": "odd",
            "alpha_bounds": [0.98, 1.02],
            "max_held_out_width_ms": 50.0,
            "held_out_timestamp_tolerance_ms": 1.0,
            "solver_tolerance_ms": 1e-7,
            "required_held_out_coverage": 1.0,
        },
        "source_hashes": source_inventory(),
        "schedule": v2.core.SCHEDULE,
        "action_levels": {name: {"index": value[0], "ratio": value[1]} for name, value in {"level065": (1, 0.65), "level105": (3, 1.05)}.items()},
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
            "relay_window_ms_after_ack": list(v2.core.HOLD_WINDOW_MS),
            "frame_deadline_ms": v2.core.DEADLINE_MS,
            "clock_assignment": "guaranteed only if all feasible affine maps agree",
            "do_not_pool": ["V3 result", "archived native sessions", "recorded-video captures", "simulator or synthetic-controller results", "prior TURN/TCP checker-abort sessions"],
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
            "selected_pair_acceptance": "Both pairs are nominated and succeeded, use a remote TURN relay candidate, and expose local loopback candidate address with relayProtocol=tcp. The local candidate type may be relay or peer-reflexive because the owned Node queue rewrites the remote relay candidate to its UDP socket.",
            "media_acceptance": "The capture collector additionally requires sender encoding, receiver decoding, selected remote candidate type relay, and at least 100 forwarded A-to-B queue packets before it seals a session as complete.",
            "listener_ip": "127.0.0.1",
            "relay_ip": "127.0.0.1",
            "allowed_peer_ip": "127.0.0.1",
            "queue_and_propagation_mechanism_unchanged": True,
        },
        "runtime": runtime,
        "preflight_reference": preflight_reference,
        "clock_calibration_reference": calibration_reference,
        "prior_no_candidate_action_capture_reference": no_candidate_reference,
        "prior_turn_checker_abort_reference": checker_failure,
        "storage": {
            "raw_capture_root": str(root),
            "registered_protocol": str(REGISTERED_PROTOCOL.relative_to(REPO)),
            "analysis_output": "reports/native-clock-action-turntcp-v3-analysis.json",
            "raw_data_outside_git": True,
        },
    }
    shutil.copytree(Path(prior_root) / "clock-calibration", root / "clock-calibration")
    shutil.copy2(Path(prior_root) / "clock_report.json", root / "clock_report.json")
    encoded = json.dumps(protocol, indent=2, sort_keys=True, allow_nan=False) + "\n"
    data = encoded.encode()
    (root / "protocol.json").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (root / "protocol.sha256").write_text(digest + "  protocol.json\n")
    if REGISTERED_PROTOCOL.exists():
        raise ValueError("registered V3 protocol exists; refusing to replace it")
    REGISTERED_PROTOCOL.write_bytes(data)
    return {"root": str(root), "registered_protocol": str(REGISTERED_PROTOCOL),
            "protocol_sha256": digest, "planned_sessions": len(trials),
            "scene_seeds": list(SCENE_SEEDS), "randomization_seed": RANDOMIZATION_SEED,
            "preflight_sha256": preflight_reference["sha256"],
            "previous_checker_abort_sha256": checker_failure["capture_index_sha256"],
            "source_hashes": protocol["source_hashes"]}


def load_registered(root: Path) -> dict:
    root = root.expanduser().resolve()
    protocol_path = root / "protocol.json"
    protocol = read_json(protocol_path)
    digest = sha(protocol_path)
    if protocol.get("abi") != "native_clock_action_probe_v3_turn_tcp_protocol":
        raise ValueError("registered TURN/TCP V3 protocol required")
    if digest != (root / "protocol.sha256").read_text().split()[0]:
        raise ValueError("V3 protocol checksum changed")
    if not REGISTERED_PROTOCOL.is_file() or sha(REGISTERED_PROTOCOL) != digest:
        raise ValueError("versioned V3 protocol differs from the captured protocol")
    if root != Path(protocol["storage"]["raw_capture_root"]).resolve():
        raise ValueError("frozen V3 raw capture path changed")
    if protocol.get("scene_seeds") != list(SCENE_SEEDS) or protocol.get("randomization_seed") != RANDOMIZATION_SEED:
        raise ValueError("V3 scene seeds or assignment-order seed changed")
    if len(protocol.get("trials", [])) != 32 or len(set(protocol["randomized_order"])) != 32:
        raise ValueError("V3 must retain its complete 32-session panel")
    v2.core.verify_sources(protocol)
    if sha(root / "clock_report.json") != protocol["clock_calibration_reference"]["report_sha256"]:
        raise ValueError("copied qualified clock report checksum changed")
    return protocol


v2.load_registered = load_registered


def transport_checks_v3(root: Path, trial_id: str, expected_turn_url: str) -> dict:
    directory = root / "sessions" / trial_id
    ice = read_json(directory / "ice_evidence.json")
    transport = read_json(directory / "transport_evidence.json")
    runtime = read_json(directory / "turn_runtime.json")
    policy = read_json(directory / "policy_check.json")
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
        "policy_unchanged": policy.get("unchanged") is True and policy.get("modified_by_runner") is False,
        "policy_value_preserved": policy.get("WebRtcIPHandling_before") == "disable_non_proxied_udp" and policy.get("WebRtcIPHandling_after") == "disable_non_proxied_udp",
        "turn_runtime_loopback": runtime.get("control_transport") == "TCP" and runtime.get("server_config", {}).get("loopback_peers_only") is True,
    }
    return {"passed": all(qualified.values()), "checks": qualified,
            "candidate_count_a": len(candidates.get("a", [])),
            "candidate_count_b": len(candidates.get("b", [])),
            "candidate_errors_a": len(ice.get("candidate_errors", {}).get("a", [])),
            "candidate_errors_b": len(ice.get("candidate_errors", {}).get("b", []))}


v2._transport_checks = transport_checks_v3


def clock_gate(root: Path) -> dict:
    root = root.expanduser().resolve()
    result = v2.clock_gate(root)
    gate_path = root / "clock_transport_gate.json"
    gate = read_json(gate_path)
    gate["abi"] = "native_turn_clock_action_v3_gate"
    gate["selected_pair_acceptance"] = "TURN relay-only gathering; nominated pair; remote relay candidate; local loopback relay or peer-reflexive candidate with relayProtocol=tcp; completed queue and decoded-media acceptance from the sealed collector."
    write_json(gate_path, gate)
    result["gate_sha256"] = sha(gate_path)
    result["selected_pair_acceptance"] = gate["selected_pair_acceptance"]
    return result


def analyze(root: Path, output: Path) -> dict:
    result = v2.analyze(root, output)
    report = read_json(output)
    report["abi"] = "native_turn_clock_action_probe_v3_turn_tcp_report"
    report["prior_turn_checker_abort_reference"] = read_json(Path(root) / "protocol.json")["prior_turn_checker_abort_reference"]
    report["prior_no_candidate_action_capture_reference"] = read_json(Path(root) / "protocol.json")["prior_no_candidate_action_capture_reference"]
    report["outcome_data_read_after_actual_run_clock_transport_gate"] = True
    report["controller_fitted_or_promoted"] = False
    write_json(output, report)
    result["report_sha256"] = sha(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--root", type=Path, default=V3_CAPTURE_ROOT)
    p.add_argument("--preflight", type=Path, default=Path("/home/agent/.cache/networkrlcd/native-turn-tcp-preflight-v1-attempt2.json"))
    p.add_argument("--prior-root", type=Path, default=Path("/home/agent/.cache/networkrlcd/native-clock-action-probe-v1-final3"))
    p = commands.add_parser("capture")
    p.add_argument("--root", type=Path, default=V3_CAPTURE_ROOT)
    p = commands.add_parser("integrity")
    p.add_argument("--root", type=Path, default=V3_CAPTURE_ROOT)
    p = commands.add_parser("clock-gate")
    p.add_argument("--root", type=Path, default=V3_CAPTURE_ROOT)
    p = commands.add_parser("analyze")
    p.add_argument("--root", type=Path, default=V3_CAPTURE_ROOT)
    p.add_argument("--out", type=Path, default=REPO / "reports/native-clock-action-turntcp-v3-analysis.json")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.root, args.preflight, args.prior_root)
    elif args.command == "capture":
        result = v2.capture(args.root)
    elif args.command == "integrity":
        result = v2.integrity(args.root)
    elif args.command == "clock-gate":
        result = clock_gate(args.root)
    else:
        result = analyze(args.root, args.out)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
