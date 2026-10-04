"""Independent bounded action-outcome candidate; synthetic tests are not efficacy."""

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from media_rl.native_action_learning import (
    calibrate_cells,
    fit_outcomes,
    load_role,
    physical_group,
    reconstruct_states,
)
from media_rl.native_action_policy import (
    CANDIDATES,
    CONFIG,
    CONTEXTS,
    MODEL_ABI,
    ActionPolicy,
    CausalState,
    action_features,
    predict_members,
    validate_bundle,
)
from media_rl.native_repair3_policy import FEATURES, INPUT_DIM
from media_rl.native_repair5_study import _close

ROOT = Path(__file__).resolve().parents[1]


def observation(now=0, cap=450000, bwe=1000000):
    f = [0.0] * 16
    f[0] = bwe / 4e6
    f[7] = cap / 4e6
    f[8] = 1.0
    f[9] = 1.0
    return dict(sample_ms=now, features=f, content_features=[0.2, 0.1, 1.0])


def feedback(now, delay=60, fps=30):
    return dict(
        source_id=int(now) + 1, capture_request_ms=now - 10 - delay, received_ms=now - 10, presented_fps=fps
    )


def bundle():
    w = np.zeros((INPUT_DIM + 3, 1))
    w[INPUT_DIM, 0] = 1
    member = [w.tolist(), [1.0], [[0.1, 0.0]], [0.0, -8.0]]
    cells = {
        f"{c}/{ctx}": dict(groups=0, episodes=0, requests=0, supported=False, platt=[1.0, 0.0], margin=1.0)
        for c in CANDIDATES
        for ctx in CONTEXTS
    }
    return dict(
        model_abi=MODEL_ABI,
        config=CONFIG.copy(),
        feature_names=FEATURES,
        candidates=list(CANDIDATES),
        training_roles=["train", "calibration"],
        members=[deepcopy(member) for _ in range(3)],
        cells=cells,
        training_skill_passed=True,
        native_deployment_qualified=False,
    )


def supported(b, cap=450000, context="ready", margin=0.02):
    b["cells"][f"{cap}/{context}"].update(groups=3, episodes=3, requests=60, supported=True, margin=margin)
    return b


def ready(p, cap=450000):
    p.observe(observation(0, cap))
    return p.observe(observation(600, cap), feedback(600))


def test_actual_scalar_history_and_causal_feedback_preserve_inputs():
    p = CausalState()
    o = observation()
    old = deepcopy(o)
    d = p.observe(o)
    assert o == old and d["history"][-16] == 450000 / 4e6
    assert d["context"] == "unknown" and len(d["history"]) == INPUT_DIM
    d = p.observe(observation(100), feedback(100))
    assert d["context"] == "ready"
    d = p.observe(observation(300), feedback(300, 150))
    assert d["context"] == "delayed"
    with pytest.raises(ValueError):
        p.observe(observation(299))
    with pytest.raises(ValueError):
        p.observe(observation(400), dict(feedback(400), received_ms=401))


def test_zero_rtt_mask_expiration_and_reset():
    p = CausalState()
    o = observation()
    o["features"][10] = 1
    d = p.observe(o)
    assert d["features"][10] == 0
    for now in range(100, 5100, 100):
        o = observation(now)
        o["features"][10] = 1
        o["features"][1] = (50 if now == 100 else 90) / 150
        d = p.observe(o)
    assert d["rtt_floor"] == 90
    d = p.observe(observation(7000))
    assert d["history_reset"] and p.started == 7000 and d["rtt_floor"] is None


@pytest.mark.parametrize("value", [True, 149999, 4000001, 450000.5, float("nan")])
def test_invalid_cap_or_features_fail_closed(value):
    o = observation()
    o["features"][7] = value / 4e6 if type(value) is not bool else value
    with pytest.raises(ValueError):
        CausalState().observe(o)


def test_missing_support_blocks_interpolation_and_global_margin_veto():
    b = bundle()
    p = ActionPolicy(b)
    d = ready(p)
    assert d["fallback"] and not any(d["eligible"]) and d["encoder_max_bitrate_bps"] == 850000
    supported(b, margin=0.102094)
    d = ready(ActionPolicy(b))
    assert d["fallback"]
    b["cells"]["450000/ready"]["groups"] = 2
    with pytest.raises(ValueError):
        validate_bundle(b)


def test_safe_supported_action_uses_same_budgets_and_exact_context():
    b = supported(bundle())
    d = ready(ActionPolicy(b))
    assert d["reason"] == "learned" and d["encoder_max_bitrate_bps"] == 450000
    assert d["learned_departure"] and d["departure_from_continuous_bwe"]
    assert d["risk_upper"][3] < 0.1 and d["hard_budget_bps"] == 950000
    p = ActionPolicy(b)
    p.observe(observation())
    d = p.observe(observation(600), feedback(600, 150))
    assert d["fallback"]
    assert (
        CONFIG["miss_budget"] == 0.1
        and CONFIG["disagreement_budget"] == 0.15
        and CONFIG["up_dwell_ms"] == 500
    )


