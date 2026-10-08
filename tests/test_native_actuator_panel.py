"""Powered panel provenance, clustered effects and preintervention stratification."""

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from media_rl import native_actuator_panel as panel
from media_rl import native_actuator_panel_statistics as stats
from media_rl import native_panel_assets as assets
from media_rl.native_protocol import write_json


def rows(clips=10, repeats=2, seed=43, heterogeneous=True):
    rng = np.random.default_rng(seed)
    result = []
    for role in stats.ROLES:
        for s, stratum in enumerate(stats.STRATA):
            for clip in range(clips):
                identifier = f"{role}-{stratum}-{clip}"
                provenance = dict(
                    source_title=identifier,
                    capture_group=identifier,
                    source_sha256=hashlib.sha256(identifier.encode()).hexdigest(),
                )
                cluster = assets.assign_clusters([provenance])[0]
                clip_slope = rng.normal(0, 0.01)
                for regime_index, regime in enumerate(stats.REGIMES):
                    for replicate in range(repeats):
                        peer = f"{identifier}-{regime}-{replicate}"
                        offset = rng.normal(0, 0.01)
                        for epoch in range(6):
                            arm = int(rng.integers(3))
                            slope = (0.005 if s == 0 and heterogeneous else 0.7) + clip_slope
                            if heterogeneous and regime_index == 2:
                                slope *= 0.5
                            actual = 0.4 + slope * stats.RATIOS[arm] + offset + rng.normal(0, 0.003)
                            state = {k: dict(status="absent", value=None) for k in stats.base.COVARIATES}
                            state["previous_action"] = None
                            result.append(
                                dict(
                                    clip_id=identifier,
                                    block_id=cluster,
                                    cluster_id=cluster,
                                    **provenance,
                                    role=role,
                                    complexity_stratum=stratum,
                                    network_regime=regime,
                                    replicate=replicate,
                                    trial_id=peer,
                                    epoch=epoch,
                                    arm=arm,
                                    ratio=stats.RATIOS[arm],
                                    propensity=1 / 3,
                                    only_factual_outcome=True,
                                    state=state,
                                    base_bwe_bps=600000.0,
                                    requested_bps=stats.RATIOS[arm] * 600000,
                                    encoder_bps=actual * 600000,
                                    send_bps=(actual + rng.normal(0, 0.001)) * 600000,
                                    utility=15 + 20 * actual + rng.normal(0, 0.03),
                                    ontime_fraction=0.95,
                                    clipped_or_aliased=False,
                                    complete=True,
                                    plateau_observed=False,
                                )
                            )
    return result


def test_no_fake_independent_blocks_from_repeated_peers():
    report = stats.analyze_panel(rows(clips=2, repeats=5))
    cell = report["cells"]["high:near-capacity"]
    assert cell["stage1"]["roles"]["discovery"]["native_peers"] == 10
    assert cell["stage1"]["roles"]["discovery"]["independent_source_clusters"] == 2
    assert not cell["stage1"]["qualified"]
    assert cell["stage2"]["status"] == "deferred_until_cell_first_stage_replicates"
    assert report["independent_source_clusters_per_role"] == dict(discovery=6, replication=6)


def test_strong_complex_only_actuation_not_global_failure():
    report = stats.analyze_panel(rows())
    assert not report["cells"]["low:underutilized"]["stage1"]["qualified"]
    assert report["cells"]["high:underutilized"]["stage1"]["qualified"]
    assert report["cells"]["high:underutilized"]["stage2"]["qualified"]
    assert report["effect_heterogeneity_established"]
    assert report["interactions"]["complexity_stratum"]["replicated"]
    assert report["interactions"]["network_regime"]["replicated"]
    assert not report["all_cells_first_stage_qualified"]
    assert not report["cells"]["high:underutilized"]["stage2"]["actual_bitrate_causal_effect_established"]
    assert report["actuator_validity"]["status"] == "not_fitted"
    assert report["actuator_validity"]["no_safety_gate_modified"]
    assert report["policy_models_fitted"] == 0 and not report["learned_controller_promoted"]


