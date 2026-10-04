"""V3 mechanical regressions; artificial fixtures are not efficacy evidence."""

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from test_native_repair import feedback
from test_native_repair import obs as base_obs

from media_rl.native_repair3_learning import load_repair_transitions, reconstruct_causal_states
from media_rl.native_repair3_policy import (
    CONFIG,
    FEATURES,
    INPUT_DIM,
    REPAIR_ABI,
    RepairPolicy,
    SenderContentEncoder,
    executed_learned_action,
    validate_repair_bundle,
)
from media_rl.native_repair_study import exploration_cap


def obs(now, **kwargs):
    return dict(base_obs(now, **kwargs), content_features=[0.2, 0.1, 1])


def bundle(action=2):
    q = [np.zeros((INPUT_DIM, 2)).tolist(), [0, 0], np.zeros((2, 7)).tolist(), [0] * 7]
    q[-1][action] = 10
    risk = deepcopy(q)
    risk[-1] = [0] * 7
    risk[-1][action] = -7
    return dict(
        model_abi=REPAIR_ABI,
        config=deepcopy(CONFIG),
        feature_names=FEATURES,
        training_roles=["train", "calibration"],
        q_weights=q,
        q_ensemble=[deepcopy(q) for _ in range(3)],
        risk_weights=[deepcopy(risk) for _ in range(3)],
        platt=[1, 0],
        risk_margin=[0.02] * 7,
        calibration_groups=[4] * 7,
        calibration_episodes=[4] * 7,
        calibration_requests=[100] * 7,
    )


@pytest.mark.parametrize(
    "fault",
    ["missing", "unsupported", "risk", "disagreement", "content", "packet_delay", "rtt_rise", "upward_guard"],
)
def test_fallback_is_exact_baseline_never_a_congestion_ratchet(fault):
    b = bundle()
    if fault == "unsupported":
        b["calibration_groups"] = [0] * 7
    if fault == "risk":
        b["risk_margin"] = [1] * 7
    if fault == "disagreement":
        b["risk_weights"][0][-1] = [8] * 7
    p = RepairPolicy(None if fault == "missing" else b)
    p.observe(obs(0), feedback(0))
    for now, bwe in [(1000, 2000000), (1100, 500000), (1200, 2000000)]:
        row = obs(
            now,
            cap=150000 if fault == "upward_guard" else 1000000,
            bwe=bwe,
            delay=20 if fault == "packet_delay" else 0,
            rtt=100 if fault == "rtt_rise" else 50,
        )
        if fault == "content":
            row["content_features"] = [0, 0, 0]
        decision = p.observe(row, feedback(now))
        assert decision["fallback"]
        assert decision["encoder_max_bitrate_bps"] == exploration_cap("bwe", 0, 0, row["features"])
        assert decision["learned_action_index"] is None
        assert not executed_learned_action(decision, decision["encoder_max_bitrate_bps"])
        p.acknowledge(decision["encoder_max_bitrate_bps"], now)


def test_action_heads_distinguish_actions_and_count_only_executed_departures():
    p = RepairPolicy(bundle())
    p.observe(obs(0), feedback(0))
    d = p.observe(obs(1000, cap=1000000), feedback(1000))
    assert d["predicted_frame_miss"][2] < 0.01
    assert d["predicted_frame_miss"][0] == 0.5
    assert d["action_index"] == 2 and d["learned_departure"]
    assert executed_learned_action(d, 600000)
    assert not executed_learned_action(d, 300000)
    assert not executed_learned_action(d, 600000, "explore")
    d["eligible"][2] = False
    assert not executed_learned_action(d, 600000)


def test_baseline_equivalent_model_action_is_not_useful_learned_coverage():
    p = RepairPolicy(bundle(4))
    p.observe(obs(0), feedback(0))
    d = p.observe(obs(1000, cap=1600000), feedback(1000))
    assert d["reason"] == "learned" and not d["learned_departure"]
    assert not executed_learned_action(d, 1600000)


def test_content_clock_and_freshness_are_causal():
    encoder = SenderContentEncoder()
    assert encoder.snapshot(0) == [0, 0, 0]
    encoder.observe([0] * 2400, 10)
    assert encoder.snapshot(10) == [0, 0, 1]
    encoder.observe([255] * 2400, 20)
    assert encoder.snapshot(20) == [0, 2, 1]
    assert encoder.snapshot(521) == [0, 0, 0]
    with pytest.raises(ValueError, match="future"):
        encoder.snapshot(19)
    with pytest.raises(ValueError, match="advance"):
        encoder.observe([0] * 2400, 20)
    with pytest.raises(ValueError, match="grid"):
        SenderContentEncoder().observe([999] * 2400, 0)


