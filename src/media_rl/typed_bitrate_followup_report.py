"""Paper evidence for the typed-control follow-up: baseline audit, population replication, factual supervision.

Every number is read from the result summaries; nothing is typed in by hand.
"""

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .typed_bitrate_audit import PRIMARY
from .typed_bitrate_factual import NEVER
from .typed_bitrate_population import PANELS
from .typed_bitrate_report import contrast_macros, plain, signed, span

ORDINALS = ("One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight")
NUMBERS = ("none", "one", "two", "three", "four")
PANEL_KEYS = ("PanelA", "PanelB", "PanelC", "PanelD")


def count(value):
    return f"{value:,}".replace(",", "{,}")


def rule_name(spec):
    """A rule's parameters in words; the grid values are whole numbers of milliseconds."""
    if spec["kind"] == "delay":
        return (
            f"delay hysteresis between {spec['high']:.2f} and {spec['low']:.2f}, "
            f"reducing at {spec['on_ms']:g}\\,ms of excess round-trip delay and restoring at {spec['off_ms']:g}\\,ms"
        )
    detail = ", ".join(f"{k.replace('_', ' ')} {v:g}" for k, v in spec.items() if k != "kind")
    return f"{spec['kind']} ({detail})"


def family_macros(rows, name, pair, digits=3, scale=1):
    """Macros of one audited contrast: the utility entry of a pair, or a plain contrast."""
    contrast_macros(rows, name, pair, digits, scale)
    if "leave_one_family_out" in pair:
        rows[f"{name}LeaveOut"] = span(pair["leave_one_family_out"], digits, scale)


def rule_macros(report):
    """The baseline audit of the frozen broadened run."""
    tuning, rows = report["tuning"], {}
    sweep = {round(r["spec"]["ratio"], 2): r for r in report["extended"]["sweep"]}
    best = tuning["selected"]["rule_best"]
    rows.update(
        TypedRuleCandidates=str(tuning["candidates"]),
        TypedRuleTuneTraces=str(tuning["traces"]),
        TypedRuleTuneBase=plain(tuning["base"]["utility"]),
        TypedRuleTuneBest=plain(best["utility"]),
        TypedRuleTuneGain=signed(best["utility"] - tuning["base"]["utility"]),
        TypedRuleBestName=rule_name(best["spec"]),
        TypedRuleTuneAbove=plain(sweep[1.1]["utility"]),
        TypedRuleTuneTop=plain(sweep[1.5]["utility"]),
        TypedRuleCeilingEffect=plain(report["extended"]["ceiling_effect"], 1),
    )
    for prefix, split, panel in (
        ("TypedRuleVal", "validation", "all"),
        ("TypedRuleDev", "development", "ood"),
        ("TypedRuleTest", "test", "all"),
    ):
        if split not in report["panels"]:
            continue
        entry = report["panels"][split]["panels"][panel]
        for label, pair in (("RuleVsFixed", "rule_best_vs_train_fixed"), ("HeadVsRule", "head_vs_rule_best")):
            family_macros(rows, prefix + label, entry["contrasts"][pair]["utility"])
        rows[prefix + "BestWide"] = max(entry["wide_fixed"], key=entry["wide_fixed"].get)
    return rows


