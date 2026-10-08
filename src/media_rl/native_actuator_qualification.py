"""Native Phase N1: preregistered actuator qualification. Estimator, test and blinded rule.

N1 asks one question of fresh native data: does the requested bitrate ratio separate the
actual encoded output rate? It uses the frozen controller and the existing three-arm
randomized hold protocol and makes no QoE claim. This module is the executable form of the
preregistered estimator, the two-stage test and the blinded sample-size rule, plus the
simulation behind the power table. It reads no native data by itself, fits no model and
leaves the source-panel study (Phase N2) as it is.
"""

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy import stats

ABI = "native_actuator_qualification_n1"
RATIOS = (0.65, 0.85, 1.05)
VERDICTS = ("qualified", "not_separable_at_threshold", "inconclusive")
HETEROGENEOUS = "qualified on average, heterogeneous by complexity"


@dataclass(frozen=True)
class Plan:
    abi: str = ABI
    margin: float = 0.03  # inherited: adjacent separation of encoded rate / frozen BWE that must be exceeded
    design_effect: float = 0.10  # smallest adjacent separation N1 is powered for: half the requested step
    alpha: float = 0.025  # one-sided, per adjacent contrast; both must pass (intersection-union)
    contrast_power: float = 0.95  # per contrast at the design effect, so both pass with at least 0.90
    strata: int = 3  # complexity terciles, one vote per source cluster, weighted equally
    first_stage_sources: int = 12
    maximum_sources: int = 24
    regimes: int = 4  # weighted equally
    peers_per_regime: int = 10  # repeated measurements inside a source; never units of inference
    holds_per_peer: int = 6
    minimum_cell_cohorts: int = 3  # complete cohorts per source x regime x arm for a source to be evaluable
    minimum_complete_fraction: float = 0.95  # inherited
    maximum_alias_fraction: float = 0.10  # inherited
    maximum_arm_completeness_gap: float = 0.05
    maximum_skipped_sources: int = 4  # sources passed over because they were not evaluable
    heterogeneity_alpha: float = 0.05  # diagnostic only: complexity strata differ

    def validate(self):
        counts = (self.strata, self.first_stage_sources, self.maximum_sources, self.regimes)
        counts += (self.peers_per_regime, self.holds_per_peer, self.minimum_cell_cohorts)
        if self.abi != ABI or any(type(v) is not int or v < 1 for v in counts):
            raise ValueError("N1 plan needs its ABI and positive integer counts")
        if not 0 < self.margin < self.design_effect <= RATIOS[1] - RATIOS[0]:
            raise ValueError(
                "margin must lie below the design effect, which cannot exceed the requested step"
            )
        if not (0 < self.alpha < 0.5 < self.contrast_power < 1 and 0 < self.heterogeneity_alpha < 1):
            raise ValueError("alpha and power out of range")
        if self.first_stage_sources < 2 * self.strata or self.maximum_sources < self.first_stage_sources:
            raise ValueError("at least two sources per stratum in stage one and a maximum no smaller")
        if self.first_stage_sources % self.strata or self.maximum_sources % self.strata:
            raise ValueError("source counts must be whole stratum-balanced blocks")
        return self


@dataclass(frozen=True)
class Capture:
    """Planning inputs that are fixed with the registration. None of them is an outcome."""

    seed: int = 260107
    template: str = "results/native-action-excitation-train-sintel-v1/runtime.json"
    reservation_root: str = "results"


@dataclass(frozen=True)
class Scenario:
    """A planning assumption about the native stack. None of these is a measurement."""

    name: str
    lower_effect: float  # mean of the 0.65 -> 0.85 contrast in live regimes
    upper_effect: float  # mean of the 0.85 -> 1.05 contrast in live regimes
    source_contrast_sd: float  # SD across source clusters, shared by both contrasts (linear response)
    peer_sd: float
    cohort_sd: float
    saturating_strata: int = 0  # strata whose upper contrast is scaled by ``saturation``
    saturation: float = 1.0
    dead_regimes: int = 0  # regimes in which the request changes nothing


