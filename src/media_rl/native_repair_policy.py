"""V2 causal temporal policy, BWE envelope and selected-action risk screen.

No hidden relay state, pixels, phase, future labels or absolute time are model inputs.
Feedback is an application ACK transported over the same impaired WebRTC connection.
"""

import numpy as np

from .native_observations import CAPS, FEATURE_NAMES
from .native_protocol import finite, require
from .networks import MLP, sigmoid

REPAIR_ABI = "native_temporal_repair_v2"
HISTORY_STEPS = 32
STEP_DIM = 20
INPUT_DIM = HISTORY_STEPS * STEP_DIM
CONFIG = dict(
    history_steps=32,
    max_history_ms=4000,
    reset_gap_ms=1000,
    feedback_fresh_ms=500,
    startup_ms=500,
    up_dwell_ms=500,
    emergency_hold_ms=2000,
    bwe_headroom=0.95,
    fallback_headroom=0.85,
    miss_budget=0.1,
    disagreement_budget=0.15,
    packet_delay_alarm_ms=15,
    feedback_delay_alarm_ms=130,
    rtt_rise_alarm_ms=30,
    min_calibration_episodes=3,
    min_calibration_requests=60,
)
FEATURES = [
    *FEATURE_NAMES,
    "feedback_roundtrip_ms",
    "feedback_observed_age_ms",
    "feedback_valid",
    "feedback_presented_fps",
]


def validate_repair_bundle(bundle):
    require(
        bundle.get("model_abi") == REPAIR_ABI
        and bundle.get("config") == CONFIG
        and bundle.get("feature_names") == FEATURES,
        "repair model/config/feature ABI mismatch",
    )
    require(bundle.get("training_roles") == ["train", "calibration"], "repair fitting roles required")
    require(
        len(bundle.get("q_ensemble", [])) == 3 and bundle["q_ensemble"][0] == bundle["q_weights"],
        "three-seed actor ensemble required",
    )
    for weights, inputs, outputs in [
        *[(w, INPUT_DIM, 7) for w in bundle["q_ensemble"]],
        *[(w, INPUT_DIM + 7, 1) for w in bundle["risk_weights"]],
    ]:
        require(isinstance(weights, list) and len(weights) == 4, "four repair MLP arrays required")
        arrays = [np.asarray(p, dtype=float) for p in weights]
        w, b, v, c = arrays
        require(
            b.ndim == 1
            and 1 <= len(b) <= 64
            and w.shape == (inputs, len(b))
            and v.shape == (len(b), outputs)
            and c.shape == (outputs,)
            and all(np.isfinite(a).all() for a in arrays),
            "repair weights/dimensions invalid",
        )
    require(len(bundle["risk_weights"]) == 3, "three repair risk members required")
    require(len(bundle["platt"]) == 2 and all(finite(p) for p in bundle["platt"]), "repair Platt invalid")
    for key in ("risk_margin", "calibration_episodes", "calibration_requests"):
        require(
            len(bundle[key]) == 7 and all(finite(x) and x >= 0 for x in bundle[key]), "repair support missing"
        )
    require(all(x <= 1 for x in bundle["risk_margin"]), "invalid repair margin")
    return bundle


def feedback_features(feedback, now):
    if feedback is None:
        return [0.0, 1.0, 0.0, 0.0]
    require(
        set(feedback) == {"source_id", "capture_request_ms", "received_ms", "presented_fps"},
        "exact feedback schema required",
    )
    require(
        type(feedback["source_id"]) is int
        and feedback["source_id"] > 0
        and all(
            finite(feedback[k]) and feedback[k] >= 0
            for k in ("capture_request_ms", "received_ms", "presented_fps")
        )
        and feedback["capture_request_ms"] <= feedback["received_ms"] <= now,
        "future/invalid receiver feedback",
    )
    age = now - feedback["received_ms"]
    return [
        min(20.0, (feedback["received_ms"] - feedback["capture_request_ms"]) / 150),
        min(20.0, age / 500),
        float(age <= CONFIG["feedback_fresh_ms"]),
        min(2.0, feedback["presented_fps"] / 30),
    ]


