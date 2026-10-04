"""Versioned canonical+growth-hold control; no weight or risk-calibration changes.

Both guarded and unguarded peers compute and log the same canonical model and
hypothetical overlay on their ACTUAL history. Only the selected output differs.
Modified fallback never acquires neural credit or reuses a canonical action's
probability as a safety certification for the modified scalar rate.
"""

from .native_action_fallback_guard import growth_hold_action
from .native_action_policy import ActionPolicy
from .native_protocol import require


class GuardPolicy(ActionPolicy):
    def __init__(self, bundle, guarded=False):
        require(
            bundle is not None and type(guarded) is bool,
            "fitted bundle and explicit boolean guard mode required",
        )
        super().__init__(bundle)
        self.guarded = guarded

    def observe(self, observation, feedback=None):
        canonical = super().observe(observation, feedback)
        overlay = growth_hold_action(canonical)
        applied = self.guarded and overlay["fallback_growth_hold_applied"]
        return dict(
            canonical,
            encoder_max_bitrate_bps=overlay["encoder_max_bitrate_bps"]
            if self.guarded
            else canonical["encoder_max_bitrate_bps"],
            canonical_decision=canonical,
            guard_decision=overlay,
            guard_enabled=self.guarded,
            guard_applied=applied,
            effective_action_origin="fallback_growth_hold" if applied else "canonical",
            modified_fallback_neural_credit=False,
        )
