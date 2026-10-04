"""Role-disjoint, multi-seed long-history CQL fitting and episode-cluster risk margins."""

from collections import defaultdict
from pathlib import Path

import numpy as np

from .native_observations import CAPS
from .native_protocol import digest, read_json, require, write_json
from .native_repair5_policy import (
    CONFIG,
    FEATURES,
    INPUT_DIM,
    REPAIR_ABI,
    RepairPolicy,
    SenderContentEncoder,
    validate_repair_bundle,
)
from .native_repair5_study import LEARNER, audit_repair_study, video_overlap
from .networks import MLP, sigmoid


def reconstruct_causal_states(sender, frames):
    """Reinterpret legal training captures using only source frames born by each sample.

    Receiver observations, quality outcomes, phase and movie time never enter state.
    The same encoder/policy computes these features in the live V3 collector.
    """
    encoder, policy = SenderContentEncoder(), RepairPolicy()
    sources = frames["sources"]
    require(
        all(
            sources[i]["capture_request_ms"] < sources[i + 1]["capture_request_ms"]
            for i in range(len(sources) - 1)
        ),
        "source content ordering required",
    )
    cursor, states = 0, []
    for row in sender["decisions"]:
        obs = row["observation"]
        while cursor < len(sources) and sources[cursor]["capture_request_ms"] <= obs["sample_ms"]:
            source = sources[cursor]
            encoder.observe(source["reference_rgb"], source["capture_request_ms"])
            cursor += 1
        decision = policy.observe(
            dict(obs, content_features=encoder.snapshot(obs["sample_ms"])), row["feedback_input"]
        )
        states.append(decision["history"])
        if row["changed"]:
            policy.acknowledge(row["actuation_readback"]["encoder_max_bitrate_bps"], row["ack_ms"])
    return states


def load_repair_transitions(root, role):
    require(role in ("train", "calibration"), "evaluation labels cannot fit a repair model")
    root = Path(root)
    p = read_json(root / "protocol.json")
    require(p["stage"] == role, "wrong repair fitting role")
    require(p["source_kind"] == "recorded_video_repair_v5", "fresh V5 encoder-recipe outcomes required")
    audit_repair_study(root)
    namespace = digest(root / "manifest.json")
    transitions = []
    for trial in read_json(root / "runtime.json")["episodes"]:
        sender = read_json(root / trial["id"] / "sender_observations.json")
        labels = read_json(root / trial["id"] / "derived.json")["quality"]["source_labels"]
        by_step = defaultdict(list)
        for label in labels:
            if label["action_transition_inflight"] or label["decision_id"] is None:
                continue
            by_step[label["decision_id"]].append(label)
        decisions = sender["decisions"]
        states = reconstruct_causal_states(sender, read_json(root / trial["id"] / "frame_events.json"))
        for i, row in enumerate(decisions):
            values = by_step[i]
            if not values:
                continue
            miss = 1 - sum(s["identifiable_ontime"] for s in values) / len(values)
            psnr = np.mean([s["ontime_sampled_psnr_contribution"] for s in values]) / LEARNER["psnr_divisor"]
            terminal = (
                i + 1 >= len(decisions)
                or not by_step[i + 1]
                or decisions[i + 1]["repair_decision"]["history_reset"]
            )
            transitions.append(
                dict(
                    episode_id=namespace + "/" + trial["id"],
                    group=namespace + "/" + trial["group"],
                    step_id=i,
                    state=states[i],
                    next_state=states[i + 1] if not terminal else [0.0] * INPUT_DIM,
                    action=CAPS.index(row["actuation_readback"]["encoder_max_bitrate_bps"]),
                    reward=float(
                        psnr - LEARNER["miss_penalty"] * miss - LEARNER["switch_penalty"] * row["changed"]
                    ),
                    miss_fraction=miss,
                    label_count=len(values),
                    terminal=terminal,
                )
            )
    require(transitions, "no outcome-complete repair transitions")
    return transitions, p


