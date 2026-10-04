"""Synthetic SOFTWARE causality and namespace tests, not live instrumentation proof."""

from copy import deepcopy
from pathlib import Path

import pytest
from test_native_action import bundle, observation
from test_native_action_live import fixture as live_fixture

from media_rl import native_action_live_study as live
from media_rl import native_presentation_study as study
from media_rl.native_action_policy import ActionPolicy
from media_rl.native_presentation_feedback import (
    CLOCK_DOMAIN,
    PRESENTATION_ABI,
    WIRE_CHANNEL,
    presentation_packet,
    receive_presentation_packet,
)
from media_rl.native_protocol import read_json, write_json
from media_rl.native_repair5_study import _close, trial_schedule

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    frames = dict(
        sources=[dict(source_id=1, capture_request_ms=0)],
        observations=[dict(source_id=1, presented_frames=3, readback_ms=95, known_source=True)],
    )
    p = presentation_packet(1, 3, 95)
    a = receive_presentation_packet(p, 0, 123)
    sender = dict(
        presentation_feedback_protocol=dict(
            abi=PRESENTATION_ABI, clock_domain=CLOCK_DOMAIN, fields_used_for_actuation=False
        ),
        feedback_protocol=dict(
            channel=WIRE_CHANNEL, ordered=False, max_retransmits=0, min_send_interval_ms=100
        ),
        presentation_feedback_events=[dict(**a["presentation"], packet=p)],
        feedback_events=[dict(**a["canonical"], presented_frames=3)],
        decisions=[
            dict(observation=dict(sample_ms=120), feedback_input=None, presentation_feedback_input=None),
            dict(
                observation=dict(sample_ms=124),
                feedback_input=a["canonical"],
                presentation_feedback_input=a["presentation"],
            ),
        ],
    )
    return sender, frames


def test_actual_readback_is_not_ack_age_and_canonical_features_remain_identical():
    packet = presentation_packet(1, 3, 95)
    before = deepcopy(packet)
    accepted = receive_presentation_packet(packet, 0, 123)
    assert packet == before and accepted["presentation"]["forward_readback_delay_ms"] == 95
    assert (
        accepted["presentation"]["return_ack_delay_ms"] == 28
        and accepted["presentation"]["capture_to_ack_received_ms"] == 123
    )
    assert set(accepted["canonical"]) == {"source_id", "capture_request_ms", "received_ms", "presented_fps"}
    p, q = ActionPolicy(bundle()), ActionPolicy(bundle())
    for t in (124, 300, 600):
        _close(
            p.observe(observation(t), accepted["canonical"]),
            q.observe(
                observation(t), dict(source_id=1, capture_request_ms=0, received_ms=123, presented_fps=0)
            ),
        )


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), -1, 2**54, 10**400])
def test_nonphysical_readback_clock_rejects(value):
    with pytest.raises(ValueError):
        presentation_packet(1, 3, value)


@pytest.mark.parametrize(
    "mutation",
    ["clock", "extra", "id", "frames", "future", "before-capture", "previous-order", "previous-time"],
)
def test_wire_domains_order_and_future_oracle_fields_reject(mutation):
    packet = presentation_packet(2, 4, 95)
    capture, received, previous = 0, 123, None
    if mutation == "clock":
        packet["clock_domain"] = "remote_unsynchronized"
    elif mutation == "extra":
        packet["phase"] = "collapse"
    elif mutation == "id":
        packet["source_id"] = True
    elif mutation == "frames":
        packet["presented_frames"] = 1.5
    elif mutation == "future":
        received = 94
    elif mutation == "before-capture":
        capture = 96
    elif mutation == "previous-order":
        previous = dict(source_id=2, presented_frames=3, received_ms=120)
    else:
        previous = dict(source_id=1, presented_frames=3, received_ms=123)
    with pytest.raises(ValueError):
        receive_presentation_packet(packet, capture, received, previous)


