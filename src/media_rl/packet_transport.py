"""Event-time media packets in a shared drop-tail bottleneck.

Synthetic systematic/FEC byte repair and frame-quality proxies, NOT a codec,
TCP implementation, packet capture replay or RFC-compliant network stack.
All randomness is indexed by trace/time/frame/packet, so previews are pure.
"""

import hashlib
import heapq
from collections import deque
from dataclasses import dataclass, field, replace

import numpy as np


@dataclass(frozen=True)
class Packet:
    frame: int | None
    ordinal: int
    wire: float
    payload: float
    parity: bool
    sent: float


@dataclass
class Frame:
    born: float
    source: float
    quality: float
    efficiency: float
    received: float = 0.0
    repair: float = 0.0
    lost: float = 0.0


@dataclass
class TransportState:
    queue: deque = field(default_factory=deque)
    queued: float = 0.0
    events: list = field(default_factory=list)
    frames: dict = field(default_factory=dict)
    frame_index: int = 0
    cross_index: int = 0
    sequence: int = 0
    receive_floor: float = 0.0
    last_rtt: float = 50.0

    def clone(self):
        # Packets and event tuples are immutable; only frame counters/head debt change.
        return replace(
            self,
            queue=deque(self.queue),
            events=list(self.events),
            frames={k: replace(v) for k, v in self.frames.items()},
        )


def uniform(seed, epoch, frame, ordinal, salt):
    token = f"{seed}:{epoch}:{frame}:{ordinal}:{salt}".encode()
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "little") / 2**64


