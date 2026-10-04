import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_learning import tiny_config

from media_rl.cli import main
from media_rl.evidence import export_paper
from media_rl.experiment import evaluate_experiment, sha256, train_experiment
from media_rl.reporting import read_episodes
from media_rl.scenarios import SCENARIOS
from media_rl.threshold_selection import ThresholdProtocol, run_threshold_selection, select_threshold


def tiny_protocol():
    return ThresholdProtocol(
        name="threshold-selector-test",
        model_seeds=[7],
        validation_seeds=[501],
        test_seeds=[1501],
        thresholds=[0.7, 0.9],
        baseline_threshold=0.9,
        max_id_qoe_drop=0.03,
        max_id_violation_increase=0.001,
        max_stress_violation_increase=0.005,
        max_stress_scenario_violation_increase=0.02,
        risk_penalty=5.0,
        minimum_score_gain=0.005,
        bootstrap_samples=20,
    ).validate()


def synthetic(*, id_qoe=2.0, id_risk=0.01, stress_qoe=1.0, stress_risk=0.10):
    return dict(
        id_qoe=id_qoe,
        id_violation_rate=id_risk,
        stress_qoe=stress_qoe,
        stress_violation_rate=stress_risk,
        scenarios={
            name: dict(qoe=0.0, violation_rate=0.10 if domain == "ood" else 0.01)
            for name, domain in SCENARIOS.items()
        },
    )


def test_threshold_selector_is_validation_only_and_enforces_stress_families():
    p = tiny_protocol()
    scores = {"0.70": synthetic(stress_qoe=1.2, stress_risk=0.102), "0.90": synthetic()}
    assert select_threshold(scores, p)["selected_threshold"] == 0.7
    scores["0.70"]["scenarios"]["collapse"]["violation_rate"] = 0.13
    assert select_threshold(scores, p)["selected_threshold"] == 0.9
    scores["0.70"] = synthetic(id_qoe=1.8, stress_qoe=1.4, stress_risk=0.08)
    assert select_threshold(scores, p)["selected_threshold"] == 0.9
    with pytest.raises(ValueError, match="overlap"):
        replace(p, test_seeds=p.validation_seeds).validate()
    with pytest.raises(ValueError, match="baseline"):
        replace(p, thresholds=[0.7, 0.8]).validate()


def test_threshold_cli_campaign_locks_then_replays_portably(tmp_path, monkeypatch):
    config = replace(tiny_config(), scenarios=list(SCENARIOS), bootstrap_samples=20).validate()
    source = train_experiment(config, tmp_path / "source-models")
    protocol = tiny_protocol()
    settings = tmp_path / "thresholds.json"
    settings.write_text(json.dumps(protocol.__dict__))
    out = tmp_path / "campaign"
    import media_rl.threshold_selection as selector

    real_complete = selector.complete_evaluation
    validation_calls, test_calls = [], []

    def seen_complete(config, models, dest, split, **kwargs):
        validation_calls.append((split, dest))
        return real_complete(config, models, dest, split, **kwargs)

    import media_rl.experiment as experiment_module

    real_evaluate = experiment_module.evaluate_experiment

    def seen_evaluate(config, models, dest, *args, **kwargs):
        test_calls.append(kwargs.get("split", "test"))
        assert (out / "selection.json").is_file()
        assert not (out / "test/episodes.csv").exists()
        return real_evaluate(config, models, dest, *args, **kwargs)

    monkeypatch.setattr(selector, "complete_evaluation", seen_complete)
    monkeypatch.setattr(experiment_module, "evaluate_experiment", seen_evaluate)
    final = run_threshold_selection(settings, source, out, plots=False)
    assert len(validation_calls) == 2 and test_calls == ["test"]
    assert [split for split, _ in validation_calls] == ["validation", "validation"]
    selection = json.loads((out / "selection.json").read_text())
    assert selection["selection_split"] == "validation"
    assert selection["selected_threshold"] in protocol.thresholds
    assert {r["threshold"] for r in selection["ranking"]} == set(protocol.thresholds)
    assert json.loads((final / "gate_overrides.json").read_text()) == {"calibrated_090": 0.9}
    manifest = json.loads((final / "manifest.json").read_text())
    assert manifest["gate_overrides"] == {"calibrated_090": 0.9}
    assert manifest["evaluation_split"] == "test"
    assert manifest["reference_artifacts"] == {}
    rows = read_episodes(final / "episodes.csv")
    assert {r["method"] for r in rows} == {
        "safe",
        "heuristic",
        "gcc",
        "rl",
        "calibrated",
        "calibrated_090",
        "uncalibrated",
    }
    assert (final / "selection.json").read_bytes() == (out / "selection.json").read_bytes()
    assert not set(protocol.validation_seeds) & set(protocol.test_seeds)
    main(["audit", "--run", str(final)])
    paper = tmp_path / "paper"
    export_paper(final, paper, prefix="Threshold")
    assert "RLCD at 0.90" in (paper / "table_comparison.tex").read_text()
    assert "RLCD at 0.90" in (paper / "table_contrasts.tex").read_text()
    thresholds = (paper / "table_thresholds.tex").read_text()
    assert "Selection score" in thresholds and "Retained" in thresholds
    assert "+0.0000" in thresholds
    evidence = (paper / "evidence.tex").read_text()
    assert "ThresholdThreshold" in evidence and "ThresholdValidationEpisodes" in evidence

    final_config = selector.load_config(final / "config.json")
    replay = evaluate_experiment(final_config, final, tmp_path / "replay")
    assert sha256(final / "steps.csv.gz") == sha256(replay / "steps.csv.gz")
    assert (replay / "gate_overrides.json").read_bytes() == (final / "gate_overrides.json").read_bytes()
    frozen = sha256(out / "selection.json")
    run_threshold_selection(settings, source, out, plots=False)
    assert len(validation_calls) == 4 and test_calls == ["test"]
    assert sha256(out / "selection.json") == frozen


def test_threshold_selector_registered_and_public_protocol_validates():
    p = ThresholdProtocol(**json.loads(Path("configs/threshold_select_v3.json").read_text())).validate()
    assert p.baseline_threshold == 0.9 and 0.9 in p.thresholds
    assert len(p.test_seeds) * len(p.model_seeds) * 11 * 7 == 7700
    assert len(p.model_seeds) == 10 and set(p.validation_seeds).isdisjoint(p.test_seeds)
    with pytest.raises(SystemExit) as error:
        main(["tune-threshold", "--help"])
    assert error.value.code == 0
