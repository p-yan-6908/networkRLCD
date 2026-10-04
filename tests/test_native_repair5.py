"""V5 mechanical tests; fixtures and fitting probes are not native efficacy evidence."""

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from test_native_repair import feedback
from test_native_repair3 import bundle as core_fixture
from test_native_repair3 import obs

from media_rl.native_repair3_policy import CONFIG as CORE_CONFIG
from media_rl.native_repair3_policy import RepairPolicy as CorePolicy
from media_rl.native_repair5_policy import CONFIG, REPAIR_ABI, RepairPolicy, executed_learned_action


def fixture(action=2):
    b = core_fixture(action)
    b.update(model_abi=REPAIR_ABI, config=CONFIG.copy())
    return b


@pytest.mark.parametrize(
    "fault", ["missing", "risk", "unsupported", "spread", "content", "queue", "rtt", "upward"]
)
def test_faults_restore_exact_bwe_fallback_not_failed_unlimited_gcc(fault):
    b = fixture()
    if fault == "missing":
        b = None
    elif fault == "risk":
        b["risk_margin"] = [1.0] * 7
    elif fault == "unsupported":
        b["calibration_groups"] = [0] * 7
    elif fault == "spread":
        b["risk_weights"][0][-1] = [9.0] * 7
    p = RepairPolicy(b)
    old = CorePolicy(
        None if b is None else dict(b, model_abi="native_temporal_repair_v3", config=CORE_CONFIG.copy())
    )
    for t in (0, 1000):
        o = obs(t, cap=150000 if fault == "upward" else 1000000, delay=20 if fault == "queue" else 0)
        if t and fault == "content":
            o["content_features"] = [0, 0, 0]
        if t and fault == "rtt":
            o["features"][1] = 1
        d, reference = p.observe(o, feedback(t)), old.observe(o, feedback(t))
    assert d["fallback"] and d["encoder_max_bitrate_bps"] == reference["encoder_max_bitrate_bps"]
    assert not executed_learned_action(d, d["encoder_max_bitrate_bps"])


def test_lifetime_rtt_floor_expires_but_unchanged_alarm_and_hold_are_respected():
    p, old = RepairPolicy(fixture()), CorePolicy(core_fixture())
    reasons = []
    for t in range(0, 6501, 500):
        o = obs(t, cap=1000000)
        o["features"][1] = (20 if t == 0 else 80) / 150
        d, before = p.observe(o, feedback(t)), old.observe(o, feedback(t))
        reasons.append(d["reason"])
    assert reasons[1] == "sender_congestion"
    assert d["reason"] == "learned" and before["reason"] == "sender_congestion"
    assert p.core.rtt_floor == 80 and old.rtt_floor == 20
    assert CONFIG["rtt_rise_alarm_ms"] == 30 and CONFIG["emergency_hold_ms"] == 2000


def test_backwards_clock_does_not_poison_rolling_baseline():
    p = RepairPolicy()
    p.observe(obs(1000))
    before = deepcopy(p.rtt_samples)
    with pytest.raises(ValueError, match="clock"):
        p.observe(obs(500))
    assert p.rtt_samples == before


def test_complete_fitting_export_on_synthetic_roles_is_not_native_efficacy(tmp_path, monkeypatch):
    import media_rl.native_repair5_learning as learning
    from media_rl.native_repair5_study import LEARNER, RECIPE

    roots = [tmp_path / name for name in ("train-a", "train-b", "cal-a", "cal-b")]
    for root in roots:
        root.mkdir()
        (root / "manifest.json").write_text(json.dumps(dict(synthetic_only=True, id=root.name)))

    def load(root, role):
        assert root.name.startswith("train" if role == "train" else "cal")
        parent = str(root)
        state = [0.0] * 736
        rows = [
            dict(
                episode_id=f"{parent}/e{e}",
                group=f"{parent}/g{e // 4}",
                step_id=i,
                state=[v + (i + 1) * 0.001 for v in state],
                next_state=state,
                action=i,
                reward=0.3,
                miss_fraction=0.05,
                label_count=3,
                terminal=True,
            )
            for e in range(16)
            for i in range(7)
        ]
        offset = 0 if role == "train" else 20000
        p = dict(
            source_kind="recorded_video_repair_v5",
            controller_config=CONFIG,
            measurement_recipe=RECIPE,
            video_source=dict(sha256=("a" if root.name.endswith("a") else "b") * 64),
            groups=[
                dict(family=f, video_segment=[offset + i * 2000, offset + (i + 1) * 2000])
                for i, f in enumerate(("stable", "collapse", "variable", "brief-collapse"))
            ],
        )
        return rows, p

    monkeypatch.setattr(learning, "load_repair_transitions", load)
    monkeypatch.setattr(learning, "LEARNER", dict(LEARNER, hidden=4, updates=4, risk_updates=4, batch_size=4))
    out = tmp_path / "synthetic-model"
    report = learning.train_repair_model(roots[:2], roots[2:], out)
    b = json.loads((out / "model.json").read_text())
    assert report["train_groups"] == 8 and report["training_movies"] == 2
    assert (
        report["state_normalization_fitted_only_on_train"] and not report["unsupported_action_max_bootstrap"]
    )
    assert b["state_normalization"]["fused_into_weights"] and b["config"] == CONFIG
    assert len(b["q_ensemble"]) == len(b["risk_weights"]) == 3
    assert set(b["provenance"]) == {str(p.resolve() / "manifest.json") for p in roots}
    RepairPolicy(b)
    assert not report["evaluation_labels_used"] and not report["SOTA_achieved"]


