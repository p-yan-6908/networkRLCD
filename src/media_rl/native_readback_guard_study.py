"""Fresh, isolated readback-vs-canonical repeatability study; never promotion.

Explicit projections reuse frozen source ownership, model/calibration, labels,
raw actuation replay and statistical gates. Only a fixed fallback consumer and
its declared wire namespace change. All peers run common shadow inference.
"""

import copy
from pathlib import Path

from . import native_action_guard_study as guard
from . import native_action_live_study as live
from . import native_dense_study as dense
from . import native_presentation_study as presentation
from .native_action_policy import CONFIG, validate_bundle
from .native_protocol import asset_directory, digest, read_json, require
from .native_readback_guard import (
    CLOCK_DOMAIN,
    GUARD_ABI,
    PRESENTATION_ABI,
    WIRE_CHANNEL,
    ReadbackGuardPolicy,
    receive_readback_packet,
)
from .native_repair5_study import _close

STUDY_ABI = "native_readback_guard_repeatability_v1"
SOURCE_KIND = "recorded_video_readback_guard_v1"
PARENT_SEAL = "native_readback_guard_study_complete"
CHILD_SEAL = "native_readback_guard_episode_verified"
CONDITIONS = copy.deepcopy(guard.CONDITIONS)
RECIPE = dict(
    copy.deepcopy(guard.RECIPE),
    abi="native_readback_guard_measurement_v1",
    guard_abi=GUARD_ABI,
    guard_rule="fallback_and_(sender_hold_or_fresh120ms_readback): min(canonical_cap,actual_own_cap)",
    presentation_transport_abi=PRESENTATION_ABI,
    presentation_clock_domain=CLOCK_DOMAIN,
    presentation_usage="declared_guard_mode_only; all_peers_compute_same_hypothesis",
    canonical_feedback_semantics="original_capture_to_sender_ack_receive",
    fitted_model_unchanged=True,
    modified_fallback_safety_certified=False,
)
PROJECTION = (
    (presentation.STUDY_ABI, STUDY_ABI, 1),
    (presentation.SOURCE_KIND, SOURCE_KIND, 2),
    ("!condition||", "!condition||typeof condition.guarded!=='boolean'||", 1),
    ("'/action_live_control.mjs'", "'/readback_guard_control.mjs'", 2),
    ("'/streamed_presentation_video.mjs'", "'/streamed_readback_guard_video.mjs'", 2),
    ("'/presentation_feedback.mjs'", "'/readback_guard.mjs'", 2),
    (presentation.WIRE_CHANNEL, WIRE_CHANNEL, 3),
    ("new RepairPolicy(repairBundle);", "new RepairPolicy(repairBundle,nativeConfig.guarded);", 1),
    ("received,lastFeedbackReceived);", "received,lastFeedbackReceived,nativeConfig.guarded);", 1),
    (
        "repairActor.observe(observation,feedback_input)",
        "repairActor.observe(observation,feedback_input,presentation_feedback_input)",
        1,
    ),
    ("repair_config:REPAIR_CONFIG}", "repair_config:REPAIR_CONFIG,guarded:nativeConfig.guarded}", 1),
    ("fields_used_for_actuation:false", "fields_used_for_actuation:nativeConfig.guarded", 1),
    (
        "controller,active_model:condition.model,",
        "controller,guarded:condition.guarded,active_model:condition.model,",
        1,
    ),
    (
        "const moduleRoutes=new Set([",
        "const moduleRoutes=new Set(['/action_live_control.mjs','/action_fallback_guard.mjs','/presentation_feedback.mjs',",
        1,
    ),
)


def project_collector(text):
    for old, new, count in PROJECTION:
        require(text.count(old) == count, "frozen readback projection anchor changed: " + old)
        text = text.replace(old, new)
    return text


