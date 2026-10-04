import csv
import gzip
import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest
from test_budget_shield import action_index, fake_bundle
from test_learning import tiny_config

from media_rl.cli import main
from media_rl.config import GateConfig, SimulatorConfig
from media_rl.controllers import DeterministicController, RLController, make_controller
from media_rl.delay_budget import (
    ABLATION_METHOD,
    CANDIDATE_METHOD,
    LOSS_BUDGET_METHOD,
    REFERENCE_METHOD,
    TEST_METHODS,
    VALIDATION_METHODS,
    run_delay_budget,
)
from media_rl.environment import Telemetry, action_space
from media_rl.evidence import audit_complete_run, export_paper
from media_rl.experiment import dump_json, sha256, train_experiment
from media_rl.scenarios import SCENARIOS
from media_rl.shield_selection import ShieldProtocol


def test_v9_loss_only_veto_preserves_fec_and_single_shadow_update():
    actions = action_space(SimulatorConfig())
    ranking = [action_index(actions, 0.6), action_index(actions, 0.3)]
    bundle = fake_bundle(actions, ranking)
    obs = Telemetry(valid=True, loss=0.12)
    old = RLController(bundle, actions, GateConfig(shield_top_k=2), LOSS_BUDGET_METHOD)
    new = RLController(bundle, actions, GateConfig(shield_top_k=2), CANDIDATE_METHOD)
    a, b = old.act(obs), new.act(obs)
    assert a.action_budget_mbps == pytest.approx(0.42)
    assert b.action_budget_mbps == pytest.approx(0.65)
    assert a.action == ranking[1] and b.action == ranking[0]
    assert new.safe.budget == pytest.approx(0.65)
    fallback = DeterministicController(actions, loss_backoff=False).act(obs)
    assert actions[fallback.action].fec == 0.1


@pytest.mark.parametrize("obs", [Telemetry(valid=True, rtt_ms=90), Telemetry(valid=True, delay_trend_ms=16)])
def test_v9_keeps_delay_backoff_even_without_loss(obs):
    actions = action_space(SimulatorConfig())
    ctrl = RLController(
        fake_bundle(actions, [action_index(actions, 0.3)]), actions, GateConfig(), CANDIDATE_METHOD
    )
    ctrl.act(Telemetry(valid=True))
    decision = ctrl.act(obs)
    assert decision.action_budget_mbps == pytest.approx(0.65 * 0.7)


@pytest.mark.parametrize("method", [CANDIDATE_METHOD, ABLATION_METHOD])
@pytest.mark.parametrize("guard", ["feedback", "support", "invalid"])
def test_v9_hard_guards(method, guard):
    actions = action_space(SimulatorConfig())
    bundle = fake_bundle(actions, [action_index(actions, 0.6)], support=10 if guard == "support" else 0)
    obs = Telemetry(
        valid=True,
        feedback_age_s=0.6 if guard == "feedback" else 0,
        throughput_mbps=float("nan") if guard == "invalid" else 0.6,
    )
    decision = RLController(bundle, actions, GateConfig(), method).act(obs)
    assert decision.fallback
    assert (
        decision.reason
        == {"feedback": "missing_feedback", "support": "ood_support", "invalid": "invalid_telemetry"}[guard]
    )


def test_v9_ablation_keeps_wire_limit_ranking_and_score_diagnostics():
    actions = action_space(SimulatorConfig())
    ranking = [action_index(actions, 0.6, 0.25), action_index(actions, 0.6), action_index(actions, 0.15)]
    bundle = fake_bundle(actions, ranking, probability=0.4, std=0.2)
    gate = GateConfig(shield_top_k=2, max_ensemble_std=0.05)
    candidate = RLController(bundle, actions, gate, CANDIDATE_METHOD).act(Telemetry(valid=True))
    ablated = RLController(bundle, actions, gate, ABLATION_METHOD).act(Telemetry(valid=True))
    assert candidate.fallback and candidate.reason == "no_safe_candidate"
    assert not ablated.fallback and ablated.action == ranking[1]
    assert ablated.action_budget_mbps == pytest.approx(0.65)
    assert ablated.action_confidence == 0.4 and ablated.action_uncertainty == 0.2
    assert ablated.budget_intervention and ablated.budget_rejections == 1


def test_v9_rejects_an_incompatible_fallback_instead_of_silently_ignoring_rule():
    actions = action_space(SimulatorConfig())
    bundle = fake_bundle(actions, [0])
    bundle.metadata = {"fallback_kind": "gcc"}
    with pytest.raises(ValueError, match="frozen safe fallback"):
        RLController(bundle, actions, GateConfig(), CANDIDATE_METHOD)


