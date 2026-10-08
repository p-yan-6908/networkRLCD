import json
from dataclasses import replace

import numpy as np
import pytest
from scipy.special import softmax

from media_rl.environment import Telemetry
from media_rl.jevbwe import Sample
from media_rl.networks import MLP
from media_rl.typed_bitrate import (
    FEATURE_DIM,
    AckedBwe,
    Features,
    Governor,
    Link,
    TypedConfig,
    TypedModel,
    TypedPolicy,
    choice_labels,
    fit_choice,
    fit_temperature,
    load_config,
    payoff_table,
    proper_reward,
    reliability,
    reward_gradient,
    rlcd_gradient,
    rollout_values,
    select_threshold,
    step,
)
from media_rl.typed_bitrate_audit import audit, contrast, family_interval
from media_rl.typed_bitrate_experiment import diagnose, evaluate_run, main, rescore, run, run_episode
from media_rl.typed_bitrate_families import FAMILIES, TEST_FAMILIES, TRAIN_FAMILIES, family_trace
from media_rl.typed_bitrate_report import export

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


def sample(now=0.0, **fields):
    values = dict(bwe_bps=1e6, delivery_bps=8e5, rtt_ms=50.0, requested_bps=8e5, loss=0.0)
    return Sample(sample_ms=now, **{**values, **fields})


def test_config_rejects_inconsistent_studies():
    for bad in (
        dict(base_ratio=0.85),  # the base must be one of the typed options
        dict(commit_ms=1000),  # shorter than the modelled encoder response
        dict(decision_ms=250),  # not a whole number of control steps
        dict(validation_seeds=[1, 2], test_seeds=[2, 3]),
        dict(ratios=[1.0, 0.9]),
        dict(bwe="oracle"),
        dict(scenarios=["unknown"]),
    ):
        with pytest.raises(ValueError):
            TypedConfig(**bad).validate()


def test_acked_estimator_cannot_outrun_delivery_but_legacy_does():
    acked = AckedBwe(0.1)
    quiet = Telemetry(throughput_mbps=0.5, rtt_ms=50, valid=True)
    for _ in range(200):
        acked.act(quiet)
    assert acked.budget == pytest.approx(0.75)  # 1.5x the acked rate, never the ladder maximum
    legacy = Link(config(bwe="legacy"), "steady", 3)
    bounded = Link(config(), "steady", 3)
    for link in (legacy, bounded):
        rules = Governor(config())
        for _ in range(150):
            step(link, rules, link.sample(), 0.6, config())
    assert legacy.bwe.budget == pytest.approx(4.0)
    assert bounded.bwe.budget < 1.0
    acked.act(Telemetry(throughput_mbps=0.5, rtt_ms=50, delay_trend_ms=20, valid=True))
    assert acked.budget == pytest.approx(0.45)  # overuse still cuts to 0.9x delivery


def test_fork_is_isolated_and_deterministic():
    c = config()
    link, rules = Link(c, "wifi", 5), Governor(c)
    for _ in range(40):
        step(link, rules, link.sample(), 0.9, c)
    current = link.sample()
    before = (link.env.t, link.env.queue, link.bwe.budget, link.encoder.target_bps, len(link.env.feedback))
    first, _ = rollout_values(link, rules, current, c)
    second, _ = rollout_values(link, rules, current, c)
    assert first == second
    assert before == (
        link.env.t,
        link.env.queue,
        link.bwe.budget,
        link.encoder.target_bps,
        len(link.env.feedback),
    )


def test_governor_delays_increases_and_never_delays_decreases():
    c = config()
    rules = Governor(c)
    assert rules.decide(sample(0, requested_bps=5e5), 1.0) == 5e5  # dwell starts at first sight
    assert rules.decide(sample(1700, requested_bps=5e5), 1.0) == 5e5
    assert rules.decide(sample(1800, requested_bps=5e5), 1.0) == 1e6
    assert rules.decide(sample(1900, requested_bps=1e6), 0.6) == 6e5  # immediate
    cut = rules.decide(sample(2000, requested_bps=6e5, loss=0.2), 1.0)
    assert cut == pytest.approx(4.2e5)  # emergency 0.7x and a fresh hold
    assert rules.decide(sample(3700, requested_bps=cut), 1.0) == cut
    assert rules.decide(sample(3900, requested_bps=cut), 1.0) == 1e6
    stale = rules.decide(sample(4000, requested_bps=1e6, feedback_age_ms=900), 1.0)
    assert stale == c.residual.min_bps


