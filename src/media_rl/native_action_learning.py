"""Train-only bounded factual outcomes; independently calibrated by causal context.

No Bellman target/unsupported-action max. No evaluation labels or neural and
normalization fitting on calibration. Direct outcomes are not long-horizon return.
"""

import json
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

import numpy as np

from .native_action_policy import (
    CANDIDATES,
    CONFIG,
    CONTEXTS,
    MODEL_ABI,
    CausalState,
    action_features,
    causal_context,
    predict_members,
    validate_bundle,
)
from .native_observations import CAPS
from .native_protocol import digest, read_json, require, write_json
from .native_repair3_policy import FEATURES, INPUT_DIM, SenderContentEncoder
from .native_repair5_calibration import _fit_monotonic, _probability
from .native_repair5_study import CONFIG as V5_CONFIG
from .native_repair5_study import audit_repair_study, video_overlap
from .networks import MLP, sigmoid

LEARNER = dict(
    abi="factual_bounded_outcomes_v1",
    model_seeds=[6601, 6611, 6621],
    hidden=32,
    updates=1800,
    cv_updates=1200,
    batch_size=128,
    learning_rate=0.001,
    state_scale_floor=0.05,
    utility_divisor=100,
    loss="weighted_utility_mse_plus_miss_log_loss",
    bootstrap=False,
    cv_folds=2,
    min_utility_skill=0.01,
    calibration_slack=0.02,
)


def physical_group(p, trial):
    value = [p["video_source"]["sha256"], trial["video_segment"], trial["schedule"]]
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def reconstruct_states(sender, frames):
    content = SenderContentEncoder()
    policy = CausalState()
    cursor = 0
    states = []
    sources = frames["sources"]
    require(
        all(a["capture_request_ms"] < b["capture_request_ms"] for a, b in zip(sources, sources[1:])),
        "source frames must be causal ordered",
    )
    for row in sender["decisions"]:
        obs = row["observation"]
        now = obs["sample_ms"]
        while cursor < len(sources) and sources[cursor]["capture_request_ms"] <= now:
            s = sources[cursor]
            content.observe(s["reference_rgb"], s["capture_request_ms"])
            cursor += 1
        require(
            abs(obs["features"][7] * 4e6 - obs["raw_source"]["encoder_cap_bps"]) < 0.01,
            "actual scalar cap must never be projected",
        )
        d = policy.observe(dict(obs, content_features=content.snapshot(now)), row["feedback_input"])
        states.append(d["history"])
    return states


def load_role(roots, role):
    require(role in ("train", "calibration"), "evaluation and diagnostic labels cannot fit")
    roots = [Path(r) for r in roots]
    require(roots and len({p.resolve() for p in roots}) == len(roots), "unique fitting parents required")
    rows = []
    protocols = []
    for root in roots:
        p = read_json(root / "protocol.json")
        require(
            p["stage"] == role
            and p["source_kind"] == "recorded_video_repair_v5"
            and p["controller_config"] == V5_CONFIG,
            "only compatible legal V5 fitting roles accepted; no diagnostic shadow history",
        )
        audit_repair_study(root)
        protocols.append(p)
        namespace = digest(root / "manifest.json")
        for trial in read_json(root / "runtime.json")["episodes"]:
            sender = read_json(root / trial["id"] / "sender_observations.json")
            states = reconstruct_states(sender, read_json(root / trial["id"] / "frame_events.json"))
            bystep = defaultdict(list)
            for label in read_json(root / trial["id"] / "derived.json")["quality"]["source_labels"]:
                if not label["action_transition_inflight"] and label["decision_id"] is not None:
                    bystep[label["decision_id"]].append(label)
            for decision in sender["decisions"]:
                step = decision["step_id"]
                labels = bystep[step]
                if not labels:
                    continue
                cap = decision["actuation_readback"]["encoder_max_bitrate_bps"]
                require(
                    cap in CANDIDATES
                    and all(
                        label["encoder_cap_bps"] == cap and label["capture_request_ms"] >= decision["ack_ms"]
                        for label in labels
                    ),
                    "factual actual action attribution required",
                )
                rows.append(
                    dict(
                        state=states[step],
                        cap=cap,
                        utility=float(
                            np.mean([label["ontime_sampled_psnr_contribution"] for label in labels])
                        )
                        / 100,
                        miss=float(np.mean([not label["identifiable_ontime"] for label in labels])),
                        weight=len(labels),
                        episode=namespace + "/" + trial["id"],
                        group=physical_group(p, trial),
                        context=causal_context(states[step]),
                        step=step,
                    )
                )
    require(
        rows and len({(r["episode"], r["step"]) for r in rows}) == len(rows),
        "nonduplicate factual labels required",
    )
    return rows, protocols, roots


