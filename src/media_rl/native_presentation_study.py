"""Wire-only identified-readback instrumentation. Never an action/model improvement.

Canonical four-field ACK features and caps remain exactly the old V2 mapping.
New readback data are transported causally and verified separately, not joined
from future receiver outcomes into model inputs.
"""

import copy
import inspect
from pathlib import Path
from types import FunctionType

from . import native_action_live_study as live
from . import native_dense_study as dense
from .native_action_policy import CONFIG, ActionPolicy, validate_bundle
from .native_presentation_feedback import (
    CLOCK_DOMAIN,
    PRESENTATION_ABI,
    WIRE_CHANNEL,
    receive_presentation_packet,
)
from .native_protocol import asset_directory, digest, read_json, require
from .native_repair5_study import _close

STUDY_ABI = "native_presentation_instrumentation_v1"
SOURCE_KIND = "recorded_video_presentation_instrumentation_v1"
PARENT_SEAL = "native_presentation_study_complete"
CHILD_SEAL = "native_presentation_episode_verified"
CONDITIONS = copy.deepcopy(live.CONDITIONS)
RECIPE = dict(
    copy.deepcopy(live.RECIPE),
    abi="native_presentation_measurement_v1",
    presentation_transport_abi=PRESENTATION_ABI,
    presentation_clock_domain=CLOCK_DOMAIN,
    presentation_fields_used_for_actuation=False,
    canonical_feedback_semantics="original_capture_to_sender_ack_receive",
    fitted_model_unchanged=True,
)
ONMESSAGE = "feedbackTx.onmessage=e=>{try{const p=JSON.parse(e.data),received=performance.now();if(!sourceTimes.has(p.source_id))throw Error('unknown causal source');const accepted=presentation.receivePresentationPacket(p,sourceTimes.get(p.source_id),received,lastFeedbackReceived);latestFeedback=accepted.canonical;latestPresentation=accepted.presentation;feedbackEvents.push({...latestFeedback,presented_frames:p.presented_frames});presentationFeedbackEvents.push({...accepted.presentation,packet:{...p}});lastFeedbackReceived={...p,received_ms:received};}catch{feedbackIgnored++;}};"
PROJECTION = (
    (live.STUDY_ABI, STUDY_ABI, 1),
    (live.SOURCE_KIND, SOURCE_KIND, 2),
    ("'/streamed_action_live_video.mjs'", "'/streamed_presentation_video.mjs'", 2),
    (
        "const recorded=await import(",
        "const presentation=await import('/presentation_feedback.mjs');const recorded=await import(",
        1,
    ),
    ("presentation-ack-v2", WIRE_CHANNEL, 3),
    (
        "feedbackEvents=[],feedbackSends=[]",
        "feedbackEvents=[],feedbackSends=[],presentationFeedbackEvents=[]",
        1,
    ),
    (
        "latestFeedback=null,lastFeedbackSent",
        "latestFeedback=null,latestPresentation=null,lastFeedbackSent",
        1,
    ),
    (
        "feedbackChannel.send(JSON.stringify({source_id:marker.source_id,presented_frames:meta.presentedFrames}));",
        "feedbackChannel.send(JSON.stringify(presentation.presentationPacket(marker.source_id,meta.presentedFrames,readTime)));",
        1,
    ),
    (
        "const feedback_input=latestFeedback?{...latestFeedback}:null,repairStart",
        "const feedback_input=latestFeedback?{...latestFeedback}:null,presentation_feedback_input=latestPresentation?{...latestPresentation}:null,repairStart",
        1,
    ),
    (
        "decisions.push({step_id,observation,feedback_input,",
        "decisions.push({step_id,observation,feedback_input,presentation_feedback_input,",
        1,
    ),
    (
        "feedback_events:feedbackEvents,feedback_sends:feedbackSends,",
        "feedback_events:feedbackEvents,presentation_feedback_events:presentationFeedbackEvents,presentation_feedback_protocol:{abi:presentation.PRESENTATION_ABI,clock_domain:presentation.CLOCK_DOMAIN,fields_used_for_actuation:false},feedback_sends:feedbackSends,",
        1,
    ),
    ("const moduleRoutes=new Set([", "const moduleRoutes=new Set(['/presentation_feedback.mjs',", 1),
)


