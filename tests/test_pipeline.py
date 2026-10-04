import csv
import gzip
import hashlib
import json
from dataclasses import replace

import numpy as np
import pytest
from test_learning import tiny_config

from media_rl.cli import main
from media_rl.config import load_config, split_seed
from media_rl.controllers import METHODS
from media_rl.environment import MediaEnvironment
from media_rl.experiment import evaluate_experiment, run_experiment, sha256, validate_bundle
from media_rl.reporting import paired_comparisons
from media_rl.scenarios import load_trace
from media_rl.training import ModelBundle


def test_end_to_end_proposal_labels_replay_and_audit(tmp_path):
    config = tiny_config()
    out = run_experiment(config, tmp_path / "run", plots=False)
    checkpoint = ModelBundle.load(out / "models/seed_7.json")
    data = json.loads((out / "manifest.json").read_text())
    assert data["stage"] == "complete" and data["model_artifacts"]
    assert (out / "table_main.tex").read_text().startswith("% Auto-generated")
    with (out / "episodes.csv").open() as f:
        episodes = list(csv.DictReader(f))
    assert len(episodes) == 15
    with gzip.open(out / "steps.csv.gz", "rt") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 300
    assert {r["method"] for r in rows} == set(config.methods)
    for name in config.scenarios:
        trace = load_trace(out / "traces" / f"{name}_20.npz")
        for method in config.methods:
            env = MediaEnvironment(config.simulator, trace)
            selected = [r for r in rows if r["scenario"] == name and r["method"] == method]
            for row in selected:
                preview = env.preview(int(row["proposal"]))
                assert preview["safe"] == int(row["proposal_safe"])
                assert preview["qoe"] == float(row["proposal_qoe"])
                obs, _, _, actual = env.step(int(row["action"]))
                assert actual["qoe"] == float(row["qoe"])
                assert obs.finite()
    main(["audit", "--run", str(out)])
    new_out = evaluate_experiment(config, out, tmp_path / "replay")
    assert sha256(out / "steps.csv.gz") == sha256(new_out / "steps.csv.gz")
    assert (out / "episodes.csv").read_bytes() == (new_out / "episodes.csv").read_bytes()
    with pytest.raises(FileExistsError):
        run_experiment(config, out, plots=False)
    with pytest.raises(ValueError):
        validate_bundle(checkpoint, replace(config, simulator=replace(config.simulator, fec_levels=[0.0])), 7)
    assert split_seed(20, "test") not in sum(checkpoint.metadata["split_trace_seeds"].values(), [])
    (out / "table_main.tex").write_text("tampered")
    with pytest.raises(SystemExit) as exc:
        main(["audit", "--run", str(out)])
    assert exc.value.code == 2


def test_public_configs_and_registration(capsys):
    for path in ["configs/smoke.json", "configs/demo.json", "configs/paper.json"]:
        config = load_config(path)
        assert set(config.methods) == METHODS - {
            "calibrated_v1",
            "id_refit",
            "stress_safe",
            "calibrated_090",
            "shielded_uncertainty",
            "shielded_budget",
            "budget_only",
            "shielded_delay_budget",
            "delay_budget_only",
        }
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "safety-shield" in help_text and "uncertainty-shield" in help_text
    with pytest.raises(SystemExit) as exc:
        main(["safety-shield", "--help"])
    assert exc.value.code == 0
    assert "--models" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        main(["uncertainty-shield", "--help"])
    assert exc.value.code == 0
    uncertainty_help = capsys.readouterr().out
    assert "--config" in uncertainty_help and "--models" in uncertainty_help
    assert "--resume-from" in uncertainty_help
    assert "budget-shield" in help_text
    with pytest.raises(SystemExit) as exc:
        main(["budget-shield", "--help"])
    assert exc.value.code == 0
    budget_help = capsys.readouterr().out
    assert "--config" in budget_help and "--models" in budget_help and "--no-plots" in budget_help
    assert "delay-budget" in help_text
    with pytest.raises(SystemExit) as exc:
        main(["delay-budget", "--help"])
    assert exc.value.code == 0
    delay_help = capsys.readouterr().out
    assert "--models" in delay_help and "--config" in delay_help and "--no-plots" in delay_help


def test_optional_config_fields_accept_historical_hashes():
    config = tiny_config()
    pre_shield = config.to_dict()
    pre_shield["gate"].pop("shield_top_k")
    pre_shield_digest = hashlib.sha256(json.dumps(pre_shield, sort_keys=True).encode()).hexdigest()
    pre_schedule_and_shield = config.to_dict()
    pre_schedule_and_shield.pop("policy_training_scenarios")
    pre_schedule_and_shield["gate"].pop("shield_top_k")
    legacy_digest = hashlib.sha256(json.dumps(pre_schedule_and_shield, sort_keys=True).encode()).hexdigest()
    assert config.digest_matches(config.digest())
    assert config.digest_matches(pre_shield_digest)
    pre_disagreement = config.to_dict()
    pre_disagreement["gate"].pop("max_ensemble_std")
    pre_disagreement_digest = hashlib.sha256(
        json.dumps(pre_disagreement, sort_keys=True).encode()
    ).hexdigest()
    assert config.digest_matches(pre_disagreement_digest)
    assert config.digest_matches(legacy_digest)
    scheduled = replace(config, policy_training_scenarios=["steady", "collapse"])
    scheduled_pre_shield = scheduled.to_dict()
    scheduled_pre_shield["gate"].pop("shield_top_k")
    scheduled_pre_shield_digest = hashlib.sha256(
        json.dumps(scheduled_pre_shield, sort_keys=True).encode()
    ).hexdigest()
    assert scheduled.digest_matches(scheduled.digest())
    assert scheduled.digest_matches(scheduled_pre_shield_digest)
    assert not scheduled.digest_matches(legacy_digest)


def test_paired_bootstrap_uses_model_seed_units():
    rows = []
    for seed in [1, 2, 3]:
        for test_seed in [10, 11]:
            for method, offset in [("rl", 0), ("calibrated", 1)]:
                rows.append(
                    dict(
                        model_seed=seed,
                        test_seed=test_seed,
                        scenario="steady",
                        domain="id",
                        method=method,
                        **{
                            metric: float(seed + offset)
                            for metric in [
                                "qoe",
                                "latency_p95_ms",
                                "residual_loss",
                                "violation_rate",
                                "fallback_rate",
                                "ece",
                            ]
                        },
                    )
                )
    results = paired_comparisons(rows, 50)
    assert all(r["n"] == 3 and r["mean"] == r["low"] == r["high"] == 1 for r in results)
    assert np.isfinite(results[0]["mean"])
