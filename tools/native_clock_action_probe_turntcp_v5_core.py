"""Freeze, capture, seal, and analyze the native TURN/TCP clock/action V5 panel."""
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
RECORDER = RTC / "clock_action_episode_v1.mjs"
CALIBRATOR = RTC / "clock_marker_calibrate_v1.mjs"
MODULES = (
    "frame_marker.mjs", "native_actuation.mjs", "sender_observation.mjs",
    "source_quality.mjs", "bwe_cap_controller.mjs", "native_policy.mjs",
    "range_control.mjs", "actuator_control.mjs", "actuator_meter.mjs",
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
T_CRITICAL = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.365}


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
    hashes["plan_document"] = sha(HERE / "docs/NATIVE_CLOCK_ACTION_PROBE_V1_PLAN.md")
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
            "do_not_pool": ["V3", "archived native sessions", "recorded-video captures", "simulator or synthetic-controller results"],
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
    if len(merged) != 9:
        raise ValueError(f"expected 9 in-session markers, found {len(merged)} in {trial['id']}")
    validation = validate_markers(merged, [0, 2, 4, 6, 8], [1, 3, 5, 7])
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
            "No pooling with V3, V4, archived native sessions, recorded-video evidence, or simulator/synthetic-controller evidence.",
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
