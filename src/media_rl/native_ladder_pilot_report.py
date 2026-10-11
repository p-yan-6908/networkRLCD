"""Paper evidence for the controller development pilot: macros and four tables from its report.

Every macro carries LadderPilot. The numbers are development evidence on sources N1 had already
used; nothing here is confirmatory. The timeline was added after the report was read, and the
export refuses one that does not say so. The range pilot's headroom pass supplies what the
design rests on: the fixed levels tuned without the scored source.
"""

import argparse
import hashlib
import json
from pathlib import Path

from .native_actuator_qualification_report import count
from .native_ladder_pilot import ABI, BIN_MS, BINS, CANDIDATES, FIXED_PAIRS, NAMES, PHASES, REGIMES, TUNED
from .native_range_pilot import ABI as RANGE_ABI
from .native_range_pilot_report import _between, _shown, _tabular

LABELS = dict(zip(NAMES, ("Ladder", "Fast", "Quarter", "Low", "Top"), strict=True))
SPAN, LATER = "session", "after_startup"  # the span the reading was fixed on, and the one beside it
QUANTITIES = (  # macro stem, report key, digits, scale
    ("Utility", "utility", 2, 1),
    ("OnTime", "on_time", 1, 100),
    ("Psnr", "psnr_on_time_db", 1, 1),
    ("Late", "shown_late", 1, 100),
    ("Never", "never_encoded", 1, 100),
    ("Age", "age_median_ms", 0, 1),
    ("Rate", "encoder_kbps", 0, 1),
    ("RateShare", "encoder_over_capacity", 0, 100),
)
GROUPS = (  # each candidate against each fixed level, the fast rule against the slow one, the fixed levels
    *(tuple((candidate, name) for name in NAMES if name not in CANDIDATES) for candidate in CANDIDATES),
    ((CANDIDATES[1], CANDIDATES[0]),),
    FIXED_PAIRS,
)
PAIRS = tuple(pair for group in GROUPS for pair in group)
DROPS = ("queue-building", "collapse-recovery")  # the schedules whose capacity falls
FAST_CUT = {1: "helps", -1: "hurts", 0: "is not shown to matter"}


def _listed(words):
    return words[0] if len(words) < 2 else ", ".join(words[:-1]) + " and " + words[-1]


def verdict(against):
    """A candidate's reading against the fixed levels as part of a sentence."""
    parts = []
    for sign, verb in ((-1, "loses to"), (1, "beats"), (0, "is not separated from")):
        names = [name for name, value in against.items() if value == sign]
        if names:
            parts.append(f"{verb} {_listed(names)}")
    return _listed(parts)


def _contrast(table, key, pair):
    return table[key]["contrasts"][f"{pair[0]} minus {pair[1]}"]


def macros(report, timeline, headroom):
    seen, later = report["all_schedules"][SPAN], report["all_schedules"][LATER]
    rows = dict(
        LadderPilotSessions=count(report["sessions"]),
        LadderPilotPlanned=count(report["planned_sessions"]),
        LadderPilotSources=count(report["sources"]),
    )
    tuned = headroom["plans"]["leaving_one_source_out"]  # what the design rests on, from the range pilot
    rows["LadderPilotTunedGain"], rows["LadderPilotTunedGainT"] = _between(tuned["fixed_minus_reference"], 2)
    rows["LadderPilotScheduleGain"], rows["LadderPilotScheduleGainT"] = _between(
        tuned["schedule_aware_minus_fixed"], 2
    )
    for name in TUNED:
        rows[f"LadderPilotFolds{LABELS[name]}"] = count(
            headroom["plans"]["levels_chosen_in_the_folds"]["fixed"][name]
        )
    for name, label in LABELS.items():
        for stem, key, digits, scale in QUANTITIES:
            rows[f"LadderPilot{stem}{label}"] = _shown(
                seen[key]["arms"][name]["level"]["mean"], digits, scale
            )
        rows[f"LadderPilotLaterUtility{label}"] = _shown(later["utility"]["arms"][name]["level"]["mean"], 2)
        rows[f"LadderPilotRepeat{label}"] = _shown(
            report["repeatability"][name]["mean_absolute_difference"], 2
        )
    for pair in PAIRS:
        stem = LABELS[pair[0]] + LABELS[pair[1]]
        for tag, table, key, digits, scale in (
            ("Utility", seen, "utility", 2, 1),
            ("OnTime", seen, "on_time", 1, 100),
            ("LaterUtility", later, "utility", 2, 1),
        ):
            rows[f"LadderPilot{tag}Diff{stem}"], rows[f"LadderPilot{tag}Diff{stem}T"] = _between(
                _contrast(table, key, pair), digits, scale
            )
    for name in CANDIDATES:
        rows[f"LadderPilotReading{LABELS[name]}"] = verdict(
            report["reading"][name]["against_each_fixed_level"]
        )
    rows["LadderPilotFastCut"] = FAST_CUT[report["reading"]["fast_minus_slow"]]
    ups = [
        block["share_of_decisions"]["up"]
        for own in report["what_the_rule_did"].values()
        for block in own.values()
        if block["share_of_decisions"]["up"] is not None
    ]
    rows["LadderPilotUpShare"] = _shown(
        max(ups, default=None), 1, 100
    )  # the largest over rules and schedules
    held = timeline["phases_by_schedule"][DROPS[-1]]  # added after the report was read
    for name, label in LABELS.items():
        for k, phase in enumerate(timeline["phases"]):
            if k:  # the phases from the fall of capacity on
                rows[f"LadderPilotDropBuffer{phase.capitalize()}{label}"] = _shown(
                    held[name]["jitter_buffer_ms"][k], 0
                )
                rows[f"LadderPilotDropLoad{phase.capitalize()}{label}"] = _shown(
                    held[name]["offered_over_capacity"][k], 0, 100
                )
    return rows


