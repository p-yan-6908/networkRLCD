"""Opt-in bitrate-only residual over an externally supplied causal BWE.

This ABI is deliberately incompatible with the absolute-cap native actors. Encoder
fields are nullable, not fabricated zeros. No trace, future reward or capacity is
accepted by the policy. Probabilities are empirical screens, not safety guarantees.
"""

import math
from dataclasses import asdict, dataclass

import numpy as np

from .calibration import Calibrator
from .networks import MLP, sigmoid

ABI = "jevbwe_residual_v1"
RATIOS = (0.60, 0.70, 0.80, 0.90, 1.00, 1.05)
FEATURES = (
    "bwe_bps",
    "delivery_bps",
    "rtt_ms",
    "rtt_delta_ms",
    "loss",
    "jitter_ms",
    "queue_trend_ms",
    "requested_bps",
    "actual_bps",
    "encoder_target_bps",
    "qp",
    "frame_size_bytes",
    "deadline_miss",
)
SCALES = (4e6, 4e6, 200, 100, 1, 50, 100, 4e6, 4e6, 4e6, 64, 20000, 1)
LAGS_MS = (3000, 2000, 1000, 0)  # ordered causal snapshots, not a permutation-invariant mean
STATE_DIM = len(LAGS_MS) * (2 * len(FEATURES) + 1)


def number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class ResidualConfig:
    min_bps: float = 150000
    max_bps: float = 4000000
    up_dwell_ms: float = 1800
    max_history_ms: float = 4000
    reset_gap_ms: float = 1000
    history_tolerance_ms: float = 250
    max_feedback_age_ms: float = 500
    fallback_ratio: float = 0.85
    risk_limit: float = 0.10
    disagreement_limit: float = 0.15
    min_calibration_rows: int = 4
    min_calibration_episodes: int = 2

    def validate(self):
        if (
            any(
                not number(v) or v <= 0
                for v in (
                    self.min_bps,
                    self.max_bps,
                    self.up_dwell_ms,
                    self.max_history_ms,
                    self.reset_gap_ms,
                    self.history_tolerance_ms,
                    self.max_feedback_age_ms,
                )
            )
            or self.min_bps > self.max_bps
            or self.max_history_ms < max(LAGS_MS)
        ):
            raise ValueError("invalid JevBWE rates/history/timing")
        if (
            any(
                not number(v) or not 0 <= v <= 1
                for v in (
                    self.fallback_ratio,
                    self.risk_limit,
                    self.disagreement_limit,
                )
            )
            or self.fallback_ratio == 0
        ):
            raise ValueError("invalid JevBWE probability/headroom")
        if any(
            type(v) is not int or v < 1
            for v in (
                self.min_calibration_rows,
                self.min_calibration_episodes,
            )
        ):
            raise ValueError("positive calibration support counts required")
        return self


@dataclass(frozen=True)
class Sample:
    sample_ms: float
    bwe_bps: float | None
    delivery_bps: float | None
    rtt_ms: float | None
    requested_bps: float
    actual_bps: float | None = None
    encoder_target_bps: float | None = None
    rtt_delta_ms: float | None = None
    loss: float | None = None
    jitter_ms: float | None = None
    queue_trend_ms: float | None = None
    qp: float | None = None
    frame_size_bytes: float | None = None
    deadline_miss: float | None = None
    feedback_age_ms: float = 0
    valid: bool = True

    def telemetry_valid(self):
        if self.valid is not True or not number(self.feedback_age_ms) or self.feedback_age_ms < 0:
            return False
        for name in FEATURES:
            v = getattr(self, name)
            if v is None:
                if name in ("bwe_bps", "delivery_bps", "rtt_ms", "requested_bps", "loss"):
                    return False
            elif not number(v) or (name not in ("rtt_delta_ms", "queue_trend_ms") and v < 0):
                return False
            elif name in ("loss", "deadline_miss") and v > 1:
                return False
        return self.bwe_bps > 0 and self.rtt_ms > 0


