"""Versioned compact regularized neural hold forecasters; training development only.

The same eight training folds have already informed this recipe. They are NOT
independent validation, a causal action-value certificate, risk calibration or a
native actor. Earlier captures, models, checks, defaults and gates are immutable.
"""

import argparse
import copy
import json
from pathlib import Path

import numpy as np

from . import native_action_policy as action_module
from . import native_repair3_policy as state_module
from . import networks as network_module
from .native_action_policy import action_features
from .native_protocol import digest, read_json, require, seal_directory, verify_seal, write_json
from .native_repair3_policy import FEATURES, HISTORY_STEPS, INPUT_DIM, STEP_DIM
from .networks import MLP, sigmoid

ABI = "native_compact_regularized_hold_cv_v1"
COMPACT_DIM = 4 * STEP_DIM
CONFIG = dict(
    abi=ABI,
    role="train",
    source_cv_manifest_sha256="5cafe0fdff1a6c3527848cfd27f0d4dc1db4c754a44c3931327dde0abc7966e0",
    history_steps=32,
    step_dim=23,
    feature_names=list(FEATURES),
    projection="latest23_recent8mean23_all32mean23_all32std23",
    compact_dim=92,
    normalize="fit_fold_only_all_compact_and_proposed_features;scale_floor=0.05",
    model_seeds=[6601, 6611, 6621],
    cv_folds=2,
    updates=1200,
    batch_size=128,
    learning_rate=0.001,
    hidden=8,
    l2_weight_penalty=0.01,
    loss="weighted_utility_mse_plus_miss_log_loss_plus_weight_l2",
    action_blind="zero_three_proposed_inputs_before_normalization_and_lock_weight_rows_zero",
    minimum_action_utility_skill=0.01,
    original_action_prior_minimum_utility_skill=0.01,
    reused_training_folds_informed_recipe=True,
    independent_validation_or_native_qualification=False,
)


def validate_config(value):
    require(value == CONFIG, "fixed compact regularized training-development recipe required")


def project_state(states):
    x = np.asarray(states, dtype=float)
    require(
        x.ndim == 2 and x.shape[1] == INPUT_DIM and np.isfinite(x).all(),
        "complete finite causal 32x23 state required",
    )
    h = x.reshape(-1, HISTORY_STEPS, STEP_DIM)
    return np.column_stack([h[:, -1], h[:, -8:].mean(axis=1), h.mean(axis=1), h.std(axis=1)])


def design(state, cap, blind=False):
    state = np.asarray(state, dtype=float)
    cap = np.asarray(cap)
    projected = project_state(state)
    require(
        cap.shape == (len(state),)
        and np.issubdtype(cap.dtype, np.integer)
        and set(cap.tolist()) <= {300000, 450000, 900000},
        "exact legal proposed hold caps required even for blind controls",
    )
    a = (
        np.zeros((len(state), 3))
        if blind
        else np.asarray([action_features(int(c), s.tolist()) for c, s in zip(cap, state, strict=True)])
    )
    return np.column_stack([projected, a])


def regularized_step(net, x, gradient, lr, penalty):
    w, b, v, _ = net.params
    hidden = np.maximum(x @ w + b, 0)
    dh = (gradient @ v.T) * (hidden > 0)
    grads = [x.T @ dh + penalty * w, dh.sum(axis=0), hidden.T @ gradient + penalty * v, gradient.sum(axis=0)]
    norm = np.sqrt(sum(np.sum(g * g) for g in grads))
    net.updates += 1
    for i, g in enumerate(grads):
        g = g * min(1.0, 10 / max(norm, 1e-12))
        net.m[i] = 0.9 * net.m[i] + 0.1 * g
        net.v[i] = 0.999 * net.v[i] + 0.001 * g * g
        mh = net.m[i] / (1 - 0.9**net.updates)
        vh = net.v[i] / (1 - 0.999**net.updates)
        net.params[i] -= lr * mh / (np.sqrt(vh) + 1e-8)