def table_arms(report):
    """Each arm's mean over sources: the whole session, and the endpoint from the second change on."""

    def row(first, label, table, key, digits, scale=1.0):
        cells = [_shown(table[key]["arms"][name]["level"]["mean"], digits, scale) for name in NAMES]
        return " & ".join([first, label, *cells]) + " \\\\"

    seen = report["all_schedules"][SPAN]
    lines = [
        row("All", "utility", seen, "utility", 2),
        row("", "on time (\\%)", seen, "on_time", 1, 100),
        row("", "PSNR of on-time frames (dB)", seen, "psnr_on_time_db", 1),
        row("", "shown late (\\%)", seen, "shown_late", 1, 100),
        row("", "never encoded (\\%)", seen, "never_encoded", 1, 100),
        row("", "median age of shown frames (ms)", seen, "age_median_ms", 0),
        row("", "encoder rate (kbit/s)", seen, "encoder_kbps", 0),
        row("", "encoder rate over capacity (\\%)", seen, "encoder_over_capacity", 0, 100),
        row("", "utility from the second change on", report["all_schedules"][LATER], "utility", 2),
        "\\midrule",
    ]
    for regime in REGIMES:
        own = report["by_schedule"][regime][SPAN]
        lines.append(row(regime.capitalize(), "utility", own, "utility", 2))
        lines.append(row("", "on time (\\%)", own, "on_time", 1, 100))
    head = "Schedule & Quantity & " + " & ".join(NAMES) + " \\\\"
    return _tabular("ll" + "r" * len(NAMES), head, lines)


def table_differences(report):
    """Differences of the endpoint within source and schedule, with 95% intervals."""
    tables = [report["all_schedules"][SPAN], report["all_schedules"][LATER]]
    tables += [report["by_schedule"][regime][SPAN] for regime in REGIMES]
    lines = []
    for group in GROUPS:
        if lines:
            lines.append("\\midrule")
        for pair in group:
            cells = [" ".join(_between(_contrast(table, "utility", pair), 2)) for table in tables]
            lines.append(" & ".join([f"{pair[0]} $-$ {pair[1]}", *cells]) + " \\\\")
    head = (
        "Difference & All schedules & All, from the second change on & "
        + " & ".join(regime.capitalize() for regime in REGIMES)
        + " \\\\"
    )
    return _tabular("l" + "l" * len(tables), head, lines)


