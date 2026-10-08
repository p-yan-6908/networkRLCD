"""Observable encoder-settled, then network-delayed, factual QoE attribution.

Unsettled, superseded and truncated cohorts are kept as censored evidence, never
assigned a reward or substituted with a fixed command-age window. Target attainment
is an attribution rule, not a training/policy input or proof of perceptual quality.
"""

import math

from .jevbwe import number


class SettledCredit:
    def __init__(self, window_ms=600, tolerance=0.05, switch_weight=0.15):
        if (
            not number(window_ms)
            or window_ms <= 0
            or not number(tolerance)
            or not 0 <= tolerance < 1
            or not number(switch_weight)
            or switch_weight < 0
        ):
            raise ValueError("invalid settled-credit configuration")
        self.window_ms, self.tolerance, self.switch_weight = window_ms, tolerance, switch_weight
        self.pending = None
        self.last_ms = None

    def begin(
        self, *, now_ms, action_index, state, requested_bps, previous_bps, network_delay_ms, **metadata
    ):
        if (
            not number(now_ms)
            or now_ms < 0
            or (self.last_ms is not None and now_ms < self.last_ms)
            or type(action_index) is not int
            or not 0 <= action_index < 6
            or any(not number(v) or v <= 0 for v in (requested_bps, previous_bps))
            or not number(network_delay_ms)
            or network_delay_ms < 0
            or not all(number(v) for v in state)
        ):
            raise ValueError("invalid causal factual credit command")
        old = self.finish("superseded")
        self.pending = dict(
            **metadata,
            command_ms=now_ms,
            action_index=action_index,
            state=list(state),
            requested_bps=requested_bps,
            previous_bps=previous_bps,
            network_delay_ms=network_delay_ms,
            changed_action=abs(requested_bps - previous_bps) > 1,
            settled_ms=None,
            credit_start_ms=None,
            credit_end_ms=None,
            covered_ms=0.0,
            reward_sum=0.0,
            unsafe=0,
            samples=0,
        )
        self.last_ms = now_ms
        return old

    def observe(self, *, now_ms, interval_ms, encoder_target_bps, delivered_qoe, unsafe):
        if (
            not number(now_ms)
            or not number(interval_ms)
            or interval_ms <= 0
            or (
                self.last_ms is not None
                and (now_ms <= self.last_ms or now_ms - interval_ms < self.last_ms - 1e-6)
            )
            or not number(delivered_qoe)
            or type(unsafe) is not int
            or unsafe not in (0, 1)
        ):
            raise ValueError("invalid chronological delivered outcome")
        self.last_ms = now_ms
        p = self.pending
        if p is None:
            return None
        matches = number(encoder_target_bps) and abs(encoder_target_bps - p["requested_bps"]) <= max(
            1, self.tolerance * p["requested_bps"]
        )
        if p["settled_ms"] is None:
            if matches:
                p["settled_ms"] = now_ms
                p["credit_start_ms"] = now_ms + p["network_delay_ms"]
                p["credit_end_ms"] = p["credit_start_ms"] + self.window_ms
            return None  # the interval discovering settlement predates that evidence
        if not matches:
            return self.finish("encoder_target_left_band")
        start = max(now_ms - interval_ms, p["credit_start_ms"])
        end = min(now_ms, p["credit_end_ms"])
        duration = max(0, end - start)
        if duration:
            p["covered_ms"] += duration
            p["reward_sum"] += duration * delivered_qoe
            p["unsafe"] = max(p["unsafe"], unsafe)
            p["samples"] += 1
        if p["covered_ms"] >= self.window_ms - 1e-6:
            switch = abs(math.log(p["requested_bps"] / p["previous_bps"]))
            reward = p["reward_sum"] / p["covered_ms"] - self.switch_weight * switch
            result = {
                **p,
                "censored": False,
                "censor_reason": None,
                "reward": reward,
                "delivered_reward": p["reward_sum"] / p["covered_ms"],
                "switch_penalty": self.switch_weight * switch,
            }
            self.pending = None
            return result
        return None

    def finish(self, reason="end_of_episode"):
        if self.pending is None:
            return None
        result = {
            **self.pending,
            "censored": True,
            "censor_reason": reason,
            "reward": None,
            "delivered_reward": None,
            "unsafe": None,
            "switch_penalty": None,
        }
        self.pending = None
        return result
