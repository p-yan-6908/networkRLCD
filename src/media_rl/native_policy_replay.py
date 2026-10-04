"""Independent replay of live native RLCD and shared-shadow conventional controls."""

import math
import re

import numpy as np

from media_rl.native_cadence import CADENCE_CONTROLLER, CADENCE_PROTOCOL, native_cadence_action
from media_rl.native_dataset import history_matrix
from media_rl.native_learning import MODEL_ABI, NativePolicy
from media_rl.native_observations import (
    CAPS,
    FEATURE_LIMITS,
    FEATURE_NAMES,
    FEATURE_SCALES,
    NATIVE_OBSERVATION_ABI,
    NativeSenderObservationEncoder,
    verify_native_sender_evidence,
)


def verify_live_capture_associations(sources, steps, initial):
    associated = transition = ties = 0
    for source in sources:
        index = source["decision_id"]
        born = source["capture_request_ms"]
        if type(source["action_transition_inflight"]) is not bool or not number(born):
            raise ValueError("invalid native capture transition/time")
        transition += source["action_transition_inflight"]
        if index is None:
            if born > steps[0]["ack_ms"]:
                raise ValueError("unassociated capture after first acknowledged decision")
            if born == steps[0]["ack_ms"]:
                if (
                    not source["action_transition_inflight"]
                    or source["encoder_cap_bps"] != initial["encoder_max_bitrate_bps"]
                    or source["receiver_target_ms"] != initial["receiver_jitter_buffer_target_ms"]
                ):
                    raise ValueError(
                        "ambiguous capture boundary must remain in-flight and initial/unassigned"
                    )
                ties += 1  # Browser clock equality is not permission to manufacture an action label.
            continue
        if type(index) is not int or not 0 <= index < len(steps):
            raise ValueError("invalid capture decision identity")
        row = steps[index]
        if born < row["ack_ms"] or (index + 1 < len(steps) and born >= steps[index + 1]["ack_ms"]):
            raise ValueError("noncausal/stale capture action assignment")
        if (
            source["encoder_cap_bps"] != row["actuation_readback"]["encoder_max_bitrate_bps"]
            or source["receiver_target_ms"] != row["actuation_readback"]["receiver_jitter_buffer_target_ms"]
        ):
            raise ValueError("capture/readback action mismatch")
        associated += 1
    return dict(
        associated_requests=associated, transition_requests=transition, quarantined_first_ack_ties=ties
    )


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def verify_native_live_evidence(evidence, bundle, model_sha256):
    if (
        not re.fullmatch(r"[0-9a-f]{64}", model_sha256)
        or evidence["model_sha256"] != model_sha256
        or evidence["common_shadow_inference"] is not True
    ):
        raise ValueError("frozen common native model required")
    policy = NativePolicy(bundle)
    controller = evidence["controller"]["controller"]
    cadence_active = controller == CADENCE_CONTROLLER
    learned = controller in (MODEL_ABI, CADENCE_CONTROLLER)
    shadow_cadence = "cadence_protocol" in evidence
    if cadence_active and not shadow_cadence:
        raise ValueError("cadence controller requires owned clock/shadow protocol")
    if shadow_cadence and (
        evidence["cadence_protocol"] != CADENCE_PROTOCOL
        or any(
            type(evidence["cadence_protocol"][key]) is not type(value)
            for key, value in CADENCE_PROTOCOL.items()
        )
        or evidence.get("common_shadow_cadence") is not True
    ):
        raise ValueError("frozen common cadence protocol required")
    if (
        controller not in (MODEL_ABI, CADENCE_CONTROLLER, "native_fixed_cap_v1", "native_bwe_cap_headroom_v1")
        or evidence["learned_policy"] is not learned
        or evidence["sampling_errors"]
    ):
        raise ValueError("live native controller identity/error mismatch")
    if learned:
        header = dict(
            controller=controller,
            model_sha256=model_sha256,
            risk_cutoff=bundle["risk_cutoff"],
            disagreement_cutoff=bundle["disagreement_cutoff"],
        )
        if cadence_active:
            header["dwell_ms"] = CADENCE_PROTOCOL["dwell_ms"]
        if evidence["controller"] != header:
            raise ValueError("frozen native gate/header mismatch")
    else:
        verify_native_sender_evidence(evidence)
    protocol = evidence["protocol"]
    if (
        protocol["abi"] != NATIVE_OBSERVATION_ABI
        or protocol["dimension"] != 16
        or tuple(protocol["feature_names"]) != FEATURE_NAMES
        or tuple(protocol["feature_scales"]) != FEATURE_SCALES
        or tuple(protocol["feature_limits"]) != FEATURE_LIMITS
    ):
        raise ValueError("native observation protocol mismatch")
    start, cutoff = evidence["measurement_start_ms"], evidence["measurement_cutoff_ms"]
    if not number(start) or not number(cutoff) or start >= cutoff:
        raise ValueError("invalid native clock window")
    last_changed_ack = evidence.get("initial_ack_ms", start)
    if shadow_cadence and (not number(last_changed_ack) or not start <= last_changed_ack <= cutoff):
        raise ValueError("invalid initial owned command acknowledgment")
    encoder = NativeSenderObservationEncoder()
    history = []
    held = 0
    arbiter_latencies = []
    last_actual = None
    last_ack = start
    latencies = []
    fallbacks = changes = 0
    worst = 0.0
    for index, row in enumerate(evidence["decisions"]):
        obs = row["observation"]
        raw = obs["raw_source"]
        sample = obs["sample_ms"]
        ack = row["ack_ms"]
        if (
            row["step_id"] != index
            or not number(sample)
            or not number(ack)
            or not start <= sample <= cutoff
            or not last_ack <= sample <= ack
        ):
            raise ValueError("noncausal live decision")
        if obs["observation_abi"] != NATIVE_OBSERVATION_ABI or tuple(obs["feature_names"]) != FEATURE_NAMES:
            raise ValueError("native decision ABI mismatch")
        features = encoder.observe(raw, sample)
        if len(obs["features"]) != 16 or any(
            not number(a) or abs(a - b) > 1e-10 for a, b in zip(obs["features"], features, strict=True)
        ):
            raise ValueError("native sender feature replay mismatch")
        if (
            raw["encoder_cap_bps"] not in CAPS
            or raw["receiver_target_ms"] != 0
            or (last_actual is not None and raw["encoder_cap_bps"] != last_actual["encoder_max_bitrate_bps"])
        ):
            raise ValueError("unacknowledged live native cap/target discontinuity")
        if shadow_cadence and (
            last_changed_ack > sample or (index == 0 and raw["encoder_cap_bps"] != 4000000)
        ):
            raise ValueError("unacknowledged initial/changed cadence clock")
        history.append(features)
        state = history_matrix(history[-4:])[-1]
        expected = policy.decide(state)
        actual = row["policy_decision"]
        if set(actual) != {"history", *expected}:
            raise ValueError("extra/missing live model fields")
        if len(actual["history"]) != 64 or any(
            not number(a) or abs(a - b) > 1e-10 for a, b in zip(actual["history"], state, strict=True)
        ):
            raise ValueError("noncausal native policy history")
        for name in ["q_values", "predicted_frame_miss", "risk_disagreement"]:
            if len(actual[name]) != 7 or any(not number(a) for a in actual[name]):
                raise ValueError("invalid native model scores")
            error = float(np.max(np.abs(np.asarray(actual[name]) - expected[name])))
            worst = max(worst, error)
            if error > 1e-10:
                raise ValueError("frozen native inference mismatch")
        for name in [
            "action_index",
            "native_action_index",
            "encoder_max_bitrate_bps",
            "receiver_jitter_buffer_target_ms",
            "fallback",
        ]:
            if type(actual[name]) is not type(expected[name]) or actual[name] != expected[name]:
                raise ValueError("frozen native selected action/fallback mismatch")
        latency = row["inference_ms"]
        if not number(latency) or not 0 <= latency <= ack - sample + 1e-6:
            raise ValueError("invalid native inference timing")
        latencies.append(latency)
        fallbacks += expected["fallback"]
        if shadow_cadence:
            guard = native_cadence_action(
                expected,
                raw["encoder_cap_bps"],
                sample,
                last_changed_ack,
                bundle["risk_cutoff"],
                bundle["disagreement_cutoff"],
                CADENCE_PROTOCOL["dwell_ms"],
            )
            actual_guard = row["cadence_decision"]
            if (
                actual_guard != guard
                or type(actual_guard["held_by_cadence"]) is not bool
                or actual_guard["prediction_screen_is_not_safety_certificate"] is not True
            ):
                raise ValueError("cadence decision/changed-ack clock differs from replay")
            held += guard["held_by_cadence"]
            arbiter_latency = row["arbiter_ms"]
            if not number(arbiter_latency) or not 0 <= arbiter_latency <= ack - sample - latency + 1e-6:
                raise ValueError("invalid native arbiter timing")
            arbiter_latencies.append(arbiter_latency)
        if cadence_active:
            proposed = guard["action"]
        elif learned:
            proposed = {
                name: expected[name]
                for name in ["encoder_max_bitrate_bps", "receiver_jitter_buffer_target_ms"]
            }
        elif controller == "native_bwe_cap_headroom_v1" and features[9] == 1:
            proposed = dict(
                encoder_max_bitrate_bps=max(
                    (c for c in CAPS if c <= features[0] * 4000000 * 0.85), default=CAPS[0]
                ),
                receiver_jitter_buffer_target_ms=0,
            )
        else:
            proposed = dict(
                encoder_max_bitrate_bps=raw["encoder_cap_bps"], receiver_jitter_buffer_target_ms=0
            )
        if row["proposed_action"] != proposed:
            raise ValueError("model/conventional proposal differs from native replay")
        readback = row["actuation_readback"]
        if (
            readback["native_action_abi"] != "native_encoder_cap_playout_v1"
            or readback["action_count"] != 14
            or any(readback[name] != value for name, value in proposed.items())
            or readback["native_jitter_target_supported"] is not True
            or readback["encoder_cap_is_not_wire_rate"] is not True
            or readback["FEC_or_encoder_latency_mode_actuated"] is not False
        ):
            raise ValueError("native live command readback mismatch")
        changed = proposed["encoder_max_bitrate_bps"] != raw["encoder_cap_bps"]
        if row["changed"] is not changed:
            raise ValueError("live transition marker mismatch")
        changes += changed
        if changed:
            last_changed_ack = ack
        last_actual = readback
        last_ack = ack
    if len(latencies) < 30:
        raise ValueError("too few live native decisions")
    result = dict(
        verified_decisions=len(latencies),
        verified_action_changes=changes,
        observation_dim=16,
        history_input_dim=64,
        legacy_checkpoint_transfer=False,
        learnt_policy_compared=learned,
        shadow_fallbacks=fallbacks,
        inference_ms_p50=float(np.quantile(latencies, 0.5)),
        inference_ms_p99=float(np.quantile(latencies, 0.99)),
        max_model_score_error=worst,
        online_policy_is_development_only=True,
    )
    if shadow_cadence:
        result.update(
            cadence_controller_executed=cadence_active,
            verified_cadence_proposals=len(latencies),
            cadence_held_proposals=held,
            arbiter_ms_p99=float(np.quantile(arbiter_latencies, 0.99)),
            total_policy_ms_p99=float(np.quantile(np.asarray(latencies) + arbiter_latencies, 0.99)),
            prediction_screen_is_not_safety_certificate=True,
        )
    return result
