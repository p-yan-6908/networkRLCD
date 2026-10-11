"""Paper evidence for the controller pilot, from a report on invented sessions. Not native evidence."""

import json
import re

import pytest
from test_native_ladder_pilot import invented_sessions

from media_rl import native_ladder_pilot as ladder
from media_rl import native_ladder_pilot_report as report

LIFT = {"ladder": 0.0, "fast ladder": 2.0, "0.25": 5.0, "0.65": 1.0, "1.05": -3.0}


def stretches(source, regime, arm):
    bins = [
        dict(
            utility=20.0 + arm + k,
            on_time=0.5 + 0.05 * k,
            age_median_ms=100.0 + 10 * arm,
            ratio=1.05 if k < 2 else 0.25,
            requested_kbps=300.0,
        )
        for k in range(ladder.BINS)
    ]
    phases = [
        dict(
            jitter_buffer_ms=20.0 + 10 * arm + 30 * k,
            relay_dropped=0.01 * k,
            offered_over_capacity=0.2 + 0.1 * k,
        )
        for k in range(len(ladder.PHASES))
    ]
    return dict(source=source, regime=regime, arm=arm, bins=bins, phases=phases)


@pytest.fixture
def made():
    def utility(source, regime, name, repetition):
        return 20 + LIFT[name] + 0.1 * "abc".index(source) * (name == "0.25") + 0.05 * repetition

    sessions = invented_sessions(utility)
    found = ladder.analyse(sessions, planned=len(sessions))
    found["plan_sha256"] = "f" * 64
    seen = [
        stretches(s, r, a) for s in "ab" for r in ("queue-building", "collapse-recovery") for a in range(5)
    ]
    timeline = dict(ladder.timeline(seen), plan_sha256="f" * 64, sessions=len(sessions))
    gain = dict(mean=4.0, interval95=[1.0, 7.0], p_value=0.01, sources=3)
    headroom = dict(
        abi="native_range_pilot_v1_headroom",
        exploratory=True,
        plans=dict(
            leaving_one_source_out=dict(
                fixed_minus_reference=gain,
                schedule_aware_minus_fixed=dict(gain, mean=2.5, interval95=[0.5, 4.5]),
            ),
            levels_chosen_in_the_folds=dict(fixed={"0.25": 2, "0.65": 1, "0.85": 0}),
        ),
    )
    return tuple(
        json.loads(json.dumps(part)) for part in (found, timeline, headroom)
    )  # as read back from disk


def test_a_reading_is_put_into_words():
    assert report.verdict({"0.25": -1, "0.65": -1, "1.05": 0}) == (
        "loses to 0.25 and 0.65 and is not separated from 1.05"
    )
    assert report.verdict({"0.25": 0, "0.65": -1, "1.05": 1}) == (
        "loses to 0.65, beats 1.05 and is not separated from 0.25"
    )
    assert report.verdict({"0.25": 1, "0.65": 1, "1.05": 1}) == "beats 0.25, 0.65 and 1.05"


def test_macros_carry_the_pilot_name_the_reading_and_the_timeline(made):
    rows = report.macros(*made)
    assert all(re.fullmatch(r"LadderPilot[A-Za-z]+", name) for name in rows)
    assert rows["LadderPilotSessions"] == "60" and rows["LadderPilotSources"] == "3"
    assert rows["LadderPilotTunedGain"] == "$+$4.00" and rows["LadderPilotTunedGainT"] == "[$+$1.00, $+$7.00]"
    assert rows["LadderPilotScheduleGain"] == "$+$2.50" and rows["LadderPilotFoldsQuarter"] == "2"
    assert rows["LadderPilotFoldsLow"] == "1" and "LadderPilotFoldsTop" not in rows
    assert rows["LadderPilotUtilityFast"] == "22.02" and rows["LadderPilotLaterUtilityFast"] == "23.02"
    assert rows["LadderPilotOnTimeTop"] == "100.0" and rows["LadderPilotRepeatQuarter"] == "0.05"
    assert rows["LadderPilotUtilityDiffFastLadder"] == "$+$2.00"
    assert rows["LadderPilotUtilityDiffLadderQuarter"] == "$-$5.10"
    assert rows["LadderPilotUtilityDiffLadderQuarterT"].startswith("[$-$5.")
    assert (
        rows["LadderPilotUtilityDiffQuarterTop"] == "$+$8.10" and "LadderPilotUtilityDiffTopLow" not in rows
    )
    assert rows["LadderPilotReadingLadder"] == "loses to 0.25 and 0.65 and beats 1.05"
    assert rows["LadderPilotReadingFast"] == "loses to 0.25 and beats 0.65 and 1.05"
    assert rows["LadderPilotFastCut"] == "helps"
    assert rows["LadderPilotUpShare"] == "20.0"  # one of five later decisions in the invented sessions
    assert (
        rows["LadderPilotDropBufferCollapseFast"] == "60"
        and rows["LadderPilotDropBufferRecoveryQuarter"] == "100"
    )
    assert rows["LadderPilotDropLoadRecoveryTop"] == "40" and "LadderPilotDropBufferHighFast" not in rows


