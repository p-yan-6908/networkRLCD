"""Software fixtures, not real controller evidence or fit data."""

import json
import subprocess
from copy import deepcopy

import numpy as np
import pytest
from native_study_helpers import bundle as legacy_bundle

from media_rl.native_protocol import digest
from media_rl.native_repair_learning import load_repair_transitions, temporal_returns
from media_rl.native_repair_policy import (
    CONFIG,
    FEATURES,
    INPUT_DIM,
    REPAIR_ABI,
    RepairPolicy,
    feedback_features,
    validate_repair_bundle,
)
from media_rl.native_repair_study import (
    exploration_cap,
    plan_repair_study,
    trial_schedule,
    validate_repair_protocol,
)


def bundle():
    def weights(inputs, outputs):
        return [np.zeros((inputs, 2)).tolist(), [0, 0], np.zeros((2, outputs)).tolist(), [0] * outputs]

    q = weights(INPUT_DIM, 7)
    q[-1] = list(range(7))
    risk = weights(INPUT_DIM + 7, 1)
    risk[-1] = [-8]
    return dict(
        model_abi=REPAIR_ABI,
        config=deepcopy(CONFIG),
        feature_names=FEATURES,
        training_roles=["train", "calibration"],
        q_weights=q,
        q_ensemble=[deepcopy(q) for _ in range(3)],
        risk_weights=[deepcopy(risk) for _ in range(3)],
        platt=[1, 0],
        risk_margin=[0] * 7,
        calibration_episodes=[4] * 7,
        calibration_requests=[100] * 7,
    )


def obs(now, cap=300000, bwe=2000000, delay=0, rtt=50):
    f = [0.0] * 16
    for i, v in {
        0: bwe / 4000000,
        1: rtt / 150,
        6: delay / 150,
        7: cap / 4000000,
        9: 1,
        10: 1,
        14: 1,
    }.items():
        f[i] = v
    return dict(sample_ms=now, features=f)


def feedback(now, delay=90):
    return dict(
        source_id=int(now) + 1, capture_request_ms=max(0, now - delay), received_ms=now, presented_fps=30
    )


def test_seconds_of_history_and_gap_reset():
    p = RepairPolicy(bundle())
    for i in range(40):
        d = p.observe(obs(i * 100), feedback(i * 100))
    assert len(d["history"]) == 640 and len(p.history) == 32
    assert d["history"][:16] == obs(800)["features"]
    d = p.observe(obs(5100), feedback(5100))
    assert d["history_reset"] and d["history"][:-20] == [0] * 620
    with pytest.raises(ValueError, match="backwards"):
        p.observe(obs(5000))


def test_no_future_or_undeclared_feedback():
    with pytest.raises(ValueError, match="future"):
        feedback_features(feedback(200), 199)
    with pytest.raises(ValueError, match="schema"):
        feedback_features(dict(feedback(200), relay_queue=3), 200)
    assert feedback_features(None, 100) == [0, 1, 0, 0]
    assert feedback_features(feedback(100), 701)[2] == 0


def test_bwe_bound_immediate_downward_and_upward_dwell():
    p = RepairPolicy(bundle())
    p.observe(obs(0), feedback(0))
    d = p.observe(obs(600), feedback(600))
    assert d["encoder_max_bitrate_bps"] == 600000 and not d["fallback"]
    p.acknowledge(600000, 601)
    d = p.observe(obs(700, cap=600000), feedback(700))
    assert d["encoder_max_bitrate_bps"] == 600000 and d["reason"] == "upward_dwell"
    d = p.observe(obs(800, cap=600000, bwe=400000), feedback(800))
    assert d["encoder_max_bitrate_bps"] == 300000


def test_congestion_cut_is_immediate_and_hold_persists():
    p = RepairPolicy(bundle())
    p.observe(obs(0, cap=1000000), feedback(0))
    d = p.observe(obs(600, cap=1000000, delay=25), feedback(600))
    assert d["encoder_max_bitrate_bps"] <= 600000 and d["reason"] == "congestion_hold"
    p.acknowledge(d["encoder_max_bitrate_bps"], 601)
    d = p.observe(obs(1600, cap=600000), feedback(1600))
    assert d["encoder_max_bitrate_bps"] <= 600000


def test_low_risk_and_independent_support_required():
    b = bundle()
    b["risk_margin"] = [0.2] * 7
    p = RepairPolicy(b)
    p.observe(obs(0), feedback(0))
    assert p.observe(obs(600), feedback(600))["fallback"]
    b = bundle()
    b["calibration_episodes"] = [2] * 7
    p = RepairPolicy(b)
    p.observe(obs(0), feedback(0))
    assert p.observe(obs(600), feedback(600))["fallback"]
    b = bundle()
    b["config"]["miss_budget"] = 0.5
    with pytest.raises(ValueError, match="ABI"):
        validate_repair_bundle(b)


