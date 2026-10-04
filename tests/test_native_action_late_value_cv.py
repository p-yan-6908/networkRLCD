import copy

import numpy as np
import pytest

from media_rl import native_action_compact_hold_cv as original
from media_rl import native_action_late_value_cv as cv
from media_rl.native_action_policy import validate_bundle


def data():
    n = 48
    return dict(
        state=np.zeros((n, 736)),
        cap=np.tile([300000, 450000, 900000], 16).astype(np.int64),
        targets=np.column_stack([np.tile([0.2, 0.5, 0.8], 16), np.full(n, 0.1)]),
        weight=np.ones(n, dtype=np.int64),
        group=np.repeat([str(i) for i in range(8)], 6),
        episode=np.asarray([str(i) for i in range(n)]),
        step=np.arange(n),
    )


def test_recipe_and_exact_neural_code_are_fixed_without_old_source_labels():
    assert (
        cv.FIT.__code__ is original.fit_forecaster.__code__
        and cv.PREDICT.__code__ is original.predict.__code__
    )
    assert cv.CONFIG["credit"]["cohort_start_after_ack_ms"] == 1800
    assert cv.CONFIG["model_recipe"]["hidden"] == 8 and cv.CONFIG["minimum_action_utility_skill"] == 0.01
    assert "source_cv_manifest_sha256" not in cv.MODEL_RECIPE
    assert cv.CONFIG["target_attainment_cannot_filter_or_enter_state"]


@pytest.mark.parametrize("kind", ["role", "credit", "threshold", "hidden", "source"])
def test_config_rejects_early_or_threshold_or_recipe_drift(kind):
    c = copy.deepcopy(cv.CONFIG)
    if kind == "role":
        c["role"] = "calibration"
    elif kind == "credit":
        c["credit"]["cohort_start_after_ack_ms"] = 200
    elif kind == "threshold":
        c["minimum_action_utility_skill"] = 0
    elif kind == "hidden":
        c["model_recipe"]["hidden"] = 32
    else:
        c["source_collector_sha256"] = "forged"
    with pytest.raises(ValueError):
        cv.validate_config(c)


@pytest.mark.parametrize("kind", ["history", "support", "group", "weight", "target", "future"])
def test_legal_fresh_matrix_only(kind):
    d = data()
    if kind == "history":
        d["state"] = d["state"][:, :95]
    elif kind == "support":
        d["cap"][0] = 500000
    elif kind == "group":
        d["group"][:6] = "1"
    elif kind == "weight":
        d["weight"][0] = 0
    elif kind == "target":
        d["targets"][0, 0] = 1.1
    else:
        d["state"][0, 0] = np.nan
    with pytest.raises(ValueError):
        cv.validate_data(d)


def test_new_auxiliary_abi_real_neural_action_learning_and_blind_boundary():
    d = data()
    before = copy.deepcopy(d)
    cv.validate_data(d)
    conditional = cv.FIT(d["state"], d["cap"], d["targets"], d["weight"], d["group"], 6601, False)
    blind = cv.FIT(d["state"], d["cap"], d["targets"], d["weight"], d["group"], 6601, True)
    cp = cv.PREDICT(conditional, d["state"], d["cap"])
    bp = cv.PREDICT(blind, d["state"], d["cap"])
    assert np.mean((cp[:, 0] - d["targets"][:, 0]) ** 2) < np.mean((bp[:, 0] - d["targets"][:, 0]) ** 2) * 0.2
    assert conditional["abi"] == cv.MODEL_ABI and not conditional["native_deployment_qualified"]
    assert np.all(np.asarray(blind["weights"][0])[-3:] == 0) and np.ptp(bp[:, 0]) == 0
    assert sum(np.asarray(w).size for w in conditional["weights"]) == 786
    assert all(np.array_equal(d[k], v) for k, v in before.items())
    with pytest.raises(ValueError):
        validate_bundle(conditional)
    with pytest.raises(ValueError):
        original.predict(conditional, d["state"], d["cap"])