def table_timeline(timeline):
    """Added after the report was read: delivery in stretches of 3 s, over sources."""
    drop = timeline["by_schedule"][DROPS[-1]]
    blocks = (
        ("Utility, all schedules", timeline["all_schedules"], "utility", 1, 1),
        (f"On time (\\%), {DROPS[-1]}", drop, "on_time", 0, 100),
        (f"Median age of shown frames (ms), {DROPS[-1]}", drop, "age_median_ms", 0, 1),
        (f"Ratio in force at the middle, {DROPS[-1]}", drop, "ratio", 2, 1),
    )
    lines = []
    for title, block, key, digits, scale in blocks:
        if lines:
            lines.append("\\midrule")
        for i, name in enumerate(NAMES):
            cells = [_shown(value, digits, scale) for value in block[name][key]]
            lines.append(" & ".join(["" if i else title, name, *cells]) + " \\\\")
    seconds = timeline["bin_ms"] // 1000
    head = (
        "Quantity & Arm & "
        + " & ".join(f"{k * seconds}--{(k + 1) * seconds}~s" for k in range(BINS))
        + " \\\\"
    )
    return _tabular("ll" + "r" * BINS, head, lines)


def table_phases(timeline):
    """Added after the report was read: the receiver and the relay in each capacity phase, where capacity falls."""
    columns = (
        ("Receiver's jitter buffer (ms)", "jitter_buffer_ms", 0, 1),
        ("Offered load over capacity (\\%)", "offered_over_capacity", 0, 100),
        ("Dropped by the relay (\\%)", "relay_dropped", 1, 100),
    )
    lines = []
    for regime in DROPS:
        if lines:
            lines.append("\\midrule")
        for i, name in enumerate(NAMES):
            own = timeline["phases_by_schedule"][regime][name]
            cells = [_shown(value, digits, scale) for _, key, digits, scale in columns for value in own[key]]
            lines.append(" & ".join(["" if i else regime.capitalize(), name, *cells]) + " \\\\")
    width = len(timeline["phases"])
    head = (
        " & & "
        + " & ".join(f"\\multicolumn{{{width}}}{{c}}{{{title}}}" for title, *_ in columns)
        + " \\\\\n"
        + "Schedule & Arm & "
        + " & ".join(" & ".join(timeline["phases"]) for _ in columns)
        + " \\\\"
    )
    return _tabular("ll" + "r" * (width * len(columns)), head, lines)


def export(report_path, timeline_path, headroom_path, out):
    """Write the macros and tables. Refuses anything that is not the pilot's own report and timeline."""
    paths = Path(report_path), Path(timeline_path), Path(headroom_path)
    report, timeline, headroom = (json.loads(path.read_text()) for path in paths)
    out = Path(out)
    if headroom.get("abi") != RANGE_ABI + "_headroom" or headroom.get("exploratory") is not True:
        raise ValueError("the range pilot's exploratory headroom report is required")
    if report.get("abi") != ABI + "_report" or report.get("development_pilot") is not True:
        raise ValueError("the controller pilot's report is required")
    if report.get("confirmatory") is not False or report.get("learned_controller_promoted") is not False:
        raise ValueError("the pilot confirms and promotes nothing")
    if (
        timeline.get("abi") != ABI + "_timeline"
        or timeline.get("added_after_the_report_was_read") is not True
    ):
        raise ValueError("the pilot's timeline, marked as added after the report was read, is required")
    if (
        timeline.get("plan_sha256") != report.get("plan_sha256")
        or timeline.get("sessions") != report["sessions"]
    ):
        raise ValueError("the timeline is of another capture than the report")
    if tuple(timeline["phases"]) != PHASES or timeline["bin_ms"] != BIN_MS:
        raise ValueError("the timeline has other stretches or phases than the pilot's")
    evidence = macros(report, timeline, headroom)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ladder_pilot_arms.tex").write_text(table_arms(report))
    (out / "ladder_pilot_differences.tex").write_text(table_differences(report))
    (out / "ladder_pilot_timeline.tex").write_text(table_timeline(timeline))
    (out / "ladder_pilot_phases.tex").write_text(table_phases(timeline))
    lines = ["% Generated by `python -m media_rl.native_ladder_pilot_report`; do not edit."]
    lines += [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in evidence.items()]
    (out / "evidence.tex").write_text("\n".join(lines) + "\n")
    provenance = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1, sort_keys=True) + "\n")
    return dict(out=str(out), macros=len(evidence), sessions=report["sessions"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--timeline", required=True, type=Path)
    parser.add_argument("--headroom", required=True, type=Path, help="the range pilot's headroom report")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = export(args.report, args.timeline, args.headroom, args.out)
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