def test_zero_rtt_is_unknown_and_raw_input_unchanged():
    p = RepairPolicy()
    o = obs(0)
    o["features"][1] = 0
    before = deepcopy(o)
    p.observe(o)
    assert p.core.rtt_floor is None and o == before
    assert p.core.history[-1][1][10] == 0


def test_learned_use_still_requires_departure_from_both_references():
    for action, expected in ((4, False), (2, True)):
        p = RepairPolicy(fixture(action))
        for t in (0, 1000):
            d = p.observe(obs(t, cap=4000000), feedback(t))
        assert d["learned_departure"] is expected
        assert d["risk_upper"][action] <= 0.1 and d["hard_budget_bps"] == 1900000
    assert CONFIG["miss_budget"] == 0.1 and CONFIG["disagreement_budget"] == 0.15
    assert CONFIG["bwe_headroom"] == 0.95 and CONFIG["min_calibration_groups"] == 3


def test_normalization_is_fused_exactly_without_changing_runtime_feature_abi():
    from media_rl.native_repair5_learning import fold_normalization
    from media_rl.networks import MLP

    rng = np.random.default_rng(41)
    net = MLP(16, 7, 7, rng)
    mean, scale = rng.normal(size=16), rng.uniform(0.1, 2, size=16)
    x = rng.normal(size=(32, 16))
    folded = fold_normalization(net, mean, scale)
    np.testing.assert_allclose(net((x - mean) / scale), folded(x), atol=1e-12)
    with pytest.raises(ValueError):
        fold_normalization(net, mean, np.zeros(16))


def test_factual_iql_terminal_target_converges_without_unsupported_action_max():
    from media_rl.native_repair5_learning import fit_iql_critic
    from media_rl.native_repair5_study import LEARNER

    config = dict(LEARNER, updates=600, learning_rate=0.003, hidden=8, batch_size=32)
    q, losses = fit_iql_critic(
        np.zeros((64, 4)),
        np.full(64, 2),
        np.full(64, 0.8),
        np.full((64, 4), 1000.0),
        np.ones(64, dtype=bool),
        config,
        1,
    )
    assert losses[-1] < losses[0] / 20
    assert abs(q(np.zeros(4))[2] - 0.8) < 0.1
    assert np.isfinite(q.params[0]).all()


def test_fitting_refuses_legacy_physics_and_selected_labels_before_audit(tmp_path):
    from media_rl.native_repair5_learning import load_repair_transitions, train_repair_model

    (tmp_path / "protocol.json").write_text(
        json.dumps(dict(stage="train", source_kind="recorded_video_repair_v4"))
    )
    with pytest.raises(ValueError, match="fresh V5"):
        load_repair_transitions(tmp_path, "train")
    with pytest.raises(ValueError, match="evaluation"):
        load_repair_transitions(tmp_path, "selected-calibration")
    with pytest.raises(ValueError, match="already exists"):
        train_repair_model("missing", "missing", tmp_path)


def test_selected_calibration_freezes_actor_risk_weights_and_limits():
    from media_rl.native_repair5_calibration import MUTABLE, fit_selected_repair_calibration

    b = fixture()
    rows = [
        dict(
            group=f"g{g}",
            episode_id=f"e{g}-{r}",
            action=2,
            state=[0.0] * 736,
            miss_fraction=0.08,
            label_count=20,
            learned=False,
        )
        for g in range(4)
        for r in range(4)
    ]
    selected, report = fit_selected_repair_calibration(b, rows)
    assert {k: v for k, v in b.items() if k not in MUTABLE} == {
        k: v for k, v in selected.items() if k not in MUTABLE
    }
    assert report["independent_groups"] == 4 and selected["risk_margin"][0] == 1


@pytest.mark.parametrize(
    "command,flags",
    [
        ("plan", ["--source-model", "source", "--video-source", "video", "--out", "out"]),
        ("study", ["--config", "config", "--out", "out"]),
        ("audit", ["--run", "run"]),
        ("calibrate", ["--run", "run", "--out", "out"]),
        (
            "train",
            [
                "--train-run",
                "a",
                "--train-run",
                "b",
                "--calibration-run",
                "c",
                "--calibration-run",
                "d",
                "--out",
                "out",
            ],
        ),
    ],
)
def test_public_v5_commands_dispatch(command, flags, monkeypatch):
    import media_rl.native_repair5_cli as m
    from media_rl.cli import main

    seen = []
    monkeypatch.setattr(m, "run", lambda args: seen.append(args))
    main([f"native-repair5-{command}", *flags])
    assert seen[0].command == f"native-repair5-{command}"
    if command == "train":
        assert seen[0].train_run == [Path("a"), Path("b")]


def test_python_js_rolling_rtt_parity_and_inherited_exact_screens():
    b = fixture()
    rows = []
    p = RepairPolicy(b)
    expected = []
    for t in range(0, 6501, 500):
        o = obs(t, cap=1000000)
        o["features"][1] = (20 if t == 0 else 80) / 150
        f = feedback(t)
        rows.append(dict(observation=o, feedback=f))
        expected.append(p.observe(o, f))
    program = "import {RepairPolicy} from './benchmarks/native_rtc/repair5_policy.mjs';const x=JSON.parse(process.argv[1]);const p=new RepairPolicy(x.bundle);console.log(JSON.stringify(x.rows.map(r=>p.observe(r.observation,r.feedback))));"
    actual = json.loads(
        subprocess.check_output(
            ["node", "--input-type=module", "-e", program, json.dumps(dict(bundle=b, rows=rows))], text=True
        )
    )
    for a, e in zip(actual, expected, strict=True):
        for k in (
            "encoder_max_bitrate_bps",
            "reason",
            "learned_departure",
            "history",
            "risk_upper",
            "eligible",
            "baseline_action_index",
        ):
            assert a[k] == e[k]
