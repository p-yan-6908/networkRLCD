"""Telemetry-only controllers and confidence-gated deterministic fallback."""

from dataclasses import dataclass

import numpy as np

from .calibration import risk_features

METHODS = {
    "safe",
    "heuristic",
    "gcc",
    "rl",
    "calibrated",
    "uncalibrated",
    "no_ood",
    "no_hysteresis",
    "single_model",
    "calibrated_v1",
    "id_refit",
    "stress_safe",
    "calibrated_090",
    "shielded",
    "shielded_uncertainty",
    "shielded_budget",
    "budget_only",
}
REFERENCE_METHODS = {"calibrated_v1", "id_refit", "stress_safe"}
CALIBRATED_ALIASES = REFERENCE_METHODS | {"calibrated_090"}


@dataclass(frozen=True)
class Decision:
    action: int
    proposal: int
    confidence: float | None = None
    raw_confidence: float | None = None
    uncertainty: float | None = None
    support_score: float | None = None
    fallback: bool = False
    reason: str = "baseline"
    action_confidence: float | None = None
    action_uncertainty: float | None = None
    action_budget_mbps: float | None = None
    budget_rejections: int = 0
    budget_intervention: bool = False


def choose_action(actions, budget, fec, low_latency):
    f = min({a.fec for a in actions}, key=lambda f: abs(f - fec))
    eligible = [
        i
        for i, a in enumerate(actions)
        if a.fec == f and a.low_latency == low_latency and a.wire_mbps <= budget
    ]
    if not eligible:
        return min(range(len(actions)), key=lambda i: (actions[i].wire_mbps, not actions[i].low_latency))
    return max(eligible, key=lambda i: actions[i].bitrate_mbps)


class DeterministicController:
    def __init__(self, actions, kind="safe", dt_s=0.1):
        self.actions, self.kind, self.dt_s = actions, kind, dt_s
        self.budget = 0.6
        self.min_rtt = float("inf")

    def act(self, obs):
        if not obs.finite() or not obs.valid or obs.feedback_age_s > 0.5:
            self.budget = max(self.actions[0].wire_mbps, self.budget * 0.5)
            a = choose_action(self.actions, self.budget, 0, True)
            return Decision(a, a, reason="missing_feedback")
        self.min_rtt = min(self.min_rtt, obs.rtt_ms)
        queue = max(0, obs.rtt_ms - self.min_rtt)
        if self.kind == "safe":
            bad = queue > 35 or obs.loss > 0.06 or obs.delay_trend_ms > 15
            if bad:
                self.budget = max(0.15, min(self.budget * 0.7, obs.throughput_mbps * 0.8))
            else:
                # Persist a probing budget across ladder rungs. Capping it by
                # application-limited ACK throughput would lock the lowest rung.
                self.budget += 0.5 * self.dt_s
            fec = 0.1 if obs.loss > 0.015 and queue < 35 else 0.0
            low_latency = True
        elif self.kind == "gcc":
            # Delay overuse + loss response + AIMD; NOT libwebrtc GCC.
            if obs.delay_trend_ms > 12 or queue > 70 or obs.loss > 0.1:
                self.budget = max(0.15, min(self.budget * 0.85, obs.throughput_mbps * 0.9))
            elif obs.loss < 0.02 and queue < 40:
                self.budget += max(0.08, 0.05 * self.budget) * self.dt_s / 0.1
            fec = 0.1 if 0.01 < obs.loss < 0.1 and queue < 40 else 0
            low_latency = queue > 40
        else:
            self.budget = max(
                0.15,
                0.85 * obs.throughput_mbps
                if queue > 50
                else max(self.budget + 0.5 * self.dt_s, 1.3 * obs.throughput_mbps + 0.05),
            )
            fec = 0.25 if obs.loss > 0.08 else 0.1 if obs.loss > 0.02 else 0
            low_latency = obs.rtt_ms > 100
        self.budget = min(self.budget, max(a.wire_mbps for a in self.actions))
        a = choose_action(self.actions, self.budget, fec, low_latency)
        return Decision(a, a)


class ConfidenceGate:
    def __init__(self, config, hysteresis=True):
        self.config, self.hysteresis = config, hysteresis
        self.active, self.held = False, 0

    def select(self, confidence, hard_reason=None):
        c = self.config
        if not np.isfinite(confidence):
            hard_reason = "invalid_confidence"
        reason = hard_reason or ("low_confidence" if confidence < c.threshold else None)
        if reason:
            if not self.active:
                self.held = 0
            self.active = True
        elif self.active:
            if not self.hysteresis or (
                self.held >= c.hold_steps and confidence >= c.threshold + c.release_margin
            ):
                self.active, self.held = False, 0
            else:
                reason = "hysteresis"
        if self.active:
            self.held += 1
        return self.active, reason or "accepted"


