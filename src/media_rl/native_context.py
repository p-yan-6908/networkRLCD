"""Frozen sender-only context/horizon switch; never an override of either risk screen."""

import math

from media_rl.native_observations import FEATURE_LIMITS, FEATURE_SCALES

CONTEXT_CONTROLLER = "native_causal_context_horizon_v5"
CONTEXT_PROTOCOL = dict(
    abi=CONTEXT_CONTROLLER,
    window_ms=2000,
    max_gap_ms=1000,
    bwe_drop_fraction=0.2,
    offered_over_bwe_ratio=1.05,
    rtt_rise_ms=30,
    rtt_max_observed_age_ms=1000,
    packet_send_delay_ms=25,
    consecutive_alarm_samples=2,
    long_hold_after_alarm_ms=2000,
    clean_recovery_ms=1000,
    risk_cutoff=0.5,
    disagreement_cutoff=0.2,
    default_horizon=3,
    deterioration_horizon=20,
    no_queue_capacity_pixel_or_phase_inputs=True,
    prediction_screen_not_safety_certificate=True,
)


class NativeContextSwitch:
    def __init__(self):
        self.reset()

    def reset(self):
        self.last = None
        self.stream = None
        self.window = []
        self.mode = "base"
        self.bad = 0
        self.alarm_at = None
        self.clean_at = None

    def observe(self, features, sample_ms, stream_key):
        if (
            type(sample_ms) not in (int, float)
            or not math.isfinite(sample_ms)
            or sample_ms < 0
            or (self.last is not None and sample_ms <= self.last)
        ):
            raise ValueError("strictly increasing context clock required")
        if (
            not isinstance(stream_key, str)
            or not stream_key
            or len(features) != 16
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= limit
                for v, limit in zip(features, FEATURE_LIMITS, strict=True)
            )
            or any(features[i] not in (0, 1) for i in range(8, 15))
        ):
            raise ValueError("exact native context features/stream required")
        previous = self.mode
        gap = self.last is not None and sample_ms - self.last > CONTEXT_PROTOCOL["max_gap_ms"]
        if self.stream is not None and (self.stream != stream_key or gap):
            self.reset()
        self.stream = stream_key
        self.last = sample_ms
        now = sample_ms
        p = CONTEXT_PROTOCOL
        self.window = [r for r in self.window if now - r[0] <= p["window_ms"]]
        bwe = features[0] * FEATURE_SCALES[0] * 1e6 if features[9] == 1 else None
        offered = features[3] * FEATURE_SCALES[3] * 1e6 if features[12] == 1 else None
        rtt = (
            features[1] * FEATURE_SCALES[1]
            if features[10] == features[11] == 1
            and features[2] * FEATURE_SCALES[2] <= p["rtt_max_observed_age_ms"]
            else None
        )
        delay = features[6] * FEATURE_SCALES[6] if features[14] == 1 else None
        self.window.append((now, bwe, rtt))
        peak = max((r[1] for r in self.window if r[1] is not None), default=0.0)
        floor = min((r[2] for r in self.window if r[2] is not None), default=None)
        alarms = dict(
            bwe_drop_under_load=bwe is not None
            and offered is not None
            and peak > 0
            and bwe <= peak * (1 - p["bwe_drop_fraction"])
            and offered >= bwe * p["offered_over_bwe_ratio"],
            rtcp_rtt_rise=rtt is not None and floor is not None and rtt - floor >= p["rtt_rise_ms"],
            packet_send_delay=delay is not None and delay >= p["packet_send_delay_ms"],
        )
        alarm = any(alarms.values())
        valid = (bwe is not None and offered is not None) or rtt is not None or delay is not None
        if alarm:
            self.bad += 1
            self.alarm_at = now
            self.clean_at = None
        else:
            self.bad = 0
            if valid:
                if self.clean_at is None:
                    self.clean_at = now
            else:
                self.clean_at = None
        if self.mode == "base" and self.bad >= p["consecutive_alarm_samples"]:
            self.mode = "long"
        if (
            self.mode == "long"
            and not alarm
            and valid
            and self.alarm_at is not None
            and now - self.alarm_at >= p["long_hold_after_alarm_ms"]
            and self.clean_at is not None
            and now - self.clean_at >= p["clean_recovery_ms"]
        ):
            self.mode = "base"
        return dict(
            selected_model=self.mode,
            switched=self.mode != previous,
            alarms=alarms,
            consecutive_alarm_samples=self.bad,
            valid_causal_signal=valid,
            peak_bwe_bps=peak,
            rtcp_rtt_floor_ms=floor,
            elapsed_since_alarm_ms=None if self.alarm_at is None else now - self.alarm_at,
            reason="alarm_long"
            if self.mode == "long" and alarm
            else "hold_long"
            if self.mode == "long"
            else "clear_to_short"
            if previous == "long"
            else "short_default",
            prediction_screen_not_safety_certificate=True,
        )
