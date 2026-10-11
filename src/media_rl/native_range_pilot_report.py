"""Paper evidence for the wide-range development pilot: macros and two tables from its report.

Every macro carries RangePilot. The numbers are development evidence on sources N1 had already
used; nothing here is confirmatory.
"""

import argparse
import hashlib
import json
from pathlib import Path

from .native_actuator_qualification_report import count, number, signed, span
from .native_range_pilot import ABI, NAMES, REFERENCE, REGIMES

LABELS = dict(zip(NAMES, ("Quarter", "Low", "Mid", "Top", "Ceiling"), strict=True))
SPAN = "after_startup"  # the span the reading was fixed on
QUANTITIES = (  # macro stem, report key, digits, scale, whether its difference from the reference is exported
    ("Utility", "utility", 2, 1, True),
    ("OnTime", "on_time", 1, 100, True),
    ("Psnr", "psnr_on_time_db", 1, 1, True),
    ("Late", "shown_late", 1, 100, False),
    ("Never", "never_encoded", 1, 100, False),
    ("Age", "age_median_ms", 0, 1, False),
    ("Rate", "encoder_kbps", 0, 1, False),
    ("RateShare", "encoder_over_capacity", 0, 100, False),
    ("Buffer", "jitter_buffer_ms", 0, 1, True),
)
STATEMENTS = dict(
    RangePilotMoves="moves_on_time",
    RangePilotPays="pays_on_the_endpoint",
    RangePilotCosts="costs_on_the_endpoint",
    RangePilotEmpties="empties_the_receiver_buffer",
)


def _shown(value, digits, scale=1.0, sign=False):
    if value is None:  # a level or schedule without sessions
        return "n/a"
    return (signed if sign else number)(scale * value, digits)


def _between(entry, digits, scale=1.0):
    """A difference and its interval as two cells."""
    pair = entry["interval95"]
    return (
        _shown(entry["mean"], digits, scale, sign=True),
        "" if pair is None else span([scale * v for v in pair], digits),
    )


def named(levels):
    """Levels in a sentence: 'no level', '0.25', '0.25 and the ceiling'."""
    words = ["the ceiling" if name == NAMES[-1] else name for name in levels]
    if len(words) < 2:
        return words[0] if words else "no level"
    return ", ".join(words[:-1]) + " and " + words[-1]


def macros(report):
    seen, read = report["all_schedules"][SPAN], report["reading"]
    rows = dict(
        RangePilotSessions=count(report["sessions"]),
        RangePilotPlanned=count(report["planned_sessions"]),
        RangePilotSources=count(report["sources"]),
    )
    for name, label in LABELS.items():
        for stem, key, digits, scale, compared in QUANTITIES:
            entry = seen[key][name]
            rows[f"RangePilot{stem}{label}"] = _shown(entry["level"]["mean"], digits, scale)
            if compared and name != NAMES[REFERENCE]:
                rows[f"RangePilot{stem}Diff{label}"], rows[f"RangePilot{stem}Diff{label}T"] = _between(
                    entry["minus_reference"], digits, scale
                )
    for macro, statement in STATEMENTS.items():
        rows[macro] = named([name for name, holds in read[statement].items() if holds])
    rows["RangePilotCeilingWorst"] = "is" if read["the_ceiling_is_worst"] else "is not"
    return rows


def _tabular(columns, head, lines):
    return "\n".join([f"\\begin{{tabular}}{{{columns}}}", "\\toprule", head, "\\midrule", *lines]) + (
        "\n\\bottomrule\n\\end{tabular}\n"
    )


def table_levels(report):
    """Each level's mean over sources, from the second hold on."""

    def row(first, label, table, key, digits, scale=1.0):
        cells = [_shown(table[key][name]["level"]["mean"], digits, scale) for name in NAMES]
        return " & ".join([first, label, *cells]) + " \\\\"

    seen = report["all_schedules"][SPAN]
    lines = [
        row("All", "utility", seen, "utility", 2),
        row("", "on time (\\%)", seen, "on_time", 1, 100),
        row("", "PSNR of on-time frames (dB)", seen, "psnr_on_time_db", 1),
        row("", "shown late (\\%)", seen, "shown_late", 1, 100),
        row("", "never encoded (\\%)", seen, "never_encoded", 1, 100),
        row("", "encoder rate (kbit/s)", seen, "encoder_kbps", 0),
        row("", "encoder rate over capacity (\\%)", seen, "encoder_over_capacity", 0, 100),
        row("", "receiver jitter buffer (ms)", seen, "jitter_buffer_ms", 0),
        "\\midrule",
    ]
    for regime in REGIMES:
        own = report["by_schedule"][regime][SPAN]
        lines.append(row(regime.capitalize(), "utility", own, "utility", 2))
        lines.append(row("", "on time (\\%)", own, "on_time", 1, 100))
    head = "Schedule & Quantity & " + " & ".join(NAMES) + " \\\\"
    return _tabular("ll" + "r" * len(NAMES), head, lines)


def table_differences(report):
    """Each level minus the reference level, within source and schedule, with 95% intervals."""
    others = [name for i, name in enumerate(NAMES) if i != REFERENCE]

    def row(first, label, table, key, digits, scale=1.0):
        cells = [" ".join(_between(table[key][name]["minus_reference"], digits, scale)) for name in others]
        return " & ".join([first, label, *cells]) + " \\\\"

    seen = report["all_schedules"][SPAN]
    lines = [
        row("All", "utility", seen, "utility", 2),
        row("", "on time (points)", seen, "on_time", 1, 100),
        row("", "receiver jitter buffer (ms)", seen, "jitter_buffer_ms", 0),
        "\\midrule",
    ]
    for regime in REGIMES:
        own = report["by_schedule"][regime][SPAN]
        lines.append(row(regime.capitalize(), "utility", own, "utility", 2))
        lines.append(row("", "on time (points)", own, "on_time", 1, 100))
    reference = NAMES[REFERENCE]
    head = "Schedule & Quantity & " + " & ".join(f"{name} $-$ {reference}" for name in others) + " \\\\"
    return _tabular("ll" + "l" * len(others), head, lines)


def export(report_path, out):
    """Write the macros and tables. Refuses anything that is not the pilot's own report."""
    report_path, out = Path(report_path), Path(out)
    report = json.loads(report_path.read_text())
    if report.get("abi") != ABI + "_report" or report.get("development_pilot") is not True:
        raise ValueError("the development pilot's report is required")
    if report.get("confirmatory") is not False or report.get("learned_controller_promoted") is not False:
        raise ValueError("the pilot confirms and promotes nothing")
    evidence = macros(report)
    out.mkdir(parents=True, exist_ok=True)
    (out / "range_pilot_levels.tex").write_text(table_levels(report))
    (out / "range_pilot_differences.tex").write_text(table_differences(report))
    lines = ["% Generated by `python -m media_rl.native_range_pilot_report`; do not edit."]
    lines += [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in evidence.items()]
    (out / "evidence.tex").write_text("\n".join(lines) + "\n")
    provenance = {str(report_path): hashlib.sha256(report_path.read_bytes()).hexdigest()}
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1, sort_keys=True) + "\n")
    return dict(out=str(out), macros=len(evidence), sessions=report["sessions"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = export(args.report, args.out)
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
