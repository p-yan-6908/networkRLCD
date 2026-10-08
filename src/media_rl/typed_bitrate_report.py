"""Paper evidence for the typed JevBWE study: macros, tables and one figure.

Every number is read from ``report.json``; nothing is typed in by hand.
"""

import hashlib
import json
from pathlib import Path

import numpy as np

ALIASES = {
    "choice_rlcd_bayes": ("Bayes", "Typed choice, RLCD, payoff-weighted"),
    "choice_rlcd_gated": ("Gated", "Typed choice, RLCD, confidence-gated"),
    "choice_rlcd_map": ("Map", "Typed choice, RLCD, most probable (no guard)"),
    "choice_analytic_bayes": ("Analytic", "Typed choice, exact gradient, payoff-weighted"),
    "regress_greedy": ("Regress", "Advantage regression (untyped)"),
    "oracle": ("Oracle", "Hindsight oracle (non-causal bound)"),
}
PANELS = {"id": "Id", "ood": "Ood", "all": "All"}


def signed(value, digits=3):
    if value is None:  # a quantity with no rows behind it, such as a rule that never left the base
        return "n/a"
    return f"{value:+.{digits}f}".replace("-", "$-$").replace("+", "$+$")


def plain(value, digits=3):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}".replace("-", "$-$")


def interval(c):
    return f"[{signed(c['interval95'][0])}, {signed(c['interval95'][1])}]"


def ratio_name(method):
    return f"Fixed {float(method.removeprefix('fixed_')):.2f}$\\times$BWE"


def panel_macros(test, prefix):
    rows = {}
    for panel, tag in PANELS.items():
        data = test[panel]
        rows[f"{prefix}{tag}BestFixedRatio"] = data["references"]["best_fixed"].removeprefix("fixed_")
        for key, reference in data["references"].items():
            name = "".join(part.title() for part in key.split("_"))
            rows[f"{prefix}{tag}{name}Utility"] = plain(data["methods"][reference]["utility"])
            rows[f"{prefix}{tag}{name}Unsafe"] = plain(100 * data["methods"][reference]["unsafe"], 2)
        for method, (alias, _) in ALIASES.items():
            entry = data["methods"][method]
            rows[f"{prefix}{tag}{alias}Utility"] = plain(entry["utility"])
            rows[f"{prefix}{tag}{alias}Unsafe"] = plain(100 * entry["unsafe"], 2)
            for key, tail in (("best_fixed", "VsBest"), ("base", "VsBase"), ("legacy_fallback", "VsLegacy")):
                c = data["contrasts"][method][key]
                rows[f"{prefix}{tag}{alias}{tail}"] = signed(c["utility"])
                rows[f"{prefix}{tag}{alias}{tail}Interval"] = interval(c)
            if "reliability" in entry:
                rows[f"{prefix}{tag}{alias}Ece"] = plain(entry["reliability"]["ece"])
                rows[f"{prefix}{tag}{alias}Accuracy"] = plain(100 * entry["reliability"]["accuracy"], 1)
                rows[f"{prefix}{tag}{alias}Confidence"] = plain(100 * entry["reliability"]["confidence"], 1)
            if "override_share" in entry:
                rows[f"{prefix}{tag}{alias}Override"] = plain(100 * entry["override_share"], 1)
            if "per_model_seed" in entry:
                rows[f"{prefix}{tag}{alias}SeedMin"] = plain(min(entry["per_model_seed"]))
                rows[f"{prefix}{tag}{alias}SeedMax"] = plain(max(entry["per_model_seed"]))
            if entry.get("reasons"):
                total = sum(entry["reasons"].values())
                for reason, name in (("unsupported_history", "Unsupported"), ("stale_telemetry", "Stale")):
                    share = 100 * entry["reasons"].get(reason, 0) / total
                    rows[f"{prefix}{tag}{alias}{name}"] = plain(share, 1)
        gap = (
            data["methods"]["oracle"]["utility"]
            - data["methods"][data["references"]["best_fixed"]]["utility"]
        )
        won = data["contrasts"]["choice_rlcd_bayes"]["best_fixed"]["utility"]
        rows[f"{prefix}{tag}HeadroomShare"] = plain(100 * won / gap, 0) if gap > 1e-9 else "n/a"
    # How the ratio that is best on held-out families in hindsight does in distribution.
    rival = test["ood"]["references"]["best_fixed"]
    rows[f"{prefix}IdOodBestFixedUtility"] = plain(test["id"]["methods"][rival]["utility"])
    return rows


