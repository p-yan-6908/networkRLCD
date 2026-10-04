"""Synthetic software invariants ONLY; no native/learned-performance evidence."""

import json
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from native_study_helpers import bundle

from media_rl.native_action_coverage import (
    _RAW_AUDIT,
    BEHAVIORS,
    RECIPE,
    _report,
    audit_coverage,
    compatible_engines,
    plan_coverage,
    project_collector,
    run_coverage,
    validate_coverage,
)
from media_rl.native_action_coverage_control import COVERAGE_CAPS, executed_learned_action, exploration_cap
from media_rl.native_action_coverage_learning import _capture_signatures, load_augmented_role
from media_rl.native_action_learning import physical_group
from media_rl.native_action_policy import CANDIDATES, MODEL_ABI
from media_rl.native_dense_study import RECIPE as DENSE_RECIPE
from media_rl.native_dense_study import STUDY_ABI as DENSE_ABI
from media_rl.native_dense_study import audit_dense_episode
from media_rl.native_protocol import (
    DEFAULT_LIMITS,
    digest,
    read_json,
    seal_directory,
    verify_seal,
    write_json,
)
from media_rl.native_repair5_study import _close, plan_repair_study, trial_schedule
from media_rl.native_video import VIDEO_ABI

ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path, stage="train"):
    """Declared fake metadata only; never accepted by a factual raw-data loader."""
    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"synthetic software fixture NOT a native movie")
    catalog = tmp_path / "catalog.json"
    write_json(
        catalog,
        dict(
            source_abi=VIDEO_ABI,
            path=str(movie),
            sha256=digest(movie),
            duration_ms=300000,
            attribution="synthetic software test",
            license_url="https://example.invalid/license",
            source_url="https://example.invalid/source",
            rights_asserted_by_importer=True,
            not_representative_corpus=True,
        ),
    )
    model = tmp_path / "model.json"
    write_json(model, bundle())
    p = plan_repair_study(
        model,
        catalog,
        tmp_path / "base-plan.json",
        stage=stage,
        groups_per_family=1,
        results_directory=tmp_path / "results",
    )
    root = tmp_path / "base"
    root.mkdir()
    (root / "models").mkdir()
    shutil.copyfile(model, root / "models/source.json")
    shutil.copyfile(movie, root / "recorded-video.mp4")
    write_json(root / "protocol.json", p)
    seals = {}
    for t in trial_schedule(p):
        child = root / t["id"]
        child.mkdir()
        write_json(
            child / "manifest.json", dict(stage="native_repair5_episode_verified", synthetic_not_native=True)
        )
        seals[t["id"]] = digest(child / "manifest.json")
    seal_directory(
        root,
        ["protocol.json", "recorded-video.mp4", "models/source.json"],
        "native_repair5_study_complete",
        episodes=seals,
        role=stage,
        SOTA_achieved=False,
    )
    plan = tmp_path / "coverage.json"
    coverage = plan_coverage(root, plan)
    return root, p, coverage, plan


@pytest.mark.parametrize("stage", ["train", "calibration"])
def test_coverage_preserves_physical_groups_roles_and_source(tmp_path, stage):
    root, p, c, _ = fixture(tmp_path, stage)
    assert c["stage"] == stage and c["limits"] == DEFAULT_LIMITS and c["measurement_recipe"] == RECIPE
    assert c["coverage_caps"] == [400000, 450000, 500000] and c["no_new_independent_groups"]
    assert compatible_engines(c) and len(trial_schedule(c)) == 24
    assert {physical_group(p, t) for t in trial_schedule(p)} == {
        physical_group(c, t) for t in trial_schedule(c)
    }
    assert c["augmentation_parent"]["manifest_sha256"] == digest(root / "manifest.json")
    assert c["learner"] is None and c["repair_model"] is None and not c["learned_policy_present"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("stage", "diagnostic"),
        ("stage", "selected-calibration"),
        ("stage", "validation"),
        ("stage", "test"),
        ("stage", "calibration"),
        ("coverage_caps", [300000, 450000, 500000]),
        ("repair_model", {}),
        ("learner", {}),
        ("no_new_independent_groups", False),
        ("limits", dict(DEFAULT_LIMITS, inference_p99_ms=20)),
    ],
)
def test_coverage_refuses_relabeling_or_gate_changes(tmp_path, key, value):
    _, _, c, _ = fixture(tmp_path)
    bad = deepcopy(c)
    bad[key] = value
    with pytest.raises(ValueError):
        validate_coverage(bad)


