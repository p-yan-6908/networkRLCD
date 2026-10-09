import json

import numpy as np
import pytest

from media_rl.networks import MLP
from media_rl.typed_bitrate import FEATURE_DIM, TypedConfig, TypedModel, load_config
from media_rl.typed_bitrate_experiment import run
from media_rl.typed_bitrate_factual import (
    NEVER,
    block_episode,
    budget,
    choose,
    collect,
    doubly_robust,
    fit,
    headline,
    load_settings,
    package,
    study,
    train,
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
    validation_seeds=[1, 3],
    test_seeds=[2],
    scenarios=["steady", "collapse"],
    bootstrap_samples=50,
    workers=1,
)
SMALL = dict(
    blocks=[40, 120],
    control_blocks=40,
    seeds=[0, 1],
    max_updates=60,
    min_epochs=1,
    check_every=20,
    patience=2,
)


def config(**changes):
    return TypedConfig(**{"base_ratio": 0.9, **changes}).validate()


def test_settings_reject_inconsistent_studies(tmp_path):
    assert load_settings()["blocks"] == [5000, 20000, 80000, 320000, 1280000]
    assert load_settings()["control_blocks"] == 80000
    for bad in (
        dict(blocks=[100, 50]),
        dict(blocks=[5]),
        dict(seeds=[]),
        dict(shares=[0.5, 0.2, 0.2]),
        dict(block_probability=0),
        dict(margins=[-0.1]),
        dict(patience=0),
        dict(control_blocks=0),
        dict(min_epochs=0.5),
        dict(budgets=[1]),  # unknown key
    ):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            load_settings(path)


def test_a_factual_block_observes_exactly_the_rollout_value_of_its_option():
    c = config(steps=240)
    for scenario, seed in (("step", 4), ("dip", 6), ("wifi", 8)):
        rows = block_episode(c, scenario, seed, 17, 0.5)
        again = block_episode(c, scenario, seed, 17, 0.5)
        count = len(rows["arms"])
        assert count and np.array_equal(rows["outcomes"], again["outcomes"])  # deterministic
        assert rows["states"].shape == (count, FEATURE_DIM) and rows["values"].shape == (count, len(c.ratios))
        assert rows["arms"].min() >= 0 and rows["arms"].max() < len(c.ratios)
        executed = rows["values"][np.arange(count), rows["arms"]]
        assert np.abs(rows["outcomes"] - executed).max() < 1e-12  # the same estimand, one option
        blind = block_episode(c, scenario, seed, 17, 0.5, truth=False)
        assert np.isnan(blind["values"]).all()
        for key in ("states", "arms", "outcomes"):  # computing hindsight never disturbs the episode
            assert np.array_equal(blind[key], rows[key])
    arms = np.concatenate([block_episode(c, "steady", seed, seed, 1.0)["arms"] for seed in range(30)])
    assert set(arms.tolist()) == set(range(len(c.ratios)))  # every option is explored
    assert len(block_episode(c, "steady", 1, 1, 1.0)["arms"]) == 4  # back-to-back blocks never overlap


def test_collect_meets_the_budget_and_splits_by_episode():
    c = config(steps=120, workers=1)
    data = collect(c, 0, 60, 0.5)
    assert len(data["arms"]) >= 60 and np.all(np.diff(data["episode"]) >= 0)
    assert data["states"].shape == (len(data["arms"]), FEATURE_DIM) and data["values"].shape[1] == len(
        c.ratios
    )
    assert data["states"].dtype == np.float32 and not np.isnan(data["values"]).any()
    partial = collect(c, 0, 60, 0.5, truth_blocks=20)
    known = ~np.isnan(partial["values"]).any(axis=1)
    assert 20 <= known.sum() < len(known) and known[:20].all() and not known[-1]
    assert np.array_equal(partial["outcomes"][:60], data["outcomes"][:60])  # the same factual rows
    assert not np.array_equal(data["outcomes"][:60], collect(c, 1, 60, 0.5)["outcomes"][:60])
    parts = budget(data, 60, [0.7, 0.1, 0.2])
    assert sum(len(p["arms"]) for p in parts) == 60 and all(len(p["arms"]) for p in parts)
    owners = [set(p["episode"].tolist()) for p in parts]
    assert not owners[0] & owners[1] and not owners[1] & owners[2] and not owners[0] & owners[2]
    assert np.array_equal(np.concatenate([p["outcomes"] for p in parts]), data["outcomes"][:60])


def test_choose_leaves_the_base_only_above_the_margin():
    advantage = np.array([[0.0, 0.3, 0.0], [0.0, 0.05, 0.0], [0.2, -0.1, 0.0], [-0.1, -0.2, 0.0]])
    assert choose(advantage, 2, 0.0).tolist() == [1, 1, 0, 2]
    assert choose(advantage, 2, 0.1).tolist() == [1, 2, 0, 2]
    assert choose(advantage, 2, NEVER).tolist() == [2, 2, 2, 2]


def test_doubly_robust_value_is_unbiased_with_a_wrong_value_model():
    rng = np.random.default_rng(0)
    n, options = 60000, 3
    context = rng.normal(size=n)
    true = np.stack([context, 0.5 + 0 * context, -context], axis=1)  # value of each option
    arms = rng.integers(options, size=n)  # uniform randomisation
    outcomes = true[np.arange(n), arms] + rng.normal(0, 0.5, n)
    policy = np.where(context > 0, 0, 2)  # worth E|context| = 0.798
    exact = doubly_robust(true, arms, outcomes, policy)
    wrong = doubly_robust(np.zeros_like(true), arms, outcomes, policy)
    assert exact == pytest.approx(0.798, abs=0.01)
    assert wrong == pytest.approx(0.798, abs=0.03)  # correct on average, only noisier
    assert doubly_robust(true, arms, outcomes, np.full(n, 1)) == pytest.approx(0.5, abs=0.01)