def project_collector(text):
    lines = [line for line in text.splitlines() if line.startswith("feedbackTx.onmessage=")]
    require(
        len(lines) == 1 and "Object.keys(p).sort().join()!=='presented_frames,source_id'" in lines[0],
        "frozen canonical feedback receiver anchor changed",
    )
    text = text.replace(lines[0], ONMESSAGE)
    for old, new, count in PROJECTION:
        require(text.count(old) == count, "frozen presentation projection anchor changed: " + old)
        text = text.replace(old, new)
    return text


def extra_sources():
    return {
        **live.extra_sources(),
        **{
            "python/" + n: Path(__file__).with_name(n)
            for n in (
                "native_presentation_feedback.py",
                "native_presentation_study.py",
                "native_presentation_cli.py",
            )
        },
        **{
            "assets/" + n: asset_directory() / n
            for n in (
                "presentation_feedback.mjs",
                "presentation_episode.mjs",
                "streamed_presentation_video.mjs",
            )
        },
    }


def compatible_engines(p):
    a = asset_directory()
    return (
        p["source_sha256"] == live.source_identity()
        and p["extra_source_sha256"] == {k: digest(v) for k, v in extra_sources().items()}
        and p["collector_template_sha256"] == digest(a / "action_live_episode.mjs")
        and (a / "presentation_episode.mjs").read_text()
        == project_collector((a / "action_live_episode.mjs").read_text())
        and (a / "action_live_episode.mjs").read_text()
        == live.project_collector((a / "dense_episode.mjs").read_text())
    )


def _bind(fn, namespace, patches=()):
    if patches:
        text = inspect.getsource(fn)
        for old, new in patches:
            require(text.count(old) == 1, "frozen inherited instrumentation anchor changed")
            text = text.replace(old, new)
        target = dict(namespace)
        exec(compile(text, "<isolated_presentation_" + fn.__name__ + ">", "exec"), target)
        result = target[fn.__name__]
    else:
        result = FunctionType(fn.__code__, dict(namespace), fn.__name__, fn.__defaults__, fn.__closure__)
    result.__kwdefaults__ = copy.deepcopy(fn.__kwdefaults__)
    return result


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
validate_presentation_protocol = _bind(live.validate_live_protocol, _CONTEXT)
_CONTEXT["validate_live_protocol"] = validate_presentation_protocol
_PLAN = _bind(
    live.plan_live_study,
    _CONTEXT,
    (('asset_directory() / "dense_episode.mjs"', 'asset_directory() / "action_live_episode.mjs"'),),
)


def plan_presentation_study(source_model, action_model, video_source, out, **kwargs):
    kwargs.setdefault("seed", 10101)
    return _PLAN(source_model, action_model, video_source, out, **kwargs)


_RAW_CONTEXT = {
    **dense.audit_dense_episode.__globals__,
    "STUDY_ABI": STUDY_ABI,
    "RECIPE": RECIPE,
    "CONFIG": CONFIG,
    "RepairPolicy": ActionPolicy,
    "validate_bundle": validate_bundle,
    "executed_learned_action": live.executed_learned_action,
    "_verify_all_models": live._verify_causal_common_models,
}
_RAW_AUDIT = _bind(
    dense.audit_dense_episode,
    _RAW_CONTEXT,
    (
        (
            '    require(repair_bundle is None, "dense probe cannot load a learned actor")',
            "    validate_bundle(repair_bundle)",
        ),
        ('name.endswith("dense_episode.mjs")', 'name.endswith("presentation_episode.mjs")'),
    ),
)
_EPISODE_BASE = _bind(
    live.audit_live_episode,
    {**_CONTEXT, "_RAW_AUDIT": _RAW_AUDIT},
    (("assets/action_live_episode.mjs", "assets/presentation_episode.mjs"),),
)