def test_causal_transform_ignores_future_source_and_all_receiver_labels():
    sender = dict(decisions=[dict(observation=obs(t), feedback_input=None, changed=False) for t in [50, 100]])
    frames = dict(
        sources=[
            dict(capture_request_ms=10, reference_rgb=[0] * 2400),
            dict(capture_request_ms=75, reference_rgb=[128] * 2400),
            dict(capture_request_ms=5000, reference_rgb=[999] * 2400),
        ],
        observations=["receiver oracle"],
    )
    before = reconstruct_causal_states(sender, frames)
    frames["observations"] = [{"identifiable_ontime": False, "receiver_pixels": [255]}]
    frames["sources"][-1]["reference_rgb"] = "future corruption"
    after = reconstruct_causal_states(sender, frames)
    assert before == after and len(before[0]) == 736
    assert before[0][-1] == 1 and after[1][-2] > 0


@pytest.mark.parametrize("role", ["validation", "test", "repeatability", "selected-calibration"])
def test_evaluation_labels_refused_before_any_read(role, monkeypatch):
    import media_rl.native_repair3_learning as m

    monkeypatch.setattr(m, "read_json", lambda _: pytest.fail("evaluation input read"))
    with pytest.raises(ValueError, match="evaluation"):
        load_repair_transitions("does-not-exist", role)


def test_old_onehot_scalar_weights_and_nonmonotonic_mapping_rejected():
    b = bundle()
    b["risk_weights"][0][0] = np.zeros((INPUT_DIM + 7, 2)).tolist()
    with pytest.raises(ValueError, match="dimensions"):
        validate_repair_bundle(b)
    b = bundle()
    b["platt"] = [-1, 0]
    with pytest.raises(ValueError, match="monotonic"):
        validate_repair_bundle(b)


def test_v3_planning_preserves_v2_reservations_and_original_gates(tmp_path):
    from native_study_helpers import bundle as legacy_bundle

    from media_rl.native_protocol import DEFAULT_LIMITS, digest
    from media_rl.native_repair3_study import plan_repair_study, trial_schedule, validate_repair_protocol
    from media_rl.native_repair_study import plan_repair_study as plan_v2

    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"test-only-movie")
    catalog = tmp_path / "source.json"
    catalog.write_text(
        json.dumps(
            dict(
                source_abi="recorded_video_v1",
                path=str(movie),
                sha256=digest(movie),
                duration_ms=734000,
                attribution="fixture",
                license_url="https://example.invalid/rights",
                rights_asserted_by_importer=True,
                not_representative_corpus=True,
            )
        )
    )
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps(legacy_bundle()))
    results = tmp_path / "results"
    prior = plan_v2(source, catalog, tmp_path / "prior.json", results_directory=results)
    interrupted = results / "native-repair-interrupted"
    interrupted.mkdir(parents=True)
    (interrupted / "protocol.json").write_text(json.dumps(prior))
    p = plan_repair_study(source, catalog, tmp_path / "new.json", results_directory=results)
    assert p["source_kind"] == "recorded_video_repair_v3"
    assert p["limits"] == DEFAULT_LIMITS and len(trial_schedule(p)) == 64
    assert "assets/streamed_video.mjs" in p["extra_source_sha256"]
    assert all(a["video_segment"] != b["video_segment"] for a in prior["groups"] for b in p["groups"])
    bad = deepcopy(p)
    bad["limits"]["inference_p99_ms"] = 15
    with pytest.raises(ValueError, match="relax"):
        validate_repair_protocol(bad)


def test_fitter_supervises_seven_heads_on_legal_roles_only(tmp_path, monkeypatch):
    import media_rl.native_repair3_learning as m

    train_root, cal_root = tmp_path / "train", tmp_path / "cal"
    for root in (train_root, cal_root):
        root.mkdir()
        (root / "manifest.json").write_text('{"fixture":true}')

    def rows(n):
        return [
            dict(
                episode_id=f"e{i}",
                group=f"g{i % 8}",
                step_id=0,
                state=[0.0] * 736,
                next_state=[0.0] * 736,
                action=i % 7,
                reward=0.1,
                terminal=True,
                miss_fraction=0.1,
                label_count=100,
            )
            for i in range(n)
        ]

    def load(_, role):
        return rows(32 if role == "train" else 24), dict(
            measurement_recipe={"fixture": True},
            controller_config={},
            video_source={"sha256": role},
            groups=[{"video_segment": [0, 20000]}],
            source_kind="recorded_video_repair_v2",
        )

    monkeypatch.setattr(m, "load_repair_transitions", load)
    monkeypatch.setattr(m, "LEARNER", dict(m.LEARNER, updates=2, risk_updates=2, batch_size=8))
    report = m.train_repair_model(train_root, cal_root, tmp_path / "model")
    b = json.loads((tmp_path / "model/model.json").read_text())
    assert report["factual_action_heads"] == 7 and report["evaluation_labels_used"] is False
    assert report["causal_sender_content_reconstructed_from_owned_past_frames"]
    validate_repair_bundle(b)
    assert len(b["risk_weights"][0][0]) == 736 and len(b["risk_weights"][0][-1]) == 7
    with pytest.raises(ValueError, match="already exists"):
        m.train_repair_model("missing", "missing", tmp_path / "model")


