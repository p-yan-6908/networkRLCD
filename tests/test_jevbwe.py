"""JevBWE invariants and synthetic end-to-end checks, not native efficacy tests."""

import copy
import gzip
import hashlib
import json
from dataclasses import asdict, replace

import numpy as np
import pytest

from media_rl.cli import main
from media_rl.config import SimulatorConfig
from media_rl.environment import action_space
from media_rl.jevbwe import (
    ABI,
    FEATURES,
    LAGS_MS,
    RATIOS,
    STATE_DIM,
    CausalHistory,
    JevBWE,
    ResidualConfig,
    ResidualModel,
    Sample,
)
from media_rl.jevbwe_credit import SettledCredit
from media_rl.jevbwe_experiment import (
    ROLES,
    DelayedEncoder,
    StudyConfig,
    audit_study,
    collect_role,
    evaluate_episode,
    evaluate_study,
    fit_network,
    load_study,
    qualify_action_value,
    role_seed,
    run_study,
    train_study,
)


def sample(now=0, **kwargs):
    return Sample(
        **{
            **dict(
                sample_ms=now,
                bwe_bps=1e6,
                delivery_bps=8e5,
                rtt_ms=50,
                requested_bps=1e6,
                actual_bps=8e5,
                encoder_target_bps=9e5,
                rtt_delta_ms=0,
                loss=0,
                jitter_ms=2,
                queue_trend_ms=0,
            ),
            **kwargs,
        }
    )


def weights(*, scores=None, bias=0):
    w = np.zeros((STATE_DIM + len(RATIOS), len(RATIOS)))
    w[-len(RATIOS) :] = np.eye(len(RATIOS))
    return [
        w.tolist(),
        [0] * len(RATIOS),
        np.asarray(scores if scores is not None else [0] * len(RATIOS)).reshape(-1, 1).tolist(),
        [bias],
    ]


def bundle(config=None):
    return dict(
        abi=ABI,
        config=asdict(config or ResidualConfig()),
        ratios=list(RATIOS),
        feature_names=list(FEATURES),
        lags_ms=list(LAGS_MS),
        training_roles=list(ROLES),
        mean=[0] * STATE_DIM,
        scale=[1] * STATE_DIM,
        reward_mean=0,
        reward_scale=1,
        utility_weights=weights(scores=[0, 0, 10, 0, 0, 0]),
        risk_weights=[weights(bias=-6) for _ in range(3)],
        calibrator=dict(slope=1, bias=0, method="identity"),
        support_limit=100,
        action_value_passed=True,
        calibration_rows=[10] * 6,
        calibration_episodes=[3] * 6,
    )


def test_six_relative_actions_do_not_change_the_legacy_42_actions():
    assert RATIOS == (0.6, 0.7, 0.8, 0.9, 1.0, 1.05)
    assert len(action_space(SimulatorConfig())) == 42
    c = ResidualConfig(max_bps=10e6)
    policy = JevBWE(ResidualModel(bundle(c)))
    d = policy.observe(sample(bwe_bps=8e6, requested_bps=8e6), safe_bps=9e6)
    assert d["requested_bps"] == 6.4e6  # the learned 0.8 residual, not an absolute cap
    assert d["proposal_ratio"] == 0.8 and d["learned_executed"]
    assert d["base_bps"] == 8e6


def test_increases_wait_1800ms_owned_same_cap_ack_does_not_restart_clock():
    b = bundle()
    b["utility_weights"] = weights(scores=[0, 0, 0, 0, 0, 10])
    policy = JevBWE(ResidualModel(b))
    for now in (0, 100, 900, 1700, 1799):
        d = policy.observe(sample(now, bwe_bps=2e6))
        assert d["requested_bps"] == 1e6 and d["reason"] == "upward_dwell"
        assert not d["learned_executed"]
        policy.acknowledge(1e6, now)  # repeated ownership ACKs must not defer increases forever
    d = policy.observe(sample(1800, bwe_bps=2e6))
    assert d["requested_bps"] == 2.1e6 and d["learned_executed"]
    policy.acknowledge(2.1e6, 1800)
    assert policy.observe(sample(1900, bwe_bps=3e6, requested_bps=2.1e6))["requested_bps"] == 2.1e6
    assert policy.observe(sample(2000, bwe_bps=4e5, requested_bps=2.1e6))["requested_bps"] == 4.2e5


