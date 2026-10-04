"""Double DQN, episode-bootstrap safety estimation, and held-out calibration."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .calibration import Calibrator, SafetyEnsemble, risk_features
from .config import split_seed
from .controllers import DeterministicController
from .environment import MediaEnvironment
from .n_step import NStepAccumulator
from .networks import MLP
from .policy_features import PolicyFeatures
from .scenarios import ID_SCENARIOS, simulation_trace


@dataclass
class ModelBundle:
    policy: MLP
    safety: SafetyEnsemble
    calibrator: Calibrator
    single_calibrator: Calibrator
    metadata: dict

    def save(self, path):
        data = dict(
            schema_version=1,
            policy=self.policy.to_dict(),
            safety=self.safety.to_dict(),
            calibrator=asdict(self.calibrator),
            single_calibrator=asdict(self.single_calibrator),
            metadata=self.metadata,
        )
        Path(path).write_text(json.dumps(data, sort_keys=True, allow_nan=False))

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if data["schema_version"] != 1:
            raise ValueError("unsupported checkpoint version")
        return cls(
            MLP.from_dict(data["policy"]),
            SafetyEnsemble.from_dict(data["safety"]),
            Calibrator(**data["calibrator"]),
            Calibrator(**data["single_calibrator"]),
            data["metadata"],
        )


def id_environment(config, seed, split, episode):
    schedule = config.safety_training_scenarios or ID_SCENARIOS
    name = schedule[episode % len(schedule)]
    trace_seed = split_seed(seed, split, episode)
    return MediaEnvironment(config.simulator, simulation_trace(config.simulator, name, trace_seed))


def policy_training_scenario(config, episode):
    schedule = config.policy_training_scenarios or ID_SCENARIOS
    return schedule[episode % len(schedule)]


def policy_training_environment(config, seed, episode, split="train"):
    name = policy_training_scenario(config, episode)
    trace_seed = split_seed(seed, split, episode)
    return MediaEnvironment(config.simulator, simulation_trace(config.simulator, name, trace_seed))


def collect_demonstrations(config, seed):
    """Conventional actions only; never use preview, rewards or hidden trace fields as labels."""
    xs, labels = [], []
    for episode in range(config.training.demonstration_episodes):
        env = policy_training_environment(config, seed, episode, "demonstration")
        expert = DeterministicController(
            env.actions,
            config.training.demonstration_methods[episode % len(config.training.demonstration_methods)],
            config.simulator.dt_s,
        )
        encoder = PolicyFeatures(config.training.policy_features, config.simulator.dt_s)
        obs = env.reset()
        for _ in range(config.simulator.steps):
            xs.append(encoder.encode(obs))
            action = expert.act(obs).action
            labels.append(action)
            obs, _, _, _ = env.step(action)
    return np.asarray(xs), np.asarray(labels, dtype=int)


def train_policy(config, seed):
    t = config.training
    rng = np.random.default_rng(split_seed(seed, "train"))
    env = policy_training_environment(config, seed, 0)
    dimension = PolicyFeatures(t.policy_features, config.simulator.dt_s).dimension
    policy = MLP(dimension, t.hidden, len(env.actions), rng)
    target = MLP(dimension, t.hidden, len(env.actions), rng)
    demo_x, demo_a = collect_demonstrations(config, seed)
    demo_rng = np.random.default_rng(split_seed(seed, "demonstration"))
    for _ in range(t.demonstration_epochs):
        order = demo_rng.permutation(len(demo_a))
        for start in range(0, len(order), t.batch_size):
            ids = order[start : start + t.batch_size]
            scores = policy(demo_x[ids])
            probabilities = np.exp(scores - scores.max(axis=1, keepdims=True))
            probabilities /= probabilities.sum(axis=1, keepdims=True)
            probabilities[np.arange(len(ids)), demo_a[ids]] -= 1
            policy.train(demo_x[ids], probabilities / len(ids), t.learning_rate)
    target.copy_from(policy)
    states = np.zeros((t.replay_size, dimension))
    next_states = np.zeros_like(states)
    actions = np.zeros(t.replay_size, dtype=int)
    rewards, dones = np.zeros(t.replay_size), np.zeros(t.replay_size)
    discounts = np.full(t.replay_size, t.gamma)
    count, updates = 0, 0
    logs = []
    for episode in range(t.episodes):
        env = policy_training_environment(config, seed, episode)
        obs, episode_reward, losses = env.reset(), 0.0, []
        encoder = PolicyFeatures(t.policy_features, config.simulator.dt_s)
        x = encoder.encode(obs)
        accumulator = NStepAccumulator(t.n_step, t.gamma) if t.n_step > 1 else None
        epsilon = t.epsilon_start + (t.epsilon_end - t.epsilon_start) * min(
            1, episode / max(1, 0.8 * (t.episodes - 1))
        )
        for _ in range(config.simulator.steps):
            a = int(rng.integers(len(env.actions))) if rng.random() < epsilon else int(np.argmax(policy(x)))
            new_obs, reward, done, _ = env.step(a)
            new_x = encoder.encode(new_obs)
            if accumulator is None:
                # Keep the historical one-step arithmetic/RNG/update order exact.
                samples = [(x, a, reward, new_x, done, t.gamma)]
            else:
                samples = [
                    (s.state, s.action, s.reward, s.next_state, s.done, s.discount)
                    for s in accumulator.push(x, a, reward, new_x, done)
                ]
            for state, action, total_reward, after, terminal, discount in samples:
                idx = count % t.replay_size
                states[idx], actions[idx], rewards[idx] = state, action, total_reward
                next_states[idx], dones[idx], discounts[idx] = after, terminal, discount
                count += 1
                if count >= max(t.warmup, t.batch_size) and count % t.update_every == 0:
                    ids = rng.choice(min(count, t.replay_size), t.batch_size, replace=False)
                    next_a = policy(next_states[ids]).argmax(axis=1)
                    td_target = (
                        rewards[ids]
                        + discounts[ids]
                        * (1 - dones[ids])
                        * target(next_states[ids])[np.arange(len(ids)), next_a]
                    )
                    predicted = policy(states[ids])
                    error = predicted[np.arange(len(ids)), actions[ids]] - td_target
                    grad = np.zeros_like(predicted)
                    grad[np.arange(len(ids)), actions[ids]] = np.clip(error, -1, 1) / len(ids)
                    policy.train(states[ids], grad, t.learning_rate)
                    if t.demonstration_weight > 0:
                        dids = demo_rng.integers(len(demo_a), size=t.batch_size)
                        scores = policy(demo_x[dids])
                        adjusted = scores + t.demonstration_margin
                        adjusted[np.arange(len(dids)), demo_a[dids]] -= t.demonstration_margin
                        alternative = adjusted.argmax(axis=1)
                        active = alternative != demo_a[dids]
                        dgrad = np.zeros_like(scores)
                        dgrad[np.arange(len(dids))[active], alternative[active]] += (
                            t.demonstration_weight / len(dids)
                        )
                        dgrad[np.arange(len(dids))[active], demo_a[dids][active]] -= (
                            t.demonstration_weight / len(dids)
                        )
                        policy.train(demo_x[dids], dgrad, t.learning_rate)
                    losses.append(float(np.mean(np.where(abs(error) < 1, 0.5 * error**2, abs(error) - 0.5))))
                    updates += 1
                    if updates % t.target_every == 0:
                        target.copy_from(policy)
            obs, x = new_obs, new_x
            episode_reward += reward
        logs.append(
            dict(
                episode=episode,
                scenario=env.trace.name,
                epsilon=epsilon,
                mean_qoe=episode_reward / config.simulator.steps,
                td_loss=float(np.mean(losses)) if losses else None,
                updates=updates,
            )
        )
    return policy, logs


def collect_safety(config, seed, policy, split, episodes, augment=False):
    """Label proposals on a predeclared mix of RL, safe and GCC state distributions."""
    rng = np.random.default_rng(split_seed(seed, split))
    xs, ys, ids = [], [], []
    for episode in range(episodes):
        env = id_environment(config, seed, split, episode)
        obs = env.reset()
        encoder = PolicyFeatures(config.training.policy_features, config.simulator.dt_s)
        baseline = DeterministicController(
            env.actions, "safe" if episode % 3 == 1 else "gcc", config.simulator.dt_s
        )
        for _ in range(config.simulator.steps):
            proposal = int(np.argmax(policy(encoder.encode(obs))))
            a = proposal if episode % 3 == 0 else baseline.act(obs).action
            if augment and rng.random() < 0.15:
                a = int(rng.integers(len(env.actions)))
            candidates = [proposal] + ([a] if augment and a != proposal else [])
            for candidate in candidates:
                outcome = env.safety_preview(candidate, config.training.safety_horizon_steps)
                if not outcome.get("label_censored", False):
                    xs.append(risk_features(obs, env.actions[candidate]))
                    ys.append(outcome["safe"])
                    ids.append(episode)
            obs, _, _, _ = env.step(a)
    return np.asarray(xs), np.asarray(ys), np.asarray(ids)


def train_bundle(config, seed):
    policy, logs = train_policy(config, seed)
    x, y, ids = collect_safety(config, seed, policy, "risk", config.training.risk_episodes, augment=True)
    safety = SafetyEnsemble.fit(
        x, y, ids, config.training, config.gate, np.random.default_rng(split_seed(seed, "risk"))
    )
    cx, cy, cids = collect_safety(config, seed, policy, "calibration", config.training.calibration_episodes)
    raw, _ = safety.predict(cx)
    single_raw, _ = safety.predict(cx, single=True)
    calibrator = Calibrator.fit(raw, cy, config.gate.calibration)
    single_calibrator = Calibrator.fit(single_raw, cy, config.gate.calibration)
    metadata = dict(
        seed=seed,
        config=config.to_dict(),
        config_sha256=config.digest(),
        risk_samples=len(y),
        risk_positive_rate=float(y.mean()),
        calibration_samples=len(cy),
        calibration_positive_rate=float(cy.mean()),
        split_trace_seeds={
            split: [split_seed(seed, split, e) for e in range(n)]
            for split, n in [
                ("train", config.training.episodes),
                ("risk", config.training.risk_episodes),
                ("calibration", config.training.calibration_episodes),
            ]
        },
        demonstration_samples=config.training.demonstration_episodes * config.simulator.steps,
        simulation_backend=config.simulator.backend,
        policy_return_steps=config.training.n_step,
        safety_label="new capture cohort under fixed action until actual deadline"
        if config.training.safety_horizon_steps > 1
        else "next control-interval settled media cohorts"
        if config.simulator.backend == "packet_v2"
        else "next interval fluid safety",
        training_log=logs,
    )
    if config.training.demonstration_episodes:
        metadata["split_trace_seeds"]["demonstration"] = [
            split_seed(seed, "demonstration", e) for e in range(config.training.demonstration_episodes)
        ]
    calibration_rows = [
        dict(episode=int(e), label=int(label), raw=float(p), calibrated=float(q), single_raw=float(sp))
        for e, label, p, q, sp in zip(cids, cy, raw, calibrator.predict(raw), single_raw)
    ]
    return ModelBundle(policy, safety, calibrator, single_calibrator, metadata), calibration_rows
