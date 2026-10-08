"""Reproducible JevBWE simulator pilot; never imports/relabels native evidence.

The legacy simulator/controller/config ABIs are unchanged. This adapter adds a
hypothetical asymmetric encoder response, continuous bitrate-only actions and
observable delayed credit. Synthetic QP/quality proxies are NOT codec measurements.
"""

import gzip
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .calibration import Calibrator
from .config import SimulatorConfig
from .controllers import DeterministicController
from .environment import Action, MediaEnvironment
from .jevbwe import (
    ABI,
    FEATURES,
    LAGS_MS,
    RATIOS,
    CausalHistory,
    JevBWE,
    ResidualConfig,
    ResidualModel,
    Sample,
    clipped_rate,
    number,
)
from .jevbwe_credit import SettledCredit
from .networks import MLP, sigmoid
from .scenarios import ID_SCENARIOS, SCENARIOS, make_trace

ROLES = ("train", "qualification", "risk", "calibration")
METHODS = ("bwe_raw", "bwe_dwell", "jevbwe", "jevbwe_ungated")
SOURCES = (
    "jevbwe.py",
    "jevbwe_credit.py",
    "jevbwe_experiment.py",
    "cli.py",
    "environment.py",
    "controllers.py",
    "networks.py",
    "calibration.py",
    "config.py",
    "scenarios.py",
)


@dataclass(frozen=True)
class StudyConfig:
    name: str = "jevbwe-synthetic-pilot-v1"
    seed: int = 7101
    steps: int = 360
    dt_ms: float = 100
    train_episodes: int = 36
    qualification_episodes: int = 18
    risk_episodes: int = 18
    calibration_episodes: int = 18
    hold_ms: float = 3000
    encoder_up_ms: float = 1500
    encoder_down_ms: float = 100
    credit_window_ms: float = 600
    switch_weight: float = 0.15
    hidden: int = 16
    epochs: int = 60
    batch_size: int = 32
    learning_rate: float = 0.003
    test_seeds: list[int] = field(default_factory=lambda: [8101, 8102, 8103, 8104])
    scenarios: list[str] = field(
        default_factory=lambda: ["steady", "step", "wifi", "collapse", "feedback_gap"]
    )
    residual: ResidualConfig = field(default_factory=ResidualConfig)

    def validate(self):
        self.residual.validate()
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("JevBWE study name required")
        if (
            any(
                type(v) is not int or v < 1
                for v in (
                    self.seed,
                    self.steps,
                    self.train_episodes,
                    self.qualification_episodes,
                    self.risk_episodes,
                    self.calibration_episodes,
                    self.hidden,
                    self.epochs,
                    self.batch_size,
                )
            )
            or self.hidden > 64
            or self.steps < 10
        ):
            raise ValueError("invalid JevBWE study sizes/seed")
        if (
            any(
                not number(v) or v <= 0
                for v in (
                    self.dt_ms,
                    self.hold_ms,
                    self.encoder_up_ms,
                    self.encoder_down_ms,
                    self.credit_window_ms,
                    self.learning_rate,
                )
            )
            or not number(self.switch_weight)
            or self.switch_weight < 0
        ):
            raise ValueError("invalid JevBWE study timing/optimizer")
        if (
            self.dt_ms > self.residual.history_tolerance_ms
            or self.hold_ms % self.dt_ms
            or self.steps * self.dt_ms <= self.hold_ms
            or self.encoder_down_ms > self.encoder_up_ms
            or self.hold_ms <= self.encoder_up_ms + self.credit_window_ms
        ):
            raise ValueError("JevBWE hold must cover modeled upward response and credit")
        if (
            not isinstance(self.scenarios, list)
            or not self.scenarios
            or len(set(self.scenarios)) != len(self.scenarios)
            or set(self.scenarios) - set(SCENARIOS)
        ):
            raise ValueError("invalid JevBWE evaluation scenarios")
        if (
            not isinstance(self.test_seeds, list)
            or not self.test_seeds
            or any(type(v) is not int or v < 0 for v in self.test_seeds)
            or len(set(self.test_seeds)) != len(self.test_seeds)
        ):
            raise ValueError("unique nonnegative JevBWE test seeds required")
        return self

    def to_dict(self):
        return asdict(self)

    def fitting_hash(self):
        data = self.to_dict()
        for key in ("name", "test_seeds", "scenarios"):
            data.pop(key)
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def load_study(path):
    data = json.loads(Path(path).read_text())
    data["residual"] = ResidualConfig(**data.get("residual", {}))
    return StudyConfig(**data).validate()