def test_emergency_and_falling_safety_ceiling_never_wait_or_claim_neural_execution():
    policy = JevBWE(ResidualModel(bundle()))
    d = policy.observe(sample(loss=0.2))
    assert d["requested_bps"] <= 7e5 and d["reason"] == "congestion_decrease"
    assert not d["learned_executed"]
    policy.acknowledge(d["requested_bps"], 0)
    d = policy.observe(sample(100, requested_bps=7e5), safe_bps=100000)
    assert d["requested_bps"] == 100000  # safety wins when below application minimum
    assert not d["learned_executed"]  # all six proposals clip to the same command
    assert policy.observe(sample(200, requested_bps=100000), safe_bps=0)["requested_bps"] == 0


@pytest.mark.parametrize(
    "fields",
    [
        {"valid": False},
        {"bwe_bps": None},
        {"bwe_bps": float("nan")},
        {"feedback_age_ms": 501},
        {"qp": float("nan")},
        {"loss": 2},
    ],
)
def test_invalid_or_stale_features_fail_closed(fields):
    d = JevBWE(ResidualModel(bundle())).observe(sample(**fields))
    assert d["requested_bps"] <= 150000 and d["reason"] == "invalid_or_stale_telemetry"
    assert not d["learned_executed"] and d["predicted_unsafe"] is None


def test_risk_support_and_action_value_screens():
    b = bundle()
    b["risk_weights"] = [weights(bias=10) for _ in range(3)]
    d = JevBWE(ResidualModel(b)).observe(sample())
    assert d["fallback"] and d["requested_bps"] == 850000 and not any(d["eligible"])
    b = bundle()
    b["support_limit"] = 0
    assert JevBWE(ResidualModel(b)).observe(sample())["reason"] == "unsupported_history"
    b = bundle()
    b["calibration_rows"] = [0] * 6
    assert not any(JevBWE(ResidualModel(b)).observe(sample())["eligible"])
    b = bundle()
    b["action_value_passed"] = False
    d = JevBWE(ResidualModel(b)).observe(sample())
    assert d["requested_bps"] == 1e6 and d["reason"] == "unqualified_action_value"
    assert not d["learned_executed"]
    d = JevBWE(ResidualModel(b), ungated=True).observe(sample())
    assert d["requested_bps"] == 800000 and d["reason"] == "ungated_ablation"


def test_nullable_encoder_fields_are_distinct_and_history_is_ordered_causal():
    history = CausalHistory()
    states = []
    for now in (0, 1000, 2000, 3000):
        x, reset = history.observe(sample(now, requested_bps=1e6 + now * 100, qp=None if now < 3000 else 0))
        assert not reset
        states.append(x)
    width = 2 * len(FEATURES) + 1
    requested = FEATURES.index("requested_bps") * 2
    assert [states[-1][i * width + requested] for i in range(4)] == [0.25, 0.275, 0.30, 0.325]
    qp = FEATURES.index("qp") * 2
    assert states[-1][qp : qp + 2].tolist() == [0, 0]
    assert states[-1][3 * width + qp : 3 * width + qp + 2].tolist() == [0, 1]
    actual = FEATURES.index("actual_bps") * 2
    assert states[-1][-width + actual] != states[-1][-width + requested]
    x, reset = history.observe(sample(4101))
    assert reset and not np.any(x[:-width])
    with pytest.raises(ValueError, match="strictly advance"):
        history.observe(sample(4101))
    with pytest.raises(TypeError):
        Sample(sample_ms=0, bwe_bps=1, delivery_bps=1, rtt_ms=1, requested_bps=1, capacity_bps=99)


@pytest.mark.parametrize("fields", [{"valid": False}, {"feedback_age_ms": 501}, {"loss": 2}])
def test_stale_network_history_remains_masked_after_fresh_feedback_returns(fields):
    history = CausalHistory()
    history.observe(sample(0, **fields))
    state, _ = history.observe(sample(1000))
    width = 2 * len(FEATURES) + 1
    past = state[-2 * width : -width]
    assert past[:14].tolist() == [0] * 14  # network values/masks stay invalid at the old lag
    local = FEATURES.index("requested_bps") * 2
    assert past[local + 1] == 1  # locally owned command is still known
    assert state[-width + 1] == 1  # present BWE is fresh now


