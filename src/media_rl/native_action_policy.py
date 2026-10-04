"""Bounded factual state/action utility and risk; no unsupported-action bootstrap.

This is an independent candidate ABI, NOT a compatible V5 replacement. State
keeps actual scalar caps. A predictive interpolation never certifies support.
"""

from math import isfinite, log2

import numpy as np

from .native_observations import CAPS, FEATURE_LIMITS
from .native_protocol import require
from .native_repair3_policy import FEATURES, INPUT_DIM, feedback_features
from .native_repair5_policy import CONFIG as LEGACY_CONFIG
from .networks import sigmoid

MODEL_ABI = "native_factual_action_outcome_v1"
CANDIDATES = (150000, 300000, 400000, 450000, 500000, 600000, 1000000, 1600000, 2500000, 4000000)
CONTEXTS = ("unknown", "delayed", "ready")
CONFIG = dict(
    LEGACY_CONFIG,
    fallback="continuous85_bwe",
    risk_architecture="bounded_state_action_outcomes",
    calibration="exact_cap_causal_context_worst_crossfit_group",
    context_delay_ms=120,
    context_min_fps=24,
    action_features=["cap_fraction", "cap_bwe_ratio", "log_cap"],
)


def finite(x):
    return type(x) in (int, float) and isfinite(x)


def scalar_cap(x):
    require(
        type(x) in (int, float) and finite(x) and int(x) == x and 150000 <= x <= 4000000,
        "bounded integer actual scalar cap required",
    )
    return int(x)


def action_features(cap, state):
    cap = scalar_cap(cap)
    f = state[-23:]
    bwe = f[0] * 4e6 if f[9] == 1 else 150000
    return [cap / 4e6, min(10.0, cap / max(150000, bwe)) / 10, min(4.0, log2(cap / 150000)) / 4]


def causal_context(state):
    f = state[-23:]
    if f[18] != 1 or f[22] != 1:
        return "unknown"
    if f[16] * 150 >= CONFIG["context_delay_ms"] or f[19] * 30 < CONFIG["context_min_fps"]:
        return "delayed"
    return "ready"


class CausalState:
    def __init__(self):
        self.history = []
        self.last_sample = None
        self.started = None
        self.rtt_samples = []

    def observe(self, observation, feedback=None):
        now = observation["sample_ms"]
        f = list(observation["features"])
        content = list(observation["content_features"])
        require(
            finite(now) and now >= 0 and (self.last_sample is None or now >= self.last_sample),
            "causal scalar clock required",
        )
        require(
            len(f) == 16
            and all(finite(x) and 0 <= x <= bound for x, bound in zip(f, FEATURE_LIMITS))
            and all(f[i] in (0, 1) for i in range(8, 15)),
            "bounded sender features required",
        )
        scalar_cap(round(f[7] * 4e6))
        require(abs(f[7] * 4e6 - round(f[7] * 4e6)) < 0.01, "integer own cap required")
        require(
            len(content) == 3 and all(finite(x) and 0 <= x <= 2 for x in content) and content[2] in (0, 1),
            "causal content required",
        )
        reset = self.last_sample is not None and now - self.last_sample > CONFIG["reset_gap_ms"]
        if reset:
            self.history = []
            self.started = None
            self.rtt_samples = []
        if self.started is None:
            self.started = now
        if f[10] == 1 and f[1] <= 0:
            f[1], f[2], f[10], f[11] = 0, 0, 0, 0
        if f[10] == 1:
            self.rtt_samples.append((now, f[1] * 150))
        self.rtt_samples = [
            (t, r) for t, r in self.rtt_samples if now - t <= CONFIG["rtt_baseline_window_ms"]
        ]
        ff = feedback_features(feedback, now)
        self.history.append((now, [*f, *ff, *content]))
        self.history = [(t, x) for t, x in self.history if now - t <= CONFIG["max_history_ms"]][-32:]
        state = [0.0] * (INPUT_DIM - len(self.history) * 23) + [v for _, x in self.history for v in x]
        self.last_sample = now
        return dict(
            history=state,
            feedback_features=ff,
            features=f,
            history_reset=reset,
            context=causal_context(state),
            rtt_floor=min((r for _, r in self.rtt_samples), default=None),
        )


