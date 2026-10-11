"""A long-session development pilot: a rule that widens its margin after a drop, against fixed levels.

Not confirmatory, and not part of Native Phase N1 or B1. Sessions last a minute and capacity
changes recur, so that what a controller has seen can matter. The candidate cruises at 0.65 of
the browser's estimate, goes up to 0.85 when the presentation acknowledgements stay young, and
goes to 0.25 when they are late, where it stays for a memory that doubles with every further
drop. Fixed levels run through the same code path. The design is
docs/NATIVE_MARGIN_PILOT_V1.md, committed before any session of record. Frozen N1, controller
and B1 files are imported and called, never changed. No model is fitted and nothing is promoted.
"""

import argparse
import copy
import json
import math
import subprocess
from collections import defaultdict
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_excitation as donor
from . import native_actuator_control as control
from . import native_actuator_panel as panel
from . import native_actuator_qualification_panel as n1
from . import native_actuator_study as physical
from . import native_ladder_pilot as ladder
from . import native_range_pilot as pilot
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

ABI = "native_margin_pilot_v1"
LADDER = (0.25, 0.65, 0.85, 1.05)
SAFE, CRUISE, HIGH, START = 0, 1, 2, 3  # steps of the ladder the rule moves among, and where it starts
LOOKBACK_MS, LOW_MS, HIGH_MS, PANIC_MS, GUARD_MS = 1000, 104, 132, 159, 1000  # the controller pilot's marks
CALM_HOLDS, MEMORY_MS, MEMORY_MAX_MS = 2, 30000, 120000
FLOOR_BPS, CEILING_BPS = control.CAP_DOMAIN
HOLD_MS, MAX_EPOCHS = control.HOLD_MS, 40
ARMS = (  # name, policy; the arm's index is its number in every record
    ("margin", dict(kind="margin")),
    ("0.25", dict(kind="fixed", step=0)),
    ("0.65", dict(kind="fixed", step=1)),
    ("1.05", dict(kind="fixed", step=3)),
)
NAMES = tuple(name for name, _ in ARMS)
CANDIDATES = ("margin",)
FIXED_PAIRS = (("0.25", "1.05"), ("0.65", "1.05"), ("0.25", "0.65"))
TUNED = ("0.25", "0.65")  # the fixed levels the range pilot's leave-one-source-out choice landed on
PHASE_MS, SESSION_PHASES = 6000, 10  # a session is a minute: ten capacity phases of 6 s
CAPACITIES = {  # Mbit/s per phase, all within N1's range
    "steady-room": [4.0] * 10,
    "steady-tight": [0.85] * 10,
    "recurring-drops": [1.2, 0.35, 1.2, 1.2, 0.35, 1.2, 1.2, 0.35, 1.2, 1.2],
    "one-drop": [1.2, 0.35] + [1.2] * 8,
}


PHASE_NAMES = ["high"] * 3 + ["collapse"] * 4 + ["recovery"] * 3


def schedule(capacities):
    """A schedule in the relay's form.

    N1's page and audit require its three phase names, and every one of them in a session. Here
    they name the first three phases, the next four and the last three, and mean nothing more.
    """
    require(len(capacities) == SESSION_PHASES, "ten capacity phases a session")
    return [[capacity, name, PHASE_MS] for capacity, name in zip(capacities, PHASE_NAMES, strict=True)]


