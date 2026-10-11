"""Paper evidence for Native Phase N1, read from the registered final analysis.

Every number comes from the final report, the public interim record, the sealed plan and the
capture manifests; nothing is typed in by hand. The sentences that state the outcome and what
follows from it were committed before any outcome was observed, and the registered verdict
alone selects among them.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from . import native_actuator_qualification as qualification
from .native_actuator_qualification_panel import REGIMES, STRATA

QUALIFIED, NOT_SEPARABLE, INCONCLUSIVE = qualification.VERDICTS
CONTRASTS = (("Lower", "0.85 $-$ 0.65"), ("Upper", "1.05 $-$ 0.85"))
ARMS = ("Low", "Mid", "High")
VERDICT_NAME = {
    QUALIFIED: "qualified",
    NOT_SEPARABLE: "not separable at the registered threshold",
    INCONCLUSIVE: "inconclusive",
}
OUTCOME = {
    QUALIFIED: (
        "Both lower bounds are above the margin, so the registered outcome is \\emph{qualified}: "
        "on this native stack the requested ratio separates the actual encoded rate."
    ),
    NOT_SEPARABLE: (
        "At least one upper bound is below the margin, so the registered outcome is "
        "\\emph{not separable at the registered threshold}: on this native stack at least one "
        "adjacent step of the requested ratio does not move the actual encoded rate by the registered margin."
    ),
    INCONCLUSIVE: (
        "Neither registered condition is met, so the registered outcome is \\emph{inconclusive}: "
        "N1 supports no claim in either direction."
    ),
}
UNSUPPORTED = (
    "A capture-support gate failed, so the registered outcome is \\emph{inconclusive} whatever "
    "the bounds are, and the estimates are descriptive only."
)
CONSEQUENCE = {
    QUALIFIED: (
        "By the registration, the actuator argument for acquiring the 96 source units of the "
        "powered panel holds, and that panel keeps its own gates on its own units."
    ),
    NOT_SEPARABLE: (
        "By the registration, the 96 source units of the powered panel are not acquired as "
        "designed, and the open question becomes the actuator itself."
    ),
    INCONCLUSIVE: "By the registration, a further native phase needs its own registration before any claim.",
}
ABSTRACT = {
    QUALIFIED: (
        "A thirteenth study, native and registered in advance, finds that on a real browser stack the "
        "requested ratio separates the actual encoded rate at the registered margin; it tests the "
        "actuator only, with no controller acting and no quality claim."
    ),
    NOT_SEPARABLE: (
        "A thirteenth study, native and registered in advance, finds that on a real browser stack at "
        "least one adjacent step of the requested ratio does not move the actual encoded rate by the "
        "registered margin, so the simulator's actuation assumption is not supported on that stack."
    ),
    INCONCLUSIVE: (
        "A thirteenth study, native and registered in advance, asks only whether the requested ratio "
        "separates the actual encoded rate on a real browser stack, and is inconclusive."
    ),
}
CONCLUSION = {
    QUALIFIED: (
        "The one native result concerns the actuator: on a real browser stack over a local emulated "
        "bottleneck, requesting a lower or a higher ratio of the bandwidth estimate moves the actual "
        "encoded rate by more than the registered margin (Section~\\ref{sec:native-n1}). No controller "
        "has acted natively, so this qualifies the instrument and nothing more."
    ),
    NOT_SEPARABLE: (
        "The one native result concerns the actuator and is negative: on a real browser stack over a "
        "local emulated bottleneck, at least one adjacent step of the requested ratio does not move the "
        "actual encoded rate by the registered margin (Section~\\ref{sec:native-n1}), so the simulator "
        "studies rest on an actuation assumption that this stack does not support."
    ),
    INCONCLUSIVE: (
        "The one native study, of whether the requested ratio moves the actual encoded rate on a real "
        "browser stack, is inconclusive (Section~\\ref{sec:native-n1}), so the simulator's actuation "
        "assumption remains untested."
    ),
}
DESIGNATION = {
    True: (
        "The registered designation \\emph{qualified on average, heterogeneous by complexity} is "
        "attached: the test that the three tercile means are equal rejects for at least one contrast."
    ),
    False: (
        "The heterogeneity designation is not attached, which is not evidence that the actuator "
        "behaves alike across complexity."
    ),
    None: "The heterogeneity designation applies to a qualified outcome only and is not assessed.",
}


def number(value, digits=3):
    return f"{value:.{digits}f}".replace("-", "$-$")


def signed(value, digits=3):
    return f"{value:+.{digits}f}".replace("-", "$-$").replace("+", "$+$")


def percent(value, digits=1):
    return f"{100 * value:.{digits}f}"


def probability(value):
    return "$<$0.001" if value < 0.001 else f"{value:.3f}"


def count(value):
    return f"{value:,}".replace(",", "{,}")


def escape(text):
    for raw, safe in (("\\", "/"), ("&", "\\&"), ("%", "\\%"), ("#", "\\#"), ("_", "\\_"), ("$", "\\$")):
        text = text.replace(raw, safe)
    return text.replace("{", "(").replace("}", ")").replace("^", " ").replace("~", " ")


def typeset(text):
    """A title the paper's Latin font can set: runs in other scripts are elided, never transliterated."""
    pieces, elided = [], False
    for character in text:
        if ord(character) <= 0x024F or 0x2010 <= ord(character) <= 0x2027:
            pieces.append(character)
            elided = False
        elif not elided:
            pieces.append(" [\x00] ")
            elided = True
    words = escape("".join(pieces)).split()
    kept = [w for i, w in enumerate(words) if not (w == "[\x00]" and i and words[i - 1] == "[\x00]")]
    return " ".join(kept).replace("[\x00]", "[\\ldots]")


def span(pair, digits=3):
    return f"[{signed(pair[0], digits)}, {signed(pair[1], digits)}]"


