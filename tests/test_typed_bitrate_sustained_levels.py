"""The simulator on sustained cap levels, set beside the native pilot. Synthetic; nothing here is native evidence."""

import json

import pytest

from media_rl import native_range_pilot as pilot
from media_rl import typed_bitrate_sustained_levels as sustained
from media_rl.typed_bitrate_b1_forecast import load_settings, mirror, simulator

SETTINGS = dict(load_settings(), replicates=3)
CONFIG = simulator()


def test_levels_are_the_native_pilot_s():
    assert sustained.LEVELS == pilot.LEVELS and sustained.NAMES == pilot.NAMES
    assert sustained.REFERENCE == pilot.REFERENCE


def test_a_sustained_level_is_read_from_the_second_hold_on_and_the_ceiling_asks_for_the_limit():
    schedule = sustained.REGIMES["underutilized"]
    trace = mirror(schedule, CONFIG, SETTINGS["relay"])
    low, top, ceiling = (sustained.sustained(CONFIG, trace, level) for level in (0, 3, 4))
    assert set(low) == set(sustained.QUANTITIES)
    assert 0 < low["encoder_over_capacity"] < top["encoder_over_capacity"] <= ceiling["encoder_over_capacity"]
    assert 0 <= low["on_time"] <= 1 and low["utility"] > 0
    assert sustained.sustained(CONFIG, trace, 0) == low  # a fresh sender every time: the same again


def test_report_is_marked_synthetic_and_after_the_pilot_and_pairs_levels_on_the_same_paths():
    report = sustained.study(SETTINGS)
    assert report["synthetic"] is True and report["written_after_the_native_pilot"] is True
    assert report["forecast"] is False and report["models_fitted"] == 0
    assert set(report["exact"]) == set(sustained.REGIMES)
    table = report["sampled"]["all_schedules"]["utility"]
    assert set(table) == set(sustained.NAMES)
    assert table["1.05"]["minus_reference"]["mean"] == 0 and table["0.25"]["level"]["sources"] == 3
    assert "against_the_native_pilot" not in report
    assert sustained.study(SETTINGS)["sampled"] == report["sampled"]  # seeded


def entry(mean, low, high):
    return dict(
        level=dict(mean=mean, interval95=[mean - 1, mean + 1]),
        minus_reference=dict(mean=(low + high) / 2, interval95=[low, high]),
    )


def test_comparison_counts_agreement_only_when_both_intervals_exclude_zero():
    assert (
        sustained.sign(dict(interval95=[0.1, 0.4])) == 1
        and sustained.sign(dict(interval95=[-0.4, -0.1])) == -1
    )
    assert sustained.sign(dict(interval95=[-0.1, 0.4])) == 0 and sustained.sign(dict(interval95=None)) == 0
    simulated_table = {
        "0.25": entry(1.0, -0.5, -0.3),
        "0.65": entry(1.2, -0.3, -0.1),
        "0.85": entry(1.3, -0.1, 0.1),
        "1.05": entry(1.4, 0.0, 0.0),
        "ceiling": entry(0.9, -0.6, -0.4),
    }
    native_table = {
        "0.25": entry(26.0, 2.0, 8.0),
        "0.65": entry(27.0, -1.0, 7.0),
        "0.85": entry(24.0, -0.4, 5.0),
        "1.05": entry(21.0, 0.0, 0.0),
        "ceiling": entry(13.0, -11.0, -5.0),
    }
    simulated = dict(
        all_schedules=dict(utility=simulated_table),
        by_schedule={regime: dict(utility=simulated_table) for regime in sustained.REGIMES},
    )
    native = dict(
        all_schedules=dict(after_startup=dict(utility=native_table)),
        by_schedule={regime: dict(after_startup=dict(utility=native_table)) for regime in sustained.REGIMES},
    )
    made = sustained.compare(simulated, native)
    pairs = made["all_schedules"]["differences_from_the_reference"]
    assert pairs["0.25"]["verdict"] == "disagrees" and pairs["ceiling"]["verdict"] == "agrees"
    assert pairs["0.65"]["verdict"] == "unclear" and pairs["0.85"]["verdict"] == "unclear"
    assert made["all_schedules"]["best_level"] == dict(simulator="1.05", native="0.65")
    assert made["comparisons"] == dict(agrees=5, disagrees=5, unclear=10)
    assert made["schedules_with_the_same_best_level"] == 0


def test_command_writes_the_report_and_refuses_to_overwrite(tmp_path, capsys):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(dict(replicates=2)))
    out = tmp_path / "made" / "report.json"
    sustained.main(["--settings", str(settings), "--out", str(out)])
    printed = json.loads(capsys.readouterr().out)
    assert set(printed["utility"]) == set(sustained.NAMES) and printed["against"] is None
    assert json.loads(out.read_text())["study"] == sustained.STUDY
    with pytest.raises(SystemExit):
        sustained.main(["--settings", str(settings), "--out", str(out)])
