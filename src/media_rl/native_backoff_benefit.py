"""Native Phase B1: does backing off help when the sender has seen congestion? Estimator and test.

One confirmatory question of fresh native data, under the unchanged three-arm randomised hold
protocol of Native Phase N1: in holds flagged before they start by a stalled estimate, is the
on-time quality proxy higher at the two lower requested ratios than at the top one? This module
is the executable form of the registered flag, estimand, test and outcomes. It reads no native
data by itself, fits no model and lets no controller act.
"""

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import stats

from . import native_actuator_qualification as actuator

ABI = "native_backoff_benefit_b1"
RATIOS = actuator.RATIOS  # 0.65, 0.85, 1.05 of the sender's estimate, as in N1
OUTCOMES = ("helps", "helps_below_practical_gate", "no_practically_relevant_benefit", "inconclusive")
ENDPOINT = "utility"  # the auditor's on-time sampled RGB-PSNR contribution in the outcome window


@dataclass(frozen=True)
class Plan:
    abi: str = ABI
    growth_limit: float = 1.05  # flagged: the frozen estimate is below this multiple of the previous hold's
    weights: list = field(default_factory=lambda: [0.5, 0.5, -1.0])  # the two lower ratios against the top
    practical_gate: float = 1.0  # Phase N2's practical-effect gate, in the endpoint's units
    alpha: float = 0.025  # one-sided, for each of the two statements
    strata: int = 3  # complexity terciles, weighted equally
    minimum_sources: int = 30  # below this B1 is not a confirmatory study
    regimes: int = 4
    peers_per_regime: int = 10  # repeated measurements inside a source; never units of inference
    holds_per_peer: int = 6
    minimum_cell_cohorts: int = 3  # planned cohorts per source x regime x arm, checked before capture
    minimum_flagged_cell: int = 3  # flagged complete holds per arm for a source to be evaluable
    minimum_complete_fraction: float = 0.95  # N1's gates, unchanged
    maximum_alias_fraction: float = 0.10
    maximum_arm_completeness_gap: float = 0.05
    maximum_skipped_share: float = 0.10  # planned sources that may turn out not evaluable

    def validate(self):
        counts = (self.strata, self.minimum_sources, self.regimes, self.peers_per_regime)
        counts += (self.holds_per_peer, self.minimum_cell_cohorts, self.minimum_flagged_cell)
        if self.abi != ABI or any(type(v) is not int or v < 1 for v in counts):
            raise ValueError("B1 plan needs its ABI and positive integer counts")
        if len(self.weights) != len(RATIOS) or abs(sum(self.weights)) > 1e-12 or not self.weights[-1] < 0:
            raise ValueError("weights must be a contrast of the three ratios against the top one")
        if not (self.growth_limit > 0 and self.practical_gate > 0 and 0 < self.alpha < 0.5):
            raise ValueError("growth limit, practical gate and alpha out of range")
        if self.minimum_sources % self.strata or self.minimum_sources < 2 * self.strata:
            raise ValueError("the minimum must be whole stratum-balanced blocks, at least two per stratum")
        if not 0 <= self.maximum_skipped_share < 1:
            raise ValueError("skipped share out of range")
        return self


@dataclass(frozen=True)
class Capture:
    """Planning inputs fixed with the registration. None of them is an outcome."""

    seed: int = 261010
    template: str = "results/native-action-excitation-train-sintel-v1/runtime.json"
    reservation_root: str = "results"


@dataclass(frozen=True)
class Scenario:
    """A planning assumption used by the mock dry run. None of these is a measurement."""

    name: str
    flagged_benefit: float  # mean benefit of backing off in flagged holds
    other_benefit: float  # the same in holds that are not flagged
    source_sd: float  # spread of the benefit over sources
    cohort_sd: float


@dataclass(frozen=True)
class Registration:
    plan: Plan
    capture: Capture
    secondary_flags: dict
    planning: dict
    scenarios: tuple


def load_registration(path):
    data = json.loads(Path(path).read_text())
    scenarios = tuple(Scenario(**s) for s in data.pop("scenarios"))
    capture, planning = Capture(**data.pop("capture")), data.pop("planning")
    flags = data.pop("secondary_flags")
    if type(capture.seed) is not int or not 0 <= capture.seed < 2**32:
        raise ValueError("registered planning seed out of range")
    if any(not isinstance(v, (int, float)) or v <= 0 for v in flags.values()):
        raise ValueError("secondary flags are positive thresholds")
    return Registration(Plan(**data).validate(), capture, flags, planning, scenarios)


def flag_rows(rows, plan, signal=None, threshold=None):
    """Every hold with a predecessor in its peer, marked by the registered flag.

    The registered flag compares the frozen estimates of consecutive holds, both observed before
    the hold starts: flagged when this one is below ``growth_limit`` times the previous one. With
    ``signal`` it is a secondary flag instead: flagged when that pre-hold value exceeds
    ``threshold``, and left out when the value is absent. Each returned hold carries its successor
    and the arm of the hold before it.
    """
    peers = defaultdict(dict)
    for r in rows:
        peers[r["trial_id"]][r["epoch"]] = r
    out = []
    for holds in peers.values():
        for epoch, r in sorted(holds.items()):
            before = holds.get(epoch - 1)
            if before is None:
                continue
            if signal is None:
                flagged = r["base_bwe_bps"] < plan.growth_limit * before["base_bwe_bps"]
            elif r[signal] is None:
                continue
            else:
                flagged = r[signal] > threshold
            more = dict(flagged=bool(flagged), following=holds.get(epoch + 1), previous_arm=before["arm"])
            out.append(dict(r, **more))
    return out


