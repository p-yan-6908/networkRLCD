"""Seeded training-only hold exploration, never learned or safety-qualified control."""

from .native_dense_control import CONFIG as CONFIG
from .native_protocol import finite, require

ABI = "native_randomized_cap_hold_control_v1"
CAPS = (300000, 450000, 900000)
BEHAVIORS = ("random-hold-a", "random-hold-b", "fixed450")
EPOCH_STEPS = 8
COHORT_START_MS = 200
COHORT_END_MS = 600
DEADLINE_MS = 150


def assignment(behavior, epoch, seed):
    require(
        behavior in BEHAVIORS
        and type(epoch) is int
        and 0 <= epoch <= 512
        and type(seed) is int
        and 0 <= seed <= 0xFFFFFFFF,
        "bounded declared training hold/epoch/seed required",
    )
    if behavior == "fixed450":
        return 450000
    # Counter-based uint32 mixer; aliases intentionally have identical assignments.
    # Schedule is fixed before labels and depends on no sender/evaluation feature.
    x = (seed ^ (((epoch + 1) * 0x9E3779B9) & 0xFFFFFFFF)) & 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x7FEB352D) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x846CA68B) & 0xFFFFFFFF
    x ^= x >> 16
    return CAPS[x % len(CAPS)]


def exploration_cap(behavior, step, seed, features):
    require(
        type(step) is int
        and 0 <= step <= EPOCH_STEPS * 512
        and len(features) == 16
        and all(finite(v) and v >= 0 for v in features)
        and features[9] in (0, 1),
        "causal sender features and bounded exploration step required",
    )
    return assignment(behavior, step // EPOCH_STEPS, seed)