class RLController:
    def __init__(self, bundle, actions, gate_config, method="calibrated", dt_s=0.1):
        self.bundle, self.actions, self.method, self.config = bundle, actions, method, gate_config
        self.safe = DeterministicController(
            actions, getattr(bundle, "metadata", {}).get("fallback_kind", "safe"), dt_s
        )
        self.gate = ConfidenceGate(gate_config, hysteresis=method != "no_hysteresis")

    def _shielded_action(self, obs, safe, proposal, q_values):
        # act() updates the shadow fallback exactly once, using telemetry only.
        budget = self.safe.budget if self.method in {"shielded_budget", "budget_only"} else None
        budget_fields = dict(action_budget_mbps=budget)
        if not obs.valid or obs.feedback_age_s > self.config.max_feedback_age_s:
            return Decision(safe, proposal, fallback=True, reason="missing_feedback", **budget_fields)

        candidates = np.argsort(q_values)[::-1][: min(self.config.shield_top_k, len(self.actions))]
        features = np.stack([risk_features(obs, self.actions[int(i)]) for i in candidates])
        support = float(np.asarray(self.bundle.safety.support_score(features[0])).reshape(-1)[0])
        if not np.isfinite(support) or support > self.bundle.safety.support_limit:
            return Decision(
                safe, proposal, support_score=support, fallback=True, reason="ood_support", **budget_fields
            )

        raw, uncertainty = self.bundle.safety.predict(features)
        raw = np.asarray(raw, dtype=float).reshape(-1)
        uncertainty = np.asarray(uncertainty, dtype=float).reshape(-1)
        confidence = np.asarray(self.bundle.calibrator.predict(raw), dtype=float).reshape(-1)
        if any(values.shape != candidates.shape for values in (raw, uncertainty, confidence)):
            return Decision(
                safe,
                proposal,
                support_score=support,
                fallback=True,
                reason="invalid_safety_prediction",
                **budget_fields,
            )
        confidence = np.where(np.isfinite(confidence), confidence, 0.0)
        raw = np.where(np.isfinite(raw), raw, 0.0)
        uncertainty = np.where(np.isfinite(uncertainty), uncertainty, 1.0)

        confident = np.flatnonzero(confidence >= self.config.threshold)
        learned_mask = confidence >= self.config.threshold
        if self.method in {"shielded_uncertainty", "shielded_budget"}:
            learned_mask &= uncertainty <= self.config.max_ensemble_std
        if self.method == "budget_only":
            # Matched ablation: keep ranking, feedback/support guards and score
            # diagnostics, but remove probability/disagreement eligibility.
            learned_mask = np.ones(len(candidates), dtype=bool)
        learned = np.flatnonzero(learned_mask)
        eligible_mask = learned_mask.copy()
        if budget is not None:
            within_budget = np.array([self.actions[int(i)].wire_mbps <= budget for i in candidates])
            budget_fields.update(
                budget_rejections=int(np.count_nonzero(~within_budget)),
                budget_intervention=bool(len(learned) and not within_budget[learned[0]]),
            )
            eligible_mask &= within_budget
        eligible = np.flatnonzero(eligible_mask)
        primary_confidence, primary_raw, primary_uncertainty = map(
            float, (confidence[0], raw[0], uncertainty[0])
        )
        if not len(eligible):
            rejected = int(learned[0]) if len(learned) else int(confident[0]) if len(confident) else None
            reason = (
                "budget_abstention"
                if len(learned)
                else "uncertainty_abstention"
                if len(confident)
                else "no_safe_candidate"
            )
            return Decision(
                safe,
                proposal,
                primary_confidence,
                primary_raw,
                primary_uncertainty,
                support,
                True,
                reason,
                float(confidence[rejected]) if rejected is not None else None,
                float(uncertainty[rejected]) if rejected is not None else None,
                **budget_fields,
            )
        selected_position = int(eligible[0])
        selected = int(candidates[selected_position])
        return Decision(
            selected,
            proposal,
            primary_confidence,
            primary_raw,
            primary_uncertainty,
            support,
            False,
            "shielded_action" if selected != proposal else "accepted",
            float(confidence[selected_position]),
            float(uncertainty[selected_position]),
            **budget_fields,
        )

    def act(self, obs):
        safe = self.safe.act(obs).action
        if not obs.finite():
            self.gate.select(float("nan"), "invalid_telemetry")
            return Decision(safe, safe, 0, 0, 0, None, True, "invalid_telemetry")
        q_values = np.asarray(self.bundle.policy(np.clip(obs.vector(), -12, 12)), dtype=float).reshape(-1)
        if q_values.shape != (len(self.actions),) or not np.all(np.isfinite(q_values)):
            return Decision(safe, safe, fallback=True, reason="invalid_policy_output")
        proposal = int(np.argmax(q_values))
        if self.method in {"shielded", "shielded_uncertainty", "shielded_budget", "budget_only"}:
            return self._shielded_action(obs, safe, proposal, q_values)
        x = risk_features(obs, self.actions[proposal])
        raw, std = self.bundle.safety.predict(x, single=self.method == "single_model")
        calibrator = (
            self.bundle.single_calibrator if self.method == "single_model" else self.bundle.calibrator
        )
        confidence = float(raw) if self.method == "uncalibrated" else float(calibrator.predict(raw))
        support = float(self.bundle.safety.support_score(x))
        hard = None
        if not obs.valid or obs.feedback_age_s > self.config.max_feedback_age_s:
            hard = "missing_feedback"
        elif self.method != "no_ood" and support > self.bundle.safety.support_limit:
            hard = "ood_support"
        fallback, reason = self.gate.select(confidence, hard)
        if self.method == "rl":
            # Exact same learned policy as the main method; no probability gate.
            fallback, reason = False, "ungated"
        return Decision(
            safe if fallback else proposal,
            proposal,
            confidence,
            float(raw),
            float(std),
            support,
            fallback,
            reason,
        )


def make_controller(method, bundle, actions, gate_config, dt_s, threshold=None):
    if method not in METHODS:
        raise ValueError(f"unknown method {method}")
    if method in {"safe", "heuristic", "gcc"}:
        return DeterministicController(actions, method, dt_s)
    if bundle is None:
        raise ValueError("RL methods require a trained model")
    effective_method = "calibrated" if method in CALIBRATED_ALIASES else method
    if threshold is not None:
        from dataclasses import replace

        gate_config = replace(
            gate_config, threshold=threshold, release_margin=min(gate_config.release_margin, 1 - threshold)
        )
    return RLController(bundle, actions, gate_config, effective_method, dt_s)
