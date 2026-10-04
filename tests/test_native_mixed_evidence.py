from copy import deepcopy

import pytest
from test_native_policy_replay import raw

from media_rl.native_mixed_evidence import validate_mixed_behavior
from media_rl.native_observations import (
    FEATURE_LIMITS,
    FEATURE_NAMES,
    FEATURE_SCALES,
    NATIVE_OBSERVATION_ABI,
    NativeSenderObservationEncoder,
    native_exploration_order,
)


def mixed_evidence(block=250, kind="block"):
    start = 100
    seed = 1701
    order = native_exploration_order(seed)
    encoder = NativeSenderObservationEncoder()
    rows = []
    cap = 4000000
    for i in range(40):
        sample = start + i * 100
        source = raw()
        source.update(encoder_cap_bps=cap, bytes_sent=i * 10000, frames_encoded=i * 3)
        features = encoder.observe(source, sample)
        desired = order[int((sample - start) // block) % 7] if kind == "block" else 1600000
        proposed = dict(encoder_max_bitrate_bps=desired, receiver_jitter_buffer_target_ms=0)
        rows.append(
            dict(
                step_id=i,
                observation=dict(
                    raw_source=source,
                    sample_ms=sample,
                    features=features,
                    observation_abi=NATIVE_OBSERVATION_ABI,
                    feature_names=FEATURE_NAMES,
                ),
                ack_ms=sample + 1,
                changed=cap != desired,
                proposed_action=proposed,
                actuation_readback=dict(
                    native_action_abi="native_encoder_cap_playout_v1", action_count=14, **proposed
                ),
            )
        )
        cap = desired
    header = (
        dict(
            controller="native_mixed_block_exploration_v3",
            seed=seed,
            block_ms=block,
            block_start_ms=start,
            cap_order=order,
            receiver_target_ms=0,
            behavior_is_not_the_learned_policy=True,
        )
        if kind == "block"
        else dict(controller="native_bwe_cap_headroom_v1", headroom=0.85)
    )
    e = dict(
        protocol=dict(
            abi=NATIVE_OBSERVATION_ABI,
            dimension=16,
            feature_names=FEATURE_NAMES,
            feature_scales=FEATURE_SCALES,
            feature_limits=FEATURE_LIMITS,
        ),
        controller=header,
        measurement_start_ms=start,
        measurement_cutoff_ms=4200,
        sampling_errors=[],
        learned_policy=False,
        decisions=rows,
    )
    return e, dict(behavior_kind=kind, behavior_seed=seed, block_ms=block)


@pytest.mark.parametrize("block", [250, 1000, 4000])
def test_declared_mixed_dwell_reconstructs_all_features_and_actions(block):
    e, c = mixed_evidence(block)
    r = validate_mixed_behavior(e, c)
    assert r["verified_decisions"] == 40 and r["observation_dim"] == 16


def test_unchanged_native_bwe_is_a_factual_behavior_not_a_new_expert_oracle():
    e, c = mixed_evidence(kind="bwe")
    assert validate_mixed_behavior(e, c)["verified_action_changes"] == 1


@pytest.mark.parametrize("attack", ["dwell", "seed", "kind", "clock", "cap", "features", "learnt", "order"])
def test_mixed_behavior_and_causal_data_forgery_reject(attack):
    e, c = mixed_evidence()
    e = deepcopy(e)
    if attack == "dwell":
        e["controller"]["block_ms"] = 500
    elif attack == "seed":
        c["behavior_seed"] += 1
    elif attack == "kind":
        c["behavior_kind"] = "bwe"
    elif attack == "clock":
        e["decisions"][0]["ack_ms"] = 99
    elif attack == "cap":
        e["decisions"][1]["proposed_action"]["encoder_max_bitrate_bps"] = 42
    elif attack == "features":
        e["decisions"][1]["observation"]["features"][0] += 1
    elif attack == "learnt":
        e["learned_policy"] = True
    else:
        e["controller"]["cap_order"] = list(reversed(e["controller"]["cap_order"]))
    with pytest.raises(ValueError):
        validate_mixed_behavior(e, c)
