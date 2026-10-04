"""Conservative BWE fallback, expiring RTT baseline and fixed encoder recipe.

All learned V3 budgets remain. V5 requires fresh fixed-recipe training, not rebase.
"""

from math import isfinite

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

REPAIR_ABI = "native_temporal_repair_v5"
GCC_CEILING = CAPS[-1]
CONFIG = dict(CORE_CONFIG, rtt_baseline_window_ms=4000, encoder_degradation_preference="maintain-framerate")


def core_bundle(bundle):
    require(
        bundle.get("model_abi") == REPAIR_ABI and bundle.get("config") == CONFIG,
        "repair5 ABI/config and fresh encoder-recipe model required",
    )
    return validate_core_bundle(dict(bundle, model_abi=CORE_ABI, config=CORE_CONFIG.copy()))


def validate_repair_bundle(bundle):
    core_bundle(bundle)
    return bundle


class RepairPolicy:
    def __init__(self, bundle=None):
        self.bundle = validate_repair_bundle(bundle) if bundle is not None else None
        self.core = CorePolicy(core_bundle(bundle) if bundle is not None else None)
        self.rtt_samples = []

    def acknowledge(self, cap, now):
        return self.core.acknowledge(cap, now)

    def observe(self, observation, feedback=None):
        now = observation["sample_ms"]
        f = list(observation["features"])
        require(
            type(now) in (int, float)
            and isfinite(now)
            and now >= 0
            and len(f) == 16
            and all(type(v) in (int, float) and isfinite(v) and v >= 0 for v in f)
            and (self.core.last_sample is None or now >= self.core.last_sample),
            "causal repair5 clock/features required",
        )
        if self.core.last_sample is not None and now - self.core.last_sample > CONFIG["reset_gap_ms"]:
            self.rtt_samples = []
        # Preserve raw evidence; this explicitly versioned transform masks only
        # nonphysical zero RTT validity, never receiver pixels or future outcomes.
        if f[10] == 1 and f[1] <= 0:
            f[1], f[2], f[10], f[11] = 0, 0, 0, 0
        if f[10] == 1:
            self.rtt_samples.append((now, f[1] * 150))
        self.rtt_samples = [
            (t, rtt) for t, rtt in self.rtt_samples if now - t <= CONFIG["rtt_baseline_window_ms"]
        ]
        self.core.rtt_floor = min((rtt for _, rtt in self.rtt_samples), default=None)
        d = self.core.observe(dict(observation, features=f), feedback)
        d["bwe_reference_action_index"] = d["baseline_action_index"]
        d["gcc_reference_action_index"] = len(CAPS) - 1
        d["gcc_departure"] = not d["fallback"] and d["encoder_max_bitrate_bps"] != GCC_CEILING
        d["learned_departure"] = d["learned_departure"] and d["gcc_departure"]
        return d


def exploration_cap(behavior, step, seed, features):
    if behavior == "gcc":
        return GCC_CEILING
    if behavior == "fixed600":
        return CAPS[2]
    from .native_repair3_study import exploration_cap as original_exploration

    return original_exploration(behavior, step, seed, features)
