"""Opt-in ordered history features only; no fitter, actor, default or old recipe change."""

import numpy as np

from . import native_action_compact_hold_cv as original

ABI = "native_32step_ordered_compact_projection_v1"
HISTORY_STEPS = 32
STEP_DIM = 23
COMPACT_DIM = 115
INPUT_DIM = 118
CONTRACT = dict(
    abi=ABI,
    state_steps=32,
    state_channels=23,
    state_dim=736,
    original_summary_dim=92,
    ordered_trend_dim=23,
    compact_dim=115,
    proposed_dim=3,
    input_dim=118,
    time_coordinate="sample_index/(32-1), not elapsed seconds",
    projection="original_latest_recent8_mean_all32_mean_std_plus_all32_OLS_index_trend",
    normalization="future_model_fit_fold_only_required",
    no_new_state_or_future_target_channels=True,
    opt_in_only=True,
    no_model_fitted=True,
    native_deployment_qualified=False,
    SOTA_achieved=False,
)


def temporal_trends(states):
    original.project_state(states)  # Exact original finite causal state guard.
    h = np.asarray(states, dtype=float).reshape(-1, HISTORY_STEPS, STEP_DIM)
    t = np.arange(HISTORY_STEPS, dtype=float) / (HISTORY_STEPS - 1)
    centered = t - t.mean()
    return np.einsum("nsc,s->nc", h - h.mean(axis=1, keepdims=True), centered) / np.dot(centered, centered)


def project_state(states):
    return np.column_stack([original.project_state(states), temporal_trends(states)])


def design(states, cap, blind=False):
    base = original.design(states, cap, blind)
    return np.column_stack([base[:, :92], temporal_trends(states), base[:, 92:]])


def temporal_ambiguity_fixture():
    h = np.zeros((2, HISTORY_STEPS, STEP_DIM), dtype=float)
    h[:, :, 7] = 0.45
    h[:, :, 14] = 1
    h[:, :, 15] = 0.1
    h[:, -8:, 6] = 12
    h[0, :24, 6] = np.arange(24)
    h[1, :24, 6] = np.arange(24)[::-1]
    return h.reshape(2, 736)