class CausalHistory:
    def __init__(self, config=None):
        self.config = (config or ResidualConfig()).validate()
        self.rows = []
        self.last_ms = None

    def observe(self, sample):
        now, c = sample.sample_ms, self.config
        if not number(now) or now < 0 or (self.last_ms is not None and now <= self.last_ms):
            raise ValueError("JevBWE sample clock must strictly advance")
        reset = self.last_ms is not None and now - self.last_ms > c.reset_gap_ms
        if reset:
            self.rows.clear()
        self.rows.append(sample)
        self.rows = [s for s in self.rows if now - s.sample_ms <= c.max_history_ms]
        self.last_ms = now
        state = []
        for lag in LAGS_MS:
            cutoff = now - lag
            candidates = [s for s in self.rows if s.sample_ms <= cutoff]
            row = candidates[-1] if candidates else None
            if row is None or cutoff - row.sample_ms > c.history_tolerance_ms:
                state.extend([0.0] * (2 * len(FEATURES) + 1))
                continue
            network_fresh = row.telemetry_valid() and row.feedback_age_ms <= c.max_feedback_age_ms
            local_fields = ("requested_bps", "actual_bps", "encoder_target_bps", "qp", "frame_size_bytes")
            for name, scale in zip(FEATURES, SCALES):
                value = getattr(row, name)
                present = (
                    number(value)
                    and (network_fresh or name in local_fields)
                    and (value >= 0 or name in ("rtt_delta_ms", "queue_trend_ms"))
                    and (name not in ("loss", "deadline_miss") or value <= 1)
                )
                state.extend([float(np.clip(value / scale, -20, 20)) if present else 0.0, float(present)])
            state.append(min(20, (now - row.sample_ms) / 1000))
        return np.asarray(state), reset


def clipped_rate(ratio, base_bps, safe_bps, config):
    # When safety and the application minimum conflict, safety wins (even at zero).
    ceiling = max(0.0, min(safe_bps, config.max_bps))
    return float(min(ceiling, max(config.min_bps, ratio * base_bps)))


def validate_bundle(bundle):
    c = ResidualConfig(**bundle["config"]).validate()
    if (
        bundle.get("abi") != ABI
        or bundle.get("ratios") != list(RATIOS)
        or bundle.get("feature_names") != list(FEATURES)
        or bundle.get("lags_ms") != list(LAGS_MS)
    ):
        raise ValueError("JevBWE model/action/history ABI mismatch; retraining required")
    for key in ("mean", "scale"):
        a = np.asarray(bundle[key], dtype=float)
        if a.shape != (STATE_DIM,) or not np.isfinite(a).all() or (key == "scale" and np.any(a <= 0)):
            raise ValueError("invalid JevBWE normalization")
    if len(bundle["risk_weights"]) != 3:
        raise ValueError("three separate risk models required")
    for weights in [bundle["utility_weights"], *bundle["risk_weights"]]:
        if not isinstance(weights, list) or len(weights) != 4:
            raise ValueError("four JevBWE MLP arrays required")
        w, b, v, bias = [np.asarray(a, dtype=float) for a in weights]
        if (
            b.ndim != 1
            or not 1 <= len(b) <= 64
            or w.shape != (STATE_DIM + len(RATIOS), len(b))
            or v.shape != (len(b), 1)
            or bias.shape != (1,)
            or not all(np.isfinite(a).all() for a in (w, b, v, bias))
        ):
            raise ValueError("invalid JevBWE model weights")
    if (
        not number(bundle["support_limit"])
        or bundle["support_limit"] < 0
        or not number(bundle["reward_mean"])
        or not number(bundle["reward_scale"])
        or bundle["reward_scale"] <= 0
    ):
        raise ValueError("invalid JevBWE model scales/support")
    for key in ("calibration_rows", "calibration_episodes"):
        if len(bundle[key]) != len(RATIOS) or any(type(v) is not int or v < 0 for v in bundle[key]):
            raise ValueError("invalid JevBWE action calibration support")
    p = bundle["calibrator"]
    if not number(p["slope"]) or p["slope"] < 0 or not number(p["bias"]):
        raise ValueError("invalid monotonic JevBWE calibration")
    if type(bundle["action_value_passed"]) is not bool or bundle.get("training_roles") != [
        "train",
        "qualification",
        "risk",
        "calibration",
    ]:
        raise ValueError("JevBWE fitting-role/qualification metadata required")
    return c


