"""Register and run a TURN/TCP micro-randomized 0.65/1.05 sender-BWE action panel."""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RTC = REPO / "benchmarks/native_rtc"
PLAN = REPO / "docs/NATIVE_CLOCK_ACTION_TURN_TCP_V9_PLAN.md"
REGISTERED_PROTOCOL = REPO / "configs/native_clock_action_probe_turn_tcp_v9.json"
CAPTURE_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v9")
PREFLIGHT_PATH = Path("/home/agent/.cache/networkrlcd/native-turn-tcp-queue-preflight-v2.json")
CALIBRATION_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-probe-v1-final3")
REPORT_PATH = REPO / "reports/native-clock-action-turntcp-v9-analysis.json"
RECORDER = RTC / "clock_action_turn_tcp_episode_v9.mjs"
CORE_PATH = REPO / "tools/native_clock_action_probe_turntcp_v9_core.py"
V7_WRAPPER_PATH = REPO / "tools/native_turn_clock_action_probe_v7.py"
V7_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v7")
V7_REPORT = REPO / "reports/native-clock-action-turntcp-v7-analysis.json"
V7_PROTOCOL_SHA256 = "2eeaf29d04fdfdd63de57132bbec8308957a330180f3f9beeb6b123a1e75b85e"
V7_INDEX_SHA256 = "8bbcc5de8b6d7e2f79dffb2abb07d85418a54dc8867deb2e865658cc9683f037"
V7_GATE_SHA256 = "48af59918b64103ec050f9ada709b94f8f813ca671d617ea64dbfa856e38aa9b"
V7_REPORT_SHA256 = "3e78b850e351f8f34fea6afb244376931e4cffd7c50bdf9c8ec8b3743e5c725c"
RANDOMIZATION_SEED = 20261020
ACTION_RANDOMIZATION_SEED = 20261021
SCENE_SEEDS = tuple(range(8000, 8012))
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
    result["turntcp_v9_wrapper"] = sha(Path(__file__).resolve())
    result["turntcp_v9_plan_document"] = sha(PLAN)
    result["turntcp_v9_micro_randomizer"] = sha(RTC / "native_micro_randomized_ratio.mjs")
    result["turntcp_v8_registered_protocol"] = sha(REPO / "configs/native_clock_action_probe_turn_tcp_v8.json")
    result["turntcp_v8_result_report"] = sha(V8_REPORT)
    result["turntcp_v7_result_report"] = sha(V7_REPORT)
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



def make_trials(root: Path) -> tuple[list[dict], list[str]]:
    blocks = [(seed, repetition) for seed in SCENE_SEEDS for repetition in range(4)]
    rng = random.Random(RANDOMIZATION_SEED)
    rng.shuffle(blocks)
    trials, order = [], []
    for seed, repetition in blocks:
        condition = "micro"
        trial_id = f"turntcp9-scene{seed}-rep{repetition}-micro"
        episode = {"id": trial_id, "role": "discovery", "scene_seed": seed,
                   "action_randomization_seed": ACTION_RANDOMIZATION_SEED,
                   "schedule": core.SCHEDULE, "episode_timeout_s": 90}
        panel = {
            "panel_abi": "native_clock_action_probe_v1", "stage": "discovery",
            "source_kind": "generated_canvas_native_webrtc", "repair_model": None,
            "models": {}, "common_shadow_inference": True, "SOTA_achieved": False,
            "episode_timeout_s": 90,
            "measurement_recipe": {
                "abi": "native_clock_action_probe_v9_measurement",
                "action_ratios": [0.65, 1.05], "state_threshold_bps": 500000,
                "action_hold_ms": 3000, "endpoint_window_ms": list(core.HOLD_WINDOW_MS),
                "deadline_ms": core.DEADLINE_MS,
                "clock_abi": "native_clock_marker_exchange_v1",
            },
            "conditions": {"micro": {key: value for key, value in POLICIES["micro"].items()
                                       if key != "policy"}},
            "episodes": [episode],
        }
        panel_path = root / "panels" / f"{trial_id}.json"
        core.write_json(panel_path, panel)
        trial = {"id": trial_id, "condition": condition,
                 "policy": POLICIES[condition]["policy"], "scene_seed": seed,
                 "seed_cluster": seed, "repetition": repetition,
                 "panel": str(panel_path.relative_to(root)), "panel_sha256": sha(panel_path),
                 "order_position": len(order)}
        trials.append(trial)
        order.append(trial_id)
    return trials, order