def test_ack_clock_config_and_checkpoint_validation():
    policy = JevBWE()
    with pytest.raises(ValueError):
        policy.acknowledge(1e6, 0)
    policy.observe(sample())
    policy.acknowledge(1e6, 100)
    with pytest.raises(ValueError):
        policy.observe(sample(50))
    with pytest.raises(ValueError):
        policy.acknowledge(1e6, 99)
    for field, value in (
        ("ratios", [0.8]),
        ("feature_names", []),
        ("scale", [0] * STATE_DIM),
        ("action_value_passed", 1),
        ("training_roles", ["test"]),
    ):
        b = bundle()
        b[field] = value
        with pytest.raises(ValueError):
            ResidualModel(b)
    b = bundle()
    b["utility_weights"][0][0][0] = float("nan")
    with pytest.raises(ValueError):
        ResidualModel(b)
    with pytest.raises(ValueError, match="runtime config"):
        JevBWE(ResidualModel(bundle()), replace(ResidualConfig(), up_dwell_ms=2000))
    with pytest.raises(ValueError):
        JevBWE().observe(sample(), safe_bps=float("nan"))


def begin(tracker, **kwargs):
    return tracker.begin(
        **{
            **dict(
                now_ms=0,
                action_index=2,
                state=[0] * STATE_DIM,
                requested_bps=1e6,
                previous_bps=450000,
                network_delay_ms=100,
            ),
            **kwargs,
        }
    )


def credit(tracker, now, target=1e6, qoe=2, unsafe=0, interval=100):
    return tracker.observe(
        now_ms=now, interval_ms=interval, encoder_target_bps=target, delivered_qoe=qoe, unsafe=unsafe
    )


def test_credit_waits_for_actual_encoder_target_then_network_propagation():
    tracker = SettledCredit()
    begin(tracker)
    for now in range(100, 1500, 100):
        assert credit(tracker, now, target=450000, qoe=1000) is None
    assert credit(tracker, 1500) is None
    assert credit(tracker, 1600, qoe=1000) is None  # pre-network response is not credited
    for now in range(1700, 2200, 100):
        assert credit(tracker, now) is None
    row = credit(tracker, 2200, unsafe=1)
    assert row["settled_ms"] == 1500 and row["credit_start_ms"] == 1600
    assert row["covered_ms"] == 600 and row["unsafe"] == 1 and not row["censored"]
    assert row["reward"] == pytest.approx(2 - 0.15 * abs(np.log(1e6 / 450000)))
    assert row["delivered_reward"] == 2


def test_decrease_credit_can_finish_earlier_and_missing_targets_are_retained():
    tracker = SettledCredit()
    begin(tracker, requested_bps=450000, previous_bps=1e6)
    for now in range(100, 800, 100):
        assert credit(tracker, now, target=450000) is None
    row = credit(tracker, 800, target=450000)
    assert row["settled_ms"] == 100 and not row["censored"]
    begin(tracker, now_ms=800)
    assert credit(tracker, 900, target=None) is None
    old = begin(tracker, now_ms=1000)
    assert old["censored"] and old["reward"] is None and old["censor_reason"] == "superseded"
    assert tracker.finish()["censored"]


def test_target_loss_and_overlapping_or_unordered_outcomes_are_not_training_rewards():
    tracker = SettledCredit()
    begin(tracker)
    credit(tracker, 100)
    with pytest.raises(ValueError):
        credit(tracker, 100)
    with pytest.raises(ValueError):
        credit(tracker, 200, interval=200)
    row = credit(tracker, 200, target=450000)
    assert row["censor_reason"] == "encoder_target_left_band" and row["reward"] is None


def tiny_config():
    return StudyConfig(
        steps=100,
        train_episodes=6,
        qualification_episodes=4,
        risk_episodes=4,
        calibration_episodes=4,
        epochs=5,
        hidden=4,
        test_seeds=[9901],
        scenarios=["steady", "collapse"],
    )


