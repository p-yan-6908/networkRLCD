"""V4 deferral invariants; artificial fixtures are not controller evidence."""

from copy import deepcopy

import pytest
from test_native_repair import feedback
from test_native_repair3 import bundle as core_fixture
from test_native_repair3 import obs

from media_rl.native_repair3_policy import CONFIG as CORE_CONFIG
from media_rl.native_repair3_policy import RepairPolicy as CorePolicy
from media_rl.native_repair4_policy import (
    CONFIG,
    GCC_CEILING,
    RepairPolicy,
    executed_learned_action,
    rebase_repair_bundle,
    validate_repair_bundle,
)


@pytest.mark.parametrize(
    "fault", ["missing", "risk", "unsupported", "spread", "content", "queue", "rtt", "upward"]
)
def test_veto_yields_native_gcc_not_another_app_limited_ceiling(fault):
    b = rebase_repair_bundle(core_fixture())
    if fault == "missing":
        b = None
    elif fault == "risk":
        b["risk_margin"] = [1.0] * 7
    elif fault == "unsupported":
        b["calibration_groups"] = [0] * 7
    elif fault == "spread":
        b["risk_weights"][0][-1] = [9.0] * 7
    p = RepairPolicy(b)
    p.observe(obs(0), feedback(0))
    row = obs(1000, cap=150000 if fault == "upward" else 1000000, delay=20 if fault == "queue" else 0)
    if fault == "content":
        row["content_features"] = [0.0, 0.0, 0.0]
    if fault == "rtt":
        row["features"][1] = 1.0
    d = p.observe(row, feedback(1000))
    assert d["fallback"] and d["encoder_max_bitrate_bps"] == GCC_CEILING
    assert not d["learned_departure"] and not executed_learned_action(d, GCC_CEILING)


def test_learned_screen_and_weights_unchanged_while_reference_is_native_gcc():
    original = core_fixture(1)
    converted = rebase_repair_bundle(original)
    assert original["config"] == CORE_CONFIG and converted["config"] == CONFIG
    assert {k: v for k, v in original.items() if k not in ("model_abi", "config")} == {
        k: v for k, v in converted.items() if k not in ("model_abi", "config")
    }
    a, b = CorePolicy(original), RepairPolicy(converted)
    for t in (0, 1000):
        before = a.observe(obs(t, cap=4000000), feedback(t))
        after = b.observe(obs(t, cap=4000000), feedback(t))
    for key in (
        "q_values",
        "predicted_frame_miss",
        "risk_upper",
        "risk_disagreement",
        "eligible",
        "hard_budget_bps",
        "history",
    ):
        assert before[key] == after[key]
    assert after["reason"] == "learned" and executed_learned_action(after, 300000)
    assert after["encoder_max_bitrate_bps"] <= after["hard_budget_bps"]
    forged = deepcopy(after)
    forged["eligible"][1] = False
    assert not executed_learned_action(forged, 300000)


def test_changing_fallback_cannot_credit_old_bwe_equivalent_model_choices():
    p = RepairPolicy(rebase_repair_bundle(core_fixture(4)))
    p.observe(obs(0, cap=4000000), feedback(0))
    d = p.observe(obs(1000, cap=4000000), feedback(1000))
    assert d["reason"] == "learned" and d["gcc_departure"]
    assert d["action_index"] == d["bwe_reference_action_index"]
    assert not d["learned_departure"] and not executed_learned_action(d, 1600000)


