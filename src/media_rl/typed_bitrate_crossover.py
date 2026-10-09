"""Per-link crossover identification of a ratio effect from factual outcomes (synthetic, development).

On one link, is ratio B better than ratio A? Hindsight rollouts answer on a shared future, which
a real network cannot provide, and comparing whole sessions run at A with others run at B needs
hundreds of sessions because sessions differ far more than the ratios do. A crossover session
alternates blocks of A and B in a random order and compares the two within the session.

The simulator can check what a native system cannot: whether the crossover estimate agrees with
the difference between running B throughout and running A throughout on identical traces, and
how many sessions each design needs. Only the crossover estimate is factual; the constant-ratio
comparison on identical traces is the yardstick.
"""

import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .typed_bitrate import Governor, Link, load_config, split_seed, step
from .typed_bitrate_experiment import dump

STUDY = "typed_bitrate_crossover_v1"
DEFAULTS = dict(
    name="typed-crossover-v1",
    pairs=[[1.05, 1.0], [1.0, 0.9], [0.9, 0.8], [1.05, 0.8]],  # (A, B): the effect is B minus A
    block_ms=[3000, 6000, 9000, 18000],
    washout_ms=[0, 1000, 2000],  # start of each block left out of the estimate
    sessions=32,  # per link
    minimum_effect=0.01,  # links with a smaller true effect are left out of the session counts
)
_WORKER = {}


def load_settings(path=None):
    settings = {**DEFAULTS, **(json.loads(Path(path).read_text()) if path else {})}
    if set(settings) != set(DEFAULTS):
        raise ValueError("unknown crossover study setting")
    if not settings["pairs"] or any(len(p) != 2 or p[0] == p[1] for p in settings["pairs"]):
        raise ValueError("pairs must name two different ratios")
    if (
        not settings["block_ms"]
        or min(settings["block_ms"]) <= 0
        or min(settings["washout_ms"], default=-1) < 0
    ):
        raise ValueError("block lengths must be positive and washouts nonnegative")
    if type(settings["sessions"]) is not int or settings["sessions"] < 2 or settings["minimum_effect"] <= 0:
        raise ValueError("at least two sessions and a positive minimum effect are required")
    return settings