def interim_sentence(report, first, maximum):
    total = report["primary"]["rule"]["total"]
    if report["interim"]["precision_futility"]:
        return (
            f"The blinded rule added no sources on grounds of precision: with the first-stage variance, "
            f"even the maximum of {maximum} sources would leave less than an even chance of qualifying at "
            f"the design effect. That is a statement about information and says nothing about the effect."
        )
    if total == first:
        return f"The blinded rule prescribed no extension beyond the first {first} sources."
    return (
        f"The blinded rule prescribed {total} sources, so {total - first} reserve sources were "
        f"captured after the interim."
    )


def contrast_macros(rows, name, analysis):
    for i, (key, _) in enumerate(CONTRASTS):
        rows[f"{name}{key}Mean"] = signed(analysis["mean_contrasts"][i])
        rows[f"{name}{key}Low"] = signed(analysis["lower_bounds"][i])
        rows[f"{name}{key}High"] = signed(analysis["upper_bounds"][i])
        rows[f"{name}{key}P"] = probability(analysis["p_values_above_margin"][i])
        rows[f"{name}{key}Share"] = percent(analysis["realised_share_of_requested_step"][i], 0)


def macros(report, public, protocol, peers, browsers):
    """Every macro of the N1 section. The verdict alone selects the outcome sentences."""
    verdict, primary, support = report["verdict"], report["primary"], report["support"]
    secondary, plan = report["secondary"], protocol["plan"]
    if verdict not in qualification.VERDICTS or report["abi"] != qualification.ABI + "_final":
        raise ValueError("a registered N1 final report is required")
    supported = report["capture_support_passed"] is True
    if not supported and verdict != INCONCLUSIVE:
        raise ValueError("a failed capture-support gate can only be inconclusive")
    if not primary["sources"] == primary["rule"]["total"] == public["prescribed_total_sources"]:
        raise ValueError("the analysed number of sources is not the one the blinded rule prescribed")
    if report["QoE_claims"] is not False or report["learned_controller_promoted"] is not False:
        raise ValueError("N1 makes no quality claim and promotes no controller")
    first, maximum = plan["first_stage_sources"], protocol["checks"]["rule_maximum_sources"]
    attached = (report["designation"] is not None) if verdict == QUALIFIED else None
    rows = dict(
        NOneVerdict=VERDICT_NAME[verdict],
        NOneOutcomeSentence=OUTCOME[verdict] if supported else UNSUPPORTED,
        NOneConsequenceSentence=CONSEQUENCE[verdict],
        NOneDesignationSentence=DESIGNATION[attached],
        NOneInterimSentence=interim_sentence(report, first, maximum),
        NOneAbstractSentence=" " + ABSTRACT[verdict],
        NOneConclusionSentence=" " + CONCLUSION[verdict],
        NOneSources=str(primary["sources"]),
        NOneFirstStage=str(first),
        NOneMaximum=str(maximum),
        NOneDegrees=str(primary["degrees_of_freedom"]),
        NOneMargin=number(plan["margin"], 2),
        NOnePeers=count(peers),
        NOneCohorts=count(support["assigned_cohorts"]),
        NOneSupport="passed" if supported else "failed",
        NOneComplete=percent(support["complete_fraction"]),
        NOneAlias=percent(support["alias_fraction"]),
        NOneGap=percent(support["arm_completeness_gap"]),
        NOneArmP=probability(support["arm_share_p_value"]),
        NOneSkipped=str(support["skipped_sources"]),
        NOneSeparating=str(primary["separating_sources"]),
        NOneSeparatingBound=percent(primary["separating_share_lower_bound"], 0),
        NOneSendVerdict=VERDICT_NAME[secondary["send_rate"]["verdict"]],
        NOneBrowser=escape("; ".join(browsers)) if browsers else "none (mock rows)",
        NOneBrowserBuilds=str(len(browsers)),
    )
    contrast_macros(rows, "NOne", primary)
    contrast_macros(rows, "NOneSend", secondary["send_rate"])
    for i, (key, _) in enumerate(CONTRASTS):
        rows[f"NOne{key}FirstSd"] = number(primary["first_stage_contrast_sd"][i])
        rows[f"NOne{key}Sd"] = number(secondary["per_source_contrast_sd"][i])
        low, high = secondary["per_source_contrast_sd_interval95"][i]
        rows[f"NOne{key}SdInterval"] = f"[{number(low)}, {number(high)}]"
        rows[f"NOneHetero{key}P"] = probability(primary["complexity"]["heterogeneity_p_values"][i])
    # Descriptive reading of the registered regime map, added after the outcome was known.
    tests = [
        (regime, label, secondary["regime_map"][regime]["holm_p_values"][i])
        for regime in REGIMES
        for i, label in enumerate(("lower", "upper"))
    ]
    below = [
        f"the {label} difference under the {regime} schedule"
        for regime, label, p in tests
        if p >= plan["alpha"]
    ]
    rows["NOneRegimeTests"] = str(len(tests))
    rows["NOneRegimeEstablished"] = str(len(tests) - len(below))
    rows["NOneRegimeOpen"] = " and ".join(below) if below else "none"
    for key, share in zip(ARMS, secondary["plateau_share_by_arm"]):
        rows[f"NOnePlateau{key}"] = percent(share, 0)
    for key, name in (("Encoder", "encoder"), ("Send", "send")):
        strength = secondary["first_stage_strength"][name]
        rows[f"NOne{key}F"] = "n/a" if strength["cluster_F"] is None else number(strength["cluster_F"], 1)
        rows[f"NOne{key}Rsq"] = "n/a" if strength["partial_R2"] is None else number(strength["partial_R2"], 3)
    return rows


