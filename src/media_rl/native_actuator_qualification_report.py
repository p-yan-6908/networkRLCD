"""Paper evidence for Native Phase N1, read from the registered final analysis.

Every number comes from the final report, the public interim record, the sealed plan and the
capture manifests; nothing is typed in by hand. The sentences that state the outcome and what
follows from it were committed before any outcome was observed, and the registered verdict
alone selects among them.
"""

import argparse
import hashlib
import json
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


def export(final, public, protocol, out, allow_mock=False, pool=None):
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
    out.mkdir(parents=True, exist_ok=True)
    tables = dict(
        n1_primary=table_primary(report),
        n1_regimes=table_regimes(report),
        n1_complexity=table_complexity(report),
        n1_sources=table_sources(report, plan, json.loads(Path(pool).read_text()) if pool else None),
    )
    for name, text in tables.items():
        (out / f"{name}.tex").write_text(text)
    lines = ["% Generated by `python -m media_rl.native_actuator_qualification_report`; do not edit."]
    lines += [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in evidence.items()]
    (out / "evidence.tex").write_text("\n".join(lines) + "\n")
    sources = [final, public, protocol, *manifests, *([Path(pool)] if pool else [])]
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
    parser.add_argument("--allow-mock", action="store_true", help="tests only: never for the paper")
    args = parser.parse_args(argv)
    try:
        result = export(args.final, args.public, args.protocol, args.out, args.allow_mock, args.pool)
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
