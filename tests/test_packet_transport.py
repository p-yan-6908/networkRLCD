from dataclasses import replace

import numpy as np
import pytest
from test_environment import constant_trace

from media_rl.config import ExperimentConfig, SimulatorConfig
from media_rl.environment import MediaEnvironment
from media_rl.packet_transport import Frame, PacketTransport
from media_rl.scenarios import SCENARIOS, load_trace, save_trace, simulation_trace


@pytest.mark.parametrize("name", SCENARIOS)
def test_packet_preview_mass_bounds_and_seeded_replay(name):
    c = SimulatorConfig(steps=30, backend="packet_v2", queue_mbit=0.12)
    trace = simulation_trace(c, name, 91)
    a, b = MediaEnvironment(c, trace), MediaEnvironment(c, trace)
    for step in range(c.steps):
        action = (step * 7 + 3) % len(a.actions)
        before = repr(a.packet.state)
        expected = a.preview(action)
        assert repr(a.packet.state) == before
        obs, reward, done, result = a.step(action)
        assert result == expected == b.step(action)[3]
        assert obs.finite() and np.isfinite(reward)
        assert result["queue_before_mbit"] + result["offered_mbit"] == pytest.approx(
            result["queue_mbit"] + result["total_service_mbit"] + result["overflow_mbit"], abs=1e-9
        )
        assert 0 <= result["queue_mbit"] <= c.queue_mbit * trace.buffer_scale[step] + 1e-9
        assert result["total_service_mbit"] <= trace.capacity[step] * c.dt_s + 1e-9
        assert result["service_mbit"] + result["cross_service_mbit"] == pytest.approx(
            result["total_service_mbit"]
        )
        for key in ["raw_loss", "residual_loss", "deadline_miss"]:
            assert 0 <= result[key] <= 1
        assert done == (step == c.steps - 1)
    with pytest.raises(RuntimeError):
        a.step(0)
    with pytest.raises(RuntimeError):
        a.preview(0)


def test_actual_delivered_cohorts_not_current_generated_quality():
    c = SimulatorConfig(steps=30, backend="packet_v2")
    env = MediaEnvironment(c, constant_trace(capacity=0, loss=0, steps=30))
    for _ in range(c.steps):
        _, _, _, result = env.step(len(env.actions) - 1)
        assert result["safe"] == 0 and result["goodput_mbps"] == 0
        assert result["qoe"] <= 0
    assert result["deadline_miss"] + result["residual_loss"] == pytest.approx(1.0)
    assert result["terminal_censored_frames"] > 0


def test_packet_headers_pacing_vbr_and_shared_background_queue():
    c = SimulatorConfig(steps=40, backend="packet_v2", queue_mbit=0.05)
    base = constant_trace(capacity=1.0, loss=0, steps=40)
    loaded = replace(base, cross_traffic=np.full(40, 1.1), vbr_scale=np.ones(40), transport_seed=2)
    a, b = MediaEnvironment(c, base), MediaEnvironment(c, loaded)
    action = next(
        i for i, x in enumerate(a.actions) if x.bitrate_mbps == 0.6 and x.fec == 0 and x.low_latency
    )
    free, busy = [], []
    for _ in range(c.steps):
        free.append(a.step(action)[3])
        busy.append(b.step(action)[3])
    assert sum(x["offered_mbit"] for x in free) > 0.6 * c.dt_s * c.steps
    assert sum(x["cross_service_mbit"] for x in busy) > 0
    assert sum(x["overflow_mbit"] for x in busy) > sum(x["overflow_mbit"] for x in free)
    assert sum(x["goodput_mbps"] for x in busy) < sum(x["goodput_mbps"] for x in free)
    assert max(x["wire_mbps"] for x in free) > min(x["wire_mbps"] for x in free)


def test_fec_byte_repair_is_bounded_and_does_not_repair_late_bytes_for_free():
    c = SimulatorConfig(steps=20, backend="packet_v2")
    transport = PacketTransport(c, constant_trace(steps=20))
    for repair, expected in [(0.0, 0.2), (0.25, 0.0)]:
        state = transport.state.clone()
        state.frames[0] = Frame(0.0, 1.0, 2.0, 0.85, received=0.8, repair=repair, lost=0.2)
        closed = []
        transport._close(state, 0, 0.1, closed)
        assert closed[0]["residual"] == pytest.approx(expected)
        assert closed[0]["goodput"] <= 1.0
    state = transport.state.clone()
    state.frames[0] = Frame(0.0, 1.0, 2.0, 0.85, received=0.8)
    closed = []
    transport._close(state, 0, 0.15, closed)
    assert closed[0]["late"] == pytest.approx(0.2)
    assert not closed[0]["safe"]


def test_feedback_requires_delivery_and_reverse_propagation_and_is_causal():
    c = SimulatorConfig(steps=20, backend="packet_v2", feedback_delay_steps=2)
    a = constant_trace(capacity=1, steps=20)
    cap = a.capacity.copy()
    cap[8:] = 0
    b = replace(a, capacity=cap)
    x, y = MediaEnvironment(c, a), MediaEnvironment(c, b)
    for i in range(8):
        ox, _, _, rx = x.step(0)
        oy, _, _, ry = y.step(0)
        assert ox == oy and rx == ry
        assert ox.valid == (i >= 2)
    assert ox.feedback_age_s == pytest.approx(0.2)
    # Queue sojourn appears once, not twice, in forward-path RTT.
    assert ox.rtt_ms >= 40


def test_transport_trace_roundtrip_and_strict_config(tmp_path):
    c = SimulatorConfig(steps=20, backend="packet_v2")
    trace = simulation_trace(c, "wifi", 13)
    save_trace(trace, tmp_path / "transport.npz")
    other = load_trace(tmp_path / "transport.npz")
    for key in vars(trace):
        np.testing.assert_equal(getattr(trace, key), getattr(other, key))
    assert not trace.cross_traffic.flags.writeable and not trace.vbr_scale.flags.writeable
    for invalid in [
        replace(c, backend="oops"),
        replace(c, fps=0),
        replace(c, packet_bytes=0),
        replace(c, pacing_factor=0.5),
        replace(c, cross_traffic_interval_s=0.2),
    ]:
        with pytest.raises(ValueError):
            replace(ExperimentConfig(), simulator=invalid).validate()