def table_primary(report):
    lines = [
        "\\begin{tabular}{llrrrrr}",
        "\\toprule",
        "Endpoint & Contrast of assigned ratios & Mean & Lower bound & Upper bound & $p$ & Share of step (\\%) \\\\",
        "\\midrule",
    ]
    endpoints = (
        ("Encoded rate / frozen BWE (confirmatory)", report["primary"]),
        ("RTP send rate / frozen BWE (secondary)", report["secondary"]["send_rate"]),
    )
    for label, analysis in endpoints:
        for i, (_, contrast) in enumerate(CONTRASTS):
            lines.append(
                f"{label if i == 0 else ''} & {contrast} & {signed(analysis['mean_contrasts'][i])} & "
                f"{signed(analysis['lower_bounds'][i])} & {signed(analysis['upper_bounds'][i])} & "
                f"{probability(analysis['p_values_above_margin'][i])} & "
                f"{percent(analysis['realised_share_of_requested_step'][i], 0)} \\\\"
            )
    return "\n".join(lines + ["\\bottomrule", "\\end{tabular}"]) + "\n"


def table_regimes(report):
    lines = [
        "\\begin{tabular}{llrrrr}",
        "\\toprule",
        "Network regime & Contrast & Mean & Lower bound & Upper bound & Holm $p$ \\\\",
        "\\midrule",
    ]
    for regime in REGIMES:
        entry = report["secondary"]["regime_map"][regime]
        for i, (_, contrast) in enumerate(CONTRASTS):
            lines.append(
                f"{regime if i == 0 else ''} & {contrast} & {signed(entry['mean_contrasts'][i])} & "
                f"{signed(entry['lower_bounds'][i])} & {signed(entry['upper_bounds'][i])} & "
                f"{probability(entry['holm_p_values'][i])} \\\\"
            )
    return "\n".join(lines + ["\\bottomrule", "\\end{tabular}"]) + "\n"


def table_complexity(report):
    complexity = report["primary"]["complexity"]
    lines = [
        "\\begin{tabular}{lrll}",
        "\\toprule",
        f"Complexity tercile & Sources & {CONTRASTS[0][1]} & {CONTRASTS[1][1]} \\\\",
        "\\midrule",
    ]
    for label, means, intervals in zip(complexity["strata"], complexity["means"], complexity["intervals95"]):
        cells = " & ".join(f"{signed(m)} {span(pair)}" for m, pair in zip(means, intervals))
        lines.append(f"{STRATA[int(label)]} & {complexity['sources_per_stratum']} & {cells} \\\\")
    return "\n".join(lines + ["\\bottomrule", "\\end{tabular}"]) + "\n"


def table_sources(report, protocol, pool=None):
    planned = {s["cluster_id"]: s for s in protocol["sources"]}
    pages = {
        s["cluster_id"]: s["candidate_id"].removeprefix("commons-") for s in (pool or {}).get("sources", [])
    }
    lines = [
        "\\begin{tabular}{rrlll}",
        "\\toprule",
        "Order & Commons page & Source title & Licence & Complexity tercile \\\\",
        "\\midrule",
    ]
    for order, name in enumerate(report["sources"], 1):
        source = planned[name]
        lines.append(
            f"{order} & {pages.get(name, 'n/a')} & {typeset(source['source_title'])} & "
            f"{escape(source.get('license', 'mock'))} & {source['complexity_stratum']} \\\\"
        )
    return "\n".join(lines + ["\\bottomrule", "\\end{tabular}"]) + "\n"


def exploratory_cell(entry, digits):
    return f"{signed(entry['mean'], digits)} {span(entry['interval95'], digits)}"


def exploratory_macros(described):
    """Macros of the exploratory description. Every name carries Exp; none enters the outcome."""
    level, growth = described["response_level"], described["estimate_growth"]
    utility, free = described["quality"]["utility"], REGIMES[0]
    top, low, wide = "1.05 - 0.85", "0.85 - 0.65", "1.05 - 0.65"
    rows = {}
    for key, name in zip(ARMS, ("0.65", "0.85", "1.05")):
        rows[f"NOneExpLevel{key}"] = number(level["overall"]["arms"][name]["mean"], 2)
        rows[f"NOneExpFreeLevel{key}"] = number(level["regimes"][free]["arms"][name]["mean"], 2)
        grown = math.exp(growth["regimes"][free]["arms"][name]["mean"]) - 1
        rows[f"NOneExpFreeGrowth{key}"] = percent(grown, 0)
    held = [level["regimes"][r]["arms"]["1.05"]["mean"] for r in REGIMES[1:]]
    rows["NOneExpHeldLevelMin"], rows["NOneExpHeldLevelMax"] = number(min(held), 2), number(max(held), 2)
    entries = (
        ("NOneExpGrowthTop", growth["overall"]["contrasts"][top], 3),
        ("NOneExpGrowthLow", growth["overall"]["contrasts"][low], 3),
        ("NOneExpFreeGrowthTop", growth["regimes"][free]["contrasts"][top], 3),
        ("NOneExpUtility", utility["overall"]["contrasts"][wide], 2),
        ("NOneExpUtilityTop", utility["overall"]["contrasts"][top], 2),
        ("NOneExpFreeUtility", utility["regimes"][free]["contrasts"][wide], 2),
    )
    for name, entry, digits in entries:
        rows[name] = signed(entry["mean"], digits)
        rows[name + "T"] = span(entry["interval95"], digits)
    contrasts = [c for r in REGIMES for c in utility["regimes"][r]["contrasts"].values()]
    held_wide = [utility["regimes"][r]["contrasts"][wide]["interval95"] for r in REGIMES[1:]]
    rows.update(
        NOneExpHeldUtilityEstablished=str(sum(i[0] > 0 or i[1] < 0 for i in held_wide)),
        NOneExpHeldSchedules=str(len(held_wide)),
        NOneExpLowerBetter=str(sum(c["interval95"][1] < 0 for c in contrasts)),
        NOneExpUtilityContrasts=str(len(contrasts)),
        NOneExpInteractionP=number(min(v["holm_p_value"] for v in utility["regime_interaction"].values()), 2),
        NOneExpFreeBestTop=str(utility["best_arm_by_source"][free]["1.05"]),
    )
    pairs = utility["highest_minus_lowest_by_hold_pair"]
    first, *later = list(pairs[free])
    later_cells = [pairs[r][name]["interval95"] for r in REGIMES for name in later]
    rows.update(
        NOneExpSchedules=str(len(REGIMES)),
        NOneExpEarlyAhead=str(sum(pairs[r][first]["interval95"][0] > 0 for r in REGIMES)),
        NOneExpLaterCells=str(len(later_cells)),
        NOneExpLaterEstablished=str(sum(i[0] > 0 or i[1] < 0 for i in later_cells)),
        NOneExpLaterLowerBetter=str(sum(i[1] < 0 for i in later_cells)),
    )
    return rows