def audit_presentation_sidecar(sender, frames):
    require(
        sender["presentation_feedback_protocol"].get("fields_used_for_actuation") is False,
        "nonacting presentation sidecar required",
    )
    require(
        sender["presentation_feedback_protocol"]
        == dict(abi=PRESENTATION_ABI, clock_domain=CLOCK_DOMAIN, fields_used_for_actuation=False),
        "presentation protocol or actuation semantics changed",
    )
    require(
        sender["feedback_protocol"]
        == dict(channel=WIRE_CHANNEL, ordered=False, max_retransmits=0, min_send_interval_ms=100),
        "declared wire-only feedback channel required",
    )
    events = sender["presentation_feedback_events"]
    require(len(events) == len(sender["feedback_events"]), "missing/extra transported readback events")
    reads = {
        (r.get("source_id"), r.get("presented_frames")): r
        for r in frames["observations"]
        if r.get("known_source")
    }
    born = {r["source_id"]: r["capture_request_ms"] for r in frames["sources"]}
    previous = None
    decoded = []
    for event, canonical in zip(events, sender["feedback_events"], strict=True):
        require(
            set(event)
            == {
                "packet",
                "abi",
                "clock_domain",
                "source_id",
                "presented_frames",
                "capture_request_ms",
                "readback_ms",
                "received_ms",
                "forward_readback_delay_ms",
                "return_ack_delay_ms",
                "capture_to_ack_received_ms",
                "fields_used_for_actuation",
            },
            "complete exact transported readback record required",
        )
        require(event["fields_used_for_actuation"] is False, "transported readback must remain nonacting")
        packet = event["packet"]
        key = packet["source_id"], packet["presented_frames"]
        require(
            key in reads
            and packet["source_id"] in born
            and packet["readback_ms"] == reads[key]["readback_ms"],
            "wire readback timestamp does not match its actual receiver callback",
        )
        accepted = receive_presentation_packet(
            packet, born[packet["source_id"]], canonical["received_ms"], previous
        )
        _close(event, dict(**accepted["presentation"], packet=packet))
        _close(canonical, dict(**accepted["canonical"], presented_frames=packet["presented_frames"]))
        previous = dict(**packet, received_ms=canonical["received_ms"])
        decoded.append(accepted)
    index = -1
    observed_steps = 0
    for row in sender["decisions"]:
        now = row["observation"]["sample_ms"]
        while index + 1 < len(decoded) and decoded[index + 1]["presentation"]["received_ms"] <= now:
            index += 1
        expected = None if index < 0 else decoded[index]
        _close(row["presentation_feedback_input"], None if expected is None else expected["presentation"])
        _close(row["feedback_input"], None if expected is None else expected["canonical"])
        if expected is not None:
            require(
                expected["presentation"]["received_ms"] <= now
                and set(row["feedback_input"])
                == {"source_id", "capture_request_ms", "received_ms", "presented_fps"},
                "future/oracle readback or extra canonical model inputs",
            )
            observed_steps += 1
    return dict(
        transported_readback_events=len(events),
        canonical_steps_with_causal_presentation=observed_steps,
        presentation_fields_used_for_actuation=False,
        canonical_feedback_semantics_unchanged=True,
    )


def audit_presentation_episode(root, p, trial, bundles, action_bundle):
    row, derived = _EPISODE_BASE(root, p, trial, bundles, action_bundle)
    row.update(
        audit_presentation_sidecar(
            read_json(Path(root) / "sender_observations.json"), read_json(Path(root) / "frame_events.json")
        )
    )
    return row, derived


def _report(rows, p):
    result = live._report(rows, p)
    require(
        all(
            r["presentation_fields_used_for_actuation"] is False
            and r["canonical_feedback_semantics_unchanged"] is True
            for r in rows
        ),
        "sidecar cannot alter fitted model or actuator semantics",
    )
    return dict(
        **result,
        transported_readback_events=sum(r["transported_readback_events"] for r in rows),
        canonical_steps_with_causal_presentation=sum(
            r["canonical_steps_with_causal_presentation"] for r in rows
        ),
        presentation_fields_used_for_actuation=False,
        canonical_feedback_semantics_unchanged=True,
        instrumentation_not_policy_improvement=True,
    )


_CONTEXT.update(audit_live_episode=audit_presentation_episode, _report=_report)
_RUN = _bind(live.run_live_study, _CONTEXT, (('"action_live_episode.mjs"', '"presentation_episode.mjs"'),))
_AUDIT = _bind(live.audit_live_study, _CONTEXT)


def run_presentation_study(config, out):
    return _RUN(config, out)


def audit_presentation_study(root):
    return _AUDIT(root)
