"""Whole sessions at one cap level, from a quarter of the estimate to the ceiling: a development pilot.

Not confirmatory and not part of N1 or B1. A session keeps one level for all six holds: 0.25,
0.65, 0.85 or 1.05 of the browser's estimate frozen at the start of each hold, as in N1, or the
4 Mbit/s ceiling of the cap domain. The design is in docs/NATIVE_RANGE_PILOT_V1.md, committed
before any session of record. The pilot has its own instrument and episode script; the frozen
N1, controller and B1 files are imported and called, never changed. No model is fitted and no
controller is evaluated or promoted.
"""

import argparse
import copy
import hashlib
import json
import math
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_excitation as donor
from . import native_actuator_control as control
from . import native_actuator_panel as panel
from . import native_actuator_qualification_delivery as delivery
from . import native_actuator_qualification_panel as n1
from . import native_actuator_study as physical
from .native_actuator_qualification_dynamics import capacity_at, read_relay
from .native_actuator_qualification_explore import summary
from .native_encoder_response import summarize_encoder_sidecars
from .native_protocol import (
    asset_directory,
    digest,
    finite,
    read_json,
    require,
    seal_directory,
    verify_seal,
    write_json,
)

ABI = "native_range_pilot_v1"
LEVELS = (0.25, 0.65, 0.85, 1.05, None)  # ratios of the frozen estimate; None is the ceiling
NAMES = ("0.25", "0.65", "0.85", "1.05", "ceiling")
REFERENCE = 3  # 1.05, N1's top ratio
FLOOR_BPS, CEILING_BPS = control.CAP_DOMAIN
HOLD_MS, MAX_EPOCHS = control.HOLD_MS, control.MAX_EPOCHS
SOURCES = 12  # N1's stage one: the sources it has already used
REGIMES = n1.REGIMES
STAGE = "discovery"  # the frozen video loader accepts only N1's two legacy labels, as N1 itself found
PLAN_STAGE, PEER_STAGE = ABI + "_plan", ABI + "_peer_verified"
ASSETS = ("range_control.mjs", "range_episode.mjs")
ORDER_SEED = 20261010
TIMEOUT_S = 90
ATTEMPTS = 2  # a session that fails is run once more at the end
EDGE_MS = (
    0.001  # the audit labels a request captured exactly a deadline before the cutoff; clocks tick in 0.1 ms
)
RECIPE = {
    **copy.deepcopy(physical.RECIPE),
    "abi": ABI + "_measurement",
    "instrument_abi": ABI,
    "instrument_ratios": list(LEVELS),
}
FROZEN_EPISODE = "actuator_episode.mjs"
EPISODE_CHANGES = (  # everything that separates range_episode.mjs from the frozen episode script
    (
        "// Native WebRTC through an owned instrumented UDP bottleneck; no RLCD/SOTA claim.\n",
        "// Development pilot of whole-session cap levels. This file is actuator_episode.mjs with the\n"
        "// replacements listed in media_rl.native_range_pilot.EPISODE_CHANGES and nothing else.\n"
        "// Native WebRTC through an owned instrumented UDP bottleneck; no RLCD/SOTA claim.\n",
    ),
    ("panel.panel_abi!=='native_actuator_identification_v1'", "panel.panel_abi!=='native_range_pilot_v1'"),
    (
        "condition.behavior!=='instrument'",
        "condition.behavior!=='level'||!Number.isInteger(condition.level)",
    ),
    (
        "import {InstrumentSampler,captureLink} from '/actuator_control.mjs';",
        "import {LevelSampler,captureLink} from '/range_control.mjs';",
    ),
    (
        "instrument=new InstrumentSampler(nativeConfig.exploration_seed)",
        "instrument=new LevelSampler(nativeConfig.level)",
    ),
    (
        "const moduleRoutes=new Set(['/actuator_control.mjs',",
        "const moduleRoutes=new Set(['/range_control.mjs','/actuator_control.mjs',",
    ),
    (
        "behavior:condition.behavior??null,exploration_seed:episode.exploration_seed,",
        "behavior:condition.behavior??null,level:condition.level,exploration_seed:episode.exploration_seed,",
    ),
)