def test_encoder_dynamics_and_fitting_role_namespaces_are_explicit():
    c = tiny_config()
    encoder = DelayedEncoder(c)
    encoder.command(1e6, 0)
    encoder.advance(1400)
    assert encoder.target_bps == 150000
    encoder.advance(1500)
    assert encoder.target_bps == 1e6
    encoder.command(450000, 1600)
    encoder.advance(1700)
    assert encoder.target_bps == 450000
    assert len({role_seed(c.seed, role, e) for role in (*ROLES, "test") for e in range(8)}) == 40
    cohorts, raw = collect_role(c, "train")
    assert any(r["changed_action"] for r in cohorts)
    assert all(r["reward"] is None for r in cohorts if r["censored"])
    assert all(r["credit_start_ms"] >= r["settled_ms"] for r in cohorts if not r["censored"])
    history = CausalHistory(c.residual)
    first = {r["command_ms"]: r["state"] for r in cohorts if r["episode"] == 0}
    for r in (r for r in raw if r["episode"] == 0):
        state, _ = history.observe(Sample(**r["sample"]))
        if r["sample"]["sample_ms"] in first:
            assert state.tolist() == first[r["sample"]["sample_ms"]]


def test_action_value_check_cannot_pass_on_unchanged_or_aliased_actions():
    conditional = ResidualModel(bundle()).utility
    blind = ResidualModel(bundle()).utility
    rows = [
        dict(
            episode=e,
            action_index=i,
            state=[0] * STATE_DIM,
            changed_action=True,
            identifiable=True,
            reward=10 if i == 2 else 0,
        )
        for e in range(4)
        for i in range(6)
    ]
    args = (conditional, blind, np.zeros(STATE_DIM), np.ones(STATE_DIM), 0, 1)
    assert qualify_action_value(rows, *args)["passed"]
    assert not qualify_action_value([{**r, "changed_action": False} for r in rows], *args)["passed"]
    assert not qualify_action_value([{**r, "identifiable": False} for r in rows], *args)["passed"]


def test_switch_cost_information_alone_cannot_pass_delivered_only_qualification():
    conditional = ResidualModel(bundle()).utility
    blind = ResidualModel(bundle()).utility
    rows = [
        dict(
            episode=e,
            action_index=i,
            state=[0] * STATE_DIM,
            changed_action=True,
            identifiable=True,
            reward=10 if i == 2 else 0,
            delivered_reward=0,
        )
        for e in range(4)
        for i in range(6)
    ]
    args = (conditional, blind, np.zeros(STATE_DIM), np.ones(STATE_DIM), 0, 1)
    assert qualify_action_value(rows, *args)["passed"]
    assert not qualify_action_value(rows, *args, target="delivered_reward")["passed"]


def test_network_actually_learns_factual_action_labels():
    c = replace(tiny_config(), epochs=100, hidden=8, learning_rate=0.01)
    x = np.tile(np.eye(6), (8, 1))
    y = np.tile(np.arange(6), 8) / 5
    net = fit_network(x, y, c, 5)
    assert np.mean((net(x).ravel() - y) ** 2) < 0.001


@pytest.fixture
def fitted(tmp_path):
    c = tiny_config()
    path = tmp_path / "training"
    report = train_study(c, path)
    return c, path, report


def test_training_roundtrip_reproducibility_and_no_test_label_use(fitted, tmp_path):
    c, path, report = fitted
    assert report["promoted"] is False and report["synthetic_only"]
    b = json.loads((path / "model.json").read_text())
    model = ResidualModel(b)
    clone = ResidualModel(json.loads(json.dumps(b)))
    state, _ = CausalHistory().observe(sample())
    for a, z in zip(model.predict(state), clone.predict(state)):
        np.testing.assert_array_equal(a, z)
    altered_test = replace(c, test_seeds=[999999], scenarios=["feedback_gap"])
    train_study(altered_test, tmp_path / "training-again")
    assert (path / "model.json").read_bytes() == (tmp_path / "training-again" / "model.json").read_bytes()
    assert audit_study(path)["artifacts"] > 10
    with pytest.raises(FileExistsError):
        train_study(c, path)
    for role in ROLES:
        rows = json.loads(gzip.decompress((path / f"{role}_cohorts.json.gz").read_bytes()))
        assert all(r["role"] == role for r in rows)


