"""The simulator's receiver layer on invented numbers. Nothing here is fitted to a pilot or is native evidence."""

import json
import math

import numpy as np
import pytest

from media_rl import native_ladder_pilot as ladder
from media_rl import typed_bitrate_native_receiver as receiver
from media_rl.native_actuator_panel import REGIMES
from media_rl.typed_bitrate_b1_forecast import load_settings, mirror, simulator

CONFIG, SETTINGS = simulator(), load_settings()
INVENTED = receiver.Layer(
    e0_bps=800_000.0, b0=12.0, gu=70.0, gq=0.4, tau_s=8.0, c0=20.0, cu=10.0, s0=8.0, s1=0.1, return_ms=30.0,
    rate_kbps=(150.0, 400.0, 1600.0), psnr_db=(30.0, 32.0, 35.0), never_encoded=(0.06, 0.03, 0.04),
)  # fmt: skip


def session(regime, arm, layer=INVENTED, moving=True):
    schedule = REGIMES[regime]
    return receiver.run(
        CONFIG, mirror(schedule, CONFIG, SETTINGS["relay"]), receiver.ARM_POLICIES[arm], layer, moving
    )


def test_the_buffer_rises_at_once_and_falls_slowly():
    assert receiver.falls(20.0, 50.0, 10.0, 100) == 50.0
    assert receiver.falls(50.0, 20.0, 10.0, 100) == pytest.approx(20 + 30 * math.exp(-0.01))
    buffer = 200.0
    for _ in range(100):  # ten seconds with a time constant of ten
        buffer = receiver.falls(buffer, 20.0, 10.0, 100)
    assert buffer == pytest.approx(20 + 180 / math.e)


def test_on_time_is_the_share_of_spread_ages_under_the_deadline():
    assert receiver.on_time_share(150.0, 10.0) == pytest.approx(0.5)
    assert receiver.on_time_share(130.0, 10.0) == pytest.approx(0.97725, abs=1e-5)
    assert receiver.on_time_share(400.0, 10.0) < 1e-9 < 1 - 1e-9 < receiver.on_time_share(60.0, 10.0)


def test_the_tables_are_linear_in_log_rate_and_flat_outside():
    assert INVENTED.table(INVENTED.psnr_db, 150.0) == pytest.approx(30.0)
    assert INVENTED.table(INVENTED.psnr_db, math.sqrt(150.0 * 400.0)) == pytest.approx(31.0)
    assert INVENTED.table(INVENTED.psnr_db, 20.0) == 30.0 and INVENTED.table(INVENTED.psnr_db, 9000.0) == 35.0
    assert INVENTED.table(INVENTED.never_encoded, 800.0) == pytest.approx(0.035)


def test_a_session_starts_as_natively_and_the_cap_stays_a_cap():
    made = session("collapse-recovery", "1.05")
    steps, assignments = made["steps"], made["assignments"]
    assert [a["at_ms"] for a in assignments] == [0, 3000, 6000, 9000, 12000, 15000]
    assert assignments[0]["requested_bps"] == 315_000  # 1.05 of the 300 kbit/s a native session starts at
    assert assignments[1]["requested_bps"] == 840_000  # 1.05 of the estimate start-up leaves: e0
    assert assignments[1]["feedback_age_ms"] == pytest.approx(steps["age"][20:29].mean() + 30.0, abs=3)
    drop = (steps["now"] >= 7000) & (steps["now"] < 9000)  # the request of the hold is still above a megabit
    assert steps["requested"][drop].min() > 1_000_000 and steps["rate"][drop].max() < 350_000
    assert (steps["rate"][drop] <= steps["estimate"][drop].max()).all()
    assert (
        steps["buffer"][drop].min() > 4 * steps["buffer"][:60].max() and steps["on_time"][drop].max() < 0.01
    )
    late = steps["buffer"][steps["now"] >= 9000]
    assert (np.diff(late) < 0).all() and late[-1] > 1.5 * steps["buffer"][:60].max()  # it falls, slowly


