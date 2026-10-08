"""Preregistered physical-block inference; never fit/select a controller.

Sequential IID assignment identifies requested-arm effects. Scalar-rate IV
interpretations require additional exclusion/washout/treatment assumptions.
CR1 small-sample t/F inference is approximate, not exact randomization inference.
"""

import numpy as np
from numpy.polynomial import Polynomial
from scipy.stats import f, t

from .native_actuator_control import RATIOS
from .native_protocol import finite, require

CRITERIA = dict(
    alpha=0.05,
    minimum_blocks_per_role=8,
    minimum_rows_per_arm=12,
    minimum_complete_fraction=0.95,
    maximum_alias_fraction=0.10,
    minimum_adjacent_rate_separation=0.03,
    minimum_first_stage_F=10.0,
    minimum_partial_R2=0.05,
)
COVARIATES = (
    "bwe_bps",
    "rtt_ms",
    "rtt_trend_ms",
    "loss_fraction",
    "jitter_ms",
    "previous_requested_bps",
    "encoder_target_bps",
    "actual_encoder_bps",
    "actual_send_bps",
    "qp",
    "mean_encoded_frame_bytes",
    "previous_action",
)


def _design(rows):
    groups = sorted({r["block_id"] for r in rows})
    w = [[float(r["block_id"] == g) for g in groups] for r in rows]
    w = np.asarray(w, float)
    controls = []
    for key in COVARIATES:
        vals = [
            r["state"][key].get("value") if isinstance(r["state"][key], dict) else r["state"][key]
            for r in rows
        ]
        known = np.array([finite(v) for v in vals])
        if not np.any(known):
            continue
        v = np.array([x if finite(x) else np.nan for x in vals], float)
        v[~known] = np.median(v[known])
        scale = np.std(v)
        if scale > 1e-10:
            controls.append((v - np.mean(v)) / scale)
        if not np.all(known):
            controls.append((~known).astype(float))
    if controls:
        w = np.column_stack([w, *controls])
    rank_w = np.linalg.matrix_rank(w)
    arms = np.asarray([[float(r["arm"] == a) for a in (1, 2)] for r in rows])
    z = arms - w @ np.linalg.lstsq(w, arms, rcond=None)[0]
    require(
        np.linalg.matrix_rank(z) == 2 and len(rows) - rank_w - 2 >= 10,
        "insufficient residualized action/state degrees of freedom",
    )
    bread = np.linalg.inv(z.T @ z)
    correction = len(groups) / (len(groups) - 1) * (len(rows) - 1) / (len(rows) - rank_w - 2)
    ids = np.array([groups.index(r["block_id"]) for r in rows])
    return w, z, bread, correction, ids, len(groups) - 1


def _fit(y, design):
    w, z, bread, correction, ids, df = design
    y = np.asarray(y, float)
    residualized = y - w @ np.linalg.lstsq(w, y, rcond=None)[0]
    b = bread @ z.T @ residualized
    error = residualized - z @ b
    scores = np.array([z[ids == g].T @ error[ids == g] for g in range(df + 1)])
    cov = correction * bread @ scores.T @ scores @ bread
    denom = residualized @ residualized
    r2 = 1 - error @ error / denom if denom > 1e-15 else 0.0
    statistic = float(b @ np.linalg.solve(cov, b) / 2) if np.linalg.matrix_rank(cov) == 2 else None
    return dict(b=b, cov=cov, scores=scores, F=statistic, partial_R2=float(r2))


def _contrasts(fit, df):
    result = []
    # Bonferroni across two roles x three pairs x two physical-rate endpoints.
    critical = t.ppf(1 - CRITERIA["alpha"] / 24, df)
    for low, high, vector in ((0, 1, [1, 0]), (0, 2, [0, 1]), (1, 2, [-1, 1])):
        v = np.array(vector)
        effect = float(v @ fit["b"])
        se = float(np.sqrt(max(0.0, v @ fit["cov"] @ v)))
        ci = [effect - critical * se, effect + critical * se]
        delta_z = RATIOS[high] - RATIOS[low]
        result.append(
            dict(
                low=low,
                high=high,
                delta_actual_over_frozen_bwe=effect,
                ci=ci,
                delta_A_over_delta_Z=effect / delta_z,
                gain_ci=[x / delta_z for x in ci],
            )
        )
    return result


