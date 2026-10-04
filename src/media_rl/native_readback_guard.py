"""Causal readback-only fallback growth hold; fixed experimental rule, not a certificate.

Reuses canonical ActionPolicy and packet validation without replacing any model
feature. The separately versioned consumer records actual guard usage explicitly.
Only this same-browser-page clock protocol is supported.
"""

from .native_action_fallback_guard import growth_hold_action
from .native_action_policy import CONFIG, ActionPolicy, finite
from .native_presentation_feedback import CLOCK_DOMAIN as CLOCK_DOMAIN
from .native_presentation_feedback import presentation_packet
from .native_presentation_feedback import receive_presentation_packet as _receive
from .native_protocol import require
from .native_repair3_policy import feedback_features

GUARD_ABI = "native_readback_fallback_growth_hold_v1"
PRESENTATION_ABI = "native_readback_guard_transport_v1"
WIRE_CHANNEL = "presentation-readback-guard-v1"


def receive_readback_packet(packet, capture_request_ms, received_ms, previous=None, guarded=False):
    require(type(guarded) is bool, "explicit readback guard usage required")
    result = _receive(packet, capture_request_ms, received_ms, previous)
    result["presentation"].update(abi=PRESENTATION_ABI, fields_used_for_actuation=guarded)
    return result


def validate_readback_input(feedback, presentation, now, guarded=None):
    require(finite(now) and 0 <= now <= 2**53 - 1, "bounded causal sample clock required")
    ff = feedback_features(feedback, now)
    require((feedback is None) == (presentation is None), "missing or unmatched readback input")
    if presentation is None:
        return ff
    require(isinstance(presentation, dict), "exact transported readback required")
    mode = presentation.get("fields_used_for_actuation")
    require(type(mode) is bool and (guarded is None or mode is guarded), "wrong readback usage mode")
    packet = presentation_packet(
        presentation.get("source_id"), presentation.get("presented_frames"), presentation.get("readback_ms")
    )
    expected = receive_readback_packet(
        packet, feedback["capture_request_ms"], feedback["received_ms"], guarded=mode
    )["presentation"]
    require(
        presentation == expected and presentation["source_id"] == feedback["source_id"],
        "readback source, clock, fields or delay decomposition mismatch",
    )
    return ff


def readback_growth_hold_action(decision, feedback, presentation, now):
    ff = validate_readback_input(feedback, presentation, now)
    legacy = growth_hold_action(decision)
    require(decision["feedback_features"] == ff, "canonical feedback features changed")
    readback_alarm = bool(
        presentation is not None
        and ff[2] == 1
        and presentation["forward_readback_delay_ms"] >= CONFIG["context_delay_ms"]
    )
    hold = decision["fallback"] and (legacy["sender_congestion_alarm"] or readback_alarm)
    cap, own = legacy["canonical_cap_bps"], legacy["actual_acknowledged_cap_bps"]
    proposed = min(cap, own) if hold else cap
    return dict(
        guard_abi=GUARD_ABI,
        encoder_max_bitrate_bps=proposed,
        receiver_jitter_buffer_target_ms=0,
        canonical_cap_bps=cap,
        actual_acknowledged_cap_bps=own,
        sender_congestion_alarm=legacy["sender_congestion_alarm"],
        legacy_fresh_ack_delay_alarm=legacy["fresh_ack_delay_alarm"],
        fresh_readback_delay_alarm=readback_alarm,
        forward_readback_delay_ms=None if presentation is None else presentation["forward_readback_delay_ms"],
        fallback_growth_hold_active=hold,
        fallback_growth_hold_applied=proposed != cap,
        neural_proposal_preserved=not decision["fallback"],
        native_deployment_qualified=False,
    )


class ReadbackGuardPolicy(ActionPolicy):
    def __init__(self, bundle, guarded=False):
        require(
            bundle is not None and type(guarded) is bool, "fitted bundle and explicit guard mode required"
        )
        super().__init__(bundle)
        self.guarded = guarded

    def observe(self, observation, feedback=None, presentation=None):
        # Invalid sidecar must not partially update the canonical actor history.
        validate_readback_input(feedback, presentation, observation["sample_ms"], self.guarded)
        canonical = super().observe(observation, feedback)
        overlay = readback_growth_hold_action(canonical, feedback, presentation, observation["sample_ms"])
        applied = self.guarded and overlay["fallback_growth_hold_applied"]
        return dict(
            canonical,
            encoder_max_bitrate_bps=overlay["encoder_max_bitrate_bps"]
            if self.guarded
            else canonical["encoder_max_bitrate_bps"],
            canonical_decision=canonical,
            guard_decision=overlay,
            guard_enabled=self.guarded,
            guard_applied=applied,
            effective_action_origin="readback_fallback_growth_hold" if applied else "canonical",
            modified_fallback_neural_credit=False,
            modified_fallback_safety_certified=False,
        )
