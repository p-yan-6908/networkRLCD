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


def test_timeline_averages_each_stretch_over_sources_and_is_marked_as_added_afterwards():
    def session(source, regime, arm, on_time):
        bins = [
            dict(
                utility=None if v is None else 30.0 * v,
                on_time=v,
                age_median_ms=None if v is None else 200.0 - 100.0 * v,
                ratio=1.05 if k < 2 else 0.25,
                requested_kbps=300.0 + k,
            )
            for k, v in enumerate(on_time)
        ]
        phases = [
            dict(jitter_buffer_ms=20.0 + 10 * arm + 30 * k, relay_dropped=0.1 * k, offered_over_capacity=0.5)
            for k in range(3)
        ]
        return dict(source=source, regime=regime, arm=arm, bins=bins, phases=phases)

    sessions = [
        session("a", "queue-building", 0, [1, 1, 0.2, 0.4, 0.6, None]),
        session("a", "queue-building", 0, [1, 1, 0.4, 0.4, 0.6, 0.8]),  # the cell's second repetition
        session("b", "queue-building", 0, [1, 0.8, 0.0, 0.2, 0.4, 0.6]),
        session("a", "underutilized", 0, [1, 1, 1, 1, 1, 1]),
        session("a", "queue-building", 2, [0.9] * 6),
    ]
    made = ladder.timeline(sessions)
    assert (
        made["added_after_the_report_was_read"] is True and made["bin_ms"] == 3000 and made["sessions"] == 5
    )
    drop = made["by_schedule"]["queue-building"]
    assert drop["ladder"]["on_time"][2] == pytest.approx((0.3 + 0.0) / 2)  # repetitions first, then sources
    assert drop["ladder"]["on_time"][5] == pytest.approx((0.8 + 0.6) / 2)  # a missing stretch is left out
    assert drop["ladder"]["ratio"][:3] == pytest.approx([1.05, 1.05, 0.25])
    assert drop["0.25"]["on_time"] == pytest.approx([0.9] * 6) and drop["0.65"]["on_time"] == [None] * 6
    assert made["all_schedules"]["ladder"]["on_time"][2] == pytest.approx(((0.3 + 1) / 2 + 0.0) / 2)
    assert made["by_schedule"]["near-capacity"]["ladder"]["utility"] == [None] * 6
    assert drop["ladder"]["age_median_ms"][2] == pytest.approx((170.0 + 200.0) / 2)
    held = made["phases_by_schedule"]["queue-building"]
    assert made["phases"] == ("high", "collapse", "recovery")
    assert held["ladder"]["jitter_buffer_ms"] == pytest.approx([20.0, 50.0, 80.0])
    assert held["0.25"]["jitter_buffer_ms"] == pytest.approx([40.0, 70.0, 100.0])
    assert held["ladder"]["relay_dropped"] == pytest.approx([0.0, 0.1, 0.2])
    assert made["phases_by_schedule"]["near-capacity"]["ladder"]["offered_over_capacity"] == [None] * 3


def test_a_session_s_stretches_and_phases_come_from_its_labels_and_cumulative_snapshots(tmp_path):
    def label(at, age, worth):
        return dict(
            capture_request_ms=at,
            readback_age_ms=age,
            identifiable_ontime=age is not None and age <= 150,
            ontime_sampled_psnr_contribution=worth,
        )

    def row(epoch, ack, ratio, bps):
        return dict(
            epoch=epoch,
            ack_ms=ack,
            ratio=ratio,
            requested_bps=bps,
            cluster_id="a",
            network_regime="queue-building",
            arm=1,
        )

    def snapshot(phase, capacity, decoded, buffer_s, offered, dropped):
        return dict(
            phase=phase,
            capacity_mbps=capacity,
            interval_ms=4000,
            frames_decoded=decoded,
            frames_encoded=decoded,
            mean_native_jitter_buffer_s=buffer_s,
            mean_native_jitter_buffer_target_s=buffer_s,
            freeze_count=0,
            network=dict(a_to_b=dict(offered_wire_bytes=offered, dropped_wire_bytes=dropped)),
        )

    labels = [label(1000, 100, 30.0), label(2000, 120, 30.0), label(3999, None, 0.0), label(4000, 300, 0.0)]
    rows = [
        row(1, 5600, 0.25, 150000),
        row(0, 1000, 1.05, 315000),
    ]  # the cut comes 1.6 s into the second stretch
    snapshots = [
        snapshot("high", 0.8, 100, 0.02, 100000, 0),
        snapshot("collapse", 0.4, 200, 0.05, 300000, 50000),
        snapshot("recovery", 0.8, 200, 0.05, 300000, 50000),  # nothing decoded and nothing offered
    ]
    (tmp_path / "cohorts.json").write_text(json.dumps(rows))
    (tmp_path / "native_derived.json").write_text(json.dumps(dict(quality=dict(source_labels=labels))))
    (tmp_path / "summary.json").write_text(json.dumps(dict(snapshots=snapshots)))
    made = ladder.session_bins(tmp_path)
    assert (made["source"], made["regime"], made["arm"]) == ("a", "queue-building", 1)
    first, second, third = made["bins"][:3]
    assert first["on_time"] == pytest.approx(2 / 3) and first["utility"] == pytest.approx(20.0)
    assert first["age_median_ms"] == pytest.approx(110.0)  # of the frames shown; the third never was
    assert second["on_time"] == 0 and second["age_median_ms"] == pytest.approx(300.0)
    assert (first["ratio"], second["ratio"], third["ratio"]) == (1.05, 1.05, 0.25)  # the ratio at the middle
    assert third["on_time"] is None and third["requested_kbps"] == pytest.approx(150.0)
    high, collapse, recovery = made["phases"]
    assert high["jitter_buffer_ms"] == pytest.approx(20.0) and high["relay_dropped"] == 0
    assert collapse["jitter_buffer_ms"] == pytest.approx(80.0)  # (200 * 50 - 100 * 20) ms over 100 frames
    assert collapse["relay_dropped"] == pytest.approx(0.25) and collapse[
        "offered_over_capacity"
    ] == pytest.approx(1.0)
    assert high["offered_over_capacity"] == pytest.approx(0.25)
    assert recovery == dict(jitter_buffer_ms=None, relay_dropped=None, offered_over_capacity=0.0)
