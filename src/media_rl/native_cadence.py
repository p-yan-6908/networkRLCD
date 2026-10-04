"""Provisional prediction-screened cadence arbiter; not a native safety guarantee."""

import math

from media_rl.native_observations import CAPS

CADENCE_CONTROLLER = "native_rlcd_screened_cadence_v1"
CADENCE_PROTOCOL = dict(
    abi="native_screened_cadence_v1",
    dwell_ms=1000,
    clock="owned_changed_command_ack_ms",
    current_cap_prediction_screen_required=True,
    unsafe_current_or_fallback_immediate_release=True,
)


def native_cadence_action(
    decision, own_cap_bps, sample_ms, last_changed_ack_ms, risk_cutoff, disagreement_cutoff, dwell_ms=1000
):
    values = [sample_ms, last_changed_ack_ms, risk_cutoff, disagreement_cutoff, dwell_ms]
    if (
        any(type(x) not in (int, float) or not math.isfinite(x) for x in values)
        or not 0 <= last_changed_ack_ms <= sample_ms
        or dwell_ms <= 0
        or not 0 <= risk_cutoff <= 1
        or not 0 <= disagreement_cutoff <= 1
    ):
        raise ValueError("owned monotonic ack clock and native screens required")
    if (
        own_cap_bps not in CAPS
        or decision["encoder_max_bitrate_bps"] not in CAPS
        or decision["receiver_jitter_buffer_target_ms"] != 0
        or type(decision["fallback"]) is not bool
    ):
        raise ValueError("supported zero-target native decision required")
    miss, spread = decision["predicted_frame_miss"], decision["risk_disagreement"]
    if (
        len(miss) != 7
        or len(spread) != 7
        or any(
            type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in [*miss, *spread]
        )
    ):
        raise ValueError("finite native per-action predictions required")
    own = CAPS.index(own_cap_bps)
    proposed = CAPS.index(decision["encoder_max_bitrate_bps"])

    def eligible(i):
        return miss[i] <= risk_cutoff and spread[i] <= disagreement_cutoff

    if not decision["fallback"] and not eligible(proposed):
        raise ValueError("base native proposal violates its declared prediction screens")
    held = (
        not decision["fallback"]
        and proposed != own
        and eligible(own)
        and sample_ms - last_changed_ack_ms < dwell_ms
    )
    return dict(
        action=dict(
            encoder_max_bitrate_bps=own_cap_bps if held else CAPS[proposed],
            receiver_jitter_buffer_target_ms=0,
        ),
        held_by_cadence=held,
        elapsed_since_changed_ack_ms=sample_ms - last_changed_ack_ms,
        dwell_ms=dwell_ms,
        reason="screened_current_cap_dwell" if held else "base_or_emergency_release",
        prediction_screen_is_not_safety_certificate=True,
    )
