from copy import deepcopy

import numpy as np
import pytest
from test_native_policy_replay import bundle, raw

from media_rl.native_cadence import CADENCE_CONTROLLER, CADENCE_PROTOCOL, native_cadence_action
from media_rl.native_dataset import history_matrix
from media_rl.native_learning import MODEL_ABI, NativePolicy
from media_rl.native_observations import (
    FEATURE_LIMITS,
    FEATURE_NAMES,
    FEATURE_SCALES,
    NATIVE_OBSERVATION_ABI,
    NativeSenderObservationEncoder,
)
from media_rl.native_policy_replay import verify_native_live_evidence
from media_rl.networks import MLP


def cadence_evidence(controller="cadence", fallback=False, unsafe_current=False):
    b = bundle()
    rng = np.random.default_rng(1)
    q = MLP(64, 4, 7, rng)
    for p in q.params:
        p[:] = 0
    q.params[0][55, 0] = 1
    q.params[2][0, 1] = 1
    q.params[2][0, 6] = -1
    q.params[3][:] = -2
    q.params[3][1] = 0
    q.params[3][6] = 1
    b["q_weights"] = q.to_dict()
    b["risk_cutoff"] = 0.4 if fallback else 0.6
    b["disagreement_cutoff"] = 0.2
    risks = []
    for _ in range(3):
        net = MLP(71, 4, 1, rng)
        for p in net.params:
            p[:] = 0
        if unsafe_current:
            net.params[0][70, 0] = 1
            net.params[2][0, 0] = 4
            net.params[3][0] = -2
        risks.append(net.to_dict())
    b["risk_weights"] = risks
    policy = NativePolicy(b)
    encoder = NativeSenderObservationEncoder()
    features = []
    steps = []
    cap = 4000000
    last_changed = 100
    for i in range(30):
        source = raw()
        source.update(encoder_cap_bps=cap, bytes_sent=i * 10000, frames_encoded=i * 3)
        sample = 100 + i * 100
        f = encoder.observe(source, sample)
        features.append(f)
        state = history_matrix(features)[-1]
        decision = policy.decide(state)
        guard = native_cadence_action(
            decision, cap, sample, last_changed, b["risk_cutoff"], b["disagreement_cutoff"]
        )
        proposed = (
            guard["action"]
            if controller == "cadence"
            else dict(
                encoder_max_bitrate_bps=decision["encoder_max_bitrate_bps"]
                if controller == "rlcd"
                else 1600000,
                receiver_jitter_buffer_target_ms=0,
            )
        )
        changed = proposed["encoder_max_bitrate_bps"] != cap
        ack = sample + 1
        steps.append(
            dict(
                step_id=i,
                observation=dict(
                    raw_source=source,
                    sample_ms=sample,
                    features=f,
                    observation_abi=NATIVE_OBSERVATION_ABI,
                    feature_names=FEATURE_NAMES,
                ),
                policy_decision=dict(history=state.tolist(), **decision),
                cadence_decision=guard,
                arbiter_ms=0.1,
                inference_ms=0.1,
                ack_ms=ack,
                proposed_action=proposed,
                actuation_readback=dict(
                    native_action_abi="native_encoder_cap_playout_v1",
                    action_count=14,
                    **proposed,
                    native_jitter_target_supported=True,
                    encoder_cap_is_not_wire_rate=True,
                    FEC_or_encoder_latency_mode_actuated=False,
                ),
                changed=changed,
            )
        )
        cap = proposed["encoder_max_bitrate_bps"]
        if changed:
            last_changed = ack
    header = dict(
        controller=CADENCE_CONTROLLER if controller == "cadence" else MODEL_ABI,
        model_sha256="a" * 64,
        risk_cutoff=b["risk_cutoff"],
        disagreement_cutoff=b["disagreement_cutoff"],
    )
    if controller == "cadence":
        header["dwell_ms"] = 1000
    elif controller == "bwe":
        header = dict(controller="native_bwe_cap_headroom_v1", headroom=0.85)
    return dict(
        protocol=dict(
            abi=NATIVE_OBSERVATION_ABI,
            dimension=16,
            feature_names=FEATURE_NAMES,
            feature_scales=FEATURE_SCALES,
            feature_limits=FEATURE_LIMITS,
        ),
        controller=header,
        model_sha256="a" * 64,
        common_shadow_inference=True,
        common_shadow_cadence=True,
        cadence_protocol=deepcopy(CADENCE_PROTOCOL),
        initial_ack_ms=100,
        learned_policy=controller != "bwe",
        sampling_errors=[],
        measurement_start_ms=100,
        measurement_cutoff_ms=3200,
        decisions=steps,
    ), b


@pytest.mark.parametrize("controller", ["cadence", "rlcd", "bwe"])
def test_live_cadence_and_both_shared_shadow_controls_replay(controller):
    e, b = cadence_evidence(controller)
    r = verify_native_live_evidence(e, b, "a" * 64)
    assert r["verified_cadence_proposals"] == 30 and r["cadence_controller_executed"] is (
        controller == "cadence"
    )
    assert r["total_policy_ms_p99"] == 0.2
    if controller == "cadence":
        assert r["verified_action_changes"] == 2 and r["cadence_held_proposals"] == 28
        assert e["decisions"][10]["cadence_decision"]["elapsed_since_changed_ack_ms"] == 1000
        assert e["decisions"][20]["cadence_decision"]["elapsed_since_changed_ack_ms"] == 999


@pytest.mark.parametrize("emergency", ["fallback", "unsafe_current"])
def test_live_emergency_release_preserves_the_model_screens(emergency):
    e, b = cadence_evidence(**{emergency: True})
    r = verify_native_live_evidence(e, b, "a" * 64)
    assert not e["decisions"][0]["cadence_decision"]["held_by_cadence"] and e["decisions"][0]["changed"]
    assert r["cadence_held_proposals"] == 0


@pytest.mark.parametrize(
    "attack",
    [
        "missing_protocol",
        "changed_dwell",
        "false_common",
        "future_initial_ack",
        "elapsed_reset_on_unchanged_ack",
        "false_hold",
        "unheld_command",
        "forged_safety",
        "bad_timing",
        "boolean_protocol",
    ],
)
def test_native_cadence_live_forgeries_reject(attack):
    e, b = cadence_evidence()
    if attack == "missing_protocol":
        del e["cadence_protocol"]
    elif attack == "changed_dwell":
        e["controller"]["dwell_ms"] = 900
    elif attack == "false_common":
        e["common_shadow_cadence"] = False
    elif attack == "future_initial_ack":
        e["initial_ack_ms"] = 101
    elif attack == "elapsed_reset_on_unchanged_ack":
        e["decisions"][5]["cadence_decision"]["elapsed_since_changed_ack_ms"] = 99
    elif attack == "false_hold":
        e["decisions"][0]["cadence_decision"]["held_by_cadence"] = False
    elif attack == "unheld_command":
        e["decisions"][0]["proposed_action"]["encoder_max_bitrate_bps"] = 300000
    elif attack == "forged_safety":
        e["decisions"][0]["cadence_decision"]["prediction_screen_is_not_safety_certificate"] = False
    elif attack == "bad_timing":
        e["decisions"][0]["arbiter_ms"] = 2
    else:
        e["cadence_protocol"]["current_cap_prediction_screen_required"] = 1
    with pytest.raises((ValueError, KeyError)):
        verify_native_live_evidence(e, b, "a" * 64)