def validate_bundle(b):
    require(
        b.get("model_abi") == MODEL_ABI
        and b.get("config") == CONFIG
        and b.get("feature_names") == FEATURES
        and b.get("candidates") == list(CANDIDATES),
        "action outcome ABI/config mismatch",
    )
    require(
        b.get("training_roles") == ["train", "calibration"] and type(b.get("training_skill_passed")) is bool,
        "legal fitting roles/skill receipt required",
    )
    require(b.get("native_deployment_qualified") is False, "this candidate is not native-qualified")
    require(len(b.get("members", [])) == 3, "three bounded outcome members required")
    for weights in b["members"]:
        require(isinstance(weights, list) and len(weights) == 4, "four network arrays required")
        w, h, v, c = [np.asarray(a, dtype=float) for a in weights]
        require(
            h.ndim == 1
            and 1 <= len(h) <= 64
            and w.shape == (INPUT_DIM + 3, len(h))
            and v.shape == (len(h), 2)
            and c.shape == (2,)
            and all(np.isfinite(a).all() for a in (w, h, v, c)),
            "action network shape/weights invalid",
        )
    require(
        set(b.get("cells", {})) == {f"{cap}/{ctx}" for cap in CANDIDATES for ctx in CONTEXTS},
        "exact-cap/context calibration cells required",
    )
    for cell in b["cells"].values():
        require(
            len(cell.get("platt", [])) == 2
            and all(finite(x) for x in cell["platt"])
            and cell["platt"][0] >= 0,
            "monotonic cell mapping required",
        )
        require(finite(cell.get("margin")) and 0 <= cell["margin"] <= 1, "bounded cell margin required")
        require(
            all(type(cell.get(k)) is int and cell[k] >= 0 for k in ("groups", "episodes", "requests"))
            and type(cell.get("supported")) is bool,
            "cell support counts required",
        )
        enough = (
            cell["groups"] >= CONFIG["min_calibration_groups"]
            and cell["episodes"] >= CONFIG["min_calibration_episodes"]
            and cell["requests"] >= CONFIG["min_calibration_requests"]
        )
        require(
            cell["supported"] == enough and (enough or cell["margin"] == 1),
            "unsupported cells must be globally vetoed",
        )
    return b


def predict_members(b, state, caps=CANDIDATES):
    require(len(state) == INPUT_DIM and all(finite(x) for x in state), "finite temporal state required")
    acts = np.asarray([action_features(c, state) for c in caps])
    state = np.asarray(state)
    # Reuse the state projection for every candidate. No N*736 matrix products.
    values = []
    for weights in b["members"]:
        w, h, v, c = [np.asarray(x, dtype=float) for x in weights]
        hidden = np.maximum(state @ w[:INPUT_DIM] + acts @ w[INPUT_DIM:] + h, 0)
        values.append(sigmoid(hidden @ v + c))
    return np.asarray(values)


