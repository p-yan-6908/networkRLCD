"""Source/title/capture-clustered diagnostics; no learned controller."""

import numpy as np
from scipy.stats import f, t

from . import native_actuator_statistics as base
from .native_actuator_control import RATIOS
from .native_panel_assets import validate_cluster_rows
from .native_protocol import finite, require

STRATA = ("low", "medium", "high")
REGIMES = ("underutilized", "near-capacity", "queue-building", "collapse-recovery")
ROLES = ("discovery", "replication")
CRITERIA = {
    **base.CRITERIA,
    "minimum_source_clusters_per_cell_role": 8,
    "equivalence_margin_actual_over_bwe": 0.03,
    "minimum_qoe_difference_db": 1.0,
    "relative_rate_sensitivity": 0.20,
    "rate_comparisons": 156,  # (12 prespecified cells + pooled) x 2 roles x 3 pairs x 2 endpoints
    "outcome_comparisons": 78,  # same cells/roles x three contrasts
}


def panel_design(rows):
    original = base._design(rows)
    w = original[0]
    # Within-source excerpts get nuisance fixed effects, NEVER extra covariance
    # clusters or extra t/F denominator degrees of freedom.
    clip_ids = sorted({r["clip_id"] for r in rows})
    clip_controls = [np.array([float(r["clip_id"] == c) for r in rows]) for c in clip_ids[1:]]
    if clip_controls:
        w = np.column_stack([w, *clip_controls])
    # Regime and within-peer epoch are prespecified nuisance main effects;
    # content stratum is constant within clip and already absorbed by clip FE.
    extras = [np.array([float(r.get("network_regime") == n) for r in rows]) for n in REGIMES[1:]]
    extras += [np.array([float(r.get("epoch") == e) for r in rows]) for e in range(1, 6)]
    w = np.column_stack([w, *extras])
    d = np.array([[float(r["arm"] == a) for a in (1, 2)] for r in rows])
    z = d - w @ np.linalg.lstsq(w, d, rcond=None)[0]
    rank = np.linalg.matrix_rank(w) + 2
    require(
        np.linalg.matrix_rank(z) == 2 and len(rows) - rank >= 10,
        "panel residualized action support insufficient",
    )
    df = original[-1]
    correction = (df + 1) / df * (len(rows) - 1) / (len(rows) - rank)
    return w, z, np.linalg.inv(z.T @ z), correction, original[4], df


def interaction_test(rows, factor):
    levels = STRATA if factor == "complexity_stratum" else REGIMES
    outcomes = {}
    vectors = []
    for role in ROLES:
        subset = [r for r in rows if r["role"] == role and r["complete"]]
        support = all(
            len({r["cluster_id"] for r in subset if r[factor] == level})
            >= CRITERIA["minimum_source_clusters_per_cell_role"]
            for level in levels
        )
        result = dict(support_qualified=support, qualified=False)
        if support:
            try:
                basic = panel_design(subset)
                w = basic[0]
                d = np.array([[float(r["arm"] == a) for a in (1, 2)] for r in subset])
                terms = [d] + [
                    d * np.array([float(r[factor] == level) for r in subset])[:, None] for level in levels[1:]
                ]
                all_z = np.column_stack(terms)
                z = all_z - w @ np.linalg.lstsq(w, all_z, rcond=None)[0]
                q = z.shape[1]
                rank = np.linalg.matrix_rank(w) + q
                require(
                    np.linalg.matrix_rank(z) == q and len(subset) - rank >= 10,
                    "interaction support insufficient",
                )
                a = np.array([r["encoder_bps"] / r["base_bwe_bps"] for r in subset])
                a = a - w @ np.linalg.lstsq(w, a, rcond=None)[0]
                bread = np.linalg.inv(z.T @ z)
                b = bread @ z.T @ a
                error = a - z @ b
                ids, df = basic[4:]
                scores = np.array([z[ids == g].T @ error[ids == g] for g in range(df + 1)])
                correction = (df + 1) / df * (len(subset) - 1) / (len(subset) - rank)
                cov = correction * bread @ scores.T @ scores @ bread
                effect, v = b[2:], cov[2:, 2:]
                require(np.linalg.matrix_rank(v) == len(effect), "interaction covariance rank insufficient")
                statistic = float(effect @ np.linalg.solve(v, effect) / len(effect))
                p = float(f.sf(statistic, len(effect), df))
                result.update(
                    cluster_F=statistic,
                    p=p,
                    interaction_effects=effect.tolist(),
                    qualified=p < CRITERIA["alpha"] / 4,
                )
                vectors.append(effect)
            except (ValueError, np.linalg.LinAlgError) as error:
                result["inference_blocker"] = str(error)
        outcomes[role] = result
    direction = len(vectors) == 2 and float(vectors[0] @ vectors[1]) > 0
    return dict(
        roles=outcomes,
        replicated=direction and all(r["qualified"] for r in outcomes.values()),
        direction_agreement=direction,
        cluster_unit="independent_source_title_capture",
        no_ML_fitted=True,
    )


