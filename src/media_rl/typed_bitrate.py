"""Jev-like typed bitrate decisions: a calibrated six-way choice over BWE ratios.

The head answers one typed ``choice`` question per decision epoch -- which
BWE-relative ratio is best over the next few seconds -- and reports a probability
for every option in a single forward pass. It is trained with RLCD as publicly
described for open typed-decision models: Gaussian noise on the reported logits,
a strictly proper log + spherical reward, and REINFORCE with a group baseline.
Software acts on the answer only above a confidence threshold; otherwise the
tuned fixed-ratio base policy runs. Labels are hindsight rollouts in the fluid
simulator, so every claim here is synthetic and none is a native codec result.
"""

import copy
import hashlib
import json
import math
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import log_softmax, logsumexp, softmax

from .environment import MediaEnvironment
from .jevbwe import RATIOS, STATE_DIM, CausalHistory, ResidualConfig, clipped_rate, number
from .jevbwe_experiment import Episode
from .networks import MLP
from .scenarios import ID_SCENARIOS, SCENARIOS
from .typed_bitrate_families import FAMILIES, TEST_FAMILIES, family_trace

ABI = "jevbwe_typed_v2"
HEADS = ("choice_rlcd", "choice_analytic", "regress")
SUMMARY = (
    "fresh",
    "requested_over_bwe",
    "target_over_bwe",
    "delivery_over_bwe",
    "rtt_excess",
    "since_change",
    "since_congestion",
    "never_congested",
    "knee_over_bwe",
    "knee",
    "peak_delivery_over_bwe",
)
FEATURE_DIM = STATE_DIM + len(SUMMARY)


