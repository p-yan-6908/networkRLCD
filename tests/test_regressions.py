import pytest
from test_environment import constant_trace

from media_rl.config import SimulatorConfig
from media_rl.controllers import DeterministicController
from media_rl.environment import MediaEnvironment


@pytest.mark.parametrize("method", ["safe", "heuristic", "gcc"])
def test_application_limited_acknowledgements_do_not_lock_bitrate_ladder(method):
    env = MediaEnvironment(SimulatorConfig(steps=100), constant_trace(capacity=10, loss=0, steps=100))
    controller = DeterministicController(env.actions, method)
    obs = env.reset()
    rates = []
    for _ in range(100):
        decision = controller.act(obs)
        obs, _, _, info = env.step(decision.action)
        rates.append(info["bitrate_mbps"])
    assert max(rates) > 1.0


def test_goodput_never_exceeds_bottleneck_service():
    env = MediaEnvironment(SimulatorConfig(steps=20), constant_trace(capacity=1.8, loss=0))
    for i in range(20):
        _, _, _, info = env.step(len(env.actions) - 1)
        assert info["goodput_mbps"] <= info["service_mbit"] / env.config.dt_s + 1e-12
