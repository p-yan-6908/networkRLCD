"""Software and recorded-context checks only; not native efficacy evidence."""

from copy import deepcopy
from pathlib import Path

import pytest
from test_native_action import bundle, observation, supported
from test_native_action_live import fixture as live_fixture

from media_rl import native_readback_guard_study as study
from media_rl.native_action_policy import CONFIG, ActionPolicy
from media_rl.native_presentation_feedback import presentation_packet
from media_rl.native_protocol import read_json, write_json
from media_rl.native_readback_guard import (
    CLOCK_DOMAIN,
    PRESENTATION_ABI,
    WIRE_CHANNEL,
    ReadbackGuardPolicy,
    readback_growth_hold_action,
    receive_readback_packet,
)
from media_rl.native_repair5_study import _close, trial_schedule

ROOT = Path(__file__).resolve().parents[1]


def packet(now=600, forward=90, returned=40, mode=True):
    born = now - 30 - forward - returned
    result = receive_readback_packet(presentation_packet(1, 3, born + forward), born, now - 30, guarded=mode)
    result["canonical"]["presented_fps"] = 30
    return result["canonical"], result["presentation"]


def decision(forward=90, returned=40, cap=850000, reason="risk_or_support", now=600):
    fb, side = packet(now, forward, returned)
    p = ActionPolicy(bundle())
    p.observe(observation(0))
    d = p.observe(observation(now), fb)
    return dict(d, reason=reason, fallback=reason != "learned", encoder_max_bitrate_bps=cap), fb, side


@pytest.mark.parametrize(
    "forward,returned,alarm", [(90, 40, False), (119, 40, False), (120, 40, True), (150, 0, True)]
)
def test_actual_readback_not_ack_return_time_and_fixed_alarm(forward, returned, alarm):
    d, fb, side = decision(forward, returned)
    original = deepcopy(d)
    g = readback_growth_hold_action(d, fb, side, 600)
    assert g["fresh_readback_delay_alarm"] is alarm
    assert g["legacy_fresh_ack_delay_alarm"]
    assert g["encoder_max_bitrate_bps"] == (450000 if alarm else 850000)
    assert d == original and CONFIG["context_delay_ms"] == 120


def test_both_modes_keep_identical_canonical_model_scores_and_history():
    b = bundle()
    plain, guarded, canonical = ReadbackGuardPolicy(b, False), ReadbackGuardPolicy(b, True), ActionPolicy(b)
    for now in (0, 600, 900):
        fb, side = (None, None) if now == 0 else packet(now, 130)
        a = plain.observe(
            observation(now), fb, None if side is None else dict(side, fields_used_for_actuation=False)
        )
        g = guarded.observe(observation(now), fb, side)
        expected = canonical.observe(observation(now), fb)
        _close(a["canonical_decision"], expected)
        _close(g["canonical_decision"], expected)
        assert a["guard_decision"] == g["guard_decision"]
        assert a["encoder_max_bitrate_bps"] == expected["encoder_max_bitrate_bps"]
    assert g["guard_applied"] and g["fallback"]
    assert not g["modified_fallback_neural_credit"] and not g["modified_fallback_safety_certified"]


def test_genuine_neural_proposals_never_change_or_acquire_guard_credit():
    p = ReadbackGuardPolicy(supported(bundle(), context="delayed"), True)
    p.observe(observation(0))
    fb, side = packet(forward=130)
    d = p.observe(observation(600), fb, side)
    assert not d["fallback"] and not d["guard_applied"]
    assert d["guard_decision"]["fresh_readback_delay_alarm"]
    assert d["encoder_max_bitrate_bps"] == d["canonical_decision"]["encoder_max_bitrate_bps"]
    p.acknowledge(d["encoder_max_bitrate_bps"], 601)
    with pytest.raises(ValueError):
        p.acknowledge(d["encoder_max_bitrate_bps"], 600)


@pytest.mark.parametrize(
    "reason,cap,expected",
    [
        ("sender_congestion", 850000, 450000),
        ("sender_congestion", 250000, 250000),
        ("learned", 850000, 850000),
    ],
)
def test_sender_hold_decreases_and_neural_bypass_are_unchanged(reason, cap, expected):
    d, fb, side = decision(reason=reason, cap=cap)
    assert readback_growth_hold_action(d, fb, side, 600)["encoder_max_bitrate_bps"] == expected


def test_stale_readback_never_triggers_a_fresh_alarm():
    d, fb, side = decision(forward=130)
    p = ActionPolicy(bundle())
    p.observe(observation(0))
    d = p.observe(observation(1100), fb)
    assert not readback_growth_hold_action(d, fb, side, 1100)["fresh_readback_delay_alarm"]


@pytest.mark.parametrize(
    "mutation",
    ["future", "source", "abi", "clock", "oracle", "usage", "delay", "missing", "extra", "canonical"],
)
def test_invalid_sidecar_rejects_before_canonical_state_mutation(mutation):
    p = ReadbackGuardPolicy(bundle(), True)
    p.observe(observation(0))
    fb, side = packet()
    if mutation == "future":
        side["received_ms"] = 601
    elif mutation == "source":
        side["source_id"] = 2
    elif mutation == "abi":
        side["abi"] = "old"
    elif mutation == "clock":
        side["clock_domain"] = "remote_wall_clock"
    elif mutation == "oracle":
        side["next_frame_miss"] = False
    elif mutation == "usage":
        side["fields_used_for_actuation"] = False
    elif mutation == "delay":
        side["forward_readback_delay_ms"] += 1
    elif mutation == "missing":
        side = None
    elif mutation == "extra":
        side.pop("return_ack_delay_ms")
    else:
        fb["presented_fps"] = float("nan")
    before = p.state.last_sample, deepcopy(p.state.history)
    with pytest.raises(ValueError):
        p.observe(observation(600), fb, side)
    assert (p.state.last_sample, p.state.history) == before


