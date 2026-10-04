from copy import deepcopy

import numpy as np
import pytest

from media_rl.native_dataset import history_matrix
from media_rl.native_learning import NativePolicy, native_metadata
from media_rl.native_observations import NativeSenderObservationEncoder
from media_rl.native_policy_replay import verify_live_capture_associations, verify_native_live_evidence
from media_rl.networks import MLP


def bundle():
    rng = np.random.default_rng(9)
    return dict(
        metadata=native_metadata(),
        q_weights=MLP(64, 4, 7, rng).to_dict(),
        risk_weights=[MLP(71, 4, 1, rng).to_dict() for _ in range(3)],
        platt=[1.0, 0.0],
        risk_cutoff=1.0,
        disagreement_cutoff=1.0,
    )


def raw():
    return dict(
        stream_key="s",
        bwe_bps=2000000,
        rtcp_rtt_s=0.05,
        rtcp_rtt_measurements=1,
        bytes_sent=1000,
        frames_encoded=3,
        total_encode_s=0.003,
        packets_sent=5,
        total_packet_send_delay_s=0.002,
        encoder_cap_bps=4000000,
        receiver_target_ms=0,
    )


def evidence():
    b = bundle()
    e = NativeSenderObservationEncoder()
    p = NativePolicy(b)
    rows = []
    features = []
    cap = 4000000
    for i in range(30):
        source = raw()
        source["encoder_cap_bps"] = cap
        source["receiver_target_ms"] = 0
        source["bytes_sent"] = i * 10000
        source["frames_encoded"] = i * 3
        sample = 100 + i * 100
        f = e.observe(source, sample)
        features.append(f)
        state = history_matrix(features)[-1]
        decision = p.decide(state)
        nextcap = decision["encoder_max_bitrate_bps"]
        actual = dict(
            native_action_abi="native_encoder_cap_playout_v1",
            action_count=14,
            encoder_max_bitrate_bps=nextcap,
            receiver_jitter_buffer_target_ms=0,
            native_jitter_target_supported=True,
            encoder_cap_is_not_wire_rate=True,
            FEC_or_encoder_latency_mode_actuated=False,
        )
        rows.append(
            dict(
                step_id=i,
                observation=dict(
                    raw_source=source,
                    sample_ms=sample,
                    features=f,
                    observation_abi=b["metadata"]["native_observation_abi"],
                    feature_names=b["metadata"]["feature_names"],
                ),
                policy_decision=dict(history=state.tolist(), **decision),
                inference_ms=0.1,
                ack_ms=sample + 1,
                proposed_action=dict(encoder_max_bitrate_bps=nextcap, receiver_jitter_buffer_target_ms=0),
                actuation_readback=actual,
                changed=cap != nextcap,
            )
        )
        cap = nextcap
    from media_rl.native_observations import (
        FEATURE_LIMITS,
        FEATURE_NAMES,
        FEATURE_SCALES,
        NATIVE_OBSERVATION_ABI,
    )

    data = dict(
        protocol=dict(
            abi=NATIVE_OBSERVATION_ABI,
            dimension=16,
            feature_names=FEATURE_NAMES,
            feature_scales=FEATURE_SCALES,
            feature_limits=FEATURE_LIMITS,
        ),
        controller=dict(
            controller="native_rlcd_cql_v1",
            model_sha256="a" * 64,
            risk_cutoff=b["risk_cutoff"],
            disagreement_cutoff=b["disagreement_cutoff"],
        ),
        model_sha256="a" * 64,
        common_shadow_inference=True,
        learned_policy=True,
        sampling_errors=[],
        measurement_start_ms=100,
        measurement_cutoff_ms=3100,
        decisions=rows,
    )
    return data, b


@pytest.mark.parametrize("change", ["future", "clean", "assigned"])
def test_capture_clock_ties_are_quarantined_not_fabricated_clean_labels(change):
    data, _ = evidence()
    steps = data["decisions"]
    initial = dict(encoder_max_bitrate_bps=4000000, receiver_jitter_buffer_target_ms=0)
    source = dict(
        decision_id=None,
        capture_request_ms=steps[0]["ack_ms"],
        action_transition_inflight=True,
        encoder_cap_bps=4000000,
        receiver_target_ms=0,
    )
    result = verify_live_capture_associations([source], steps, initial)
    assert result["quarantined_first_ack_ties"] == 1 and result["associated_requests"] == 0
    if change == "future":
        source["capture_request_ms"] += 0.1
    elif change == "clean":
        source["action_transition_inflight"] = False
    else:
        source.update(decision_id=0, capture_request_ms=steps[1]["ack_ms"])
    with pytest.raises(ValueError):
        verify_live_capture_associations([source], steps, initial)


def test_live_frozen_history_scores_and_actuation_replay():
    data, b = evidence()
    r = verify_native_live_evidence(data, b, "a" * 64)
    assert (
        r["verified_decisions"] == 30 and r["learnt_policy_compared"] and r["max_model_score_error"] < 1e-12
    )


@pytest.mark.parametrize("attack", ["history", "scores", "cap", "clock", "model", "latency", "oracle"])
def test_live_native_corruptions_reject(attack):
    data, b = evidence()
    bad = deepcopy(data)
    row = bad["decisions"][5]
    if attack == "history":
        row["policy_decision"]["history"][0] += 1
    elif attack == "scores":
        row["policy_decision"]["q_values"][0] += 1
    elif attack == "cap":
        row["actuation_readback"]["encoder_max_bitrate_bps"] = 42
    elif attack == "clock":
        row["ack_ms"] = 0
    elif attack == "model":
        bad["model_sha256"] = "b" * 64
    elif attack == "latency":
        row["inference_ms"] = 1000
    else:
        row["observation"]["raw_source"]["true_capacity_mbps"] = 2
    with pytest.raises(ValueError):
        verify_native_live_evidence(bad, b, "a" * 64)
