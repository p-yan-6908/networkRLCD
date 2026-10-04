import json
import shutil
from dataclasses import asdict, replace
from pathlib import Path

from test_learning import tiny_config

from media_rl.evidence import export_paper
from media_rl.experiment import dump_json, sha256, train_experiment
from media_rl.scenarios import SCENARIOS
from media_rl.selected_calibration import recalibrate_screen_models
from media_rl.shield_selection import ShieldProtocol, run_safety_shield
from media_rl.training import ModelBundle
from media_rl.uncertainty_shield import resume_uncertainty_shield, run_uncertainty_shield


def test_selected_action_recalibration_freezes_weights_and_tracks_reference(tmp_path):
    base = tiny_config()
    config = replace(
        base,
        scenarios=list(SCENARIOS),
        methods=["safe", "gcc", "rl", "calibrated"],
        gate=replace(base.gate, threshold=0.0),
    ).validate()
    source = train_experiment(config, tmp_path / "source")

    calibration_settings = tmp_path / "action-calibration.json"
    dump_json(
        calibration_settings,
        {
            "name": "test-action-calibration",
            "episodes": 2,
            "split_namespace": "action_calibration_v6",
            "top_k": 5,
            "threshold": 0.0,
            "calibration": config.gate.calibration,
        },
    )
    candidate = tmp_path / "candidate"
    result = recalibrate_screen_models(calibration_settings, source, candidate)
    assert result["sample_counts"]["7"] > 0
    source_bundle = ModelBundle.load(source / "models" / "seed_7.json")
    candidate_bundle = ModelBundle.load(candidate / "models" / "seed_7.json")
    assert candidate_bundle.policy.to_dict() == source_bundle.policy.to_dict()
    assert candidate_bundle.safety.to_dict() == source_bundle.safety.to_dict()
    assert (
        candidate_bundle.metadata["selected_action_calibration"]["split_namespace"] == "action_calibration_v6"
    )
    assert candidate_bundle.metadata["selected_action_calibration"]["fit_metrics_are_in_sample"]

    campaign_settings = tmp_path / "selection.json"
    protocol = ShieldProtocol(
        name="test-v6-reference",
        model_seeds=[7],
        validation_seeds=[601],
        test_seeds=[602],
        top_k=5,
        threshold=0.0,
        max_id_qoe_drop=0.03,
        max_id_violation_increase=0.01,
        max_stress_violation_increase=0.02,
        max_stress_scenario_violation_increase=0.03,
        risk_penalty=5.0,
        minimum_score_gain=0.005,
    )
    dump_json(campaign_settings, asdict(protocol))
    campaign = tmp_path / "campaign"
    run_safety_shield(campaign_settings, candidate, campaign, plots=False, reference_models=source)

    identity = json.loads((campaign / "campaign.json").read_text())
    selection = json.loads((campaign / "selection.json").read_text())
    assert identity["reference_model_sha256"]["7"]
    assert selection["baseline_model_sha256"] == identity["reference_model_sha256"]
    assert selection["candidate_model_sha256"] == identity["model_sha256"]
    assert Path(campaign / "test" / "steps.csv.gz").is_file()

    uncertainty_protocol = replace(
        protocol,
        name="test-v7-uncertainty",
        validation_seeds=[701],
        test_seeds=[702],
        max_ensemble_std=0.05,
    )
    uncertainty_settings = tmp_path / "uncertainty-selection.json"
    dump_json(uncertainty_settings, asdict(uncertainty_protocol))
    uncertainty_run = run_uncertainty_shield(
        uncertainty_settings, candidate, tmp_path / "uncertainty-campaign", plots=False
    )
    uncertainty_selection = json.loads((uncertainty_run.parent / "selection.json").read_text())
    assert uncertainty_selection["reference_method"] == "shielded"
    assert uncertainty_selection["candidate_method"] == "shielded_uncertainty"
    assert uncertainty_selection["validation_seeds"] == [701]
    assert uncertainty_selection["test_seeds"] == [702]
    assert json.loads((uncertainty_run / "manifest.json").read_text())["evaluation_split"] == "test"
    assert Path(uncertainty_run / "shield_diagnostics.csv").is_file()

    partial_campaign = tmp_path / "partial-uncertainty-campaign"
    shutil.copytree(uncertainty_run.parent, partial_campaign)
    shutil.rmtree(partial_campaign / "test")
    (partial_campaign / "test").mkdir()
    partial_marker = partial_campaign / "test" / "unfinished.partial"
    partial_marker.write_text("preserved-not-evaluated")
    recovered_run = resume_uncertainty_shield(
        uncertainty_settings,
        candidate,
        tmp_path / "recovered-uncertainty-campaign",
        partial_campaign,
        plots=False,
    )
    recovered_root = recovered_run.parent
    assert partial_marker.read_text() == "preserved-not-evaluated"
    assert json.loads((recovered_root / "selection.json").read_text()) == uncertainty_selection
    resume_provenance = json.loads((recovered_root / "resume_provenance.json").read_text())
    assert resume_provenance["preserved_partial_test_artifacts"]["unfinished.partial"] == sha256(
        partial_marker
    )
    recovered_manifest = json.loads((recovered_run / "manifest.json").read_text())
    assert recovered_manifest["resume_provenance_sha256"] == sha256(recovered_root / "resume_provenance.json")

    paper = tmp_path / "uncertainty-paper"
    provenance = export_paper(recovered_run, paper, prefix="VSeven")
    for table in [
        "table_uncertainty_shield_selection.tex",
        "table_uncertainty_shield_families.tex",
        "table_uncertainty_shield_contrasts.tex",
        "table_uncertainty_shield_diagnostics.tex",
    ]:
        assert table in provenance["generated_sha256"]
    assert {"selection.json", "shield_diagnostics.csv", "steps.csv.gz"} <= set(provenance["source_files"])
