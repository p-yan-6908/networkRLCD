"""Fixed once-only combined train CV: balanced new data, never independent validation."""

import argparse
import copy
import json
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_late_forecast as frozen
from .native_action_learning import physical_group
from .native_protocol import digest, read_json, require, seal_directory, verify_seal, write_json
from .networks import MLP

ABI = "native_balanced_combined_late_value_cv_v2"
MODEL_ABI = ABI + "_auxiliary"
RECIPE = {**copy.deepcopy(frozen.RECIPE), "abi": MODEL_ABI}
CONTRACT = dict(
    abi=ABI,
    role="train",
    model_recipe=RECIPE,
    old_train_manifest_sha256=frozen.SOURCE_MANIFEST,
    old_physical_folds_unchanged=True,
    new_fold_rule="(family_index_stable0_collapse1+film_index_sintel0_bbb1)%2",
    expected_old_rows=160,
    expected_new_rows=120,
    expected_combined_rows=280,
    expected_physical_groups=12,
    minimum_action_utility_skill=0.01,
    minimum_prior_utility_skill=0.01,
    minimum_prior_risk_skill=0.0,
    both_original_extended_folds_required=True,
    new_balanced_only_and_each_film_action_skill_required=True,
    cluster_bootstrap_seed=88801,
    cluster_bootstrap_resamples=1024,
    cluster_ci95_lower_above_zero_required=True,
    no_validation_calibration_or_diagnostic_labels=True,
    training_development_only=True,
    no_new_hyperparameter_or_window_search=True,
    native_deployment_qualified=False,
    SOTA_achieved=False,
)
_NS = {**frozen.FIT.__globals__, "ABI": MODEL_ABI, "CONFIG": RECIPE}
FIT = FunctionType(frozen.FIT.__code__, _NS, "fit_balanced_combined", frozen.FIT.__defaults__)
PREDICT = FunctionType(frozen.PREDICT.__code__, _NS, "predict_balanced_combined")


def _load(source, full_native=True):
    from . import native_action_balanced_matrix as matrix

    source = Path(source).resolve()
    verify_seal(source, matrix.ABI + "_complete")
    cfg = read_json(source / "protocol.json")
    runtimes = matrix.validate_plan(cfg)
    if full_native:
        matrix.audit_matrix(source)
    old_root, old = frozen.training_source(cfg["old_train"]["path"])
    old_report = read_json(old_root / "report.json")
    old_films = {}
    for parent in old_report["provenance"]:
        p = read_json(Path(parent) / "runtime.json")
        film = (
            "sintel" if p["video_source"]["sha256"] == runtimes["sintel"]["video_source"]["sha256"] else "tos"
        )
        for t in p["episodes"]:
            old_films[physical_group(p, t)] = film
    rows = []
    for film, p in runtimes.items():
        for t in p["episodes"]:
            if t["condition"] == "fixed450":
                continue
            d = read_json(source / film / t["id"] / "derived.json")["late_credit"]
            require(d["credit"] == cfg["credit"], "exact same late credit required")
            for c in d["cohorts"]:
                require(
                    c["role"] == "train"
                    and not c["future_actions_mixed"]
                    and not c["counterfactual_labels_used"]
                    and c["target_status_not_used_to_filter"] is True,
                    "only factual train rows/no target filtering required",
                )
                rows.append(
                    dict(
                        state=c["state"],
                        cap=c["cap"],
                        targets=[c["utility"], c["miss"]],
                        weight=c["weight"],
                        group=physical_group(p, t),
                        episode=digest(source / "manifest.json") + ":" + t["id"],
                        step=c["step"],
                        film=film,
                    )
                )
    new = {k: np.asarray([r[k] for r in rows], dtype=old[k].dtype) for k in old}
    data = {k: np.concatenate([old[k], new[k]]) for k in old}
    data["film"] = np.asarray([old_films[g] for g in old["group"]] + [r["film"] for r in rows])
    data["new_balanced"] = np.asarray([False] * len(old["cap"]) + [True] * len(rows))
    require(
        len(rows) == 120
        and data["state"].shape == (280, 736)
        and data["targets"].shape == (280, 2)
        and len(set(data["group"].tolist())) == 12
        and set(data["group"].tolist()) == set(cfg["physical_fold_map"]),
        "exact original+new legal rows/groups/folds required",
    )
    require(
        np.isfinite(data["state"]).all()
        and np.isfinite(data["targets"]).all()
        and ((data["targets"] >= 0) & (data["targets"] <= 1)).all()
        and (data["weight"] > 0).all(),
        "all bounded finite factual outcomes and positive request weights required",
    )
    return data, cfg


def _skill(model, baseline):
    return float(1 - model / baseline) if baseline > 1e-12 else 0.0