@pytest.mark.parametrize("field", ["video_segment", "schedule", "scene_seed"])
def test_parent_physical_identity_cannot_be_aliased(tmp_path, field):
    _, _, c, _ = fixture(tmp_path)
    bad = deepcopy(c)
    if field == "video_segment":
        bad["groups"][0][field][0] += 1
    elif field == "schedule":
        bad["groups"][0][field][0][0] += 0.01
    else:
        bad["groups"][0][field] += 1
    with pytest.raises(ValueError):
        validate_coverage(bad)


def test_original_diagnostic_role_rejects_fitting_before_labels(tmp_path):
    root = tmp_path / "diagnostic"
    root.mkdir()
    write_json(root / "protocol.json", dict(stage="train", source_kind="recorded_video_dense_probe_v1"))
    with pytest.raises(ValueError, match="only original legal"):
        load_augmented_role([root], "train")
    with pytest.raises(ValueError, match="cannot fit"):
        load_augmented_role([root], "validation")


def test_template_only_projection_and_raw_verifier_isolated():
    original = (ROOT / "benchmarks/native_rtc/dense_episode.mjs").read_text()
    assert project_collector(original) == (ROOT / "benchmarks/native_rtc/coverage_episode.mjs").read_text()
    with pytest.raises(ValueError):
        project_collector(original.replace("panel.stage!=='diagnostic'", "false"))
    assert _RAW_AUDIT.__code__ is audit_dense_episode.__code__
    assert _RAW_AUDIT.__globals__ is not audit_dense_episode.__globals__
    assert (
        _RAW_AUDIT.__globals__["RECIPE"] == RECIPE
        and audit_dense_episode.__globals__["RECIPE"] == DENSE_RECIPE
    )
    assert audit_dense_episode.__globals__["STUDY_ABI"] == DENSE_ABI