def extra_sources():
    return {
        **guard.extra_sources(),
        **presentation.extra_sources(),
        **{
            "python/" + n: Path(__file__).with_name(n)
            for n in (
                "native_readback_guard.py",
                "native_readback_guard_study.py",
                "native_readback_guard_cli.py",
            )
        },
        **{
            "assets/" + n: asset_directory() / n
            for n in (
                "readback_guard.mjs",
                "readback_guard_control.mjs",
                "readback_guard_episode.mjs",
                "streamed_readback_guard_video.mjs",
            )
        },
    }


def compatible_engines(p):
    a = asset_directory()
    return (
        p["source_sha256"] == live.source_identity()
        and p["extra_source_sha256"] == {k: digest(v) for k, v in extra_sources().items()}
        and p["collector_template_sha256"] == digest(a / "presentation_episode.mjs")
        and (a / "readback_guard_episode.mjs").read_text()
        == project_collector((a / "presentation_episode.mjs").read_text())
        and (a / "presentation_episode.mjs").read_text()
        == presentation.project_collector((a / "action_live_episode.mjs").read_text())
        and (a / "action_live_episode.mjs").read_text()
        == live.project_collector((a / "dense_episode.mjs").read_text())
    )


_bind = presentation._bind
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


def validate_readback_protocol(p):
    require(
        p.get("conditions") and all(type(c.get("guarded")) is bool for c in p["conditions"].values()),
        "explicit boolean guard mode required for every declared peer",
    )
    return _VALIDATE_BASE(p)


_CONTEXT["validate_live_protocol"] = validate_readback_protocol
_PLAN = _bind(
    live.plan_live_study,
    _CONTEXT,
    (('asset_directory() / "dense_episode.mjs"', 'asset_directory() / "presentation_episode.mjs"'),),
)


def plan_readback_guard_study(source_model, action_model, video_source, out, **kwargs):
    kwargs.setdefault("seed", 11101)
    return _PLAN(source_model, action_model, video_source, out, **kwargs)


_RAW_NAMESPACE = {
    **dense.audit_dense_episode.__globals__,
    "STUDY_ABI": STUDY_ABI,
    "RECIPE": RECIPE,
    "CONFIG": CONFIG,
    "RepairPolicy": ReadbackGuardPolicy,
    "validate_bundle": validate_bundle,
    "executed_learned_action": live.executed_learned_action,
    "_verify_all_models": live._verify_causal_common_models,
}
_RAW_AUDIT = _bind(
    dense.audit_dense_episode,
    _RAW_NAMESPACE,
    (
        (
            '    require(repair_bundle is None, "dense probe cannot load a learned actor")',
            "    validate_bundle(repair_bundle)",
        ),
        ('name.endswith("dense_episode.mjs")', 'name.endswith("readback_guard_episode.mjs")'),
        (
            "    policy = RepairPolicy(repair_bundle)",
            '    policy = RepairPolicy(repair_bundle, condition["guarded"])',
        ),
        (
            "            repair_config=CONFIG,",
            '            repair_config=CONFIG,\n            guarded=condition["guarded"],',
        ),
        (
            "decision = policy.observe(obs, expected_feedback)",
            'decision = policy.observe(obs, expected_feedback, row["presentation_feedback_input"])',
        ),
    ),
)
_EPISODE_BASE = _bind(
    live.audit_live_episode,
    {**_CONTEXT, "_RAW_AUDIT": _RAW_AUDIT},
    (("assets/action_live_episode.mjs", "assets/readback_guard_episode.mjs"),),
)
_GUARD_AUDIT = _bind(guard.audit_guard_episode, {**guard.__dict__, "_EPISODE_BASE": _EPISODE_BASE})