def _contrasts(fit, df, comparisons, divisor=1):
    critical = t.ppf(1 - CRITERIA["alpha"] / (2 * comparisons), df)
    result = []
    for low, high, vector in ((0, 1, [1, 0]), (0, 2, [0, 1]), (1, 2, [-1, 1])):
        v = np.array(vector)
        effect = float(v @ fit["b"])
        se = float(np.sqrt(max(0.0, v @ fit["cov"] @ v)))
        ci = [effect - critical * se, effect + critical * se]
        scale = (RATIOS[high] - RATIOS[low]) if divisor else 1
        result.append(
            dict(
                low=low,
                high=high,
                effect=effect,
                ci=ci,
                delta_A_over_delta_Z=effect / scale if divisor else None,
                gain_ci=[x / scale for x in ci] if divisor else None,
            )
        )
    return result


def _rate(rows, key, design):
    fit = base._fit([r[key] / r["base_bwe_bps"] for r in rows], design)
    contrasts = _contrasts(fit, design[-1], CRITERIA["rate_comparisons"])
    qualified = fit["F"] is not None and fit["F"] >= CRITERIA["minimum_first_stage_F"]
    qualified = qualified and fit["partial_R2"] >= CRITERIA["minimum_partial_R2"]
    qualified = qualified and all(
        c["ci"][0] > CRITERIA["minimum_adjacent_rate_separation"]
        for c in contrasts
        if c["high"] - c["low"] == 1
    )
    margin = CRITERIA["equivalence_margin_actual_over_bwe"]
    equivalent = all(-margin < c["ci"][0] and c["ci"][1] < margin for c in contrasts)
    return dict(
        qualified=bool(qualified),
        cluster_F=fit["F"],
        partial_R2=fit["partial_R2"],
        contrasts=contrasts,
        equivalently_small_effect=bool(equivalent),
        interpretation="separated" if qualified else "equivalently_small" if equivalent else "inconclusive",
    ), fit


def _role(rows):
    complete = [r for r in rows if r["complete"]]
    counts = [sum(r["arm"] == a for r in complete) for a in range(3)]
    clips = {r["cluster_id"] for r in complete}
    arm_clips = [len({r["cluster_id"] for r in complete if r["arm"] == a}) for a in range(3)]
    support = (
        len(clips) >= CRITERIA["minimum_source_clusters_per_cell_role"]
        and min(counts) >= CRITERIA["minimum_rows_per_arm"]
        and min(arm_clips) >= CRITERIA["minimum_source_clusters_per_cell_role"]
        and len(complete) / max(1, len(rows)) >= CRITERIA["minimum_complete_fraction"]
        and sum(r["clipped_or_aliased"] for r in complete) / max(1, len(complete))
        <= CRITERIA["maximum_alias_fraction"]
    )
    result = dict(
        assigned=len(rows),
        complete=len(complete),
        independent_source_clusters=len(clips),
        content_files_or_windows=len({r["clip_id"] for r in complete}),
        native_peers=len({r["trial_id"] for r in rows}),
        counts_per_arm=counts,
        independent_source_clusters_per_arm=arm_clips,
        support_qualified=bool(support),
        qualified=False,
        non_plateau=sum(not r["plateau_observed"] for r in complete),
        non_plateau_not_excluded=True,
        distributions={
            str(a): {
                k: base._distribution([r for r in complete if r["arm"] == a], k)
                for k in ("requested_bps", "encoder_bps", "send_bps", "utility", "ontime_fraction")
            }
            for a in range(3)
        },
    )
    internal = None
    if support:
        try:
            # block_id MUST be source cluster, not file/window/regime/replicate. Pooled
            # design also adjusts prespecified regime/epoch via nuisance columns.
            adjusted = []
            for row in complete:
                item = dict(row)
                item["block_id"] = row["cluster_id"]
                adjusted.append(item)
            design = panel_design(adjusted)
            result["encoder"], a = _rate(adjusted, "encoder_bps", design)
            result["send"], _ = _rate(adjusted, "send_bps", design)
            result["qualified"] = result["encoder"]["qualified"] and result["send"]["qualified"]
            internal = adjusted, design, a
        except (ValueError, np.linalg.LinAlgError) as error:
            result["inference_blocker"] = str(error)
    return result, internal


