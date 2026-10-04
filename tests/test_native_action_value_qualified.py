"""Numeric/receipt/candidate guard invariants; no native or causal-gain claim."""

from pathlib import Path

import numpy as np
import pytest
from test_native_action import bundle
from test_native_action_value_skill import cv, rows

from media_rl import native_action_value_qualified as qualified
from media_rl import native_action_value_skill as skill
from media_rl.native_protocol import digest, read_json, seal_directory, write_json
from media_rl.native_repair3_policy import INPUT_DIM


def fixture(tmp_path, monkeypatch, conditional_mse=0.005):
    model, root = tmp_path / "model", tmp_path / "skill"
    model.mkdir()
    root.mkdir()
    data = rows()
    b = bundle()
    prior = cv(conditional_mse)
    write_json(model / "model.json", b)
    write_json(
        model / "training_report.json",
        dict(training_cv=prior, rows=dict(train=16), requests=dict(train=48), physical_groups=dict(train=8)),
    )

    def fitted(data, seed, updates):
        state = np.asarray([r["state"] for r in data])
        w = np.zeros((INPUT_DIM + 3, 1))
        return (
            [w.tolist(), [0.0], [[0.0, 0.0]], [0.0, 0.0]],
            dict(
                mean=state.mean(axis=0).tolist(),
                scale=np.maximum(state.std(axis=0), 0.05).tolist(),
                fused_into_weights=True,
                fitted_roles=["train"],
            ),
            [],
        )

    monkeypatch.setattr(skill, "fit_action_blind_outcomes", fitted)
    report = skill.check_action_value_skill(data, prior, models_directory=root / "models")
    report.update(
        implementation_sha256=digest(Path(skill.__file__)),
        source_sha256={},
        original_model_sha256=digest(model / "model.json"),
        original_training_report_sha256=digest(model / "training_report.json"),
    )
    write_json(root / "report.json", report)
    np.savez_compressed(
        root / "train_rows.npz",
        state=np.asarray([r["state"] for r in data]),
        cap=np.asarray([r["cap"] for r in data]),
        targets=np.asarray([[r["utility"], r["miss"]] for r in data]),
        weight=np.asarray([r["weight"] for r in data]),
        group=np.asarray([r["group"] for r in data]),
        episode=np.asarray([r["episode"] for r in data]),
        step=np.asarray([r["step"] for r in data]),
    )
    reseal(root)
    monkeypatch.setattr(qualified, "_candidate", lambda entry: b)
    return model, root, digest(root / "manifest.json"), b


def corrupt_json(path, value):
    # Intentional private-fixture corruption; production writers stay exclusive.
    path.unlink()
    write_json(path, value)


def reseal(root):
    (root / "manifest.json").unlink(missing_ok=True)
    seal_directory(
        root,
        [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"],
        "native_action_value_skill_complete",
    )


def test_full_numeric_reverification_and_pinned_qualified_constructor(tmp_path, monkeypatch):
    model, root, pin, b = fixture(tmp_path, monkeypatch)
    before = {str(p): digest(p) for p in root.rglob("*") if p.is_file()}
    report = qualified.audit_model_value_skill(model, root, expected_manifest_sha256=pin)
    assert report["passed"]
    assert qualified.load_value_qualified_candidate(model, root, expected_manifest_sha256=pin) == b
    actor = qualified.ValueQualifiedActionPolicy(model, root, expected_manifest_sha256=pin)
    assert actor.bundle == b and actor.state.last_sample is None
    assert before == {str(p): digest(p) for p in root.rglob("*") if p.is_file()}


def test_negative_original_proxy_pass_rejects_before_actor_init(tmp_path, monkeypatch):
    model, root, pin, _ = fixture(tmp_path, monkeypatch, conditional_mse=0.02)
    called = []
    monkeypatch.setattr(qualified.ActionPolicy, "__init__", lambda *args: called.append(True))
    report = qualified.audit_model_value_skill(model, root, expected_manifest_sha256=pin)
    assert report["original_proxy_passed"] and not report["passed"]
    with pytest.raises(ValueError, match="not established"):
        qualified.ValueQualifiedActionPolicy(model, root, expected_manifest_sha256=pin)
    assert not called


@pytest.mark.parametrize("pin", [None, "not-a-hash", "0" * 64, True])
def test_missing_foreign_or_truthy_external_pins_reject(tmp_path, monkeypatch, pin):
    model, root, _, _ = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        qualified.load_value_qualified_candidate(model, root, expected_manifest_sha256=pin)


def test_resealed_artifact_cannot_replace_frozen_qualification_receipt(tmp_path, monkeypatch):
    model, root, pin, _ = fixture(tmp_path, monkeypatch)
    report = read_json(root / "report.json")
    report["extra"] = "different receipt"
    corrupt_json(root / "report.json", report)
    reseal(root)
    with pytest.raises(ValueError, match="external"):
        qualified.load_value_qualified_candidate(model, root, expected_manifest_sha256=pin)


@pytest.mark.parametrize("mutation", ["model", "mse", "normalization", "action-weight", "fold", "role"])
def test_numeric_or_candidate_forgery_reject_even_with_newly_approved_pin(tmp_path, monkeypatch, mutation):
    model, root, _, _ = fixture(tmp_path, monkeypatch)
    report = read_json(root / "report.json")
    if mutation == "model":
        report["original_model_sha256"] = "0" * 64
    elif mutation == "mse":
        report["folds"][0]["state_only_utility_mse"] = 0.1
    elif mutation == "role":
        report["role"] = "calibration"
    else:
        path = root / "models/fold-0-seed-6601.json"
        entry = read_json(path)
        if mutation == "normalization":
            entry["normalization"]["mean"][0] = 1
        elif mutation == "action-weight":
            entry["weights"][0][-1][0] = 1
        else:
            entry["held_out_groups"] = ["other"]
        corrupt_json(path, entry)
    corrupt_json(root / "report.json", report)
    reseal(root)
    with pytest.raises(ValueError):
        qualified.audit_model_value_skill(
            model, root, expected_manifest_sha256=digest(root / "manifest.json")
        )
