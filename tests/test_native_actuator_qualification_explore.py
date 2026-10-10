"""Exploratory N1 description: source-level means, causal carry-over from consecutive holds, interaction."""

import gzip
import json
import math

import numpy as np
import pytest

from media_rl import native_actuator_qualification_explore as explore
from media_rl.native_actuator_qualification_panel import REGIMES


def synthetic(sources=4, peers=6, seed=0):
    """Rows with a known response, a known effect of the arm on the next estimate and a known interaction."""
    rng, rows = np.random.default_rng(seed), []
    for s in range(sources):
        for regime in REGIMES:
            for peer in range(peers):
                bwe = 1e6 * (1 + 0.1 * s)
                for epoch in range(6):
                    arm = int(rng.integers(3))
                    constrained = regime != REGIMES[0]
                    rows.append(
                        dict(
                            cluster_id=f"source-{s}",
                            trial_id=f"{s}-{regime}-{peer}",
                            network_regime=regime,
                            epoch=epoch,
                            arm=arm,
                            complete=True,
                            base_bwe_bps=bwe,
                            encoder_bps=bwe * (0.5 + 0.15 * arm) + rng.normal(0, 1e3),
                            utility=30 + (-2.0 if constrained else 3.0) * arm + rng.normal(0, 0.05),
                            ontime_fraction=1.0 - (0.1 * arm if constrained else 0.0),
                        )
                    )
                    bwe *= math.exp(0.05 * (arm - 1))
    return rows


def test_response_levels_and_contrasts_are_recovered_at_source_level():
    report = explore.explore(synthetic())
    level = report["response_level"]["overall"]
    assert [round(level["arms"][k]["mean"], 2) for k in ("0.65", "0.85", "1.05")] == [0.5, 0.65, 0.8]
    assert level["contrasts"]["0.85 - 0.65"]["sources"] == 4
    assert level["contrasts"]["1.05 - 0.65"]["mean"] == pytest.approx(0.30, abs=0.01)
    low, high = level["contrasts"]["0.85 - 0.65"]["interval95"]
    assert low < 0.15 < high or abs(low - 0.15) < 0.01
    assert (
        report["exploratory"] is True
        and report["registered"] is False
        and report["changes_the_n1_outcome"] is False
    )


def test_estimate_growth_uses_consecutive_holds_of_one_peer_only():
    rows = synthetic()
    grown = explore.estimate_growth(rows)
    assert len(grown) == len(rows) * 5 // 6 and all(r["epoch"] < 5 for r in grown)
    growth = explore.explore(rows)["estimate_growth"]["overall"]["contrasts"]
    assert growth["0.85 - 0.65"]["mean"] == pytest.approx(0.05, abs=1e-9)
    assert growth["1.05 - 0.65"]["mean"] == pytest.approx(0.10, abs=1e-9)
    gap = [r for r in rows if not (r["trial_id"] == rows[0]["trial_id"] and r["epoch"] == 1)]
    assert len(explore.estimate_growth(gap)) == len(grown) - 2


def test_regime_interaction_and_best_arm_tally():
    report = explore.explore(synthetic())["quality"]["utility"]
    for regime in REGIMES[1:]:
        entry = report["regime_interaction"][regime]
        assert entry["mean"] == pytest.approx(10.0, abs=0.2) and entry["holm_p_value"] < 0.01
    assert report["best_arm_by_source"][REGIMES[0]] == {"0.65": 0, "0.85": 0, "1.05": 4}
    assert report["best_arm_by_source"][REGIMES[1]] == {"0.65": 4, "0.85": 0, "1.05": 0}
    pairs = report["highest_minus_lowest_by_hold_pair"][REGIMES[1]]
    assert set(pairs) == set(explore.HOLD_PAIRS) and pairs["holds 1-2"]["mean"] == pytest.approx(
        -4.0, abs=0.2
    )


def test_planning_sizes_a_later_study_from_the_spread_of_source_contrasts():
    assert explore.sources_needed(1.0, 1.0, 0.8) == 10 and explore.sources_needed(1.0, 0.5, 0.8) == 34
    assert explore.sources_needed(1.0, 1e-6, 0.8, limit=50) is None
    note = explore.planning(synthetic(sources=6))
    assert note["for_planning_only"] is True and note["added_after_the_exploratory_results"] is True
    first, second = note["contrasts"].values()
    assert first["sources"] == 6 and first["per_source_sd"] > 0
    assert second["mean"] == pytest.approx(
        4.0, abs=0.2
    )  # the synthetic rows favour the low ratio when constrained
    needed = second["sources_needed"]
    assert needed["effect 1, power 0.9"] >= needed["effect 1, power 0.8"] >= needed["effect 2, power 0.8"]


