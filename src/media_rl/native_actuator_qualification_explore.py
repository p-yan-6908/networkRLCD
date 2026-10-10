"""Exploratory description of the N1 cohort rows. Not registered and not confirmatory.

Run after the registered final analysis. The quantities are listed in
docs/NATIVE_PHASE_N1_EXPLORATORY.md, which was committed before any of them was computed. The
unit is the source: cohorts are averaged within source, regime and arm, and every interval is a
two-sided 95% t interval over sources. Nothing here changes the N1 outcome, fits a model or
supports a claim about a controller.
"""

import argparse
import gzip
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from . import native_actuator_qualification as qualification
from .native_actuator_qualification_panel import REGIMES

ARMS = range(len(qualification.RATIOS))
PAIRS = ((1, 0), (2, 1), (2, 0))  # 0.85 - 0.65, 1.05 - 0.85, 1.05 - 0.65
HOLD_PAIRS = ("holds 1-2", "holds 3-4", "holds 5-6")
REFERENCE = REGIMES[0]  # the underutilized schedule


def pair_name(pair):
    return f"{qualification.RATIOS[pair[0]]:.2f} - {qualification.RATIOS[pair[1]]:.2f}"


def load(path):
    """Complete audited cohort rows, from the capture's cohorts.json or its gzip."""
    path = Path(path)
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    rows = [r for r in json.loads(raw) if r["complete"] is True]
    if not rows or any(r["base_bwe_bps"] <= 0 for r in rows):
        raise ValueError("complete cohort rows with a positive frozen estimate are required")
    return rows, hashlib.sha256(raw).hexdigest()


def rate(row):
    return row["encoder_bps"] / row["base_bwe_bps"]


def estimate_growth(rows):
    """Per hold with a successor in its peer: log of the next frozen estimate over this one."""
    peers = defaultdict(dict)
    for r in rows:
        peers[r["trial_id"]][r["epoch"]] = r
    out = []
    for holds in peers.values():
        for epoch, r in holds.items():
            if epoch + 1 in holds:
                out.append(dict(r, growth=math.log(holds[epoch + 1]["base_bwe_bps"] / r["base_bwe_bps"])))
    return out


def summary(values):
    """Mean over sources with a two-sided 95% t interval and the p-value against zero."""
    x = np.asarray(values, dtype=float)
    if len(x) < 2:
        return dict(sources=len(x), mean=float(x.mean()) if len(x) else None, interval95=None, p_value=None)
    error = x.std(ddof=1) / math.sqrt(len(x))
    half = float(stats.t.ppf(0.975, len(x) - 1)) * error
    if error > 0:
        p = float(2 * stats.t.sf(abs(x.mean()) / error, len(x) - 1))
    else:  # identical values in every source
        p = 1.0 if x.mean() == 0 else 0.0
    return dict(
        sources=len(x),
        mean=float(x.mean()),
        interval95=[float(x.mean() - half), float(x.mean() + half)],
        p_value=p,
    )


def source_means(rows, value, key=lambda r: ()):
    """Mean of ``value`` per (source, key, arm) over the rows where it is defined."""
    cells = defaultdict(list)
    for r in rows:
        v = value(r)
        if v is not None:
            cells[(r["cluster_id"], key(r), r["arm"])].append(v)
    return {k: float(np.mean(v)) for k, v in cells.items()}


def by_arm(rows, value, regime=None):
    """Arm means and adjacent contrasts over sources; all regimes weighted equally when none is named."""
    regimes = REGIMES if regime is None else (regime,)
    cells = source_means(rows, value, key=lambda r: r["network_regime"])
    per_source = {}
    for source in sorted({k[0] for k in cells}):
        if all((source, r, arm) in cells for r in regimes for arm in ARMS):
            per_source[source] = [float(np.mean([cells[(source, r, arm)] for r in regimes])) for arm in ARMS]
    table = np.array(list(per_source.values()), dtype=float).reshape(-1, len(qualification.RATIOS))
    return dict(
        arms={f"{qualification.RATIOS[arm]:.2f}": summary(table[:, arm]) for arm in ARMS},
        contrasts={pair_name(p): summary(table[:, p[0]] - table[:, p[1]]) for p in PAIRS},
    )


def holm(p_values):
    known = [i for i, p in enumerate(p_values) if p is not None]  # a test without two sources has none
    running, out = 0.0, [None] * len(p_values)
    for rank, index in enumerate(sorted(known, key=lambda i: p_values[i])):
        running = max(running, min(1.0, (len(known) - rank) * p_values[index]))
        out[index] = running
    return out


def regime_interaction(rows, value):
    """Does the effect of the highest against the lowest ratio differ from the underutilized schedule?"""
    cells = source_means(rows, value, key=lambda r: r["network_regime"])
    sources = sorted({k[0] for k in cells})
    effect = {
        r: {
            s: cells[(s, r, 2)] - cells[(s, r, 0)]
            for s in sources
            if (s, r, 2) in cells and (s, r, 0) in cells
        }
        for r in REGIMES
    }
    out = {}
    for r in REGIMES[1:]:
        shared = [s for s in sources if s in effect[REFERENCE] and s in effect[r]]
        out[r] = summary([effect[REFERENCE][s] - effect[r][s] for s in shared])
    adjusted = holm([out[r]["p_value"] for r in REGIMES[1:]])
    for r, p in zip(REGIMES[1:], adjusted):
        out[r]["holm_p_value"] = p
    return out