def test_training_skill_and_upward_or_sender_guard_prevent_use():
    b = supported(bundle())
    b["training_skill_passed"] = False
    assert ready(ActionPolicy(b))["reason"] == "training_skill"
    b["training_skill_passed"] = True
    assert ready(ActionPolicy(b), 300000)["reason"] == "upward_guard"
    p = ActionPolicy(b)
    p.observe(observation())
    o = observation(600)
    o["features"][14] = 1
    o["features"][6] = 0.2
    assert p.observe(o, feedback(600))["reason"] == "sender_congestion"


def test_bwe_cap_budget_and_saturation_are_distinct_from_learning():
    b = supported(bundle())
    p = ActionPolicy(b)
    p.observe(observation())
    d = p.observe(observation(600, bwe=400000), feedback(600))
    assert d["fallback"] and d["encoder_max_bitrate_bps"] == 340000 and not d["eligible"][3]
    d = ActionPolicy().observe(observation(bwe=100000))
    assert d["scalar_cap_saturation"] and not d["learned_departure"]


def test_python_js_full_policy_and_prediction_parity(tmp_path):
    b = supported(bundle())
    rows = [dict(o=observation(i * 100), f=feedback(i * 100) if i else None) for i in range(1, 45)]
    rows.insert(0, dict(o=observation(), f=None))
    p = ActionPolicy(b)
    expected = []
    for r in rows:
        d = p.observe(r["o"], r["f"])
        expected.append(d)
        p.acknowledge(d["encoder_max_bitrate_bps"], r["o"]["sample_ms"] + 1)
    path = tmp_path / "input.json"
    path.write_text(json.dumps(dict(bundle=b, rows=rows)))
    code = "import fs from 'node:fs';const m=await import(process.argv[1]),v=JSON.parse(fs.readFileSync(process.argv[2])),p=new m.ActionPolicy(v.bundle),out=[];for(const r of v.rows){const d=p.observe(r.o,r.f);out.push(d);p.acknowledge(d.encoder_max_bitrate_bps,r.o.sample_ms+1);}console.log(JSON.stringify(out));"
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            code,
            (ROOT / "benchmarks/native_rtc/action_policy.mjs").as_uri(),
            str(path),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    _close(json.loads(result.stdout), expected)


def test_factual_fit_is_bounded_normalizes_only_train_and_learns_signal():
    rows = []
    for i in range(100):
        o = observation(i * 100)
        o["content_features"][0] = i / 100
        state = CausalState().observe(o)["history"]
        rows.append(
            dict(
                state=state,
                cap=300000 if i % 2 else 600000,
                utility=0.05 + 0.8 * i / 100,
                miss=0.95 - 0.8 * i / 100,
                weight=3,
                group=f"g{i % 4}",
            )
        )
    weights, norm, loss = fit_outcomes(rows, 6601, 120)
    assert (
        norm["fitted_roles"] == ["train"]
        and norm["mean"] == np.mean([r["state"] for r in rows], axis=0).tolist()
    )
    assert (
        loss[-1]["utility_mse"] < loss[0]["utility_mse"]
        and loss[-1]["miss_log_loss"] < loss[0]["miss_log_loss"]
    )
    b = bundle()
    b["members"] = [weights] * 3
    p = predict_members(b, rows[50]["state"])
    assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()
    assert action_features(450000, rows[0]["state"]) != action_features(400000, rows[0]["state"])


def test_exact_context_cell_crossfitting_and_unsupported_new_rates():
    b = bundle()
    state = CausalState().observe(observation())["history"]
    rows = []
    for i in range(3):
        rows.append(
            dict(
                state=state,
                cap=300000,
                context="ready",
                miss=0.05 + 0.1 * i,
                weight=30,
                group=f"g{i}",
                episode=f"e{i}",
            )
        )
    cells = calibrate_cells(b["members"], rows)
    c = cells["300000/ready"]
    assert c["supported"] and c["groups"] == 3 and c["requests"] == 90
    assert c["margin"] == pytest.approx(np.clip(max(c["held_out_group_residuals"]) + 0.02, 0, 1))
    assert all(f["held_out_group"] not in f["fit_groups"] for f in c["folds"])
    assert all(cells[f"{cap}/{ctx}"]["margin"] == 1 for cap in (400000, 450000, 500000) for ctx in CONTEXTS)


def test_physical_groups_never_count_parent_alias_or_repeat_as_independent():
    p = dict(video_source=dict(sha256="a" * 64))
    trial = dict(video_segment=[1, 2], schedule=[[2, "high", 6000]], group="g0", repetition=0)
    assert physical_group(p, trial) == physical_group(p, dict(trial, group="g1", repetition=99))
    assert physical_group(p, trial) != physical_group(p, dict(trial, video_segment=[3, 4]))


@pytest.mark.parametrize("role", ["diagnostic", "selected-calibration", "validation", "test"])
def test_forbidden_label_roles_are_rejected_before_any_audit(role):
    with pytest.raises(ValueError):
        load_role([], role)


