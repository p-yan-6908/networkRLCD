"""Run the frozen 0.65/1.05 clock-action probe over local TURN/TCP."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CORE_PATH = REPO / "tools/native_clock_action_probe.py"
RECORDER = REPO / "benchmarks/native_rtc/clock_action_turn_tcp_episode_v1.mjs"
PREFLIGHT_SCRIPT = REPO / "tools/native_turn_media_preflight.mjs"
PLAN = REPO / "docs/NATIVE_CLOCK_ACTION_TURN_TCP_V2_PLAN.md"
REGISTERED_PROTOCOL = REPO / "configs/native_clock_action_probe_turn_tcp_v2.json"
DEFAULT_CALIBRATION = Path("/home/agent/.cache/networkrlcd/native-clock-action-probe-v1-final3")
DEFAULT_PRIOR = DEFAULT_CALIBRATION
PREFLIGHT_SHA256 = "b34ffed02189b4865268c37d701a75252ce2fc19ec5210cb9882bf7cc2d71aaa"
CALIBRATION_PROTOCOL_SHA256 = "9c09468dda2d6126dcb551fe14762c7d64de722c2b03d04430e657ad8b0a3f1f"
CALIBRATION_REPORT_SHA256 = "27946a8b2a312ab30ddbf6dbfefadc419f1e010cd32fe66f7f491fec09711dbf"
CALIBRATION_INTEGRITY_SHA256 = "e103234d399a6d1b85d461ec8b908ef8bdec141204a76949fc276a057a6bb7ab"
PRIOR_INDEX_SHA256 = "f844c2500df1de885466fcef8bef69c300ce99ef9b36b7eac09cf6c397778f1b"
POLICY_PATH = Path("/etc/chromium/policies/managed/misc.json")
CHROMIUM_PATH = Path("/usr/bin/chromium")


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


_core_spec = importlib.util.spec_from_file_location("native_clock_action_probe_core", CORE_PATH)
if _core_spec is None or _core_spec.loader is None:
    raise RuntimeError("cannot load frozen clock/action analysis implementation")
core = importlib.util.module_from_spec(_core_spec)
_core_spec.loader.exec_module(core)
core.RECORDER = RECORDER
_base_source_inventory = core.source_inventory


def source_inventory() -> dict[str, str]:
    result = _base_source_inventory()
    result["turn_media_preflight"] = sha(PREFLIGHT_SCRIPT)
    result["turn_action_wrapper"] = sha(Path(__file__).resolve())
    result["turn_action_plan"] = sha(PLAN)
    return result


core.source_inventory = source_inventory


def verify_prior_evidence(root: Path) -> tuple[dict, dict, dict]:
    root = root.expanduser().resolve()
    protocol_path = root / "protocol.json"
    report_path = root / "clock_report.json"
    calibration_dir = root / "clock-calibration"
    if sha(protocol_path) != CALIBRATION_PROTOCOL_SHA256:
        raise ValueError("the qualified clock calibration protocol checksum changed")
    if sha(report_path) != CALIBRATION_REPORT_SHA256:
        raise ValueError("the qualified clock calibration report checksum changed")
    if sha(calibration_dir / "integrity.json") != CALIBRATION_INTEGRITY_SHA256:
        raise ValueError("the qualified calibration inventory checksum changed")
    calibration_manifest = core.verify_directory(calibration_dir, "clock_calibration")
    report = read_json(report_path)
    if not report.get("passed") or report.get("coverage") != 1.0 or report.get("held_out_count") != 60:
        raise ValueError("the registered clock alignment did not pass its held-out qualification")
    if report.get("protocol_sha256") != CALIBRATION_PROTOCOL_SHA256:
        raise ValueError("clock report does not reference the qualified calibration protocol")

    index_path = root / "capture_index.json"
    if sha(index_path) != PRIOR_INDEX_SHA256:
        raise ValueError("the preserved no-candidate action-session index changed")
    prior_index = read_json(index_path)
    prior_protocol = read_json(protocol_path)
    expected_ids = {trial["id"] for trial in prior_protocol["trials"]}
    if len(prior_index.get("sessions", [])) != 32 or {s["trial"] for s in prior_index["sessions"]} != expected_ids:
        raise ValueError("the prior 32-session transport-failure inventory is incomplete")
    if any(session.get("status") != "failed" for session in prior_index["sessions"]):
        raise ValueError("the preserved pre-TURN action capture is not the expected failed ICE capture")
    for session in prior_index["sessions"]:
        directory = root / "sessions" / session["trial"]
        manifest = core.verify_directory(directory, "native_action_session_failed")
        if sha(directory / "integrity.json") != session["integrity_manifest_sha256"]:
            raise ValueError("a preserved no-candidate session manifest checksum changed")
    prior_reference = {
        "root": str(root),
        "capture_index_sha256": sha(index_path),
        "protocol_sha256": sha(protocol_path),
        "attempted_sessions": len(prior_index["sessions"]),
        "failed_sessions": 32,
        "failure_class": "managed WebRtcIPHandling disabled non-proxied UDP; no ICE candidates; no treatment outcomes",
        "outcomes_read": False,
        "pooled": False,
    }
    calibration_reference = {
        "root": str(root),
        "protocol_sha256": sha(protocol_path),
        "report_sha256": sha(report_path),
        "integrity_manifest_sha256": sha(calibration_dir / "integrity.json"),
        "marker_count": report["marker_count"],
        "held_out_covered": report["covered_count"],
        "coverage": report["coverage"],
        "alpha_feasible": report["alpha_feasible"],
        "max_held_out_width_ms": report["max_held_out_width_ms"],
        "qualified": True,
    }
    return calibration_reference, prior_reference, calibration_manifest


def runtime_provenance(preflight_path: Path) -> tuple[dict, dict]:
    preflight_path = preflight_path.expanduser().resolve()
    preflight_hash = sha(preflight_path)
    if preflight_hash != PREFLIGHT_SHA256:
        raise ValueError("the successful TURN/TCP preflight checksum changed")
    preflight = read_json(preflight_path)
    if preflight.get("abi") != "native_turn_tcp_media_preflight_v1" or not preflight.get("passed"):
        raise ValueError("TURN/TCP ICE and bidirectional media preflight did not pass")
    if not all(preflight.get("acceptance", {}).values()):
        raise ValueError("TURN/TCP preflight acceptance evidence is incomplete")
    source_hash = sha(PREFLIGHT_SCRIPT)
    if preflight.get("source_sha256") != source_hash:
        raise ValueError("the TURN/TCP preflight source differs from its recorded run")
    if preflight.get("managed_policy", {}).get("WebRtcIPHandling_before") != "disable_non_proxied_udp":
        raise ValueError("preflight did not run with the registered managed Chromium policy")
    if not preflight.get("managed_policy", {}).get("unchanged"):
        raise ValueError("managed Chromium policy changed during preflight")

    turn = preflight["turn"]
    binary = Path("/home/agent/.cache/networkrlcd/turn-runtime/extracted/usr/bin/turnserver")
    package = Path("/home/agent/.cache/networkrlcd/turn-runtime/coturn_4.6.1-2_amd64.deb")
    library_dir = Path(turn["library_dir"])
    if sha(binary) != turn["binary_sha256"] or sha(package) != turn["package_sha256"]:
        raise ValueError("the local Coturn executable or package changed after preflight")
    library_hashes = {}
    for name, expected in turn["library_sha256"].items():
        path = library_dir / name
        if not expected or sha(path) != expected:
            raise ValueError("a Coturn runtime library changed after preflight: " + name)
        library_hashes[name] = expected
    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = str(library_dir) + (
        os.pathsep + environment["LD_LIBRARY_PATH"] if environment.get("LD_LIBRARY_PATH") else ""
    )
    linked = subprocess.check_output(["ldd", str(binary)], text=True, env=environment)
    if "not found" in linked:
        raise ValueError("the pinned Coturn runtime has an unresolved shared library")

    policy_bytes = POLICY_PATH.read_bytes()
    policy = json.loads(policy_bytes)
    policy_sha = hashlib.sha256(policy_bytes).hexdigest()
    browser_sha = sha(CHROMIUM_PATH)
    if policy.get("WebRtcIPHandling") != "disable_non_proxied_udp":
        raise ValueError("managed Chromium policy no longer matches the TURN/TCP preflight")
    if policy_sha != preflight["managed_policy"]["sha256_after"]:
        raise ValueError("managed Chromium policy differs from the preflight state")
    if browser_sha != preflight["browser"]["sha256"]:
        raise ValueError("Chromium binary differs from the preflight runtime")
    runtime = {
        "coturn_version": turn["version"],
        "coturn_package_path": str(package),
        "coturn_package_sha256": turn["package_sha256"],
        "coturn_binary_path": str(binary),
        "coturn_binary_sha256": turn["binary_sha256"],
        "coturn_library_dir": str(library_dir),
        "coturn_library_sha256": library_hashes,
        "chromium_binary_path": str(CHROMIUM_PATH),
        "chromium_sha256": browser_sha,
        "chromium_version": preflight["browser"]["version"],
        "managed_policy_path": str(POLICY_PATH),
        "managed_policy_value": policy["WebRtcIPHandling"],
        "managed_policy_sha256": policy_sha,
        "network_policy": "unrestricted HTTP via configured proxy; TURN sockets are loopback TCP/UDP only",
    }
    reference = {"path": str(preflight_path), "sha256": preflight_hash,
                 "source_sha256": source_hash, "passed": True,
                 "turn_candidates": [len(preflight["ice"]["peer_a_candidates"]), len(preflight["ice"]["peer_b_candidates"])],
                 "bidirectional_video_frames": [
                     preflight["media"]["peer_a_to_peer_b"]["sender"]["frames"],
                     preflight["media"]["peer_b_to_peer_a"]["sender"]["frames"],
                 ]}
    return runtime, reference


def write_registered_protocol(root: Path, protocol: dict) -> str:
    encoded = json.dumps(protocol, indent=2, sort_keys=True, allow_nan=False) + "\n"
    data = encoded.encode()
    protocol_path = root / "protocol.json"
    protocol_path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (root / "protocol.sha256").write_text(digest + "  protocol.json\n")
    if REGISTERED_PROTOCOL.exists():
        raise ValueError("registered TURN/TCP protocol path already exists; refusing to replace it")
    REGISTERED_PROTOCOL.write_bytes(data)
    return digest


def prepare(root: Path, preflight_path: Path, prior_root: Path) -> dict:
    root = root.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("TURN/TCP action capture root must be new and empty")
    calibration_reference, prior_reference, _ = verify_prior_evidence(prior_root)
    runtime, preflight_reference = runtime_provenance(preflight_path)
    result = core.prepare(root)
    shutil.copytree(Path(prior_root) / "clock-calibration", root / "clock-calibration")
    shutil.copy2(Path(prior_root) / "clock_report.json", root / "clock_report.json")
    protocol = read_json(root / "protocol.json")
    protocol["abi"] = "native_clock_action_probe_v2_turn_tcp_protocol"
    protocol["transport"] = {
        "browser_ice_transport_policy": "relay",
        "turn_uri_scheme": "turn:",
        "browser_to_turn_transport": "TCP",
        "turn_relay_transport": "UDP",
        "media_route": "Chromium TURN allocation over TCP; relay candidates fed through the existing measured Node UDP queue to Coturn relay allocations",
        "managed_WebRtcIPHandling": "disable_non_proxied_udp",
        "managed_policy_change": False,
        "TURN_listener_ip": "127.0.0.1",
        "TURN_relay_ip": "127.0.0.1",
        "TURN_allowed_peer_ip": "127.0.0.1",
        "queue_capacity_schedule_Mbps": [[1.2, "high", 6000], [0.35, "collapse", 6000], [1.2, "recovery", 6600]],
        "queue_and_propagation_mechanism_unchanged": True,
    }
    protocol["runtime"] = runtime
    protocol["preflight_reference"] = preflight_reference
    protocol["clock_calibration_reference"] = calibration_reference
    protocol["prior_failed_action_capture_reference"] = prior_reference
    protocol["storage"] = {
        "raw_capture_root": str(root),
        "registered_protocol": str(REGISTERED_PROTOCOL.relative_to(REPO)),
        "analysis_output": "reports/native-clock-action-turntcp-v2-analysis.json",
        "raw_data_outside_git": True,
    }
    protocol["source_hashes"] = source_inventory()
    digest = write_registered_protocol(root, protocol)
    return {"root": str(root), "registered_protocol": str(REGISTERED_PROTOCOL),
            "protocol_sha256": digest, "planned_sessions": len(protocol["trials"]),
            "seed_clusters": protocol["seed_clusters"],
            "preflight_sha256": preflight_reference["sha256"],
            "baseline_clock_report_sha256": calibration_reference["report_sha256"],
            "prior_failed_index_sha256": prior_reference["capture_index_sha256"],
            "source_hashes": protocol["source_hashes"]}


def load_registered(root: Path) -> dict:
    root = root.expanduser().resolve()
    protocol_path = root / "protocol.json"
    protocol = read_json(protocol_path)
    if protocol.get("abi") != "native_clock_action_probe_v2_turn_tcp_protocol":
        raise ValueError("the registered TURN/TCP protocol is required")
    digest = sha(protocol_path)
    if digest != (root / "protocol.sha256").read_text().split()[0]:
        raise ValueError("TURN/TCP protocol checksum changed")
    if not REGISTERED_PROTOCOL.is_file() or sha(REGISTERED_PROTOCOL) != digest:
        raise ValueError("versioned protocol differs from the captured protocol")
    if root != Path(protocol["storage"]["raw_capture_root"]).resolve():
        raise ValueError("the frozen raw output path changed")
    core.verify_sources(protocol)
    if sha(root / "clock_report.json") != protocol["clock_calibration_reference"]["report_sha256"]:
        raise ValueError("copied qualified clock report checksum changed")
    return protocol


def set_runtime_env(protocol: dict) -> None:
    os.environ["RLCD_TURN_BINARY"] = protocol["runtime"]["coturn_binary_path"]
    os.environ["RLCD_TURN_LIBRARY_DIR"] = protocol["runtime"]["coturn_library_dir"]
    inherited = os.environ.get("LD_LIBRARY_PATH", "")
    library_dir = protocol["runtime"]["coturn_library_dir"]
    if not inherited.startswith(library_dir):
        os.environ["LD_LIBRARY_PATH"] = library_dir + (os.pathsep + inherited if inherited else "")
    os.environ["RLCD_CHROME"] = protocol["runtime"]["chromium_binary_path"]


def capture(root: Path) -> dict:
    protocol = load_registered(root)
    runtime_now, preflight_now = runtime_provenance(Path(protocol["preflight_reference"]["path"]))
    if runtime_now != protocol["runtime"] or preflight_now["sha256"] != protocol["preflight_reference"]["sha256"]:
        raise ValueError("TURN runtime or successful preflight changed after registration")
    set_runtime_env(protocol)
    return core.capture(root)


def integrity(root: Path) -> dict:
    protocol = load_registered(root)
    _, index = core.check_capture_integrity(root)
    return {"planned": len(protocol["trials"]),
            "sealed": sum(item["status"] == "sealed" for item in index["sessions"]),
            "failed": sum(item["status"] == "failed" for item in index["sessions"]),
            "capture_index_sha256": sha(root / "capture_index.json"),
            "outcome_telemetry_read": False}


def _transport_checks(root: Path, trial_id: str, expected_turn_url: str) -> dict:
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
    pair_ok = lambda pair: (
        pair.get("local", {}).get("candidateType") == "relay"
        and pair.get("local", {}).get("relayProtocol") == "tcp"
        and pair.get("remote", {}).get("candidateType") == "relay"
    )
    qualified = {
        "ice_complete": ice.get("gathering_state_a") == "complete" and ice.get("gathering_state_b") == "complete",
        "candidate_url_is_loopback_turn_tcp": expected_turn_url.startswith("turn:127.0.0.1:") and expected_turn_url.endswith("?transport=tcp")
        and ice.get("turn_url") == expected_turn_url and transport.get("turn_url") == expected_turn_url
        and runtime.get("turn_url") == expected_turn_url and runtime.get("control_transport") == "TCP",
        "only_turn_tcp_candidates": only_turn_tcp,
        "no_ice_candidate_errors": not ice.get("candidate_errors", {}).get("a") and not ice.get("candidate_errors", {}).get("b"),
        "selected_relay_pairs": pair_ok(transport.get("selected_a", {})) and pair_ok(transport.get("selected_b", {})),
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


def clock_gate(root: Path) -> dict:
    root = root.expanduser().resolve()
    protocol = load_registered(root)
    _, index = core.check_capture_integrity(root)
    by_id = {trial["id"]: trial for trial in protocol["trials"]}
    results = []
    for item in index["sessions"]:
        result = {"trial": item["trial"], "capture_status": item["status"], "clock_passed": False,
                  "transport_passed": False, "outcome_data_read": False}
        if item["status"] != "sealed":
            result["reason"] = "session capture failed; excluded from treatment outcomes"
            results.append(result)
            continue
        # The port is randomized per session; require one exact loopback TURN/TCP URI on both peers.
        ice = read_json(root / "sessions" / item["trial"] / "ice_evidence.json")
        urls = {candidate.get("url") for peer in ("a", "b") for candidate in ice.get("candidates", {}).get(peer, [])}
        url = next(iter(urls)) if len(urls) == 1 else ""
        transport = _transport_checks(root, item["trial"], url)
        transport["turn_url"] = url
        markers = core.load_marker_pair(
            root / "sessions" / item["trial"] / "clock_markers_browser.json",
            root / "sessions" / item["trial"] / "clock_markers_node.json",
        )
        order_ok = (
            len(markers) == 5
            and [marker.get("marker_id") for marker in markers] == [f"m{n:04d}" for n in range(1, 6)]
            and [marker.get("endpoint") for marker in markers]
            == ["/clock-marker", "/phase", "/phase", "/phase", "/clock-marker"]
            and [marker.get("phase") for marker in markers[1:4]] == ["high", "collapse", "recovery"]
        )
        clock = core.validate_markers(markers, [0, 2, 4], [1, 3]) if order_ok else {"passed": False, "reason": "marker order/count mismatch"}
        clock_ok = order_ok and clock.get("passed") is True and clock.get("max_held_out_width_ms", float("inf")) <= core.MAX_CLOCK_WIDTH_MS
        result.update({"transport_passed": transport["passed"], "transport": transport,
                       "clock_passed": clock_ok, "clock": {key: value for key, value in clock.items() if key != "checks"},
                       "marker_count": len(markers), "outcome_data_read": False})
        if not clock_ok or not transport["passed"]:
            result["reason"] = "actual-session transport or clock acceptance failed"
        results.append(result)
    passed = (
        len(results) == len(protocol["trials"])
        and all(item["capture_status"] == "sealed" and item["clock_passed"] and item["transport_passed"] for item in results)
    )
    gate = {
        "abi": "native_turn_clock_action_v2_gate",
        "protocol_sha256": sha(root / "protocol.json"),
        "capture_index_sha256": sha(root / "capture_index.json"),
        "passed": passed,
        "planned_sessions": len(protocol["trials"]),
        "session_count": len(results),
        "clock_qualified_sessions": sum(item["clock_passed"] for item in results),
        "turn_transport_qualified_sessions": sum(item["transport_passed"] for item in results),
        "failed_capture_sessions": [item["trial"] for item in results if item["capture_status"] != "sealed"],
        "clock_or_transport_failures": [item["trial"] for item in results if item["capture_status"] == "sealed" and not (item["clock_passed"] and item["transport_passed"])],
        "outcome_analysis_performed": False,
        "session_results": results,
        "claim": "No per-hold relay cost, delivery, or QoE estimate is permitted unless every planned session has sealed, TURN-backed media and a passing actual-run clock map.",
    }
    gate_path = root / "clock_transport_gate.json"
    write_json(gate_path, gate)
    return {"passed": passed, "clock_qualified_sessions": gate["clock_qualified_sessions"],
            "turn_transport_qualified_sessions": gate["turn_transport_qualified_sessions"],
            "failed_capture_sessions": gate["failed_capture_sessions"],
            "clock_or_transport_failures": gate["clock_or_transport_failures"],
            "gate_sha256": sha(gate_path), "outcome_analysis_performed": False}


def analyze(root: Path, output: Path) -> dict:
    root, output = root.expanduser().resolve(), output.expanduser().resolve()
    protocol = load_registered(root)
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
        raise ValueError("all sessions must pass the checksum, TURN media, and actual-run clock gates before outcome analysis")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("fresh action-analysis report path required")
    core_report_path = root / "unpublished-core-analysis.json"
    core.analyze(root, core_report_path)
    report = read_json(core_report_path)
    report["abi"] = "native_turn_clock_action_probe_v2_turn_tcp_report"
    report["transport"] = protocol["transport"]
    report["runtime"] = protocol["runtime"]
    report["preflight_reference"] = protocol["preflight_reference"]
    report["clock_calibration_reference"] = protocol["clock_calibration_reference"]
    report["prior_failed_action_capture_reference"] = protocol["prior_failed_action_capture_reference"]
    report["actual_run_clock_transport_gate_sha256"] = sha(gate_path)
    report["outcome_data_read_after_gate"] = True
    report["controller_fitted_or_promoted"] = False
    write_json(output, report)
    return {"report": str(output), "report_sha256": sha(output),
            "sessions": report["sealed_sessions"],
            "actual_session_clocks_all_pass": report["session_clock_validations_all_pass"],
            "controller_fitted_or_promoted": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--preflight", type=Path, default=Path("/home/agent/.cache/networkrlcd/native-turn-tcp-preflight-v1-attempt2.json"))
    p.add_argument("--prior-root", type=Path, default=DEFAULT_PRIOR)
    p = commands.add_parser("capture")
    p.add_argument("--root", type=Path, required=True)
    p = commands.add_parser("integrity")
    p.add_argument("--root", type=Path, required=True)
    p = commands.add_parser("clock-gate")
    p.add_argument("--root", type=Path, required=True)
    p = commands.add_parser("analyze")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
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
