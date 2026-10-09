import json

import numpy as np
import pytest

from media_rl.typed_bitrate import TypedConfig, load_config
from media_rl.typed_bitrate_baselines import run_rule
from media_rl.typed_bitrate_crossover import (
    designs,
    headline,
    load_settings,
    needed,
    session,
    study,
    summarise,
)
from media_rl.typed_bitrate_experiment import run

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
    bootstrap_samples=50,
    workers=1,
)


def config(**changes):
    return TypedConfig(**{"base_ratio": 0.9, **changes}).validate()


def test_settings_reject_inconsistent_studies(tmp_path):
    assert load_settings()["sessions"] == 32
    for bad in (
        dict(pairs=[]),
        dict(pairs=[[1.0, 1.0]]),
        dict(block_ms=[0]),
        dict(washout_ms=[-1]),
        dict(sessions=1),
        dict(minimum_effect=0),
        dict(blocks=[1]),
    ):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            load_settings(path)


def test_a_constant_session_is_a_fixed_ratio_episode():
    c = config(steps=120)
    for scenario, seed in (("steady", 3), ("dip", 5)):
        utility, measured = session(c, scenario, seed, 0.9)
        assert measured is None
        assert utility == pytest.approx(run_rule(c, scenario, seed, dict(kind="fixed", ratio=0.9))["utility"])
        same, means = session(c, scenario, seed, (0.9, 0.9, 30, 0, 0))  # crossing over to itself
        assert (
            same == pytest.approx(utility) and means[0] != means[1]
        )  # the blocks differ, the session does not


def test_a_crossover_session_measures_each_ratio_in_its_own_blocks():
    c = config(steps=120)
    whole, means = session(c, "steady", 3, (1.0, 0.6, 30, 0, 0))  # blocks A B A B
    swapped, other = session(c, "steady", 3, (1.0, 0.6, 30, 0, 1))  # blocks B A B A
    assert whole != swapped and means != other
    assert whole == pytest.approx(np.mean(means))  # equal block counts and no washout
    washed, trimmed = session(c, "steady", 3, (1.0, 0.6, 30, 10, 0))
    assert washed == whole and trimmed != means  # the washout changes the estimate, not the session
    _, lonely = session(c, "steady", 3, (1.0, 0.6, 120, 0, 0))  # one block: the second ratio never runs
    assert np.isnan(lonely[1]) and not np.isnan(lonely[0])


def test_designs_keep_a_measured_part_and_two_blocks():
    c = config(steps=120)
    made = designs(c, load_settings() | dict(block_ms=[3000, 6000, 9000], washout_ms=[0, 3000]))
    assert [(d["block"], d["washout"]) for d in made] == [(30, 0), (60, 0), (60, 30)]


def test_summary_recovers_a_known_effect_and_counts_sessions():
    rng = np.random.default_rng(0)
    links, sessions = 40, 200
    truth = rng.normal(0, 0.05, links)
    level = rng.normal(0, 0.3, (links, sessions))  # sessions differ far more than ratios do
    a = 1.0 + level
    b = a + truth[:, None] + rng.normal(0, 0.02, (links, sessions))
    estimate = truth[:, None] + rng.normal(0, 0.05, (links, sessions))
    row = summarise(estimate, a - 0.01, truth, b - a, a, b, 0.01)
    assert row["usable"] and row["slope"] == pytest.approx(1, abs=0.05) and abs(row["bias"]) < 0.005
    assert row["sign_agreement"] == 1 and row["experiment_cost"] == pytest.approx(-0.01)
    assert (
        row["sessions_needed_identical_traces"]
        < row["sessions_needed"]
        < row["sessions_needed_whole_sessions"]
    )
    halved = summarise(0.5 * estimate, a, truth, b - a, a, b, 0.01)
    assert not halved["usable"] and halved["slope"] == pytest.approx(0.5, abs=0.05)
    shifted = summarise(estimate + 0.02, a, truth, b - a, a, b, 0.01)
    assert not shifted["usable"] and shifted["bias"] == pytest.approx(0.02, abs=0.005)
    assert needed(np.ones(3), np.zeros(3), 0.01) is None
    assert needed(np.full(3, 0.1), np.full(3, 0.05), 0.01) == pytest.approx(16)


def test_study_compares_crossover_estimates_with_identical_trace_differences(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(TINY))
    run(load_config(path), tmp_path / "run", splits=("validation",))
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            dict(pairs=[[1.0, 0.9], [1.0, 0.6]], block_ms=[3000, 6000], washout_ms=[0, 1000], sessions=3)
        )
    )
    report = study(tmp_path / "run", tmp_path / "crossover", settings)
    assert report["synthetic_only"] is True and report["links"] == 4 and report["sessions"] == 3
    assert [(p["a"], p["b"]) for p in report["pairs"]] == [(1.0, 0.9), (1.0, 0.6)]
    for pair in report["pairs"]:
        assert [(d["block_ms"], d["washout_ms"]) for d in pair["designs"]] == [
            (3000, 0),
            (3000, 1000),
            (6000, 0),
            (6000, 1000),
        ]
        for d in pair["designs"]:
            assert np.isfinite(
                [d["bias"], d["slope"], d["intercept"], d["session_spread"], d["experiment_cost"]]
            ).all()
            assert isinstance(d["usable"], bool)
    assert "B=0.9 minus A=1" in headline(report)
    with pytest.raises(FileExistsError):
        study(tmp_path / "run", tmp_path / "crossover", settings)
    settings.write_text(json.dumps(dict(pairs=[[1.0, 1.5]])))
    with pytest.raises(ValueError):
        study(tmp_path / "run", tmp_path / "above", settings)  # above the governor's ceiling
