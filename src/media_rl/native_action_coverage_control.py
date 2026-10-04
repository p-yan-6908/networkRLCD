"""Legal-role scalar coverage. Fixed exploration is NEVER learned credit."""

from .native_dense_control import (
    ACTUATION_ABI,
    CAP_DOMAIN,
    CONFIG,
    RepairPolicy,
    SenderContentEncoder,
    executed_learned_action,
)
from .native_protocol import finite, require

COVERAGE_CAPS = (400000, 450000, 500000)
BEHAVIORS = ("fixed400", "fixed450", "fixed500")


def exploration_cap(behavior, step, seed, features):
    require(
        behavior in BEHAVIORS
        and len(features) == 16
        and all(finite(v) and v >= 0 for v in features)
        and features[9] in (0, 1),
        "declared exact-cap exploration and causal sender features required",
    )
    return COVERAGE_CAPS[BEHAVIORS.index(behavior)]


__all__ = [
    "ACTUATION_ABI",
    "CAP_DOMAIN",
    "CONFIG",
    "RepairPolicy",
    "SenderContentEncoder",
    "executed_learned_action",
    "exploration_cap",
    "COVERAGE_CAPS",
    "BEHAVIORS",
]
