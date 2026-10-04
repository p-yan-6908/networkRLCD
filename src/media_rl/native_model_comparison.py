"""Independent two-model shadow comparison; actual source trajectories stay factual."""

import re

import numpy as np

from media_rl.native_learning import NativePolicy
from media_rl.native_policy_replay import number, verify_native_live_evidence


def verify_native_model_comparison(sender, active, other, active_sha, other_sha):
    if (
        not re.fullmatch(r"[0-9a-f]{64}", other_sha)
        or sender["shadow_model_sha256"] != other_sha
        or sender["common_two_model_shadow"] is not True
    ):
        raise ValueError("frozen common two-model shadow required")
    result = verify_native_live_evidence(sender, active, active_sha)
    policy = NativePolicy(other)
    worst = 0.0
    times = []
    for step in sender["decisions"]:
        base = step["policy_decision"]
        shadow = step["shadow_policy_decision"]
        expected = policy.decide(np.asarray(base["history"]))
        if set(shadow) != {"history", *expected} or shadow["history"] != base["history"]:
            raise ValueError("shadow native history/fields mismatch")
        for field in [
            "action_index",
            "native_action_index",
            "encoder_max_bitrate_bps",
            "receiver_jitter_buffer_target_ms",
            "fallback",
        ]:
            if type(shadow[field]) is not type(expected[field]) or shadow[field] != expected[field]:
                raise ValueError("shadow native action/fallback mismatch")
        for field in ["q_values", "predicted_frame_miss", "risk_disagreement"]:
            values = np.asarray(shadow[field])
            error = float(np.max(np.abs(values - expected[field])))
            if values.shape != (7,) or not np.isfinite(values).all() or error > 1e-10:
                raise ValueError("shadow native score mismatch")
            worst = max(worst, error)
        elapsed = step["shadow_inference_ms"]
        total = step["inference_ms"] + elapsed
        if not number(elapsed) or not 0 <= total <= step["ack_ms"] - step["observation"]["sample_ms"] + 1e-6:
            raise ValueError("two-model shadow clock mismatch")
        times.append(total)
    result.update(
        verified_secondary_decisions=len(times),
        max_secondary_score_error=worst,
        total_two_model_ms_p99=float(np.quantile(times, 0.99)),
        native_promoted_or_SOTA=False,
    )
    return result
