"""Frozen all-training late-utility/risk forecasters; never native actor/safety qualification."""

import argparse
import copy
import json
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_late_value_cv as development
from .native_protocol import digest, read_json, require, seal_directory, verify_seal, write_json

ABI = "native_late_forecast_candidate_v3"
MODEL_ABI = ABI + "_auxiliary"
SOURCE_MANIFEST = "d33bbf484f15d90af7875ac0d6baad52ca192c0222cdc8c8cfe7ff3ad7c67ddf"
RECIPE = {**copy.deepcopy(development.MODEL_RECIPE), "abi": MODEL_ABI}
CONFIG = dict(
    abi=ABI,
    source_development_manifest_sha256=SOURCE_MANIFEST,
    recipe=RECIPE,
    credit=development.CONFIG["credit"],
    role="train",
    native_actor=False,
    risk_target="miss_fraction_only_in_1800_2200_ms_factual_window_not_all_requests",
    calibration_or_validation_labels_used=False,
    SOTA_achieved=False,
)
_NS = {**development.FIT.__globals__, "ABI": MODEL_ABI, "CONFIG": RECIPE}
FIT = FunctionType(
    development.FIT.__code__, _NS, "fit_all_training_late_forecaster", development.FIT.__defaults__
)
PREDICT = FunctionType(development.PREDICT.__code__, _NS, "predict_frozen_late_forecaster")


def training_source(root):
    root = Path(root).resolve()
    require(
        digest(root / "manifest.json") == SOURCE_MANIFEST,
        "exact previously audited late-development training receipt required",
    )
    verify_seal(root, development.ABI + "_complete")
    report = read_json(root / "report.json")
    require(
        report["necessary_action_skill_passed"] is True
        and report["training_development_only"] is True
        and report["native_deployment_qualified"] is False
        and report["rows"] == 160
        and report["requests"] == 1944,
        "exact legal train source/no old candidate promotion required",
    )
    require(
        digest(development.__file__) == report["implementation_sha256"],
        "frozen development implementation changed",
    )
    # Prior complete source/raw replay is reused only through this fixed external
    # manifest. Every actual canonical training row must still match its cache.
    data, provenance = development.load_late_rows(list(report["provenance"]), False)
    require(provenance == report["provenance"], "bound complete source receipts changed")
    with np.load(root / "train_rows.npz", allow_pickle=False) as saved:
        require(
            set(saved.files) == set(data) and all(np.array_equal(saved[k], v) for k, v in data.items()),
            "canonical all-training source cache changed",
        )
    return root, data


def check_model(m, data, seed, blind):
    groups = sorted(set(data["group"].tolist()))
    require(
        m["abi"] == MODEL_ABI
        and m["seed"] == seed
        and m["blind"] is blind
        and m["fit_groups"] == groups
        and m["updates"] == 1200
        and m["recipe"] == RECIPE
        and m["training_credit"] == CONFIG["credit"]
        and m["native_deployment_qualified"] is False,
        "exact frozen all-training auxiliary model provenance required",
    )
    require(
        [np.asarray(w).shape for w in m["weights"]] == [(95, 8), (8,), (8, 2), (2,)],
        "786-parameter neural model required",
    )
    raw = development.neural.design(data["state"], data["cap"], blind)
    require(
        np.allclose(m["normalization"]["mean"], raw.mean(axis=0), rtol=0, atol=1e-12)
        and np.allclose(m["normalization"]["scale"], np.maximum(raw.std(axis=0), 0.05), rtol=0, atol=1e-12),
        "all-train-only normalization required",
    )
    if blind:
        require(np.all(np.asarray(m["weights"][0])[-3:] == 0), "blind forecaster acquired action features")
    return PREDICT(m, data["state"], data["cap"])


def _report(root, data, models, config):
    errors = {}
    for mode, members in models.items():
        prediction = np.mean(
            [
                check_model(m, data, seed, mode == "blind")
                for m, seed in zip(members, RECIPE["model_seeds"], strict=True)
            ],
            axis=0,
        )
        error = np.average((prediction - data["targets"]) ** 2, axis=0, weights=data["weight"])
        errors[mode] = dict(train_utility_mse=float(error[0]), train_risk_brier=float(error[1]))
    return dict(
        abi=ABI,
        config=CONFIG,
        training_source=str(root),
        training_manifest_sha256=SOURCE_MANIFEST,
        training_rows=160,
        training_requests=1944,
        training_physical_groups=sorted(set(data["group"].tolist())),
        all_training_models=6,
        parameters_each=786,
        models_fitted_once=True,
        fit_errors=errors,
        config_sha256=digest(config),
        implementation_sha256=digest(__file__),
        development_sha256=digest(development.__file__),
        labels_from_validation_calibration_diagnostic_or_test_used=False,
        late_risk_is_not_selected_native_all_request_confidence=True,
        independent_validation=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def plan_forecast(out):
    require(not Path(out).exists(), "immutable forecast plan already exists")
    write_json(out, CONFIG)
    return CONFIG


def freeze_forecast(config, training, out):
    require(read_json(config) == CONFIG, "fixed all-training forecast recipe required")
    root, data = training_source(training)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "config.json", CONFIG)
    models = {}
    for mode in ("conditional", "blind"):
        members = []
        for seed in RECIPE["model_seeds"]:
            m = FIT(
                data["state"],
                data["cap"],
                data["targets"],
                data["weight"],
                data["group"],
                seed,
                mode == "blind",
            )
            m["training_credit"] = CONFIG["credit"]
            m["recipe"] = copy.deepcopy(RECIPE)
            path = out / "models" / f"{mode}-seed-{seed}.json"
            path.parent.mkdir(exist_ok=True)
            write_json(path, m)
            members.append(m)
        models[mode] = members
    report = _report(root, data, models, config)
    write_json(out / "report.json", report)
    seal_directory(
        out,
        sorted(str(x.relative_to(out)) for x in out.rglob("*") if x.is_file()),
        ABI + "_complete",
        SOTA_achieved=False,
    )
    return report


def audit_forecast(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    report = read_json(out / "report.json")
    require(read_json(out / "config.json") == CONFIG, "fixed forecast config changed")
    root, data = training_source(report["training_source"])
    models = {
        mode: [read_json(out / "models" / f"{mode}-seed-{seed}.json") for seed in RECIPE["model_seeds"]]
        for mode in ("conditional", "blind")
    }
    require(
        report == _report(root, data, models, out / "config.json"),
        "actual source/models/normalization/all-train fit errors/flags differ",
    )
    return dict(
        read_only=True,
        actual_auxiliary_models=6,
        actual_training_rows=160,
        prior_fixed_full_native_source_receipt_reused=True,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def load_forecasts(out):
    audit_forecast(out)
    out = Path(out).resolve()
    return {
        mode: [read_json(out / "models" / f"{mode}-seed-{seed}.json") for seed in RECIPE["model_seeds"]]
        for mode in ("conditional", "blind")
    }


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_late_forecast")
    sub = p.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--out", required=True)
    fit = sub.add_parser("freeze")
    fit.add_argument("--config", required=True)
    fit.add_argument("--training", required=True)
    fit.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "plan":
        r = plan_forecast(a.out)
        result = dict(abi=r["abi"], models_to_fit=6, SOTA_achieved=False)
    elif a.command == "freeze":
        r = freeze_forecast(a.config, a.training, a.out)
        result = {
            k: r[k]
            for k in (
                "all_training_models",
                "training_rows",
                "training_requests",
                "native_deployment_qualified",
                "SOTA_achieved",
            )
        }
    else:
        result = audit_forecast(a.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
