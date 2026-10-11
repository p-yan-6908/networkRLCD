"""A first rule-based candidate against tuned fixed levels: a development pilot's harness and report.

Not confirmatory and not part of N1 or B1. The candidate, the "ladder", starts a session at the
top of four ratios of the browser's estimate and, at the start of every later 3 s hold, moves by
the mean age of the presentation acknowledgements it saw in the last second: one step up when
frames arrive with time to spare, one step down when they do not, to the bottom when they are
late or absent. Fixed levels run through the same code path. The design is in
docs/NATIVE_LADDER_PILOT_V1.md, committed before any session of record. Frozen N1, controller
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
from . import native_range_pilot as pilot
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

ABI = "native_ladder_pilot_v1"
LADDER = (0.25, 0.65, 0.85, 1.05)
LOOKBACK_MS, LOW_MS, HIGH_MS, PANIC_MS = 1000, 104, 132, 159
GUARD_MS = 1000  # a fast cut waits this long after the last change, so that the acknowledgements are of it
FAST_EPOCHS = 12  # a fast ladder may change more often than once a hold
FLOOR_BPS, CEILING_BPS = control.CAP_DOMAIN
HOLD_MS, MAX_EPOCHS = control.HOLD_MS, control.MAX_EPOCHS
ARMS = (  # name, policy; the arm's index is its number in every record
    ("ladder", dict(kind="ladder", fast=False)),
    ("fast ladder", dict(kind="ladder", fast=True)),
    ("0.25", dict(kind="fixed", step=0)),
    ("0.65", dict(kind="fixed", step=1)),
    ("1.05", dict(kind="fixed", step=3)),
)
NAMES = tuple(name for name, _ in ARMS)
CANDIDATES = ("ladder", "fast ladder")
TUNED = ("0.25", "0.65")  # the fixed levels the leave-one-source-out choice of the range pilot landed on
SOURCES = pilot.SOURCES
REGIMES = pilot.REGIMES
STAGE = pilot.STAGE  # the frozen video loader accepts only N1's two legacy labels
PLAN_STAGE, PEER_STAGE = ABI + "_plan", ABI + "_peer_verified"
ASSETS = ("ladder_control.mjs", "ladder_episode.mjs")
ORDER_SEED = 20261011
TIMEOUT_S = 90
RECIPE = {
    **copy.deepcopy(physical.RECIPE),
    "abi": ABI + "_measurement",
    "instrument_abi": ABI,
    "instrument_ratios": list(LADDER),
}
EPISODE_CHANGES = (  # everything that separates ladder_episode.mjs from the frozen episode script
    (
        "// Native WebRTC through an owned instrumented UDP bottleneck; no RLCD/SOTA claim.\n",
        "// Development pilot of a rule-based candidate and fixed levels. This file is actuator_episode.mjs\n"
        "// with the replacements listed in media_rl.native_ladder_pilot.EPISODE_CHANGES and nothing else.\n"
        "// Native WebRTC through an owned instrumented UDP bottleneck; no RLCD/SOTA claim.\n",
    ),
    ("panel.panel_abi!=='native_actuator_identification_v1'", "panel.panel_abi!=='native_ladder_pilot_v1'"),
    ("condition.behavior!=='instrument'", "condition.behavior!=='policy'||!condition.policy"),
    (
        "import {InstrumentSampler,captureLink} from '/actuator_control.mjs';",
        "import {PolicySampler,captureLink} from '/ladder_control.mjs';",
    ),
    (
        "instrument=new InstrumentSampler(nativeConfig.exploration_seed)",
        "instrument=new PolicySampler(nativeConfig.policy)",
    ),
    (
        "const moduleRoutes=new Set(['/actuator_control.mjs',",
        "const moduleRoutes=new Set(['/ladder_control.mjs','/actuator_control.mjs',",
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


def next_step(step, age):
    """The rule. ``age`` is the mean age of the acknowledgements of the last second, or None."""
    if age is None or age >= PANIC_MS:
        return 0
    if age >= HIGH_MS:
        return max(0, step - 1)
    if age < LOW_MS:
        return min(len(LADDER) - 1, step + 1)
    return step


class PolicyReplay:
    """The page's sampler, poll by poll. The audit runs it over the record and requires agreement."""

    def __init__(self, policy):
        fixed = (
            policy.get("kind") == "fixed"
            and type(policy.get("step")) is int
            and 0 <= policy["step"] < len(LADDER)
        )
        ladder = policy.get("kind") == "ladder" and type(policy.get("fast")) is bool
        require(
            (fixed or ladder) and type(policy.get("arm")) is int and policy["arm"] >= 0,
            "pilot policy required",
        )
        self.kind, self.arm = policy["kind"], policy["arm"]
        self.fast = bool(ladder and policy["fast"])
        self.step = policy["step"] if fixed else len(LADDER) - 1
        self.limit = FAST_EPOCHS if self.fast else MAX_EPOCHS
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
        epoch = 0 if self.current is None else self.current["epoch"] + 1
        ready = self.current is None or (self.ack is not None and now >= self.ack + HOLD_MS)
        cut = (
            not ready
            and self.fast
            and self.ack is not None
            and self.step > 0
            and now >= self.ack + GUARD_MS
            and age is not None
            and age >= PANIC_MS
        )
        if (ready or cut) and epoch < self.limit and finite(bwe) and bwe > 0:
            before = self.step
            if self.kind == "ladder" and epoch > 0:
                self.step = 0 if cut else next_step(before, age)
            if self.kind == "fixed":
                decision = "fixed"
            elif epoch == 0:
                decision = "start"
            elif cut:
                decision = "cut"
            else:
                decision = "up" if self.step > before else "down" if self.step < before else "hold"
            requested = requested_bps(self.step, bwe)
            self.current = dict(
                abi=ABI,
                kind=self.kind,
                fast=self.fast,
                epoch=epoch,
                arm=self.arm,
                step=self.step,
                ratio=LADDER[self.step],
                decision=decision,
                feedback_age_ms=age,
                feedback_seen=len(self.seen),
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
        "audit_ladder_pilot_raw",
    )
    bundles = {k: donor.dense._base_bundle(e["path"]) for k, e in runtime["models"].items()}
    row, derived = audit(root, runtime, trial, bundles, None)
    require(
        digest(root / "source_snapshot.mjs") == runtime["extra_source_sha256"]["assets/ladder_episode.mjs"],
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
        "build_ladder_pilot_cohorts",
    )(sender, frames, derived["quality"], trial)
    return row, derived, cohorts


