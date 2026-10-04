from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from media_rl.calibration import Calibrator
from media_rl.config import ExperimentConfig, GateConfig, SimulatorConfig, TrainingConfig, split_seed
from media_rl.controllers import ConfidenceGate, DeterministicController, RLController
from media_rl.environment import OBS_DIM, Telemetry, action_space
from media_rl.metrics import calibration_metrics, cluster_interval, reliability, risk_coverage, runs
from media_rl.networks import MLP, sigmoid
from media_rl.training import ModelBundle, id_environment, policy_training_scenario, train_bundle


def tiny_config():
    return ExperimentConfig(
        seeds=[7],
        test_seeds=[20],
        scenarios=["steady", "collapse", "outage"],
        methods=["safe", "gcc", "rl", "calibrated", "uncalibrated"],
        bootstrap_samples=30,
        simulator=SimulatorConfig(steps=20),
        training=TrainingConfig(
            episodes=4,
            risk_episodes=4,
            calibration_episodes=4,
            hidden=12,
            batch_size=16,
            warmup=16,
            risk_epochs=2,
        ),
    ).validate()


def test_policy_training_schedule_is_weighted_deterministic_and_split_isolated():
    config = replace(tiny_config(), policy_training_scenarios=["collapse", "steady", "collapse"])
    assert [policy_training_scenario(config, i) for i in range(6)] == [
        "collapse",
        "steady",
        "collapse",
        "collapse",
        "steady",
        "collapse",
    ]
    bundle, _ = train_bundle(config, 7)
    assert [row["scenario"] for row in bundle.metadata["training_log"]] == [
        "collapse",
        "steady",
        "collapse",
        "collapse",
    ]
    assert id_environment(config, 7, "risk", 0).trace.name in {"steady", "step", "ramp", "wifi"}
    with pytest.raises(ValueError, match="policy_training_scenarios"):
        replace(config, policy_training_scenarios=["unknown"]).validate()


def test_mlp_really_learns_and_roundtrips():
    rng = np.random.default_rng(4)
    x = rng.normal(size=(128, 3))
    y = (x[:, 0] > 0).astype(float)
    model = MLP(3, 12, 1, rng)
    before = np.mean((sigmoid(model(x)[:, 0]) - y) ** 2)
    for _ in range(150):
        model.train(x, ((sigmoid(model(x)[:, 0]) - y) / len(y))[:, None], 0.02)
    after = np.mean((sigmoid(model(x)[:, 0]) - y) ** 2)
    assert after < before / 4
    np.testing.assert_array_equal(model(x), MLP.from_dict(model.to_dict())(x))


@pytest.mark.parametrize("method", ["platt", "temperature"])
def test_calibration_reduces_heldout_objective_and_handles_extremes(method):
    p = np.full(200, 0.99)
    y = np.tile([0, 1], 100)
    c = Calibrator.fit(p, y, method)
    assert calibration_metrics(c.predict(p), y)["nll"] < calibration_metrics(p, y)["nll"]
    assert np.all(np.isfinite(c.predict([0, 1])))
    assert np.all(np.diff(c.predict(np.linspace(0, 1, 100))) >= 0)
    degenerate = Calibrator.fit([0.1, 0.2], [1, 1])
    assert degenerate.method == "constant_single_class"
    assert degenerate.predict(0.5) == pytest.approx(0.75)
    with pytest.raises(ValueError):
        Calibrator.fit([], [])


def test_known_metric_answers_and_null_coverage():
    assert calibration_metrics([0, 1], [0, 1])["ece"] == 0
    assert calibration_metrics([0, 1], [0, 1])["brier"] == 0
    assert calibration_metrics([0.5, 0.5], [0, 1])["brier"] == 0.25
    assert sum(r["count"] for r in reliability([0, 1], [0, 1])) == 2
    assert risk_coverage([0.2], [1])[-1]["risk"] is None
    assert cluster_interval([1])["low"] is None
    assert cluster_interval([1, 2, 3], 100) == cluster_interval([1, 2, 3], 100)
    assert runs([True, True, False, True]) == [2, 1]
    with pytest.raises(ValueError):
        calibration_metrics([1.5], [1])


def test_hysteresis_hold_release_and_nonfinite():
    g = ConfidenceGate(GateConfig(threshold=0.8, release_margin=0.1, hold_steps=3))
    assert g.select(0.7) == (True, "low_confidence")
    assert g.select(0.99) == (True, "hysteresis")
    assert g.select(0.85) == (True, "hysteresis")
    assert g.select(0.99) == (False, "accepted")
    assert g.select(float("nan"))[0]
    assert g.select(0.99, "missing_feedback") == (True, "missing_feedback")
    fast = ConfidenceGate(GateConfig(), hysteresis=False)
    fast.select(0.1)
    assert fast.select(0.95) == (False, "accepted")


def fake_bundle(confidence=0.1, support=0):
    return SimpleNamespace(
        policy=lambda x: np.arange(42),
        safety=SimpleNamespace(
            predict=lambda x, single=False: (confidence, 0.0),
            support_score=lambda x: support,
            support_limit=2,
        ),
        calibrator=Calibrator(),
        single_calibrator=Calibrator(),
    )