def test_actual_model_evaluation_replay_preserves_weights_and_hash_inventory(fitted, tmp_path):
    c, path, _ = fitted
    before = hashlib.sha256((path / "model.json").read_bytes()).hexdigest()
    evaluation = tmp_path / "evaluation"
    report = evaluate_study(c, path / "model.json", evaluation)
    assert len(report["episodes"]) == 8 and len(report["contrasts"]) == 2
    assert report["model_sha256"] == before
    model = ResidualModel(json.loads((path / "model.json").read_text()))
    saved = json.loads(gzip.decompress((evaluation / "steady_9901_jevbwe.json.gz").read_bytes()))
    assert saved == evaluate_episode(c, model, "steady", 9901, "jevbwe")
    policy = JevBWE(model)
    for row in saved:
        decision = policy.observe(Sample(**row["sample"]))
        assert decision == row["decision"]
        if row["changed"]:
            policy.acknowledge(decision["requested_bps"], row["sample"]["sample_ms"])
    assert hashlib.sha256((path / "model.json").read_bytes()).hexdigest() == before
    assert audit_study(evaluation)["artifacts"] == 11
    (evaluation / "model.json").write_text("{}")
    with pytest.raises(ValueError, match="hash/inventory"):
        audit_study(evaluation)
    with pytest.raises(ValueError, match="config mismatch"):
        evaluate_study(replace(c, encoder_up_ms=1600), path / "model.json", tmp_path / "invalid")
    forged = json.loads((path / "model.json").read_text())
    forged["source_sha256"]["jevbwe.py"] = "0" * 64
    forged_path = tmp_path / "drifted-model.json"
    forged_path.write_text(json.dumps(forged))
    with pytest.raises(ValueError, match="source drift"):
        evaluate_study(c, forged_path, tmp_path / "drifted-evaluation")
    assert not (tmp_path / "drifted-evaluation").exists()


def test_raw_bwe_reference_logs_its_own_ceiling_during_feedback_gaps():
    c = tiny_config()
    rows = evaluate_episode(c, None, "feedback_gap", 9901, "bwe_raw")
    assert rows[0]["sample"]["valid"] is False
    assert any(r["sample"]["feedback_age_ms"] > 500 for r in rows)
    for row in rows:
        d, s = row["decision"], row["sample"]
        assert d["base_bps"] == s["bwe_bps"]
        assert d["safe_bps"] == min(c.residual.max_bps, 1.05 * s["bwe_bps"])
        assert d["requested_bps"] <= d["safe_bps"]


def test_public_commands_presets_config_rejection_and_end_to_end_run(tmp_path, capsys):
    for preset in ("configs/jevbwe_smoke_v1.json", "configs/jevbwe_pilot_v1.json"):
        assert load_study(preset).residual.up_dwell_ms == 1800
    with pytest.raises(SystemExit) as result:
        main(["--help"])
    assert result.value.code == 0
    help_text = capsys.readouterr().out
    for name in ("jevbwe-run", "jevbwe-train", "jevbwe-evaluate", "jevbwe-audit"):
        assert name in help_text
    c = tiny_config()
    config = tmp_path / "config.json"
    config.write_text(json.dumps(c.to_dict()))
    run = tmp_path / "run"
    main(["jevbwe-run", "--config", str(config), "--out", str(run)])
    assert json.loads(capsys.readouterr().out)["promoted"] is False
    main(["jevbwe-audit", "--run", str(run)])
    assert json.loads(capsys.readouterr().out)["artifacts"] > 20
    main(
        [
            "jevbwe-evaluate",
            "--config",
            str(config),
            "--model",
            str(run / "training" / "model.json"),
            "--out",
            str(tmp_path / "cli-evaluation"),
        ]
    )
    assert json.loads(capsys.readouterr().out)["synthetic_only"]
    with pytest.raises(SystemExit) as result:
        main(["jevbwe-run", "--config", str(config), "--out", str(run)])
    assert result.value.code == 2
    with pytest.raises(ValueError):
        replace(c, hold_ms=2000).validate()
    bad = copy.deepcopy(c.to_dict())
    bad["unrecognized"] = 1
    config.write_text(json.dumps(bad))
    with pytest.raises(TypeError):
        load_study(config)
    assert run_study  # public convenience symbol is imported/registered, not dead code