def episode_source():
    """The pilot's episode script: the frozen one with ``EPISODE_CHANGES``, each applied exactly once."""
    text = (asset_directory() / FROZEN_EPISODE).read_text()
    for old, new in EPISODE_CHANGES:
        require(text.count(old) == 1, "the frozen episode script no longer has: " + old[:60])
        text = text.replace(old, new)
    return text


def requested_bps(level, bwe):
    """The cap a level asks for, given the estimate frozen at the start of the hold."""
    require(
        type(level) is int and 0 <= level < len(LEVELS) and finite(bwe) and bwe > 0,
        "pilot level and positive estimate required",
    )
    ratio = LEVELS[level]
    if ratio is None:
        return CEILING_BPS
    return max(FLOOR_BPS, min(CEILING_BPS, math.floor(ratio * bwe + 0.5)))  # JavaScript's Math.round


def replay_assignments(sender, level):
    """Recompute every hold from the recorded polls and require the record to agree.

    Returns the cap in force at each poll and one assignment per hold, as the frozen study's
    replay does for N1's instrument.
    """
    physical._meter(sender)
    current = ack = last = None
    caps, assignments = [], []
    for row in sender["decisions"]:
        now, bwe = row["observation"]["sample_ms"], row["observation"]["raw_source"]["bwe_bps"]
        require(
            finite(now) and now >= 0 and (last is None or now > last), "strictly causal pilot sample clock"
        )
        last = now
        epoch = 0 if current is None else current["epoch"] + 1
        ready = current is None or (ack is not None and now >= ack + HOLD_MS)
        if ready and epoch < MAX_EPOCHS and finite(bwe) and bwe > 0:
            ratio, requested = LEVELS[level], requested_bps(level, bwe)
            current = dict(
                abi=ABI,
                level=level,
                epoch=epoch,
                arm=level,
                ratio=ratio,
                assignment_ms=now,
                base_bwe_bps=bwe,
                requested_bps=requested,
                clipped=ratio is not None and requested != math.floor(ratio * bwe + 0.5),
            )
            ack = None
        donor.dense._close(row["actuator_assignment"], current)
        caps.append(300000 if current is None else current["requested_bps"])
        if current is not None and (not assignments or assignments[-1]["epoch"] != current["epoch"]):
            assignments.append(dict(current, ack_ms=row["ack_ms"], first_step_id=row["step_id"]))
        if current is not None:
            require(
                finite(row["ack_ms"])
                and row["ack_ms"] >= current["assignment_ms"]
                and row["actuation_readback"]["encoder_max_bitrate_bps"] == current["requested_bps"],
                "owned pilot cap acknowledgment required",
            )
            if ack is None:
                ack = row["ack_ms"]
    return caps, assignments


def audit_peer(root, runtime, trial):
    """The frozen study's raw audit of one session, with the pilot's instrument in place of N1's.

    The shared auditor replays the wire, the frames, the labels and every applied cap. Only the
    rule that says which cap was due is the pilot's.
    """
    root = Path(root)
    level = runtime["conditions"][trial["condition"]]["level"]
    sender = read_json(root / "sender_observations.json")
    caps, _ = replay_assignments(sender, level)

    def replay_cap(behavior, step, seed, features):
        require(behavior == "level", "wrong pilot replay identity")
        return caps[step]

    audit = FunctionType(
        donor.dense.audit_dense_episode.__code__,
        {
            **donor.dense.audit_dense_episode.__globals__,
            "STUDY_ABI": ABI,
            "RECIPE": RECIPE,
            "exploration_cap": replay_cap,
        },
        "audit_range_pilot_raw",
    )
    bundles = {k: donor.dense._base_bundle(e["path"]) for k, e in runtime["models"].items()}
    row, derived = audit(root, runtime, trial, bundles, None)
    require(
        digest(root / "source_snapshot.mjs") == runtime["extra_source_sha256"]["assets/range_episode.mjs"],
        "actual pilot producer changed",
    )
    frames = read_json(root / "frame_events.json")
    summarize_encoder_sidecars(sender, frames)
    cohorts = FunctionType(
        physical.build_cohorts.__code__,
        {
            **physical.build_cohorts.__globals__,
            "replay_assignments": lambda s, t: replay_assignments(s, level),
        },
        "build_range_pilot_cohorts",
    )(sender, frames, derived["quality"], trial)
    return row, derived, cohorts


