import csv
import json
from dataclasses import replace

import pytest
from test_learning import tiny_config

from media_rl.cli import main
from media_rl.evidence import export_paper, matched_method_contrast, run_status
from media_rl.experiment import (
    dump_json,
    evaluate_experiment,
    initialize,
    manifest,
    run_experiment,
    sha256,
    train_experiment,
)
from media_rl.reporting import build_report
from media_rl.scenarios import SCENARIOS


def test_matched_contrast_uses_explicit_reference_and_training_seed_clusters():
    episodes = []
    for seed, pairs in [(1, [(3.0, 1.0), (5.0, 1.0)]), (2, [(10.0, 1.0), (14.0, 1.0)])]:
        for trace, (candidate_value, reference_value) in enumerate(pairs):
            common = {
                "domain": "id",
                "model_seed": seed,
                "test_seed": trace,
                "scenario": "steady",
            }
            episodes.extend(
                [
                    {**common, "method": "calibrated_v1", "qoe": reference_value},
                    {**common, "method": "calibrated", "qoe": 100.0},
                    {**common, "method": "shielded", "qoe": candidate_value},
                ]
            )

    result = matched_method_contrast(episodes, "id", "shielded", "calibrated_v1", "qoe", samples=100, seed=17)
    assert result["mean"] == pytest.approx(7.0)
    assert result["n"] == 2


def test_status_is_read_only_and_does_not_infer_process_liveness(tmp_path):
    config = tiny_config()
    run = initialize(tmp_path / "run", config)
    before = {str(p): sha256(p) for p in run.rglob("*") if p.is_file()}
    status = run_status(run)
    after = {str(p): sha256(p) for p in run.rglob("*") if p.is_file()}
    assert before == after
    assert status["phase"] == "training" and status["models_complete"] == 0
    assert not status["integrity_checked"]
    (run / "models").mkdir()
    (run / "models/seed_7.json").write_text('{"policy":')
    assert "7" in run_status(run)["checkpoint_errors"]
    main(["status", "--run", str(run)])


def test_export_matches_audited_data_and_has_provenance(tmp_path):
    run = run_experiment(tiny_config(), tmp_path / "run", plots=False)
    status = run_status(run)
    assert status["phase"] == "complete" and status["models_complete"] == 1
    before = sha256(run / "manifest.json")
    out = tmp_path / "paper"
    data = export_paper(run, out)
    assert before == sha256(run / "manifest.json")
    assert data["integrity_checked"] and data["episodes"] == 15 and data["steps"] == 300
    assert data["manifest_sha256"] == before
    with (run / "summary.csv").open() as file:
        row = next(
            r
            for r in csv.DictReader(file)
            if (r["scope"], r["group"], r["method"], r["metric"])
            == ("domain", "ood", "calibrated", "violation_rate")
        )
    assert (
        f"{{\\EvidenceOODRLCDUnsafePct}}{{{float(row['mean']) * 100:.3f}}}"
        in (out / "evidence.tex").read_text()
    )
    for name, digest in data["generated_sha256"].items():
        assert sha256(out / name) == digest
    main(["export-paper", "--run", str(run), "--out", str(out)])
    assert json.loads((out / "provenance.json").read_text())["source_run"] == str(run.resolve())
    assert "raw" in (out / "table_calibration.tex").read_text()
    with pytest.raises(ValueError, match="outside"):
        export_paper(run, run / "paper")
    (run / "summary.csv").write_text("tampered")
    with pytest.raises(ValueError, match="integrity"):
        export_paper(run, out)


def test_v4_export_includes_locked_decision_family_and_scenario_tables(tmp_path):
    config = replace(
        tiny_config(),
        scenarios=list(SCENARIOS),
        methods=["safe", "gcc", "rl", "calibrated_v1", "calibrated", "uncalibrated"],
    ).validate()
    models = train_experiment(config, tmp_path / "models")
    run = tmp_path / "run"
    evaluate_experiment(config, models, run, model_map={"calibrated_v1": models})
    build_report(run, plots=False)
    dump_json(
        run / "selection.json",
        {
            "selected_controller": "calibrated_v1",
            "candidate_promoted": False,
            "candidate_feasible": False,
            "baseline_metrics": {
                "id_qoe": 1.0,
                "id_violation_rate": 0.01,
                "stress_qoe": 0.5,
                "stress_violation_rate": 0.20,
            },
            "candidate_metrics": {
                "id_qoe": 0.9,
                "id_violation_rate": 0.02,
                "stress_qoe": 0.4,
                "stress_violation_rate": 0.25,
            },
            "baseline_score": 0.25,
            "candidate_score": -0.125,
            "score_gain": -0.375,
            "stress_scenario_violation_deltas": {
                name: 0.04 if name == "bufferbloat" else -0.01
                for name, domain in SCENARIOS.items()
                if domain == "ood"
            },
            "protocol": {"max_stress_scenario_violation_increase": 0.03},
        },
    )
    manifest(run, config, "complete")
    out = tmp_path / "paper"
    evidence = export_paper(run, out, prefix="Random")
    assert evidence["integrity_checked"]
    assert "table_policy_randomization.tex" in evidence["generated_sha256"]
    assert "table_randomization_families.tex" in evidence["generated_sha256"]
    assert "table_randomization_scenarios.tex" in evidence["generated_sha256"]
    assert "Not promoted" in (out / "table_policy_randomization.tex").read_text()
    families = (out / "table_randomization_families.tex").read_text()
    assert "bufferbloat" in families and "Fail" in families
    scenarios = (out / "table_randomization_scenarios.tex").read_text()
    assert "handover" in scenarios and "Delta (pp)" in scenarios
    macros = (out / "evidence.tex").read_text()
    assert "RandomOODVoneQoE" in macros and "RandomOODDeltaVoneQoE" in macros


