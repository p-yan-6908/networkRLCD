"""Three-arm IID instrument sampler; no learned policy or controller ABI change."""

import copy
import hashlib
import math

from .native_protocol import finite, require

ABI = "native_actuator_instrument_v1"
RATIOS = (0.65, 0.85, 1.05)
CAP_DOMAIN = (150000, 4000000)
HOLD_MS = 3000
MAX_EPOCHS = 6
WINDOW_MS = (1800, 2600)
DEADLINE_MS = 150


def assigned_arm(seed, epoch):
    require(
        type(seed) is int and 0 <= seed <= 2**32 - 1 and type(epoch) is int and epoch >= 0,
        "bounded instrument seed/epoch required",
    )
    # Rejection removes modulo bias; unlike permutations, every arm remains
    # possible conditional on the entire observed action history.
    for attempt in range(100):
        digest = hashlib.sha256(f"{ABI}:{seed}:{epoch}:{attempt}".encode()).digest()
        draw = int.from_bytes(digest[:4], "big")
        if draw < 2**32 - 1:
            return draw % 3
    raise ValueError("instrument hash rejection exhausted")


def status(value, *, fraction=False):
    valid = finite(value) and value >= 0 and (not fraction or value <= 1)
    return dict(
        status="absent" if value is None else "present" if valid else "invalid",
        value=value if valid else None,
    )


class InstrumentSampler:
    def __init__(self, seed):
        assigned_arm(seed, 0)
        self.seed = seed
        self.current = None
        self.ack = None
        self.last_ms = None
        self.previous = None
        self.last_rtt = None

    def observe(self, observation, encoder, meter, link):
        now = observation["sample_ms"]
        require(
            finite(now) and now >= 0 and (self.last_ms is None or now > self.last_ms),
            "strictly causal instrument sample clock",
        )
        self.last_ms = now
        raw = observation["raw_source"]
        bwe = raw["bwe_bps"]
        rtt = raw["rtcp_rtt_s"]
        fields = encoder["fields"]
        previous = self.previous
        qp = size = actual = send = None
        if previous and raw["stream_key"] == previous["observation"]["raw_source"]["stream_key"]:
            dt = now - previous["observation"]["sample_ms"]
            old_fields = previous["encoder"]["fields"]
            frames = fields["framesEncoded"]["value"]
            old_frames = old_fields["framesEncoded"]["value"]
            delta_frames = frames - old_frames if finite(frames) and finite(old_frames) else None
            if 0 < dt <= 1000:
                before_bytes = previous["observation"]["raw_source"]["bytes_sent"]
                if finite(raw["bytes_sent"]) and finite(before_bytes) and raw["bytes_sent"] >= before_bytes:
                    send = (raw["bytes_sent"] - before_bytes) * 8000 / dt
                if meter["status"] == previous["meter"]["status"] == "active":
                    delta = meter["total_bytes"] - previous["meter"]["total_bytes"]
                    if delta >= 0:
                        actual = delta * 8000 / dt
                        count = meter["total_frames"] - previous["meter"]["total_frames"]
                        size = delta / count if count > 0 else None
                if finite(delta_frames) and delta_frames > 0:
                    q, oq = fields["qpSum"]["value"], old_fields["qpSum"]["value"]
                    if finite(q) and finite(oq) and q >= oq:
                        qp = (q - oq) / delta_frames
        trend = (rtt - self.last_rtt) * 1000 if finite(rtt) and finite(self.last_rtt) else None
        if finite(rtt):
            self.last_rtt = rtt
        context = dict(
            bwe_bps=status(bwe),
            rtt_ms=status(rtt * 1000 if finite(rtt) else None),
            rtt_trend_ms=dict(status="present" if finite(trend) else "absent", value=trend),
            loss_fraction=link["loss_fraction"],
            jitter_ms=link["jitter_ms"],
            previous_requested_bps=status(raw["encoder_cap_bps"]),
            encoder_target_bps=copy.deepcopy(fields["targetBitrate"]),
            actual_encoder_bps=status(actual),
            actual_send_bps=status(send),
            qp=status(qp),
            mean_encoded_frame_bytes=status(size),
            complexity=copy.deepcopy(observation["content_features"]),
            previous_action=None if self.current is None else self.current["arm"],
            rtt_age_known=bool(observation["features"][11]),
        )
        self.previous = dict(
            observation=copy.deepcopy(observation), encoder=copy.deepcopy(encoder), meter=copy.deepcopy(meter)
        )
        epoch = 0 if self.current is None else self.current["epoch"] + 1
        ready = self.current is None or self.ack is not None and now >= self.ack + HOLD_MS
        if ready and epoch < MAX_EPOCHS and finite(bwe) and bwe > 0:
            arm = assigned_arm(self.seed, epoch)
            caps = [max(CAP_DOMAIN[0], min(CAP_DOMAIN[1], math.floor(r * bwe + 0.5))) for r in RATIOS]
            self.current = dict(
                abi=ABI,
                seed=self.seed,
                epoch=epoch,
                arm=arm,
                ratio=RATIOS[arm],
                assignment_ms=now,
                base_bwe_bps=bwe,
                requested_bps=caps[arm],
                candidates_bps=caps,
                clipped_or_aliased=len(set(caps)) != 3,
                propensity=1 / 3,
                propensities=[1 / 3] * 3,
                state=context,
            )
            self.ack = None
        return copy.deepcopy(self.current)

    def acknowledge(self, now, applied_bps):
        if self.current is None:
            return
        require(
            finite(now)
            and now >= self.current["assignment_ms"]
            and applied_bps == self.current["requested_bps"],
            "owned instrument cap acknowledgment required",
        )
        if self.ack is None:
            self.ack = now  # unchanged caps STILL begin a randomized assignment, not a new physical action