class ActionPolicy:
    def __init__(self, bundle=None):
        self.bundle = validate_bundle(bundle) if bundle is not None else None
        self.state = CausalState()
        self.last_change = None
        self.hold_until = 0.0

    def acknowledge(self, cap, now):
        scalar_cap(cap)
        require(
            finite(now)
            and self.state.last_sample is not None
            and now >= self.state.last_sample
            and (self.last_change is None or now >= self.last_change),
            "causal action acknowledgment required",
        )
        self.last_change = now

    def observe(self, observation, feedback=None):
        d = self.state.observe(observation, feedback)
        f = d["features"]
        now = observation["sample_ms"]
        state = d["history"]
        if self.last_change is None or d["history_reset"]:
            self.last_change = now
            self.hold_until = 0.0
        own = scalar_cap(round(f[7] * 4e6))
        bwe = f[0] * 4e6 if f[9] == 1 else None
        baseline = (
            scalar_cap(max(150000, min(4000000, int(CONFIG["fallback_headroom"] * bwe))))
            if bwe is not None
            else 150000
        )
        legacy = (
            max((c for c in CAPS if c <= CONFIG["fallback_headroom"] * bwe), default=150000)
            if bwe is not None
            else 150000
        )
        budget = CONFIG["bwe_headroom"] * bwe if bwe is not None else 150000
        emergency = (f[14] == 1 and f[6] * 150 >= CONFIG["packet_delay_alarm_ms"]) or (
            f[10] == 1
            and d["rtt_floor"] is not None
            and f[1] * 150 - d["rtt_floor"] >= CONFIG["rtt_rise_alarm_ms"]
        )
        if emergency:
            self.hold_until = max(self.hold_until, now + CONFIG["emergency_hold_ms"])
        utility = np.zeros(len(CANDIDATES))
        risk = np.ones(len(CANDIDATES))
        spread = np.ones(len(CANDIDATES))
        upper = np.ones(len(CANDIDATES))
        eligible = np.zeros(len(CANDIDATES), dtype=bool)
        ready = (
            d["feedback_features"][2] == 1
            and state[-1] == 1
            and now - self.state.started >= CONFIG["startup_ms"]
        )
        if self.bundle is not None:
            members = predict_members(self.bundle, state)
            utility = members[:, :, 0].mean(axis=0)
            raw = members[:, :, 1].mean(axis=0)
            spread = np.ptp(members[:, :, 1], axis=0)
            for i, cap in enumerate(CANDIDATES):
                cell = self.bundle["cells"][f"{cap}/{d['context']}"]
                p = float(np.clip(raw[i], 1e-6, 1 - 1e-6))
                risk[i] = float(sigmoid(cell["platt"][0] * np.log(p / (1 - p)) + cell["platt"][1]))
                upper[i] = min(1, risk[i] + cell["margin"])
                eligible[i] = (
                    ready
                    and self.bundle["training_skill_passed"]
                    and cell["supported"]
                    and cap <= budget + 0.001
                    and upper[i] <= CONFIG["miss_budget"]
                    and spread[i] <= CONFIG["disagreement_budget"]
                )
        best = max(
            (i for i in range(len(CANDIDATES)) if eligible[i]), key=lambda i: (utility[i], -i), default=-1
        )
        reason = "risk_or_support" if ready else "startup_or_feedback"
        if self.bundle is not None and not self.bundle["training_skill_passed"]:
            best = -1
            reason = "training_skill"
        if now < self.hold_until:
            best = -1
            reason = "sender_congestion"
        next_up = min((c for c in CANDIDATES if c > own), default=4000000)
        if (
            best >= 0
            and CANDIDATES[best] > own
            and (CANDIDATES[best] > next_up or now - self.last_change < CONFIG["up_dwell_ms"])
        ):
            best = -1
            reason = "upward_guard"
        cap = baseline if best < 0 else CANDIDATES[best]
        if best >= 0:
            reason = "learned"
        return dict(
            **d,
            encoder_max_bitrate_bps=cap,
            receiver_jitter_buffer_target_ms=0,
            fallback=best < 0,
            reason=reason,
            expected_utility=utility.tolist(),
            predicted_frame_miss=risk.tolist(),
            risk_upper=upper.tolist(),
            risk_disagreement=spread.tolist(),
            eligible=eligible.tolist(),
            hard_budget_bps=budget,
            continuous_bwe_cap_bps=baseline,
            legacy_bwe_cap_bps=legacy,
            learned_departure=best >= 0 and cap not in (legacy, 4000000),
            departure_from_continuous_bwe=best >= 0 and cap != baseline,
            scalar_cap_saturation=baseline == 150000 and bwe is not None and 0.85 * bwe < 150000,
            native_deployment_qualified=False,
        )
