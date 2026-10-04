"""Compact-development model invariants; synthetic software is not native gain."""

import copy

import numpy as np
import pytest

from media_rl import native_action_compact_hold_cv as c
from media_rl.native_protocol import write_json


def toy():
    state = np.zeros((24, c.INPUT_DIM))
    state[:, -23 + 7] = 0.075
    cap = np.tile(np.asarray([300000, 450000, 900000]), 8)
    utility = np.tile(np.asarray([0.2, 0.45, 0.8]), 8)
    target = np.column_stack([utility, 1 - utility])
    weight = np.full(24, 12)
    group = np.repeat(np.asarray([f"physical-{i}" for i in range(8)]), 3)
    return state, cap, target, weight, group


def test_projection_is_exact_causal_history_summary_with_no_context_labels():
    history = np.arange(c.INPUT_DIM).reshape(1, 32, 23)
    p = c.project_state(history.reshape(1, -1))
    expected = np.column_stack(
        [history[:, -1], history[:, -8:].mean(axis=1), history.mean(axis=1), history.std(axis=1)]
    )
    assert p.shape == (1, 92) and np.array_equal(p, expected)


@pytest.mark.parametrize(
    "value", [np.zeros((2, 23)), np.zeros(736), np.full((1, 736), np.nan), np.full((1, 736), np.inf)]
)
def test_bad_or_nonfinite_state_projection_fails(value):
    with pytest.raises(ValueError):
        c.project_state(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("role", "calibration"),
        ("cv_folds", 1),
        ("minimum_action_utility_skill", 0),
        ("source_cv_manifest_sha256", "forged"),
        ("reused_training_folds_informed_recipe", False),
    ],
)
def test_contract_cannot_turn_development_into_qualification_or_change_gates(field, value):
    with pytest.raises(ValueError):
        c.validate_config(dict(c.CONFIG, **{field: value}))


@pytest.mark.parametrize(
    "caps", [np.asarray([True] * 24), np.full(24, 450000.0), np.full(24, 400000), np.full(1, 450000)]
)
def test_proposed_input_support_stays_strict_even_in_action_blind_control(caps):
    with pytest.raises(ValueError):
        c.design(toy()[0], caps, True)


def test_blind_design_zeros_actions_without_erasing_sender_state():
    state, cap, *_ = toy()
    a = c.design(state, cap, True)
    b = c.design(state, cap[::-1], True)
    assert np.array_equal(a, b) and np.all(a[:, -3:] == 0)
    assert np.array_equal(a[:, :92], c.project_state(state))


def test_l2_step_regularizes_only_weights_and_does_not_modify_shared_network_code():
    net = c.MLP(95, 8, 2, np.random.default_rng(4))
    before = [p.copy() for p in net.params]
    c.regularized_step(net, np.zeros((2, 95)), np.zeros((2, 2)), 0.001, 0.01)
    assert np.linalg.norm(net.params[0]) < np.linalg.norm(before[0])
    assert np.linalg.norm(net.params[2]) < np.linalg.norm(before[2])
    assert np.array_equal(net.params[1], before[1]) and np.array_equal(net.params[3], before[3])


def test_real_neural_fits_learn_action_signal_and_remain_auxiliary_with_train_only_normalization():
    state, cap, target, weight, group = toy()
    before = [p.copy() for p in (state, cap, target, weight, group)]
    conditional = c.fit_forecaster(state, cap, target, weight, group, 6601)
    blind = c.fit_forecaster(state, cap, target, weight, group, 6601, True)
    cp = c.predict(conditional, state, cap)
    bp = c.predict(blind, state, cap)
    assert np.mean((cp[:, 0] - target[:, 0]) ** 2) < np.mean((bp[:, 0] - target[:, 0]) ** 2) / 4
    assert np.array_equal(c.predict(blind, state, cap), c.predict(blind, state, cap[::-1]))
    assert np.all(np.asarray(blind["weights"][0])[-3:] == 0)
    assert conditional["updates"] == 1200 and conditional["normalization"]["fitted_roles"] == ["train"]
    assert np.allclose(conditional["normalization"]["mean"], c.design(state, cap).mean(axis=0))
    assert (
        not conditional["native_deployment_qualified"] and conditional["neural_forecaster_not_native_actor"]
    )
    assert all(np.array_equal(a, b) for a, b in zip(before, (state, cap, target, weight, group), strict=True))
    broken = copy.deepcopy(conditional)
    broken["normalization"]["scale"][0] = 0
    with pytest.raises(ValueError):
        c.predict(broken, state, cap)


def test_invalid_config_fails_before_source_loading_or_output(tmp_path, monkeypatch):
    def forbidden(*args):
        raise AssertionError("invalid config reached source/fitting")

    monkeypatch.setattr(c, "load_source", forbidden)
    path = tmp_path / "config.json"
    write_json(path, dict(c.CONFIG, role="diagnostic"))
    with pytest.raises(ValueError):
        c.run_compact_hold_cv(path, "unused", tmp_path / "out")
    assert not (tmp_path / "out").exists()