class ResidualModel:
    def __init__(self, bundle):
        self.config = validate_bundle(bundle)
        self.bundle = bundle
        self.utility = MLP.from_dict(bundle["utility_weights"])
        self.risks = [MLP.from_dict(w) for w in bundle["risk_weights"]]
        self.calibrator = Calibrator(**bundle["calibrator"])

    def predict(self, state):
        state = np.asarray(state, dtype=float)
        if state.shape != (STATE_DIM,) or not np.isfinite(state).all():
            raise ValueError("finite causal JevBWE history required")
        z = (state - self.bundle["mean"]) / self.bundle["scale"]
        support = float(np.sqrt(np.mean(z * z)))
        x = np.column_stack([np.tile(np.clip(z, -12, 12), (len(RATIOS), 1)), np.eye(len(RATIOS))])
        utility = self.utility(x).ravel() * self.bundle["reward_scale"] + self.bundle["reward_mean"]
        members = np.asarray([sigmoid(net(x).ravel()) for net in self.risks])
        risk = self.calibrator.predict(members.mean(axis=0))
        return utility, risk, np.ptp(members, axis=0), support


class JevBWE:
    """NN ranks six residuals; causal hard constraints always run after the screen.

    acknowledge() must be called only after an owned command is successfully applied.
    Holding or failing a command must not reset the increase clock or claim NN credit.
    """

    def __init__(self, model=None, config=None, *, ungated=False):
        self.model = model
        self.config = (config or (model.config if model else ResidualConfig())).validate()
        if model is not None and asdict(self.config) != model.bundle["config"]:
            raise ValueError("JevBWE runtime config differs from frozen model")
        self.ungated = ungated
        self.history = CausalHistory(self.config)
        self.last_change_ms = None
        self.acknowledged_bps = None
        self.last_ack_ms = None
        self.hold_until_ms = 0.0
        self.rtt_floor = None

    def acknowledge(self, bitrate_bps, now_ms):
        if (
            not number(bitrate_bps)
            or bitrate_bps < 0
            or not number(now_ms)
            or self.history.last_ms is None
            or now_ms < self.history.last_ms
            or (self.last_ack_ms is not None and now_ms < self.last_ack_ms)
        ):
            raise ValueError("invalid JevBWE owned acknowledgment")
        self.last_ack_ms = now_ms
        if self.acknowledged_bps is None or abs(bitrate_bps - self.acknowledged_bps) > 1:
            self.last_change_ms = now_ms
            self.acknowledged_bps = bitrate_bps

    def observe(self, sample, *, safe_bps=None):
        c, now = self.config, sample.sample_ms
        if self.last_ack_ms is not None and (not number(now) or now < self.last_ack_ms):
            raise ValueError("JevBWE sample predates an owned acknowledgment")
        if safe_bps is not None and (not number(safe_bps) or safe_bps < 0):
            raise ValueError("finite nonnegative externally supplied safety ceiling required")
        state, reset = self.history.observe(sample)
        if self.last_change_ms is None or reset:
            self.last_change_ms = now
            self.acknowledged_bps = sample.requested_bps if number(sample.requested_bps) else c.min_bps
            self.rtt_floor = None
        valid = sample.telemetry_valid() and sample.feedback_age_ms <= c.max_feedback_age_ms
        base = sample.bwe_bps if valid else c.min_bps
        ceiling = min(c.max_bps, RATIOS[-1] * base) if safe_bps is None else min(safe_bps, c.max_bps)
        current = (
            sample.requested_bps if number(sample.requested_bps) and sample.requested_bps >= 0 else c.min_bps
        )
        candidates = [clipped_rate(r, base, ceiling, c) for r in RATIOS]
        utility = risk = spread = None
        support = None
        proposal = 4
        accepted = False
        eligible = [False] * len(RATIOS)
        reason = "bwe_reference"
        desired = clipped_rate(1, base, ceiling, c)
        if not valid:
            desired = min(current, c.min_bps, ceiling)
            reason = "invalid_or_stale_telemetry"
        elif self.model is not None:
            utility, risk, spread, support = self.model.predict(state)
            b = self.model.bundle
            if self.ungated:
                eligible = [True] * len(RATIOS)
            elif not b["action_value_passed"]:
                reason = "unqualified_action_value"
            elif support > b["support_limit"]:
                reason = "unsupported_history"
            else:
                eligible = [
                    bool(
                        risk[i] <= c.risk_limit
                        and spread[i] <= c.disagreement_limit
                        and b["calibration_rows"][i] >= c.min_calibration_rows
                        and b["calibration_episodes"][i] >= c.min_calibration_episodes
                    )
                    for i in range(len(RATIOS))
                ]
                reason = "risk_or_calibration_support"
            if any(eligible):
                proposal = max((i for i, ok in enumerate(eligible) if ok), key=lambda i: (utility[i], -i))
                desired = candidates[proposal]
                accepted = True
                reason = "ungated_ablation" if self.ungated else "learned_residual"
            elif b["action_value_passed"]:
                desired = clipped_rate(c.fallback_ratio, base, ceiling, c)
        emergency = not valid
        if valid:
            self.rtt_floor = sample.rtt_ms if self.rtt_floor is None else min(self.rtt_floor, sample.rtt_ms)
            emergency = (
                sample.loss >= 0.1
                or sample.rtt_ms - self.rtt_floor >= 70
                or (sample.rtt_delta_ms is not None and sample.rtt_delta_ms >= 30)
                or (sample.queue_trend_ms is not None and sample.queue_trend_ms >= 15)
            )
        if emergency:
            self.hold_until_ms = max(self.hold_until_ms, now + c.up_dwell_ms)
            desired = min(desired, clipped_rate(0.7, current, ceiling, c))
        final = min(desired, ceiling)  # decreases and falling ceilings never wait
        if final > current + 1 and (now - self.last_change_ms < c.up_dwell_ms or now < self.hold_until_ms):
            final = min(current, ceiling)
            reason = "upward_dwell"
        elif emergency and valid:
            reason = "congestion_decrease"
        elif final < desired:
            reason = "safety_ceiling"
        # Aliases/clipping, fallback, holds and safety reductions are not NN action execution.
        different_from_bwe = abs(final - clipped_rate(1, base, ceiling, c)) > 1
        unaliased = sum(abs(rate - candidates[proposal]) <= 1 for rate in candidates) == 1
        learned_executed = (
            accepted
            and not emergency
            and unaliased
            and abs(final - candidates[proposal]) <= 1
            and different_from_bwe
        )
        return dict(
            abi=ABI,
            history=state.tolist(),
            history_reset=reset,
            base_bps=float(base),
            safe_bps=float(ceiling),
            requested_bps=float(final),
            proposal_index=proposal,
            proposal_ratio=RATIOS[proposal],
            effective_ratio=float(final / base),
            learned_executed=bool(learned_executed),
            fallback=not accepted and self.model is not None,
            reason=reason,
            eligible=eligible,
            utility=None if utility is None else utility.tolist(),
            predicted_unsafe=None if risk is None else risk.tolist(),
            disagreement=None if spread is None else spread.tolist(),
            support_score=support,
        )
