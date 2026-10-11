"""Paper evidence for the development pilot, from a report on invented sessions. Not native evidence."""

import json
import re

import pytest
from test_native_range_pilot import invented_capture

from media_rl import native_range_pilot as pilot
from media_rl import native_range_pilot_report as report


@pytest.fixture
def made(tmp_path):
    sessions, plan = pilot.collect(invented_capture(tmp_path))
    return json.loads(
        json.dumps(pilot.analyse(sessions, planned=len(plan["order"])))
    )  # as read back from disk


def test_levels_are_named_in_a_sentence():
    assert report.named([]) == "no level"
    assert report.named(["0.25"]) == "0.25"
    assert report.named(["0.25", "ceiling"]) == "0.25 and the ceiling"
    assert report.named(["0.25", "0.65", "ceiling"]) == "0.25, 0.65 and the ceiling"


def test_macros_carry_the_pilot_name_and_the_reading(made):
    rows = report.macros(made)
    assert all(re.fullmatch(r"RangePilot[A-Za-z]+", name) for name in rows)
    assert (
        rows["RangePilotSessions"] == "30"
        and rows["RangePilotPlanned"] == "30"
        and rows["RangePilotSources"] == "3"
    )
    assert rows["RangePilotOnTimeTop"] == "100.0" and rows["RangePilotPsnrCeiling"] == "40.0"
    assert rows["RangePilotUtilityDiffLow"] == "$-$4.00" and rows["RangePilotUtilityDiffLowT"].startswith(
        "[$-$4.00"
    )
    assert "RangePilotUtilityDiffTop" not in rows  # the reference is not compared with itself
    assert "RangePilotLateDiffQuarter" not in rows
    assert rows["RangePilotMoves"] == "0.25 and the ceiling"
    assert (
        rows["RangePilotPays"] == "no level" and rows["RangePilotCosts"] == "0.25, 0.65, 0.85 and the ceiling"
    )
    assert rows["RangePilotEmpties"] == "0.25" and rows["RangePilotCeilingWorst"] == "is"


def test_tables_have_a_column_per_level_and_tolerate_empty_schedules(made):
    levels = report.table_levels(made)
    assert levels.count("\\\\") == 1 + 8 + 2 * 4 and "0.25 & 0.65 & 0.85 & 1.05 & ceiling" in levels
    assert "n/a" in levels  # the invented capture has no near-capacity sessions
    differences = report.table_differences(made)
    assert differences.count("\\\\") == 1 + 3 + 2 * 4
    assert (
        "0.25 $-$ 1.05" in differences
        and "ceiling $-$ 1.05" in differences
        and "1.05 $-$ 1.05" not in differences
    )


def test_export_writes_evidence_and_refuses_other_reports(made, tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(made))
    result = report.export(path, tmp_path / "evidence")
    assert result["sessions"] == 30 and result["macros"] > 50
    evidence = (tmp_path / "evidence" / "evidence.tex").read_text()
    assert evidence.count("\\newcommand") == result["macros"] and "\\RangePilotCeilingWorst}{is}" in evidence
    assert (tmp_path / "evidence" / "range_pilot_levels.tex").exists()
    assert len(json.loads((tmp_path / "evidence" / "provenance.json").read_text())) == 1
    path.write_text(json.dumps(dict(made, confirmatory=True)))
    with pytest.raises(ValueError, match="confirms and promotes nothing"):
        report.export(path, tmp_path / "other")
    path.write_text(json.dumps(dict(made, abi="something_else")))
    with pytest.raises(ValueError, match="pilot's report is required"):
        report.export(path, tmp_path / "other")