def table_exploratory(described):
    level, growth = described["response_level"], described["estimate_growth"]
    quality = described["quality"]
    lines = [
        "\\begin{tabular}{lrrrlll}",
        "\\toprule",
        " & \\multicolumn{3}{c}{Encoded rate / estimate at ratio} & Log growth of estimate & On-time PSNR & On-time fraction \\\\",
        "Schedule & 0.65 & 0.85 & 1.05 & 1.05 $-$ 0.85 & 1.05 $-$ 0.65 & 1.05 $-$ 0.65 \\\\",
        "\\midrule",
    ]
    scopes = [("all, equal weight", lambda e: e["overall"])] + [
        (r, lambda e, r=r: e["regimes"][r]) for r in REGIMES
    ]
    for label, pick in scopes:
        levels = " & ".join(number(pick(level)["arms"][a]["mean"], 2) for a in ("0.65", "0.85", "1.05"))
        lines.append(
            f"{label} & {levels} & {exploratory_cell(pick(growth)['contrasts']['1.05 - 0.85'], 2)} & "
            f"{exploratory_cell(pick(quality['utility'])['contrasts']['1.05 - 0.65'], 1)} & "
            f"{exploratory_cell(pick(quality['ontime_fraction'])['contrasts']['1.05 - 0.65'], 2)} \\\\"
        )
    return "\n".join(lines + ["\\bottomrule", "\\end{tabular}"]) + "\n"


def table_exploratory_holds(described):
    pairs = described["quality"]["utility"]["highest_minus_lowest_by_hold_pair"]
    names = list(pairs[REGIMES[0]])
    lines = [
        "\\begin{tabular}{l" + "l" * len(names) + "}",
        "\\toprule",
        "Schedule & " + " & ".join(n.capitalize().replace("-", "--") for n in names) + " \\\\",
        "\\midrule",
    ]
    for regime in REGIMES:
        lines.append(
            f"{regime} & " + " & ".join(exploratory_cell(pairs[regime][n], 1) for n in names) + " \\\\"
        )
    return "\n".join(lines + ["\\bottomrule", "\\end{tabular}"]) + "\n"


CONDITIONAL_SIGNALS = {
    "estimate_growth": ("Growth", "growth of the estimate since the previous hold (log)"),
    "jitter_ms": ("Jitter", "jitter (ms)"),
    "rtt_ms": ("Rtt", "round-trip time (ms)"),
    "rtt_trend_ms": ("Trend", "round-trip time trend (ms)"),
    "loss_fraction": ("Loss", "loss fraction"),
}
CONDITIONAL_MINIMUM_SHARE = 0.1  # a signal that flags fewer holds than this says nothing


def conditional_macros(passed):
    """Macros of the state-conditional second pass. Every name carries Cond; none enters the outcome."""
    signals, names = passed["signals"], passed["candidates"]
    usable = [n for n in signals if signals[n]["flagged_share"] >= CONDITIONAL_MINIMUM_SHARE]
    labels = [CONDITIONAL_SIGNALS[n][1].split(" (")[0] for n in names]
    rows = dict(
        NOneCondSignals=str(len(signals)),
        NOneCondUnusable=str(len(signals) - len(usable)),
        NOneCondCandidates=str(len(names)),
        NOneCondCandidateSentence=(
            f"The rule named {' and '.join(labels)} as a candidate for a confirmatory study."
            if names
            else "The rule named no signal as a candidate for a confirmatory study."
        ),
        NOneCondBestHolm=number(min(signals[n]["utility"]["interaction"]["holm_p_value"] for n in usable), 2),
    )
    for name in usable:
        key, entry = "NOneCond" + CONDITIONAL_SIGNALS[name][0], signals[name]
        rows[key + "Share"] = percent(entry["flagged_share"], 0)
        for part, label in (("flagged", "Flagged"), ("rest", "Rest"), ("interaction", "Interaction")):
            rows[key + label] = signed(entry["utility"][part]["mean"], 2)
            rows[key + label + "T"] = span(entry["utility"][part]["interval95"], 2)
    return rows


def table_conditional(passed):
    lines = [
        "\\begin{tabular}{llrlllr}",
        "\\toprule",
        "Signal before the hold & Flagged when & Flagged (\\%) & Benefit, flagged & Benefit, other holds & Difference & Holm $p$ \\\\",
        "\\midrule",
    ]
    for name, (_, label) in CONDITIONAL_SIGNALS.items():
        entry = passed["signals"][name]
        utility = entry["utility"]
        cells = [
            label,
            f"{entry['side']} {number(entry['threshold'], 3 if abs(entry['threshold']) < 1 else 1)}",
        ]
        cells.append(percent(entry["flagged_share"], 0))
        if entry["flagged_share"] < CONDITIONAL_MINIMUM_SHARE:
            cells += ["too few holds", exploratory_cell(utility["rest"], 1), "--", "--"]
        else:
            cells += [exploratory_cell(utility[k], 1) for k in ("flagged", "rest", "interaction")]
            cells.append(number(utility["interaction"]["holm_p_value"], 2))
        lines.append(" & ".join(cells) + " \\\\")
    return "\n".join(lines + ["\\bottomrule", "\\end{tabular}"]) + "\n"