def rate_statistics(rows, key, design):
    fitted = _fit([r[key] / r["base_bwe_bps"] for r in rows], design)
    contrasts = _contrasts(fitted, design[-1])
    qualified = (
        fitted["F"] is not None
        and fitted["F"] >= CRITERIA["minimum_first_stage_F"]
        and fitted["partial_R2"] >= CRITERIA["minimum_partial_R2"]
        and all(
            c["ci"][0] > CRITERIA["minimum_adjacent_rate_separation"]
            for c in contrasts
            if c["high"] - c["low"] == 1
        )
    )
    result = dict(
        qualified=bool(qualified), cluster_F=fitted["F"], partial_R2=fitted["partial_R2"], contrasts=contrasts
    )
    return result, fitted


def anderson_rubin_set(a, y, design, alpha):
    """Invert a two-instrument cluster AR test on the entire real line.

    Polynomial root partitioning retains disconnected and unbounded sets. No
    finite grid truncation and no delta-method interval under weak instruments.
    Units are delivered-QoE proxy dB per actual-encoder/frozen-BWE ratio unit.
    """
    bread, correction = design[2:4]
    cross = correction * bread @ y["scores"].T @ a["scores"] @ bread
    matrix = [
        [Polynomial([y["cov"][i, j], -cross[i, j] - cross[j, i], a["cov"][i, j]]) for j in range(2)]
        for i in range(2)
    ]
    b = [Polynomial([y["b"][i], -a["b"][i]]) for i in range(2)]
    det = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    numerator = matrix[1][1] * b[0] ** 2 - 2 * matrix[0][1] * b[0] * b[1] + matrix[0][0] * b[1] ** 2
    cutoff = 2 * f.ppf(1 - alpha, 2, design[-1])
    equation = numerator - cutoff * det
    roots = []
    for poly in (det, equation):
        for root in poly.trim(tol=1e-18).roots():
            if abs(np.imag(root)) <= 1e-7 * (1 + abs(np.real(root))):
                value = float(np.real(root))
                if finite(value) and all(abs(value - old) > 1e-7 * (1 + abs(value)) for old in roots):
                    roots.append(value)
    boundaries = [-np.inf, *sorted(roots), np.inf]
    intervals = []
    for left, right in zip(boundaries, boundaries[1:], strict=False):
        point = (
            (left + right) / 2
            if np.isfinite(left) and np.isfinite(right)
            else right - max(1, abs(right))
            if np.isfinite(right)
            else left + max(1, abs(left))
            if np.isfinite(left)
            else 0.0
        )
        if det(point) > 0 and equation(point) <= 0:
            intervals.append(
                dict(
                    lower=float(left) if np.isfinite(left) else None,
                    upper=float(right) if np.isfinite(right) else None,
                )
            )
    return dict(
        intervals=intervals,
        unbounded=any(x["lower"] is None or x["upper"] is None for x in intervals),
        empty=not intervals,
        null_means_infinite_endpoint=True,
        method="cluster_CR1_two_instrument_AR_full_real_line_polynomial_inversion",
        conditional_on_IV_exclusion_and_rate_treatment_assumptions=True,
    )


def _distribution(rows, key):
    values = [r[key] for r in rows if finite(r.get(key))]
    return dict(
        n=len(values), quantiles=np.quantile(values, [0, 0.25, 0.5, 0.75, 1]).tolist() if values else None
    )


