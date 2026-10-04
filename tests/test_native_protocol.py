import json
from copy import deepcopy

import pytest
from native_study_helpers import plan

from media_rl.cli import main
from media_rl.native_protocol import artifact_path, load_protocol, validate_protocol
from media_rl.native_study import known_scene_ranges, trial_schedule


def test_frozen_plan_is_role_explicit_fresh_balanced_and_complete(tmp_path):
    p, path, _ = plan(tmp_path)
    assert load_protocol(path)[0] == p
    assert p["stage"] == "repeatability" and p["SOTA_achieved"] is False
    assert all(g["scene_seed"] > 500 for g in p["groups"])
    assert p["conditions"]["rlcd-a"] == p["conditions"]["rlcd-b"]
    trials = trial_schedule(p)
    assert len(trials) == 48 and len({x["id"] for x in trials}) == 48
    assert all(x["role"] == "repeatability" for x in trials)


@pytest.mark.parametrize(
    "field,value",
    [
        ("repetitions", True),
        ("repetitions", 1),
        ("episode_timeout_s", 999),
        ("SOTA_achieved", True),
        ("risk_cutoff", 0.7),
        ("source_kind", "natural_video"),
    ],
)
def test_unsupported_or_weakened_protocol_rejects(tmp_path, field, value):
    p, _, _ = plan(tmp_path)
    p[field] = value
    with pytest.raises(ValueError):
        validate_protocol(p)


def test_scene_role_overlap_alias_forgery_and_unsafe_ids_reject(tmp_path):
    p, _, _ = plan(tmp_path)
    bad = deepcopy(p)
    bad["groups"][1]["scene_seed"] = bad["groups"][0]["scene_seed"]
    with pytest.raises(ValueError, match="leakage"):
        validate_protocol(bad)
    bad = deepcopy(p)
    bad["conditions"]["rlcd-b"]["controller"] = "bwe"
    with pytest.raises(ValueError, match="exact same policy"):
        validate_protocol(bad)
    bad = deepcopy(p)
    bad["groups"][0]["id"] = "../escaped"
    with pytest.raises(ValueError):
        validate_protocol(bad)
    with pytest.raises(ValueError):
        artifact_path(tmp_path, "../outside.json")


def test_frozen_model_and_source_digest_changes_reject(tmp_path):
    p, path, model = plan(tmp_path)
    b = json.loads(model.read_text())
    b["platt"][1] += 0.1
    model.write_text(json.dumps(b))
    with pytest.raises(ValueError, match="model changed"):
        load_protocol(path)
    p["source_sha256"]["assets/episode.mjs"] = "b" * 64
    path.write_text(json.dumps(p))
    with pytest.raises(ValueError, match="implementation changed"):
        load_protocol(path)


def test_scene_scan_distinguishes_old_marker_only_content_and_seeded_quality(tmp_path):
    old = tmp_path / "native-marker-only"
    old.mkdir()
    (old / "frame_events.json").write_text(json.dumps(dict(sources=[dict(source_id=1)])))
    new = tmp_path / "native-seeded-quality"
    new.mkdir()
    (new / "frame_events.json").write_text(
        json.dumps(dict(quality_protocol={}, scene_seed=100, sources=[dict(source_id=1), dict(source_id=20)]))
    )
    spans, inputs = known_scene_ranges(tmp_path)
    assert spans == [[101, 120]] and len(inputs) == 1
    (new / "frame_events.json").write_text(json.dumps(dict(quality_protocol={}, sources=[dict(source_id=1)])))
    with pytest.raises(ValueError, match="source identity"):
        known_scene_ranges(tmp_path)


def test_calibration_and_final_roles_cannot_claim_or_hide_controls(tmp_path):
    p, _, _ = plan(tmp_path, stage="calibration")
    assert validate_protocol(p)["conditions"] == {"source": {"controller": "rlcd", "model": "source"}}
    p["conditions"]["source"]["controller"] = "bwe"
    with pytest.raises(ValueError, match="source-selected"):
        validate_protocol(p)
    q, _, _ = plan(tmp_path, stage="test")
    q.pop("validation_lock")
    with pytest.raises(ValueError, match="frozen before test"):
        validate_protocol(q)


@pytest.mark.parametrize("command", ["native-plan", "native-study", "native-audit", "native-calibrate"])
def test_public_native_cli_commands_registered(command, capsys):
    with pytest.raises(SystemExit) as result:
        main([command, "--help"])
    assert result.value.code == 0 and command in capsys.readouterr().out
