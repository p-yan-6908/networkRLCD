"""What the typed simulator says about cap levels kept for a whole session (synthetic comparison).

The native range pilot found that a lower level kept for a whole session scores higher on its
endpoint than 1.05 of the estimate, and that the browser under the ceiling does worst. This
module runs the same five levels in the fluid simulator, as built, on mirrors of the four
native capacity schedules. It was written after the pilot's result was known, so it is a
comparison and not a forecast. No model is trained or evaluated, no controller acts, and
nothing here is native evidence.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .environment import MediaEnvironment
from .native_actuator_panel import REGIMES
from .native_actuator_qualification_explore import summary
from .scenarios import ID_SCENARIOS
from .typed_bitrate import Link, split_seed
from .typed_bitrate_b1_forecast import HOLD_MS, load_settings, mirror, simulator

STUDY = "typed_bitrate_sustained_levels_v1"
LEVELS = (0.25, 0.65, 0.85, 1.05, None)  # the native pilot's: ratios of the frozen estimate, or the ceiling
NAMES = ("0.25", "0.65", "0.85", "1.05", "ceiling")
REFERENCE = 3
HOLDS = 6
QUANTITIES = ("utility", "on_time", "encoder_over_capacity")


def sustained(config, trace, level):
    """One fresh simulated sender kept at one level for six holds, read from the second hold on.

    The request is the level's ratio of the estimate frozen at the start of each hold, inside the
    simulator's rate limits, or the upper limit for the ceiling. Utility is the simulator's
    delivered on-time quality term, as in the forecast of B1.
    """
    link = Link(config, ID_SCENARIOS[0], 0)
    link.env = MediaEnvironment(link.env.config, trace)
    limits, hold, ratio = config.residual, int(HOLD_MS / config.dt_ms), LEVELS[level]
    kept, rate = [], None
    for epoch in range(HOLDS):
        for k in range(hold):
            sample = link.sample()
            if k == 0:
                asked = limits.max_bps if ratio is None else ratio * sample.bwe_bps
                rate = float(np.clip(asked, limits.min_bps, limits.max_bps))
            o = link.advance(rate)
            if epoch >= 1:
                ontime = (1 - o["residual_loss"]) * (1 - o["deadline_miss"])
                quality = math.log1p(o["bitrate_mbps"] / 0.15) * (0.82 if o["low_latency"] else 1.0)
                capacity = float(trace.capacity[epoch * hold + k]) * 1e6
                kept.append((quality * ontime, 1 - o["deadline_miss"], link.actual_bps / capacity))
    return dict(zip(QUANTITIES, (float(v) for v in np.mean(kept, axis=0)), strict=True))


def exact(config, settings):
    """Every level on the relay's mirror of each schedule, without path noise."""
    return {
        regime: {
            name: sustained(config, mirror(schedule, config, settings["relay"]), level)
            for level, name in enumerate(NAMES)
        }
        for regime, schedule in REGIMES.items()
    }


def sampled(config, settings):
    """Replicates with the path noise the simulator's own families draw: one noisy path per schedule
    and replicate, the five levels on the same path."""
    rows = []
    for replicate in range(settings["replicates"]):
        path = np.random.default_rng(split_seed(settings["seed"], "sustained-levels-path", replicate))
        for regime, schedule in REGIMES.items():
            trace = mirror(schedule, config, settings["relay"], path)
            for level in range(len(LEVELS)):
                rows.append(
                    dict(replicate=replicate, regime=regime, level=level, **sustained(config, trace, level))
                )
    return rows


def by_level(rows, quantity, regime=None):
    """Per level over replicates: its mean, and its difference from the reference on the same paths."""
    cells = {}
    for r in rows:
        if regime is None or r["regime"] == regime:
            cells.setdefault(r["level"], {}).setdefault(r["replicate"], []).append(r[quantity])
    means = {level: {k: float(np.mean(v)) for k, v in own.items()} for level, own in cells.items()}
    reference = means.get(REFERENCE, {})
    out = {}
    for level, name in enumerate(NAMES):
        own = means.get(level, {})
        out[name] = dict(
            level=summary(list(own.values())),
            minus_reference=summary([own[k] - reference[k] for k in own if k in reference]),
        )
    return out


def sign(entry):
    """+1 or -1 when the interval excludes zero, 0 when it does not or there is none."""
    pair = entry.get("interval95")
    if pair is None:
        return 0
    return 1 if pair[0] > 0 else -1 if pair[1] < 0 else 0


def best(table):
    known = {
        name: entry["level"]["mean"] for name, entry in table.items() if entry["level"]["mean"] is not None
    }
    return max(known, key=known.get) if known else None


def compare(simulated, pilot):
    """The simulator's utility against the pilot's, level by level.

    A comparison agrees when both differences from the reference exclude zero on the same side,
    disagrees when they exclude it on opposite sides, and is unclear otherwise. The best level is
    the one with the highest mean utility.
    """

    def one(own, native):
        pairs = {}
        for level, name in enumerate(NAMES):
            if level == REFERENCE:
                continue
            mine, theirs = sign(own[name]["minus_reference"]), sign(native[name]["minus_reference"])
            verdict = "unclear" if 0 in (mine, theirs) else "agrees" if mine == theirs else "disagrees"
            pairs[name] = dict(simulator=mine, native=theirs, verdict=verdict)
        return dict(
            differences_from_the_reference=pairs,
            best_level=dict(simulator=best(own), native=best(native)),
        )

    span = "after_startup"
    out = dict(
        all_schedules=one(simulated["all_schedules"]["utility"], pilot["all_schedules"][span]["utility"])
    )
    out["by_schedule"] = {
        regime: one(
            simulated["by_schedule"][regime]["utility"], pilot["by_schedule"][regime][span]["utility"]
        )
        for regime in REGIMES
    }
    verdicts = [
        p["verdict"]
        for block in (out["all_schedules"], *out["by_schedule"].values())
        for p in block["differences_from_the_reference"].values()
    ]
    out["comparisons"] = {v: verdicts.count(v) for v in ("agrees", "disagrees", "unclear")}
    out["schedules_with_the_same_best_level"] = sum(
        b["best_level"]["simulator"] == b["best_level"]["native"] for b in out["by_schedule"].values()
    )
    return out


def study(settings, pilot=None):
    config = simulator()
    rows = sampled(config, settings)
    simulated = dict(
        all_schedules={q: by_level(rows, q) for q in QUANTITIES},
        by_schedule={regime: {q: by_level(rows, q, regime) for q in QUANTITIES} for regime in REGIMES},
    )
    report = dict(
        study=STUDY,
        synthetic=True,
        written_after_the_native_pilot=True,
        forecast=False,
        models_fitted=0,
        levels=list(NAMES),
        reference_level=NAMES[REFERENCE],
        replicates=settings["replicates"],
        relay=settings["relay"],
        exact=exact(config, settings),
        sampled=simulated,
    )
    if pilot is not None:
        report["against_the_native_pilot"] = compare(simulated, pilot)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--settings", type=Path, help="the forecast's settings: relay mirror, seed, replicates"
    )
    parser.add_argument("--pilot", type=Path, help="the native range pilot's report, to compare with")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(2, "error: fresh output file required\n")
    pilot = json.loads(args.pilot.read_text()) if args.pilot else None
    report = study(load_settings(args.settings), pilot)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    shown = {
        name: round(e["level"]["mean"], 4)
        for name, e in report["sampled"]["all_schedules"]["utility"].items()
    }
    print(
        json.dumps(
            dict(utility=shown, against=report.get("against_the_native_pilot", {}).get("comparisons")),
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