def test_fixed_control_py_js_parity_and_scalar_history_not_learned():
    f = [0.0] * 16
    f[7] = 500000 / 4e6
    f[9] = 1
    f[10] = 1
    observation = dict(sample_ms=100, features=f, content_features=[0.2, 0.1, 1])
    code = "const m=await import(process.argv[1]),o=JSON.parse(process.argv[2]),p=new m.RepairPolicy();console.log(JSON.stringify({caps:m.BEHAVIORS.map(b=>m.explorationCap(b,0,1,o)),d:p.observe(o)}))"
    got = json.loads(
        subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                code,
                (ROOT / "benchmarks/native_rtc/coverage_control.mjs").as_uri(),
                json.dumps(observation),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    from media_rl.native_action_coverage_control import RepairPolicy

    assert got["caps"] == [exploration_cap(b, 0, 1, f) for b in BEHAVIORS] == list(COVERAGE_CAPS)
    _close(got["d"], RepairPolicy().observe(observation))
    assert got["d"]["actual_scalar_cap_bps"] == 500000 and got["d"]["shadow_projected_cap_bps"] == 300000
    assert not executed_learned_action(got["d"], 500000)
    with pytest.raises(ValueError):
        exploration_cap("bwe-continuous", 0, 1, f)


def test_mutated_parent_or_partial_parent_refused(tmp_path):
    root, _, c, _ = fixture(tmp_path)
    (root / "recorded-video.mp4").write_bytes(b"changed")
    with pytest.raises(ValueError):
        validate_coverage(c)
    with pytest.raises(ValueError):
        plan_coverage(root, tmp_path / "new.json")


def test_failed_capture_preserves_prefix_and_cannot_be_replaced(tmp_path, monkeypatch):
    import media_rl.native_action_coverage as m

    _, _, _, plan = fixture(tmp_path)
    calls = []

    def fail(args, timeout, log):
        child = Path(args[2])
        child.mkdir()
        (child / "partial.txt").write_text("retained")
        calls.append(child)
        raise ValueError("synthetic failure")

    monkeypatch.setattr(m, "_collect", fail)
    monkeypatch.setattr(m, "_recover_cleanup_capture", lambda *args: None)
    out = tmp_path / "capture"
    with pytest.raises(FileNotFoundError):
        run_coverage(plan, out)
    assert (
        calls[0].joinpath("partial.txt").read_text() == "retained"
        and read_json(out / "failure.json")["no_outcomes_replaced"]
    )
    with pytest.raises(FileExistsError):
        run_coverage(plan, out)
    assert len(calls) == 1
    with pytest.raises((ValueError, FileNotFoundError)):
        audit_coverage(out)


def test_complete_coverage_report_not_policy_success(tmp_path):
    _, _, c, _ = fixture(tmp_path)
    rows = [dict(t, utility=30.0, ontime_fraction=0.9, eligible=400) for t in trial_schedule(c)]
    r = _report(rows, c)
    assert (
        r["actual_executed_learned_steps"] == 0
        and r["no_new_independent_groups"]
        and not r["native_improvement_proven"]
    )
    with pytest.raises(ValueError):
        _report(rows[:-1], c)


def test_capture_aliases_do_not_add_support(tmp_path):
    roots = []
    for name in ("a", "b"):
        root = tmp_path / name
        root.mkdir()
        write_json(root / "runtime.json", dict(episodes=[dict(id="episode")]))
        child = root / "episode"
        child.mkdir()
        write_json(child / "sender_observations.json", dict(fake=True))
        write_json(child / "frame_events.json", dict(fake=True))
        roots.append(root)
    with pytest.raises(ValueError, match="aliases"):
        _capture_signatures(roots)


@pytest.mark.parametrize(
    "command,flags",
    [
        ("plan", ["--parent", "p", "--out", "o"]),
        ("study", ["--config", "c", "--out", "o"]),
        ("audit", ["--run", "r"]),
        ("fit", ["--train-run", "t", "--calibration-run", "c", "--out", "o"]),
    ],
)
def test_public_coverage_commands_dispatch(command, flags, monkeypatch):
    import media_rl.native_action_coverage_cli as m
    from media_rl.cli import main

    seen = []
    monkeypatch.setattr(m, "run", lambda args: seen.append(args))
    main(["native-action-coverage-" + command, *flags])
    assert seen[0].command == "native-action-coverage-" + command


def test_independent_full_fitting_boundaries_and_seal(tmp_path, monkeypatch):
    import media_rl.native_action_coverage_learning as m

    parents = []
    for role in ("train", "calibration"):
        root = tmp_path / role
        root.mkdir()
        write_json(root / "manifest.json", dict(fake=role))
        parents.append(root)

    def data(role):
        rows = [
            dict(
                state=[0.1 if role == "train" else 0.9] * 736,
                cap=cap,
                utility=0.5,
                miss=0.05,
                weight=30,
                episode=f"{role}-{g}-{cap}",
                group=f"{role}-g{g}",
                context="ready",
                step=0,
            )
            for g in range(8)
            for cap in CANDIDATES
        ]
        ps = [
            dict(
                video_source=dict(sha256=f"movie{movie}"),
                groups=[
                    dict(
                        video_segment=[
                            60000 if role == "train" else 80000,
                            80000 if role == "train" else 100000,
                        ],
                        family=family,
                    )
                    for family in ("stable", "collapse", "variable", "brief-collapse")
                ],
            )
            for movie in (0, 1)
        ]
        info = dict(
            original_measurement_recipe={"fake": "same frozen physics"},
            physical_groups_before=8,
            physical_groups_after=8,
        )
        return rows, ps, [parents[role == "calibration"]], info

    td = data("train")
    cd = data("calibration")
    monkeypatch.setattr(m, "load_augmented_role", lambda roots, role: td if role == "train" else cd)
    monkeypatch.setattr(m, "LEARNER", dict(m.LEARNER, updates=1))
    monkeypatch.setattr(
        m, "held_out_training_check", lambda rows: dict(passed=rows is td[0], synthetic_only=True)
    )
    fit = m.fit_outcomes
    seen = []

    def track(rows, seed, updates):
        seen.append(rows)
        return fit(rows, seed, updates)

    monkeypatch.setattr(m, "fit_outcomes", track)
    out = tmp_path / "fitted"
    report = m.train_coverage_model([parents[0]], [parents[1]], out)
    b = read_json(out / "model.json")
    assert report["training_cv"]["passed"] and len(seen) == 3 and all(rows is td[0] for rows in seen)
    assert (
        b["model_abi"] == MODEL_ABI
        and b["state_normalization"]["fitted_roles"] == ["train"]
        and np.allclose(b["state_normalization"]["mean"], 0.1)
    )
    assert b["no_new_independent_groups_from_augmentation"] and not b["native_deployment_qualified"]
    assert len(b["source_reservations"]) == 4 and len(b["provenance"]) == 2
    verify_seal(out, "bounded_action_candidate_fitted")
    with pytest.raises(ValueError):
        m.train_coverage_model([parents[0]], [parents[1]], out)