def test_the_rules_are_the_native_ones_and_a_held_buffer_takes_their_signal_away():
    fast, slow = session("collapse-recovery", "fast ladder"), session("collapse-recovery", "ladder")
    assert [a["decision"] for a in fast["assignments"]] == [
        "start",
        "hold",
        "down",
        "cut",
        "hold",
        "hold",
        "hold",
    ]
    assert [a["at_ms"] for a in fast["assignments"]][3:] == [
        7000,
        10000,
        13000,
        16000,
    ]  # the clock restarts at a cut
    assert [a["step"] for a in slow["assignments"]] == [3, 3, 2, 0, 0, 0] and len(slow["assignments"]) == 6
    held = session("underutilized", "ladder", moving=False)
    assert set(held["steps"]["buffer"]) == {INVENTED.b0}
    assert {a["decision"] for a in held["assignments"][1:]} == {
        "hold"
    }  # at the top, with young acknowledgements


def test_a_summary_has_two_spans_six_stretches_and_three_phases():
    now = np.arange(0, 18600, 100, dtype=float)
    steps = dict(
        now=now,
        utility=np.where(now < 3000, 10.0, 20.0),
        on_time=np.where(now < 3000, 0.5, 1.0),
        own=np.ones(186),
        rate=np.full(186, 300_000.0),
        capacity=np.full(186, 600_000.0),
        age=np.where(now < 6000, 80.0, 200.0),
        shown=np.where(now < 9000, 1.0, 0.0),
        one_way=np.full(186, 33.0),
        buffer=np.where(now < 6000, 20.0, np.where(now < 12000, 100.0, 60.0)),
        load=np.full(186, 0.5),
        estimate=np.where(now < 3000, 300_000.0, 800_000.0),
    )
    assignments = [
        dict(epoch=0, at_ms=0.0, step=3, ratio=1.05, decision="start", requested_bps=315_000),
        dict(epoch=1, at_ms=3000.0, step=3, ratio=1.05, decision="hold", requested_bps=840_000),
        dict(epoch=2, at_ms=7600.0, step=0, ratio=0.25, decision="cut", requested_bps=150_000),
    ]
    made = receiver.summarise(dict(steps=steps, assignments=assignments), REGIMES["collapse-recovery"])
    assert made["session"]["utility"] == pytest.approx((30 * 10 + 156 * 20) / 186)
    assert made["after_startup"] == dict(
        utility=20.0, on_time=1.0, own=1.0, encoder_over_capacity=0.5, encoder_kbps=300.0
    )
    assert [b["age_median_ms"] for b in made["bins"]] == [
        80.0,
        80.0,
        200.0,
        None,
        None,
        None,
    ]  # of frames shown
    assert made["bins"][2]["delay_and_buffer_ms"] == pytest.approx(133.0) and made["bins"][3]["load"] is None
    assert [b["ratio"] for b in made["bins"]] == [
        1.05,
        1.05,
        1.05,
        0.25,
        0.25,
        0.25,
    ]  # in force at the middle
    assert [p["jitter_buffer_ms"] for p in made["phases"]] == [20.0, 100.0, None]
    assert made["estimate_hold2_bps"] == 800_000.0 and made["decisions"] == ["hold", "cut"]