def panel_macros(report, audit, rules, prefix="TypedRep"):
    """A registered transfer: frozen models on a population panel they never trained on."""
    rows, panel = {}, audit["panels"]["all"]
    head, table = panel["methods"][PRIMARY], report["panels"]["test"]["all"]["methods"]
    base, hindsight = panel["train_fixed"], panel["hindsight_fixed"]
    families = len(panel["families"])
    gain = head["utility_vs_train_fixed"]
    by_family = np.asarray(gain["by_family"])
    ece = [audit["families"][f]["methods"][PRIMARY]["ece"] for f in panel["families"]]
    calibration = audit["calibration"][PRIMARY]["all"]
    registered = report["transfer"]["registration"]
    rows.update(
        Families=str(families),
        TraceSeeds=str(len(registered["test_seeds"])),
        Traces=count(families * len(registered["test_seeds"])),
        SealedFamilies=str(PANELS["s"]),
        PoolFamilies=str(PANELS["d"]),
        BaseRatio=f"{float(base.removeprefix('fixed_')):.2f}",
        HindsightRatio=f"{float(hindsight.removeprefix('fixed_')):.2f}",
        BaseUtility=plain(table[base]["utility"]),
        HindsightUtility=plain(table[hindsight]["utility"]),
        HeadUtility=plain(table[PRIMARY]["utility"]),
        OracleUtility=plain(table["oracle"]["utility"]),
        BaseUnsafe=plain(100 * table[base]["unsafe"], 2),
        HeadUnsafe=plain(100 * table[PRIMARY]["unsafe"], 2),
        Override=plain(100 * table[PRIMARY]["override_share"], 1),
        Ece=plain(calibration["ece"]),
        EceFamily=span(calibration["family_interval95"]).replace("$+$", ""),
        Accuracy=plain(calibration["accuracy"]),
        Confidence=plain(calibration["confidence"]),
        EceBest=plain(min(ece)),
        EceWorst=plain(max(ece)),
        EceMedian=plain(float(np.median(ece))),
        EceAbove=str(int(np.sum(np.asarray(ece) > 0.05))),
        FamilySd=plain(float(by_family.std(ddof=1))),
        NearZero=str(int(np.sum(np.abs(by_family) < 0.005))),
        Largest=signed(float(by_family.max())),
        Smallest=signed(float(by_family.min())),
        Floor=plain(100 * float(np.mean([audit["families"][f]["floor"] for f in panel["families"]])), 1),
        IsolationEpisodes=count(audit["isolation"]["episodes"]),
        IsolationDifference=plain(audit["isolation"]["unlabelled_replay"], 1),
        RuleName=rule_name(registered["rule_best"]),
    )
    family_macros(rows, "Gain", gain)
    family_macros(rows, "GainVsHindsight", head["utility_vs_hindsight_fixed"])
    family_macros(rows, "Unsafe", head["unsafe_vs_train_fixed"], 2, 100)
    family_macros(rows, "OracleGain", panel["methods"]["oracle"]["utility_vs_train_fixed"])
    oracle = panel["methods"]["oracle"]["utility_vs_train_fixed"]["mean"]
    rows["OracleShare"] = plain(100 * gain["mean"] / oracle, 0)
    # A constant ratio chosen per family in hindsight: what knowing the family alone would give.
    fixed = [m["per_scenario"] for name, m in table.items() if name.startswith("fixed_")]
    constant = float(
        np.mean([max(f[s] for f in fixed) - table[base]["per_scenario"][s] for s in panel["families"]])
    )
    rows.update(
        FamilyConstantGain=signed(constant),
        FamilyConstantShare=plain(100 * constant / oracle, 0),
        HeadVsFamilyConstant=signed(gain["mean"] - constant),
        RegressVsFamilyConstant=signed(
            panel["methods"]["regress_greedy"]["utility_vs_train_fixed"]["mean"] - constant
        ),
    )
    family_macros(rows, "RegressGain", panel["methods"]["regress_greedy"]["utility_vs_train_fixed"])
    for label, pair in (
        ("RlcdVsAnalytic", "rlcd_vs_exact_gradient"),
        ("RlcdVsRegress", "rlcd_vs_regression"),
        ("BayesVsMap", "payoff_weighted_vs_map"),
    ):
        family_macros(rows, label, panel["pairs"][pair]["utility"])
    panels = rules["panels"]["test"]["panels"]
    family_macros(rows, "GainVsRule", panels["all"]["contrasts"]["head_vs_rule_best"]["utility"])
    family_macros(rows, "RuleVsFixed", panels["all"]["contrasts"]["rule_best_vs_train_fixed"]["utility"])
    if "sensitive" in panels:
        sensitive = panels["sensitive"]
        rows["SensitiveFamilies"] = str(len(sensitive["families"]))
        rows["SensitiveMargin"] = plain(registered["sensitive_margin"], 2)
        family_macros(rows, "SensitiveGain", sensitive["contrasts"]["head_vs_train_fixed"]["utility"])
        family_macros(rows, "SensitiveGainVsRule", sensitive["contrasts"]["head_vs_rule_best"]["utility"])
    if audit.get("paired"):  # this run minus a reference run on identical traces
        paired = audit["paired"]["panels"]["all"]
        family_macros(rows, "VsReference", paired[PRIMARY]["utility"])
        family_macros(rows, "VsReferenceUnsafe", paired[PRIMARY]["unsafe"], 2, 100)
        family_macros(rows, "FixedVsReference", paired["train_fixed"]["utility"])
        rows["ReferenceIdentity"] = plain(audit["paired"]["fixed_ratio_identity"], 1)
    met = verdicts(audit, rules)
    rows.update({f"Met{k.title()}": "met" if v else "not met" for k, v in met.items()})
    rows.update(CriteriaMet=NUMBERS[sum(met.values())], Criteria=NUMBERS[len(met)])
    return {prefix + name: value for name, value in rows.items()}


def validation_macros(audit, prefix):
    """A run's own validation panel: the families it trained on, fresh traces."""
    rows, panel = {}, audit["panels"]["all"]
    head = panel["methods"][PRIMARY]
    calibration = audit["calibration"][PRIMARY]["all"]
    rows.update(Families=str(len(panel["families"])), Ece=plain(calibration["ece"]))
    family_macros(rows, "Gain", head["utility_vs_train_fixed"])
    family_macros(rows, "Unsafe", head["unsafe_vs_train_fixed"], 2, 100)
    family_macros(rows, "OracleGain", panel["methods"]["oracle"]["utility_vs_train_fixed"])
    return {prefix + name: value for name, value in rows.items()}


