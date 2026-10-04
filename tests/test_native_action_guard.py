"""Synthetic SOFTWARE invariants only, never native guard efficacy."""

from copy import deepcopy
from pathlib import Path

import pytest
from test_native_action import bundle, feedback, observation, supported
from test_native_action_live import fixture as live_fixture

from media_rl import native_action_guard_study as guard
from media_rl import native_action_live_study as live
from media_rl.native_action_guard_policy import GuardPolicy
from media_rl.native_action_policy import ActionPolicy
from media_rl.native_protocol import read_json, write_json
from media_rl.native_repair5_study import _close, trial_schedule

ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    old, _ = live_fixture(tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    write_json(configs / "native_old_live.json", old)
    config = configs / "native_guard.json"
    p = guard.plan_guard_study(
        old["models"]["source"]["path"],
        old["repair_model"]["path"],
        tmp_path / "catalog.json",
        config,
        results_directory=tmp_path / "results",
    )
    return old, p, config


def test_common_canonical_and_overlay_compute_but_only_guarded_output_changes():
    b = bundle()
    before = deepcopy(b)
    original, unguarded, guarded = ActionPolicy(b), GuardPolicy(b, False), GuardPolicy(b, True)
    for now in (0, 600):
        o, fb = observation(now), feedback(now, delay=160) if now else None
        expected = original.observe(o, fb)
        a, g = unguarded.observe(o, fb), guarded.observe(o, fb)
        _close(a["canonical_decision"], expected)
        _close(g["canonical_decision"], expected)
        assert a["guard_decision"] == g["guard_decision"]
        assert a["encoder_max_bitrate_bps"] == expected["encoder_max_bitrate_bps"]
    assert g["guard_applied"] and g["encoder_max_bitrate_bps"] == 450000
    assert g["fallback"] and not g["learned_departure"] and not g["modified_fallback_neural_credit"]
    assert g["effective_action_origin"] == "fallback_growth_hold" and b == before


def test_accepted_neural_action_and_causal_ack_reset_are_unchanged():
    b = supported(bundle())
    p = GuardPolicy(b, True)
    p.observe(observation(0))
    d = p.observe(observation(600), feedback(600))
    assert (
        not d["fallback"]
        and d["encoder_max_bitrate_bps"] == d["canonical_decision"]["encoder_max_bitrate_bps"]
    )
    assert not d["guard_applied"] and d["guard_decision"]["neural_proposal_preserved"]
    p.acknowledge(d["encoder_max_bitrate_bps"], 601)
    with pytest.raises(ValueError):
        p.acknowledge(d["encoder_max_bitrate_bps"], 600)
    assert p.observe(observation(2000), feedback(2000))["history_reset"]


@pytest.mark.parametrize("mode", [None, 0, 1, "guarded"])
def test_guard_mode_is_not_truthy_untrusted_metadata(mode):
    with pytest.raises(ValueError):
        GuardPolicy(bundle(), mode)


def test_prospective_plan_has_both_variant_aliases_and_both_controls(tmp_path):
    old, p, path = fixture(tmp_path)
    assert read_json(path) == p and guard.compatible_engines(p)
    assert p["groups"][0]["video_segment"] == [100000, 120000]
    assert old["panel_abi"] == live.STUDY_ABI and p["panel_abi"] == guard.STUDY_ABI
    assert len(trial_schedule(p)) == 12 and len(p["conditions"]) == 6
    assert p["conditions"]["rlcd-a"]["guarded"] and not p["conditions"]["baseline-a"]["guarded"]
    assert p["controller_config"] == old["controller_config"] and p["limits"] == old["limits"]
    assert p["learner"] is None and not p["native_deployment_qualified"]
    with pytest.raises(ValueError, match="plan exists"):
        guard.plan_guard_study(
            p["models"]["source"]["path"], p["repair_model"]["path"], tmp_path / "catalog.json", path
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "guard-mode",
        "mode-type",
        "weights",
        "recipe",
        "risk",
        "order",
        "prior-role",
        "validation",
        "promotion",
    ],
)
def test_plan_relabel_model_mode_recipe_and_source_forgeries_reject(tmp_path, mutation):
    old, p, _ = fixture(tmp_path)
    if mutation == "guard-mode":
        p["conditions"]["baseline-a"]["guarded"] = True
    elif mutation == "mode-type":
        p["conditions"]["rlcd-a"]["guarded"] = 1
    elif mutation == "weights":
        p["repair_model"]["sha256"] = "f" * 64
    elif mutation == "recipe":
        p["measurement_recipe"]["modified_fallback_neural_credit"] = True
    elif mutation == "risk":
        p["controller_config"]["miss_budget"] = 0.2
    elif mutation == "order":
        p["groups"][0]["orders"][0].reverse()
    elif mutation == "prior-role":
        p["groups"][0]["video_segment"] = old["groups"][0]["video_segment"]
    elif mutation == "validation":
        p["stage"] = "validation"
    else:
        p["native_deployment_qualified"] = True
    with pytest.raises(ValueError):
        guard.validate_guard_protocol(p)