@dataclass(frozen=True)
class TypedConfig:
    name: str = "jevbwe-typed-v2"
    seed: int = 27101
    steps: int = 360
    dt_ms: float = 100
    encoder_up_ms: float = 1500
    encoder_down_ms: float = 100
    switch_weight: float = 0.15
    bwe: str = "acked"
    ratios: list[float] = field(default_factory=lambda: list(RATIOS))
    base_ratio: float | None = None  # None: tuned on the ID tune split before any fitting
    decision_ms: float = 1000
    commit_ms: float = 3000
    tail_ms: float = 2000
    margin: float = 0.02
    summaries: bool = True  # False zeroes the long-memory features (ablation)
    tune_episodes: int = 64
    train_episodes: int = 800
    rounds: int = 5
    explore: float = 0.2
    calibration_episodes: int = 200
    hidden: int = 64
    epochs: int = 30
    batch_size: int = 256
    learning_rate: float = 0.002
    noise_std: float = 0.2
    group_size: int = 8
    spherical_weight: float = 0.5
    thresholds: list[float] = field(default_factory=lambda: [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    support_quantile: float = 0.995
    model_seeds: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    validation_seeds: list[int] = field(default_factory=lambda: list(range(29101, 29117)))
    test_seeds: list[int] = field(default_factory=lambda: list(range(29201, 29225)))
    scenarios: list[str] = field(default_factory=lambda: list(SCENARIOS))
    train_scenarios: list[str] = field(default_factory=lambda: list(ID_SCENARIOS))  # every fitting step
    development_scenarios: list[str] = field(default_factory=list)  # optional panel on the test seeds
    bootstrap_samples: int = 2000
    workers: int = 8
    residual: ResidualConfig = field(default_factory=ResidualConfig)

    def validate(self):
        self.residual.validate()
        sizes = (
            self.seed,
            self.steps,
            self.tune_episodes,
            self.train_episodes,
            self.rounds,
            self.calibration_episodes,
            self.hidden,
            self.epochs,
            self.batch_size,
            self.group_size,
            self.bootstrap_samples,
            self.workers,
        )
        if any(type(v) is not int or v < 1 for v in sizes) or self.group_size < 2:
            raise ValueError("positive integer study sizes required")
        timing = (self.dt_ms, self.encoder_up_ms, self.encoder_down_ms, self.decision_ms, self.commit_ms)
        if any(not number(v) or v <= 0 for v in timing) or not number(self.tail_ms) or self.tail_ms < 0:
            raise ValueError("positive timing required")
        if any(v % self.dt_ms for v in (self.decision_ms, self.commit_ms, self.tail_ms)):
            raise ValueError("decision, commit and tail must be whole control steps")
        if self.commit_ms < self.encoder_up_ms or self.horizon_steps >= self.steps:
            raise ValueError("commit must cover the encoder response and fit inside an episode")
        if self.bwe not in ("acked", "legacy") or type(self.summaries) is not bool:
            raise ValueError("bwe must be 'acked' or 'legacy' and summaries a boolean")
        ratios = self.ratios
        if len(ratios) < 2 or ratios != sorted(set(ratios)) or any(not number(r) or r <= 0 for r in ratios):
            raise ValueError("ratios must be sorted, unique and positive")
        if self.base_ratio is not None and self.base_ratio not in ratios:
            raise ValueError("base ratio must be one of the typed options")
        probabilities = (self.explore, self.support_quantile, *self.thresholds)
        if any(not number(v) or not 0 <= v <= 1 for v in probabilities) or not self.thresholds:
            raise ValueError("probabilities and thresholds must lie in [0, 1]")
        scales = (self.learning_rate, self.noise_std)
        weights = (self.margin, self.spherical_weight, self.switch_weight)
        if any(not number(v) or v <= 0 for v in scales) or any(not number(v) or v < 0 for v in weights):
            raise ValueError("invalid optimiser or reward weights")
        for seeds in (self.model_seeds, self.validation_seeds, self.test_seeds):
            if not seeds or len(set(seeds)) != len(seeds) or any(type(v) is not int or v < 0 for v in seeds):
                raise ValueError("unique nonnegative seeds required")
        if set(self.validation_seeds) & set(self.test_seeds):
            raise ValueError("validation and test seeds must be disjoint")
        seen = (*self.train_scenarios, *self.development_scenarios)
        if not self.scenarios or not self.train_scenarios:
            raise ValueError("training and test scenarios required")
        if {*seen, *self.scenarios} - set(SCENARIOS) - set(FAMILIES):
            raise ValueError("unknown scenario")
        if set(seen) & set(TEST_FAMILIES):
            raise ValueError("untouched test families are evaluation-only")
        return self

    @property
    def decision_steps(self):
        return int(self.decision_ms / self.dt_ms)

    @property
    def commit_steps(self):
        return int(self.commit_ms / self.dt_ms)

    @property
    def tail_steps(self):
        return int(self.tail_ms / self.dt_ms)

    @property
    def horizon_steps(self):
        return self.commit_steps + self.tail_steps

    def to_dict(self):
        return asdict(self)


def load_config(path):
    data = json.loads(Path(path).read_text())
    data["residual"] = ResidualConfig(**data.get("residual", {}))
    return TypedConfig(**data).validate()


def split_seed(seed, role, *index):
    """Hashed namespaces keep every fitting and evaluation role on disjoint traces."""
    key = f"{ABI}:{seed}:{role}:" + ":".join(str(i) for i in index)
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little")


class AckedBwe:
    """GCC-like delay/loss AIMD whose growth is bounded by 1.5x the acked rate.

    The legacy ``gcc`` budget has no such bound: it climbs to the ladder maximum
    whenever the sender stays below capacity, so a BWE-relative ratio silently
    becomes an absolute cap. The bound follows draft-ietf-rmcat-gcc-02, sec. 5.5.
    This is still a simplified estimator, not libwebrtc.
    """

    def __init__(self, dt_s, floor=0.15, ceiling=4.0):
        self.dt_s, self.floor, self.ceiling = dt_s, floor, ceiling
        self.budget, self.min_rtt = 0.6, float("inf")

    def act(self, obs):
        if not obs.finite() or not obs.valid or obs.feedback_age_s > 0.5:
            self.budget = max(self.floor, self.budget * 0.5)
            return
        self.min_rtt = min(self.min_rtt, obs.rtt_ms)
        queue = max(0, obs.rtt_ms - self.min_rtt)
        if obs.delay_trend_ms > 12 or queue > 70 or obs.loss > 0.1:
            self.budget = max(self.floor, min(self.budget * 0.85, obs.throughput_mbps * 0.9))
        elif obs.loss < 0.02 and queue < 40:
            grown = self.budget + max(0.08, 0.05 * self.budget) * self.dt_s / 0.1
            self.budget = max(self.budget, min(grown, 1.5 * obs.throughput_mbps))
        self.budget = min(self.budget, self.ceiling)


class Link(Episode):
    """Simulator episode whose state can be forked for hindsight rollouts."""

    def __init__(self, config, scenario, seed):
        legacy = scenario in SCENARIOS
        super().__init__(config, scenario if legacy else ID_SCENARIOS[0], seed)
        if not legacy:  # families of the broadened study live outside the legacy registry
            self.env = MediaEnvironment(self.env.config, family_trace(scenario, config.steps, seed))
        if config.bwe == "acked":
            self.bwe = AckedBwe(config.dt_ms / 1000)

    def fork(self):
        twin = copy.copy(self)
        twin.env = copy.copy(self.env)
        twin.env.feedback = list(self.env.feedback)
        twin.bwe, twin.encoder = copy.copy(self.bwe), copy.copy(self.encoder)
        twin.miss_feedback = list(self.miss_feedback)
        return twin


class Governor:
    """Hard rules shared by every method: stale floor, emergency cut, ceiling, increase dwell."""

    def __init__(self, config):
        self.config, self.ceiling_ratio = config.residual, max(config.ratios)
        self.last_change_ms = None
        self.hold_until_ms = 0.0
        self.rtt_floor = None

    def decide(self, sample, ratio):
        c, now = self.config, sample.sample_ms
        if self.last_change_ms is None:
            self.last_change_ms = now
        valid = sample.telemetry_valid() and sample.feedback_age_ms <= c.max_feedback_age_ms
        base = sample.bwe_bps if valid else c.min_bps
        ceiling = min(c.max_bps, self.ceiling_ratio * base)
        current = sample.requested_bps
        desired = clipped_rate(ratio, base, ceiling, c) if valid else min(current, c.min_bps, ceiling)
        emergency = not valid
        if valid:
            self.rtt_floor = sample.rtt_ms if self.rtt_floor is None else min(self.rtt_floor, sample.rtt_ms)
            emergency = congested(sample, self.rtt_floor)
        if emergency:
            self.hold_until_ms = max(self.hold_until_ms, now + c.up_dwell_ms)
            desired = min(desired, clipped_rate(0.7, current, ceiling, c))
        final = min(desired, ceiling)  # decreases and falling ceilings never wait
        if final > current + 1 and (now - self.last_change_ms < c.up_dwell_ms or now < self.hold_until_ms):
            final = min(current, ceiling)
        if abs(final - current) > 1:
            self.last_change_ms = now
        return final


def congested(sample, rtt_floor):
    """Causal congestion evidence; the governor cuts on it and the features remember it."""
    return (
        sample.loss >= 0.1
        or sample.rtt_ms - rtt_floor >= 70
        or (sample.rtt_delta_ms is not None and sample.rtt_delta_ms >= 30)
        or (sample.queue_trend_ms is not None and sample.queue_trend_ms >= 15)
    )


class Features:
    """Ordered three-second history plus long-memory causal summaries.

    Three seconds cannot show where the link last saturated, so the summaries keep
    the delivered rate at the last congestion onset (a capacity knee), the time since
    congestion and since the last cap change, and rates relative to the estimate.
    No clock, scenario identity, capacity or future outcome is included.
    """

    def __init__(self, config):
        self.residual, self.enabled = config.residual, config.summaries
        self.history = CausalHistory(config.residual)
        self.recent = deque()
        self.rtt_floor = self.requested = self.change_ms = self.congestion_ms = self.knee_bps = None
        self.was_congested = False

    def observe(self, sample):
        state, _ = self.history.observe(sample)
        if not self.enabled:
            return np.concatenate([state, np.zeros(len(SUMMARY))])
        now = sample.sample_ms
        if self.requested is None or abs(sample.requested_bps - self.requested) > 1:
            self.requested, self.change_ms = sample.requested_bps, now
        fresh = sample.telemetry_valid() and sample.feedback_age_ms <= self.residual.max_feedback_age_ms
        summary = np.zeros(len(SUMMARY))
        summary[5] = min(now - self.change_ms, 10000) / 1000
        if fresh:
            self.rtt_floor = sample.rtt_ms if self.rtt_floor is None else min(self.rtt_floor, sample.rtt_ms)
            now_congested = congested(sample, self.rtt_floor)
            if now_congested:
                window = [v for t, v in self.recent if now - t <= 2000]
                if not self.was_congested and window:  # an onset right after a feedback gap shows no knee
                    self.knee_bps = max(window)
                self.congestion_ms = now
            self.was_congested = now_congested
            self.recent.append((now, sample.delivery_bps))
            while now - self.recent[0][0] > 10000:
                self.recent.popleft()
            bwe = sample.bwe_bps
            summary[:5] = (
                1.0,
                min(sample.requested_bps / bwe, 3),
                min((sample.encoder_target_bps or 0) / bwe, 3),
                min(sample.delivery_bps / bwe, 3),
                min((sample.rtt_ms - self.rtt_floor) / 100, 20),
            )
            summary[10] = min(max(v for _, v in self.recent) / bwe, 3)
            if self.knee_bps is not None:
                summary[8:10] = min(self.knee_bps / bwe, 3), self.knee_bps / 4e6
        if self.congestion_ms is None:
            summary[6:8] = 3.0, 1.0
        else:
            summary[6] = min(now - self.congestion_ms, 30000) / 10000
        return np.concatenate([state, summary])


def step(link, governor, sample, ratio, config):
    """Apply one ratio for one control step; utility is delivered QoE minus the switch cost."""
    rate = governor.decide(sample, ratio)
    changed = abs(rate - sample.requested_bps) > 1
    switch = config.switch_weight * abs(math.log(rate / sample.requested_bps)) if changed else 0.0
    outcome = link.advance(rate)
    return outcome["qoe"] - switch, outcome


def rollout_values(link, governor, sample, config):
    """Mean utility of holding each ratio for the commit window, then the base policy.

    Branches replay the true future trace, so these are hindsight labels for training
    and evaluation only. No controller ever receives them.
    """
    values, unsafe = [], []
    for ratio in config.ratios:
        twin, rules, current, total, bad = link.fork(), copy.copy(governor), sample, 0.0, 0
        for k in range(config.horizon_steps):
            if k:
                current = twin.sample()
            chosen = ratio if k < config.commit_steps else config.base_ratio
            utility, outcome = step(twin, rules, current, chosen, config)
            total += utility
            bad += 1 - outcome["safe"]
        values.append(total / config.horizon_steps)
        unsafe.append(bad / config.horizon_steps)
    return values, unsafe


def choice_labels(values, config):
    """Best option per row; the base wins unless another ratio beats it by the margin."""
    values = np.asarray(values, dtype=float)
    base = config.ratios.index(config.base_ratio)
    best = values.max(axis=-1, keepdims=True)
    labels = np.argmax(best - values < 1e-9, axis=-1)  # lowest ratio among exact ties
    return np.where(best[..., 0] - values[..., base] < config.margin, base, labels)


def proper_reward(logits, labels, spherical_weight):
    """log p[y] + w * p[y]/||p||: strictly proper, so only honest probabilities maximise it."""
    log_p = log_softmax(logits, axis=-1)
    index = np.broadcast_to(labels, logits.shape[:-1])[..., None]
    chosen = np.take_along_axis(log_p, index, axis=-1)[..., 0]
    return chosen + spherical_weight * np.exp(chosen - 0.5 * logsumexp(2 * log_p, axis=-1))


def reward_gradient(logits, labels, spherical_weight):
    """Exact d reward / d logits; the noise-free limit of the RLCD estimator."""
    p = softmax(logits, axis=-1)
    onehot = np.eye(p.shape[-1])[labels]
    chosen = np.sum(p * onehot, axis=-1, keepdims=True)
    square = np.sum(p * p, axis=-1, keepdims=True)
    spherical = chosen * (onehot - p) / np.sqrt(square) - chosen * p * (p - square) / square**1.5
    return onehot - p + spherical_weight * spherical


def rlcd_gradient(logits, labels, config, rng):
    """REINFORCE over Gaussian logit reports with a leave-one-out group baseline."""
    noise = rng.normal(0, config.noise_std, (config.group_size, *logits.shape))
    reward = proper_reward(logits[None] + noise, labels, config.spherical_weight)
    baseline = (reward.sum(axis=0, keepdims=True) - reward) / (config.group_size - 1)
    return np.mean((reward - baseline)[..., None] * noise, axis=0) / config.noise_std**2


def fit_choice(x, labels, config, seed, *, estimator="rlcd"):
    if estimator not in ("rlcd", "analytic"):
        raise ValueError("estimator must be 'rlcd' or 'analytic'")
    rng = np.random.default_rng(seed)
    net = MLP(x.shape[1], config.hidden, len(config.ratios), rng)
    ids = np.arange(len(x))
    for epoch in range(config.epochs):
        rate = config.learning_rate * (1 - 0.9 * epoch / config.epochs)
        rng.shuffle(ids)
        for start in range(0, len(ids), config.batch_size):
            idx = ids[start : start + config.batch_size]
            logits = net(x[idx])
            if estimator == "rlcd":
                ascent = rlcd_gradient(logits, labels[idx], config, rng)
            else:
                ascent = reward_gradient(logits, labels[idx], config.spherical_weight)
            net.train(x[idx], -ascent / len(idx), rate)
    return net


def fit_regression(x, targets, config, seed):
    """Untyped baseline: least-squares advantage over the base ratio for every option."""
    rng = np.random.default_rng(seed)
    net = MLP(x.shape[1], config.hidden, targets.shape[1], rng)
    ids = np.arange(len(x))
    for epoch in range(config.epochs):
        rate = config.learning_rate * (1 - 0.9 * epoch / config.epochs)
        rng.shuffle(ids)
        for start in range(0, len(ids), config.batch_size):
            idx = ids[start : start + config.batch_size]
            net.train(x[idx], 2 * (net(x[idx]) - targets[idx]) / len(idx), rate)
    return net


def fit_temperature(logits, labels):
    """One held-out scalar; the argmax, and so the proposed ratio, is unchanged."""
    rows = np.arange(len(labels))

    def loss(log_t):
        return -np.mean(log_softmax(logits / math.exp(log_t), axis=-1)[rows, labels])

    result = minimize_scalar(loss, bounds=(-3, 3), method="bounded")
    return float(math.exp(result.x)) if result.success and result.fun <= loss(0.0) else 1.0


def reliability(probabilities, labels, bins=10):
    """Top-label calibration of the reported confidence against hindsight correctness."""
    p, labels = np.asarray(probabilities, dtype=float), np.asarray(labels, dtype=int)
    if not len(p):
        return dict(rows=0, accuracy=None, confidence=None, ece=None, nll=None, brier=None, bins=[])
    rows = np.arange(len(p))
    confidence, correct = p.max(axis=1), p.argmax(axis=1) == labels
    index = np.minimum((confidence * bins).astype(int), bins - 1)
    table, ece = [], 0.0
    for b in range(bins):
        mask = index == b
        if mask.any():
            gap = float(correct[mask].mean() - confidence[mask].mean())
            ece += mask.mean() * abs(gap)
            table.append(
                dict(
                    lower=b / bins,
                    rows=int(mask.sum()),
                    confidence=float(confidence[mask].mean()),
                    accuracy=float(correct[mask].mean()),
                )
            )
    return dict(
        rows=len(p),
        accuracy=float(correct.mean()),
        confidence=float(confidence.mean()),
        ece=float(ece),
        nll=float(-np.mean(np.log(np.maximum(p[rows, labels], 1e-300)))),
        brier=float(np.mean(np.sum((p - np.eye(p.shape[1])[labels]) ** 2, axis=1))),
        bins=table,
    )


def select_threshold(score, advantage, proposes, thresholds):
    """Threshold with the best mean rollout advantage over always running the base."""
    curve = [
        dict(
            threshold=float(t),
            coverage=float(np.mean(proposes & (score >= t))),
            advantage=float(np.mean(np.where(proposes & (score >= t), advantage, 0.0))),
        )
        for t in thresholds
    ]
    return max(curve, key=lambda row: (row["advantage"], row["threshold"]))["threshold"], curve


def payoff_table(advantage, labels, minimum=10):
    """payoff[a][b]: mean advantage of running option a when option b turned out best.

    Options that were rarely best keep a zero column, so they never argue for leaving the base.
    """
    options = advantage.shape[1]
    table = np.zeros((options, options))
    for b in range(options):
        if np.sum(labels == b) >= minimum:
            table[:, b] = advantage[labels == b].mean(axis=0)
    return table


class TypedModel:
    """Frozen heads plus the normalisation, temperatures and gates fitted with them."""

    def __init__(self, bundle):
        if bundle.get("abi") != ABI or len(bundle.get("ratios", [])) < 2:
            raise ValueError("typed JevBWE model ABI mismatch")
        self.bundle, self.ratios = bundle, list(bundle["ratios"])
        if bundle["base_ratio"] not in self.ratios:
            raise ValueError("base ratio must be one of the typed options")
        self.base = self.ratios.index(bundle["base_ratio"])
        self.mean, self.scale = (np.asarray(bundle[k], dtype=float) for k in ("mean", "scale"))
        if self.mean.shape != (FEATURE_DIM,) or self.scale.shape != (FEATURE_DIM,) or np.any(self.scale <= 0):
            raise ValueError("invalid typed JevBWE normalisation")
        self.heads = {}
        for name, head in bundle["heads"].items():
            net = MLP.from_dict(head["weights"])
            if net.params[0].shape[0] != FEATURE_DIM or net.params[2].shape[1] != len(self.ratios):
                raise ValueError("typed JevBWE head shape mismatch")
            if not all(np.isfinite(p).all() for p in net.params):
                raise ValueError("typed JevBWE weights must be finite")
            self.heads[name] = net

    def answer(self, state, head):
        """One forward pass: a probability per option (choice) or a predicted advantage (regress)."""
        raw = (np.asarray(state, dtype=float) - self.mean) / self.scale
        support = float(np.sqrt(np.mean(raw * raw)))
        output = self.heads[head](np.clip(raw, -12, 12))
        spec = self.bundle["heads"][head]
        if head == "regress":
            return output * spec["target_scale"], support
        return softmax(output / spec["temperature"]), support


RULES = ("map", "gated", "bayes", "greedy")


class TypedPolicy:
    """Turns the typed answer into a ratio; the base ratio runs whenever a guard rejects it.

    ``map`` takes the most probable option with no guard (ablation). ``gated`` acts on it
    only above the confidence threshold. ``bayes`` weighs the calibrated probabilities by
    the measured payoff of each option given which option turned out best, and so abstains
    by itself when no option has positive expected advantage. ``greedy`` is the regression
    baseline's argmax. All but ``map`` also require fresh telemetry and supported history.
    """

    def __init__(self, model, head, rule, config):
        if head not in model.heads or rule not in RULES or (rule == "greedy") != (head == "regress"):
            raise ValueError(f"unsupported typed head/rule {head}/{rule}")
        self.model, self.head, self.rule = model, head, rule
        spec = model.bundle["heads"][head]
        self.threshold = spec["threshold"] if rule == "gated" else None
        self.payoff = np.asarray(spec["payoff"], dtype=float) if rule == "bayes" else None
        self.residual = config.residual
        self.features = Features(config)
        self.ratio = model.bundle["base_ratio"]

    def observe(self, sample, decide):
        state = self.features.observe(sample)  # every step, so lags and summaries stay ordered
        if not decide:
            return self.ratio, None
        scores, support = self.model.answer(state, self.head)
        ranking = self.payoff @ scores if self.rule == "bayes" else scores
        proposal = int(np.argmax(ranking))
        fresh = sample.telemetry_valid() and sample.feedback_age_ms <= self.residual.max_feedback_age_ms
        if proposal == self.model.base or (self.rule == "bayes" and ranking[proposal] <= 0):
            reason = "base_answer"
        elif self.rule == "map":
            reason = "ungated"
        elif not fresh:
            reason = "stale_telemetry"
        elif support > self.model.bundle["support_limit"]:
            reason = "unsupported_history"
        elif self.rule == "gated" and scores[proposal] < self.threshold:
            reason = "low_confidence"
        else:
            reason = "accepted"
        arm = proposal if reason in ("accepted", "ungated") else self.model.base
        self.ratio = self.model.ratios[arm]
        supported = bool(support <= self.model.bundle["support_limit"])
        answer = dict(state=state, scores=scores, proposal=proposal, arm=arm, reason=reason)
        return self.ratio, dict(answer, fresh=bool(fresh), supported=supported)