def role_seed(seed, role, episode):
    if role not in (*ROLES, "test", "optimizer", "bootstrap"):
        raise ValueError("unknown JevBWE role")
    return int.from_bytes(hashlib.sha256(f"{ABI}:{seed}:{role}:{episode}".encode()).digest()[:8], "little")


class DelayedEncoder:
    """Synthetic response hypothesis, not fitted native encoder dynamics."""

    def __init__(self, config):
        self.config = config
        self.target_bps = self.requested_bps = config.residual.min_bps
        self.pending = None

    def command(self, rate, now):
        if rate != self.requested_bps:
            delay = self.config.encoder_up_ms if rate > self.target_bps else self.config.encoder_down_ms
            self.pending = (now + delay, rate)
            self.requested_bps = rate

    def advance(self, now):
        if self.pending is not None and now >= self.pending[0]:
            self.target_bps = self.pending[1]
            self.pending = None
        # Application content limitation: requested cap, encoder target and output differ.
        return self.target_bps * (0.90 + 0.08 * np.sin(now / 1700))


class Episode:
    def __init__(self, config, scenario, seed):
        self.config = config
        sim = SimulatorConfig(steps=config.steps, dt_s=config.dt_ms / 1000, fec_levels=[0.0], switch_weight=0)
        self.env = MediaEnvironment(sim, make_trace(scenario, config.steps, seed))
        self.bwe = DeterministicController(self.env.actions, "gcc", sim.dt_s)
        self.encoder = DelayedEncoder(config)
        self.now = 0.0
        self.actual_bps = config.residual.min_bps * 0.90
        self.last_miss = None
        self.miss_feedback = []

    def sample(self):
        obs = self.env.observation
        self.bwe.act(obs)  # updates a telemetry-only conventional budget exactly once
        ready = [m for t, m in self.miss_feedback if t <= self.now]
        if ready:
            self.last_miss = ready[-1]
        self.miss_feedback = [(t, m) for t, m in self.miss_feedback if t > self.now]
        return Sample(
            sample_ms=self.now,
            bwe_bps=self.bwe.budget * 1e6,
            delivery_bps=obs.throughput_mbps * 1e6,
            rtt_ms=obs.rtt_ms,
            requested_bps=self.encoder.requested_bps,
            actual_bps=self.actual_bps,
            encoder_target_bps=self.encoder.target_bps,
            rtt_delta_ms=obs.delay_trend_ms,
            loss=obs.loss,
            jitter_ms=obs.jitter_ms,
            queue_trend_ms=obs.delay_trend_ms,
            qp=float(np.clip(52 - 7 * np.log1p(self.encoder.target_bps / 150000), 4, 63)),
            frame_size_bytes=self.actual_bps / 8 / 30,
            deadline_miss=self.last_miss,
            feedback_age_ms=obs.feedback_age_s * 1000,
            valid=obs.valid,
        )

    def advance(self, requested_bps):
        self.encoder.command(requested_bps, self.now)
        self.actual_bps = self.encoder.advance(self.now)
        self.env.actions = (Action(self.actual_bps / 1e6, 0.0, True),)
        _, _, _, result = self.env.step(0)
        self.now += self.config.dt_ms
        self.miss_feedback.append((self.now + self.env.observation.rtt_ms / 2, result["deadline_miss"]))
        return result