def source_benefits(held, plan, key=ENDPOINT, weights=None, flagged=True, following=False):
    """Per source: the contrast of arm means of ``key`` over its flagged (or other) holds.

    Unadjusted arm means on purpose: the arm is IID with equal propensity and independent of
    everything before the hold, so within flagged holds a difference of means is unbiased without
    a model. Schedules are pooled, because a controller sees the state and not the schedule.
    ``following`` scores the next hold of the same peer by this hold's arm. A source without the
    minimum number of scored holds in every arm the contrast uses is returned as not evaluable.
    """
    weights = plan.weights if weights is None else weights
    cells = defaultdict(list)
    for r in held:
        scored = r["following"] if following else r
        if r["flagged"] is flagged and scored is not None and scored["complete"] is True:
            cells[(r["source"], r["arm"])].append(scored[key])
    used = [arm for arm, weight in enumerate(weights) if weight]
    benefits, unevaluable = {}, []
    for source in sorted({r["source"] for r in held}):
        if any(len(cells[(source, arm)]) < plan.minimum_flagged_cell for arm in used):
            unevaluable.append(source)
            continue
        benefits[source] = float(sum(weights[arm] * np.mean(cells[(source, arm)]) for arm in used))
    return benefits, unevaluable


def flagged_support(held, plan):
    """How many holds the flag marks and how thin the thinnest source x arm cell is. No outcome."""
    cells = defaultdict(int)
    for r in held:
        if r["flagged"] and r["complete"] is True:
            cells[(r["source"], r["arm"])] += 1
    sources = sorted({r["source"] for r in held})
    smallest = min((cells[(s, arm)] for s in sources for arm in range(len(RATIOS))), default=0)
    after_top = [r["previous_arm"] == len(RATIOS) - 1 for r in held if r["flagged"]]
    return dict(
        holds_with_a_predecessor=len(held),
        flagged_share=float(np.mean([r["flagged"] for r in held])) if held else 0.0,
        share_of_flagged_holds_after_the_top_ratio=float(np.mean(after_top)) if after_top else 0.0,
        smallest_flagged_cell=int(smallest),
        minimum_flagged_cell=plan.minimum_flagged_cell,
    )


def summary(values, alpha=0.025):
    """Mean over sources with a two-sided interval at ``1 - 2 * alpha``. Descriptive."""
    x = np.asarray(values, dtype=float)
    if len(x) < 2:
        return dict(sources=len(x), mean=float(x.mean()) if len(x) else None, interval=None)
    half = float(stats.t.ppf(1 - alpha, len(x) - 1)) * float(x.std(ddof=1)) / math.sqrt(len(x))
    return dict(
        sources=len(x), mean=float(x.mean()), interval=[float(x.mean() - half), float(x.mean() + half)]
    )


def analyse(values, strata, plan):
    """The registered test on per-source benefits: two one-sided statements and one outcome.

    Strata are weighted equally, which needs equal numbers of sources per stratum. The standard
    error is the unstratified one, which is conservative when strata differ.
    """
    x, strata = np.asarray(values, dtype=float), np.asarray(strata)
    labels = sorted(set(strata.tolist()))
    balanced = len({int(np.sum(strata == s)) for s in labels}) == 1
    if x.ndim != 1 or len(x) != len(strata) or len(labels) != plan.strata or not balanced:
        raise ValueError("one benefit per source and equal numbers of sources per complexity stratum")
    if len(x) < 2 * plan.strata:
        raise ValueError("at least two sources per stratum")
    stratum_means = [float(x[strata == s].mean()) for s in labels]
    mean, spread = float(np.mean(stratum_means)), float(x.std(ddof=1))
    error = spread / math.sqrt(len(x))
    quantile = float(stats.t.ppf(1 - plan.alpha, len(x) - 1))
    lower, upper = mean - quantile * error, mean + quantile * error
    helps, small = lower > 0, upper < plan.practical_gate
    outcome = OUTCOMES[1 if small else 0] if helps else OUTCOMES[2 if small else 3]
    return dict(
        outcome=outcome,
        sources=len(x),
        degrees_of_freedom=len(x) - 1,
        mean_benefit=mean,
        lower_bound=float(lower),
        upper_bound=float(upper),
        standard_error=error,
        per_source_sd=spread,
        p_value_above_zero=float(stats.t.sf(mean / error, len(x) - 1)) if error > 0 else None,
        backing_off_helps=bool(helps),
        benefit_below_practical_gate=bool(small),
        stratum_means=stratum_means,
        sources_with_a_positive_benefit=int(np.sum(x > 0)),
    )


def support(rows, plan):
    """N1's capture-quality gates, by N1's own frozen function. None looks at an outcome by arm."""
    return actuator.support(rows, plan)


def power(sources, effect, spread, alpha=0.025):
    """Chance that the lower bound clears zero, for a true mean benefit and a per-source spread."""
    critical = stats.t.ppf(1 - alpha, sources - 1)
    return float(stats.nct.sf(critical, sources - 1, effect * math.sqrt(sources) / spread))


def power_table(plan, planning):
    """Planning figures from the registered assumptions. Not measurements of B1."""
    rows = []
    for spread in (planning["per_source_sd"], planning["pessimistic_sd"]):
        for sources in planning["sources"]:
            half = float(stats.t.ppf(1 - plan.alpha, sources - 1)) * spread / math.sqrt(sources)
            rows.append(
                dict(
                    per_source_sd=spread,
                    sources=sources,
                    interval_half_width=half,
                    power={
                        f"{effect:g}": power(sources, effect, spread, plan.alpha)
                        for effect in planning["effects"]
                    },
                    largest_estimate_read_as_below_the_gate=plan.practical_gate - half,
                )
            )
    return dict(planning_only=True, source=planning["source"], rows=rows)