def test_homogeneous_effect_is_not_an_interaction():
    report = stats.analyze_panel(rows(heterogeneous=False))
    assert len(report["first_stage_valid_cells"]) == 12
    assert not report["effect_heterogeneity_established"]
    assert not report["interactions"]["complexity_stratum"]["replicated"]


def test_clip_leakage_and_propensity_forgery_rejected():
    data = rows(clips=2)
    data[-1].update(
        {k: data[0][k] for k in ("block_id", "cluster_id", "source_title", "capture_group", "source_sha256")}
    )
    data[-1]["clip_id"] = "another-excerpt-same-source"
    with pytest.raises(ValueError, match="role leakage"):
        stats.analyze_panel(data)
    data = rows(clips=2)
    data[0]["propensity"] = 1.0
    with pytest.raises(ValueError, match="provenance"):
        stats.analyze_panel(data)
    data = rows(clips=2)
    data[0]["block_id"] += "-fake-independent-peer"
    with pytest.raises(ValueError, match="source-cluster"):
        stats.analyze_panel(data)


def test_factual_zero_is_retained_and_none_only_censored():
    data = rows(clips=2)
    data[0].update(encoder_bps=0.0, utility=0.0, plateau_observed=False)
    data[1].update(complete=False, encoder_bps=None, utility=None)
    report = stats.analyze_panel(data)
    result = report["cells"]["low:underutilized"]["stage1"]["roles"]["discovery"]
    assert result["complete"] == result["assigned"] - 1
    assert result["non_plateau"] == result["complete"]
    assert result["non_plateau_not_excluded"]


def test_complexity_measured_from_owned_frames_not_encoder_outcomes():
    static = np.zeros((100, 20, 40), np.uint8)
    easy = panel.complexity_features(static)
    rng = np.random.default_rng(2)
    hard = panel.complexity_features(rng.integers(0, 256, static.shape, dtype=np.uint8))
    assert easy["score"] == 0 and hard["temporal"] > 0 and hard["spatial"] > 0
    assert hard["score"] > easy["score"]
    assert panel.SCREEN_RECIPE["no_QP_bitrate_or_QoE_used"]
    with pytest.raises(ValueError):
        panel.complexity_features(static[:1])


def test_inventory_excludes_all_roles_and_does_not_reserve(tmp_path, monkeypatch):
    movie = tmp_path / "owned.mp4"
    movie.write_bytes(b"owned movie placeholder")
    catalog = dict(
        source_abi="recorded_video_v1",
        path=str(movie),
        sha256=panel.digest(movie),
        duration_ms=160000,
        attribution="owned",
        license_url="https://example.org/license",
        rights_asserted_by_importer=True,
        not_representative_corpus=True,
    )
    path = tmp_path / "catalog.json"
    write_json(path, catalog)
    monkeypatch.setattr(
        panel.physical.reservations,
        "reservations",
        lambda root: ([dict(sha256=catalog["sha256"], segment=[60000, 100000])], {}),
    )
    output = panel.inventory([path], tmp_path)
    assert output["no_content_reserved_by_inventory"]
    assert all(c["segment"][0] >= 100000 for c in output["clips"])
    assert len({c["clip_id"] for c in output["clips"]}) == output["available_unique_clips"]
    assert not output["outcome_data_used"]


def test_prospective_power_is_serializable_and_not_causal_evidence():
    assumptions = dict(
        adjacent_effect_actual_over_bwe=0.15,
        source_random_slope_sd=0.1,
        peer_noise_sd=0.08,
        cohort_noise_sd=0.08,
    )
    a = stats.power_projection(8, 5, assumptions, draws=20, seed=13)
    b = stats.power_projection(8, 5, assumptions, draws=20, seed=13)
    assert a == b
    assert a["source_clusters_per_cell_role"] == 8 and a["expected_cohorts_per_cell_role"] == 240
    assert a["sensitivity_not_guarantee"] and not a["empirical_power_established"]
    assert a["policy_models_fitted"] == 0
    json.dumps(a, allow_nan=False)
    weak = stats.power_projection(8, 5, dict(assumptions, adjacent_effect_actual_over_bwe=0.005), draws=20)
    assert not weak["projected_80_percent_power"]


