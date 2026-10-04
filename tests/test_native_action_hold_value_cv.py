"""New-credit CV integrity software fixtures, never native/causal evidence."""

from copy import deepcopy

import numpy as np
import pytest

from media_rl import native_action_hold_value_cv as cv
from media_rl.native_action_policy import action_features
from media_rl.native_protocol import read_json, seal_directory, write_json
from media_rl.native_repair3_policy import INPUT_DIM
from media_rl.networks import MLP, sigmoid


def rows():
    result = []
    for group in range(8):
        for cap in (300000, 450000, 900000):
            state = [0.0] * INPUT_DIM
            state[-23 + 7] = 300000 / 4e6
            result.append(
                dict(
                    state=state,
                    cap=cap,
                    utility=0.4,
                    miss=0.2,
                    weight=12,
                    episode=f"group-{group}",
                    step=cap,
                    group=f"physical-{group}",
                )
            )
    return result


def fitted(data, seed, updates):
    assert seed in (6601, 6611, 6621) and updates == 1200
    state = np.asarray([r["state"] for r in data])
    w = np.zeros((INPUT_DIM + 3, 1))
    return (
        [w.tolist(), [0.0], [[0.0, 0.0]], [0.0, 0.0]],
        dict(
            mean=state.mean(axis=0).tolist(),
            scale=np.maximum(state.std(axis=0), 0.05).tolist(),
            fitted_roles=["train"],
            fused_into_weights=True,
        ),
        [],
    )


def fixture(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    write_json(config, cv.CONFIG)
    data = rows()
    before = deepcopy(data)
    monkeypatch.setattr(
        cv, "load_randomized_hold_rows", lambda roots: (data, dict(synthetic_software_only=True))
    )
    monkeypatch.setattr(cv.learner, "fit_outcomes", fitted)
    monkeypatch.setattr(cv.skill, "fit_action_blind_outcomes", fitted)
    out = tmp_path / "cv"
    report = cv.run_hold_value_cv(config, ["software-a", "software-b"], out)
    assert data == before
    return config, out, report


def replace(path, data):
    path.unlink()
    write_json(path, data)


def reseal(out):
    (out / "manifest.json").unlink()
    seal_directory(
        out, [str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()], cv.ABI + "_complete"
    )


def test_actual_cap_dependence_passes_necessary_skill_without_native_qualification(tmp_path, monkeypatch):
    data = rows()
    w = np.zeros((INPUT_DIM + 3, 1))
    w[INPUT_DIM, 0] = 1
    weights = [w.tolist(), [0.0], [[4.0, 0.0]], [-1.0, 0.0]]
    for row in data:
        inputs = np.asarray([row["state"] + action_features(row["cap"], row["state"])])
        row["utility"], row["miss"] = map(float, sigmoid(MLP.from_dict(weights)(inputs))[0])

    def conditional(train, seed, updates):
        _, normalization, trace = fitted(train, seed, updates)
        return weights, normalization, trace

    monkeypatch.setattr(
        cv, "load_randomized_hold_rows", lambda roots: (data, dict(synthetic_software_only=True))
    )
    monkeypatch.setattr(cv.learner, "fit_outcomes", conditional)
    monkeypatch.setattr(cv.skill, "fit_action_blind_outcomes", fitted)
    config = tmp_path / "config.json"
    write_json(config, cv.CONFIG)
    out = tmp_path / "positive-cv"
    report = cv.run_hold_value_cv(config, ["software-a", "software-b"], out)
    assert report["action_conditioning_skill_passed"]
    assert all(f["action_conditioning_utility_skill"] >= 0.99 for f in report["comparison"]["folds"])
    audit = cv.audit_hold_value_cv(out)
    assert audit["action_conditioning_skill_passed"] and not audit["native_deployment_qualified"]
    assert not audit["SOTA_achieved"]


def test_new_credit_cv_saves_twelve_actual_fits_and_numerically_recomputes_both_folds(tmp_path, monkeypatch):
    config, out, report = fixture(tmp_path, monkeypatch)
    assert len(list((out / "conditional_models").glob("*.json"))) == 6
    assert len(list((out / "state_only_models").glob("*.json"))) == 6
    assert report["rows"] == 24 and report["requests"] == 288 and report["physical_groups"] == 8
    audit = cv.audit_hold_value_cv(out)
    assert audit["numerically_recomputed_folds"] == 2 and not audit["action_conditioning_skill_passed"]
    assert not audit["native_deployment_qualified"] and not audit["SOTA_achieved"]
    assert not report["previous_immediate_horizon_conditional_models_refitted"]
    assert not report["deployed_or_candidate_or_selected_risk_weights_changed"]
    with pytest.raises(ValueError):
        cv.run_hold_value_cv(config, ["a", "b"], out)


@pytest.mark.parametrize(
    "field,value",
    [
        ("role", "calibration"),
        ("previous_immediate_horizon_rows_used", True),
        ("minimum_physical_groups", 1),
        ("conditions", ["fixed450"]),
    ],
)
def test_config_forbids_role_reuse_instant_credit_or_fixed_control_selection(field, value):
    with pytest.raises(ValueError):
        cv.validate_config(dict(cv.CONFIG, **{field: value}))


@pytest.mark.parametrize("roots", [[], ["one"], ["one", "one"], ["one", "two", "three"]])
def test_invalid_root_scope_rejects_before_raw_audit(monkeypatch, roots):
    def forbidden(*args):
        raise AssertionError("bad source scope reached raw audit")

    monkeypatch.setattr(cv.excitation, "audit_excitation", forbidden)
    with pytest.raises(ValueError):
        cv.load_randomized_hold_rows(roots)


@pytest.mark.parametrize("mutation", ["mse", "fold", "normalization", "action-weight", "seed", "proxy"])
def test_saved_prediction_or_metadata_forgery_rejects_not_just_a_green_seal(tmp_path, monkeypatch, mutation):
    _, out, report = fixture(tmp_path, monkeypatch)
    if mutation == "mse":
        report["conditional_cv"]["folds"][0]["utility_mse"] = 0.1
    elif mutation == "fold":
        report["comparison"]["folds"][0]["held_out_groups"] = ["other"]
    elif mutation == "proxy":
        report["conditional_cv"]["passed"] = True
    else:
        path = out / "state_only_models/fold-0-seed-6601.json"
        model = read_json(path)
        if mutation == "normalization":
            model["normalization"]["mean"][0] = 1
        elif mutation == "action-weight":
            model["weights"][0][-1][0] = 1
        else:
            model["seed"] = 99
        replace(path, model)
    replace(out / "report.json", report)
    reseal(out)
    with pytest.raises(ValueError):
        cv.audit_hold_value_cv(out)