def analyze_cohorts(cohorts, iv_assumptions=False):
    require(type(iv_assumptions) is bool, "explicit IV assumption declaration required")
    require(
        all(
            r["role"] in ("discovery", "replication") and r["arm"] in (0, 1, 2) and r["propensity"] == 1 / 3
            for r in cohorts
        ),
        "only factual prospective IID three-arm cohorts",
    )
    # A physical content reservation is the cluster, never a frame or repeated epoch.
    by_role = {role: [r for r in cohorts if r["role"] == role] for role in ("discovery", "replication")}
    require(
        not {r["block_id"] for r in by_role["discovery"]} & {r["block_id"] for r in by_role["replication"]},
        "role-disjoint physical blocks required",
    )
    stages, internals = {}, {}
    for role, all_rows in by_role.items():
        rows = [r for r in all_rows if r["complete"]]
        counts = [sum(r["arm"] == arm for r in rows) for arm in range(3)]
        distributions = {
            str(arm): {
                k: _distribution([r for r in rows if r["arm"] == arm], k)
                for k in ("requested_bps", "encoder_bps", "send_bps", "utility", "ontime_fraction")
            }
            for arm in range(3)
        }
        support = (
            len({r["block_id"] for r in rows}) >= CRITERIA["minimum_blocks_per_role"]
            and min(counts) >= CRITERIA["minimum_rows_per_arm"]
            and len(rows) / max(1, len(all_rows)) >= CRITERIA["minimum_complete_fraction"]
            and sum(r["clipped_or_aliased"] for r in rows) / max(1, len(rows))
            <= CRITERIA["maximum_alias_fraction"]
        )
        result = dict(
            assigned=len(all_rows),
            complete=len(rows),
            counts_per_arm=counts,
            blocks=len({r["block_id"] for r in rows}),
            support_qualified=support,
            aliased=sum(r["clipped_or_aliased"] for r in all_rows),
            non_plateau=sum(r["complete"] and not r["plateau_observed"] for r in all_rows),
            non_plateau_not_excluded=True,
            distributions=distributions,
            qualified=False,
        )
        if support:
            try:
                design = _design(rows)
                result["encoder"], a = rate_statistics(rows, "encoder_bps", design)
                result["send"], _ = rate_statistics(rows, "send_bps", design)
                result["qualified"] = result["encoder"]["qualified"] and result["send"]["qualified"]
                internals[role] = (rows, design, a)
            except (ValueError, np.linalg.LinAlgError) as error:
                result["inference_blocker"] = str(error)
        stages[role] = result
    stage1 = all(s["qualified"] for s in stages.values())
    outcome = dict(
        status="deferred_until_stage1_replicates",
        qualified=False,
        actual_bitrate_causal_effect_established=False,
    )
    if stage1:
        outcome["status"] = "tested_factual_randomized_ITT_and_assumption_conditional_IV"
        outcome["roles"] = {}
        for role, (rows, design, a) in internals.items():
            y = _fit([r["utility"] for r in rows], design)
            p = float(f.sf(y["F"], 2, design[-1])) if y["F"] is not None else 1.0
            gram = design[1].T @ design[1]
            denominator = a["b"] @ gram @ a["b"]
            estimate = float(a["b"] @ gram @ y["b"] / denominator) if denominator > 1e-15 else None
            ar = anderson_rubin_set(a, y, design, CRITERIA["alpha"] / 2)
            ar_excludes_zero = bool(ar["intervals"]) and all(
                (x["lower"] is not None and x["lower"] > 0) or (x["upper"] is not None and x["upper"] < 0)
                for x in ar["intervals"]
            )
            outcome["roles"][role] = dict(
                ITT_cluster_F=y["F"],
                ITT_p=p,
                assigned_arm_affects_delivered_qoe=p < CRITERIA["alpha"] / 2,
                scalar_rate_2SLS_estimate=estimate,
                weak_instrument_robust_AR=ar,
                scalar_rate_effect_supported_conditional_on_assumptions=ar_excludes_zero,
            )
        outcome["qualified"] = all(r["assigned_arm_affects_delivered_qoe"] for r in outcome["roles"].values())
        outcome["actual_bitrate_causal_effect_established"] = (
            iv_assumptions
            and outcome["qualified"]
            and all(
                r["scalar_rate_effect_supported_conditional_on_assumptions"]
                for r in outcome["roles"].values()
            )
        )
    return dict(
        abi="native_actuator_identification_report_v1",
        criteria=CRITERIA,
        inference_unit="fresh_physical_content_context_block",
        method="pretreatment_state_and_block_adjusted_cluster_CR1_small_sample_t_F_approximate",
        stage1=dict(qualified=stage1, roles=stages),
        stage2=outcome,
        iv_assumptions_explicitly_assumed_not_verified=iv_assumptions,
        stage3=dict(
            status="not_fitted_architecture_frozen",
            eligible_next_experiment=bool(stage1 and outcome["actual_bitrate_causal_effect_established"]),
        ),
        policy_models_fitted=0,
        learned_controller_promoted=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
        no_counterfactual_outcomes_imputed=True,
    )