@pytest.mark.parametrize("mode", [None, 0, 1, "true"])
def test_mode_is_not_truthy_metadata(mode):
    with pytest.raises(ValueError):
        ReadbackGuardPolicy(bundle(), mode)
    with pytest.raises(ValueError):
        receive_readback_packet(presentation_packet(1, 1, 1), 0, 2, guarded=mode)


def sidecar_fixture(mode):
    p = presentation_packet(1, 3, 95)
    accepted = receive_readback_packet(p, 0, 123, guarded=mode)
    frames = dict(
        sources=[dict(source_id=1, capture_request_ms=0)],
        observations=[dict(source_id=1, presented_frames=3, readback_ms=95, known_source=True)],
    )
    sender = dict(
        presentation_feedback_protocol=dict(
            abi=PRESENTATION_ABI, clock_domain=CLOCK_DOMAIN, fields_used_for_actuation=mode
        ),
        feedback_protocol=dict(
            channel=WIRE_CHANNEL, ordered=False, max_retransmits=0, min_send_interval_ms=100
        ),
        presentation_feedback_events=[dict(**accepted["presentation"], packet=p)],
        feedback_events=[dict(**accepted["canonical"], presented_frames=3)],
        decisions=[
            dict(observation=dict(sample_ms=120), feedback_input=None, presentation_feedback_input=None),
            dict(
                observation=dict(sample_ms=124),
                feedback_input=accepted["canonical"],
                presentation_feedback_input=accepted["presentation"],
            ),
        ],
    )
    return sender, frames


@pytest.mark.parametrize("mode", [False, True])
def test_wire_replay_records_real_guard_usage_and_only_received_inputs(mode):
    sender, frames = sidecar_fixture(mode)
    out = study.audit_readback_sidecar(sender, frames, mode)
    assert out["presentation_fields_used_for_actuation"] is mode and out["steps_with_causal_readback"] == 1
    assert out["canonical_feedback_semantics_unchanged"]


@pytest.mark.parametrize("mutation", ["callback", "future", "usage", "oracle", "unknown"])
def test_receiver_join_future_and_packet_forgery_reject(mutation):
    s, f = sidecar_fixture(True)
    if mutation == "callback":
        f["observations"][0]["readback_ms"] += 1
    elif mutation == "future":
        s["decisions"][0]["presentation_feedback_input"] = s["decisions"][1]["presentation_feedback_input"]
    elif mutation == "usage":
        s["presentation_feedback_protocol"]["fields_used_for_actuation"] = False
    elif mutation == "oracle":
        s["presentation_feedback_events"][0]["packet"]["miss"] = False
    else:
        f["observations"][0]["source_id"] = 2
    with pytest.raises((ValueError, AssertionError)):
        study.audit_readback_sidecar(s, f, True)


def planned(tmp_path):
    old, _ = live_fixture(tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    write_json(configs / "native_old_live.json", old)
    path = configs / "native_readback_guard.json"
    p = study.plan_readback_guard_study(
        old["models"]["source"]["path"],
        old["repair_model"]["path"],
        tmp_path / "catalog.json",
        path,
        families=["stable", "collapse"],
        results_directory=tmp_path / "results",
    )
    return old, p, path


def test_fresh_plan_aliases_strong_controls_hashes_and_unchanged_gates(tmp_path):
    old, p, path = planned(tmp_path)
    assert read_json(path) == p and study.compatible_engines(p)
    assert len(trial_schedule(p)) == 24 and len(p["groups"]) == 2
    assert p["groups"][0]["video_segment"] == [100000, 120000]
    assert p["groups"][1]["video_segment"] == [120000, 140000]
    assert p["controller_config"] == old["controller_config"] and p["limits"] == old["limits"]
    assert p["conditions"]["rlcd-a"]["guarded"] and not p["conditions"]["baseline-a"]["guarded"]
    assert not p["native_deployment_qualified"] and p["learner"] is None
    for name, source in study.extra_sources().items():
        assert p["extra_source_sha256"][name] == study.digest(source)
    with pytest.raises(ValueError):
        study.plan_readback_guard_study("unused", "unused", "unused", path)


@pytest.mark.parametrize("mutation", ["mode", "risk", "recipe", "role", "order", "promotion"])
def test_changed_risk_recipe_roles_order_or_aliases_reject(tmp_path, mutation):
    old, p, _ = planned(tmp_path)
    if mutation == "mode":
        p["conditions"]["baseline-a"]["guarded"] = True
    elif mutation == "risk":
        p["controller_config"]["context_delay_ms"] = 150
    elif mutation == "recipe":
        p["measurement_recipe"]["modified_fallback_neural_credit"] = True
    elif mutation == "role":
        p["groups"][0]["video_segment"] = old["groups"][0]["video_segment"]
    elif mutation == "order":
        p["groups"][0]["orders"][0].reverse()
    else:
        p["stage"] = "validation"
    with pytest.raises(ValueError):
        study.validate_readback_protocol(p)


def test_collector_projection_is_exact_and_missing_anchor_rejects():
    parent = (ROOT / "benchmarks/native_rtc/presentation_episode.mjs").read_text()
    assert (
        study.project_collector(parent)
        == (ROOT / "benchmarks/native_rtc/readback_guard_episode.mjs").read_text()
    )
    with pytest.raises(ValueError):
        study.project_collector(parent.replace("repairActor.observe(observation,feedback_input)", "changed"))
