"""Synthetic SOFTWARE tests; never native learned-performance evidence."""

from pathlib import Path

import pytest
from native_study_helpers import bundle as legacy_bundle
from test_native_action import bundle as action_bundle

from media_rl import native_action_live_study as live
from media_rl import native_dense_study as dense
from media_rl.native_protocol import digest, read_json, seal_directory, write_json
from media_rl.native_repair5_study import trial_schedule
from media_rl.native_video import VIDEO_ABI

ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"synthetic SOFTWARE fixture, not native movie evidence")
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
    old = tmp_path / "legacy.json"
    write_json(old, legacy_bundle())
    parent = tmp_path / "legal-parent.json"
    write_json(parent, dict(synthetic_not_native=True))
    folder = tmp_path / "fitted"
    folder.mkdir()
    b = action_bundle()
    b.update(
        provenance={str(parent): digest(parent)},
        source_reservations=[dict(sha256=digest(movie), segment=[60000, 80000])],
        source_sha256={
            "python/native_action_policy.py": digest(ROOT / "src/media_rl/native_action_policy.py")
        },
    )
    write_json(folder / "model.json", b)
    write_json(
        folder / "training_report.json",
        dict(
            training_cv=dict(
                passed=True,
                folds=[dict(utility_skill=0.2, risk_skill=0.1), dict(utility_skill=0.3, risk_skill=0.1)],
            ),
            diagnostic_selected_validation_test_labels_used=False,
            native_deployment_qualified=False,
            synthetic_not_native=True,
        ),
    )
    seal_directory(
        folder, ["model.json", "training_report.json"], "bounded_action_candidate_fitted", SOTA_achieved=False
    )
    plan = tmp_path / "live.json"
    p = live.plan_live_study(
        old, folder / "model.json", catalog, plan, results_directory=tmp_path / "results"
    )
    return p, plan


def test_fresh_prospective_roles_orders_and_original_gates(tmp_path):
    p, path = fixture(tmp_path)
    assert read_json(path) == p
    assert p["groups"][0]["video_segment"] == [80000, 100000]
    assert live.compatible_engines(p)
    assert len(trial_schedule(p)) == 8
    assert p["stage"] == "repeatability" and p["conditions"] == live.CONDITIONS
    assert p["controller_config"]["miss_budget"] == 0.1
    assert p["controller_config"]["disagreement_budget"] == 0.15
    assert p["limits"]["inference_p99_ms"] == 10
    assert live.MIN_GENUINE_USE_FRACTION == 0.05
    assert p["learner"] is None and not p["native_deployment_qualified"] and not p["SOTA_achieved"]
    with pytest.raises(ValueError, match="plan exists"):
        live.plan_live_study(
            p["models"]["source"]["path"], p["repair_model"]["path"], tmp_path / "catalog.json", path
        )


@pytest.mark.parametrize(
    "stage", ["train", "calibration", "selected-calibration", "validation", "test", "diagnostic"]
)
def test_live_may_not_relabel_for_fitting_or_qualification(tmp_path, stage):
    p, _ = fixture(tmp_path)
    p["stage"] = stage
    with pytest.raises(ValueError, match="repeatability-only"):
        live.validate_live_protocol(p)


@pytest.mark.parametrize(
    "mutation", ["risk", "tail", "compute", "controls", "order", "role_overlap", "schedule", "qualification"]
)
def test_guard_source_compute_and_schedule_forgeries_reject(tmp_path, mutation):
    p, _ = fixture(tmp_path)
    if mutation == "risk":
        p["controller_config"]["miss_budget"] = 0.2
    elif mutation == "tail":
        p["limits"]["inference_p99_ms"] = 11
    elif mutation == "compute":
        p["common_shadow_inference"] = False
    elif mutation == "controls":
        p["conditions"].pop("bwe-continuous")
    elif mutation == "order":
        p["groups"][0]["orders"][0].reverse()
    elif mutation == "role_overlap":
        p["groups"][0]["video_segment"] = [60000, 80000]
    elif mutation == "schedule":
        p["groups"][0]["schedule"][1][0] = 0.1
    else:
        p["native_deployment_qualified"] = True
    with pytest.raises(ValueError):
        live.validate_live_protocol(p)