def test_choice_labels_prefer_base_inside_margin_and_lowest_tied_ratio():
    c = config(margin=0.02)
    base = c.ratios.index(0.9)
    values = np.zeros((4, 6))
    values[0, 5] = 0.019  # inside the margin: stay on the base
    values[1, 5] = 0.021
    values[2, [1, 2]] = 0.5  # exact tie: the lower ratio
    values[3, [0, base]] = 0.3, 0.29
    assert choice_labels(values, c).tolist() == [base, 5, 1, base]
    assert int(choice_labels(values[1], c)) == 5


def test_proper_reward_is_maximised_by_the_true_distribution():
    truth = np.array([0.5, 0.3, 0.2])
    labels = np.arange(3)

    def expected(p):
        return float(truth @ proper_reward(np.tile(np.log(p), (3, 1)), labels, 0.5))

    rng = np.random.default_rng(0)
    for _ in range(200):
        other = rng.dirichlet(np.ones(3))
        assert expected(truth) >= expected(other)


def test_reward_gradient_matches_finite_differences_and_rlcd_estimates_it():
    rng = np.random.default_rng(1)
    logits, labels = rng.normal(size=(5, 6)), rng.integers(6, size=5)
    exact = reward_gradient(logits, labels, 0.5)
    numeric = np.zeros_like(logits)
    for i in range(5):
        for j in range(6):
            shift = np.zeros_like(logits)
            shift[i, j] = 1e-6
            numeric[i, j] = (
                proper_reward(logits + shift, labels, 0.5)[i] - proper_reward(logits - shift, labels, 0.5)[i]
            ) / 2e-6
    assert np.allclose(exact, numeric, atol=1e-6)
    c = config(group_size=64, noise_std=0.1)
    estimate = np.mean([rlcd_gradient(logits, labels, c, rng) for _ in range(600)], axis=0)
    assert np.corrcoef(estimate.ravel(), exact.ravel())[0, 1] > 0.98
    assert np.abs(estimate - exact).max() < 0.1


@pytest.mark.parametrize("estimator", ["rlcd", "analytic"])
def test_fit_choice_learns_honest_probabilities(estimator):
    rng = np.random.default_rng(2)
    x = rng.normal(size=(4000, 4))
    truth = softmax(np.column_stack([1.5 * x[:, 0], -1.5 * x[:, 0], 0.5 * x[:, 1]]), axis=1)
    labels = np.array([rng.choice(3, p=p) for p in truth])
    c = replace(config(hidden=16, epochs=12, batch_size=64), ratios=[0.8, 0.9, 1.0])
    net = fit_choice(x, labels, c, 7, estimator=estimator)
    report = reliability(softmax(net(x), axis=1), labels)
    assert report["accuracy"] > 0.6
    assert report["ece"] < 0.06
    assert report["nll"] < -np.mean(np.log(truth[np.arange(4000), labels])) + 0.05
    with pytest.raises(ValueError):
        fit_choice(x, labels, c, 7, estimator="supervised")


def test_temperature_and_reliability_detect_overconfidence():
    rng = np.random.default_rng(3)
    logits = rng.normal(size=(5000, 4))
    labels = np.array([rng.choice(4, p=p) for p in softmax(logits, axis=1)])
    sharp = softmax(3 * logits, axis=1)
    assert fit_temperature(3 * logits, labels) == pytest.approx(3, rel=0.15)
    assert reliability(softmax(logits, axis=1), labels)["ece"] < 0.03
    assert reliability(sharp, labels)["ece"] > 0.15
    assert reliability([], [])["rows"] == 0


def test_threshold_selection_and_payoff_table():
    score = np.array([0.9, 0.8, 0.4, 0.3])
    advantage = np.array([0.2, 0.1, -0.3, -0.2])
    proposes = np.array([True, True, True, False])
    threshold, curve = select_threshold(score, advantage, proposes, [0.0, 0.5, 0.95])
    assert threshold == 0.5
    assert [row["coverage"] for row in curve] == [0.75, 0.5, 0.0]
    labels = np.array([0] * 12 + [1] * 3)
    table = payoff_table(np.column_stack([np.ones(15), -np.ones(15)]), labels)
    assert table[:, 0].tolist() == [1.0, -1.0]
    assert table[:, 1].tolist() == [0.0, 0.0]  # rarely-best options never argue for leaving the base


