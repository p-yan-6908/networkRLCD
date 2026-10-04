from copy import deepcopy

import numpy as np
import pytest

from media_rl.native_learning import (
    NativePolicy,
    fit_native_platt,
    native_metadata,
    train_native_bundle,
    validate_native_bundle,
)
from media_rl.networks import MLP


def bundle():
    rng = np.random.default_rng(9)
    q = MLP(64, 4, 7, rng)
    risks = [MLP(71, 4, 1, rng) for _ in range(3)]
    return dict(
        metadata=native_metadata(),
        q_weights=q.to_dict(),
        risk_weights=[r.to_dict() for r in risks],
        platt=[1.0, 0.0],
        risk_cutoff=1.0,
        disagreement_cutoff=1.0,
    )


def test_native_model_schema_rejects_legacy_equal_width_semantics():
    b = bundle()
    assert validate_native_bundle(b)
    for key, value in [
        ("native_observation_abi", "legacy"),
        ("action_count", 42),
        ("input_dim", 16),
        ("native_action_indices", list(range(7))),
    ]:
        bad = deepcopy(b)
        bad["metadata"][key] = value
        with pytest.raises(ValueError):
            validate_native_bundle(bad)


def test_malformed_nonfinite_model_parameters_and_screens_reject():
    b = bundle()
    b["q_weights"][0][0][0] = float("nan")
    with pytest.raises(ValueError):
        validate_native_bundle(b)
    b = bundle()
    b["risk_cutoff"] = float("nan")
    with pytest.raises(ValueError):
        validate_native_bundle(b)


def test_native_prediction_is_valid_zero_target_action_and_finite_scores():
    b = bundle()
    state = np.zeros(64)
    state[-9] = 1
    state[-8] = 1
    state[-7] = 1
    d = NativePolicy(b).decide(state)
    assert (
        d["native_action_index"] == 2 * d["action_index"] + 1 and d["receiver_jitter_buffer_target_ms"] == 0
    )
    assert np.isfinite(d["q_values"]).all() and np.isfinite(d["predicted_frame_miss"]).all()
    with pytest.raises(ValueError):
        NativePolicy(b).decide(np.ones(16))


def test_rejected_candidates_fall_back_to_causal_bwe_control():
    b = bundle()
    b["risk_cutoff"] = 0.0
    state = np.zeros(64)
    state[-16] = 0.5
    state[-9] = 1
    state[-8] = 1
    state[-7] = 1
    d = NativePolicy(b).decide(state)
    assert d["fallback"] and d["encoder_max_bitrate_bps"] == 1600000


def test_weighted_platt_is_finite_and_responds_to_actual_calibration_labels():
    p = np.linspace(0.05, 0.95, 20)
    y = (p > 0.5).astype(float)
    a, b = fit_native_platt(p, y, np.ones(20))
    assert np.isfinite([a, b]).all() and a > 0


def test_fresh_native_learner_keeps_calibration_out_of_actor_fit_and_rejects_overlap():
    def row(i, episode):
        return dict(
            episode_id=episode,
            step_id=i,
            state=np.zeros(64),
            next_state=np.zeros(64),
            action=i % 7,
            reward=(i % 7) / 20,
            terminal=i == 27,
            miss_fraction=(i % 3) / 2,
            label_count=3,
        )

    roles = dict(train=[row(i, "train") for i in range(28)], calibration=[row(i, "cal") for i in range(28)])
    panel = dict(
        reward=dict(gamma=0.97, n_step=3),
        learner=dict(
            model_seed=13,
            hidden=8,
            updates=12,
            batch_size=8,
            learning_rate=0.001,
            cql_alpha=0.05,
            target_update_every=4,
            risk_updates=8,
        ),
    )
    b, report = train_native_bundle(roles, panel, {})
    assert validate_native_bundle(b) and not report["legacy_weights_loaded"] and not report["test_used"]
    assert report["train_episodes"] == 1 and report["calibration_episodes"] == 1
    roles["calibration"][0]["episode_id"] = "train"
    with pytest.raises(ValueError):
        train_native_bundle(roles, panel, {})