def plan_from(chosen, runtimes, protocol_sha256):
    """The pilot's plan from N1's sources and their runtime panels: every schedule, every level.

    Each source and schedule reuses the clip segment and scene seed of N1's first peer there, so
    the five levels of a cell see the same content. The order of sessions is one seeded shuffle
    of all of them.
    """
    extra = {"assets/" + name: digest(asset_directory() / name) for name in ASSETS}
    require(
        (asset_directory() / ASSETS[1]).read_text() == episode_source(),
        "range_episode.mjs is not the frozen episode script with the listed changes",
    )
    conditions = {
        f"level{i}": dict(controller="explore", behavior="level", level=i, model="source")
        for i in range(len(LEVELS))
    }
    made, sessions = {}, []
    for source in chosen:
        clip = source["clip_id"]
        runtime = copy.deepcopy(runtimes["n1-" + clip])
        require(Path(runtime["video_source"]["path"]).is_file(), "N1's source video is not on this machine")
        first = {t["network_regime"]: t for t in runtime["episodes"] if t["position"] == 0}
        require(set(first) == set(REGIMES), "N1's first peer of every schedule is required")
        episodes = [
            dict(
                first[regime],
                id=f"rp-{clip}-{regime}-l{level}",
                group=f"rp-{clip}-{regime}",
                condition=f"level{level}",
                role=STAGE,
            )
            for regime in REGIMES
            for level in range(len(LEVELS))
        ]
        runtime.update(
            panel_abi=ABI,
            stage=STAGE,
            measurement_recipe=RECIPE,
            conditions=conditions,
            episodes=episodes,
            extra_source_sha256={**runtime["extra_source_sha256"], **extra},
        )
        made["rp-" + clip] = runtime
        sessions += [("rp-" + clip, e["id"]) for e in episodes]
    rng = np.random.default_rng(ORDER_SEED)
    order = [list(sessions[int(i)]) for i in rng.permutation(len(sessions))]
    return dict(
        abi=ABI + "_plan",
        development_pilot=True,
        confirmatory=False,
        n1_protocol_sha256=protocol_sha256,
        levels=list(NAMES),
        level_ratios=list(LEVELS),
        reference_level=NAMES[REFERENCE],
        sources=[s["cluster_id"] for s in chosen],
        regimes=list(REGIMES),
        order_seed=ORDER_SEED,
        order=order,
        runtimes=made,
        outcomes_observed=False,
        policy_models_fitted=0,
        learned_controller_promoted=False,
        SOTA_achieved=False,
    )


def plan(protocol_path, out):
    """Write and seal the plan for N1's stage-one sources, the ones it has already used."""
    protocol = n1.sealed_protocol(protocol_path)
    require(protocol["mock"] is False, "N1's real plan is required")
    out = Path(out)
    require(not out.exists(), "fresh plan directory required")
    chosen, _ = n1._planned(protocol, 0, SOURCES)
    made = plan_from(chosen, protocol["runtimes"], digest(protocol_path))
    out.mkdir(parents=True)
    write_json(out / "protocol.json", made)
    seal_directory(out, ["protocol.json"], PLAN_STAGE, policy_models_fitted=0, SOTA_achieved=False)
    return dict(sessions=len(made["order"]), sources=len(made["sources"]), levels=made["levels"])


def sealed_plan(path):
    verify_seal(Path(path).resolve().parent, PLAN_STAGE)
    made = read_json(path)
    require(made["abi"] == ABI + "_plan" and made["development_pilot"] is True, "pilot plan required")
    return made