REGIMES = {name: schedule(capacities) for name, capacities in CAPACITIES.items()}
SEGMENT_MS = 64000  # of source video for a session of a minute; N1's clips are 20 s for 18.6 s
SOURCES = pilot.SOURCES
STAGE = pilot.STAGE  # the frozen video loader accepts only N1's two legacy labels
PLAN_STAGE, PEER_STAGE = ABI + "_plan", ABI + "_peer_verified"
ASSETS = ("margin_control.mjs", "margin_episode.mjs")
ORDER_SEED = 20261012
TIMEOUT_S = 180
RECIPE = {
    **copy.deepcopy(physical.RECIPE),
    "abi": ABI + "_measurement",
    "instrument_abi": ABI,
    "instrument_ratios": list(LADDER),
    "max_assignments": MAX_EPOCHS,
}
EPISODE_CHANGES = (  # everything that separates margin_episode.mjs from the frozen episode script
    (
        "// Native WebRTC through an owned instrumented UDP bottleneck; no RLCD/SOTA claim.\n",
        "// Development pilot of a rule with a remembered margin and of fixed levels, in sessions of a minute.\n"
        "// This file is actuator_episode.mjs with the replacements listed in\n"
        "// media_rl.native_margin_pilot.EPISODE_CHANGES and nothing else.\n"
        "// Native WebRTC through an owned instrumented UDP bottleneck; no RLCD/SOTA claim.\n",
    ),
    ("panel.panel_abi!=='native_actuator_identification_v1'", "panel.panel_abi!=='native_margin_pilot_v1'"),
    ("condition.behavior!=='instrument'", "condition.behavior!=='policy'||!condition.policy"),
    (
        "import {InstrumentSampler,captureLink} from '/actuator_control.mjs';",
        "import {PolicySampler,captureLink} from '/margin_control.mjs';",
    ),
    (
        "instrument=new InstrumentSampler(nativeConfig.exploration_seed)",
        "instrument=new PolicySampler(nativeConfig.policy)",
    ),
    (
        "const moduleRoutes=new Set(['/actuator_control.mjs',",
        "const moduleRoutes=new Set(['/margin_control.mjs','/actuator_control.mjs',",
    ),
    (
        "behavior:condition.behavior??null,exploration_seed:episode.exploration_seed,",
        "behavior:condition.behavior??null,policy:condition.policy,exploration_seed:episode.exploration_seed,",
    ),
    (  # the candidate reads the presentation acknowledgement the page already holds
        "await instrument.observe(observation,encoder_response,encoded_snapshot,instrument_link)",
        "await instrument.observe(observation,encoder_response,encoded_snapshot,instrument_link,"
        "latestFeedback?{...latestFeedback}:null)",
    ),
    ("episode.schedule.length!==3", "episode.schedule.length!==10"),  # ten capacity phases instead of three
)


def episode_source():
    """The pilot's episode script: the frozen one with ``EPISODE_CHANGES``, each applied exactly once."""
    text = (asset_directory() / pilot.FROZEN_EPISODE).read_text()
    for old, new in EPISODE_CHANGES:
        require(text.count(old) == 1, "the frozen episode script no longer has: " + old[:60])
        text = text.replace(old, new)
    return text


def requested_bps(step, bwe):
    require(
        type(step) is int and 0 <= step < len(LADDER) and finite(bwe) and bwe > 0,
        "ladder step and positive estimate required",
    )
    return max(FLOOR_BPS, min(CEILING_BPS, math.floor(LADDER[step] * bwe + 0.5)))  # JavaScript's Math.round


