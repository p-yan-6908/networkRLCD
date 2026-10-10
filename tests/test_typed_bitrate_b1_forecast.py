"""Simulator forecast of Native Phase B1: protocol mirror, registered estimator, pre-declared reading."""

import json

import numpy as np
import pytest

from media_rl import native_backoff_benefit as benefit
from media_rl import typed_bitrate_b1_forecast as forecast

SETTINGS = forecast.load_settings()
CONFIG = forecast.simulator()


def test_settings_file_matches_the_coded_defaults_and_bad_ones_are_rejected(tmp_path):
    assert forecast.load_settings("configs/jevbwe_typed_b1_forecast_v1.json") == forecast.DEFAULTS
    for bad in (dict(window_ms=[2600, 1800]), dict(window_ms=[0, 3100]), dict(replicates=1), dict(extra=1)):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            forecast.load_settings(path)
    path.write_text(json.dumps(dict(relay=dict(rtt_ms=50.0, queue_mbit=0.0))))
    with pytest.raises(ValueError, match="relay"):
        forecast.load_settings(path)


def test_variants_are_b1_ratios_and_the_levels_n1_realised():
    made = forecast.variants(SETTINGS)
    assert made["as_built"] == list(benefit.RATIOS) == [0.65, 0.85, 1.05]
    realised = SETTINGS["n1_reference"]["encoder_over_bwe"]["all"]
    assert np.allclose(np.array(made["n1_realised"]) * forecast.ENCODER_SHARE, realised)
    assert (
        max(made["n1_realised"]) < 1 < max(made["as_built"])
    )  # natively the top arm stays below the estimate


def test_mirror_follows_the_native_schedule_and_the_relay():
    assert CONFIG.steps == 186 and CONFIG.bwe == "acked"
    trace = forecast.mirror(forecast.REGIMES["collapse-recovery"], CONFIG, SETTINGS["relay"])
    assert (
        trace.capacity[0] == trace.capacity[59] == 1.2 and trace.capacity[60] == trace.capacity[119] == 0.35
    )
    assert trace.capacity[120] == trace.capacity[-1] == 1.2
    assert set(trace.base_rtt) == {50.0} and not trace.loss.any() and not trace.jitter.any()
    assert np.allclose(trace.buffer_scale * forecast.SimulatorConfig().queue_mbit, 0.24)
    noisy = forecast.mirror(
        forecast.REGIMES["underutilized"], CONFIG, SETTINGS["relay"], np.random.default_rng(1)
    )
    assert 3.4 <= noisy.capacity[0] <= 4.6 and 35 <= noisy.base_rtt[0] <= 65 and noisy.jitter.any()
    assert 0.002 <= noisy.loss[0] <= 0.012


def test_session_freezes_the_estimate_and_holds_one_request_per_hold():
    trace = forecast.mirror(forecast.REGIMES["underutilized"], CONFIG, SETTINGS["relay"])
    ratios = forecast.variants(SETTINGS)["as_built"]
    rows = forecast.session(CONFIG, trace, ratios, (2, 0, 2, 2, 1, 0), SETTINGS["window_ms"], "t")
    assert [r["epoch"] for r in rows] == list(range(6)) and [r["arm"] for r in rows] == [2, 0, 2, 2, 1, 0]
    assert rows == forecast.session(CONFIG, trace, ratios, (2, 0, 2, 2, 1, 0), SETTINGS["window_ms"], "t")
    assert all(
        r["complete"] is True and r["base_bwe_bps"] > 0 and 0 <= r["ontime_fraction"] <= 1 for r in rows
    )
    # With room on the link the encoder settles near its share of the request by the outcome window.
    late = rows[3]
    assert late["encoder_over_bwe"] == pytest.approx(1.05 * forecast.ENCODER_SHARE, abs=0.1)
    assert rows[5]["encoder_over_bwe"] < rows[4]["encoder_over_bwe"] < late["encoder_over_bwe"]
    held = benefit.flag_rows([dict(r, source="s", regime="underutilized") for r in rows], benefit.Plan())
    assert len(held) == 5 and [r["previous_arm"] for r in held] == [2, 0, 2, 2, 1]
    # A request of 0.65 of the estimate keeps the acked rate too low for the estimate to grow.
    assert held[1]["flagged"] is True and held[1]["previous_arm"] == 0