def collect_role(config, role):
    cohorts, samples = [], []
    hold_steps = int(config.hold_ms / config.dt_ms)
    for episode in range(getattr(config, f"{role}_episodes")):
        seed = role_seed(config.seed, role, episode)
        scenario = ID_SCENARIOS[episode % len(ID_SCENARIOS)]  # never evaluation/OOD labels
        runtime = Episode(config, scenario, seed)
        history = CausalHistory(config.residual)
        tracker = SettledCredit(config.credit_window_ms, switch_weight=config.switch_weight)
        rng = np.random.default_rng(seed)
        schedule = []
        while len(schedule) < config.steps // hold_steps + 1:
            schedule.extend(rng.permutation(len(RATIOS)).tolist())
        for step in range(config.steps):
            sample = runtime.sample()
            state, _ = history.observe(sample)
            request = sample.requested_bps
            if step % hold_steps == 0:
                action = schedule[step // hold_steps]
                ceiling = min(config.residual.max_bps, RATIOS[-1] * sample.bwe_bps)
                candidates = [clipped_rate(r, sample.bwe_bps, ceiling, config.residual) for r in RATIOS]
                request = candidates[action]
                old = tracker.begin(
                    now_ms=sample.sample_ms,
                    action_index=action,
                    state=state.tolist(),
                    requested_bps=request,
                    previous_bps=sample.requested_bps,
                    network_delay_ms=sample.rtt_ms / 2,
                    role=role,
                    episode=episode,
                    scenario=scenario,
                    trace_seed=seed,
                    base_bps=sample.bwe_bps,
                    identifiable=sum(abs(v - request) <= 1 for v in candidates) == 1,
                )
                if old is not None:
                    cohorts.append(old)
            result = runtime.advance(request)
            row = tracker.observe(
                now_ms=runtime.now,
                interval_ms=config.dt_ms,
                encoder_target_bps=runtime.encoder.target_bps,
                delivered_qoe=result["qoe"],
                unsafe=1 - result["safe"],
            )
            if row is not None:
                cohorts.append(row)
            samples.append(
                dict(
                    role=role,
                    episode=episode,
                    step=step,
                    sample=asdict(sample),
                    command_bps=request,
                    encoder_target_bps=runtime.encoder.target_bps,
                    delivered_qoe=result["qoe"],
                    unsafe=1 - result["safe"],
                )
            )
        tail = tracker.finish()
        if tail is not None:
            cohorts.append(tail)
    return cohorts, samples


def inputs(rows, mean, scale, *, blind=False):
    states = np.asarray([r["state"] for r in rows])
    z = np.clip((states - mean) / scale, -12, 12)
    actions = (
        np.zeros((len(rows), len(RATIOS)))
        if blind
        else np.eye(len(RATIOS))[[r["action_index"] for r in rows]]
    )
    return np.column_stack([z, actions])


def fit_network(x, y, config, seed, *, binary=False, indices=None):
    rng = np.random.default_rng(seed)
    net = MLP(x.shape[1], config.hidden, 1, rng)
    indices = np.arange(len(x)) if indices is None else np.asarray(indices).copy()
    for _ in range(config.epochs):
        rng.shuffle(indices)
        for start in range(0, len(indices), config.batch_size):
            idx = indices[start : start + config.batch_size]
            predicted = net(x[idx]).ravel()
            if binary:
                predicted = sigmoid(predicted)
            gradient = ((predicted - y[idx]) * (1 if binary else 2) / len(idx))[:, None]
            net.train(x[idx], gradient, config.learning_rate)
    return net


def qualify_action_value(
    rows, conditional, blind, mean, scale, reward_mean, reward_scale, *, target="reward"
):
    if target not in ("reward", "delivered_reward"):
        raise ValueError("utility or delivered-only qualification target required")
    # Only genuinely changed, non-aliased factual commands; unchanged rows cannot make the check green.
    rows = [r for r in rows if r["changed_action"] and r["identifiable"]]
    folds = []
    for fold in (None, 0, 1):
        selected = [r for r in rows if fold is None or r["episode"] % 2 == fold]
        if not selected:
            folds.append(dict(fold=fold, rows=0, skill=None, conditional_mse=None, blind_mse=None))
            continue
        y = np.asarray([r[target] for r in selected])
        p = conditional(inputs(selected, mean, scale)).ravel() * reward_scale + reward_mean
        q = blind(inputs(selected, mean, scale, blind=True)).ravel() * reward_scale + reward_mean
        a, b = float(np.mean((p - y) ** 2)), float(np.mean((q - y) ** 2))
        folds.append(
            dict(
                fold=fold, rows=len(y), skill=1 - a / b if b > 1e-12 else None, conditional_mse=a, blind_mse=b
            )
        )
    counts = [sum(r["action_index"] == i for r in rows) for i in range(len(RATIOS))]
    passed = (
        len(rows) >= 24
        and min(counts) >= 2
        and all(f["skill"] is not None and f["skill"] >= 0.01 for f in folds)
    )
    return dict(
        passed=passed,
        threshold=0.01,
        action_counts=counts,
        folds=folds,
        scope="changed non-aliased role-disjoint synthetic factual cohorts; necessary, not causal/native proof",
    )


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def dump_gzip(path, data):
    Path(path).write_bytes(gzip.compress(json.dumps(data, sort_keys=True, allow_nan=False).encode(), mtime=0))


def source_hashes():
    root = Path(__file__).parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCES}


