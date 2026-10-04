"""Scalar-rate mechanism probe, not a learned policy or a safety certificate.

Actual scalar caps stay in raw sender features. ONLY the never-actuated legacy
repair shadow receives an explicit floor-cap projection to its seven-cap ABI.
"""

from math import floor

from .native_observations import CAPS
from .native_protocol import finite, require
from .native_repair5_policy import CONFIG as CONFIG
from .native_repair5_policy import RepairPolicy as LegacyShadow
from .native_repair5_policy import SenderContentEncoder as SenderContentEncoder
from .native_repair5_policy import exploration_cap as legacy_exploration

CONTROL_ABI = "native_dense_diagnostic_control_v1"
ACTUATION_ABI = "native_scalar_encoder_cap_playout_v1"
CAP_DOMAIN = (150000, 4000000)
BEHAVIORS = ("bwe", "bwe-continuous", "fixed450", "gcc")


def scalar_cap(value):
    require(
        type(value) in (int, float)
        and finite(value)
        and value == floor(value)
        and CAP_DOMAIN[0] <= value <= CAP_DOMAIN[1],
        "bounded integer scalar encoder cap required",
    )
    return int(value)


def legacy_cap_projection(value):
    cap = scalar_cap(value)
    return max(c for c in CAPS if c <= cap)


def exploration_cap(behavior, step, seed, features):
    require(
        behavior in BEHAVIORS
        and len(features) == 16
        and all(finite(x) and x >= 0 for x in features)
        and features[9] in (0, 1),
        "declared dense diagnostic/sender features required",
    )
    if behavior == "fixed450":
        return 450000
    if behavior == "bwe-continuous" and features[9] == 1:
        return max(
            CAP_DOMAIN[0], min(CAP_DOMAIN[1], floor(CONFIG["fallback_headroom"] * (features[0] * 4000000)))
        )
    return legacy_exploration("bwe" if behavior == "bwe-continuous" else behavior, step, seed, features)


class RepairPolicy:
    """Non-actuated no-model V5 shadow with declared own-cap projection."""

    def __init__(self, bundle=None):
        require(bundle is None, "dense mechanism probe must not load a learned actor")
        self.shadow = LegacyShadow()

    def acknowledge(self, cap, now):
        return self.shadow.acknowledge(legacy_cap_projection(cap), now)

    def observe(self, observation, feedback=None):
        features = list(observation["features"])
        actual = scalar_cap(round(features[7] * 4000000))
        require(abs(features[7] * 4000000 - actual) < 0.01, "actual scalar cap not integral")
        projected = legacy_cap_projection(actual)
        features[7] = projected / 4000000
        result = self.shadow.observe(dict(observation, features=features), feedback)
        result.update(
            shadow_only=True,
            actual_scalar_cap_bps=actual,
            shadow_projected_cap_bps=projected,
            shadow_projection="legacy_floor_cap",
        )
        require(
            result["fallback"] and not result["learned_departure"],
            "diagnostic shadow cannot earn learned credit",
        )
        return result


def executed_learned_action(decision, cap, controller="explore"):
    return False


def validate_repair_bundle(bundle):
    raise ValueError("dense diagnostic has no trained-model ABI")
