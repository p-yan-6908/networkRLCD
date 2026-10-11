"""Headroom over a tuned fixed level and what the sender can see, on invented sessions. Not native evidence."""

import json
import math

import pytest
from test_native_range_pilot import invented_capture

from media_rl import native_range_pilot as pilot
from media_rl import native_range_pilot_headroom as headroom
from media_rl.native_protocol import seal_directory

REGIMES = ("underutilized", "queue-building")


def invented(utility, sources=("a", "b", "c", "d"), growth=None, age=None):
    """Sessions as the reader returns them: ``utility(source, regime, level, epoch)`` per hold."""
    sessions = []
    for source in sources:
        for regime in REGIMES:
            for level in range(5):
                holds = [
                    dict(
                        epoch=epoch,
                        requests=90,
                        utility=float(utility(source, regime, level, epoch)),
                        on_time=1.0,
                        estimate_growth=math.nan
                        if epoch == 0
                        else (growth or (lambda *a: 1.0))(regime, level),
                        feedback_age_ms=(age or (lambda *a: 80.0))(regime, level),
                        rtt_ms=55.0,
                    )
                    for epoch in range(6)
                ]
                sessions.append(
                    dict(
                        trial_id=f"{source}-{regime}-{level}",
                        source=source,
                        regime=regime,
                        level=level,
                        holds=holds,
                    )
                )
    return sessions


def test_a_fixed_level_is_chosen_without_the_source_it_is_scored_on():
    # Level 1 is best everywhere except for source "d", whose own best is level 4.
    def utility(source, regime, level, epoch):
        if source == "d":
            return 40 if level == 4 else 10
        return {0: 20, 1: 30, 2: 25, 3: 22, 4: 5}[level]

    made = headroom.plans(invented(utility))
    honest, optimistic = made["leaving_one_source_out"], made["in_sample"]
    assert made["levels_chosen_in_the_folds"]["fixed"]["0.65"] == 4  # "d" is scored at the others' level
    assert honest["utility"]["fixed"]["mean"] == pytest.approx((30 * 3 + 10) / 4)
    assert honest["fixed_minus_reference"]["mean"] == pytest.approx(((30 - 22) * 3 + 0) / 4)
    assert made["levels_chosen_in_sample"]["fixed"] == "0.65"
    assert optimistic["utility"]["fixed"]["mean"] == honest["utility"]["fixed"]["mean"]
    assert honest["schedule_aware_minus_fixed"]["mean"] == pytest.approx(0)


def test_knowing_the_schedule_and_switching_by_hold_are_scored_apart():
    # With room level 2 is best, under constraint level 0; in the last hold level 3 is best everywhere.
    def utility(source, regime, level, epoch):
        base = (
            {0: 20, 1: 24, 2: 30, 3: 22, 4: 5}[level]
            if regime == "underutilized"
            else {0: 28, 1: 24, 2: 18, 3: 12, 4: 5}[level]
        )
        return 50 if (epoch == 5 and level == 3) else base

    made = headroom.plans(invented(utility))
    honest = made["leaving_one_source_out"]
    chosen = made["levels_chosen_in_sample"]
    assert chosen["schedule_aware"] == {"underutilized": "0.85", "queue-building": "0.25"}
    assert chosen["switching_by_hold"]["underutilized"] == {
        "2": "0.85",
        "3": "0.85",
        "4": "0.85",
        "5": "0.85",
        "6": "1.05",
    }
    # The best single level over both schedules: level 1 at (24+24)/2 ties with level 0 and 2 at 24: the lowest wins.
    assert chosen["fixed"] == "0.25"
    assert honest["utility"]["fixed"]["mean"] == pytest.approx(24)
    assert honest["schedule_aware_minus_fixed"]["mean"] == pytest.approx((30 + 28) / 2 - 24)
    assert honest["switching_minus_schedule_aware"]["mean"] == pytest.approx(((50 - 30) + (50 - 28)) / 2 / 5)
    assert made["levels_chosen_in_the_folds"]["schedule_aware"]["queue-building"]["0.25"] == 4


def test_separation_is_a_probability_and_respects_the_direction():
    assert headroom.separation([2, 3], [1, 1], 1) == 1
    assert headroom.separation([2, 3], [1, 1], -1) == 0
    assert headroom.separation([1, 1], [1, 1], 1) == 0.5
    assert headroom.separation([1, 2], [1.5], -1) == 0.5
    assert math.isnan(headroom.separation([], [1], 1)) and math.isnan(headroom.separation([math.nan], [1], 1))


