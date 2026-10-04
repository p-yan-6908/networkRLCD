from dataclasses import replace

import numpy as np
from test_environment import constant_trace
from test_history_training import history_config

from media_rl.config import SimulatorConfig
from media_rl.environment import MediaEnvironment, Telemetry
from media_rl.policy_features import PolicyFeatures
from media_rl.training import train_bundle


def test_new_cohort_labels_are_pure_action_sensitive_and_deadline_resolved():
    c = SimulatorConfig(steps=20, backend="packet_v2", queue_mbit=0.1)
    env = MediaEnvironment(c, constant_trace(capacity=1, loss=0, steps=20))
    low = next(i for i, a in enumerate(env.actions) if a.bitrate_mbps == 0.3 and a.fec == 0 and a.low_latency)
    high = next(i for i, a in enumerate(env.actions) if a.bitrate_mbps == 4 and a.fec == 0 and a.low_latency)
    before = repr(env.packet.state), env.t, env.queue, env.observation
    a, b = env.safety_preview(low, 3), env.safety_preview(high, 3)
    assert (repr(env.packet.state), env.t, env.queue, env.observation) == before
    assert a["safe"] == 1 and b["safe"] == 0
    assert not a["label_censored"] and not b["label_censored"]
    for _ in range(18):
        env.step(low)
    assert env.safety_preview(low, 3)["label_censored"]


def test_stale_reports_do_not_repeat_history_updates():
    encoder = PolicyFeatures("history_v2", 0.1)
    encoder.encode(Telemetry(valid=True, throughput_mbps=2, rtt_ms=50, feedback_age_s=0.1))
    value = encoder.throughput, encoder.loss, encoder.trend, encoder.min_rtt
    encoder.encode(Telemetry(valid=True, throughput_mbps=9, rtt_ms=10, feedback_age_s=0.2))
    assert (encoder.throughput, encoder.loss, encoder.trend, encoder.min_rtt) == value


def test_cohort_safety_training_excludes_censoring_and_uses_explicit_teacher():
    config = history_config()
    config = replace(
        config, training=replace(config.training, safety_horizon_steps=3, demonstration_methods=["gcc"])
    ).validate()
    bundle, rows = train_bundle(config, 7)
    assert len(rows) == config.training.calibration_episodes * (config.simulator.steps - 2)
    assert bundle.metadata["calibration_samples"] == len(rows)
    assert "new capture cohort" in bundle.metadata["safety_label"]
    assert all(np.isfinite(r["calibrated"]) for r in rows)