DYNAMICS_RATIOS = dict(Low="0.65", Mid="0.85", Top="1.05")
DYNAMICS_DROPS = {"queue-building": "Shallow", "collapse-recovery": "Deep"}
POSITION_KINDS = dict(
    drop="Drop", after_drop="After", late_drop_schedules="Late", near_capacity="Near", room="Room"
)
DYNAMICS_BIN_S = 0.2


def _below_capacity(curves, regime):
    """Seconds after the acknowledgement by which the mean estimate is below the new capacity at every ratio."""
    ends = []
    for ratio in DYNAMICS_RATIOS.values():
        curve = curves[f"{regime}|2|{ratio}"]["estimate_over_capacity"]
        first = next((i for i, v in enumerate(curve) if v is not None and v < 1), None)
        if first is None:  # never below within the hold
            return None
        ends.append((first + 1) * DYNAMICS_BIN_S)
    return max(ends)


def dynamics_macros(inside, flags=None, bound=None):
    """Macros of the within-hold pass. Every name carries Dyn; no quality label is behind any of them."""
    tables, curves = inside["tables"], inside["curves"]
    settling, room, steady = (
        tables["encoder_settling"],
        tables["estimate_with_room"],
        tables["steady_constraint"],
    )
    rows = dict(NOneDynPeers=count(inside["peers"]), NOneDynHolds=count(inside["holds"]))
    for label, ratio in DYNAMICS_RATIOS.items():
        rows["NOneDynTargetEarly" + label] = number(settling["target"]["early"][ratio]["mean"], 2)
        rows["NOneDynTargetWindow" + label] = number(settling["target"]["outcome"][ratio]["mean"], 2)
        rows["NOneDynEncoderWindow" + label] = number(settling["encoder"]["outcome"][ratio]["mean"], 2)
        rows["NOneDynEncoderEnd" + label] = number(curves[f"underutilized|1|{ratio}"]["encoder"][-1], 2)
        rows["NOneDynRoomFirst" + label] = percent(room["first hold"]["end"][ratio]["mean"] - 1, 0)
        rows["NOneDynRoomLater" + label] = percent(room["later holds"]["end"][ratio]["mean"] - 1, 0)
        rows["NOneDynRecovery" + label] = percent(tables["recovery"]["estimate_at_end"][ratio]["mean"] - 1, 0)
        rows["NOneDynSteadySojourn" + label] = number(steady["outcome_sojourn_ms"][ratio]["mean"], 1)
    rows["NOneDynRoomJump"] = number(
        curves["underutilized|1|1.05"]["estimate"][2], 2
    )  # 0.4 to 0.6 s in hold 2
    recovery = tables["recovery"]["estimate_at_end"]["top_minus_lower"]
    rows["NOneDynRecoveryDiff"] = signed(recovery["mean"], 2)
    rows["NOneDynRecoveryDiffT"] = span(recovery["interval95"], 2)
    rows["NOneDynSteadyDiff"] = signed(steady["outcome_sojourn_ms"]["top_minus_lower"]["mean"], 1)
    rows["NOneDynSteadyDiffT"] = span(steady["outcome_sojourn_ms"]["top_minus_lower"]["interval95"], 1)
    rows["NOneDynSteadyLoss"] = percent(
        max(steady["dropped_share"][r]["mean"] for r in DYNAMICS_RATIOS.values()), 1
    )
    rows["NOneDynSteadyMechanism"] = "present" if steady["mechanism_present"] else "not established"
    rows["NOneDynSteadyWindow"] = "sees" if steady["visible_in_the_outcome_window"] else "does not see"
    for regime, name in DYNAMICS_DROPS.items():
        drop, key = tables["capacity_drop"][regime], "NOneDyn" + name
        for label, ratio in DYNAMICS_RATIOS.items():
            rows[key + "Peak" + label] = number(drop["peak_sojourn_ms"][ratio]["mean"], 0)
            rows[key + "Loss" + label] = percent(drop["dropped_share"][ratio]["mean"], 1)
        rows[key + "PeakDiff"] = signed(drop["peak_sojourn_ms"]["top_minus_lower"]["mean"], 0)
        rows[key + "PeakDiffT"] = span(drop["peak_sojourn_ms"]["top_minus_lower"]["interval95"], 0)
        rows[key + "Mechanism"] = "present" if drop["mechanism_present"] else "not established"
        below = _below_capacity(curves, regime)
        rows[key + "Below"] = "more than 3.0" if below is None else number(below, 1)
    if flags:
        rows["NOneDynFlagged"] = count(flags["flagged_holds"])
        for kind, label in POSITION_KINDS.items():
            rows["NOneDynFlag" + label] = percent(flags["kinds"][kind]["share_of_flagged_holds"], 0)
        for label, ratio in DYNAMICS_RATIOS.items():
            rows["NOneDynFlagDropAfter" + label] = percent(flags["drop_hold_by_previous_ratio"][ratio], 0)
    if bound:
        names = {"underutilized": "Room", "near-capacity": "Near", **DYNAMICS_DROPS}
        for regime, name in names.items():
            entry = bound["top_ratio_over_sources"][regime]
            rows["NOneDynBind" + name] = "n/a" if entry["mean"] is None else percent(entry["mean"], 0)
            pair = entry["interval95"]
            rows["NOneDynBind" + name + "T"] = (
                "" if pair is None else f"[{percent(pair[0], 0)}, {percent(pair[1], 0)}]"
            )
        for key, record in (
            ("NOneDynBindCapOverLive", "top_ratio_with_room_cap_over_live_estimate"),
            ("NOneDynBrowserShare", "browser_allocation_over_live_estimate"),
        ):
            median = bound[record]["median"]
            rows[key] = "n/a" if median is None else number(median, 2)
    return rows