def seal(path):
    hashes = {
        str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(path.rglob("*"))
        if p.is_file() and p != path / "manifest.json"
    }
    dump(
        path / "manifest.json", dict(abi=ABI, scope="synthetic_only_not_native_validation", artifacts=hashes)
    )


def train_study(config, out):
    config.validate()
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    dump(out / "config.json", config.to_dict())
    data, raw, complete = {}, {}, {}
    for role in ROLES:
        data[role], raw[role] = collect_role(config, role)
        complete[role] = [r for r in data[role] if not r["censored"]]
        dump_gzip(out / f"{role}_cohorts.json.gz", data[role])
        dump_gzip(out / f"{role}_samples.json.gz", raw[role])
        if not complete[role]:
            raise ValueError(f"no encoder-settled {role} cohorts; censored evidence saved in {out}")
    train = complete["train"]
    states = np.asarray([r["state"] for r in train])
    mean, scale = states.mean(axis=0), np.maximum(states.std(axis=0), 0.05)
    rewards = np.asarray([r["reward"] for r in train])
    reward_mean, reward_scale = float(rewards.mean()), float(max(rewards.std(), 0.1))
    y = (rewards - reward_mean) / reward_scale
    seed = role_seed(config.seed, "optimizer", 0)
    conditional = fit_network(inputs(train, mean, scale), y, config, seed)
    blind = fit_network(inputs(train, mean, scale, blind=True), y, config, seed)
    utility_qualification = qualify_action_value(
        complete["qualification"], conditional, blind, mean, scale, reward_mean, reward_scale
    )
    # An analytically known action-dependent switch cost cannot identify delivered action value.
    # Fit an additional matched pair offline, on delivered-only labels, with the same recipe.
    delivered = np.asarray([r["delivered_reward"] for r in train])
    delivered_mean, delivered_scale = float(delivered.mean()), float(max(delivered.std(), 0.1))
    delivered_y = (delivered - delivered_mean) / delivered_scale
    delivered_conditional = fit_network(inputs(train, mean, scale), delivered_y, config, seed)
    delivered_blind = fit_network(inputs(train, mean, scale, blind=True), delivered_y, config, seed)
    delivered_qualification = qualify_action_value(
        complete["qualification"],
        delivered_conditional,
        delivered_blind,
        mean,
        scale,
        delivered_mean,
        delivered_scale,
        target="delivered_reward",
    )
    qualification = dict(
        passed=utility_qualification["passed"] and delivered_qualification["passed"],
        utility=utility_qualification,
        delivered_only=delivered_qualification,
    )
    risk_rows = complete["risk"]
    risk_x = inputs(risk_rows, mean, scale)
    risk_y = np.asarray([r["unsafe"] for r in risk_rows])
    episodes = np.asarray([r["episode"] for r in risk_rows])
    risks = []
    for member in range(3):
        member_seed = role_seed(config.seed, "optimizer", member + 1)
        rng = np.random.default_rng(member_seed)
        groups = np.unique(episodes)
        indices = np.concatenate(
            [np.flatnonzero(episodes == e) for e in rng.choice(groups, len(groups), replace=True)]
        )
        risks.append(fit_network(risk_x, risk_y, config, member_seed, binary=True, indices=indices))
    calibration = complete["calibration"]
    cal_x = inputs(calibration, mean, scale)
    cal_y = np.asarray([r["unsafe"] for r in calibration])
    raw_p = np.mean([sigmoid(net(cal_x).ravel()) for net in risks], axis=0)
    calibrator = Calibrator.fit(raw_p, cal_y)
    risk_support = np.sqrt(
        np.mean(((np.asarray([r["state"] for r in risk_rows]) - mean) / scale) ** 2, axis=1)
    )
    bundle = dict(
        abi=ABI,
        config=asdict(config.residual),
        ratios=list(RATIOS),
        feature_names=list(FEATURES),
        lags_ms=list(LAGS_MS),
        training_roles=list(ROLES),
        fitting_hash=config.fitting_hash(),
        mean=mean.tolist(),
        scale=scale.tolist(),
        reward_mean=reward_mean,
        reward_scale=reward_scale,
        utility_weights=conditional.to_dict(),
        blind_control_weights=blind.to_dict(),
        delivered_qualification_weights=dict(
            conditional=delivered_conditional.to_dict(),
            blind=delivered_blind.to_dict(),
            mean=delivered_mean,
            scale=delivered_scale,
        ),
        risk_weights=[net.to_dict() for net in risks],
        calibrator=asdict(calibrator),
        support_limit=float(np.quantile(risk_support, 0.995)),
        action_value_passed=qualification["passed"],
        calibration_rows=[sum(r["action_index"] == i for r in calibration) for i in range(len(RATIOS))],
        calibration_episodes=[
            len({r["episode"] for r in calibration if r["action_index"] == i}) for i in range(len(RATIOS))
        ],
        source_sha256=source_hashes(),
        synthetic_only=True,
    )
    ResidualModel(bundle)  # mechanically verify the emitted public inference ABI
    dump(out / "model.json", bundle)
    report = dict(
        abi=ABI,
        synthetic_only=True,
        promoted=False,
        qualification=qualification,
        roles={
            role: dict(
                cohorts=len(data[role]),
                complete=len(complete[role]),
                censored=len(data[role]) - len(complete[role]),
                censor_reasons=dict(Counter(r["censor_reason"] for r in data[role] if r["censored"])),
                changed_complete=sum(r["changed_action"] for r in complete[role]),
            )
            for role in ROLES
        },
        calibration=dict(
            unsafe_rate=float(cal_y.mean()),
            raw_brier=float(np.mean((raw_p - cal_y) ** 2)),
            fitted_brier=float(np.mean((calibrator.predict(raw_p) - cal_y) ** 2)),
            method=calibrator.method,
            scope="factual randomized-hold labels, not selected live-policy calibration",
        ),
        parameter_count=sum(p.size for p in conditional.params),
    )
    dump(out / "training_report.json", report)
    snapshot = out / "source"
    snapshot.mkdir()
    for name in SOURCES:
        (snapshot / name).write_bytes((Path(__file__).parent / name).read_bytes())
    seal(out)
    return report


