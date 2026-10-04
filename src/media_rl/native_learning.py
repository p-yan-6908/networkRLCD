"""Fresh native CQL/Double-DQN actor and factual calibrated frame-risk ensemble.

Offline losses/choices are not policy performance or a safety certificate.
"""

import math

import numpy as np

from media_rl.native_dataset import n_step_arrays
from media_rl.native_observations import CAPS, FEATURE_NAMES, NATIVE_OBSERVATION_ABI
from media_rl.networks import MLP, sigmoid

MODEL_ABI = "native_rlcd_cql_v1"


def fit_native_platt(probability, target, weight):
    p = np.clip(probability, 1e-6, 1 - 1e-6)
    x = np.column_stack([np.log(p / (1 - p)), np.ones(len(p))])
    theta = np.array([1.0, 0.0])
    weights = np.asarray(weight, dtype=float)
    weights /= weights.sum()
    for _ in range(80):
        pred = sigmoid(x @ theta)
        gradient = x.T @ (weights * (pred - target)) + 1e-3 * np.array([theta[0] - 1, theta[1]])
        hessian = x.T @ ((weights * pred * (1 - pred))[:, None] * x) + np.eye(2) * 1e-3
        step = np.linalg.solve(hessian, gradient)
        theta -= np.clip(step, -1, 1)
        if np.linalg.norm(step) < 1e-7:
            break
    return theta.tolist()


def native_metadata():
    return dict(
        model_abi=MODEL_ABI,
        native_observation_abi=NATIVE_OBSERVATION_ABI,
        observation_dim=16,
        history_steps=4,
        input_dim=64,
        feature_names=list(FEATURE_NAMES),
        native_action_abi="native_encoder_cap_playout_v1",
        action_count=14,
        policy_output_count=7,
        native_action_indices=list(range(1, 14, 2)),
        caps=list(CAPS),
        receiver_target_ms=0,
        risk_event="factual source request exceeds 150ms pixel-readback deadline or remains unidentified",
        calibration_is_not_episode_safety_certificate=True,
        evaluation_status="unvalidated native candidate",
        SOTA_achieved=False,
    )


def validate_native_bundle(bundle):
    m = bundle.get("metadata", {})
    for key, value in native_metadata().items():
        if key not in ("evaluation_status",) and m.get(key) != value:
            raise ValueError("native model/observation/action ABI mismatch: " + key)
    for name, weights, inputs, outputs in [("q", bundle["q_weights"], 64, 7)] + [
        ("risk", w, 71, 1) for w in bundle["risk_weights"]
    ]:
        if len(weights) != 4:
            raise ValueError("four native MLP parameters required")
        w, b, v, c = [np.asarray(a, dtype=float) for a in weights]
        if (
            w.ndim != 2
            or w.shape[0] != inputs
            or b.shape != (w.shape[1],)
            or v.shape != (w.shape[1], outputs)
            or c.shape != (outputs,)
            or any(not np.isfinite(a).all() for a in [w, b, v, c])
        ):
            raise ValueError("native " + name + " parameter shape/value mismatch")
    if (
        len(bundle["risk_weights"]) != 3
        or len(bundle["platt"]) != 2
        or not all(type(v) in (int, float) and math.isfinite(v) for v in bundle["platt"])
    ):
        raise ValueError("three-member native risk ensemble/calibrator required")
    if any(
        type(bundle[k]) not in (int, float) or not 0 <= bundle[k] <= 1
        for k in ["risk_cutoff", "disagreement_cutoff"]
    ):
        raise ValueError("invalid native provisional screens")
    return True


class NativePolicy:
    def __init__(self, bundle):
        validate_native_bundle(bundle)
        self.bundle = bundle
        self.q = MLP.from_dict(bundle["q_weights"])
        self.risks = [MLP.from_dict(w) for w in bundle["risk_weights"]]

    def decide(self, history):
        state = np.asarray(history, dtype=float)
        if state.shape != (64,) or not np.isfinite(state).all() or np.any(state < 0):
            raise ValueError("native four-step sender history required")
        q = self.q(state[None, :])[0]
        inputs = np.column_stack([np.repeat(state[None, :], 7, axis=0), np.eye(7)])
        members = np.asarray([sigmoid(net(inputs).ravel()) for net in self.risks])
        raw = members.mean(axis=0)
        a, b = self.bundle["platt"]
        p = sigmoid(a * np.log(np.clip(raw, 1e-6, 1 - 1e-6) / (1 - np.clip(raw, 1e-6, 1 - 1e-6))) + b)
        spread = np.ptp(members, axis=0)
        eligible = (p <= self.bundle["risk_cutoff"]) & (spread <= self.bundle["disagreement_cutoff"])
        if eligible.any():
            action = int(np.argmax(np.where(eligible, q, -np.inf)))
            fallback = False
        else:
            recent = state[-16:]
            cap = recent[7] * 4000000
            if recent[9] == 1:
                cap = recent[0] * 4000000 * 0.85
            action = max((i for i, c in enumerate(CAPS) if c <= cap + 0.001), default=0)
            fallback = True
        return dict(
            action_index=action,
            native_action_index=2 * action + 1,
            encoder_max_bitrate_bps=CAPS[action],
            receiver_jitter_buffer_target_ms=0,
            fallback=fallback,
            q_values=q.tolist(),
            predicted_frame_miss=p.tolist(),
            risk_disagreement=spread.tolist(),
        )


