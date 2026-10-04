"""Opt-in deterministic mixed-dwell/BWE replay; original native verifier unchanged."""

from media_rl.native_observations import (
    CAPS,
    FEATURE_LIMITS,
    FEATURE_NAMES,
    FEATURE_SCALES,
    NATIVE_OBSERVATION_ABI,
    NativeSenderObservationEncoder,
    _number,
    native_exploration_order,
)


def validate_mixed_behavior(evidence, episode):
    controller = evidence["controller"]
    if episode["behavior_kind"] == "bwe":
        if controller["controller"] != "native_bwe_cap_headroom_v1" or controller["headroom"] != 0.85:
            raise ValueError("frozen native BWE behavior required")
    elif episode["behavior_kind"] == "block":
        if (
            controller["controller"] != "native_mixed_block_exploration_v3"
            or controller["seed"] != episode["behavior_seed"]
            or controller["block_ms"] != episode["block_ms"]
            or controller["behavior_is_not_the_learned_policy"] is not True
        ):
            raise ValueError("frozen mixed exploration behavior required")
    else:
        raise ValueError("undeclared native fitting behavior")
    return verify_native_mixed_evidence(evidence)


def verify_native_mixed_evidence(evidence):
    protocol = evidence["protocol"]
    if (
        protocol["abi"] != NATIVE_OBSERVATION_ABI
        or protocol["dimension"] != 16
        or tuple(protocol["feature_names"]) != FEATURE_NAMES
        or tuple(protocol["feature_scales"]) != FEATURE_SCALES
        or tuple(protocol["feature_limits"]) != FEATURE_LIMITS
    ):
        raise ValueError("native feature ABI mismatch")
    if evidence["sampling_errors"] or evidence["learned_policy"] is not False:
        raise ValueError("not an error-free conventional telemetry probe")
    start, cutoff = evidence["measurement_start_ms"], evidence["measurement_cutoff_ms"]
    if not _number(start) or not _number(cutoff) or start >= cutoff:
        raise ValueError("invalid measurement window")
    controller = evidence["controller"]["controller"]
    if controller not in (
        "native_fixed_cap_v1",
        "native_bwe_cap_headroom_v1",
        "native_mixed_block_exploration_v3",
    ):
        raise ValueError("unsupported controller")
    if controller == "native_bwe_cap_headroom_v1" and evidence["controller"]["headroom"] != 0.85:
        raise ValueError("different controller headroom")
    order = None
    if controller == "native_mixed_block_exploration_v3":
        behavior = evidence["controller"]
        order = native_exploration_order(behavior["seed"])
        if (
            behavior["block_ms"] not in (250, 1000, 4000)
            or behavior["block_start_ms"] != start
            or behavior["cap_order"] != order
            or behavior["receiver_target_ms"] != 0
        ):
            raise ValueError("different exploration behavior")
    encoder = NativeSenderObservationEncoder()
    last_actual, last_ack, changes = None, start, 0
    for index, row in enumerate(evidence["decisions"]):
        obs = row["observation"]
        raw, sample, ack = obs["raw_source"], obs["sample_ms"], row["ack_ms"]
        if (
            row["step_id"] != index
            or not _number(sample)
            or not _number(ack)
            or not start <= sample <= cutoff
            or not last_ack <= sample <= ack
        ):
            raise ValueError("noncausal decision timing")
        if obs["observation_abi"] != NATIVE_OBSERVATION_ABI or tuple(obs["feature_names"]) != FEATURE_NAMES:
            raise ValueError("decision observation ABI mismatch")
        expected = encoder.observe(raw, sample)
        if len(obs["features"]) != 16 or any(
            not _number(a) or abs(a - b) > 1e-10 for a, b in zip(obs["features"], expected, strict=True)
        ):
            raise ValueError("native feature reconstruction mismatch")
        if raw["encoder_cap_bps"] not in CAPS or (
            last_actual is not None and raw["encoder_cap_bps"] != last_actual["encoder_max_bitrate_bps"]
        ):
            raise ValueError("unacknowledged cap discontinuity")
        cap = raw["encoder_cap_bps"]
        if controller == "native_bwe_cap_headroom_v1" and expected[9] == 1:
            budget = expected[0] * 4000000 * 0.85
            cap = max((c for c in CAPS if c <= budget), default=CAPS[0])
        if order is not None:
            cap = order[int((sample - start) // evidence["controller"]["block_ms"]) % len(order)]
        target = (
            0
            if controller in ("native_bwe_cap_headroom_v1", "native_mixed_block_exploration_v3")
            else raw["receiver_target_ms"]
        )
        proposed = dict(encoder_max_bitrate_bps=cap, receiver_jitter_buffer_target_ms=target)
        if row["proposed_action"] != proposed:
            raise ValueError("decision differs from declared sender-only controller")
        actual = row["actuation_readback"]
        if (
            actual["native_action_abi"] != "native_encoder_cap_playout_v1"
            or actual["action_count"] != 14
            or actual["encoder_max_bitrate_bps"] != cap
            or actual["receiver_jitter_buffer_target_ms"] != target
        ):
            raise ValueError("native command readback mismatch")
        changed = cap != raw["encoder_cap_bps"] or target != raw["receiver_target_ms"]
        if row["changed"] is not changed:
            raise ValueError("incorrect action transition marker")
        changes += changed
        last_actual, last_ack = actual, ack
    if len(evidence["decisions"]) < 30:
        raise ValueError("too few native sender samples")
    return dict(
        verified_decisions=len(evidence["decisions"]),
        verified_action_changes=changes,
        observation_dim=16,
        history_input_dim=64,
        legacy_checkpoint_transfer=False,
        learnt_policy_compared=False,
    )