def test_selected_calibration_preserves_heads_and_strict_limits_and_blocks_missing_groups():
    from media_rl.native_repair3_calibration import MUTABLE, fit_selected_repair_calibration

    b = bundle()
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
    fitted, report = fit_selected_repair_calibration(b, rows)
    assert {k: v for k, v in b.items() if k not in MUTABLE} == {
        k: v for k, v in fitted.items() if k not in MUTABLE
    }
    assert fitted["calibration_groups"] == [0, 0, 4, 0, 0, 0, 0]
    assert fitted["risk_margin"][0] == 1 and fitted["risk_margin"][2] < 1
    assert fitted["platt"][0] >= 0 and not report["policy_improved"]
    assert fitted["config"]["miss_budget"] == 0.1


@pytest.mark.parametrize(
    "command,flags",
    [
        ("plan", ["--source-model", "source", "--video-source", "video", "--out", "out"]),
        ("study", ["--config", "config", "--out", "out"]),
        ("audit", ["--run", "run"]),
        ("train", ["--train-run", "train", "--calibration-run", "cal", "--out", "out"]),
        ("calibrate", ["--run", "run", "--out", "out"]),
    ],
)
def test_all_public_v3_commands_dispatch_explicitly(command, flags, monkeypatch):
    import media_rl.native_repair3_cli as m
    from media_rl.cli import main

    seen = []
    monkeypatch.setattr(m, "run", lambda args: seen.append(args.command))
    main([f"native-repair3-{command}", *flags])
    assert seen == [f"native-repair3-{command}"]


def test_python_js_state_action_risk_and_content_parity(tmp_path):
    b = bundle()
    rng = np.random.default_rng(3611)
    for ensemble in (b["q_ensemble"], b["risk_weights"]):
        for w in ensemble:
            w[0] = rng.normal(0, 0.01, (INPUT_DIM, 2)).tolist()
            w[1] = [0.2, 0.3]
            w[2] = rng.normal(0, 0.1, (2, 7)).tolist()
    b["q_weights"] = deepcopy(b["q_ensemble"][0])
    p, content = RepairPolicy(b), SenderContentEncoder()
    steps, expected = [], []
    now, cap = 100.0, 300000
    for i in range(80):
        now += 1400 if i == 47 else 100
        rgb = rng.integers(0, 256, 2400).tolist()
        content.observe(rgb, now - 10)
        row = obs(now, cap=cap, bwe=400000 + (i % 7) * 400000, delay=20 if i % 11 == 0 else 0)
        row["content_features"] = content.snapshot(now)
        fb = None if i % 13 == 0 else feedback(now)
        d = p.observe(row, fb)
        cap = d["encoder_max_bitrate_bps"]
        p.acknowledge(cap, now + 1)
        steps.append(dict(observation=row, feedback=fb, rgb=rgb))
        expected.append(d)
    path = tmp_path / "input.json"
    path.write_text(json.dumps(dict(bundle=b, steps=steps)))
    module = (Path(__file__).parents[1] / "benchmarks/native_rtc/repair3_policy.mjs").as_uri()
    code = f"import {{RepairPolicy,SenderContentEncoder}} from '{module}';import {{readFileSync}} from 'node:fs';const input=JSON.parse(readFileSync(process.argv[1]));const p=new RepairPolicy(input.bundle),c=new SenderContentEncoder();const out=input.steps.map(s=>{{c.observe(s.rgb,s.observation.sample_ms-10);s.observation.content_features=c.snapshot(s.observation.sample_ms);const d=p.observe(s.observation,s.feedback);p.acknowledge(d.encoder_max_bitrate_bps,s.observation.sample_ms+1);return d;}});console.log(JSON.stringify(out));"
    actual = json.loads(subprocess.check_output(["node", "--input-type=module", "--eval", code, str(path)]))
    for a, e in zip(actual, expected, strict=True):
        assert a.keys() == e.keys()
        for k, value in e.items():
            if isinstance(value, list):
                np.testing.assert_allclose(a[k], value, atol=1e-10, rtol=1e-10)
            elif isinstance(value, float):
                assert a[k] == pytest.approx(value, abs=1e-10)
            else:
                assert a[k] == value