def evaluate_episode(config, model, scenario, seed, method):
    runtime = Episode(config, scenario, role_seed(seed, "test", SCENARIOS_ORDER.index(scenario)))
    policy = JevBWE(
        model if method.startswith("jevbwe") else None, config.residual, ungated=method == "jevbwe_ungated"
    )
    rows = []
    for step in range(config.steps):
        sample = runtime.sample()
        decision = policy.observe(sample)
        request = (
            clipped_rate(
                1, sample.bwe_bps, min(config.residual.max_bps, RATIOS[-1] * sample.bwe_bps), config.residual
            )
            if method == "bwe_raw"
            else decision["requested_bps"]
        )
        if method == "bwe_raw":
            decision.update(
                requested_bps=request,
                reason="raw_bwe",
                effective_ratio=request / sample.bwe_bps,
                base_bps=sample.bwe_bps,
                safe_bps=min(config.residual.max_bps, RATIOS[-1] * sample.bwe_bps),
            )
        changed = abs(request - sample.requested_bps) > 1
        switch = config.switch_weight * abs(np.log(request / sample.requested_bps)) if changed else 0
        if changed:
            policy.acknowledge(request, sample.sample_ms)
        result = runtime.advance(request)
        # No hidden capacity/service/queue fields are exposed to the model or emitted as features.
        metrics = {
            key: result[key] for key in ("qoe", "latency_ms", "raw_loss", "deadline_miss", "goodput_mbps")
        }
        rows.append(
            dict(
                step=step,
                sample=asdict(sample),
                decision=decision,
                changed=changed,
                encoder_target_bps=runtime.encoder.target_bps,
                actual_bps=runtime.actual_bps,
                metrics=metrics,
                utility=result["qoe"] - switch,
            )
        )
    return rows