def temporal_returns(transitions, n=10, gamma=0.98):
    require(type(n) is int and n > 0 and 0 < gamma < 1, "valid temporal horizon/discount required")
    by_key = {(t["episode_id"], t["step_id"]): t for t in transitions}
    require(len(by_key) == len(transitions), "duplicate repair transition")
    rows = []
    for first in transitions:
        current = first
        total = 0.0
        discount = 1.0
        bootstrap = 0.0
        future = np.zeros(INPUT_DIM)
        for k in range(n):
            total += discount * current["reward"]
            future = np.asarray(current["next_state"])
            if current["terminal"]:
                break
            discount *= gamma
            if k == n - 1:
                bootstrap = discount
                break
            following = by_key.get((first["episode_id"], current["step_id"] + 1))
            if following is None:
                future = np.zeros(INPUT_DIM)
                break
            current = following
        rows.append((first["state"], first["action"], total, future, bootstrap))
    return [np.asarray([r[k] for r in rows]) for k in range(5)]


def fold_normalization(net, mean, scale):
    """Fuse train-state-only whitening into the shipped first affine layer."""
    mean, scale = np.asarray(mean), np.asarray(scale)
    require(
        mean.shape == scale.shape == (net.params[0].shape[0],)
        and np.isfinite(mean).all()
        and np.isfinite(scale).all()
        and (scale > 0).all(),
        "finite positive train-state normalization required",
    )
    result = MLP.from_dict(net.to_dict())
    result.params[0] /= scale[:, None]
    result.params[1] -= mean @ result.params[0]
    return result


def fit_iql_critic(states, actions, rewards, future, terminals, config, seed):
    """Bootstrap from fitted factual value, never a max over unsupported actions."""
    states, future = np.asarray(states), np.asarray(future)
    actions, rewards = np.asarray(actions, dtype=int), np.asarray(rewards)
    terminals = np.asarray(terminals, dtype=bool)
    require(
        len(states) > 0
        and states.shape == future.shape
        and np.isfinite(states).all()
        and np.isfinite(future).all()
        and np.isfinite(rewards).all()
        and actions.shape == rewards.shape == terminals.shape == (len(states),)
        and ((0 <= actions) & (actions < 7)).all(),
        "finite factual IQL rows required",
    )
    require(
        0 < config["gamma"] < 1 and 0 < config["iql_expectile"] < 1 and 0 < config["target_tau"] <= 1,
        "valid IQL discounts/expectile/target update required",
    )
    rng = np.random.default_rng(seed)
    q = MLP(states.shape[1], config["hidden"], 7, rng)
    value = MLP(states.shape[1], config["hidden"], 1, rng)
    target = MLP(states.shape[1], config["hidden"], 1, rng)
    target.copy_from(value)
    low, high = -config["miss_penalty"] / (1 - config["gamma"]), 1 / (1 - config["gamma"])
    losses = []
    for update in range(config["updates"]):
        ix = rng.integers(0, len(states), config["batch_size"])
        s, ns, a = states[ix], future[ix], actions[ix]
        expected = rewards[ix] + config["gamma"] * (~terminals[ix]) * np.clip(target(ns)[:, 0], low, high)
        expected = np.clip(expected, low, high)
        q_values = q(s)
        error = q_values[np.arange(len(ix)), a] - expected
        gradient = np.zeros_like(q_values)
        gradient[np.arange(len(ix)), a] = np.clip(error, -1, 1) / len(ix)
        q.train(s, gradient, config["learning_rate"])
        residual = q(s)[np.arange(len(ix)), a] - value(s)[:, 0]
        weight = np.where(residual >= 0, config["iql_expectile"], 1 - config["iql_expectile"])
        value.train(s, (-weight * np.clip(residual, -1, 1) / len(ix))[:, None], config["learning_rate"])
        for p, v in zip(target.params, value.params, strict=True):
            p *= 1 - config["target_tau"]
            p += config["target_tau"] * v
        if update % 300 == 0 or update == config["updates"] - 1:
            losses.append(float(np.mean(error**2)))
    require(
        all(np.isfinite(p).all() for p in q.params) and np.isfinite(losses).all(),
        "nonfinite critic cannot be shipped",
    )
    return q, losses


