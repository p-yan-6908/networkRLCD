import numpy as np

from media_rl.native_turn_action_diagnostic import _fit, _holm


def test_peer_and_epoch_fixed_effects_recover_randomized_arm_contrasts():
    rows = []
    action_effect = (0.0, 0.1, 0.25)
    for peer_index in range(12):
        for epoch in range(6):
            arm = (peer_index + epoch) % 3
            rows.append(
                {
                    "peer": f"peer-{peer_index:02d}",
                    "epoch": epoch,
                    "arm": arm,
                    "outcome": 0.2 * peer_index + 0.01 * epoch + action_effect[arm],
                    "requests": 10 + (peer_index + epoch) % 4,
                }
            )

    result = _fit(rows, "outcome", None)
    estimates = [contrast["estimate"] for contrast in result["contrasts"]]

    assert np.allclose(estimates, [0.1, 0.25, 0.15], atol=1e-12, rtol=0)
    assert all(contrast["degrees_of_freedom"] == 11 for contrast in result["contrasts"])


def test_holm_adjustment_is_monotone_and_covers_all_outcomes():
    p_values = [0.04, 0.01, 0.03, 0.005, 0.06, 0.02]
    results = [{"contrasts": [{"p_value_two_sided": value}]} for value in p_values]

    _holm(results)
    adjusted = [result["contrasts"][0]["p_value_holm_all_six"] for result in results]

    assert np.allclose(adjusted, [0.09, 0.05, 0.09, 0.03, 0.09, 0.08])