def fit_outcomes(rows, seed, updates):
    x = np.asarray([r["state"] for r in rows])
    mean = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0), LEARNER["state_scale_floor"])
    a = np.asarray([action_features(r["cap"], r["state"]) for r in rows])
    x = np.column_stack([(x - mean) / scale, a])
    y = np.asarray([[r["utility"], r["miss"]] for r in rows])
    weights = np.asarray([r["weight"] for r in rows], dtype=float)
    require(
        np.isfinite(x).all() and np.isfinite(y).all() and ((y >= 0) & (y <= 1)).all() and (weights > 0).all(),
        "bounded factual training targets required",
    )
    rng = np.random.default_rng(seed)
    net = MLP(INPUT_DIM + 3, LEARNER["hidden"], 2, rng)
    groups = sorted({r["group"] for r in rows})
    pool = {g: np.asarray([i for i, r in enumerate(rows) if r["group"] == g]) for g in groups}
    losses = []
    for step in range(updates):
        ix = np.asarray([rng.choice(pool[g]) for g in rng.choice(groups, LEARNER["batch_size"])])
        pred = sigmoid(net(x[ix]))
        w = weights[ix] / weights[ix].sum()
        delta = pred - y[ix]
        grad = np.column_stack([2 * delta[:, 0] * pred[:, 0] * (1 - pred[:, 0]), delta[:, 1]]) * w[:, None]
        net.train(x[ix], grad, LEARNER["learning_rate"])
        if step % 100 == 0 or step == updates - 1:
            z = net(x)
            p = sigmoid(z)
            losses.append(
                dict(
                    update=step,
                    utility_mse=float(np.average((p[:, 0] - y[:, 0]) ** 2, weights=weights)),
                    miss_log_loss=float(
                        np.average(np.logaddexp(0, z[:, 1]) - y[:, 1] * z[:, 1], weights=weights)
                    ),
                )
            )
    w, b, v, c = [z.copy() for z in net.params]
    w[:INPUT_DIM] /= scale[:, None]
    b -= mean @ w[:INPUT_DIM]
    net.params = [w, b, v, c]
    return (
        net.to_dict(),
        dict(mean=mean.tolist(), scale=scale.tolist(), fused_into_weights=True, fitted_roles=["train"]),
        losses,
    )