def plan_from(chosen, runtimes, protocol_sha256, repetitions):
    """Every arm on every source and schedule, ``repetitions`` times, in one seeded shuffle.

    A cell's sessions use the clip segment and scene seed of N1's first peer there, as in the
    range pilot, so the arms of a cell see the same content.
    """
    require(type(repetitions) is int and 1 <= repetitions <= 4, "one to four repetitions")
    extra = {"assets/" + name: digest(asset_directory() / name) for name in ASSETS}
    require(
        (asset_directory() / ASSETS[1]).read_text() == episode_source(),
        "ladder_episode.mjs is not the frozen episode script with the listed changes",
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
        first = {t["network_regime"]: t for t in runtime["episodes"] if t["position"] == 0}
        require(set(first) == set(REGIMES), "N1's first peer of every schedule is required")
        episodes = [
            dict(
                first[regime],
                id=f"lp-{clip}-{regime}-a{arm}-r{repetition}",
                group=f"lp-{clip}-{regime}",
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
        made["lp-" + clip] = runtime
        sessions += [("lp-" + clip, e["id"]) for e in episodes]
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
        repetitions=repetitions,
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
    require(made["abi"] == ABI + "_plan" and made["development_pilot"] is True, "ladder pilot plan required")
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
        feedback_age_ms=[r["feedback_age_ms"] for r in rows],
    )
    return seen


QUANTITIES = (
    "utility",
    "on_time",
    "psnr_on_time_db",
    "never_encoded",
    "shown_late",
    "age_median_ms",
    "encoder_kbps",
    "encoder_over_capacity",
)
SPANS = ("session", "after_startup")  # the whole session is the candidate's span: start-up is its own doing


def _cells(sessions, value, where):
    """Per arm: source and schedule to the mean of the value over the cell's repetitions."""
    cells = defaultdict(lambda: defaultdict(list))
    for s in sessions:
        if where(s):
            v = value(s)
            if v is not None and math.isfinite(v):
                cells[s["arm"]][(s["source"], s["regime"])].append(v)
    return {arm: {cell: float(np.mean(v)) for cell, v in own.items()} for arm, own in cells.items()}


def _over_sources(values):
    grouped = defaultdict(list)
    for (source, _), v in values.items():
        grouped[source].append(v)
    return summary([float(np.mean(v)) for _, v in sorted(grouped.items())])


def by_arm(sessions, value, where=lambda s: True):
    """Per arm its mean over sources; and each candidate minus every other arm, within source and
    schedule and then averaged within source."""
    cells = _cells(sessions, value, where)
    levels = {
        name: dict(level=_over_sources(cells.get(arm, {})), cells=len(cells.get(arm, {})))
        for arm, name in enumerate(NAMES)
    }
    contrasts = {}
    for candidate in CANDIDATES:
        own = cells.get(NAMES.index(candidate), {})
        for arm, name in enumerate(NAMES):
            if name == candidate or (name in CANDIDATES and NAMES.index(name) < NAMES.index(candidate)):
                continue  # each pair of candidates once: the later one minus the earlier
            other = cells.get(arm, {})
            if name in CANDIDATES:
                paired = {cell: other[cell] - own[cell] for cell in own if cell in other}
                contrasts[f"{name} minus {candidate}"] = _over_sources(paired)
            else:
                paired = {cell: own[cell] - other[cell] for cell in own if cell in other}
                contrasts[f"{candidate} minus {name}"] = _over_sources(paired)
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


def _sign(entry):
    pair = entry["interval95"]
    if pair is None:
        return 0
    return 1 if pair[0] > 0 else -1 if pair[1] < 0 else 0


def reading(table):
    """The statements fixed in advance, per candidate, on utility over the whole session."""
    contrasts = table["session"]["utility"]["contrasts"]
    out = {}
    for candidate in CANDIDATES:
        against = {
            name: _sign(contrasts[f"{candidate} minus {name}"]) for name in NAMES if name not in CANDIDATES
        }
        out[candidate] = dict(
            against_each_fixed_level=against,
            beats_the_tuned_fixed_levels=all(against[name] > 0 for name in TUNED),
            loses_to_a_tuned_fixed_level=any(against[name] < 0 for name in TUNED),
            beats_the_top_ratio=against["1.05"] > 0,
        )
    out["fast_minus_slow"] = _sign(contrasts[f"{CANDIDATES[1]} minus {CANDIDATES[0]}"])
    return out


def repeatability(sessions):
    """How far two sessions of the same cell lie apart: the mean absolute difference in utility
    between repetitions, per arm, over the whole session."""
    cells = defaultdict(list)
    for s in sessions:
        cells[(s["arm"], s["source"], s["regime"])].append(s["session"]["utility"])
    out = {}
    for arm, name in enumerate(NAMES):
        gaps = [abs(v[0] - v[1]) for (a, _, _), v in cells.items() if a == arm and len(v) >= 2]
        out[name] = dict(cells=len(gaps), mean_absolute_difference=float(np.mean(gaps)) if gaps else None)
    return out


def behaviour(sessions):
    """What each rule did: its changes per session and the share of each decision, per schedule."""
    out = {}
    for candidate in CANDIDATES:
        arm, block = NAMES.index(candidate), {}
        for regime in REGIMES:
            own = [s for s in sessions if s["arm"] == arm and s["regime"] == regime]
            decisions = [d for s in own for d in s["decisions"][1:]]
            steps = [step for s in own for step in s["steps"][1:]]
            block[regime] = dict(
                sessions=len(own),
                changes_per_session=(len(decisions) / len(own) if own else None),
                share_of_later_assignments_at_each_ratio={
                    f"{ratio:.2f}": (steps.count(i) / len(steps) if steps else None)
                    for i, ratio in enumerate(LADDER)
                },
                share_of_decisions={
                    d: (decisions.count(d) / len(decisions) if decisions else None)
                    for d in ("up", "hold", "down", "cut")
                },
            )
        out[candidate] = block
    return out


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