def test_a_native_session_gives_spread_estimate_and_return_time(tmp_path):
    def label(source_id, at, age):
        return dict(
            source_id=source_id,
            capture_request_ms=at,
            readback_age_ms=age,
            identifiable_ontime=age is not None and age <= 150,
            ontime_sampled_psnr_contribution=30.0 if age is not None and age <= 150 else 0.0,
        )

    def row(epoch, ack, bwe):
        return dict(
            epoch=epoch, ack_ms=ack, ratio=0.65, requested_bps=0.65 * bwe, base_bwe_bps=bwe,
            cluster_id="a", network_regime="queue-building", arm=1,
        )  # fmt: skip

    labels = [label(k, 1000.0 + 100 * k, 80.0 + k) for k in range(21)] + [label(99, 3500.0, None)]
    polls = [dict(feedback_input=None)]
    polls += [
        dict(
            feedback_input=dict(
                source_id=k, capture_request_ms=1000.0 + 100 * k, received_ms=1000.0 + 100 * k + 80 + k + 25
            )
        )
        for k in (0, 0, 5, 10)
    ]
    polls += [
        dict(feedback_input=dict(source_id=99, capture_request_ms=3500.0, received_ms=3700.0))
    ]  # never shown
    snapshot = dict(
        phase="high", capacity_mbps=1.2, interval_ms=6000, frames_decoded=100, frames_encoded=100,
        mean_native_jitter_buffer_s=0.03, mean_native_jitter_buffer_target_s=0.03, freeze_count=0,
        network=dict(a_to_b=dict(offered_wire_bytes=1000, dropped_wire_bytes=0)),
    )  # fmt: skip

    def later(frames):  # the page's snapshots are cumulative
        return dict(snapshot, frames_decoded=frames, frames_encoded=frames)

    (tmp_path / "cohorts.json").write_text(json.dumps([row(1, 4000.0, 700_000.0), row(0, 1000.0, 300_000.0)]))
    (tmp_path / "native_derived.json").write_text(json.dumps(dict(quality=dict(source_labels=labels))))
    (tmp_path / "summary.json").write_text(json.dumps(dict(snapshots=[snapshot, later(200), later(300)])))
    (tmp_path / "sender_observations.json").write_text(json.dumps(dict(decisions=polls)))
    made = receiver.session_targets(tmp_path)
    assert (made["level"], made["regime"], made["source"]) == ("0.65", "queue-building", "a")
    assert made["estimate_hold2_bps"] == 700_000.0 and made["returns_ms"] == [
        25.0,
        25.0,
        25.0,
    ]  # each frame once
    first = made["bins"][0]
    low, high = np.percentile([80.0 + k for k in range(21)], [16, 84])
    assert first["age_median_ms"] == 90.0 and first["spread_ms"] == pytest.approx((high - low) / 2)
    assert made["bins"][1]["spread_ms"] is None and made["phases"][0]["jitter_buffer_ms"] == pytest.approx(
        30.0
    )
    both = receiver.targets([made, dict(made, source="b", estimate_hold2_bps=900_000.0)])
    cell = both["cells"]["0.65"]["queue-building"]
    assert cell["sources"] == 2 and cell["estimate_hold2_bps"] == 800_000.0 and both["sessions"] == 2
    assert both["return_ms"] == 25.0 and both["return_points"] == 6 and len(both["spread_points"]) == 2


def invented_range_pilot(layer):
    """Targets and a report as the range pilot would give them if the simulator with ``layer`` were the truth."""
    made = receiver.exact(CONFIG, SETTINGS, receiver.LEVEL_POLICIES, layer)
    cells = {
        level: {
            regime: dict(
                bins=dict(age_median_ms=[b["age_median_ms"] for b in own["bins"]]),
                phases=dict(jitter_buffer_ms=[p["jitter_buffer_ms"] for p in own["phases"]]),
                estimate_hold2_bps=own["estimate_hold2_bps"],
            )
            for regime, own in by_regime.items()
        }
        for level, by_regime in made.items()
    }
    points = [[age, layer.s0 + layer.s1 * age] for age in range(60, 400, 20)]
    seen = dict(cells=cells, spread_points=points, return_ms=layer.return_ms, return_points=7)

    def entry(mean, lift=0.0):
        return dict(mean=mean + lift, interval95=[mean + lift - 0.2, mean + lift + 0.2])

    def table(values):
        return {
            level: dict(level=entry(values[level]), minus_reference=entry(values[level], -values["1.05"]))
            for level in receiver.LEVELS
        }

    span = "after_startup"
    knots = dict(
        zip(
            ("encoder_kbps", "psnr_on_time_db", "never_encoded"),
            (layer.rate_kbps, layer.psnr_db, layer.never_encoded),
            strict=True,
        )
    )
    everywhere = {
        key: table(dict(zip(receiver.LEVELS, values, strict=True))) for key, values in knots.items()
    }
    for quantity in ("utility", "on_time", "encoder_over_capacity"):
        everywhere[quantity] = table(receiver.over_schedules(made, span, quantity))
    by_schedule = {
        regime: {
            span: {
                quantity: table({level: made[level][regime][span][quantity] for level in receiver.LEVELS})
                for quantity in ("utility", "on_time", "encoder_over_capacity")
            }
        }
        for regime in REGIMES
    }
    return seen, dict(all_schedules={span: everywhere}, by_schedule=by_schedule)