@dataclass(frozen=True)
class Registration:
    plan: Plan
    capture: Capture
    scenarios: tuple


def load_registration(path):
    data = json.loads(Path(path).read_text())
    scenarios = tuple(Scenario(**s) for s in data.pop("power_scenarios"))
    capture = Capture(**data.pop("capture"))
    if type(capture.seed) is not int or not 0 <= capture.seed < 2**32:
        raise ValueError("registered planning seed out of range")
    return Registration(Plan(**data).validate(), capture, scenarios)


@lru_cache(maxsize=None)
def quantile(probability, df):
    return float(stats.t.ppf(probability, df))


def source_contrasts(rows, plan, key="encoder_bps", regime=None):
    """Per source cluster: adjacent contrasts of the regime-averaged arm means of rate / frozen BWE.

    Unadjusted arm means are used on purpose. Arms are IID with known equal propensity inside
    every peer, so a difference of means is unbiased without any model. Regimes are weighted
    equally. Rows are assigned cohorts with ``source``, ``regime``, ``arm``, ``base_bwe_bps``,
    the rate ``key`` and ``complete``; a source lacking the minimum complete cohorts in any
    regime x arm cell is returned as not evaluable rather than estimated from the cells it has.
    ``regime`` restricts the contrast to one regime for the secondary regime map.
    """
    cells = {}
    for r in rows:
        if r["complete"]:
            cells.setdefault((r["source"], r["regime"], r["arm"]), []).append(r[key] / r["base_bwe_bps"])
    regimes = sorted({r["regime"] for r in rows})
    used = regimes if regime is None else [regime]
    contrasts, unevaluable = {}, []
    for source in sorted({r["source"] for r in rows}):
        cell = [[cells.get((source, g, arm), []) for g in used] for arm in range(len(RATIOS))]
        thin = any(len(values) < plan.minimum_cell_cohorts for arm in cell for values in arm)
        if thin or len(regimes) != plan.regimes:
            unevaluable.append(source)
            continue
        low, middle, high = (float(np.mean([np.mean(values) for values in arm])) for arm in cell)
        contrasts[source] = [middle - low, high - middle]
    return contrasts, unevaluable


def support(rows, plan):
    """Capture-quality gates. None of them looks at an outcome by arm."""
    rows = list(rows)
    by_arm = [[r for r in rows if r["arm"] == arm] for arm in range(len(RATIOS))]
    complete = [float(np.mean([r["complete"] for r in arm])) if arm else 0.0 for arm in by_arm]
    shares = stats.chisquare([len(arm) for arm in by_arm])
    result = dict(
        assigned_cohorts=len(rows),
        complete_fraction=float(np.mean([r["complete"] for r in rows])),
        alias_fraction=float(np.mean([bool(r.get("clipped_or_aliased")) for r in rows])),
        arm_completeness_gap=max(complete) - min(complete),
        arm_share_p_value=float(shares.pvalue),
    )
    result["passed"] = bool(
        result["complete_fraction"] >= plan.minimum_complete_fraction
        and result["alias_fraction"] <= plan.maximum_alias_fraction
        and result["arm_completeness_gap"] <= plan.maximum_arm_completeness_gap
        and result["arm_share_p_value"] >= 0.001
    )
    return result


