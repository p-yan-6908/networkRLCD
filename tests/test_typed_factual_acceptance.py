"""Factual DR contributions, cluster uncertainty, selection and no-oracle boundaries."""

from types import SimpleNamespace

import numpy as np
import pytest

from media_rl import typed_bitrate_factual as factual
from media_rl import typed_factual_acceptance as audit
from media_rl.typed_bitrate import TypedConfig


def test_dr_contributions_match_original_uniform_factual_estimator():
    rng = np.random.default_rng(42)
    values = rng.normal(size=(100, 6))
    arms, choices = rng.integers(6, size=100), rng.integers(6, size=100)
    outcomes = rng.normal(size=100)
    observed = audit.dr_gap(values, arms, outcomes, choices, 5)
    expected = factual.doubly_robust(values, arms, outcomes, choices) - factual.doubly_robust(
        values, arms, outcomes, np.full(100, 5)
    )
    assert observed.mean() == pytest.approx(expected, abs=1e-12)
    assert np.all(audit.dr_gap(values, arms, outcomes, np.full(100, 5), 5) == 0)


def test_repeated_correlated_rows_do_not_create_cluster_precision():
    scores = np.array([0.9, -0.9, 0.9, -0.8])
    clusters = np.arange(4)
    single = audit.lower_bound(scores, clusters, 0.05, 6)
    repeated = audit.lower_bound(np.repeat(scores, 100), np.repeat(clusters, 100), 0.05, 6)
    assert repeated == pytest.approx(single)
    assert single["mean"] > 0 and single["lower"] < 0
    assert audit.lower_bound(scores, clusters, 0.05, 1)["lower"] > single["lower"]


def test_single_cluster_or_missing_labels_cannot_supply_acceptance_bound():
    with pytest.raises(ValueError, match="two"):
        audit.lower_bound([0.1, 0.2], [0, 0], 0.05, 6)
    with pytest.raises(ValueError, match="finite"):
        audit.lower_bound([0.1, np.nan], [0, 1], 0.05, 6)


def test_positive_point_estimate_can_be_rejected_by_both_clustered_bounds():
    config = SimpleNamespace(ratios=[0.6, 1.05], base_ratio=1.05, train_scenarios=list("abcd"))
    arms = np.tile([0, 1], 20)
    episode = np.repeat(np.arange(4), 10)
    outcome = np.repeat([0.9, -0.9, 0.9, -0.8], 10) * (arms == 0)
    held = dict(states=np.zeros((40, 2)), arms=arms, outcomes=outcome, episode=episode)

    def net(x):
        return np.tile([0.5, 0.0], (len(x), 1))

    selection = audit.select(
        config,
        net,
        (np.zeros(2), np.ones(2), 1.0),
        1.0,
        [dict(outcomes=np.zeros(10)), {}, held],
        [0.0, 0.1, 0.2],
        0.05,
    )
    assert selection["selected"]["point"]["accepted"]
    for method in ("episode_lcb", "family_lcb"):
        assert not selection["selected"][method]["accepted"]
        assert selection["selected"][method]["margin"] == factual.NEVER


def test_factual_collection_does_not_compute_counterfactual_labels(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("counterfactual labels forbidden in this factual audit")

    monkeypatch.setattr(factual, "rollout_values", forbidden)
    config = TypedConfig(steps=150, base_ratio=1.05, workers=1)
    data = factual.collect(config, 99, 20, 0.5, truth_blocks=0)
    assert np.isnan(data["values"]).all()
    assert np.isfinite(data["outcomes"]).all()
    assert len(data["arms"]) >= 20