def test_planning_adds_gcc_without_dropping_old_controls_or_v3_reservations(tmp_path):
    import json

    from native_study_helpers import bundle as legacy_bundle

    from media_rl.native_protocol import DEFAULT_LIMITS, digest
    from media_rl.native_repair3_study import plan_repair_study as plan_v3
    from media_rl.native_repair4_study import (
        exploration_cap,
        plan_repair_study,
        trial_schedule,
        validate_repair_protocol,
    )

    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"fixture-only")
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
    previous = plan_v3(source, catalog, tmp_path / "prior.json", results_directory=results)
    prefix = results / "native-repair3-interrupted"
    prefix.mkdir(parents=True)
    (prefix / "protocol.json").write_text(json.dumps(previous))
    p = plan_repair_study(source, catalog, tmp_path / "new.json", results_directory=results)
    assert p["limits"] == DEFAULT_LIMITS and len(trial_schedule(p)) == 80
    assert set(p["conditions"]) == {"gcc", "bwe", "fixed300", "sweep", "bounded"}
    assert all(a["video_segment"] != b["video_segment"] for a in previous["groups"] for b in p["groups"])
    assert "assets/repair3_policy.mjs" in p["extra_source_sha256"]
    assert "assets/streamed_video4.mjs" in p["extra_source_sha256"]
    assert "python/native_repair3_policy.py" in p["extra_source_sha256"]
    assert exploration_cap("gcc", 0, 0, obs(0)["features"]) == 4000000
    bad = deepcopy(p)
    bad["limits"]["inference_p99_ms"] = 15
    with pytest.raises(ValueError, match="relax"):
        validate_repair_protocol(bad)


def test_native_gcc_superiority_is_an_additional_strict_gate(tmp_path):
    from native_study_helpers import plan, rows

    from media_rl.native_repair4_statistics import analyze_native_rows
    from media_rl.native_statistics import validation_selection

    p, _, _ = plan(tmp_path, "validation")
    data = rows(p)
    extra = [
        dict(
            x,
            id=x["id"].replace("baseline", "gcc"),
            condition="gcc",
            utility=23.0,
            phases={k: dict(utility=23.0, ontime_fraction=0.8) for k in ("high", "collapse", "recovery")},
        )
        for x in data
        if x["condition"] == "baseline"
    ]
    p["conditions"]["gcc"] = dict(controller="gcc", model="source")
    report = analyze_native_rows(data + extra, p)
    assert set(report["candidate_minus_control"]) == {"baseline", "bwe", "gcc"}
    selected = validation_selection(report, p)
    assert selected["selected"] == "baseline" and "gcc:aggregate:utility" in selected["failures"]


def test_rebase_output_is_immutable_and_does_not_fit_weights(tmp_path):
    import json

    from media_rl.native_repair4_learning import rebase_repair_model

    source = tmp_path / "source.json"
    source.write_text(json.dumps(core_fixture()))
    report = rebase_repair_model(source, tmp_path / "model")
    b = json.loads((tmp_path / "model/model.json").read_text())
    assert not report["actor_risk_refitted"] and not report["labels_used"]
    assert b["q_ensemble"] == core_fixture()["q_ensemble"]
    with pytest.raises(ValueError, match="already exists"):
        rebase_repair_model("missing", tmp_path / "model")


@pytest.mark.parametrize(
    "command,flags",
    [
        ("plan", ["--source-model", "source", "--video-source", "video", "--out", "out"]),
        ("study", ["--config", "config", "--out", "out"]),
        ("audit", ["--run", "run"]),
        ("calibrate", ["--run", "run", "--out", "out"]),
        ("rebase", ["--source-model", "model", "--out", "out"]),
    ],
)
def test_five_v4_public_commands_dispatch_explicitly(command, flags, monkeypatch):
    import media_rl.native_repair4_cli as m
    from media_rl.cli import main

    seen = []
    monkeypatch.setattr(m, "run", lambda args: seen.append(args.command))
    main([f"native-repair4-{command}", *flags])
    assert seen == [f"native-repair4-{command}"]


def test_native_gcc_calibration_keeps_actor_risk_limits_and_both_use_references():
    from media_rl.native_repair4_calibration import MUTABLE, fit_selected_repair_calibration

    original = rebase_repair_bundle(core_fixture())
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
    candidate, report = fit_selected_repair_calibration(original, rows)
    assert {k: v for k, v in original.items() if k not in MUTABLE} == {
        k: v for k, v in candidate.items() if k not in MUTABLE
    }
    assert candidate["config"] == CONFIG and candidate["risk_margin"][0] == 1
    assert not report["policy_improved"] and report["learned_selected_requests"] == 0


def test_wrong_abi_and_old_selected_probability_mapping_cannot_be_rebased():
    old = core_fixture()
    old["selected_calibration"] = {"not_gcc": True}
    with pytest.raises(ValueError, match="fresh GCC"):
        rebase_repair_bundle(old)
    with pytest.raises(ValueError, match="repair4"):
        validate_repair_bundle(core_fixture())