def test_v5_export_includes_shield_selection_and_fresh_test_tables(tmp_path):
    config = replace(
        tiny_config(),
        scenarios=list(SCENARIOS),
        methods=["safe", "gcc", "rl", "calibrated_v1", "calibrated", "shielded", "uncalibrated"],
    ).validate()
    models = train_experiment(config, tmp_path / "models")
    run = tmp_path / "run"
    evaluate_experiment(config, models, run, model_map={"calibrated_v1": models})
    build_report(run, plots=False)
    (run / "shield_diagnostics.csv").write_text(
        "domain,model_seed,steps,intervention_rate,no_safe_candidate_rate,proposal_violation_rate,executed_violation_rate,intervention_proposal_violation_rate,intervention_executed_violation_rate,interventions\\n"
        "id,7,100,0.02,0.01,0.1,0.08,0.5,0.2,2\\n"
        "ood,7,100,0.03,0.02,0.2,0.15,0.6,0.3,3\\n"
    )
    dump_json(
        run / "selection.json",
        {
            "selected_controller": "calibrated_v1",
            "candidate_method": "shielded",
            "candidate_promoted": False,
            "candidate_feasible": False,
            "baseline_metrics": {
                "id_qoe": 1.0,
                "id_violation_rate": 0.01,
                "stress_qoe": 0.5,
                "stress_violation_rate": 0.20,
            },
            "candidate_metrics": {
                "id_qoe": 0.9,
                "id_violation_rate": 0.02,
                "stress_qoe": 0.4,
                "stress_violation_rate": 0.25,
            },
            "baseline_score": 0.25,
            "candidate_score": -0.125,
            "score_gain": -0.375,
            "stress_scenario_violation_deltas": {
                name: 0.04 if name == "bufferbloat" else -0.01
                for name, domain in SCENARIOS.items()
                if domain == "ood"
            },
            "protocol": {"max_stress_scenario_violation_increase": 0.03},
        },
    )
    manifest(run, config, "complete")
    out = tmp_path / "paper"
    evidence = export_paper(run, out, prefix="Shield")
    assert "table_action_shield.tex" in evidence["generated_sha256"]
    assert "table_action_shield_families.tex" in evidence["generated_sha256"]
    assert "table_action_shield_contrasts.tex" in evidence["generated_sha256"]
    assert "table_action_shield_scenarios.tex" in evidence["generated_sha256"]
    assert "Top-five action shield" in (out / "table_action_shield.tex").read_text()
    assert "Not promoted" in (out / "table_action_shield.tex").read_text()
    assert "bufferbloat" in (out / "table_action_shield_families.tex").read_text()
    assert "Shield minus v1" in (out / "table_action_shield_contrasts.tex").read_text()
    assert "wifi" in (out / "table_action_shield_scenarios.tex").read_text()
    assert "table_action_shield_diagnostics.tex" in evidence["generated_sha256"]
    diagnostic_table = (out / "table_action_shield_diagnostics.tex").read_text()
    assert "Action replacement" in diagnostic_table
    assert r"Rate (\%)" in diagnostic_table
    assert "table_action_selection_calibration.tex" in evidence["generated_sha256"]
    selection_table = (out / "table_action_selection_calibration.tex").read_text()
    assert "Screen-selected action" in selection_table
    assert "Selected replacement action" in selection_table
    assert "Confidence minus safe (pp)" in selection_table
    assert evidence["source_files"]["steps.csv.gz"] == sha256(run / "steps.csv.gz")


def test_export_rejects_partial_runs(tmp_path):
    run = initialize(tmp_path / "partial", tiny_config())
    dump_json(run / "manifest.json", {"stage": "trained"})
    with pytest.raises(ValueError, match="completed"):
        export_paper(run, tmp_path / "paper")
    assert not (tmp_path / "paper").exists()


def test_export_rejects_manifest_path_escape(tmp_path):
    run = run_experiment(tiny_config(), tmp_path / "run", plots=False)
    outside = tmp_path / "outside"
    outside.write_text("not an experiment artifact")
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["artifacts_sha256"]["../outside"] = sha256(outside)
    dump_json(run / "manifest.json", manifest)
    with pytest.raises(ValueError, match="integrity"):
        export_paper(run, tmp_path / "paper")
