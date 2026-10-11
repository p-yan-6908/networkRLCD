"""A receiver layer for the typed simulator, fitted on the native range pilot (synthetic modelling).

The simulator as built ranks fixed cap levels in the reverse order of the native range pilot,
and its receiver is a fixed delay. This module puts a small layer on top of it: the cap acts as
a cap, a receiver buffer rises at once and falls slowly, and frames are valued as the native
endpoint values them. Every number of the layer is fitted on the range pilot only, each to the
observable it stands for; the endpoint and the share on time are never fitted. The layer is
then tested once on the controller pilot. The design is docs/JEVBWE_TYPED_RECEIVER_V1.md,
committed before anything was fitted. Nothing here is native evidence and nothing is promoted.
"""

import argparse
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from . import native_ladder_pilot as ladder
from . import native_range_pilot as pilot
from .environment import MediaEnvironment
from .native_actuator_panel import REGIMES
from .native_protocol import digest, read_json
from .scenarios import ID_SCENARIOS
from .typed_bitrate import Link, split_seed
from .typed_bitrate_b1_forecast import load_settings, mirror, simulator
from .typed_bitrate_sustained_levels import NAMES as LEVELS
from .typed_bitrate_sustained_levels import sign, sustained

STUDY = "typed_bitrate_native_receiver_v1"
DEADLINE_MS, START_BPS, HOLD_MS = 150.0, 300_000.0, ladder.HOLD_MS
BIN_MS, BINS, PHASES = ladder.BIN_MS, ladder.BINS, ladder.PHASES
REFERENCE = "1.05"
MINIMUM = 0.5  # a simulated difference of the endpoint counts as a difference from this size on
MIN_SPREAD_MS = 5.0
FITTED = LEVELS[:-1]  # the four ratios; in the simulator the ceiling is not the browser left to itself
NEAR_MS = 2 * DEADLINE_MS  # ages and spreads are fitted on stretches within twice the deadline
BUFFER_START = (15.0, 60.0, 0.3, 10.0)  # b0 ms, gu ms, gq, tau s
BUFFER_BOUNDS = ((0.0, 0.0, 0.0, 0.5), (60.0, 300.0, 3.0, 120.0))
SPANS = ("after_startup", "session")  # the span of the verdict, and the one reported beside it
LEVEL_POLICIES = {
    **{f"{ratio:.2f}": dict(kind="fixed", step=step, arm=step) for step, ratio in enumerate(ladder.LADDER)},
    "ceiling": "ceiling",
}
ARM_POLICIES = {name: dict(policy, arm=arm) for arm, (name, policy) in enumerate(ladder.ARMS)}
PAIRS = (  # the controller pilot's ten differences
    *(
        (candidate, name)
        for candidate in ladder.CANDIDATES
        for name in ladder.NAMES
        if name not in ladder.CANDIDATES
    ),
    (ladder.CANDIDATES[1], ladder.CANDIDATES[0]),
    *ladder.FIXED_PAIRS,
)


@dataclass(frozen=True)
class Layer:
    """The fitted numbers. Rates are in kbit/s, times in ms unless named otherwise."""

    e0_bps: float  # the estimate the browser's start-up reaches by the second hold
    b0: float  # the receiver's buffer: base, per unit of rate over capacity, per ms of queue delay
    gu: float
    gq: float
    tau_s: float  # and the time constant of its fall
    c0: float  # the rest of a shown frame's age: constant, and per unit of rate over capacity
    cu: float
    s0: float  # spread of ages within a step: constant, and per ms of age
    s1: float
    return_ms: float  # from a frame's presentation to its acknowledgement at the sender
    rate_kbps: tuple  # knots of the two tables, increasing
    psnr_db: tuple
    never_encoded: tuple

    def table(self, values, kbps):
        """Linear in log rate between the knots and constant outside them."""
        return float(np.interp(math.log(max(kbps, 1e-9)), np.log(self.rate_kbps), values))


