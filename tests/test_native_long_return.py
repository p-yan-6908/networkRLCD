import numpy as np
import pytest
from test_native_dataset import transition

from media_rl.native_dataset import n_step_arrays


def test_twenty_step_return_exact_sum_and_bootstrap_not_a_single_late_label():
    rows = [transition(i, reward=float(i + 1), terminal=i == 24) for i in range(25)]
    r = n_step_arrays(rows, 0.97, 20)
    for i in range(25):
        k = min(20, 25 - i)
        assert r["returns"][i] == pytest.approx(sum(0.97**j * (i + j + 1) for j in range(k)))
        assert r["bootstrap_discounts"][i] == pytest.approx(0.97**20 if i + 20 < 25 else 0)
    assert np.array_equal(r["next_states"][0], rows[19]["next_state"])


@pytest.mark.parametrize("gap", [1, 4, 19])
def test_long_return_stops_at_missing_decision_or_true_terminal_before_other_episode(gap):
    rows = [transition(i) for i in range(gap)] + [
        transition(i, episode="other", reward=99, terminal=i == 25) for i in range(26)
    ]
    r = n_step_arrays(rows, 0.97, 20)
    assert (
        r["returns"][0] == pytest.approx(sum(0.97**j for j in range(gap)))
        and r["bootstrap_discounts"][0] == 0
    )
    rows[gap - 1]["terminal"] = True
    r = n_step_arrays(rows, 0.97, 20)
    assert (
        r["returns"][0] == pytest.approx(sum(0.97**j for j in range(gap)))
        and r["bootstrap_discounts"][0] == 0
    )


@pytest.mark.parametrize("horizon", [True, 0, -1, 20.5])
def test_long_return_horizon_is_a_positive_integer(horizon):
    with pytest.raises(ValueError):
        n_step_arrays([transition(0)], 0.97, horizon)
