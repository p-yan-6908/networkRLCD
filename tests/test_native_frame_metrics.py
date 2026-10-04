from copy import deepcopy

import pytest

from media_rl.native_frame_metrics import _crc8, summarize_native_frames


def protocol():
    return dict(
        deadline_ms=150,
        min_known_marker_coverage=0.95,
        min_readbacks=30,
        metric="capture_request_to_video_pixel_readback",
        clock_domain="single_document_performance_now",
        capture_method="canvas_manual_requestFrame",
        terminal_censoring="exclude_all_requests_with_deadline_after_cutoff",
    )


def observation(id, at, valid=True):
    crc = _crc8([id >> 8, id & 255])
    bits = [(id >> (15 - i)) & 1 for i in range(16)] + [(crc >> (7 - i)) & 1 for i in range(8)]
    if not valid:
        bits[23] ^= 1
    return dict(
        candidate_id=id,
        source_id=id if valid else None,
        crc_valid=valid,
        known_source=valid,
        luma=[245 if b else 10 for b in bits],
        callback_ms=at - 1,
        readback_ms=at,
    )


def evidence():
    return dict(
        protocol=protocol(),
        measurement_start_ms=100,
        measurement_cutoff_ms=600,
        read_errors=0,
        sources=[
            dict(source_id=1, capture_request_ms=50, phase="warmup"),
            dict(source_id=2, capture_request_ms=100, phase="high"),
            dict(source_id=3, capture_request_ms=200, phase="collapse"),
            dict(source_id=4, capture_request_ms=300, phase="collapse"),
            dict(source_id=5, capture_request_ms=450, phase="recovery"),
            dict(source_id=6, capture_request_ms=500, phase="recovery"),
        ],
        observations=[observation(2, 250), observation(3, 400), observation(6, 550)],
    )


def test_crc_cross_language_standard_vector():
    assert _crc8(list(b"123456789")) == 0xF4


def test_missing_late_boundary_and_outcome_independent_censor():
    result = summarize_native_frames(evidence())
    assert result["warmup_excluded"] == 1
    assert result["terminal_censored"] == 1  # even an already delivered terminal frame is censored
    assert result["overall"]["eligible"] == 4
    assert result["overall"]["identifiable_ontime"] == 1  # equality at exactly 150 ms is on-time
    assert result["overall"]["identified_late"] == 1
    assert result["overall"]["no_identifiable_readback"] == 2
    assert result["overall"]["deadline_miss_rate_bounds_allowing_unknown_readbacks"] == [0.75, 0.75]
    assert result["physical_scanout_or_capture_instant_verified"] is False


def test_unknown_crc_not_imputed_safe_and_bounds_are_conservative():
    ev = evidence()
    ev["observations"].insert(1, observation(4, 390, valid=False))
    result = summarize_native_frames(ev)
    assert result["unknown_marker_callbacks"] == 1
    assert result["overall"]["no_identifiable_readback"] == 2
    assert result["overall"]["deadline_miss_rate_bounds_allowing_unknown_readbacks"] == [0.5, 0.75]
    assert not result["measurement_qualified"]


def test_duplicate_readbacks_never_inflate_opportunity_delivery():
    ev = evidence()
    ev["observations"].insert(1, observation(2, 260))
    result = summarize_native_frames(ev)
    assert result["duplicate_identified_readbacks"] == 1
    assert result["overall"]["identifiable_ontime"] == 1


@pytest.mark.parametrize("change", ["crc", "source", "future", "clock", "censor", "nan", "duplicates"])
def test_corrupt_identity_clock_or_protocol_rejects(change):
    ev = deepcopy(evidence())
    if change == "crc":
        ev["observations"][0]["luma"][23] = 255 - ev["observations"][0]["luma"][23]
    if change == "source":
        ev["observations"][0]["source_id"] = 3
    if change == "future":
        ev["observations"][0] = observation(5, 250)
    if change == "clock":
        ev["observations"][0]["readback_ms"] = 200
    if change == "censor":
        ev["protocol"]["terminal_censoring"] = "exclude_missing_only"
    if change == "nan":
        ev["sources"][0]["capture_request_ms"] = float("nan")
    if change == "duplicates":
        ev["sources"][1]["source_id"] = 1
    with pytest.raises(ValueError):
        summarize_native_frames(ev)


def test_sufficient_valid_readback_coverage_is_a_measurement_not_SOTA_gate():
    ev = dict(
        protocol=protocol(),
        measurement_start_ms=0,
        measurement_cutoff_ms=1000,
        read_errors=0,
        sources=[dict(source_id=i + 1, capture_request_ms=i * 20, phase="high") for i in range(40)],
        observations=[observation(i + 1, i * 20 + 100) for i in range(40)],
    )
    result = summarize_native_frames(ev)
    assert result["measurement_qualified"]
    assert result["overall"]["identifiable_ontime_rate"] == 1
    assert result["network_loss_or_controller_SOTA_certified"] is False


def test_no_complete_deadlines_never_produces_zero_risk_claim():
    ev = evidence()
    ev["measurement_start_ms"] = 500
    ev["measurement_cutoff_ms"] = 600
    result = summarize_native_frames(ev)
    assert result["overall"]["eligible"] == 0
    assert result["overall"]["identifiable_ontime_rate"] is None
    assert not result["measurement_qualified"]
