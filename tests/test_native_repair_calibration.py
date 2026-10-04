"""Software fixtures only, not controller performance or training data."""

from copy import deepcopy
from pathlib import Path

import pytest
from test_native_repair import bundle

from media_rl.native_protocol import digest, read_json, write_json
from media_rl.native_repair_calibration import (
    MUTABLE,
    fit_selected_repair_calibration,
    selected_repair_samples,
    verify_selected_repair_calibration,
)
from media_rl.native_repair_study import (
    _expected_runtime,
    _preflight_resume,
    _validate_recorded_runtime,
    plan_repair_study,
    validate_repair_protocol,
    video_overlap,
)


def samples():
    return [
        dict(
            group=f"g{g}",
            episode_id=f"g{g}-e{e}",
            state=[0.0] * 640,
            action=2 if g < 2 and e == 0 else 3,
            miss_fraction=0.02 * (g + 1),
            label_count=30,
            learned=True,
        )
        for g in range(4)
        for e in range(4)
    ]


def test_monotonic_cross_fitting_and_frozen_weights():
    original = bundle()
    candidate, report = fit_selected_repair_calibration(original, samples())
    assert candidate["platt"][0] > 0 and report["independent_groups"] == 4
    assert all(f["held_out_group"] not in f["fit_groups"] for f in report["leave_one_source_group_out"])
    assert {k: v for k, v in original.items() if k not in MUTABLE} == {
        k: v for k, v in candidate.items() if k not in MUTABLE
    }
    assert candidate["risk_margin"][2] == 1  # Two source groups, not enough support.
    assert candidate["risk_margin"][3] < 1 and candidate["calibration_requests"][3] >= 60
    assert report["cross_fitted"]["frame_brier"] >= 0
    assert report["empirical_margins_not_pointwise_safety_guarantees"]
    assert not report["policy_improved"]


def test_repeated_peers_never_replace_independent_support():
    rows = samples()
    for row in rows:
        row["group"] = "same-source"
    with pytest.raises(ValueError, match="independent"):
        fit_selected_repair_calibration(bundle(), rows)


@pytest.mark.parametrize("role", ["train", "calibration", "validation", "test", "repeatability"])
def test_selected_calibration_refuses_wrong_role_before_raw_audit(tmp_path, monkeypatch, role):
    import media_rl.native_repair_calibration as module

    write_json(tmp_path / "protocol.json", dict(stage=role))
    monkeypatch.setattr(module, "audit_repair_study", lambda *a: pytest.fail("wrong role reached audit"))
    with pytest.raises(ValueError, match="forbidden"):
        selected_repair_samples(tmp_path)


def test_provisional_model_cannot_enter_evaluation():
    with pytest.raises(ValueError, match="locked selected"):
        verify_selected_repair_calibration(bundle())


def test_invalid_factual_outcomes_and_state_rejected():
    rows = samples()
    rows[0]["miss_fraction"] = float("nan")
    with pytest.raises(ValueError, match="outcomes"):
        fit_selected_repair_calibration(bundle(), rows)
    rows = samples()
    rows[0]["state"][-1] = -1
    with pytest.raises(ValueError, match="states"):
        fit_selected_repair_calibration(bundle(), rows)


def minimal_protocol():
    return dict(
        stage="train",
        order_seed=3,
        models={"source": {"path": "old.json", "sha256": "unused"}},
        repair_model=None,
        video_source={"path": "old.mp4"},
        groups=[
            dict(
                id="stable-0",
                family="stable",
                scene_seed=0,
                reservation_frames=1000,
                schedule=[[2, "high", 6000], [2, "collapse", 6000], [2, "recovery", 6000]],
                video_segment=[60000, 80000],
                orders=[["bwe", "sweep"]],
            )
        ],
    )


