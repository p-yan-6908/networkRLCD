"""Train-only action-conditioned value skill against an identical action-blind control.

Reuses sealed original conditional CV results, not its action-only prior as a
qualification proxy. Only new state-only models are fitted; no deployed/candidate
weights, risk calibration, labels, roles, defaults or old sources change. Passing
this necessary predictive check is NOT causal identifiability or native gain.
"""

import argparse
import copy
import inspect
import json
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_coverage_learning as augmented
from . import native_action_learning as original
from .native_action_live_study import _candidate
from .native_action_policy import scalar_cap
from .native_protocol import digest, read_json, require, seal_directory, verify_seal, write_json
from .native_repair3_policy import INPUT_DIM
from .networks import MLP, sigmoid

CHECK_ABI = "native_action_conditioned_value_skill_v1"
CHECK_CONFIG = dict(
    abi=CHECK_ABI,
    role="train",
    model_seeds=original.LEARNER["model_seeds"].copy(),
    cv_updates=original.LEARNER["cv_updates"],
    cv_folds=original.LEARNER["cv_folds"],
    min_utility_skill=original.LEARNER["min_utility_skill"],
    action_blind_inputs="three_proposed_action_features_zero; temporal_sender_state_unchanged",
    conditional_results="reuse_original_sealed_same_folds_not_refit",
)


def validate_value_skill_config(config):
    require(config == CHECK_CONFIG, "fixed training-only value-skill configuration required")
    return config


def _state_only_fitter():
    text = inspect.getsource(original.fit_outcomes)
    patches = (
        (
            'a = np.asarray([action_features(r["cap"], r["state"]) for r in rows])',
            "a = np.zeros((len(rows), 3))",
        ),
        ("    net.params = [w, b, v, c]", "    w[INPUT_DIM:] = 0.0\n    net.params = [w, b, v, c]"),
    )
    for old, new in patches:
        require(text.count(old) == 1, "frozen action-blind fitter anchor changed")
        text = text.replace(old, new)
    namespace = dict(original.fit_outcomes.__globals__)
    exec(compile(text, "<isolated_action_blind_fit>", "exec"), namespace)
    return namespace["fit_outcomes"]


_FIT_STATE_ONLY = _state_only_fitter()


def fit_action_blind_outcomes(rows, seed, updates):
    return _FIT_STATE_ONLY(rows, seed, updates)


def load_verified_training_rows(model_directory):
    """Revalidate checksum chains from the already raw-replayed V2 fitting parents.

    Exact original row loaders retain role/schema/source/cap/clock/alias checks.
    Their expensive raw replay callbacks are replaced ONLY by membership in the
    candidate-pinned, fully checksum-verified parents, never by unchecked no-ops.
    """
    directory = Path(model_directory).resolve()
    model = directory / "model.json"
    b = _candidate(dict(path=str(model), sha256=digest(model)))
    require(
        b.get("fitting_interface") == augmented.FITTING_ABI and b.get("learner") == original.LEARNER,
        "original augmented candidate and identical learner required",
    )
    receipt = read_json(directory / "training_report.json")
    roots, bindings, child_count, artifact_count = [], {}, 0, 0
    for name, sha in b["provenance"].items():
        manifest = Path(name)
        require(digest(manifest) == sha, "candidate-pinned parent manifest changed")
        p = read_json(manifest.parent / "protocol.json")
        if p["stage"] != "train":
            continue
        parent = manifest.parent.resolve()
        seal = verify_seal(parent)
        require(seal.get("episodes"), "complete fitting parent child seals required")
        bindings[str(manifest.resolve())] = sha
        artifact_count += len(seal["artifacts_sha256"])
        for child_name, child_sha in seal["episodes"].items():
            child = parent / child_name
            require(digest(child / "manifest.json") == child_sha, "fitting child seal changed")
            artifact_count += len(verify_seal(child)["artifacts_sha256"])
            child_count += 1
        roots.append(parent)
    require(len(roots) == 4, "two original plus two augmented training parents required")
    verified = frozenset(roots)

    def already_verified(root):
        require(Path(root).resolve() in verified, "unverified parent cannot skip prior raw replay")
        return dict(prior_raw_replay_reused=True, checksum_chain_revalidated=True)

    base = FunctionType(
        original.load_role.__code__,
        dict(original.load_role.__globals__, audit_repair_study=already_verified),
        original.load_role.__name__,
        original.load_role.__defaults__,
        original.load_role.__closure__,
    )
    loader = FunctionType(
        augmented.load_augmented_role.__code__,
        dict(augmented.load_augmented_role.__globals__, load_role=base, audit_coverage=already_verified),
        augmented.load_augmented_role.__name__,
        augmented.load_augmented_role.__defaults__,
        augmented.load_augmented_role.__closure__,
    )
    rows, _, _, info = loader(roots, "train")
    require(
        len(rows) == receipt["rows"]["train"]
        and sum(r["weight"] for r in rows) == receipt["requests"]["train"]
        and len({r["group"] for r in rows}) == receipt["physical_groups"]["train"],
        "reconstructed rows/groups/request weights differ from original fit",
    )
    return (
        rows,
        receipt,
        dict(
            parent_manifest_sha256=bindings,
            verified_children=child_count,
            verified_artifact_hashes=artifact_count,
            role="train",
            augmentation=info,
            raw_replay_reused_not_rerun=True,
        ),
    )


