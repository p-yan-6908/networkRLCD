"""Independent replay of native sender-only telemetry; not legacy observation ABI."""

import math

NATIVE_OBSERVATION_ABI = "native_sender_stats_v1"
FEATURE_NAMES = (
    "bwe_mbps",
    "rtcp_rtt_ms",
    "rtcp_rtt_observed_age_ms",
    "rtp_payload_send_mbps",
    "encoder_fps",
    "encode_ms_per_frame",
    "packet_send_delay_ms",
    "encoder_cap_mbps",
    "receiver_zero_target",
    "bwe_valid",
    "rtcp_rtt_valid",
    "rtcp_rtt_age_known",
    "byte_interval_valid",
    "encode_interval_valid",
    "packet_delay_valid",
    "interval_s",
)
FEATURE_SCALES = (4, 150, 1000, 4, 30, 1000 / 30, 150, 4, 1, 1, 1, 1, 1, 1, 1, 0.1)
FEATURE_LIMITS = (2.5, 20, 60, 2.5, 2, 30, 100, 1, 1, 1, 1, 1, 1, 1, 1, 100)
RAW_KEYS = (
    "stream_key",
    "bwe_bps",
    "rtcp_rtt_s",
    "rtcp_rtt_measurements",
    "bytes_sent",
    "frames_encoded",
    "total_encode_s",
    "packets_sent",
    "total_packet_send_delay_s",
    "encoder_cap_bps",
    "receiver_target_ms",
)
CAPS = (150000, 300000, 600000, 1000000, 1600000, 2500000, 4000000)


def _number(v):
    return type(v) in (int, float) and math.isfinite(v) and v >= 0


class NativeSenderObservationEncoder:
    def __init__(self):
        self.previous = None
        self.rtt_counter = None
        self.rtt_observed_at = None

    def observe(self, source, now):
        if not _number(now) or set(source) != set(RAW_KEYS):
            raise ValueError("exact sender-only schema and monotonic clock required")
        if not isinstance(source["stream_key"], str) or not source["stream_key"]:
            raise ValueError("sender stream key required")
        for key in RAW_KEYS:
            if (
                key not in ("stream_key", "receiver_target_ms")
                and source[key] is not None
                and not _number(source[key])
            ):
                raise ValueError("invalid sender numeric field")
        cap, target = source["encoder_cap_bps"], source["receiver_target_ms"]
        if not _number(cap) or cap <= 0 or (target is not None and (type(target) is not int or target != 0)):
            raise ValueError("native action readbacks required")
        counter = source["rtcp_rtt_measurements"]
        if counter is not None and (not _number(counter) or int(counter) != counter):
            raise ValueError("integer RTCP counter required")
        previous = self.previous
        if previous and now < previous[0]:
            raise ValueError("sender clock moved backward")
        if previous and previous[1]["stream_key"] != source["stream_key"]:
            previous = None
            self.rtt_counter = self.rtt_observed_at = None
        dt = now - previous[0] if previous else 0
        interval_valid = previous is not None and 0 < dt <= 1000

        def delta(key):
            a, b = source[key], previous[1][key] if previous else None
            return a - b if interval_valid and _number(a) and _number(b) and a >= b else None

        byte, frame, encode, packet, delay = [
            delta(k)
            for k in (
                "bytes_sent",
                "frames_encoded",
                "total_encode_s",
                "packets_sent",
                "total_packet_send_delay_s",
            )
        ]
        bwe = _number(source["bwe_bps"]) and source["bwe_bps"] > 0
        rtt = _number(source["rtcp_rtt_s"]) and (counter is None or counter > 0)
        if counter is not None:
            if self.rtt_counter is not None and counter > self.rtt_counter and rtt:
                self.rtt_observed_at = now
            elif self.rtt_counter is not None and counter < self.rtt_counter:
                self.rtt_observed_at = None
            self.rtt_counter = counter
        else:
            self.rtt_counter = self.rtt_observed_at = None
        age = rtt and self.rtt_observed_at is not None
        enc_valid = frame is not None and frame > 0 and encode is not None
        delay_valid = packet is not None and packet > 0 and delay is not None
        values = [
            source["bwe_bps"] / 1e6 if bwe else 0,
            source["rtcp_rtt_s"] * 1000 if rtt else 0,
            now - self.rtt_observed_at if age else 0,
            byte * 8 / (dt * 1000) if byte is not None else 0,
            frame * 1000 / dt if frame is not None else 0,
            encode * 1000 / frame if enc_valid else 0,
            delay * 1000 / packet if delay_valid else 0,
            cap / 1e6,
            int(target == 0),
            int(bwe),
            int(rtt),
            int(age),
            int(byte is not None),
            int(enc_valid),
            int(delay_valid),
            dt / 1000,
        ]
        features = [
            min(limit, max(0, value / scale))
            for value, scale, limit in zip(values, FEATURE_SCALES, FEATURE_LIMITS, strict=True)
        ]
        self.previous = (now, dict(source))
        return features


def native_exploration_order(seed):
    """Independent uint32 xorshift/Fisher-Yates behavior replay, not policy features."""
    if type(seed) is not int or not 1 <= seed <= 0xFFFFFFFF:
        raise ValueError("nonzero uint32 behavior seed required")
    state, caps = seed, list(CAPS)
    for i in range(len(caps) - 1, 0, -1):
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        state &= 0xFFFFFFFF
        j = state % (i + 1)
        caps[i], caps[j] = caps[j], caps[i]
    return caps


def verify_native_sender_evidence(evidence):
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
    if controller not in ("native_fixed_cap_v1", "native_bwe_cap_headroom_v1", "native_block_exploration_v1"):
        raise ValueError("unsupported controller")
    if controller == "native_bwe_cap_headroom_v1" and evidence["controller"]["headroom"] != 0.85:
        raise ValueError("different controller headroom")
    order = None
    if controller == "native_block_exploration_v1":
        behavior = evidence["controller"]
        order = native_exploration_order(behavior["seed"])
        if (
            behavior["block_ms"] != 1000
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
            cap = order[int((sample - start) // 1000) % len(order)]
        target = (
            0
            if controller in ("native_bwe_cap_headroom_v1", "native_block_exploration_v1")
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