def test_candidate_receipt_and_original_parent_mutations_reject(tmp_path):
    p, _ = fixture(tmp_path)
    b = read_json(p["repair_model"]["path"])
    parent = Path(next(iter(b["provenance"])))
    parent.write_bytes(b"changed")
    with pytest.raises(ValueError, match="parent changed"):
        live.validate_live_protocol(p)


def test_empty_or_partial_fit_manifest_does_not_prove_skill(tmp_path):
    p, _ = fixture(tmp_path)
    folder = Path(p["repair_model"]["path"]).parent
    manifest = read_json(folder / "manifest.json")
    manifest["artifacts_sha256"].pop("training_report.json")
    (folder / "manifest.json").unlink()
    write_json(folder / "manifest.json", manifest)
    with pytest.raises(ValueError, match="receipt seal"):
        live._candidate(p["repair_model"])


def test_all_recorded_namespaces_are_reserved_before_plan(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    run = results / "prior"
    run.mkdir()
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    for file, kind, segment in [
        (run / "protocol.json", live.SOURCE_KIND, [80000, 100000]),
        (config_dir / "native_prior.json", "recorded_video_future_role", [100000, 120000]),
    ]:
        write_json(
            file,
            dict(source_kind=kind, video_source=dict(sha256="f" * 64), groups=[dict(video_segment=segment)]),
        )
    excluded, inputs = live.reservations(results)
    assert len(excluded) == 2 and len(inputs) == 2


def test_projection_changes_only_declared_interfaces_and_isolates_audit():
    assets = ROOT / "benchmarks/native_rtc"
    old = (assets / "dense_episode.mjs").read_text()
    assert live.project_collector(old) == (assets / "action_live_episode.mjs").read_text()
    with pytest.raises(ValueError, match="anchor changed"):
        live.project_collector(old.replace("panel.stage!=='diagnostic'", "true"))
    assert dense.audit_dense_episode.__globals__["RepairPolicy"] is not live.ActionPolicy
    assert dense.audit_dense_episode.__globals__["STUDY_ABI"] == dense.STUDY_ABI
    assert live._RAW_AUDIT.__globals__["RepairPolicy"] is live.ActionPolicy
    assert live._RAW_AUDIT.__globals__["require"] is dense.audit_dense_episode.__globals__["require"]
    for check in (
        "replay_native_wire",
        "verify_live_capture_associations",
        "feedback was not causally",
        "content_encoder.snapshot",
        "_verify_all_models",
        "repair action readback mismatch",
    ):
        assert check in live._RAW_SOURCE


def test_common_shadow_history_is_reconstructed_not_merely_scored(monkeypatch):
    f = [0.0] * 16
    f[7] = 450000 / 4e6
    rows = [
        dict(observation=dict(features=f), all_policy_decisions=dict(source=dict(history=[0.0] * 48 + f)))
    ]
    monkeypatch.setattr(live, "_verify_all_models", lambda sender, bundles: 2.5)
    assert live._verify_causal_common_models(dict(decisions=rows), {}) == 2.5
    rows[0]["all_policy_decisions"]["source"]["history"][-9] = 300000 / 4e6
    with pytest.raises(ValueError, match="replay mismatch"):
        live._verify_causal_common_models(dict(decisions=rows), {})


@pytest.mark.parametrize(
    "field", ["fallback", "learned_departure", "departure_from_continuous_bwe", "cap", "controller"]
)
def test_actual_credit_requires_genuine_readback_and_both_references(field):
    d = dict(
        fallback=False,
        encoder_max_bitrate_bps=450000,
        learned_departure=True,
        departure_from_continuous_bwe=True,
    )
    assert live.executed_learned_action(d, 450000, "repair")
    cap, controller = 450000, "repair"
    if field == "fallback":
        d[field] = True
    elif field in d:
        d[field] = False
    elif field == "cap":
        cap = 400000
    else:
        controller = "explore"
    assert not live.executed_learned_action(d, cap, controller)


def software_rows(p):
    return [
        dict(
            **t,
            utility=10 if t["condition"].startswith("rlcd") else 12,
            eligible=100,
            ontime_fraction=0.8,
            inference_p99_ms=2.0,
            learned_fraction=0.1 if t["condition"].startswith("rlcd") else 0.0,
            actual_executed_learned_steps=10 if t["condition"].startswith("rlcd") else 0,
            decisions=100,
            phases={
                phase: dict(utility=10 if t["condition"].startswith("rlcd") else 12, ontime_fraction=0.8)
                for phase in ("high", "collapse", "recovery")
            },
        )
        for t in trial_schedule(p)
    ]


def test_report_is_complete_group_based_and_never_promotes(tmp_path):
    p, _ = fixture(tmp_path)
    rows = software_rows(p)
    report = live._report(rows, p)
    assert report["actual_executed_learned_steps"] == 40
    assert report["genuine_dual_and_continuous_use_fraction"] == 0.1
    assert report["genuine_use_gate_passed"] and report["identical_policy"]["passed"]
    assert (
        not report["native_improvement_proven"]
        and not report["native_deployment_qualified"]
        and not report["SOTA_achieved"]
    )
    assert report["paired_descriptive_contrasts"]["bwe-continuous"]["aggregate"]["utility"]["mean"] == -2
    assert report["paired_descriptive_contrasts"]["bwe"]["aggregate"]["utility"]["ci95"] is None
    for bad in (rows[:-1], rows[::-1], [rows[0], *rows[1:-1], rows[0]]):
        with pytest.raises(ValueError):
            live._report(bad, p)
    rows[0]["inference_p99_ms"] = 11
    assert not live._report(rows, p)["identical_policy"]["passed"]


def test_failure_preserves_prefix_and_refuses_overwrite(tmp_path, monkeypatch):
    p, config = fixture(tmp_path)
    out = tmp_path / "failed-live"

    def fail_collect(command, timeout, log):
        child = Path(command[2])
        child.mkdir()
        (child / "partial.txt").write_text("preserve this incomplete capture")
        raise RuntimeError("synthetic capture failure")

    monkeypatch.setattr(live, "_collect", fail_collect)
    monkeypatch.setattr(
        live,
        "_recover_cleanup_capture",
        lambda child, log: (_ for _ in ()).throw(ValueError("no completed outcome")),
    )
    with pytest.raises(ValueError, match="no completed"):
        live.run_live_study(config, out)
    assert read_json(out / "failure.json")["all_partial_evidence_preserved"]
    assert list(out.glob("*/partial.txt")) and not (out / "manifest.json").exists()
    with pytest.raises(FileExistsError):
        live.run_live_study(config, out)
    with pytest.raises(FileNotFoundError):
        live.audit_live_study(out)


@pytest.mark.parametrize(
    "command,flags",
    [
        ("plan", ["--source-model", "m", "--action-model", "a", "--video-source", "v", "--out", "o"]),
        ("study", ["--config", "c", "--out", "o"]),
        ("audit", ["--run", "r"]),
    ],
)
def test_public_live_commands_dispatch(command, flags, monkeypatch):
    from media_rl import native_action_live_cli
    from media_rl.cli import main

    calls = []
    monkeypatch.setattr(native_action_live_cli, "run", lambda args: calls.append(args))
    main(["native-action-live-" + command, *flags])
    assert calls[0].command == "native-action-live-" + command


@pytest.mark.parametrize("command", ["train", "calibrate", "promote", "test"])
def test_no_live_fitting_or_promotion_command(command):
    from media_rl.cli import main

    with pytest.raises(SystemExit):
        main(["native-action-live-" + command])