def required_sources(variances, plan):
    """Blinded rule: total source clusters as a function of first-stage contrast variances only.

    The variance across sources of a per-source contrast is independent of its mean under the
    analysis model, so this rule sees nothing about the sign or size of the separation. It can
    only add sources. ``precision_futility`` means the variance is so large that even the
    maximum would leave less than an even chance at the design effect, so no source is added.
    That is a statement about attainable precision. It is never evidence about the effect.
    """
    df = plan.first_stage_sources - 1
    gap, worst = plan.design_effect - plan.margin, float(max(variances))
    reach = quantile(1 - plan.alpha, df)
    needed = math.ceil((reach + quantile(plan.contrast_power, df)) ** 2 * worst / gap**2)
    needed = max(plan.first_stage_sources, math.ceil(needed / plan.strata) * plan.strata)
    futile = reach**2 * worst / gap**2 > plan.maximum_sources
    total = plan.first_stage_sources if futile else min(needed, plan.maximum_sources)
    return dict(total=total, uncapped=needed, precision_futility=bool(futile))


def blinded_interim(rows, first_stage, plan):
    """The only look at first-stage data before the final analysis.

    ``public`` holds what may be seen: the prescribed total and outcome-free capture support.
    ``sealed`` holds the contrast variances and why the total came out as it did; it is
    stored unread until the final analysis. Neither part contains a mean, a per-source
    contrast or any statistic labelled by arm. A total equal to the first stage does not say
    whether the variance was small or precision was futile.
    """
    rows = [r for r in rows if r["source"] in set(first_stage)]
    contrasts, unevaluable = source_contrasts(rows, plan)
    if unevaluable or len(first_stage) != plan.first_stage_sources or set(contrasts) != set(first_stage):
        raise ValueError(
            f"stage one needs {plan.first_stage_sources} evaluable sources; not evaluable: {unevaluable}"
        )
    variances = np.var([contrasts[s] for s in first_stage], axis=0, ddof=1)
    rule = required_sources(variances, plan)
    public = dict(
        abi=plan.abi + "_interim_public",
        first_stage_sources=len(first_stage),
        prescribed_total_sources=rule["total"],
        support=support(rows, plan),
        released="prescribed total and outcome-free capture support only",
    )
    sealed = dict(
        abi=plan.abi + "_interim_sealed",
        contrast_variances=[float(v) for v in variances],
        uncapped_sources=rule["uncapped"],
        precision_futility=rule["precision_futility"],
        prescribed_total_sources=rule["total"],
    )
    return dict(public=public, sealed=sealed)


