"""The rule-based candidates and their pilot's report, on invented records. Nothing here is native evidence."""

import json
import math

import pytest
from test_native_range_pilot import invented_plan

from media_rl import native_ladder_pilot as ladder
from media_rl.native_protocol import asset_directory


def test_episode_script_is_the_frozen_one_with_the_listed_changes_only():
    frozen = (asset_directory() / "actuator_episode.mjs").read_text()
    made = ladder.episode_source()
    assert (asset_directory() / "ladder_episode.mjs").read_text() == made
    undone = made
    for old, new in ladder.EPISODE_CHANGES:
        assert frozen.count(old) == 1 and undone.count(new) == 1
        undone = undone.replace(new, old)
    assert undone == frozen
    assert "PolicySampler(nativeConfig.policy)" in made and "latestFeedback?{...latestFeedback}:null)" in made


def test_the_python_rule_is_the_page_s_rule():
    page = (asset_directory() / "ladder_control.mjs").read_text()
    assert "LADDER=Object.freeze([0.25,0.65,0.85,1.05])" in page and f"ABI='{ladder.ABI}'" in page
    assert "LOOKBACK_MS=1000,LOW_MS=104,HIGH_MS=132,PANIC_MS=159,GUARD_MS=1000" in page
    assert "HOLD_MS=3000,MAX_EPOCHS=6,FAST_EPOCHS=12" in page
    assert (ladder.LOOKBACK_MS, ladder.LOW_MS, ladder.HIGH_MS, ladder.PANIC_MS, ladder.GUARD_MS) == (
        1000,
        104,
        132,
        159,
        1000,
    )
    low, high, panic = ladder.LOW_MS, ladder.HIGH_MS, ladder.PANIC_MS
    assert ladder.next_step(1, low - 1) == 2 and ladder.next_step(3, 50) == 3  # the top stays the top
    assert ladder.next_step(1, low) == 1 and ladder.next_step(2, high - 1) == 2  # inside the band: hold
    assert (
        ladder.next_step(2, high) == 1 and ladder.next_step(0, high) == 0
    )  # one step down, not below the bottom
    assert ladder.next_step(3, panic) == 0 and ladder.next_step(2, None) == 0  # to the bottom
    assert ladder.requested_bps(0, 400000) == 150000 and ladder.requested_bps(2, 300001) == 255001
    assert ladder.requested_bps(3, 3_900_000) == 4_000_000


def thresholds_follow_from_the_headroom_report():
    return dict(low=(94.52 + 113.91) / 2, high=(109.86 + 153.19) / 2, panic=159.39)


def test_thresholds_are_the_medians_the_design_names():
    made = thresholds_follow_from_the_headroom_report()
    assert (round(made["low"]), round(made["high"]), round(made["panic"])) == (
        ladder.LOW_MS,
        ladder.HIGH_MS,
        ladder.PANIC_MS,
    )


def record(policy, age, estimate=600000, polls=100, lost=()):
    """A sender record made by driving the replay class poll by poll, as the page drives its sampler.

    ``age(now)`` is the age of the acknowledgement that arrives just before each poll; no
    acknowledgement arrives in the polls listed in ``lost``.
    """
    sampler, rows, feedback = ladder.PolicyReplay(policy), [], None
    for step in range(polls):
        now = 100.0 * (step + 1)
        if step not in lost and step > 0:
            feedback = dict(
                source_id=step, capture_request_ms=now - 5 - age(now), received_ms=now - 5, presented_fps=30
            )
        current = sampler.observe(now, estimate, None if feedback is None else dict(feedback))
        cap = 300000 if current is None else current["requested_bps"]
        sampler.acknowledge(now + 4, cap)
        rows.append(
            dict(
                step_id=step,
                observation=dict(sample_ms=now, raw_source=dict(bwe_bps=estimate)),
                feedback_input=None if feedback is None else dict(feedback),
                actuator_assignment=current,
                ack_ms=now + 4,
                actuation_readback=dict(encoder_max_bitrate_bps=cap),
            )
        )
    meter = dict(
        abi="native_encoded_payload_meter_v1",
        owner="unique_owned_video_sender",
        pass_through_no_frame_mutation=True,
        error=None,
        unit="encoded_video_payload_bytes_before_RTP_packetization",
        measurement_start_ms=0.0,
        measurement_cutoff_ms=100.0 * polls + 50,
        started_ms=0.0,
        ended_ms=None,
        events=[],
    )
    return dict(
        decisions=rows,
        encoded_meter=meter,
        measurement_start_ms=0.0,
        measurement_cutoff_ms=100.0 * polls + 50,
    )


SLOW = dict(kind="ladder", fast=False, arm=0)
FAST = dict(kind="ladder", fast=True, arm=1)


