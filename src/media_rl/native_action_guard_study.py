"""Fresh canonical-vs-fallback-growth-hold repeatability experiment, never promotion.

Isolated bindings reuse full frozen live planning/capture/audit code. Checked
projections only change collector identity, explicit guard-mode construction and
provenance. No old module globals, collectors, models or gates are rewritten.
"""

import copy
import inspect
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_live_study as live
from . import native_dense_study as dense
from .native_action_fallback_guard import GUARD_ABI
from .native_action_guard_policy import GuardPolicy
from .native_action_policy import CONFIG, validate_bundle
from .native_protocol import asset_directory, digest, read_json, require
from .native_repair5_statistics import analyze_native_rows, cluster_estimate
from .native_repair5_study import trial_schedule

STUDY_ABI = "native_action_guard_repeatability_v1"
SOURCE_KIND = "recorded_video_action_guard_v1"
PARENT_SEAL = "native_action_guard_study_complete"
CHILD_SEAL = "native_action_guard_episode_verified"
CONDITIONS = {
    "rlcd-a": dict(controller="repair", model="source", guarded=True),
    "rlcd-b": dict(controller="repair", model="source", guarded=True),
    "baseline-a": dict(controller="repair", model="source", guarded=False),
    "baseline-b": dict(controller="repair", model="source", guarded=False),
    "bwe": dict(controller="explore", model="source", behavior="bwe", guarded=False),
    "bwe-continuous": dict(controller="explore", model="source", behavior="bwe-continuous", guarded=False),
}
RECIPE = dict(
    copy.deepcopy(live.RECIPE),
    abi="native_action_guard_measurement_v1",
    fallback="canonical_continuous85_optional_growth_hold",
    guard_abi=GUARD_ABI,
    guard_rule="fallback_and_(sender_hold_or_fresh120ms_ack): min(canonical_cap,actual_own_cap)",
    common_guard_shadow_inference=True,
    accepted_neural_actions_unchanged=True,
    modified_fallback_neural_credit=False,
)
PROJECTION = (
    (live.STUDY_ABI, STUDY_ABI, 1),
    (live.SOURCE_KIND, SOURCE_KIND, 2),
    ("!condition||", "!condition||typeof condition.guarded!=='boolean'||", 1),
    ("'/action_live_control.mjs'", "'/action_guard_control.mjs'", 2),
    ("'/streamed_action_live_video.mjs'", "'/streamed_action_guard_video.mjs'", 2),
    ("new RepairPolicy(repairBundle);", "new RepairPolicy(repairBundle,nativeConfig.guarded);", 1),
    ("repair_config:REPAIR_CONFIG}", "repair_config:REPAIR_CONFIG,guarded:nativeConfig.guarded}", 1),
    (
        "controller,active_model:condition.model,",
        "controller,guarded:condition.guarded,active_model:condition.model,",
        1,
    ),
    (
        "const moduleRoutes=new Set([",
        "const moduleRoutes=new Set(['/action_fallback_guard.mjs','/action_live_control.mjs',",
        1,
    ),
)


def project_collector(text):
    for old, new, count in PROJECTION:
        require(text.count(old) == count, "frozen guard collector projection anchor changed")
        text = text.replace(old, new)
    return text


def extra_sources():
    return {
        **live.extra_sources(),
        **{
            "python/" + n: Path(__file__).with_name(n)
            for n in (
                "native_action_fallback_guard.py",
                "native_action_guard_policy.py",
                "native_action_guard_study.py",
                "native_action_guard_cli.py",
            )
        },
        **{
            "assets/" + n: asset_directory() / n
            for n in (
                "action_fallback_guard.mjs",
                "action_guard_control.mjs",
                "action_guard_episode.mjs",
                "streamed_action_guard_video.mjs",
            )
        },
    }


def compatible_engines(p):
    return (
        p["source_sha256"] == live.source_identity()
        and p["extra_source_sha256"] == {k: digest(v) for k, v in extra_sources().items()}
        and p["collector_template_sha256"] == digest(asset_directory() / "action_live_episode.mjs")
        and (asset_directory() / "action_guard_episode.mjs").read_text()
        == project_collector((asset_directory() / "action_live_episode.mjs").read_text())
        and (asset_directory() / "action_live_episode.mjs").read_text()
        == live.project_collector((asset_directory() / "dense_episode.mjs").read_text())
    )