def test_runtime_reconstruction_is_absolute_and_does_not_mutate_plan(tmp_path):
    p = minimal_protocol()
    original = deepcopy(p)
    relative = Path("test-relative-root")
    runtime = _expected_runtime(p, relative)
    assert Path(runtime["video_source"]["path"]).is_absolute()
    assert p == original
    root = tmp_path
    (root / "models").mkdir()
    (root / "models/source.json").write_text("original")
    p["models"]["source"]["sha256"] = digest(root / "models/source.json")
    runtime = _expected_runtime(p, root)
    _validate_recorded_runtime(root, p, runtime)
    bad = deepcopy(runtime)
    bad["episodes"][0]["condition"] = "fixed300"
    with pytest.raises(ValueError, match="runtime differs"):
        _validate_recorded_runtime(root, p, bad)
    (root / "models/source.json").write_text("replacement")
    with pytest.raises(ValueError, match="model changed"):
        _validate_recorded_runtime(root, p, runtime)


def test_resume_refuses_partial_or_nonprefix_peers_before_collecting(tmp_path):
    p = minimal_protocol()
    runtime = _expected_runtime(p, tmp_path)
    first, second = runtime["episodes"]
    child = tmp_path / second["id"]
    child.mkdir()
    with pytest.raises(ValueError, match="prospective schedule prefix"):
        _preflight_resume(tmp_path, p, runtime, {}, None)
    child.rmdir()
    (tmp_path / first["id"]).mkdir()
    with pytest.raises(ValueError, match="partial"):
        _preflight_resume(tmp_path, p, runtime, {}, None)


def test_preflight_complete_capture_is_read_only(tmp_path, monkeypatch):
    import media_rl.native_repair_study as module

    p = minimal_protocol()
    runtime = _expected_runtime(p, tmp_path)
    write_json(tmp_path / "runtime.json", runtime)
    child = tmp_path / runtime["episodes"][0]["id"]
    child.mkdir()
    for name in ("summary.json", "frame_events.json", "sender_observations.json", "events.jsonl.gz"):
        (child / name).write_bytes(b"software-fixture")
    (child / "panel_snapshot.json").write_bytes((tmp_path / "runtime.json").read_bytes())
    before = {x.name: digest(x) for x in child.iterdir()}
    monkeypatch.setattr(
        module, "audit_repair_episode", lambda *a: (dict(start_epoch_ms=1, cutoff_epoch_ms=2), {})
    )
    _preflight_resume(tmp_path, p, runtime, {}, None)
    assert before == {x.name: digest(x) for x in child.iterdir()}


def test_half_open_movie_endpoints_are_disjoint():
    assert not video_overlap([60, 80], [80, 100])
    assert video_overlap([60, 81], [80, 100])


def test_selected_role_planner_and_condition_lock(tmp_path, monkeypatch):
    from native_study_helpers import bundle as legacy

    monkeypatch.chdir(tmp_path)
    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"software fixture")
    source = tmp_path / "source.json"
    write_json(source, legacy())
    model = tmp_path / "repair.json"
    write_json(model, bundle())
    catalog = tmp_path / "catalog.json"
    write_json(
        catalog,
        dict(
            source_abi="recorded_video_v1",
            path=str(movie),
            sha256=digest(movie),
            duration_ms=734000,
            attribution="software fixture",
            license_url="https://example.invalid/rights",
            rights_asserted_by_importer=True,
            not_representative_corpus=True,
        ),
    )
    p = plan_repair_study(
        source,
        catalog,
        tmp_path / "plan.json",
        stage="selected-calibration",
        model=model,
        groups_per_family=1,
        results_directory=tmp_path / "results",
    )
    assert p["conditions"] == {"source": {"controller": "repair", "model": "source"}}
    bad = deepcopy(p)
    bad["conditions"]["source"]["controller"] = "bwe"
    with pytest.raises(ValueError, match="mapping"):
        validate_repair_protocol(bad)
    assert read_json(tmp_path / "plan.json") == p