class Ceiling:
    """The range pilot's fifth level: the top of the cap domain at every hold."""

    def __init__(self):
        self.current = self.ack = None

    def observe(self, now, bwe, feedback):
        ready = self.current is None or (self.ack is not None and now >= self.ack + HOLD_MS)
        epoch = 0 if self.current is None else self.current["epoch"] + 1
        if ready and epoch < ladder.MAX_EPOCHS:
            self.current = dict(
                epoch=epoch,
                step=None,
                ratio=None,
                decision="fixed",
                feedback_age_ms=None,
                requested_bps=ladder.CEILING_BPS,
            )
            self.ack = None
        return dict(self.current)

    def acknowledge(self, now, applied):
        if self.ack is None:
            self.ack = now


def falls(buffer, target, tau_s, dt_ms):
    """The buffer one step on: at a higher target at once, towards a lower one exponentially."""
    if target >= buffer:
        return target
    return target + (buffer - target) * math.exp(-dt_ms / 1000 / tau_s)


def on_time_share(age, spread):
    """The share of normally spread ages at or under the deadline."""
    return 0.5 * (1 + math.erf((DEADLINE_MS - age) / spread / math.sqrt(2)))


def run(config, trace, policy, layer, moving=True, replay=ladder.PolicyReplay):
    """One simulated session under a policy with the layer on top: a row per step, and the assignments.

    ``policy`` is a policy of the controller pilot or "ceiling". With ``moving`` false the buffer
    is held at its base, which is the ablation of the design.
    """
    link = Link(config, ID_SCENARIOS[0], 0)
    link.env = MediaEnvironment(link.env.config, trace)
    rule = Ceiling() if policy == "ceiling" else replay(policy)  # the class that audits the native sessions
    dt, buffer, pending, seen = config.dt_ms, layer.b0, [], None
    rows, assignments = [], []
    for k in range(config.steps):
        now = k * dt
        link.sample()  # the simulator's estimator reads its telemetry once a step
        if now < HOLD_MS:  # the browser's start-up probing, which that estimator lacks
            link.bwe.budget = (START_BPS + (layer.e0_bps - START_BPS) * now / (HOLD_MS - dt)) / 1e6
        estimate = float(link.bwe.budget) * 1e6  # a plain float: the rule refuses anything else
        arrived = [a for a in pending if a["received_ms"] <= now]
        if arrived:
            seen = max(arrived, key=lambda a: a["capture_request_ms"])
            pending = [a for a in pending if a["received_ms"] > now]
        current = rule.observe(now, estimate, seen)
        rule.acknowledge(now, current["requested_bps"])
        if not assignments or assignments[-1]["epoch"] != current["epoch"]:
            assignments.append(
                dict(
                    epoch=current["epoch"],
                    at_ms=now,
                    step=current["step"],
                    ratio=current["ratio"],
                    decision=current["decision"],
                    feedback_age_ms=current["feedback_age_ms"],
                    requested_bps=current["requested_bps"],
                )
            )
        o = link.advance(min(current["requested_bps"], estimate))  # the cap is a cap
        rate, capacity = link.actual_bps, o["capacity_mbps"] * 1e6
        load = min(1.0, rate / capacity) if capacity > 0 else 1.0
        target = layer.b0 + layer.gu * load + layer.gq * o["queue_delay_ms"]
        buffer = falls(buffer, target, layer.tau_s, dt) if moving else layer.b0
        age = o["latency_ms"] + buffer + layer.c0 + layer.cu * load
        shown = (1 - o["residual_loss"]) * (1 - layer.table(layer.never_encoded, rate / 1000))
        timely = shown * on_time_share(age, max(MIN_SPREAD_MS, layer.s0 + layer.s1 * age))
        if shown >= 0.5:  # one frame a step stands for the step's frames
            pending.append(dict(source_id=k, capture_request_ms=now, received_ms=now + age + layer.return_ms))
        rows.append(
            dict(
                now=now,
                estimate=estimate,
                requested=current["requested_bps"],
                rate=rate,
                capacity=capacity,
                load=load,
                queue_delay=o["queue_delay_ms"],
                one_way=o["latency_ms"],
                buffer=buffer,
                age=age,
                shown=shown,
                on_time=timely,
                utility=timely * layer.table(layer.psnr_db, rate / 1000),
                own=math.log1p(o["bitrate_mbps"] / 0.15)  # the simulator's own valuation of the step
                * (0.82 if o["low_latency"] else 1.0)
                * (1 - o["residual_loss"])
                * (1 - o["deadline_miss"]),
            )
        )
    return dict(
        steps={key: np.array([r[key] for r in rows], dtype=float) for key in rows[0]}, assignments=assignments
    )


