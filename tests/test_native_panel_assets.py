"""Asset rights, lineage independence and immutable frozen-controller contracts."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from media_rl import native_actuator_panel as panel
from media_rl import native_actuator_panel_statistics as stats
from media_rl import native_panel_assets as assets
from media_rl.native_protocol import write_json


def source(tmp_path, title="Title", capture="session", media=b"owned clip", license="CC-BY-4.0"):
    video = tmp_path / (title.replace(" ", "_") + ".mp4")
    video.write_bytes(media)
    evidence = tmp_path / (title.replace(" ", "_") + "-license.txt")
    quote = f"{title}: CC BY 4.0. License applies to this asset."
    evidence.write_text(quote)
    return dict(
        path=str(video),
        sha256=assets.digest(video),
        source="owned-provider",
        source_title=title,
        capture_group=capture,
        independence_basis="reviewed original independent capture session",
        license=license,
        license_url=assets.LICENSE_URLS.get(license, "https://example.org/unknown"),
        source_url="https://example.org/owned-title",
        attribution="Owner supplied attribution",
        rights_asserted_by_importer=True,
        license_evidence=dict(
            path=str(evidence),
            sha256=assets.digest(evidence),
            scope="this_asset",
            source_title=title,
            license=license,
            source_url="https://example.org/asset-readme",
            checked_at_utc="2026-10-04T00:00:00Z",
            reviewed_by_importer=True,
            binding_quote=quote,
        ),
    )


def test_shared_title_capture_and_mirror_lineage_are_transitively_one_cluster():
    def r(title, capture, sha, parent=None):
        return dict(
            source_title=title,
            capture_group=capture,
            source_sha256=hashlib.sha256(sha.encode()).hexdigest(),
            parent_sha256=hashlib.sha256(parent.encode()).hexdigest() if parent else None,
        )

    records = [
        r("Meridian", "take-a", "master"),
        r(" MERIDIAN ", "take-b", "encode"),
        r("Different title", "take-b", "other"),
        r("Mirror alias", "take-c", "mirror", "master"),
        r("Truly separate", "new-session", "new"),
    ]
    ids = assets.assign_clusters(records)
    assert len(set(ids[:4])) == 1 and ids[4] != ids[0]
    assert ids == assets.assign_clusters(records)


@pytest.mark.parametrize("license", ["CC-BY-NC-4.0", "CC-BY-ND-4.0", "unknown"])
def test_nc_nd_and_unspecified_permission_blocked(tmp_path, license):
    with pytest.raises(ValueError, match="NC, ND and unknown"):
        assets.validate_source(source(tmp_path, license=license))


def test_rights_snapshot_quote_scope_and_title_verified(tmp_path):
    record = source(tmp_path)
    assert assets.validate_source(record) == record
    record["license_evidence"]["scope"] = "collection_assumed"
    with pytest.raises(ValueError, match="per-asset"):
        assets.validate_source(record)
    record = source(tmp_path)
    Path(record["license_evidence"]["path"]).write_text("changed rights")
    with pytest.raises(ValueError, match="evidence bytes"):
        assets.validate_source(record)
    record = source(tmp_path)
    record["license_evidence"]["binding_quote"] = "invented permission"
    with pytest.raises(ValueError, match="binding quote"):
        assets.validate_source(record)


def test_synthetic_ownership_not_inferred(tmp_path):
    record = source(tmp_path)
    record["synthetic"] = True
    with pytest.raises(ValueError, match="component-level"):
        assets.validate_source(record)
    record["generation_provenance"] = dict(all_components_owned_or_permitted=True, scene_seed=1)
    assert assets.validate_source(record)


def test_freeze_detects_controller_drift_and_refuses_replacement(tmp_path, monkeypatch):
    controller = tmp_path / "policy.py"
    controller.write_text("frozen original")
    monkeypatch.setattr(assets, "ROOT", tmp_path)
    monkeypatch.setattr(assets, "frozen_paths", lambda: [controller])
    path = tmp_path / "freeze.json"
    assets.freeze_controllers(path)
    assert assets.verify_controller_freeze(path)["verified"]
    with pytest.raises(ValueError, match="immutable"):
        assets.freeze_controllers(path)
    controller.write_text("changed model")
    with pytest.raises(ValueError, match="changed after freeze"):
        assets.verify_controller_freeze(path)


def test_ingest_manifest_counts_units_not_files_and_quarantines_short_sequences(tmp_path, monkeypatch):
    (tmp_path / "master").mkdir()
    (tmp_path / "derivative").mkdir()
    one = source(tmp_path / "master", title="One title", capture="one-session", media=b"master")
    two = source(tmp_path / "derivative", title="one title", capture="one-session", media=b"other encode")
    # Separate fixture names ensure each record's snapshotted bytes stay unchanged.
    request = tmp_path / "request.json"
    write_json(request, dict(abi=assets.ABI + "_request", assets=[one, two]))
    monkeypatch.setattr(assets, "verify_controller_freeze", lambda: dict(verified=True))
    monkeypatch.setattr(
        assets,
        "inspect_media",
        lambda path: dict(duration_ms=10000, width=3840, height=2160, frame_rate="60/1", codec="h264"),
    )
    result = assets.ingest(request, tmp_path / "imported")
    assert result["independent_source_clusters"] == 1 and result["native_ready_source_clusters"] == 0
    assert result["no_downloads_performed"] and not result["inferred_legal_permission"]
    assert all(r["no_looping_padding_or_interpolation_performed"] for r in result["assets"])
    assert (tmp_path / "imported" / "manifest.json").exists()
    with pytest.raises(ValueError, match="fresh"):
        assets.ingest(request, tmp_path / "imported")


def test_inspect_media_uses_actual_geometry_and_duration(monkeypatch):
    data = dict(
        streams=[dict(codec_name="h264", width=1920, height=1080, r_frame_rate="30000/1001")],
        format=dict(duration="90.5"),
    )
    monkeypatch.setattr(
        assets.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, json.dumps(data), "")
    )
    result = assets.inspect_media("owned.mp4")
    assert result["duration_ms"] == 90500 and result["frame_rate"] == "30000/1001"


def test_repeated_excerpts_do_not_pass_source_support(monkeypatch):
    from test_native_actuator_panel import rows

    data = rows(clips=10)
    # Each role/stratum really has only two source captures, despite ten files.
    for row in data:
        unit = row["clip_id"].rsplit("-", 1)[-1]
        name = f"{row['role']}-{row['complexity_stratum']}-capture-{int(unit) % 2}"
        provenance = dict(
            source_title=name, capture_group=name, source_sha256=hashlib.sha256(name.encode()).hexdigest()
        )
        row.update(provenance)
        row["cluster_id"] = row["block_id"] = assets.assign_clusters([provenance])[0]
    report = stats.analyze_panel(data)
    cell = report["cells"]["high:underutilized"]["stage1"]["roles"]["discovery"]
    assert cell["independent_source_clusters"] == 2 and cell["content_files_or_windows"] == 10
    assert not cell["support_qualified"] and not report["first_stage_valid_cells"]
    subset = [r for r in data if r["role"] == "discovery" and r["complexity_stratum"] == "high"]
    assert stats.panel_design(subset)[-1] == 1  # 2 source clusters, not ten clips
    assert not report["within_source_clip_independence_assumed"]


def test_different_cluster_ids_cannot_disguise_same_title_or_capture():
    from test_native_actuator_panel import rows

    data = rows(clips=2)
    first = data[0]
    last = data[-1]
    last["source_title"] = first["source_title"]
    with pytest.raises(ValueError, match="pseudo-replication"):
        stats.analyze_panel(data)


def test_all_same_title_cannot_meet_preregistered_unit_quota(tmp_path):
    clips = []
    for i in range(96):
        clips.append(
            dict(
                clip_id=str(i),
                cluster_id="source-one",
                source_title="One title",
                capture_group="one-session",
                source_sha256="a" * 64,
                complexity_stratum="low",
                segment=[i * 20000, (i + 1) * 20000],
                complexity=dict(score=0.1),
                source_complexity_score=0.1,
                panel_eligible=True,
            )
        )
    with pytest.raises(ValueError, match="independent source clusters insufficient.*1 available"):
        panel._build(dict(seed=1, source_units_per_stratum_role=16), dict(clips=clips), [])


def test_source_strata_weight_each_cluster_once():
    clips = [dict(cluster_id=f"source-{i}", complexity=dict(score=i / 10)) for i in range(6)]
    scores, thresholds = panel.cluster_scores(clips)
    duplicated = clips + [dict(clips[0]) for _ in range(95)]
    more_scores, more_thresholds = panel.cluster_scores(duplicated)
    assert scores == more_scores and thresholds == more_thresholds


def test_complete_acquisition_screen_plan_chain_binds_source_manifests(tmp_path, monkeypatch):
    # Full provenance/allocation chain with explicit media/complexity test doubles;
    # this is NOT an acquired corpus or native causal experiment.
    records = [
        source(tmp_path, title=f"Independent title {i}", capture=f"capture-{i}", media=f"owned-{i}".encode())
        for i in range(96)
    ]
    request = tmp_path / "request.json"
    write_json(request, dict(abi=assets.ABI + "_request", assets=records))
    monkeypatch.setattr(
        assets,
        "inspect_media",
        lambda path: dict(duration_ms=100000, width=640, height=360, frame_rate="30/1", codec="h264"),
    )
    imported = assets.ingest(request, tmp_path / "assets")
    assert imported["native_ready_source_clusters"] == 96
    catalogs = [tmp_path / "assets" / f"asset-{i:04d}.json" for i in range(96)]
    monkeypatch.setattr(panel.physical.reservations, "reservations", lambda root: ([], {}))

    def complexity(catalog, segment, ffmpeg):
        index = int(catalog["source_title"].rsplit(" ", 1)[1])
        score = (index + 1) / 100
        return dict(
            spatial=score, temporal=score, score=score, sampled_frames=100, no_treatment_outcomes_used=True
        )

    monkeypatch.setattr(panel, "_screen_clip", complexity)
    screen = panel.screen_inventory(catalogs, tmp_path, tmp_path / "screen", limit=120)
    assert screen["source_clusters"] == 96
    assert len(screen["clips"]) == 120
    assert panel._screen(tmp_path / "screen" / "screen.json") == screen
    for c in screen["clips"]:
        assert {
            "clip_id",
            "source",
            "source_title",
            "license",
            "license_url",
            "capture_group",
            "resolution",
            "fps",
            "duration_ms",
            "spatial_complexity",
            "temporal_complexity",
            "motion_score",
            "content_stratum",
            "panel_split",
            "sha256",
        } <= c.keys()
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    template = template_dir / "runtime.json"
    write_json(
        template,
        dict(
            conditions={"random-hold-a": dict(model="frozen")}, repair_model=None, learner=None, order_seed=10
        ),
    )
    from media_rl.native_protocol import seal_directory

    seal_directory(template_dir, ["runtime.json"], panel.physical.donor.PARENT_SEAL)
    monkeypatch.setattr(panel.physical.donor, "compatible_engines", lambda p: True)
    settings = json.loads((assets.ROOT / "configs/native_actuator_powered_panel_v1.json").read_text())
    settings.update(template=str(template), reservation_root=str(tmp_path), power_simulations=100)
    settings_path = tmp_path / "settings.json"
    write_json(settings_path, settings)
    planned = panel.plan_panel(settings_path, tmp_path / "screen" / "screen.json", tmp_path / "plan")
    assert len(planned["clips"]) == 96
    assert len({c["cluster_id"] for c in planned["clips"]}) == 96
    assert sum(len(p["episodes"]) for p in planned["runtimes"].values()) == 1920
    roles = {role: {c["cluster_id"] for c in planned["clips"] if c["role"] == role} for role in stats.ROLES}
    assert not roles["discovery"] & roles["replication"]
    assert all(c["panel_split"] == c["role"] for c in planned["clips"])
    assert panel.validate_panel(planned) == planned
    # Externally bound accompanying license evidence is reverified, not blindly
    # accepted because a source JSON was previously sealed.
    proof = Path(records[0]["license_evidence"]["path"])
    proof.write_text("changed terms")
    with pytest.raises(ValueError, match="evidence bytes"):
        panel.validate_panel(planned)


def test_registry_requires_license_review_and_does_not_claim_acquired_assets():
    registry = json.loads((assets.ROOT / "configs/native_panel_acquisition_sources_v1.json").read_text())
    assert registry["target_independent_source_units"] == 96
    assert registry["media_download_budget_bytes"] == 0 and not registry["downloads_enabled"]
    assert all(s["acquired_units"] == 0 for s in registry["sources"])
    assert registry["blinded_reestimation"]["baseline_96_uses_assumed_not_measured_variance"]
    assert not registry["blinded_reestimation"]["enabled"]
    assert assets.verify_controller_freeze()["verified"]