def test_masked_regression_learns_each_option_from_its_own_rows():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(4000, 4))
    true = np.stack([x[:, 0], -x[:, 0], 0.5 * x[:, 1]], axis=1)
    arms = rng.integers(3, size=len(x))
    mask = np.eye(3)[arms]
    target = mask * true
    settings = dict(max_updates=3000, min_epochs=1, check_every=100, patience=5)
    net, info = fit(
        x[:3000],
        target[:3000],
        mask[:3000],
        (x[3000:], target[3000:], mask[3000:]),
        settings,
        16,
        0.01,
        64,
        3,
    )
    assert info["stop_loss"] < 0.02 and info["updates"] <= 3000
    assert np.mean((net(x[3000:]) - true[3000:]) ** 2) < 0.03  # unseen options of every row are recovered
    stopped, early = fit(
        x[:3000],
        target[:3000],
        mask[:3000],
        (x[3000:], target[3000:], mask[3000:]),
        dict(settings, patience=1),
        16,
        0.01,
        64,
        3,
    )
    assert early["updates"] <= info["updates"]


def test_packaged_head_acts_exactly_where_choose_does():
    c = config()
    base = c.ratios.index(c.base_ratio)
    rng = np.random.default_rng(2)
    net = MLP(FEATURE_DIM, c.hidden, len(c.ratios), rng)
    norm = (rng.normal(size=FEATURE_DIM), rng.uniform(0.5, 2, FEATURE_DIM), 100.0)
    states = rng.normal(size=(300, FEATURE_DIM)) * norm[1] + norm[0]
    output = net(np.clip((states - norm[0]) / norm[1], -12, 12))
    advantage = (output - output[:, [base]]) * 0.7
    for margin in (0.0, 0.3, NEVER):
        model = TypedModel(package(c, norm, net, 0.7, margin, 0))
        picked = [int(np.argmax(model.answer(s, "regress")[0])) for s in states]
        assert picked == choose(advantage, base, margin).tolist()
    assert len(set(choose(advantage, base, 0.0).tolist())) > 1 and set(picked) == {base}


def test_factual_pipeline_never_reads_rollout_values():
    c = config(steps=120, workers=1, hidden=8)
    data = collect(c, 0, 200, 0.5)
    parts = budget(data, 200, [0.7, 0.1, 0.2])
    settings = load_settings() | dict(max_updates=40, check_every=20, patience=2)
    scrambled = [dict(p, values=np.full_like(p["values"], np.nan)) for p in parts]
    net, norm, scale, info = train(c, parts, "factual", settings, 0)
    blind, _, blind_scale, blind_info = train(c, scrambled, "factual", settings, 0)
    assert all(np.array_equal(a, b) for a, b in zip(net.params, blind.params))
    assert (scale, info["margin"]) == (blind_scale, blind_info["margin"])
    control, _, _, control_info = train(c, parts, "rollout", settings, 0)
    assert not np.array_equal(control.params[2], net.params[2])
    assert info["margin"] in (*settings["margins"], NEVER) and len(info["margin_curve"]) == len(
        settings["margins"]
    )
    with pytest.raises(ValueError):
        train(c, parts, "oracle", settings, 0)


def test_study_reports_learning_curves_paired_with_the_frozen_run(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(TINY))
    run(load_config(path), tmp_path / "run", splits=("validation",))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(SMALL))
    before = (tmp_path / "run" / "report.json").read_bytes()
    report = study(tmp_path / "run", tmp_path / "factual", settings, samples=30)
    assert (tmp_path / "run" / "report.json").read_bytes() == before
    assert report["synthetic_only"] is True and report["never_acting_head_matches_fixed"] == 0
    assert set(report["reference"]) == {"v3_regress", "v3_head"}
    for c in report["collection"]:
        assert c["factual_matches_rollout"] < 1e-12 and c["blocks"] >= 120
        assert 40 <= c["rollout_rows"] < c["blocks"]  # hindsight only as far as the control needs it
    assert [b["blocks"] for b in report["budgets"]] == [40, 120]
    assert report["budgets"][0]["link_hours"] < report["budgets"][1]["link_hours"]
    small, large = report["budgets"]
    assert set(small["pipelines"]) == {"factual", "factual_zero_margin", "rollout", "rollout_zero_margin"}
    assert {"factual_vs_fixed", "rollout_vs_fixed", "factual_vs_rollout"} <= set(small["contrasts"])
    assert set(large["pipelines"]) == {"factual", "factual_zero_margin"}  # beyond the control's budget
    assert set(large["contrasts"]) == {"factual_vs_fixed", "factual_zero_margin_vs_fixed"}
    for entry in report["budgets"]:
        for name, pipeline in entry["pipelines"].items():
            assert [s["seed"] for s in pipeline["seeds"]] == [0, 1]
            if name.endswith("zero_margin"):
                assert all(s["margin"] == 0 for s in pipeline["seeds"])
        u = entry["contrasts"]["factual_vs_fixed"]["utility"]
        assert u["families"] == 4 and len(u["family_t_interval95"]) == 2
    assert (tmp_path / "factual" / "model_factual_120_seed_1.json").exists()
    assert not (tmp_path / "factual" / "model_rollout_120_seed_1.json").exists()
    assert "120 blocks" in headline(report)
    with pytest.raises(FileExistsError):
        study(tmp_path / "run", tmp_path / "factual", settings)
