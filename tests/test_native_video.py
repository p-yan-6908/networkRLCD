"""Artificial source fixtures are software tests, never empirical controller evidence."""

import json
from copy import deepcopy

import pytest
from native_study_helpers import bundle
from test_native_quality import qualified

from media_rl import native_study as study
from media_rl.native_protocol import digest
from media_rl.native_video import (
    VIDEO_ABI,
    VIDEO_QUALITY_PROTOCOL,
    load_video_protocol,
    plan_video_study,
    summarize_video_quality,
    validate_video_protocol,
)


def fixture(tmp_path, name="repeatability", **options):
    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"artificial fixture, not actual video")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            dict(
                source_abi=VIDEO_ABI,
                path=str(movie),
                sha256=digest(movie),
                duration_ms=600000,
                attribution="test only",
                license_url="https://example.invalid/license",
                source_url="https://example.invalid/video",
                rights_asserted_by_importer=True,
                not_representative_corpus=True,
            )
        )
    )
    model = tmp_path / "model.json"
    model.write_text(json.dumps(bundle()))
    path = tmp_path / (name + ".json")
    protocol = plan_video_study(
        model,
        path,
        catalog,
        stage="repeatability",
        groups_per_family=1,
        results_directory=tmp_path / "results",
        **options,
    )
    return protocol, path, movie


def test_recorded_plan_preserves_guards_and_loader_binds_bytes(tmp_path):
    p, path, movie = fixture(tmp_path)
    assert load_video_protocol(path)[0] == p
    assert len(p["groups"]) == 4 and len(study.trial_schedule(p)) == 24
    assert all("video_segment" in trial for trial in study.trial_schedule(p))
    assert (p["risk_cutoff"], p["disagreement_cutoff"]) == (0.5, 0.2)
    movie.write_bytes(b"changed")
    with pytest.raises(ValueError, match="video changed"):
        load_video_protocol(path)


@pytest.mark.parametrize("bad", [True, [60000, 60000], [60000, 60001], [60000, 80000.0], [-1, 20000]])
def test_invalid_or_insufficient_clip_reservations_reject(tmp_path, bad):
    p, _, _ = fixture(tmp_path)
    p["groups"][0]["video_segment"] = bad
    with pytest.raises(ValueError):
        validate_video_protocol(p)


def test_clip_role_and_group_reuse_reject(tmp_path):
    p, _, _ = fixture(tmp_path)
    bad = deepcopy(p)
    bad["groups"][1]["video_segment"] = bad["groups"][0]["video_segment"]
    with pytest.raises(ValueError, match="group leakage"):
        validate_video_protocol(bad)
    bad = deepcopy(p)
    bad["excluded_video_ranges"] = [
        dict(sha256=p["video_source"]["sha256"], segment=p["groups"][0]["video_segment"])
    ]
    with pytest.raises(ValueError, match="role leakage"):
        validate_video_protocol(bad)
    with pytest.raises(ValueError, match="role leakage"):
        study._require_video_groups_disjoint(p, p)


def test_interrupted_protocols_consume_video_segments(tmp_path):
    p, _, _ = fixture(tmp_path)
    partial = tmp_path / "results/native-interrupted"
    partial.mkdir(parents=True)
    (partial / "protocol.json").write_text(json.dumps(p))
    next_p, _, _ = fixture(tmp_path, name="new")
    old = {tuple(g["video_segment"]) for g in p["groups"]}
    assert all(tuple(g["video_segment"]) not in old for g in next_p["groups"])


def movie_evidence():
    frames = qualified()
    frames["quality_protocol"] = dict(VIDEO_QUALITY_PROTOCOL)
    trial = dict(video_segment=[60000, 80000])
    p = dict(video_source=dict(sha256="a" * 64))
    frames["video_source"] = dict(
        sha256="a" * 64, segment=trial["video_segment"], geometry="center_crop_fill_640x360"
    )
    for source in frames["sources"]:
        source["reference_rgb"] = [0] * 2400
        source["source_media_ms"] = 60000 + source["capture_request_ms"]
    return frames, p, trial


def test_recorded_quality_reuses_crc_deadline_and_rgb_math():
    frames, p, trial = movie_evidence()
    result = summarize_video_quality(frames, p, trial)
    assert result["eligible_requests"] == 4 and result["identified_ontime"] == 1
    known = frames["observations"][0]["source_id"]
    next(s for s in frames["sources"] if s["source_id"] == known)["reference_rgb"][0] = 1
    with pytest.raises(ValueError, match="captured source"):
        summarize_video_quality(frames, p, trial)


def test_frozen_or_wrong_source_playback_rejects():
    frames, p, trial = movie_evidence()
    for source in frames["sources"]:
        source["source_media_ms"] = 60000
    with pytest.raises(ValueError, match="did not advance"):
        summarize_video_quality(frames, p, trial)
    frames, p, trial = movie_evidence()
    frames["video_source"]["sha256"] = "b" * 64
    with pytest.raises(ValueError, match="source geometry"):
        summarize_video_quality(frames, p, trial)