def _bind(fn, namespace, patches=()):
    """Independent function globals; explicit checked source edits when necessary."""
    if patches:
        text = inspect.getsource(fn)
        for old, new in patches:
            require(text.count(old) == 1, "frozen guard inherited-code anchor changed")
            text = text.replace(old, new)
        isolated = dict(namespace)
        exec(compile(text, "<isolated_guard_" + fn.__name__ + ">", "exec"), isolated)
        bound = isolated[fn.__name__]
    else:
        bound = FunctionType(fn.__code__, dict(namespace), fn.__name__, fn.__defaults__, fn.__closure__)
    bound.__kwdefaults__ = copy.deepcopy(fn.__kwdefaults__)
    return bound


_CONTEXT = {
    **live.__dict__,
    "__file__": __file__,
    "STUDY_ABI": STUDY_ABI,
    "SOURCE_KIND": SOURCE_KIND,
    "PARENT_SEAL": PARENT_SEAL,
    "CHILD_SEAL": CHILD_SEAL,
    "CONDITIONS": CONDITIONS,
    "RECIPE": RECIPE,
    "extra_sources": extra_sources,
    "compatible_engines": compatible_engines,
}
_VALIDATE_BASE = _bind(live.validate_live_protocol, _CONTEXT)


def validate_guard_protocol(p):
    require(
        p.get("conditions") and all(type(c.get("guarded")) is bool for c in p["conditions"].values()),
        "explicit boolean guard mode required for every declared peer",
    )
    return _VALIDATE_BASE(p)


_CONTEXT["validate_live_protocol"] = validate_guard_protocol
_PLAN = _bind(
    live.plan_live_study,
    _CONTEXT,
    (('asset_directory() / "dense_episode.mjs"', 'asset_directory() / "action_live_episode.mjs"'),),
)


def plan_guard_study(source_model, action_model, video_source, out, **kwargs):
    kwargs.setdefault("seed", 9101)
    return _PLAN(source_model, action_model, video_source, out, **kwargs)


RAW_PROJECTION = (
    (
        '    require(repair_bundle is None, "dense probe cannot load a learned actor")',
        "    validate_bundle(repair_bundle)",
    ),
    ('name.endswith("dense_episode.mjs")', 'name.endswith("action_guard_episode.mjs")'),
    (
        "    policy = RepairPolicy(repair_bundle)",
        '    policy = RepairPolicy(repair_bundle, condition["guarded"])',
    ),
    (
        "            repair_config=CONFIG,",
        '            repair_config=CONFIG,\n            guarded=condition["guarded"],',
    ),
)
_RAW_NAMESPACE = {
    **dense.audit_dense_episode.__globals__,
    "STUDY_ABI": STUDY_ABI,
    "RECIPE": RECIPE,
    "CONFIG": CONFIG,
    "RepairPolicy": GuardPolicy,
    "validate_bundle": validate_bundle,
    "executed_learned_action": live.executed_learned_action,
    "_verify_all_models": live._verify_causal_common_models,
}
_RAW_AUDIT = _bind(dense.audit_dense_episode, _RAW_NAMESPACE, RAW_PROJECTION)
_EPISODE_CONTEXT = {**_CONTEXT, "_RAW_AUDIT": _RAW_AUDIT}
_EPISODE_BASE = _bind(
    live.audit_live_episode,
    _EPISODE_CONTEXT,
    (("assets/action_live_episode.mjs", "assets/action_guard_episode.mjs"),),
)


def audit_guard_episode(root, p, trial, bundles, action_bundle):
    row, derived = _EPISODE_BASE(root, p, trial, bundles, action_bundle)
    guarded = p["conditions"][trial["condition"]]["guarded"]
    active = p["conditions"][trial["condition"]]["controller"] == "repair"
    held = 0
    neural_changed = 0
    for r in read_json(Path(root) / "sender_observations.json")["decisions"]:
        d = r["repair_decision"]
        canonical = d["canonical_decision"]
        require(
            type(d["guard_enabled"]) is bool
            and d["guard_enabled"] is guarded
            and d["modified_fallback_neural_credit"] is False,
            "wrong guard mode or modified-fallback credit",
        )
        if not canonical["fallback"]:
            neural_changed += d["encoder_max_bitrate_bps"] != canonical["encoder_max_bitrate_bps"]
            require(not d["guard_applied"], "accepted neural action was modified")
        if d["guard_applied"]:
            require(
                guarded
                and canonical["fallback"]
                and d["fallback"]
                and not d["learned_departure"]
                and d["encoder_max_bitrate_bps"] < canonical["encoder_max_bitrate_bps"],
                "growth hold cannot gain neural credit or change a neural proposal",
            )
            held += (
                active and r["actuation_readback"]["encoder_max_bitrate_bps"] == d["encoder_max_bitrate_bps"]
            )
        if not guarded:
            require(
                d["encoder_max_bitrate_bps"] == canonical["encoder_max_bitrate_bps"],
                "unguarded reference mapping changed",
            )
    require(neural_changed == 0, "neural proposal changes forbidden")
    row.update(
        guarded=guarded, actual_held_growth_steps=held, accepted_neural_proposal_changes=neural_changed
    )
    return row, derived


