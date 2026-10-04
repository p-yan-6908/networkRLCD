import json
from dataclasses import asdict, replace

import pytest
from test_history_training import history_config
from test_learning import tiny_config

from media_rl.cli import main
from media_rl.experiment import sha256
from media_rl.realism_study import RealismStudy, run_realism_study, select_recipe


def protocol():
    old = tiny_config()
    methods = ["gcc", "heuristic", "rl", "calibrated"]
    base = replace(old, methods=methods, simulator=replace(old.simulator, backend="packet_v2"))
    candidate = replace(
        history_config(),
        methods=methods,
        training=replace(history_config().training, safety_horizon_steps=3, demonstration_methods=["gcc"]),
    )
    return RealismStudy("tiny-realism", base.to_dict(), candidate.to_dict(), [301], [401], [201])


def test_realism_public_contract_and_disjoint_panels():
    data = RealismStudy(**json.loads(open("configs/realism_v10.json").read()))
    base, candidate = data.configs()
    assert base.simulator == candidate.simulator and base.seeds == candidate.seeds == [41, 52, 63]
    assert candidate.training.safety_horizon_steps == 3
    assert candidate.training.demonstration_methods == ["gcc"]
    with pytest.raises(ValueError, match="overlap"):
        replace(data, test_seeds=data.validation_seeds).configs()
    with pytest.raises(SystemExit) as exc:
        main(["realism-study", "--help"])
    assert exc.value.code == 0


def test_recipe_selector_rejects_high_reward_with_unsafe_regression():
    def rows(qoe, risk):
        return [
            dict(domain=domain, method="calibrated", qoe=qoe, violation_rate=risk) for domain in ["id", "ood"]
        ]

    p = protocol()
    assert not select_recipe(rows(1, 0.05), rows(5, 0.15), p)["candidate_eligible"]
    assert select_recipe(rows(1, 0.05), rows(1.1, 0.04), p)["candidate_eligible"]


def test_complete_matched_study_locks_before_test_and_refuses_overwrite(tmp_path, monkeypatch):
    import media_rl.realism_study as study

    original = study.evaluate_experiment
    root = tmp_path / "run"

    def observe(*args, **kwargs):
        if kwargs.get("split") == "test":
            assert (root / "selection.json").exists()
            assert json.loads((root / "selection.json").read_text())["selection_split"] == "validation"
        return original(*args, **kwargs)

    monkeypatch.setattr(study, "evaluate_experiment", observe)
    settings = tmp_path / "protocol.json"
    settings.write_text(json.dumps(asdict(protocol())))
    out = run_realism_study(settings, root)
    result = json.loads((out / "results.json").read_text())
    assert result["test_episodes"] == result["validation_episodes"] == 24
    assert len(result["contrasts"]) == 20
    manifest = json.loads((out / "study_manifest.json").read_text())
    assert all(sha256(out / name) == digest for name, digest in manifest["artifacts_sha256"].items())
    for name in ["baseline", "candidate"]:
        assert (out / name / "test/selection.json").read_bytes() == (out / "selection.json").read_bytes()
    with pytest.raises(FileExistsError):
        run_realism_study(settings, root)