def test_a_fixed_level_never_moves_and_a_slow_ladder_moves_at_hold_boundaries_only():
    late_then_early = lambda now: 200.0 if now < 4000 else 80.0  # noqa: E731
    fixed = dict(kind="fixed", step=1, arm=3)
    caps, held = ladder.replay_assignments(record(fixed, late_then_early), fixed)
    assert [a["decision"] for a in held] == ["fixed"] * 4 and {a["step"] for a in held} == {1}
    assert set(caps) == {390000}  # 0.65 of 600 kbit/s from the first poll on
    caps, moved = ladder.replay_assignments(record(SLOW, late_then_early), SLOW)
    assert [a["decision"] for a in moved] == ["start", "down", "up", "up"]
    assert [a["step"] for a in moved] == [3, 0, 1, 2]
    assert [round(a["assignment_ms"]) for a in moved] == [
        100,
        3200,
        6300,
        9400,
    ]  # 3 s after each acknowledgement
    assert moved[1]["feedback_age_ms"] == pytest.approx(200) and 8 <= moved[1]["feedback_seen"] <= 11
    assert moved[0]["feedback_age_ms"] is None and moved[0]["fast"] is False


def test_a_fast_ladder_cuts_inside_a_hold_after_the_guard():
    late_then_early = lambda now: 200.0 if now < 4000 else 80.0  # noqa: E731
    caps, moved = ladder.replay_assignments(record(FAST, late_then_early), FAST)
    assert [a["decision"] for a in moved][:3] == ["start", "cut", "hold"]
    assert (
        moved[1]["step"] == 0 and round(moved[1]["assignment_ms"]) == 1200
    )  # one second after the first ack
    assert (
        moved[2]["decision"] == "hold" and round(moved[2]["assignment_ms"]) == 4300
    )  # still averaging late ones
    assert [a["decision"] for a in moved][3:] == ["up"]
    quiet = record(FAST, lambda now: 80.0, lost=range(1, 100))  # no acknowledgement at all
    _, silent = ladder.replay_assignments(quiet, FAST)
    assert [a["decision"] for a in silent] == [
        "start",
        "down",
        "hold",
        "hold",
    ]  # to the bottom, at a boundary


def test_replay_refuses_a_record_that_disagrees():
    made = record(SLOW, lambda now: 120.0)
    ladder.replay_assignments(made, SLOW)
    with pytest.raises(ValueError):  # recorded under the other rule
        ladder.replay_assignments(record(FAST, lambda now: 200.0), SLOW)
    wrong = json.loads(json.dumps(made))
    wrong["decisions"][40]["actuation_readback"]["encoder_max_bitrate_bps"] += 1
    with pytest.raises(ValueError, match="acknowledgment"):
        ladder.replay_assignments(wrong, SLOW)
    moved = json.loads(json.dumps(made))
    for row in moved["decisions"][20:32]:
        row["feedback_input"]["capture_request_ms"] -= 100  # the acknowledgements were older than recorded
    with pytest.raises(ValueError):
        ladder.replay_assignments(moved, SLOW)
    for bad in (dict(kind="ladder", arm=0), dict(kind="fixed", step=4, arm=0), dict(kind="fixed", step=1)):
        with pytest.raises(ValueError, match="policy"):
            ladder.PolicyReplay(bad)


def test_plan_runs_every_arm_on_the_same_content_with_repetitions(tmp_path):
    chosen, runtimes = invented_plan(tmp_path)
    made = ladder.plan_from(chosen, runtimes, "f" * 64, 2)
    assert made["development_pilot"] is True and made["confirmatory"] is False
    assert made["arms"] == ["ladder", "fast ladder", "0.25", "0.65", "1.05"]
    assert made["candidates"] == ["ladder", "fast ladder"] and made["tuned_fixed_levels"] == ["0.25", "0.65"]
    assert made["thresholds_ms"] == dict(lookback=1000, low=104, high=132, panic=159, guard=1000)
    assert len(made["order"]) == 2 * 4 * 5 * 2 and len({tuple(o) for o in made["order"]}) == 80
    runtime = made["runtimes"]["lp-a"]
    assert runtime["panel_abi"] == ladder.ABI and runtime["stage"] == "discovery"
    assert runtime["conditions"]["arm1"]["policy"] == dict(kind="ladder", fast=True, arm=1)
    assert runtime["conditions"]["arm4"] == dict(
        controller="explore", behavior="policy", policy=dict(kind="fixed", step=3, arm=4), model="source"
    )
    assert {"assets/ladder_control.mjs", "assets/ladder_episode.mjs"} <= set(runtime["extra_source_sha256"])
    cell = [e for e in runtime["episodes"] if e["network_regime"] == "near-capacity"]
    assert (
        len(cell) == 10
        and {e["repetition"] for e in cell} == {0, 1}
        and {e["scene_seed"] for e in cell} == {0}
    )
    assert made["order"] == ladder.plan_from(chosen, runtimes, "f" * 64, 2)["order"]
    with pytest.raises(ValueError, match="repetitions"):
        ladder.plan_from(chosen, runtimes, "f" * 64, 0)


