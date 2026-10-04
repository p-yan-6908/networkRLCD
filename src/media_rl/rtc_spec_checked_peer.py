"""Spec-checked inference entrypoint; not a verified original receiver/actuator."""

import time

import numpy as np

from .published_rtc_peer import PublishedRtcPeer
from .rtc_receiver_contract import validate_receiver_observation


class SpecCheckedRtcPeer(PublishedRtcPeer):
    """Reject known feature contradictions before touching estimator state.

    The original immutable checkpoint, CPU ABI, channel and state carry remain
    unchanged. Passing aggregate checks never certifies upstream causality,
    original extraction or live controller readiness.
    """

    def act(self, observation):
        start = time.perf_counter_ns()
        # Snapshot once so caller mutation/array conversion cannot change input
        # between semantic validation and the inherited inference call.
        snapshot = np.asarray(observation).copy()
        validate_receiver_observation(snapshot)
        model_input = snapshot.astype(np.float32, copy=True)
        validate_receiver_observation(model_input)
        result = super().act(model_input)
        return dict(
            **result,
            documented_receiver_checks_pass=True,
            contract_and_act_latency_ms=(time.perf_counter_ns() - start) / 1e6,
            policy_inference_executed=True,
            original_controller_ready=False,
            original_extractor_equivalence=False,
            causality_certified=False,
            closed_loop=False,
            auxiliary_is_calibrated_risk=False,
        )
