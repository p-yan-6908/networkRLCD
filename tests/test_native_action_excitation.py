"""Randomized hold/data credit software only; no native or learned gain evidence."""

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from test_native_action_coverage import fixture

from media_rl import native_action_coverage as coverage
from media_rl import native_action_excitation as study
from media_rl import native_action_excitation_control as control
from media_rl.native_action_learning import physical_group
from media_rl.native_dense_study import audit_dense_episode
from media_rl.native_protocol import digest, read_json
from media_rl.native_repair3_policy import INPUT_DIM

ROOT = Path(__file__).resolve().parents[1]


def test_fixed_source_projection_exact_and_full_verifier_code_preserved():
    old = (ROOT / "benchmarks/native_rtc/coverage_episode.mjs").read_text()
    new = (ROOT / "benchmarks/native_rtc/excitation_episode.mjs").read_text()
    assert study.project_collector(old) == new
    assert study._RAW_AUDIT.__code__ is audit_dense_episode.__code__
    assert study._RAW_AUDIT.__globals__ is not audit_dense_episode.__globals__
    assert study._RAW_AUDIT.__globals__["exploration_cap"] is control.exploration_cap
    assert audit_dense_episode.__globals__["exploration_cap"] is not control.exploration_cap
    assert coverage._RAW_AUDIT.__code__ is audit_dense_episode.__code__
    with pytest.raises(ValueError):
        study.project_collector(old.replace("native_exact_cap_coverage_v1", "changed"))


def test_preregistered_training_plan_role_source_groups_and_alias_seeds(tmp_path):
    root, parent, old, _ = fixture(tmp_path)
    old_sha = digest(root / "manifest.json")
    config = tmp_path / "excitation.json"
    p = study.plan_excitation(root, config, seed=8101)
    assert p["stage"] == "train" and p["no_new_independent_groups"] and p["repair_model"] is None
    assert p["learner"] is None and not p["learned_policy_present"]
    assert p["excitation_caps"] == [300000, 450000, 900000] and study.compatible_engines(p)
    trials = coverage.trial_schedule(p)
    assert len(trials) == 24 and {physical_group(p, t) for t in trials} == {
        physical_group(old, t) for t in coverage.trial_schedule(old)
    }
    for t in trials:
        same = [a for a in trials if a["group"] == t["group"] and a["repetition"] == t["repetition"]]
        assert len({a["exploration_seed"] for a in same}) == 1
    assert digest(root / "manifest.json") == old_sha
    assert read_json(config) == p
    with pytest.raises(ValueError):
        study.plan_excitation(root, config)
    for role in ("calibration", "diagnostic", "selected", "validation", "test"):
        with pytest.raises(ValueError):
            study.validate_excitation(dict(p, stage=role))


def test_calibration_parent_cannot_be_relabelled(tmp_path):
    root, *_ = fixture(tmp_path, stage="calibration")
    with pytest.raises(ValueError, match="training parents"):
        study.plan_excitation(root, tmp_path / "forbidden.json")


def test_assignment_hold_alias_equivalence_feature_and_label_independence():
    features = [0.0] * 16
    features[9] = 1
    varied = features.copy()
    varied[0] = 400
    varied[7] = 0.9
    for seed in (0, 8101, 0xFFFFFFFF):
        caps = []
        for epoch in range(60):
            values = [
                control.exploration_cap("random-hold-a", epoch * 8 + i, seed, features) for i in range(8)
            ]
            assert len(set(values)) == 1
            assert values[0] == control.exploration_cap("random-hold-b", epoch * 8, seed, varied)
            caps.append(values[0])
        assert set(caps) == set(control.CAPS) and sum(a != b for a, b in zip(caps, caps[1:])) / 59 >= 0.4
        assert all(control.assignment("fixed450", epoch, seed) == 450000 for epoch in range(60))


def test_python_javascript_exact_parity(tmp_path):
    script = tmp_path / "parity.mjs"
    script.write_text(
        "import {assignment} from "
        + json.dumps((ROOT / "benchmarks/native_rtc/excitation_control.mjs").as_uri())
        + ';console.log(JSON.stringify([0,8101,4294967295].flatMap(s=>["random-hold-a","random-hold-b","fixed450"].flatMap(b=>Array.from({length:60},(_,e)=>assignment(b,e,s))))));'
    )
    output = json.loads(subprocess.check_output(["node", str(script)], text=True))
    expected = [
        control.assignment(b, e, s)
        for s in (0, 8101, 0xFFFFFFFF)
        for b in control.BEHAVIORS
        for e in range(60)
    ]
    assert output == expected and len(output) == 540