def weighted_median(values, weights):
    order = np.argsort(values)
    total = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(total, total[-1] / 2)]) if total[-1] > 0 else None


def _mean(values, weights=None):
    if weights is None:
        return float(values.mean()) if len(values) else None
    return float((values * weights).sum() / weights.sum()) if weights.sum() > 0 else None


def summarise(made, schedule, bin_ms=BIN_MS, stretches=BINS):
    """A simulated session as the pilots report theirs: two spans, six stretches, three capacity phases."""
    s, assignments = made["steps"], made["assignments"]
    second = assignments[1]["at_ms"] if len(assignments) > 1 else math.inf

    def span(keep):
        return dict(
            utility=_mean(s["utility"][keep]),
            on_time=_mean(s["on_time"][keep]),
            own=_mean(s["own"][keep]),
            encoder_over_capacity=_mean((s["rate"] / s["capacity"])[keep]),
            encoder_kbps=_mean(s["rate"][keep] / 1000),
        )

    bins = []
    for k in range(stretches):
        keep = (s["now"] >= k * bin_ms) & (s["now"] < (k + 1) * bin_ms)
        in_force = [a for a in assignments if a["at_ms"] <= (k + 0.5) * bin_ms]
        bins.append(
            dict(
                utility=_mean(s["utility"][keep]),
                on_time=_mean(s["on_time"][keep]),
                age_median_ms=weighted_median(s["age"][keep], s["shown"][keep]),
                delay_and_buffer_ms=weighted_median((s["one_way"] + s["buffer"])[keep], s["shown"][keep]),
                load=_mean(s["load"][keep], s["shown"][keep]),
                ratio=in_force[-1]["ratio"],
                requested_kbps=in_force[-1]["requested_bps"] / 1000,
            )
        )
    phases, start = [], 0.0
    for _, _, duration in schedule:
        keep = (s["now"] >= start) & (s["now"] < start + duration)
        phases.append(dict(jitter_buffer_ms=_mean(s["buffer"][keep], s["shown"][keep])))
        start += duration
    later = [a for a in assignments[1:]]
    return dict(
        session=span(s["now"] >= 0),
        after_startup=span(s["now"] >= second),
        bins=bins,
        phases=phases,
        estimate_hold2_bps=float(s["estimate"][s["now"] >= HOLD_MS][0]),
        decisions=[a["decision"] for a in later],
        steps=[a["step"] for a in later],
    )


def session_targets(root):
    """What one native session of the range pilot gives the fit. None of it is the endpoint's own doing."""
    root = Path(root)
    seen = ladder.session_bins(root)
    rows = sorted(read_json(root / "cohorts.json"), key=lambda r: r["epoch"])
    labels = read_json(root / "native_derived.json")["quality"]["source_labels"]
    at = np.array([x["capture_request_ms"] for x in labels], dtype=float)
    age = np.array([math.nan if x["readback_age_ms"] is None else x["readback_age_ms"] for x in labels])
    start = float(rows[0]["ack_ms"])
    for k, own in enumerate(seen["bins"]):
        shown = age[(at >= start + k * BIN_MS) & (at < start + (k + 1) * BIN_MS) & np.isfinite(age)]
        low, high = np.percentile(shown, [16, 84]) if len(shown) >= 2 else (math.nan, math.nan)
        own["spread_ms"] = float(high - low) / 2 if len(shown) >= 2 else None
    by_id = {x["source_id"]: x["readback_age_ms"] for x in labels if x["readback_age_ms"] is not None}
    returns, last = [], None
    for poll in read_json(root / "sender_observations.json")["decisions"]:
        heard = poll.get("feedback_input")
        if heard and heard["source_id"] != last and heard["source_id"] in by_id:
            returns.append(heard["received_ms"] - heard["capture_request_ms"] - by_id[heard["source_id"]])
        last = heard["source_id"] if heard else last
    return dict(
        level=LEVELS[seen["arm"]],
        regime=seen["regime"],
        source=seen["source"],
        bins=seen["bins"],
        phases=seen["phases"],
        estimate_hold2_bps=float(rows[1]["base_bwe_bps"]),
        returns_ms=returns,
    )


