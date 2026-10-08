"""Network families for the broadened typed-bitrate study (synthetic, seeded, exogenous).

``TRAIN_FAMILIES`` widen the fitting distribution beyond the four legacy in-distribution
families: randomised capacity shapes and the impairments the legacy training set never had.
``TEST_FAMILIES`` are evaluation-only. They were written before any controller ran on them,
and no fitting, tuning or development step may draw from them. Each differs from every
training family in temporal structure or in parameter range. The legacy registry in
``scenarios.py`` is left untouched because the older studies depend on it.
"""

import numpy as np

from .scenarios import Trace


def _base(rng, steps):
    scale = rng.uniform(0.85, 1.15)
    return dict(
        cap=np.full(steps, 2.8 * scale),
        rtt=np.full(steps, rng.uniform(35, 65)),
        loss=np.full(steps, rng.uniform(0.002, 0.012)),
        jitter=np.abs(rng.normal(0, 2, steps)),
        feedback=np.ones(steps, dtype=bool),
        burst=np.zeros(steps),
        buffer=np.ones(steps),
    )


def _span(rng, steps, low, high):
    """A random window lasting between ``low`` and ``high`` of the episode."""
    length = max(1, int(rng.uniform(low, high) * steps))
    start = int(rng.integers(0, steps - length + 1))
    return slice(start, start + length)


def _levels(rng, steps, pieces, low, high):
    """Piecewise-constant multipliers with random change points."""
    cuts = np.sort(rng.uniform(0.08, 0.92, pieces - 1))
    return rng.uniform(low, high, pieces)[np.searchsorted(cuts, np.arange(steps) / steps)]


def _drift(rng, steps, rho, sigma):
    noise = np.zeros(steps)
    for i in range(1, steps):
        noise[i] = rho * noise[i - 1] + rng.normal(0, sigma)
    return noise


# Training families ---------------------------------------------------------------------------


def multi_step(rng, steps, t):
    t["cap"] *= _levels(rng, steps, int(rng.integers(3, 7)), 0.25, 1.6)


def multi_ramp(rng, steps, t):
    knots = int(rng.integers(3, 7))
    at = np.concatenate([[0], np.sort(rng.uniform(0.05, 0.95, knots - 2)), [1]])
    t["cap"] *= np.interp(np.arange(steps) / steps, at, rng.uniform(0.25, 1.6, knots))


def drift(rng, steps, t):
    u = np.arange(steps) / steps
    wave = rng.uniform(0, 0.3) * np.sin(2 * np.pi * (rng.uniform(1, 6) * u + rng.random()))
    noise = _drift(rng, steps, rng.uniform(0.8, 0.98), rng.uniform(0.02, 0.08))
    t["cap"] *= np.clip(rng.uniform(0.6, 1.2) + wave + noise, 0.2, 1.6)


def dip(rng, steps, t):
    for _ in range(int(rng.integers(1, 4))):
        t["cap"][_span(rng, steps, 0.04, 0.22)] *= rng.uniform(0.1, 0.5)


def loss_episode(rng, steps, t):
    t["cap"] *= np.clip(1 + _drift(rng, steps, 0.9, 0.03), 0.6, 1.4)
    for _ in range(int(rng.integers(1, 5))):
        window = _span(rng, steps, 0.015, 0.14)
        t["loss"][window] = rng.uniform(0.05, 0.35)
        t["burst"][window] = rng.uniform(0.3, 0.9)


def deep_queue(rng, steps, t):
    t["buffer"][:] = rng.uniform(3, 10)
    t["cap"] *= _levels(rng, steps, int(rng.integers(2, 4)), 0.25, 1.2)


def delay_shift(rng, steps, t):
    start = int(rng.uniform(0.2, 0.6) * steps)
    stop = steps if rng.random() < 0.5 else min(steps, start + int(rng.uniform(0.15, 0.4) * steps))
    t["rtt"][start:stop] += rng.uniform(40, 200)
    t["jitter"][start:stop] += np.abs(rng.normal(0, rng.uniform(5, 25), stop - start))
    if rng.random() < 0.5:
        t["cap"][start : start + max(1, int(rng.uniform(0.02, 0.1) * steps))] *= rng.uniform(0.05, 0.3)


def blackout(rng, steps, t):
    for _ in range(int(rng.integers(1, 3))):
        kind = int(rng.integers(3))  # feedback gap, dead link, or both
        if kind != 1:
            window = _span(rng, steps, 0.03, 0.17)
            t["feedback"][window] = False
            if rng.random() < 0.5:
                t["cap"][window] = rng.uniform(0.2, 0.8)
        if kind != 0:
            window = _span(rng, steps, 0.015, 0.11)
            t["cap"][window] = 0
            t["loss"][window] = 1


def headroom(rng, steps, t):
    start = int(rng.uniform(0.2, 0.6) * steps)
    stop = min(steps, start + int(rng.uniform(0.2, 0.6) * steps))
    t["cap"][start:stop] *= rng.uniform(1.5, 4.5)
    t["rtt"][start:stop] = rng.uniform(10, 30)


# Untouched test families ---------------------------------------------------------------------


def sawtooth(rng, steps, t):
    phase = (np.arange(steps) / steps / rng.uniform(0.17, 0.33) + rng.random()) % 1
    low = rng.uniform(0.3, 0.5)
    t["cap"] *= low + (rng.uniform(1.0, 1.5) - low) * phase


