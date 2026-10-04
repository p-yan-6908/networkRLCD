import csv
import gzip
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from test_learning import tiny_config

from media_rl.budget_shield import CANDIDATE_METHOD, REFERENCE_METHOD, TEST_METHODS, run_budget_shield
from media_rl.cli import main
from media_rl.config import GateConfig, SimulatorConfig
from media_rl.controllers import RLController
from media_rl.environment import Telemetry, action_space
from media_rl.evidence import audit_complete_run, export_paper, selected_action_calibration_table
from media_rl.experiment import dump_json, sha256, train_experiment
from media_rl.scenarios import SCENARIOS
from media_rl.shield_selection import ShieldProtocol


def action_index(actions, bitrate, fec=0.0, low_latency=False):
    return next(
        i
        for i, action in enumerate(actions)
        if (action.bitrate_mbps, action.fec, action.low_latency) == (bitrate, fec, low_latency)
    )


def fake_bundle(actions, ranking, probability=0.99, std=0.01, support=0.0):
    values = np.full(len(actions), -100.0)
    for position, index in enumerate(ranking):
        values[index] = len(ranking) - position
    return SimpleNamespace(
        policy=lambda _: values,
        safety=SimpleNamespace(
            predict=lambda features: (np.full(len(features), probability), np.full(len(features), std)),
            support_score=lambda _: support,
            support_limit=1.0,
        ),
        calibrator=SimpleNamespace(predict=lambda probability: probability),
        metadata={},
    )


def test_budget_screen_prunes_high_confidence_wire_rate_including_fec():
    actions = action_space(SimulatorConfig())
    ranking = [action_index(actions, 4.0), action_index(actions, 0.6, 0.25), action_index(actions, 0.6)]
    bundle = fake_bundle(actions, ranking)
    gate = GateConfig(shield_top_k=3, max_ensemble_std=0.05)
    obs = Telemetry(valid=True)
    baseline = RLController(bundle, actions, gate, REFERENCE_METHOD).act(obs)
    decision = RLController(bundle, actions, gate, CANDIDATE_METHOD).act(obs)
    assert baseline.action == ranking[0]
    assert decision.action == ranking[2] and not decision.fallback
    assert decision.action_budget_mbps == pytest.approx(0.65)
    assert actions[decision.action].wire_mbps <= decision.action_budget_mbps
    assert decision.budget_rejections == 2 and decision.budget_intervention
    assert decision.confidence == decision.action_confidence == pytest.approx(0.99)


def test_budget_abstention_keeps_warm_fallback_and_never_scans_beyond_top_k():
    actions = action_space(SimulatorConfig())
    ranking = [action_index(actions, bitrate) for bitrate in [4.0, 2.5, 1.6, 0.15]]
    controller = RLController(
        fake_bundle(actions, ranking), actions, GateConfig(shield_top_k=3), CANDIDATE_METHOD
    )
    decision = controller.act(Telemetry(valid=True))
    assert decision.fallback and decision.reason == "budget_abstention"
    assert decision.budget_intervention and decision.budget_rejections == 3
    assert controller.safe.budget == pytest.approx(0.65)  # Only one shadow update.
    assert actions[decision.action].bitrate_mbps == 0.6
    assert decision.action != ranking[-1]  # The fourth-ranked action was not screened.


def test_budget_only_removes_probability_and_disagreement_not_the_envelope():
    actions = action_space(SimulatorConfig())
    ranking = [action_index(actions, 1.0), action_index(actions, 0.6)]
    bundle = fake_bundle(actions, ranking, probability=0.4, std=0.2)
    gate = GateConfig(shield_top_k=2, max_ensemble_std=0.05)
    candidate = RLController(bundle, actions, gate, CANDIDATE_METHOD).act(Telemetry(valid=True))
    ablation = RLController(bundle, actions, gate, "budget_only").act(Telemetry(valid=True))
    assert candidate.fallback and candidate.reason == "no_safe_candidate"
    assert ablation.action == ranking[1] and not ablation.fallback
    assert ablation.action_confidence == pytest.approx(0.4)
    assert ablation.action_uncertainty == pytest.approx(0.2)
    assert ablation.budget_intervention


@pytest.mark.parametrize("method", [CANDIDATE_METHOD, "budget_only"])
@pytest.mark.parametrize("guard", ["feedback", "support", "invalid"])
def test_budget_screens_preserve_hard_causal_guards(method, guard):
    actions = action_space(SimulatorConfig())
    bundle = fake_bundle(actions, [action_index(actions, 0.6)], support=10 if guard == "support" else 0)
    obs = Telemetry(
        valid=True,
        feedback_age_s=0.6 if guard == "feedback" else 0,
        throughput_mbps=float("nan") if guard == "invalid" else 0.6,
    )
    decision = RLController(bundle, actions, GateConfig(), method).act(obs)
    expected = {"feedback": "missing_feedback", "support": "ood_support", "invalid": "invalid_telemetry"}
    assert decision.fallback and decision.reason == expected[guard]


def test_budget_memory_backs_off_on_congestion_without_application_limited_lock():
    actions = action_space(SimulatorConfig())
    ranking = [action_index(actions, 0.6), action_index(actions, 0.3)]
    bundle = fake_bundle(actions, ranking)
    controller = RLController(bundle, actions, GateConfig(shield_top_k=2), CANDIDATE_METHOD)
    controller.act(Telemetry(valid=True))
    congestion = controller.act(Telemetry(valid=True, rtt_ms=110, delay_trend_ms=20))
    assert congestion.action_budget_mbps == pytest.approx(0.65 * 0.7)
    assert congestion.action == ranking[1]
    probing = RLController(bundle, actions, GateConfig(shield_top_k=2), CANDIDATE_METHOD)
    for _ in range(30):
        decision = probing.act(Telemetry(valid=True, throughput_mbps=0.15))
    assert decision.action_budget_mbps == pytest.approx(2.1)
    assert decision.action == ranking[0]


