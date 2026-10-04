import copy
from types import FunctionType

import numpy as np
import pytest

from media_rl import native_action_ordered_value_cv as cv
from media_rl.native_protocol import require


def fixture():
    rng = np.random.default_rng(71021)
    state = rng.normal(size=(24, 736))
    cap = np.tile(np.array([300000, 450000, 900000], dtype=np.int64), 8)
    target = np.column_stack([np.linspace(0.15, 0.85, 24), np.linspace(0.7, 0.3, 24)])
    weight = np.arange(1, 25, dtype=float)
    group = np.repeat(np.array(["a", "b", "c", "d"]), 6)
    return state, cap, target, weight, group


def test_only_new_opt_in_feature_recipe_no_original_global_mutation_or_algorithm_sweep():
    assert cv.FIT.__code__ is cv.base.FIT.__code__
    assert cv.PREDICT.__code__ is cv.base.PREDICT.__code__
    assert cv.evaluate.__code__ is cv.base.evaluate.__code__
    assert cv._check_model.__code__.co_code == cv.base._check_model.__code__.co_code
    changed = [
        (a, b)
        for a, b in zip(
            cv._check_model.__code__.co_consts, cv.base._check_model.__code__.co_consts, strict=True
        )
        if a != b
    ]
    assert len(changed) == 2
    for k, v in cv.base.RECIPE.items():
        if k not in ("abi", "projection", "compact_dim"):
            assert cv.RECIPE[k] == v
    for k, v in cv.base.CONTRACT.items():
        if k not in ("abi", "model_recipe"):
            assert cv.CONTRACT[k] == v
    assert cv.base.FIT.__globals__["COMPACT_DIM"] == 92
    assert cv.base.PREDICT.__globals__["COMPACT_DIM"] == 92
    assert cv.FIT.__globals__["design"] is cv.ordered.design
    assert cv.CONTRACT["parameters"] == 970 and len(cv.artifact_names()) == 17
    assert not cv.CONTRACT["native_deployment_qualified"] and not cv.CONTRACT["SOTA_achieved"]
    assert not any(hasattr(cv, k) for k in ("collect", "run_native", "choose_action", "deploy"))


@pytest.mark.parametrize("seed", [6601, 6611, 6621])
def test_zero_padding_preserves_every_old_initial_weight_and_exact_minibatch_rng_stream(seed):
    a, b = np.random.default_rng(seed), np.random.default_rng(seed)
    original = cv.networks.MLP(95, 8, 2, a)
    ordered = cv.OrderedMLP(118, 8, 2, b)
    assert np.array_equal(original.params[0][:92], ordered.params[0][:92])
    assert np.array_equal(original.params[0][-3:], ordered.params[0][-3:])
    assert np.array_equal(ordered.params[0][92:115], np.zeros((23, 8)))
    assert all(np.array_equal(x, y) for x, y in zip(original.params[1:], ordered.params[1:], strict=True))
    assert a.bit_generator.state == b.bit_generator.state
    assert np.array_equal(a.integers(0, 12, size=2048), b.integers(0, 12, size=2048))
    assert all(
        m.shape == p.shape and v.shape == p.shape and not m.any() and not v.any()
        for m, v, p in zip(ordered.m, ordered.v, ordered.params, strict=True)
    )
    state, cap, *_ = fixture()
    old_x = cv.ordered.original.design(state, cap)
    new_x = cv.ordered.design(state, cap)
    assert np.allclose(original(old_x), ordered(new_x), rtol=0, atol=1e-12)


@pytest.mark.parametrize("blind", [False, True])
def test_new_trend_paths_actually_learn_and_blind_proposals_stay_zero(blind):
    # Fast mathematical probe, deliberately not a qualifying 1200-update public model.
    config = {**cv.RECIPE, "updates": 3, "batch_size": 16}
    fit = FunctionType(
        cv.FIT.__code__, {**cv.FIT.__globals__, "CONFIG": config}, "short_probe", cv.FIT.__defaults__
    )
    state, cap, target, weight, group = fixture()
    m = fit(state, cap, target, weight, group, 6601, blind)
    assert np.asarray(m["weights"][0]).shape == (118, 8)
    assert np.linalg.norm(np.asarray(m["weights"][0])[92:115]) > 0
    assert m["normalization"]["fitted_roles"] == ["train"]
    raw = cv.ordered.design(state, cap, blind)
    assert np.array_equal(np.asarray(m["normalization"]["mean"]), raw.mean(axis=0))
    assert np.array_equal(np.asarray(m["normalization"]["scale"]), np.maximum(raw.std(axis=0), 0.05))
    prediction = cv.PREDICT(m, state, cap)
    assert prediction.shape == (24, 2) and np.isfinite(prediction).all()
    if blind:
        assert (np.asarray(m["weights"][0])[-3:] == 0).all()
        assert np.array_equal(prediction, cv.PREDICT(m, state, np.full(24, 300000, dtype=np.int64)))
    m.update(recipe=cv.RECIPE, held_out_groups=[], training_credit=cv.base.frozen.CONFIG["credit"])
    with pytest.raises(ValueError, match="provenance"):
        cv._check_model(
            m,
            dict(state=state, cap=cap, targets=target, weight=weight, group=group),
            np.ones(24, dtype=bool),
            [],
            6601,
            blind,
        )


@pytest.mark.parametrize("case", ["role", "updates", "dimensions", "SOTA", "seeds"])
def test_public_plan_rejects_recipe_or_role_changes_before_opening_source(case):
    plan = dict(abi=cv.ABI + "_predeclared", contract=copy.deepcopy(cv.CONTRACT))
    if case == "role":
        plan["contract"]["role"] = "validation"
    elif case == "updates":
        plan["contract"]["model_recipe"]["updates"] = 1201
    elif case == "dimensions":
        plan["contract"]["input_dim"] = 119
    elif case == "SOTA":
        plan["contract"]["SOTA_achieved"] = True
    else:
        plan["contract"]["model_recipe"]["model_seeds"] = [3]
    with pytest.raises(ValueError, match="sole fixed"):
        cv.validate_plan(plan)


@pytest.mark.parametrize("geometry", [(95, 8, 2), (118, 16, 2), (118, 8, 3)])
def test_new_initializer_cannot_silently_change_network_geometry(geometry):
    with pytest.raises(ValueError):
        cv.OrderedMLP(*geometry, np.random.default_rng(0))


def test_exact_same_zero_over_zero_skill_and_every_film_fold_ci_gates(monkeypatch):
    state, cap, target, weight, group = fixture()
    data = dict(
        state=state,
        cap=cap,
        targets=target,
        weight=weight,
        group=group,
        film=np.tile(np.array(["sintel", "tos", "bbb"]), 8),
        new_balanced=np.ones(24, dtype=bool),
    )

    def perfect(m, d, fit, held, seed, blind):
        require(m["seed"] == seed, "fixture identity")
        return d["targets"].copy()

    monkeypatch.setitem(cv._EVAL_NS, "_check_model", perfect)
    models = {
        f: {mode: [dict(seed=s) for s in cv.RECIPE["model_seeds"]] for mode in ("conditional", "blind")}
        for f in range(2)
    }
    result, _, _ = cv.evaluate(data, dict(a=0, b=1, c=0, d=1), models)
    assert not result["training_action_information_passed"]
    assert result["physical_group_action_skill_ci95"] == [0.0, 0.0]
    assert set(result["metrics"]) == {"pooled", "new_balanced_only", "sintel", "tos", "bbb"}
    assert len(result["folds"]) == 2 and result["cluster_resamples"] == 1024