def targets(sessions):
    """Cells of a level and schedule as means over sources, the spread points, and the return time."""
    cells = defaultdict(list)
    for s in sessions:
        cells[(s["level"], s["regime"])].append(s)

    def over_sources(own, part, k, key):
        values = [s[part][k][key] for s in own if s[part][k][key] is not None]
        return float(np.mean(values)) if values else None

    out = {}
    for (level, regime), own in sorted(cells.items()):
        out.setdefault(level, {})[regime] = dict(
            sources=len(own),
            bins={
                key: [over_sources(own, "bins", k, key) for k in range(BINS)]
                for key in ("age_median_ms", "on_time", "utility", "requested_kbps", "spread_ms")
            },
            phases=dict(
                jitter_buffer_ms=[
                    over_sources(own, "phases", k, "jitter_buffer_ms") for k in range(len(PHASES))
                ]
            ),
            estimate_hold2_bps=float(np.mean([s["estimate_hold2_bps"] for s in own])),
        )
    spread = [
        [b["age_median_ms"], b["spread_ms"]]
        for s in sessions
        for b in s["bins"]
        if b["age_median_ms"] is not None and b["spread_ms"] is not None
    ]
    returns = [value for s in sessions for value in s["returns_ms"]]
    return dict(
        study=STUDY + "_targets",
        source="the native range pilot, development evidence",
        sessions=len(sessions),
        cells=out,
        spread_points=spread,
        return_ms=float(np.median(returns)) if returns else None,
        return_points=len(returns),
    )


def _line(x, y):
    """Ordinary least squares of y on [1, x]: intercept, slope, and the root mean square of what is left."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    (intercept, slope), *_ = np.linalg.lstsq(design, y, rcond=None)
    return float(intercept), float(slope), float(np.sqrt(np.mean((y - design @ [intercept, slope]) ** 2)))


def exact(config, settings, policies, layer, moving=True):
    """Every policy on the relay's mirror of each schedule, without path noise."""
    return {
        name: {
            regime: summarise(
                run(config, mirror(schedule, config, settings["relay"]), policy, layer, moving), schedule
            )
            for regime, schedule in REGIMES.items()
        }
        for name, policy in policies.items()
    }


def over_schedules(made, span, quantity):
    """Per policy the mean over the four schedules, weighted equally as in the pilots."""
    return {name: float(np.mean([own[r][span][quantity] for r in REGIMES])) for name, own in made.items()}