def bundle(logits, *, payoff=None, threshold=0.6, support_limit=5.0):
    """A model whose choice head ignores its input and always reports softmax(logits)."""
    weights = [np.zeros((FEATURE_DIM, 1)).tolist(), [0.0], np.zeros((1, 6)).tolist(), list(logits)]
    head = dict(
        weights=weights,
        temperature=1.0,
        threshold=threshold,
        payoff=(np.zeros((6, 6)) if payoff is None else payoff).tolist(),
    )
    regress = dict(weights=weights, target_scale=1.0, threshold=0.0)
    return dict(
        abi="jevbwe_typed_v2",
        ratios=[0.6, 0.7, 0.8, 0.9, 1.0, 1.05],
        base_ratio=0.9,
        mean=[0.0] * FEATURE_DIM,
        scale=[1.0] * FEATURE_DIM,
        support_limit=support_limit,
        heads=dict(choice_rlcd=head, regress=regress),
    )


def test_policy_rules_and_guards():
    c = config()
    confident, unsure = [0, 0, 0, 0, 0, 4.0], [0, 0, 0, 0, 0, 0.5]

    def decide(logits, rule, current=None, **kwargs):
        policy = TypedPolicy(TypedModel(bundle(logits, **kwargs)), "choice_rlcd", rule, c)
        return policy.observe(current or sample(), True)

    assert decide(confident, "gated")[1]["reason"] == "accepted"
    assert decide(confident, "gated")[0] == 1.05
    ratio, info = decide(unsure, "gated")
    assert (ratio, info["reason"], info["proposal"], info["arm"]) == (0.9, "low_confidence", 5, 3)
    assert decide(unsure, "map")[0] == 1.05  # the ungated ablation ignores every guard
    assert decide(confident, "gated", support_limit=0.01)[1]["reason"] == "unsupported_history"
    stale = sample(feedback_age_ms=900)
    assert decide(confident, "gated", current=stale)[1]["reason"] == "stale_telemetry"
    assert decide(confident, "map", current=stale)[0] == 1.05
    assert decide([0, 0, 0, 4.0, 0, 0], "gated")[1]["reason"] == "base_answer"
    # Bayes: a likely-best option is still declined when its expected payoff is negative.
    payoff = np.zeros((6, 6))
    payoff[5, 5], payoff[5, 0] = 0.05, -2.0
    ratio, info = decide([1.0, 0, 0, 0, 0, 2.0], "bayes", payoff=payoff)
    assert (ratio, info["reason"]) == (0.9, "base_answer")
    assert decide(confident, "bayes", payoff=payoff)[0] == 1.05
    with pytest.raises(ValueError):
        TypedPolicy(TypedModel(bundle(confident)), "choice_rlcd", "greedy", c)
    with pytest.raises(ValueError):
        TypedModel(dict(bundle(confident), abi="jevbwe_residual_v1"))


def test_policy_holds_its_ratio_between_decisions():
    policy = TypedPolicy(TypedModel(bundle([0, 0, 0, 0, 0, 4.0])), "choice_rlcd", "map", config())
    assert policy.observe(sample(0), False) == (0.9, None)
    assert policy.observe(sample(100), True)[0] == 1.05
    assert policy.observe(sample(200), False) == (1.05, None)


def test_features_remember_the_capacity_knee_causally():
    features = Features(config())
    names = dict(zip(("fresh", "never", "knee"), (-11, -4, -2)))
    for i in range(10):
        state = features.observe(sample(100.0 * i, delivery_bps=1e6 + 1e4 * i))
    assert state.shape == (FEATURE_DIM,)
    assert (state[names["fresh"]], state[names["never"]], state[names["knee"]]) == (1.0, 1.0, 0.0)
    state = features.observe(sample(1000.0, delivery_bps=2e5, rtt_ms=200.0))
    assert state[names["never"]] == 0.0
    assert state[names["knee"]] == pytest.approx(1.09e6 / 4e6)  # peak delivery before the onset
    state = features.observe(sample(1100.0, feedback_age_ms=900))
    assert state[names["fresh"]] == 0.0
    assert state[names["knee"]] == 0.0  # stale telemetry reports nothing as measured
    ablated = Features(config(summaries=False))
    assert not ablated.observe(sample(0.0, rtt_ms=200.0))[-11:].any()


def test_congestion_onset_after_a_feedback_gap_keeps_the_previous_knee():
    features = Features(config())
    for i in range(10):
        features.observe(sample(100.0 * i, delivery_bps=9e5))
    features.observe(sample(1000.0, delivery_bps=9e5, loss=0.2))  # onset with fresh evidence
    assert features.knee_bps == 9e5
    features.observe(sample(1100.0, delivery_bps=2e5))  # congestion clears
    state = features.observe(sample(4000.0, delivery_bps=1e5, loss=0.2))  # next onset, 2.9 s later
    assert features.knee_bps == 9e5 and np.isfinite(state).all()


