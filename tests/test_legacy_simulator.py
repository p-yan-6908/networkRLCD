"""Frozen V9 fluid implementation: new simulator defaults must not rewrite history."""

import importlib.util
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

from media_rl.config import SimulatorConfig
from media_rl.environment import MediaEnvironment
from media_rl.scenarios import SCENARIOS, make_trace


@pytest.mark.parametrize("name", SCENARIOS)
def test_default_fluid_matches_immutable_v9_implementation(name):
    path = Path(__file__).parent / "fixtures" / "environment_v1.py"
    key = "media_rl._golden_fluid_v1"
    spec = importlib.util.spec_from_file_location(key, path)
    reference = importlib.util.module_from_spec(spec)
    sys.modules[key] = reference
    spec.loader.exec_module(reference)
    config = SimulatorConfig(steps=60, feedback_delay_steps=3)
    trace = make_trace(name, 60, 179)
    actual, old = MediaEnvironment(config, trace), reference.MediaEnvironment(config, trace)
    rng = np.random.default_rng(41)
    assert asdict(actual.reset()) == asdict(old.reset())
    for _ in range(config.steps):
        action = int(rng.integers(42))
        assert actual.preview(action) == old.preview(action)
        obs, reward, done, info = actual.step(action)
        expected, old_reward, old_done, old_info = old.step(action)
        assert asdict(obs) == asdict(expected)
        assert (reward, done, info) == (old_reward, old_done, old_info)
