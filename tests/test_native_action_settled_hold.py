import copy
from pathlib import Path

import pytest

from media_rl import native_action_excitation as base
from media_rl import native_action_settled_hold as h


def fixture():
    f = [0.0] * 16
    f[7] = 450000 / 4e6
    rows = [
        dict(
            step_id=i,
            observation=dict(sample_ms=i * 100, features=f),
            ack_ms=i * 100 + 1,
            proposed_action=dict(encoder_max_bitrate_bps=450000),
            actuation_readback=dict(encoder_max_bitrate_bps=450000),
        )
        for i in range(33)
    ]
    labels = [
        dict(
            source_id=i,
            capture_request_ms=t,
            encoder_cap_bps=450000,
            decision_id=int(t // 100),
            action_transition_inflight=False,
            identifiable_ontime=i % 2 == 0,
            ontime_sampled_psnr_contribution=80 if i % 2 == 0 else 0,
        )
        for i, t in enumerate((250, 350, 1850, 1950, 2050, 2150))
    ]
    return (
        dict(decisions=rows, measurement_cutoff_ms=3300),
        labels,
        [[0.0] * 736 for _ in rows],
        dict(condition="fixed450", exploration_seed=8101, id="test"),
    )


def test_versioned_temporal_globals_only_complete_raw_and_cohort_code():
    assert h.RAW_AUDIT.__code__ is base._RAW_AUDIT.__code__
    assert h.build_late_cohorts.__code__ is base.build_cohorts.__code__
    assert h.build_reference_cohorts.__code__ is base.build_cohorts.__code__
    assert h.EPOCH_STEPS == 32 and h.START_MS == 1800 and h.END_MS == 2200
    assert base.EPOCH_STEPS == 8 and base.COHORT_START_MS == 200 and base.COHORT_END_MS == 600


def test_seed_only_aliases_boundary_support():
    f = [0.0] * 16
    for step in range(200):
        assert h.settled_cap("random-hold-a", step, 8101, f) == h.settled_cap(
            "random-hold-b", step, 8101, [1.0] * 16
        )
        assert h.settled_cap("random-hold-a", step, 8101, f) == h.assignment(
            "random-hold-a", step // 32, 8101
        )
        assert h.settled_cap("fixed450", step, 0, f) == 450000
    assert {h.assignment("random-hold-a", i, 8101) for i in range(100)} == {300000, 450000, 900000}


@pytest.mark.parametrize(
    "step,seed,f",
    [
        (True, 0, [0] * 16),
        (-1, 0, [0] * 16),
        (0, -1, [0] * 16),
        (0, 0, [0] * 15),
        (0, 0, [float("nan")] * 16),
        (0, True, [0] * 16),
    ],
)
def test_invalid_action_input(step, seed, f):
    with pytest.raises(ValueError):
        h.settled_cap("random-hold-a", step, seed, f)


def test_late_reference_disjoint_misses_and_no_mutation():
    sender, labels, states, trial = fixture()
    before = copy.deepcopy((sender, labels, states, trial))
    late = h.build_late_cohorts(sender, labels, states, trial)
    early = h.build_reference_cohorts(sender, labels, states, trial)
    c = late["cohorts"][0]
    assert c["source_ids"] == [2, 3, 4, 5] and c["utility"] == 0.4 and c["miss"] == 0.5 and c["weight"] == 4
    assert early["cohorts"][0]["source_ids"] == [0, 1]
    assert c["last_request_deadline_before_ms"] == 2351 and c["next_action_observation_or_cutoff_ms"] == 3200
    assert c["state"] == states[0] and before == (sender, labels, states, trial)
    assert late["credit"]["actual_target_threshold_is_not_an_eligibility_gate"]


def test_future_deadline_and_zero_misses_retained():
    sender, labels, states, trial = fixture()
    for x in labels:
        x.update(identifiable_ontime=False, ontime_sampled_psnr_contribution=0)
    assert h.build_late_cohorts(sender, labels, states, trial)["cohorts"][0]["utility"] == 0
    sender["decisions"] = sender["decisions"][:24]
    states = states[:24]
    sender["measurement_cutoff_ms"] = 2300
    result = h.build_late_cohorts(sender, labels, states, trial)
    assert (
        not result["cohorts"]
        and result["dropped"][0]["reason"] == "future_action_or_cutoff_before_last_deadline"
    )


@pytest.mark.parametrize("kind", ["cap", "decision", "clock", "duplicate", "utility", "held-cap"])
def test_invalid_factual_cohort(kind):
    sender, labels, states, trial = fixture()
    if kind == "cap":
        labels[2]["encoder_cap_bps"] = 900000
    elif kind == "decision":
        labels[2]["decision_id"] = 32
    elif kind == "clock":
        sender["decisions"][0]["ack_ms"] = -1
    elif kind == "duplicate":
        labels.append(copy.deepcopy(labels[2]))
    elif kind == "utility":
        labels[2]["ontime_sampled_psnr_contribution"] = -1
    else:
        sender["decisions"][10]["actuation_readback"]["encoder_max_bitrate_bps"] = 300000
    with pytest.raises(ValueError):
        h.build_late_cohorts(sender, labels, states, trial)


def test_projection_actor_schema_unchanged_and_no_fallback():
    old = Path("benchmarks/native_rtc/encoder_response_episode.mjs").read_text()
    new = h.project_collector(old)
    actor = "const policyInput={observation_abi:observation.observation_abi,feature_names:observation.feature_names,features:observation.features};"
    assert (
        old.count(actor) == new.count(actor) == 1
        and "settledHoldCap(nativeConfig.behavior,decisions.length,nativeConfig.exploration_seed,observation)"
        in new
    )
    with pytest.raises(ValueError):
        h.project_collector(new)
