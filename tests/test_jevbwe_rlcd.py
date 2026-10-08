"""Proper-score, causal-bandit and isolated-runtime behavioral contracts."""

import copy
import gzip
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from test_jevbwe import bundle, sample

from media_rl.jevbwe import RATIOS, STATE_DIM, ResidualConfig
from media_rl.jevbwe_experiment import StudyConfig, source_hashes
from media_rl.jevbwe_laya import KEYS, LayaModel, LocalLaya, decode, prepare, typed_request
from media_rl.jevbwe_rlcd import (
    ABI,
    ROLES,
    NumericModel,
    RLCDConfig,
    RLCDPolicy,
    calibrate_binary,
    calibrate_choice,
    factual_proper_reward,
    fit_policy,
    forecasts,
    load_config,
    split_seed,
)
from media_rl.jevbwe_rlcd_experiment import (
    audit,
    collect,
    control_episode,
    evaluate,
    inspect_data,
    paired_significance,
    promotion_panel,
    run,
    train,
)
from media_rl.networks import MLP

ROOT = Path(__file__).resolve().parents[1]


def artifact(logits=None):
    net = MLP(STATE_DIM, 4, 6, np.random.default_rng(0))
    net.params = [np.zeros_like(p) for p in net.params]
    net.params[-1] = np.asarray(logits if logits is not None else [4, -1, -1, -1, -1, -1], dtype=float)
    return dict(
        abi=ABI,
        ratios=list(RATIOS),
        baseline_bundle=bundle(),
        policy_weights=net.to_dict(),
        mean=[0] * STATE_DIM,
        scale=[1] * STATE_DIM,
        calibration=dict(binary=dict(slope=1, bias=0), choice=dict(temperature=1)),
        action_value_passed=True,
        calibration_rows=[10] * 6,
        calibration_episodes=[3] * 6,
        inference_budget_ms=100,
        promoted=False,
        synthetic_only=True,
    )


def test_log_and_spherical_ipw_reward_is_strictly_proper_without_winner_labels():
    config = RLCDConfig()
    truth = np.asarray([0.1, 0.25, 0.45, 0.65, 0.8, 0.9])
    mu = np.asarray([0.05, 0.1, 0.15, 0.2, 0.25, 0.25])
    actions = np.repeat(np.arange(6), 2)
    labels = np.tile([0, 1], 6)
    weights = np.repeat(mu, 2) * np.column_stack([1 - truth, truth]).ravel()

    def expected(q):
        logits = np.tile(np.log(q / (1 - q)), (12, 1))
        return np.dot(weights, factual_proper_reward(logits, actions, labels, mu[actions], config))

    honest = expected(truth)
    assert honest > expected(truth[::-1])
    assert honest > expected(truth * 0.8)  # same posterior, but dishonest Bernoulli forecasts
    assert honest > expected(np.full(6, 0.5))
    for a in range(6):
        for delta in (-0.01, 0.01):
            changed = truth.copy()
            changed[a] += delta
            assert honest > expected(changed)


def test_factual_failure_does_not_label_unobserved_actions_negative():
    config = RLCDConfig()
    a, y, mu = np.array([2]), np.array([0]), np.array([1 / 6])
    first = np.zeros((1, 6))
    second = np.full((1, 6), 1000.0)
    second[0, 2] = 0
    assert factual_proper_reward(first, a, y, mu, config) == factual_proper_reward(second, a, y, mu, config)
    assert np.isfinite(
        factual_proper_reward(np.array([[-1000, 1000, 0, 0, 0, 0]]), np.array([0]), np.array([1]), mu, config)
    ).all()


@pytest.mark.parametrize(
    "a,y,mu", [([6], [1], [1 / 6]), ([0], [2], [1 / 6]), ([0], [1], [0]), ([0], [1], [np.nan])]
)
def test_proper_reward_rejects_unknown_or_invalid_factual_contract(a, y, mu):
    with pytest.raises(ValueError):
        factual_proper_reward(np.zeros((1, 6)), np.array(a), np.array(y), np.array(mu), RLCDConfig())


