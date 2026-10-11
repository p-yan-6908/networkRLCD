"""The long-session pilot's rule, plan and report, on invented records. Nothing here is native evidence."""

import json

import pytest
from test_native_range_pilot import invented_plan

from media_rl import native_margin_pilot as margin
from media_rl.native_protocol import asset_directory

RULE = dict(kind="margin", arm=0)


def test_episode_script_is_the_frozen_one_with_the_listed_changes_only():
    frozen = (asset_directory() / "actuator_episode.mjs").read_text()
    made = margin.episode_source()
    assert (asset_directory() / "margin_episode.mjs").read_text() == made
    undone = made
    for old, new in margin.EPISODE_CHANGES:
        assert frozen.count(old) == 1 and undone.count(new) == 1
        undone = undone.replace(new, old)
    assert undone == frozen and len(margin.EPISODE_CHANGES) == 9
    assert "PolicySampler(nativeConfig.policy)" in made and "episode.schedule.length!==10" in made


def test_the_python_rule_has_the_page_s_constants():
    page = (asset_directory() / "margin_control.mjs").read_text()
    assert "LADDER=Object.freeze([0.25,0.65,0.85,1.05])" in page and f"ABI='{margin.ABI}'" in page
    assert "SAFE=0,CRUISE=1,HIGH=2,START=3" in page and "HOLD_MS=3000,MAX_EPOCHS=40" in page
    assert "LOOKBACK_MS=1000,LOW_MS=104,HIGH_MS=132,PANIC_MS=159,GUARD_MS=1000" in page
    assert "CALM_HOLDS=2,MEMORY_MS=30000,MEMORY_MAX_MS=120000" in page
    assert (margin.SAFE, margin.CRUISE, margin.HIGH, margin.START) == (0, 1, 2, 3)
    assert (margin.LOW_MS, margin.HIGH_MS, margin.PANIC_MS, margin.GUARD_MS) == (104, 132, 159, 1000)
    assert (margin.CALM_HOLDS, margin.MEMORY_MS, margin.MEMORY_MAX_MS, margin.MAX_EPOCHS) == (
        2,
        30000,
        120000,
        40,
    )
    assert margin.requested_bps(0, 400000) == 150000 and margin.requested_bps(3, 5000000) == 4000000
    for bad in (
        dict(kind="margin"),
        dict(kind="fixed", step=4, arm=0),
        dict(kind="ladder", fast=True, arm=0),
    ):
        with pytest.raises(ValueError, match="policy"):
            margin.PolicyReplay(bad)


def drive(policy, age, start=100, stop=25000):
    """The page test's own scenario: polls every 100 ms, each with an acknowledgement of ``age(t)``
    received 5 ms earlier or none, and every assignment acknowledged 4 ms after it."""
    sampler, made, epoch, sent = margin.PolicyReplay(policy), [], -1, 0
    for t in range(start, stop, 100):
        a, sent = age(t), sent + 1
        heard = None if a is None else dict(source_id=sent, capture_request_ms=t - 5 - a, received_ms=t - 5)
        current = sampler.observe(t, 800000, heard)
        if current["epoch"] != epoch:
            epoch = current["epoch"]
            made.append(current)
            sampler.acknowledge(t + 4, current["requested_bps"])
    return made