def held_out_training_check(rows):
    groups = sorted({r["group"] for r in rows})
    folds = []
    require(len(groups) >= 8, "eight physical training groups required")
    for fold in range(LEARNER["cv_folds"]):
        held = set(groups[fold :: LEARNER["cv_folds"]])
        train = [r for r in rows if r["group"] not in held]
        test = [r for r in rows if r["group"] in held]
        members = [fit_outcomes(train, s, LEARNER["cv_updates"])[0] for s in LEARNER["model_seeds"]]
        inputs = np.asarray([r["state"] + action_features(r["cap"], r["state"]) for r in test])
        pred = np.mean([sigmoid(MLP.from_dict(m)(inputs)) for m in members], axis=0)
        y = np.asarray([[r["utility"], r["miss"]] for r in test])
        weights = np.asarray([r["weight"] for r in test])
        priors = {}
        for cap in {r["cap"] for r in test}:
            rr = [t for t in train if t["cap"] == cap]
            require(rr, "held-out action has no training support")
            priors[cap] = np.average(
                [[t["utility"], t["miss"]] for t in rr], axis=0, weights=[t["weight"] for t in rr]
            )
        baseline = np.asarray([priors[r["cap"]] for r in test])
        mse = np.average((pred - y) ** 2, axis=0, weights=weights)
        prior = np.average((baseline - y) ** 2, axis=0, weights=weights)
        folds.append(
            dict(
                held_out_groups=sorted(held),
                fit_groups=sorted(set(groups) - held),
                utility_mse=float(mse[0]),
                prior_utility_mse=float(prior[0]),
                risk_brier=float(mse[1]),
                prior_risk_brier=float(prior[1]),
                utility_skill=float((prior[0] - mse[0]) / max(1e-12, prior[0])),
                risk_skill=float((prior[1] - mse[1]) / max(1e-12, prior[1])),
            )
        )
    return dict(
        folds=folds,
        passed=all(
            f["utility_skill"] >= LEARNER["min_utility_skill"] and f["risk_skill"] >= 0 for f in folds
        ),
        not_critic_or_causal_convergence_certificate=True,
    )


def calibrate_cells(members, rows):
    x = np.asarray([r["state"] + action_features(r["cap"], r["state"]) for r in rows])
    raw = np.mean([sigmoid(MLP.from_dict(m)(x))[:, 1] for m in members], axis=0)
    cells = {}
    for cap in CANDIDATES:
        for context in CONTEXTS:
            ix = np.asarray(
                [i for i, r in enumerate(rows) if r["cap"] == cap and r["context"] == context], dtype=int
            )
            rr = [rows[i] for i in ix]
            groups = sorted({r["group"] for r in rr})
            ep = len({r["episode"] for r in rr})
            count = sum(r["weight"] for r in rr)
            supported = len(groups) >= 3 and ep >= 3 and count >= 60
            cell = dict(
                groups=len(groups),
                episodes=ep,
                requests=count,
                supported=supported,
                platt=[1.0, 0.0],
                margin=1.0,
                held_out_group_residuals=[],
                folds=[],
            )
            if supported:
                y = np.asarray([r["miss"] for r in rr])
                w = np.asarray([r["weight"] for r in rr])
                p = raw[ix]
                g = np.asarray([r["group"] for r in rr])
                cell["platt"] = _fit_monotonic(p, y, w)
                for group in groups:
                    test = g == group
                    platt = _fit_monotonic(p[~test], y[~test], w[~test])
                    estimate = _probability(p[test], platt)
                    residual = float(np.average(y[test] - estimate, weights=w[test]))
                    cell["held_out_group_residuals"].append(residual)
                    cell["folds"].append(
                        dict(held_out_group=group, fit_groups=[a for a in groups if a != group], platt=platt)
                    )
                cell["margin"] = float(
                    np.clip(max(cell["held_out_group_residuals"]) + LEARNER["calibration_slack"], 0, 1)
                )
            cells[f"{cap}/{context}"] = cell
    return cells


