import copy
from pathlib import Path

import numpy as np
import pytest

from media_rl import native_action_late_forecast as forecast
from media_rl import native_action_late_validation as validation
from media_rl import native_action_late_value_cv as previous
from media_rl import native_action_settled_hold as hold
from media_rl.native_action_policy import validate_bundle


def training():
    n = 48
    return dict(
        state=np.zeros((n, 736)),
        cap=np.tile([300000, 450000, 900000], 16).astype(np.int64),
        targets=np.column_stack([np.tile([0.2, 0.5, 0.8], 16), np.full(n, 0.1)]),
        weight=np.ones(n, dtype=np.int64),
        group=np.repeat([str(i) for i in range(8)], 6),
    )


def test_forecast_recipe_exact_old_code_new_auxiliary_and_full_train_normalization():
    d = training()
    before = copy.deepcopy(d)
    assert (
        forecast.FIT.__code__ is previous.FIT.__code__
        and forecast.PREDICT.__code__ is previous.PREDICT.__code__
    )
    assert (
        forecast.CONFIG["source_development_manifest_sha256"]
        == "d33bbf484f15d90af7875ac0d6baad52ca192c0222cdc8c8cfe7ff3ad7c67ddf"
    )
    for blind in (False, True):
        m = forecast.FIT(d["state"], d["cap"], d["targets"], d["weight"], d["group"], 6601, blind)
        m["training_credit"] = forecast.CONFIG["credit"]
        m["recipe"] = copy.deepcopy(forecast.RECIPE)
        result = forecast.check_model(m, d, 6601, blind)
        assert (
            result.shape == (48, 2)
            and m["abi"] == forecast.MODEL_ABI
            and not m["native_deployment_qualified"]
        )
        with pytest.raises(ValueError):
            validate_bundle(m)
        m["normalization"]["mean"][0] += 1
        with pytest.raises(ValueError):
            forecast.check_model(m, d, 6601, blind)
    assert all(np.array_equal(d[k], v) for k, v in before.items())


def test_validation_role_entry_is_exact_two_anchor_projection_and_preserves_v2():
    p = Path("benchmarks/native_rtc/settled_hold_episode.mjs")
    before = p.read_text()
    projected = validation.project_collector(before)
    assert projected == Path("benchmarks/native_rtc/late_validation_episode.mjs").read_text()
    assert "panel.stage!=='validation'" in projected and "panel.stage!=='train'" not in projected
    assert p.read_text() == before
    assert validation.hold.RAW_AUDIT.__code__ is hold.RAW_AUDIT.__code__
    with pytest.raises(ValueError):
        validation.project_collector(projected)


@pytest.mark.parametrize("drift", ["role", "threshold", "credit", "fits", "selection"])
def test_no_validation_refit_relabel_reward_or_threshold_drift(drift):
    cfg = dict(
        abi=validation.ABI,
        role="validation",
        criteria=copy.deepcopy(validation.CRITERIA),
        credit=copy.deepcopy(hold.CREDIT),
        early_reference=copy.deepcopy(hold.REFERENCE),
        models_fitted_during_validation=0,
        no_target_quality_or_result_based_selection=True,
        SOTA_achieved=False,
    )
    if drift == "role":
        cfg["role"] = "train"
    elif drift == "threshold":
        cfg["criteria"]["minimum_action_utility_skill"] = 0
    elif drift == "credit":
        cfg["credit"]["cohort_start_after_ack_ms"] = 200
    elif drift == "fits":
        cfg["models_fitted_during_validation"] = 1
    else:
        cfg["no_target_quality_or_result_based_selection"] = False
    with pytest.raises(ValueError):
        validation.validate_plan(cfg)


