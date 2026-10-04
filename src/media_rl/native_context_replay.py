"""Independent causal state, both actor, selected action and native readback replay."""

import re

import numpy as np

from media_rl.native_context import CONTEXT_CONTROLLER, CONTEXT_PROTOCOL, NativeContextSwitch
from media_rl.native_dataset import history_matrix
from media_rl.native_learning import NativePolicy
from media_rl.native_observations import (
    CAPS,
    FEATURE_LIMITS,
    FEATURE_NAMES,
    FEATURE_SCALES,
    NATIVE_OBSERVATION_ABI,
    NativeSenderObservationEncoder,
)
from media_rl.native_policy_replay import number


def _inference(actual, expected, state):
    if (
        set(actual) != {"history", *expected}
        or len(actual["history"]) != 64
        or any(not number(a) or abs(a - b) > 1e-10 for a, b in zip(actual["history"], state, strict=True))
    ):
        raise ValueError("noncausal context actor history/schema")
    worst = 0.0
    for name in ["q_values", "predicted_frame_miss", "risk_disagreement"]:
        if len(actual[name]) != 7 or any(not number(a) for a in actual[name]):
            raise ValueError("invalid context actor scores")
        worst = max(worst, float(np.max(np.abs(np.asarray(actual[name]) - expected[name]))))
    if worst > 1e-10:
        raise ValueError("frozen context actor inference mismatch")
    for name in [
        "action_index",
        "native_action_index",
        "encoder_max_bitrate_bps",
        "receiver_jitter_buffer_target_ms",
        "fallback",
    ]:
        if type(actual[name]) is not type(expected[name]) or actual[name] != expected[name]:
            raise ValueError("context actor action/fallback mismatch")
    return worst


