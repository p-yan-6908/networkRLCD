"""Run the independently randomized V3 replication of the native TURN assay.

The V2 capture and analysis modules remain byte-frozen. This small adapter
validates a new, prospectively registered seed panel and delegates to their
unchanged capture, audit, and analysis implementations.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from media_rl import native_turn_action_panel_v2, native_turn_probe_v2

SCENES = tuple(range(301, 309))
PATTERNS = native_turn_probe_v2.TRACE_PATTERNS
TRIAL_ORDER_SEED = 2026101302
EXPLORATION_SEED_BASE = 2300000016
RATIOS = native_turn_probe_v2.RATIOS


def verify_v3_trials(spec: dict) -> None:
    trials = spec.get("trials", [])
    if len(trials) != 64:
        raise ValueError("the registered 64-peer V3 replication is required")
    design = spec.get("design", {})
    if (
        design.get("scene_seeds") != list(SCENES)
        or design.get("trace_patterns_mbps") != {key: list(value) for key, value in PATTERNS.items()}
        or design.get("repetitions_per_scene_trace") != 2
        or design.get("phase_duration_ms") != 3000
        or design.get("phases_per_peer") != 6
        or design.get("randomized_trial_order_seed") != TRIAL_ORDER_SEED
        or design.get("minimum_arm_support_per_trace_phase") != 2
        or design.get("requested_action_ratios") != list(RATIOS)
        or design.get("assignment_probability") != 1 / 3
        or design.get("exploration_seed_base") != EXPLORATION_SEED_BASE
    ):
        raise ValueError("the frozen V3 crossed panel or randomized action design changed")

    cells = [
        (scene, pattern, repetition)
        for scene in SCENES
        for pattern in PATTERNS
        for repetition in (0, 1)
    ]
    expected_order = cells.copy()
    random.Random(TRIAL_ORDER_SEED).shuffle(expected_order)
    seed_by_cell = {cell: EXPLORATION_SEED_BASE + index for index, cell in enumerate(cells)}
    seen_cells, seen_ids, seen_seeds = set(), set(), set()
    support: dict[tuple[str, int], dict[int, int]] = {}

    for order, trial in enumerate(trials):
        cell = (trial.get("scene_seed"), trial.get("regime"), trial.get("repetition"))
        if cell != expected_order[order]:
            raise ValueError("the prospectively randomized V3 capture order changed")
        if (
            trial.get("capture_order") != order
            or trial.get("id") != f"turn-v3-{cell[1]}-s{cell[0]}-r{cell[2]}"
            or trial.get("exploration_seed") != seed_by_cell.get(cell)
            or trial.get("id") in seen_ids
            or trial.get("exploration_seed") in seen_seeds
        ):
            raise ValueError("the V3 peer identity or assignment seed changed")
        seen_cells.add(cell)
        seen_ids.add(trial["id"])
        seen_seeds.add(trial["exploration_seed"])

        schedule = trial.get("schedule", [])
        expected = PATTERNS.get(cell[1])
        if (
            expected is None
            or len(schedule) != 6
            or tuple(row[0] for row in schedule) != expected
            or tuple(row[1] for row in schedule) != tuple(f"{cell[1]}-{i}" for i in range(6))
            or any(row[2] != 3000 for row in schedule)
        ):
            raise ValueError("the V3 registered capacity schedule changed")

        for epoch in range(6):
            counts = support.setdefault((cell[1], epoch), {0: 0, 1: 0, 2: 0})
            arm = native_turn_probe_v2.assigned_arm(trial["exploration_seed"], epoch)
            counts[arm] += 1

    if seen_cells != set(cells):
        raise ValueError("the V3 scene-by-trace repeated crossing is incomplete")
    minimum = design["minimum_arm_support_per_trace_phase"]
    if any(min(counts.values()) < minimum for counts in support.values()):
        raise ValueError("the V3 action-support floor is not satisfied")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture")
    capture.add_argument("--spec", type=Path, required=True)
    capture.add_argument("--raw-out", type=Path, required=True)
    capture.add_argument("--report-out", type=Path, required=True)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--spec", type=Path, required=True)
    analyze.add_argument("--capture", type=Path, required=True)
    analyze.add_argument("--compact", type=Path, required=True)
    analyze.add_argument("--inventory", type=Path, required=True)
    analyze.add_argument("--audit", type=Path, required=True)
    analyze.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "capture":
        native_turn_probe_v2.verify_trials = verify_v3_trials
        native_turn_probe_v2.capture(args.spec, args.raw_out, args.report_out)
        return

    native_turn_action_panel_v2.verify_trials = verify_v3_trials
    result = native_turn_action_panel_v2.run(
        args.spec, args.capture, args.compact, args.inventory, args.audit, args.out
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
