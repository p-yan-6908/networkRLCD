"""Software value-skill invariants; not native causal or policy-gain evidence."""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from media_rl import native_action_value_skill as skill
from media_rl.native_action_policy import action_features
from media_rl.native_protocol import read_json
from media_rl.native_repair3_policy import INPUT_DIM
from media_rl.networks import MLP, sigmoid


def rows():
    out = []
    for g in range(8):
        for step in range(2):
            state = [0.0] * INPUT_DIM
            state[-23 + 7] = 400000 / 4e6
            out.append(
                dict(
                    state=state,
                    cap=400000,
                    utility=0.4,
                    miss=0.2,
                    weight=3,
                    episode=f"episode-{g}",
                    group=f"group-{g}",
                    step=step,
                )
            )
    return out


def cv(mse=0.005):
    groups = sorted({r["group"] for r in rows()})
    return dict(
        passed=True,
        folds=[
            dict(
                held_out_groups=groups[i::2],
                fit_groups=sorted(set(groups) - set(groups[i::2])),
                utility_mse=mse,
            )
            for i in range(2)
        ],
    )


def fake_fit(rows, seed, updates):
    assert updates == 1200 and seed in (6601, 6611, 6621)
    w = np.zeros((INPUT_DIM + 3, 1))
    # Both output probabilities are exactly 0.5, giving utility MSE = 0.01.
    return [w.tolist(), [0.0], [[0.0, 0.0]], [0.0, 0.0]], dict(fitted_roles=["train"]), []


def test_configuration_frozen_to_original_folds_seeds_updates_and_skill():
    path = Path(__file__).resolve().parents[1] / "configs/native_action_value_skill_v1.json"
    assert skill.validate_value_skill_config(read_json(path)) == skill.CHECK_CONFIG
    for key, value in (("role", "calibration"), ("min_utility_skill", 0), ("cv_updates", 20)):
        with pytest.raises(ValueError):
            skill.validate_value_skill_config(dict(skill.CHECK_CONFIG, **{key: value}))


def test_identical_mlp_has_zero_action_dependence_and_train_only_normalization():
    data = rows()
    old = deepcopy(data)
    weights, normalization, trace = skill.fit_action_blind_outcomes(data, 6601, 4)
    assert np.all(np.asarray(weights[0])[INPUT_DIM:] == 0)
    s = data[0]["state"]
    predictions = sigmoid(
        MLP.from_dict(weights)(np.asarray([s + action_features(c, s) for c in (150000, 400000, 4000000)]))
    )
    assert np.array_equal(predictions[0], predictions[1]) and np.array_equal(predictions[0], predictions[2])
    assert normalization["fitted_roles"] == ["train"] and normalization["fused_into_weights"] and trace
    assert data == old


def test_action_sensitive_models_must_beat_state_only_not_just_prior(monkeypatch):
    monkeypatch.setattr(skill, "fit_action_blind_outcomes", fake_fit)
    report = skill.check_action_value_skill(rows(), cv(0.02))
    assert report["original_proxy_passed"] and not report["passed"]
    assert all(f["action_conditioning_utility_skill"] < 0 for f in report["folds"])
    assert report["factual_action_equals_own_fraction"] == 1
    assert not report["conditional_models_refitted"] and report["state_only_models_fitted"] == 6
    assert report["necessary_predictive_check_not_causal_certificate"]
    with pytest.raises(ValueError):
        skill.require_action_value_skill(report)
    good = skill.check_action_value_skill(rows(), cv(0.005))
    assert skill.require_action_value_skill(good)["passed"]


@pytest.mark.parametrize(
    "role", ["calibration", "diagnostic", "repeatability", "validation", "test", "selected"]
)
def test_nontraining_roles_cannot_fit_controls(role):
    with pytest.raises(ValueError):
        skill.check_action_value_skill(rows(), cv(), role=role)


@pytest.mark.parametrize(
    "mutation", ["few-groups", "duplicates", "source-groups", "nan", "cap", "weight", "target", "mse"]
)
def test_bad_rows_and_forged_fold_provenance_reject_before_fit(monkeypatch, mutation):
    def forbidden(*args):
        raise AssertionError("bad data reached fit")

    monkeypatch.setattr(skill, "fit_action_blind_outcomes", forbidden)
    data, prior = rows(), cv()
    if mutation == "few-groups":
        data = data[:-2]
    elif mutation == "duplicates":
        data.append(deepcopy(data[0]))
    elif mutation == "source-groups":
        prior["folds"][0]["held_out_groups"] = ["other"]
    elif mutation == "nan":
        data[0]["state"][0] = float("nan")
    elif mutation == "cap":
        data[0]["cap"] = 100
    elif mutation == "weight":
        data[0]["weight"] = 0
    elif mutation == "target":
        data[0]["utility"] = 2
    else:
        prior["folds"][0]["utility_mse"] = float("nan")
    with pytest.raises(ValueError):
        skill.check_action_value_skill(data, prior)


def test_each_fold_fit_never_contains_its_held_out_groups(monkeypatch):
    calls = []

    def fitted(data, seed, updates):
        calls.append({r["group"] for r in data})
        return fake_fit(data, seed, updates)

    monkeypatch.setattr(skill, "fit_action_blind_outcomes", fitted)
    report = skill.check_action_value_skill(rows(), cv())
    for i, fold in enumerate(report["folds"]):
        assert all(not set(fold["held_out_groups"]) & fit for fit in calls[i * 3 : (i + 1) * 3])
        assert fold["test_requests"] == 24
    assert len(calls) == 6


def test_gate_does_not_accept_truthy_pass_or_relaxed_configuration(monkeypatch):
    monkeypatch.setattr(skill, "fit_action_blind_outcomes", fake_fit)
    report = skill.check_action_value_skill(rows(), cv())
    for mutated in (
        dict(report, passed=1),
        dict(report, role="test"),
        dict(report, config=dict(skill.CHECK_CONFIG, min_utility_skill=0)),
    ):
        with pytest.raises(ValueError):
            skill.require_action_value_skill(mutated)