def test_gaussian_rlcd_learns_a_known_randomized_bandit_with_no_dense_labels():
    rng = np.random.default_rng(22)
    states = np.zeros((1800, STATE_DIM))
    a = rng.integers(6, size=len(states))
    truth = np.asarray([0.1, 0.15, 0.85, 0.2, 0.25, 0.15])
    y = (rng.random(len(states)) < truth[a]).astype(int)
    cfg = RLCDConfig(
        study=StudyConfig(epochs=100, hidden=4, learning_rate=0.02, batch_size=64), group_size=12
    )
    net = fit_policy(states, a, y, np.full(len(a), 1 / 6), cfg, 33)
    q, p, _ = forecasts(net(states[:1]))
    assert np.argmax(p[0]) == 2 and q[0, 2] > 0.7 and q[0, 0] < 0.3
    blind = fit_policy(
        states, a, y, np.full(len(a), 1 / 6), replace(cfg, study=replace(cfg.study, epochs=2)), 33, blind=True
    )
    _, p_blind, _ = forecasts(np.repeat(blind(states[:1]).mean(axis=-1, keepdims=True), 6, axis=-1))
    assert p_blind[0] == pytest.approx([1 / 6] * 6)


def test_calibration_is_factual_and_single_class_is_not_causal_evidence():
    cal = calibrate_binary(np.array([0.0, 0.0]), np.array([1, 1]), np.array([1 / 6] * 2))
    assert cal["method"] == "constant_single_class" and cal["slope"] == 0
    assert (
        calibrate_choice(np.full((2, 6), 1 / 6), np.array([0, 1]), np.zeros(2), np.array([1 / 6] * 2))[
            "method"
        ]
        == "unidentified_no_success"
    )


def test_numeric_policy_replaces_only_the_scalar_head_preserving_dwell_and_emergency():
    model = NumericModel(artifact([-1, -1, -1, -1, -1, 4]))
    model.risk.utility = lambda _: (_ for _ in ()).throw(AssertionError("supervised scalar head called"))
    policy = RLCDPolicy(model)
    hold = policy.observe(sample(0))
    assert hold["reason"] == "upward_dwell" and not hold["learned_executed"]
    for now in range(100, 1800, 100):
        policy.observe(sample(now))
    increase = policy.observe(sample(1800))
    assert increase["requested_bps"] == 1.05e6 and increase["learned_executed"]
    assert len(increase["action_probabilities"]) == 6 and sum(
        increase["action_probabilities"]
    ) == pytest.approx(1)
    assert "utility" not in increase
    policy.acknowledge(increase["requested_bps"], 1800)
    model.net.params[-1] = np.asarray([4, -1, -1, -1, -1, -1])
    decrease = policy.observe(sample(1900, requested_bps=1.05e6))
    assert decrease["requested_bps"] == 0.6e6 and decrease["learned_executed"]
    policy.acknowledge(0.6e6, 1900)
    emergency = policy.observe(sample(2000, requested_bps=0.6e6, loss=0.2))
    assert emergency["requested_bps"] < 0.6e6 and not emergency["learned_executed"]


def test_numeric_deadline_and_risk_fail_closed_without_neural_credit():
    data = artifact()
    data["inference_budget_ms"] = 1e-12
    out = RLCDPolicy(NumericModel(data)).observe(sample(0))
    assert out["reason"] == "inference_deadline" and out["inference_overrun"]
    assert not out["learned_executed"] and not any(out["eligible"])
    data = artifact()
    data["baseline_bundle"]["calibration_rows"] = [0] * 6
    out = RLCDPolicy(NumericModel(data)).observe(sample(0))
    assert not out["learned_executed"]
    with pytest.raises(ValueError):
        NumericModel(artifact()).predict(np.full(STATE_DIM, np.nan))


@pytest.mark.parametrize(
    "change", [dict(ratios=[0.6] * 6), dict(action_value_passed=1), dict(scale=[0] * STATE_DIM)]
)
def test_new_model_abi_rejects_incompatible_metadata(change):
    with pytest.raises(ValueError):
        NumericModel({**artifact(), **change})


def test_config_separates_panels_and_freezes_the_1800ms_dwell():
    config = load_config(ROOT / "configs/jevbwe_rlcd_pilot_v1.json")
    assert len(config.validation_seeds) == len(config.study.test_seeds) == 8
    assert config.study.residual.up_dwell_ms == 1800
    assert split_seed(10, "train") != split_seed(10, "qualification")
    with pytest.raises(ValueError):
        replace(config, validation_seeds=config.study.test_seeds).validate()
    with pytest.raises(ValueError):
        replace(config, study=replace(config.study, residual=ResidualConfig(up_dwell_ms=1000))).validate()


@pytest.fixture(scope="module")
def study(tmp_path_factory):
    path = tmp_path_factory.mktemp("rlcd")
    cfg = RLCDConfig(
        study=StudyConfig(
            name="rlcd-tests",
            seed=17101,
            steps=150,
            hidden=4,
            epochs=3,
            train_episodes=12,
            qualification_episodes=12,
            calibration_episodes=12,
            test_seeds=[19201, 19202],
            scenarios=["steady", "collapse"],
        ),
        validation_seeds=[19101, 19102],
        bootstrap_samples=100,
    )
    frozen = {**bundle(), "source_sha256": source_hashes(), "synthetic_only": True}
    baseline = path / "baseline.json"
    baseline.write_text(json.dumps(frozen))
    original = baseline.read_bytes()
    result = run(cfg, baseline, path / "run")
    assert baseline.read_bytes() == original
    return path, cfg, result