def check_action_value_skill(rows, original_cv, *, role="train", models_directory=None):
    require(role == "train", "only original training roles may fit action-blind controls")
    require(
        rows and len({(r["episode"], r["step"]) for r in rows}) == len(rows),
        "unique factual training rows required",
    )
    groups = sorted({r["group"] for r in rows})
    require(len(groups) >= 8, "eight original physical training groups required")
    require(
        type(original_cv.get("passed")) is bool
        and len(original_cv.get("folds", [])) == CHECK_CONFIG["cv_folds"],
        "original sealed two-fold CV evidence required",
    )
    for r in rows:
        scalar_cap(r["cap"])
        require(
            len(r["state"]) == INPUT_DIM
            and np.isfinite(r["state"]).all()
            and all(
                type(r[k]) in (int, float) and np.isfinite(r[k]) and 0 <= r[k] <= 1
                for k in ("utility", "miss")
            )
            and type(r["weight"]) is int
            and r["weight"] > 0,
            "bounded factual targets/state/request weights required",
        )
    folder = None if models_directory is None else Path(models_directory)
    if folder is not None:
        require(
            not folder.exists() and not folder.is_symlink(), "fresh action-blind model directory required"
        )
        folder.mkdir(parents=True)
    folds = []
    for fold, previous in enumerate(original_cv["folds"]):
        held = set(groups[fold :: CHECK_CONFIG["cv_folds"]])
        train = [r for r in rows if r["group"] not in held]
        test = [r for r in rows if r["group"] in held]
        require(
            previous["held_out_groups"] == sorted(held)
            and previous["fit_groups"] == sorted(set(groups) - held),
            "held-out/fit groups differ from sealed conditional CV",
        )
        require(
            type(previous.get("utility_mse")) in (int, float)
            and np.isfinite(previous["utility_mse"])
            and previous["utility_mse"] >= 0,
            "finite conditional CV MSE required",
        )
        members, normalizations = [], []
        for seed in CHECK_CONFIG["model_seeds"]:
            weights, normalization, trace = fit_action_blind_outcomes(train, seed, CHECK_CONFIG["cv_updates"])
            require(
                np.asarray(weights[0])[INPUT_DIM:].shape[0] == 3
                and np.all(np.asarray(weights[0])[INPUT_DIM:] == 0),
                "proposed-action inputs must be completely removed",
            )
            members.append(weights)
            normalizations.append(normalization)
            if folder is not None:
                write_json(
                    folder / f"fold-{fold}-seed-{seed}.json",
                    dict(
                        model_abi="native_action_blind_skill_control_v1",
                        weights=weights,
                        normalization=normalization,
                        seed=seed,
                        updates=CHECK_CONFIG["cv_updates"],
                        fit_groups=sorted(set(groups) - held),
                        held_out_groups=sorted(held),
                        fit_trace=trace,
                        native_deployment_qualified=False,
                    ),
                )
        require(
            all(n == normalizations[0] for n in normalizations), "identical train-only normalization required"
        )
        x = np.asarray([r["state"] + [0.0] * 3 for r in test])
        pred = np.mean([sigmoid(MLP.from_dict(m)(x)) for m in members], axis=0)
        y = np.asarray([[r["utility"], r["miss"]] for r in test])
        mse = np.average((pred - y) ** 2, axis=0, weights=[r["weight"] for r in test])
        gain = float((mse[0] - previous["utility_mse"]) / max(1e-12, float(mse[0])))
        folds.append(
            dict(
                fold=fold,
                held_out_groups=sorted(held),
                fit_groups=sorted(set(groups) - held),
                test_rows=len(test),
                test_requests=sum(r["weight"] for r in test),
                conditional_utility_mse=previous["utility_mse"],
                state_only_utility_mse=float(mse[0]),
                state_only_risk_brier=float(mse[1]),
                action_conditioning_utility_skill=gain,
                passed=gain >= CHECK_CONFIG["min_utility_skill"],
            )
        )
    same = sum(r["cap"] == round(r["state"][-23 + 7] * 4e6) for r in rows)
    return dict(
        check_abi=CHECK_ABI,
        config=copy.deepcopy(CHECK_CONFIG),
        role="train",
        rows=len(rows),
        requests=sum(r["weight"] for r in rows),
        physical_groups=len(groups),
        folds=folds,
        passed=all(f["passed"] for f in folds),
        original_proxy_passed=original_cv["passed"],
        factual_action_equals_previous_own_cap_rows=same,
        factual_action_equals_own_fraction=same / len(rows),
        conditional_models_refitted=False,
        state_only_models_fitted=len(folds) * len(CHECK_CONFIG["model_seeds"]),
        calibration_selected_diagnostic_validation_test_labels_used=False,
        necessary_predictive_check_not_causal_certificate=True,
        native_improvement_proven=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def require_action_value_skill(report):
    require(
        report.get("check_abi") == CHECK_ABI
        and report.get("config") == CHECK_CONFIG
        and report.get("role") == "train"
        and report.get("passed") is True
        and report.get("physical_groups", 0) >= 8
        and len(report.get("folds", [])) == CHECK_CONFIG["cv_folds"]
        and all(
            f.get("passed") is True
            and f["action_conditioning_utility_skill"] >= CHECK_CONFIG["min_utility_skill"]
            for f in report["folds"]
        ),
        "action-conditioned utility skill is not established",
    )
    return report


def run_value_skill_audit(model_directory, config, out):
    config_path, out = Path(config).resolve(), Path(out).resolve()
    validate_value_skill_config(read_json(config_path))
    require(not out.exists() and not out.is_symlink(), "immutable fresh value-skill output required")
    rows, original_receipt, provenance = load_verified_training_rows(model_directory)
    print(
        f"Reconstructed {len(rows)} train-only rows; reusing conditional CV, fitting six new action-blind controls",
        flush=True,
    )
    out.mkdir(parents=True)
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
    write_json(out / "provenance.json", provenance)
    report = check_action_value_skill(rows, original_receipt["training_cv"], models_directory=out / "models")
    model_directory = Path(model_directory).resolve()
    report.update(
        original_model_sha256=digest(model_directory / "model.json"),
        original_training_report_sha256=digest(model_directory / "training_report.json"),
        config_sha256=digest(config_path),
        implementation_sha256=digest(Path(__file__)),
        source_sha256={
            str(Path(original.__file__).resolve()): digest(Path(original.__file__)),
            str(Path(augmented.__file__).resolve()): digest(Path(augmented.__file__)),
        },
    )
    write_json(out / "report.json", report)
    seal_directory(
        out,
        [str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()],
        "native_action_value_skill_complete",
        goal_achieved=False,
        SOTA_achieved=False,
    )
    return report


def audit_value_skill(root):
    root = Path(root).resolve()
    verify_seal(root, "native_action_value_skill_complete")
    r = read_json(root / "report.json")
    validate_value_skill_config(r["config"])
    require(
        r["implementation_sha256"] == digest(Path(__file__))
        and all(digest(Path(p)) == sha for p, sha in r["source_sha256"].items()),
        "audited skill source changed",
    )
    require(
        r["rows"] > 0
        and r["physical_groups"] >= 8
        and r["role"] == "train"
        and r["conditional_models_refitted"] is False
        and r["state_only_models_fitted"] == 6
        and r["calibration_selected_diagnostic_validation_test_labels_used"] is False,
        "necessary predictive audit cannot claim refitting, leakage or native gain",
    )
    require(
        r["passed"] is all(f["passed"] for f in r["folds"])
        and all(
            f["passed"] is (f["action_conditioning_utility_skill"] >= CHECK_CONFIG["min_utility_skill"])
            for f in r["folds"]
        ),
        "value-skill threshold/result changed",
    )
    return dict(
        read_only=True,
        rows=r["rows"],
        groups=r["physical_groups"],
        passed=r["passed"],
        conditional_models_refitted=False,
        native_improvement_proven=False,
        SOTA_achieved=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_action_value_skill")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "run", help="original train-only action-blind CV comparison; no candidate refit"
    )
    run.add_argument("--model-dir", required=True)
    run.add_argument("--config", required=True)
    run.add_argument("--out", required=True)
    audit = commands.add_parser("audit", help="read-only value-skill artifact and scope audit")
    audit.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    result = (
        run_value_skill_audit(args.model_dir, args.config, args.out)
        if args.command == "run"
        else audit_value_skill(args.run)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