class PacketTransport:
    def __init__(self, config, trace):
        self.config, self.trace = config, trace
        self.state = TransportState()

    @staticmethod
    def _event(state, at, kind, value):
        priority = {"receive": 0, "send": 1, "deadline": 2}[kind]
        heapq.heappush(state.events, (at, priority, state.sequence, kind, value))
        state.sequence += 1

    def _emit_frames(self, state, action, t, end):
        c, tr = self.config, self.trace
        payload = c.packet_bytes * 8 / 1e6
        header = c.packet_header_bytes * 8 / 1e6
        scale = 1.0 if tr.vbr_scale is None else float(tr.vbr_scale[t])
        while state.frame_index / c.fps < end - 1e-10:
            fid = state.frame_index
            born = fid / c.fps
            state.frame_index += 1
            # Larger periodic intra frames; mean size stays approximately nominal.
            intra = (2.5 if fid % (2 * c.fps) == 0 else 1.0) / (1 + 1.5 / (2 * c.fps))
            source = action.bitrate_mbps / c.fps * scale * intra
            frame = Frame(
                born,
                source,
                float(np.log1p(action.bitrate_mbps / 0.15)) * (0.82 if action.low_latency else 1.0),
                c.fec_efficiency * (1 - 0.7 * float(tr.burst[t])),
            )
            state.frames[fid] = frame
            self._event(state, born + c.deadline_ms / 1000, "deadline", fid)
            ready = born + ((8 if action.low_latency else 25) + 20 * action.fec) / 1000
            ordinal, offset = 0, 0.0
            for parity, amount in [(False, source), (True, source * action.fec)]:
                while amount > 1e-12:
                    chunk = min(amount, payload)
                    wire = chunk + header
                    sent = ready + offset / (action.wire_mbps * c.pacing_factor)
                    self._event(state, sent, "send", Packet(fid, ordinal, wire, chunk, parity, sent))
                    offset += wire
                    amount -= chunk
                    ordinal += 1

    def _emit_cross(self, state, t, end):
        c, tr = self.config, self.trace
        rate = 0.0 if tr.cross_traffic is None else float(tr.cross_traffic[t])
        payload = c.packet_bytes * 8 / 1e6
        while state.cross_index * c.cross_traffic_interval_s < end - 1e-10:
            at = state.cross_index * c.cross_traffic_interval_s
            state.cross_index += 1
            amount = rate * c.cross_traffic_interval_s
            ordinal = 0
            while amount > 1e-12:
                wire = min(amount, payload)
                self._event(state, at, "send", Packet(None, ordinal, wire, 0.0, False, at))
                amount -= wire
                ordinal += 1

    @staticmethod
    def _lose(state, packet):
        frame = state.frames.get(packet.frame)
        if frame is not None and not packet.parity:
            frame.lost += packet.payload

    def _close(self, state, fid, at, completed):
        frame = state.frames.pop(fid, None)
        if frame is None:
            return
        c = self.config
        recovered = min(max(0.0, frame.source - frame.received), frame.repair * frame.efficiency)
        fraction = float(np.clip((frame.received + recovered) / frame.source, 0, 1))
        residual = float(np.clip((frame.lost - recovered) / frame.source, 0, 1))
        late = float(np.clip(1 - fraction - residual, 0, 1))
        latency = max(0.0, (at - frame.born) * 1000)
        qoe = (
            frame.quality * fraction
            - c.latency_weight * min(latency / c.deadline_ms, 10)
            - c.loss_weight * residual
            - c.deadline_weight * late
        )
        completed.append(
            dict(
                frame_id=fid,
                born_s=frame.born,
                qoe=qoe,
                latency=latency,
                raw=min(1.0, frame.lost / frame.source),
                residual=residual,
                late=late,
                goodput=frame.source * fraction,
                safe=latency <= c.safe_latency_ms + 1e-8 and residual <= c.safe_loss and late <= c.safe_loss,
            )
        )

    def advance(self, action, last, t):
        """Return a branched state, outcomes and receiver statistics; no mutation."""
        c, tr = self.config, self.trace
        state = self.state.clone()
        start, end = t * c.dt_s, (t + 1) * c.dt_s
        capacity = float(tr.capacity[t])
        limit = c.queue_mbit * float(tr.buffer_scale[t])
        before = state.queued
        offered = offered_own = service = service_own = overflow = cross_service = 0.0
        received_wire = source_offered = parity_offered = headers_offered = 0.0
        rtts, completed = [], []
        self._emit_frames(state, action, t, end)
        self._emit_cross(state, t, end)
        while state.queue and state.queued > limit + 1e-12:
            packet, debt = state.queue.pop()
            state.queued -= debt
            overflow += debt
            self._lose(state, packet)
        now = start
        while now < end - 1e-12 or (state.events and state.events[0][0] <= end + 1e-12):
            event_time = min(end, state.events[0][0]) if state.events else end
            if state.queue and capacity > 0 and now < event_time - 1e-12:
                packet, debt = state.queue[0]
                amount = min(debt, capacity * (event_time - now))
                duration = amount / capacity
                now += duration
                state.queued = max(0.0, state.queued - amount)
                service += amount
                if packet.frame is None:
                    cross_service += amount
                else:
                    service_own += amount
                if amount >= debt - 1e-12:
                    state.queue.popleft()
                    if packet.frame is not None:
                        seed = tr.transport_seed or 0
                        lost = uniform(seed, t, packet.frame, packet.ordinal, "loss") < tr.loss[t]
                        if lost:
                            self._lose(state, packet)
                        else:
                            jitter = (
                                float(tr.jitter[t])
                                * 2
                                * uniform(seed, t, packet.frame, packet.ordinal, "pdv")
                            )
                            # Ordered forward delivery; jitter cannot reorder this single path.
                            arrival = max(
                                now + (float(tr.base_rtt[t]) / 2 + jitter) / 1000,
                                state.receive_floor + duration,
                            )
                            state.receive_floor = arrival
                            rtt = (now - packet.sent) * 1000 + float(tr.base_rtt[t]) + 2 * jitter
                            self._event(state, arrival, "receive", (packet, rtt))
                else:
                    state.queue[0] = (packet, debt - amount)
                continue
            now = max(now, event_time)
            if not state.events or state.events[0][0] > end + 1e-12:
                break
            _, _, _, kind, value = heapq.heappop(state.events)
            if kind == "send":
                packet = value
                offered += packet.wire
                offered_own += packet.wire if packet.frame is not None else 0.0
                if packet.frame is not None:
                    source_offered += packet.payload if not packet.parity else 0.0
                    parity_offered += packet.payload if packet.parity else 0.0
                    headers_offered += packet.wire - packet.payload
                if state.queued + packet.wire <= limit + 1e-12:
                    state.queue.append((packet, packet.wire))
                    state.queued += packet.wire
                else:
                    overflow += packet.wire
                    self._lose(state, packet)
            elif kind == "receive":
                packet, rtt = value
                received_wire += packet.wire
                rtts.append(rtt)
                frame = state.frames.get(packet.frame)
                if frame is not None:
                    if packet.parity:
                        frame.repair += packet.payload
                    else:
                        frame.received += packet.payload
                    if frame.received + frame.repair * frame.efficiency >= frame.source - 1e-10:
                        self._close(state, packet.frame, now, completed)
            else:
                self._close(state, value, now, completed)
        if rtts:
            state.last_rtt = float(np.mean(rtts))

        def mean(key, default=0.0):
            return float(np.mean([r[key] for r in completed])) if completed else default

        switch = abs(np.log(action.bitrate_mbps / last.bitrate_mbps))
        # Credit the actual cohort outcomes, never hypothetical current-action quality.
        qoe = sum(r["qoe"] for r in completed) / (c.fps * c.dt_s) - c.switch_weight * switch
        latency = mean("latency", 0.0)
        raw_loss, residual, late = mean("raw"), mean("residual"), mean("late")
        pending = len(state.frames)
        result = dict(
            qoe=float(qoe),
            latency_ms=latency,
            raw_loss=raw_loss,
            residual_loss=residual,
            deadline_miss=late,
            goodput_mbps=sum(r["goodput"] for r in completed) / c.dt_s,
            bitrate_mbps=action.bitrate_mbps,
            wire_mbps=offered_own / c.dt_s,
            fec=action.fec,
            low_latency=int(action.low_latency),
            switch_magnitude=float(switch),
            safe=int(capacity > 0 and all(r["safe"] for r in completed)),
            queue_mbit=state.queued,
            capacity_mbps=capacity,
            service_mbit=service_own,
            overflow_mbit=overflow,
            queue_delay_ms=1000 * state.queued / max(capacity, 0.01),
            offered_mbit=offered,
            source_offered_mbit=source_offered,
            parity_offered_mbit=parity_offered,
            headers_offered_mbit=headers_offered,
            total_service_mbit=service,
            queue_before_mbit=before,
            cross_service_mbit=cross_service,
            cross_traffic_mbps=0.0 if tr.cross_traffic is None else float(tr.cross_traffic[t]),
            frames_completed=len(completed),
            frames_pending=pending,
            terminal_censored_frames=pending if t + 1 == c.steps else 0,
        )
        measure = dict(
            throughput_mbps=received_wire / c.dt_s,
            rtt_ms=state.last_rtt,
            loss=raw_loss,
            jitter_ms=float(np.std(rtts)) if rtts else 0.0,
        )
        return state, result, measure, completed
