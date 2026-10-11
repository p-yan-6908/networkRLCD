"""What the range pilot leaves for a controller: a tuned fixed level, headroom over it, and signals.

Exploratory, on the development pilot's sealed sessions. A level, a level per schedule, or a
level per schedule and hold is chosen on eleven sources and scored on the twelfth; and three
signals the sender has when a hold begins are checked for whether they tell a link with room
from a constrained one. The quantities and the reading are in
docs/NATIVE_RANGE_PILOT_HEADROOM_V1.md, committed before any of them was computed. Nothing is
captured, no model is fitted, no controller is evaluated or promoted.
"""

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import native_backoff_benefit as benefit
from .native_actuator_control import DEADLINE_MS
from .native_actuator_qualification_explore import summary
from .native_protocol import read_json, require
from .native_range_pilot import ABI as PILOT
from .native_range_pilot import EDGE_MS, NAMES, REFERENCE, REGIMES, _labels, _sealed

ABI = PILOT + "_headroom"
ROOM = REGIMES[0]  # the underutilized schedule
LOOKBACK_MS = 1000  # signals are averaged over the second before a hold begins
SIGNALS = dict(estimate_growth=1, feedback_age_ms=-1, rtt_ms=-1)  # +1: larger with room; -1: smaller
FLAG = benefit.Plan().growth_limit


