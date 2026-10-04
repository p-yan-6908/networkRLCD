"""Synthetic SOFTWARE checks; the hypothesis has not executed natively."""

from copy import deepcopy

import pytest

from media_rl.native_action_fallback_guard import growth_hold_action


def decision(cap=1700000, own=1000000, reason="risk_or_support", delay=80, valid=1):
    f = [0.0] * 16
    f[7] = own / 4e6
    return dict(
        features=f,
        feedback_features=[delay / 150, 0.0, float(valid), 1.0],
        fallback=reason != "learned",
        reason=reason,
        encoder_max_bitrate_bps=cap,
        receiver_jitter_buffer_target_ms=0,
    )


def test_delayed_fallback_cannot_grow_and_input_remains_immutable():
    d = decision(delay=120)
    before = deepcopy(d)
    out = growth_hold_action(d)
    assert out["encoder_max_bitrate_bps"] == 1000000
    assert out["fallback_growth_hold_applied"] and d == before
    assert not out["native_deployment_qualified"]


def test_original_sender_hold_applies_without_an_ack():
    out = growth_hold_action(decision(reason="sender_congestion", valid=0, delay=0))
    assert out["fallback_growth_hold_applied"] and out["sender_congestion_alarm"]


def test_existing_fallback_decreases_are_never_blocked():
    out = growth_hold_action(decision(cap=600000, delay=200))
    assert out["encoder_max_bitrate_bps"] == 600000
    assert out["fallback_growth_hold_active"] and not out["fallback_growth_hold_applied"]


@pytest.mark.parametrize(
    "reason", ["startup_or_feedback", "risk_or_support", "upward_guard", "training_skill"]
)
def test_no_sender_alarm_and_stale_ack_preserve_original_mapping(reason):
    assert (
        growth_hold_action(decision(reason=reason, delay=200, valid=0))["encoder_max_bitrate_bps"] == 1700000
    )
    assert growth_hold_action(decision(reason=reason, delay=119.9))["encoder_max_bitrate_bps"] == 1700000


def test_every_accepted_neural_action_remains_exactly_unchanged():
    out = growth_hold_action(decision(reason="learned", delay=300))
    assert out["encoder_max_bitrate_bps"] == 1700000 and out["neural_proposal_preserved"]
    assert not out["fallback_growth_hold_active"]


@pytest.mark.parametrize(
    "mutation",
    [
        "own-domain",
        "own-fractional",
        "proposal-domain",
        "feedback-flag",
        "feedback-nonfinite",
        "target",
        "reason",
    ],
)
def test_invalid_inputs_cannot_grant_guard_or_learned_credit(mutation):
    d = decision()
    if mutation == "own-domain":
        d["features"][7] = 149999 / 4e6
    elif mutation == "own-fractional":
        d["features"][7] = 150000.2 / 4e6
    elif mutation == "proposal-domain":
        d["encoder_max_bitrate_bps"] = 4000001
    elif mutation == "feedback-flag":
        d["feedback_features"][2] = 0.5
    elif mutation == "feedback-nonfinite":
        d["feedback_features"][0] = float("nan")
    elif mutation == "target":
        d["receiver_jitter_buffer_target_ms"] = 1
    else:
        d["fallback"] = False
    with pytest.raises(ValueError):
        growth_hold_action(d)
