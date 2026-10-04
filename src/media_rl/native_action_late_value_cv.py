"""Fresh late-credit compact neural action-value comparison, no native promotion."""

import argparse
import copy
import json
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_compact_hold_cv as neural
from . import native_action_settled_hold as collection
from .native_action_learning import physical_group
from .native_protocol import digest, read_json, require, seal_directory, verify_seal, write_json

ABI = "native_fresh_late_credit_action_skill_cv_v2"
MODEL_ABI = ABI + "_auxiliary_forecaster"
MODEL_RECIPE = {
    k: copy.deepcopy(v) for k, v in neural.CONFIG.items() if k not in ("abi", "source_cv_manifest_sha256")
}
MODEL_RECIPE["abi"] = MODEL_ABI
CONFIG = dict(
    abi=ABI,
    role="train",
    credit=collection.CREDIT,
    conditions=["random-hold-a", "random-hold-b"],
    minimum_physical_groups=8,
    model_recipe=MODEL_RECIPE,
    original_physical_fold_reference_manifest_sha256="5cafe0fdff1a6c3527848cfd27f0d4dc1db4c754a44c3931327dde0abc7966e0",
    source_collector_sha256=digest(collection.__file__),
    neural_recipe_source_sha256=digest(neural.__file__),
    target_attainment_cannot_filter_or_enter_state=True,
    prior_models_refitted=False,
    training_development_only_not_independent_validation=True,
    minimum_action_utility_skill=0.01,
    SOTA_achieved=False,
)
_NS = {**neural.__dict__, "ABI": MODEL_ABI, "CONFIG": MODEL_RECIPE}
FIT = FunctionType(
    neural.fit_forecaster.__code__, _NS, "fit_fresh_late_forecaster", neural.fit_forecaster.__defaults__
)
PREDICT = FunctionType(neural.predict.__code__, _NS, "predict_fresh_late_forecaster")
METRICS = FunctionType(neural.fold_metrics.__code__, {**_NS, "predict": PREDICT}, "fresh_late_fold_metrics")


def validate_config(cfg):
    require(cfg == CONFIG, "fixed once-only fresh late-credit training neural comparison required")


def load_late_rows(roots, full_native_replay=True):
    require(
        len(roots) == 2 and len({str(Path(p).resolve()) for p in roots}) == 2,
        "both unique source-film late training parents required",
    )
    rows = []
    provenance = {}
    signatures = set()
    for source in roots:
        root = Path(source).resolve()
        verify_seal(root, collection.ABI + "_complete")
        if full_native_replay:
            collection.audit_settled_hold(root)
        cfg = read_json(root / "protocol.json")
        p = collection.validate_config(cfg)
        report = read_json(root / "report.json")
        require(
            report["seeded_support_established"] is True
            and report["target_attainment_is_not_eligibility"] is True,
            "all real cap support/no target selection required",
        )
        provenance[str(root)] = dict(
            manifest_sha256=digest(root / "manifest.json"),
            protocol_sha256=digest(root / "protocol.json"),
            role="train",
            full_original_native_and_credit_replay_completed=True,
        )
        for trial in cfg["trials"]:
            if trial["condition"] not in CONFIG["conditions"]:
                continue
            child = root / trial["id"]
            sig = (digest(child / "sender_observations.json"), digest(child / "frame_events.json"))
            require(sig not in signatures, "copied aliases cannot add independence or rows")
            signatures.add(sig)
            data = read_json(child / "derived.json")["late_credit"]
            require(
                data["credit"] == CONFIG["credit"], "only new late-credit rows, not early/reference/old data"
            )
            for c in data["cohorts"]:
                require(
                    c["role"] == "train"
                    and not c["future_actions_mixed"]
                    and not c["counterfactual_labels_used"]
                    and c["target_status_not_used_to_filter"] is True,
                    "all factual same-role cohorts without target screening required",
                )
                rows.append(
                    dict(
                        state=c["state"],
                        cap=c["cap"],
                        utility=c["utility"],
                        miss=c["miss"],
                        weight=c["weight"],
                        group=physical_group(p, trial),
                        episode=digest(root / "manifest.json") + ":" + trial["id"],
                        step=c["step"],
                    )
                )
    data = {
        "state": np.asarray([r["state"] for r in rows], dtype=float),
        "cap": np.asarray([r["cap"] for r in rows], dtype=np.int64),
        "targets": np.asarray([[r["utility"], r["miss"]] for r in rows]),
        "weight": np.asarray([r["weight"] for r in rows], dtype=np.int64),
        "group": np.asarray([r["group"] for r in rows]),
        "episode": np.asarray([r["episode"] for r in rows]),
        "step": np.asarray([r["step"] for r in rows], dtype=np.int64),
    }
    validate_data(data)
    return data, provenance


