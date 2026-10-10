"""Headroom under truncated option sets: re-selected base, identical traces, pre-declared reading."""

import json

import numpy as np
import pytest

from media_rl.typed_bitrate import TypedConfig
from media_rl.typed_bitrate_experiment import run_many
from media_rl.typed_bitrate_headroom import (
    DEFAULTS,
    headline,
    load_settings,
    measure,
    reading,
    score,
    truncated,
)

TINY = dict(
    steps=120,
    tune_episodes=4,
    train_episodes=8,
    rounds=2,
    calibration_episodes=4,
    hidden=8,
    epochs=3,
    batch_size=32,
    model_seeds=[0],
    validation_seeds=[1],
    test_seeds=[2],
    scenarios=["steady", "collapse"],
    train_scenarios=["steady", "collapse"],
    bootstrap_samples=50,
    workers=1,
)
PANELS = {"x": (["steady", "collapse", "ramp"], [11, 12])}


def config(**changes):
    return TypedConfig(**{**TINY, **changes}).validate()


def test_truncation_keeps_lower_options_and_reselects_the_base():
    tuned, tune = truncated(config(), 1.0)
    assert tuned.ratios == [0.6, 0.7, 0.8, 0.9, 1.0] and tuned.base_ratio in tuned.ratios
    assert tune["source"] == "id_tune_split" and len(tune["sweep"]) == 5
    with pytest.raises(ValueError, match="one of the options"):
        truncated(config(), 0.95)
    with pytest.raises(ValueError, match="at least two"):
        truncated(config(), 0.6)


def test_score_matches_direct_episodes_on_the_same_traces():
    tuned, _ = truncated(config(), 1.0)
    families, seeds = PANELS["x"]
    scored = score(tuned, families, seeds)
    direct = run_many(tuned, None, [("collapse", 12, dict(kind="fixed", ratio=0.8))])[0]
    assert scored[0.8]["utility"].shape == (3, 2) and scored[0.8]["utility"][1, 1] == direct["utility"]
    oracle = run_many(tuned, None, [("ramp", 11, dict(kind="oracle"))])[0]
    assert scored["oracle"]["utility"][2, 0] == oracle["utility"]
    assert (
        sum(scored["oracle"]["option_share"]) == pytest.approx(1.0)
        and len(scored["oracle"]["option_share"]) == 5
    )


def test_measure_compares_each_set_with_the_widest_on_identical_traces():
    settings = load_settings()
    settings.update(tops=[1.05, 1.0], samples=50)
    sets = measure(config(), settings, PANELS)
    wide, cut = sets
    assert "against_widest" not in wide and wide["ratios"][-1] == 1.05 and cut["ratios"][-1] == 1.0
    panel, change = cut["panels"]["x"], cut["against_widest"]["x"]
    assert panel["headroom"]["families"] == 3
    assert panel["headroom"]["mean"] == pytest.approx(panel["oracle_utility"] - panel["base_utility"])
    assert change["headroom"]["mean"] == pytest.approx(
        panel["headroom"]["mean"] - wide["panels"]["x"]["headroom"]["mean"]
    )
    assert change["oracle_minus_widest_base"]["mean"] == pytest.approx(
        panel["oracle_utility"] - wide["panels"]["x"]["base_utility"]
    )
    assert change["headroom_share"] == pytest.approx(
        panel["headroom"]["mean"] / wide["panels"]["x"]["headroom"]["mean"]
    )
    assert change["reading"] in ("below", "above", "mixed")
    text = headline(dict(sets=sets))
    assert "top 1.05" in text and "share of the widest set's headroom" in text
    json.dumps(sets, allow_nan=False)


def test_reading_follows_the_pre_declared_thresholds():
    settings = load_settings()
    lost, kept = dict(family_t_interval95=[-0.05, -0.01]), dict(family_t_interval95=[-0.01, 0.01])
    assert reading(0.8, lost, settings) == "below"
    assert reading(0.4, lost, settings) == "above"
    assert reading(0.4, kept, settings) == "mixed"
    assert reading(0.6, lost, settings) == "mixed"


def test_settings_are_validated(tmp_path):
    assert load_settings() == DEFAULTS and np.all(np.diff(DEFAULTS["tops"]) < 0)
    for bad in (
        dict(tops=[1.0, 1.05]),
        dict(tops=[1.05]),
        dict(panels={}),
        dict(above_share=0.8),
        dict(extra=1),
    ):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            load_settings(path)