def test_low_confidence_invalid_and_ood_fallback():
    actions = action_space(SimulatorConfig())
    obs = Telemetry(valid=True)
    for bundle, observation, reason in [
        (fake_bundle(), obs, "low_confidence"),
        (fake_bundle(0.99, 10), obs, "ood_support"),
        (fake_bundle(0.99), replace(obs, feedback_age_s=1), "missing_feedback"),
        (fake_bundle(0.99), replace(obs, rtt_ms=float("nan")), "invalid_telemetry"),
    ]:
        ctrl = RLController(bundle, actions, GateConfig())
        decision = ctrl.act(observation)
        assert decision.fallback and decision.reason == reason
        assert 0 <= decision.action < len(actions)
        if reason != "invalid_telemetry":
            assert decision.proposal == 41
            assert decision.action != decision.proposal
    plain = RLController(fake_bundle(0.1, 10), actions, GateConfig(), "rl").act(obs)
    assert plain.action == plain.proposal == 41 and not plain.fallback
    no_ood = RLController(fake_bundle(0.99, 10), actions, GateConfig(), "no_ood").act(obs)
    assert not no_ood.fallback


def test_shielded_controller_selects_highest_q_safe_candidate_or_falls_back():
    actions = action_space(SimulatorConfig())
    obs = Telemetry(valid=True)

    class ShieldSafety:
        support_limit = 2

        def __init__(self, support=0, accept_fec_zero=True):
            self.support = support
            self.accept_fec_zero = accept_fec_zero

        def support_score(self, x):
            return self.support

        def predict(self, x, single=False):
            safe_fec = np.isclose(np.asarray(x)[:, -3], 0) if self.accept_fec_zero else np.zeros(len(x), bool)
            p = np.where(safe_fec, 0.99, 0.2)
            return p, np.zeros_like(p)

    def bundle(support=0, accept_fec_zero=True):
        return SimpleNamespace(
            policy=lambda x: np.arange(len(actions), dtype=float),
            safety=ShieldSafety(support, accept_fec_zero),
            calibrator=Calibrator(),
            metadata={},
        )

    decision = RLController(bundle(), actions, GateConfig(), method="shielded").act(obs)
    assert decision.proposal == len(actions) - 1
    assert decision.action == len(actions) - 5
    assert not decision.fallback and decision.reason == "shielded_action"
    assert decision.confidence == pytest.approx(0.2)
    assert decision.action_confidence == pytest.approx(0.99)

    no_candidate = RLController(bundle(accept_fec_zero=False), actions, GateConfig(), method="shielded").act(
        obs
    )
    assert no_candidate.fallback and no_candidate.reason == "no_safe_candidate"
    ood = RLController(bundle(support=10), actions, GateConfig(), method="shielded").act(obs)
    assert ood.fallback and ood.reason == "ood_support"
    stale = RLController(bundle(), actions, GateConfig(), method="shielded").act(
        replace(obs, feedback_age_s=1)
    )
    assert stale.fallback and stale.reason == "missing_feedback"


def test_uncertainty_screen_skips_disagreement_and_abstains_when_all_candidates_disagree():
    actions = action_space(SimulatorConfig())
    obs = Telemetry(valid=True)

    class DisagreementSafety:
        support_limit = 2

        def __init__(self, values):
            self.values = np.asarray(values, dtype=float)

        def support_score(self, x):
            return 0.0

        def predict(self, x, single=False):
            return np.full(len(x), 0.99), self.values[: len(x)]

    def bundle(values):
        return SimpleNamespace(
            policy=lambda x: np.arange(len(actions), dtype=float),
            safety=DisagreementSafety(values),
            calibrator=Calibrator(),
            metadata={},
        )

    gate = GateConfig(threshold=0.9, max_ensemble_std=0.05)
    candidate = RLController(
        bundle([0.10, 0.01, 0.02, 0.03, 0.04]), actions, gate, method="shielded_uncertainty"
    ).act(obs)
    assert candidate.proposal == len(actions) - 1
    assert candidate.action == len(actions) - 2
    assert candidate.reason == "shielded_action" and not candidate.fallback
    assert candidate.uncertainty == pytest.approx(0.10)
    assert candidate.action_uncertainty == pytest.approx(0.01)

    abstain = RLController(bundle([0.10] * 5), actions, gate, method="shielded_uncertainty").act(obs)
    assert abstain.fallback and abstain.reason == "uncertainty_abstention"
    assert abstain.action_uncertainty == pytest.approx(0.10)

    baseline = RLController(bundle([0.10] * 5), actions, gate, method="shielded").act(obs)
    assert baseline.action == baseline.proposal == len(actions) - 1
    assert not baseline.fallback and baseline.action_uncertainty == pytest.approx(0.10)


def test_baselines_deterministic_and_no_privileged_input():
    actions = action_space(SimulatorConfig())
    for name in ["safe", "gcc", "heuristic"]:
        a, b = DeterministicController(actions, name), DeterministicController(actions, name)
        for rtt in [50, 60, 90, 250, 55]:
            obs = Telemetry(valid=True, rtt_ms=rtt)
            assert a.act(obs) == b.act(obs)


def test_training_reproducibility_and_disjoint_calibration(tmp_path):
    config = tiny_config()
    a, rows_a = train_bundle(config, 7)
    b, rows_b = train_bundle(config, 7)
    assert rows_a == rows_b
    assert a.policy.to_dict() == b.policy.to_dict()
    assert a.safety.to_dict() == b.safety.to_dict()
    initial = MLP(OBS_DIM, config.training.hidden, 42, np.random.default_rng(split_seed(7, "train")))
    assert any(not np.array_equal(x, y) for x, y in zip(initial.params, a.policy.params))
    assert a.metadata["training_log"][-1]["updates"] > 0
    sets = [set(s) for s in a.metadata["split_trace_seeds"].values()]
    assert all(not x & y for i, x in enumerate(sets) for y in sets[i + 1 :])
    assert a.metadata["calibration_samples"] == config.training.calibration_episodes * config.simulator.steps
    a.save(tmp_path / "model.json")
    loaded = ModelBundle.load(tmp_path / "model.json")
    np.testing.assert_array_equal(a.policy(np.zeros(10)), loaded.policy(np.zeros(10)))
    assert a.calibrator == loaded.calibrator