def _report(rows, p):
    expected = trial_schedule(p)
    require(
        [{k: r[k] for k in t} for r, t in zip(rows, expected, strict=True)] == expected,
        "complete prospectively ordered guard panel required",
    )
    result = analyze_native_rows(rows, p)
    guarded = [r for r in rows if r["condition"] in ("rlcd-a", "rlcd-b")]
    baseline = [r for r in rows if r["condition"] in ("baseline-a", "baseline-b")]
    contrasts = {}
    for control in ("baseline", "bwe", "bwe-continuous"):
        cases = []
        for g in p["groups"]:
            candidate = [r for r in guarded if r["group"] == g["id"]]
            refs = [
                r
                for r in (baseline if control == "baseline" else rows)
                if r["group"] == g["id"] and (control == "baseline" or r["condition"] == control)
            ]
            cases.append(
                dict(
                    group=g["id"],
                    family=g["family"],
                    **{
                        k: float(np.mean([r[k] for r in candidate]) - np.mean([r[k] for r in refs]))
                        for k in ("utility", "ontime_fraction")
                    },
                    phases={
                        phase: {
                            k: float(
                                np.mean([r["phases"][phase][k] for r in candidate])
                                - np.mean([r["phases"][phase][k] for r in refs])
                            )
                            for k in ("utility", "ontime_fraction")
                        }
                        for phase in ("high", "collapse", "recovery")
                    },
                )
            )
        contrasts[control] = dict(
            cases=cases,
            aggregate={k: cluster_estimate([c[k] for c in cases]) for k in ("utility", "ontime_fraction")},
        )
    baseline_spreads = []
    for g in p["groups"]:
        peers = [r for r in baseline if r["group"] == g["id"]]
        baseline_spreads.append(
            dict(
                group=g["id"],
                utility_span=float(np.ptp([r["utility"] for r in peers])),
                ontime_fraction_span=float(np.ptp([r["ontime_fraction"] for r in peers])),
            )
        )
    baseline_passed = not result["tail_budget_failures"] and all(
        s["utility_span"] <= p["limits"]["repeatability_utility_span"]
        and s["ontime_fraction_span"] <= p["limits"]["repeatability_ontime_span"]
        for s in baseline_spreads
    )
    totals = {}
    for name, peers in (("guarded", guarded), ("baseline", baseline)):
        steps = sum(r["decisions"] for r in peers)
        genuine = sum(r["actual_executed_learned_steps"] for r in peers)
        totals[name] = dict(
            decisions=steps,
            genuine_learned_steps=genuine,
            genuine_fraction=genuine / steps if steps else 0,
            original_min_genuine_fraction=live.MIN_GENUINE_USE_FRACTION,
            genuine_use_gate_passed=bool(steps and genuine / steps >= live.MIN_GENUINE_USE_FRACTION),
            actual_held_growth_steps=sum(r["actual_held_growth_steps"] for r in peers),
        )
    require(
        all(r["accepted_neural_proposal_changes"] == 0 and r["above_bwe_budget_steps"] == 0 for r in rows),
        "neural/budget invariants failed",
    )
    return dict(
        **result,
        model_sha256=p["repair_model"]["sha256"],
        guard_abi=GUARD_ABI,
        actual_learned_decisions=sum(t["decisions"] for t in totals.values()),
        actual_executed_learned_steps=sum(r["actual_executed_learned_steps"] for r in rows),
        actual_held_growth_steps=sum(r["actual_held_growth_steps"] for r in rows),
        accepted_neural_proposal_changes=0,
        variant_actual_use=totals,
        baseline_identical_policy=dict(
            group_spreads=baseline_spreads, passed=baseline_passed, causal_gain_inferred=False
        ),
        paired_descriptive_contrasts=contrasts,
        modified_fallback_neural_credit=False,
        selected_calibration_still_required=True,
        independent_validation_test_still_required=True,
        native_deployment_qualified=False,
        native_improvement_proven=False,
    )


_CONTEXT.update(audit_live_episode=audit_guard_episode, _report=_report)
_RUN = _bind(live.run_live_study, _CONTEXT, (('"action_live_episode.mjs"', '"action_guard_episode.mjs"'),))
_AUDIT = _bind(live.audit_live_study, _CONTEXT)


def run_guard_study(config, out):
    return _RUN(config, out)


def audit_guard_study(root):
    return _AUDIT(root)