def test_selected_action_audit_excludes_rejected_candidate_fallback_scores(tmp_path):
    path = tmp_path / "steps.csv.gz"
    rows = [
        dict(
            domain="id",
            model_seed=7,
            method=CANDIDATE_METHOD,
            confidence=0.99,
            action_confidence=0.98,
            reason="budget_abstention",
            proposal_safe=0,
            safe=1,
        ),
        dict(
            domain="id",
            model_seed=7,
            method=CANDIDATE_METHOD,
            confidence=0.8,
            action_confidence=0.8,
            reason="accepted",
            proposal_safe=0,
            safe=0,
        ),
    ]
    with gzip.open(path, "wt", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    table = selected_action_calibration_table(path, tiny_config(), method=CANDIDATE_METHOD)
    accepted = next(line for line in table.splitlines() if line.startswith("ID & Screen-selected action"))
    assert " & 1 & 80.00 & 0.00 & 80.00 & " in accepted


def test_v8_panels_are_fresh_and_protocol_is_registered():
    settings = Path("configs/budget_shield_v8.json")
    protocol = ShieldProtocol(**json.loads(settings.read_text())).validate()
    current = set(protocol.validation_seeds + protocol.test_seeds)
    for path in Path("configs").glob("*.json"):
        if path == settings:
            continue
        previous = json.loads(path.read_text())
        for key in ["validation_seeds", "test_seeds"]:
            assert not current.intersection(previous.get(key, []))
    assert len(protocol.model_seeds) == 10
    assert len(protocol.validation_seeds) == 5 and len(protocol.test_seeds) == 10
    assert protocol.max_ensemble_std == 0.05


def test_v8_cli_campaign_locks_before_test_exports_ablations_and_refuses_tampering(tmp_path):
    config = replace(tiny_config(), scenarios=list(SCENARIOS)).validate()
    models = train_experiment(config, tmp_path / "models")
    settings = tmp_path / "settings.json"
    protocol = json.loads(Path("configs/budget_shield_v8.json").read_text())
    protocol.update(name="v8-unit-smoke", model_seeds=[7], validation_seeds=[12791], test_seeds=[13791])
    dump_json(settings, protocol)
    out = tmp_path / "campaign"
    main(
        ["budget-shield", "--config", str(settings), "--models", str(models), "--out", str(out), "--no-plots"]
    )
    final = out / "test"
    resolved, manifest = audit_complete_run(final)
    assert resolved.methods == TEST_METHODS
    assert manifest["evaluation_split"] == "test"
    selection = json.loads((out / "selection.json").read_text())
    assert selection["selection_split"] == "validation"
    assert selection["reference_method"] == REFERENCE_METHOD
    assert selection["candidate_method"] == CANDIDATE_METHOD
    assert selection["ablation_method"] == "budget_only"
    assert selection["baseline_model_sha256"] == selection["candidate_model_sha256"]
    assert selection["validation_manifest_sha256"] == sha256(out / "validation/manifest.json")
    assert manifest["selection_sha256"] == sha256(out / "selection.json") == sha256(final / "selection.json")
    assert (models / "models/seed_7.json").read_bytes() == (final / "models/seed_7.json").read_bytes()
    with gzip.open(final / "steps.csv.gz", "rt") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 11 * len(TEST_METHODS) * config.simulator.steps
    for row in rows:
        if row["method"] in {CANDIDATE_METHOD, "budget_only"} and row["fallback"] == "False":
            assert float(row["wire_mbps"]) <= float(row["action_budget_mbps"])
    paper = tmp_path / "paper"
    evidence = export_paper(final, paper, prefix="Budget")
    expected = {
        "table_budget_shield_selection.tex",
        "table_budget_shield_contrasts.tex",
        "table_budget_shield_families.tex",
        "table_budget_shield_diagnostics.tex",
        "table_budget_shield_scenarios.tex",
        "table_budget_shield_calibration.tex",
        "table_budget_only_calibration.tex",
        "budget_results.json",
    }
    assert expected <= evidence["generated_sha256"].keys()
    assert "table_policy_randomization.tex" not in evidence["generated_sha256"]
    assert evidence["source_files"]["budget_only_diagnostics.csv"] == sha256(
        final / "budget_only_diagnostics.csv"
    )
    assert evidence["source_files"]["steps.csv.gz"] == sha256(final / "steps.csv.gz")
    results = json.loads((paper / "budget_results.json").read_text())
    assert len(results["contrasts"]) == 12
    assert {row["reference"] for row in results["contrasts"]} == {REFERENCE_METHOD, "budget_only", "gcc"}
    steps_hash, manifest_hash = sha256(final / "steps.csv.gz"), sha256(final / "manifest.json")
    run_budget_shield(settings, models, out, plots=False)
    assert steps_hash == sha256(final / "steps.csv.gz") and manifest_hash == sha256(final / "manifest.json")
    dump_json(settings, dict(protocol, risk_penalty=6.0))
    with pytest.raises(ValueError, match="changed or output is partial"):
        run_budget_shield(settings, models, out, plots=False)
    dump_json(settings, protocol)
    (final / "steps.csv.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        run_budget_shield(settings, models, out, plots=False)
    with pytest.raises(ValueError, match="artifact integrity check failed"):
        export_paper(final, paper)