DELIVERY_SCHEDULES = {"underutilized": "Room", "near-capacity": "Near", **DYNAMICS_DROPS}
DELIVERY_FATES = dict(OnTime="on_time", Late="shown_late", Never="never_encoded", Lost="encoded_not_shown")
DELIVERY_STATEMENTS = dict(
    NOneDelEncoderCost="a_lower_cap_costs_frames_at_the_encoder",
    NOneDelRestCost="a_higher_cap_costs_time_after_the_relay",
    NOneDelDeadline="it_reaches_the_deadline",
)


def _shown(value, digits, scale=1.0, sign=False):
    if value is None:  # a state without data, as on invented peers
        return "n/a"
    return (signed if sign else number)(scale * value, digits)


def _between(entry, digits, scale=1.0):
    """A difference and its interval as two cells."""
    pair = entry["interval95"]
    return (
        _shown(entry["mean"], digits, scale, sign=True),
        "" if pair is None else span([scale * v for v in pair], digits),
    )


def _across(entry):
    """Mean over the three ratios of a by-ratio entry."""
    values = [entry[ratio]["mean"] for ratio in DYNAMICS_RATIOS.values()]
    return None if any(v is None for v in values) else sum(values) / len(values)


def delivery_macros(delivered, first=None):
    """Macros of the delivery pass. Every name carries Del; timing labels are behind them and no PSNR."""
    tables = delivered["tables"]
    state = tables["all_schedules"]
    seen, receiver = state["outcome"], tables["receiver_per_phase"]
    rows = dict(
        NOneDelPeers=count(delivered["peers"]),
        NOneDelHolds=count(delivered["holds"]),
        NOneDelPhases=count(delivered["phases"]),
    )
    for label, ratio in DYNAMICS_RATIOS.items():
        for name, key in DELIVERY_FATES.items():
            rows[f"NOneDel{name}{label}"] = _shown(seen[key][ratio]["mean"], 1, 100)
        for name, key in (("Age", "age_median_ms"), ("Relay", "relay_ms"), ("Rest", "rest_ms")):
            rows[f"NOneDel{name}{label}"] = _shown(seen[key][ratio]["mean"], 0)
    for name, key in DELIVERY_FATES.items():
        rows[f"NOneDel{name}Diff"], rows[f"NOneDel{name}DiffT"] = _between(
            seen[key]["top_minus_lower"], 1, 100
        )
    rows["NOneDelRestDiff"], rows["NOneDelRestDiffT"] = _between(seen["rest_ms"]["top_minus_lower"], 1)
    for name, statement in DELIVERY_STATEMENTS.items():
        rows[name] = "holds" if state[statement] else "is not established"
    groups = {"": receiver["all_phases"]}
    groups.update({name: receiver["by_schedule"][regime] for regime, name in DELIVERY_SCHEDULES.items()})
    if "2" in receiver["by_phase_position"]:  # the phase that holds the drop
        groups["PhaseTwo"] = receiver["by_phase_position"]["2"]
    for name, table in groups.items():
        buffer = table["jitter_buffer_ms"]
        rows[f"NOneDel{name}Buffer"] = _shown(buffer["level"]["mean"], 0)
        rows[f"NOneDel{name}BufferSlope"], rows[f"NOneDel{name}BufferSlopeT"] = _between(
            buffer["slope_per_span_of_ratio"], 1
        )
    fills = receiver["all_phases"]["a_higher_cap_fills_the_receiver_buffer"]
    rows["NOneDelBufferFills"] = "holds" if fills else "is not established"
    for regime, name in DELIVERY_SCHEDULES.items():
        own = tables["by_schedule"][regime]["outcome"]
        rows[f"NOneDel{name}OnTime"] = _shown(_across(own["on_time"]), 0, 100)
        rows[f"NOneDel{name}Rest"] = _shown(_across(own["rest_ms"]), 0)
    if first:
        skipped = first["first_hold_frames"]["never_encoded"]["by_ratio"]
        timely = first["on_time"]["first_hold"]["by_ratio"]
        for label, ratio in DYNAMICS_RATIOS.items():
            rows["NOneDelStartNever" + label] = _shown(skipped[ratio]["mean"], 0, 100)
            rows["NOneDelStartOnTime" + label] = _shown(timely[ratio]["mean"], 0, 100)
        for name, key in (("Start", "first_hold"), ("After", "later_holds"), ("Pooled", "all_holds")):
            rows[f"NOneDel{name}Diff"], rows[f"NOneDel{name}DiffT"] = _between(
                first["on_time"][key]["highest_minus_lowest"], 1, 100
            )
    return rows


def table_delivery(delivered):
    tables = delivered["tables"]

    def row(state, label, entry, digits, scale=1.0):
        cells = [_shown(entry[ratio]["mean"], digits, scale) for ratio in DYNAMICS_RATIOS.values()]
        return (
            " & ".join([state, label, *cells, " ".join(_between(entry["top_minus_lower"], digits, scale))])
            + " \\\\"
        )

    seen = tables["all_schedules"]["outcome"]
    lines = [
        "\\begin{tabular}{llrrrl}",
        "\\toprule",
        "Schedule & Quantity & 0.65 & 0.85 & 1.05 & Top $-$ lower \\\\",
        "\\midrule",
        row("All", "on time (\\%)", seen["on_time"], 1, 100),
        row("", "shown late (\\%)", seen["shown_late"], 1, 100),
        row("", "never encoded (\\%)", seen["never_encoded"], 1, 100),
        row("", "encoded, not shown (\\%)", seen["encoded_not_shown"], 1, 100),
        row("", "median age (ms)", seen["age_median_ms"], 0),
        row("", "relay (ms)", seen["relay_ms"], 0),
        row("", "rest (ms)", seen["rest_ms"], 0),
        "\\midrule",
    ]
    for regime in DELIVERY_SCHEDULES:
        own = tables["by_schedule"][regime]["outcome"]
        lines.append(row(regime.capitalize(), "on time (\\%)", own["on_time"], 1, 100))
        lines.append(row("", "rest (ms)", own["rest_ms"], 0))
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


