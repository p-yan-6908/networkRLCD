"""A declared population of network families for confirmatory typed-bitrate panels (synthetic).

Hand-written test families are a convenience sample: a family-level interval over twelve of
them does not say which families it generalises to. Here a family is one draw of family-level
parameters from the distribution in ``parameters``, and an episode is one draw of a trace given
those parameters. "An unseen family" is then a new draw from a stated population, and a
panel's family-level interval refers to that population.

The ranges are those the hand-written training and test families already use; the population
adds no signal the simulator did not have. Capacity shape, path delay, loss, buffer depth,
jitter and impairment events are drawn independently, so most families combine mechanisms
that no hand-written family combined.

Three disjoint index spaces: ``pop_r`` (replication panel), ``pop_s`` (sealed for the next
confirmatory experiment) and ``pop_d`` (development pool, the only one fitting may draw from).
"""

import hashlib
import json

import numpy as np

SEED = 20261008
PANELS = dict(r=48, s=48, d=64)
SHAPES = ("flat", "steps", "ramps", "sine", "saw", "square", "fade", "walk")
EVENTS = ("surge", "delay_shift", "jitter_storm", "loss_episode", "feedback_gap", "outage")
EVENT_SHARE = 0.25  # each impairment is present in a family independently
LOSSY_SHARE = 0.15  # families with persistent random loss between 2% and 4.5%


def _between(rng, low, high):
    """Log-uniform: scale parameters spread evenly over their orders of magnitude."""
    return float(np.exp(rng.uniform(np.log(low), np.log(high))))


def parameters(panel, index):
    """Family-level parameters of one population member; a pure function of the registered seed."""
    if panel not in PANELS or not 0 <= index < PANELS[panel]:
        raise ValueError("unknown population family")
    rng = np.random.default_rng([SEED, list(PANELS).index(panel), index])
    p = dict(
        shape=SHAPES[int(rng.integers(len(SHAPES)))],
        level=_between(rng, 0.12, 1.3),  # mean capacity as a multiple of the 2.8 Mbps base
        low=float(rng.uniform(0.2, 0.6)),  # trough and crest of the shape, relative to the level
        high=float(rng.uniform(1.0, 1.6)),
        pieces=int(rng.integers(2, 9)),
        period=_between(rng, 0.08, 0.4),  # share of an episode
        duty=float(rng.uniform(0.35, 0.65)),
        width=float(rng.uniform(0.08, 0.2)),
        rho=float(rng.uniform(0.8, 0.98)),
        sigma=float(rng.uniform(0.02, 0.08)),
        noise=float(rng.uniform(0.0, 0.04)),
        rtt=_between(rng, 20, 180),
        buffer=_between(rng, 0.25, 10),
        jitter=float(rng.uniform(1, 4)),
    )
    p["loss"] = float(rng.uniform(0.02, 0.045)) if rng.random() < LOSSY_SHARE else None
    events = {}
    for name in EVENTS:
        present = rng.random() < EVENT_SHARE
        count = int(rng.integers(1, 17 if name == "outage" else 21))
        scale = dict(
            surge=float(rng.uniform(2.0, 4.5)),  # largest capacity multiple
            delay_shift=float(rng.uniform(40, 200)),  # largest added round-trip delay, ms
            jitter_storm=float(rng.uniform(15, 40)),  # largest jitter deviation, ms
            loss_episode=float(rng.uniform(0.1, 0.35)),  # largest loss rate
            feedback_gap=float(rng.uniform(0.01, min(0.17, 0.4 / count))),  # longest gap, share of an episode
            outage=float(rng.uniform(0.006, min(0.11, 0.25 / count))),
        )[name]
        if present:
            events[name] = [count, scale] if name in ("feedback_gap", "outage") else scale
    p["events"] = events
    return p


def _walk(rng, steps, rho, sigma):
    noise = np.zeros(steps)
    for i in range(1, steps):
        noise[i] = rho * noise[i - 1] + rng.normal(0, sigma)
    return noise


def _window(rng, steps, low, high):
    length = max(1, int(rng.uniform(low, high) * steps))
    start = int(rng.integers(0, steps - length + 1))
    return slice(start, start + length)


