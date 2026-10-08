"""Numeric RLCD forecaster: proper-score Gaussian policy gradients on factual arms.

q[a] forecasts a predeclared settled QoE-success event under action a. The six-way
Choice distribution is q / sum(q), i.e. the action distribution conditional on
success under a UNIFORM action intervention. It is NOT P(action is optimal).
No best-action labels or counterfactual failures are inferred from bandit logs.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

from .jevbwe import RATIOS, STATE_DIM, JevBWE, ResidualModel, number
from .jevbwe_experiment import StudyConfig
from .networks import MLP, sigmoid

ABI = "jevbwe_rlcd_numeric_v1"
BEHAVIOR = "jevbwe_rlcd_iid_uniform_v1"
ROLES = ("train", "calibration", "qualification")


@dataclass(frozen=True)
class RLCDConfig:
    study: StudyConfig = field(
        default_factory=lambda: StudyConfig(
            name="jevbwe-rlcd-pilot-v1",
            seed=17101,
            epochs=80,
            test_seeds=list(range(19201, 19209)),
        )
    )
    validation_seeds: list[int] = field(default_factory=lambda: list(range(19101, 19109)))
    noise_std: float = 0.2
    group_size: int = 8
    categorical_weight: float = 0.5
    spherical_weight: float = 0.5
    success_qoe: float = 1.0
    alpha: float = 0.05
    bootstrap_samples: int = 2000
    min_neural_cohorts: int = 24

    def validate(self):
        self.study.validate()
        if self.study.residual.up_dwell_ms != 1800:
            raise ValueError("RLCD V1 preserves the 1.8 s increase dwell")
        if (
            not number(self.noise_std)
            or self.noise_std <= 0
            or type(self.group_size) is not int
            or self.group_size < 2
            or not number(self.success_qoe)
            or not number(self.alpha)
            or not 0 < self.alpha <= 0.05
        ):
            raise ValueError("invalid RLCD noise/event/significance contract")
        for value in (self.categorical_weight, self.spherical_weight):
            if not number(value) or value < 0:
                raise ValueError("proper-score weights must be nonnegative")
        if self.categorical_weight == 0:
            raise ValueError("a six-way proper-scoring Choice objective is required")
        if any(type(v) is not int or v < 1 for v in (self.bootstrap_samples, self.min_neural_cohorts)):
            raise ValueError("positive RLCD verification sizes required")
        if (
            not self.validation_seeds
            or len(set(self.validation_seeds)) != len(self.validation_seeds)
            or any(type(v) is not int or v < 0 for v in self.validation_seeds)
            or set(self.validation_seeds) & set(self.study.test_seeds)
        ):
            raise ValueError("validation and test seeds must be unique and disjoint")
        return self

    def to_dict(self):
        return asdict(self)

    def fitting_hash(self):
        data = self.to_dict()
        data.pop("validation_seeds")
        for key in ("name", "test_seeds", "scenarios"):
            data["study"].pop(key)
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def evaluation_hash(self):
        contract = dict(
            validation=self.validation_seeds, test=self.study.test_seeds, scenarios=self.study.scenarios
        )
        return hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()


def load_config(path):
    from .jevbwe import ResidualConfig

    data = json.loads(Path(path).read_text())
    study = data.get("study", {})
    study["residual"] = ResidualConfig(**study.get("residual", {}))
    data["study"] = StudyConfig(**study)
    return RLCDConfig(**data).validate()


def split_seed(seed, role, episode=0):
    if role not in (*ROLES, "optimizer", "validation", "test", "bootstrap", "assignment"):
        raise ValueError("unknown RLCD role")
    return int.from_bytes(hashlib.sha256(f"{ABI}:{seed}:{role}:{episode}".encode()).digest()[:8], "little")


def forecasts(logits, *, choice_temperature=1):
    logits = np.asarray(logits, dtype=float)
    if logits.shape[-1] != 6 or not np.isfinite(logits).all():
        raise ValueError("six finite numeric outcome logits required")
    if not number(choice_temperature) or choice_temperature <= 0:
        raise ValueError("positive choice temperature required")
    log_q = -np.logaddexp(0, -logits)
    log_p = log_q / choice_temperature
    log_p -= logsumexp(log_p, axis=-1, keepdims=True)
    return np.exp(log_q), np.exp(log_p), log_p


def factual_proper_reward(logits, actions, labels, propensities, config):
    """IPW proper score. On a failure ONLY the observed arm gets a negative label.

    Expected binary log + success-conditional log/spherical score is uniquely
    maximized at honest six-arm event forecasts given positivity/ignorability.
    Scaling by 1/(6*mu[a|H]) targets uniform interventions, not behavior cloning.
    Stable log-space scores have no arbitrary reward floor or IPS weight clipping.
    """
    logits = np.asarray(logits, dtype=float)
    actions, labels, mu = np.asarray(actions), np.asarray(labels), np.asarray(propensities)
    if logits.ndim < 2 or logits.shape[-1] != 6 or not np.isfinite(logits).all():
        raise ValueError("finite factual forecast logits required")
    n = logits.shape[-2]
    if (
        actions.shape != (n,)
        or not np.issubdtype(actions.dtype, np.integer)
        or np.any((actions < 0) | (actions >= 6))
        or labels.shape != (n,)
        or not np.all(np.isin(labels, [0, 1]))
        or mu.shape != (n,)
        or not np.isfinite(mu).all()
        or np.any((mu <= 0) | (mu > 1))
    ):
        raise ValueError("only known factual actions/outcomes/positive propensities may be scored")
    _, p, log_p = forecasts(logits)
    chosen = np.take_along_axis(logits, actions.reshape((1,) * (logits.ndim - 2) + (n, 1)), axis=-1)[..., 0]
    binary = -labels * np.logaddexp(0, -chosen) - (1 - labels) * np.logaddexp(0, chosen)
    chosen_p = np.take_along_axis(p, actions.reshape((1,) * (logits.ndim - 2) + (n, 1)), axis=-1)[..., 0]
    chosen_log = np.take_along_axis(log_p, actions.reshape((1,) * (logits.ndim - 2) + (n, 1)), axis=-1)[
        ..., 0
    ]
    spherical = chosen_p / np.linalg.norm(p, axis=-1)
    return (
        binary + config.categorical_weight * labels * (chosen_log + config.spherical_weight * spherical)
    ) / (6 * mu)


def fit_policy(states, actions, labels, mu, config, seed, *, blind=False):
    """REINFORCE over Gaussian logit reports with an unbiased leave-one-out baseline.

    Exploration is in the reported forecast, distinct from physical arm sampling.
    Neither outcome regression nor a supervised scalar utility-ranking head is used.
    """
    rng = np.random.default_rng(seed)
    net = MLP(STATE_DIM, config.study.hidden, 6, rng)
    ids = np.arange(len(states))
    for _ in range(config.study.epochs):
        rng.shuffle(ids)
        for start in range(0, len(ids), config.study.batch_size):
            idx = ids[start : start + config.study.batch_size]
            logits = net(states[idx])
            if blind:
                logits = np.repeat(logits.mean(axis=-1, keepdims=True), 6, axis=-1)
            dims = 1 if blind else 6
            noise = rng.normal(0, config.noise_std, (config.group_size, len(idx), dims))
            reports = logits[None, ...] + noise
            reward = factual_proper_reward(reports, actions[idx], labels[idx], mu[idx], config)
            baseline = (reward.sum(axis=0, keepdims=True) - reward) / (config.group_size - 1)
            gradient = -np.mean((reward - baseline)[..., None] * noise / config.noise_std**2, axis=0)
            if blind:
                gradient = np.repeat(gradient / 6, 6, axis=-1)
            net.train(states[idx], gradient / len(idx), config.study.learning_rate)
    return net


def calibrate_binary(logits, labels, mu):
    logits, labels, mu = map(np.asarray, (logits, labels, mu))
    weights = 1 / (6 * mu)
    if not len(logits) or not np.isfinite(logits).all() or not np.all(np.isin(labels, [0, 1])):
        raise ValueError("valid factual calibration outcomes required")
    if len(np.unique(labels)) < 2:
        prior = (np.sum(weights * labels) + 1) / (weights.sum() + 2)
        return dict(slope=0.0, bias=float(np.log(prior / (1 - prior))), method="constant_single_class")

    def objective(theta):
        z = np.exp(theta[0]) * logits + theta[1]
        return np.average(np.logaddexp(0, z) - labels * z, weights=weights)

    initial = np.zeros(2)
    result = minimize(objective, initial, method="L-BFGS-B", bounds=[(-5, 5), (-15, 15)])
    if not result.success or result.fun > objective(initial):
        return dict(slope=1.0, bias=0.0, method="identity_optimization_failed")
    return dict(slope=float(np.exp(result.x[0])), bias=float(result.x[1]), method="ipw_platt")


def calibrate_choice(probabilities, actions, labels, mu):
    probabilities = np.asarray(probabilities, dtype=float)
    labels = np.asarray(labels)
    selected = labels == 1
    if not np.any(selected):
        return dict(temperature=1.0, method="unidentified_no_success")
    log_p = np.log(np.maximum(probabilities[selected], 1e-300))
    a, weights = np.asarray(actions)[selected], 1 / (6 * np.asarray(mu)[selected])

    def objective(theta):
        z = log_p / np.exp(theta[0])
        return np.average(logsumexp(z, axis=1) - z[np.arange(len(a)), a], weights=weights)

    result = minimize(objective, [0.0], method="L-BFGS-B", bounds=[(-3, 3)])
    if not result.success or result.fun > objective([0.0]):
        return dict(temperature=1.0, method="identity_optimization_failed")
    return dict(temperature=float(np.exp(result.x[0])), method="ipw_success_conditional_temperature")


def calibrated_forecasts(net, state, mean, scale, calibration, *, blind=False):
    z = np.clip((np.asarray(state) - mean) / scale, -12, 12)
    logits = net(z)
    if blind:
        logits = np.repeat(logits.mean(axis=-1, keepdims=True), 6, axis=-1)
    binary = calibration["binary"]
    calibrated = binary["slope"] * logits + binary["bias"]
    q, p, _ = forecasts(calibrated, choice_temperature=calibration["choice"]["temperature"])
    return q, p


class NumericModel:
    def __init__(self, artifact):
        if artifact.get("abi") != ABI or artifact.get("ratios") != list(RATIOS):
            raise ValueError("numeric RLCD/action ABI mismatch")
        self.artifact = artifact
        self.risk = ResidualModel(artifact["baseline_bundle"])
        self.config = self.risk.config
        w, b, v, c = [np.asarray(p, dtype=float) for p in artifact["policy_weights"]]
        if (
            b.ndim != 1
            or not 1 <= len(b) <= 64
            or w.shape != (STATE_DIM, len(b))
            or v.shape != (len(b), 6)
            or c.shape != (6,)
            or not all(np.isfinite(p).all() for p in (w, b, v, c))
        ):
            raise ValueError("invalid numeric six-action RLCD head")
        for key in ("mean", "scale"):
            values = np.asarray(artifact[key], dtype=float)
            if (
                values.shape != (STATE_DIM,)
                or not np.isfinite(values).all()
                or (key == "scale" and np.any(values <= 0))
            ):
                raise ValueError("invalid RLCD normalization")
        calibration = artifact["calibration"]
        if (
            not number(calibration["binary"]["slope"])
            or calibration["binary"]["slope"] < 0
            or not number(calibration["binary"]["bias"])
            or not number(calibration["choice"]["temperature"])
            or calibration["choice"]["temperature"] <= 0
            or type(artifact["action_value_passed"]) is not bool
        ):
            raise ValueError("invalid numeric RLCD calibration/qualification")
        if not number(artifact["inference_budget_ms"]) or artifact["inference_budget_ms"] <= 0:
            raise ValueError("positive inference budget required")
        self.net = MLP.from_dict(artifact["policy_weights"])
        self.bundle = dict(self.risk.bundle)
        self.bundle["action_value_passed"] = artifact["action_value_passed"]
        for key in ("calibration_rows", "calibration_episodes"):
            support = artifact[key]
            if len(support) != 6 or any(type(x) is not int or x < 0 for x in support):
                raise ValueError("factual policy calibration support required")
            self.bundle[key] = [min(a, b) for a, b in zip(support, self.risk.bundle[key])]
        self.last_ms, self.last_q, self.last_p, self.overrun = 0.0, None, None, False

    def policy_forecast(self, state):
        return calibrated_forecasts(
            self.net, state, self.artifact["mean"], self.artifact["scale"], self.artifact["calibration"]
        )

    def predict(self, state):
        state = np.asarray(state, dtype=float)
        if state.shape != (STATE_DIM,) or not np.isfinite(state).all():
            raise ValueError("finite causal RLCD history required")
        start = time.perf_counter()
        q, p = self.policy_forecast(state)
        # Reuse ONLY the frozen risk ensemble; the old scalar QoE head is never called.
        state = np.asarray(state, dtype=float)
        rb = self.risk.bundle
        z = (state - rb["mean"]) / rb["scale"]
        support = float(np.sqrt(np.mean(z * z)))
        x = np.column_stack([np.tile(np.clip(z, -12, 12), (6, 1)), np.eye(6)])
        members = np.asarray([sigmoid(net(x).ravel()) for net in self.risk.risks])
        risk = self.risk.calibrator.predict(members.mean(axis=0))
        self.last_ms = (time.perf_counter() - start) * 1000
        self.last_q, self.last_p = None if q is None else q.tolist(), p.tolist()
        self.overrun = self.last_ms > self.artifact["inference_budget_ms"]
        if self.overrun:
            support = max(support, self.bundle["support_limit"] + 1)
        return p, risk, np.ptp(members, axis=0), support


class RLCDPolicy(JevBWE):
    """Same risk/clock/hard constraints; MAP choice from the calibrated distribution."""

    def observe(self, sample, *, safe_bps=None):
        self.model.last_q = self.model.last_p = None
        self.model.last_ms = 0.0
        self.model.overrun = False
        result = super().observe(sample, safe_bps=safe_bps)
        result.pop("utility")  # do not mislabel probabilities as scalar QoE estimates
        result.update(
            abi=self.model.artifact.get("laya_abi", ABI),
            action_probabilities=self.model.last_p,
            outcome_probabilities=self.model.last_q,
            inference_ms=self.model.last_ms,
            inference_overrun=self.model.overrun,
            probability_target="successful-action distribution under a uniform intervention; not optimal-action labels",
        )
        if self.model.overrun:
            result["learned_executed"] = False
            result["fallback"] = True
            result["reason"] = "inference_deadline"
        return result
