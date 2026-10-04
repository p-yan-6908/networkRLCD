"""Prospective train-only utility action-skill CV for newly randomized hold cohorts.

New factual data/horizon only: no previous conditional refit, risk calibration,
diagnostic labels, deployed/candidate weights or promotion. This is a necessary
predictive experiment, not a causal-effect/native/SOTA qualification certificate.
"""

import argparse
import copy
import json
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_excitation as excitation
from . import native_action_excitation_audit as replay
from . import native_action_learning as learner
from . import native_action_value_skill as skill
from .native_action_learning import physical_group
from .native_action_policy import action_features
from .native_protocol import digest, read_json, require, seal_directory, verify_seal, write_json
from .networks import MLP, sigmoid

ABI = "native_randomized_hold_action_skill_cv_v1"
CONFIG = dict(
    abi=ABI,
    role="train",
    conditions=["random-hold-a", "random-hold-b"],
    credit=copy.deepcopy(excitation.CREDIT),
    comparison=copy.deepcopy(skill.CHECK_CONFIG),
    minimum_physical_groups=8,
    previous_immediate_horizon_rows_used=False,
    candidate_or_selected_risk_calibration_forbidden=True,
    no_native_deployment_or_causal_gain_claim=True,
)


def validate_config(config):
    require(config == CONFIG, "fixed preregistered hold-credit train-only comparison required")
    return config


def load_randomized_hold_rows(roots):
    roots = [Path(root).resolve() for root in roots]
    require(
        len(roots) == 2 and len(set(roots)) == 2, "both unique original-source hold training parents required"
    )
    rows, provenance, signatures = [], {}, set()
    for root in roots:
        # Actual complete raw verification, including future-action-free request credit.
        replay.audit_excitation(root)
        p = excitation.validate_excitation(read_json(root / "protocol.json"))
        report = read_json(root / "report.json")
        require(report["excitation_observed"] is True, "actual randomized excitation gate not established")
        provenance[str(root)] = dict(
            manifest_sha256=digest(root / "manifest.json"),
            protocol_sha256=digest(root / "protocol.json"),
            role="train",
        )
        for trial in read_json(root / "runtime.json")["episodes"]:
            if trial["condition"] not in CONFIG["conditions"]:
                continue
            child = root / trial["id"]
            signature = (digest(child / "sender_observations.json"), digest(child / "frame_events.json"))
            require(signature not in signatures, "copied capture aliases cannot add randomized support")
            signatures.add(signature)
            data = read_json(child / "derived.json")["excitation"]
            require(data["credit"] == CONFIG["credit"], "immediate/mixed credit cannot enter hold-skill CV")
            for c in data["cohorts"]:
                require(
                    c["role"] == "train"
                    and not c["future_actions_mixed"]
                    and not c["counterfactual_labels_used"],
                    "factual uncontaminated train cohorts required",
                )
                rows.append(
                    dict(
                        state=c["state"],
                        cap=c["cap"],
                        utility=c["utility"],
                        miss=c["miss"],
                        weight=c["weight"],
                        step=c["step"],
                        episode=digest(root / "manifest.json") + ":" + trial["id"],
                        group=physical_group(p, trial),
                    )
                )
    require(
        len({row["group"] for row in rows}) >= CONFIG["minimum_physical_groups"],
        "eight original physical groups required; repeated aliases are not independence",
    )
    return rows, provenance


def run_hold_value_cv(config, roots, out):
    config_path, out = Path(config).resolve(), Path(out).resolve()
    validate_config(read_json(config_path))
    require(not out.exists() and not out.is_symlink(), "fresh immutable hold-value CV output required")
    rows, provenance = load_randomized_hold_rows(roots)
    out.mkdir(parents=True)
    write_json(out / "config.json", CONFIG)
    write_json(out / "provenance.json", provenance)
    np.savez_compressed(
        out / "train_rows.npz",
        state=np.asarray([r["state"] for r in rows]),
        cap=np.asarray([r["cap"] for r in rows]),
        targets=np.asarray([[r["utility"], r["miss"]] for r in rows]),
        weight=np.asarray([r["weight"] for r in rows]),
        group=np.asarray([r["group"] for r in rows]),
        episode=np.asarray([r["episode"] for r in rows]),
        step=np.asarray([r["step"] for r in rows]),
    )
    # Six entirely NEW conditional folds, once; retain every actual fit for replay.
    conditional = fit_conditional_cv(rows, out / "conditional_models")
    write_json(out / "conditional_cv.json", conditional)
    # Six NEW state-only fits with identical folds/seeds/updates/loss on that corpus.
    comparison = skill.check_action_value_skill(rows, conditional, models_directory=out / "state_only_models")
    report = dict(
        abi=ABI,
        config=copy.deepcopy(CONFIG),
        rows=len(rows),
        requests=sum(r["weight"] for r in rows),
        physical_groups=len({r["group"] for r in rows}),
        conditional_cv=conditional,
        comparison=comparison,
        action_conditioning_skill_passed=comparison["passed"],
        conditional_models_fitted=6,
        state_only_models_fitted=6,
        previous_immediate_horizon_conditional_models_refitted=False,
        deployed_or_candidate_or_selected_risk_weights_changed=False,
        calibration_diagnostic_validation_test_labels_used=False,
        native_deployment_qualified=False,
        causal_effect_proven=False,
        native_improvement_proven=False,
        SOTA_achieved=False,
        config_sha256=digest(config_path),
        implementation_sha256=digest(Path(__file__)),
        source_sha256={
            str(Path(module.__file__).resolve()): digest(Path(module.__file__))
            for module in (learner, excitation, skill, replay)
        },
    )
    write_json(out / "report.json", report)
    seal_directory(
        out,
        [str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()],
        ABI + "_complete",
        SOTA_achieved=False,
    )
    return report