def fit(seen, native, config, settings):
    """The six stages of the design as revised, on the range pilot only, and how the layer sits on it.

    Stages 1, 3 and 4 use the four ratio levels; stage 3 fits the buffer in logarithms; stages 4
    and 5 use stretches whose native median age is within twice the deadline.
    """
    cells = seen["cells"]
    if set(cells) != set(LEVELS) or any(set(own) != set(REGIMES) for own in cells.values()):
        raise ValueError("targets for every level and schedule of the range pilot are required")
    e0 = float(
        np.mean([cells[level][regime]["estimate_hold2_bps"] for level in FITTED for regime in REGIMES])
    )
    later = native["all_schedules"]["after_startup"]
    tables = {
        key: tuple(float(later[key][level]["level"]["mean"]) for level in LEVELS)
        for key in ("encoder_kbps", "psnr_on_time_db", "never_encoded")
    }
    if any(b <= a for a, b in zip(tables["encoder_kbps"], tables["encoder_kbps"][1:], strict=False)):
        raise ValueError("the encoder rate must rise with the level for the tables")

    def layer(b0, gu, gq, tau, c0=0.0, cu=0.0, s0=MIN_SPREAD_MS, s1=0.0):
        return Layer(
            e0, b0, gu, gq, tau, c0, cu, s0, s1, float(seen["return_ms"]),
            tables["encoder_kbps"], tables["psnr_on_time_db"], tables["never_encoded"],
        )  # fmt: skip

    # What a fixed level sends does not depend on the receiver, so one run a cell serves stage 3.
    drafts = {
        (level, regime): run(config, mirror(schedule, config, settings["relay"]), LEVEL_POLICIES[level], layer(*BUFFER_START))["steps"]
        for level in FITTED
        for regime, schedule in REGIMES.items()
    }  # fmt: skip
    edges = {regime: np.cumsum([0.0] + [ms for _, _, ms in schedule]) for regime, schedule in REGIMES.items()}
    wanted = [
        (level, regime, k, cells[level][regime]["phases"]["jitter_buffer_ms"][k])
        for level in FITTED
        for regime in REGIMES
        for k in range(len(PHASES))
        if cells[level][regime]["phases"]["jitter_buffer_ms"][k] is not None
    ]

    def buffers(steps, b0, gu, gq, tau):
        out, buffer = [], b0
        for load, queue in zip(steps["load"], steps["queue_delay"], strict=True):
            buffer = falls(buffer, b0 + gu * load + gq * queue, tau, config.dt_ms)
            out.append(buffer)
        return np.array(out)

    def held(x):
        """The simulated buffer of each wanted cell and phase, over the frames shown."""
        made = {key: buffers(steps, *x) for key, steps in drafts.items()}
        out = []
        for level, regime, k, _ in wanted:
            steps, low, high = drafts[(level, regime)], edges[regime][k], edges[regime][k + 1]
            keep = (steps["now"] >= low) & (steps["now"] < high)
            mine = _mean(made[(level, regime)][keep], steps["shown"][keep])
            out.append(made[(level, regime)][keep].mean() if mine is None else mine)
        return np.array(out)

    measured = np.array([value for *_, value in wanted])
    solved = least_squares(
        lambda x: np.log(np.maximum(held(x), 1e-3)) - np.log(measured), BUFFER_START, bounds=BUFFER_BOUNDS
    )
    b0, gu, gq, tau = (float(v) for v in solved.x)
    made = exact(config, settings, {level: LEVEL_POLICIES[level] for level in FITTED}, layer(b0, gu, gq, tau))
    ages = [
        (own["load"], cells[level][regime]["bins"]["age_median_ms"][k] - own["delay_and_buffer_ms"])
        for level in FITTED
        for regime in REGIMES
        for k, own in enumerate(made[level][regime]["bins"])
        if own["delay_and_buffer_ms"] is not None
        and cells[level][regime]["bins"]["age_median_ms"][k] is not None
        and cells[level][regime]["bins"]["age_median_ms"][k] <= NEAR_MS
    ]
    c0, cu, age_rms = _line(*zip(*ages, strict=True))
    near = [point for point in seen["spread_points"] if point[0] <= NEAR_MS]
    s0, s1, spread_rms = _line(*zip(*near, strict=True))
    fitted = layer(b0, gu, gq, tau, c0, cu, s0, s1)
    stages = dict(
        buffer=dict(
            cells=len(wanted),
            rms_log=float(np.sqrt(np.mean(solved.fun**2))),
            rms_ms=float(np.sqrt(np.mean((held(solved.x) - measured) ** 2))),
            at_a_bound=[
                bool(math.isclose(v, low) or math.isclose(v, high))
                for v, low, high in zip(solved.x, *BUFFER_BOUNDS, strict=True)
            ],
        ),
        age=dict(cells=len(ages), rms_ms=age_rms),
        spread=dict(points=len(near), rms_ms=spread_rms),
        return_time=dict(points=seen["return_points"]),
    )
    return fitted, stages, in_sample(exact(config, settings, LEVEL_POLICIES, fitted), cells, native)