def test_exploration_holds_its_option_until_the_next_decision():
    c = config(steps=120)
    model = TypedModel(bundle([0, 0, 0, 4.0, 0, 0]))  # the head itself always answers the base
    spec = dict(kind="typed", head="choice_rlcd", rule="map", explore=1.0, seed=3)
    explored = run_episode(c, model, "steady", 5, spec, "data")
    quiet = run_episode(c, model, "steady", 5, dict(spec, explore=0.0), "data")
    assert {d["executed"] for d in quiet["decisions"]} == {3}
    assert len({d["executed"] for d in explored["decisions"]}) > 1
    assert explored["utility"] != quiet["utility"]
    assert explored["rate_mbps"] != pytest.approx(quiet["rate_mbps"], rel=0.01)  # held, not a one-step blip


def test_oracle_uses_hindsight_but_fixed_and_typed_policies_do_not():
    c = config(steps=120)
    fixed = run_episode(c, None, "step", 11, dict(kind="fixed", ratio=0.9))
    oracle = run_episode(c, None, "step", 11, dict(kind="oracle"))
    assert oracle["utility"] >= fixed["utility"]
    assert fixed["decisions"] == [] and oracle["decisions"] == []
    labelled = run_episode(c, None, "step", 11, dict(kind="explore", explore=0.5, seed=4), "data")
    assert len(labelled["decisions"]) == 8  # epochs whose rollout horizon fits in the episode
    assert all(len(d["state"]) == FEATURE_DIM and len(d["values"]) == 6 for d in labelled["decisions"])


def test_new_families_are_valid_seeded_and_disjoint():
    from media_rl.scenarios import SCENARIOS

    assert not set(TRAIN_FAMILIES) & set(TEST_FAMILIES) and not set(FAMILIES) & set(SCENARIOS)
    for name in FAMILIES:
        for seed in range(6):
            trace = family_trace(name, 360, seed)  # Trace validates ranges, shapes and finiteness
            assert trace.name == name and len(trace.capacity) == 360
            assert np.array_equal(trace.capacity, family_trace(name, 360, seed).capacity)
        assert not np.array_equal(trace.capacity, family_trace(name, 360, 99).capacity)
        assert len(family_trace(name, 60, 1).capacity) == 60
    with pytest.raises(ValueError):
        family_trace("steady", 360, 0)


def test_untouched_test_families_cannot_enter_fitting_or_development():
    config(train_scenarios=["steady", "dip"], scenarios=["sawtooth"], development_scenarios=["collapse"])
    for field in ("train_scenarios", "development_scenarios"):
        with pytest.raises(ValueError, match="evaluation-only"):
            config(**{field: ["steady", "sawtooth"]})
    with pytest.raises(ValueError, match="unknown scenario"):
        config(train_scenarios=["nowhere"])
    episode = run_episode(config(steps=120), None, "blackout", 5, dict(kind="fixed", ratio=0.9))
    assert np.isfinite(episode["utility"]) and 0 <= episode["unsafe"] <= 1


def test_hindsight_rollouts_never_reach_a_typed_controller(monkeypatch):
    import media_rl.typed_bitrate_experiment as experiment

    c = config(steps=120)
    rng = np.random.default_rng(3)
    weights = MLP(FEATURE_DIM, 8, 6, rng).to_dict()
    head = dict(weights=weights, temperature=1.0, threshold=0.0, payoff=rng.normal(0, 1, (6, 6)).tolist())
    model = TypedModel(
        dict(
            abi="jevbwe_typed_v2",
            ratios=list(c.ratios),
            base_ratio=0.9,
            mean=[0.0] * FEATURE_DIM,
            scale=[1.0] * FEATURE_DIM,
            support_limit=1e9,
            heads=dict(choice_rlcd=head),
        )
    )
    spec = dict(kind="typed", head="choice_rlcd", rule="bayes")
    scored = run_episode(c, model, "step", 11, spec, "score")
    assert len({d["executed"] for d in scored["decisions"]}) > 1  # the answers do move the ratio

    def forbidden(*args, **kwargs):
        raise AssertionError("a controller asked for hindsight")

    monkeypatch.setattr(experiment, "rollout_values", forbidden)
    monkeypatch.setattr(Link, "fork", forbidden)
    blind = run_episode(c, model, "step", 11, spec)
    assert blind["decisions"] == []
    assert all(blind[k] == scored[k] for k in ("utility", "unsafe", "deadline_miss", "rate_mbps"))


