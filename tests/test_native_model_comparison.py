from copy import deepcopy

import pytest
from test_native_policy_replay import evidence

from media_rl.native_learning import NativePolicy
from media_rl.native_model_comparison import verify_native_model_comparison


def two_model():
    e, b = evidence()
    other = deepcopy(b)
    other["q_weights"][3][0] += 0.1
    e.update(shadow_model_sha256="b" * 64, common_two_model_shadow=True)
    for step in e["decisions"]:
        step.update(
            shadow_policy_decision=dict(
                history=step["policy_decision"]["history"],
                **NativePolicy(other).decide(step["policy_decision"]["history"]),
            ),
            shadow_inference_ms=0.1,
        )
    return e, b, other


def test_both_models_replay_on_actual_same_causal_states_and_owned_clocks():
    e, b, other = two_model()
    r = verify_native_model_comparison(e, b, other, "a" * 64, "b" * 64)
    assert (
        r["verified_secondary_decisions"] == 30
        and r["total_two_model_ms_p99"] == 0.2
        and r["max_secondary_score_error"] == 0
    )


@pytest.mark.parametrize("attack", ["history", "score", "action", "hash", "clock", "common", "extra"])
def test_common_shadow_model_history_identity_score_and_time_forgeries_reject(attack):
    e, b, other = two_model()
    row = e["decisions"][4]
    if attack == "history":
        row["shadow_policy_decision"]["history"] = list(row["shadow_policy_decision"]["history"])
        row["shadow_policy_decision"]["history"][0] += 1
    elif attack == "score":
        row["shadow_policy_decision"]["q_values"][0] += 1
    elif attack == "action":
        row["shadow_policy_decision"]["action_index"] += 1
    elif attack == "hash":
        e["shadow_model_sha256"] = "c" * 64
    elif attack == "clock":
        row["shadow_inference_ms"] = 10
    elif attack == "common":
        e["common_two_model_shadow"] = False
    else:
        row["shadow_policy_decision"]["receiver_pixels"] = 1
    with pytest.raises(ValueError):
        verify_native_model_comparison(e, b, other, "a" * 64, "b" * 64)
