from dataclasses import replace

import numpy as np
import pytest

from media_rl.config import ExperimentConfig, SimulatorConfig, split_seed
from media_rl.environment import MediaEnvironment, Telemetry, action_space
from media_rl.scenarios import SCENARIOS, Trace, load_trace, make_trace, save_trace


def constant_trace(capacity=3.0, loss=0.01, steps=20):
    return Trace(
        "custom",
        np.full(steps, capacity),
        np.full(steps, 40.0),
        np.full(steps, loss),
        np.zeros(steps),
        np.ones(steps, dtype=bool),
        np.zeros(steps),
        np.ones(steps),
    )


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_trace_determinism_and_episode_bounds(scenario):
    c = SimulatorConfig(steps=30)
    a, b = make_trace(scenario, 30, 1), make_trace(scenario, 30, 1)
    for key in vars(a):
        np.testing.assert_equal(getattr(a, key), getattr(b, key))
    with pytest.raises(ValueError):
        a.capacity[0] = 1
    env = MediaEnvironment(c, a)
    for i in range(c.steps):
        obs, reward, done, info = env.step(i % len(env.actions))
        assert obs.finite() and np.isfinite(reward)
        assert 0 <= info["queue_mbit"] <= c.queue_mbit * a.buffer_scale[i] + 1e-9
        for key in ["raw_loss", "residual_loss", "deadline_miss"]:
            assert 0 <= info[key] <= 1
        assert done == (i == c.steps - 1)
    with pytest.raises(RuntimeError):
        env.step(0)


def test_queue_conservation_and_preview_is_pure():
    env = MediaEnvironment(SimulatorConfig(steps=20), constant_trace(capacity=0.4))
    for _ in range(20):
        before = (env.t, env.queue, env.last, env.observation, len(env.feedback))
        expected = env.preview(len(env.actions) - 1)
        assert before == (env.t, env.queue, env.last, env.observation, len(env.feedback))
        _, _, _, actual = env.step(len(env.actions) - 1)
        assert actual == expected
        assert before[1] + actual["wire_mbps"] * env.config.dt_s == pytest.approx(
            actual["service_mbit"] + actual["queue_mbit"] + actual["overflow_mbit"]
        )


def test_fec_overhead_recovery_and_media_tradeoff():
    env = MediaEnvironment(SimulatorConfig(steps=20), constant_trace(capacity=10, loss=0.1))
    candidates = [(i, a) for i, a in enumerate(env.actions) if a.bitrate_mbps == 1.0]
    nofec = next(i for i, a in candidates if a.fec == 0 and a.low_latency)
    fec = next(i for i, a in candidates if a.fec == 0.25 and a.low_latency)
    normal = next(i for i, a in candidates if a.fec == 0 and not a.low_latency)
    x, y, z = env.preview(nofec), env.preview(fec), env.preview(normal)
    assert y["wire_mbps"] > x["wire_mbps"]
    assert y["residual_loss"] < x["residual_loss"]
    assert z["latency_ms"] > x["latency_ms"]


def test_outage_cannot_be_declared_safe():
    env = MediaEnvironment(SimulatorConfig(steps=20), constant_trace(capacity=0))
    for i in range(len(env.actions)):
        result = env.preview(i)
        assert result["safe"] == 0
        assert result["goodput_mbps"] == 0
        assert result["residual_loss"] == 1


def test_feedback_delay_and_no_future_capacity_leak():
    c = SimulatorConfig(steps=20, feedback_delay_steps=3)
    a = constant_trace(capacity=1)
    cap = a.capacity.copy()
    cap[5:] = 0
    b = replace(a, capacity=cap)
    x, y = MediaEnvironment(c, a), MediaEnvironment(c, b)
    assert x.observation == y.observation
    assert "capacity" not in vars(Telemetry())
    for i in range(5):
        ox, _, _, _ = x.step(0)
        oy, _, _, _ = y.step(0)
        assert ox == oy
        assert ox.valid == (i >= 2)
    assert ox.feedback_age_s == pytest.approx(0.2)


def test_feedback_gap_age_and_trace_roundtrip(tmp_path):
    trace = make_trace("feedback_gap", 100, 2)
    save_trace(trace, tmp_path / "trace.npz")
    other = load_trace(tmp_path / "trace.npz")
    np.testing.assert_array_equal(trace.capacity, other.capacity)
    env = MediaEnvironment(SimulatorConfig(steps=100), trace)
    for _ in range(50):
        obs, _, _, _ = env.step(0)
    assert obs.feedback_age_s > 1


def test_split_namespaces_and_config_validation():
    values = [
        split_seed(1, split, e) for split in ["train", "risk", "calibration", "test"] for e in range(100)
    ]
    assert len(values) == len(set(values))
    for config in [
        replace(ExperimentConfig(), methods=["typo"]),
        replace(ExperimentConfig(), seeds=[1, 1]),
        replace(ExperimentConfig(), simulator=SimulatorConfig(dt_s=0)),
        replace(ExperimentConfig(), simulator=SimulatorConfig(bitrates=[1, 0.5])),
        replace(ExperimentConfig(), simulator=SimulatorConfig(fec_levels=[-0.1])),
        replace(ExperimentConfig(), gate=replace(ExperimentConfig().gate, max_ensemble_std=0.51)),
    ]:
        with pytest.raises(ValueError):
            config.validate()
    with pytest.raises(ValueError):
        split_seed(1, "unknown")
    assert len(action_space(SimulatorConfig())) == 42