def macros(report, diagnosis, ablation=None, robustness=None):
    test = report["panels"]["test"]
    training = report["training"]
    rows = {
        "TypedModelSeeds": test["all"]["model_seeds"],
        "TypedTraceSeeds": test["all"]["trace_seeds"],
        "TypedScenarios": len(test["all"]["scenarios"]),
        "TypedIdScenarios": len(test["id"]["scenarios"]),
        "TypedOodScenarios": len(test["ood"]["scenarios"]),
        "TypedBaseRatio": f"{report['base_tuning']['selected']:.2f}",
        "TypedTrainRows": f"{sum(r['rows'] for r in training[0]['rounds']):,}".replace(",", "{,}"),
        "TypedRounds": len(training[0]["rounds"]),
        "TypedParameters": f"{training[0]['parameters']['choice_rlcd']:,}".replace(",", "{,}"),
        "TypedInferenceMicros": f"{report['inference_us']:.0f}",
    }
    temperatures = [t["calibration"]["choice_rlcd"]["temperature"] for t in training]
    rows["TypedTemperatureMin"] = f"{min(temperatures):.2f}"
    rows["TypedTemperatureMax"] = f"{max(temperatures):.2f}"
    thresholds = sorted({t["calibration"]["choice_rlcd"]["threshold"] for t in training})
    rows["TypedThresholds"] = ", ".join(f"{t:.1f}" for t in thresholds)
    rows.update(panel_macros(test, "Typed"))
    if ablation:
        # Same model seed, same ID validation panel, long-memory summaries zeroed.
        seed = ablation["training"][0]["model_seed"]
        full = report["panels"]["validation"]["id"]["methods"]
        bare = ablation["panels"]["validation"]["id"]["methods"]
        for method, alias in (("choice_rlcd_bayes", "Bayes"), ("regress_greedy", "Regress")):
            rows[f"TypedAblation{alias}With"] = plain(full[method]["per_model_seed"][seed])
            rows[f"TypedAblation{alias}Without"] = plain(bare[method]["utility"])
    if robustness:
        rows["TypedUnboundedBaseRatio"] = f"{robustness['base_tuning']['selected']:.2f}"
        rows.update(panel_macros(robustness["panels"]["test"], "TypedUnbounded"))
    if diagnosis:
        for bwe, tag in (("legacy", "Legacy"), ("acked", "Acked")):
            m = diagnosis[bwe]["methods"]
            rows[f"TypedDiag{tag}Best"] = f"{diagnosis[bwe]['best_fixed']:.2f}"
            rows[f"TypedDiag{tag}BestUtility"] = plain(
                m[f"fixed_{diagnosis[bwe]['best_fixed']:.2f}"]["utility"]
            )
            rows[f"TypedDiag{tag}FallbackUtility"] = plain(m["fixed_0.85"]["utility"])
            rows[f"TypedDiag{tag}OracleUtility"] = plain(m["oracle"]["utility"])
    return rows