def session(config, scenario, seed, plan=None):
    """One session at a constant ratio, or alternating two ratios in blocks.

    ``plan`` is ``(a, b, block_steps, washout_steps, first)``; ``first`` says which ratio runs in
    the first block. Returns the session's mean utility and, for a crossover, the mean utility of
    the measured steps of each ratio (NaN if a ratio has none).
    """
    link, governor = Link(config, scenario, seed), Governor(config)
    constant = isinstance(plan, (int, float))
    total, measured = 0.0, ([], [])
    for t in range(config.steps):
        sample = link.sample()
        if constant:
            ratio = plan
        else:
            a, b, block, washout, first = plan
            arm = (t // block + first) % 2
            ratio = b if arm else a
        utility, _ = step(link, governor, sample, ratio, config)
        total += utility
        if not constant and t % block >= washout:
            measured[arm].append(utility)
    if constant:
        return total / config.steps, None
    means = [float(np.mean(m)) if m else float("nan") for m in measured]
    return total / config.steps, means


def _init(config):
    _WORKER["config"] = config


def _session(task):
    return session(_WORKER["config"], *task)


def run_sessions(config, tasks):
    if config.workers == 1 or len(tasks) < 4:
        return [session(config, *task) for task in tasks]
    with ProcessPoolExecutor(config.workers, initializer=_init, initargs=(config,)) as pool:
        return list(pool.map(_session, tasks, chunksize=32))


def designs(config, settings):
    """Block and washout lengths in control steps; a washout must leave part of the block."""
    out = []
    for block_ms in settings["block_ms"]:
        for washout_ms in settings["washout_ms"]:
            block, washout = int(block_ms / config.dt_ms), int(washout_ms / config.dt_ms)
            if washout < block and 2 * block <= config.steps:
                out.append(dict(block_ms=block_ms, washout_ms=washout_ms, block=block, washout=washout))
    return out


def needed(spread, effect, minimum):
    """Sessions for the per-link effect to stand two standard errors from zero; median over links."""
    keep = np.abs(effect) >= minimum
    if not keep.any():
        return None
    return float(np.median((2 * spread[keep] / np.abs(effect[keep])) ** 2))


def summarise(estimate, cost, truth, paired, a_sessions, b_sessions, minimum):
    """One design on one pair. ``estimate`` is [link, session]; ``truth`` the per-link true effect."""
    mean = np.nanmean(estimate, axis=1)
    slope, intercept = np.polyfit(truth, mean, 1)
    large = np.abs(truth) >= 2 * minimum
    spread = np.nanstd(estimate, axis=1, ddof=1)
    unpaired = np.sqrt(a_sessions.var(axis=1, ddof=1) + b_sessions.var(axis=1, ddof=1))
    return dict(
        bias=float(np.mean(mean - truth)),
        slope=float(slope),
        intercept=float(intercept),
        correlation=float(np.corrcoef(truth, mean)[0, 1]),
        sign_agreement=float(np.mean(np.sign(mean[large]) == np.sign(truth[large]))) if large.any() else None,
        links_with_large_effect=int(large.sum()),
        session_spread=float(np.median(spread)),
        sessions_needed=needed(spread, truth, minimum),
        sessions_needed_whole_sessions=needed(
            unpaired, truth, minimum
        ),  # per ratio, sessions run at one ratio
        sessions_needed_identical_traces=needed(paired.std(axis=1, ddof=1), truth, minimum),
        experiment_cost=float(np.mean(cost - a_sessions)),  # utility of crossing over instead of staying at A
        usable=bool(0.8 <= slope <= 1.2 and abs(intercept) <= 0.005),
    )


def study(run, out, settings=None):
    """Crossover estimates against constant-ratio differences on the run's training families."""
    run, out = Path(run), Path(out)
    if out.exists():
        raise FileExistsError(out)
    config, settings = load_config(run / "config.json"), load_settings(settings)
    links, count, started = list(config.train_scenarios), settings["sessions"], time.time()
    ratios = sorted({r for pair in settings["pairs"] for r in pair})
    if any(r > max(config.ratios) for r in ratios):
        raise ValueError("a pair names a ratio above the governor's ceiling")
    out.mkdir(parents=True)
    dump(out / "settings.json", settings)
    traces = [(link, split_seed(config.seed, "crossover", link, s)) for link in links for s in range(count)]
    shape = (len(links), count)
    constant = {}
    for ratio in ratios:
        results = run_sessions(config, [(link, seed, ratio) for link, seed in traces])
        constant[ratio] = np.asarray([u for u, _ in results]).reshape(shape)
    report = dict(
        abi=STUDY,
        run=str(run),
        synthetic_only=True,
        settings=settings,
        links=len(links),
        sessions=count,
        session_seconds=config.steps * config.dt_ms / 1000,
        between_session_spread=float(np.median(constant[ratios[-1]].std(axis=1, ddof=1))),
        pairs=[],
    )
    for a, b in settings["pairs"]:
        paired = constant[b] - constant[a]  # the yardstick: identical traces, not available natively
        truth = paired.mean(axis=1)
        entry = dict(
            a=a,
            b=b,
            true_effect_mean=float(truth.mean()),
            true_effect_spread=float(truth.std(ddof=1)),
            links_above_minimum=int(np.sum(np.abs(truth) >= settings["minimum_effect"])),
            designs=[],
        )
        for design in designs(config, settings):
            tasks = [
                (link, seed, (a, b, design["block"], design["washout"], split_seed(seed, "order", a, b) % 2))
                for link, seed in traces
            ]
            results = run_sessions(config, tasks)
            estimate = np.asarray([m[1] - m[0] for _, m in results]).reshape(shape)
            cost = np.asarray([u for u, _ in results]).reshape(shape)
            row = summarise(
                estimate, cost, truth, paired, constant[a], constant[b], settings["minimum_effect"]
            )
            entry["designs"].append(dict(block_ms=design["block_ms"], washout_ms=design["washout_ms"], **row))
        report["pairs"].append(entry)
    report["elapsed_s"] = time.time() - started
    dump(out / "report.json", report)
    return report


def headline(report):
    lines = [
        f"{report['links']} links, {report['sessions']} sessions of {report['session_seconds']:.0f} s each; "
        f"between-session spread {report['between_session_spread']:.3f}"
    ]
    for pair in report["pairs"]:
        lines.append(
            f"B={pair['b']:g} minus A={pair['a']:g}: true effect {pair['true_effect_mean']:+.3f}, "
            f"spread over links {pair['true_effect_spread']:.3f}, {pair['links_above_minimum']} links above the minimum"
        )
        for d in pair["designs"]:
            need = "n/a" if d["sessions_needed"] is None else f"{d['sessions_needed']:.0f}"
            lines.append(
                f"  block {d['block_ms'] / 1000:g} s washout {d['washout_ms'] / 1000:g} s: slope {d['slope']:.2f} "
                f"intercept {d['intercept']:+.4f} corr {d['correlation']:.2f} sessions {need} "
                f"cost {d['experiment_cost']:+.4f} {'usable' if d['usable'] else 'not usable'}"
            )
        d = pair["designs"][0]
        whole, ideal = d["sessions_needed_whole_sessions"], d["sessions_needed_identical_traces"]
        if whole is not None:
            lines.append(
                f"  whole sessions at one ratio: {whole:.0f} per ratio; identical traces: {ideal:.1f}"
            )
    return "\n".join(lines)