def test_tables_have_a_column_per_arm_and_tolerate_empty_schedules(made):
    found, timeline, _ = made
    arms = report.table_arms(found)
    assert arms.count("\\\\") == 1 + 9 + 2 * 4 and "ladder & fast ladder & 0.25 & 0.65 & 1.05" in arms
    assert "n/a" in arms  # the invented sessions have no near-capacity schedule
    differences = report.table_differences(found)
    assert differences.count("\\\\") == 1 + 10 and differences.count("\\midrule") == 1 + 3
    assert "fast ladder $-$ ladder" in differences and "0.25 $-$ 0.65" in differences
    over_time = report.table_timeline(timeline)
    assert over_time.count("\\\\") == 1 + 4 * 5 and "0--3~s" in over_time and "15--18~s" in over_time
    assert "Utility, all schedules & ladder & 20.0 & 21.0" in over_time
    held = report.table_phases(timeline)
    assert held.count("\\\\") == 2 + 2 * 5 and "high & collapse & recovery" in held
    assert "Collapse-recovery & ladder & 20 & 50 & 80 & 20 & 30 & 40 & 0.0 & 1.0 & 2.0" in held


def test_export_writes_evidence_and_refuses_other_records(made, tmp_path):
    found, timeline, headroom = made

    def write(*bodies):
        paths = tmp_path / "report.json", tmp_path / "timeline.json", tmp_path / "headroom.json"
        for path, body in zip(paths, bodies, strict=True):
            path.write_text(json.dumps(body))
        return paths

    out = tmp_path / "generated"
    result = report.export(*write(*made), out)
    assert result["sessions"] == 60 and result["macros"] == len(report.macros(*made))
    assert {p.name for p in out.iterdir()} == {
        "evidence.tex",
        "provenance.json",
        "ladder_pilot_arms.tex",
        "ladder_pilot_differences.tex",
        "ladder_pilot_timeline.tex",
        "ladder_pilot_phases.tex",
    }
    assert "\\newcommand{\\LadderPilotFastCut}{helps}" in (out / "evidence.tex").read_text()
    assert len(json.loads((out / "provenance.json").read_text())) == 3
    for wrong, match in (
        ((dict(found, abi="native_range_pilot_v1_report"), timeline, headroom), "controller pilot"),
        ((dict(found, confirmatory=True), timeline, headroom), "confirms and promotes nothing"),
        (
            (dict(found, learned_controller_promoted=True), timeline, headroom),
            "confirms and promotes nothing",
        ),
        ((found, dict(timeline, added_after_the_report_was_read=False), headroom), "added after"),
        ((found, dict(timeline, plan_sha256="0" * 64), headroom), "another capture"),
        ((found, dict(timeline, sessions=59), headroom), "another capture"),
        ((found, dict(timeline, bin_ms=1000), headroom), "other stretches"),
        ((found, timeline, dict(headroom, exploratory=False)), "headroom"),
        ((found, timeline, dict(headroom, abi="native_ladder_pilot_v1_report")), "headroom"),
    ):
        with pytest.raises(ValueError, match=match):
            report.export(*write(*wrong), tmp_path / "refused")
    assert not (tmp_path / "refused").exists()
    missing = [str(tmp_path / name) for name in ("no-report.json", "no-timeline.json", "no-headroom.json")]
    with pytest.raises(SystemExit):
        report.main(
            ["--report", missing[0], "--timeline", missing[1], "--headroom", missing[2], "--out", str(out)]
        )