def _outcome(internals, first_stage, iv_assumptions):
    result = dict(
        status="deferred_until_cell_first_stage_replicates",
        qualified=False,
        actual_bitrate_causal_effect_established=False,
    )
    if not first_stage:
        return result
    result.update(status="factual_ITT_and_assumption_conditional_IV", roles={})
    vectors = []
    for role, (rows, design, a) in internals.items():
        y = base._fit([r["utility"] for r in rows], design)
        contrasts = _contrasts(y, design[-1], CRITERIA["outcome_comparisons"], divisor=0)
        meaningful = any(
            c["ci"][0] > CRITERIA["minimum_qoe_difference_db"]
            or c["ci"][1] < -CRITERIA["minimum_qoe_difference_db"]
            for c in contrasts
        )
        gram = design[1].T @ design[1]
        denominator = a["b"] @ gram @ a["b"]
        estimate = float(a["b"] @ gram @ y["b"] / denominator) if denominator > 1e-15 else None
        ar = base.anderson_rubin_set(a, y, design, CRITERIA["alpha"] / 26)
        excludes = bool(ar["intervals"]) and all(
            (x["lower"] is not None and x["lower"] > 0) or (x["upper"] is not None and x["upper"] < 0)
            for x in ar["intervals"]
        )
        actual = [r["encoder_bps"] / r["base_bwe_bps"] for r in rows]
        dose = float(np.mean(actual)) * CRITERIA["relative_rate_sensitivity"]
        sensitivity = [
            dict(
                lower=x["lower"] * dose if x["lower"] is not None else None,
                upper=x["upper"] * dose if x["upper"] is not None else None,
            )
            for x in ar["intervals"]
        ]
        result["roles"][role] = dict(
            ITT_cluster_F=y["F"],
            ITT_p=float(f.sf(y["F"], 2, design[-1])) if y["F"] is not None else None,
            meaningful_factual_qoe_difference=bool(meaningful),
            contrasts=contrasts,
            scalar_rate_2SLS_estimate=estimate,
            weak_IV_robust_AR=ar,
            scalar_rate_effect_supported_conditional_on_assumptions=excludes,
            qoe_change_for_20_percent_actual_rate=estimate * dose if estimate is not None else None,
            qoe_change_for_20_percent_AR_set=sensitivity,
            linear_rate_effect_assumption_required=True,
        )
        vectors.append(y["b"])
    direction = len(vectors) == 2 and float(vectors[0] @ vectors[1]) > 0
    result["replicated_direction_agreement"] = direction
    result["qualified"] = direction and all(
        r["meaningful_factual_qoe_difference"] for r in result["roles"].values()
    )
    result["actual_bitrate_causal_effect_established"] = bool(
        iv_assumptions
        and result["qualified"]
        and all(
            r["scalar_rate_effect_supported_conditional_on_assumptions"] for r in result["roles"].values()
        )
    )
    return result


def analyze_panel(rows, iv_assumptions=False):
    require(type(iv_assumptions) is bool, "explicit IV assumptions required")
    validate_cluster_rows(rows)
    require(
        all(
            r["role"] in ROLES
            and r["complexity_stratum"] in STRATA
            and r["network_regime"] in REGIMES
            and r["arm"] in range(3)
            and r["propensity"] == 1 / 3
            and r["only_factual_outcome"] is True
            and r["block_id"] == r["cluster_id"]
            for r in rows
        ),
        "factual IID panel/source-cluster provenance required",
    )
    roles = {role: {r["cluster_id"] for r in rows if r["role"] == role} for role in ROLES}
    require(not roles["discovery"] & roles["replication"], "clip role leakage")

    def cell(subset):
        role_results, internals = {}, {}
        for role in ROLES:
            role_results[role], internal = _role([r for r in subset if r["role"] == role])
            if internal:
                internals[role] = internal
        qualified = all(r["qualified"] for r in role_results.values())
        return dict(
            stage1=dict(qualified=qualified, roles=role_results),
            stage2=_outcome(internals, qualified, iv_assumptions),
        )

    cells = {
        s + ":" + n: cell([r for r in rows if r["complexity_stratum"] == s and r["network_regime"] == n])
        for s in STRATA
        for n in REGIMES
    }
    pooled = cell(rows)
    valid = [key for key, c in cells.items() if c["stage1"]["qualified"]]
    relevant = [key for key, c in cells.items() if c["stage2"]["qualified"]]
    interactions = {
        factor: interaction_test(rows, factor) for factor in ("complexity_stratum", "network_regime")
    }
    return dict(
        abi="native_actuator_source_panel_report_v2",
        criteria=CRITERIA,
        inference_unit="independent_source_title_capture_cluster_across_all_excerpts_regimes_replicates",
        independent_source_clusters_per_role={k: len(v) for k, v in roles.items()},
        cells=cells,
        pooled=pooled,
        first_stage_valid_cells=valid,
        outcome_sensitive_cells=relevant,
        all_cells_first_stage_qualified=len(valid) == len(cells),
        effect_heterogeneity_established=any(x["replicated"] for x in interactions.values()),
        interactions=interactions,
        subgroup_significance_is_not_interaction_test=True,
        within_source_clip_independence_assumed=False,
        novel_source_generalization_established=False,
        actuator_validity=dict(
            status="not_fitted",
            possible_future_target="P(action_has_measurable_effect|pretreatment_state)",
            no_safety_gate_modified=True,
        ),
        state_action_preference=dict(status="deferred_no_model_fitted", qualified=False),
        iv_assumptions_explicitly_assumed_not_verified=iv_assumptions,
        policy_models_fitted=0,
        learned_controller_promoted=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
        no_counterfactual_outcomes_imputed=True,
    )