def train_action_model(train_runs, calibration_runs, out):
    out = Path(out)
    require(not out.exists() and not out.is_symlink(), "immutable new candidate output required")
    train, tps, tr = load_role(train_runs, "train")
    cal, cps, cr = load_role(calibration_runs, "calibration")
    require(not ({r.resolve() for r in tr} & {r.resolve() for r in cr}), "distinct fitting roles required")
    protocols = tps + cps
    require(
        all(p["measurement_recipe"] == tps[0]["measurement_recipe"] for p in protocols),
        "identical V5 native encoder physics required",
    )
    for i, p in enumerate(protocols):
        for q in protocols[i + 1 :]:
            if p["video_source"]["sha256"] == q["video_source"]["sha256"]:
                require(
                    all(
                        not video_overlap(a["video_segment"], b["video_segment"])
                        for a in p["groups"]
                        for b in q["groups"]
                    ),
                    "source fitting overlap forbidden",
                )
    for role, rows, ps in [("train", train, tps), ("calibration", cal, cps)]:
        require(
            len({r["group"] for r in rows}) >= 8
            and len({r["episode"] for r in rows}) >= 32
            and len({p["video_source"]["sha256"] for p in ps}) >= 2,
            "two movies/eight physical groups/larger fitting panel required",
        )
        require(
            {g["family"] for p in ps for g in p["groups"]}
            == {"stable", "collapse", "variable", "brief-collapse"},
            "four network families required",
        )
        require({r["cap"] for r in rows} == set(CAPS), "legal factual seven-cap parent coverage required")
    cv = held_out_training_check(train)
    members = []
    normalizations = []
    traces = []
    for seed in LEARNER["model_seeds"]:
        m, n, trace = fit_outcomes(train, seed, LEARNER["updates"])
        members.append(m)
        normalizations.append(n)
        traces.append(trace)
    require(
        normalizations[0] == normalizations[1] == normalizations[2],
        "train-only normalization must be identical",
    )
    cells = calibrate_cells(members, cal)
    bundle = dict(
        model_abi=MODEL_ABI,
        config=CONFIG.copy(),
        feature_names=FEATURES,
        candidates=list(CANDIDATES),
        training_roles=["train", "calibration"],
        members=members,
        cells=cells,
        training_skill_passed=cv["passed"],
        native_deployment_qualified=False,
        state_normalization=normalizations[0],
        learner=LEARNER.copy(),
        provenance={str(r.resolve() / "manifest.json"): digest(r / "manifest.json") for r in tr + cr},
        source_reservations=[
            dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"])
            for p in protocols
            for g in p["groups"]
        ],
        source_sha256={
            n: digest(Path(__file__).with_name(n))
            for n in (
                "native_action_policy.py",
                "native_action_learning.py",
                "native_repair3_policy.py",
                "native_repair5_policy.py",
                "native_observations.py",
                "native_protocol.py",
                "native_repair5_calibration.py",
                "native_repair5_study.py",
                "networks.py",
            )
        },
    )
    validate_bundle(bundle)
    sample = [r["state"] for r in cal[:: max(1, len(cal) // 100)]]
    pred = [predict_members(bundle, s).tolist() for s in sample]
    require(
        all(np.isfinite(a).all() and ((np.asarray(a) >= 0) & (np.asarray(a) <= 1)).all() for a in pred),
        "all action outputs must stay bounded",
    )
    report = dict(
        model_abi=MODEL_ABI,
        rows=dict(train=len(train), calibration=len(cal)),
        requests=dict(train=sum(r["weight"] for r in train), calibration=sum(r["weight"] for r in cal)),
        physical_groups=dict(
            train=len({r["group"] for r in train}), calibration=len({r["group"] for r in cal})
        ),
        training_cv=cv,
        fit_traces=traces,
        unsupported_new_caps=[c for c in CANDIDATES if c not in CAPS],
        supported_cells=sum(c["supported"] for c in cells.values()),
        minimum_supported_margins={
            ctx: min(
                (cells[f"{cap}/{ctx}"]["margin"] for cap in CANDIDATES if cells[f"{cap}/{ctx}"]["supported"]),
                default=1,
            )
            for ctx in CONTEXTS
        },
        actual_native_learned_improvement_proven=False,
        native_deployment_qualified=False,
        not_long_horizon_return_model=True,
        diagnostic_selected_validation_test_labels_used=False,
    )
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "model.json", bundle)
    write_json(out / "training_report.json", report)
    write_json(
        out / "manifest.json",
        dict(
            stage="bounded_action_candidate_fitted",
            artifacts_sha256={n: digest(out / n) for n in ("model.json", "training_report.json")},
            SOTA_achieved=False,
        ),
    )
    return report