def test_iid_exploration_records_conditional_propensities_and_rejects_retrofits(study):
    path, cfg, result = study
    support = result["training"]["data_support"]
    assert support["known_randomization_and_positivity"]
    rows = json.loads(gzip.decompress((path / "run/training/train_cohorts.json.gz").read_bytes()))
    assert all(r["behavior_seed"] != r["trace_seed"] and r["behavior_probability"] == 1 / 6 for r in rows)
    altered = copy.deepcopy(rows)
    for r in altered:
        r.pop("behavior_probability")
    assert not inspect_data({"train": altered})["known_randomization_and_positivity"]
    altered = copy.deepcopy(rows)
    altered[0]["action_index"] = (altered[0]["action_index"] + 1) % 6
    assert not inspect_data({"train": altered})["known_randomization_and_positivity"]
    # Withheld outcomes remain censored evidence, never failure labels.
    short = replace(cfg, study=replace(cfg.study, steps=70))
    cohorts, _ = collect(short, "train")
    assert any(r["censored"] and r["reward"] is None for r in cohorts)


def test_end_to_end_results_preserve_all_roles_baseline_and_unpromoted_state(study):
    path, _, result = study
    assert result["promoted"] is False and result["optional_laya"] == "not_run"
    assert not result["promotion_eligible"]["numeric_rlcd"]  # 2 seeds cannot prove significance
    model = json.loads((path / "run/training/model.json").read_text())
    original = json.loads((path / "baseline.json").read_text())
    assert model["baseline_bundle"] == original and model["promoted"] is False
    assert model["baseline_bundle"]["risk_weights"] == original["risk_weights"]
    assert all((path / f"run/training/{r}_cohorts.json.gz").exists() for r in ROLES)
    assert set(result["panels"]) == {"validation", "test"}
    assert audit(path / "run")["artifacts"] > 20


def test_partial_factual_logs_block_training_instead_of_inventing_propensities(study, tmp_path):
    path, cfg, _ = study
    data = tmp_path / "data"
    data.mkdir()
    for role in ROLES:
        rows = json.loads(gzip.decompress((path / f"run/training/{role}_cohorts.json.gz").read_bytes()))
        for r in rows:
            r.pop("behavior")
        (data / f"{role}_cohorts.json.gz").write_bytes(gzip.compress(json.dumps(rows).encode()))
    with pytest.raises(ValueError, match="propensities|randomization"):
        train(cfg, path / "baseline.json", tmp_path / "blocked", data_run=data)
    assert not (tmp_path / "blocked/model.json").exists()
    assert (tmp_path / "blocked/data_support.json").exists()


def test_statistical_gain_is_not_sufficient_for_promotion_without_safety():
    cfg = RLCDConfig(bootstrap_samples=500)
    assert paired_significance([0.1] * 8, cfg)["significant"]
    assert not paired_significance([0.1] * 4, cfg)["significant"]
    assert not paired_significance([0] * 8, cfg)["significant"]
    episodes = [
        dict(
            seed=seed,
            scenario="steady",
            method=method,
            utility=utility,
            unsafe=unsafe,
            deadline_miss=unsafe,
            checks=dict(rate_violations=0, dwell_violations=0, inference_overruns=0),
        )
        for seed in range(8)
        for method, utility, unsafe in (("fallback_only", 1, 0), ("numeric_rlcd", 1.1, 0.1))
    ]
    panel = promotion_panel(episodes, [], "numeric_rlcd", cfg)
    assert panel["qoe_vs_fallback"]["significant"] and not panel["eligible"]


def test_zero_event_risk_bound_accounts_for_independent_seed_precision():
    cfg = RLCDConfig()
    episodes = [
        dict(
            seed=seed,
            scenario="steady",
            method=method,
            utility=utility,
            unsafe=0,
            deadline_miss=0,
            checks=dict(rate_violations=0, dwell_violations=0, inference_overruns=0),
        )
        for seed in range(8)
        for method, utility in (("fallback_only", 1), ("numeric_rlcd", 1.1))
    ]
    cohorts = [
        dict(seed=seed, method="numeric_rlcd", censored=False, unsafe=0)
        for seed in range(8)
        for _ in range(3)
    ]
    panel = promotion_panel(episodes, cohorts, "numeric_rlcd", cfg)
    assert panel["qoe_vs_fallback"]["significant"]
    assert panel["settled_neural_risk_interval"][1] > cfg.study.residual.risk_limit
    assert not panel["settled_risk_supported"] and not panel["eligible"]


