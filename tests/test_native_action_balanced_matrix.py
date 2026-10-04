"""Fixed pre-label matrix/old-fold preservation and exact compact numerical semantics."""

import copy

import numpy as np
import pytest

from media_rl import native_action_balanced_matrix as matrix
from media_rl import native_action_balanced_value_cv as value
from media_rl import native_action_late_forecast as old
from media_rl.native_protocol import read_json


def test_fitter_predict_code_recipe_geometry_unchanged_except_auxiliary_abi():
    assert value.FIT.__code__ is old.FIT.__code__
    assert value.PREDICT.__code__ is old.PREDICT.__code__
    assert {k: v for k, v in value.RECIPE.items() if k != "abi"} == {
        k: v for k, v in old.RECIPE.items() if k != "abi"
    }
    assert value.MODEL_ABI != old.MODEL_ABI
    assert (95 * 8 + 8 + 8 * 2 + 2) == 786
    assert value.RECIPE["model_seeds"] == [6601, 6611, 6621]


def test_actual_new_four_context_ranges_groups_folds_and_future_plural_role_visibility():
    cfg = read_json("configs/native_action_balanced_matrix_v2.json")
    r = matrix.validate_plan(cfg)
    assert {f: [g["video_segment"] for g in p["groups"]] for f, p in r.items()} == {
        "sintel": [[680000, 700000], [700000, 720000]],
        "bbb": [[120000, 140000], [140000, 160000]],
    }
    assert sum(len(p["episodes"]) for p in r.values()) == 36
    assert all(
        p["stage"] == "train" and p["repair_model"] is None and p["learner"] is None for p in r.values()
    )
    old_report = read_json("results/native-action-late-value-cv-v2/report.json")
    for i, fold in enumerate(old_report["folds"]):
        assert all(cfg["physical_fold_map"][g] == i for g in fold["held_out_groups"])
    assert len(cfg["physical_fold_map"]) == 12 and all(
        list(cfg["physical_fold_map"].values()).count(i) == 6 for i in range(2)
    )
    ranges, inputs = matrix.pilot.roles.reservations("results")
    from pathlib import Path

    assert str(Path("configs/native_action_balanced_matrix_v2.json").resolve()) in inputs
    assert all(
        dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) in ranges
        for p in r.values()
        for g in p["groups"]
    )


@pytest.mark.parametrize("case", ["role", "recipe", "fold", "drop-peer", "seed", "role-exclusions", "window"])
def test_actual_frozen_scientific_provenance_drift_rejected(case):
    c = read_json("configs/native_action_balanced_matrix_v2.json")
    if case == "role":
        c["role"] = "validation"
    elif case == "recipe":
        c["cv_contract"]["model_recipe"]["updates"] = 1201
    elif case == "fold":
        g = next(iter(c["physical_fold_map"]))
        c["physical_fold_map"][g] = 1 - c["physical_fold_map"][g]
    elif case == "drop-peer":
        c["runtimes"]["bbb"]["episodes"].pop()
    elif case == "seed":
        c["runtimes"]["bbb"]["episodes"][0]["exploration_seed"] += 1
    elif case == "role-exclusions":
        c["excluded_video_ranges"].pop()
    else:
        c["credit"]["cohort_start_after_ack_ms"] = 200
    with pytest.raises(ValueError):
        matrix.validate_plan(c)


def _perfect_synthetic():
    n = 24
    groups = np.repeat([f"g{i}" for i in range(12)], 2)
    fold_map = {f"g{i}": i % 2 for i in range(12)}
    data = dict(
        state=np.zeros((n, 736)),
        cap=np.tile([300000, 450000, 900000], 8).astype(np.int64),
        targets=np.full((n, 2), 0.5),
        weight=np.arange(12, 36, dtype=np.int64),
        group=groups,
        film=np.tile(["sintel", "tos", "bbb"], 8),
        new_balanced=np.arange(n) % 2 == 0,
    )
    models = {}
    for fold in range(2):
        held = sorted(g for g, i in fold_map.items() if i == fold)
        fit = ~np.isin(groups, held)
        models[fold] = {}
        for mode in ("conditional", "blind"):
            raw = old.development.neural.design(data["state"][fit], data["cap"][fit], mode == "blind")
            models[fold][mode] = []
            for seed in value.RECIPE["model_seeds"]:
                models[fold][mode].append(
                    dict(
                        abi=value.MODEL_ABI,
                        recipe=value.RECIPE,
                        seed=seed,
                        blind=mode == "blind",
                        updates=1200,
                        fit_groups=sorted(set(groups[fit].tolist())),
                        held_out_groups=held,
                        normalization=dict(
                            mean=raw.mean(axis=0).tolist(),
                            scale=np.maximum(raw.std(axis=0), 0.05).tolist(),
                            fitted_roles=["train"],
                        ),
                        training_credit=old.CONFIG["credit"],
                        native_deployment_qualified=False,
                        neural_forecaster_not_native_actor=True,
                        weights=[np.zeros((95, 8)).tolist(), [0] * 8, np.zeros((8, 2)).tolist(), [0, 0]],
                        fit_trace=[dict(update=1199, utility_mse=0.0, miss_log_loss=float(np.log(2)))],
                    )
                )
    return data, fold_map, models


def test_perfect_zero_baselines_do_not_false_pass_new_only_each_film_or_bootstrap():
    d, f, m = _perfect_synthetic()
    r, oof, p = value.evaluate(d, f, m)
    assert not r["training_action_information_passed"]
    assert r["cluster_resamples"] == 1024 and r["physical_group_action_skill_ci95"] == [0.0, 0.0]
    assert all(x["action_utility_skill"] == 0 and x["prior_risk_skill"] == 0 for x in r["metrics"].values())
    assert np.array_equal(p, d["targets"]) and np.array_equal(oof["conditional"], oof["blind"])


@pytest.mark.parametrize("case", ["normalization", "blind-action", "loss", "shape", "held-groups"])
def test_actual_numeric_model_invariants_not_just_self_sealed_metadata(case):
    d, f, models = _perfect_synthetic()
    m = copy.deepcopy(models[0]["blind"][0])
    held = m["held_out_groups"]
    fit = ~np.isin(d["group"], held)
    if case == "normalization":
        m["normalization"]["mean"][0] += 0.01
    elif case == "blind-action":
        m["weights"][0][-1][0] = 0.01
    elif case == "loss":
        m["fit_trace"][-1]["utility_mse"] += 0.01
    elif case == "shape":
        m["weights"][0].pop()
    else:
        m["held_out_groups"] = []
    with pytest.raises(ValueError):
        value._check_model(m, d, fit, held, 6601, True)