def fit_forecaster(state, cap, target, weight, group, seed, blind=False):
    raw = design(state, cap, blind)
    mean = raw.mean(axis=0)
    scale = np.maximum(raw.std(axis=0), 0.05)
    x = (raw - mean) / scale
    require(
        target.shape == (len(state), 2)
        and np.isfinite(target).all()
        and ((target >= 0) & (target <= 1)).all()
        and weight.shape == (len(state),)
        and np.isfinite(weight).all()
        and (weight > 0).all(),
        "bounded factual target/positive request weights required",
    )
    rng = np.random.default_rng(seed)
    net = MLP(COMPACT_DIM + 3, CONFIG["hidden"], 2, rng)
    if blind:
        net.params[0][-3:] = 0
    groups = sorted(set(group.tolist()))
    pool = {g: np.flatnonzero(group == g) for g in groups}
    trace = []
    for update in range(CONFIG["updates"]):
        ix = np.asarray([rng.choice(pool[g]) for g in rng.choice(groups, CONFIG["batch_size"])])
        prediction = sigmoid(net(x[ix]))
        delta = prediction - target[ix]
        w = weight[ix] / weight[ix].sum()
        grad = (
            np.column_stack([2 * delta[:, 0] * prediction[:, 0] * (1 - prediction[:, 0]), delta[:, 1]])
            * w[:, None]
        )
        regularized_step(net, x[ix], grad, CONFIG["learning_rate"], CONFIG["l2_weight_penalty"])
        if blind:
            require(np.all(net.params[0][-3:] == 0), "action-blind forecaster acquired proposal dependence")
        if update % 100 == 0 or update == CONFIG["updates"] - 1:
            logits = net(x)
            p = sigmoid(logits)
            trace.append(
                dict(
                    update=update,
                    utility_mse=float(np.average((p[:, 0] - target[:, 0]) ** 2, weights=weight)),
                    miss_log_loss=float(
                        np.average(
                            np.logaddexp(0, logits[:, 1]) - target[:, 1] * logits[:, 1], weights=weight
                        )
                    ),
                    weight_l2=float(sum(np.sum(net.params[i] ** 2) for i in (0, 2))),
                )
            )
    return dict(
        abi=ABI,
        weights=net.to_dict(),
        normalization=dict(mean=mean.tolist(), scale=scale.tolist(), fitted_roles=["train"]),
        seed=seed,
        updates=CONFIG["updates"],
        blind=blind,
        fit_trace=trace,
        fit_groups=groups,
        neural_forecaster_not_native_actor=True,
        native_deployment_qualified=False,
    )


def predict(model, state, cap):
    require(
        model["abi"] == ABI and model["neural_forecaster_not_native_actor"] is True,
        "compact auxiliary forecaster ABI required",
    )
    mean, scale = (np.asarray(model["normalization"][k]) for k in ("mean", "scale"))
    require(
        mean.shape == scale.shape == (COMPACT_DIM + 3,)
        and np.isfinite(mean).all()
        and np.isfinite(scale).all()
        and (scale >= 0.05).all(),
        "valid compact normalization required",
    )
    return sigmoid(MLP.from_dict(model["weights"])((design(state, cap, model["blind"]) - mean) / scale))


def load_source(root):
    root = Path(root).resolve()
    require(
        digest(root / "manifest.json") == CONFIG["source_cv_manifest_sha256"],
        "pinned factual hold-CV source receipt required",
    )
    seal = verify_seal(root, "native_randomized_hold_action_skill_cv_v1_complete")
    report = read_json(root / "report.json")
    require(
        report["rows"] == 672
        and report["requests"] == 8071
        and report["physical_groups"] == 8
        and report["calibration_diagnostic_validation_test_labels_used"] is False,
        "only original legal train hold cohorts may be reused",
    )
    with np.load(root / "train_rows.npz", allow_pickle=False) as cache:
        data = {k: cache[k].copy() for k in ("state", "cap", "targets", "weight", "group")}
    require(
        data["state"].shape == (672, INPUT_DIM)
        and data["targets"].shape == (672, 2)
        and data["cap"].shape == data["weight"].shape == data["group"].shape == (672,)
        and set(data["cap"].tolist()) == {300000, 450000, 900000}
        and len(set(data["group"].tolist())) == 8
        and np.issubdtype(data["cap"].dtype, np.integer)
        and np.issubdtype(data["weight"].dtype, np.integer)
        and data["weight"].sum() == 8071
        and (data["weight"] > 0).all()
        and np.isfinite(data["targets"]).all()
        and ((data["targets"] >= 0) & (data["targets"] <= 1)).all(),
        "exact finite factual training cache required",
    )
    project_state(data["state"])
    return root, seal, report, data


