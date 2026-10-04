from dataclasses import replace

import numpy as np
import pytest
from test_history_training import history_config

from media_rl.controllers import Decision
from media_rl.environment import MediaEnvironment, Telemetry
from media_rl.frontier_calibration import (
    FrontierCalibrationProtocol,
    collect_frontier_samples,
    recalibrate_frontier_bundle,
)
from media_rl.training import ModelBundle, train_bundle


def setup():
    config = history_config()
    config = replace(
        config,
        training=replace(config.training, safety_horizon_steps=3),
        gate=replace(config.gate, shield_top_k=42, threshold=0, max_ensemble_std=0.5),
    )
    bundle, _ = train_bundle(config, 7)
    return config, bundle


def accepted_controller(monkeypatch, fallback=False):
    class Controller:
        def act(self, obs):
            assert isinstance(obs, Telemetry)
            return Decision(0, 1, action_confidence=0.99, action_uncertainty=0, fallback=fallback)

    monkeypatch.setattr("media_rl.frontier_calibration.make_controller", lambda *args: Controller())


def test_cohort_collection_is_selected_not_proposal_deadline_resolved_and_censored(monkeypatch):
    config, bundle = setup()
    accepted_controller(monkeypatch)
    old = MediaEnvironment.safety_preview
    calls = []

    def preview(self, action, horizon):
        calls.append((action, horizon))
        return old(self, action, horizon)

    monkeypatch.setattr(MediaEnvironment, "safety_preview", preview)
    monkeypatch.setattr(
        MediaEnvironment,
        "preview",
        lambda *args: (_ for _ in ()).throw(AssertionError("one-step label used")),
    )
    protocol = FrontierCalibrationProtocol(episodes=2)
    raw, labels, rows, counts = collect_frontier_samples(config, 7, bundle, protocol)
    assert calls == [(0, 3)] * 40
    assert len(labels) == 36 and counts == dict(accepted=40, censored_excluded=4)
    assert all(r["action"] == 0 and r["proposal"] == 1 and r["step"] < 18 for r in rows)
    assert all(r["label_horizon_steps"] == 3 for r in rows)
    again, same, same_rows, _ = collect_frontier_samples(config, 7, bundle, protocol)
    np.testing.assert_array_equal(raw, again)
    np.testing.assert_array_equal(labels, same)
    assert rows == same_rows
    old_ids = {s for ids in bundle.metadata["split_trace_seeds"].values() for s in ids}
    assert not old_ids & {r["trace_seed"] for r in rows}


def test_fallback_rejected_candidate_scores_do_not_enter_selected_calibration(monkeypatch):
    config, bundle = setup()
    accepted_controller(monkeypatch, fallback=True)
    with pytest.raises(ValueError, match="no accepted"):
        collect_frontier_samples(config, 7, bundle, FrontierCalibrationProtocol(episodes=1))


def test_recalibration_freezes_actor_risk_single_and_source_metadata(tmp_path):
    config, bundle = setup()
    policy, safety, metadata = bundle.policy.to_dict(), bundle.safety.to_dict(), dict(bundle.metadata)
    derived, rows = recalibrate_frontier_bundle(config, 7, bundle, FrontierCalibrationProtocol(episodes=3))
    assert derived.policy.to_dict() == policy and derived.safety.to_dict() == safety
    assert derived.single_calibrator == bundle.single_calibrator and bundle.metadata == metadata
    assert derived.metadata["frontier_calibration"]["samples"] == len(rows)
    groups = [set(s) for s in derived.metadata["split_trace_seeds"].values()]
    assert all(not a & b for i, a in enumerate(groups) for b in groups[i + 1 :])
    derived.save(tmp_path / "derived.json")
    restored = ModelBundle.load(tmp_path / "derived.json")
    assert restored.policy.to_dict() == policy and restored.safety.to_dict() == safety
    assert restored.metadata["frontier_calibration"]["changed_selection_distribution_not_certified"]
    assert np.all(np.isfinite(restored.calibrator.predict([0.1, 0.5, 0.9])))


@pytest.mark.parametrize("episodes", [0, True, -1, 1.5])
def test_namespace_count_frontier_and_target_contracts(episodes):
    config, bundle = setup()
    with pytest.raises(ValueError):
        FrontierCalibrationProtocol(episodes=episodes).validate(config, bundle, 7)
    with pytest.raises(ValueError):
        FrontierCalibrationProtocol(split_namespace="test").validate(config, bundle, 7)
    with pytest.raises(ValueError):
        FrontierCalibrationProtocol().validate(
            replace(config, gate=replace(config.gate, shield_top_k=5)), bundle, 7
        )
