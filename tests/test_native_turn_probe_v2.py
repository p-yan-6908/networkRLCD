import copy
import random
from pathlib import Path

import pytest

from media_rl.native_turn_action_panel_v2 import _outcomes
from media_rl.native_turn_probe_v2 import (
    TRACE_PATTERNS,
    _runtime_tempdir,
    verify_analysis_spec,
    verify_trials,
)


def registered_spec():
    trials = []
    for scene in range(201, 209):
        for regime, capacities in TRACE_PATTERNS.items():
            for repetition in range(2):
                order = len(trials)
                trials.append(
                    {
                        "id": f"v2-{regime}-{scene}-{repetition}",
                        "scene_seed": scene,
                        "regime": regime,
                        "repetition": repetition,
                        "exploration_seed": 2200000000 + order,
                        "capture_order": order,
                        "schedule": [
                            [capacity, f"{regime}-{index}", 3000] for index, capacity in enumerate(capacities)
                        ],
                    }
                )
    random.Random(2026101301).shuffle(trials)
    for order, trial in enumerate(trials):
        trial["capture_order"] = order
    return {
        "trials": trials,
        "design": {
            "scene_seeds": list(range(201, 209)),
            "trace_patterns_mbps": {key: list(value) for key, value in TRACE_PATTERNS.items()},
            "repetitions_per_scene_trace": 2,
            "phase_duration_ms": 3000,
            "phases_per_peer": 6,
            "randomized_trial_order_seed": 2026101301,
            "minimum_arm_support_per_trace_phase": 2,
            "requested_action_ratios": [0.65, 0.85, 1.05],
            "assignment_probability": 1 / 3,
        },
        "analysis_window_ms": [1800, 2600],
        "on_time_deadline_ms": 150,
        "analysis": {
            "fixed_effects": ["peer", "within_peer_phase"],
            "covariance": "peer-clustered CR1 sandwich with t reference on 63 degrees of freedom",
            "contrasts": ["0.85 - 0.65", "1.05 - 0.65", "1.05 - 0.85"],
            "familywise_alpha": 0.05,
            "p_adjustment": "Holm across all six two-sided endpoint-by-contrast tests",
            "all_assigned_rows_retained": True,
            "endpoints": [
                {"name": "actual_payload_ratio", "weighting": "equal hold"},
                {"name": "on_time_share", "weighting": "eligible capture request"},
            ],
        },
    }


def test_v2_requires_the_complete_crossed_panel_and_frozen_capacity_shapes():
    spec = registered_spec()

    verify_trials(spec)
    verify_analysis_spec(spec)

    changed = copy.deepcopy(spec)
    changed["trials"][0]["schedule"][0][0] += 0.01
    with pytest.raises(ValueError, match="schedule"):
        verify_trials(changed)

    changed = copy.deepcopy(spec)
    changed["trials"][1]["exploration_seed"] = changed["trials"][0]["exploration_seed"]
    with pytest.raises(ValueError, match="duplicate"):
        verify_trials(changed)

    changed = copy.deepcopy(spec)
    changed["analysis"]["familywise_alpha"] = 0.10
    with pytest.raises(ValueError, match="specification"):
        verify_analysis_spec(changed)


def test_v2_frozen_contrast_model_recovers_constant_proximal_effects():
    rows = []
    payload_effect = (0.0, 0.1, 0.25)
    delivery_effect = (0.0, -0.02, 0.04)
    for peer_index in range(64):
        for epoch in range(6):
            arm = (peer_index + epoch) % 3
            rows.append(
                {
                    "peer": f"peer-{peer_index:02d}",
                    "epoch": epoch,
                    "arm": arm,
                    "actual_payload_ratio": (0.2 * peer_index + 0.01 * epoch + payload_effect[arm]),
                    "on_time_share": 0.7 + 0.001 * peer_index + 0.002 * epoch + delivery_effect[arm],
                    "capture_requests": 30 + (peer_index + epoch) % 5,
                }
            )

    results = _outcomes(rows)

    payload = results[0]["contrasts"]
    delivery = results[1]["contrasts"]
    assert [row["estimate"] for row in payload] == pytest.approx([0.1, 0.25, 0.15])
    assert [row["estimate"] for row in delivery] == pytest.approx([-0.02, 0.04, 0.06])
    assert all(row["degrees_of_freedom"] == 63 for group in results for row in group["contrasts"])
    assert all("p_value_holm_all_six" in row for group in results for row in group["contrasts"])


def test_chromium_ephemeral_files_use_a_short_external_runtime_directory():
    with _runtime_tempdir() as runtime_tmp:
        path = Path(runtime_tmp)
        assert path.parent == Path("/tmp")
        assert path.name.startswith("n2")
        assert len(str(path)) <= 20
        assert not path.resolve().is_relative_to(Path.home() / ".cache" / "networkrlcd" / "working")
