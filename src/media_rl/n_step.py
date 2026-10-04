"""Finite-horizon replay credit for delayed media outcomes; no trace/oracle access."""

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ReplayTransition:
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool
    steps: int
    discount: float


class NStepAccumulator:
    """Emit one discounted prefix per decision, truncating/flushing at termination."""

    def __init__(self, n_step, gamma):
        if type(n_step) is not int or not 1 <= n_step <= 16:
            raise ValueError("n_step must be an integer in [1, 16]")
        if not np.isfinite(gamma) or not 0 <= gamma <= 1:
            raise ValueError("gamma must be finite and in [0, 1]")
        self.n_step, self.gamma = n_step, float(gamma)
        self.pending = deque()

    def push(self, state, action, reward, next_state, done):
        state, next_state = (
            np.array(state, dtype=float, copy=True),
            np.array(next_state, dtype=float, copy=True),
        )
        if (
            state.ndim != 1
            or state.shape != next_state.shape
            or not np.all(np.isfinite(state))
            or not np.all(np.isfinite(next_state))
            or not np.isfinite(reward)
            or isinstance(action, (bool, np.bool_))
            or not isinstance(action, (int, np.integer))
            or action < 0
            or not isinstance(done, (bool, np.bool_))
        ):
            raise ValueError("invalid replay transition")
        if self.pending and self.pending[-1][3].shape != state.shape:
            raise ValueError("replay state dimension changed within episode")
        self.pending.append((state, int(action), float(reward), next_state, bool(done)))
        emitted = []
        while self.pending and (done or len(self.pending) >= self.n_step):
            window = list(self.pending)[: self.n_step]
            first, last = window[0], window[-1]
            reward_sum = sum(self.gamma**i * item[2] for i, item in enumerate(window))
            emitted.append(
                ReplayTransition(
                    first[0], first[1], reward_sum, last[3], last[4], len(window), self.gamma ** len(window)
                )
            )
            self.pending.popleft()
        return emitted
