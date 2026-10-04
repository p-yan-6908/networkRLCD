"""Transported identified-readback time, separate from canonical ACK-age features.

Only the declared one-browser-page clock domain is supported. Not a general
remote clock synchronization protocol or a safety/model/action certificate.
"""

import math

from .native_protocol import require

PRESENTATION_ABI = "native_presentation_readback_transport_v1"
CLOCK_DOMAIN = "same_browser_page_performance_v1"
WIRE_CHANNEL = "presentation-readback-v1"
WIRE_KEYS = {"source_id", "presented_frames", "readback_ms", "clock_domain"}


def _number(x):
    return type(x) in (int, float) and 0 <= x <= 2**53 - 1 and math.isfinite(x)


def presentation_packet(source_id, presented_frames, readback_ms):
    require(
        type(source_id) is int
        and 1 <= source_id <= 2**53 - 1
        and type(presented_frames) is int
        and 1 <= presented_frames <= 2**53 - 1
        and _number(readback_ms),
        "valid identified callback packet required",
    )
    return dict(
        source_id=source_id,
        presented_frames=presented_frames,
        readback_ms=readback_ms,
        clock_domain=CLOCK_DOMAIN,
    )


def receive_presentation_packet(packet, capture_request_ms, received_ms, previous=None):
    """Return unchanged four-field canonical feedback plus NON-ACTING sidecar."""
    require(
        isinstance(packet, dict) and set(packet) == WIRE_KEYS and packet["clock_domain"] == CLOCK_DOMAIN,
        "declared exact readback wire fields and same-page clock required",
    )
    require(
        packet == presentation_packet(packet["source_id"], packet["presented_frames"], packet["readback_ms"]),
        "valid readback packet required",
    )
    require(
        _number(capture_request_ms)
        and _number(received_ms)
        and capture_request_ms <= packet["readback_ms"] <= received_ms,
        "future or pre-capture readback forbidden",
    )
    if previous is not None:
        require(
            isinstance(previous, dict)
            and type(previous.get("source_id")) is int
            and type(previous.get("presented_frames")) is int
            and _number(previous.get("received_ms"))
            and packet["source_id"] > previous["source_id"]
            and packet["presented_frames"] >= previous["presented_frames"]
            and received_ms > previous["received_ms"],
            "stale, duplicate or out-of-order readback feedback",
        )
    fps = (
        0
        if previous is None
        else 1000
        * (packet["presented_frames"] - previous["presented_frames"])
        / (received_ms - previous["received_ms"])
    )
    canonical = dict(
        source_id=packet["source_id"],
        capture_request_ms=capture_request_ms,
        received_ms=received_ms,
        presented_fps=fps,
    )
    presentation = dict(
        abi=PRESENTATION_ABI,
        clock_domain=CLOCK_DOMAIN,
        source_id=packet["source_id"],
        presented_frames=packet["presented_frames"],
        capture_request_ms=capture_request_ms,
        readback_ms=packet["readback_ms"],
        received_ms=received_ms,
        forward_readback_delay_ms=packet["readback_ms"] - capture_request_ms,
        return_ack_delay_ms=received_ms - packet["readback_ms"],
        capture_to_ack_received_ms=received_ms - capture_request_ms,
        fields_used_for_actuation=False,
    )
    return dict(canonical=canonical, presentation=presentation)