def analyse(contrasts, strata, plan):
    """Two-stage test and diagnostics on per-source contrasts, first-stage sources first.

    Stein's two-stage procedure: the mean uses every source, the standard error uses the
    first-stage variance with its degrees of freedom. The level is then exact under normality
    for any rule that chose the total from first-stage variances alone. Strata are weighted
    equally, which requires equal numbers of sources per stratum.
    """
    x, strata = np.asarray(contrasts, dtype=float), np.asarray(strata)
    first = plan.first_stage_sources
    if x.ndim != 2 or x.shape[1] != 2 or len(x) < first or len(strata) != len(x):
        raise ValueError("one lower and one upper contrast per source, first stage first")
    labels = sorted(set(strata.tolist()))
    balanced = all(len({int(np.sum(part == s)) for s in labels}) == 1 for part in (strata, strata[:first]))
    if len(labels) != plan.strata or not balanced:
        raise ValueError("equal numbers of sources per complexity stratum, in stage one and overall")
    size = len(x) // len(labels)
    variances = x[:first].var(axis=0, ddof=1)
    stratum_means = np.array([x[strata == s].mean(axis=0) for s in labels])
    mean = stratum_means.mean(axis=0)  # equal weight per stratum
    error = np.sqrt(variances / len(x))
    # Qualifying needs both contrasts, so each is tested at alpha. Failing needs only one,
    # so each upper bound is taken at alpha / 2 to keep that verdict at alpha as well.
    lower = mean - quantile(1 - plan.alpha, first - 1) * error
    upper = mean + quantile(1 - plan.alpha / 2, first - 1) * error
    if np.all(lower > plan.margin):
        verdict = VERDICTS[0]
    elif np.any(upper < plan.margin):
        verdict = VERDICTS[1]
    else:
        verdict = VERDICTS[2]
    # Complexity is a diagnostic. Intervals use the pooled within-stratum variance and are not
    # adjusted for the two-stage design; a handful of sources per tercile cannot show uniformity.
    within_df = len(x) - len(labels)
    within = sum(((x[strata == s] - m) ** 2).sum(axis=0) for s, m in zip(labels, stratum_means)) / within_df
    half = float(stats.t.ppf(0.975, within_df)) * np.sqrt(within / size)
    between = size * ((stratum_means - mean) ** 2).sum(axis=0) / (len(labels) - 1)
    differ = [
        float(stats.f.sf(b / w, len(labels) - 1, within_df)) if w > 0 else 1.0
        for b, w in zip(between, within)
    ]
    heterogeneous = bool(2 * min(differ) < plan.heterogeneity_alpha)  # two contrasts examined
    separating = int(np.sum(np.all(x > plan.margin, axis=1)))
    prevalence = float(stats.beta.ppf(plan.alpha, separating, len(x) - separating + 1)) if separating else 0.0
    return dict(
        verdict=verdict,
        designation=HETEROGENEOUS if verdict == VERDICTS[0] and heterogeneous else None,
        sources=len(x),
        degrees_of_freedom=first - 1,
        mean_contrasts=[float(v) for v in mean],
        lower_bounds=[float(v) for v in lower],
        upper_bounds=[float(v) for v in upper],
        p_values_above_margin=[float(stats.t.sf(v, first - 1)) for v in (mean - plan.margin) / error],
        realised_share_of_requested_step=[float(v / (RATIOS[1] - RATIOS[0])) for v in mean],
        first_stage_contrast_sd=[float(v) for v in np.sqrt(variances)],
        complexity=dict(
            strata=[str(s) for s in labels],
            sources_per_stratum=size,
            means=[[float(v) for v in row] for row in stratum_means],
            intervals95=[[[float(m - h), float(m + h)] for m, h in zip(row, half)] for row in stratum_means],
            heterogeneity_p_values=differ,
            heterogeneous_by_complexity=heterogeneous,
            diagnostic_only=True,
            no_flag_is_not_evidence_of_uniformity=True,
        ),
        separating_sources=separating,
        separating_share_lower_bound=prevalence,
    )


def decide(contrasts, strata, plan):
    """The confirmatory analysis: refuses any number of sources but the one the blinded rule prescribed."""
    x = np.asarray(contrasts, dtype=float)
    if x.ndim != 2 or len(x) < plan.first_stage_sources:
        raise ValueError("one lower and one upper contrast per source, first stage first")
    rule = required_sources(x[: plan.first_stage_sources].var(axis=0, ddof=1), plan)
    if len(x) != rule["total"]:
        raise ValueError(f"the blinded rule prescribed {rule['total']} sources, not {len(x)}")
    return dict(analyse(x, strata, plan), rule=rule)


def simulate(rng, draws, sources, scenario, plan):
    """Per-source contrasts from simulated cohorts: [draws, sources, 2]. Planning only."""
    shape = (draws, sources, plan.regimes, plan.peers_per_regime, plan.holds_per_peer)
    shift = rng.normal(0, scenario.source_contrast_sd, (draws, sources))
    saturating = (np.arange(sources) % plan.strata) < scenario.saturating_strata
    lower = scenario.lower_effect + shift
    upper = np.where(saturating, scenario.saturation, 1.0) * (scenario.upper_effect + shift)
    live = (np.arange(plan.regimes) >= scenario.dead_regimes)[None, None, :, None, None]
    arms = rng.integers(len(RATIOS), size=shape)
    wide = (..., None, None, None)
    response = live * ((arms >= 1) * lower[wide] + (arms == 2) * upper[wide])
    y = (
        response
        + rng.normal(0, scenario.peer_sd, (*shape[:-1], 1))
        + rng.normal(0, scenario.cohort_sd, shape)
    )
    means = []
    for arm in range(len(RATIOS)):
        chosen = arms == arm
        count = chosen.sum(axis=(-1, -2))
        cell = np.where(count > 0, (y * chosen).sum(axis=(-1, -2)) / np.maximum(count, 1), np.nan)
        means.append(np.nanmean(cell, axis=-1))  # an empty cell is vanishingly rare; average the rest
    return np.stack([means[1] - means[0], means[2] - means[1]], axis=-1)