def run_session(child, runtime_path, runtime, trial):
    """One native session and its audit. Leaves a sealed directory or raises."""
    command = ["node", str(asset_directory() / ASSETS[1]), str(child), str(runtime_path)]
    command += [trial["id"], trial["condition"]]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=TIMEOUT_S)
    native, derived, cohorts = audit_peer(child, runtime, trial)
    derived["panel_peer_queue"] = panel.peer_queue_realization(child)
    cohorts = panel._panel_rows(cohorts, trial, derived)
    write_json(child / "native_row.json", native)
    write_json(child / "native_derived.json", derived)
    write_json(child / "cohorts.json", cohorts)
    files = sorted(str(f.relative_to(child)) for f in child.rglob("*") if f.is_file())
    seal_directory(child, files, PEER_STAGE, policy_models_fitted=0, SOTA_achieved=False)


def _sealed(child, stage=PEER_STAGE):
    try:
        verify_seal(child, stage)
    except (OSError, ValueError, KeyError):
        return False
    return True


def capture(plan_path, out, limit=None, run=run_session, plan_reader=None, stage=PEER_STAGE):
    """Collect the planned sessions in planned order. Can be stopped and started again.

    A sealed session is never repeated. A session that fails is kept under ``failed/`` with its
    error and run once more after all the others; a second failure leaves its cell empty. No
    outcome is computed here.
    """
    made = (plan_reader or sealed_plan)(plan_path)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "protocol.json").exists():
        require(read_json(out / "protocol.json") == made, "this capture belongs to another plan")
    else:
        write_json(out / "protocol.json", made)
    (out / "failed").mkdir(exist_ok=True)
    trials = {t["id"]: t for runtime in made["runtimes"].values() for t in runtime["episodes"]}
    attempted = 0
    for _ in range(ATTEMPTS):
        for key, trial_id in made["order"]:
            child = out / trial_id
            failures = sorted((out / "failed").glob(trial_id + "-*"))
            if _sealed(child, stage) or len(failures) >= ATTEMPTS:
                continue
            if limit is not None and attempted >= limit:
                break
            attempted += 1
            runtime_path = out / (key + ".json")
            if not runtime_path.exists():
                write_json(runtime_path, made["runtimes"][key])
            try:
                require(not child.exists(), "unsealed session directory left behind")
                run(child, runtime_path, made["runtimes"][key], trials[trial_id])
            except Exception as error:  # every failure is kept, none is hidden
                kept = out / "failed" / f"{trial_id}-{len(failures) + 1}"
                if child.exists():
                    shutil.move(str(child), str(kept))
                else:
                    kept.mkdir()
                stderr = getattr(error, "stderr", None)
                (kept / "pilot_failure.json").write_text(
                    json.dumps(
                        dict(error=repr(error)[:2000], collector_stderr=(stderr or "")[-6000:]), indent=1
                    )
                    + "\n"
                )
    return status(out, stage)


def status(out, stage=PEER_STAGE):
    out = Path(out)
    made = read_json(out / "protocol.json")
    done = [trial_id for _, trial_id in made["order"] if _sealed(out / trial_id, stage)]
    failed = sorted(p.name for p in (out / "failed").iterdir()) if (out / "failed").is_dir() else []
    return dict(planned=len(made["order"]), sealed=len(done), failed_attempts=failed)


def _labels(path):
    labels = read_json(path)["quality"]["source_labels"]
    return dict(
        at=np.array([x["capture_request_ms"] for x in labels], dtype=float),
        contribution=np.array([x["ontime_sampled_psnr_contribution"] for x in labels], dtype=float),
        psnr=np.array([math.nan if x["psnr_db"] is None else x["psnr_db"] for x in labels], dtype=float),
        ontime=np.array([x["identifiable_ontime"] is True for x in labels], dtype=bool),
    )