def fold_metrics(data, models, held):
    state, cap, target, weight, group = (data[k] for k in ("state", "cap", "targets", "weight", "group"))
    test = np.isin(group, held)
    fit = ~test
    out = {}
    for mode, members in models.items():
        prediction = np.mean([predict(m, state, cap) for m in members], axis=0)
        for name, mask in (("fit", fit), ("held", test)):
            mse = np.average((prediction[mask] - target[mask]) ** 2, axis=0, weights=weight[mask])
            out[mode + "_" + name + "_utility_mse"] = float(mse[0])
            out[mode + "_" + name + "_risk_brier"] = float(mse[1])
    priors = {
        c: np.average(target[fit & (cap == c)], axis=0, weights=weight[fit & (cap == c)])
        for c in set(cap[test].tolist())
    }
    baseline = np.asarray([priors[c] for c in cap[test]])
    prior = np.average((baseline - target[test]) ** 2, axis=0, weights=weight[test])
    out.update(
        prior_utility_mse=float(prior[0]),
        prior_risk_brier=float(prior[1]),
        action_utility_skill=float(
            1 - out["conditional_held_utility_mse"] / max(1e-12, out["blind_held_utility_mse"])
        ),
        prior_utility_skill=float(1 - out["conditional_held_utility_mse"] / max(1e-12, float(prior[0]))),
        prior_risk_skill=float(1 - out["conditional_held_risk_brier"] / max(1e-12, float(prior[1]))),
        test_rows=int(test.sum()),
        test_requests=int(weight[test].sum()),
    )
    out["necessary_action_skill_passed"] = (
        out["action_utility_skill"] >= CONFIG["minimum_action_utility_skill"]
    )
    out["original_prior_proxy_passed"] = (
        out["prior_utility_skill"] >= CONFIG["original_action_prior_minimum_utility_skill"]
        and out["prior_risk_skill"] >= 0
    )
    return out


def run_compact_hold_cv(config, source, out):
    validate_config(read_json(config))
    out = Path(out).resolve()
    require(not out.exists() and not out.is_symlink(), "fresh immutable compact CV output required")
    root, source_seal, original, data = load_source(source)
    out.mkdir(parents=True)
    write_json(out / "config.json", copy.deepcopy(CONFIG))
    groups = sorted(set(data["group"].tolist()))
    folds = []
    for fold in range(2):
        held = groups[fold::2]
        fit = ~np.isin(data["group"], held)
        models = {}
        require(
            held == original["comparison"]["folds"][fold]["held_out_groups"],
            "original physical folds must not be selected/repartitioned",
        )
        for mode in ("conditional", "blind"):
            members = []
            for seed in CONFIG["model_seeds"]:
                model = fit_forecaster(
                    data["state"][fit],
                    data["cap"][fit],
                    data["targets"][fit],
                    data["weight"][fit],
                    data["group"][fit],
                    seed,
                    mode == "blind",
                )
                model["held_out_groups"] = held
                path = out / "models" / f"fold-{fold}-{mode}-seed-{seed}.json"
                path.parent.mkdir(exist_ok=True)
                write_json(path, model)
                members.append(model)
            models[mode] = members
        folds.append(
            dict(
                fold=fold,
                held_out_groups=held,
                fit_groups=groups[(1 - fold) :: 2],
                **fold_metrics(data, models, held),
            )
        )
    require(
        all(digest(root / p) == sha for p, sha in source_seal["artifacts_sha256"].items()),
        "compact fit changed a pinned prior artifact",
    )
    result = dict(
        abi=ABI,
        config=copy.deepcopy(CONFIG),
        rows=672,
        requests=8071,
        physical_groups=8,
        folds=folds,
        necessary_action_skill_passed=all(f["necessary_action_skill_passed"] for f in folds),
        original_prior_proxy_passed=all(f["original_prior_proxy_passed"] for f in folds),
        parameters_per_forecaster=786,
        original_parameters_per_forecaster=23746,
        new_forecasters_fitted=12,
        previous_models_refitted=False,
        new_native_captures=0,
        training_development_not_independent_validation=True,
        original_native_and_source_cv_numeric_replay_reused=True,
        old_candidate_or_risk_or_default_changed=False,
        native_deployment_qualified=False,
        causal_gain_proven=False,
        native_improvement_proven=False,
        SOTA_achieved=False,
        source_cv=str(root),
        source_cv_manifest_sha256=digest(root / "manifest.json"),
        config_sha256=digest(config),
        implementation_sha256=digest(Path(__file__)),
        dependency_sha256={
            str(Path(m.__file__).resolve()): digest(Path(m.__file__))
            for m in (action_module, state_module, network_module)
        },
    )
    write_json(out / "report.json", result)
    seal_directory(
        out,
        [str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()],
        ABI + "_complete",
        SOTA_achieved=False,
    )
    return result


