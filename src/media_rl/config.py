"""Strict JSON configuration and split-specific random streams."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from itertools import product
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class SimulatorConfig:
    steps: int = 240
    dt_s: float = 0.1
    queue_mbit: float = 0.6
    deadline_ms: float = 150.0
    safe_latency_ms: float = 150.0
    safe_loss: float = 0.05
    feedback_delay_steps: int = 1
    fec_efficiency: float = 0.85
    latency_weight: float = 0.8
    loss_weight: float = 5.0
    deadline_weight: float = 2.0
    switch_weight: float = 0.15
    bitrates: list[float] = field(default_factory=lambda: [0.15, 0.3, 0.6, 1.0, 1.6, 2.5, 4.0])
    fec_levels: list[float] = field(default_factory=lambda: [0.0, 0.1, 0.25])
    # Explicitly opt in: old experiments/checkpoints keep their original physics.
    backend: str = "fluid_v1"
    fps: int = 30
    packet_bytes: int = 1200
    packet_header_bytes: int = 40
    pacing_factor: float = 1.5
    cross_traffic_interval_s: float = 0.01


@dataclass(frozen=True)
class TrainingConfig:
    episodes: int = 32
    risk_episodes: int = 12
    calibration_episodes: int = 12
    hidden: int = 48
    batch_size: int = 64
    replay_size: int = 20000
    warmup: int = 128
    update_every: int = 4
    target_every: int = 100
    learning_rate: float = 0.001
    gamma: float = 0.95
    epsilon_start: float = 1.0
    epsilon_end: float = 0.08
    ensemble_size: int = 3
    risk_epochs: int = 15
    policy_features: str = "telemetry"
    demonstration_episodes: int = 0
    demonstration_epochs: int = 0
    demonstration_weight: float = 0.0
    demonstration_margin: float = 0.5
    demonstration_methods: list[str] = field(default_factory=lambda: ["gcc", "heuristic"])
    safety_horizon_steps: int = 1
    n_step: int = 1


@dataclass(frozen=True)
class GateConfig:
    threshold: float = 0.9
    release_margin: float = 0.03
    hold_steps: int = 3
    ood_quantile: float = 0.995
    max_feedback_age_s: float = 0.5
    calibration: str = "platt"
    shield_top_k: int = 5
    max_ensemble_std: float = 0.5


@dataclass(frozen=True)
class ExperimentConfig:
    name: str = "experiment"
    seeds: list[int] = field(default_factory=lambda: [11, 22, 33])
    test_seeds: list[int] = field(default_factory=lambda: [101, 102, 103, 104])
    scenarios: list[str] = field(
        default_factory=lambda: [
            "steady",
            "step",
            "ramp",
            "wifi",
            "collapse",
            "burst_loss",
            "bufferbloat",
            "handover",
            "outage",
            "feedback_gap",
            "capacity_surge",
        ]
    )
    # Optional periodic policy-training scenario schedule; duplicate entries intentionally weight families.
    # Risk fitting and calibration retain their separate default ID-only schedule.
    policy_training_scenarios: list[str] | None = None
    safety_training_scenarios: list[str] | None = None
    methods: list[str] = field(
        default_factory=lambda: [
            "safe",
            "heuristic",
            "gcc",
            "rl",
            "calibrated",
            "uncalibrated",
            "no_ood",
            "no_hysteresis",
            "single_model",
            "shielded",
        ]
    )
    bootstrap_samples: int = 2000
    simulator: SimulatorConfig = field(default_factory=SimulatorConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    gate: GateConfig = field(default_factory=GateConfig)

    def validate(self):
        from .controllers import METHODS
        from .scenarios import SCENARIOS

        if not self.name or not self.seeds or not self.test_seeds or not self.scenarios or not self.methods:
            raise ValueError("name, seeds, scenarios and methods must not be empty")
        for name, values in [("seeds", self.seeds), ("test_seeds", self.test_seeds)]:
            if len(set(values)) != len(values) or any(type(x) is not int or x < 0 for x in values):
                raise ValueError(f"{name} must contain unique nonnegative integers")
        if len(set(self.methods)) != len(self.methods) or len(set(self.scenarios)) != len(self.scenarios):
            raise ValueError("duplicate methods/scenarios")
        if set(self.methods) - set(METHODS) or set(self.scenarios) - set(SCENARIOS):
            raise ValueError("unknown method or scenario")
        if self.policy_training_scenarios is not None and (
            not isinstance(self.policy_training_scenarios, list)
            or not self.policy_training_scenarios
            or any(
                not isinstance(name, str) or name not in SCENARIOS for name in self.policy_training_scenarios
            )
        ):
            raise ValueError("policy_training_scenarios must be a nonempty weighted list of known scenarios")
        if self.safety_training_scenarios is not None and (
            not isinstance(self.safety_training_scenarios, list)
            or not self.safety_training_scenarios
            or any(
                not isinstance(name, str) or name not in SCENARIOS for name in self.safety_training_scenarios
            )
        ):
            raise ValueError("safety_training_scenarios must be a nonempty weighted list of known scenarios")
        s, t, g = self.simulator, self.training, self.gate
        if s.backend not in {"fluid_v1", "packet_v2"}:
            raise ValueError("unknown simulator backend")
        if any(type(v) is not int or v < 1 for v in [s.fps, s.packet_bytes]) or (
            type(s.packet_header_bytes) is not int or s.packet_header_bytes < 0
        ):
            raise ValueError("invalid packet/frame dimensions")
        if (
            not np.isfinite(s.pacing_factor)
            or not 1 <= s.pacing_factor <= 10
            or (not np.isfinite(s.cross_traffic_interval_s) or not 0 < s.cross_traffic_interval_s <= s.dt_s)
        ):
            raise ValueError("invalid pacing or cross-traffic timing")
        if (
            type(t.safety_horizon_steps) is not int
            or t.safety_horizon_steps < 1
            or t.safety_horizon_steps > 10
        ):
            raise ValueError("invalid safety horizon")
        if type(t.n_step) is not int or not 1 <= t.n_step <= 16:
            raise ValueError("n_step must be an integer in [1, 16]")
        if t.safety_horizon_steps > 1 and (
            s.backend != "packet_v2" or t.safety_horizon_steps * s.dt_s < s.dt_s + s.deadline_ms / 1000
        ):
            raise ValueError(
                "cohort safety horizon must cover all newly captured frame deadlines in packet_v2"
            )
        if (
            not isinstance(t.demonstration_methods, list)
            or not t.demonstration_methods
            or set(t.demonstration_methods) - {"gcc", "heuristic", "safe"}
        ):
            raise ValueError("invalid demonstration teachers")
        if t.policy_features not in {"telemetry", "history_v2"}:
            raise ValueError("unknown policy feature encoder")
        if any(type(v) is not int or v < 0 for v in [t.demonstration_episodes, t.demonstration_epochs]):
            raise ValueError("demonstration sizes must be nonnegative integers")
        if any(not np.isfinite(v) or v < 0 for v in [t.demonstration_weight, t.demonstration_margin]):
            raise ValueError("invalid demonstration loss parameters")
        if bool(t.demonstration_episodes) != bool(t.demonstration_epochs) or (
            t.demonstration_weight > 0 and not t.demonstration_episodes
        ):
            raise ValueError("demonstration episodes/epochs must be enabled together")
        for obj, names in [
            (s, ["steps", "feedback_delay_steps"]),
            (
                t,
                [
                    "episodes",
                    "risk_episodes",
                    "calibration_episodes",
                    "hidden",
                    "batch_size",
                    "replay_size",
                    "warmup",
                    "update_every",
                    "target_every",
                    "ensemble_size",
                    "risk_epochs",
                ],
            ),
            (g, ["hold_steps", "shield_top_k"]),
        ]:
            if any(type(getattr(obj, k)) is not int or getattr(obj, k) < 1 for k in names):
                raise ValueError("step counts and training sizes must be positive integers")
        positive = [
            s.dt_s,
            s.queue_mbit,
            s.deadline_ms,
            s.safe_latency_ms,
            t.learning_rate,
            g.max_feedback_age_s,
        ]
        if any(not np.isfinite(x) or x <= 0 for x in positive):
            raise ValueError("physical scales and learning rate must be finite and positive")
        probabilities = [
            s.safe_loss,
            s.fec_efficiency,
            t.gamma,
            t.epsilon_start,
            t.epsilon_end,
            g.threshold,
            g.release_margin,
            g.ood_quantile,
        ]
        if any(not np.isfinite(x) or not 0 <= x <= 1 for x in probabilities):
            raise ValueError("probability outside [0,1]")
        if g.threshold + g.release_margin > 1 or g.ood_quantile <= 0 or t.epsilon_end > t.epsilon_start:
            raise ValueError("invalid gate or epsilon range")
        if not np.isfinite(g.max_ensemble_std) or not 0 <= g.max_ensemble_std <= 0.5:
            raise ValueError("max_ensemble_std must be finite and in [0, 0.5]")
        if t.replay_size < max(t.batch_size, t.warmup) or s.steps < 10:
            raise ValueError("insufficient replay capacity or episode length")
        if g.calibration not in {"platt", "temperature"}:
            raise ValueError("calibration must be platt or temperature")
        if type(self.bootstrap_samples) is not int or self.bootstrap_samples < 20:
            raise ValueError("bootstrap_samples must be an integer >=20")
        for values, lower, upper in [(s.bitrates, 0, 100), (s.fec_levels, -1e-12, 1)]:
            if (
                not values
                or values != sorted(set(values))
                or any(not np.isfinite(x) or not lower < x <= upper for x in values)
            ):
                raise ValueError("action levels must be finite, unique, sorted and physically valid")
        if g.shield_top_k > len(s.bitrates) * len(s.fec_levels) * 2:
            raise ValueError("shield_top_k exceeds the configured action-space size")
        for w in [s.latency_weight, s.loss_weight, s.deadline_weight, s.switch_weight]:
            if not np.isfinite(w) or w < 0:
                raise ValueError("reward weights must be nonnegative")
        return self

    def to_dict(self):
        return asdict(self)

    def digest(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    def digest_matches(self, expected):
        """Accept historical hashes from before optional protocol fields."""
        if self.digest() == expected:
            return True
        sim_fields = [
            "backend",
            "fps",
            "packet_bytes",
            "packet_header_bytes",
            "pacing_factor",
            "cross_traffic_interval_s",
        ]
        train_fields = [
            "policy_features",
            "demonstration_episodes",
            "demonstration_epochs",
            "demonstration_weight",
            "demonstration_margin",
            "demonstration_methods",
            "safety_horizon_steps",
        ]
        groups = [
            ("gate", ["shield_top_k"], self.gate.shield_top_k == 5),
            ("gate", ["max_ensemble_std"], self.gate.max_ensemble_std == 0.5),
            ("training", ["n_step"], self.training.n_step == 1),
            (None, ["policy_training_scenarios"], self.policy_training_scenarios is None),
            (None, ["safety_training_scenarios"], self.safety_training_scenarios is None),
            (
                "simulator",
                sim_fields,
                all(getattr(self.simulator, k) == getattr(SimulatorConfig(), k) for k in sim_fields),
            ),
            (
                "training",
                train_fields,
                all(getattr(self.training, k) == getattr(TrainingConfig(), k) for k in train_fields),
            ),
        ]
        for drops in product(*([False, True] if allowed else [False] for _, _, allowed in groups)):
            legacy = self.to_dict()
            for drop, (section, keys, _) in zip(drops, groups):
                if drop:
                    for key in keys:
                        (legacy[section] if section else legacy).pop(key, None)
            if hashlib.sha256(json.dumps(legacy, sort_keys=True).encode()).hexdigest() == expected:
                return True
        return False


def load_config(path):
    data = json.loads(Path(path).read_text())
    for key, cls in [("simulator", SimulatorConfig), ("training", TrainingConfig), ("gate", GateConfig)]:
        data[key] = cls(**data.get(key, {}))
    return ExperimentConfig(**data).validate()


def split_seed(seed: int, split: str, episode: int = 0):
    """Stable namespaces: no Python hash randomization, no test/train overlap."""
    if split not in {
        "train",
        "risk",
        "calibration",
        "test",
        "bootstrap",
        "risk_v2",
        "calibration_v2",
        "action_calibration_v6",
        "validation",
        "demonstration",
        "frontier_calibration_v12",
    }:
        raise ValueError(f"unknown split: {split}")
    return int.from_bytes(hashlib.sha256(f"{seed}:{split}:{episode}".encode()).digest()[:8], "little")