def verify_native_context_evidence(evidence, base, long, base_sha, long_sha):
    if (
        any(not re.fullmatch(r"[0-9a-f]{64}", sha) for sha in (base_sha, long_sha))
        or evidence["model_sha256"] != base_sha
        or evidence["shadow_model_sha256"] != long_sha
        or evidence["common_two_model_shadow"] is not True
        or evidence["common_context_shadow"] is not True
        or evidence["common_shadow_inference"] is not True
    ):
        raise ValueError("frozen common context models required")
    if (
        base["risk_weights"] != long["risk_weights"]
        or base["platt"] != long["platt"]
        or base["reward_protocol"]["n_step"] != 3
        or long["reward_protocol"]["n_step"] != 20
        or any(m["risk_cutoff"] != 0.5 or m["disagreement_cutoff"] != 0.2 for m in (base, long))
    ):
        raise ValueError("unchanged short/long risk screens required")
    controller = evidence["controller"]
    condition = controller["condition"]
    header = dict(
        controller=CONTEXT_CONTROLLER,
        condition=condition,
        base_model_sha256=base_sha,
        long_model_sha256=long_sha,
        risk_cutoff=0.5,
        disagreement_cutoff=0.2,
    )
    if (
        condition not in ("context", "rlcd-3step", "rlcd-20step", "bwe")
        or controller != header
        or evidence["learned_policy"] is not (condition != "bwe")
        or evidence["sampling_errors"]
        or evidence["context_protocol"] != CONTEXT_PROTOCOL
        or any(type(evidence["context_protocol"][k]) is not type(v) for k, v in CONTEXT_PROTOCOL.items())
    ):
        raise ValueError("context controller/protocol mismatch")
    p = evidence["protocol"]
    if (
        p["abi"] != NATIVE_OBSERVATION_ABI
        or p["dimension"] != 16
        or tuple(p["feature_names"]) != FEATURE_NAMES
        or tuple(p["feature_scales"]) != FEATURE_SCALES
        or tuple(p["feature_limits"]) != FEATURE_LIMITS
    ):
        raise ValueError("context sender ABI mismatch")
    start = evidence["measurement_start_ms"]
    end = evidence["measurement_cutoff_ms"]
    if not number(start) or not number(end) or start >= end:
        raise ValueError("invalid context window")
    encoder = NativeSenderObservationEncoder()
    policies = [NativePolicy(base), NativePolicy(long)]
    switch = NativeContextSwitch()
    history = []
    last_ack = start
    last_actual = None
    latencies = []
    short_times = []
    long_times = []
    context_times = []
    errors = [0.0, 0.0]
    changes = fallbacks = selected_fallbacks = switches = long_samples = 0
    alarm_counts = {k: 0 for k in ["bwe_drop_under_load", "rtcp_rtt_rise", "packet_send_delay"]}
    for index, row in enumerate(evidence["decisions"]):
        obs = row["observation"]
        raw = obs["raw_source"]
        sample = obs["sample_ms"]
        ack = row["ack_ms"]
        if (
            type(row["step_id"]) is not int
            or row["step_id"] != index
            or not number(sample)
            or not number(ack)
            or not start <= sample <= end
            or not last_ack <= sample <= ack
            or obs["observation_abi"] != NATIVE_OBSERVATION_ABI
            or tuple(obs["feature_names"]) != FEATURE_NAMES
        ):
            raise ValueError("noncausal context observation/ack")
        features = encoder.observe(raw, sample)
        if len(obs["features"]) != 16 or any(
            not number(a) or abs(a - b) > 1e-10 for a, b in zip(obs["features"], features, strict=True)
        ):
            raise ValueError("context sender feature replay mismatch")
        if (
            raw["encoder_cap_bps"] not in CAPS
            or raw["receiver_target_ms"] != 0
            or (last_actual is not None and raw["encoder_cap_bps"] != last_actual["encoder_max_bitrate_bps"])
            or (index == 0 and raw["encoder_cap_bps"] != 4000000)
        ):
            raise ValueError("unacknowledged context actuator discontinuity")
        history.append(features)
        state = history_matrix(history[-4:])[-1]
        expected = [p.decide(state) for p in policies]
        for i, name in enumerate(["policy_decision", "shadow_policy_decision"]):
            errors[i] = max(errors[i], _inference(row[name], expected[i], state))
        if (
            expected[0]["predicted_frame_miss"] != expected[1]["predicted_frame_miss"]
            or expected[0]["risk_disagreement"] != expected[1]["risk_disagreement"]
        ):
            raise ValueError("common-history risk screen changed")
        ctx = switch.observe(features, sample, raw["stream_key"])
        if row["context_decision"] != ctx or type(row["context_decision"]["switched"]) is not bool:
            raise ValueError("causal context state replay mismatch")
        for key, value in ctx["alarms"].items():
            alarm_counts[key] += value
        switches += ctx["switched"]
        long_samples += ctx["selected_model"] == "long"
        chosen = (
            expected[1]
            if condition == "rlcd-20step" or condition == "context" and ctx["selected_model"] == "long"
            else expected[0]
        )
        proposed = {k: chosen[k] for k in ["encoder_max_bitrate_bps", "receiver_jitter_buffer_target_ms"]}
        if condition == "bwe":
            proposed = dict(
                encoder_max_bitrate_bps=max(
                    (c for c in CAPS if c <= features[0] * 4000000 * 0.85), default=CAPS[0]
                )
                if features[9] == 1
                else raw["encoder_cap_bps"],
                receiver_jitter_buffer_target_ms=0,
            )
        if row["proposed_action"] != proposed:
            raise ValueError("selected context/conventional proposal mismatch")
        times = [row[k] for k in ["inference_ms", "shadow_inference_ms", "context_ms"]]
        if any(not number(t) or t < 0 for t in times) or sum(times) > ack - sample + 1e-6:
            raise ValueError("invalid combined context inference timing")
        short_times.append(times[0])
        long_times.append(times[1])
        context_times.append(times[2])
        latencies.append(sum(times))
        fallbacks += expected[0]["fallback"]
        selected_fallbacks += chosen["fallback"] if condition != "bwe" else 0
        readback = row["actuation_readback"]
        if (
            readback["native_action_abi"] != "native_encoder_cap_playout_v1"
            or readback["action_count"] != 14
            or any(readback[k] != v for k, v in proposed.items())
            or readback["native_jitter_target_supported"] is not True
            or readback["encoder_cap_is_not_wire_rate"] is not True
            or readback["FEC_or_encoder_latency_mode_actuated"] is not False
        ):
            raise ValueError("actual context command readback mismatch")
        changed = proposed["encoder_max_bitrate_bps"] != raw["encoder_cap_bps"]
        if row["changed"] is not changed:
            raise ValueError("context transition marker mismatch")
        changes += changed
        last_actual = readback
        last_ack = ack
    if len(latencies) < 30:
        raise ValueError("too few context decisions")
    return dict(
        verified_decisions=len(latencies),
        verified_action_changes=changes,
        observation_dim=16,
        history_input_dim=64,
        legacy_checkpoint_transfer=False,
        learnt_policy_compared=condition != "bwe",
        shadow_fallbacks=fallbacks,
        selected_fallbacks=selected_fallbacks,
        inference_ms_p99=float(np.quantile(short_times, 0.99)),
        shadow_inference_ms_p99=float(np.quantile(long_times, 0.99)),
        context_ms_p99=float(np.quantile(context_times, 0.99)),
        total_two_model_ms_p99=float(np.quantile(latencies, 0.99)),
        max_model_score_error=errors[0],
        max_secondary_score_error=errors[1],
        context_switches=switches,
        context_long_samples=long_samples,
        context_alarm_counts=alarm_counts,
        identical_common_history_risk_vectors=True,
        prediction_screen_not_safety_certificate=True,
        online_policy_is_development_only=True,
    )