def test_insufficient_fresh_strata_is_blocker_not_negative_result(tmp_path, monkeypatch):
    settings = dict(source_units_per_stratum_role=8, seed=4)
    screening = dict(clips=[], catalogs={})
    with pytest.raises(ValueError, match="fresh low independent source clusters insufficient"):
        panel._build(settings, screening, [])


def test_prefix_cannot_qualify_even_with_significant_synthetic_effect():
    report = stats.analyze_panel(rows(heterogeneous=False))
    assert report["first_stage_valid_cells"]
    panel.prohibit_prefix_qualification(report)
    assert not report["first_stage_valid_cells"] and not report["outcome_sensitive_cells"]
    assert report["prefix_only_not_qualification"]
    assert all(
        not c["stage1"]["qualified"] and not c["stage2"]["qualified"] for c in report["cells"].values()
    )


def test_failed_panel_prefix_preserved_and_no_overwrite(tmp_path, monkeypatch):
    protocol = tmp_path / "protocol.json"
    write_json(
        protocol,
        dict(settings=dict(seed=1), runtimes=dict(one=dict(episodes=[dict(id="native", role="discovery")]))),
    )
    monkeypatch.setattr(panel, "verify_seal", lambda *args: {})
    monkeypatch.setattr(panel, "validate_panel", lambda p: p)

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["node"], stderr="no factual encoder output")

    monkeypatch.setattr(panel.subprocess, "run", fail)
    out = tmp_path / "capture"
    with pytest.raises(subprocess.CalledProcessError):
        panel.run_panel(protocol, out)
    failure = json.loads((out / "failure.json").read_text())
    assert failure["rerun_requires_fresh_path"] and failure["collector_stderr"] == "no factual encoder output"
    assert (out / "protocol.json").exists()
    with pytest.raises(ValueError, match="fresh"):
        panel.run_panel(protocol, out)


def test_queue_summary_does_not_forge_browser_relay_clock_alignment(tmp_path):
    import gzip

    events = [
        dict(kind="phase", capacity_mbps=0.6),
        dict(kind="offer", direction="a_to_b", wire_bytes=1000, queue_after_wire_bytes=1000, dropped=False),
        dict(kind="offer", direction="a_to_b", wire_bytes=1000, queue_after_wire_bytes=1000, dropped=True),
    ]
    with gzip.open(tmp_path / "events.jsonl.gz", "wt") as f:
        f.write("\n".join(json.dumps(e) for e in events))
    result = panel.peer_queue_realization(tmp_path)
    assert result["observed_capacity_mbps"] == [0.6] and result["dropped_datagrams"] == 1
    assert result["scope"] == "entire_peer_not_cohort_aligned" and result["no_cross_clock_alignment_assumed"]