def test_the_fit_recovers_a_layer_from_sessions_the_simulator_made_itself():
    truth = receiver.Layer(
        e0_bps=800_000.0, b0=12.0, gu=70.0, gq=0.4, tau_s=8.0, c0=20.0, cu=10.0, s0=8.0, s1=0.1, return_ms=30.0,
        rate_kbps=(180.0, 330.0, 470.0, 780.0, 1070.0), psnr_db=(29.8, 31.7, 33.0, 34.0, 36.0),
        never_encoded=(0.065, 0.027, 0.028, 0.039, 0.081),
    )  # fmt: skip
    seen, native = invented_range_pilot(truth)
    fitted, stages, beside = receiver.fit(seen, native, CONFIG, SETTINGS)
    assert fitted.e0_bps == pytest.approx(truth.e0_bps, rel=0.02)
    assert (fitted.b0, fitted.gu, fitted.gq, fitted.tau_s) == pytest.approx((12.0, 70.0, 0.4, 8.0), rel=0.05)
    assert (fitted.s0, fitted.s1, fitted.return_ms) == pytest.approx((8.0, 0.1, 30.0))
    assert fitted.c0 + 0.5 * fitted.cu == pytest.approx(25.0, abs=3)  # a median against a mean: about right
    assert fitted.rate_kbps == truth.rate_kbps and fitted.psnr_db == truth.psnr_db
    assert stages["buffer"]["cells"] == 48 and stages["buffer"]["rms_log"] < 0.02  # four ratios, three phases
    assert stages["buffer"]["rms_ms"] < 1 and not any(stages["buffer"]["at_a_bound"])
    assert 60 < stages["age"]["cells"] <= 96 and stages["spread"]["rms_ms"] < 1e-6
    assert stages["spread"]["points"] == sum(age <= 300 for age in range(60, 400, 20))
    assert beside["comparisons"]["disagrees"] == 0 and beside["schedules_with_the_same_best_level"] == 4
    one = beside["levels"]["utility"]["0.65"]
    assert one["simulated"] == pytest.approx(one["native"], abs=1.0)
    with pytest.raises(ValueError, match="every level and schedule"):
        receiver.fit(dict(seen, cells={"0.25": seen["cells"]["0.25"]}), native, CONFIG, SETTINGS)


def entry(mean, half):
    return dict(mean=mean, interval95=[mean - half, mean + half])


def test_a_difference_is_judged_by_sign_and_size():
    lost = entry(-3.0, 2.0)
    assert (
        receiver.judge(-1.2, lost)["verdict"] == "agrees" and receiver.judge(0.3, lost)["verdict"] == "flat"
    )
    assert (
        receiver.judge(-0.49, lost)["verdict"] == "flat"
        and receiver.judge(0.5, lost)["verdict"] == "disagrees"
    )
    assert receiver.judge(9.0, entry(1.0, 2.0))["verdict"] == "not established"
    assert receiver.judge(9.0, dict(mean=None, interval95=None))["verdict"] == "not established"


def test_the_verdict_is_the_one_fixed_in_the_design():
    def block(verdicts):
        return {pair: dict(verdict=v) for pair, v in verdicts.items()}

    good = block(
        {"ladder minus 0.25": "agrees", "0.25 minus 1.05": "agrees", "0.25 minus 0.65": "not established"}
    )
    local = block(
        {
            "ladder minus 0.25": "agrees",
            "ladder minus 0.65": "agrees",
            "0.65 minus 1.05": "agrees",
            "0.25 minus 1.05": "agrees",
            "fast ladder minus ladder": "flat",
        }
    )
    made = receiver.decide(good, dict(a=local))
    assert made["verdict"] == "the layer predicts the controller pilot"
    assert made["share_agreeing_under_the_schedules"] == 0.8 and made["established_over_all_schedules"] == 2
    weak = dict(local, **block({"0.65 minus 1.05": "flat"}))  # three of five
    assert receiver.decide(good, dict(a=weak))["verdict"] == "the layer predicts the order only"
    turned = dict(local, **block({"fast ladder minus ladder": "agrees", "ladder minus 0.65": "disagrees"}))
    made = receiver.decide(
        good, dict(a=turned)
    )  # four of five agree, but a rule beats a tuned level it lost to
    assert made["verdict"] == "the layer predicts the order only"
    assert made["rule_against_tuned_level_reversed"] == ["a: ladder minus 0.65"]
    for bad in ("flat", "disagrees"):
        missed = dict(good, **block({"0.25 minus 1.05": bad}))
        assert (
            receiver.decide(missed, dict(a=local))["verdict"]
            == "the layer does not predict the controller pilot"
        )
    nothing = block({"ladder minus 0.25": "not established"})
    assert (
        receiver.decide(nothing, dict(a=local))["verdict"]
        == "the layer does not predict the controller pilot"
    )