def identified(entry, name="factual"):
    """The reading fixed in the design: the family-level t interval of the gain excludes zero."""
    return entry["contrasts"][f"{name}_vs_fixed"]["utility"]["family_t_interval95"][0] > 0


def factual_macros(report, prefix="TypedFact"):
    """Learning curves of the factual pipeline and its rollout-labelled control."""
    rows = _factual_macros(report)
    for key, (name, panel) in zip(PANEL_KEYS, report.get("unseen", {}).items()):
        rows[f"TypedFact{key}Families"] = str(panel["families"])
        rows[f"TypedFact{key}TraceSeeds"] = str(panel["trace_seeds"])
        family_macros(rows, f"TypedFact{key}RefRegress", panel["reference"]["regress"]["utility"])
        family_macros(rows, f"TypedFact{key}RefHead", panel["reference"]["head"]["utility"])
        for ordinal, entry in zip(ORDINALS, report["budgets"]):
            there, stem = entry["unseen"][name], f"TypedFact{ordinal}{key}"
            family_macros(rows, stem + "Gain", there["factual_vs_fixed"]["utility"])
            family_macros(rows, stem + "Unsafe", there["factual_vs_fixed"]["unsafe"], 2, 100)
            if "rollout_vs_fixed" in there:
                family_macros(rows, stem + "ControlGain", there["rollout_vs_fixed"]["utility"])
                family_macros(rows, stem + "Price", there["factual_vs_rollout"]["utility"])
    return {prefix + name.removeprefix("TypedFact"): value for name, value in rows.items()}


def table_factual_unseen(report):
    """Factual pipeline and control against the fixed ratio: in distribution and on each unseen panel."""
    panels = list(report.get("unseen", {}))
    heads = " & ".join(f"\\multicolumn{{2}}{{c}}{{Unseen panel {chr(65 + i)}}}" for i in range(len(panels)))
    subs = " & ".join("factual & control" for _ in panels)
    lines = [
        "\\begin{tabular}{rr" + "ll" * (1 + len(panels)) + "}",
        "\\toprule",
        f"Blocks & Hours & \\multicolumn{{2}}{{c}}{{Training families}} & {heads} \\\\",
        f" & & factual & control & {subs} \\\\",
        "\\midrule",
    ]
    for entry in report["budgets"]:
        c = entry["contrasts"]
        cells = [count(entry["blocks"]), count(int(round(entry["link_hours"])))]
        cells.append(with_interval(c["factual_vs_fixed"]["utility"]))
        cells.append(
            with_interval(c["rollout_vs_fixed"]["utility"]) if "rollout_vs_fixed" in c else "not run"
        )
        for name in panels:
            there = entry["unseen"][name]
            cells.append(with_interval(there["factual_vs_fixed"]["utility"]))
            cells.append(
                with_interval(there["rollout_vs_fixed"]["utility"])
                if "rollout_vs_fixed" in there
                else "not run"
            )
        lines.append(" & ".join(cells) + " \\\\")
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


def _factual_macros(report):
    rows, budgets = {}, report["budgets"]
    rows.update(
        TypedFactSeeds=str(len(report["settings"]["seeds"])),
        TypedFactBudgets=str(len(budgets)),
        TypedFactStates=count(report["truth"]["states"]),
        TypedFactOracleAdvantage=signed(report["truth"]["oracle_advantage"]),
        TypedFactBlocksPerEpisode=plain(
            float(np.mean([c["blocks_per_episode"] for c in report["collection"]])), 1
        ),
        TypedFactLabelDifference=plain(max(c["factual_matches_rollout"] for c in report["collection"]), 1),
        TypedFactControlBlocks=count(report["settings"]["control_blocks"]),
    )
    for name, label in (("v3_regress", "TypedFactRefRegress"), ("v3_head", "TypedFactRefHead")):
        family_macros(rows, label, report["reference"][name]["utility"])
    for ordinal, entry in zip(ORDINALS, budgets):
        prefix = f"TypedFact{ordinal}"
        rows[prefix + "Blocks"] = count(entry["blocks"])
        rows[prefix + "Hours"] = count(int(round(entry["link_hours"])))
        family_macros(rows, prefix + "Gain", entry["contrasts"]["factual_vs_fixed"]["utility"])
        family_macros(rows, prefix + "Unsafe", entry["contrasts"]["factual_vs_fixed"]["unsafe"], 2, 100)
        rows[prefix + "Offline"] = signed(entry["pipelines"]["factual"]["offline_advantage"])
        rows[prefix + "Correlation"] = plain(entry["pipelines"]["factual"]["correlation"], 2)
        if "rollout" in entry["pipelines"]:
            family_macros(rows, prefix + "ControlGain", entry["contrasts"]["rollout_vs_fixed"]["utility"])
            family_macros(rows, prefix + "Price", entry["contrasts"]["factual_vs_rollout"]["utility"])
            rows[prefix + "ControlOffline"] = signed(entry["pipelines"]["rollout"]["offline_advantage"])
            rows[prefix + "ControlCorrelation"] = plain(entry["pipelines"]["rollout"]["correlation"], 2)
    first = next((e for e in budgets if identified(e)), None)
    rows["TypedFactIdentifiedBlocks"] = count(first["blocks"]) if first else "none"
    rows["TypedFactIdentifiedHours"] = count(int(round(first["link_hours"]))) if first else "none"
    rows["TypedFactIdentifiedBudgets"] = str(sum(identified(e) for e in budgets))
    last = budgets[-1]
    rows["TypedFactLastBlocks"] = count(last["blocks"])
    rows["TypedFactLastHours"] = count(int(round(last["link_hours"])))
    family_macros(rows, "TypedFactLastGain", last["contrasts"]["factual_vs_fixed"]["utility"])
    controlled = [e for e in budgets if "rollout" in e["pipelines"]]
    if controlled:
        top = controlled[-1]
        rows["TypedFactControlHours"] = count(int(round(top["link_hours"])))
        family_macros(rows, "TypedFactControlTopGain", top["contrasts"]["rollout_vs_fixed"]["utility"])
        family_macros(rows, "TypedFactControlTopFactual", top["contrasts"]["factual_vs_fixed"]["utility"])
        family_macros(rows, "TypedFactControlTopPrice", top["contrasts"]["factual_vs_rollout"]["utility"])
    return rows