def power_projection(source_units_per_stratum_role, replicates, assumptions, draws=200, seed=514):
    """Prospective stress calculation, never observed causal evidence.

    Source-cluster random slopes + peer/cohort noise; one representative per
    source unit. More excerpts/encodes do not change independent N. Assumptions
    are not measured variance; no automatic unblinded sample-size re-estimation.
    """
    require(
        type(source_units_per_stratum_role) is int
        and 8 <= source_units_per_stratum_role <= 100
        and type(replicates) is int
        and 1 <= replicates <= 20
        and type(draws) is int
        and 20 <= draws <= 1000,
        "bounded prospective power simulation",
    )
    keys = ("adjacent_effect_actual_over_bwe", "source_random_slope_sd", "peer_noise_sd", "cohort_noise_sd")
    require(
        set(assumptions) == set(keys) and all(finite(v) and v > 0 for v in assumptions.values()),
        "explicit positive power assumptions required",
    )
    rng = np.random.default_rng(seed)
    passed = 0
    for _ in range(draws):
        samples = []
        for clip in range(source_units_per_stratum_role):
            slope = assumptions["adjacent_effect_actual_over_bwe"] / 0.2 + rng.normal(
                0, assumptions["source_random_slope_sd"]
            )
            for peer in range(replicates):
                offset = rng.normal(0, assumptions["peer_noise_sd"])
                for epoch in range(6):
                    arm = int(rng.integers(3))
                    actual = (
                        0.1 + slope * RATIOS[arm] + offset + rng.normal(0, assumptions["cohort_noise_sd"])
                    )
                    state = {k: dict(status="absent", value=None) for k in base.COVARIATES}
                    state["previous_action"] = None
                    samples.append(
                        dict(
                            block_id=str(clip),
                            clip_id=str(clip),
                            arm=arm,
                            state=state,
                            base_bwe_bps=1.0,
                            encoder_bps=actual,
                            epoch=epoch,
                        )
                    )
        design = panel_design(samples)
        result, _ = _rate(samples, "encoder_bps", design)
        passed += result["qualified"]
    estimate = passed / draws
    # Wilson lower bound prevents calling a noisy Monte Carlo point estimate powered.
    z = 1.96
    denominator = 1 + z * z / draws
    center = (estimate + z * z / (2 * draws)) / denominator
    width = z * np.sqrt(estimate * (1 - estimate) / draws + z * z / (4 * draws * draws)) / denominator
    return dict(
        assumptions=assumptions,
        simulations=draws,
        source_clusters_per_cell_role=source_units_per_stratum_role,
        native_peers_per_cell_role=source_units_per_stratum_role * replicates,
        expected_cohorts_per_cell_role=source_units_per_stratum_role * replicates * 6,
        adjacent_effect_detection_probability=estimate,
        simulation_ci95=[center - width, center + width],
        replicated_role_detection_probability=estimate**2,
        replicated_role_simulation_ci95=[(center - width) ** 2, min(1.0, center + width) ** 2],
        projected_80_percent_power=bool((center - width) ** 2 >= 0.8),
        power_scope="encoded_first_stage_single_cell_two_independent_roles_given_identical_noise_assumptions",
        send_outcome_and_all_cell_joint_power_not_established=True,
        sensitivity_not_guarantee=True,
        empirical_power_established=False,
        policy_models_fitted=0,
    )