def invented_controller_pilot(lift):
    """A controller-pilot report with the given endpoint per arm, the same under every schedule."""

    def table():
        return dict(
            arms={name: dict(level=entry(20.0 + lift[name], 3.0)) for name in ladder.NAMES},
            contrasts={f"{a} minus {b}": entry(lift[a] - lift[b], 1.0) for a, b in receiver.PAIRS},
        )

    spans = {span: dict(utility=table(), on_time=table()) for span in receiver.SPANS}
    return dict(all_schedules=spans, by_schedule={regime: spans for regime in REGIMES})


def test_the_test_runs_the_five_arms_and_reports_what_the_design_lists():
    native = invented_controller_pilot(
        {"ladder": 0.0, "fast ladder": 0.5, "0.25": 4.0, "0.65": 4.5, "1.05": -2.0}
    )
    made = receiver.test(INVENTED, native, CONFIG, dict(SETTINGS, replicates=2))
    assert made["verdict"] == made["spans"]["after_startup"]["verdict"] and set(made["spans"]) == set(
        receiver.SPANS
    )
    assert made["verdict"] in {
        "the layer predicts the controller pilot",
        "the layer predicts the order only",
        "the layer does not predict the controller pilot",
    }
    seen = made["spans"]["after_startup"]
    assert set(seen["differences_over_all_schedules"]) == {f"{a} minus {b}" for a, b in receiver.PAIRS}
    assert (
        seen["established_over_all_schedules"] == 8
    )  # two of the invented differences are inside their intervals
    assert 0 <= seen["endpoints_inside_the_native_interval"] <= 5
    for name in ladder.CANDIDATES:
        for regime in REGIMES:
            did = made["what_the_rules_did"][name][regime]
            assert sum(did["share_of_decisions"].values()) == pytest.approx(1.0)
            assert sum(did["share_of_later_assignments_at_each_ratio"].values()) == pytest.approx(1.0)
    assert len(made["timeline"]["fast ladder"]["collapse-recovery"]["utility"]) == 6
    held = made["ablations"]["buffer_held_at_its_base"]
    assert set(held["endpoint"]) == set(ladder.NAMES) and held["verdict"].startswith("the layer")
    built = made["ablations"]["simulator_as_built"]
    assert set(built["own_utility"]) == {"0.25", "0.65", "1.05"} and built[
        "native_order_of_the_fixed_arms"
    ] == ["0.65", "0.25", "1.05"]
    shares = made["robustness"]["share_of_replicates_agreeing"]
    assert (
        made["robustness"]["replicates"] == 2
        and len(shares) == 8
        and all(0 <= v <= 1 for v in shares.values())
    )


def test_commands_refuse_to_overwrite_and_to_take_another_report(tmp_path):
    taken = tmp_path / "taken.json"
    taken.write_text("{}")
    with pytest.raises(SystemExit):
        receiver.main(["fit", "--targets", str(taken), "--pilot", str(taken), "--out", str(taken)])
    with pytest.raises(SystemExit):  # an empty file is not the range pilot's report
        receiver.main(
            ["fit", "--targets", str(taken), "--pilot", str(taken), "--out", str(tmp_path / "layer.json")]
        )
    with pytest.raises(SystemExit):  # nor the controller pilot's
        receiver.main(
            ["test", "--layer", str(taken), "--pilot", str(taken), "--out", str(tmp_path / "report.json")]
        )
    assert not (tmp_path / "layer.json").exists() and not (tmp_path / "report.json").exists()