def with_interval(c):
    return f"{signed(c['mean'])} {span(c.get('family_t_interval95'))}"


def table_rules(report, replication=None):
    """Tuned rule against the fixed ratio and the head, per panel, with family-level t intervals."""
    lines = [
        "\\begin{tabular}{lrlll}",
        "\\toprule",
        "Panel & Families & Tuned rule $-$ fixed & Head $-$ tuned rule & Oracle $-$ tuned rule \\\\",
        "\\midrule",
    ]
    panels = [
        ("Validation (training families)", report, "validation", "all"),
        ("Development, never trained on", report, "development", "ood"),
        ("Former test families", report, "test", "all"),
    ]
    if replication:
        panels.append(("Population panel (registered)", replication, "test", "all"))
    for title, source, split, panel in panels:
        if split not in source["panels"]:
            continue
        entry = source["panels"][split]["panels"][panel]
        c = entry["contrasts"]
        cells = (
            c[k]["utility"] for k in ("rule_best_vs_train_fixed", "head_vs_rule_best", "oracle_vs_rule_best")
        )
        lines.append(
            f"{title} & {len(entry['families'])} & " + " & ".join(with_interval(x) for x in cells) + " \\\\"
        )
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


def verdicts(audit, rules):
    """Whether each registered criterion holds, from the audited numbers and the registered thresholds."""

    def clear(c):
        return all(low > 0 or high < 0 for low, high in (c["family_interval95"], c["family_t_interval95"]))

    head = audit["panels"]["all"]["methods"][PRIMARY]
    rule = rules["panels"]["test"]["panels"]["all"]["contrasts"]["head_vs_rule_best"]["utility"]
    return dict(
        gain=clear(head["utility_vs_train_fixed"]),
        rule=clear(rule),
        calibration=audit["calibration"][PRIMARY]["all"]["ece"] <= 0.05,
        constraints=head["unsafe_vs_train_fixed"]["family_interval95"][1] <= 0.01,
    )


def table_replication(rows, prefix="TypedRep"):
    """The four registered criteria and the secondary contrasts, from the macros already computed."""

    def line(label, name, verdict=None, t=True):
        cells = [rows[prefix + name], rows[f"{prefix}{name}Family"], rows[f"{prefix}{name}T"] if t else "n/a"]
        return f"{label} & " + " & ".join(cells) + f" & {rows[prefix + verdict] if verdict else ''} \\\\"

    lines = [
        "\\begin{tabular}{lrllr}",
        "\\toprule",
        "Quantity & Estimate & Family bootstrap & Family $t$ & Criterion \\\\",
        "\\midrule",
        line("1. Head $-$ train-selected fixed ratio", "Gain", "MetGain"),
        line("2. Head $-$ tuned rule", "GainVsRule", "MetRule"),
        line("3. Pooled ECE (at most 0.05)", "Ece", "MetCalibration", t=False),
        line("4. Unsafe intervals, points (upper end at most $+$1.0)", "Unsafe", "MetConstraints"),
        "\\midrule",
        line("Head $-$ hindsight-best fixed ratio", "GainVsHindsight"),
        line("RLCD $-$ exact-gradient head", "RlcdVsAnalytic"),
        line("RLCD $-$ regression head", "RlcdVsRegress"),
        line("Tuned rule $-$ fixed ratio", "RuleVsFixed"),
        line("Hindsight oracle $-$ fixed ratio", "OracleGain"),
    ]
    if prefix + "SensitiveGain" in rows:
        label = f"Head $-$ fixed ratio, {rows[prefix + 'SensitiveFamilies']} action-sensitive families"
        lines.append(line(label, "SensitiveGain"))
    if prefix + "VsReference" in rows:
        lines.append(line("Head $-$ reference head on identical traces", "VsReference"))
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