def table_dynamics(inside):
    tables = inside["tables"]

    def row(state, label, entry, digits, scale=1.0):
        cells = [number(scale * entry[ratio]["mean"], digits) for ratio in DYNAMICS_RATIOS.values()]
        gap = entry["top_minus_lower"]
        between = (
            f"{signed(scale * gap['mean'], digits)} {span([scale * v for v in gap['interval95']], digits)}"
        )
        return " & ".join([state, label, *cells, between]) + " \\\\"

    shallow, deep = (tables["capacity_drop"][regime] for regime in DYNAMICS_DROPS)
    steady = tables["steady_constraint"]
    lines = [
        "\\begin{tabular}{llrrrl}",
        "\\toprule",
        "State & Quantity & 0.65 & 0.85 & 1.05 & Top $-$ lower \\\\",
        "\\midrule",
        row("Shallower drop", "peak sojourn (ms)", shallow["peak_sojourn_ms"], 0),
        row("", "sojourn in the window (ms)", shallow["outcome_sojourn_ms"], 0),
        row("", "dropped (\\%)", shallow["dropped_share"], 1, 100),
        row("Deeper drop", "peak sojourn (ms)", deep["peak_sojourn_ms"], 0),
        row("", "sojourn in the window (ms)", deep["outcome_sojourn_ms"], 0),
        row("", "dropped (\\%)", deep["dropped_share"], 1, 100),
        row("Steady constraint", "peak sojourn (ms)", steady["peak_sojourn_ms"], 1),
        row("", "sojourn in the window (ms)", steady["outcome_sojourn_ms"], 1),
        row("", "dropped (\\%)", steady["dropped_share"], 1, 100),
        "\\midrule",
        row(
            "Room, later holds", "estimate at the end", tables["estimate_with_room"]["later holds"]["end"], 2
        ),
        row("Return of capacity", "estimate at the end", tables["recovery"]["estimate_at_end"], 2),
    ]
    return "\n".join([*lines, "\\bottomrule", "\\end{tabular}"]) + "\n"