def validate_data(data):
    n = len(data["cap"])
    require(
        n > 0
        and data["state"].shape == (n, 736)
        and data["targets"].shape == (n, 2)
        and data["weight"].shape == data["group"].shape == (n,),
        "complete original causal history/target/group matrix required",
    )
    require(
        np.isfinite(data["state"]).all()
        and np.isfinite(data["targets"]).all()
        and ((data["targets"] >= 0) & (data["targets"] <= 1)).all()
        and (data["weight"] > 0).all()
        and np.issubdtype(data["weight"].dtype, np.integer),
        "finite bounded factual targets and all positive request weights required",
    )
    require(
        np.issubdtype(data["cap"].dtype, np.integer)
        and set(data["cap"].tolist()) == {300000, 450000, 900000}
        and len(set(data["group"].tolist())) == 8,
        "exact three-cap/eight-original-group training support required",
    )
    neural.project_state(data["state"])


def verify_fold_reference(reference, groups):
    root = Path(reference).resolve()
    require(
        digest(root / "manifest.json") == CONFIG["original_physical_fold_reference_manifest_sha256"],
        "original physical-fold receipt changed",
    )
    report = read_json(root / "report.json")
    require(
        all(report["comparison"]["folds"][i]["held_out_groups"] == groups[i::2] for i in range(2)),
        "exact original physical folds must not be selected/repartitioned",
    )


def _expected_report(data, folds, provenance, reference, config_path):
    return dict(
        abi=ABI,
        config=CONFIG,
        rows=len(data["cap"]),
        requests=int(data["weight"].sum()),
        physical_groups=8,
        folds=folds,
        necessary_action_skill_passed=all(f["necessary_action_skill_passed"] for f in folds),
        original_prior_proxy_passed=all(f["original_prior_proxy_passed"] for f in folds),
        forecasters_fitted=12,
        parameters_per_forecaster=786,
        old_models_or_actor_or_calibration_changed=False,
        source_full_native_raw_credit_replay_completed=True,
        training_development_only=True,
        target_attainment_not_used_for_selection_or_features=True,
        independent_validation=False,
        native_deployment_qualified=False,
        causal_quality_effect_proven=False,
        SOTA_achieved=False,
        provenance=provenance,
        physical_fold_reference=str(Path(reference).resolve()),
        config_sha256=digest(config_path),
        implementation_sha256=digest(__file__),
        imported_neural_recipe_sha256=digest(neural.__file__),
        imported_collector_sha256=digest(collection.__file__),
    )


def run_late_cv(config, roots, reference, out):
    validate_config(read_json(config))
    data, provenance = load_late_rows(roots)
    groups = sorted(set(data["group"].tolist()))
    verify_fold_reference(reference, groups)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "config.json", CONFIG)
    np.savez_compressed(out / "train_rows.npz", **data)
    folds = []
    for fold in range(2):
        held = groups[fold::2]
        fit = ~np.isin(data["group"], held)
        require(
            set(data["cap"][fit].tolist()) == {300000, 450000, 900000},
            "fit fold missing required proposal support",
        )
        models = {}
        for mode in ("conditional", "blind"):
            members = []
            for seed in MODEL_RECIPE["model_seeds"]:
                m = FIT(
                    data["state"][fit],
                    data["cap"][fit],
                    data["targets"][fit],
                    data["weight"][fit],
                    data["group"][fit],
                    seed,
                    mode == "blind",
                )
                m["held_out_groups"] = held
                m["training_credit"] = collection.CREDIT
                path = out / "models" / f"fold-{fold}-{mode}-seed-{seed}.json"
                path.parent.mkdir(exist_ok=True)
                write_json(path, m)
                members.append(m)
            models[mode] = members
        folds.append(
            dict(
                fold=fold,
                held_out_groups=held,
                fit_groups=groups[(1 - fold) :: 2],
                **METRICS(data, models, held),
            )
        )
    report = _expected_report(data, folds, provenance, reference, config)
    write_json(out / "report.json", report)
    seal_directory(
        out,
        sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()),
        ABI + "_complete",
        SOTA_achieved=False,
    )
    return report