def test_sidecar_replay_uses_only_actually_received_wire_packets():
    sender, frames = fixture()
    assert study.audit_presentation_sidecar(sender, frames) == dict(
        transported_readback_events=1,
        canonical_steps_with_causal_presentation=1,
        presentation_fields_used_for_actuation=False,
        canonical_feedback_semantics_unchanged=True,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "wire-time",
        "row-time",
        "future-row",
        "missing",
        "canonical-feature",
        "protocol",
        "bool-type",
        "source",
        "frame",
        "oracle",
    ],
)
def test_sidecar_forgeries_never_join_future_receiver_labels_into_model(mutation):
    s, f = fixture()
    if mutation == "wire-time":
        s["presentation_feedback_events"][0]["packet"]["readback_ms"] = 96
    elif mutation == "row-time":
        s["decisions"][1]["presentation_feedback_input"]["forward_readback_delay_ms"] = 96
    elif mutation == "future-row":
        s["decisions"][0]["presentation_feedback_input"] = s["decisions"][1]["presentation_feedback_input"]
    elif mutation == "missing":
        s["presentation_feedback_events"] = []
    elif mutation == "canonical-feature":
        s["decisions"][1]["feedback_input"]["readback_ms"] = 95
    elif mutation == "protocol":
        s["feedback_protocol"]["channel"] = "presentation-ack-v2"
    elif mutation == "bool-type":
        s["presentation_feedback_protocol"]["fields_used_for_actuation"] = 0
    elif mutation == "source":
        s["presentation_feedback_events"][0]["packet"]["source_id"] = 2
    elif mutation == "frame":
        s["presentation_feedback_events"][0]["packet"]["presented_frames"] = 4
    else:
        s["presentation_feedback_events"][0]["packet"]["future_quality"] = 40
    with pytest.raises((ValueError, KeyError)):
        study.audit_presentation_sidecar(s, f)


def test_fresh_prospective_plan_and_all_old_mapping_gates_preserved(tmp_path):
    old, _ = live_fixture(tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    write_json(configs / "native_old_live.json", old)
    path = configs / "native_presentation.json"
    p = study.plan_presentation_study(
        old["models"]["source"]["path"],
        old["repair_model"]["path"],
        tmp_path / "catalog.json",
        path,
        results_directory=tmp_path / "results",
    )
    assert read_json(path) == p and study.compatible_engines(p)
    assert p["groups"][0]["video_segment"] == [100000, 120000] and len(trial_schedule(p)) == 8
    assert (
        p["conditions"] == live.CONDITIONS
        and p["controller_config"] == old["controller_config"]
        and p["limits"] == old["limits"]
    )
    assert p["learner"] is None and not p["native_deployment_qualified"]
    for key, value in (
        ("presentation_fields_used_for_actuation", True),
        ("canonical_feedback_semantics", "readback_age"),
    ):
        bad = deepcopy(p)
        bad["measurement_recipe"][key] = value
        with pytest.raises(ValueError):
            study.validate_presentation_protocol(bad)
    assert study._RAW_AUDIT.__globals__["RepairPolicy"] is ActionPolicy
    assert study._RUN.__globals__ is not live.run_live_study.__globals__


def test_exact_projection_has_no_new_control_or_feedback_feature_call():
    assets = ROOT / "benchmarks/native_rtc"
    source = (assets / "action_live_episode.mjs").read_text()
    projected = study.project_collector(source)
    assert projected == (assets / "presentation_episode.mjs").read_text()
    assert (
        "repairActor.observe(observation,feedback_input)" in projected
        and "repairActor.observe(observation,presentation_feedback_input)" not in projected
    )
    assert "presentation.receivePresentationPacket" in projected
    with pytest.raises(ValueError):
        study.project_collector(source.replace("presented_frames,source_id", "readback_ms,source_id"))


@pytest.mark.parametrize(
    "command,flags",
    [
        ("plan", ["--source-model", "s", "--action-model", "a", "--video-source", "v", "--out", "o"]),
        ("study", ["--config", "c", "--out", "o"]),
        ("audit", ["--run", "r"]),
    ],
)
def test_public_dispatch(command, flags, monkeypatch):
    from media_rl import native_presentation_cli
    from media_rl.cli import main

    calls = []
    monkeypatch.setattr(native_presentation_cli, "run", lambda args: calls.append(args))
    main(["native-presentation-" + command, *flags])
    assert calls[0].command == "native-presentation-" + command


@pytest.mark.parametrize("command", ["train", "calibrate", "validate", "test", "promote"])
def test_no_fitting_or_promotion_public_command(command):
    from media_rl.cli import main

    with pytest.raises(SystemExit):
        main(["native-presentation-" + command])
