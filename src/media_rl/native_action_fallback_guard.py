"""Independent fallback growth-hold hypothesis, not integrated or qualified.

Use only an already replay-verified canonical ActionPolicy decision. Reuse the
original sender-congestion hold and fresh ACK delay threshold, without tuning.
While fallback is active and either alarm holds, forbid increasing the actual
acknowledged cap; permit the canonical fallback's decreases. Never alter an
accepted neural action. This is not calibration, native actuation or a safety
certificate; recorded-input intents do not represent closed-loop outcomes.
"""

from .native_action_policy import CONFIG, finite, scalar_cap
from .native_observations import FEATURE_LIMITS
from .native_protocol import require

GUARD_ABI = "native_action_fallback_growth_hold_v1"
REASONS = {
    "learned",
    "sender_congestion",
    "startup_or_feedback",
    "risk_or_support",
    "upward_guard",
    "training_skill",
}


def growth_hold_action(decision):
    require(isinstance(decision, dict), "verified canonical decision required")
    f, ff = decision["features"], decision["feedback_features"]
    require(
        len(f) == 16
        and all(finite(x) and 0 <= x <= bound for x, bound in zip(f, FEATURE_LIMITS))
        and all(f[i] in (0, 1) for i in range(8, 15)),
        "bounded actual sender state required",
    )
    require(
        len(ff) == 4
        and all(finite(x) and 0 <= x <= bound for x, bound in zip(ff, (20, 20, 1, 2)))
        and ff[2] in (0, 1),
        "bounded causal feedback features required",
    )
    require(
        type(decision["fallback"]) is bool
        and decision["reason"] in REASONS
        and decision["fallback"] == (decision["reason"] != "learned"),
        "canonical fallback/reason identity required",
    )
    require(
        type(decision["receiver_jitter_buffer_target_ms"]) is int
        and decision["receiver_jitter_buffer_target_ms"] == 0,
        "unchanged native zero receiver target required",
    )
    own = scalar_cap(round(f[7] * 4e6))
    require(abs(f[7] * 4e6 - own) < 0.01, "integer actual acknowledged cap required")
    cap = scalar_cap(decision["encoder_max_bitrate_bps"])
    sender_alarm = decision["reason"] == "sender_congestion"
    # ACK delay is capture-request -> causal received presentation ACK, NOT
    # receiver pixels, a future miss label or a physical scan-out guarantee.
    feedback_alarm = ff[2] == 1 and ff[0] * 150 >= CONFIG["context_delay_ms"]
    hold = decision["fallback"] and (sender_alarm or feedback_alarm)
    proposed = min(cap, own) if hold else cap
    return dict(
        guard_abi=GUARD_ABI,
        encoder_max_bitrate_bps=proposed,
        receiver_jitter_buffer_target_ms=0,
        canonical_cap_bps=cap,
        actual_acknowledged_cap_bps=own,
        sender_congestion_alarm=sender_alarm,
        fresh_ack_delay_alarm=feedback_alarm,
        fallback_growth_hold_active=hold,
        fallback_growth_hold_applied=proposed != cap,
        neural_proposal_preserved=not decision["fallback"],
        native_deployment_qualified=False,
    )