class PolicyReplay:
    """The page's sampler, poll by poll. The audit runs it over the record and requires agreement."""

    def __init__(self, policy):
        fixed = (
            policy.get("kind") == "fixed"
            and type(policy.get("step")) is int
            and 0 <= policy["step"] < len(LADDER)
        )
        require(
            (fixed or policy.get("kind") == "margin")
            and type(policy.get("arm")) is int
            and policy["arm"] >= 0,
            "pilot policy required",
        )
        self.kind, self.arm = policy["kind"], policy["arm"]
        self.step = policy["step"] if fixed else START
        self.drops, self.memory, self.last_late, self.calm = 0, MEMORY_MS, None, 0
        self.current = self.ack = self.last = self.last_source = None
        self.seen = []

    def observe(self, now, bwe, feedback):
        require(
            finite(now) and now >= 0 and (self.last is None or now > self.last),
            "strictly causal pilot sample clock",
        )
        self.last = now
        if feedback and feedback["source_id"] != self.last_source:
            self.last_source = feedback["source_id"]
            self.seen.append(
                (feedback["received_ms"], feedback["received_ms"] - feedback["capture_request_ms"])
            )
        self.seen = [f for f in self.seen if f[0] >= now - LOOKBACK_MS]
        total = 0
        for _, value in self.seen:
            total += value
        age = total / len(self.seen) if self.seen else None
        late, rule = age is not None and age >= PANIC_MS, self.kind == "margin"
        if rule and late and self.step == SAFE and self.last_late is not None:
            self.last_late = now  # lateness seen at the bottom keeps the memory running
        epoch = 0 if self.current is None else self.current["epoch"] + 1
        ready = self.current is None or (self.ack is not None and now >= self.ack + HOLD_MS)
        cut = (
            not ready
            and rule
            and self.ack is not None
            and self.step > SAFE
            and now >= self.ack + GUARD_MS
            and late
        )
        if (ready or cut) and epoch < MAX_EPOCHS and finite(bwe) and bwe > 0:
            before, decision = self.step, "start" if rule else "fixed"
            if rule and epoch > 0:
                if cut or late or age is None:
                    if before > SAFE:
                        self.drops += 1
                        self.memory = min(MEMORY_MAX_MS, MEMORY_MS * 2 ** (self.drops - 1))
                    self.step, self.last_late, self.calm = SAFE, now, 0
                    decision = "cut" if cut else "drop" if before > SAFE else "hold"
                elif before == SAFE:
                    if now - self.last_late < self.memory:
                        decision = "hold"
                    else:
                        self.step, self.calm, decision = CRUISE, 0, "return"
                elif before == START:
                    self.step, self.calm, decision = CRUISE, 0, "cruise"
                elif before == CRUISE:
                    self.calm = self.calm + 1 if age < LOW_MS else 0
                    if self.calm >= CALM_HOLDS:
                        self.step, self.calm, decision = HIGH, 0, "up"
                    else:
                        decision = "hold"
                elif age >= HIGH_MS:
                    self.step, self.calm, decision = CRUISE, 0, "down"
                else:
                    decision = "hold"
            requested = requested_bps(self.step, bwe)
            self.current = dict(
                abi=ABI,
                kind=self.kind,
                epoch=epoch,
                arm=self.arm,
                step=self.step,
                ratio=LADDER[self.step],
                decision=decision,
                feedback_age_ms=age,
                feedback_seen=len(self.seen),
                drops=self.drops,
                memory_ms=self.memory,
                last_late_ms=self.last_late,
                assignment_ms=now,
                base_bwe_bps=bwe,
                requested_bps=requested,
                clipped=requested != math.floor(LADDER[self.step] * bwe + 0.5),
            )
            self.ack = None
        return None if self.current is None else dict(self.current)

    def acknowledge(self, now, applied):
        if self.current is None:
            return
        require(
            finite(now) and now >= self.current["assignment_ms"] and applied == self.current["requested_bps"],
            "owned pilot cap acknowledgment required",
        )
        if self.ack is None:
            self.ack = now


def replay_assignments(sender, policy):
    """Recompute every change from the recorded polls and acknowledgements; the record must agree."""
    physical._meter(sender)
    sampler = PolicyReplay(policy)
    caps, assignments = [], []
    for row in sender["decisions"]:
        raw = row["observation"]
        current = sampler.observe(raw["sample_ms"], raw["raw_source"]["bwe_bps"], row["feedback_input"])
        donor.dense._close(row["actuator_assignment"], current)
        caps.append(300000 if current is None else current["requested_bps"])
        if current is not None and (not assignments or assignments[-1]["epoch"] != current["epoch"]):
            assignments.append(dict(current, ack_ms=row["ack_ms"], first_step_id=row["step_id"]))
        sampler.acknowledge(row["ack_ms"], row["actuation_readback"]["encoder_max_bitrate_bps"])
    return caps, assignments


