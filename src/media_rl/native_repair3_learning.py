"""Role-disjoint, multi-seed long-history CQL fitting and episode-cluster risk margins."""

from collections import defaultdict
from pathlib import Path

import numpy as np

from .native_observations import CAPS
from .native_protocol import digest, read_json, require, write_json
from .native_repair3_policy import (
    CONFIG,
    FEATURES,
    INPUT_DIM,
    REPAIR_ABI,
    RepairPolicy,
    SenderContentEncoder,
    validate_repair_bundle,
)
from .native_repair3_study import LEARNER, audit_repair_study, video_overlap
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
    if p["source_kind"] == "recorded_video_repair_v2":
        from .native_repair_study import audit_repair_study as audit_legacy

        audit_legacy(root)
    else:
        require(p["source_kind"] == "recorded_video_repair_v3", "owned versioned fitting source required")
        audit_repair_study(root)
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
                    episode_id=trial["id"],
                    group=trial["group"],
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


def train_repair_model(train_run, calibration_run, out):
    out = Path(out)
    require(not out.exists() and not out.is_symlink(), "repair3 model output already exists")
    train, tp = load_repair_transitions(train_run, "train")
    cal, cp = load_repair_transitions(calibration_run, "calibration")
    require(
        tp["measurement_recipe"] == cp["measurement_recipe"]
        and tp["controller_config"] == cp["controller_config"],
        "fitting recipe mismatch",
    )
    if tp["video_source"]["sha256"] == cp["video_source"]["sha256"]:
        require(
            all(
                not video_overlap(a["video_segment"], b["video_segment"])
                for a in tp["groups"]
                for b in cp["groups"]
            ),
            "train/calibration source leakage",
        )
    require(
        len({t["episode_id"] for t in train}) >= 32
        and len({t["group"] for t in train}) >= 8
        and len({t["episode_id"] for t in cal}) >= 16,
        "larger independent fitting panel required",
    )
    actions = {t["action"] for t in train}
    require(actions == set(range(7)), "all seven caps need factual training coverage")
    states, actions, returns, future, discounts = temporal_returns(train, LEARNER["n_step"], LEARNER["gamma"])
    actions = actions.astype(int)
    models = []
    losses = []
    for seed in LEARNER["model_seeds"]:
        rng = np.random.default_rng(seed)
        q = MLP(INPUT_DIM, LEARNER["hidden"], 7, rng)
        target = MLP(INPUT_DIM, LEARNER["hidden"], 7, rng)
        target.copy_from(q)
        sampled_losses = []
        for update in range(LEARNER["updates"]):
            ix = rng.integers(0, len(train), LEARNER["batch_size"])
            s = states[ix]
            next_s = future[ix]
            greedy = np.argmax(q(next_s), axis=1)
            expected = returns[ix] + discounts[ix] * target(next_s)[np.arange(len(ix)), greedy]
            values = q(s)
            difference = values[np.arange(len(ix)), actions[ix]] - expected
            gradient = np.zeros_like(values)
            gradient[np.arange(len(ix)), actions[ix]] = np.clip(difference, -1, 1)
            exp = np.exp(values - values.max(axis=1, keepdims=True))
            softmax = exp / exp.sum(axis=1, keepdims=True)
            softmax[np.arange(len(ix)), actions[ix]] -= 1
            q.train(s, (gradient + LEARNER["cql_alpha"] * softmax) / len(ix), LEARNER["learning_rate"])
            if (update + 1) % LEARNER["target_update_every"] == 0:
                target.copy_from(q)
            if update % 300 == 0:
                sampled_losses.append(float(np.mean(difference**2)))
        models.append(q)
        losses.append(sampled_losses)
    inputs = states
    miss = np.asarray([t["miss_fraction"] for t in train])
    weights = np.asarray([t["label_count"] for t in train])
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
        risks.append(net)
    cal_states = np.asarray([t["state"] for t in cal])
    ca = np.asarray([t["action"] for t in cal])
    cx = cal_states
    cy = np.asarray([t["miss_fraction"] for t in cal])
    cw = np.asarray([t["label_count"] for t in cal])
    raw = np.asarray([sigmoid(net(cx))[np.arange(len(cal)), ca] for net in risks]).mean(axis=0)
    from .native_repair3_calibration import _fit_monotonic

    platt = _fit_monotonic(raw, cy, cw)
    clipped = np.clip(raw, 1e-6, 1 - 1e-6)
    pred = sigmoid(platt[0] * np.log(clipped / (1 - clipped)) + platt[1])
    margins = []
    episode_counts = []
    request_counts = []
    rng = np.random.default_rng(2601)
    for action in range(7):
        ix = np.where(ca == action)[0]
        episodes = sorted({cal[i]["episode_id"] for i in ix})
        episode_counts.append(len(episodes))
        request_counts.append(int(cw[ix].sum()))
        # Conservative empirical calibration residual, clustered by source/schedule group.
        source_groups = sorted({cal[i]["group"] for i in ix})
        residual = [
            float(np.average((cy - pred)[j], weights=cw[j]))
            for g in source_groups
            if len(j := np.asarray([i for i in ix if cal[i]["group"] == g], dtype=int))
        ]
        if (
            len(source_groups) < 3
            or len(episodes) < CONFIG["min_calibration_episodes"]
            or cw[ix].sum() < CONFIG["min_calibration_requests"]
        ):
            margins.append(1.0)
        else:
            a = np.asarray(residual)
            draws = a[rng.integers(0, len(a), (4000, len(a)))].mean(axis=1)
            margins.append(float(np.clip(np.quantile(draws, 0.95) + 0.02, 0, 1)))
    reservations = [
        dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"])
        for p in (tp, cp)
        for g in p["groups"]
    ]
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
        calibration_groups=[len({t["group"] for t in cal if t["action"] == a}) for a in range(7)],
        calibration_episodes=episode_counts,
        calibration_requests=request_counts,
        learner=LEARNER,
        source_reservations=reservations,
        causal_transform_source_sha256={
            n: digest(Path(__file__).with_name(n))
            for n in ("native_repair3_policy.py", "native_repair3_learning.py")
        },
        provenance={
            str(Path(r).resolve() / "manifest.json"): digest(Path(r) / "manifest.json")
            for r in (train_run, calibration_run)
        },
    )
    validate_repair_bundle(bundle)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "model.json", bundle)
    report = dict(
        train_episodes=len({t["episode_id"] for t in train}),
        train_groups=len({t["group"] for t in train}),
        train_transitions=len(train),
        calibration_episodes=len({t["episode_id"] for t in cal}),
        calibration_transitions=len(cal),
        model_seeds=LEARNER["model_seeds"],
        bellman_mse=losses,
        risk_margin=margins,
        calibration_requests=request_counts,
        empirical_margins_not_pointwise_safety_guarantees=True,
        proper_scoring_risk_loss="Bernoulli cross-entropy on factual request fractions",
        selected_policy_calibration_still_required=True,
        evaluation_labels_used=False,
        causal_sender_content_reconstructed_from_owned_past_frames=True,
        factual_action_heads=7,
        fitting_source_kinds=[tp["source_kind"], cp["source_kind"]],
        SOTA_achieved=False,
    )
    write_json(out / "training_report.json", report)
    return report
