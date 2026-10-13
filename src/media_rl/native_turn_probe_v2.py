"""Capture a prospective factual randomized-hold panel with the corrected V2 collector.

The V1 collector, its raw files and its analysis remain frozen. This runner uses
the V2 closing-ledger fix and keeps all full raw peers outside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

from .native_actuator_control import assigned_arm
from .native_turn_probe import summarize, validate_peer

ABI = "native_turn_probe_v2_action_assay_v1"
RATIOS = (0.65, 0.85, 1.05)
TRACE_PATTERNS = {
    "ramp_up": (0.40, 0.55, 0.70, 0.90, 1.15, 1.40),
    "ramp_down": (1.40, 1.15, 0.90, 0.70, 0.55, 0.40),
    "alternating": (1.30, 0.50, 1.30, 0.50, 1.30, 0.50),
    "repeated_dip": (1.20, 0.35, 1.20, 0.35, 1.20, 1.20),
}
TRIAL_ORDER_SEED = 2026101301
EXPLORATION_SEED_BASE = 2200000000


def verify_analysis_spec(spec: dict) -> None:
    analysis = spec.get("analysis", {})
    expected = {
        "fixed_effects": ["peer", "within_peer_phase"],
        "covariance": "peer-clustered CR1 sandwich with t reference on 63 degrees of freedom",
        "contrasts": ["0.85 - 0.65", "1.05 - 0.65", "1.05 - 0.85"],
        "familywise_alpha": 0.05,
        "p_adjustment": "Holm across all six two-sided endpoint-by-contrast tests",
        "all_assigned_rows_retained": True,
    }
    endpoints = analysis.get("endpoints", [])
    if (
        any(analysis.get(key) != value for key, value in expected.items())
        or [(row.get("name"), row.get("weighting")) for row in endpoints]
        != [("actual_payload_ratio", "equal hold"), ("on_time_share", "eligible capture request")]
        or spec.get("analysis_window_ms") != [1800, 2600]
        or spec.get("on_time_deadline_ms") != 150
    ):
        raise ValueError("the prospectively frozen V2 endpoint and inference specification is required")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def verify_source_snapshot(project: Path, spec: dict) -> None:
    for relative, expected in spec["source_sha256"].items():
        source = project / relative
        if not source.is_file() or sha(source) != expected:
            raise ValueError("registered V2 source changed: " + relative)


def verify_trials(spec: dict) -> None:
    trials = spec.get("trials", [])
    if len(trials) != 64:
        raise ValueError("the frozen 64-peer development panel is required")
    design = spec.get("design", {})
    if (
        design.get("scene_seeds") != list(range(201, 209))
        or design.get("trace_patterns_mbps") != {key: list(value) for key, value in TRACE_PATTERNS.items()}
        or design.get("repetitions_per_scene_trace") != 2
        or design.get("phase_duration_ms") != 3000
        or design.get("phases_per_peer") != 6
        or design.get("randomized_trial_order_seed") != TRIAL_ORDER_SEED
        or design.get("minimum_arm_support_per_trace_phase") != 2
        or design.get("requested_action_ratios") != list(RATIOS)
        or design.get("assignment_probability") != 1 / 3
    ):
        raise ValueError("the frozen V2 crossed panel or randomized action design changed")
    scenes, patterns, cells, ids, seeds = set(), set(), set(), set(), set()
    orders = set()
    arm_support: dict[tuple[str, int], dict[int, int]] = {}
    expected_cells = [
        (scene, pattern, repetition)
        for scene in range(201, 209)
        for pattern in TRACE_PATTERNS
        for repetition in (0, 1)
    ]
    expected_order = expected_cells.copy()
    random.Random(TRIAL_ORDER_SEED).shuffle(expected_order)
    seed_by_cell = {cell: EXPLORATION_SEED_BASE + index for index, cell in enumerate(expected_cells)}
    for order, trial in enumerate(trials):
        if trial["id"] in ids or trial["exploration_seed"] in seeds:
            raise ValueError("duplicate trial or randomization seed")
        if trial.get("capture_order") != order:
            raise ValueError("the prospectively randomized capture order changed")
        ids.add(trial["id"])
        seeds.add(trial["exploration_seed"])
        orders.add(trial["capture_order"])
        scenes.add(trial["scene_seed"])
        patterns.add(trial["regime"])
        cells.add((trial["scene_seed"], trial["regime"], trial["repetition"]))
        cell = (trial["scene_seed"], trial["regime"], trial["repetition"])
        if cell != expected_order[order] or trial["exploration_seed"] != seed_by_cell[cell]:
            raise ValueError("the frozen trial permutation or randomization seed assignment changed")
        for epoch in range(6):
            counts = arm_support.setdefault((trial["regime"], epoch), {0: 0, 1: 0, 2: 0})
            counts[assigned_arm(trial["exploration_seed"], epoch)] += 1
        expected = TRACE_PATTERNS.get(trial["regime"])
        if (
            not 201 <= trial["scene_seed"] <= 208
            or trial["repetition"] not in (0, 1)
            or expected is None
            or len(trial["schedule"]) != 6
            or tuple(row[0] for row in trial["schedule"]) != expected
            or tuple(row[1] for row in trial["schedule"])
            != tuple(f"{trial['regime']}-{index}" for index in range(6))
            or sum(row[2] for row in trial["schedule"]) != 18000
            or any(row[2] != 3000 for row in trial["schedule"])
        ):
            raise ValueError("unexpected content seed or capacity-trace schedule")
    if (
        scenes != set(range(201, 209))
        or patterns != set(TRACE_PATTERNS)
        or len(cells) != 64
        or orders != set(range(64))
    ):
        raise ValueError("the registered content/trace/repetition crossing changed")
    for scene in scenes:
        for pattern in patterns:
            if {(scene, pattern, repetition) for repetition in (0, 1)} - cells:
                raise ValueError("incomplete scene-by-trace repeated panel")
    minimum = design["minimum_arm_support_per_trace_phase"]
    if any(min(counts.values()) < minimum for counts in arm_support.values()):
        raise ValueError("the frozen trace-by-phase randomized-action support floor was not met")


def _capture_config(spec: dict, raw: Path, project: Path) -> tuple[dict, dict]:
    runtime = spec["runtime"]
    turn_binary = Path(runtime["turn_binary"]["path"])
    libdir = Path(runtime["turn_library_dir"])
    if (
        not turn_binary.is_file()
        or not os.access(turn_binary, os.X_OK)
        or sha(turn_binary) != runtime["turn_binary"]["sha256"]
        or not libdir.is_dir()
    ):
        raise ValueError("the pinned local TURN runtime is unavailable or changed")
    inherited_libs = os.environ.get("LD_LIBRARY_PATH", "")
    library_path = str(libdir) + (os.pathsep + inherited_libs if inherited_libs else "")
    runtime_env = os.environ.copy()
    runtime_env["LD_LIBRARY_PATH"] = library_path
    turn_version = subprocess.check_output(
        [str(turn_binary), "--version"], text=True, env=runtime_env
    ).strip()
    if turn_version != runtime["turn_version"]:
        raise ValueError("the registered Coturn version changed")
    linked = subprocess.check_output(["ldd", str(turn_binary)], text=True, env=runtime_env)
    linked_libraries = []
    for line in linked.splitlines():
        if "=>" in line:
            name, target = (part.strip() for part in line.split("=>", maxsplit=1))
            target = target.split(" (", maxsplit=1)[0]
            if target == "not found":
                raise ValueError("a registered TURN shared library is unresolved")
            if target.startswith("/"):
                linked_libraries.append({"name": name, "path": target, "sha256": sha(Path(target))})
        else:
            target = line.strip().split(" (", maxsplit=1)[0]
            if target.startswith("/"):
                linked_libraries.append(
                    {"name": Path(target).name, "path": target, "sha256": sha(Path(target))}
                )
    linked_libraries.sort(key=lambda row: (row["name"], row["path"]))
    if linked_libraries != runtime["turn_linked_libraries"]:
        raise ValueError("the registered TURN shared-library inventory changed")
    browser = Path(runtime["chromium_binary"])
    if (
        browser != Path("/usr/bin/chromium")
        or not browser.is_file()
        or not os.access(browser, os.X_OK)
        or sha(browser) != runtime["chromium_sha256"]
    ):
        raise ValueError("the pinned local Chromium executable is unavailable")
    version = subprocess.check_output([str(browser), "--version"], text=True).strip()
    if version != runtime["chromium_version"]:
        raise ValueError("the registered Chromium version changed")
    resolved = raw.expanduser().resolve()
    work = (Path.home() / ".cache" / "networkrlcd" / "working").resolve()
    if resolved.exists() or not resolved.is_relative_to(work) or resolved.is_relative_to(project):
        raise ValueError("fresh raw output must be under the external networkrlcd working cache")
    node_version = subprocess.check_output(["node", "--version"], text=True).strip()
    node = shutil.which("node")
    if (
        node_version != runtime["node_version"]
        or node != runtime["node_binary"]
        or sha(Path(node)) != runtime["node_sha256"]
    ):
        raise ValueError("the registered Node runtime changed")
    return runtime, {
        "raw_capture": str(resolved),
        "chromium_version": version,
        "node_version": node_version,
        "turn_version": turn_version,
        "turn_linked_libraries": linked_libraries,
    }


def _inventory(root: Path) -> dict:
    files = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("raw capture contains an unexpected symlink")
        if path.is_file():
            size = path.stat().st_size
            total += size
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": size,
                    "sha256": sha(path),
                }
            )
    return {
        "abi": ABI + "_local_evidence_inventory",
        "scope": "all V2 action-assay capture files",
        "files": files,
        "total_bytes": total,
        "archive_verified": False,
        "local_cache_is_not_backup": True,
        "raw_bytes_pruned": False,
    }


def _stop_process_group(group_id: int) -> None:
    try:
        os.killpg(group_id, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.killpg(group_id, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.killpg(group_id, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_collector(command: list[str], log, env: dict[str, str], timeout_s: int = 120) -> None:
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    try:
        returncode = process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired as error:
        _stop_process_group(process.pid)
        process.wait()
        raise TimeoutError("bounded native peer capture timed out; child process group stopped") from error
    if returncode != 0:
        _stop_process_group(process.pid)
        raise subprocess.CalledProcessError(returncode, command)


def _runtime_tempdir() -> tempfile.TemporaryDirectory:
    directory = tempfile.TemporaryDirectory(prefix="n2", dir="/tmp")
    if len(directory.name) > 20:
        directory.cleanup()
        raise ValueError("the Chromium runtime temporary path exceeds its socket-safe bound")
    return directory


def capture(spec_path: Path, raw_out: Path, report_out: Path) -> dict:
    project = Path(__file__).resolve().parents[2]
    spec_path, raw_out, report_out = Path(spec_path), Path(raw_out), Path(report_out)
    if report_out.exists():
        raise ValueError("fresh compact report directory required")
    spec = json.loads(spec_path.read_text())
    if (
        spec.get("abi") != ABI
        or spec.get("native_counterfactuals") is not False
        or spec.get("controller_promoted") is not False
        or spec.get("capture_role") != "prospective_development"
    ):
        raise ValueError("the frozen factual-only V2 development specification is required")
    storage = spec.get("storage", {})
    raw_destination = raw_out.expanduser().resolve()
    report_destination = report_out.resolve()
    if (
        raw_destination != Path(storage.get("raw_capture_root", "")).expanduser().resolve()
        or report_destination != (project / storage.get("compact_report_root", "")).resolve()
    ):
        raise ValueError("the one-time frozen V2 output locations changed")
    verify_trials(spec)
    verify_analysis_spec(spec)
    verify_source_snapshot(project, spec)
    runtime, runtime_provenance = _capture_config(spec, raw_out, project)
    raw = Path(runtime_provenance["raw_capture"])
    raw.mkdir(parents=True, exist_ok=False)
    (raw / "spec.json").write_bytes(spec_path.read_bytes())
    runtime_tmp = _runtime_tempdir()

    child_env = os.environ.copy()
    child_env["RLCD_TURN_BINARY"] = runtime["turn_binary"]["path"]
    inherited_libs = child_env.get("LD_LIBRARY_PATH", "")
    child_env["LD_LIBRARY_PATH"] = runtime["turn_library_dir"] + (
        os.pathsep + inherited_libs if inherited_libs else ""
    )
    child_env["TMPDIR"] = runtime_tmp.name
    sessions = []
    collector = project / "benchmarks/native_rtc/turn_probe_v2.mjs"
    try:
        for index, trial in enumerate(spec["trials"], start=1):
            trial_path = raw / (trial["id"] + ".json")
            peer_root = raw / trial["id"]
            log_path = raw / (trial["id"] + ".log")
            trial_path.write_text(json.dumps(trial, sort_keys=True) + "\n")
            print(
                json.dumps(
                    {
                        "stage": "native_turn_v2_capture",
                        "index": index,
                        "total": len(spec["trials"]),
                        "trial": trial["id"],
                    }
                ),
                flush=True,
            )
            with log_path.open("x") as log:
                _run_collector(["node", str(collector), str(peer_root), str(trial_path)], log, child_env)
            peer, assignments = validate_peer(peer_root, trial)
            sessions.append(summarize(peer, assignments, trial))
            print(
                json.dumps(
                    {
                        "stage": "native_turn_v2_peer_sealed",
                        "index": index,
                        "trial": trial["id"],
                        "samples": sessions[-1]["samples"],
                    }
                ),
                flush=True,
            )
    except Exception as error:
        inventory = _inventory(raw)
        inventory["raw_capture"] = str(raw)
        report_out.mkdir(parents=True, exist_ok=False)
        (report_out / "partial-local-evidence-inventory.json").write_text(
            json.dumps(inventory, indent=2, sort_keys=True) + "\n"
        )
        (report_out / "capture-failure.json").write_text(
            json.dumps(
                {
                    "abi": ABI + "_capture_failure",
                    "spec_sha256": sha(raw / "spec.json"),
                    "completed_sessions": [session["trial"]["id"] for session in sessions],
                    "raw_capture": str(raw),
                    "exception_type": type(error).__name__,
                    "message": str(error),
                    "partial_evidence_preserved": True,
                    "controller_promoted": False,
                    "real_network_validation": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        raise
    finally:
        runtime_tmp.cleanup()

    spec_hash = sha(raw / "spec.json")
    holds = [cohort for session in sessions for cohort in session["cohorts"]]
    levels = {}
    for arm, ratio in enumerate(RATIOS):
        own = [row for row in holds if row["arm"] == arm]
        realized = [row["realized_ratio"] for row in own if row["realized_ratio"] is not None]
        levels[str(ratio)] = {
            "assigned_holds": len(own),
            "complete_windows": sum(row["window_complete"] for row in own),
            "mean_realized_ratio": float(np.mean(realized)) if realized else None,
            "on_time_requests": sum(row["on_time_requests"] for row in own),
            "capture_requests": sum(row["capture_requests"] for row in own),
            "aliased_holds": sum(row["clipped_or_aliased"] for row in own),
        }
    report = {
        "abi": ABI + "_report",
        "analysis_status": "prospective_native_development",
        "native_stack_factual": True,
        "native_counterfactuals": False,
        "controller_promoted": False,
        "real_network_validation": False,
        "controller_model_fitted": False,
        "sessions": len(sessions),
        "holds": len(holds),
        "scene_seeds": len({session["trial"]["scene_seed"] for session in sessions}),
        "capacity_trace_patterns": len({session["trial"]["regime"] for session in sessions}),
        "capture_order": [session["trial"]["id"] for session in sessions],
        "samples": sum(session["samples"] for session in sessions),
        "encoded_frames": sum(session["encoded_frames"] for session in sessions),
        "levels": levels,
        "runtime": runtime_provenance,
        "spec_sha256": spec_hash,
        "source_sha256": spec["source_sha256"],
        "raw_capture": str(raw),
        "limitations": spec["claim_limits"],
    }
    (raw / "sessions.json").write_text(json.dumps(sessions, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (raw / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    inventory = _inventory(raw)
    report_out.mkdir(parents=True)
    (report_out / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    (report_out / "sessions.json").write_text(
        json.dumps(sessions, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    inventory["raw_capture"] = str(raw)
    (report_out / "local-evidence-inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(json.dumps({"stage": "native_turn_v2_complete", "report": report}, indent=2, sort_keys=True))
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--raw-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args(argv)
    capture(args.spec, args.raw_out, args.report_out)


if __name__ == "__main__":
    main()