@pytest.mark.parametrize(
    "method",
    [
        "safe",
        "heuristic",
        "gcc",
        "rl",
        "calibrated",
        "uncalibrated",
        "no_ood",
        "no_hysteresis",
        "single_model",
        "shielded",
        "shielded_uncertainty",
        "shielded_budget",
        "budget_only",
    ],
)
def test_pre_v9_methods_match_immutable_v8_snapshot(method):
    path = Path("tests/fixtures/controllers_v8.py")
    spec = importlib.util.spec_from_file_location("media_rl._legacy_v8", path)
    legacy = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = legacy
    spec.loader.exec_module(legacy)
    actions = action_space(SimulatorConfig())
    bundle = fake_bundle(actions, [action_index(actions, 1.0), action_index(actions, 0.6)])
    bundle.single_calibrator = bundle.calibrator
    bundle.safety.predict = lambda x, single=False: (
        (0.99, 0.01) if np.asarray(x).ndim == 1 else (np.full(len(x), 0.99), np.full(len(x), 0.01))
    )
    gate = GateConfig(max_ensemble_std=0.05)
    a = legacy.make_controller(method, bundle, actions, gate, 0.1)
    b = make_controller(method, bundle, actions, gate, 0.1)
    for obs in [
        Telemetry(valid=True),
        Telemetry(valid=True, loss=0.12),
        Telemetry(valid=True, rtt_ms=110, delay_trend_ms=20),
        Telemetry(valid=False),
        Telemetry(valid=True, feedback_age_s=1),
        Telemetry(valid=True, throughput_mbps=float("nan")),
    ]:
        assert asdict(a.act(obs)) == asdict(b.act(obs))


def test_v9_declared_panels_are_disjoint_from_prior_studies():
    settings = Path("configs/delay_budget_v9.json")
    protocol = ShieldProtocol(**json.loads(settings.read_text())).validate()
    current = set(protocol.validation_seeds + protocol.test_seeds)
    for path in Path("configs").glob("*.json"):
        if path != settings:
            previous = json.loads(path.read_text())
            for key in ["validation_seeds", "test_seeds"]:
                assert not current.intersection(previous.get(key, []))
    assert (
        len(protocol.model_seeds) == 10
        and len(protocol.validation_seeds) == 5
        and len(protocol.test_seeds) == 10
    )


def test_v9_cli_lock_export_immutability_and_tamper_rejection(tmp_path):
    config = replace(tiny_config(), scenarios=list(SCENARIOS)).validate()
    models = train_experiment(config, tmp_path / "models")
    protocol = json.loads(Path("configs/delay_budget_v9.json").read_text())
    protocol.update(name="v9-unit-smoke", model_seeds=[7], validation_seeds=[14791], test_seeds=[15791])
    settings = tmp_path / "settings.json"
    dump_json(settings, protocol)
    out = tmp_path / "campaign"
    main(
        ["delay-budget", "--config", str(settings), "--models", str(models), "--out", str(out), "--no-plots"]
    )
    final = out / "test"
    resolved, manifest = audit_complete_run(final)
    assert resolved.methods == TEST_METHODS and manifest["evaluation_split"] == "test"
    assert json.loads((out / "validation/config.json").read_text())["methods"] == VALIDATION_METHODS
    selection = json.loads((out / "selection.json").read_text())
    assert selection["selection_split"] == "validation"
    assert (
        selection["candidate_method"] == CANDIDATE_METHOD
        and selection["reference_method"] == REFERENCE_METHOD
    )
    assert (
        selection["mechanistic_comparator"] == LOSS_BUDGET_METHOD
        and selection["ablation_method"] == ABLATION_METHOD
    )
    assert selection["baseline_model_sha256"] == selection["candidate_model_sha256"]
    assert selection["validation_manifest_sha256"] == sha256(out / "validation/manifest.json")
    assert manifest["selection_sha256"] == sha256(final / "selection.json") == sha256(out / "selection.json")
    assert (out / "selection.json").stat().st_mtime_ns <= min(
        p.stat().st_mtime_ns for p in (final / "traces").glob("*.npz")
    )
    assert (models / "models/seed_7.json").read_bytes() == (final / "models/seed_7.json").read_bytes()
    with gzip.open(final / "steps.csv.gz", "rt") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 11 * len(TEST_METHODS) * config.simulator.steps
    for row in rows:
        if row["method"] in {CANDIDATE_METHOD, ABLATION_METHOD} and row["fallback"] == "False":
            assert float(row["wire_mbps"]) <= float(row["action_budget_mbps"])
    paper = tmp_path / "paper"
    evidence = export_paper(final, paper, prefix="DelayBudget")
    assert {
        "table_delay_budget_selection.tex",
        "table_delay_budget_contrasts.tex",
        "table_delay_budget_scenarios.tex",
        "table_delay_budget_scenarios_v8.tex",
        "table_delay_budget_calibration.tex",
        "table_delay_budget_only_calibration.tex",
        "delay_budget_results.json",
    } <= evidence["generated_sha256"].keys()
    assert "table_policy_randomization.tex" not in evidence["generated_sha256"]
    assert evidence["source_files"]["delay_budget_only_diagnostics.csv"] == sha256(
        final / "delay_budget_only_diagnostics.csv"
    )
    results = json.loads((paper / "delay_budget_results.json").read_text())
    assert len(results["contrasts"]) == 16 and all(row["n"] == 1 for row in results["contrasts"])
    before = sha256(final / "steps.csv.gz"), sha256(final / "manifest.json")
    run_delay_budget(settings, models, out, plots=False)
    assert before == (sha256(final / "steps.csv.gz"), sha256(final / "manifest.json"))
    dump_json(settings, dict(protocol, risk_penalty=6.0))
    with pytest.raises(ValueError, match="changed or output is partial"):
        run_delay_budget(settings, models, out, plots=False)
    dump_json(settings, protocol)
    (final / "steps.csv.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        run_delay_budget(settings, models, out, plots=False)
