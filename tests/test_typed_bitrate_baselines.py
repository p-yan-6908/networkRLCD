import json

import pytest

from media_rl.jevbwe import Sample
from media_rl.typed_bitrate import TypedConfig, load_config
from media_rl.typed_bitrate_baselines import KINDS, Rule, audit, candidates, headline, label, run_rule, tune
from media_rl.typed_bitrate_experiment import main, run, run_episode

TINY = dict(
    steps=120,
    tune_episodes=4,
    train_episodes=8,
    rounds=2,
    calibration_episodes=4,
    hidden=8,
    epochs=3,
    batch_size=32,
    model_seeds=[0],
    validation_seeds=[1],
    test_seeds=[2],
    scenarios=["steady", "collapse"],
    bootstrap_samples=50,
    workers=1,
)


def config(**changes):
    return TypedConfig(**{"base_ratio": 0.9, **changes}).validate()


def sample(now=0.0, **fields):
    values = dict(bwe_bps=1e6, delivery_bps=8e5, rtt_ms=50.0, requested_bps=8e5, loss=0.0)
    return Sample(sample_ms=now, **{**values, **fields})


def drive(rule, samples, every=10):
    """Feed one sample per 100 ms step; a decision every ``every`` steps, as in an episode."""
    return [rule.observe(s, i % every == 0) for i, s in enumerate(samples)]


def test_rules_reject_options_outside_the_typed_set():
    for bad in (
        dict(kind="pid", high=1.0, low=0.8),
        dict(kind="backoff", high=0.95, low=0.8),  # not a typed option
        dict(kind="backoff", high=0.8, low=0.9),  # the reduced ratio must be lower
        dict(kind="delay", high=1.0, low=0.8, on_ms=5, off_ms=10),
        dict(kind="knee", high=1.0, scale=0),
    ):
        with pytest.raises(ValueError):
            Rule(config(), **bad)


def test_candidates_stay_inside_the_declared_class():
    c = config()
    specs = candidates(c)
    assert {s["kind"] for s in specs} == set(KINDS)
    assert len({label(s) for s in specs}) == len(specs)
    assert all(s["high"] >= 0.9 and s["high"] in c.ratios for s in specs)
    assert all(s["low"] in c.ratios and s["low"] < s["high"] for s in specs if "low" in s)
    for spec in specs:
        Rule(c, **spec)


def test_backoff_holds_the_reduced_ratio_after_congestion_evidence():
    rule = Rule(config(), "backoff", high=1.0, low=0.7, hold_ms=2000)
    quiet = [sample(100.0 * i) for i in range(10)]
    assert set(drive(rule, quiet)) == {1.0}
    loss = sample(1000.0, loss=0.2)  # evidence on a decision step
    assert rule.observe(loss, True) == 0.7
    later = [rule.observe(sample(1000.0 + 100 * i), i % 10 == 0) for i in range(1, 31)]
    assert later[9] == 0.7 and later[19] == 0.7  # 1 s and 2 s after the evidence
    assert later[29] == 1.0  # the hold has passed


def test_rule_changes_ratio_only_at_decision_epochs():
    rule = Rule(config(), "backoff", high=1.0, low=0.7, hold_ms=4000)
    assert rule.observe(sample(0.0), True) == 1.0
    assert rule.observe(sample(100.0, loss=0.2), False) == 1.0  # seen, not yet acted on
    assert rule.observe(sample(200.0), False) == 1.0
    assert rule.observe(sample(1000.0), True) == 0.7


def test_delay_rule_has_hysteresis_and_survives_a_feedback_gap():
    rule = Rule(config(), "delay", high=1.0, low=0.8, on_ms=30, off_ms=10)
    assert rule.observe(sample(0.0, rtt_ms=50), True) == 1.0
    assert rule.observe(sample(1000.0, rtt_ms=85), True) == 0.8  # 35 ms over the floor
    assert rule.observe(sample(2000.0, rtt_ms=70), True) == 0.8  # between the thresholds: unchanged
    assert rule.observe(sample(3000.0, rtt_ms=70, valid=False), True) == 0.8  # no fresh telemetry
    assert rule.observe(sample(4000.0, rtt_ms=58), True) == 1.0


