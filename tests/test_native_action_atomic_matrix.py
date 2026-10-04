from pathlib import Path

import pytest

from media_rl import native_action_atomic_matrix as matrix
from media_rl import native_action_atomic_value_cv as value
from media_rl import native_action_balanced_matrix as old_matrix
from media_rl import native_action_balanced_value_cv as old_value
from media_rl import native_action_balanced_value_cv_v3 as identity
from media_rl.native_protocol import asset_directory, read_json

PLAN = "configs/native_action_atomic_matrix_v4.json"


def test_actual_complete_role_disjoint_source_matrix_and_original_fold_identity():
    cfg = read_json(PLAN)
    r = matrix.validate_plan(cfg)
    assert len(cfg["excluded_inputs_sha256"]) == 65
    assert {f: [g["video_segment"] for g in p["groups"]] for f, p in r.items()} == {
        "sintel": [[720000, 740000], [740000, 760000]],
        "bbb": [[160000, 180000], [180000, 200000]],
    }
    assert sum(len(p["episodes"]) for p in r.values()) == 36
    assert all(
        p["stage"] == "train" and p["repair_model"] is None and p["learner"] is None for p in r.values()
    )
    assert len(cfg["physical_fold_map"]) == 12 and all(
        list(cfg["physical_fold_map"].values()).count(i) == 6 for i in range(2)
    )
    for i, f in enumerate(read_json("results/native-action-late-value-cv-v2/report.json")["folds"]):
        assert all(cfg["physical_fold_map"][g] == i for g in f["held_out_groups"])
    assert cfg["cv_contract"] == old_value.CONTRACT
    assert len(cfg["dependencies_sha256"]) >= 12
    ranges, inputs = old_matrix.pilot.roles.reservations("results")
    assert str(Path(PLAN).resolve()) in inputs
    assert all(
        dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) in ranges
        for p in r.values()
        for g in p["groups"]
    )


def test_exact_numeric_fit_prediction_evaluation_identity_and_two_unique_import_redirects():
    assert value.FIT is old_value.FIT and value.PREDICT is old_value.PREDICT
    assert value.fit_cv.__code__ is old_value.fit_cv.__code__
    assert value._NS["evaluate"] is old_value.evaluate
    assert value.CONTRACT is old_value.CONTRACT and value.RECIPE is old_value.RECIPE
    assert value.LOAD.__code__ is identity.load_lossless.__code__
    for projected, original in ((value.RAW_LOAD, old_value._load), (value.audit_cv, old_value.audit_cv)):
        assert projected.__code__.co_code == original.__code__.co_code
        assert projected.__code__.co_names.count("native_action_atomic_matrix") == 1
        assert projected.__code__.co_consts.count(("native_action_atomic_matrix",)) == 1
        assert "native_action_balanced_matrix" not in projected.__code__.co_names
    assert matrix.RAW_PEER.__code__.co_code == old_matrix.pilot.audit_peer.__code__.co_code
    assert matrix.RAW_PEER.__globals__ is old_matrix.pilot.audit_peer.__globals__
    assert matrix.collect_matrix.__code__.co_code == old_matrix.collect_matrix.__code__.co_code
    assert matrix.audit_matrix.__code__.co_code == old_matrix.audit_matrix.__code__.co_code


@pytest.mark.parametrize(
    "case", ["role", "reuse", "recipe", "dependency", "helper", "fold", "drop-peer", "video"]
)
def test_actual_frozen_physical_recipe_role_source_drift_rejected(case):
    c = read_json(PLAN)
    if case == "role":
        c["role"] = "diagnostic"
    elif case == "reuse":
        c["failed_or_diagnostic_source_reused"] = True
    elif case == "recipe":
        c["cv_contract"]["model_recipe"]["updates"] = 1201
    elif case == "dependency":
        c["dependencies_sha256"][next(iter(c["dependencies_sha256"]))] = "0" * 64
    elif case == "helper":
        c["source_sha256"]["assets/native_failure_evidence.mjs"] = "0" * 64
    elif case == "fold":
        g = next(iter(c["physical_fold_map"]))
        c["physical_fold_map"][g] = 1 - c["physical_fold_map"][g]
    elif case == "drop-peer":
        c["runtimes"]["bbb"]["episodes"].pop()
    else:
        c["runtimes"]["bbb"]["groups"][0]["video_segment"] = [120000, 140000]
    with pytest.raises(ValueError):
        matrix.validate_plan(c)


@pytest.mark.parametrize(
    "source", ["results/native-action-balanced-matrix-v2", "results/native-failure-snapshot-replay-v3"]
)
def test_old_partial_or_diagnostic_source_cannot_enter_fresh_atomic_learning(source, tmp_path):
    out = tmp_path / "no-fit"
    with pytest.raises((ValueError, FileNotFoundError)):
        value.fit_cv(source, out)
    assert not out.exists()


def test_exact_train_producer_projection_and_atomic_helper_never_actor_features():
    assets = asset_directory()
    text = (assets / matrix.ENTRY).read_text()
    assert text == matrix.project_collector((assets / "balanced_hold_episode.mjs").read_text())
    assert "episode.role!==panel.stage||panel.stage!=='train'" in text
    assert text.index("const diagnosticRawEventCount=events.length") > text.index(
        "const result=answer.result.value"
    )
    assert text.index("await retainNativeResult") < text.index(
        "throw Error('unexpected UDP source endpoint')"
    )
    assert len(value.RECIPE["feature_names"]) == 23 and value.RECIPE["history_steps"] == 32