def _scores(target, prediction, blind, prior, weight, mask):
    require(mask.any(), "every fixed comparison stratum must have rows")
    c = np.average((prediction[mask] - target[mask]) ** 2, axis=0, weights=weight[mask])
    b = np.average((blind[mask] - target[mask]) ** 2, axis=0, weights=weight[mask])
    p = np.average((prior[mask] - target[mask]) ** 2, axis=0, weights=weight[mask])
    return dict(
        rows=int(mask.sum()),
        requests=int(weight[mask].sum()),
        conditional_utility_mse=float(c[0]),
        blind_utility_mse=float(b[0]),
        prior_utility_mse=float(p[0]),
        conditional_miss_fraction_mse=float(c[1]),
        blind_miss_fraction_mse=float(b[1]),
        prior_miss_fraction_mse=float(p[1]),
        action_utility_skill=_skill(c[0], b[0]),
        prior_utility_skill=_skill(c[0], p[0]),
        prior_risk_skill=_skill(c[1], p[1]),
    )


def _check_model(m, data, fit, held, seed, blind):
    require(
        m["abi"] == MODEL_ABI
        and m["recipe"] == RECIPE
        and m["seed"] == seed
        and m["blind"] is blind
        and m["updates"] == 1200
        and m["fit_groups"] == sorted(set(data["group"][fit].tolist()))
        and m["held_out_groups"] == held
        and m["normalization"]["fitted_roles"] == ["train"]
        and m["training_credit"] == frozen.CONFIG["credit"]
        and m["native_deployment_qualified"] is False,
        "fixed actual train-only auxiliary model provenance required",
    )
    shapes = [(95, 8), (8,), (8, 2), (2,)]
    require(
        [np.asarray(w).shape for w in m["weights"]] == shapes
        and all(np.isfinite(w).all() for w in map(np.asarray, m["weights"])),
        "786-parameter actual finite network required",
    )
    raw = frozen.development.neural.design(data["state"][fit], data["cap"][fit], blind)
    mean = raw.mean(axis=0)
    scale = np.maximum(raw.std(axis=0), 0.05)
    require(
        np.allclose(m["normalization"]["mean"], mean, rtol=0, atol=1e-12)
        and np.allclose(m["normalization"]["scale"], scale, rtol=0, atol=1e-12),
        "fit-fold-only normalization required",
    )
    if blind:
        require(np.all(np.asarray(m["weights"][0])[-3:] == 0), "blind acquired action weights")
    prediction = PREDICT(m, data["state"], data["cap"])
    require(
        np.isfinite(prediction).all() and ((prediction >= 0) & (prediction <= 1)).all(),
        "finite bounded actual predictions required",
    )
    mse = float(np.average((prediction[fit, 0] - data["targets"][fit, 0]) ** 2, weights=data["weight"][fit]))
    logits = MLP.from_dict(m["weights"])((raw - mean) / scale)
    ll = float(
        np.average(
            np.logaddexp(0, logits[:, 1]) - data["targets"][fit, 1] * logits[:, 1],
            weights=data["weight"][fit],
        )
    )
    require(
        m["fit_trace"][-1]["update"] == 1199
        and abs(m["fit_trace"][-1]["utility_mse"] - mse) < 1e-12
        and abs(m["fit_trace"][-1]["miss_log_loss"] - ll) < 1e-12,
        "actual saved neural loss trace mismatch",
    )
    return prediction


def evaluate(data, fold_map, models):
    oof = {mode: np.zeros_like(data["targets"]) for mode in ("conditional", "blind")}
    prior = np.zeros_like(data["targets"])
    folds = []
    for fold in range(2):
        held = sorted(g for g, i in fold_map.items() if i == fold)
        test = np.isin(data["group"], held)
        fit = ~test
        require(
            set(data["cap"][fit].tolist()) == {300000, 450000, 900000}, "every fit fold needs all actions"
        )
        prediction = {
            mode: np.mean(
                [
                    _check_model(m, data, fit, held, seed, mode == "blind")
                    for m, seed in zip(models[fold][mode], RECIPE["model_seeds"], strict=True)
                ],
                axis=0,
            )
            for mode in ("conditional", "blind")
        }
        priors = {
            c: np.average(
                data["targets"][fit & (data["cap"] == c)],
                axis=0,
                weights=data["weight"][fit & (data["cap"] == c)],
            )
            for c in (300000, 450000, 900000)
        }
        prior[test] = np.asarray([priors[c] for c in data["cap"][test]])
        for mode in oof:
            oof[mode][test] = prediction[mode][test]
        folds.append(
            dict(
                fold=fold,
                held_out_groups=held,
                fit_groups=sorted(set(data["group"][fit].tolist())),
                **_scores(
                    data["targets"],
                    prediction["conditional"],
                    prediction["blind"],
                    prior,
                    data["weight"],
                    test,
                ),
            )
        )
    masks = [
        ("pooled", np.ones(len(data["cap"]), dtype=bool)),
        ("new_balanced_only", data["new_balanced"]),
        *[(film, data["film"] == film) for film in ("sintel", "tos", "bbb")],
    ]
    metrics = {
        name: _scores(data["targets"], oof["conditional"], oof["blind"], prior, data["weight"], mask)
        for name, mask in masks
    }
    groups = sorted(set(data["group"].tolist()))
    sums = []
    for g in groups:
        ix = data["group"] == g
        sums.append(
            [
                float(np.sum(data["weight"][ix] * (oof[mode][ix, 0] - data["targets"][ix, 0]) ** 2))
                for mode in ("conditional", "blind")
            ]
        )
    sums = np.asarray(sums)
    rng = np.random.default_rng(CONTRACT["cluster_bootstrap_seed"])
    skills = []
    for _ in range(CONTRACT["cluster_bootstrap_resamples"]):
        sample = sums[rng.integers(0, len(groups), size=len(groups))].sum(axis=0)
        skills.append(_skill(sample[0], sample[1]))
    ci = np.quantile(skills, [0.025, 0.975]).tolist()
    gate = (
        all(x["action_utility_skill"] >= 0.01 for x in [*folds, *metrics.values()])
        and all(
            x["prior_utility_skill"] >= 0.01 and x["prior_risk_skill"] >= 0
            for x in [*folds, *metrics.values()]
        )
        and ci[0] > 0
    )
    return (
        dict(
            folds=folds,
            metrics=metrics,
            physical_group_action_skill_ci95=ci,
            cluster_resamples=1024,
            training_action_information_passed=bool(gate),
            miss_fraction_mse_not_request_brier_or_selected_confidence=True,
        ),
        oof,
        prior,
    )


