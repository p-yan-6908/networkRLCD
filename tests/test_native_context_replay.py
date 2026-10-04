"""Explicit artificial telemetry unit fixtures; not actual browser evidence."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from media_rl.native_context import CONTEXT_CONTROLLER, CONTEXT_PROTOCOL, NativeContextSwitch
from media_rl.native_context_integrity import verify_native_context_integrity
from media_rl.native_dataset import history_matrix
from media_rl.native_learning import NativePolicy
from media_rl.native_observations import (
    FEATURE_LIMITS,
    FEATURE_NAMES,
    FEATURE_SCALES,
    NATIVE_OBSERVATION_ABI,
    NativeSenderObservationEncoder,
)


@pytest.fixture
def evidence():
    models = []
    shas = []
    for p in ["results/native-model-v3/model.json", "results/native-model-v4/model.json"]:
        raw = Path(p).read_bytes()
        models.append(json.loads(raw))
        shas.append(hashlib.sha256(raw).hexdigest())
    policies = [NativePolicy(m) for m in models]
    encoder = NativeSenderObservationEncoder()
    selector = NativeContextSwitch()
    history = []
    rows = []
    cap = 4000000
    for i in range(32):
        now = 100 + i * 100
        raw = dict(
            stream_key="unit",
            bwe_bps=2000000 if i < 5 else 1400000,
            rtcp_rtt_s=0.04 if i < 5 else 0.12,
            rtcp_rtt_measurements=i + 1,
            bytes_sent=i * 30000,
            frames_encoded=i * 3,
            total_encode_s=i * 0.03,
            packets_sent=i * 20,
            total_packet_send_delay_s=i * 0.01,
            encoder_cap_bps=cap,
            receiver_target_ms=0,
        )
        features = encoder.observe(raw, now)
        history.append(features)
        state = history_matrix(history[-4:])[-1]
        outputs = [dict(history=state.tolist(), **p.decide(state)) for p in policies]
        ctx = selector.observe(features, now, "unit")
        chosen = outputs[1] if ctx["selected_model"] == "long" else outputs[0]
        action = {k: chosen[k] for k in ["encoder_max_bitrate_bps", "receiver_jitter_buffer_target_ms"]}
        actual = dict(
            **action,
            native_action_abi="native_encoder_cap_playout_v1",
            action_count=14,
            native_jitter_target_supported=True,
            encoder_cap_is_not_wire_rate=True,
            FEC_or_encoder_latency_mode_actuated=False,
        )
        rows.append(
            dict(
                step_id=i,
                observation=dict(
                    observation_abi=NATIVE_OBSERVATION_ABI,
                    feature_names=list(FEATURE_NAMES),
                    features=features,
                    sample_ms=now,
                    raw_source=raw,
                ),
                policy_decision=outputs[0],
                shadow_policy_decision=outputs[1],
                context_decision=ctx,
                inference_ms=0.1,
                shadow_inference_ms=0.1,
                context_ms=0.01,
                proposed_action=action,
                actuation_readback=actual,
                changed=cap != action["encoder_max_bitrate_bps"],
                ack_ms=now + 1,
            )
        )
        cap = action["encoder_max_bitrate_bps"]
    e = dict(
        model_sha256=shas[0],
        shadow_model_sha256=shas[1],
        common_two_model_shadow=True,
        common_context_shadow=True,
        common_shadow_inference=True,
        controller=dict(
            controller=CONTEXT_CONTROLLER,
            condition="context",
            base_model_sha256=shas[0],
            long_model_sha256=shas[1],
            risk_cutoff=0.5,
            disagreement_cutoff=0.2,
        ),
        learned_policy=True,
        sampling_errors=[],
        context_protocol=copy.deepcopy(CONTEXT_PROTOCOL),
        protocol=dict(
            abi=NATIVE_OBSERVATION_ABI,
            dimension=16,
            feature_names=list(FEATURE_NAMES),
            feature_scales=list(FEATURE_SCALES),
            feature_limits=list(FEATURE_LIMITS),
        ),
        measurement_start_ms=100,
        measurement_cutoff_ms=3300,
        decisions=rows,
    )
    return e, *models, *shas


def test_actual_selected_actor_and_acknowledged_readbacks_replay(evidence):
    r = verify_native_context_integrity(*evidence)
    assert r["verified_decisions"] == 32
    assert r["identical_common_history_risk_vectors"]
    assert r["context_switches"] >= 1
    assert r["context_long_samples"] > 0


@pytest.mark.parametrize(
    "attack",
    [
        "selected_actor",
        "shadow_q",
        "raw_oracle",
        "changed",
        "clock",
        "risk_cutoff",
        "timing",
        "alarm_type",
        "boolean_counter",
    ],
)
def test_forged_context_state_scores_action_or_future_input_reject(evidence, attack):
    e, *args = evidence
    e = copy.deepcopy(e)
    step = e["decisions"][7]
    if attack == "selected_actor":
        step["context_decision"]["selected_model"] = "base"
    elif attack == "shadow_q":
        step["shadow_policy_decision"]["q_values"][0] += 1
    elif attack == "raw_oracle":
        step["observation"]["raw_source"]["relay_queue_bytes"] = 0
    elif attack == "changed":
        step["changed"] = not step["changed"]
    elif attack == "clock":
        step["observation"]["sample_ms"] = e["decisions"][6]["ack_ms"] - 1
    elif attack == "risk_cutoff":
        e["controller"]["risk_cutoff"] = 0.6
    elif attack == "timing":
        step["context_ms"] = 5
    elif attack == "alarm_type":
        step["context_decision"]["alarms"]["rtcp_rtt_rise"] = 1
    else:
        step["context_decision"]["consecutive_alarm_samples"] = True
    with pytest.raises(ValueError):
        verify_native_context_integrity(e, *args)