def prepare(root: Path = CAPTURE_ROOT, preflight: Path = PREFLIGHT_PATH,
            prior_root: Path = CALIBRATION_ROOT) -> dict:
    root = root.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("fresh V9 TURN/TCP capture root required")
    calibration_reference, no_candidate_reference, _ = v2.verify_prior_evidence(prior_root)
    runtime, preflight_reference = base.runtime_provenance(preflight)
    prior_references = {
        "turn_v2": base.verify_previous_turn_v2(),
        "turn_v3": base.verify_previous_turn_v3(),
        "turn_v4": base.verify_previous_turn_v4(),
        "turn_v5": base.verify_previous_turn_v5(),
        "turn_v6": base.verify_previous_turn_v6(),
        "turn_v7": verify_v7_result(),
        "turn_v8": verify_v8_result(),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "panels").mkdir()
    trials, randomized_order = make_trials(root)
    protocol = {
        "abi": "native_clock_action_probe_v9_turn_tcp_protocol",
        "confirmatory": False,
        "question": "Does the pre-action sender BWE split identify different causal delivery or relay effects for randomized 0.65 and 1.05 actions?",
        "source_hashes": source_inventory(),
        "seed_clusters": {"count": len(SCENE_SEEDS), "ids": list(SCENE_SEEDS)},
        "repetitions_per_seed": 4,
        "session_order_seed": RANDOMIZATION_SEED,
        "action_randomization_seed": ACTION_RANDOMIZATION_SEED,
        "randomization": {
            "abi": "native_micro_randomized_ratio_v1",
            "seed": ACTION_RANDOMIZATION_SEED,
            "state_threshold_bps": 500000,
            "state_bins": ["bwe_lt_500k", "bwe_ge_500k"],
            "ratios": [0.65, 1.05], "propensity_each_ratio": 0.5,
            "draw": "first uint32 big-endian of SHA256(networkrlcd-native-v9:{seed}:{trial_id}:{epoch}); low bit 0 selects 0.65, 1 selects 1.05",
        },
        "scene_seeds": list(SCENE_SEEDS),
        "randomized_session_order": True,
        "randomized_order": randomized_order,
        "conditions": POLICIES,
        "trials": trials,
        "schedule": core.SCHEDULE,
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
            "media_acceptance": "Each scheduled phase has more than ten encoded and decoded frames and finite mean encode time.",
            "queue_acceptance": "Both directions forward at least 100 packets from matching TURN allocation ports, no unexpected sources or send errors; packet and byte replay exactly matches offer/drop/service/forward ledgers; capacity and conservation checks pass.",
            "queue_and_propagation_mechanism_unchanged": True,
        },
        "analysis": {
            "unit": "generated-scene seed cluster", "degrees_of_freedom": len(SCENE_SEEDS) - 1,
            "confidence": 0.95,
            "primary_endpoint": "1.05-0.65 on-time contrast at BWE >=500kbps minus the same contrast at BWE <500kbps",
            "min_hold_windows_per_seed_state_action_cell": 2,
            "minimum_complete_seed_clusters": 8,
            "secondary_endpoints": ["on-time and sampled RGB PSNR action effects by BWE stratum",
                                    "guaranteed relay wire bytes per hold by BWE stratum", "queue drops"],
            "clock_assignment": "only estimate relay joins when all feasible affine maps cover every held-out marker",
            "action_validation": "replay every SHA256 draw; classify BWE before action; verify requested ratio/cap against proposal and native readback",
            "do_not_pool": ["V3", "V4", "V5", "V6", "V7", "V8", "archived native sessions",
                            "recorded-video captures", "simulator/synthetic-controller evidence"],
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
            "scene_seeds": list(SCENE_SEEDS), "randomization_seed": RANDOMIZATION_SEED,
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
    if protocol.get("abi") != "native_clock_action_probe_v9_turn_tcp_protocol":
        raise ValueError("registered V9 TURN/TCP protocol required")
    if digest != (root / "protocol.sha256").read_text().split()[0]:
        raise ValueError("V9 protocol checksum changed")
    if not REGISTERED_PROTOCOL.is_file() or sha(REGISTERED_PROTOCOL) != digest:
        raise ValueError("versioned V9 protocol differs from capture registration")
    if root != Path(protocol["storage"]["raw_capture_root"]).resolve():
        raise ValueError("V9 raw capture root changed")
    if (protocol.get("scene_seeds") != list(SCENE_SEEDS)
            or protocol.get("session_order_seed") != RANDOMIZATION_SEED
            or protocol.get("action_randomization_seed") != ACTION_RANDOMIZATION_SEED):
        raise ValueError("V9 scene or randomization seed changed")
    if len(protocol.get("trials", [])) != 48 or len(set(protocol["randomized_order"])) != 48:
        raise ValueError("V9 must retain its complete 48-session randomized panel")
    if protocol.get("calibration", {}).get("held_out_indices") != [2, 5, 8, 10]:
        raise ValueError("V9 actual-run clock marker holdouts changed")
    core.verify_sources(protocol)
    if sha(root / "clock_report.json") != protocol["clock_calibration_reference"]["report_sha256"]:
        raise ValueError("copied qualified clock report changed")
    return protocol


def capture(root: Path = CAPTURE_ROOT) -> dict:
    root = root.expanduser().resolve()
    protocol = load_registered(root)
    runtime_now, preflight_now = base.runtime_provenance(Path(protocol["preflight_reference"]["path"]))
    if runtime_now != protocol["runtime"]:
        raise ValueError("V9 runtime changed after registration")
    if preflight_now["sha256"] != protocol["preflight_reference"]["sha256"]:
        raise ValueError("V9 TURN/TCP preflight changed after registration")
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


def clock_gate(root: Path = CAPTURE_ROOT) -> dict:
    root = root.expanduser().resolve()
    protocol = load_registered(root)
    _, index = core.check_capture_integrity(root)
    results = []
    for item in index["sessions"]:
        row = {"trial": item["trial"], "capture_status": item["status"],
               "clock_passed": False, "transport_passed": False, "outcome_data_read": False}
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
        expected_phases = [None, None, "high", None, None, "collapse", None, None,
                           "recovery", None, None, None]
        order_ok = (len(markers) == 12
                    and [marker.get("marker_id") for marker in markers] == expected_ids
                    and [marker.get("endpoint") for marker in markers] == expected_endpoints
                    and [marker.get("phase") for marker in markers] == expected_phases)
        clock = (core.validate_markers(markers, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])
                 if order_ok else {"passed": False, "reason": "12-marker order/count mismatch"})
        clock_ok = (order_ok and clock.get("passed") is True
                    and clock.get("max_held_out_width_ms", float("inf"))
                    <= protocol["calibration"]["max_held_out_width_ms"])
        row.update({"transport_passed": transport["passed"], "transport": transport,
                    "clock_passed": clock_ok,
                    "clock": {key: value for key, value in clock.items() if key != "checks"},
                    "marker_count": len(markers), "outcome_data_read": False})
        if not clock_ok or not transport["passed"]:
            row["reason"] = "actual-run transport or clock gate failed"
        results.append(row)
    passed = (len(results) == len(protocol["trials"])
              and all(row["capture_status"] == "sealed" and row["clock_passed"]
                      and row["transport_passed"] for row in results))
    gate = {"abi": "native_turn_clock_action_v9_gate",
            "protocol_sha256": sha(root / "protocol.json"),
            "capture_index_sha256": sha(root / "capture_index.json"),
            "passed": passed, "planned_sessions": len(protocol["trials"]),
            "qualified_clock_sessions": sum(row["clock_passed"] for row in results),
            "qualified_transport_sessions": sum(row["transport_passed"] for row in results),
            "failed_capture_sessions": sum(row["capture_status"] != "sealed" for row in results),
            "outcome_analysis_performed": False, "sessions": results}
    gate_path = root / "clock_transport_gate.json"
    core.write_json(gate_path, gate)
    return {key: gate[key] for key in ("passed", "planned_sessions", "qualified_clock_sessions",
            "qualified_transport_sessions", "failed_capture_sessions", "outcome_analysis_performed")} | {
                "gate_sha256": sha(gate_path)}


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
        raise ValueError("all V9 sessions must pass integrity, transport, and actual-run clock gates before outcomes are read")
    if output.exists():
        raise ValueError("fresh V9 analysis report path required")
    report = core.analyze_v9(root, root / "unpublished-v9-analysis.json")
    report["transport"] = protocol["transport"]
    report["runtime"] = protocol["runtime"]
    report["preflight_reference"] = protocol["preflight_reference"]
    report["clock_calibration_reference"] = protocol["clock_calibration_reference"]
    report["prior_frozen_studies"] = protocol["prior_frozen_studies"]
    report["actual_run_clock_transport_gate_sha256"] = sha(gate_path)
    report["outcome_data_read_after_gate"] = True
    report["controller_fitted_or_promoted"] = False
    core.write_json(output, report)
    return {"report": str(output), "report_sha256": sha(output),
            "sessions": report["sealed_sessions"],
            "actual_session_clocks_all_pass": report["session_clock_validations_all_pass"],
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
