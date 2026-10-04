"""Group-cluster intervals and identical-policy variability, never frame-level inference."""

from collections import defaultdict

import numpy as np

from .native_protocol import finite, require


def cluster_estimate(values, seed=1901, resamples=4000):
    """Each value is one content/network group's repeat-averaged paired contrast."""
    a = np.asarray(values, dtype=float)
    require(a.ndim == 1 and len(a) > 0 and np.isfinite(a).all(), "finite independent group effects required")
    result = dict(mean=float(a.mean()), groups=len(a), unit="source_schedule_group", ci95=None)
    if len(a) > 1:
        rng = np.random.default_rng(seed)
        means = a[rng.integers(0, len(a), size=(resamples, len(a)))].mean(axis=1)
        result["ci95"] = np.quantile(means, [0.025, 0.975]).tolist()
    return result


def analyze_native_rows(rows, protocol):
    """Require the whole frozen panel; never silently drop failed/missing peers."""
    groups = {g["id"]: g for g in protocol["groups"]}
    conditions = protocol["conditions"]
    expected = {(g, c, r) for g in groups for c in conditions for r in range(protocol["repetitions"])}
    actual = {(x["group"], x["condition"], x["repetition"]) for x in rows}
    require(len(rows) == len(actual) and actual == expected, "incomplete/duplicate native study panel")
    metrics = ("utility", "ontime_fraction", "inference_p99_ms")
    by_group = defaultdict(list)
    for row in rows:
        require(row["family"] == groups[row["group"]]["family"], "native group family mismatch")
        require(
            all(finite(row[k]) for k in metrics) and 0 <= row["ontime_fraction"] <= 1,
            "invalid native episode metrics",
        )
        by_group[row["group"], row["condition"]].append(row)
    means = {
        c: {k: float(np.mean([np.mean([x[k] for x in by_group[g, c]]) for g in groups])) for k in metrics}
        for c in conditions
    }
    result = dict(
        means=means,
        episodes=len(rows),
        independent_groups=len(groups),
        uncertainty_unit="source_schedule_group",
        repeated_peers_are_not_independent_groups=True,
        intervals_conditional_on_frozen_model_and_synthetic_families=True,
        identical_packet_trajectories=False,
        SOTA_achieved=False,
        tail_budget_failures=[
            x["id"] for x in rows if x["inference_p99_ms"] > protocol["limits"]["inference_p99_ms"]
        ],
    )
    if protocol["stage"] == "repeatability":
        differences, spreads = [], []
        for g in groups:
            peers = by_group[g, "rlcd-a"] + by_group[g, "rlcd-b"]
            spread = dict(group=g, family=groups[g]["family"], repeats=len(peers))
            for k in ("utility", "ontime_fraction"):
                a = np.asarray([x[k] for x in peers])
                spread[k + "_span"] = float(np.ptp(a))
                spread[k + "_std"] = float(a.std(ddof=1))
            differences.append(
                {
                    k: float(
                        np.mean([x[k] for x in by_group[g, "rlcd-a"]])
                        - np.mean([x[k] for x in by_group[g, "rlcd-b"]])
                    )
                    for k in ("utility", "ontime_fraction")
                }
            )
            spread["signal_mean_spans"] = {
                name: float(np.ptp([x["signals"][name] for x in peers if x["signals"][name] is not None]))
                if sum(x["signals"][name] is not None for x in peers) >= 2
                else None
                for name in peers[0].get("signals", {})
            }
            spreads.append(spread)
        limits = protocol["limits"]
        result["identical_policy"] = dict(
            group_spreads=spreads,
            alias_differences={
                k: cluster_estimate([x[k] for x in differences]) for k in ("utility", "ontime_fraction")
            },
            same_policy_mapping_not_same_history=True,
            passed=not result["tail_budget_failures"]
            and all(
                x["utility_span"] <= limits["repeatability_utility_span"]
                and x["ontime_fraction_span"] <= limits["repeatability_ontime_span"]
                for x in spreads
            ),
            causal_policy_gain_inferred=False,
        )
    if protocol["stage"] in ("validation", "test"):
        contrasts = {}
        for reference in ("baseline", "bwe", "gcc"):
            case = []
            for g in groups:
                case.append(
                    dict(
                        group=g,
                        family=groups[g]["family"],
                        **{
                            k: float(
                                np.mean([x[k] for x in by_group[g, "candidate"]])
                                - np.mean([x[k] for x in by_group[g, reference]])
                            )
                            for k in ("utility", "ontime_fraction")
                        },
                    )
                )
            contrasts[reference] = dict(
                aggregate={k: cluster_estimate([x[k] for x in case]) for k in ("utility", "ontime_fraction")},
                source_phases={
                    phase: cluster_estimate(
                        [
                            float(
                                np.mean([x["phases"][phase]["utility"] for x in by_group[g, "candidate"]])
                                - np.mean([x["phases"][phase]["utility"] for x in by_group[g, reference]])
                            )
                            for g in groups
                        ]
                    )
                    for phase in ("high", "collapse", "recovery")
                },
                families={
                    f: {
                        k: cluster_estimate([x[k] for x in case if x["family"] == f])
                        for k in ("utility", "ontime_fraction")
                    }
                    for f in sorted({x["family"] for x in case})
                },
                cases=case,
            )
        result["candidate_minus_control"] = contrasts
    return result


def validation_selection(report, protocol):
    require(protocol["stage"] == "validation", "selection only allowed on validation")
    limits = protocol["limits"]
    failures = []
    if report["independent_groups"] < limits["min_validation_groups"]:
        failures.append("insufficient_independent_groups")
    families = {g["family"] for g in protocol["groups"]}
    if families != {"stable", "collapse", "variable", "brief-collapse"}:
        failures.append("missing_regime")
    if report["tail_budget_failures"]:
        failures.append("inference_tail_budget")
    for reference, contrast in report["candidate_minus_control"].items():
        for key, lower in [
            ("utility", limits["min_utility_gain"]),
            ("ontime_fraction", -limits["max_ontime_drop"]),
        ]:
            interval = contrast["aggregate"][key]["ci95"]
            if interval is None or interval[0] < lower or (key == "utility" and interval[0] == lower):
                failures.append(reference + ":aggregate:" + key)
        high = contrast["source_phases"]["high"]["ci95"]
        if high is None or high[0] < -limits["max_family_utility_drop"]:
            failures.append(reference + ":high_phase_quality")
        for family, metrics in contrast["families"].items():
            for key, lower in [
                ("utility", -limits["max_family_utility_drop"]),
                ("ontime_fraction", -limits["max_ontime_drop"]),
            ]:
                interval = metrics[key]["ci95"]
                if metrics[key]["groups"] < 2 or interval is None or interval[0] < lower:
                    failures.append(reference + ":" + family + ":" + key)
    return dict(
        selected="baseline" if failures else "candidate",
        failures=failures,
        synthetic_native_recipe_only=True,
        native_safety_certificate=False,
        SOTA_achieved=False,
    )