def in_sample(made, cells, native):
    """The fitted layer beside the range pilot: what it was fitted to, and what it was not."""
    span = SPANS[0]

    def judged(own, theirs):
        out = {}
        for level in LEVELS:
            if level == REFERENCE:
                continue
            difference = own[level] - own[REFERENCE]
            mine = 0 if abs(difference) < MINIMUM else 1 if difference > 0 else -1
            other = sign(theirs[level]["minus_reference"])
            verdict = "unclear" if 0 in (mine, other) else "agrees" if mine == other else "disagrees"
            out[level] = dict(
                simulated=difference, native=theirs[level]["minus_reference"]["mean"], verdict=verdict
            )
        best = max(own, key=own.get), max(theirs, key=lambda n: theirs[n]["level"]["mean"])
        return dict(differences_from_the_reference=out, best_level=dict(simulator=best[0], native=best[1]))

    blocks = dict(
        all_schedules=judged(over_schedules(made, span, "utility"), native["all_schedules"][span]["utility"])
    )
    blocks["by_schedule"] = {
        regime: judged(
            {level: made[level][regime][span]["utility"] for level in LEVELS}, native["by_schedule"][regime][span]["utility"]
        )
        for regime in REGIMES
    }  # fmt: skip
    verdicts = [
        entry["verdict"]
        for block in (blocks["all_schedules"], *blocks["by_schedule"].values())
        for entry in block["differences_from_the_reference"].values()
    ]
    levels = {
        quantity: {
            level: dict(
                simulated=over_schedules(made, span, quantity)[level],
                native=native["all_schedules"][span][quantity][level]["level"]["mean"],
                by_schedule={
                    regime: dict(
                        simulated=made[level][regime][span][quantity],
                        native=native["by_schedule"][regime][span][quantity][level]["level"]["mean"],
                    )
                    for regime in REGIMES
                },
            )
            for level in LEVELS
        }
        for quantity in ("utility", "on_time", "encoder_over_capacity")
    }
    return dict(
        span=span,
        levels=levels,
        comparison=blocks,
        comparisons={v: verdicts.count(v) for v in ("agrees", "disagrees", "unclear")},
        schedules_with_the_same_best_level=sum(
            b["best_level"]["simulator"] == b["best_level"]["native"] for b in blocks["by_schedule"].values()
        ),
        fitted_cells=dict(
            jitter_buffer_ms={
                level: {
                    regime: dict(
                        simulated=[p["jitter_buffer_ms"] for p in made[level][regime]["phases"]],
                        native=cells[level][regime]["phases"]["jitter_buffer_ms"],
                    )
                    for regime in REGIMES
                }
                for level in LEVELS
            }
        ),
    )


def judge(simulated, entry):
    """One simulated difference against a native one, by the rule of the design."""
    established = sign(entry)
    mine = 0 if abs(simulated) < MINIMUM else 1 if simulated > 0 else -1
    if established == 0:
        verdict = "not established"
    else:
        verdict = "agrees" if mine == established else "flat" if mine == 0 else "disagrees"
    return dict(
        simulated=simulated, native=entry["mean"], native_interval95=entry["interval95"], verdict=verdict
    )


def decide(everywhere, by_schedule, rule_pairs=None):
    """The verdict fixed in the design, from the judged differences over all schedules and under each."""
    established = [e for e in everywhere.values() if e["verdict"] != "not established"]
    order = bool(established) and all(e["verdict"] == "agrees" for e in established)
    local = [e for block in by_schedule.values() for e in block.values() if e["verdict"] != "not established"]
    share = sum(e["verdict"] == "agrees" for e in local) / len(local) if local else None
    reversed_rule = [
        f"{regime}: {pair}"
        for regime, block in by_schedule.items()
        for pair, e in block.items()
        if e["verdict"] == "disagrees" and pair in (RULE_AGAINST_TUNED if rule_pairs is None else rule_pairs)
    ]
    schedules = share is not None and share >= 0.8 and not reversed_rule
    if not order:
        verdict = "the layer does not predict the controller pilot"
    elif schedules:
        verdict = "the layer predicts the controller pilot"
    else:
        verdict = "the layer predicts the order only"
    return dict(
        verdict=verdict,
        established_over_all_schedules=len(established),
        agreeing_over_all_schedules=sum(e["verdict"] == "agrees" for e in established),
        established_under_the_schedules=len(local),
        share_agreeing_under_the_schedules=share,
        rule_against_tuned_level_reversed=reversed_rule,
    )


RULE_AGAINST_TUNED = tuple(
    f"{candidate} minus {name}" for candidate in ladder.CANDIDATES for name in ladder.TUNED
)