def test_the_python_rule_moves_as_the_page_s_tests_say():
    calm = drive(RULE, lambda t: 100 if t < 11500 else 120 if t < 14600 else 140 if t < 17700 else 100 if t < 20800 else 110 if t < 23900 else 100)  # fmt: skip
    assert [c["assignment_ms"] for c in calm] == [100, 3200, 6300, 9400, 12500, 15600, 18700, 21800, 24900]
    assert [c["decision"] for c in calm] == [
        "start",
        "cruise",
        "hold",
        "up",
        "hold",
        "down",
        "hold",
        "hold",
        "hold",
    ]
    assert [c["step"] for c in calm] == [3, 1, 1, 2, 2, 1, 1, 1, 1] and calm[3]["requested_bps"] == 680000
    assert all(c["drops"] == 0 and c["last_late_ms"] is None for c in calm)
    late = drive(
        RULE, lambda t: 90 if t < 4000 else 300 if t < 10000 else 90 if t < 43700 else 300, stop=44100
    )
    assert [(c["decision"], c["assignment_ms"]) for c in late[:5]] == [
        ("start", 100), ("cruise", 3200), ("cut", 4300), ("hold", 7400), ("hold", 10500),
    ]  # fmt: skip
    assert late[2]["feedback_age_ms"] == pytest.approx(174) and late[2]["requested_bps"] == 200000
    assert [c["last_late_ms"] for c in late[2:5]] == [4300, 7400, 10500]
    assert [c["decision"] for c in late[5:14]] == ["hold"] * 9 and {
        c["last_late_ms"] for c in late[5:14]
    } == {10500}
    assert (late[14]["decision"], late[14]["step"], late[14]["assignment_ms"]) == ("return", 1, 41500)
    assert (late[15]["decision"], late[15]["drops"], late[15]["memory_ms"], late[15]["assignment_ms"]) == (
        "cut",
        2,
        60000,
        44000,
    )
    at_start = drive(RULE, lambda t: 2000 if t == 3200 else 90, stop=3300)
    assert [(c["decision"], c["step"], c["drops"]) for c in at_start] == [("start", 3, 0), ("drop", 0, 1)]
    silent = drive(RULE, lambda t: 90 if t < 2000 else None, stop=6500)
    assert [(c["decision"], c["drops"], c["feedback_age_ms"]) for c in silent] == [
        ("start", 0, 90), ("drop", 1, None), ("hold", 1, None),
    ]  # fmt: skip
    fixed = drive(dict(kind="fixed", step=1, arm=2), lambda t: 300, stop=9500)
    assert [(c["decision"], c["step"], c["requested_bps"]) for c in fixed] == [("fixed", 1, 520000)] * 4