def train_native_bundle(roles, panel, provenance):
    train, cal = roles["train"], roles["calibration"]
    config = panel["learner"]
    seed = config["model_seed"]
    rng = np.random.default_rng(seed)
    if not train or not cal:
        raise ValueError("disjoint native train/calibration data required")
    if set(t["episode_id"] for t in train) & set(t["episode_id"] for t in cal):
        raise ValueError("native calibration episode leakage")
    data = n_step_arrays(train, panel["reward"]["gamma"], panel["reward"]["n_step"])
    q = MLP(64, config["hidden"], 7, rng)
    target = MLP(64, config["hidden"], 7, rng)
    target.copy_from(q)
    losses = []
    for update in range(config["updates"]):
        indices = rng.integers(0, len(train), config["batch_size"])
        states = data["states"][indices]
        actions = data["actions"][indices]
        future = data["next_states"][indices]
        greedy = np.argmax(q(future), axis=1)
        expected = (
            data["returns"][indices]
            + data["bootstrap_discounts"][indices] * target(future)[np.arange(len(indices)), greedy]
        )
        values = q(states)
        difference = values[np.arange(len(indices)), actions] - expected
        gradient = np.zeros_like(values)
        gradient[np.arange(len(indices)), actions] = np.clip(difference, -1, 1)
        exp = np.exp(values - values.max(axis=1, keepdims=True))
        softmax = exp / exp.sum(axis=1, keepdims=True)
        conservative = softmax.copy()
        conservative[np.arange(len(indices)), actions] -= 1
        q.train(
            states, (gradient + config["cql_alpha"] * conservative) / len(indices), config["learning_rate"]
        )
        if (update + 1) % config["target_update_every"] == 0:
            target.copy_from(q)
        if update % 200 == 0:
            losses.append(float(np.mean(difference**2)))
    states = np.asarray([t["state"] for t in train])
    actions = np.asarray([t["action"] for t in train])
    risk_inputs = np.column_stack([states, np.eye(7)[actions]])
    outcomes = np.asarray([t["miss_fraction"] for t in train])
    weights = np.asarray([t["label_count"] for t in train])
    ids = sorted(set(t["episode_id"] for t in train))
    risks = []
    for member in range(3):
        r = np.random.default_rng(seed + 211 * (member + 1))
        net = MLP(71, 32, 1, r)
        sampled = r.choice(ids, len(ids), replace=True)
        pool = np.concatenate(
            [np.asarray([i for i, t in enumerate(train) if t["episode_id"] == id]) for id in sampled]
        )
        for _ in range(config["risk_updates"]):
            i = r.choice(pool, config["batch_size"], replace=True)
            pred = sigmoid(net(risk_inputs[i]).ravel())
            gradient = (pred - outcomes[i]) * weights[i] / weights[i].sum()
            net.train(risk_inputs[i], gradient[:, None], config["learning_rate"])
        risks.append(net)
    cx = np.column_stack([np.asarray([t["state"] for t in cal]), np.eye(7)[[t["action"] for t in cal]]])
    cy = np.asarray([t["miss_fraction"] for t in cal])
    cw = np.asarray([t["label_count"] for t in cal])
    raw = np.asarray([sigmoid(net(cx).ravel()) for net in risks]).mean(axis=0)
    platt = fit_native_platt(raw, cy, cw)
    pred = sigmoid(
        platt[0] * np.log(np.clip(raw, 1e-6, 1 - 1e-6) / (1 - np.clip(raw, 1e-6, 1 - 1e-6))) + platt[1]
    )
    bundle = dict(
        metadata=native_metadata(),
        q_weights=q.to_dict(),
        risk_weights=[r.to_dict() for r in risks],
        platt=platt,
        risk_cutoff=0.5,
        disagreement_cutoff=0.2,
        training=panel["learner"],
        reward_protocol=panel["reward"],
        provenance=provenance,
    )
    validate_native_bundle(bundle)
    report = dict(
        train_transitions=len(train),
        calibration_transitions=len(cal),
        train_source_requests=int(weights.sum()),
        calibration_source_requests=int(cw.sum()),
        train_episodes=len(ids),
        calibration_episodes=len(set(t["episode_id"] for t in cal)),
        bellman_mse_samples=losses,
        calibration_fraction_mse_raw=float(np.average((raw - cy) ** 2, weights=cw)),
        calibration_fraction_mse_platt=float(np.average((pred - cy) ** 2, weights=cw)),
        calibration_frame_brier_raw=float(np.average((raw - cy) ** 2 + cy * (1 - cy), weights=cw)),
        calibration_frame_brier_platt=float(np.average((pred - cy) ** 2 + cy * (1 - cy), weights=cw)),
        risk_episode_bootstrap=True,
        offline_metrics_are_not_controller_performance=True,
        provisional_screens_not_validation_selected=True,
        legacy_weights_loaded=False,
        test_used=False,
    )
    return bundle, report
