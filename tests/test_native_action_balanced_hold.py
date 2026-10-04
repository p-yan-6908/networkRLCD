"""Balanced future assignment and read-only actual train-only gradient evidence."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from media_rl import native_action_balanced_control as control
from media_rl import native_action_balanced_hold as balanced
from media_rl import native_action_settled_hold as old
from media_rl.native_protocol import asset_directory, digest, read_json, write_json


def test_every_arm_every_epoch_and_complete_previous_current_transition_blocks():
    for seed in (0, 1, 10801, 123456, control.MAX_BLOCK_SEED):
        for epoch in range(513):
            caps = [
                control.assignment("random-hold-a", epoch, control.encoded_seed(seed, r)) for r in range(3)
            ]
            assert sorted(caps) == sorted(control.CAPS)
            assert caps == [
                control.assignment("random-hold-b", epoch, control.encoded_seed(seed, r)) for r in range(3)
            ]
        for block in range(170):
            pairs = {
                (
                    control.assignment("random-hold-a", e - 1, control.encoded_seed(seed, r)),
                    control.assignment("random-hold-a", e, control.encoded_seed(seed, r)),
                )
                for r in range(3)
                for e in range(block * 3 + 1, block * 3 + 4)
            }
            assert pairs == {(a, b) for a in control.CAPS for b in control.CAPS}


def test_exact_32_step_holds_features_unused_aliases_equal_and_fixed450():
    for r in range(3):
        seed = control.encoded_seed(10801, r)
        for step in range(160):
            a = [0.0] * 16
            b = [1000.0] * 16
            b[9] = 1
            assert (
                control.settled_cap("random-hold-a", step, seed, a)
                == control.settled_cap("random-hold-b", step, seed, b)
                == control.assignment("random-hold-a", step // 32, seed)
            )
            assert control.settled_cap("fixed450", step, seed, b) == 450000


@pytest.mark.parametrize(
    "seed,rep", [(True, 0), (-1, 0), (control.MAX_BLOCK_SEED + 1, 0), (0, True), (0, -1), (0, 3)]
)
def test_invalid_replica_and_seed_never_silently_coerce(seed, rep):
    with pytest.raises(ValueError):
        control.encoded_seed(seed, rep)


def test_exact_entry_projection_raw_and_measurement_code_identity():
    a = asset_directory()
    assert (a / "balanced_hold_episode.mjs").read_text() == balanced.project_collector(
        (a / "settled_hold_episode.mjs").read_text()
    )
    assert balanced.RAW_AUDIT.__code__ is old.RAW_AUDIT.__code__
    assert balanced.build_late.__code__ is old.build_late_cohorts.__code__
    assert balanced.build_early.__code__ is old.build_reference_cohorts.__code__
    assert balanced.audit_peer.__code__.co_code == old.audit_peer.__code__.co_code
    assert (
        tuple(
            "assets/settled_hold_episode.mjs" if x == "assets/balanced_hold_episode.mjs" else x
            for x in balanced.audit_peer.__code__.co_consts
        )
        == old.audit_peer.__code__.co_consts
    )
    assert balanced.RAW_AUDIT.__globals__["exploration_cap"] is control.settled_cap
    assert old.RAW_AUDIT.__globals__["exploration_cap"] is old.settled_cap


@pytest.mark.parametrize("case", ["role", "credit", "exclusions", "seed", "drop-peer"])
def test_actual_fixed_pilot_rejects_training_role_and_provenance_drift(case):
    c = read_json("configs/native_action_balanced_hold_pilot_v1.json")
    if case == "role":
        c["role"] = "validation"
    elif case == "credit":
        c["credit"]["cohort_start_after_ack_ms"] = 200
    elif case == "exclusions":
        c["excluded_video_ranges"].pop()
    elif case == "seed":
        c["runtime"]["episodes"][0]["exploration_seed"] += 1
    else:
        c["runtime"]["episodes"].pop()
    with pytest.raises(ValueError):
        balanced.validate_plan(c)


@pytest.mark.parametrize("penalty", [0.0, 0.01])
def test_train_only_gradient_norm_and_head_bias_match_all_parameter_finite_differences(penalty):
    path = Path(__file__).resolve().parents[1] / "results/jobs/native_action_late_training_diagnosis.py"
    spec = importlib.util.spec_from_file_location("gradient_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rng = np.random.default_rng(71)
    x = rng.normal(size=(9, 4))
    params = [
        rng.normal(scale=0.02, size=(4, 3)),
        np.full(3, 0.5),
        rng.normal(scale=0.3, size=(3, 2)),
        np.zeros(2),
    ]
    y = rng.uniform(size=(9, 2))
    weights = np.arange(1, 10, dtype=float)
    diagnostic = module.gradient_diagnostic(x, params, y, weights, penalty)
    grad = []
    epsilon = 1e-6
    for p in params:
        gp = np.zeros_like(p)
        for index in np.ndindex(p.shape):
            original = p[index]
            p[index] = original + epsilon
            plus = module.gradient_diagnostic(x, params, y, weights, penalty)["objective"]
            p[index] = original - epsilon
            minus = module.gradient_diagnostic(x, params, y, weights, penalty)["objective"]
            p[index] = original
            gp[index] = (plus - minus) / (2 * epsilon)
        grad.append(gp)
    assert np.isclose(
        diagnostic["gradient_l2"], np.sqrt(sum(np.sum(g * g) for g in grad)), rtol=1e-6, atol=1e-8
    )
    assert np.allclose(
        grad[-1],
        [diagnostic["utility_output_bias_gradient"], diagnostic["risk_output_bias_gradient"]],
        atol=1e-8,
    )


def test_consumed_role_receipt_closes_singular_runtime_blind_spot_without_old_schema_edits(tmp_path):
    actual = Path("results/native-action-balanced-hold-pilot-v1")
    cfg = read_json(actual / "protocol.json")
    receipt_path = Path("configs/native_action_balanced_hold_pilot_v1_role_receipt.json")
    receipt = read_json(receipt_path)
    assert receipt["video_source"] == cfg["runtime"]["video_source"]
    assert receipt["groups"] == cfg["runtime"]["groups"]
    assert receipt["consumed_source"]["manifest_sha256"] == digest(actual / "manifest.json")
    reservation = dict(sha256=receipt["video_source"]["sha256"], segment=[100000, 120000])
    (tmp_path / "results/pilot").mkdir(parents=True)
    (tmp_path / "configs").mkdir()
    write_json(tmp_path / "results/pilot/protocol.json", cfg)
    missing, _ = balanced.roles.reservations(tmp_path / "results")
    assert reservation not in missing
    write_json(tmp_path / "configs/native_consumed_receipt.json", receipt)
    covered, inputs = balanced.roles.reservations(tmp_path / "results")
    assert reservation in covered and len(inputs) == 1
    actual_covered, actual_inputs = balanced.roles.reservations("results")
    assert reservation in actual_covered
    assert actual_inputs[str(receipt_path.resolve())] == digest(receipt_path)


def test_actual_training_only_diagnosis_does_not_conflate_factual_support_and_potentials():
    r = read_json("results/jobs/native-action-late-training-diagnosis-v1.json")
    assert (
        r["training_role_only"]
        and r["no_validation_calibration_diagnostic_or_test_labels_read"]
        and r["no_new_fits_or_captures"]
    )
    assert (
        r["rows"],
        r["requests"],
        r["physical_groups"],
        r["group_epoch_strata"],
        r["strata_all_three_caps"],
    ) == (160, 1944, 8, 40, 0)
    assert not r["causal_effect_or_model_generalization_established"] and not r["native_deployment_qualified"]
    assert len(r["models"]) == 6 and all(
        m["proposed_action_potentials_not_observed_counterfactuals"] for m in r["models"]
    )