def audit_peer(root, runtime, trial):
    """The frozen study's raw audit of one session, with the pilot's rule for which cap was due."""
    root = Path(root)
    policy = runtime["conditions"][trial["condition"]]["policy"]
    sender = read_json(root / "sender_observations.json")
    caps, _ = replay_assignments(sender, policy)

    def replay_cap(behavior, step, seed, features):
        require(behavior == "policy", "wrong pilot replay identity")
        return caps[step]

    audit = FunctionType(
        donor.dense.audit_dense_episode.__code__,
        {
            **donor.dense.audit_dense_episode.__globals__,
            "STUDY_ABI": ABI,
            "RECIPE": RECIPE,
            "exploration_cap": replay_cap,
        },
        "audit_margin_pilot_raw",
    )
    bundles = {k: donor.dense._base_bundle(e["path"]) for k, e in runtime["models"].items()}
    row, derived = audit(root, runtime, trial, bundles, None)
    require(
        digest(root / "source_snapshot.mjs") == runtime["extra_source_sha256"]["assets/" + ASSETS[1]],
        "actual pilot producer changed",
    )
    frames = read_json(root / "frame_events.json")
    summarize_encoder_sidecars(sender, frames)
    cohorts = FunctionType(
        physical.build_cohorts.__code__,
        {
            **physical.build_cohorts.__globals__,
            "replay_assignments": lambda s, t: replay_assignments(s, policy),
        },
        "build_margin_pilot_cohorts",
    )(sender, frames, derived["quality"], trial)
    return row, derived, cohorts


def segment(first, duration_ms):
    """A session's 64 s of source video: from where N1's clip begins, or ending with the source when
    that would run past it. Two of the twelve sources are that short."""
    require(duration_ms >= SEGMENT_MS, "the source is shorter than a session")
    start = first if first + SEGMENT_MS <= duration_ms else (duration_ms - SEGMENT_MS) // 1000 * 1000
    return [int(start), int(start) + SEGMENT_MS]


def plan_from(chosen, runtimes, protocol_sha256, repetitions):
    """Every arm on every source and schedule, ``repetitions`` times, in one seeded shuffle.

    A source's sessions all use the same 64 s of its video and the scene seed of N1's first peer,
    so the arms of a cell see the same content.
    """
    require(type(repetitions) is int and 1 <= repetitions <= 4, "one to four repetitions")
    extra = {"assets/" + name: digest(asset_directory() / name) for name in ASSETS}
    require(
        (asset_directory() / ASSETS[1]).read_text() == episode_source(),
        "margin_episode.mjs is not the frozen episode script with the listed changes",
    )
    conditions = {
        f"arm{i}": dict(controller="explore", behavior="policy", policy=dict(policy, arm=i), model="source")
        for i, (_, policy) in enumerate(ARMS)
    }
    made, sessions = {}, []
    for source in chosen:
        clip = source["clip_id"]
        runtime = copy.deepcopy(runtimes["n1-" + clip])
        require(Path(runtime["video_source"]["path"]).is_file(), "N1's source video is not on this machine")
        first = min((t for t in runtime["episodes"] if t["position"] == 0), key=lambda t: t["id"])
        cut = segment(first["video_segment"][0], runtime["video_source"]["duration_ms"])
        episodes = [
            dict(
                first,
                id=f"mp-{clip}-{regime}-a{arm}-r{repetition}",
                group=f"mp-{clip}-{regime}",
                family=regime,
                network_regime=regime,
                schedule=copy.deepcopy(REGIMES[regime]),
                video_segment=cut,
                condition=f"arm{arm}",
                repetition=repetition,
                role=STAGE,
            )
            for regime in REGIMES
            for arm in range(len(ARMS))
            for repetition in range(repetitions)
        ]
        runtime.update(
            panel_abi=ABI,
            stage=STAGE,
            measurement_recipe=RECIPE,
            conditions=conditions,
            episodes=episodes,
            extra_source_sha256={**runtime["extra_source_sha256"], **extra},
        )
        made["mp-" + clip] = runtime
        sessions += [("mp-" + clip, e["id"]) for e in episodes]
    rng = np.random.default_rng(ORDER_SEED)
    order = [list(sessions[int(i)]) for i in rng.permutation(len(sessions))]
    return dict(
        abi=ABI + "_plan",
        development_pilot=True,
        confirmatory=False,
        n1_protocol_sha256=protocol_sha256,
        arms=list(NAMES),
        candidates=list(CANDIDATES),
        tuned_fixed_levels=list(TUNED),
        ladder=list(LADDER),
        thresholds_ms=dict(lookback=LOOKBACK_MS, low=LOW_MS, high=HIGH_MS, panic=PANIC_MS, guard=GUARD_MS),
        memory_ms=dict(first=MEMORY_MS, most=MEMORY_MAX_MS),
        calm_holds=CALM_HOLDS,
        repetitions=repetitions,
        sources=[s["cluster_id"] for s in chosen],
        regimes=copy.deepcopy(REGIMES),
        segment_ms=SEGMENT_MS,
        order_seed=ORDER_SEED,
        order=order,
        runtimes=made,
        outcomes_observed=False,
        policy_models_fitted=0,
        learned_controller_promoted=False,
        SOTA_achieved=False,
    )