def square_wave(rng, steps, t):
    phase = (np.arange(steps) / steps / rng.uniform(0.08, 0.22) + rng.random()) % 1
    high = rng.uniform(0.9, 1.5)
    t["cap"] *= np.where(phase < rng.uniform(0.35, 0.65), high, high / rng.uniform(2, 4))


def staircase(rng, steps, t):
    u = np.arange(steps) / steps
    stairs = int(rng.integers(5, 9))
    top, bottom = rng.uniform(1.3, 1.6), rng.uniform(0.2, 0.35)
    start, stop = rng.uniform(0.05, 0.15), rng.uniform(0.7, 0.8)
    stair = np.minimum((np.clip((u - start) / (stop - start), 0, 1) * stairs).astype(int), stairs - 1)
    t["cap"] *= np.where(u >= stop, top, np.linspace(top, bottom, stairs)[stair])


def slow_fade(rng, steps, t):
    u = np.arange(steps) / steps
    centre, width, floor = rng.uniform(0.45, 0.6), rng.uniform(0.12, 0.2), rng.uniform(0.15, 0.3)
    depth = np.exp(-0.5 * ((u - centre) / width) ** 2)
    t["cap"] *= 1 - (1 - floor) * depth
    t["loss"] += rng.uniform(0.02, 0.035) * depth  # loss rises with the fade, below the safety limit


def low_rate(rng, steps, t):
    t["cap"] = np.clip(rng.uniform(0.3, 0.7) * (1 + _drift(rng, steps, 0.9, 0.05)), 0.2, 1.0)


def long_path(rng, steps, t):
    t["rtt"][:] = rng.uniform(120, 180)
    t["cap"] *= _levels(rng, steps, int(rng.integers(2, 5)), 0.4, 1.4)


def jitter_storm(rng, steps, t):
    t["cap"] *= np.clip(1 + _drift(rng, steps, 0.9, 0.03), 0.6, 1.4)
    for _ in range(int(rng.integers(2, 5))):
        window = _span(rng, steps, 0.05, 0.15)
        t["jitter"][window] += np.abs(rng.normal(0, rng.uniform(15, 40), window.stop - window.start))


def micro_outage(rng, steps, t):
    for _ in range(int(rng.integers(6, 17))):
        start = int(rng.integers(0, steps - 6))
        window = slice(start, start + int(rng.integers(2, 7)))
        t["cap"][window] = 0
        t["loss"][window] = 1


def feedback_flap(rng, steps, t):
    t["cap"] *= np.clip(rng.uniform(0.6, 1.2) + _drift(rng, steps, 0.95, 0.04), 0.3, 1.5)
    for _ in range(int(rng.integers(8, 21))):
        start = int(rng.integers(0, steps - 12))
        t["feedback"][start : start + int(rng.integers(3, 13))] = False


def shallow_buffer(rng, steps, t):
    t["buffer"][:] = rng.uniform(0.25, 0.5)
    t["cap"] *= _levels(rng, steps, int(rng.integers(2, 4)), 0.4, 1.4)
    t["cap"] *= np.clip(1 + _drift(rng, steps, 0.9, 0.04), 0.6, 1.4)


def lossy_link(rng, steps, t):
    t["loss"][:] = rng.uniform(0.02, 0.045)
    t["burst"][:] = rng.uniform(0.2, 0.5)
    t["cap"] *= _levels(rng, steps, 2, 0.5, 1.3)


def compound(rng, steps, t):
    start = int(rng.uniform(0.25, 0.4) * steps)
    stop = min(steps, start + int(rng.uniform(0.2, 0.35) * steps))
    gap = start + int(rng.uniform(0.03, 0.08) * steps)
    t["cap"][start:stop] *= rng.uniform(0.25, 0.45)
    t["rtt"][start:stop] += rng.uniform(30, 90)
    t["jitter"][start:stop] += np.abs(rng.normal(0, rng.uniform(5, 15), stop - start))
    t["feedback"][gap : gap + max(1, int(rng.uniform(0.03, 0.06) * steps))] = False
    t["cap"][stop:] *= rng.uniform(1.2, 2.5)
    t["rtt"][stop:] = np.maximum(10, t["rtt"][stop:] - rng.uniform(5, 15))


TRAIN_FAMILIES = dict(
    multi_step=multi_step,
    multi_ramp=multi_ramp,
    drift=drift,
    dip=dip,
    loss_episode=loss_episode,
    deep_queue=deep_queue,
    delay_shift=delay_shift,
    blackout=blackout,
    headroom=headroom,
)
TEST_FAMILIES = dict(
    sawtooth=sawtooth,
    square_wave=square_wave,
    staircase=staircase,
    slow_fade=slow_fade,
    low_rate=low_rate,
    long_path=long_path,
    jitter_storm=jitter_storm,
    micro_outage=micro_outage,
    feedback_flap=feedback_flap,
    shallow_buffer=shallow_buffer,
    lossy_link=lossy_link,
    compound=compound,
)
FAMILIES = {**TRAIN_FAMILIES, **TEST_FAMILIES}


def family_trace(name, steps, seed):
    if name not in FAMILIES or steps < 20:
        raise ValueError("unknown family or steps <20")
    rng = np.random.default_rng(seed)
    t = _base(rng, steps)
    FAMILIES[name](rng, steps, t)
    return Trace(
        name,
        t["cap"],
        t["rtt"],
        np.clip(t["loss"], 0, 1),
        t["jitter"],
        t["feedback"],
        t["burst"],
        t["buffer"],
    )