def test_evaluation_labels_refused_before_loading(monkeypatch):
    with pytest.raises(ValueError, match="evaluation"):
        load_repair_transitions("does-not-exist", "validation")


def test_temporal_return_never_bridges_episode_or_gap():
    rows = [
        dict(
            episode_id="a",
            step_id=0,
            state=[0] * 640,
            next_state=[1] * 640,
            action=0,
            reward=1,
            terminal=False,
        ),
        dict(
            episode_id="b",
            step_id=1,
            state=[0] * 640,
            next_state=[0] * 640,
            action=0,
            reward=10,
            terminal=True,
        ),
    ]
    _, _, returns, future, discounts = temporal_returns(rows)
    assert returns.tolist() == [1, 10] and not future[0].any() and discounts.tolist() == [0, 0]


@pytest.mark.parametrize("existing_kind", ["file", "directory", "symlink"])
def test_plan_refuses_existing_path_before_loading_inputs(tmp_path, existing_kind):
    out = tmp_path / "reserved.json"
    if existing_kind == "file":
        out.write_bytes(b"frozen protocol")
    elif existing_kind == "directory":
        out.mkdir()
    else:
        out.symlink_to(tmp_path / "missing-target.json")
    with pytest.raises(ValueError, match="plan already exists"):
        plan_repair_study(tmp_path / "missing-model", tmp_path / "missing-catalog", out)
    if existing_kind == "file":
        assert out.read_bytes() == b"frozen protocol"
    elif existing_kind == "directory":
        assert out.is_dir() and list(out.iterdir()) == []
    else:
        assert out.is_symlink() and not out.exists()


def test_plan_and_interrupted_reservations(tmp_path):
    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"software fixture")
    catalog = tmp_path / "source.json"
    catalog.write_text(
        json.dumps(
            dict(
                source_abi="recorded_video_v1",
                path=str(movie),
                sha256=digest(movie),
                duration_ms=734000,
                attribution="test",
                license_url="https://example.invalid/rights",
                rights_asserted_by_importer=True,
                not_representative_corpus=True,
            )
        )
    )
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps(legacy_bundle()))
    results = tmp_path / "results"
    p = plan_repair_study(source, catalog, tmp_path / "plan.json", results_directory=results)
    assert len(trial_schedule(p)) == 64
    interrupted = results / "native-repair-interrupted"
    interrupted.mkdir(parents=True)
    (interrupted / "protocol.json").write_text(json.dumps(p))
    new = plan_repair_study(source, catalog, tmp_path / "new.json", results_directory=results)
    assert all(a["video_segment"] != b["video_segment"] for a in p["groups"] for b in new["groups"])
    bad = deepcopy(p)
    bad["groups"][1]["video_segment"] = bad["groups"][0]["video_segment"]
    with pytest.raises(ValueError, match="leakage"):
        validate_repair_protocol(bad)
    bad = deepcopy(p)
    bad["limits"]["inference_p99_ms"] = 15
    with pytest.raises(ValueError, match="relax"):
        validate_repair_protocol(bad)


def test_python_js_parity(tmp_path):
    b = bundle()
    p = RepairPolicy(b)
    sequence = []
    expected = []
    cap = 300000
    rng = np.random.default_rng(3)
    for i in range(80):
        o = obs(i * 100, cap=cap, bwe=float(rng.uniform(0.2, 4) * 1e6), delay=20 if i % 19 == 0 else 0)
        f = feedback(i * 100) if i % 11 else None
        d = p.observe(o, f)
        changed = d["encoder_max_bitrate_bps"] != cap
        cap = d["encoder_max_bitrate_bps"]
        if changed:
            p.acknowledge(cap, i * 100 + 1)
        sequence.append(dict(observation=o, feedback=f, changed=changed, ack_ms=i * 100 + 1))
        expected.append(d)
    file = tmp_path / "input.json"
    file.write_text(json.dumps(dict(bundle=b, sequence=sequence)))
    js = "import {readFileSync} from 'node:fs';import {RepairPolicy} from './benchmarks/native_rtc/repair_policy.mjs';const x=JSON.parse(readFileSync(process.argv[1])),p=new RepairPolicy(x.bundle);console.log(JSON.stringify(x.sequence.map(r=>{const d=p.observe(r.observation,r.feedback);if(r.changed)p.acknowledge(d.encoder_max_bitrate_bps,r.ack_ms);return d;})));"
    r = subprocess.run(
        ["node", "--input-type=module", "-e", js, str(file)], capture_output=True, text=True, check=True
    )
    actual = json.loads(r.stdout)
    from media_rl.native_repair_study import _close

    _close(actual, expected)
    assert exploration_cap("sweep", 10, 3, obs(10)["features"]) in (
        150000,
        300000,
        600000,
        1000000,
        1600000,
        2500000,
        4000000,
    )