def plan(protocol_path, out, repetitions):
    """Write and seal the plan for N1's stage-one sources, the ones it has already used."""
    protocol = n1.sealed_protocol(protocol_path)
    require(protocol["mock"] is False, "N1's real plan is required")
    out = Path(out)
    require(not out.exists(), "fresh plan directory required")
    chosen, _ = n1._planned(protocol, 0, SOURCES)
    made = plan_from(chosen, protocol["runtimes"], digest(protocol_path), repetitions)
    out.mkdir(parents=True)
    write_json(out / "protocol.json", made)
    seal_directory(out, ["protocol.json"], PLAN_STAGE, policy_models_fitted=0, SOTA_achieved=False)
    return dict(sessions=len(made["order"]), sources=len(made["sources"]), arms=made["arms"])


def sealed_plan(path):
    verify_seal(Path(path).resolve().parent, PLAN_STAGE)
    made = read_json(path)
    require(made["abi"] == ABI + "_plan" and made["development_pilot"] is True, "margin pilot plan required")
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


def capture(plan_path, out, limit=None, run=run_session):
    """The range pilot's capture loop on this plan: resumable, failures kept and retried once."""
    return pilot.capture(plan_path, out, limit, run, plan_reader=sealed_plan, stage=PEER_STAGE)


def session_bins(root):
    """One sealed session in its ten stretches of 6 s from the first acknowledgement."""
    root = Path(root)
    rows = sorted(read_json(root / "cohorts.json"), key=lambda r: r["epoch"])
    labels = read_json(root / "native_derived.json")["quality"]["source_labels"]
    at = np.array([x["capture_request_ms"] for x in labels], dtype=float)
    worth = np.array([x["ontime_sampled_psnr_contribution"] for x in labels], dtype=float)
    timely = np.array([x["identifiable_ontime"] is True for x in labels], dtype=bool)
    age = np.array([math.nan if x["readback_age_ms"] is None else x["readback_age_ms"] for x in labels])
    start, bins = float(rows[0]["ack_ms"]), []
    for k in range(SESSION_PHASES):
        low, high = start + k * PHASE_MS, start + (k + 1) * PHASE_MS
        asked = (at >= low) & (at < high)
        shown = asked & np.isfinite(age)
        in_force = [r for r in rows if r["ack_ms"] <= (low + high) / 2]
        bins.append(
            dict(
                utility=float(worth[asked].mean()) if asked.any() else None,
                on_time=float(timely[asked].mean()) if asked.any() else None,
                age_median_ms=float(np.median(age[shown])) if shown.any() else None,
                ratio=in_force[-1]["ratio"] if in_force else None,
                requested_kbps=in_force[-1]["requested_bps"] / 1000 if in_force else None,
            )
        )
    return bins


