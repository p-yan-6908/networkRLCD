"""Workflow tests with explicitly artificial collectors; live probes are separate."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from native_study_helpers import plan

import media_rl.native_study as study
from media_rl.native_calibration import recalibrate_native_study
from media_rl.native_protocol import ASSET_NAMES, asset_directory, digest, read_json, write_json


def mocked_collector(monkeypatch):
    def collect(command, timeout, log):
        child, runtime_path, trial_id, condition_id = map(Path, command[2:6])
        runtime = read_json(runtime_path)
        trial = next(x for x in runtime["episodes"] if x["id"] == str(trial_id))
        condition = runtime["conditions"][str(condition_id)]
        index = runtime["episodes"].index(trial)
        child.mkdir()
        Path(log).write_text("artificial collector fixture\n")
        shutil.copyfile(runtime_path, child / "panel_snapshot.json")
        for k, entry in runtime["models"].items():
            shutil.copyfile(entry["path"], child / ("model_" + k + ".json"))
        shutil.copyfile(runtime["models"][condition["model"]]["path"], child / "model.json")
        for asset in ASSET_NAMES:
            shutil.copyfile(
                asset_directory() / asset,
                child / ("source_snapshot.mjs" if asset == "episode.mjs" else asset),
            )
        for name in ("summary.json", "frame_events.json", "all_models.json"):
            write_json(child / name, {})
        (child / "events.jsonl.gz").write_bytes(b"artificial fixture, not wire evidence")
        decisions, labels = [], []
        for i in range(4):
            decisions.append(
                dict(
                    observation=dict(features=[0] * 16),
                    ack_ms=10 + i * 100,
                    changed=False,
                    actuation_readback=dict(
                        encoder_max_bitrate_bps=300000, receiver_jitter_buffer_target_ms=0
                    ),
                    policy_decision=dict(
                        action_index=1,
                        encoder_max_bitrate_bps=300000,
                        predicted_frame_miss=[0.2] * 7,
                        risk_disagreement=[0.1] * 7,
                        fallback=False,
                    ),
                )
            )
            for j in range(4):
                labels.append(
                    dict(
                        action_transition_inflight=False,
                        decision_id=i,
                        capture_request_ms=30 + i * 100 + j,
                        encoder_cap_bps=300000,
                        receiver_target_ms=0,
                        identifiable_ontime=j % 2 == 0,
                        ontime_sampled_psnr_contribution=40 if j % 2 == 0 else 0,
                    )
                )
        write_json(child / "sender_observations.json", dict(decisions=decisions))
        c = str(condition_id)
        utility = 23 if c == "candidate" else 18 if c == "bwe" else 20
        row = dict(
            **trial,
            utility=utility,
            ontime_fraction=0.9 if c == "candidate" else 0.8,
            inference_p99_ms=1.0,
            signals=dict(bwe_mbps=2.0),
            phases={
                phase: dict(utility=utility, ontime_fraction=0.9 if c == "candidate" else 0.8)
                for phase in ("high", "collapse", "recovery")
            },
            start_epoch_ms=index * 5000 + 1,
            cutoff_epoch_ms=index * 5000 + 4000,
        )
        write_json(child / "artificial_replay.json", dict(row=row, quality=dict(source_labels=labels)))

    def replay(root, protocol, trial, bundles):
        artificial = read_json(Path(root) / "artificial_replay.json")
        return artificial["row"], dict(quality=artificial["quality"])

    monkeypatch.setattr(study, "_collect", collect)
    monkeypatch.setattr(study, "audit_native_episode", replay)
    monkeypatch.setattr(study.shutil, "which", lambda _: "node")


def test_repeatability_run_and_audit_are_immutable_and_rederive_statistics(tmp_path, monkeypatch):
    mocked_collector(monkeypatch)
    _, config, _ = plan(tmp_path)
    out = tmp_path / "controls"
    report = study.run_native_study(config, out)
    assert report["identical_policy"]["passed"] is True
    before = {str(x): digest(x) for x in out.rglob("*") if x.is_file()}
    assert study.audit_native_study(out)["verified_peers"] == 48
    assert before == {str(x): digest(x) for x in out.rglob("*") if x.is_file()}
    with pytest.raises(FileExistsError):
        study.run_native_study(config, out)
    report["means"]["bwe"]["utility"] += 1
    (out / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="artifact changed"):
        study.audit_native_study(out)


def test_selected_calibration_validation_lock_and_fresh_final_test(tmp_path, monkeypatch):
    mocked_collector(monkeypatch)
    _, controls_config, model = plan(tmp_path)
    controls = tmp_path / "controls"
    study.run_native_study(controls_config, controls)
    cal_config = tmp_path / "cal-plan.json"
    study.plan_native_study(
        model, cal_config, stage="calibration", exclude_runs=[controls], groups_per_family=1
    )
    cal_run, fit = tmp_path / "calibration", tmp_path / "fit"
    study.run_native_study(cal_config, cal_run)
    report = recalibrate_native_study(cal_run, fit)
    assert report["actor_risk_weights_and_cutoffs_unchanged"]
    source, candidate = read_json(model), read_json(fit / "model.json")
    assert (
        source["q_weights"] == candidate["q_weights"] and source["risk_weights"] == candidate["risk_weights"]
    )
    assert source["risk_cutoff"] == candidate["risk_cutoff"] == 0.5
    validation_config, validation = tmp_path / "validation-plan.json", tmp_path / "validation"
    study.plan_native_study(
        model,
        validation_config,
        stage="validation",
        candidate=fit / "model.json",
        repeatability_run=controls,
        groups_per_family=2,
    )
    study.run_native_study(validation_config, validation)
    locked = (validation / "selection.json").read_bytes()
    assert read_json(validation / "selection.json")["selected"] == "candidate"
    final_config, final = tmp_path / "test-plan.json", tmp_path / "test"
    study.plan_native_study(
        model,
        final_config,
        stage="test",
        candidate=fit / "model.json",
        repeatability_run=controls,
        validation_run=validation,
        groups_per_family=2,
    )
    study.run_native_study(final_config, final)
    assert (final / "selection_snapshot.json").read_bytes() == locked
    assert (validation / "selection.json").read_bytes() == locked
    assert study.audit_native_study(final)["role"] == "test"
    with pytest.raises(ValueError, match="forbidden"):
        recalibrate_native_study(final, tmp_path / "forbidden-fit")
    protocol = read_json(final_config)
    protocol["models"]["candidate"]["sha256"] = "a" * 64
    final_config.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="model changed"):
        study.run_native_study(final_config, tmp_path / "changed-test")


def test_failed_collection_is_preserved_and_cannot_be_resumed_or_promoted(tmp_path, monkeypatch):
    _, config, _ = plan(tmp_path)
    monkeypatch.setattr(study.shutil, "which", lambda _: "node")

    def fail(*args):
        raise ValueError("test infrastructure interruption")

    monkeypatch.setattr(study, "_collect", fail)
    out = tmp_path / "partial"
    with pytest.raises(ValueError, match="interruption"):
        study.run_native_study(config, out)
    assert read_json(out / "failure.json")["partial_evidence_preserved"] is True
    assert not (out / "manifest.json").exists()
    with pytest.raises(FileExistsError):
        study.run_native_study(config, out)


def test_cleanup_interruption_resumes_original_driver_without_recollecting_outcomes(tmp_path, monkeypatch):
    mocked_collector(monkeypatch)
    _, config, _ = plan(tmp_path, groups=1)
    original_collect = study._collect
    count = [0]
    drivers = []

    def interrupted(command, timeout, log):
        drivers.append(command[1])
        original_collect(command, timeout, log)
        count[0] += 1
        if count[0] == 3:
            profile = Path(tempfile.mkdtemp(prefix="rlcd-native-rtc-"))
            (profile / "Default").mkdir()
            with Path(log).open("a") as stream:
                stream.write(
                    "[Error: ENOTEMPTY: directory not empty, rmdir '" + str(profile / "Default") + "']\n"
                )
            raise ValueError("native collector failed; cleanup after complete capture")

    monkeypatch.setattr(study, "_collect", interrupted)
    out = tmp_path / "interrupted"
    with pytest.raises(ValueError, match="cleanup"):
        study.run_native_study(config, out)
    before = {str(p): digest(p) for p in out.rglob("*") if p.is_file()}
    report = study.run_native_study(config, out, resume=True)
    assert report["episodes"] == 24 and count[0] == 24
    assert all(d == str(out / "sources/assets/episode.mjs") for d in drivers[3:])
    assert all(digest(p) == sha for p, sha in before.items())
    assert study.audit_native_study(out)["verified_peers"] == 24
    assert read_json(out / "resume_receipt_1.json")["no_completed_outcome_replaced"]
    assert any(p.name == "cleanup_recovery.json" for p in out.rglob("*"))
    with pytest.raises(ValueError, match="interrupted"):
        study.run_native_study(config, out, resume=True)


def test_resume_refuses_pre_outcome_failure_or_changed_role(tmp_path, monkeypatch):
    mocked_collector(monkeypatch)
    p, config, _ = plan(tmp_path, groups=1)

    def fail(command, timeout, log):
        Path(log).write_text("connection failed before measurement")
        Path(command[2]).mkdir()
        raise ValueError("connection failed")

    monkeypatch.setattr(study, "_collect", fail)
    out = tmp_path / "incomplete"
    with pytest.raises(ValueError):
        study.run_native_study(config, out)
    with pytest.raises(ValueError, match="complete post-outcome"):
        study.run_native_study(config, out, resume=True)
    p["stage"] = "calibration"
    p["conditions"] = dict(source=dict(controller="rlcd", model="source"))
    for g in p["groups"]:
        g["orders"] = [["source"], ["source"]]
    config.write_text(json.dumps(p))
    with pytest.raises(ValueError, match="changed the frozen"):
        study.run_native_study(config, out, resume=True)


def test_frozen_replay_allows_only_plumbing_drift_not_label_semantics(tmp_path, monkeypatch):
    mocked_collector(monkeypatch)
    _, config, _ = plan(tmp_path, groups=1)
    out = tmp_path / "sealed"
    study.run_native_study(config, out)
    original = study.source_identity

    def plumbing():
        values = original()
        values["assets/episode.mjs"] = "b" * 64
        values["python/native_study.py"] = "c" * 64
        return values

    monkeypatch.setattr(study, "source_identity", plumbing)
    assert study.audit_native_study(out)["read_only"] is True

    def changed_labels():
        values = plumbing()
        values["python/native_quality.py"] = "a" * 64
        return values

    monkeypatch.setattr(study, "source_identity", changed_labels)
    with pytest.raises(ValueError, match="behavioral/verifier"):
        study.audit_native_study(out)


def test_cleanup_refuses_any_path_outside_owned_temporary_profiles(tmp_path):
    child = tmp_path / "capture"
    child.mkdir()
    for name in ("summary.json", "frame_events.json", "sender_observations.json", "events.jsonl.gz"):
        (child / name).write_text("artificial fixture")
    log = tmp_path / "error.log"
    log.write_text("[Error: ENOTEMPTY: directory not empty, rmdir '" + str(tmp_path / "user-profile") + "']")
    with pytest.raises(ValueError, match="owned temporary"):
        study._recover_cleanup_capture(child, log)


def test_failed_repeatability_blocks_validation_before_browser_or_output(tmp_path, monkeypatch):
    mocked_collector(monkeypatch)
    _, config, model = plan(tmp_path)
    controls = tmp_path / "controls"
    study.run_native_study(config, controls)
    # This test models a prerequisite failure, not a resealed/forged empirical run.
    real_read = study.read_json

    def failed_report(path):
        data = real_read(path)
        if Path(path) == controls / "report.json":
            data["identical_policy"]["passed"] = False
        return data

    monkeypatch.setattr(study, "read_json", failed_report)
    monkeypatch.setattr(study, "audit_native_study", lambda *args, **kwargs: {})
    val_config = tmp_path / "validation-plan.json"
    study.plan_native_study(
        model, val_config, stage="validation", candidate=model, repeatability_run=controls
    )
    with pytest.raises(ValueError, match="repeatability failed"):
        study.run_native_study(val_config, tmp_path / "blocked")
    assert not (tmp_path / "blocked").exists()
