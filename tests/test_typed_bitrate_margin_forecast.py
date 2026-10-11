"""The forecast of the long-session pilot, with an invented layer. Nothing here is native evidence."""

import json

import pytest
from test_typed_bitrate_native_receiver import INVENTED, SETTINGS

from media_rl import native_margin_pilot as margin
from media_rl import typed_bitrate_margin_forecast as forecast

CONFIG = forecast.simulator()


@pytest.fixture(scope="module")
def made():
    return json.loads(json.dumps(forecast.forecast(INVENTED, CONFIG, dict(SETTINGS, replicates=2))))


def test_the_simulated_session_is_as_long_as_the_pilot_s_and_runs_its_rule():
    assert CONFIG.steps * CONFIG.dt_ms == 60000
    seen = forecast.simulate(CONFIG, SETTINGS, INVENTED)
    assert set(seen) == set(margin.NAMES) and set(seen["margin"]) == set(margin.REGIMES)
    one = seen["margin"]["one-drop"]
    assert len(one["bins"]) == 10 and len(one["phases"]) == 10
    moves = [a["decision"] for a in one["assignments"]]
    assert moves[:2] == ["start", "cruise"] and ("cut" in moves or "drop" in moves)  # it sees the drop
    assert set(moves) <= {"start", "cruise", "up", "down", "hold", "drop", "cut", "return"}
    fixed = seen["0.65"]["steady-tight"]["assignments"]
    assert [a["at_s"] for a in fixed] == [3.0 * k for k in range(20)] and {a["ratio"] for a in fixed} == {
        0.65
    }


def test_the_forecast_has_every_arm_schedule_and_difference(made):
    assert set(made["spans"]) == {"session", "after_startup"}
    seen = made["spans"]["session"]
    assert set(seen["levels"]["utility"]) == set(margin.NAMES)
    assert set(seen["levels"]["utility"]["margin"]["by_schedule"]) == set(margin.REGIMES)
    assert set(seen["differences_over_all_schedules"]) == set(forecast.PAIRS) and len(forecast.PAIRS) == 6
    levels = {name: e["all_schedules"] for name, e in seen["levels"]["utility"].items()}
    assert seen["differences_over_all_schedules"]["margin minus 0.65"] == pytest.approx(
        levels["margin"] - levels["0.65"]
    )
    assert (
        set(made["what_the_rule_does"]) == {"margin"}
        and len(made["timeline"]["1.05"]["one-drop"]["utility"]) == 10
    )
    robust = made["robustness"]
    assert robust["replicates"] == 2 and set(robust["differences"]) == set(forecast.PAIRS)
    assert all(0 <= e["share_positive"] + e["share_negative"] <= 1 for e in robust["differences"].values())


def native_report(made, flip=None, widen=()):
    """A pilot report that agrees with the forecast, except where ``flip`` turns a difference round
    or ``widen`` makes its interval include zero."""

    def table(own_levels, own_differences):
        contrasts = {}
        for pair, value in own_differences.items():
            mean = -value if pair == flip else value
            half = abs(mean) + 1 if pair in widen else 0.25 * abs(mean)
            contrasts[pair] = dict(mean=mean, interval95=[mean - half, mean + half])
        arms = {
            name: dict(level=dict(mean=value + 0.3, interval95=[value - 2, value + 2]))
            for name, value in own_levels.items()
        }
        return dict(utility=dict(arms=arms, contrasts=contrasts))

    spans = {}
    for span, seen in made["spans"].items():
        levels = {name: e["all_schedules"] for name, e in seen["levels"]["utility"].items()}
        spans[span] = table(levels, seen["differences_over_all_schedules"])
    by_schedule = {
        regime: {
            span: table(
                {name: e["by_schedule"][regime] for name, e in seen["levels"]["utility"].items()},
                seen["differences_under_each_schedule"][regime],
            )
            for span, seen in made["spans"].items()
        }
        for regime in margin.REGIMES
    }
    return dict(abi=margin.ABI + "_report", all_schedules=spans, by_schedule=by_schedule)


def test_the_forecast_is_judged_by_the_rule_of_the_design(made):
    same = forecast.judged(made, native_report(made))
    seen = same["spans"]["session"]
    counted = [e["verdict"] for e in seen["differences_over_all_schedules"].values()]
    assert (
        set(counted) <= {"agrees", "flat", "not established"}
        and seen["endpoints_inside_the_native_interval"] == 4
    )
    if (
        "flat" not in counted and "agrees" in counted
    ):  # every forecast difference the invented layer makes large enough
        assert same["verdict"] in {"the layer forecast the pilot", "the layer forecast the order only"}
    large = max(
        made["spans"]["session"]["differences_over_all_schedules"].items(), key=lambda item: abs(item[1])
    )[0]
    turned = forecast.judged(made, native_report(made, flip=large))
    assert turned["spans"]["session"]["differences_over_all_schedules"][large]["verdict"] == "disagrees"
    assert turned["verdict"] == "the layer did not forecast the pilot"
    nothing = forecast.judged(made, native_report(made, widen=forecast.PAIRS))
    assert nothing["spans"]["session"]["established_over_all_schedules"] == 0
    assert (
        nothing["verdict"] == "the layer did not forecast the pilot"
    )  # nothing established: nothing forecast


def test_commands_refuse_to_overwrite_and_to_take_other_records(tmp_path):
    taken = tmp_path / "taken.json"
    taken.write_text("{}")
    with pytest.raises(SystemExit):
        forecast.main(["forecast", "--layer", str(taken), "--out", str(taken)])
    with pytest.raises(SystemExit):  # an empty file is not the fitted layer
        forecast.main(["forecast", "--layer", str(taken), "--out", str(tmp_path / "forecast.json")])
    with pytest.raises(SystemExit):  # nor a forecast and a pilot report
        forecast.main(
            ["judge", "--forecast", str(taken), "--pilot", str(taken), "--out", str(tmp_path / "judged.json")]
        )
    assert not (tmp_path / "forecast.json").exists() and not (tmp_path / "judged.json").exists()