def span_outcomes(start, labels, timing, sender, phases, packets, offset):
    """One span of a session, from ``start`` to where labels stop: the endpoint, timing and rate.

    The last labelled request can be captured exactly one deadline before the cutoff, so the
    span ends a microsecond after that instant.
    """
    stop = sender["cutoff"] - control.DEADLINE_MS + EDGE_MS
    out = delivery.window_delivery(
        dict(ack_ms=start),
        (0, stop - start),
        timing,
        dict(sender, cutoff=sender["cutoff"] + 2 * EDGE_MS),  # so that the span above is not cut short
        phases,
        packets,
        offset,
    )
    asked = (labels["at"] >= start) & (labels["at"] < stop)
    made = (sender["encoded_at"] >= start) & (sender["encoded_at"] < stop)
    timely = asked & labels["ontime"]
    steps = np.arange(start + 100, stop, 200)
    capacity = float(np.mean([capacity_at(phases, t + offset) for t in steps])) * 1e6
    rate = float(sender["encoded_bytes"][made].sum()) * 8000 / (stop - start)
    out.update(
        utility=float(labels["contribution"][asked].mean()) if asked.any() else math.nan,
        psnr_on_time_db=float(labels["psnr"][timely].mean()) if timely.any() else math.nan,
        encoder_kbps=rate / 1000,
        encoder_over_capacity=rate / capacity,
    )
    return out


def session_outcomes(root):
    """One sealed session: its level, its cell, and what it delivered over the whole session and
    from the second hold on."""
    root = Path(root)
    rows = read_json(root / "cohorts.json")
    native = read_json(root / "native_row.json")
    require(rows and len({r["arm"] for r in rows}) == 1, "one level per session")
    labels = _labels(root / "native_derived.json")
    timing = delivery.read_labels(root / "native_derived.json")
    sender = delivery.read_sender(root / "sender_observations.json")
    phases, packets = read_relay(root / "events.jsonl.gz")
    offset = phases[0][0] - sender["start"]
    acks = {r["epoch"]: float(r["ack_ms"]) for r in rows}
    spans = dict(session=span_outcomes(sender["start"], labels, timing, sender, phases, packets, offset))
    spans["after_startup"] = (
        span_outcomes(acks[1], labels, timing, sender, phases, packets, offset) if 1 in acks else None
    )
    require(
        abs(spans["session"]["utility"] - native["utility"]) < 1e-9
        and abs(spans["session"]["on_time"] - native["ontime_fraction"]) < 1e-9,
        f"{root.name}: the labels do not reproduce the audited session",
    )
    buffer = delivery.read_phases(root / "summary.json")
    later = [p["jitter_buffer_ms"] for p in buffer[1:] if math.isfinite(p["jitter_buffer_ms"])]
    return dict(
        trial_id=native["id"],
        source=native["cluster_id"],
        regime=native["network_regime"],
        level=rows[0]["arm"],
        holds=len(rows),
        clipped_holds=sum(bool(r["clipped"]) for r in rows),
        requested_kbps=[r["requested_bps"] / 1000 for r in sorted(rows, key=lambda r: r["epoch"])],
        estimate_kbps=[r["base_bwe_bps"] / 1000 for r in sorted(rows, key=lambda r: r["epoch"])],
        jitter_buffer_ms=[p["jitter_buffer_ms"] for p in buffer],
        jitter_buffer_after_startup_ms=float(np.mean(later)) if later else math.nan,
        **spans,
    )


QUANTITIES = (
    "utility",
    "on_time",
    "psnr_on_time_db",
    "never_encoded",
    "encoded_not_shown",
    "shown_late",
    "age_median_ms",
    "relay_ms",
    "rest_ms",
    "relay_dropped_share",
    "encoder_kbps",
    "encoder_over_capacity",
)


def _cells(sessions, value, where):
    """Per level: source and schedule to the value of the one session there."""
    cells = defaultdict(dict)
    for s in sessions:
        if where(s):
            v = value(s)
            if v is not None and math.isfinite(v):
                cells[s["level"]][(s["source"], s["regime"])] = v
    return cells


def _over_sources(values):
    """Mean over sources of a source's mean over its schedules, with a 95% t interval."""
    grouped = defaultdict(list)
    for (source, _), v in values.items():
        grouped[source].append(v)
    return summary([float(np.mean(v)) for _, v in sorted(grouped.items())])