class RepairPolicy:
    def __init__(self, bundle=None):
        self.bundle = validate_repair_bundle(bundle) if bundle is not None else None
        self.q = [MLP.from_dict(w) for w in bundle["q_ensemble"]] if bundle is not None else []
        self.risks = [MLP.from_dict(w) for w in bundle["risk_weights"]] if bundle is not None else []
        self.history = []
        self.started = None
        self.last_sample = None
        self.last_change = None
        self.hold_until = 0.0
        self.rtt_floor = None

    def acknowledge(self, cap, now):
        require(
            cap in CAPS and finite(now) and self.last_sample is not None and now >= self.last_sample,
            "invalid repair acknowledgment",
        )
        self.last_change = now

    def observe(self, observation, feedback=None):
        now, f = observation["sample_ms"], observation["features"]
        require(
            finite(now) and now >= 0 and len(f) == 16 and all(finite(x) and x >= 0 for x in f),
            "causal sender features required",
        )
        require(self.last_sample is None or now >= self.last_sample, "repair clock moved backwards")
        gap = self.last_sample is not None and now - self.last_sample > CONFIG["reset_gap_ms"]
        if gap:
            self.history = []
            self.started = None
            self.rtt_floor = None
        if self.started is None:
            self.started = now
            self.last_change = now
        ff = feedback_features(feedback, now)
        self.history.append((now, [*f, *ff]))
        self.history = [(t, x) for t, x in self.history if now - t <= CONFIG["max_history_ms"]][
            -HISTORY_STEPS:
        ]
        state = np.asarray(
            [0.0] * ((HISTORY_STEPS - len(self.history)) * STEP_DIM) + [v for _, x in self.history for v in x]
        )
        self.last_sample = now
        q = np.zeros(7)
        risk, spread = np.ones(7), np.ones(7)
        upper = np.ones(7)
        if self.bundle is not None:
            q = np.asarray([net(state) for net in self.q]).mean(axis=0)
            inputs = np.column_stack([np.tile(state, (7, 1)), np.eye(7)])
            members = np.asarray([sigmoid(net(inputs).ravel()) for net in self.risks])
            raw = np.clip(members.mean(axis=0), 1e-6, 1 - 1e-6)
            risk = sigmoid(self.bundle["platt"][0] * np.log(raw / (1 - raw)) + self.bundle["platt"][1])
            spread = np.ptp(members, axis=0)
            upper = np.minimum(1, risk + self.bundle["risk_margin"])
        own = f[7] * 4000000
        require(any(abs(own - c) < 0.01 for c in CAPS), "supported actual repair cap required")
        current = min(range(7), key=lambda i: abs(CAPS[i] - own))
        bwe = f[0] * 4000000 if f[9] == 1 else None
        if f[10] == 1:
            rtt = f[1] * 150
            self.rtt_floor = rtt if self.rtt_floor is None else min(self.rtt_floor, rtt)
        rtt_alarm = (
            f[10] == 1
            and self.rtt_floor is not None
            and f[1] * 150 - self.rtt_floor >= CONFIG["rtt_rise_alarm_ms"]
        )
        emergency = (
            (f[14] == 1 and f[6] * 150 >= CONFIG["packet_delay_alarm_ms"])
            or (ff[2] == 1 and ff[0] * 150 >= CONFIG["feedback_delay_alarm_ms"])
            or rtt_alarm
            or (now - self.started >= CONFIG["startup_ms"] and ff[2] == 0)
        )
        if emergency:
            self.hold_until = max(self.hold_until, now + CONFIG["emergency_hold_ms"])
        baseline_budget = CONFIG["fallback_headroom"] * bwe if bwe is not None else CAPS[0]
        fallback_index = max([i for i, c in enumerate(CAPS) if c <= baseline_budget + 0.001], default=0)
        budget = CONFIG["bwe_headroom"] * bwe if bwe is not None else CAPS[0]
        eligible = np.zeros(7, dtype=bool)
        if self.bundle is not None and ff[2] == 1 and now - self.started >= CONFIG["startup_ms"]:
            eligible = (
                (np.asarray(CAPS) <= budget + 0.001)
                & (upper <= CONFIG["miss_budget"])
                & (spread <= CONFIG["disagreement_budget"])
                & (np.asarray(self.bundle["calibration_episodes"]) >= CONFIG["min_calibration_episodes"])
                & (np.asarray(self.bundle["calibration_requests"]) >= CONFIG["min_calibration_requests"])
            )
        best = max([i for i in range(7) if eligible[i]], key=lambda i: (q[i], -i), default=-1)
        fallback = best < 0
        selected = fallback_index if fallback else best
        reason = "risk_or_support" if fallback else "learned"
        if now - self.started < CONFIG["startup_ms"]:
            selected = min(selected, 1)
            reason = "startup"
        if now < self.hold_until:
            selected = min(selected, max(0, current - 1)) if emergency else min(selected, current)
            reason = "congestion_hold"
        if selected > current:
            selected = min(selected, current + 1)
            if now - self.last_change < CONFIG["up_dwell_ms"]:
                selected = current
                reason = "upward_dwell"
        # A falling BWE ceiling overrides an upward dwell immediately.
        maximum = max([i for i, c in enumerate(CAPS) if c <= budget + 0.001], default=0)
        selected = min(selected, maximum)
        return dict(
            history=state.tolist(),
            action_index=selected,
            encoder_max_bitrate_bps=CAPS[selected],
            receiver_jitter_buffer_target_ms=0,
            fallback=fallback,
            reason=reason,
            q_values=q.tolist(),
            predicted_frame_miss=risk.tolist(),
            risk_upper=upper.tolist(),
            risk_disagreement=spread.tolist(),
            eligible=eligible.tolist(),
            feedback_features=ff,
            hard_budget_bps=budget,
            history_reset=gap,
        )
