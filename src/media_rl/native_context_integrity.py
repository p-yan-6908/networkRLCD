"""Additive strict context telemetry types; frozen V5 inference semantics stay intact."""

from media_rl.native_context_replay import verify_native_context_evidence
from media_rl.native_policy_replay import number


def verify_native_context_integrity(evidence, base, long, base_sha, long_sha):
    for row in evidence["decisions"]:
        ctx = row["context_decision"]
        if (
            any(
                type(ctx[k]) is not bool
                for k in ["switched", "valid_causal_signal", "prediction_screen_not_safety_certificate"]
            )
            or ctx["prediction_screen_not_safety_certificate"] is not True
            or any(type(v) is not bool for v in ctx["alarms"].values())
            or type(ctx["consecutive_alarm_samples"]) is not int
            or ctx["consecutive_alarm_samples"] < 0
        ):
            raise ValueError("strict context boolean/counter telemetry required")
        if any(
            ctx[k] is not None and not number(ctx[k])
            for k in ["peak_bwe_bps", "rtcp_rtt_floor_ms", "elapsed_since_alarm_ms"]
        ):
            raise ValueError("finite context telemetry required")
    return verify_native_context_evidence(evidence, base, long, base_sha, long_sha)