SCENARIOS_ORDER = tuple(SCENARIOS)  # stable scenario identities independent of evaluation ordering


def evaluate_study(config, model_path, out):
    config.validate()
    model_path, out = Path(model_path), Path(out)
    bundle = json.loads(model_path.read_text())
    model = ResidualModel(bundle)
    if bundle.get("fitting_hash") != config.fitting_hash() or bundle.get("synthetic_only") is not True:
        raise ValueError("JevBWE fitting/physics config mismatch or non-synthetic checkpoint")
    if bundle.get("source_sha256") != source_hashes():
        raise ValueError("JevBWE source drift from frozen fitting snapshot; explicitly fork/refit")
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    dump(out / "config.json", config.to_dict())
    dump(out / "model.json", bundle)
    summaries = []
    for scenario in config.scenarios:
        for seed in config.test_seeds:
            for method in METHODS:
                rows = evaluate_episode(config, model, scenario, seed, method)
                dump_gzip(out / f"{scenario}_{seed}_{method}.json.gz", rows)
                summaries.append(
                    dict(
                        scenario=scenario,
                        seed=seed,
                        method=method,
                        utility=float(np.mean([r["utility"] for r in rows])),
                        deadline_miss=float(np.mean([r["metrics"]["deadline_miss"] for r in rows])),
                        latency_p95_ms=float(np.quantile([r["metrics"]["latency_ms"] for r in rows], 0.95)),
                        cap_changes=sum(r["changed"] for r in rows),
                        learned_steps=sum(r["decision"]["learned_executed"] for r in rows),
                        fallback_steps=sum(r["decision"]["fallback"] for r in rows),
                        reasons=dict(Counter(r["decision"]["reason"] for r in rows)),
                    )
                )
    contrasts = []
    for reference in ("bwe_raw", "bwe_dwell"):
        effects = []
        for seed in config.test_seeds:
            effects.append(
                np.mean(
                    [
                        next(
                            r["utility"]
                            for r in summaries
                            if r["seed"] == seed and r["scenario"] == scenario and r["method"] == "jevbwe"
                        )
                        - next(
                            r["utility"]
                            for r in summaries
                            if r["seed"] == seed and r["scenario"] == scenario and r["method"] == reference
                        )
                        for scenario in config.scenarios
                    ]
                )
            )
        rng = np.random.default_rng(role_seed(config.seed, "bootstrap", 0))
        boots = np.mean(rng.choice(effects, (2000, len(effects)), replace=True), axis=1)
        contrasts.append(
            dict(
                reference=reference,
                paired_seed_mean=float(np.mean(effects)),
                interval95=np.quantile(boots, [0.025, 0.975]).tolist(),
                seeds=len(effects),
            )
        )
    report = dict(
        abi=ABI,
        synthetic_only=True,
        promoted=False,
        action_value_passed=bundle["action_value_passed"],
        model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
        evaluation_source_sha256=source_hashes(),
        episodes=summaries,
        contrasts=contrasts,
        limitations=[
            "hypothetical encoder delays and QP proxy, not Chrome/VP8 measurements",
            "randomized-hold risk calibration is not selected-live-policy calibration",
            "ungated is an explicitly unqualified/unscreened diagnostic ablation",
            "no native causal-value, perceptual quality, superiority or safety claim",
        ],
    )
    dump(out / "evaluation_report.json", report)
    seal(out)
    return report


def audit_study(path):
    """Artifact integrity only; not raw native replay or proof of model efficacy."""
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest.get("abi") != ABI or not manifest.get("artifacts"):
        raise ValueError("invalid JevBWE manifest")
    actual = {
        str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in path.rglob("*")
        if p.is_file() and p != path / "manifest.json"
    }
    if actual != manifest["artifacts"]:
        raise ValueError("JevBWE artifact hash/inventory mismatch")
    return dict(artifacts=len(actual), synthetic_only=True, integrity_only=True)


def run_study(config, out):
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    dump(out / "config.json", config.to_dict())  # predeclare test panel before fitting
    training = train_study(config, out / "training")
    evaluation = evaluate_study(config, out / "training" / "model.json", out / "evaluation")
    seal(out)
    return dict(training=training, contrasts=evaluation["contrasts"], synthetic_only=True, promoted=False)