def _load_runs(runs, role):
    roots = [Path(runs)] if isinstance(runs, (str, Path)) else [Path(p) for p in runs]
    require(roots and len(set(p.resolve() for p in roots)) == len(roots), "unique fitting parents required")
    rows, protocols = [], []
    for root in roots:
        r, p = load_repair_transitions(root, role)
        rows.extend(r)
        protocols.append(p)
    require(len({(t["episode_id"], t["step_id"]) for t in rows}) == len(rows), "duplicate fitting data")
    return roots, rows, protocols


def train_repair_model(train_run, calibration_run, out):
    out = Path(out)
    require(not out.exists() and not out.is_symlink(), "repair5 model output already exists")
    train_roots, train, tps = _load_runs(train_run, "train")
    cal_roots, cal, cps = _load_runs(calibration_run, "calibration")
    require(
        not (set(p.resolve() for p in train_roots) & set(p.resolve() for p in cal_roots)),
        "train/calibration parents must differ",
    )
    protocols = tps + cps
    require(
        all(
            p["measurement_recipe"] == tps[0]["measurement_recipe"] and p["controller_config"] == CONFIG
            for p in protocols
        ),
        "fresh fixed-recipe fitting required",
    )
    for i, p in enumerate(protocols):
        for other in protocols[i + 1 :]:
            if p["video_source"]["sha256"] == other["video_source"]["sha256"]:
                require(
                    all(
                        not video_overlap(a["video_segment"], b["video_segment"])
                        for a in p["groups"]
                        for b in other["groups"]
                    ),
                    "fitting source overlap",
                )
    require(
        len({t["episode_id"] for t in train}) >= 32
        and len({t["group"] for t in train}) >= 8
        and len({t["episode_id"] for t in cal}) >= 16,
        "larger independent fitting panel required",
    )
    require(
        len({p["video_source"]["sha256"] for p in tps}) >= 2
        and len({p["video_source"]["sha256"] for p in cps}) >= 2,
        "two movies required in both fitting roles",
    )
    require(
        {g["family"] for p in tps for g in p["groups"]}
        == {"stable", "collapse", "variable", "brief-collapse"},
        "all four network families required",
    )
    require({t["action"] for t in train} == set(range(7)), "all seven caps need factual training coverage")
    states = np.asarray([t["state"] for t in train])
    actions = np.asarray([t["action"] for t in train], dtype=int)
    future = np.asarray([t["next_state"] for t in train])
    rewards = np.asarray([t["reward"] for t in train])
    terminals = np.asarray([t["terminal"] for t in train], dtype=bool)
    mean, scale = states.mean(axis=0), np.maximum(states.std(axis=0), LEARNER["state_scale_floor"])
    inputs, next_inputs = (states - mean) / scale, (future - mean) / scale
    models, losses = [], []
    for seed in LEARNER["model_seeds"]:
        q, loss = fit_iql_critic(inputs, actions, rewards, next_inputs, terminals, LEARNER, seed)
        models.append(fold_normalization(q, mean, scale))
        losses.append(loss)
    miss, weights = (
        np.asarray([t["miss_fraction"] for t in train]),
        np.asarray([t["label_count"] for t in train]),
    )
    groups = sorted({t["group"] for t in train})
    risks = []
    for seed in LEARNER["model_seeds"]:
        rng = np.random.default_rng(seed + 401)
        net = MLP(INPUT_DIM, LEARNER["hidden"], 7, rng)
        chosen = rng.choice(groups, len(groups), replace=True)
        pool = np.concatenate([np.where(np.asarray([t["group"] == g for t in train]))[0] for g in chosen])
        for _ in range(LEARNER["risk_updates"]):
            ix = rng.choice(pool, LEARNER["batch_size"], replace=True)
            logits = net(inputs[ix])
            pred = sigmoid(logits)[np.arange(len(ix)), actions[ix]]
            gradient = np.zeros_like(logits)
            gradient[np.arange(len(ix)), actions[ix]] = (pred - miss[ix]) * weights[ix] / weights[ix].sum()
            net.train(inputs[ix], gradient, LEARNER["learning_rate"])
        risks.append(fold_normalization(net, mean, scale))
    cx, ca = np.asarray([t["state"] for t in cal]), np.asarray([t["action"] for t in cal], dtype=int)
    cy, cw = np.asarray([t["miss_fraction"] for t in cal]), np.asarray([t["label_count"] for t in cal])
    raw = np.asarray([sigmoid(net(cx))[np.arange(len(cal)), ca] for net in risks]).mean(axis=0)
    from .native_repair5_calibration import _fit_monotonic

    platt = _fit_monotonic(raw, cy, cw)
    clipped = np.clip(raw, 1e-6, 1 - 1e-6)
    pred = sigmoid(platt[0] * np.log(clipped / (1 - clipped)) + platt[1])
    margins, episode_counts, request_counts, group_counts = [], [], [], []
    rng = np.random.default_rng(5601)
    for action in range(7):
        ix = np.where(ca == action)[0]
        episodes = sorted({cal[i]["episode_id"] for i in ix})
        source_groups = sorted({cal[i]["group"] for i in ix})
        episode_counts.append(len(episodes))
        request_counts.append(int(cw[ix].sum()))
        group_counts.append(len(source_groups))
        residual = [
            float(np.average((cy - pred)[j], weights=cw[j]))
            for g in source_groups
            if len(j := np.asarray([i for i in ix if cal[i]["group"] == g], dtype=int))
        ]
        if (
            len(source_groups) < CONFIG["min_calibration_groups"]
            or len(episodes) < CONFIG["min_calibration_episodes"]
            or cw[ix].sum() < CONFIG["min_calibration_requests"]
        ):
            margins.append(1.0)
        else:
            a = np.asarray(residual)
            draws = a[rng.integers(0, len(a), (4000, len(a)))].mean(axis=1)
            margins.append(float(np.clip(np.quantile(draws, 0.95) + 0.02, 0, 1)))
    roots = train_roots + cal_roots
    bundle = dict(
        model_abi=REPAIR_ABI,
        config=CONFIG.copy(),
        feature_names=FEATURES,
        training_roles=["train", "calibration"],
        q_weights=models[0].to_dict(),
        q_ensemble=[m.to_dict() for m in models],
        risk_weights=[m.to_dict() for m in risks],
        platt=list(platt),
        risk_margin=margins,
        calibration_groups=group_counts,
        calibration_episodes=episode_counts,
        calibration_requests=request_counts,
        learner=LEARNER.copy(),
        source_reservations=[
            dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"])
            for p in protocols
            for g in p["groups"]
        ],
        state_normalization=dict(
            mean=mean.tolist(), scale=scale.tolist(), fused_into_weights=True, fitted_roles=["train"]
        ),
        causal_transform_source_sha256={
            n: digest(Path(__file__).with_name(n))
            for n in ("native_repair5_policy.py", "native_repair5_learning.py", "native_repair3_policy.py")
        },
        provenance={str(r.resolve() / "manifest.json"): digest(r / "manifest.json") for r in roots},
    )
    validate_repair_bundle(bundle)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "model.json", bundle)
    report = dict(
        train_episodes=len({t["episode_id"] for t in train}),
        train_groups=len(groups),
        train_transitions=len(train),
        calibration_episodes=len({t["episode_id"] for t in cal}),
        calibration_groups=len({t["group"] for t in cal}),
        calibration_transitions=len(cal),
        model_seeds=LEARNER["model_seeds"],
        algorithm=LEARNER["algorithm"],
        bellman_mse=losses,
        risk_margin=margins,
        calibration_requests=request_counts,
        training_movies=len({p["video_source"]["sha256"] for p in tps}),
        calibration_movies=len({p["video_source"]["sha256"] for p in cps}),
        empirical_margins_not_pointwise_safety_guarantees=True,
        proper_scoring_risk_loss="Bernoulli cross-entropy on factual request fractions",
        selected_policy_calibration_still_required=True,
        evaluation_labels_used=False,
        causal_sender_content_reconstructed_from_owned_past_frames=True,
        factual_action_heads=7,
        state_normalization_fitted_only_on_train=True,
        unsupported_action_max_bootstrap=False,
        fitting_source_kinds=[p["source_kind"] for p in protocols],
        SOTA_achieved=False,
    )
    write_json(out / "training_report.json", report)
    return report
