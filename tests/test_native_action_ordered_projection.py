import numpy as np
import pytest

from media_rl import native_action_atomic_value_cv as value
from media_rl import native_action_ordered_projection as ordered
from media_rl.native_protocol import read_json


def test_exact_actual_old_summary_prefix_and_proposal_features_no_new_channels():
    with np.load("results/native-action-atomic-value-cv-v4/train_rows.npz", allow_pickle=False) as z:
        state = z["state"]
        cap = z["cap"]
    old = ordered.original.design(state, cap)
    new = ordered.design(state, cap)
    assert new.shape == (280, 118) and np.isfinite(new).all()
    assert np.array_equal(new[:, :92], old[:, :92]) and np.array_equal(new[:, -3:], old[:, -3:])
    blind = ordered.design(state, cap, True)
    assert np.array_equal(blind[:, :115], new[:, :115]) and (blind[:, -3:] == 0).all()
    assert not any(hasattr(ordered, k) for k in ("fit", "fit_cv", "fit_forecaster", "collect", "predict"))
    assert ordered.CONTRACT["state_dim"] == 736 and not ordered.CONTRACT["native_deployment_qualified"]


def test_two_causal_histories_old_actual_forecasters_indistinguishable_new_projection_distinct():
    state = ordered.temporal_ambiguity_fixture()
    old = ordered.original.project_state(state)
    new = ordered.project_state(state)
    assert np.array_equal(old[0], old[1]) and not np.array_equal(state[0], state[1])
    assert not np.array_equal(new[0], new[1])
    assert ordered.temporal_trends(state)[0, 6] > 0 and ordered.temporal_trends(state)[1, 6] < 0
    m = read_json("results/native-action-atomic-value-cv-v4/models/fold-0-conditional-seed-6601.json")
    for cap in (300000, 450000, 900000):
        p = value.PREDICT(m, state, np.full(2, cap, dtype=np.int64))
        assert np.array_equal(p[0], p[1])


def test_full32_index_OLS_exact_linear_ramp_and_constant_shift_invariance():
    t = np.arange(32, dtype=float) / 31
    slope = np.arange(23, dtype=float)
    h = 4 + t[:, None] * slope
    state = h.reshape(1, 736)
    assert np.allclose(ordered.temporal_trends(state)[0], slope, rtol=0, atol=1e-12)
    assert np.allclose(
        ordered.temporal_trends(state + 100), ordered.temporal_trends(state), rtol=0, atol=1e-12
    )
    assert np.array_equal(ordered.temporal_trends(np.ones((2, 736))), np.zeros((2, 23)))


@pytest.mark.parametrize("case", ["state-width", "state-rank", "state-nan", "cap-float", "cap-illegal"])
def test_exact_original_causal_input_and_proposal_guard_preserved(case):
    state = np.zeros((2, 736))
    cap = np.full(2, 450000, dtype=np.int64)
    if case == "state-width":
        state = state[:, :735]
    elif case == "state-rank":
        state = state.ravel()
    elif case == "state-nan":
        state[0, 0] = np.nan
    elif case == "cap-float":
        cap = cap.astype(float)
    else:
        cap[0] = 400000
    with pytest.raises(ValueError):
        ordered.design(state, cap)