def test_real_factorial_scheduler_and_raw_run_audit_pipeline(tmp_path, monkeypatch):
    # Small construction fixture, NOT a qualified content panel. The real old
    # runtime/scheduler is used; only native capture/raw audit are test doubles.
    import gzip

    template_path = tmp_path / "template.json"
    write_json(
        template_path,
        dict(
            conditions={"random-hold-a": dict(model="frozen")}, repair_model=None, learner=None, order_seed=10
        ),
    )
    monkeypatch.setattr(panel.physical.donor, "compatible_engines", lambda p: True)
    monkeypatch.setattr(panel, "verify_seal", lambda *args: {})
    clips = []
    catalogs = {}
    for si, stratum in enumerate(stats.STRATA):
        for i in range(2):
            source = hashlib.sha256(f"source-{si}-{i}".encode()).hexdigest()
            provenance = dict(
                source_title=f"title-{si}-{i}", capture_group=f"capture-{si}-{i}", source_sha256=source
            )
            catalogs[source] = dict(sha256=source)
            segment = [60000, 80000]
            clips.append(
                dict(
                    clip_id=panel.clip_identity(source, segment),
                    **provenance,
                    cluster_id=assets.assign_clusters([provenance])[0],
                    segment=segment,
                    complexity_stratum=stratum,
                    source_complexity_score=si * 0.1,
                    panel_eligible=True,
                    complexity=dict(score=si * 0.1),
                )
            )
    settings = dict(seed=19, source_units_per_stratum_role=1, replicates=2, template=str(template_path))
    monkeypatch.setattr(assets, "verify_controller_freeze", lambda *args: dict(verified=True))
    chosen, runtimes = panel._build(settings, dict(clips=clips, catalogs=catalogs), [])
    assert len(chosen) == 6 and len(runtimes) == 6
    assert sum(len(p["episodes"]) for p in runtimes.values()) == 48
    for p in runtimes.values():
        assert p["extra_source_sha256"] == {
            k: panel.digest(v) for k, v in panel.physical.extra_sources().items()
        }
        assert p["measurement_recipe"] == panel.physical.RECIPE
        assert {t["network_regime"] for t in p["episodes"]} == set(stats.REGIMES)
        assert len({t["exploration_seed"] for t in p["episodes"]}) == 8
        assert len({t["clip_id"] for t in p["episodes"]}) == 1
    cfg = dict(settings=settings, runtimes=runtimes)
    protocol = tmp_path / "protocol.json"
    write_json(protocol, cfg)
    monkeypatch.setattr(panel, "validate_panel", lambda p: p)
    seed_row = rows(clips=2)[0]

    def capture(args, **kwargs):
        root = Path(args[2])
        root.mkdir()
        with gzip.open(root / "events.jsonl.gz", "wt") as f:
            f.write(json.dumps(dict(kind="phase", capacity_mbps=0.6)) + "\n")
        return subprocess.CompletedProcess(args, 0)

    def raw_audit(root, p, trial):
        cohorts = []
        for epoch in range(6):
            row = dict(
                seed_row, role=trial["role"], block_id=trial["block_id"], trial_id=trial["id"], epoch=epoch
            )
            cohorts.append(row)
        return dict(id=trial["id"]), dict(wire=dict(fifo_capacity_accounting_verified=True)), cohorts

    monkeypatch.setattr(panel.subprocess, "run", capture)
    monkeypatch.setattr(panel.physical, "audit_peer", raw_audit)
    # Restore real seals for capture and audit; the fixture protocol is authorized
    # by the explicit validator double above, not labelled production evidence.
    from media_rl.native_protocol import verify_seal

    monkeypatch.setattr(panel, "verify_seal", verify_seal)
    from media_rl.native_protocol import seal_directory

    seal_directory(tmp_path, ["protocol.json"], panel.ABI + "_plan")
    out = tmp_path / "prefix"
    report = panel.run_panel(protocol, out, max_peers=2)
    assert report["prefix_only_not_qualification"] and not report["complete_prospective_inventory"]
    audited = panel.audit_panel(out)
    assert audited["native_peers"] == 2 and audited["cohorts"] == 12
    assert not audited["complete_prospective_inventory"]
    full_out = tmp_path / "full"
    full_report = panel.run_panel(protocol, full_out)
    assert full_report["complete_prospective_inventory"] and not full_report["first_stage_valid_cells"]
    assert panel.audit_panel(full_out)["native_peers"] == 48
    saved = json.loads((full_out / "cohorts.json").read_text())
    assert saved[0]["network_realization"]["peer_queue"]["scope"] == "entire_peer_not_cohort_aligned"


def test_public_cli_and_config_registration():
    root = Path(__file__).resolve().parents[1]
    assert (
        'media-actuator-panel = "media_rl.native_actuator_panel:main"'
        in (root / "pyproject.toml").read_text()
    )
    settings = panel._settings(
        json.loads((root / "configs/native_actuator_powered_panel_v1.json").read_text())
    )
    assert settings["iv_assumptions_explicitly_assumed"] is False
    assert set(panel.REGIMES) == set(stats.REGIMES)
    result = subprocess.run(["media-actuator-panel", "--help"], capture_output=True, text=True, check=True)
    assert "inventory" in result.stdout and "screen" in result.stdout and "audit" in result.stdout