def test_knee_rule_caps_at_the_delivery_seen_before_congestion():
    rule = Rule(config(), "knee", high=1.05, scale=1.0, hold_ms=5000)
    assert rule.observe(sample(0.0, delivery_bps=9e5), True) == 1.05
    rule.observe(sample(100.0, delivery_bps=7.2e5), False)
    rule.observe(sample(200.0, loss=0.2), False)  # onset: the knee is the best recent delivery
    assert rule.knee_bps == 9e5
    assert rule.observe(sample(1000.0, bwe_bps=1e6), True) == 0.9  # largest option within 0.9x BWE
    assert rule.observe(sample(2000.0, bwe_bps=2e6), True) == 0.6  # nothing fits: the lowest option
    assert rule.observe(sample(8000.0, bwe_bps=1e6), True) == 1.05  # the hold has passed


def test_ladder_steps_down_on_evidence_and_up_after_a_quiet_hold():
    rule = Rule(config(), "ladder", high=1.0, low=0.8, hold_ms=2000)
    assert rule.observe(sample(0.0), True) == 1.0
    assert rule.observe(sample(1000.0, loss=0.2), True) == 0.9
    assert rule.observe(sample(2000.0, loss=0.2), True) == 0.8
    assert rule.observe(sample(3000.0, loss=0.2), True) == 0.8  # never below the reduced ratio
    assert rule.observe(sample(4000.0), True) == 0.8  # 1 s of quiet is not enough
    assert rule.observe(sample(6000.0), True) == 0.9
    assert rule.observe(sample(7000.0), True) == 0.9  # one step per hold
    assert rule.observe(sample(8000.0), True) == 1.0


def test_fixed_ratio_replay_matches_the_study_runner():
    c = config(steps=120)
    for scenario, seed in (("steady", 5), ("collapse", 7), ("dip", 9)):
        mine = run_rule(c, scenario, seed, dict(kind="fixed", ratio=0.9))
        theirs = run_episode(c, None, scenario, seed, dict(kind="fixed", ratio=0.9))
        assert all(mine[k] == theirs[k] for k in mine)


def test_audit_tunes_on_training_traces_and_pairs_with_the_frozen_panel(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(TINY))
    run(load_config(path), tmp_path / "run")
    frozen = load_config(tmp_path / "run" / "config.json")
    before = (tmp_path / "run" / "report.json").read_bytes()
    report = audit(tmp_path / "run", tmp_path / "audit", samples=40)
    assert (tmp_path / "run" / "report.json").read_bytes() == before  # the frozen run is only read
    tuning = report["tuning"]
    assert tuning["best_fixed"] == frozen.base_ratio  # the same traces select the same base
    assert tuning["candidates"] == len(candidates(frozen))
    best = tuning["selected"]["rule_best"]
    assert best["utility"] == max(row["utility"] for row in tuning["rules"])
    assert best == tune(frozen)["selected"]["rule_best"]  # deterministic
    safe = tuning["selected"]["rule_safe"]
    assert safe is None or safe["unsafe"] <= tuning["base"]["unsafe"]
    assert report["extended"]["ceiling_effect"] == 0  # the raised ceiling leaves the frozen options alone
    assert max(report["extended"]["ratios"]) == 1.5
    assert set(report["panels"]) == {"validation", "test"}
    for split in report["panels"].values():
        assert split["pairing_max_difference"] == 0
    test = report["panels"]["test"]["panels"]
    assert set(test) == {"id", "ood", "all"}
    pairs = test["all"]["contrasts"]
    assert {
        "rule_best_vs_train_fixed",
        "head_vs_rule_best",
        "head_vs_train_fixed",
        "oracle_vs_rule_best",
    } <= set(pairs)
    u = pairs["head_vs_rule_best"]["utility"]
    assert u["families"] == 2 and len(u["family_t_interval95"]) == 2
    head = pairs["head_vs_train_fixed"]["utility"]["mean"]
    rule = pairs["rule_best_vs_train_fixed"]["utility"]["mean"]
    assert u["mean"] == pytest.approx(head - rule)
    assert set(test["all"]["wide_fixed"]) == {f"{r:.2f}" for r in report["extended"]["ratios"]}
    assert "head_vs_rule_best" in headline(report)
    with pytest.raises(FileExistsError):
        audit(tmp_path / "run", tmp_path / "audit")
    with pytest.raises(SystemExit):
        main(["baselines", "--run", str(tmp_path / "run"), "--out", str(tmp_path / "audit")])
