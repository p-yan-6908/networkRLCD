import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from test_history_training import history_config
from test_learning import tiny_config

from media_rl.config import ExperimentConfig
from media_rl.controllers import RLController
from media_rl.environment import MediaEnvironment
from media_rl.evidence import audit_complete_run
from media_rl.experiment import run_experiment
from media_rl.n_step import NStepAccumulator
from media_rl.realism_study import RealismStudy
from media_rl.scenarios import simulation_trace
from media_rl.training import ModelBundle, train_bundle, train_policy


def test_discounted_prefixes_and_terminal_flush_are_exact_and_episode_local():
    acc = NStepAccumulator(3, 0.5)
    out = []
    for i, reward in enumerate([1.0, 2.0, 3.0, 4.0]):
        out.extend(acc.push([i], i, reward, [i + 1], i == 3))
    assert [s.reward for s in out] == [2.75, 4.5, 5.0, 4.0]
    assert [s.steps for s in out] == [3, 3, 2, 1]
    assert [s.discount for s in out] == [0.125, 0.125, 0.25, 0.5]
    assert [s.done for s in out] == [False, True, True, True]
    assert [s.action for s in out] == [0, 1, 2, 3]
    assert [s.state.item() for s in out] == [0, 1, 2, 3]
    assert [s.next_state.item() for s in out] == [3, 4, 4, 4]
    # A done prefix cannot bootstrap from another episode even with a large Q.
    assert [s.reward + s.discount * (not s.done) * 100 for s in out] == [15.25, 4.5, 5.0, 4.0]
    assert not acc.pending
    assert acc.push([100], 0, 8.0, [101], False) == []
    next_episode = acc.push([101], 1, 10.0, [102], True)
    assert [s.reward for s in next_episode] == [13.0, 10.0]
    assert [s.steps for s in next_episode] == [2, 1]


def test_replay_capture_is_snapshot_isolated_and_zero_gamma_is_valid():
    acc = NStepAccumulator(2, 0.0)
    state, after = np.array([2.0]), np.array([3.0])
    assert acc.push(state, 1, 4.0, after, False) == []
    state[0], after[0] = -100, -100
    first, last = acc.push([3.0], 2, 99.0, [4.0], True)
    assert first.state.item() == 2 and first.next_state.item() == 4
    assert first.reward == 4 and first.discount == 0
    assert last.reward == 99 and not acc.pending
    with pytest.raises(ValueError):
        acc.push([float("nan")], 0, 1, [0], False)


@pytest.mark.parametrize("n", [0, -1, 17, True, 2.5, "3"])
def test_nondefault_return_requires_strict_validated_configuration(n):
    config = tiny_config()
    with pytest.raises(ValueError):
        replace(config, training=replace(config.training, n_step=n)).validate()
    with pytest.raises(ValueError):
        NStepAccumulator(n, 0.95)


def test_v10_hashes_match_only_when_optional_return_is_unchanged():
    for config in [tiny_config(), history_config()]:
        before = config.to_dict()
        before["training"].pop("n_step")
        digest = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
        assert config.digest_matches(digest)
        assert not replace(config, training=replace(config.training, n_step=3)).digest_matches(digest)
        assert ExperimentConfig().training.n_step == 1


@pytest.mark.parametrize("packet", [False, True])
def test_one_step_policy_training_is_bit_exact_against_frozen_v10(packet):
    path = Path(__file__).parent / "fixtures/training_v10.py"
    # Self-contained fixture: do not require generated results for a fresh checkout.
    digest = "b6ad0ce53fa9032f8db0cf9c401747f4889b7e61d78b6b23e695d9f488c66e55"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    spec = importlib.util.spec_from_file_location("media_rl._frozen_v10_training", path)
    legacy = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = legacy
    spec.loader.exec_module(legacy)
    config = history_config() if packet else tiny_config()
    config = replace(config, training=replace(config.training, target_every=3))
    current, logs = train_policy(config, 7)
    old, old_logs = legacy.train_policy(config, 7)
    assert current.to_dict() == old.to_dict() and logs == old_logs


def test_frozen_v11_protocol_changes_only_return_with_new_matched_panels():
    data = json.loads(Path("configs/n_step_v11.json").read_text())
    protocol = RealismStudy(**data)
    base, candidate = protocol.configs()
    before, after = base.training.__dict__.copy(), candidate.training.__dict__.copy()
    assert before.pop("n_step") == 1 and after.pop("n_step") == 3
    assert before == after
    assert base.policy_training_scenarios == candidate.policy_training_scenarios
    assert base.safety_training_scenarios == candidate.safety_training_scenarios
    assert len(base.seeds) == 5 and base.simulator == candidate.simulator and base.gate == candidate.gate
    assert not set(base.seeds) & {40, 41, 52, 63, 70}
    assert not (set(protocol.validation_seeds) | set(protocol.test_seeds)) & {
        17101,
        18101,
        18102,
        19101,
        19102,
        19103,
        20001,
    }


def test_n_step_full_pipeline_has_audited_horizon_and_censoring_metadata(tmp_path):
    config = history_config()
    config = replace(config, training=replace(config.training, n_step=3, safety_horizon_steps=3)).validate()
    out = run_experiment(config, tmp_path / "run", plots=False)
    audit_complete_run(out)
    restored = ModelBundle.load(out / "models/seed_7.json")
    assert restored.metadata["policy_return_steps"] == 3
    assert restored.metadata["config"]["training"]["safety_horizon_steps"] == 3
    assert json.loads((out / "manifest.json").read_text())["stage"] == "complete"


def test_n_step_training_checkpoint_runtime_and_update_budget(tmp_path):
    base = replace(
        history_config(), training=replace(history_config().training, target_every=3, replay_size=32)
    )
    config = replace(base, training=replace(base.training, n_step=3)).validate()
    a, logs = train_policy(config, 7)
    b, same = train_policy(config, 7)
    one, before = train_policy(base, 7)
    assert a.to_dict() == b.to_dict() and logs == same
    assert a.to_dict() != one.to_dict()
    assert [r["updates"] for r in logs] == [r["updates"] for r in before]
    model, _ = train_bundle(config, 7)
    assert model.metadata["policy_return_steps"] == 3
    assert model.metadata["config"]["training"]["n_step"] == 3
    model.save(tmp_path / "model.json")
    restored = ModelBundle.load(tmp_path / "model.json")
    assert restored.policy.to_dict() == model.policy.to_dict()
    env = MediaEnvironment(config.simulator, simulation_trace(config.simulator, "collapse", 40))
    controller = RLController(restored, env.actions, config.gate)
    obs = env.reset()
    for _ in range(config.simulator.steps):
        action = controller.act(obs).action
        obs, _, _, _ = env.step(action)