def differences(made, span, native):
    """The ten differences of the endpoint, over all schedules and under each, judged against the pilot."""
    everywhere = over_schedules(made, span, "utility")
    return (
        {
            f"{a} minus {b}": judge(
                everywhere[a] - everywhere[b], native["all_schedules"][span]["utility"]["contrasts"][f"{a} minus {b}"]
            )
            for a, b in PAIRS
        },
        {
            regime: {
                f"{a} minus {b}": judge(
                    made[a][regime][span]["utility"] - made[b][regime][span]["utility"],
                    native["by_schedule"][regime][span]["utility"]["contrasts"][f"{a} minus {b}"],
                )
                for a, b in PAIRS
            }
            for regime in REGIMES
        },
    )  # fmt: skip


def behaviour(made):
    """What each rule did in the simulator: the share of each later decision and of each ratio."""
    out = {}
    for name in ladder.CANDIDATES:
        out[name] = {}
        for regime in REGIMES:
            decisions, steps = made[name][regime]["decisions"], made[name][regime]["steps"]
            out[name][regime] = dict(
                share_of_decisions={
                    d: decisions.count(d) / len(decisions) for d in ("up", "hold", "down", "cut")
                },
                share_of_later_assignments_at_each_ratio={
                    f"{ratio:.2f}": steps.count(i) / len(steps) for i, ratio in enumerate(ladder.LADDER)
                },
            )
    return out


def test(layer, native, config, settings):
    """The controller pilot's five arms in the simulator with the fitted layer, judged as the design says."""
    made = exact(config, settings, ARM_POLICIES, layer)
    report = dict(spans={})
    for span in SPANS:
        everywhere, by_schedule = differences(made, span, native)
        levels = {}
        for quantity in ("utility", "on_time"):
            simulated = over_schedules(made, span, quantity)
            levels[quantity] = {
                name: dict(
                    simulated=simulated[name],
                    native=native["all_schedules"][span][quantity]["arms"][name]["level"]["mean"],
                    native_interval95=native["all_schedules"][span][quantity]["arms"][name]["level"][
                        "interval95"
                    ],
                    by_schedule={
                        regime: dict(
                            simulated=made[name][regime][span][quantity],
                            native=native["by_schedule"][regime][span][quantity]["arms"][name]["level"][
                                "mean"
                            ],
                        )
                        for regime in REGIMES
                    },
                )
                for name in ladder.NAMES
            }
        inside = sum(
            e["native_interval95"][0] <= e["simulated"] <= e["native_interval95"][1]
            for e in levels["utility"].values()
        )
        report["spans"][span] = dict(
            levels=levels,
            endpoints_inside_the_native_interval=inside,
            differences_over_all_schedules=everywhere,
            differences_under_each_schedule=by_schedule,
            **decide(everywhere, by_schedule),
        )
    report["verdict"] = report["spans"][SPANS[0]][
        "verdict"
    ]  # the whole session is beside it, not the verdict
    report["what_the_rules_did"] = behaviour(made)
    report["timeline"] = {
        name: {
            regime: {
                key: [b[key] for b in made[name][regime]["bins"]]
                for key in ("utility", "on_time", "age_median_ms", "ratio", "requested_kbps")
            }
            | dict(jitter_buffer_ms=[p["jitter_buffer_ms"] for p in made[name][regime]["phases"]])
            for regime in REGIMES
        }
        for name in ladder.NAMES
    }
    report["ablations"] = ablations(layer, native, config, settings)
    report["robustness"] = robustness(layer, native, config, settings)
    return report


def ablations(layer, native, config, settings):
    """What the buffer itself adds: the layer with the buffer held at its base, and the simulator as built.

    As built the simulator has no receiver whose ages a rule could act on, so only the fixed arms
    run there, held at the hold's request and scored with its own utility from the second hold on.
    """
    span = SPANS[0]
    held = exact(config, settings, ARM_POLICIES, layer, moving=False)
    everywhere, by_schedule = differences(held, span, native)
    fixed = [name for name in ladder.NAMES if name not in ladder.CANDIDATES]
    built = {
        name: float(
            np.mean(
                [
                    sustained(config, mirror(schedule, config, settings["relay"]), LEVELS.index(name))[
                        "utility"
                    ]
                    for schedule in REGIMES.values()
                ]
            )
        )
        for name in fixed
    }
    return dict(
        buffer_held_at_its_base=dict(
            endpoint=over_schedules(held, span, "utility"),
            differences_over_all_schedules=everywhere,
            **decide(everywhere, by_schedule),
        ),
        simulator_as_built=dict(
            own_utility=built,
            order_of_the_fixed_arms=sorted(built, key=built.get, reverse=True),
            native_order_of_the_fixed_arms=sorted(
                fixed,
                key=lambda n: native["all_schedules"][span]["utility"]["arms"][n]["level"]["mean"],
                reverse=True,
            ),
        ),
    )