def record(policy, age, polls=120):
    """A sender record made by driving the replay class poll by poll, as the page drives its sampler."""
    sampler, rows, feedback = margin.PolicyReplay(policy), [], None
    for step in range(polls):
        now = 100.0 * (step + 1)
        if step > 0:
            feedback = dict(
                source_id=step, capture_request_ms=now - 5 - age(now), received_ms=now - 5, presented_fps=30
            )
        current = sampler.observe(now, 600000, None if feedback is None else dict(feedback))
        cap = current["requested_bps"]
        sampler.acknowledge(now + 4, cap)
        rows.append(
            dict(
                step_id=step,
                observation=dict(sample_ms=now, raw_source=dict(bwe_bps=600000)),
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


def test_the_replay_recomputes_a_record_and_refuses_one_that_disagrees():
    made = record(RULE, lambda now: 90.0 if now < 4000 else 300.0)
    caps, moved = margin.replay_assignments(made, RULE)
    assert [a["decision"] for a in moved] == ["start", "cruise", "cut", "hold", "hold"]
    assert caps[0] == 630000 and caps[-1] == 150000 and moved[2]["ack_ms"] == moved[2]["assignment_ms"] + 4
    with pytest.raises(ValueError):  # recorded under the rule, replayed as a fixed level
        margin.replay_assignments(made, dict(kind="fixed", step=1, arm=0))
    wrong = json.loads(json.dumps(made))
    wrong["decisions"][60]["actuation_readback"]["encoder_max_bitrate_bps"] += 1
    with pytest.raises(ValueError, match="acknowledgment"):
        margin.replay_assignments(wrong, RULE)
    moved_ack = json.loads(json.dumps(made))
    for row in moved_ack["decisions"][30:45]:
        row["feedback_input"]["capture_request_ms"] += 250  # the acknowledgements were younger than recorded
    with pytest.raises(ValueError):
        margin.replay_assignments(moved_ack, RULE)


def test_schedules_last_a_minute_and_carry_all_three_of_n1_s_phase_names():
    assert set(margin.REGIMES) == {"steady-room", "steady-tight", "recurring-drops", "one-drop"}
    for made in margin.REGIMES.values():
        assert len(made) == 10 and sum(ms for _, _, ms in made) == 60000
        assert [name for _, name, _ in made] == ["high"] * 3 + ["collapse"] * 4 + ["recovery"] * 3
        assert all(0 < capacity <= 4 and ms == 6000 for capacity, _, ms in made)
    assert [c for c, _, _ in margin.REGIMES["recurring-drops"]] == [
        1.2,
        0.35,
        1.2,
        1.2,
        0.35,
        1.2,
        1.2,
        0.35,
        1.2,
        1.2,
    ]
    assert [c for c, _, _ in margin.REGIMES["one-drop"]] == [1.2, 0.35] + [1.2] * 8
    with pytest.raises(ValueError, match="ten"):
        margin.schedule([1.2] * 3)
    assert margin.segment(160000, 231000) == [160000, 224000]  # from where N1's clip begins
    assert margin.segment(60000, 84866) == [20000, 84000]  # a short source: the last whole 64 s
    with pytest.raises(ValueError, match="shorter"):
        margin.segment(0, 63999)


def test_plan_runs_every_arm_on_the_same_content(tmp_path):
    chosen, runtimes = invented_plan(tmp_path)
    for runtime in runtimes.values():
        runtime["video_source"]["duration_ms"] = 200000
        for episode in runtime["episodes"]:
            episode["video_segment"] = [100000, 120000]
    made = margin.plan_from(chosen, runtimes, "f" * 64, 1)
    assert made["development_pilot"] is True and made["confirmatory"] is False
    assert made["arms"] == ["margin", "0.25", "0.65", "1.05"] and made["candidates"] == ["margin"]
    assert made["memory_ms"] == dict(first=30000, most=120000) and made["segment_ms"] == 64000
    assert len(made["order"]) == 2 * 4 * 4 and len({tuple(o) for o in made["order"]}) == 32
    runtime = made["runtimes"]["mp-a"]
    assert runtime["panel_abi"] == margin.ABI and runtime["stage"] == "discovery"
    assert runtime["conditions"]["arm0"]["policy"] == dict(kind="margin", arm=0)
    assert runtime["conditions"]["arm3"]["policy"] == dict(kind="fixed", step=3, arm=3)
    assert runtime["measurement_recipe"]["max_assignments"] == 40
    assert {"assets/margin_control.mjs", "assets/margin_episode.mjs"} <= set(runtime["extra_source_sha256"])
    cell = [e for e in runtime["episodes"] if e["network_regime"] == "one-drop"]
    assert len(cell) == 4 and {tuple(e["video_segment"]) for e in runtime["episodes"]} == {(100000, 164000)}
    assert cell[0]["schedule"] == margin.REGIMES["one-drop"] and cell[0]["family"] == "one-drop"
    assert made["order"] == margin.plan_from(chosen, runtimes, "f" * 64, 1)["order"]
    with pytest.raises(ValueError, match="repetitions"):
        margin.plan_from(chosen, runtimes, "f" * 64, 0)


def invented_sessions(utility, repetitions=2, sources=("a", "b", "c")):
    sessions = []
    for source in sources:
        for regime in ("steady-room", "recurring-drops"):
            for arm, name in enumerate(margin.NAMES):
                for repetition in range(repetitions):
                    value = float(utility(source, regime, name, repetition))
                    span = {q: value if q == "utility" else 1.0 for q in margin.QUANTITIES}
                    rule = name in margin.CANDIDATES
                    sessions.append(
                        dict(
                            trial_id=f"{source}-{regime}-{arm}-{repetition}",
                            source=source,
                            regime=regime,
                            arm=arm,
                            repetition=repetition,
                            session=span,
                            after_startup=dict(span, utility=value + 1),
                            steps=[3, 1, 0, 0, 1] if rule else [arm] * 5,
                            decisions=["start", "cruise", "cut", "hold", "return"] if rule else ["fixed"] * 5,
                            at_s=[0.0, 3.1, 7.2, 10.3, 44.1],
                            feedback_age_ms=[None, 100, 170, 180, 100],
                            drops=1 if rule else 0,
                            bins=[
                                dict(
                                    utility=value + k,
                                    on_time=0.9,
                                    age_median_ms=100.0,
                                    ratio=0.65,
                                    requested_kbps=400.0,
                                )
                                for k in range(10)
                            ],
                            phases=[
                                dict(jitter_buffer_ms=30.0 + k, relay_dropped=0.0, offered_over_capacity=0.5)
                                for k in range(10)
                            ],
                        )
                    )
    return sessions


def test_report_sets_the_rule_against_each_fixed_level_within_source_and_schedule():
    lift = {"margin": 2.0, "0.25": 0.0, "0.65": 1.0, "1.05": -3.0}
    sessions = invented_sessions(
        lambda s, r, n, k: 20 + lift[n] + 0.2 * "abc".index(s) * (n == "margin") + 0.1 * k
    )
    report = json.loads(json.dumps(margin.analyse(sessions, planned=len(sessions))))
    assert report["sessions"] == 48 and report["sources"] == 3 and report["development_pilot"] is True
    assert report["sessions_by_arm"] == {"margin": 12, "0.25": 12, "0.65": 12, "1.05": 12}
    seen = report["all_schedules"]["session"]["utility"]
    assert seen["arms"]["0.65"]["level"]["mean"] == pytest.approx(21.05)
    assert set(seen["contrasts"]) == {f"{a} minus {b}" for a, b in margin.PAIRS} and len(margin.PAIRS) == 6
    assert seen["contrasts"]["margin minus 0.25"]["mean"] == pytest.approx(2.2)
    assert seen["contrasts"]["margin minus 0.65"]["mean"] == pytest.approx(1.2)
    assert seen["contrasts"]["0.25 minus 1.05"]["mean"] == pytest.approx(3.0)
    assert report["reading"]["margin"] == dict(
        against_each_fixed_level={"0.25": 1, "0.65": 1, "1.05": 1},
        beats_the_tuned_fixed_levels=True,
        loses_to_a_tuned_fixed_level=False,
        beats_the_top_ratio=True,
    )
    assert report["by_schedule"]["steady-tight"]["session"]["utility"]["arms"]["margin"]["cells"] == 0
    assert report["by_schedule"]["steady-tight"]["reading"]["margin"]["beats_the_tuned_fixed_levels"] is False
    assert report["repeatability"]["0.65"] == dict(cells=6, mean_absolute_difference=pytest.approx(0.1))
    did = report["what_the_rule_did"]["margin"]["recurring-drops"]
    assert (
        did["sessions"] == 6 and did["drops_per_session"] == 1.0 and did["first_time_at_the_bottom_s"] == 7.2
    )
    assert did["share_of_later_decisions"]["cut"] == 0.25 and did["share_of_later_decisions"]["up"] == 0
    assert did["share_of_later_assignments_at_each_ratio"] == {"0.25": 0.5, "0.65": 0.5, "0.85": 0, "1.05": 0}
    assert report["what_the_rule_did"]["margin"]["one-drop"]["sessions"] == 0
    over_time = report["timeline"]["recurring-drops"]["1.05"]
    assert over_time["utility"] == pytest.approx([17.05 + k for k in range(10)])
    assert over_time["jitter_buffer_ms"] == pytest.approx([30.0 + k for k in range(10)])
    assert report["timeline"]["one-drop"]["margin"]["utility"] == [None] * 10
    worse = margin.analyse(
        invented_sessions(lambda s, r, n, k: 20 - 2 * (n == "margin") + 0.1 * "abc".index(s) * (n == "0.25"))
    )
    assert worse["reading"]["margin"]["loses_to_a_tuned_fixed_level"] is True
    assert worse["reading"]["margin"]["beats_the_tuned_fixed_levels"] is False