def with_state(rows, seed=3):
    """Give synthetic rows a pre-hold state in which a rising RTT makes the low ratio the better one."""
    rng, out = np.random.default_rng(seed), []
    for r in rows:
        rising = float(rng.uniform(0, 30))
        hot = rising > 20
        present = dict(status="present")
        out.append(
            dict(
                r,
                state=dict(
                    rtt_trend_ms=dict(present, value=rising),
                    rtt_ms=dict(present, value=float(rng.uniform(40, 60))),
                    loss_fraction=dict(status="absent", value=None)
                    if r["epoch"] == 1
                    else dict(present, value=0.0),
                    jitter_ms=dict(present, value=float(rng.uniform(1, 5))),
                ),
                utility=30.0 + (3.0 if hot else -3.0) * (2 - r["arm"]) / 2 + float(rng.normal(0, 0.1)),
                ontime_fraction=0.9,
            )
        )
    return out


def test_conditional_pass_finds_a_signal_that_modifies_the_effect():
    rows = with_state(synthetic(sources=5, peers=8))
    held = explore.with_signals(rows)
    assert len(held) == len(rows) * 5 // 6 and all(r["epoch"] > 0 for r in held)
    report = explore.conditional(rows)
    trend = report["signals"]["rtt_trend_ms"]
    assert trend["side"] == "above" and trend["threshold"] == pytest.approx(20.0, abs=1.0)
    assert trend["flagged_share"] == pytest.approx(1 / 3, abs=0.02) and set(
        trend["flagged_share_by_regime"]
    ) == set(REGIMES)
    assert trend["utility"]["flagged"]["mean"] == pytest.approx(3.0, abs=0.3)
    assert trend["utility"]["rest"]["mean"] == pytest.approx(-3.0, abs=0.3)
    assert trend["utility"]["interaction"]["holm_p_value"] < 0.01
    assert trend["utility"]["flagged_middle_ratio"]["mean"] == pytest.approx(1.5, abs=0.3)
    assert report["candidates"] == ["rtt_trend_ms"] and report["second_pass_on_the_same_rows"] is True
    growth = report["signals"]["estimate_growth"]
    assert growth["side"] == "below" and growth["holds"] == len(held)
    assert report["signals"]["loss_fraction"]["holds"] < len(held)  # absent values are left out, not imputed


def test_flag_sizing_uses_flagged_holds_and_pools_the_lower_ratios():
    rows = with_state(synthetic(sources=5, peers=8))
    note = explore.flag_sizing(rows, growth=0.0)  # in the synthetic rows the estimate falls after ratio 0.65
    assert note["for_planning_only"] is True and note["third_look_at_the_same_rows"] is True
    assert 0 < note["flagged_share"] < 1 and note["smallest_flagged_cell"] >= 1
    assert len(note["flagged_holds_per_source"]) == note["benefit"]["sources"] == 5
    assert set(note["flagged_share_by_previous_arm"]) == {"0", "1", "2"}
    assert 0 <= note["share_of_flagged_holds_after_the_top_arm"] <= 1
    assert note["per_source_sd"] > 0 and set(note["sources_needed"]) >= {
        "effect 1, power 0.8",
        "effect 2, power 0.9",
    }


def test_holm_is_monotone_and_bounded():
    assert explore.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert explore.holm([0.9, 0.8]) == [1.0, 1.0]


def test_load_reads_gzip_and_keeps_complete_rows(tmp_path):
    rows = synthetic(sources=2, peers=1)
    rows[0] = dict(rows[0], complete=False, encoder_bps=None)
    path = tmp_path / "cohorts.json.gz"
    path.write_bytes(gzip.compress(json.dumps(rows).encode()))
    loaded, digest = explore.load(path)
    assert len(loaded) == len(rows) - 1 and len(digest) == 64
    explore.main(["--rows", str(path), "--out", str(tmp_path / "out.json")])
    assert json.loads((tmp_path / "out.json").read_text())["rows_sha256"] == digest
    with pytest.raises(SystemExit):
        explore.main(["--rows", str(path), "--out", str(tmp_path / "out.json")])
