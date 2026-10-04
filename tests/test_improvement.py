import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from test_learning import tiny_config

from media_rl.cli import main
from media_rl.config import split_seed
from media_rl.controllers import METHODS, make_controller
from media_rl.environment import action_space
from media_rl.evidence import export_paper
from media_rl.experiment import evaluate_experiment, sha256, train_experiment
from media_rl.improvement import (
    ImprovementConfig,
    collect_refit,
    randomized_stress,
    run_improvement,
    select_candidate,
)
from media_rl.scenarios import load_trace
from media_rl.training import ModelBundle, train_bundle


def protocol():
    return ImprovementConfig(**json.loads(Path("configs/improve_v2.json").read_text())).validate()


def test_campaign_registration_configuration_and_namespace_separation():
    p = protocol()
    assert p.model_seeds == [11, 22, 33]
    assert {"calibrated_v1", "id_refit", "stress_safe"} <= METHODS
    values = [
        split_seed(11, split, i)
        for split in ["train", "risk", "calibration", "risk_v2", "calibration_v2", "validation", "test"]
        for i in range(50)
    ]
    assert len(values) == len(set(values))
    with pytest.raises(ValueError, match="overlap"):
        replace(p, test_seeds=p.validation_seeds).validate()
    with pytest.raises(ValueError, match="candidate"):
        replace(p, candidates=["posthoc_winner"]).validate()
    with pytest.raises(SystemExit) as error:
        main(["improve", "--help"])
    assert error.value.code == 0


def test_training_stress_is_deterministic_and_collector_cannot_touch_test():
    a, b = randomized_stress(100, 44), randomized_stress(100, 44)
    for key in ["capacity", "base_rtt", "loss", "jitter", "feedback", "burst", "buffer_scale"]:
        np.testing.assert_array_equal(getattr(a, key), getattr(b, key))
        assert not getattr(a, key).flags.writeable
    assert a.cross_traffic is None and a.vbr_scale is None and a.transport_seed is None
    assert not np.array_equal(a.capacity, randomized_stress(100, 45).capacity)
    config = tiny_config()
    bundle, _ = train_bundle(config, 7)
    with pytest.raises(ValueError, match="cannot access"):
        collect_refit(config, 7, bundle.policy, "test", 4, 0.5, True)
    x, y, ids, info = collect_refit(config, 7, bundle.policy, "risk_v2", 4, 0.5, True)
    assert x.shape[1] == 14 and len(x) == len(y) == len(ids)
    assert info["families"].count("randomized_training") == 2
    assert info["positive_rate"] == y.mean()
    again = collect_refit(config, 7, bundle.policy, "risk_v2", 4, 0.5, True)[3]
    assert info == again


def test_selector_rejects_unsafe_high_qoe_and_keeps_baseline_without_gain():
    p = protocol()
    base = dict(id_qoe=2.0, ood_qoe=1.0, id_violation_rate=0.01, ood_violation_rate=0.1)
    scores = {k: dict(base) for k in ["v1", *p.candidates]}
    assert select_candidate(scores, p)["selected"] == "v1"
    scores["stress_safe"].update(ood_qoe=5.0, ood_violation_rate=0.11)
    scores["stress_gcc"].update(ood_qoe=1.05, ood_violation_rate=0.09)
    selection = select_candidate(scores, p)
    assert selection["selected"] == "stress_gcc"
    assert not next(r for r in selection["ranking"] if r["candidate"] == "stress_safe")["feasible"]


def test_full_refit_campaign_locks_selection_and_preserves_originals(tmp_path, monkeypatch):
    config = tiny_config()
    original = train_experiment(config, tmp_path / "original")
    checkpoint = original / "models/seed_7.json"
    original_hash = sha256(checkpoint)
    p = replace(
        protocol(),
        model_seeds=[7],
        validation_seeds=[501],
        test_seeds=[1501],
        safety_episodes=4,
        calibration_episodes=4,
        bootstrap_samples=20,
    )
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(vars(p)))
    root = tmp_path / "campaign"
    import media_rl.improvement as module

    real_evaluate = module.evaluate_experiment
    calls = []

    def observed(*args, **kwargs):
        calls.append(kwargs["split"])
        if kwargs["split"] == "test":
            assert (root / "selection.json").is_file()
            assert not (root / "test/episodes.csv").exists()
        return real_evaluate(*args, **kwargs)

    monkeypatch.setattr(module, "evaluate_experiment", observed)
    result = run_improvement(settings, original, root, plots=False)
    assert calls == ["validation"] * 4 + ["test"]
    assert sha256(checkpoint) == original_hash
    baseline = ModelBundle.load(checkpoint)
    for candidate in p.candidates:
        refit = ModelBundle.load(root / "candidates" / candidate / "models/seed_7.json")
        assert refit.policy.to_dict() == baseline.policy.to_dict()
        assert refit.metadata["source_checkpoint_sha256"] == original_hash
        assert not set(refit.metadata["split_trace_seeds"]["risk_v2"]) & set(
            refit.metadata["split_trace_seeds"]["calibration_v2"]
        )
    safe = ModelBundle.load(root / "candidates/stress_safe/models/seed_7.json")
    gcc = ModelBundle.load(root / "candidates/stress_gcc/models/seed_7.json")
    assert safe.safety.to_dict() == gcc.safety.to_dict()
    assert safe.calibrator == gcc.calibrator
    controller = make_controller(
        "calibrated", gcc, action_space(config.simulator), config.gate, config.simulator.dt_s
    )
    assert controller.safe.kind == "gcc"
    assert (result / "confidence_benchmark.csv").is_file()
    final = json.loads((result / "manifest.json").read_text())
    assert final["evaluation_split"] == "test"
    assert set(final["reference_artifacts"]) == {"calibrated_v1", "id_refit", "stress_safe"}
    main(["audit", "--run", str(result)])
    exported = tmp_path / "paper"
    export_paper(result, exported, prefix="Followup")
    assert "\\FollowupNumEpisodes" in (exported / "evidence.tex").read_text()
    assert (exported / "table_predictors.tex").is_file()
    assert "Stress" in (exported / "table_comparison.tex").read_text()
    with pytest.raises(ValueError, match="ASCII"):
        export_paper(result, tmp_path / "bad", prefix="bad_1")
    locked_hash = sha256(root / "selection.json")
    run_improvement(settings, original, root, plots=False)
    assert len(calls) == 5 and sha256(root / "selection.json") == locked_hash
    test_trace = load_trace(result / "traces/steady_1501.npz")
    val_trace = load_trace(root / "validation/v1/traces/steady_501.npz")
    assert not np.array_equal(test_trace.capacity, val_trace.capacity)
    # A self-contained run carries its reference mapping into a deterministic replay.
    final_config = module.load_config(result / "config.json")
    replay = evaluate_experiment(final_config, result, tmp_path / "replay")
    assert sha256(replay / "steps.csv.gz") == sha256(result / "steps.csv.gz")
    with pytest.raises(ValueError, match="model map"):
        evaluate_experiment(final_config, original, tmp_path / "missing-map")