def by_level(sessions, value, where=lambda s: True):
    """Per level: its mean over sources, and its difference from the reference level.

    The difference is taken within source and schedule, where both sessions exist, then averaged
    within source.
    """
    cells = _cells(sessions, value, where)
    reference = cells.get(REFERENCE, {})
    out = {}
    for level, name in enumerate(NAMES):
        own = cells.get(level, {})
        paired = {cell: own[cell] - reference[cell] for cell in own if cell in reference}
        out[name] = dict(level=_over_sources(own), minus_reference=_over_sources(paired), sessions=len(own))
    return out


def _excludes_zero(entry):
    pair = entry["interval95"]
    return pair is not None and (pair[0] > 0 or pair[1] < 0)


def _sign(entry):
    pair = entry["interval95"]
    if pair is None or not _excludes_zero(entry):
        return 0
    return 1 if pair[0] > 0 else -1


def tables(sessions, where=lambda s: True):
    """Every quantity by level for one set of sessions, over the session and from the second hold on."""
    out = {}
    for span in ("session", "after_startup"):
        out[span] = {
            name: by_level(
                sessions,
                lambda s, span=span, name=name: None if s[span] is None else s[span][name],
                where,
            )
            for name in QUANTITIES
        }
    out["after_startup"]["jitter_buffer_ms"] = by_level(
        sessions, lambda s: s["jitter_buffer_after_startup_ms"], where
    )
    out["session"]["jitter_buffer_first_phase_ms"] = by_level(
        sessions, lambda s: s["jitter_buffer_ms"][0] if s["jitter_buffer_ms"] else None, where
    )
    return out


def reading(table):
    """The statements fixed in advance, from the second hold on and against the reference level."""
    seen = table["after_startup"]
    others = [name for i, name in enumerate(NAMES) if i != REFERENCE]
    lower = [name for i, name in enumerate(NAMES) if i < REFERENCE]
    utility = {name: seen["utility"][name]["minus_reference"] for name in others}
    means = {name: seen["utility"][name]["level"]["mean"] for name in NAMES}
    top = NAMES[-1]
    worst = all(v is not None for v in means.values()) and means[top] == min(means.values())
    return dict(
        moves_on_time={
            name: bool(_excludes_zero(seen["on_time"][name]["minus_reference"])) for name in others
        },
        pays_on_the_endpoint={name: _sign(utility[name]) > 0 for name in others},
        costs_on_the_endpoint={name: _sign(utility[name]) < 0 for name in others},
        empties_the_receiver_buffer={
            name: _sign(seen["jitter_buffer_ms"][name]["minus_reference"]) < 0 for name in lower
        },
        the_ceiling_is_worst=bool(worst and _sign(utility[top]) < 0),
    )


def analyse(sessions, planned=None):
    """The report fixed in advance, from the outcomes of the sealed sessions."""
    overall = tables(sessions)
    return dict(
        abi=ABI + "_report",
        development_pilot=True,
        confirmatory=False,
        models_fitted=0,
        learned_controller_promoted=False,
        levels=list(NAMES),
        reference_level=NAMES[REFERENCE],
        planned_sessions=planned,
        sessions=len(sessions),
        sources=len({s["source"] for s in sessions}),
        sessions_by_level={name: sum(s["level"] == i for s in sessions) for i, name in enumerate(NAMES)},
        clipped_holds_by_level={
            name: [
                sum(s["clipped_holds"] for s in sessions if s["level"] == i),
                sum(s["holds"] for s in sessions if s["level"] == i),
            ]
            for i, name in enumerate(NAMES)
        },
        all_schedules=overall,
        reading=reading(overall),
        by_schedule={
            regime: (lambda t: dict(t, reading=reading(t)))(
                tables(sessions, lambda s, regime=regime: s["regime"] == regime)
            )
            for regime in REGIMES
        },
    )


