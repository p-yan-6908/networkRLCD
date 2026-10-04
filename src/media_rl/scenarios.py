"""Exogenous seeded traces, shared across all methods (Mbps and milliseconds)."""

from dataclasses import dataclass, replace

import numpy as np

SCENARIOS = {
    "steady": "id",
    "step": "id",
    "ramp": "id",
    "wifi": "id",
    "collapse": "ood",
    "burst_loss": "ood",
    "bufferbloat": "ood",
    "handover": "ood",
    "outage": "ood",
    "feedback_gap": "ood",
    "capacity_surge": "ood",
}
ID_SCENARIOS = tuple(k for k, v in SCENARIOS.items() if v == "id")


@dataclass(frozen=True)
class Trace:
    name: str
    capacity: np.ndarray
    base_rtt: np.ndarray
    loss: np.ndarray
    jitter: np.ndarray
    feedback: np.ndarray
    burst: np.ndarray
    buffer_scale: np.ndarray
    cross_traffic: np.ndarray | None = None
    vbr_scale: np.ndarray | None = None
    transport_seed: int | None = None

    def __post_init__(self):
        arrays = [
            self.capacity,
            self.base_rtt,
            self.loss,
            self.jitter,
            self.feedback,
            self.burst,
            self.buffer_scale,
        ]
        n = len(self.capacity)
        if n == 0 or any(a.shape != (n,) or not np.all(np.isfinite(a)) for a in arrays):
            raise ValueError("trace arrays must be finite, nonempty and equally sized")
        if np.any(self.capacity < 0) or np.any(self.base_rtt <= 0) or np.any(self.buffer_scale <= 0):
            raise ValueError("invalid trace capacity, RTT or buffer scale")
        if (
            np.any(self.jitter < 0)
            or np.any((self.loss < 0) | (self.loss > 1))
            or np.any((self.burst < 0) | (self.burst > 1))
        ):
            raise ValueError("invalid jitter/loss/burst")
        for key in ["cross_traffic", "vbr_scale"]:
            value = getattr(self, key)
            if value is not None:
                if (
                    value.shape != (n,)
                    or not np.all(np.isfinite(value))
                    or np.any(value < 0)
                    or (key == "vbr_scale" and np.any(value == 0))
                ):
                    raise ValueError("invalid transport trace profile")
                arrays.append(value)
        if self.transport_seed is not None and (
            type(self.transport_seed) is not int or self.transport_seed < 0
        ):
            raise ValueError("invalid transport seed")
        for a in arrays:
            a.setflags(write=False)


def make_trace(name: str, steps: int, seed: int) -> Trace:
    if name not in SCENARIOS or steps < 10:
        raise ValueError("unknown scenario or steps <10")
    rng = np.random.default_rng(seed)
    u = np.arange(steps) / steps
    scale = rng.uniform(0.85, 1.15)
    cap = np.full(steps, 2.8 * scale)
    rtt = np.full(steps, rng.uniform(35, 65))
    loss = np.full(steps, rng.uniform(0.002, 0.012))
    jitter = np.abs(rng.normal(0, 2, steps))
    feedback = np.ones(steps, dtype=bool)
    burst = np.zeros(steps)
    buffer = np.ones(steps)
    if name == "step":
        cap = np.select([u < 0.3, u < 0.65], [3.5, 1.1], default=2.5) * scale
    elif name == "ramp":
        cap = (1.0 + 3.0 * np.abs(2 * u - 1)) * scale
    elif name == "wifi":
        noise = np.zeros(steps)
        for i in range(1, steps):
            noise[i] = 0.9 * noise[i - 1] + rng.normal(0, 0.18)
        cap = np.clip(2.2 + noise + 0.5 * np.sin(u * 8 * np.pi), 0.8, 4) * scale
        loss += 0.025 * (np.sin(u * 13 * np.pi) > 0.85)
    elif name == "collapse":
        cap[(u >= 0.3) & (u < 0.7)] = 0.28 * scale
    elif name == "burst_loss":
        bad = False
        for i in range(steps):
            bad = rng.random() >= 0.18 if bad else rng.random() < 0.035
            if bad:
                loss[i], burst[i] = 0.3, 0.8
    elif name == "bufferbloat":
        cap[u >= 0.3] = 0.8 * scale
        buffer[:] = 8
    elif name == "handover":
        cap[(u >= 0.4) & (u < 0.5)] = 0.08
        rtt[u >= 0.4] += 160
        jitter[u >= 0.4] += np.abs(rng.normal(0, 20, sum(u >= 0.4)))
    elif name == "outage":
        cap[(u >= 0.35) & (u < 0.5)] = 0
        loss[(u >= 0.35) & (u < 0.5)] = 1
    elif name == "feedback_gap":
        feedback[(u >= 0.3) & (u < 0.55)] = False
        cap[(u >= 0.35) & (u < 0.6)] = 0.6
    elif name == "capacity_surge":
        cap[u >= 0.4] = 10 * scale
        rtt[u >= 0.4] = 12
    return Trace(name, cap, rtt, loss, jitter, feedback, burst, buffer)


def with_transport_profile(trace: Trace, seed: int) -> Trace:
    """Independent exogenous VBR/UDP background variation; no policy/test information."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 8593]))
    n = len(trace.capacity)
    vbr, load = np.zeros(n), np.zeros(n)
    for i in range(1, n):
        vbr[i] = 0.85 * vbr[i - 1] + rng.normal(0, 0.10)
        load[i] = 0.95 * load[i - 1] + rng.normal(0, 0.03)
    # Offered cross traffic does not vanish when bottleneck capacity collapses.
    reference = rng.uniform(1.8, 3.0)
    cross = reference * np.clip(rng.uniform(0.08, 0.22) + load, 0, 0.6)
    cross *= np.where((np.arange(n) // max(1, n // 6)) % 2, 1.8, 0.6)
    return replace(trace, cross_traffic=cross, vbr_scale=np.clip(np.exp(vbr), 0.5, 2.0), transport_seed=seed)


def simulation_trace(config, name: str, seed: int) -> Trace:
    trace = make_trace(name, config.steps, seed)
    return with_transport_profile(trace, seed) if config.backend == "packet_v2" else trace


def save_trace(trace, path):
    # Preserve the original seven-array NPZ contract when using legacy physics.
    np.savez_compressed(path, **{k: v for k, v in vars(trace).items() if v is not None})


def load_trace(path):
    with np.load(path, allow_pickle=False) as data:
        return Trace(
            **{
                k: str(data[k]) if k == "name" else int(data[k]) if k == "transport_seed" else data[k].copy()
                for k in data.files
            }
        )