def _shape(p, rng, steps):
    u, low, high, kind = np.arange(steps) / steps, p["low"], p["high"], p["shape"]
    if kind == "flat":
        return np.ones(steps)
    if kind == "steps":
        pieces = int(rng.integers(2, p["pieces"] + 1))
        cuts = np.sort(rng.uniform(0.08, 0.92, pieces - 1))
        return rng.uniform(low, high, pieces)[np.searchsorted(cuts, u)]
    if kind == "ramps":
        knots = int(rng.integers(3, p["pieces"] + 2))
        at = np.concatenate([[0], np.sort(rng.uniform(0.05, 0.95, knots - 2)), [1]])
        return np.interp(u, at, rng.uniform(low, high, knots))
    if kind == "fade":
        shape = np.ones(steps)
        for _ in range(int(rng.integers(1, 3))):
            shape *= 1 - (1 - low) * np.exp(-0.5 * ((u - rng.uniform(0.15, 0.85)) / p["width"]) ** 2)
        return shape
    if kind == "walk":
        return np.clip(1 + _walk(rng, steps, p["rho"], p["sigma"]), low, high)
    phase = (u / p["period"] + rng.random()) % 1
    wave = dict(sine=0.5 + 0.5 * np.sin(2 * np.pi * phase), saw=phase, square=phase < p["duty"])[kind]
    return low + (high - low) * wave


def member(p):
    """The episode generator of one family, in the signature ``typed_bitrate_families`` registers."""

    def family(rng, steps, t):
        t["cap"] *= p["level"] * _shape(p, rng, steps)
        t["cap"] *= np.clip(1 + _walk(rng, steps, 0.9, p["noise"]), 0.7, 1.3)
        t["cap"] = np.maximum(t["cap"], 0.2)
        t["rtt"][:] = p["rtt"] * rng.uniform(0.85, 1.15)
        t["jitter"] = np.abs(rng.normal(0, p["jitter"], steps))
        t["buffer"][:] = p["buffer"]
        if p["loss"] is not None:
            t["loss"][:] = p["loss"] * rng.uniform(0.85, 1.15)
        events = p["events"]
        if "surge" in events:
            window = _window(rng, steps, 0.2, 0.6)
            t["cap"][window] *= rng.uniform(1.5, events["surge"])
            t["rtt"][window] *= rng.uniform(0.4, 0.8)
        if "delay_shift" in events:
            start = int(rng.uniform(0.2, 0.6) * steps)
            stop = steps if rng.random() < 0.5 else min(steps, start + int(rng.uniform(0.15, 0.4) * steps))
            t["rtt"][start:stop] += rng.uniform(0.5, 1) * events["delay_shift"]
            t["jitter"][start:stop] += np.abs(rng.normal(0, rng.uniform(5, 25), max(0, stop - start)))
        if "jitter_storm" in events:
            for _ in range(int(rng.integers(2, 5))):
                window = _window(rng, steps, 0.05, 0.15)
                deviation = rng.uniform(0.5, 1) * events["jitter_storm"]
                t["jitter"][window] += np.abs(rng.normal(0, deviation, window.stop - window.start))
        if "loss_episode" in events:
            for _ in range(int(rng.integers(1, 5))):
                t["loss"][_window(rng, steps, 0.015, 0.14)] = rng.uniform(0.05, events["loss_episode"])
        if "feedback_gap" in events:
            count, longest = events["feedback_gap"]
            for _ in range(int(rng.integers(1, count + 1))):
                t["feedback"][_window(rng, steps, 0.008, longest)] = False
        if "outage" in events:
            count, longest = events["outage"]
            for _ in range(int(rng.integers(1, count + 1))):
                window = _window(rng, steps, 0.005, longest)
                t["cap"][window] = 0
                t["loss"][window] = 1

    return family


def names(panel):
    return [f"pop_{panel}{i:02d}" for i in range(PANELS[panel])]


def table():
    """Every member's parameters by name: the population as registered."""
    return {name: parameters(panel, i) for panel in PANELS for i, name in enumerate(names(panel))}


def table_hash():
    return hashlib.sha256(json.dumps(table(), sort_keys=True).encode()).hexdigest()


POPULATION = {name: member(p) for name, p in table().items()}
SEALED = frozenset(names("r") + names("s"))  # evaluation-only: no fitting step may draw from these