def supplement(sessions):
    """Added after the report was read: three descriptions of the same sessions, from the second hold on.

    How many sources agree with each difference in utility, which level does best under each
    schedule, and where the time of the shown frames goes. None was in the design and none is a
    statement of its reading.
    """

    def utility(s):
        return None if s["after_startup"] is None else s["after_startup"]["utility"]

    cells = _cells(sessions, utility, lambda s: True)
    reference = cells.get(REFERENCE, {})
    agreement = {}
    for level, name in enumerate(NAMES):
        if level == REFERENCE:
            continue
        grouped = defaultdict(list)
        for cell, value in cells.get(level, {}).items():
            if cell in reference:
                grouped[cell[0]].append(value - reference[cell])
        means = [float(np.mean(v)) for v in grouped.values()]
        agreement[name] = dict(sources=len(means), above_reference=sum(m > 0 for m in means))
    best = {}
    for regime in REGIMES:
        means = {
            name: by_level(sessions, utility, lambda s, regime=regime: s["regime"] == regime)[name]["level"][
                "mean"
            ]
            for name in NAMES
        }
        known = {name: mean for name, mean in means.items() if mean is not None}
        best[regime] = dict(level=max(known, key=known.get) if known else None, utility_by_level=means)
    overall = {name: entry["level"]["mean"] for name, entry in by_level(sessions, utility).items()}
    known = {name: mean for name, mean in overall.items() if mean is not None}
    chosen = [b["utility_by_level"][b["level"]] for b in best.values() if b["level"] is not None]
    return dict(
        abi=ABI + "_supplement",
        development_pilot=True,
        added_after_the_report_was_read=True,
        sources_with_higher_utility_than_the_reference=agreement,
        best_level_by_schedule=best,
        utility_of_the_best_single_level=dict(
            level=max(known, key=known.get) if known else None, by_level=overall
        ),
        utility_if_each_schedule_had_its_best_level=float(np.mean(chosen)) if chosen else None,
        time_of_the_shown_frames_ms={
            name: by_level(
                sessions,
                lambda s, name=name: None if s["after_startup"] is None else s["after_startup"][name],
            )
            for name in ("encode_ms", "pacer_ms", "relay_ms", "rest_ms", "frame_wire_ms")
        },
    )


def collect(out):
    """Outcomes of every sealed session of a capture, in planned order."""
    out = Path(out)
    made = read_json(out / "protocol.json")
    return [
        session_outcomes(out / trial_id) for _, trial_id in made["order"] if _sealed(out / trial_id)
    ], made


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("plan", help="derive the pilot's plan from N1's sealed plan")
    planner.add_argument("--n1-protocol", required=True, type=Path)
    planner.add_argument("--out", required=True, type=Path)
    collector = commands.add_parser("capture", help="collect planned sessions; can be resumed")
    collector.add_argument("--protocol", required=True, type=Path)
    collector.add_argument("--out", required=True, type=Path)
    collector.add_argument("--limit", type=int, help="stop after this many attempts")
    state = commands.add_parser("status", help="sealed and failed sessions of a capture")
    state.add_argument("--capture", required=True, type=Path)
    analysis = commands.add_parser("analyse", help="the report fixed in the design")
    analysis.add_argument("--capture", required=True, type=Path)
    analysis.add_argument("--out", required=True, type=Path)
    extra = commands.add_parser("supplement", help="descriptions added after the report was read")
    extra.add_argument("--sessions", required=True, type=Path)
    extra.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "plan":
        result = plan(args.n1_protocol, args.out)
    elif args.command == "capture":
        result = capture(args.protocol, args.out, args.limit)
    elif args.command == "status":
        result = status(args.capture)
    elif args.command == "supplement":
        if args.out.exists():
            parser.exit(2, "error: fresh output file required\n")
        raw = args.sessions.read_bytes()
        result = dict(supplement(json.loads(raw)), sessions_sha256=hashlib.sha256(raw).hexdigest())
        args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    else:
        if args.out.exists():
            parser.exit(2, "error: fresh output directory required\n")
        sessions, made = collect(args.capture)
        report = analyse(sessions, planned=len(made["order"]))
        report["plan_sha256"] = digest(args.capture / "protocol.json")
        args.out.mkdir(parents=True)
        (args.out / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
        (args.out / "sessions.json").write_text(json.dumps(sessions, indent=1) + "\n")
        result = dict(sessions=report["sessions"], reading=report["reading"])
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