def _mean(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(values.mean()) if len(values) else math.nan


def session_holds(root):
    """One sealed session hold by hold: the endpoint over each hold, and what the sender knew as it began."""
    root = Path(root)
    rows = sorted(read_json(root / "cohorts.json"), key=lambda r: r["epoch"])
    require(rows and len({r["arm"] for r in rows}) == 1, "one level per session")
    labels = _labels(root / "native_derived.json")
    sender = json.loads((root / "sender_observations.json").read_text())
    stop = float(sender["measurement_cutoff_ms"]) - DEADLINE_MS + EDGE_MS
    acks = sender["feedback_events"]
    received = np.array([e["received_ms"] for e in acks], dtype=float)
    age = received - np.array([e["capture_request_ms"] for e in acks], dtype=float)
    polls = sender["decisions"]
    sample = np.array([p["observation"]["sample_ms"] for p in polls], dtype=float)
    rtt = np.array(
        [
            math.nan
            if p["observation"]["raw_source"].get("rtcp_rtt_s") is None
            else 1000 * p["observation"]["raw_source"]["rtcp_rtt_s"]
            for p in polls
        ],
        dtype=float,
    )
    holds = []
    for index, r in enumerate(rows):
        start = float(r["ack_ms"])
        end = float(rows[index + 1]["ack_ms"]) if index + 1 < len(rows) else stop
        asked = (labels["at"] >= start) & (labels["at"] < end)
        begun = float(r["assignment_ms"])
        growth = r["base_bwe_bps"] / rows[index - 1]["base_bwe_bps"] if index else math.nan
        holds.append(
            dict(
                epoch=r["epoch"],
                requests=int(asked.sum()),
                utility=float(labels["contribution"][asked].mean()) if asked.any() else math.nan,
                on_time=float(labels["ontime"][asked].mean()) if asked.any() else math.nan,
                estimate_growth=float(growth),
                feedback_age_ms=_mean(age[(received >= begun - LOOKBACK_MS) & (received < begun)]),
                rtt_ms=_mean(rtt[(sample >= begun - LOOKBACK_MS) & (sample < begun)]),
            )
        )
    return dict(
        trial_id=rows[0]["trial_id"],
        source=rows[0]["cluster_id"],
        regime=rows[0]["network_regime"],
        level=rows[0]["arm"],
        holds=holds,
    )


def stitched(holds):
    """Utility over a list of holds, weighted by their requests."""
    kept = [h for h in holds if h["requests"] > 0 and math.isfinite(h["utility"])]
    total = sum(h["requests"] for h in kept)
    return sum(h["requests"] * h["utility"] for h in kept) / total if total else math.nan


def later(session):
    return [h for h in session["holds"] if h["epoch"] >= 1]


def _best(scores):
    """The level with the highest finite score; the lowest level wins a tie."""
    known = {level: v for level, v in scores.items() if math.isfinite(v)}
    return max(sorted(known), key=known.get) if known else None


def plans(sessions):
    """A fixed level, a level per schedule and a level per schedule and hold, each chosen on the
    other sources and scored on the one left out; and the same chosen in sample."""
    table = {(s["source"], s["regime"], s["level"]): s for s in sessions}
    sources = sorted({s["source"] for s in sessions})
    regimes = [r for r in REGIMES if any(s["regime"] == r for s in sessions)]
    levels = range(len(NAMES))
    epochs = sorted({h["epoch"] for s in sessions for h in later(s)})

    def session_value(source, regime, level):
        own = table.get((source, regime, level))
        return stitched(later(own)) if own else math.nan

    def hold(source, regime, level, epoch):
        own = table.get((source, regime, level))
        found = [h for h in own["holds"] if h["epoch"] == epoch] if own else []
        return found[0] if found else None

    def choose(training):
        fixed = _best(
            {
                lv: _mean([_mean([session_value(o, r, lv) for r in regimes]) for o in training])
                for lv in levels
            }
        )
        aware = {
            r: _best({lv: _mean([session_value(o, r, lv) for o in training]) for lv in levels})
            for r in regimes
        }
        switched = {
            (r, e): _best(
                {
                    lv: _mean([h["utility"] for o in training if (h := hold(o, r, lv, e)) is not None])
                    for lv in levels
                }
            )
            for r in regimes
            for e in epochs
        }
        return fixed, aware, switched

    def score(source, chosen):
        fixed, aware, switched = chosen
        parts = []
        for r in regimes:
            taken = [hold(source, r, switched[(r, e)], e) for e in epochs if switched[(r, e)] is not None]
            parts.append(stitched([h for h in taken if h is not None]))
        return dict(
            reference=_mean([session_value(source, r, REFERENCE) for r in regimes]),
            fixed=_mean([session_value(source, r, fixed) for r in regimes])
            if fixed is not None
            else math.nan,
            schedule_aware=_mean(
                [session_value(source, r, aware[r]) for r in regimes if aware[r] is not None]
            ),
            switching_by_hold=_mean(parts),
        )

    folds = {source: choose([o for o in sources if o != source]) for source in sources}
    out_of_sample = {source: score(source, folds[source]) for source in sources}
    everyone = choose(sources)
    in_sample = {source: score(source, everyone) for source in sources}

    def over(scores, name):
        return summary([v[name] for v in scores.values() if math.isfinite(v[name])])

    def gap(scores, high, low):
        pairs = [(v[high], v[low]) for v in scores.values()]
        return summary([a - b for a, b in pairs if math.isfinite(a) and math.isfinite(b)])

    def described(scores):
        return dict(
            utility={
                name: over(scores, name)
                for name in ("reference", "fixed", "schedule_aware", "switching_by_hold")
            },
            fixed_minus_reference=gap(scores, "fixed", "reference"),
            schedule_aware_minus_fixed=gap(scores, "schedule_aware", "fixed"),
            switching_minus_schedule_aware=gap(scores, "switching_by_hold", "schedule_aware"),
            switching_minus_fixed=gap(scores, "switching_by_hold", "fixed"),
        )

    def name(level):
        return None if level is None else NAMES[level]

    counts = dict(
        fixed={n: sum(name(f[0]) == n for f in folds.values()) for n in NAMES},
        schedule_aware={
            r: {n: sum(name(f[1][r]) == n for f in folds.values()) for n in NAMES} for r in regimes
        },
    )
    return dict(
        leaving_one_source_out=described(out_of_sample),
        in_sample=described(in_sample),
        levels_chosen_in_the_folds=counts,
        levels_chosen_in_sample=dict(
            fixed=name(everyone[0]),
            schedule_aware={r: name(everyone[1][r]) for r in regimes},
            switching_by_hold={r: {str(e + 1): name(everyone[2][(r, e)]) for e in epochs} for r in regimes},
        ),
    )


def separation(room, constrained, direction):
    """Probability that a hold with room has the more favourable value than a constrained one."""
    a = np.asarray([v for v in room if math.isfinite(v)], dtype=float) * direction
    b = np.asarray([v for v in constrained if math.isfinite(v)], dtype=float) * direction
    if not len(a) or not len(b):
        return math.nan
    wins = (a[:, None] > b[None, :]).sum() + 0.5 * (a[:, None] == b[None, :]).sum()
    return float(wins / (len(a) * len(b)))


def signals(sessions):
    """Per level: how well each signal known as a hold begins tells room from constraint, and how
    often B1's flag marks a hold under each schedule."""
    out = {}
    for level, level_name in enumerate(NAMES):
        own = [s for s in sessions if s["level"] == level]
        sources = sorted({s["source"] for s in own})
        told = {}
        for signal, direction in SIGNALS.items():
            per_source = []
            for source in sources:
                with_room = [
                    h[signal] for s in own if s["source"] == source and s["regime"] == ROOM for h in later(s)
                ]
                without = [
                    h[signal] for s in own if s["source"] == source and s["regime"] != ROOM for h in later(s)
                ]
                value = separation(with_room, without, direction)
                if math.isfinite(value):
                    per_source.append(value)
            entry = summary(per_source)
            entry["tells_room_from_constraint"] = bool(
                entry["interval95"] is not None and entry["interval95"][0] > 0.5
            )
            told[signal] = entry
        flagged = {}
        for regime in REGIMES:
            shares = []
            for source in sources:
                marks = [
                    h["estimate_growth"] < FLAG
                    for s in own
                    if s["source"] == source and s["regime"] == regime
                    for h in later(s)
                    if math.isfinite(h["estimate_growth"])
                ]
                if marks:
                    shares.append(float(np.mean(marks)))
            flagged[regime] = summary(shares)
        medians = {
            signal: {
                kind: _mean(
                    [
                        float(np.median(vs))
                        for source in sources
                        if (
                            vs := [
                                h[signal]
                                for s in own
                                if s["source"] == source and (s["regime"] == ROOM) == (kind == "room")
                                for h in later(s)
                                if math.isfinite(h[signal])
                            ]
                        )
                    ]
                )
                for kind in ("room", "constrained")
            }
            for signal in SIGNALS
        }
        out[level_name] = dict(separation=told, flagged_share_by_schedule=flagged, median_by_state=medians)
    return out


def _above(entry, bound=0.0):
    return entry["interval95"] is not None and entry["interval95"][0] > bound


def analyse(sessions):
    made = plans(sessions)
    seen = signals(sessions)
    honest = made["leaving_one_source_out"]
    return dict(
        abi=ABI,
        exploratory=True,
        development_pilot=True,
        confirmatory=False,
        models_fitted=0,
        learned_controller_promoted=False,
        sessions=len(sessions),
        sources=len({s["source"] for s in sessions}),
        reference_level=NAMES[REFERENCE],
        plans=made,
        signals=seen,
        reading=dict(
            tuning_the_fixed_level_pays_out_of_sample=bool(_above(honest["fixed_minus_reference"])),
            knowing_the_schedule_adds_to_a_tuned_fixed_level=bool(
                _above(honest["schedule_aware_minus_fixed"])
            ),
            switching_by_hold_could_add_more_at_best=bool(_above(honest["switching_minus_schedule_aware"])),
            signals_that_tell_room_from_constraint={
                level: [name for name, e in block["separation"].items() if e["tells_room_from_constraint"]]
                for level, block in seen.items()
            },
        ),
    )


def collect(capture, reported=None):
    """Every sealed session hold by hold. With the pilot's own session outcomes, each session's
    holds from the second on must add up to the utility the pilot reported for it."""
    capture = Path(capture)
    made = read_json(capture / "protocol.json")
    known = {s["trial_id"]: s for s in reported} if reported is not None else None
    sessions = []
    for _, trial_id in made["order"]:
        if not _sealed(capture / trial_id):
            continue
        session = session_holds(capture / trial_id)
        if known is not None:
            theirs = known[trial_id]["after_startup"]
            require(
                theirs is not None and abs(stitched(later(session)) - theirs["utility"]) < 1e-9,
                f"{trial_id}: the holds do not add up to the pilot's reported utility",
            )
        sessions.append(session)
    return sessions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--sessions", required=True, type=Path, help="the pilot report's sessions.json")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(2, "error: fresh output file required\n")
    raw = args.sessions.read_bytes()
    sessions = collect(args.capture, json.loads(raw))
    report = dict(analyse(sessions), pilot_sessions_sha256=hashlib.sha256(raw).hexdigest())
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    held = defaultdict(list)
    for s in sessions:
        held[s["level"]].append(s)
    print(json.dumps(report["reading"], indent=1))


if __name__ == "__main__":
    main()
