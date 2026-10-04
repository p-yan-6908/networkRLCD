"""V4 defers unsafe/unavailable learned control to native Chrome GCC.

The 4 Mb/s ceiling is not a requested send rate or safety certificate. Chrome's
congestion controller remains responsible for transport. All learned V3 screens,
causal state, support, dwell and actual-action checks remain unchanged.
"""

from copy import deepcopy

from .native_observations import CAPS
from .native_protocol import require
from .native_repair3_policy import CONFIG as CORE_CONFIG
from .native_repair3_policy import FEATURES as FEATURES
from .native_repair3_policy import INPUT_DIM as INPUT_DIM
from .native_repair3_policy import REPAIR_ABI as CORE_ABI
from .native_repair3_policy import RepairPolicy as CorePolicy
from .native_repair3_policy import SenderContentEncoder as SenderContentEncoder
from .native_repair3_policy import executed_learned_action as executed_learned_action
from .native_repair3_policy import validate_repair_bundle as validate_core_bundle

REPAIR_ABI = "native_temporal_repair_v4"
GCC_CEILING = CAPS[-1]
CONFIG = dict(CORE_CONFIG, fallback="native_gcc", gcc_ceiling_bps=GCC_CEILING)


def core_bundle(bundle):
    require(
        bundle.get("model_abi") == REPAIR_ABI and bundle.get("config") == CONFIG,
        "repair4 ABI/config required",
    )
    projected = dict(bundle, model_abi=CORE_ABI, config=CORE_CONFIG.copy())
    return validate_core_bundle(projected)


def validate_repair_bundle(bundle):
    core_bundle(bundle)
    return bundle


def rebase_repair_bundle(bundle):
    """Rebase only an unselected V3 model; never pretend old selected labels fit GCC."""
    validate_core_bundle(bundle)
    require("selected_calibration" not in bundle, "fresh GCC selected calibration required")
    result = deepcopy(bundle)
    result.update(model_abi=REPAIR_ABI, config=CONFIG.copy())
    validate_repair_bundle(result)
    return result


class RepairPolicy:
    def __init__(self, bundle=None):
        self.bundle = validate_repair_bundle(bundle) if bundle is not None else None
        self.core = CorePolicy(core_bundle(bundle) if bundle is not None else None)

    def acknowledge(self, cap, now):
        return self.core.acknowledge(cap, now)

    def observe(self, observation, feedback=None):
        d = self.core.observe(observation, feedback)
        # V3's unsafe/missing/startup/congestion/upward-veto paths cannot throttle
        # the native estimator. This is a ceiling, never a forced wire bitrate.
        d["bwe_reference_action_index"] = d["baseline_action_index"]
        d["baseline_action_index"] = len(CAPS) - 1
        if d["fallback"]:
            d["action_index"] = len(CAPS) - 1
            d["encoder_max_bitrate_bps"] = GCC_CEILING
            d["learned_action_index"] = None
        d["gcc_departure"] = not d["fallback"] and d["encoder_max_bitrate_bps"] != GCC_CEILING
        # Keep the original useful-use gate: must differ from BOTH references.
        d["learned_departure"] = d["learned_departure"] and d["gcc_departure"]
        return d


def exploration_cap(behavior, step, seed, features):
    if behavior == "gcc":
        return GCC_CEILING
    from .native_repair3_study import exploration_cap as legacy_exploration

    return legacy_exploration(behavior, step, seed, features)