def test_declared_panels_cannot_be_changed_after_fit(study, tmp_path):
    path, cfg, _ = study
    altered = replace(cfg, validation_seeds=[21101, 21102])
    assert altered.fitting_hash() == cfg.fitting_hash()
    assert altered.evaluation_hash() != cfg.evaluation_hash()
    with pytest.raises(ValueError, match="predeclared-panel"):
        evaluate(altered, path / "run/training/model.json", tmp_path / "altered")
    assert not (tmp_path / "altered").exists()


def test_laya_typed_decision_has_same_history_and_six_actions_no_future_labels():
    state = np.arange(STATE_DIM) / STATE_DIM
    request = typed_request(state, RLCDConfig(), diagnostics=True)
    assert np.asarray(request["state"]["history"]).ravel() == pytest.approx(state)
    assert tuple(request["questions"]["bitrate"]["criteria"]) == KEYS
    assert list(request["state"]["action_ratios"].values()) == list(RATIOS)
    assert len(request["questions"]) == 13 and "outcome" not in request["state"]
    response = dict(
        answers={
            key: dict(type="choice", probabilities={k: 1 / len(q["criteria"]) for k in q["criteria"]})
            for key, q in request["questions"].items()
        }
    )
    p, q = decode(response, diagnostics=True)
    assert sum(p) == pytest.approx(1) and q["u"] == pytest.approx([0.5] * 6)
    response["answers"]["bitrate"]["probabilities"].pop(KEYS[0])
    with pytest.raises(ValueError):
        decode(response)


def test_laya_online_choice_does_not_use_numeric_actor_or_invent_event_probabilities():
    backend = SimpleNamespace(predict=lambda state: (np.array([0.05, 0.05, 0.7, 0.05, 0.1, 0.05]), {}))
    model = LayaModel({**artifact(), "laya_choice_calibration": dict(temperature=1)}, backend)
    model.net = lambda _: (_ for _ in ()).throw(AssertionError("numeric actor called"))
    out = RLCDPolicy(model).observe(sample(0))
    assert out["proposal_index"] == 2 and out["outcome_probabilities"] is None
    assert out["action_probabilities"][2] == pytest.approx(0.7)


def test_laya_refuses_history_truncation_and_is_not_imported_by_default():
    backend = LocalLaya.__new__(LocalLaya)
    backend.config = RLCDConfig()
    backend.agent = SimpleNamespace(tok=SimpleNamespace(encode=lambda *args, **kwargs: [0] * 9000))
    with pytest.raises(ValueError, match="truncate"):
        backend.predict(np.zeros(STATE_DIM))
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys,media_rl.jevbwe_rlcd_cli; assert 'laya' not in sys.modules and 'torch' not in sys.modules",
        ],
        check=True,
        capture_output=True,
    )


def test_laya_calibration_runs_factual_adapter_but_stub_is_not_pretrained_evidence(study, tmp_path):
    path, cfg, _ = study

    class Backend:
        identity = dict(kind="test_stub", pretrained_weights_changed=False)

        def predict(self, state, *, diagnostics=False):
            self.last_request = typed_request(state, cfg, diagnostics=diagnostics)
            self.last_response = dict(
                answers={
                    key: dict(type="choice", probabilities={k: 1 / len(q["criteria"]) for k in q["criteria"]})
                    for key, q in self.last_request["questions"].items()
                }
            )
            return decode(self.last_response, diagnostics=diagnostics)

    model = prepare(cfg, path / "run/training", Backend(), tmp_path / "laya")
    assert model.artifact["numeric_policy_used"] is False and model.artifact["action_value_passed"] is False
    assert model.artifact["laya_backend"]["kind"] == "test_stub"
    assert audit(tmp_path / "laya")["artifacts"] == 4


def test_control_episode_direct_replay_is_deterministic_except_timing(study):
    path, cfg, _ = study
    model = json.loads((path / "run/training/model.json").read_text())
    fresh, cohorts = control_episode(
        cfg, NumericModel(model), model["baseline_bundle"], "steady", 19101, "validation", "numeric_rlcd"
    )
    recorded = json.loads(
        gzip.decompress(
            (path / "run/evaluation/validation_steady_19101_numeric_rlcd_decisions.json.gz").read_bytes()
        )
    )
    for got, expected in zip(fresh, recorded):
        got["decision"].pop("inference_ms")
        expected["decision"].pop("inference_ms")
    assert fresh == recorded
    assert isinstance(cohorts, list)
