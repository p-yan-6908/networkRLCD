"""Single predeclared ordered-feature ablation; train only, never a native actor."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np

from . import native_action_atomic_matrix as matrix
from . import native_action_atomic_portable_audit as portable
from . import native_action_atomic_value_cv as atomic
from . import native_action_balanced_value_cv as base
from . import native_action_ordered_projection as ordered
from . import networks
from .native_protocol import digest, read_json, require, seal_directory, verify_seal, write_json

ABI = "native_ordered_atomic_train_value_cv_v1"
MODEL_ABI = ABI + "_auxiliary"
SOURCE_SHA = "25cd60b661c0f1a0fa26f71b876ae7299ebcd1de2c49f63e10cd8321b06b5a28"
BASELINE_SHA = "7b9c9d2ca80ed97ed81dced89dbb4e009b4640a788a3a36dbc57632625c3a36c"
RECIPE = {
    **copy.deepcopy(base.RECIPE),
    "abi": MODEL_ABI,
    "projection": ordered.CONTRACT["projection"],
    "compact_dim": ordered.COMPACT_DIM,
    "ordered_initialization": "original_seeded_95_network_plus_23_zero_trend_rows;no_extra_RNG_draws",
}
CONTRACT = {
    **copy.deepcopy(base.CONTRACT),
    "abi": ABI,
    "model_recipe": RECIPE,
    "feature_contract": ordered.CONTRACT,
    "input_dim": 118,
    "parameters": 970,
    "initial_92_summary_action_weights_heads_biases_and_minibatch_RNG_preserved": True,
    "single_predeclared_feature_ablation_no_sweep": True,
    "same_sample_index_features_not_elapsed_time": True,
    "original_95_models_not_refitted": True,
    "source_manifest_sha256": SOURCE_SHA,
    "baseline_cv_manifest_sha256": BASELINE_SHA,
    "training_recipe_and_reused_folds_not_independent_validation": True,
}


class OrderedMLP(networks.MLP):
    """Add learnable paths without moving the fixed initial weights or RNG stream."""

    def __init__(self, inputs, hidden, outputs, rng):
        require((inputs, hidden, outputs) == (118, 8, 2), "fixed ordered network geometry required")
        super().__init__(95, hidden, outputs, rng)
        self.params[0] = np.vstack([self.params[0][:92], np.zeros((23, hidden)), self.params[0][-3:]])
        self.m[0] = np.zeros_like(self.params[0])
        self.v[0] = np.zeros_like(self.params[0])


_FIT_NS = {
    **base.FIT.__globals__,
    "ABI": MODEL_ABI,
    "CONFIG": RECIPE,
    "COMPACT_DIM": ordered.COMPACT_DIM,
    "design": ordered.design,
    "MLP": OrderedMLP,
}
FIT = FunctionType(base.FIT.__code__, _FIT_NS, "fit_fixed_ordered", base.FIT.__defaults__)
_PREDICT_NS = {
    **base.PREDICT.__globals__,
    "ABI": MODEL_ABI,
    "COMPACT_DIM": ordered.COMPACT_DIM,
    "design": ordered.design,
}
PREDICT = FunctionType(base.PREDICT.__code__, _PREDICT_NS, "predict_fixed_ordered")
_NEURAL = SimpleNamespace(**{**base.frozen.development.neural.__dict__, "design": ordered.design})
_DEVELOPMENT = SimpleNamespace(**{**base.frozen.development.__dict__, "neural": _NEURAL})
_FROZEN = SimpleNamespace(**{**base.frozen.__dict__, "development": _DEVELOPMENT})
_CHECK_NS = {**base.__dict__, "MODEL_ABI": MODEL_ABI, "RECIPE": RECIPE, "PREDICT": PREDICT, "frozen": _FROZEN}
_code = base._check_model.__code__
_OLD_GEOMETRY = ((95, 8), (8,), (8, 2), (2,))
require(_code.co_consts.count(_OLD_GEOMETRY) == 1, "unique original input geometry guard required")
_CHECK_CODE = _code.replace(
    co_consts=tuple(
        ((118, 8), (8,), (8, 2), (2,))
        if c == _OLD_GEOMETRY
        else "970-parameter actual finite network required"
        if c == "786-parameter actual finite network required"
        else c
        for c in _code.co_consts
    )
)
_check_model = FunctionType(_CHECK_CODE, _CHECK_NS, "check_ordered_actual_model")
_EVAL_NS = {**base.__dict__, "CONTRACT": CONTRACT, "RECIPE": RECIPE, "_check_model": _check_model}
evaluate = FunctionType(base.evaluate.__code__, _EVAL_NS, "evaluate_fixed_ordered")


def implementation_dependencies():
    result = {Path(p).name: s for p, s in matrix._dependencies(atomic).items()}
    for m in (ordered, portable, networks, base.frozen.development):
        result[Path(m.__file__).name] = digest(m.__file__)
    result[Path(__file__).name] = digest(__file__)
    return result


def row_fingerprint(data):
    h = hashlib.sha256()
    for k, v in sorted(data.items()):
        h.update(
            json.dumps(
                [k, str(v.dtype), v.shape, v.tolist()], separators=(",", ":"), allow_nan=False
            ).encode()
        )
    return h.hexdigest()


def make_plan(source, baseline, full_native=False):
    source, baseline = Path(source).resolve(), Path(baseline).resolve()
    require(
        digest(source / "manifest.json") == SOURCE_SHA and digest(baseline / "manifest.json") == BASELINE_SHA,
        "exact immutable atomic training source and original 95-input comparison required",
    )
    verify_seal(baseline, atomic.ABI + "_complete")
    if full_native:
        portable.audit_cv(baseline)
    data, cfg = portable.LOAD(source, False)
    with np.load(baseline / "train_rows.npz", allow_pickle=False) as cached:
        require(
            set(cached.files) == set(data) and all(np.array_equal(cached[k], v) for k, v in data.items()),
            "every original state/target/cap/weight/fold/episode identity must remain identical",
        )
    plan = dict(
        abi=ABI + "_predeclared",
        contract=CONTRACT,
        source=dict(
            path=str(source), manifest_sha256=SOURCE_SHA, protocol_sha256=digest(source / "protocol.json")
        ),
        baseline=dict(path=str(baseline), manifest_sha256=BASELINE_SHA),
        implementation_dependencies_sha256=implementation_dependencies(),
        canonical_row_fingerprint=row_fingerprint(data),
        physical_fold_map=cfg["physical_fold_map"],
        all_prior_role_inputs_sha256=cfg["excluded_inputs_sha256"],
        rows=280,
        requests=int(data["weight"].sum()),
        physical_groups=12,
        new_models=12,
        prospective_before_any_new_model_fit=True,
        no_validation_calibration_or_diagnostic_targets=True,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    return plan, data, cfg


def validate_plan(plan):
    require(
        plan.get("abi") == ABI + "_predeclared" and plan.get("contract") == CONTRACT,
        "sole fixed ordered feature ablation contract required",
    )
    expected, data, cfg = make_plan(plan["source"]["path"], plan["baseline"]["path"])
    require(plan == expected, "exact prospective source/code/rows/physical folds/roles recipe required")
    return data, cfg


def predeclare(source, baseline, out):
    require(not Path(out).exists(), "immutable prospective plan already exists")
    plan, _, _ = make_plan(source, baseline, True)
    write_json(out, plan)
    return dict(
        predeclared_sha256=digest(out), new_fits=0, fixed_input_dim=118, native_deployment_qualified=False
    )


def model_for_fold(data, cfg, fold, mode, seed):
    held = sorted(g for g, i in cfg["physical_fold_map"].items() if i == fold)
    fit = ~np.isin(data["group"], held)
    model = FIT(
        *(data[k][fit] for k in ("state", "cap", "targets", "weight", "group")), seed, mode == "blind"
    )
    model.update(held_out_groups=held, training_credit=base.frozen.CONFIG["credit"], recipe=RECIPE)
    return model


def paired_comparison(plan, evaluation):
    old = read_json(Path(plan["baseline"]["path"]) / "report.json")["evaluation"]
    return dict(
        exact_95_input_reference_manifest_sha256=BASELINE_SHA,
        old_models_refitted=0,
        no_hyperparameter_selection_or_native_promotion=True,
        pooled_action_utility_skill_delta=evaluation["metrics"]["pooled"]["action_utility_skill"]
        - old["metrics"]["pooled"]["action_utility_skill"],
        strata={
            name: dict(
                original_action_utility_skill=old["metrics"][name]["action_utility_skill"],
                ordered_action_utility_skill=score["action_utility_skill"],
                conditional_utility_mse_delta=score["conditional_utility_mse"]
                - old["metrics"][name]["conditional_utility_mse"],
            )
            for name, score in evaluation["metrics"].items()
        },
        original_training_action_information_passed=old["training_action_information_passed"],
        ordered_training_action_information_passed=evaluation["training_action_information_passed"],
        feature_function_is_not_a_fitted_model_or_native_actor=True,
    )


def report_for(plan, data, evaluation, plan_sha):
    return dict(
        abi=ABI,
        contract=CONTRACT,
        predeclared_plan_sha256=plan_sha,
        source=plan["source"],
        baseline=plan["baseline"],
        implementation_dependencies_sha256=implementation_dependencies(),
        canonical_row_fingerprint=row_fingerprint(data),
        rows=280,
        requests=int(data["weight"].sum()),
        physical_groups=12,
        forecasters_fitted=12,
        lossless_unique_episode_ids=len(set(data["episode"].tolist())),
        evaluation=evaluation,
        paired_95_input_comparison=paired_comparison(plan, evaluation),
        original_weight_initialization_and_group_row_minibatch_RNG_stream_preserved=True,
        normalization_fit_fold_only=True,
        no_new_targets_or_observation_schema=True,
        original_models_and_data_untouched=True,
        no_validation_labels_used=True,
        training_development_only=True,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def artifact_names():
    return [
        "predeclared.json",
        "contract.json",
        "train_rows.npz",
        "held_predictions.npz",
        "report.json",
        *[
            f"models/fold-{fold}-{mode}-seed-{seed}.json"
            for fold in range(2)
            for mode in ("conditional", "blind")
            for seed in RECIPE["model_seeds"]
        ],
    ]


def fit_cv(plan_path, out):
    plan = read_json(plan_path)
    data, cfg = validate_plan(plan)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "predeclared.json", plan)
    require(
        digest(out / "predeclared.json") == digest(plan_path),
        "exact prospective original plan bytes required",
    )
    write_json(out / "contract.json", CONTRACT)
    np.savez_compressed(out / "train_rows.npz", **data)
    models = {}
    for fold in range(2):
        models[fold] = {}
        for mode in ("conditional", "blind"):
            models[fold][mode] = []
            for seed in RECIPE["model_seeds"]:
                model = model_for_fold(data, cfg, fold, mode, seed)
                path = out / "models" / f"fold-{fold}-{mode}-seed-{seed}.json"
                path.parent.mkdir(exist_ok=True)
                write_json(path, model)
                models[fold][mode].append(model)
    evaluation, oof, prior = evaluate(data, cfg["physical_fold_map"], models)
    np.savez_compressed(out / "held_predictions.npz", **oof, prior=prior)
    report = report_for(plan, data, evaluation, digest(plan_path))
    write_json(out / "report.json", report)
    seal_directory(out, artifact_names(), ABI + "_complete", SOTA_achieved=False)
    return report


def audit_cv(out):
    out = Path(out).resolve()
    seal = verify_seal(out, ABI + "_complete")
    require(
        set(seal["artifacts_sha256"]) == set(artifact_names()) and seal.get("SOTA_achieved") is False,
        "exact complete twelve-model ordered ablation layout required",
    )
    report, plan = read_json(out / "report.json"), read_json(out / "predeclared.json")
    require(
        report.get("native_deployment_qualified") is False and report.get("SOTA_achieved") is False,
        "training forecast ablation is not native/SOTA qualification",
    )
    require(
        read_json(out / "contract.json") == CONTRACT and report.get("contract") == CONTRACT,
        "fixed feature-only recipe/criterion contract required",
    )
    data, cfg = validate_plan(plan)
    require(
        digest(out / "predeclared.json") == report["predeclared_plan_sha256"],
        "prospective plan bytes changed",
    )
    with np.load(out / "train_rows.npz", allow_pickle=False) as cache:
        require(
            set(cache.files) == set(data) and all(np.array_equal(cache[k], v) for k, v in data.items()),
            "exact lossless canonical training arrays required",
        )
    models = {
        fold: {
            mode: [
                read_json(out / "models" / f"fold-{fold}-{mode}-seed-{seed}.json")
                for seed in RECIPE["model_seeds"]
            ]
            for mode in ("conditional", "blind")
        }
        for fold in range(2)
    }
    evaluation, oof, prior = evaluate(data, cfg["physical_fold_map"], models)
    with np.load(out / "held_predictions.npz", allow_pickle=False) as cache:
        require(
            set(cache.files) == {"conditional", "blind", "prior"}
            and all(np.array_equal(cache[k], v) for k, v in {**oof, "prior": prior}.items()),
            "all actual held-out ensemble and fit-only prior predictions required",
        )
    require(
        report == report_for(plan, data, evaluation, digest(out / "predeclared.json")),
        "every numerical fold/film/group bootstrap/comparison/flag required",
    )
    for fold, modes in models.items():
        for mode, members in modes.items():
            for seed, model in zip(RECIPE["model_seeds"], members, strict=True):
                require(
                    model == model_for_fold(data, cfg, fold, mode, seed),
                    "every actual fixed 1200-update weight/normalizer/full loss trace must reproduce",
                )
    portable.audit_matrix(plan["source"]["path"])
    return dict(
        read_only=True,
        actual_forecasters=12,
        exact_fixed_training_replays=12,
        rows=280,
        requests=report["requests"],
        physical_groups=12,
        input_dim=118,
        every_model_weight_full_trace_normalizer_OOF_and_fixed_gate_recomputed=True,
        training_action_information_passed=evaluation["training_action_information_passed"],
        no_original_95_models_refitted=True,
        new_captures=0,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_action_ordered_value_cv")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("predeclare")
    p.add_argument("--source", required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("fit")
    p.add_argument("--plan", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("audit")
    p.add_argument("--run", required=True)
    args = parser.parse_args()
    if args.command == "predeclare":
        result = predeclare(args.source, args.baseline, args.out)
    elif args.command == "fit":
        report = fit_cv(args.plan, args.out)
        result = dict(
            rows=report["rows"],
            requests=report["requests"],
            evaluation=report["evaluation"],
            native_deployment_qualified=False,
            SOTA_achieved=False,
        )
    else:
        result = audit_cv(args.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
