"""Stateful telemetry-only policy encoder; risk features remain unchanged."""

import numpy as np


class PolicyFeatures:
    def __init__(self, kind="telemetry", dt_s=0.1):
        if kind not in {"telemetry", "history_v2"}:
            raise ValueError("unknown policy features")
        self.kind = kind
        self.dimension = 10 if kind == "telemetry" else 16
        self.min_rtt = float("inf")
        self.throughput = self.loss = self.trend = 0.0
        self.previous_bitrate = None
        self.initialized = False
        self.dt_s, self.clock, self.last_report_time = dt_s, 0.0, -float("inf")

    def encode(self, obs):
        base = np.clip(obs.vector(), -12, 12)
        if self.kind == "telemetry":
            return base
        self.clock += self.dt_s
        report_time = self.clock - obs.feedback_age_s
        if obs.valid and obs.finite() and report_time > self.last_report_time + 1e-8:
            self.last_report_time = report_time
            self.min_rtt = min(self.min_rtt, obs.rtt_ms)
            weight = 0.25 if self.initialized else 1.0
            self.throughput += weight * (obs.throughput_mbps - self.throughput)
            self.loss += weight * (obs.loss - self.loss)
            self.trend += weight * (obs.delay_trend_ms - self.trend)
            self.initialized = True
        excess = max(0.0, obs.rtt_ms - self.min_rtt) if self.initialized else 0.0
        change = 0.0 if self.previous_bitrate is None else obs.last_bitrate_mbps - self.previous_bitrate
        self.previous_bitrate = obs.last_bitrate_mbps
        extra = [
            excess / 200,
            self.throughput / 4,
            self.loss,
            self.trend / 100,
            (obs.throughput_mbps - self.throughput) / 4 if self.initialized else 0.0,
            change / 4,
        ]
        return np.clip(np.concatenate([base, extra]), -12, 12)


def bundle_feature_kind(bundle):
    return (
        getattr(bundle, "metadata", {})
        .get("config", {})
        .get("training", {})
        .get("policy_features", "telemetry")
    )