def operating_characteristics(scenario, plan, draws=20000, seed=0, fixed=(), batch=500):
    """Verdict frequencies of the adaptive design and of fixed designs on the same simulated sources."""
    rng = np.random.default_rng(seed)
    designs = {"adaptive": plan}
    designs.update({f"fixed_{n}": replace(plan, first_stage_sources=n, maximum_sources=n) for n in fixed})
    widest = max(d.maximum_sources for d in designs.values())
    strata = np.arange(widest) % plan.strata
    tally = {name: Counter() for name in designs}
    totals, spread = Counter(), []
    for start in range(0, draws, batch):
        samples = simulate(rng, min(batch, draws - start), widest, scenario, plan)
        spread.append(samples.reshape(-1, 2).std(axis=0))
        for sample in samples:
            for name, design in designs.items():
                first = sample[: design.first_stage_sources]
                total = required_sources(first.var(axis=0, ddof=1), design)["total"]
                result = decide(sample[:total], strata[:total], design)
                tally[name][result["verdict"]] += 1
                tally[name]["flagged_heterogeneous"] += result["complexity"]["heterogeneous_by_complexity"]
                if name == "adaptive":
                    totals[total] += 1
    report = {
        name: {key: counts[key] / draws for key in (*VERDICTS, "flagged_heterogeneous")}
        for name, counts in tally.items()
    }
    report["adaptive"]["mean_sources"] = sum(n * c for n, c in totals.items()) / draws
    report["adaptive"]["sources_distribution"] = {str(n): c / draws for n, c in sorted(totals.items())}
    implied = [float(v) for v in np.mean(spread, axis=0)]  # between-source and within-source parts together
    return dict(scenario=asdict(scenario), draws=draws, per_source_contrast_sd=implied, designs=report)


def rule_table(plan):
    """Largest first-stage contrast SD that still leads to each total, for the registration text."""
    df = plan.first_stage_sources - 1
    gap = plan.design_effect - plan.margin
    span = quantile(1 - plan.alpha, df) + quantile(plan.contrast_power, df)
    rows = [
        dict(total=n, largest_first_stage_sd=gap * math.sqrt(n) / span)
        for n in range(plan.first_stage_sources, plan.maximum_sources + 1, plan.strata)
    ]
    futile = gap * math.sqrt(plan.maximum_sources) / quantile(1 - plan.alpha, df)
    return dict(rows=rows, precision_futility_above_sd=futile, degrees_of_freedom=df)


def power_report(plan, scenarios, draws, seed, fixed=(6, 9, 12, 18, 24), peers=(5, 10, 20)):
    reference = next((s for s in scenarios if s.name == "design_effect_smoke_noise"), scenarios[0])
    replication = {}
    for count in peers:  # peers are cheap and sources are not: what within-source replication buys
        varied = replace(plan, peers_per_regime=count)
        entry = operating_characteristics(reference, varied, max(100, draws // 4), seed + 1000 + count)
        replication[str(count)] = dict(
            entry["designs"]["adaptive"], per_source_contrast_sd=entry["per_source_contrast_sd"]
        )
    return dict(
        abi=plan.abi,
        plan=asdict(plan),
        rule=rule_table(plan),
        scenarios=[
            operating_characteristics(s, plan, draws, seed + i, fixed) for i, s in enumerate(scenarios)
        ],
        peers_per_regime_sensitivity=dict(scenario=reference.name, designs=replication),
        planning_assumptions_not_measurements=True,
        native_data_collected=False,
        models_fitted=0,
    )
