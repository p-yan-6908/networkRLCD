"""Causal single-bottleneck fluid simulator. No controller can observe a Trace."""

from dataclasses import dataclass, replace

import numpy as np

from .config import SimulatorConfig
from .scenarios import Trace


@dataclass(frozen=True)
class Action:
    bitrate_mbps: float
    fec: float
    low_latency: bool

    @property
    def wire_mbps(self):
        return self.bitrate_mbps * (1 + self.fec)


def action_space(config: SimulatorConfig):
    return tuple(
        Action(b, f, mode) for b in config.bitrates for f in config.fec_levels for mode in [False, True]
    )


@dataclass(frozen=True)
class Telemetry:
    throughput_mbps: float = 0.6
    rtt_ms: float = 50.0
    loss: float = 0.0
    jitter_ms: float = 0.0
    delay_trend_ms: float = 0.0
    last_bitrate_mbps: float = 0.15
    last_fec: float = 0.0
    last_low_latency: bool = True
    feedback_age_s: float = 0.0
    valid: bool = False

    def vector(self):
        return np.array(
            [
                self.throughput_mbps / 4,
                self.rtt_ms / 200,
                self.loss,
                self.jitter_ms / 50,
                self.delay_trend_ms / 100,
                self.last_bitrate_mbps / 4,
                self.last_fec,
                float(self.last_low_latency),
                self.feedback_age_s,
                float(self.valid),
            ],
            dtype=float,
        )

    def finite(self):
        return bool(np.all(np.isfinite(self.vector())))


OBS_DIM = 10


class MediaEnvironment:
    def __init__(self, config: SimulatorConfig, trace: Trace):
        if len(trace.capacity) != config.steps:
            raise ValueError("trace length differs from configured horizon")
        self.config, self.trace = config, trace
        self.actions = action_space(config)
        self.reset()

    def reset(self):
        self.t, self.queue = 0, 0.0
        self.last = Action(self.config.bitrates[0], self.config.fec_levels[0], True)
        self.feedback = []
        self.last_feedback_end = 0
        self.observation = Telemetry(last_bitrate_mbps=self.last.bitrate_mbps, last_fec=self.last.fec)
        return self.observation

    def preview(self, action_index: int):
        """Pure evaluation/training oracle; NEVER passed to a controller."""
        if self.t >= self.config.steps:
            raise RuntimeError("episode has terminated")
        if type(action_index) not in (int, np.int64, np.int32) or not 0 <= action_index < len(self.actions):
            raise ValueError("invalid action index")
        a, c, tr, t = self.actions[action_index], self.config, self.trace, self.t
        arrivals = a.wire_mbps * c.dt_s
        capacity = float(tr.capacity[t])
        service = min(self.queue + arrivals, capacity * c.dt_s)
        unbounded = max(0.0, self.queue + arrivals - service)
        overflow = max(0.0, unbounded - c.queue_mbit * tr.buffer_scale[t])
        queue = unbounded - overflow
        # Fluid tail drop assigned to current arrivals; backlog losses are approximated.
        congestion_loss = min(1.0, overflow / max(arrivals, 1e-12))
        if capacity == 0:
            congestion_loss = 1.0
        raw_loss = 1 - (1 - congestion_loss) * (1 - float(tr.loss[t]))
        recovery = c.fec_efficiency * (1 - 0.7 * tr.burst[t]) * a.fec / (1 + a.fec)
        residual_loss = float(max(0, raw_loss - recovery) / max(1 - recovery, 1e-9))
        if capacity == 0:
            residual_loss = 1.0
        queue_ms = 1000 * (self.queue + queue) / (2 * max(capacity, 0.01))
        latency = float(
            tr.base_rtt[t] / 2 + queue_ms + tr.jitter[t] + (8 if a.low_latency else 25) + 20 * a.fec
        )
        # Uniform frame completion times over one control interval, centered at latency.
        deadline_miss = float(np.clip(0.5 + (latency - c.deadline_ms) / (1000 * c.dt_s), 0, 1))
        if capacity == 0:
            deadline_miss = 1.0
        media_service = min(a.bitrate_mbps, service / c.dt_s / (1 + a.fec))
        goodput = media_service * (1 - residual_loss) * (1 - deadline_miss)
        switch = abs(np.log(a.bitrate_mbps / self.last.bitrate_mbps))
        quality = np.log1p(a.bitrate_mbps / 0.15) * (0.82 if a.low_latency else 1.0)
        qoe = float(
            quality * (1 - residual_loss) * (1 - deadline_miss)
            - c.latency_weight * min(latency / c.deadline_ms, 10)
            - c.loss_weight * residual_loss
            - c.deadline_weight * deadline_miss
            - c.switch_weight * switch
        )
        safe = latency <= c.safe_latency_ms and residual_loss <= c.safe_loss and capacity > 0
        return dict(
            qoe=qoe,
            latency_ms=latency,
            raw_loss=float(raw_loss),
            residual_loss=residual_loss,
            deadline_miss=deadline_miss,
            goodput_mbps=float(goodput),
            bitrate_mbps=a.bitrate_mbps,
            wire_mbps=a.wire_mbps,
            fec=a.fec,
            low_latency=int(a.low_latency),
            switch_magnitude=float(switch),
            safe=int(safe),
            queue_mbit=float(queue),
            capacity_mbps=capacity,
            service_mbit=float(service),
            overflow_mbit=float(overflow),
            queue_delay_ms=float(queue_ms),
        )

    def step(self, action_index: int):
        result = self.preview(action_index)
        a, t = self.actions[action_index], self.t
        rtt = float(self.trace.base_rtt[t] + 2 * result["queue_delay_ms"] + self.trace.jitter[t])
        measure = Telemetry(
            throughput_mbps=result["service_mbit"] / self.config.dt_s * (1 - self.trace.loss[t]),
            rtt_ms=rtt,
            loss=result["raw_loss"],
            jitter_ms=float(self.trace.jitter[t]),
            delay_trend_ms=rtt - self.observation.rtt_ms,
            valid=True,
        )
        self.feedback.append(measure if self.trace.feedback[t] else None)
        self.queue, self.last = result["queue_mbit"], a
        self.t += 1
        index = self.t - self.config.feedback_delay_steps
        if index >= 0 and self.feedback[index] is not None:
            self.observation = self.feedback[index]
            self.last_feedback_end = index + 1
        self.observation = replace(
            self.observation,
            last_bitrate_mbps=a.bitrate_mbps,
            last_fec=a.fec,
            last_low_latency=a.low_latency,
            feedback_age_s=(self.t - self.last_feedback_end) * self.config.dt_s,
        )
        return self.observation, result["qoe"], self.t == self.config.steps, result