def margins(seeds):
    return ", ".join("never" if s["margin"] == NEVER else f"{s['margin']:g}" for s in seeds)


def table_factual(report):
    lines = [
        "\\begin{tabular}{rrlllrrl}",
        "\\toprule",
        "Blocks & Hours & Factual $-$ fixed & Rollout control $-$ fixed & Factual $-$ control"
        " & \\multicolumn{2}{c}{Offline advantage} & Factual margins \\\\",
        " & & & & & factual & control & \\\\",
        "\\midrule",
    ]
    for entry in report["budgets"]:
        c, p = entry["contrasts"], entry["pipelines"]
        control = "rollout" in p
        lines.append(
            " & ".join(
                [
                    count(entry["blocks"]),
                    count(int(round(entry["link_hours"]))),
                    with_interval(c["factual_vs_fixed"]["utility"]),
                    with_interval(c["rollout_vs_fixed"]["utility"]) if control else "not run",
                    with_interval(c["factual_vs_rollout"]["utility"]) if control else "n/a",
                    signed(p["factual"]["offline_advantage"]),
                    signed(p["rollout"]["offline_advantage"]) if control else "n/a",
                    margins(p["factual"]["seeds"]),
                ]
            )
            + " \\\\"
        )
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


def figure_factual(report, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, accent, warm = "#1f2933", "#9aa5b1", "#1f6fb2", "#c2571a"
    plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
    fig, axis = plt.subplots(figsize=(4.6, 2.9))
    axis.axhline(0, color=muted, linewidth=0.8)
    reference = report["reference"]["v3_regress"]["utility"]["mean"]
    axis.axhline(reference, color=muted, linewidth=0.8, linestyle=":")
    budgets = report["budgets"]
    axis.annotate(
        "frozen regression head (rollouts, on-policy aggregation)",
        (budgets[0]["link_hours"], reference),
        textcoords="offset points",
        xytext=(0, 3),
        fontsize=6,
        color=ink,
    )
    for name, label, colour, marker in (
        ("rollout", "Rollout-labelled control", warm, "s"),
        ("factual", "Factual outcomes only", accent, "o"),
    ):
        rows = [e for e in budgets if name in e["pipelines"]]
        hours = [e["link_hours"] for e in rows]
        cells = [e["contrasts"][f"{name}_vs_fixed"]["utility"] for e in rows]
        mean = np.asarray([c["mean"] for c in cells])
        low, high = np.asarray([c["family_t_interval95"] for c in cells]).T
        axis.errorbar(
            hours,
            mean,
            yerr=[mean - low, high - mean],
            color=colour,
            marker=marker,
            markersize=3.5,
            linewidth=1.0,
            elinewidth=0.8,
            capsize=2,
            label=label,
        )
    axis.set_xscale("log")
    axis.set_xlabel("Randomised link time (hours, log scale)")
    axis.set_ylabel("Utility gain over the fixed ratio")
    axis.set_title("Validation traces; bars are family-level 95% t intervals", loc="left", color=ink)
    axis.legend(frameon=False, fontsize=6, loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def crossover_macros(report):
    """Per-link crossover identification: how many designs are usable and what they cost."""
    rows, pairs = {}, report["pairs"]
    cells = [(p, d) for p in pairs for d in p["designs"]]
    usable = [(p, d) for p, d in cells if d["usable"]]
    short = [d for _, d in cells if d["block_ms"] < max(x["block_ms"] for _, x in cells)]
    primary = pairs[0]
    rows.update(
        TypedCrossLinks=str(report["links"]),
        TypedCrossSessions=str(report["sessions"]),
        TypedCrossSessionSeconds=f"{report['session_seconds']:.0f}",
        TypedCrossBetweenSpread=plain(report["between_session_spread"]),
        TypedCrossDesigns=str(len(cells)),
        TypedCrossUsable=NUMBERS[len(usable)] if len(usable) < len(NUMBERS) else str(len(usable)),
        TypedCrossShortSlopeLow=signed(min(d["slope"] for d in short), 2),
        TypedCrossShortSlopeHigh=signed(max(d["slope"] for d in short), 2),
        TypedCrossShortCorrelationLow=signed(min(d["correlation"] for d in short), 2),
        TypedCrossShortCorrelationHigh=signed(max(d["correlation"] for d in short), 2),
        TypedCrossPrimaryA=f"{primary['a']:.2f}",
        TypedCrossPrimaryB=f"{primary['b']:.2f}",
        TypedCrossPrimaryEffect=signed(primary["true_effect_mean"]),
        TypedCrossPrimarySpread=plain(primary["true_effect_spread"]),
        TypedCrossPrimaryWhole=count(int(round(primary["designs"][0]["sessions_needed_whole_sessions"]))),
        TypedCrossPrimaryIdeal=count(int(round(primary["designs"][0]["sessions_needed_identical_traces"]))),
    )
    whole = [p["designs"][0]["sessions_needed_whole_sessions"] for p in pairs]
    rows["TypedCrossWholeLow"] = count(int(round(min(whole))))
    rows["TypedCrossWholeHigh"] = count(int(round(max(whole))))
    if usable:
        needs = [d["sessions_needed"] for _, d in usable]
        rows["TypedCrossUsableLow"] = count(int(round(min(needs))))
        rows["TypedCrossUsableHigh"] = count(int(round(max(needs))))
        rows["TypedCrossUsableBlock"] = f"{min(d['block_ms'] for _, d in usable) / 1000:g}"
    return rows


HEADROOM_SETS = ("Ref", "Cap", "Low")  # as studied, cut off at the estimate, cut off below it
HEADROOM_PANELS = {"r": ("Rep", "replication"), "s": ("Seal", "sealed")}


def headroom_share(change):
    return "n/a" if change["headroom_share"] is None else f"{100 * change['headroom_share']:.0f}"


def headroom_macros(report):
    """Hindsight headroom under truncated option sets; the first set is the reference."""
    if len(report["sets"]) != len(HEADROOM_SETS) or set(report["families"]) != set(HEADROOM_PANELS):
        raise ValueError("the headroom study must hold three option sets on the two population panels")
    rows = dict(TypedHeadFamilies=str(report["families"]["r"]))
    for key, entry in zip(HEADROOM_SETS, report["sets"]):
        name = "TypedHead" + key
        rows[name + "Top"], rows[name + "Base"] = f"{entry['top']:.2f}", f"{entry['base_ratio']:.2f}"
        for panel, (label, _) in HEADROOM_PANELS.items():
            scored, prefix = entry["panels"][panel], name + label
            rows[prefix + "Fixed"] = plain(scored["base_utility"])
            rows[prefix + "Oracle"] = plain(scored["oracle_utility"])
            rows[prefix + "TopShare"] = f"{100 * scored['oracle_option_share'][-1]:.0f}"
            family_macros(rows, prefix + "Room", scored["headroom"])
            if "against_widest" in entry:
                change = entry["against_widest"][panel]
                rows[prefix + "Share"] = headroom_share(change)
                rows[prefix + "Reading"] = change["reading"]
                family_macros(rows, prefix + "FixedChange", change["base"])
                family_macros(rows, prefix + "OracleChange", change["oracle"])
                family_macros(rows, prefix + "OverRef", change["oracle_minus_widest_base"])
    return rows


def table_headroom(report):
    lines = [
        "\\begin{tabular}{rrlrrlrl}",
        "\\toprule",
        "Top option & Fixed ratio & Panel & Fixed & Oracle & Headroom & Share (\\%) & Oracle $-$ reference fixed \\\\",
        "\\midrule",
    ]
    for entry in report["sets"]:
        label = f"{entry['top']:.2f} & {entry['base_ratio']:.2f}"
        for panel, (_, name) in HEADROOM_PANELS.items():
            scored, change = entry["panels"][panel], entry.get("against_widest", {}).get(panel)
            room = scored["headroom"]
            cells = [
                label,
                name,
                plain(scored["base_utility"]),
                plain(scored["oracle_utility"]),
                f"{signed(room['mean'])} {span(room['family_t_interval95'])}",
                headroom_share(change) if change else "100",
            ]
            over = change["oracle_minus_widest_base"] if change else room
            cells.append(f"{signed(over['mean'])} {span(over['family_t_interval95'])}")
            lines.append(" & ".join(cells) + " \\\\")
            label = " & "
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


FORECAST_VARIANTS = dict(as_built="Built", n1_realised="Real")  # description of the actuator: macro key
FORECAST_CLASS = dict(helps="helps", hurts="hurts", no_clear_benefit="shows no clear benefit")
FORECAST_ARMS = ("Low", "Mid", "Top")
FORECAST_CONTRASTS = dict(
    Other="other_holds",
    Gap="flagged_minus_other",
    Next="next_hold",
    Qoe="simulator_qoe",
    Ontime="ontime_fraction",
)


def percent(value):
    return f"{100 * value:.0f}"


def spread(summary):
    if summary["interval"] is None:  # fewer than two replicates could be scored
        return "n/a"
    low, high = summary["interval"]
    return f"[{signed(low)}, {signed(high)}]"


def forecast_macros(report):
    """Simulator forecast of Native Phase B1, beside the N1 figures it is compared with."""
    if set(report["variants"]) != set(FORECAST_VARIANTS):
        raise ValueError("the forecast must hold both descriptions of the actuator")
    reference = report["settings"]["n1_reference"]
    rows = dict(
        TypedCastReplicates=str(report["settings"]["replicates"]),
        TypedCastNOneFlag=percent(reference["flagged_share"]),
    )

    def by_arm(prefix, flag_after, encoder, growth):
        for arm, label in enumerate(FORECAST_ARMS):
            rows[prefix + "FlagAfter" + label] = percent(flag_after[arm])
            rows[prefix + "Enc" + label] = f"{encoder[arm]:.3f}"
            rows[prefix + "Grow" + label] = percent(math.expm1(growth[arm]))

    by_arm(
        "TypedCastNOne",
        reference["flagged_share_by_previous_arm"],
        reference["encoder_over_bwe"]["all"],
        reference["estimate_log_growth"]["underutilized"],
    )
    for key, name in FORECAST_VARIANTS.items():
        made, prefix = report["variants"][key], "TypedCast" + name
        exact, sampled = made["exact"], made["sampled"]["contrasts"]
        rows[prefix + "Sessions"] = f"{exact['sessions']:,}".replace(",", "{,}")
        rows[prefix + "Class"] = FORECAST_CLASS[made["forecast"]]
        rows[prefix + "Stable"] = "agrees" if made["exact_panel_agrees"] else "disagrees"
        rows[prefix + "Exact"] = signed(exact["contrasts"]["primary"])
        rows[prefix + "Mean"] = signed(sampled["primary"]["mean"])
        rows[prefix + "Interval"] = spread(sampled["primary"])
        relative = made["relative_benefit"]
        rows[prefix + "Relative"] = "n/a" if relative is None else percent(abs(relative))
        for label, contrast in FORECAST_CONTRASTS.items():
            rows[prefix + label] = signed(sampled[contrast]["mean"])
            rows[prefix + label + "T"] = spread(sampled[contrast])
        rows[prefix + "Flag"] = percent(exact["flag"]["all"])
        by_arm(
            prefix,
            exact["flag"]["by_previous_arm"],
            exact["encoder_over_bwe"]["all"],
            exact["estimate_log_growth"]["underutilized"],
        )
    return rows


def table_forecast(report):
    reference = report["settings"]["n1_reference"]
    made = [report["variants"][key] for key in FORECAST_VARIANTS]

    def row(label, pick, cell, native):
        cells = [" / ".join(cell(v) for v in pick(m["exact"])) for m in made]
        return " & ".join([label, *cells, " / ".join(cell(v) for v in native)]) + " \\\\"

    def growth(value):
        return percent(math.expm1(value))

    lines = [
        "\\begin{tabular}{lrrr}",
        "\\toprule",
        "Quantity & As built & At N1's levels & Native (N1) \\\\",
        "\\midrule",
        row(
            "Encoder over estimate, by arm",
            lambda e: e["encoder_over_bwe"]["all"],
            lambda v: f"{v:.3f}",
            reference["encoder_over_bwe"]["all"],
        ),
        row(
            "Estimate growth per hold with room, by arm (\\%)",
            lambda e: e["estimate_log_growth"]["underutilized"],
            growth,
            reference["estimate_log_growth"]["underutilized"],
        ),
        row("Holds flagged (\\%)", lambda e: [e["flag"]["all"]], percent, [reference["flagged_share"]]),
        row(
            "Flagged after each arm (\\%)",
            lambda e: e["flag"]["by_previous_arm"],
            percent,
            reference["flagged_share_by_previous_arm"],
        ),
        "\\midrule",
    ]
    contrasts = (
        ("Benefit of backing off, flagged holds", "primary", "registered, not run"),
        ("Same, unflagged holds", "other_holds", "---"),
        ("Flagged minus unflagged", "flagged_minus_other", "---"),
        ("Same contrast on the next hold", "next_hold", "---"),
    )
    for label, name, native in contrasts:
        cells = [
            f"{signed(m['sampled']['contrasts'][name]['mean'])} {spread(m['sampled']['contrasts'][name])}"
            for m in made
        ]
        lines.append(" & ".join([label, *cells, native]) + " \\\\")
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


def table_crossover(report, washout_ms=1000):
    lines = [
        "\\begin{tabular}{lrrrrrrl}",
        "\\toprule",
        "Pair & True effect & Block (s) & Slope & Intercept & Correlation & Sessions & Usable \\\\",
        "\\midrule",
    ]
    for pair in report["pairs"]:
        first = pair["designs"][0]
        label = f"{pair['a']:.2f} to {pair['b']:.2f}"
        for design in (d for d in pair["designs"] if d["washout_ms"] == washout_ms):
            cells = [
                label,
                signed(pair["true_effect_mean"]) if label else "",
                f"{design['block_ms'] / 1000:g}",
                signed(design["slope"], 2),
                signed(design["intercept"]),
                signed(design["correlation"], 2),
                count(int(round(design["sessions_needed"]))),
                "yes" if design["usable"] else "no",
            ]
            lines.append(" & ".join(cells) + " \\\\")
            label = ""
        whole, ideal = first["sessions_needed_whole_sessions"], first["sessions_needed_identical_traces"]
        note = f"whole sessions: {count(int(round(whole)))} per ratio; identical traces: {count(int(round(ideal)))}"
        lines.append(f" & & \\multicolumn{{6}}{{l}}{{{note}}} \\\\")
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


def load_panel(run, baselines):
    """Report, audit and rule audit of one registered transfer, with the checks the paper relies on."""
    files = [Path(run) / "report.json", Path(run) / "audit_test.json", Path(baselines) / "report.json"]
    report, audit, rules = (json.loads(p.read_text()) for p in files)
    if "transfer" not in report or not all(d.get("synthetic_only") for d in (report, audit, rules)):
        raise ValueError("a panel must be a registered synthetic transfer")
    if not audit.get("isolation"):
        raise ValueError("replay the panel before exporting its evidence")
    return files, report, audit, rules


def export(
    out,
    baselines,
    replication=None,
    replication_baselines=None,
    factual=None,
    panels=(),
    validations=(),
    crossover=None,
    factual_unseen=None,
    headroom=None,
    forecast=None,
):
    """Write macros, tables and the learning-curve figure from the follow-up summaries.

    ``panels`` adds further registered transfers as (macro prefix, run, rule audit) and
    ``validations`` a run's audited validation panel as (macro prefix, run).
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sources = [Path(baselines) / "report.json"]
    audited = json.loads(sources[0].read_text())
    if not audited.get("synthetic_only"):
        raise ValueError("the baseline audit must be marked synthetic")
    evidence, rules = rule_macros(audited), None
    if replication:
        if not replication_baselines:
            raise ValueError("the replication needs its baseline audit")
        files, report, audit, rules = load_panel(replication, replication_baselines)
        evidence.update(panel_macros(report, audit, rules))
        (out / "followup_replication.tex").write_text(table_replication(evidence))
        sources += files
    (out / "followup_rules.tex").write_text(table_rules(audited, rules))
    for prefix, run, rule_audit in panels:
        if not prefix.isalpha() or f"{prefix}Gain" in evidence:
            raise ValueError("panel prefixes must be distinct and consist of letters")
        files, report, audit, panel_rules = load_panel(run, rule_audit)
        evidence.update(panel_macros(report, audit, panel_rules, prefix))
        (out / f"followup_{prefix.lower()}.tex").write_text(table_replication(evidence, prefix))
        sources += files
    for prefix, run in validations:
        path = Path(run) / "audit_validation.json"
        if not prefix.isalpha() or f"{prefix}Gain" in evidence:
            raise ValueError("validation prefixes must be distinct and consist of letters")
        evidence.update(validation_macros(json.loads(path.read_text()), prefix))
        sources.append(path)
    if factual:
        path = Path(factual) / "report.json"
        curves = json.loads(path.read_text())
        if not curves.get("synthetic_only"):
            raise ValueError("the factual study must be marked synthetic")
        evidence.update(factual_macros(curves))
        (out / "followup_factual.tex").write_text(table_factual(curves))
        figure_factual(curves, out / "followup_factual.pdf")
        sources.append(path)
    if factual_unseen:
        path = Path(factual_unseen) / "report.json"
        wider = json.loads(path.read_text())
        if not wider.get("synthetic_only") or not wider.get("unseen"):
            raise ValueError("the unseen-family factual study must be synthetic and score unseen panels")
        evidence.update(factual_macros(wider, "TypedUnseen"))
        (out / "followup_factual_unseen.tex").write_text(table_factual_unseen(wider))
        sources.append(path)
    if crossover:
        path = Path(crossover) / "report.json"
        crossed = json.loads(path.read_text())
        if not crossed.get("synthetic_only"):
            raise ValueError("the crossover study must be marked synthetic")
        evidence.update(crossover_macros(crossed))
        (out / "followup_crossover.tex").write_text(table_crossover(crossed))
        sources.append(path)
    if headroom:
        path = Path(headroom) / "report.json"
        room = json.loads(path.read_text())
        if not room.get("synthetic_only") or room.get("models_trained") != 0:
            raise ValueError("the headroom study must be synthetic and model-free")
        evidence.update(headroom_macros(room))
        (out / "followup_headroom.tex").write_text(table_headroom(room))
        sources.append(path)
    if forecast:
        path = Path(forecast) / "report.json"
        cast = json.loads(path.read_text())
        if (
            not cast.get("synthetic")
            or cast.get("native_evidence")
            or cast.get("models_trained_or_evaluated")
        ):
            raise ValueError("the B1 forecast must be synthetic, model-free and no native evidence")
        evidence.update(forecast_macros(cast))
        (out / "followup_b1_forecast.tex").write_text(table_forecast(cast))
        sources.append(path)
    lines = ["% Generated by `jevbwe-typed followup`; do not edit."]
    lines += [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in evidence.items()]
    (out / "evidence.tex").write_text("\n".join(lines) + "\n")
    provenance = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1, sort_keys=True) + "\n")
    return dict(out=str(out), macros=len(evidence), sources=provenance)