def test_collector_and_full_audit_bindings_are_isolated_checked_projections():
    assets = ROOT / "benchmarks/native_rtc"
    template = (assets / "action_live_episode.mjs").read_text()
    assert guard.project_collector(template) == (assets / "action_guard_episode.mjs").read_text()
    with pytest.raises(ValueError, match="anchor changed"):
        guard.project_collector(template.replace("new RepairPolicy(repairBundle);", "new UnknownPolicy();"))
    assert live._RAW_AUDIT.__globals__["RepairPolicy"] is ActionPolicy
    assert guard._RAW_AUDIT.__globals__["RepairPolicy"] is GuardPolicy
    assert guard._RAW_AUDIT.__globals__["require"] is live._RAW_AUDIT.__globals__["require"]
    assert live.CONDITIONS != guard.CONDITIONS and live.STUDY_ABI != guard.STUDY_ABI
    for old, new in guard.RAW_PROJECTION:
        assert old != new
    assert guard._RUN.__globals__ is not live.run_live_study.__globals__


def software_rows(p):
    return [
        dict(
            **t,
            utility=20.0 if t["condition"].startswith("rlcd") else 22.0,
            eligible=100,
            ontime_fraction=0.8,
            inference_p99_ms=2.0,
            learned_fraction=0.1 if p["conditions"][t["condition"]]["controller"] == "repair" else 0.0,
            actual_executed_learned_steps=10
            if p["conditions"][t["condition"]]["controller"] == "repair"
            else 0,
            decisions=100,
            phases={
                phase: dict(utility=20.0 if t["condition"].startswith("rlcd") else 22.0, ontime_fraction=0.8)
                for phase in ("high", "collapse", "recovery")
            },
            signals=dict(feedback_receipts=100),
            guarded=p["conditions"][t["condition"]]["guarded"],
            actual_held_growth_steps=40 if p["conditions"][t["condition"]]["guarded"] else 0,
            above_bwe_budget_steps=0,
            accepted_neural_proposal_changes=0,
        )
        for t in trial_schedule(p)
    ]


def test_whole_panel_reports_all_reference_phase_harms_and_both_alias_gates(tmp_path):
    _, p, _ = fixture(tmp_path)
    rows = software_rows(p)
    r = guard._report(rows, p)
    assert r["actual_held_growth_steps"] == 160 and r["actual_executed_learned_steps"] == 80
    assert r["variant_actual_use"]["guarded"]["genuine_fraction"] == 0.1
    assert r["baseline_identical_policy"]["passed"] and r["identical_policy"]["passed"]
    assert (
        not r["modified_fallback_neural_credit"]
        and not r["native_deployment_qualified"]
        and not r["native_improvement_proven"]
        and not r["SOTA_achieved"]
    )
    for c in ("baseline", "bwe", "bwe-continuous"):
        assert r["paired_descriptive_contrasts"][c]["aggregate"]["utility"]["mean"] == -2
        assert r["paired_descriptive_contrasts"][c]["aggregate"]["utility"]["ci95"] is None
        assert r["paired_descriptive_contrasts"][c]["cases"][0]["phases"]["high"]["utility"] == -2
    for bad in (rows[:-1], rows[::-1]):
        with pytest.raises(ValueError):
            guard._report(bad, p)
    row = next(r for r in rows if r["condition"] == "baseline-a")
    row["utility"] = 30
    assert not guard._report(rows, p)["baseline_identical_policy"]["passed"]


def test_failed_prefix_cannot_be_silently_replaced_or_completed(tmp_path, monkeypatch):
    _, _, config = fixture(tmp_path)
    out = tmp_path / "partial-guard"

    def fail(command, timeout, log):
        child = Path(command[2])
        child.mkdir()
        (child / "partial.txt").write_text("keep this capture")
        raise RuntimeError("synthetic capture failure")

    monkeypatch.setitem(guard._RUN.__globals__, "_collect", fail)
    monkeypatch.setitem(
        guard._RUN.__globals__,
        "_recover_cleanup_capture",
        lambda child, log: (_ for _ in ()).throw(ValueError("incomplete native outcome")),
    )
    with pytest.raises(ValueError, match="incomplete native"):
        guard.run_guard_study(config, out)
    assert read_json(out / "failure.json")["all_partial_evidence_preserved"] and list(
        out.glob("*/partial.txt")
    )
    assert not (out / "manifest.json").exists()
    with pytest.raises(FileExistsError):
        guard.run_guard_study(config, out)
    with pytest.raises(FileNotFoundError):
        guard.audit_guard_study(out)
    assert live.run_live_study.__globals__["_collect"] is not fail


@pytest.mark.parametrize(
    "command,flags",
    [
        ("plan", ["--source-model", "s", "--action-model", "a", "--video-source", "v", "--out", "o"]),
        ("study", ["--config", "c", "--out", "o"]),
        ("audit", ["--run", "r"]),
    ],
)
def test_three_public_guard_commands_dispatch(command, flags, monkeypatch):
    from media_rl import native_action_guard_cli
    from media_rl.cli import main

    calls = []
    monkeypatch.setattr(native_action_guard_cli, "run", lambda args: calls.append(args))
    main(["native-action-guard-" + command, *flags])
    assert calls[0].command == "native-action-guard-" + command


@pytest.mark.parametrize("command", ["train", "calibrate", "promote", "test"])
def test_no_qualifying_or_fitting_guard_registration(command):
    from media_rl.cli import main

    with pytest.raises(SystemExit):
        main(["native-action-guard-" + command])