def robustness(layer, native, config, settings):
    """With the path noise of the simulator's own families: how often each established difference agrees."""
    span, counts = SPANS[0], defaultdict(int)
    for replicate in range(settings["replicates"]):
        path = np.random.default_rng(split_seed(settings["seed"], "native-receiver-path", replicate))
        made = {name: {} for name in ARM_POLICIES}
        for regime, schedule in REGIMES.items():
            trace = mirror(schedule, config, settings["relay"], path)
            for name, policy in ARM_POLICIES.items():
                made[name][regime] = summarise(run(config, trace, policy, layer), schedule)
        everywhere, _ = differences(made, span, native)
        for pair, entry in everywhere.items():
            counts[pair] += entry["verdict"] == "agrees"
    native_all = native["all_schedules"][span]["utility"]["contrasts"]
    return dict(
        replicates=settings["replicates"],
        share_of_replicates_agreeing={
            pair: counts[pair] / settings["replicates"] for pair in counts if sign(native_all[pair]) != 0
        },
    )


def collect(capture):
    """The range pilot's sealed sessions as targets for the fit."""
    capture = Path(capture)
    made = read_json(capture / "protocol.json")
    if made.get("abi") != pilot.PLAN_STAGE:
        raise ValueError("a capture of the range pilot is required")
    roots = [capture / trial for _, trial in made["order"] if pilot._sealed(capture / trial)]
    return dict(
        targets([session_targets(root) for root in roots]), plan_sha256=digest(capture / "protocol.json")
    )


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    reader = commands.add_parser("targets", help="what the range pilot gives the fit")
    reader.add_argument("--capture", required=True, type=Path)
    fitter = commands.add_parser("fit", help="fit the layer on the range pilot only")
    fitter.add_argument("--targets", required=True, type=Path)
    fitter.add_argument("--pilot", required=True, type=Path, help="the range pilot's report")
    tester = commands.add_parser("test", help="the fitted layer on the controller pilot's arms, once")
    tester.add_argument("--layer", required=True, type=Path)
    tester.add_argument("--pilot", required=True, type=Path, help="the controller pilot's report")
    for command in (reader, fitter, tester):
        command.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(2, "error: fresh output file required\n")
    config, settings = simulator(), load_settings()
    if args.command == "targets":
        result = collect(args.capture)
        shown = dict(sessions=result["sessions"], return_ms=result["return_ms"])
    elif args.command == "fit":
        native = read_json(args.pilot)
        if native.get("abi") != pilot.ABI + "_report":
            parser.exit(2, "error: the range pilot's report is required\n")
        layer, stages, beside = fit(read_json(args.targets), native, config, settings)
        result = dict(
            study=STUDY + "_layer",
            synthetic=True,
            fitted_on="the native range pilot only",
            targets_sha256=_sha(args.targets),
            pilot_report_sha256=_sha(args.pilot),
            layer=asdict(layer),
            stages=stages,
            beside_the_range_pilot=beside,
        )
        shown = dict(layer=result["layer"], stages=stages, comparisons=beside["comparisons"])
    else:
        native, fitted = read_json(args.pilot), read_json(args.layer)
        if native.get("abi") != ladder.ABI + "_report" or fitted.get("study") != STUDY + "_layer":
            parser.exit(2, "error: the fitted layer and the controller pilot's report are required\n")
        values = fitted["layer"]
        layer = Layer(**{k: tuple(v) if isinstance(v, list) else v for k, v in values.items()})
        result = dict(
            study=STUDY + "_test",
            synthetic=True,
            native_evidence=False,
            learned_controller_promoted=False,
            layer_sha256=_sha(args.layer),
            pilot_report_sha256=_sha(args.pilot),
            **test(layer, native, config, settings),
        )
        shown = dict(verdict=result["verdict"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(shown, indent=1))


if __name__ == "__main__":
    main()