def session_outcomes(root):
    """One sealed session, read as the range pilot reads its own, with what the rule did in it."""
    root = Path(root)
    seen = pilot.session_outcomes(root)
    rows = sorted(read_json(root / "cohorts.json"), key=lambda r: r["epoch"])
    native = read_json(root / "native_row.json")
    seen.update(
        arm=seen.pop("level"),
        repetition=native["repetition"],
        steps=[r["step"] for r in rows],
        decisions=[r["decision"] for r in rows],
        at_s=[(r["ack_ms"] - rows[0]["ack_ms"]) / 1000 for r in rows],
        feedback_age_ms=[r["feedback_age_ms"] for r in rows],
        drops=rows[-1]["drops"],
        bins=session_bins(root),
        phases=ladder.session_phases(root),
    )
    return seen


QUANTITIES, SPANS = ladder.QUANTITIES, ladder.SPANS  # the whole session is the span of the reading
PAIRS = (
    *((candidate, name) for candidate in CANDIDATES for name in NAMES if name not in CANDIDATES),
    *FIXED_PAIRS,
)
MOVES = ("cruise", "up", "down", "hold", "drop", "cut", "return")


def by_arm(sessions, value, where=lambda s: True):
    """Per arm its mean over sources; and the candidate minus each fixed level and the fixed levels
    against each other, within source and schedule and then averaged within source."""
    cells = ladder._cells(sessions, value, where)
    levels = {
        name: dict(level=ladder._over_sources(cells.get(arm, {})), cells=len(cells.get(arm, {})))
        for arm, name in enumerate(NAMES)
    }
    contrasts = {}
    for first, second in PAIRS:
        own, other = cells.get(NAMES.index(first), {}), cells.get(NAMES.index(second), {})
        contrasts[f"{first} minus {second}"] = ladder._over_sources(
            {c: own[c] - other[c] for c in own if c in other}
        )
    return dict(arms=levels, contrasts=contrasts)


def tables(sessions, where=lambda s: True):
    return {
        span: {
            name: by_arm(
                sessions, lambda s, span=span, name=name: None if s[span] is None else s[span][name], where
            )
            for name in QUANTITIES
        }
        for span in SPANS
    }


def reading(table):
    """The statements fixed in advance, on utility over the whole session."""
    contrasts = table["session"]["utility"]["contrasts"]
    out = {}
    for candidate in CANDIDATES:
        against = {
            name: ladder._sign(contrasts[f"{candidate} minus {name}"])
            for name in NAMES
            if name not in CANDIDATES
        }
        out[candidate] = dict(
            against_each_fixed_level=against,
            beats_the_tuned_fixed_levels=all(against[name] > 0 for name in TUNED),
            loses_to_a_tuned_fixed_level=any(against[name] < 0 for name in TUNED),
            beats_the_top_ratio=against["1.05"] > 0,
        )
    return out


def repeatability(sessions):
    """The mean absolute difference in utility between a cell's two sessions, per arm."""
    cells = defaultdict(list)
    for s in sessions:
        cells[(s["arm"], s["source"], s["regime"])].append(s["session"]["utility"])
    out = {}
    for arm, name in enumerate(NAMES):
        gaps = [abs(v[0] - v[1]) for (a, _, _), v in cells.items() if a == arm and len(v) >= 2]
        out[name] = dict(cells=len(gaps), mean_absolute_difference=float(np.mean(gaps)) if gaps else None)
    return out