def test_wrong_parent_and_projected_raw_cap_are_rejected(tmp_path):
    (tmp_path / "protocol.json").write_text(json.dumps(dict(stage="diagnostic")))
    with pytest.raises(ValueError):
        load_role([tmp_path], "train")
    o = observation()
    o["raw_source"] = dict(encoder_cap_bps=300000)
    with pytest.raises(ValueError):
        reconstruct_states(dict(decisions=[dict(observation=o, feedback_input=None)]), dict(sources=[]))


def test_zero_variance_prior_is_no_skill_not_a_false_win(monkeypatch):
    import media_rl.native_action_learning as m

    b = bundle()
    member = deepcopy(b["members"][0])
    member[0] = np.zeros((INPUT_DIM + 3, 1)).tolist()
    member[1], member[2], member[3] = [0.0], [[0.0, 0.0]], [0.0, 0.0]
    rows = [
        dict(state=[0.0] * INPUT_DIM, cap=cap, utility=0.5, miss=0.5, weight=1, group=f"g{group}")
        for group in range(8)
        for cap in (150000, 300000, 600000)
    ]
    monkeypatch.setattr(m, "fit_outcomes", lambda rows, seed, updates: (member, {}, []))
    cv = m.held_out_training_check(rows)
    assert not cv["passed"]
    assert all(f["utility_skill"] == 0 and f["risk_skill"] == 0 for f in cv["folds"])
    assert all(not (set(f["fit_groups"]) & set(f["held_out_groups"])) for f in cv["folds"])


def test_complete_fitting_pipeline_never_fits_calibration_weights(tmp_path, monkeypatch):
    import media_rl.native_action_learning as m
    from media_rl.native_observations import CAPS
    from media_rl.native_protocol import digest

    families = ["stable", "collapse", "variable", "brief-collapse"]
    datasets = {}
    for role, offset in [("train", 60), ("calibration", 400)]:
        roots = []
        ps = []
        for movie in range(2):
            root = tmp_path / f"{role}-{movie}"
            root.mkdir()
            (root / "manifest.json").write_text(json.dumps(dict(role=role, movie=movie)))
            roots.append(root)
            ps.append(
                dict(
                    video_source=dict(sha256=str(movie) * 64),
                    measurement_recipe=dict(encoder="synthetic fixture not native"),
                    groups=[
                        dict(family=f, video_segment=[offset + i * 20, offset + i * 20 + 20])
                        for i, f in enumerate(families)
                    ],
                )
            )
        rows = [
            dict(
                state=[0.0] * INPUT_DIM,
                cap=cap,
                utility=0.1,
                miss=0.2,
                weight=3,
                context="ready",
                group=f"{role}-g{g}",
                episode=f"{role}-g{g}-c{cap}",
                step=0,
            )
            for g in range(8)
            for cap in CAPS
        ]
        datasets[role] = (rows, ps, roots)
    monkeypatch.setattr(m, "load_role", lambda roots, role: datasets[role])
    monkeypatch.setattr(m, "held_out_training_check", lambda rows: dict(passed=False, folds=[]))
    calls = []
    norm = dict(
        mean=[0.0] * INPUT_DIM, scale=[1.0] * INPUT_DIM, fused_into_weights=True, fitted_roles=["train"]
    )

    def fit(rows, seed, updates):
        calls.append({r["group"] for r in rows})
        return deepcopy(bundle()["members"][0]), norm, []

    monkeypatch.setattr(m, "fit_outcomes", fit)
    out = tmp_path / "model"
    report = m.train_action_model(datasets["train"][2], datasets["calibration"][2], out)
    assert len(calls) == 3 and all(all(g.startswith("train-") for g in groups) for groups in calls)
    assert report["training_cv"]["passed"] is False and report["native_deployment_qualified"] is False
    model = json.loads((out / "model.json").read_text())
    assert model["state_normalization"]["fitted_roles"] == ["train"]
    seal = json.loads((out / "manifest.json").read_text())
    assert all(digest(out / name) == sha for name, sha in seal["artifacts_sha256"].items())
    with pytest.raises(ValueError):
        m.train_action_model(datasets["train"][2], datasets["calibration"][2], out)


def test_public_training_dispatch_preserves_multiple_legal_parents(monkeypatch, capsys):
    import media_rl.native_action_learning as m
    from media_rl.cli import main

    calls = []
    monkeypatch.setattr(
        m,
        "train_action_model",
        lambda tr, cr, out: calls.append((tr, cr, out)) or dict(native_deployment_qualified=False),
    )
    main(
        [
            "native-action-train",
            "--train-run",
            "t1",
            "--train-run",
            "t2",
            "--calibration-run",
            "c1",
            "--out",
            "o",
        ]
    )
    assert calls == [([Path("t1"), Path("t2")], [Path("c1")], Path("o"))]
    assert json.loads(capsys.readouterr().out)["native_deployment_qualified"] is False