def test_family_clustering_widens_intervals_when_families_disagree():
    rng = np.random.default_rng(0)
    effects = np.asarray([0.4, 0.3, -0.2, 0.1, -0.3, 0.2])[:, None, None]  # families disagree
    diff = effects + rng.normal(0, 0.01, (6, 5, 24))  # seeds and traces barely matter
    entry = contrast(diff, np.random.default_rng(1), 400)
    seed_width = entry["seed_interval95"][1] - entry["seed_interval95"][0]
    family_width = entry["family_interval95"][1] - entry["family_interval95"][0]
    assert family_width > 10 * seed_width and entry["positive_families"] == 4
    low, high = entry["family_t_interval95"]
    assert low < 0 < high and np.isclose((low + high) / 2, entry["mean"])
    assert entry["leave_one_family_out"][0] < entry["mean"] < entry["leave_one_family_out"][1]
    same = family_interval(np.full((3, 2, 4), 0.25), rng, 20)
    assert same == [0.25, 0.25]


def test_study_runs_end_to_end_and_is_reproducible(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(TINY))
    first = run(load_config(path), tmp_path / "a")
    run(load_config(path), tmp_path / "b", splits=("validation",))
    with pytest.raises(ValueError):
        evaluate_run(tmp_path / "b", ("validation",))  # frozen panels are never recomputed
    second = evaluate_run(tmp_path / "b", ("test",))  # later evaluation from the saved models
    assert first["base_tuning"]["source"] == "id_tune_split"
    assert first["base_tuning"]["selected"] in [row["ratio"] for row in first["base_tuning"]["sweep"]]
    assert set(first["panels"]) == {"validation", "test"}
    assert set(first["panels"]["validation"]) == {"id", "all"}  # held-out families are test only
    assert set(first["panels"]["test"]) == {"id", "ood", "all"}
    panel = first["panels"]["test"]["all"]
    assert {"oracle", "fixed_0.85", "choice_rlcd_bayes", "regress_greedy"} <= set(panel["methods"])
    assert panel["methods"]["oracle"]["utility"] >= panel["methods"][panel["references"]["base"]]["utility"]
    assert "reliability" in panel["methods"]["choice_rlcd_bayes"]
    for split in ("validation", "test"):
        for name, data in first["panels"][split].items():
            for method, entry in data["methods"].items():
                assert entry["utility"] == second["panels"][split][name]["methods"][method]["utility"]
    checks = rescore(tmp_path / "a")  # frozen outcomes replay exactly, with and without labels
    assert checks["episodes"] == 10 and checks["unlabelled_replay"] == 0.0 and "labelled_replay" not in checks
    decisions = np.load(tmp_path / "a" / "test_decisions.npz")
    assert set(decisions["methods"]) == {"choice_rlcd_bayes", "choice_rlcd_gated", "choice_rlcd_map"} | {
        "choice_analytic_bayes",
        "regress_greedy",
    }
    assert decisions["scores"].shape == decisions["values"].shape == (len(decisions["step"]), 6)
    (tmp_path / "a" / "test_decisions.npz").unlink()  # a panel that predates decision records
    checks = rescore(tmp_path / "a")
    assert checks["labelled_replay"] == 0.0 and checks["unlabelled_replay"] == 0.0
    assert np.array_equal(np.load(tmp_path / "a" / "test_decisions.npz")["scores"], decisions["scores"])
    audited = audit(tmp_path / "a", robustness=tmp_path / "b", reference=tmp_path / "b", samples=40)
    assert audited["isolation"]["unlabelled_replay"] == 0.0 and audited["ece_difference_to_report"] < 1e-6
    assert audited["rules"]["recomputed_equals_executed"] == 1.0  # the runtime rule is the documented one
    assert (
        set(audited["families"]) == {"steady", "collapse"}
        and audited["families"]["collapse"]["group"] == "ood"
    )
    assert audited["paired"]["fixed_ratio_identity"] == 0.0
    assert audited["paired"]["panels"]["all"]["choice_rlcd_bayes"]["utility"]["mean"] == 0.0
    whole = audited["panels"]["all"]["methods"]["choice_rlcd_bayes"]["utility_vs_train_fixed"]
    assert (
        whole["families"] == 2 and len(whole["family_interval95"]) == len(whole["family_t_interval95"]) == 2
    )
    assert "family_interval95" not in audited["panels"]["id"]["methods"]["oracle"]["utility_vs_train_fixed"]
    assert audited["tradeoff"]["all"]["floor"] >= 0 and "fixed_0.90" in audited["tradeoff"]["all"]["methods"]
    assert audited["cross_estimator"]["panels"]["all"]["typed_minus_cap"]["utility"]["families"] == 2
    assert json.loads((tmp_path / "a" / "audit_test.json").read_text())["synthetic_only"] is True
    # No controller runs on an untouched test family here either; "outage" stands in for one.
    broad = dict(
        TINY, train_scenarios=["steady", "dip"], development_scenarios=["collapse"], scenarios=["outage"]
    )
    path.write_text(json.dumps(broad))
    wide = run(load_config(path), tmp_path / "wide", splits=("validation", "development"))
    assert set(wide["panels"]["validation"]) == {"id", "all"} and set(wide["panels"]["development"]) == {
        "ood",
        "all",
    }
    assert wide["panels"]["validation"]["id"]["scenarios"] == ["steady", "dip"]
    assert set(evaluate_run(tmp_path / "wide", ("test",))["panels"]["test"]) == {"ood", "all"}
    path.write_text(json.dumps(TINY))
    model = json.loads((tmp_path / "a" / "model_seed_0.json").read_text())
    TypedModel(model)
    assert model["synthetic_only"] is True and model["base_ratio"] == first["base_tuning"]["selected"]
    assert all(np.isfinite(MLP.from_dict(h["weights"]).params[0]).all() for h in model["heads"].values())
    with pytest.raises(FileExistsError):
        run(load_config(path), tmp_path / "a")
    with pytest.raises(SystemExit) as error:
        main(["run", "--config", str(path), "--out", str(tmp_path / "a")])
    assert error.value.code == 2

    # Paper evidence is generated from the saved reports only.
    diagnosis = diagnose(load_config(path), tmp_path / "diagnosis")
    assert set(diagnosis) == {"legacy", "acked"}
    assert {"oracle", "fixed_0.85"} <= set(diagnosis["acked"]["methods"])
    paper = tmp_path / "paper"
    written = export(tmp_path / "a", paper, tmp_path / "diagnosis", tmp_path / "b", tmp_path / "b")
    evidence = (paper / "evidence.tex").read_text()
    utility = first["panels"]["test"]["id"]["methods"]["choice_rlcd_bayes"]["utility"]
    assert f"\\newcommand{{\\TypedIdBayesUtility}}{{{utility:.3f}}}".replace("-", "$-$") in evidence
    for macro in ("TypedDiagLegacyBest", "TypedAblationBayesWithout", "TypedUnboundedIdBayesVsBest"):
        assert f"\\newcommand{{\\{macro}}}" in evidence
    tables = ("methods", "contrasts", "calibration", "scenarios", "diagnosis", "robustness")
    assert all((paper / f"table_{name}.tex").read_text().endswith("\\end{tabular}\n") for name in tables)
    assert (paper / "figure.pdf").stat().st_size > 1000
    assert len(written["sources"]) == 5  # run report, config and audit, diagnosis, the reused second run
    audited_tables = (
        "family_utility",
        "family_risk",
        "family_contrasts",
        "clustered",
        "rules",
        "payoff",
        "tradeoff",
    )
    assert all(
        (paper / f"table_{name}.tex").read_text().endswith("\\end{tabular}\n") for name in audited_tables
    )
    assert "collapse & Held-out" in (paper / "table_family_utility.tex").read_text()
    assert (paper / "figure_tradeoff.pdf").stat().st_size > 1000
    listed = json.loads((paper / "outputs_manifest.json").read_text())
    assert written["outputs"] == len(listed) and {"a/model_seed_0.json", "b/report.json"} <= set(listed)
    assert listed["a/report.json"]["bytes"] == (tmp_path / "a" / "report.json").stat().st_size
    for macro in ("TypedAuditAllBayesVsTrainT", "TypedAuditReplayDifference", "TypedAuditAllCrossUnsafe"):
        assert f"\\newcommand{{\\{macro}}}" in evidence
    broad = export(tmp_path / "a", tmp_path / "paper-broad", broadened=tmp_path / "wide")
    assert len(broad["sources"]) == 5  # the broadened run adds its report and config; it has no audit yet
    run(load_config(path), tmp_path / "c", splits=("validation",))
    with pytest.raises(ValueError):
        export(tmp_path / "c", paper)  # no test panel, no paper evidence
