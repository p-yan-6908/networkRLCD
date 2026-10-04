import hashlib
import json
from dataclasses import replace

import numpy as np
import pytest
from test_learning import tiny_config

from media_rl.config import ExperimentConfig, split_seed
from media_rl.controllers import RLController
from media_rl.environment import MediaEnvironment, Telemetry
from media_rl.experiment import run_experiment, sha256
from media_rl.policy_features import PolicyFeatures
from media_rl.scenarios import simulation_trace
from media_rl.training import ModelBundle, collect_demonstrations, train_bundle


def history_config():
    old = tiny_config()
    return replace(
        old,
        simulator=replace(old.simulator, backend="packet_v2"),
        policy_training_scenarios=["steady", "collapse", "wifi", "bufferbloat"],
        safety_training_scenarios=["steady", "collapse", "wifi", "bufferbloat"],
        training=replace(
            old.training,
            policy_features="history_v2",
            demonstration_episodes=2,
            demonstration_epochs=3,
            demonstration_weight=0.1,
        ),
    ).validate()


def test_history_features_causal_finite_and_reset():
    a, b = PolicyFeatures("history_v2"), PolicyFeatures("history_v2")
    obs = Telemetry(valid=True, throughput_mbps=2, rtt_ms=40, loss=0.01)
    assert a.encode(obs).shape == (16,)
    a.encode(replace(obs, rtt_ms=100, throughput_mbps=1))
    np.testing.assert_array_equal(b.encode(obs), PolicyFeatures("history_v2").encode(obs))
    assert not np.array_equal(a.encode(obs), PolicyFeatures("history_v2").encode(obs))
    np.testing.assert_array_equal(PolicyFeatures().encode(obs), np.clip(obs.vector(), -12, 12))


def test_demo_labels_are_telemetry_experts_not_preview_or_test_oracles(monkeypatch):
    config = history_config()

    def forbidden(*args):
        raise AssertionError("demonstration labeling inspected the oracle")

    monkeypatch.setattr(MediaEnvironment, "preview", forbidden)
    x, labels = collect_demonstrations(config, 7)
    y, again = collect_demonstrations(config, 7)
    np.testing.assert_array_equal(x, y)
    np.testing.assert_array_equal(labels, again)
    assert x.shape == (40, 16)
    assert np.all((labels >= 0) & (labels < 42))
    assert split_seed(7, "demonstration") != split_seed(7, "test")


def test_history_training_checkpoint_runtime_and_split_isolation(tmp_path):
    config = history_config()
    a, rows = train_bundle(config, 7)
    b, same = train_bundle(config, 7)
    assert a.policy.to_dict() == b.policy.to_dict() and rows == same
    assert a.policy.params[0].shape[0] == 16
    assert a.metadata["demonstration_samples"] == 40
    sets = [set(s) for s in a.metadata["split_trace_seeds"].values()]
    assert all(not x & y for i, x in enumerate(sets) for y in sets[i + 1 :])
    assert a.metadata["simulation_backend"] == "packet_v2"
    a.save(tmp_path / "model.json")
    restored = ModelBundle.load(tmp_path / "model.json")
    env = MediaEnvironment(config.simulator, simulation_trace(config.simulator, "collapse", 40))
    controller = RLController(restored, env.actions, config.gate, "calibrated")
    obs = env.reset()
    for _ in range(config.simulator.steps):
        decision = controller.act(obs)
        assert 0 <= decision.action < len(env.actions)
        obs, _, _, _ = env.step(decision.action)


def test_old_optional_hashes_cannot_mask_new_physics_or_training():
    config = tiny_config()
    old = config.to_dict()
    old.pop("safety_training_scenarios")
    for key in [
        "backend",
        "fps",
        "packet_bytes",
        "packet_header_bytes",
        "pacing_factor",
        "cross_traffic_interval_s",
    ]:
        old["simulator"].pop(key)
    for key in [
        "policy_features",
        "demonstration_episodes",
        "demonstration_epochs",
        "demonstration_weight",
        "demonstration_margin",
        "demonstration_methods",
        "safety_horizon_steps",
    ]:
        old["training"].pop(key)
    digest = hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
    assert config.digest_matches(digest)
    assert not history_config().digest_matches(digest)
    for changes in [
        dict(demonstration_episodes=1),
        dict(policy_features="future_capacity"),
        dict(demonstration_weight=-1),
        dict(demonstration_epochs=-1),
    ]:
        with pytest.raises(ValueError):
            replace(config, training=replace(config.training, **changes)).validate()
    with pytest.raises(ValueError):
        replace(ExperimentConfig(), safety_training_scenarios=["unknown"]).validate()


def test_packet_history_pipeline_audit_and_no_implicit_overwrite(tmp_path):
    config = replace(history_config(), methods=["safe", "gcc", "rl", "calibrated"])
    out = run_experiment(config, tmp_path / "run", plots=False)
    data = json.loads((out / "manifest.json").read_text())
    assert data["stage"] == "complete"
    assert all(sha256(out / name) == digest for name, digest in data["artifacts_sha256"].items())
    assert "Packet-v2" in data["notes"][1]
    with pytest.raises(FileExistsError):
        run_experiment(config, out, plots=False)
