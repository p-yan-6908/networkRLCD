import numpy as np
import pytest

from media_rl.published_rtc_peer import PublishedRtcPeer
from media_rl.rtc_spec_checked_peer import SpecCheckedRtcPeer


def first_packet():
    v = np.zeros((15, 10))
    for k, ms in [(0, 60), (5, 600)]:
        v[:, k] = [146 * 8000 / ms, 1, 146, 0, 0, 200, 1, 0, 0, 0, 0, 0, 0, 1, 0]
    return v.reshape(150)


@pytest.fixture
def forwarded(monkeypatch):
    calls = []

    def act(self, obs):
        calls.append(obs.copy())
        return dict(bandwidth_bps=12345.0, auxiliary_output=678.0, act_latency_ms=0.2)

    monkeypatch.setattr(PublishedRtcPeer, "act", act)
    # Parent construction/checkpoint/runtime behavior is independently covered;
    # this fixture isolates the new gate-to-inference boundary without model files.
    return SpecCheckedRtcPeer.__new__(SpecCheckedRtcPeer), calls


def test_valid_snapshot_forwarded_unchanged_as_float32_and_readiness_withheld(forwarded):
    estimator, calls = forwarded
    obs = first_packet()
    result = estimator.act(obs)
    assert np.array_equal(calls[0], obs.astype(np.float32)) and calls[0].dtype == np.float32
    assert result["bandwidth_bps"] == 12345 and result["auxiliary_output"] == 678
    assert result["policy_inference_executed"] and result["documented_receiver_checks_pass"]
    assert result["contract_and_act_latency_ms"] >= 0
    assert not result["original_controller_ready"] and not result["closed_loop"]
    assert not result["auxiliary_is_calibrated_risk"] and not result["causality_certified"]
    assert np.array_equal(obs, first_packet())


@pytest.mark.parametrize("error", ["units", "conditional_loss", "fixed_prior", "native", "boolean"])
def test_bad_inputs_never_forward_to_model(forwarded, error):
    estimator, calls = forwarded
    obs = first_packet()
    if error == "units":
        obs[:10] /= 1000
    elif error == "conditional_loss":
        obs[110] = 1
    elif error == "fixed_prior":
        obs[120] = 0.5624
    elif error == "native":
        obs = np.zeros(64)
    else:
        obs = np.zeros(150, dtype=bool)
    with pytest.raises(ValueError):
        estimator.act(obs)
    assert not calls


def test_caller_array_conversion_occurs_once_before_copy(forwarded):
    estimator, calls = forwarded

    class ChangingInput:
        def __init__(self):
            self.count = 0

        def __array__(self, dtype=None, copy=None):
            self.count += 1
            return first_packet() if self.count == 1 else np.zeros(64)

    obs = ChangingInput()
    estimator.act(obs)
    assert obs.count == 1 and len(calls) == 1