def table_methods(test):
    names = [n for n in test["all"]["methods"] if n.startswith("fixed_")] + list(ALIASES)
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r" & \multicolumn{2}{c}{ID families} & \multicolumn{2}{c}{Held-out families} & All \\",
        r"Method & Utility & Unsafe \% & Utility & Unsafe \% & Utility \\",
        r"\midrule",
    ]
    for name in names:
        if name == "choice_rlcd_bayes" or name == "oracle":
            lines.append(r"\midrule")
        label = ALIASES[name][1] if name in ALIASES else ratio_name(name)
        cells = []
        for panel in ("id", "ood"):
            entry = test[panel]["methods"][name]
            cells += [plain(entry["utility"]), plain(100 * entry["unsafe"], 2)]
        cells.append(plain(test["all"]["methods"][name]["utility"]))
        lines.append(f"{label} & " + " & ".join(cells) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_contrasts(test):
    lines = [
        r"\begin{tabular}{lrlrl}",
        r"\toprule",
        r" & \multicolumn{2}{c}{ID families} & \multicolumn{2}{c}{Held-out families} \\",
        r"Method minus best fixed ratio & $\Delta$ utility & 95\% interval & $\Delta$ utility & 95\% interval \\",
        r"\midrule",
    ]
    for name, (_, label) in ALIASES.items():
        cells = []
        for panel in ("id", "ood"):
            c = test[panel]["contrasts"][name]["best_fixed"]
            cells += [signed(c["utility"]), interval(c)]
        lines.append(f"{label} & " + " & ".join(cells) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_calibration(test):
    lines = [
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Head and rule & Panel & Decisions & Accuracy \% & Confidence \% & ECE & NLL \\",
        r"\midrule",
    ]
    for name, (_, label) in ALIASES.items():
        for panel, title in (("id", "ID"), ("ood", "Held-out")):
            r = test[panel]["methods"][name].get("reliability")
            if r:
                cells = [
                    f"{r['rows']:,}".replace(",", "{,}"),
                    plain(100 * r["accuracy"], 1),
                    plain(100 * r["confidence"], 1),
                    plain(r["ece"]),
                    plain(r["nll"]),
                ]
                short = label.removeprefix("Typed choice, ")
                lines.append(f"{short[0].upper()}{short[1:]} & {title} & " + " & ".join(cells) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_scenarios(test):
    data = test["all"]
    shown = [data["references"]["base"], "choice_rlcd_bayes", "regress_greedy", "oracle"]
    fixed = [n for n in data["methods"] if n.startswith("fixed_")]
    lines = [
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Family & Split & Base & Best fixed (ratio) & Typed choice & Regression & Oracle \\",
        r"\midrule",
    ]
    for scenario in data["scenarios"]:
        split = "ID" if scenario in test["id"]["scenarios"] else "held-out"
        best = max(fixed, key=lambda n: data["methods"][n]["per_scenario"][scenario])
        value = {n: data["methods"][n]["per_scenario"][scenario] for n in [*shown, best]}
        cells = [
            plain(value[shown[0]]),
            f"{plain(value[best])} ({best.removeprefix('fixed_')})",
            plain(value[shown[1]]),
            plain(value[shown[2]]),
            plain(value[shown[3]]),
        ]
        lines.append(f"{scenario.replace('_', ' ')} & {split} & " + " & ".join(cells) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_diagnosis(diagnosis):
    names = [n for n in diagnosis["acked"]["methods"] if n.startswith("fixed_")]
    names = sorted(names, key=lambda n: float(n.removeprefix("fixed_"))) + ["oracle"]
    lines = [
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Policy & Unbounded estimator & Acked-rate-bounded estimator \\",
        r"\midrule",
    ]
    for name in names:
        label = ALIASES[name][1] if name in ALIASES else ratio_name(name)
        cells = [plain(diagnosis[bwe]["methods"][name]["utility"]) for bwe in ("legacy", "acked")]
        lines.append(f"{label} & " + " & ".join(cells) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_robustness(bounded, unbounded):
    """Same frozen pipeline under both estimators; identical traces, separate fits."""
    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Estimator & Method & ID utility & Held-out utility & All & Unsafe \% (all) \\",
        r"\midrule",
    ]
    for title, test in (("Unbounded (legacy)", unbounded), ("Acked-rate-bounded", bounded)):
        best = test["all"]["references"]["best_fixed"]
        shown = [(best, f"Best fixed ratio ({best.removeprefix('fixed_')})")]
        shown += [(n, ALIASES[n][1]) for n in ("choice_rlcd_bayes", "regress_greedy", "oracle")]
        for name, label in shown:
            cells = [plain(test[p]["methods"][name]["utility"]) for p in ("id", "ood", "all")]
            cells.append(plain(100 * test["all"]["methods"][name]["unsafe"], 2))
            lines.append(f"{title} & {label} & " + " & ".join(cells) + r" \\")
            title = ""
        lines.append(r"\midrule")
    return "\n".join([*lines[:-1], r"\bottomrule", r"\end{tabular}", ""])


def figure(test, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, accent, warm = "#1f2933", "#9aa5b1", "#1f6fb2", "#c2571a"
    plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 2.7), gridspec_kw=dict(width_ratios=[1, 1.9]))
    left.plot([0, 1], [0, 1], color=muted, linewidth=0.8, linestyle="--")
    for panel, colour, label in (("id", accent, "ID families"), ("ood", warm, "Held-out families")):
        bins = test[panel]["methods"]["choice_rlcd_bayes"]["reliability"]["bins"]
        sizes = [18 + 60 * b["rows"] / max(x["rows"] for x in bins) for b in bins]
        left.plot([b["confidence"] for b in bins], [b["accuracy"] for b in bins], color=colour, linewidth=1.2)
        left.scatter(
            [b["confidence"] for b in bins], [b["accuracy"] for b in bins], s=sizes, color=colour, label=label
        )
    left.set(xlim=(0, 1), ylim=(0, 1), xlabel="Reported confidence", ylabel="Hindsight accuracy")
    left.set_title("Reliability of the typed answer", loc="left", color=ink)
    left.legend(frameon=False, loc="upper left")
    data = test["all"]
    scenarios = data["scenarios"]
    series = (
        (data["references"]["base"], muted, "Base (tuned fixed ratio)"),
        ("choice_rlcd_bayes", accent, "Typed choice (RLCD)"),
        ("oracle", ink, "Hindsight oracle"),
    )
    for offset, (name, colour, label) in enumerate(series):
        values = [data["methods"][name]["per_scenario"][s] for s in scenarios]
        right.bar(
            [i + 0.27 * (offset - 1) for i in range(len(scenarios))], values, 0.25, color=colour, label=label
        )
    split = len(test["id"]["scenarios"]) - 0.5
    right.axvline(split, color=muted, linewidth=0.8, linestyle=":")
    right.axhline(0, color=ink, linewidth=0.6)
    right.set_xticks(range(len(scenarios)))
    right.set_xticklabels([s.replace("_", "\n") for s in scenarios], fontsize=6.5)
    right.set_ylabel("Mean utility")
    right.set_title("Utility by family (ID left of the dotted line)", loc="left", color=ink)
    right.legend(frameon=False, ncol=3, loc="lower left", fontsize=6.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


TITLES = {"id": "ID", "ood": "Held-out", "all": "All"}
RULE_NAMES = {
    "map": ("Map", "Most probable option", "choice_rlcd_map"),
    "gated": ("Gated", "Most probable, if confident enough", "choice_rlcd_gated"),
    "payoff_weighted": ("Bayes", "Payoff-weighted (the rule that runs)", "choice_rlcd_bayes"),
    "hindsight_best": ("Best", "Best option in hindsight (non-causal)", "oracle"),
}
PAIR_NAMES = {
    "rlcd_vs_exact_gradient": ("RlcdVsExact", "RLCD minus exact gradient"),
    "rlcd_vs_regression": ("RlcdVsRegress", "RLCD minus regression"),
    "payoff_weighted_vs_map": ("BayesVsMap", "Payoff-weighted minus most probable"),
    "payoff_weighted_vs_gated": ("BayesVsGated", "Payoff-weighted minus confidence-gated"),
}


def span(pair, digits=3, scale=1):
    if pair is None:  # a single family has no family-level interval
        return "n/a"
    return f"[{signed(scale * pair[0], digits)}, {signed(scale * pair[1], digits)}]"


def family_name(name):
    return name.replace("_", " ")


def contrast_macros(rows, name, c, digits=3, scale=1):
    rows[name] = signed(scale * c["mean"], digits)
    rows[f"{name}Seed"] = span(c["seed_interval95"], digits, scale)
    rows[f"{name}Positive"] = f"{c['positive_families']} of {c['families']}"
    if "family_interval95" in c:
        rows[f"{name}Family"] = span(c["family_interval95"], digits, scale)
        rows[f"{name}T"] = span(c["family_t_interval95"], digits, scale)


def frontier_gap(methods, name):
    """Utility of a method minus the fixed-ratio frontier at the same share of unsafe intervals."""
    points = sorted((m["unsafe"], m["utility"]) for n, m in methods.items() if n.startswith("fixed_"))
    xs, ys = [], []
    for x, y in points:
        best = max([y, *ys])
        if xs and x == xs[-1]:
            ys[-1] = best
        else:
            xs.append(x)
            ys.append(best)
    if methods[name]["unsafe"] < xs[0]:
        return None
    return methods[name]["utility"] - float(np.interp(methods[name]["unsafe"], xs, ys))


def payoff_macros(audit, prefix):
    """How much a right or wrong move is worth on either side of the base option."""
    table, base = audit["rules"]["payoff_mean"], audit["rules"]["ratios"].index(audit["rules"]["base_ratio"])
    below, above = range(base), range(base + 1, len(table))
    groups = dict(
        DownRight=[table[a][a] for a in below],
        UpRight=[table[a][a] for a in above],
        Overshoot=[table[a][b] for a in above for b in below],
        Undershoot=[table[a][b] for a in below for b in above],
    )
    rows = {}
    for name, values in groups.items():
        if values:
            rows[f"{prefix}Payoff{name}Min"] = signed(min(values))
            rows[f"{prefix}Payoff{name}Max"] = signed(max(values))
    return rows


def audit_macros(audit, prefix):
    """Macros of one audited panel: family-level contrasts, calibration, rules and trade-off."""
    rows = {}
    for panel, tag in PANELS.items():
        if panel not in audit["panels"]:
            continue
        data, trade = audit["panels"][panel], audit["tradeoff"][panel]
        rows[f"{prefix}{tag}Families"] = len(data["families"])
        rows[f"{prefix}{tag}TrainFixedRatio"] = data["train_fixed"].removeprefix("fixed_")
        rows[f"{prefix}{tag}HindsightFixedRatio"] = data["hindsight_fixed"].removeprefix("fixed_")
        rows[f"{prefix}{tag}Floor"] = plain(100 * trade["floor"], 2)
        for key, name in (("train_fixed", "TrainFixed"), ("hindsight_fixed", "HindsightFixed")):
            rows[f"{prefix}{tag}{name}Utility"] = plain(trade["methods"][data[key]]["utility"])
            rows[f"{prefix}{tag}{name}Unsafe"] = plain(100 * trade["methods"][data[key]]["unsafe"], 2)
        for method, (alias, _) in ALIASES.items():
            c = data["methods"][method]
            rows[f"{prefix}{tag}{alias}Utility"] = plain(trade["methods"][method]["utility"])
            rows[f"{prefix}{tag}{alias}Unsafe"] = plain(100 * trade["methods"][method]["unsafe"], 2)
            contrast_macros(rows, f"{prefix}{tag}{alias}VsTrain", c["utility_vs_train_fixed"])
            contrast_macros(rows, f"{prefix}{tag}{alias}VsHindsight", c["utility_vs_hindsight_fixed"])
            contrast_macros(rows, f"{prefix}{tag}{alias}UnsafeVsTrain", c["unsafe_vs_train_fixed"], 2, 100)
            gap = frontier_gap(trade["methods"], method)
            rows[f"{prefix}{tag}{alias}FrontierGap"] = "n/a" if gap is None else signed(gap)
        for key, (name, _) in PAIR_NAMES.items():
            contrast_macros(rows, f"{prefix}{tag}{name}", data["pairs"][key]["utility"])
        for method, alias in (("choice_rlcd_bayes", "Bayes"), ("choice_analytic_bayes", "Analytic")):
            cal = audit["calibration"][method][panel]
            by_family = [audit["families"][f]["methods"][method]["ece"] for f in data["families"]]
            rows[f"{prefix}{tag}{alias}Ece"] = plain(cal["ece"])
            rows[f"{prefix}{tag}{alias}EceFamily"] = (
                "[" + ", ".join(plain(v) for v in cal["family_interval95"]) + "]"
            )
            rows[f"{prefix}{tag}{alias}Accuracy"] = plain(100 * cal["accuracy"], 1)
            rows[f"{prefix}{tag}{alias}Confidence"] = plain(100 * cal["confidence"], 1)
            rows[f"{prefix}{tag}{alias}WorstFamily"] = family_name(cal["worst_family"])
            rows[f"{prefix}{tag}{alias}WorstEce"] = plain(max(by_family))
            rows[f"{prefix}{tag}{alias}BestEce"] = plain(min(by_family))
        rules = audit["rules"]["panels"][panel]
        rows[f"{prefix}{tag}LabelBase"] = plain(100 * rules["label_is_base"], 1)
        rows[f"{prefix}{tag}GuardBlocks"] = plain(100 * rules["guard_blocks"], 1)
        rows[f"{prefix}{tag}RulesDiffer"] = plain(100 * rules["payoff_weighted_differs_from_map"], 1)
        for key, name in (("map_advantage", "DifferMap"), ("payoff_weighted_advantage", "DifferBayes")):
            rows[f"{prefix}{tag}{name}"] = signed(rules["where_they_differ"][key])
        rows[f"{prefix}{tag}Predicted"] = signed(rules["predicted_advantage_when_leaving"])
        rows[f"{prefix}{tag}Realised"] = signed(rules["realised_advantage_when_leaving"])
        for rule, (alias, _, _) in RULE_NAMES.items():
            r = rules["rules"][rule]
            for key, name in (("leaves_base", "Leaves"), ("below_base", "Below"), ("above_base", "Above")):
                rows[f"{prefix}{tag}Rule{alias}{name}"] = plain(100 * r[key], 1)
            rows[f"{prefix}{tag}Rule{alias}Matches"] = plain(100 * r["matches_label"], 1)
            rows[f"{prefix}{tag}Rule{alias}Advantage"] = signed(r["advantage"])
    rows.update(payoff_macros(audit, prefix))
    rows[f"{prefix}RuleAgreement"] = plain(100 * audit["rules"]["recomputed_equals_executed"], 1)
    rows[f"{prefix}Threshold"] = "/".join(sorted({f"{t:.1f}" for t in audit["rules"]["thresholds"]}))
    if audit.get("isolation"):
        checks = audit["isolation"]
        worst = max(v for k, v in checks.items() if k.endswith("_replay"))
        rows[f"{prefix}ReplayEpisodes"] = f"{checks['episodes']:,}".replace(",", "{,}")
        rows[f"{prefix}ReplayDifference"] = "0" if worst == 0 else f"{worst:.1e}"
    for panel, entry in (audit.get("cross_estimator") or {}).get("panels", {}).items():
        tag, cap = PANELS[panel], entry["constant_cap"]
        other = audit["cross_estimator"]["tradeoff"][panel]["methods"]
        rows[f"{prefix}{tag}CapRatio"] = cap.removeprefix("fixed_")
        rows[f"{prefix}{tag}CapUtility"] = plain(other[cap]["utility"])
        rows[f"{prefix}{tag}CapUnsafe"] = plain(100 * other[cap]["unsafe"], 2)
        contrast_macros(rows, f"{prefix}{tag}CrossUtility", entry["typed_minus_cap"]["utility"])
        contrast_macros(rows, f"{prefix}{tag}CrossUnsafe", entry["typed_minus_cap"]["unsafe"], 2, 100)
        contrast_macros(rows, f"{prefix}{tag}OtherVsCap", entry["other_typed_minus_cap"]["utility"])
        contrast_macros(
            rows, f"{prefix}{tag}OtherVsCapUnsafe", entry["other_typed_minus_cap"]["unsafe"], 2, 100
        )
    for panel, entry in (audit.get("paired") or {}).get("panels", {}).items():
        names = {"train_fixed": "TrainFixed", **{m: alias for m, (alias, _) in ALIASES.items() if m in entry}}
        for key, alias in names.items():
            contrast_macros(rows, f"{prefix}{PANELS[panel]}Paired{alias}", entry[key]["utility"])
            contrast_macros(rows, f"{prefix}{PANELS[panel]}Paired{alias}Unsafe", entry[key]["unsafe"], 2, 100)
    return rows


def table_family_utility(audit, titles=TITLES):
    base = audit["panels"]["all"]["train_fixed"]
    lines = [
        r"\begin{tabular}{llrrrlrrr}",
        r"\toprule",
        r" & & Train-sel. & Hindsight & Typed & $\Delta$ to train-selected & Exact & & \\",
        r"Family & Split & fixed & fixed (ratio) & (RLCD) & [95\% over seeds] & gradient & Regression & Oracle \\",
        r"\midrule",
    ]
    for family in audit["panels"]["all"]["families"]:
        entry = audit["families"][family]
        m, rival = entry["methods"], entry["hindsight_fixed"]
        typed = m["choice_rlcd_bayes"]
        cells = [
            plain(m[base]["utility"]),
            f"{plain(m[rival]['utility'])} ({rival.removeprefix('fixed_')})",
            plain(typed["utility"]),
            f"{signed(typed['utility_vs_train_fixed'])} {span(typed['utility_vs_train_fixed_seed_interval95'])}",
            plain(m["choice_analytic_bayes"]["utility"]),
            plain(m["regress_greedy"]["utility"]),
            plain(m["oracle"]["utility"]),
        ]
        lines.append(f"{family_name(family)} & {titles[entry['group']]} & " + " & ".join(cells) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_family_risk(audit, titles=TITLES):
    base = audit["panels"]["all"]["train_fixed"]
    lines = [
        r"\begin{tabular}{llrrrrrrrr}",
        r"\toprule",
        r" & & \multicolumn{4}{c}{Unsafe control intervals (\%)} & \multicolumn{4}{c}{Typed head (RLCD)} \\",
        r"Family & Split & Floor & Train-sel. & Typed & Regression & Decisions & Acc. \% & Conf. \% & ECE \\",
        r"\midrule",
    ]
    for family in audit["panels"]["all"]["families"]:
        entry = audit["families"][family]
        m = entry["methods"]
        typed = m["choice_rlcd_bayes"]
        cells = [plain(100 * entry["floor"], 2)]
        cells += [plain(100 * m[n]["unsafe"], 2) for n in (base, "choice_rlcd_bayes", "regress_greedy")]
        cells += [
            f"{typed['rows']:,}".replace(",", "{,}"),
            plain(100 * typed["accuracy"], 1),
            plain(100 * typed["confidence"], 1),
            plain(typed["ece"]),
        ]
        lines.append(f"{family_name(family)} & {titles[entry['group']]} & " + " & ".join(cells) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_family_contrasts(audit, panels=("id", "ood"), titles=TITLES):
    """Every learned method against both fixed-ratio references, families as the unit."""
    last = panels[-1]
    head = "".join(rf" & \multicolumn{{3}}{{c}}{{{titles[p]}: minus train-selected}}" for p in panels)
    head += rf" & \multicolumn{{2}}{{c}}{{{titles[last]}: minus hindsight-best}} \\"
    lines = [
        r"\begin{tabular}{l" + "rlc" * len(panels) + "rl}",
        r"\toprule",
        head,
        "Method"
        + r" & $\Delta$ & family 95\% $t$ & $>0$" * len(panels)
        + r" & $\Delta$ & family 95\% $t$ \\",
        r"\midrule",
    ]
    for method, (_, label) in ALIASES.items():
        cells = []
        for panel in panels:
            c = audit["panels"][panel]["methods"][method]["utility_vs_train_fixed"]
            cells += [
                signed(c["mean"]),
                span(c.get("family_t_interval95")),
                f"{c['positive_families']}/{c['families']}",
            ]
        c = audit["panels"][last]["methods"][method]["utility_vs_hindsight_fixed"]
        cells += [signed(c["mean"]), span(c.get("family_t_interval95"))]
        short = label.removeprefix("Typed choice, ")
        lines.append(f"{short[0].upper()}{short[1:]} & " + " & ".join(cells) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_clustered(audit, titles=TITLES):
    """The same contrasts under three uncertainty procedures, for the primary head and its controls."""
    lines = [
        r"\begin{tabular}{llrlllc}",
        r"\toprule",
        r" & & & Seeds and traces & \multicolumn{2}{c}{Families resampled} & Families \\",
        r"Contrast & Panel & $\Delta$ utility & (families fixed) & bootstrap & $t$ interval & $>0$ \\",
        r"\midrule",
    ]

    def row(label, panel, c):
        cells = [signed(c["mean"]), span(c["seed_interval95"]), span(c["family_interval95"])]
        cells += [span(c["family_t_interval95"]), f"{c['positive_families']}/{c['families']}"]
        lines.append(f"{label} & {titles[panel]} & " + " & ".join(cells) + r" \\")

    panels = [p for p in titles if p in audit["panels"] and len(audit["panels"][p]["families"]) > 1]
    for key, label in (
        ("utility_vs_train_fixed", "Typed (RLCD) minus train-selected fixed"),
        ("utility_vs_hindsight_fixed", "Typed (RLCD) minus hindsight-best fixed"),
    ):
        for panel in panels:
            row(label, panel, audit["panels"][panel]["methods"]["choice_rlcd_bayes"][key])
            label = ""
        lines.append(r"\midrule")
    for key, (_, label) in list(PAIR_NAMES.items())[:2]:
        for panel in panels:
            row(label, panel, audit["panels"][panel]["pairs"][key]["utility"])
            label = ""
        lines.append(r"\midrule")
    return "\n".join([*lines[:-1], r"\bottomrule", r"\end{tabular}", ""])


def table_rules(audit, panels=("id", "ood"), titles=TITLES):
    head = "".join(rf" & \multicolumn{{2}}{{c}}{{{titles[p]}}}" for p in panels)
    lines = [
        r"\begin{tabular}{lrrr" + "rr" * len(panels) + "}",
        r"\toprule",
        rf" & \multicolumn{{3}}{{c}}{{{titles[panels[0]]}: share of decisions (\%)}}" + head + r" \\",
        "Rule applied to the same reported probabilities & below base & above base & agrees with label"
        + r" & one decision & closed loop" * len(panels)
        + r" \\",
        r"\midrule",
    ]
    for rule, (_, label, method) in RULE_NAMES.items():
        first = audit["rules"]["panels"][panels[0]]["rules"][rule]
        cells = [plain(100 * first[k], 1) for k in ("below_base", "above_base", "matches_label")]
        for panel in panels:
            cells.append(signed(audit["rules"]["panels"][panel]["rules"][rule]["advantage"]))
            cells.append(signed(audit["panels"][panel]["methods"][method]["utility_vs_train_fixed"]["mean"]))
        lines.append(f"{label} & " + " & ".join(cells) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_payoff(audit):
    ratios = [f"{r:.2f}" for r in audit["rules"]["ratios"]]
    lines = [
        r"\begin{tabular}{l" + "r" * len(ratios) + "}",
        r"\toprule",
        rf" & \multicolumn{{{len(ratios)}}}{{c}}{{Option that turned out best in hindsight}} \\",
        "Option run & " + " & ".join(ratios) + r" \\",
        r"\midrule",
    ]
    for ratio, row in zip(ratios, audit["rules"]["payoff_mean"]):
        lines.append(f"{ratio} & " + " & ".join(signed(v) for v in row) + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def table_tradeoff(audit, titles=TITLES):
    """Utility beside the share of unsafe control intervals, for both estimators and every method."""
    panels = [p for p in titles if p in audit["tradeoff"]]
    lines = [
        r"\begin{tabular}{ll" + "rr" * len(panels) + "}",
        r"\toprule",
        " & " + "".join(rf" & \multicolumn{{2}}{{c}}{{{titles[p]}}}" for p in panels) + r" \\",
        "Estimator & Method" + r" & Utility & Unsafe \%" * len(panels) + r" \\",
        r"\midrule",
    ]
    blocks = [("Acked-rate-bounded", audit["tradeoff"])]
    if audit.get("cross_estimator"):
        blocks.insert(0, ("Unbounded (legacy)", audit["cross_estimator"]["tradeoff"]))
    for title, trade in blocks:
        names = sorted(n for n in trade[panels[0]]["methods"] if n.startswith("fixed_"))
        names += [
            n
            for n in ALIASES
            if n in ("choice_rlcd_bayes", "choice_analytic_bayes", "regress_greedy", "oracle")
        ]
        for name in names:
            label = ALIASES[name][1] if name in ALIASES else ratio_name(name)
            cells = []
            for panel in panels:
                entry = trade[panel]["methods"][name]
                cells += [plain(entry["utility"]), plain(100 * entry["unsafe"], 2)]
            lines.append(f"{title} & {label} & " + " & ".join(cells) + r" \\")
            title = ""
        lines.append(r"\midrule")
    floor = " & ".join(f"& {plain(100 * audit['tradeoff'][p]['floor'], 2)}" for p in panels)
    lines.append(f"Either & Floor: unsafe whatever is sent & {floor}" + r" \\")
    return "\n".join([*lines, r"\bottomrule", r"\end{tabular}", ""])


def figure_tradeoff(audit, path, titles=TITLES):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, accent, warm = "#1f2933", "#9aa5b1", "#1f6fb2", "#c2571a"
    plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
    panels = [p for p in titles if p in audit["tradeoff"] and p != "all"] or ["all"]
    fig, axes = plt.subplots(1, len(panels), figsize=(3.6 * len(panels), 2.9), squeeze=False)
    blocks = [("bounded estimator", audit["tradeoff"], accent)]
    if audit.get("cross_estimator"):
        blocks.append(("unbounded estimator", audit["cross_estimator"]["tradeoff"], warm))
    for axis, panel in zip(axes[0], panels):
        axis.axvline(100 * audit["tradeoff"][panel]["floor"], color=muted, linewidth=0.8, linestyle=":")
        for title, trade, colour in blocks:
            m = trade[panel]["methods"]
            fixed = sorted(n for n in m if n.startswith("fixed_") and n != "fixed_0.85")
            axis.plot(
                [100 * m[n]["unsafe"] for n in fixed],
                [m[n]["utility"] for n in fixed],
                color=colour,
                linewidth=0.9,
                marker="o",
                markersize=3,
                label=f"Fixed ratios, {title}",
            )
            for n in (fixed[0], fixed[-1]):
                axis.annotate(
                    n.removeprefix("fixed_"),
                    (100 * m[n]["unsafe"], m[n]["utility"]),
                    textcoords="offset points",
                    xytext=(3, -8),
                    fontsize=6,
                    color=colour,
                )
            for name, marker, label in (
                ("choice_rlcd_bayes", "*", "Typed head"),
                ("regress_greedy", "s", "Regression"),
                ("oracle", "D", "Hindsight oracle"),
            ):
                axis.scatter(
                    100 * m[name]["unsafe"],
                    m[name]["utility"],
                    marker=marker,
                    s=70 if marker == "*" else 22,
                    facecolor="none" if name == "oracle" else colour,
                    edgecolor=colour,
                    linewidth=0.9,
                    zorder=3,
                    label=f"{label}, {title}",
                )
        axis.set_xlabel("Unsafe control intervals (%)")
        axis.set_ylabel("Mean utility")
        axis.set_title(f"{titles[panel]} families (dotted: policy-independent floor)", loc="left", color=ink)
    axes[0][-1].legend(frameon=False, fontsize=6, loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def outputs_manifest(runs):
    """Size and sha256 of every file in the run directories, whether or not it is in version control.

    Models, training data, per-episode outcomes and decision records are too large to track.
    Listing them lets a regenerated run be compared with the one the paper's numbers came from.
    """
    manifest = {}
    for run in map(Path, runs):
        for path in sorted(p for p in run.iterdir() if p.is_file()):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest[f"{run.name}/{path.name}"] = dict(bytes=path.stat().st_size, sha256=digest)
    return manifest


def load_audit(run, split):
    path = Path(run) / f"audit_{split}.json"
    return (json.loads(path.read_text()), path) if path.exists() else (None, path)


def export(run, out, diagnosis=None, ablation=None, robustness=None, broadened=None):
    run, out = Path(run), Path(out)
    report = json.loads((run / "report.json").read_text())
    if "test" not in report["panels"]:
        raise ValueError("paper evidence needs the frozen test panel")
    diagnosed = json.loads((Path(diagnosis) / "diagnosis.json").read_text()) if diagnosis else None
    ablated = json.loads((Path(ablation) / "report.json").read_text()) if ablation else None
    robust = json.loads((Path(robustness) / "report.json").read_text()) if robustness else None
    out.mkdir(parents=True, exist_ok=True)
    test = report["panels"]["test"]
    lines = ["% Generated by `jevbwe-typed export`; synthetic evidence only. Do not edit."]
    evidence = macros(report, diagnosed, ablated, robust)
    sources = [run / "report.json", run / "config.json"]
    audited, audit_path = load_audit(run, "test")
    if audited:
        evidence.update(audit_macros(audited, "TypedAudit"))
        sources.append(audit_path)
        (out / "table_family_utility.tex").write_text(table_family_utility(audited))
        (out / "table_family_risk.tex").write_text(table_family_risk(audited))
        (out / "table_family_contrasts.tex").write_text(table_family_contrasts(audited))
        (out / "table_clustered.tex").write_text(table_clustered(audited))
        (out / "table_rules.tex").write_text(table_rules(audited))
        (out / "table_payoff.tex").write_text(table_payoff(audited))
        (out / "table_tradeoff.tex").write_text(table_tradeoff(audited))
        figure_tradeoff(audited, out / "figure_tradeoff.pdf")
    if broadened:
        sources += broadened_evidence(Path(broadened), out, evidence)
    lines += [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in evidence.items()]
    (out / "evidence.tex").write_text("\n".join(lines) + "\n")
    (out / "table_methods.tex").write_text(table_methods(test))
    (out / "table_contrasts.tex").write_text(table_contrasts(test))
    (out / "table_calibration.tex").write_text(table_calibration(test))
    (out / "table_scenarios.tex").write_text(table_scenarios(test))
    if diagnosed:
        (out / "table_diagnosis.tex").write_text(table_diagnosis(diagnosed))
    if robust:
        (out / "table_robustness.tex").write_text(table_robustness(test, robust["panels"]["test"]))
    figure(test, out / "figure.pdf")
    if diagnosis:
        sources.append(Path(diagnosis) / "diagnosis.json")
    for extra in (ablation, robustness):
        if extra:
            sources.append(Path(extra) / "report.json")
    provenance = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1, sort_keys=True) + "\n")
    outputs = outputs_manifest(p for p in (run, diagnosis, ablation, robustness, broadened) if p)
    (out / "outputs_manifest.json").write_text(json.dumps(outputs, indent=1, sort_keys=True) + "\n")
    return dict(out=str(out), macros=len(lines) - 1, sources=provenance, outputs=len(outputs))


def broadened_evidence(run, out, evidence):
    """Evidence of the run trained on the broadened families: untouched test and development panels."""
    report = json.loads((run / "report.json").read_text())
    config = json.loads((run / "config.json").read_text())
    sources = [run / "report.json", run / "config.json"]
    evidence["TypedBroadTrainFamilies"] = len(config["train_scenarios"])
    evidence["TypedBroadBaseRatio"] = f"{report['base_tuning']['selected']:.2f}"
    evidence["TypedBroadTrainEpisodes"] = f"{config['train_episodes'] * config['rounds']:,}".replace(
        ",", "{,}"
    )
    if "validation" in report["panels"]:
        evidence.update(validation_macros(report))
    titles = {"test": {"ood": "Test"}}  # every test family is unseen, so "all" would repeat it
    titles["development"] = {"id": "Legacy training", "ood": "Development", "all": "All"}
    for split, prefix in (("test", "TypedBroadTest"), ("development", "TypedBroadDev")):
        audited, path = load_audit(run, split)
        if not audited:
            continue
        sources.append(path)
        evidence.update(audit_macros(audited, prefix))
        names = titles[split]
        panels = ("ood",) if split == "test" else ("id", "ood")
        (out / f"broad_{split}_family_utility.tex").write_text(table_family_utility(audited, names))
        (out / f"broad_{split}_family_risk.tex").write_text(table_family_risk(audited, names))
        (out / f"broad_{split}_family_contrasts.tex").write_text(
            table_family_contrasts(audited, panels, names)
        )
        (out / f"broad_{split}_clustered.tex").write_text(table_clustered(audited, names))
        (out / f"broad_{split}_rules.tex").write_text(table_rules(audited, panels, names))
        figure_tradeoff(audited, out / f"broad_{split}_tradeoff.pdf", names)
    return sources


def validation_macros(report):
    """In-distribution reference of the broadened run: its validation panel on training families."""
    data = report["panels"]["validation"]["id"]
    rows = {"TypedBroadValFamilies": len(data["scenarios"])}
    rows["TypedBroadValBaseUtility"] = plain(data["methods"][data["references"]["base"]]["utility"])
    for method, (alias, _) in ALIASES.items():
        entry = data["methods"][method]
        rows[f"TypedBroadVal{alias}Utility"] = plain(entry["utility"])
        rows[f"TypedBroadVal{alias}Unsafe"] = plain(100 * entry["unsafe"], 2)
        c = data["contrasts"][method]["base"]
        rows[f"TypedBroadVal{alias}VsBase"] = signed(c["utility"])
        rows[f"TypedBroadVal{alias}VsBaseInterval"] = interval(c)
        if "reliability" in entry:
            rows[f"TypedBroadVal{alias}Ece"] = plain(entry["reliability"]["ece"])
    return rows