def audit_late_cv(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    report = read_json(out / "report.json")
    validate_config(read_json(out / "config.json"))
    require(
        digest(__file__) == report["implementation_sha256"]
        and digest(neural.__file__) == report["imported_neural_recipe_sha256"]
        and digest(collection.__file__) == report["imported_collector_sha256"],
        "exact fitted/audited dependency bytes required",
    )
    require(
        all(
            digest(Path(root) / "manifest.json") == entry["manifest_sha256"]
            for root, entry in report["provenance"].items()
        ),
        "fully replayed source manifest changed",
    )
    # Reject malformed models/cache/numeric reports before the expensive full source
    # replay. A successful audit still verifies every raw source before returning.
    data, provenance = load_late_rows(list(report["provenance"]), False)
    with np.load(out / "train_rows.npz", allow_pickle=False) as cache:
        require(
            set(cache.files) == set(data) and all(np.array_equal(cache[k], v) for k, v in data.items()),
            "fresh cache differs from every actual source cohort",
        )
    groups = sorted(set(data["group"].tolist()))
    verify_fold_reference(report["physical_fold_reference"], groups)
    folds = []
    for fold in range(2):
        held = groups[fold::2]
        fit = ~np.isin(data["group"], held)
        models = {}
        for mode in ("conditional", "blind"):
            members = []
            for seed in MODEL_RECIPE["model_seeds"]:
                m = read_json(out / "models" / f"fold-{fold}-{mode}-seed-{seed}.json")
                require(
                    m["abi"] == MODEL_ABI
                    and m["fit_groups"] == groups[(1 - fold) :: 2]
                    and m["held_out_groups"] == held
                    and m["seed"] == seed
                    and m["updates"] == 1200
                    and m["blind"] == (mode == "blind")
                    and m["training_credit"] == collection.CREDIT
                    and m["native_deployment_qualified"] is False,
                    "actual auxiliary neural model provenance differs",
                )
                require(
                    [np.asarray(w).shape for w in m["weights"]] == [(95, 8), (8,), (8, 2), (2,)],
                    "exact 786-parameter auxiliary network shape required",
                )
                raw = neural.design(data["state"][fit], data["cap"][fit], m["blind"])
                require(
                    np.allclose(m["normalization"]["mean"], raw.mean(axis=0), rtol=0, atol=1e-12)
                    and np.allclose(
                        m["normalization"]["scale"], np.maximum(raw.std(axis=0), 0.05), rtol=0, atol=1e-12
                    ),
                    "actual fit-fold-only state/proposal normalization differs",
                )
                if m["blind"]:
                    require(
                        np.all(np.asarray(m["weights"][0])[-3:] == 0),
                        "blind model acquired proposed-action weights",
                    )
                PREDICT(m, data["state"], data["cap"])
                members.append(m)
            models[mode] = members
        folds.append(
            dict(
                fold=fold,
                held_out_groups=held,
                fit_groups=groups[(1 - fold) :: 2],
                **METRICS(data, models, held),
            )
        )
    expected = _expected_report(
        data, folds, provenance, report["physical_fold_reference"], out / "config.json"
    )
    require(expected == report, "actual late-data neural folds/errors/priors/flags differ")
    for root in report["provenance"]:
        collection.audit_settled_hold(root)
    return dict(
        read_only=True,
        rows=report["rows"],
        requests=report["requests"],
        actual_forecasters=12,
        actual_folds_recomputed=2,
        all_fresh_source_rows_reconstructed=True,
        complete_native_sources_independently_replayed=True,
        necessary_action_skill_passed=report["necessary_action_skill_passed"],
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_late_value_cv")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--source", action="append", required=True)
    run.add_argument("--physical-fold-reference", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "run":
        r = run_late_cv(a.config, a.source, a.physical_fold_reference, a.out)
        result = {k: r[k] for k in ("rows", "requests", "necessary_action_skill_passed", "SOTA_achieved")}
    else:
        result = audit_late_cv(a.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