def evidence():
    decisions, labels = [], []
    features = [0.0] * 16
    features[9] = 1
    prior = 300000
    for step in range(16):
        f = features.copy()
        f[7] = prior / 4e6
        cap = control.exploration_cap("random-hold-a", step, 8101, f)
        decisions.append(
            dict(
                step_id=step,
                observation=dict(features=f, sample_ms=step * 110),
                ack_ms=step * 110 + 5,
                proposed_action=dict(encoder_max_bitrate_bps=cap),
                actuation_readback=dict(encoder_max_bitrate_bps=cap),
            )
        )
        prior = cap
    for epoch in range(2):
        first = epoch * 8
        ack = decisions[first]["ack_ms"]
        for offset in (200, 310, 420, 530, 600):
            labels.append(
                dict(
                    source_id=len(labels) + 1,
                    capture_request_ms=ack + offset,
                    encoder_cap_bps=decisions[first]["actuation_readback"]["encoder_max_bitrate_bps"],
                    decision_id=first + offset // 110,
                    action_transition_inflight=offset == 530,
                    identifiable_ontime=offset != 200,
                    ontime_sampled_psnr_contribution=0 if offset == 200 else 30,
                )
            )
    sender = dict(decisions=decisions, measurement_cutoff_ms=1760)
    return (
        sender,
        labels,
        [[0.0] * INPUT_DIM for _ in decisions],
        dict(id="synthetic", condition="random-hold-a", exploration_seed=8101),
    )


def test_cohort_first_state_postack_window_deadline_and_zero_outcomes_preserved():
    args = evidence()
    before = deepcopy(args)
    r = study.build_cohorts(*args)
    assert r["completed_epochs"] == 2 and r["requests"] == 6 and not r["dropped"]
    assert all(c["weight"] == 3 and c["utility"] == 0.2 and c["miss"] == 1 / 3 for c in r["cohorts"])
    assert all(c["window_end_ms"] + 150 <= c["next_action_observation_or_cutoff_ms"] for c in r["cohorts"])
    assert r["cohorts"][0]["step"] == 0 and r["cohorts"][1]["step"] == 8
    assert all(c["excluded_inflight_requests"] == 1 and not c["future_actions_mixed"] for c in r["cohorts"])
    assert args == before and r["actual_executed_learned_steps"] == 0 and not r["causal_effect_proven"]


def test_future_action_before_deadline_and_partial_last_epoch_are_dropped_not_credited():
    sender, labels, states, trial = evidence()
    sender["decisions"][8]["observation"]["sample_ms"] = 700
    sender["measurement_cutoff_ms"] = sender["decisions"][8]["ack_ms"] + 740
    r = study.build_cohorts(sender, labels, states, trial)
    assert not r["cohorts"] and len(r["dropped"]) == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "state",
        "source-id",
        "step-id",
        "changed-cap",
        "source-cap",
        "future-decision",
        "future-ack",
        "target",
        "clock",
    ],
)
def test_tampered_factual_hold_association_rejects(mutation):
    sender, labels, states, trial = evidence()
    if mutation == "state":
        states[0][0] = float("nan")
    elif mutation == "source-id":
        labels[1]["source_id"] = labels[0]["source_id"]
    elif mutation == "step-id":
        sender["decisions"][2]["step_id"] = 99
    elif mutation == "changed-cap":
        sender["decisions"][2]["actuation_readback"]["encoder_max_bitrate_bps"] = 400000
    elif mutation == "source-cap":
        labels[0]["encoder_cap_bps"] = 400000
    elif mutation == "future-decision":
        labels[0]["decision_id"] = 8
    elif mutation == "future-ack":
        labels[0]["decision_id"] = 7
    elif mutation == "target":
        labels[0]["ontime_sampled_psnr_contribution"] = float("nan")
    else:
        sender["decisions"][0]["ack_ms"] = -1
    with pytest.raises(ValueError):
        study.build_cohorts(sender, labels, states, trial)


@pytest.mark.parametrize("seed", [-1, 2**32, True, 1.5, None])
def test_bad_seed_reject(seed):
    with pytest.raises(ValueError):
        control.assignment("random-hold-a", 0, seed)