def invented_sessions(utility, repetitions=2, sources=("a", "b", "c")):
    sessions = []
    for source in sources:
        for regime in ("underutilized", "queue-building"):
            for arm, name in enumerate(ladder.NAMES):
                for repetition in range(repetitions):
                    value = float(utility(source, regime, name, repetition))
                    span = {q: value if q == "utility" else 1.0 for q in ladder.QUANTITIES}
                    moves = (
                        ["start", "hold", "down", "up", "hold", "cut"]
                        if name in ladder.CANDIDATES
                        else ["fixed"] * 6
                    )
                    sessions.append(
                        dict(
                            trial_id=f"{source}-{regime}-{arm}-{repetition}",
                            source=source,
                            regime=regime,
                            arm=arm,
                            repetition=repetition,
                            session=span,
                            after_startup=dict(span, utility=value + 1),
                            steps=[3, 3, 2, 3, 3, 0],
                            decisions=moves,
                            feedback_age_ms=[None, 100, 140, 90, 110, 200],
                        )
                    )
    return sessions


def test_report_sets_each_candidate_against_each_fixed_level_within_source_and_schedule():
    base = {"ladder": 30.0, "fast ladder": 33.0, "0.25": 26.0, "0.65": 31.0, "1.05": 21.0}
    lift = {"a": 0.0, "b": 0.1, "c": 0.2}

    def utility(source, regime, name, repetition):
        return (
            base[name]
            + lift[source] * (1 if name in ladder.CANDIDATES else 0)
            + (0.5 if repetition else -0.5)
        )

    report = ladder.analyse(invented_sessions(utility), planned=60)
    assert (
        report["development_pilot"] is True and report["confirmatory"] is False and report["sessions"] == 60
    )
    assert report["sessions_by_arm"] == dict.fromkeys(ladder.NAMES, 12)
    seen = report["all_schedules"]["session"]["utility"]
    assert seen["arms"]["0.65"]["level"]["mean"] == pytest.approx(31) and seen["arms"]["0.65"]["cells"] == 6
    assert seen["contrasts"]["ladder minus 0.25"]["mean"] == pytest.approx(4.1)
    assert seen["contrasts"]["ladder minus 0.65"]["mean"] == pytest.approx(-0.9)
    assert seen["contrasts"]["fast ladder minus ladder"]["mean"] == pytest.approx(3)
    assert "ladder minus fast ladder" not in seen["contrasts"]  # each pair of candidates once
    assert seen["contrasts"]["0.25 minus 1.05"]["mean"] == pytest.approx(
        5
    )  # the fixed levels against each other
    assert seen["contrasts"]["0.65 minus 1.05"]["mean"] == pytest.approx(10)
    assert seen["contrasts"]["0.25 minus 0.65"]["mean"] == pytest.approx(-5)
    read = report["reading"]
    assert read["ladder"]["against_each_fixed_level"] == {"0.25": 1, "0.65": -1, "1.05": 1}
    assert (
        read["ladder"]["beats_the_tuned_fixed_levels"] is False
        and read["ladder"]["loses_to_a_tuned_fixed_level"] is True
    )
    assert (
        read["fast ladder"]["beats_the_tuned_fixed_levels"] is True
        and read["fast ladder"]["beats_the_top_ratio"] is True
    )
    assert read["fast_minus_slow"] == 1
    assert report["all_schedules"]["after_startup"]["utility"]["arms"]["1.05"]["level"][
        "mean"
    ] == pytest.approx(22)
    assert report["repeatability"]["0.25"] == dict(cells=6, mean_absolute_difference=pytest.approx(1))
    did = report["what_the_rule_did"]["fast ladder"]["underutilized"]
    assert did["sessions"] == 6 and did["changes_per_session"] == 5
    assert did["share_of_decisions"] == dict(up=0.2, hold=0.4, down=0.2, cut=0.2)
    assert math.isclose(sum(did["share_of_later_assignments_at_each_ratio"].values()), 1)
    empty = report["by_schedule"]["near-capacity"]
    assert (
        empty["reading"]["ladder"]["beats_the_tuned_fixed_levels"] is False
    )  # nothing is claimed without data
    assert empty["reading"]["fast_minus_slow"] == 0