def audit_readback_sidecar(sender, frames, guarded):
    require(
        type(guarded) is bool
        and sender["presentation_feedback_protocol"]
        == dict(abi=PRESENTATION_ABI, clock_domain=CLOCK_DOMAIN, fields_used_for_actuation=guarded),
        "wrong declared acting/nonacting readback protocol",
    )
    require(
        sender["feedback_protocol"]
        == dict(channel=WIRE_CHANNEL, ordered=False, max_retransmits=0, min_send_interval_ms=100),
        "wire-only readback channel required",
    )
    events = sender["presentation_feedback_events"]
    require(len(events) == len(sender["feedback_events"]), "missing/extra transported readback events")
    reads = {
        (r.get("source_id"), r.get("presented_frames")): r
        for r in frames["observations"]
        if r.get("known_source")
    }
    born = {r["source_id"]: r["capture_request_ms"] for r in frames["sources"]}
    previous, decoded = None, []
    for event, canonical in zip(events, sender["feedback_events"], strict=True):
        packet = event["packet"]
        key = packet["source_id"], packet["presented_frames"]
        require(
            key in reads
            and packet["source_id"] in born
            and packet["readback_ms"] == reads[key]["readback_ms"],
            "transported readback must match its actual receiver callback",
        )
        accepted = receive_readback_packet(
            packet, born[packet["source_id"]], canonical["received_ms"], previous, guarded
        )
        _close(event, dict(**accepted["presentation"], packet=packet))
        _close(canonical, dict(**accepted["canonical"], presented_frames=packet["presented_frames"]))
        previous = dict(**packet, received_ms=canonical["received_ms"])
        decoded.append(accepted)
    index, steps = -1, 0
    for row in sender["decisions"]:
        now = row["observation"]["sample_ms"]
        while index + 1 < len(decoded) and decoded[index + 1]["presentation"]["received_ms"] <= now:
            index += 1
        expected = None if index < 0 else decoded[index]
        _close(row["presentation_feedback_input"], None if expected is None else expected["presentation"])
        _close(row["feedback_input"], None if expected is None else expected["canonical"])
        steps += expected is not None
    return dict(
        transported_readback_events=len(events),
        steps_with_causal_readback=steps,
        presentation_fields_used_for_actuation=guarded,
        canonical_feedback_semantics_unchanged=True,
    )


def audit_readback_guard_episode(root, p, trial, bundles, action_bundle):
    guarded = p["conditions"][trial["condition"]]["guarded"]
    sidecar = audit_readback_sidecar(
        read_json(Path(root) / "sender_observations.json"),
        read_json(Path(root) / "frame_events.json"),
        guarded,
    )
    row, derived = _GUARD_AUDIT(root, p, trial, bundles, action_bundle)
    require(
        all(
            r["repair_decision"]["modified_fallback_safety_certified"] is False
            for r in read_json(Path(root) / "sender_observations.json")["decisions"]
        ),
        "modified fallback cannot borrow canonical probabilities as certification",
    )
    row.update(sidecar)
    return row, derived


_REPORT_BASE = _bind(guard._report, {**guard.__dict__, "GUARD_ABI": GUARD_ABI})


def _report(rows, p):
    result = _REPORT_BASE(rows, p)
    require(
        all(
            r["canonical_feedback_semantics_unchanged"] is True
            and r["presentation_fields_used_for_actuation"] is p["conditions"][r["condition"]]["guarded"]
            for r in rows
        ),
        "readback/canonical semantics changed",
    )
    return dict(
        **result,
        transported_readback_events=sum(r["transported_readback_events"] for r in rows),
        steps_with_causal_readback=sum(r["steps_with_causal_readback"] for r in rows),
        canonical_feedback_semantics_unchanged=True,
        modified_fallback_safety_certified=False,
        readback_fallback_intervention_not_model_refit=True,
    )


_CONTEXT.update(audit_live_episode=audit_readback_guard_episode, _report=_report)
_RUN = _bind(live.run_live_study, _CONTEXT, (('"action_live_episode.mjs"', '"readback_guard_episode.mjs"'),))
_AUDIT = _bind(live.audit_live_study, _CONTEXT)


def run_readback_guard_study(config, out):
    return _RUN(config, out)


def audit_readback_guard_study(root):
    return _AUDIT(root)