def test_reservation_snapshot_covers_prior_train_calibration_diagnostic_and_validation(tmp_path):
    from media_rl.native_protocol import write_json

    results = tmp_path / "results"
    results.mkdir()
    configs = tmp_path / "configs"
    configs.mkdir()
    for i, role in enumerate(("train", "calibration", "diagnostic", "validation")):
        write_json(
            configs / f"native_{role}.json",
            dict(
                stage=role,
                video_source=dict(sha256="a" * 64),
                groups=[dict(video_segment=[20000 * i, 20000 * (i + 1)])],
            ),
        )
    ranges, inputs = validation.reservations(results)
    assert len(inputs) == len(ranges) == 4 and {tuple(x["segment"]) for x in ranges} == {
        (20000 * i, 20000 * (i + 1)) for i in range(4)
    }


def test_runtimes_new_truthful_four_groups_do_not_reuse_template_train_trials():
    p = dict(
        video_source=dict(sha256="a" * 64, duration_ms=400000),
        extra_source_sha256={},
        stage="train",
        episodes=[dict(role="train")],
    )
    templates = {film: copy.deepcopy(p) for film in validation.FILMS}
    excluded = [dict(sha256="a" * 64, segment=[0, 200000])]
    original = copy.deepcopy(templates)
    r = validation._runtimes(templates, excluded, "f" * 64)
    assert templates == original
    for film, p in r.items():
        assert p["stage"] == "validation" and len(p["episodes"]) == 12
        assert all(t["role"] == "validation" and t["video_segment"][0] >= 200000 for t in p["episodes"])
        assert {t["condition"] for t in p["episodes"]} == {"fixed450", "random-hold-a", "random-hold-b"}
        assert p["measurement_recipe"] == hold.RECIPE and p["no_forecasters_executed_by_native_controller"]


def validation_data():
    d = training()
    d["group"] = np.repeat([str(i) for i in range(4)], 12)
    d["film"] = np.repeat(list(validation.FILMS), 24)
    return d


def test_actual_fixed_forecasts_full_priors_each_film_cluster_uncertainty_and_no_mutation(monkeypatch):
    d = validation_data()
    train = training()
    train["targets"][:] = [0, 0.5]
    before = copy.deepcopy(d)
    monkeypatch.setattr(
        forecast,
        "PREDICT",
        lambda m, state, cap: d["targets"].copy() if m == "conditional" else np.full_like(d["targets"], 0.5),
    )
    r = validation.evaluate(d, {"conditional": ["conditional"], "blind": ["blind"]}, train)
    assert r["prospective_forecast_replication_passed"] and r["exact_physical_group_resamples"] == 256
    assert r["physical_group_action_skill_ci95"] == [1, 1]
    assert set(r["metrics"]) == {"pooled", *validation.FILMS}
    assert all(np.array_equal(d[k], v) for k, v in before.items())


@pytest.mark.parametrize(
    "case", ["threshold", "role-exclusion", "candidate-link", "catalog-link", "runtime-role"]
)
def test_actual_frozen_validation_plan_rejects_scientific_provenance_drift(case):
    from media_rl.native_protocol import read_json

    cfg = read_json("configs/native_action_late_validation_v3.json")
    if case == "threshold":
        cfg["criteria"]["minimum_action_utility_skill"] = 0
    elif case == "role-exclusion":
        cfg["excluded_video_ranges"].pop()
    elif case == "candidate-link":
        cfg["candidate"]["manifest_sha256"] = "0" * 64
    elif case == "catalog-link":
        cfg["replacement_catalog"]["sha256"] = "0" * 64
    else:
        cfg["runtimes"]["bbb"]["episodes"][0]["role"] = "train"
    with pytest.raises(ValueError):
        validation.validate_plan(cfg)


def test_no_perfect_blind_or_prior_zero_over_zero_false_green(monkeypatch):
    d = validation_data()
    train = training()
    monkeypatch.setattr(forecast, "PREDICT", lambda *args: d["targets"].copy())
    r = validation.evaluate(d, {"conditional": [1], "blind": [2]}, train)
    assert not r["prospective_forecast_replication_passed"]
    assert all(v["action_utility_skill"] == 0 for v in r["metrics"].values())
    assert r["physical_group_action_skill_ci95"] == [0, 0]
    assert validation._skill(0, 0) == 0 and validation._skill(1, 0) < 0
