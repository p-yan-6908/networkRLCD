"""Freeze, capture, seal, and analyze the native TURN/TCP V10 sender-BWE threshold-policy validation."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
RTC = HERE / "benchmarks/native_rtc"
RECORDER = RTC / "clock_action_turn_tcp_episode_v10.mjs"
CALIBRATOR = RTC / "clock_marker_calibrate_v1.mjs"
MODULES = (
    "frame_marker.mjs", "native_actuation.mjs", "sender_observation.mjs",
    "source_quality.mjs", "bwe_cap_controller.mjs", "native_policy.mjs",
    "range_control.mjs", "native_bwe_hold_control.mjs", "native_bwe_threshold_policy.mjs", "actuator_control.mjs", "actuator_meter.mjs",
    "encoder_response.mjs", "dense_control.mjs", "excitation_control.mjs",
    "dense_actuation.mjs", "streamed_actuator_video.mjs", "fixed_encoder5.mjs",
    "repair5_policy.mjs", "repair3_policy.mjs", "streamed_video5.mjs",
    "streamed_video.mjs", "recorded_video.mjs",
)
SCHEDULE = [[1.2, "high", 6000], [0.35, "collapse", 6000], [1.2, "recovery", 6600]]
LEVELS = {"level065": (1, 0.65), "level105": (3, 1.05)}
ALPHA_BOUNDS = (0.98, 1.02)
MAX_CLOCK_WIDTH_MS = 50.0
CLOCK_VALIDATION_TOLERANCE_MS = 1.0
FEASIBILITY_SOLVER_TOLERANCE_MS = 1e-7
DEADLINE_MS = 150.0
HOLD_WINDOW_MS = (1800.0, 2600.0)
T_CRITICAL = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_json(path: Path):
    return json.loads(path.read_text())


def source_inventory() -> dict[str, str]:
    names = [RECORDER.name, CALIBRATOR.name, *MODULES]
    hashes = {name: sha(RTC / name) for name in names}
    hashes["frozen_range_episode_parent"] = sha(RTC / "range_episode.mjs")
    hashes["analysis_tool"] = sha(Path(__file__).resolve())
    hashes["plan_document"] = sha(HERE / "docs/NATIVE_CLOCK_ACTION_TURN_TCP_V10_PLAN.md")
    return hashes


def prepare(root: Path) -> dict:
    root = root.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("probe root must be fresh or empty")
    root.mkdir(parents=True, exist_ok=True)
    (root / "panels").mkdir(exist_ok=True)
    rng = random.Random(20261013)
    blocks = [(seed, rep) for seed in range(8) for rep in range(2)]
    rng.shuffle(blocks)
    flips = [False] * 8 + [True] * 8
    rng.shuffle(flips)
    order = []
    panels = {}
    trials = []
    for (seed, rep), flip in zip(blocks, flips):
        levels = ["level065", "level105"]
        if flip:
            levels.reverse()
        for level_name in levels:
            level, ratio = LEVELS[level_name]
            trial_id = f"scene{seed:02d}-rep{rep}-r{int(ratio*100):03d}"
            episode = {
                "id": trial_id, "role": "discovery", "scene_seed": 1000 + seed,
                "schedule": SCHEDULE, "episode_timeout_s": 90,
            }
            panel = {
                "panel_abi": "native_clock_action_probe_v1", "stage": "discovery",
                "source_kind": "generated_canvas_native_webrtc",
                "repair_model": None, "models": {}, "common_shadow_inference": True,
                "SOTA_achieved": False, "episode_timeout_s": 90,
                "measurement_recipe": {
                    "abi": "native_clock_action_probe_v1_measurement",
                    "action_ratios": [0.65, 1.05], "hold_ms": 3000,
                    "endpoint_window_ms": list(HOLD_WINDOW_MS),
                    "deadline_ms": DEADLINE_MS,
                    "clock_abi": "native_clock_marker_exchange_v1",
                },
                "conditions": {
                    "level065": {"controller": "explore", "behavior": "level", "level": 1},
                    "level105": {"controller": "explore", "behavior": "level", "level": 3},
                },
                "episodes": [episode],
            }
            panel_path = root / "panels" / f"{trial_id}.json"
            write_json(panel_path, panel)
            panel_sha = sha(panel_path)
            trial = {
                "id": trial_id, "condition": level_name, "ratio": ratio,
                "scene_seed": 1000 + seed, "seed_cluster": seed, "repetition": rep,
                "panel": str(panel_path.relative_to(root)), "panel_sha256": panel_sha,
                "order_position": len(order),
            }
            trials.append(trial)
            order.append(trial_id)
    protocol = {
        "abi": "native_clock_action_probe_v1_protocol",
        "confirmatory": False,
        "calibration": {
            "marker_count": 120, "interval_ms": 500, "train_indices": "even",
            "held_out_indices": "odd", "alpha_bounds": list(ALPHA_BOUNDS),
            "max_held_out_width_ms": MAX_CLOCK_WIDTH_MS,
            "held_out_timestamp_tolerance_ms": CLOCK_VALIDATION_TOLERANCE_MS,
            "solver_tolerance_ms": FEASIBILITY_SOLVER_TOLERANCE_MS,
            "required_held_out_coverage": 1.0,
        },
        "source_hashes": source_inventory(), "schedule": SCHEDULE,
        "action_levels": {k: {"index": v[0], "ratio": v[1]} for k, v in LEVELS.items()},
        "seed_clusters": 8, "repetitions_per_level_per_seed": 2,
        "randomization_seed": 20261013, "balanced_within_block_order": True,
        "randomized_order": order, "trials": trials,
        "analysis": {
            "unit": "generated-scene seed cluster", "degrees_of_freedom": 7,
            "confidence": 0.95, "action_contrast": "0.65 minus 1.05",
            "relay_window_ms_after_ack": list(HOLD_WINDOW_MS),
            "frame_deadline_ms": DEADLINE_MS,
            "clock_assignment": "guaranteed only if all feasible affine maps agree",
            "do_not_pool": ["V3", "V4", "V5", "V6", "archived native sessions", "recorded-video captures", "simulator or synthetic-controller results"],
            "fit_or_promote_controller": False,
        },
    }
    write_json(root / "protocol.json", protocol)
    (root / "protocol.sha256").write_text(sha(root / "protocol.json") + "  protocol.json\n")
    return {"root": str(root), "trials": len(trials), "seed_clusters": 8,
            "source_hashes": protocol["source_hashes"], "protocol_sha256": sha(root / "protocol.json")}


def verify_sources(protocol: dict) -> None:
    current = source_inventory()
    if protocol["source_hashes"] != current:
        raise ValueError("probe source/module hashes changed after the protocol was frozen")


def seal_directory(directory: Path, stage: str) -> dict:
    files = sorted(p for p in directory.rglob("*") if p.is_file() and p.name != "integrity.json")
    inventory = {str(p.relative_to(directory)): sha(p) for p in files}
    payload = {"abi": "native_clock_action_probe_integrity_v1", "stage": stage,
               "files": inventory, "file_count": len(inventory)}
    write_json(directory / "integrity.json", payload)
    return payload


def verify_directory(directory: Path, stage: str | None = None) -> dict:
    payload = read_json(directory / "integrity.json")
    if payload.get("abi") != "native_clock_action_probe_integrity_v1":
        raise ValueError(f"invalid integrity manifest in {directory}")
    if stage is not None and payload.get("stage") != stage:
        raise ValueError(f"wrong integrity stage in {directory}")
    actual_paths = {str(p.relative_to(directory)) for p in directory.rglob("*")
                    if p.is_file() and p.name != "integrity.json"}
    if actual_paths != set(payload["files"]):
        raise ValueError(f"integrity inventory differs in {directory}")
    for name, expected in payload["files"].items():
        if sha(directory / name) != expected:
            raise ValueError(f"checksum mismatch: {directory / name}")
    return payload


def marker_constraints(markers: list[dict], origin: float):
    constraints = []
    for marker in markers:
        bsend, brecv = marker["browser_send_ms"], marker["browser_receive_ms"]
        nrecv, nsend = marker["node_receive_ms"], marker["node_send_ms"]
        constraints.append((bsend - origin, 1.0, nrecv))
        constraints.append((-(brecv - origin), -1.0, -nsend))
    amin, amax = ALPHA_BOUNDS
    constraints += [(-1.0, 0.0, -amin), (1.0, 0.0, amax)]
    return constraints


def feasible_polygon(markers: list[dict]) -> tuple[float, list[tuple[float, float]]]:
    if len(markers) < 2:
        return 0.0, []
    origin = (min(m["browser_send_ms"] for m in markers) +
              max(m["browser_receive_ms"] for m in markers)) / 2
    constraints = marker_constraints(markers, origin)
    vertices = []
    for i, (a1, b1, c1) in enumerate(constraints):
        for a2, b2, c2 in constraints[i + 1:]:
            det = a1 * b2 - a2 * b1
            if abs(det) < 1e-15:
                continue
            alpha = (c1 * b2 - c2 * b1) / det
            beta0 = (a1 * c2 - a2 * c1) / det
            if all(a * alpha + b * beta0 <= c + FEASIBILITY_SOLVER_TOLERANCE_MS
                   for a, b, c in constraints):
                if not any(abs(alpha - x) < 1e-8 and abs(beta0 - y) < 1e-5 for x, y in vertices):
                    vertices.append((alpha, beta0))
    if len(vertices) >= 3:
        cx = statistics.mean(v[0] for v in vertices)
        cy = statistics.mean(v[1] for v in vertices)
        vertices.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    return origin, vertices


def mapped_browser_range(node_ms: float, origin: float, vertices: list[tuple[float, float]]):
    mapped = [origin + (node_ms - beta0) / alpha for alpha, beta0 in vertices]
    return min(mapped), max(mapped)


def validate_markers(markers: list[dict], train_indices: list[int], holdout_indices: list[int]):
    train = [markers[i] for i in train_indices]
    origin, vertices = feasible_polygon(train)
    if len(vertices) < 3:
        return {"passed": False, "reason": "empty or unbounded affine feasible polygon",
                "training_markers": len(train), "vertices": len(vertices)}
    widths, covered = [], 0
    checks = []
    for i in holdout_indices:
        m = markers[i]
        rlo, rhi = mapped_browser_range(m["node_receive_ms"], origin, vertices)
        slo, shi = mapped_browser_range(m["node_send_ms"], origin, vertices)
        width = max(rhi - rlo, shi - slo)
        widths.append(width)
        pointwise = [
            (origin + (m["node_receive_ms"] - beta0) / alpha,
             origin + (m["node_send_ms"] - beta0) / alpha)
            for alpha, beta0 in vertices
        ]
        tolerance = CLOCK_VALIDATION_TOLERANCE_MS
        ok = all(m["browser_send_ms"] - tolerance <= receive <= send <=
                 m["browser_receive_ms"] + tolerance for receive, send in pointwise)
        covered += int(ok)
        checks.append({"marker_id": m["marker_id"], "covered": ok,
                       "mapped_receive_ms": [rlo, rhi], "mapped_send_ms": [slo, shi],
                       "round_trip_ms": m["browser_receive_ms"] - m["browser_send_ms"],
                       "width_ms": width})
    alpha = [v[0] for v in vertices]
    beta_at_origin = [v[1] for v in vertices]
    maximum = max(widths, default=0.0)
    return {
        "passed": bool(covered == len(holdout_indices) and maximum <= MAX_CLOCK_WIDTH_MS),
        "coverage": covered / len(holdout_indices) if holdout_indices else 0.0,
        "held_out_count": len(holdout_indices), "covered_count": covered,
        "max_held_out_width_ms": maximum,
        "p95_held_out_width_ms": sorted(widths)[max(0, math.ceil(0.95 * len(widths)) - 1)] if widths else None,
        "alpha_feasible": [min(alpha), max(alpha)],
        "beta_at_origin_feasible_ms": [min(beta_at_origin), max(beta_at_origin)],
        "origin_browser_ms": origin, "vertex_count": len(vertices),
        "training_marker_count": len(train), "checks": checks,
    }


def load_marker_pair(browser_path: Path, node_path: Path) -> list[dict]:
    browser = read_json(browser_path)["markers"]
    node = read_json(node_path)
    by_node = {m["marker_id"]: m for m in node}
    if len(by_node) != len(node) or len({m["marker_id"] for m in browser}) != len(browser):
        raise ValueError("duplicate marker IDs")
    if {m["marker_id"] for m in browser} != set(by_node):
        raise ValueError("browser/Node marker inventories differ")
    merged = []
    for b in browser:
        n = by_node[b["marker_id"]]
        if abs(b["browser_send_ms"] - n["browser_send_ms"]) > 1e-7:
            raise ValueError("echoed browser timestamp changed")
        merged.append({**n, "browser_receive_ms": b["browser_receive_ms"],
                       "endpoint": b.get("endpoint", "/clock-marker")})
    return merged


def calibrate(root: Path) -> dict:
    root = root.expanduser().resolve()
    protocol = read_json(root / "protocol.json")
    verify_sources(protocol)
    out = root / "clock-calibration"
    if out.exists():
        raise ValueError("clock-calibration directory already exists")
    result = subprocess.run(["node", str(CALIBRATOR), str(out)], cwd=HERE,
                            capture_output=True, text=True, timeout=100)
    (out / "capture_stdout.log").write_text(result.stdout)
    (out / "capture_stderr.log").write_text(result.stderr)
    if result.returncode != 0:
        seal_directory(out, "clock_calibration_failed")
        raise RuntimeError(f"clock calibration failed with exit code {result.returncode}; raw failure retained at {out}")
    seal_directory(out, "clock_calibration")
    return {"out": str(out), "exit_code": result.returncode}


def analyze_clock(root: Path) -> dict:
    root = root.expanduser().resolve()
    protocol = read_json(root / "protocol.json")
    verify_sources(protocol)
    directory = root / "clock-calibration"
    verify_directory(directory, "clock_calibration")
    markers = load_marker_pair(directory / "clock_markers_browser.json", directory / "clock_markers_node.json")
    if len(markers) != 120:
        raise ValueError(f"expected 120 calibration exchanges, found {len(markers)}")
    validation = validate_markers(markers, list(range(0, 120, 2)), list(range(1, 120, 2)))
    validation.update({"abi": "native_clock_marker_calibration_report_v1",
                       "marker_count": len(markers), "alpha_bounds": list(ALPHA_BOUNDS),
                       "held_out_timestamp_tolerance_ms": CLOCK_VALIDATION_TOLERANCE_MS,
                       "solver_tolerance_ms": FEASIBILITY_SOLVER_TOLERANCE_MS,
                       "max_width_threshold_ms": MAX_CLOCK_WIDTH_MS,
                       "protocol_sha256": sha(root / "protocol.json"),
                       "integrity_manifest_sha256": sha(directory / "integrity.json")})
    write_json(root / "clock_report.json", validation)
    return {k: validation[k] for k in ("passed", "coverage", "held_out_count", "max_held_out_width_ms", "alpha_feasible", "vertex_count")}


def capture(root: Path) -> dict:
    root = root.expanduser().resolve()
    protocol_path = root / "protocol.json"
    protocol = read_json(protocol_path)
    verify_sources(protocol)
    if sha(protocol_path) != (root / "protocol.sha256").read_text().split()[0]:
        raise ValueError("frozen protocol checksum mismatch")
    clock = read_json(root / "clock_report.json")
    if not clock.get("passed"):
        raise ValueError("clock calibration has not passed; no action capture started")
    sessions_root = root / "sessions"
    sessions_root.mkdir(exist_ok=False)
    index = {"abi": "native_clock_action_capture_index_v1", "protocol_sha256": sha(protocol_path), "sessions": []}
    for trial_id in protocol["randomized_order"]:
        trial = next(t for t in protocol["trials"] if t["id"] == trial_id)
        child = sessions_root / trial_id
        panel_path = root / trial["panel"]
        if sha(panel_path) != trial["panel_sha256"]:
            raise ValueError(f"panel checksum mismatch before capture: {trial_id}")
        command = ["node", str(RECORDER), str(child), str(panel_path), trial_id, trial["condition"]]
        env = os.environ.copy()
        env.setdefault("RLCD_CHROME", "/usr/bin/chromium")
        try:
            proc = subprocess.run(command, cwd=HERE, env=env, capture_output=True, text=True, timeout=110)
            (child / "capture_stdout.log").write_text(proc.stdout)
            (child / "capture_stderr.log").write_text(proc.stderr)
            status = "sealed" if proc.returncode == 0 else "failed"
            error = None if proc.returncode == 0 else f"exit code {proc.returncode}"
        except subprocess.TimeoutExpired as exc:
            (child / "capture_stdout.log").write_text(exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or "")
            (child / "capture_stderr.log").write_text(exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or "")
            status, error = "failed", "bounded 110-second timeout"
        child.mkdir(parents=True, exist_ok=True)
        seal = seal_directory(child, "native_action_session" if status == "sealed" else "native_action_session_failed")
        index["sessions"].append({"trial": trial_id, "status": status, "error": error,
                                  "integrity_manifest_sha256": sha(child / "integrity.json"),
                                  "file_count": seal["file_count"]})
        write_json(root / "capture_index.json", index)
    return {"planned": len(protocol["trials"]),
            "sealed": sum(s["status"] == "sealed" for s in index["sessions"]),
            "failed": sum(s["status"] == "failed" for s in index["sessions"]),
            "capture_index_sha256": sha(root / "capture_index.json")}


def check_capture_integrity(root: Path):
    protocol = read_json(root / "protocol.json")
    verify_sources(protocol)
    if sha(root / "protocol.json") != (root / "protocol.sha256").read_text().split()[0]:
        raise ValueError("frozen protocol checksum mismatch")
    index = read_json(root / "capture_index.json")
    if index["protocol_sha256"] != sha(root / "protocol.json"):
        raise ValueError("capture index references a different protocol")
    expected = {t["id"] for t in protocol["trials"]}
    seen = {s["trial"] for s in index["sessions"]}
    if seen != expected or len(seen) != len(index["sessions"]):
        raise ValueError("capture inventory does not match the frozen randomized order")
    for session in index["sessions"]:
        directory = root / "sessions" / session["trial"]
        manifest = verify_directory(directory)
        if sha(directory / "integrity.json") != session["integrity_manifest_sha256"]:
            raise ValueError(f"session manifest changed: {session['trial']}")
        if manifest["stage"] not in ("native_action_session", "native_action_session_failed"):
            raise ValueError(f"unexpected session seal: {session['trial']}")
        if session["status"] == "sealed" and manifest["stage"] != "native_action_session":
            raise ValueError(f"session status/seal mismatch: {session['trial']}")
    return protocol, index


def extract_holds(sender: dict, phases: list[dict]) -> list[dict]:
    by_epoch = {}
    for decision in sender["decisions"]:
        assignment = decision.get("actuator_assignment")
        if not assignment or not isinstance(assignment.get("epoch"), int):
            continue
        epoch = assignment["epoch"]
        ack = decision.get("ack_ms")
        if not isinstance(ack, (float, int)) or ack < assignment["assignment_ms"]:
            continue
        if epoch not in by_epoch or ack < by_epoch[epoch]["ack_ms"]:
            by_epoch[epoch] = {"epoch": epoch, "assignment": assignment, "ack_ms": ack}
    ordered = sorted(by_epoch.values(), key=lambda h: h["ack_ms"])
    holds = []
    for index, hold in enumerate(ordered):
        start, end = hold["ack_ms"] + HOLD_WINDOW_MS[0], hold["ack_ms"] + HOLD_WINDOW_MS[1]
        phase = next((p for p in phases if start >= p["start_ms"] and end <= p["end_ms"]), None)
        holds.append({**hold, "window_start_ms": start, "window_end_ms": end,
                      "phase": phase["phase"] if phase else None,
                      "phase_marker_id": phase["marker_id"] if phase else None})
    return holds


def load_session(root: Path, trial: dict, protocol: dict) -> dict:
    directory = root / "sessions" / trial["id"]
    summary = read_json(directory / "summary.json")
    frame = read_json(directory / "frame_events.json")
    sender = read_json(directory / "sender_observations.json")
    browser_markers = frame["clock_markers"]
    node_events = [json.loads(line) for line in gzip.open(directory / "events.jsonl.gz", "rt") if line.strip()]
    node_markers = [e for e in node_events if e.get("kind") == "clock_marker"]
    node_by_id = {m["marker_id"]: m for m in node_markers}
    merged = []
    for b in browser_markers:
        n = node_by_id.get(b["marker_id"])
        if n is None or b["browser_send_ms"] != n["browser_send_ms"]:
            raise ValueError(f"marker mismatch in {trial['id']}")
        merged.append({**n, "browser_receive_ms": b["browser_receive_ms"]})
    if len(merged) != 12:
        raise ValueError(f"expected 12 in-session markers, found {len(merged)} in {trial['id']}")
    validation = validate_markers(merged, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])
    origin, vertices = feasible_polygon(merged)
    if len(vertices) < 3:
        validation["passed"] = False
    if summary.get("connection") != "connected" or not summary.get("native_rtc"):
        raise ValueError(f"native RTC session did not qualify: {trial['id']}")
    holds = extract_holds(sender, frame["phase_windows"])
    if len(holds) > 6:
        raise ValueError(f"unexpected hold count in {trial['id']}")
    expected_ratio = protocol["action_levels"][trial["condition"]]["ratio"]
    if trial["ratio"] != expected_ratio:
        raise ValueError(f"protocol arm/ratio mismatch in {trial['id']}")
    assigned = [decision for decision in sender["decisions"]
                if isinstance(decision.get("actuator_assignment"), dict)]
    mismatched = []
    for decision in assigned:
        assignment = decision["actuator_assignment"]
        base_bwe = assignment.get("base_bwe_bps")
        if not isinstance(base_bwe, (int, float)) or not math.isfinite(base_bwe) or base_bwe <= 0:
            mismatched.append(decision.get("step_id"))
            continue
        expected_cap = max(150000, min(4000000, math.floor(expected_ratio * base_bwe + 0.5)))
        proposed = decision.get("proposed_action", {}).get("encoder_max_bitrate_bps")
        actual = decision.get("actuation_readback", {}).get("encoder_max_bitrate_bps")
        if (assignment.get("ratio") != expected_ratio
                or assignment.get("requested_bps") != expected_cap
                or proposed != expected_cap or actual != expected_cap):
            mismatched.append(decision.get("step_id"))
    if not assigned or mismatched:
        raise ValueError(f"registered bitrate action/readback mismatch in {trial['id']}: {mismatched}")
    phase_hold_counts = {state: sum(hold["phase"] == state for hold in holds)
                         for state in ("high", "collapse", "recovery")}
    if any(count < 1 for count in phase_hold_counts.values()):
        raise ValueError(f"fewer than one complete action hold window in every state for {trial['id']}: {phase_hold_counts}")
    sources = {s["source_id"]: s for s in frame["sources"] if isinstance(s.get("source_id"), int)}
    observations = {}
    for observation in frame["observations"]:
        source_id = observation.get("source_id")
        if isinstance(source_id, int) and observation.get("known_source"):
            observations.setdefault(source_id, []).append(observation)
    hold_rows = []
    for hold in holds:
        lo, hi = hold["window_start_ms"], hold["window_end_ms"]
        selected = [s for s in sources.values() if lo <= s.get("capture_request_ms", -1) < hi]
        on_time, psnrs = 0, []
        for source in selected:
            choices = observations.get(source["source_id"], [])
            valid = [o for o in choices if isinstance(o.get("readback_ms"), (int, float)) and
                     0 <= o["readback_ms"] - source["capture_request_ms"] <= DEADLINE_MS]
            if valid:
                on_time += 1
                q = min(valid, key=lambda o: o["readback_ms"]).get("quality") or {}
                if isinstance(q.get("psnr_db"), (int, float)):
                    psnrs.append(q["psnr_db"])
        relay = {"guaranteed_packets": 0, "guaranteed_wire_bytes": 0,
                 "guaranteed_dropped_wire_bytes": 0, "possible_packets": 0,
                 "possible_wire_bytes": 0, "possible_dropped_wire_bytes": 0}
        for event in node_events if validation.get("passed") else []:
            if event.get("kind") != "offer" or event.get("direction") != "a_to_b":
                continue
            event_lo, event_hi = mapped_browser_range(event["at_ms"], origin, vertices)
            possible = event_hi >= lo and event_lo < hi
            guaranteed = event_lo >= lo and event_hi < hi
            if possible:
                relay["possible_packets"] += 1
                relay["possible_wire_bytes"] += event["wire_bytes"]
                if event.get("dropped"):
                    relay["possible_dropped_wire_bytes"] += event["wire_bytes"]
            if guaranteed:
                relay["guaranteed_packets"] += 1
                relay["guaranteed_wire_bytes"] += event["wire_bytes"]
                if event.get("dropped"):
                    relay["guaranteed_dropped_wire_bytes"] += event["wire_bytes"]
        if not validation.get("passed"):
            relay = {name: None for name in relay}
        hold_rows.append({
            "epoch": hold["epoch"], "ratio": hold["assignment"].get("ratio"),
            "base_bwe_bps": hold["assignment"].get("base_bwe_bps"),
            "requested_bps": hold["assignment"].get("requested_bps"),
            "ack_ms": hold["ack_ms"], "window_ms": [lo, hi], "phase": hold["phase"],
            "source_frames": len(selected), "on_time_frames": on_time,
            "on_time_fraction": on_time / len(selected) if selected else None,
            "mean_ontime_psnr_db": statistics.mean(psnrs) if psnrs else None,
            "relay": relay,
        })
    return {
        "trial": trial["id"], "seed_cluster": trial["seed_cluster"],
        "repetition": trial["repetition"], "condition": trial["condition"],
        "ratio": trial["ratio"], "clock_validation": validation,
        "action_validation": {
            "expected_ratio": expected_ratio,
            "assigned_decisions": len(assigned),
            "all_requested_caps_read_back": not mismatched,
            "phase_hold_counts": phase_hold_counts,
        },
        "clock_feasible_vertices": len(vertices), "clock_origin_browser_ms": origin,
        "holds": hold_rows,
    }


def mean_or_none(values):
    v = [x for x in values if isinstance(x, (int, float)) and math.isfinite(x)]
    return statistics.mean(v) if v else None


def interval(values):
    values = [x for x in values if isinstance(x, (int, float)) and math.isfinite(x)]
    if len(values) < 2:
        return {"n": len(values), "mean": mean_or_none(values), "ci95": None}
    mean = statistics.mean(values)
    sd = statistics.stdev(values)
    critical = T_CRITICAL.get(len(values) - 1)
    if critical is None:
        critical = 1.96
    half = critical * sd / math.sqrt(len(values))
    return {"n": len(values), "mean": mean, "ci95": [mean - half, mean + half], "sd": sd}


def bwe_headroom_action(policy_input: dict) -> int:
    """Replay the existing BWE-only 0.85-headroom selector from saved input."""
    from_features = policy_input.get("features") if isinstance(policy_input, dict) else None
    if (policy_input.get("observation_abi") != "native_sender_stats_v1"
            or not isinstance(from_features, list) or len(from_features) != 16
            or any(not isinstance(value, (int, float)) or not math.isfinite(value)
                   for value in from_features)):
        raise ValueError("registered BWE baseline input is missing or malformed")
    caps = [150000, 300000, 600000, 1000000, 1600000, 2500000, 4000000]
    observed_cap = from_features[7] * 4000000
    current = next((cap for cap in caps if abs(cap - observed_cap) < 0.001), None)
    if current is None or from_features[9] not in (0, 1):
        raise ValueError("BWE baseline current cap or validity bit is unsupported")
    if from_features[9] == 0:
        return current
    budget = from_features[0] * 4000000 * 0.85
    return next((cap for cap in reversed(caps) if cap <= budget), caps[0])


def load_session_v8(root: Path, trial: dict, protocol: dict) -> dict:
    directory = root / "sessions" / trial["id"]
    summary = read_json(directory / "summary.json")
    frame = read_json(directory / "frame_events.json")
    sender = read_json(directory / "sender_observations.json")
    browser_markers = frame["clock_markers"]
    node_events = [json.loads(line) for line in gzip.open(directory / "events.jsonl.gz", "rt") if line.strip()]
    node_markers = [event for event in node_events if event.get("kind") == "clock_marker"]
    node_by_id = {marker["marker_id"]: marker for marker in node_markers}
    merged = []
    for browser in browser_markers:
        node = node_by_id.get(browser["marker_id"])
        if node is None or browser["browser_send_ms"] != node["browser_send_ms"]:
            raise ValueError(f"marker mismatch in {trial['id']}")
        merged.append({**node, "browser_receive_ms": browser["browser_receive_ms"]})
    if len(merged) != 12:
        raise ValueError(f"expected twelve actual-run clock markers in {trial['id']}")
    clock = validate_markers(merged, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])
    origin, vertices = feasible_polygon(merged)
    if len(vertices) < 3:
        clock["passed"] = False
    if summary.get("connection") != "connected" or not summary.get("native_rtc"):
        raise ValueError(f"native RTC session did not qualify: {trial['id']}")

    condition = trial["condition"]
    expected_policy = protocol["conditions"][condition]["policy"]
    holds = extract_holds(sender, frame["phase_windows"])
    if len(holds) != 6 or any(hold.get("phase") is None for hold in holds):
        raise ValueError(f"complete six-epoch phase coverage missing in {trial['id']}")
    decisions = sender.get("decisions", [])
    assigned = [decision for decision in decisions
                if isinstance(decision.get("actuator_assignment"), dict)]
    mismatched = []
    epoch_assignments = {}
    for decision in assigned:
        assignment = decision["actuator_assignment"]
        epoch = assignment.get("epoch")
        if not isinstance(epoch, int) or not 0 <= epoch < 6:
            mismatched.append(decision.get("step_id"))
            continue
        epoch_assignments.setdefault(epoch, assignment)
        proposed = decision.get("proposed_action", {})
        actual = decision.get("actuation_readback", {})
        requested = assignment.get("requested_bps")
        if (not isinstance(requested, int) or proposed.get("encoder_max_bitrate_bps") != requested
                or actual.get("encoder_max_bitrate_bps") != requested
                or proposed.get("receiver_jitter_buffer_target_ms") != 0
                or actual.get("receiver_jitter_buffer_target_ms") != 0):
            mismatched.append(decision.get("step_id"))
        if condition == "fixed065":
            base = assignment.get("base_bwe_bps")
            expected = (max(150000, min(4000000, math.floor(0.65 * base + 0.5)))
                        if isinstance(base, (int, float)) and math.isfinite(base) and base > 0 else None)
            if (assignment.get("ratio") != 0.65 or requested != expected
                    or assignment.get("abi") != "native_range_pilot_v1"):
                mismatched.append(decision.get("step_id"))
        else:
            if (assignment.get("abi") != "native_bwe_cap_hold_v1"
                    or assignment.get("policy") != "bwe-headroom-085"):
                mismatched.append(decision.get("step_id"))
            if decision.get("sample_ms") == assignment.get("assignment_ms"):
                try:
                    replayed = bwe_headroom_action(decision.get("policy_input", {}))
                except ValueError:
                    replayed = None
                if replayed != requested:
                    mismatched.append(decision.get("step_id"))
    if len(epoch_assignments) != 6 or not assigned or mismatched:
        raise ValueError(f"registered policy/action/readback replay failed in {trial['id']}: {mismatched}")
    hold_counts = {state: sum(hold["phase"] == state for hold in holds)
                   for state in ("high", "collapse", "recovery")}
    if any(count < 1 for count in hold_counts.values()):
        raise ValueError(f"phase hold coverage incomplete in {trial['id']}: {hold_counts}")

    sources = {source["source_id"]: source for source in frame["sources"]
               if isinstance(source.get("source_id"), int)}
    observations = {}
    for observation in frame["observations"]:
        source_id = observation.get("source_id")
        if isinstance(source_id, int) and observation.get("known_source"):
            observations.setdefault(source_id, []).append(observation)
    hold_rows = []
    for hold in holds:
        lo, hi = hold["window_start_ms"], hold["window_end_ms"]
        selected = [source for source in sources.values()
                    if lo <= source.get("capture_request_ms", -1) < hi]
        on_time = 0
        psnrs = []
        for source in selected:
            valid = [observation for observation in observations.get(source["source_id"], [])
                     if isinstance(observation.get("readback_ms"), (int, float))
                     and 0 <= observation["readback_ms"] - source["capture_request_ms"] <= DEADLINE_MS]
            if valid:
                on_time += 1
                quality = min(valid, key=lambda row: row["readback_ms"]).get("quality") or {}
                if isinstance(quality.get("psnr_db"), (int, float)):
                    psnrs.append(quality["psnr_db"])
        relay = {"guaranteed_packets": 0, "guaranteed_wire_bytes": 0,
                 "guaranteed_dropped_wire_bytes": 0, "possible_packets": 0,
                 "possible_wire_bytes": 0, "possible_dropped_wire_bytes": 0}
        for event in node_events:
            if event.get("kind") != "offer" or event.get("direction") != "a_to_b":
                continue
            event_lo, event_hi = mapped_browser_range(event["at_ms"], origin, vertices)
            possible = event_hi >= lo and event_lo < hi
            guaranteed = event_lo >= lo and event_hi < hi
            if possible:
                relay["possible_packets"] += 1
                relay["possible_wire_bytes"] += event["wire_bytes"]
                if event.get("dropped"):
                    relay["possible_dropped_wire_bytes"] += event["wire_bytes"]
            if guaranteed:
                relay["guaranteed_packets"] += 1
                relay["guaranteed_wire_bytes"] += event["wire_bytes"]
                if event.get("dropped"):
                    relay["guaranteed_dropped_wire_bytes"] += event["wire_bytes"]
        assignment = hold["assignment"]
        hold_rows.append({
            "epoch": hold["epoch"], "policy": assignment.get("policy"),
            "ratio": assignment.get("ratio"), "base_bwe_bps": assignment.get("base_bwe_bps"),
            "requested_bps": assignment.get("requested_bps"), "ack_ms": hold["ack_ms"],
            "window_ms": [lo, hi], "phase": hold["phase"],
            "source_frames": len(selected), "on_time_frames": on_time,
            "on_time_fraction": on_time / len(selected) if selected else None,
            "psnr_frame_count": len(psnrs),
            "mean_ontime_psnr_db": statistics.mean(psnrs) if psnrs else None,
            "psnr_sum_db": sum(psnrs), "relay": relay,
        })
    return {
        "trial": trial["id"], "seed_cluster": trial["seed_cluster"],
        "repetition": trial["repetition"], "condition": condition,
        "policy": expected_policy, "clock_validation": clock,
        "action_validation": {"expected_policy": expected_policy,
            "assigned_decisions": len(assigned), "assigned_epochs": len(epoch_assignments),
            "all_requested_caps_read_back": True, "phase_hold_counts": hold_counts},
        "clock_feasible_vertices": len(vertices), "clock_origin_browser_ms": origin,
        "holds": hold_rows,
    }


def analyze_v8(root: Path, out: Path) -> dict:
    root = root.expanduser().resolve()
    protocol, index = check_capture_integrity(root)
    if any(session["status"] != "sealed" for session in index["sessions"]):
        raise ValueError("all planned V8 sessions must be sealed before analysis")
    if not read_json(root / "clock_report.json").get("passed"):
        raise ValueError("the registered marker-only calibration did not pass")
    trial_map = {trial["id"]: trial for trial in protocol["trials"]}
    results = [load_session_v8(root, trial_map[item["trial"]], protocol)
               for item in index["sessions"]]
    seeds = list(protocol["seed_clusters"]["ids"])
    states = ("high", "collapse", "recovery")
    conditions = ("fixed065", "bwe085")
    metrics = ("on_time_fraction", "mean_ontime_psnr_db", "guaranteed_wire_bytes",
               "possible_wire_bytes", "guaranteed_dropped_wire_bytes", "possible_dropped_wire_bytes")
    session_rows = {}
    for result in results:
        for state in (*states, "all"):
            holds = [hold for hold in result["holds"] if state == "all" or hold["phase"] == state]
            source_frames = sum(hold["source_frames"] for hold in holds)
            on_time_frames = sum(hold["on_time_frames"] for hold in holds)
            psnr_count = sum(hold["psnr_frame_count"] for hold in holds)
            relay = {name: sum(hold["relay"][name] for hold in holds) for name in (
                "guaranteed_wire_bytes", "possible_wire_bytes",
                "guaranteed_dropped_wire_bytes", "possible_dropped_wire_bytes")}
            session_rows[(result["seed_cluster"], result["condition"], result["repetition"], state)] = {
                "source_frames": source_frames, "on_time_frames": on_time_frames,
                "on_time_fraction": on_time_frames / source_frames if source_frames else None,
                "mean_ontime_psnr_db": (sum(hold["psnr_sum_db"] for hold in holds) / psnr_count
                                         if psnr_count else None),
                **relay,
            }
    contrasts = {state: {} for state in (*states, "all")}
    for state in (*states, "all"):
        for metric in metrics:
            per_seed = []
            for seed in seeds:
                arm = {}
                for condition in conditions:
                    rows = [session_rows[(seed, condition, rep, state)]
                            for rep in (0, 1)
                            if (seed, condition, rep, state) in session_rows]
                    vals = [row[metric] for row in rows if row.get(metric) is not None]
                    arm[condition] = mean_or_none(vals)
                if arm["bwe085"] is not None and arm["fixed065"] is not None:
                    per_seed.append(arm["bwe085"] - arm["fixed065"])
            contrasts[state][metric] = interval(per_seed)
    interactions = {}
    for state in ("collapse", "recovery"):
        values = []
        for seed in seeds:
            arm_diffs = {}
            for current_state in ("high", state):
                arm = {}
                for condition in conditions:
                    rows = [session_rows[(seed, condition, rep, current_state)]
                            for rep in (0, 1)
                            if (seed, condition, rep, current_state) in session_rows]
                    arm[condition] = mean_or_none(row["on_time_fraction"] for row in rows)
                if arm["bwe085"] is not None and arm["fixed065"] is not None:
                    arm_diffs[current_state] = arm["bwe085"] - arm["fixed065"]
            if len(arm_diffs) == 2:
                values.append(arm_diffs[state] - arm_diffs["high"])
        interactions[state + "_minus_high_on_time_fraction"] = interval(values)
    clock_pass = all(result["clock_validation"].get("passed") for result in results)
    report = {
        "abi": "native_turn_clock_action_probe_v8_turn_tcp_report",
        "protocol_sha256": sha(root / "protocol.json"),
        "capture_index_sha256": sha(root / "capture_index.json"),
        "clock_report_sha256": sha(root / "clock_report.json"),
        "sealed_sessions": len(results), "seed_clusters": len(seeds),
        "session_clock_validations_all_pass": clock_pass,
        "clock_validation_failures": [row["trial"] for row in results
                                       if not row["clock_validation"].get("passed")],
        "session_results": results,
        "whole_session_policy_contrast_bwe085_minus_fixed065": contrasts["all"],
        "per_state_policy_contrasts_bwe085_minus_fixed065": {
            state: contrasts[state] for state in states},
        "scheduled_state_interactions_on_time_fraction": interactions,
        "analysis_unit": "generated-scene seed cluster; mean of two randomized whole-session repetitions per arm",
        "confidence": 0.95, "degrees_of_freedom": max(0, len(seeds) - 1),
        "limits": [
            "Fresh generated-scene seeds are not independent content families or physical network sources.",
            "One local Chromium build, one loopback userspace relay, one generated scene algorithm, and one capacity schedule.",
            "150 ms pixel-readback and sampled RGB PSNR are delivery/QoE proxies, not human QoE.",
            "Offered relay wire bytes are a local transport-volume proxy; possible events include clock-boundary ambiguity.",
            "No pooling with V3-V7, archived native sessions, recorded-video evidence, or simulator/synthetic-controller evidence.",
            "The existing 0.85-BWE headroom rule was evaluated as a fixed baseline; no policy was fit or promoted.",
        ],
    }
    write_json(out, report)
    return report


def micro_draw(seed: int, trial_id: str, epoch: int) -> int:
    payload = f"networkrlcd-native-v9:{seed}:{trial_id}:{epoch}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def load_session_v9(root: Path, trial: dict, protocol: dict) -> dict:
    directory = root / "sessions" / trial["id"]
    summary = read_json(directory / "summary.json")
    frame = read_json(directory / "frame_events.json")
    sender = read_json(directory / "sender_observations.json")
    browser = frame["clock_markers"]
    node_events = [json.loads(line) for line in gzip.open(directory / "events.jsonl.gz", "rt") if line.strip()]
    node_by_id = {row["marker_id"]: row for row in node_events if row.get("kind") == "clock_marker"}
    markers = []
    for item in browser:
        row = node_by_id.get(item["marker_id"])
        if row is None or row["browser_send_ms"] != item["browser_send_ms"]:
            raise ValueError(f"sender/relay marker mismatch in {trial['id']}")
        markers.append({**row, "browser_receive_ms": item["browser_receive_ms"]})
    if len(markers) != 12:
        raise ValueError(f"expected twelve actual-run clock markers in {trial['id']}")
    clock = validate_markers(markers, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])
    origin, vertices = feasible_polygon(markers)
    if len(vertices) < 3:
        clock["passed"] = False
    if summary.get("connection") != "connected" or not summary.get("native_rtc"):
        raise ValueError(f"native RTC session did not qualify: {trial['id']}")

    holds = extract_holds(sender, frame["phase_windows"])
    if len(holds) != 6 or any(hold.get("phase") is None for hold in holds):
        raise ValueError(f"complete six-epoch phase coverage missing in {trial['id']}")
    assigned = [decision for decision in sender.get("decisions", [])
                if isinstance(decision.get("actuator_assignment"), dict)]
    epoch_assignments = {}
    epoch_starts = 0
    mismatched = []
    random_seed = protocol["randomization"]["seed"]
    threshold = protocol["randomization"]["state_threshold_bps"]
    for decision in assigned:
        assignment = decision["actuator_assignment"]
        epoch = assignment.get("epoch")
        if (not isinstance(epoch, int) or not 0 <= epoch < 6
                or assignment.get("abi") != "native_micro_randomized_ratio_v1"):
            mismatched.append(decision.get("step_id"))
            continue
        epoch_assignments.setdefault(epoch, assignment)
        requested = assignment.get("requested_bps")
        proposed = decision.get("proposed_action", {})
        actual = decision.get("actuation_readback", {})
        if (not isinstance(requested, int) or proposed.get("encoder_max_bitrate_bps") != requested
                or actual.get("encoder_max_bitrate_bps") != requested
                or proposed.get("receiver_jitter_buffer_target_ms") != 0
                or actual.get("receiver_jitter_buffer_target_ms") != 0
                or assignment.get("propensity") != 0.5):
            mismatched.append(decision.get("step_id"))
        if decision.get("sample_ms") == assignment.get("assignment_ms"):
            epoch_starts += 1
            draw = micro_draw(random_seed, trial["id"], epoch)
            ratio = 1.05 if draw & 1 else 0.65
            base_bwe = assignment.get("base_bwe_bps")
            policy_input = decision.get("policy_input", {})
            features = policy_input.get("features") if isinstance(policy_input, dict) else None
            observation_bwe = (features[0] * 4000000
                               if policy_input.get("observation_abi") == "native_sender_stats_v1"
                               and isinstance(features, list) and len(features) == 16
                               and isinstance(features[0], (int, float)) else None)
            expected_cap = (max(150000, min(4000000, math.floor(ratio * base_bwe + 0.5)))
                            if isinstance(base_bwe, (int, float)) and math.isfinite(base_bwe)
                            and base_bwe > 0 else None)
            state_bin = "bwe_lt_500k" if base_bwe < threshold else "bwe_ge_500k"
            if (assignment.get("trial_id") != trial["id"]
                    or assignment.get("randomization_seed") != random_seed
                    or assignment.get("draw_uint32") != draw
                    or assignment.get("arm") != (draw & 1)
                    or assignment.get("ratio") != ratio
                    or assignment.get("state_bin") != state_bin
                    or observation_bwe is None or abs(observation_bwe - base_bwe) > 0.01
                    or requested != expected_cap):
                mismatched.append(decision.get("step_id"))
    if len(epoch_assignments) != 6 or epoch_starts != 6 or not assigned or mismatched:
        raise ValueError(f"V9 randomized assignment/readback replay failed in {trial['id']}: {mismatched}")

    sources = {row["source_id"]: row for row in frame["sources"]
               if isinstance(row.get("source_id"), int)}
    observations = {}
    for row in frame["observations"]:
        source_id = row.get("source_id")
        if isinstance(source_id, int) and row.get("known_source"):
            observations.setdefault(source_id, []).append(row)
    hold_rows = []
    for hold in holds:
        lo, hi = hold["window_start_ms"], hold["window_end_ms"]
        selected = [row for row in sources.values()
                    if lo <= row.get("capture_request_ms", -1) < hi]
        on_time, psnrs = 0, []
        for source in selected:
            valid = [row for row in observations.get(source["source_id"], [])
                     if isinstance(row.get("readback_ms"), (int, float))
                     and 0 <= row["readback_ms"] - source["capture_request_ms"] <= DEADLINE_MS]
            if valid:
                on_time += 1
                quality = min(valid, key=lambda row: row["readback_ms"]).get("quality") or {}
                if isinstance(quality.get("psnr_db"), (int, float)):
                    psnrs.append(quality["psnr_db"])
        relay = {"guaranteed_packets": 0, "guaranteed_wire_bytes": 0,
                 "guaranteed_dropped_wire_bytes": 0, "possible_packets": 0,
                 "possible_wire_bytes": 0, "possible_dropped_wire_bytes": 0}
        for event in node_events:
            if event.get("kind") != "offer" or event.get("direction") != "a_to_b":
                continue
            event_lo, event_hi = mapped_browser_range(event["at_ms"], origin, vertices)
            possible = event_hi >= lo and event_lo < hi
            guaranteed = event_lo >= lo and event_hi < hi
            if possible:
                relay["possible_packets"] += 1
                relay["possible_wire_bytes"] += event["wire_bytes"]
                if event.get("dropped"):
                    relay["possible_dropped_wire_bytes"] += event["wire_bytes"]
            if guaranteed:
                relay["guaranteed_packets"] += 1
                relay["guaranteed_wire_bytes"] += event["wire_bytes"]
                if event.get("dropped"):
                    relay["guaranteed_dropped_wire_bytes"] += event["wire_bytes"]
        assignment = hold["assignment"]
        hold_rows.append({
            "epoch": hold["epoch"], "ratio": assignment["ratio"],
            "state_bin": assignment["state_bin"], "base_bwe_bps": assignment["base_bwe_bps"],
            "requested_bps": assignment["requested_bps"], "propensity": assignment["propensity"],
            "ack_ms": hold["ack_ms"], "window_ms": [lo, hi], "phase": hold["phase"],
            "source_frames": len(selected), "on_time_frames": on_time,
            "on_time_fraction": on_time / len(selected) if selected else None,
            "psnr_frame_count": len(psnrs), "mean_ontime_psnr_db": statistics.mean(psnrs) if psnrs else None,
            "psnr_sum_db": sum(psnrs), "relay": relay,
        })
    return {
        "trial": trial["id"], "seed_cluster": trial["seed_cluster"],
        "repetition": trial["repetition"], "clock_validation": clock,
        "action_validation": {"assigned_decisions": len(assigned), "assigned_epochs": len(epoch_assignments),
            "randomization_epoch_starts_replayed": epoch_starts,
            "all_random_draws_and_cap_readbacks_match": True},
        "clock_feasible_vertices": len(vertices), "clock_origin_browser_ms": origin,
        "holds": hold_rows,
    }


def analyze_v9(root: Path, out: Path) -> dict:
    root = root.expanduser().resolve()
    protocol, index = check_capture_integrity(root)
    if any(row["status"] != "sealed" for row in index["sessions"]):
        raise ValueError("all V9 sessions must be sealed before action analysis")
    if not read_json(root / "clock_report.json").get("passed"):
        raise ValueError("registered marker-only clock calibration failed")
    trials = {trial["id"]: trial for trial in protocol["trials"]}
    sessions = [load_session_v9(root, trials[item["trial"]], protocol) for item in index["sessions"]]
    seeds = list(protocol["seed_clusters"]["ids"])
    states = ("bwe_lt_500k", "bwe_ge_500k")
    ratios = (0.65, 1.05)
    cell = {}
    for seed in seeds:
        for state in states:
            for ratio in ratios:
                rows = [hold for session in sessions if session["seed_cluster"] == seed
                        for hold in session["holds"]
                        if hold["state_bin"] == state and hold["ratio"] == ratio]
                source_frames = sum(row["source_frames"] for row in rows)
                on_time_frames = sum(row["on_time_frames"] for row in rows)
                psnr_count = sum(row["psnr_frame_count"] for row in rows)
                relay_sum = sum(row["relay"]["guaranteed_wire_bytes"] for row in rows)
                cell[(seed, state, ratio)] = {
                    "hold_windows": len(rows), "source_frames": source_frames,
                    "on_time_frames": on_time_frames,
                    "on_time_fraction": on_time_frames / source_frames if source_frames else None,
                    "mean_ontime_psnr_db": (sum(row["psnr_sum_db"] for row in rows) / psnr_count
                                             if psnr_count else None),
                    "mean_guaranteed_wire_bytes_per_window": relay_sum / len(rows) if rows else None,
                    "total_guaranteed_dropped_wire_bytes": sum(row["relay"]["guaranteed_dropped_wire_bytes"] for row in rows),
                }
    minimum_holds = protocol["analysis"]["min_hold_windows_per_seed_state_action_cell"]
    complete = [seed for seed in seeds if all(
        cell[(seed, state, ratio)]["hold_windows"] >= minimum_holds
        for state in states for ratio in ratios)]
    coverage = {"minimum_hold_windows_per_cell": minimum_holds,
        "complete_seed_clusters": complete, "complete_seed_cluster_count": len(complete),
        "per_seed_cell_hold_windows": {str(seed): {
            state: {str(ratio): cell[(seed, state, ratio)]["hold_windows"] for ratio in ratios}
            for state in states} for seed in seeds},
        "primary_estimable": len(complete) >= protocol["analysis"]["minimum_complete_seed_clusters"]}

    def paired_effects(metric: str):
        by_state = {state: [] for state in states}
        interaction = []
        for seed in complete:
            effects = {}
            for state in states:
                low = cell[(seed, state, 0.65)].get(metric)
                high = cell[(seed, state, 1.05)].get(metric)
                effects[state] = high - low if low is not None and high is not None else None
                if effects[state] is not None:
                    by_state[state].append(effects[state])
            if effects["bwe_ge_500k"] is not None and effects["bwe_lt_500k"] is not None:
                interaction.append(effects["bwe_ge_500k"] - effects["bwe_lt_500k"])
        return {state: interval(values) for state, values in by_state.items()}, interval(interaction)

    outcomes = {}
    for metric in ("on_time_fraction", "mean_ontime_psnr_db", "mean_guaranteed_wire_bytes_per_window"):
        by_state, interaction = paired_effects(metric)
        outcomes[metric] = {"action_effect_105_minus_065_by_bwe_state": by_state,
                            "interaction_high_bwe_minus_low_bwe": interaction}
    clock_pass = all(session["clock_validation"].get("passed") for session in sessions)
    report = {
        "abi": "native_turn_clock_action_probe_v9_turn_tcp_report",
        "protocol_sha256": sha(root / "protocol.json"),
        "capture_index_sha256": sha(root / "capture_index.json"),
        "clock_report_sha256": sha(root / "clock_report.json"),
        "sealed_sessions": len(sessions), "seed_clusters": len(seeds),
        "session_clock_validations_all_pass": clock_pass,
        "clock_validation_failures": [row["trial"] for row in sessions
                                       if not row["clock_validation"].get("passed")],
        "randomization_replay": {"epoch_starts": sum(row["action_validation"]["randomization_epoch_starts_replayed"] for row in sessions),
            "mismatches": 0, "action_decision_readbacks_all_match": all(
                row["action_validation"]["all_random_draws_and_cap_readbacks_match"] for row in sessions)},
        "coverage": coverage, "state_action_cell_outcomes": {
            str(seed): {state: {str(ratio): cell[(seed, state, ratio)] for ratio in ratios}
                        for state in states} for seed in seeds},
        "action_effects": outcomes,
        "primary_endpoint": "1.05-0.65 on-time contrast at BWE >= 500kbps minus the same contrast at BWE < 500kbps",
        "primary_interaction": outcomes["on_time_fraction"]["interaction_high_bwe_minus_low_bwe"] if coverage["primary_estimable"] else None,
        "analysis_unit": "generated-scene seed cluster; complete four-cell state/action coverage only",
        "confidence": 0.95, "degrees_of_freedom": max(0, len(complete) - 1),
        "controller_fitted_or_promoted": False,
        "limits": [
            "Proximal action effects at an observed sender BWE state do not estimate closed-loop policy value.",
            "The two BWE strata and six short action holds occur under one generated scene algorithm and one local capacity schedule.",
            "The local relay and RGB/deadline metrics are not measured-Internet cost or human QoE.",
            "No pooling with V3-V8, archived native sessions, recorded-video evidence, or simulator/synthetic-controller evidence.",
        ],
    }
    write_json(out, report)
    return report


def load_session_v10(root: Path, trial: dict, protocol: dict) -> dict:
    directory = root / "sessions" / trial["id"]
    summary = read_json(directory / "summary.json")
    frame = read_json(directory / "frame_events.json")
    sender = read_json(directory / "sender_observations.json")
    browser = frame["clock_markers"]
    node_events = [json.loads(line) for line in gzip.open(directory / "events.jsonl.gz", "rt") if line.strip()]
    node_by_id = {row["marker_id"]: row for row in node_events if row.get("kind") == "clock_marker"}
    markers = []
    for item in browser:
        row = node_by_id.get(item["marker_id"])
        if row is None or row["browser_send_ms"] != item["browser_send_ms"]:
            raise ValueError(f"sender/relay marker mismatch in {trial['id']}")
        markers.append({**row, "browser_receive_ms": item["browser_receive_ms"]})
    if len(markers) != 12:
        raise ValueError(f"expected twelve actual-run clock markers in {trial['id']}")
    clock = validate_markers(markers, [0, 1, 3, 4, 6, 7, 9, 11], [2, 5, 8, 10])
    if not clock.get("passed"):
        raise ValueError(f"per-hold sender/relay joins require a passing actual-run clock map: {trial['id']}")
    origin, vertices = feasible_polygon(markers)
    if len(vertices) < 3:
        raise ValueError(f"actual-run clock feasible region is not bounded: {trial['id']}")
    if summary.get("connection") != "connected" or not summary.get("native_rtc"):
        raise ValueError(f"native RTC session did not qualify: {trial['id']}")

    condition = trial["condition"]
    if condition not in ("fixed065", "bwe_threshold"):
        raise ValueError(f"unregistered V10 condition in {trial['id']}")
    holds = extract_holds(sender, frame["phase_windows"])
    if len(holds) != 6 or any(hold.get("phase") is None for hold in holds):
        raise ValueError(f"complete six-epoch phase coverage missing in {trial['id']}")
    assigned = [decision for decision in sender.get("decisions", [])
                if isinstance(decision.get("actuator_assignment"), dict)]
    epoch_assignments = {}
    epoch_starts = 0
    mismatched = []
    threshold = protocol["policy_rule"]["state_threshold_bps"]
    for decision in assigned:
        assignment = decision["actuator_assignment"]
        epoch = assignment.get("epoch")
        if (not isinstance(epoch, int) or not 0 <= epoch < 6
                or assignment.get("abi") != "native_bwe_threshold_policy_v1"):
            mismatched.append(decision.get("step_id"))
            continue
        epoch_assignments.setdefault(epoch, assignment)
        requested = assignment.get("requested_bps")
        proposed = decision.get("proposed_action", {})
        actual = decision.get("actuation_readback", {})
        base_bwe = assignment.get("base_bwe_bps")
        state_bin = ("bwe_lt_500k" if isinstance(base_bwe, (int, float)) and base_bwe < threshold
                     else "bwe_ge_500k")
        valid_bwe = (isinstance(base_bwe, (int, float)) and math.isfinite(base_bwe) and base_bwe > 0)
        ratio = (0.65 if condition == "fixed065" or base_bwe < threshold else 1.05) if valid_bwe else None
        expected_cap = (max(150000, min(4000000, math.floor(ratio * base_bwe + 0.5)))
                        if isinstance(base_bwe, (int, float)) and math.isfinite(base_bwe)
                        and base_bwe > 0 else None)
        features = (decision.get("policy_input") or {}).get("features")
        policy_input = decision.get("policy_input") or {}
        observation_bwe = (features[0] * 4000000
                           if policy_input.get("observation_abi") == "native_sender_stats_v1"
                           and isinstance(features, list) and len(features) == 16
                           and isinstance(features[0], (int, float)) else None)
        if (assignment.get("policy") != condition or assignment.get("state_bin") != state_bin
                or assignment.get("ratio") != ratio or observation_bwe is None
                or not isinstance(base_bwe, (int, float)) or abs(observation_bwe - base_bwe) > 0.01
                or requested != expected_cap
                or proposed.get("encoder_max_bitrate_bps") != requested
                or actual.get("encoder_max_bitrate_bps") != requested
                or proposed.get("receiver_jitter_buffer_target_ms") != 0
                or actual.get("receiver_jitter_buffer_target_ms") != 0):
            mismatched.append(decision.get("step_id"))
        if decision.get("sample_ms") == assignment.get("assignment_ms"):
            epoch_starts += 1
    if len(epoch_assignments) != 6 or epoch_starts != 6 or not assigned or mismatched:
        raise ValueError(f"V10 policy/cap/readback replay failed in {trial['id']}: {mismatched}")

    sources = {row["source_id"]: row for row in frame["sources"]
               if isinstance(row.get("source_id"), int)}
    observations = {}
    for row in frame["observations"]:
        source_id = row.get("source_id")
        if isinstance(source_id, int) and row.get("known_source"):
            observations.setdefault(source_id, []).append(row)
    hold_rows = []
    for hold in holds:
        lo, hi = hold["window_start_ms"], hold["window_end_ms"]
        selected = [row for row in sources.values()
                    if lo <= row.get("capture_request_ms", -1) < hi]
        on_time, psnrs = 0, []
        for source in selected:
            valid = [row for row in observations.get(source["source_id"], [])
                     if isinstance(row.get("readback_ms"), (int, float))
                     and 0 <= row["readback_ms"] - source["capture_request_ms"] <= DEADLINE_MS]
            if valid:
                on_time += 1
                quality = min(valid, key=lambda row: row["readback_ms"]).get("quality") or {}
                if isinstance(quality.get("psnr_db"), (int, float)):
                    psnrs.append(quality["psnr_db"])
        relay = {"guaranteed_packets": 0, "guaranteed_wire_bytes": 0,
                 "guaranteed_dropped_wire_bytes": 0, "possible_packets": 0,
                 "possible_wire_bytes": 0, "possible_dropped_wire_bytes": 0}
        for event in node_events:
            if event.get("kind") != "offer" or event.get("direction") != "a_to_b":
                continue
            event_lo, event_hi = mapped_browser_range(event["at_ms"], origin, vertices)
            possible = event_hi >= lo and event_lo < hi
            guaranteed = event_lo >= lo and event_hi < hi
            if possible:
                relay["possible_packets"] += 1
                relay["possible_wire_bytes"] += event["wire_bytes"]
                if event.get("dropped"):
                    relay["possible_dropped_wire_bytes"] += event["wire_bytes"]
            if guaranteed:
                relay["guaranteed_packets"] += 1
                relay["guaranteed_wire_bytes"] += event["wire_bytes"]
                if event.get("dropped"):
                    relay["guaranteed_dropped_wire_bytes"] += event["wire_bytes"]
        assignment = hold["assignment"]
        hold_rows.append({
            "epoch": hold["epoch"], "policy": assignment["policy"],
            "state_bin": assignment["state_bin"], "ratio": assignment["ratio"],
            "base_bwe_bps": assignment["base_bwe_bps"],
            "requested_bps": assignment["requested_bps"],
            "ack_ms": hold["ack_ms"], "window_ms": [lo, hi], "phase": hold["phase"],
            "source_frames": len(selected), "on_time_frames": on_time,
            "on_time_fraction": on_time / len(selected) if selected else None,
            "psnr_frame_count": len(psnrs), "mean_ontime_psnr_db": statistics.mean(psnrs) if psnrs else None,
            "psnr_sum_db": sum(psnrs), "relay": relay,
        })
    return {"trial": trial["id"], "seed_cluster": trial["seed_cluster"],
            "repetition": trial["repetition"], "condition": condition,
            "clock_validation": clock,
            "action_validation": {"assigned_decisions": len(assigned),
                "assigned_epochs": len(epoch_assignments), "epoch_starts_replayed": epoch_starts,
                "all_policy_ratios_and_cap_readbacks_match": True},
            "clock_feasible_vertices": len(vertices), "clock_origin_browser_ms": origin,
            "holds": hold_rows}


def analyze_v10(root: Path, out: Path) -> dict:
    root = root.expanduser().resolve()
    protocol, index = check_capture_integrity(root)
    if any(row["status"] != "sealed" for row in index["sessions"]):
        raise ValueError("all V10 sessions must be sealed before policy outcome analysis")
    if not read_json(root / "clock_report.json").get("passed"):
        raise ValueError("registered marker-only clock calibration failed")
    trials = {trial["id"]: trial for trial in protocol["trials"]}
    sessions = [load_session_v10(root, trials[item["trial"]], protocol) for item in index["sessions"]]
    states = ("high", "collapse", "recovery")
    metrics = ("on_time_fraction", "mean_ontime_psnr_db", "guaranteed_wire_bytes",
               "possible_wire_bytes", "guaranteed_dropped_wire_bytes", "possible_dropped_wire_bytes")

    def summarize(rows):
        sources = sum(hold["source_frames"] for hold in rows)
        on_time = sum(hold["on_time_frames"] for hold in rows)
        psnr_count = sum(hold["psnr_frame_count"] for hold in rows)
        return {"hold_windows": len(rows), "source_frames": sources, "on_time_frames": on_time,
                "on_time_fraction": on_time / sources if sources else None,
                "mean_ontime_psnr_db": (sum(hold["psnr_sum_db"] for hold in rows) / psnr_count
                                         if psnr_count else None),
                "guaranteed_wire_bytes": sum(hold["relay"]["guaranteed_wire_bytes"] for hold in rows),
                "possible_wire_bytes": sum(hold["relay"]["possible_wire_bytes"] for hold in rows),
                "guaranteed_dropped_wire_bytes": sum(hold["relay"]["guaranteed_dropped_wire_bytes"] for hold in rows),
                "possible_dropped_wire_bytes": sum(hold["relay"]["possible_dropped_wire_bytes"] for hold in rows)}

    by_session = {}
    for session in sessions:
        all_row = summarize(session["holds"])
        by_session[(session["seed_cluster"], session["condition"], session["repetition"])] = {
            "all": all_row,
            **{state: summarize([hold for hold in session["holds"] if hold["phase"] == state])
               for state in states},
        }

    seed_results = {}
    contrasts = {"all": {metric: [] for metric in metrics},
                 **{state: {metric: [] for metric in metrics} for state in states}}
    for seed in protocol["seed_clusters"]["ids"]:
        policy_rows = {}
        for condition in ("fixed065", "bwe_threshold"):
            repetitions = [by_session[(seed, condition, rep)] for rep in (0, 1)]
            policy_rows[condition] = {}
            for state in ("all", *states):
                policy_rows[condition][state] = {
                    metric: mean_or_none(row[state][metric] for row in repetitions)
                    for metric in metrics}
        for state in ("all", *states):
            for metric in metrics:
                left = policy_rows["bwe_threshold"][state][metric]
                right = policy_rows["fixed065"][state][metric]
                if left is not None and right is not None:
                    contrasts[state][metric].append(left - right)
        seed_results[str(seed)] = policy_rows
    intervals = {state: {metric: interval(values) for metric, values in rows.items()}
                 for state, rows in contrasts.items()}
    clock_pass = all(session["clock_validation"].get("passed") for session in sessions)
    report = {
        "abi": "native_turn_clock_action_probe_v10_turn_tcp_report",
        "protocol_sha256": sha(root / "protocol.json"),
        "capture_index_sha256": sha(root / "capture_index.json"),
        "clock_report_sha256": sha(root / "clock_report.json"),
        "sealed_sessions": len(sessions), "seed_clusters": len(protocol["seed_clusters"]["ids"]),
        "session_clock_validations_all_pass": clock_pass,
        "clock_validation_failures": [row["trial"] for row in sessions
                                       if not row["clock_validation"].get("passed")],
        "action_validation": {
            "epoch_starts": sum(row["action_validation"]["epoch_starts_replayed"] for row in sessions),
            "mismatches": 0,
            "all_policy_ratios_and_cap_readbacks_match": all(
                row["action_validation"]["all_policy_ratios_and_cap_readbacks_match"] for row in sessions)},
        "seed_cluster_policy_outcomes": seed_results,
        "policy_effects_bwe_threshold_minus_fixed065": intervals,
        "primary_endpoint": protocol["analysis"]["primary_endpoint"],
        "primary_effect": intervals["all"]["on_time_fraction"],
        "analysis_unit": "generated-scene seed cluster after averaging two randomized whole-session repetitions per policy",
        "confidence": 0.95, "degrees_of_freedom": len(protocol["seed_clusters"]["ids"]) - 1,
        "outcome_data_read_after_gate": True, "controller_fitted_or_promoted": False,
        "limits": [
            "This is a single fixed threshold rule validation and is not a fitted controller.",
            "The scene algorithm, local TURN relay, and capacity schedule remain one source family.",
            "The 150 ms pixel-readback and sampled RGB PSNR are delivery/QoE proxies, not human QoE.",
            "Relay bytes are local transport-volume measures, not measured-Internet cost.",
            "No pooling with V3-V9, archived native sessions, recorded-video results, or simulator/synthetic-controller evidence.",
        ],
    }
    write_json(out, report)
    return report


def analyze(root: Path, out: Path) -> dict:
    root = root.expanduser().resolve()
    protocol, index = check_capture_integrity(root)
    if any(s["status"] != "sealed" for s in index["sessions"]):
        raise ValueError("all planned sessions must be sealed before outcome analysis")
    clock_report = read_json(root / "clock_report.json")
    if not clock_report.get("passed"):
        raise ValueError("the marker-only calibration did not pass")
    trial_map = {t["id"]: t for t in protocol["trials"]}
    results = [load_session(root, trial_map[s["trial"]], protocol)
               for s in index["sessions"]]
    # Every raw file has been checksum-verified before this point. Preserve per-session failures
    # in the result if a session-specific marker validation fails; do not discard its outcomes.
    state_names = ["high", "collapse", "recovery"]
    metrics = ["on_time_fraction", "mean_ontime_psnr_db", "guaranteed_wire_bytes",
               "possible_wire_bytes", "guaranteed_dropped_wire_bytes", "possible_dropped_wire_bytes"]
    by_session_state = {}
    for result in results:
        key = (result["seed_cluster"], result["condition"], result["repetition"])
        by_session_state[key] = {}
        for state in state_names:
            holds = [h for h in result["holds"] if h["phase"] == state]
            row = {"holds": len(holds)}
            row["on_time_fraction"] = mean_or_none(h["on_time_fraction"] for h in holds)
            row["mean_ontime_psnr_db"] = mean_or_none(h["mean_ontime_psnr_db"] for h in holds)
            for name in metrics[2:]:
                field = name
                row[name] = mean_or_none(h["relay"][field] for h in holds)
            by_session_state[key][state] = row
    contrasts = {}
    for state in state_names:
        contrasts[state] = {}
        for metric in metrics:
            diffs = []
            for seed in range(8):
                arm_values = {}
                for condition in ("level065", "level105"):
                    observations = [by_session_state[(seed, condition, rep)][state][metric]
                                    for rep in range(2)
                                    if (seed, condition, rep) in by_session_state]
                    arm_values[condition] = mean_or_none(observations)
                if arm_values["level065"] is not None and arm_values["level105"] is not None:
                    diffs.append(arm_values["level065"] - arm_values["level105"])
            contrasts[state][metric] = interval(diffs)
    interactions = {}
    for other in ("collapse", "recovery"):
        interactions[other + "_minus_high"] = {}
        for metric in metrics:
            per_seed = []
            for seed in range(8):
                arm_diffs = {}
                for state in ("high", other):
                    arm_values = {}
                    for condition in ("level065", "level105"):
                        vals = [by_session_state[(seed, condition, rep)][state][metric]
                                for rep in range(2) if (seed, condition, rep) in by_session_state]
                        arm_values[condition] = mean_or_none(vals)
                    if arm_values["level065"] is not None and arm_values["level105"] is not None:
                        arm_diffs[state] = arm_values["level065"] - arm_values["level105"]
                if len(arm_diffs) == 2:
                    per_seed.append(arm_diffs[other] - arm_diffs["high"])
            interactions[other + "_minus_high"][metric] = interval(per_seed)
    all_clock_pass = all(r["clock_validation"].get("passed") for r in results)
    report = {
        "abi": "native_clock_action_probe_v1_report",
        "protocol_sha256": sha(root / "protocol.json"),
        "clock_report_sha256": sha(root / "clock_report.json"),
        "capture_index_sha256": sha(root / "capture_index.json"),
        "sealed_sessions": len(results), "seed_clusters": 8,
        "session_clock_validations_all_pass": all_clock_pass,
        "clock_validation_failures": [r["trial"] for r in results if not r["clock_validation"].get("passed")],
        "session_results": results,
        "per_state_action_contrast_065_minus_105": contrasts,
        "action_by_state_interactions": interactions,
        "limits": [
            "Development evidence from one local Chromium build, one loopback userspace relay, one generated scene algorithm, and one capacity schedule.",
            "Eight generated-seed clusters are not eight independent content families or physical network sources.",
            "Sampled RGB PSNR and a 150 ms pixel-readback deadline are proxies, not human QoE.",
            "Relay cost uses validated feasible clock bounds; possible events include boundary-ambiguous offers.",
            "No pooling with V3, V4, V5, archived native sessions, recorded-video evidence, or simulator/synthetic-controller evidence.",
            "No controller was fitted or promoted by this probe.",
        ],
    }
    write_json(out, report)
    return {"sessions": len(results), "all_session_clocks_pass": all_clock_pass,
            "state_contrasts": contrasts, "interactions": interactions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--root", type=Path, required=True)
    p = sub.add_parser("calibrate"); p.add_argument("--root", type=Path, required=True)
    p = sub.add_parser("analyze-clock"); p.add_argument("--root", type=Path, required=True)
    p = sub.add_parser("capture"); p.add_argument("--root", type=Path, required=True)
    p = sub.add_parser("status"); p.add_argument("--root", type=Path, required=True)
    p = sub.add_parser("analyze"); p.add_argument("--root", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.root)
    elif args.command == "calibrate":
        result = calibrate(args.root)
    elif args.command == "analyze-clock":
        result = analyze_clock(args.root)
    elif args.command == "capture":
        result = capture(args.root)
    elif args.command == "status":
        _, index = check_capture_integrity(args.root.expanduser().resolve())
        result = {"planned": len(index["sessions"]), "sealed": sum(x["status"] == "sealed" for x in index["sessions"]),
                  "failed": sum(x["status"] == "failed" for x in index["sessions"])}
    else:
        result = analyze(args.root, args.out)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