def figure_dynamics(inside, path):
    """Three small multiples of the mean curves: one y-axis each, the registered window as a wash."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, quiet, grid = "#1f2933", "#52606d", "#e4e7eb"
    series = (
        ("0.65", "#2a78d6", "-"),
        ("0.85", "#eb6834", (0, (5, 2))),
        ("1.05", "#1baf7a", (0, (1.2, 1.6))),
    )
    panels = (
        ("underutilized|1", "estimate", "Estimate over its frozen value", "Room on the link (hold 2)"),
        (
            "collapse-recovery|2",
            "estimate_over_capacity",
            "Estimate over the new capacity",
            "Deeper drop (hold 3)",
        ),
        ("collapse-recovery|2", "sojourn_ms", "Time in the relay (ms)", "Deeper drop (hold 3)"),
    )
    plt.rcParams.update({"font.size": 7.5, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.35))
    seconds = [DYNAMICS_BIN_S * (i + 0.5) for i in range(inside["bins"])]
    low, high = (v / 1000 for v in inside["windows_ms"]["outcome"])
    for axis, (key, name, label, title) in zip(axes, panels, strict=True):
        axis.axvspan(low, high, color=quiet, alpha=0.10, linewidth=0)
        for ratio, colour, dash in series:
            values = [float("nan") if v is None else v for v in inside["curves"][f"{key}|{ratio}"][name]]
            axis.plot(
                seconds,
                values,
                color=colour,
                linestyle=dash,
                linewidth=1.5,
                solid_capstyle="round",
                label=ratio,
            )
            axis.plot(
                seconds[-1],
                values[-1],
                "o",
                color=colour,
                markersize=4.5,
                markeredgecolor="white",
                markeredgewidth=1.0,
            )
        if name == "estimate_over_capacity":
            axis.axhline(1, color=quiet, linewidth=0.6)
        axis.set_title(title, fontsize=7.5, color=ink, loc="left")
        axis.set_xlabel("Seconds since the request", color=quiet)
        axis.set_ylabel(label, color=quiet)
        axis.set_xlim(0, 3.0)
        axis.set_ylim(bottom=0)
        axis.grid(axis="y", color=grid, linewidth=0.5)
        axis.set_axisbelow(True)
        axis.tick_params(colors=quiet, length=2)
        for side in ("left", "bottom"):
            axis.spines[side].set_color(grid)
    top = axes[0].get_ylim()[1]
    axes[0].text(
        (low + high) / 2, 0.04 * top, "registered\nwindow", ha="center", va="bottom", fontsize=6, color=quiet
    )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        title="Requested ratio",
        ncol=3,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        fontsize=7,
        title_fontsize=7,
        handlelength=3.2,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, metadata={"CreationDate": None})
    plt.close(fig)


def capture_facts(report):
    """Peers behind the analysis and the browser builds that produced them, read after the final."""
    peers, browsers, files = 0, set(), []
    for root in report["input_manifests_sha256"]:
        manifest = Path(root) / "manifest.json"
        files.append(manifest)
        for identifier in json.loads(manifest.read_text()).get("episodes", {}):
            peers += 1
            browsers.add(json.loads((Path(root) / identifier / "summary.json").read_text())["browser_build"])
    return peers, sorted(browsers), files


def export(
    final,
    public,
    protocol,
    out,
    allow_mock=False,
    pool=None,
    exploratory=None,
    conditional=None,
    dynamics=None,
    flags=None,
    binding=None,
    delivery=None,
    first_hold=None,
):
    """Write macros and tables for the paper from one registered final report."""
    final, public, protocol, out = Path(final), Path(public), Path(protocol), Path(out)
    report, interim, plan = (json.loads(p.read_text()) for p in (final, public, protocol))
    digest = hashlib.sha256(protocol.read_bytes()).hexdigest()
    if not report["protocol_sha256"] == interim["protocol_sha256"] == digest:
        raise ValueError("the final report, the interim record and the sealed plan do not belong together")
    if report["mock"] is not False and not allow_mock:
        raise ValueError("mock rows prove nothing about the native stack and never enter the paper")
    peers, browsers, manifests = capture_facts(report)
    evidence = macros(report, interim, plan, peers, browsers)
    described = None
    if exploratory:
        described = json.loads(Path(exploratory).read_text())
        captured = {
            json.loads(m.read_text()).get("artifacts_sha256", {}).get("cohorts.json") for m in manifests
        }
        if described.get("exploratory") is not True or described.get("mock") is not False:
            raise ValueError("an exploratory description of native rows is required")
        if described["rows_sha256"] not in captured:
            raise ValueError("the exploratory description is not of the analysed capture's rows")
        evidence.update(exploratory_macros(described))
    passed = None
    if conditional:
        passed = json.loads(Path(conditional).read_text())
        if passed.get("second_pass_on_the_same_rows") is not True or passed.get("mock") is not False:
            raise ValueError("a state-conditional pass over native rows is required")
        if not described or passed["rows_sha256"] != described["rows_sha256"]:
            raise ValueError("the second pass must be of the same rows as the exploratory description")
        evidence.update(conditional_macros(passed))
    inside = marked = None
    if dynamics:
        inside = json.loads(Path(dynamics).read_text())
        if not (
            inside.get("mechanism_only") is True and inside.get("quality_or_ontime_labels_read") is False
        ):
            raise ValueError("a mechanism-only within-hold description is required")
        if not described or inside["rows_sha256"] != described["rows_sha256"]:
            raise ValueError("the within-hold pass must be of the same rows as the exploratory description")
        if flags:
            marked = json.loads(Path(flags).read_text())
            if marked.get("outcome_free") is not True or marked["rows_sha256"] != inside["rows_sha256"]:
                raise ValueError("an outcome-free flag composition of the same rows is required")
        bound = json.loads(Path(binding).read_text()) if binding else None
        if bound and bound.get("mechanism_only") is not True:
            raise ValueError("a mechanism-only record of where the cap binds is required")
        evidence.update(dynamics_macros(inside, marked, bound))
    delivered = started = None
    if delivery:
        delivered = json.loads(Path(delivery).read_text())
        if not (delivered.get("exploratory") is True and delivered.get("psnr_read") is False):
            raise ValueError("an exploratory delivery description that reads no PSNR is required")
        if not described or delivered["rows_sha256"] != described["rows_sha256"]:
            raise ValueError("the delivery pass must be of the same rows as the exploratory description")
        if first_hold:
            started = json.loads(Path(first_hold).read_text())
            if started.get("added_after_the_tables_were_read") is not True:
                raise ValueError("the first-hold split must be marked as added after the tables were read")
        evidence.update(delivery_macros(delivered, started))
    out.mkdir(parents=True, exist_ok=True)
    tables = dict(
        n1_primary=table_primary(report),
        n1_regimes=table_regimes(report),
        n1_complexity=table_complexity(report),
        n1_sources=table_sources(report, plan, json.loads(Path(pool).read_text()) if pool else None),
    )
    if described:
        tables.update(
            n1_exploratory=table_exploratory(described),
            n1_exploratory_holds=table_exploratory_holds(described),
        )
    if passed:
        tables.update(n1_conditional=table_conditional(passed))
    if inside:
        tables.update(n1_dynamics=table_dynamics(inside))
        figure_dynamics(inside, out / "n1_dynamics.pdf")
    if delivered:
        tables.update(n1_delivery=table_delivery(delivered))
    for name, text in tables.items():
        (out / f"{name}.tex").write_text(text)
    lines = ["% Generated by `python -m media_rl.native_actuator_qualification_report`; do not edit."]
    lines += [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in evidence.items()]
    (out / "evidence.tex").write_text("\n".join(lines) + "\n")
    extra = (
        pool,
        exploratory,
        conditional,
        dynamics,
        flags if dynamics else None,
        binding if dynamics else None,
        delivery,
        first_hold if delivery else None,
    )
    sources = [final, public, protocol, *manifests, *(Path(p) for p in extra if p)]
    provenance = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1, sort_keys=True) + "\n")
    return dict(out=str(out), verdict=report["verdict"], macros=len(evidence), mock=report["mock"])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Paper evidence for Native Phase N1")
    parser.add_argument("--final", required=True, type=Path)
    parser.add_argument("--public", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--pool", type=Path, help="tracked pool record, for the sources' Commons page numbers"
    )
    parser.add_argument("--exploratory", type=Path, help="exploratory description of the same rows")
    parser.add_argument("--conditional", type=Path, help="state-conditional second pass over the same rows")
    parser.add_argument("--dynamics", type=Path, help="within-hold description of the same capture")
    parser.add_argument("--flags", type=Path, help="outcome-free count of the holds the B1 flag marks")
    parser.add_argument("--binding", type=Path, help="where the requested cap limits the encoder")
    parser.add_argument("--delivery", type=Path, help="where frames and time go, from the same capture")
    parser.add_argument("--delivery-first-hold", type=Path, help="the first hold against the later ones")
    parser.add_argument("--allow-mock", action="store_true", help="tests only: never for the paper")
    args = parser.parse_args(argv)
    try:
        result = export(
            args.final,
            args.public,
            args.protocol,
            args.out,
            args.allow_mock,
            args.pool,
            args.exploratory,
            args.conditional,
            args.dynamics,
            args.flags,
            args.binding,
            args.delivery,
            args.delivery_first_hold,
        )
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