def _report(data, cfg, evaluation, source):
    return dict(
        abi=ABI,
        contract=CONTRACT,
        source=dict(path=str(Path(source).resolve()), manifest_sha256=digest(Path(source) / "manifest.json")),
        old_train=cfg["old_train"],
        rows=len(data["cap"]),
        requests=int(data["weight"].sum()),
        physical_groups=12,
        forecasters_fitted=12,
        evaluation=evaluation,
        implementation_sha256=digest(__file__),
        original_fitter_sha256=digest(frozen.development.neural.__file__),
        training_development_only=True,
        no_validation_labels_used=True,
        no_original_models_refitted=True,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def fit_cv(source, out):
    data, cfg = _load(source)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "contract.json", CONTRACT)
    np.savez_compressed(out / "train_rows.npz", **data)
    models = {}
    for fold in range(2):
        held = sorted(g for g, i in cfg["physical_fold_map"].items() if i == fold)
        fit = ~np.isin(data["group"], held)
        models[fold] = {}
        for mode in ("conditional", "blind"):
            members = []
            for seed in RECIPE["model_seeds"]:
                m = FIT(
                    data["state"][fit],
                    data["cap"][fit],
                    data["targets"][fit],
                    data["weight"][fit],
                    data["group"][fit],
                    seed,
                    mode == "blind",
                )
                m.update(held_out_groups=held, training_credit=frozen.CONFIG["credit"], recipe=RECIPE)
                path = out / "models" / f"fold-{fold}-{mode}-seed-{seed}.json"
                path.parent.mkdir(exist_ok=True)
                write_json(path, m)
                members.append(m)
            models[fold][mode] = members
    evaluation, oof, prior = evaluate(data, cfg["physical_fold_map"], models)
    np.savez_compressed(out / "held_predictions.npz", **oof, prior=prior)
    report = _report(data, cfg, evaluation, source)
    write_json(out / "report.json", report)
    seal_directory(
        out,
        sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()),
        ABI + "_complete",
        SOTA_achieved=False,
    )
    return report


def audit_cv(out):
    from . import native_action_balanced_matrix as matrix

    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    report = read_json(out / "report.json")
    require(
        read_json(out / "contract.json") == CONTRACT
        and report["implementation_sha256"] == digest(__file__)
        and report["original_fitter_sha256"] == digest(frozen.development.neural.__file__),
        "exact fixed numerical recipe source required",
    )
    source = Path(report["source"]["path"])
    require(
        digest(source / "manifest.json") == report["source"]["manifest_sha256"],
        "actual source manifest changed",
    )
    data, cfg = _load(source, False)
    with np.load(out / "train_rows.npz", allow_pickle=False) as cache:
        require(
            set(cache.files) == set(data) and all(np.array_equal(cache[k], v) for k, v in data.items()),
            "canonical old+new source cache changed",
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
            "every actual OOF/model/prior prediction changed",
        )
    require(report == _report(data, cfg, evaluation, source), "actual metrics/folds/bootstraps/flags changed")
    matrix.audit_matrix(source)
    return dict(
        read_only=True,
        actual_forecasters=12,
        rows=280,
        requests=report["requests"],
        physical_groups=12,
        complete_new_native_sources_replayed=True,
        old_raw_replay_reused_only_through_fixed_external_d33_receipt=True,
        all_actual_numeric_folds_predictions_recomputed=True,
        training_action_information_passed=evaluation["training_action_information_passed"],
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_balanced_value_cv")
    sub = p.add_subparsers(dest="command", required=True)
    fit = sub.add_parser("fit")
    fit.add_argument("--source", required=True)
    fit.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "fit":
        r = fit_cv(a.source, a.out)
        result = dict(
            rows=r["rows"],
            requests=r["requests"],
            evaluation=r["evaluation"],
            native_deployment_qualified=False,
            SOTA_achieved=False,
        )
    else:
        result = audit_cv(a.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