def test_signals_are_judged_per_level_and_the_flag_is_b1_s():
    # The estimate grows with room only at the upper levels; the feedback is older under constraint only at the top.
    def growth(regime, level):
        return 1.5 if (regime == "underutilized" and level >= 2) else 1.0

    def age(regime, level):
        return 140.0 if (regime != "underutilized" and level >= 3) else 80.0

    seen = headroom.signals(invented(lambda *a: 20.0, growth=growth, age=age))
    assert seen["0.25"]["separation"]["estimate_growth"]["mean"] == pytest.approx(0.5)
    assert seen["0.25"]["separation"]["estimate_growth"]["tells_room_from_constraint"] is False
    assert seen["0.85"]["separation"]["estimate_growth"]["mean"] == pytest.approx(1)
    assert seen["0.85"]["separation"]["estimate_growth"]["tells_room_from_constraint"] is True
    assert seen["0.85"]["separation"]["feedback_age_ms"]["tells_room_from_constraint"] is False
    assert seen["1.05"]["separation"]["feedback_age_ms"]["mean"] == pytest.approx(1)
    assert seen["0.85"]["flagged_share_by_schedule"]["underutilized"]["mean"] == 0  # growth 1.5: not flagged
    assert seen["0.85"]["flagged_share_by_schedule"]["queue-building"]["mean"] == 1
    assert seen["0.85"]["flagged_share_by_schedule"]["near-capacity"]["sources"] == 0
    assert seen["1.05"]["median_by_state"]["feedback_age_ms"] == dict(room=80.0, constrained=140.0)
    assert headroom.FLAG == 1.05


def test_reading_follows_the_intervals():
    def utility(source, regime, level, epoch):
        lift = {"a": 0.0, "b": 0.4, "c": 0.8, "d": 1.2}[source]
        base = (
            {0: 20, 1: 24, 2: 30, 3: 22, 4: 5}[level]
            if regime == "underutilized"
            else {0: 28, 1: 24, 2: 18, 3: 12, 4: 5}[level]
        )
        return base + lift * (1 + level)

    report = headroom.analyse(invented(utility))
    assert report["exploratory"] is True and report["confirmatory"] is False
    assert report["reading"]["tuning_the_fixed_level_pays_out_of_sample"] is True
    assert report["reading"]["knowing_the_schedule_adds_to_a_tuned_fixed_level"] is True
    assert report["reading"]["switching_by_hold_could_add_more_at_best"] is False
    assert set(report["reading"]["signals_that_tell_room_from_constraint"]) == set(pilot.NAMES)


def with_signals(capture):
    """Give the invented sessions what a real one records and the fixture leaves out."""
    for root in sorted(p for p in capture.iterdir() if p.is_dir()):
        rows = json.loads((root / "cohorts.json").read_text())
        (root / "cohorts.json").write_text(json.dumps([dict(r, assignment_ms=r["ack_ms"] - 2) for r in rows]))
        sender = json.loads((root / "sender_observations.json").read_text())
        for poll in sender["decisions"]:
            poll["observation"]["raw_source"]["rtcp_rtt_s"] = 0.055
        sender["feedback_events"] = [
            dict(capture_request_ms=t - 90.0, received_ms=float(t))
            for t in range(
                int(sender["measurement_start_ms"]) + 200, int(sender["measurement_cutoff_ms"]), 100
            )
        ]
        (root / "sender_observations.json").write_text(json.dumps(sender))
        (root / "manifest.json").unlink()  # the files changed: seal the session again
        seal_directory(root, sorted(f.name for f in root.iterdir()), pilot.PEER_STAGE)


def test_reader_takes_each_hold_and_checks_itself_against_the_pilot_s_report(tmp_path, capsys):
    capture = invented_capture(tmp_path)
    with_signals(capture)
    reported, _ = pilot.collect(capture)
    sessions = headroom.collect(capture, json.loads(json.dumps(reported)))
    assert len(sessions) == 30
    one = next(s for s in sessions if s["trial_id"] == "rp-s0-underutilized-l1")
    assert [h["epoch"] for h in one["holds"]] == list(range(6)) and one["level"] == 1
    assert math.isnan(one["holds"][0]["estimate_growth"]) and one["holds"][1]["estimate_growth"] == 1
    assert one["holds"][2]["feedback_age_ms"] == pytest.approx(90) and one["holds"][2][
        "rtt_ms"
    ] == pytest.approx(55)
    assert one["holds"][3]["utility"] == pytest.approx(34) and one["holds"][3]["requests"] > 70
    wrong = json.loads(json.dumps(reported))
    wrong[0]["after_startup"]["utility"] += 1
    with pytest.raises(ValueError, match="do not add up to the pilot's reported utility"):
        headroom.collect(capture, wrong)
    table = tmp_path / "sessions.json"
    table.write_text(json.dumps(reported))
    out = tmp_path / "headroom.json"
    headroom.main(["--capture", str(capture), "--sessions", str(table), "--out", str(out)])
    printed = json.loads(capsys.readouterr().out)
    assert printed["tuning_the_fixed_level_pays_out_of_sample"] is False  # invented: 1.05 is the best level
    written = json.loads(out.read_text())
    assert written["abi"] == pilot.ABI + "_headroom" and len(written["pilot_sessions_sha256"]) == 64
    assert written["plans"]["levels_chosen_in_sample"]["fixed"] == "1.05"
    with pytest.raises(SystemExit):
        headroom.main(["--capture", str(capture), "--sessions", str(table), "--out", str(out)])