def audit_compact_hold_cv(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    report = read_json(out / "report.json")
    validate_config(report["config"])
    require(
        report["implementation_sha256"] == digest(Path(__file__))
        and all(digest(Path(p)) == sha for p, sha in report["dependency_sha256"].items())
        and report["source_cv_manifest_sha256"] == CONFIG["source_cv_manifest_sha256"]
        and report["training_development_not_independent_validation"] is True
        and report["old_candidate_or_risk_or_default_changed"] is False
        and report["native_deployment_qualified"] is False
        and report["SOTA_achieved"] is False,
        "compact CV cannot qualify/replace a native actor or independent validation",
    )
    _, _, original, data = load_source(report["source_cv"])
    groups = sorted(set(data["group"].tolist()))
    require(len(report["folds"]) == 2, "both fixed compact folds required")
    for fold, stored in enumerate(report["folds"]):
        held = groups[fold::2]
        fit = ~np.isin(data["group"], held)
        models = {}
        require(
            stored["fold"] == fold
            and stored["held_out_groups"] == held == original["comparison"]["folds"][fold]["held_out_groups"]
            and stored["fit_groups"] == groups[(1 - fold) :: 2],
            "original physical fold identity changed",
        )
        for mode in ("conditional", "blind"):
            members = []
            raw = design(data["state"][fit], data["cap"][fit], mode == "blind")
            for seed in CONFIG["model_seeds"]:
                model = read_json(out / "models" / f"fold-{fold}-{mode}-seed-{seed}.json")
                norm = model["normalization"]
                params = [np.asarray(p) for p in model["weights"]]
                require(
                    model["seed"] == seed
                    and model["updates"] == CONFIG["updates"]
                    and model["blind"] is (mode == "blind")
                    and model["fit_groups"] == groups[(1 - fold) :: 2]
                    and model["held_out_groups"] == held
                    and norm["fitted_roles"] == ["train"]
                    and np.allclose(norm["mean"], raw.mean(axis=0), atol=1e-12, rtol=0)
                    and np.allclose(norm["scale"], np.maximum(raw.std(axis=0), 0.05), atol=1e-12, rtol=0)
                    and [p.shape for p in params] == [(95, 8), (8,), (8, 2), (2,)]
                    and all(np.isfinite(p).all() for p in params)
                    and (mode != "blind" or np.all(params[0][-3:] == 0)),
                    "compact role/normalization/seed/weights/action-blind identity changed",
                )
                members.append(model)
            models[mode] = members
        actual = fold_metrics(data, models, held)
        require(
            all(
                stored[k] is v if type(v) is bool else np.isclose(stored[k], v, atol=1e-10, rtol=0)
                for k, v in actual.items()
            ),
            "saved compact fold forecasts/prior/errors/skills mismatch",
        )
    require(
        report["necessary_action_skill_passed"]
        is all(f["necessary_action_skill_passed"] for f in report["folds"])
        and report["original_prior_proxy_passed"]
        is all(f["original_prior_proxy_passed"] for f in report["folds"]),
        "compact development result flag mismatch",
    )
    return dict(
        read_only=True,
        numerically_recomputed_folds=2,
        rows=672,
        requests=8071,
        necessary_action_skill_passed=report["necessary_action_skill_passed"],
        original_prior_proxy_passed=report["original_prior_proxy_passed"],
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_action_compact_hold_cv")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--source-cv", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    args = parser.parse_args()
    result = (
        run_compact_hold_cv(args.config, args.source_cv, args.out)
        if args.command == "run"
        else audit_compact_hold_cv(args.run)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