def best_arm(rows, value):
    """Per regime, how many sources have their highest mean at each ratio. A tally, not a test."""
    cells = source_means(rows, value, key=lambda r: r["network_regime"])
    out = {}
    for r in REGIMES:
        counts = [0] * len(qualification.RATIOS)
        for source in sorted({k[0] for k in cells}):
            if all((source, r, arm) in cells for arm in ARMS):
                counts[int(np.argmax([cells[(source, r, arm)] for arm in ARMS]))] += 1
        out[r] = {f"{qualification.RATIOS[arm]:.2f}": counts[arm] for arm in ARMS}
    return out


def by_hold_pair(rows, value):
    """The highest-against-lowest contrast per regime and pair of holds; sources with an empty cell drop out."""
    cells = source_means(rows, value, key=lambda r: (r["network_regime"], r["epoch"] // 2))
    sources = sorted({k[0] for k in cells})
    out = {}
    for r in REGIMES:
        out[r] = {}
        for index, name in enumerate(HOLD_PAIRS):
            kept = [s for s in sources if (s, (r, index), 2) in cells and (s, (r, index), 0) in cells]
            out[r][name] = summary([cells[(s, (r, index), 2)] - cells[(s, (r, index), 0)] for s in kept])
    return out


def describe(rows, value):
    return dict(overall=by_arm(rows, value), regimes={r: by_arm(rows, value, r) for r in REGIMES})


def explore(rows):
    quality = {
        name: dict(
            describe(rows, lambda r, name=name: r[name]),
            regime_interaction=regime_interaction(rows, lambda r, name=name: r[name]),
            best_arm_by_source=best_arm(rows, lambda r, name=name: r[name]),
            highest_minus_lowest_by_hold_pair=by_hold_pair(rows, lambda r, name=name: r[name]),
        )
        for name in ("utility", "ontime_fraction")
    }
    return dict(
        abi=qualification.ABI + "_exploratory",
        exploratory=True,
        registered=False,
        changes_the_n1_outcome=False,
        unit="source",
        interval="two-sided 95% t interval over sources",
        complete_cohorts=len(rows),
        sources=len({r["cluster_id"] for r in rows}),
        mock=any(r.get("mock") for r in rows),
        response_level=describe(rows, rate),
        estimate_growth=describe(estimate_growth(rows), lambda r: r["growth"]),
        quality=quality,
        quality_is="on-time sampled RGB-PSNR contribution and on-time fraction of frames captured in the outcome window; not perceptual quality",
        policy_models_fitted=0,
        learned_controller_promoted=False,
    )


def sources_needed(spread, effect, power, limit=2000):
    """Smallest number of sources at which a two-sided 5% t test of a mean detects ``effect``."""
    for n in range(3, limit + 1):
        critical, shift = stats.t.ppf(0.975, n - 1), effect * math.sqrt(n) / spread
        reached = stats.nct.sf(critical, n - 1, shift) + stats.nct.cdf(-critical, n - 1, shift)
        if reached >= power:
            return n
    return None


def planning(rows, effects=(1.0, 2.0), powers=(0.8, 0.9)):
    """A sizing note added after the exploratory results were read. For planning only.

    How many sources a later study with this design per source would need to detect a given
    difference in the on-time PSNR proxy, from the spread of per-source contrasts seen here.
    The second contrast was chosen after seeing where the pilot's point estimates were
    negative, so its mean is biased toward an effect and only its spread is used.
    """
    whole = source_means(rows, lambda r: r["utility"], key=lambda r: r["network_regime"])
    cells = source_means(rows, lambda r: r["utility"], key=lambda r: (r["network_regime"], r["epoch"] // 2))
    sources = sorted({k[0] for k in whole})
    contrasts = {
        "all schedules, ratio 1.05 minus 0.65": [
            float(np.mean([whole[(s, r, 2)] - whole[(s, r, 0)] for r in REGIMES])) for s in sources
        ],
        "constrained schedules, holds 3-4, ratio 0.65 minus 1.05": [
            float(np.mean([cells[(s, (r, 1), 0)] - cells[(s, (r, 1), 2)] for r in REGIMES[1:]]))
            for s in sources
            if all((s, (r, 1), arm) in cells for r in REGIMES[1:] for arm in (0, 2))
        ],
    }
    out = {}
    for name, values in contrasts.items():
        spread = float(np.std(values, ddof=1))
        out[name] = dict(
            summary(values),
            per_source_sd=spread,
            sources_needed={
                f"effect {effect:g}, power {power:g}": sources_needed(spread, effect, power)
                for effect in effects
                for power in powers
            },
        )
    return dict(
        abi=qualification.ABI + "_planning",
        exploratory=True,
        added_after_the_exploratory_results=True,
        for_planning_only=True,
        assumes="the N1 design per source: ten peers per schedule, six holds per peer",
        contrasts=out,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Exploratory description of the N1 cohort rows")
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--planning", action="store_true", help="write the sizing note instead")
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.exit(2, "error: fresh output path required\n")
    rows, digest = load(args.rows)
    report = dict(planning(rows) if args.planning else explore(rows), rows_sha256=digest)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps(
            {k: report.get(k) for k in ("exploratory", "complete_cohorts", "sources", "mock")}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