def fit_conditional_cv(rows, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    written = []
    all_groups = sorted({row["group"] for row in rows})

    def recorded(train, seed, updates):
        index = len(written)
        require(
            index < 6
            and seed == learner.LEARNER["model_seeds"][index % 3]
            and updates == learner.LEARNER["cv_updates"],
            "identical prospective conditional folds/seeds/updates required",
        )
        weights, normalization, trace = learner.fit_outcomes(train, seed, updates)
        fit = sorted({row["group"] for row in train})
        held = sorted(set(all_groups) - set(fit))
        fold = index // 3
        require(held == all_groups[fold::2], "conditional fit contains held-out physical groups")
        write_json(
            folder / f"fold-{fold}-seed-{seed}.json",
            dict(
                model_abi="native_hold_conditional_cv_forecaster_v1",
                weights=weights,
                normalization=normalization,
                seed=seed,
                updates=updates,
                fit_groups=fit,
                held_out_groups=held,
                fit_trace=trace,
                native_deployment_qualified=False,
            ),
        )
        written.append((fold, seed))
        return weights, normalization, trace

    cv = FunctionType(
        learner.held_out_training_check.__code__,
        {**learner.held_out_training_check.__globals__, "fit_outcomes": recorded},
        "new_hold_conditional_cv",
    )
    result = cv(rows)
    require(len(written) == 6, "all six conditional fits must be retained")
    return result


def _audit_numeric(root, report):
    with np.load(root / "train_rows.npz", allow_pickle=False) as cache:
        state, target, weight, cap, group = (
            cache[key] for key in ("state", "targets", "weight", "cap", "group")
        )
        groups = sorted(set(group.tolist()))
        require(
            state.shape == (report["rows"], excitation.INPUT_DIM)
            and target.shape == (report["rows"], 2)
            and len(groups) == report["physical_groups"]
            and len(set(zip(cache["episode"].tolist(), cache["step"].tolist(), strict=True))) == len(state)
            and np.isfinite(state).all()
            and np.isfinite(target).all()
            and ((target >= 0) & (target <= 1)).all()
            and (weight > 0).all()
            and np.issubdtype(weight.dtype, np.integer)
            and np.issubdtype(cap.dtype, np.integer)
            and set(cap.tolist()) <= set(excitation.CAPS)
            and int(weight.sum()) == report["requests"],
            "invalid cached factual hold-credit rows",
        )
        require(
            len(report["conditional_cv"]["folds"]) == len(report["comparison"]["folds"]) == 2,
            "complete two-fold hold-credit results required",
        )
        for fold, (conditional, blind) in enumerate(
            zip(report["conditional_cv"]["folds"], report["comparison"]["folds"], strict=True)
        ):
            held = groups[fold::2]
            fit = sorted(set(groups) - set(held))
            mask = np.isin(group, held)
            require(
                conditional["held_out_groups"] == blind["held_out_groups"] == held
                and conditional["fit_groups"] == blind["fit_groups"] == fit,
                "hold-credit fold identity changed",
            )
            mean = state[~mask].mean(axis=0)
            scale = np.maximum(state[~mask].std(axis=0), learner.LEARNER["state_scale_floor"])
            actions = np.asarray(
                [action_features(int(c), s.tolist()) for c, s in zip(cap[mask], state[mask], strict=True)]
            )
            mses = []
            for mode, folder in (("conditional", "conditional_models"), ("blind", "state_only_models")):
                x = np.column_stack(
                    [state[mask], actions if mode == "conditional" else np.zeros_like(actions)]
                )
                predictions = []
                for seed in learner.LEARNER["model_seeds"]:
                    model = read_json(root / folder / f"fold-{fold}-seed-{seed}.json")
                    norm = model["normalization"]
                    require(
                        model["seed"] == seed
                        and model["updates"] == learner.LEARNER["cv_updates"]
                        and model["fit_groups"] == fit
                        and model["held_out_groups"] == held
                        and norm["fitted_roles"] == ["train"]
                        and norm["fused_into_weights"] is True
                        and np.allclose(norm["mean"], mean, atol=1e-12, rtol=0)
                        and np.allclose(norm["scale"], scale, atol=1e-12, rtol=0),
                        "hold-credit normalization/seed/fold leaked or changed",
                    )
                    weights = [np.asarray(p) for p in model["weights"]]
                    require(
                        all(np.isfinite(w).all() for w in weights)
                        and weights[0].shape[0] == excitation.INPUT_DIM + 3
                        and (mode != "blind" or np.all(weights[0][excitation.INPUT_DIM :] == 0)),
                        "hold-credit weights malformed or action-blind control has action dependence",
                    )
                    predictions.append(sigmoid(MLP.from_dict(model["weights"])(x)))
                mse = np.average(
                    (np.mean(predictions, axis=0) - target[mask]) ** 2, axis=0, weights=weight[mask]
                )
                mses.append(mse)
            cmse, bmse = mses
            prior = {}
            for c in set(cap[mask].tolist()):
                selected = (~mask) & (cap == c)
                require(selected.any(), "hold-credit test action has no fit-fold support")
                prior[c] = np.average(target[selected], axis=0, weights=weight[selected])
            baseline = np.asarray([prior[int(c)] for c in cap[mask]])
            pmse = np.average((baseline - target[mask]) ** 2, axis=0, weights=weight[mask])
            utility_skill = float((pmse[0] - cmse[0]) / max(1e-12, float(pmse[0])))
            risk_skill = float((pmse[1] - cmse[1]) / max(1e-12, float(pmse[1])))
            gain = float((bmse[0] - cmse[0]) / max(1e-12, float(bmse[0])))
            expected = {
                "utility_mse": cmse[0],
                "risk_brier": cmse[1],
                "prior_utility_mse": pmse[0],
                "prior_risk_brier": pmse[1],
                "utility_skill": utility_skill,
                "risk_skill": risk_skill,
            }
            require(
                all(
                    np.isclose(conditional[key], value, atol=1e-10, rtol=0) for key, value in expected.items()
                )
                and np.isclose(blind["conditional_utility_mse"], cmse[0], atol=1e-12, rtol=0)
                and np.isclose(blind["state_only_utility_mse"], bmse[0], atol=1e-12, rtol=0)
                and np.isclose(blind["state_only_risk_brier"], bmse[1], atol=1e-12, rtol=0)
                and np.isclose(blind["action_conditioning_utility_skill"], gain, atol=1e-10, rtol=0)
                and blind["passed"] is (gain >= skill.CHECK_CONFIG["min_utility_skill"]),
                "actual saved-weight held-out prediction/prior/MSE/skill mismatch",
            )
        cv_pass = all(
            f["utility_skill"] >= learner.LEARNER["min_utility_skill"] and f["risk_skill"] >= 0
            for f in report["conditional_cv"]["folds"]
        )
        require(
            report["conditional_cv"]["passed"] is cv_pass
            and report["comparison"]["original_proxy_passed"] is cv_pass
            and report["comparison"]["passed"] is all(f["passed"] for f in report["comparison"]["folds"]),
            "new hold-credit proxy or action-skill pass flag mismatch",
        )


def audit_hold_value_cv(root):
    root = Path(root).resolve()
    verify_seal(root, ABI + "_complete")
    report = read_json(root / "report.json")
    validate_config(report["config"])
    require(
        report["implementation_sha256"] == digest(Path(__file__))
        and all(digest(Path(path)) == sha for path, sha in report["source_sha256"].items()),
        "hold-value CV sources changed",
    )
    require(
        report["physical_groups"] >= 8
        and report["conditional_models_fitted"] == 6
        and report["state_only_models_fitted"] == 6
        and report["previous_immediate_horizon_conditional_models_refitted"] is False
        and report["deployed_or_candidate_or_selected_risk_weights_changed"] is False
        and report["calibration_diagnostic_validation_test_labels_used"] is False,
        "hold-value CV must remain factual/train-only/new-fit evidence, not deployment",
    )
    require(
        report["action_conditioning_skill_passed"] is report["comparison"]["passed"],
        "hold-value result changed",
    )
    _audit_numeric(root, report)
    return dict(
        read_only=True,
        numerically_recomputed_folds=2,
        rows=report["rows"],
        physical_groups=report["physical_groups"],
        action_conditioning_skill_passed=report["action_conditioning_skill_passed"],
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_action_hold_value_cv")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--train-run", action="append", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    result = (
        run_hold_value_cv(args.config, args.train_run, args.out)
        if args.command == "run"
        else audit_hold_value_cv(args.run)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