def test_exact_panel_enumerates_every_arm_sequence_once():
    rows = forecast.exact_panel(CONFIG, SETTINGS, [0.65, 0.85, 1.05], holds=3)
    assert len(rows) == 4 * 27 * 3 and len({r["trial_id"] for r in rows}) == 4 * 27
    assert {r["source"] for r in rows} == {"exact"} and {r["regime"] for r in rows} == set(forecast.REGIMES)
    for epoch in range(3):
        arms = [r["arm"] for r in rows if r["epoch"] == epoch]
        assert np.bincount(arms).tolist() == [36, 36, 36]  # the randomisation distribution, exactly
    table = forecast.levels(rows)
    assert set(table["encoder_over_bwe"]) == {*forecast.REGIMES, "all"}
    assert all(len(v) == 3 for v in table["estimate_log_growth"].values())


def test_sampled_panel_gives_every_variant_the_same_arms_and_paths():
    small = dict(SETTINGS, replicates=2)
    one = forecast.sampled_panel(CONFIG, small, [0.65, 0.85, 1.05], holds=3, peers=2)
    two = forecast.sampled_panel(CONFIG, small, [0.6, 0.8, 0.9], holds=3, peers=2)
    assert [(r["trial_id"], r["epoch"], r["arm"]) for r in one] == [
        (r["trial_id"], r["epoch"], r["arm"]) for r in two
    ]
    assert len(one) == 2 * 4 * 2 * 3 and {r["source"] for r in one} == {"r0", "r1"}
    first = [r["base_bwe_bps"] for r in one if r["epoch"] == 0]
    assert first == [r["base_bwe_bps"] for r in two if r["epoch"] == 0]  # before any arm acts


def test_forecast_class_and_reading_are_fixed_in_advance():
    assert forecast.sign([0.1, 0.3]) == "helps" and forecast.sign([-0.3, -0.1]) == "hurts"
    assert forecast.sign([-0.1, 0.3]) == forecast.sign(None) == "no_clear_benefit"
    assert forecast.reading("helps", "helps") == forecast.reading("helps", "helps_below_practical_gate")
    assert forecast.reading("helps", "helps") == "agrees in sign"
    assert forecast.reading("helps", "no_practically_relevant_benefit") == "simulator overstates the benefit"
    assert forecast.reading("hurts", "no_practically_relevant_benefit") == "agrees in sign"
    assert forecast.reading("no_clear_benefit", "helps") == "simulator misses the benefit"
    assert {forecast.reading(c, "inconclusive") for c in forecast.CLASSES} == {"not assessed"}
    with pytest.raises(ValueError):
        forecast.reading("helps", "qualified")


def test_study_reports_both_actuator_descriptions_and_claims_nothing_native():
    report = forecast.study(dict(SETTINGS, replicates=3), holds=4, peers=10)
    assert report["synthetic"] is True and report["native_evidence"] is False
    assert report["models_trained_or_evaluated"] == 0 and report["holds_per_sender"] == 4
    assert report["b1_freeze_sha256"] == json.loads(forecast.FREEZE.read_text())["sha256"]
    assert set(report["variants"]) == {"as_built", "n1_realised"}
    assert set(report["readings_fixed_in_advance"]) == set(benefit.OUTCOMES)
    for made in report["variants"].values():
        assert made["forecast"] in forecast.CLASSES and made["exact"]["sessions"] == 4 * 81
        assert made["sampled"]["sessions"] == 3 * 4 * 10 and 0 < made["exact"]["flag"]["all"] < 1
        names = set(made["exact"]["contrasts"])
        assert names == set(made["sampled"]["contrasts"])
        assert {"primary", "other_holds", "next_hold", "after_top", "flagged_minus_other"} <= names
        assert {f"regime:{g}" for g in forecast.REGIMES} <= names
        assert len(made["exact"]["flag"]["by_previous_arm"]) == 3
    assert set(forecast.headline(report)) == {"as_built", "n1_realised"}


def test_cli_refuses_an_existing_output(tmp_path):
    with pytest.raises(SystemExit):
        forecast.main(["--out", str(tmp_path)])
