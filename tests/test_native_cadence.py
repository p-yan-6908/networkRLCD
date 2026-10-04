import pytest

from media_rl.native_cadence import native_cadence_action


def decision():
    return dict(
        encoder_max_bitrate_bps=150000,
        receiver_jitter_buffer_target_ms=0,
        fallback=False,
        predicted_frame_miss=[0.2] * 7,
        risk_disagreement=[0.1] * 7,
    )


def test_dwell_only_holds_still_screened_current_cap_and_releases_at_boundary():
    d = decision()
    r = native_cadence_action(d, 1000000, 900, 0, 0.5, 0.2)
    assert r["held_by_cadence"] and r["action"]["encoder_max_bitrate_bps"] == 1000000
    assert not native_cadence_action(d, 1000000, 1000, 0, 0.5, 0.2)["held_by_cadence"]


@pytest.mark.parametrize("emergency", ["fallback", "miss", "disagreement"])
def test_predicted_unsafe_current_cap_and_fallback_never_wait_for_dwell(emergency):
    d = decision()
    if emergency == "fallback":
        d["fallback"] = True
    elif emergency == "miss":
        d["predicted_frame_miss"][3] = 0.7
    else:
        d["risk_disagreement"][3] = 0.3
    r = native_cadence_action(d, 1000000, 100, 0, 0.5, 0.2)
    assert not r["held_by_cadence"] and r["action"]["encoder_max_bitrate_bps"] == 150000


@pytest.mark.parametrize("attack", ["future_ack", "legacy_cap", "nonfinite", "unsafe_base"])
def test_cadence_guard_rejects_bad_clocks_and_model_fields(attack):
    d = decision()
    own = 1000000
    ack = 0
    if attack == "future_ack":
        ack = 1000
    elif attack == "legacy_cap":
        own = 42
    elif attack == "nonfinite":
        d["risk_disagreement"][0] = float("nan")
    else:
        d["predicted_frame_miss"][0] = 0.9
    with pytest.raises(ValueError):
        native_cadence_action(d, own, 100, ack, 0.5, 0.2)