def behaviour(sessions):
    """What the rule did, per schedule: its moves, where it stood, the drops it counted and its first cut."""
    out = {}
    for candidate in CANDIDATES:
        arm, block = NAMES.index(candidate), {}
        for regime in REGIMES:
            own = [s for s in sessions if s["arm"] == arm and s["regime"] == regime]
            decisions = [d for s in own for d in s["decisions"][1:]]
            steps = [step for s in own for step in s["steps"][1:]]
            first = [
                next(t for t, d in zip(s["at_s"], s["decisions"], strict=True) if d in ("cut", "drop"))
                for s in own
                if any(d in ("cut", "drop") for d in s["decisions"])
            ]
            block[regime] = dict(
                sessions=len(own),
                share_of_later_decisions={
                    d: decisions.count(d) / len(decisions) if decisions else None for d in MOVES
                },
                share_of_later_assignments_at_each_ratio={
                    f"{ratio:.2f}": (steps.count(i) / len(steps) if steps else None)
                    for i, ratio in enumerate(LADDER)
                },
                drops_per_session=float(np.mean([s["drops"] for s in own])) if own else None,
                sessions_that_went_to_the_bottom=len(first),
                first_time_at_the_bottom_s=float(np.median(first)) if first else None,
            )
        out[candidate] = block
    return out


def timeline(sessions):
    """Per arm and schedule, the mean over sources in each stretch of 6 s and each capacity phase.

    Part of the design: a description beside the reading, with no intervals.
    """

    def over_sources(arm, regime, part, k, key):
        cells = defaultdict(list)
        for s in sessions:
            if s["arm"] == arm and s["regime"] == regime and s[part][k][key] is not None:
                cells[s["source"]].append(s[part][k][key])
        values = [float(np.mean(v)) for v in cells.values()]
        return float(np.mean(values)) if values else None

    stretches = ("utility", "on_time", "age_median_ms", "ratio", "requested_kbps")
    held = ("jitter_buffer_ms", "relay_dropped", "offered_over_capacity")
    return {
        regime: {
            name: {
                **{
                    key: [over_sources(arm, regime, "bins", k, key) for k in range(SESSION_PHASES)]
                    for key in stretches
                },
                **{
                    key: [over_sources(arm, regime, "phases", k, key) for k in range(SESSION_PHASES)]
                    for key in held
                },
            }
            for arm, name in enumerate(NAMES)
        }
        for regime in REGIMES
    }


def analyse(sessions, planned=None):
    overall = tables(sessions)
    return dict(
        abi=ABI + "_report",
        development_pilot=True,
        confirmatory=False,
        models_fitted=0,
        learned_controller_promoted=False,
        arms=list(NAMES),
        candidates=list(CANDIDATES),
        tuned_fixed_levels=list(TUNED),
        planned_sessions=planned,
        sessions=len(sessions),
        sources=len({s["source"] for s in sessions}),
        sessions_by_arm={name: sum(s["arm"] == i for s in sessions) for i, name in enumerate(NAMES)},
        all_schedules=overall,
        reading=reading(overall),
        by_schedule={
            regime: (lambda t: dict(t, reading=reading(t)))(
                tables(sessions, lambda s, regime=regime: s["regime"] == regime)
            )
            for regime in REGIMES
        },
        repeatability=repeatability(sessions),
        what_the_rule_did=behaviour(sessions),
        timeline=timeline(sessions),
    )


def collect(out):
    out = Path(out)
    made = read_json(out / "protocol.json")
    sessions = [
        session_outcomes(out / trial_id)
        for _, trial_id in made["order"]
        if pilot._sealed(out / trial_id, PEER_STAGE)
    ]
    return sessions, made


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("plan", help="derive the pilot's plan from N1's sealed plan")
    planner.add_argument("--n1-protocol", required=True, type=Path)
    planner.add_argument("--repetitions", required=True, type=int)
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
    args = parser.parse_args(argv)
    if args.command == "plan":
        result = plan(args.n1_protocol, args.out, args.repetitions)
    elif args.command == "capture":
        result = capture(args.protocol, args.out, args.limit)
    elif args.command == "status":
        result = pilot.status(args.capture, PEER_STAGE)
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
