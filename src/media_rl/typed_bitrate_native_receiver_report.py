"""Paper evidence for the simulator's receiver layer: macros and three tables from its fit and its test.

Every macro carries ReceiverLayer. The numbers are synthetic, set beside two native development
pilots; nothing here is native evidence and nothing is promoted.
"""

import argparse
import hashlib
import json
from pathlib import Path

from .native_actuator_qualification_report import count, number, signed, span
from .native_ladder_pilot import NAMES as ARMS
from .native_range_pilot_report import _tabular
from .typed_bitrate_native_receiver import LEVELS, PAIRS, SPANS, STUDY

SPAN = SPANS[0]  # the span of the verdict
NUMBERS = (  # macro stem, key of the layer, digits, scale
    ("Start", "e0_bps", 0, 0.001),
    ("Base", "b0", 1, 1),
    ("PerLoad", "gu", 0, 1),
    ("PerQueue", "gq", 2, 1),
    ("Fall", "tau_s", 0, 1),
    ("Return", "return_ms", 0, 1),
)
LABELS = dict(zip(ARMS, ("Ladder", "Fast", "Quarter", "Low", "Top"), strict=True))
FAST = "fast ladder minus ladder"


def macros(fitted, report):
    seen, beside = report["spans"][SPAN], fitted["beside_the_range_pilot"]
    everywhere = seen["differences_over_all_schedules"]
    rows = dict(
        ReceiverLayerVerdict=report["verdict"],
        ReceiverLayerEstablished=count(seen["established_over_all_schedules"]),
        ReceiverLayerAgreeing=count(seen["agreeing_over_all_schedules"]),
        ReceiverLayerLocalEstablished=count(seen["established_under_the_schedules"]),
        ReceiverLayerLocalAgreeing=count(
            round(seen["share_agreeing_under_the_schedules"] * seen["established_under_the_schedules"])
        ),
        ReceiverLayerInside=count(seen["endpoints_inside_the_native_interval"]),
        ReceiverLayerFastSim=signed(everywhere[FAST]["simulated"], 2),
        ReceiverLayerFastNative=signed(everywhere[FAST]["native"], 2),
        ReceiverLayerFastJudged=everywhere[FAST]["verdict"],
        ReceiverLayerInAgree=count(beside["comparisons"]["agrees"]),
        ReceiverLayerInDisagree=count(beside["comparisons"]["disagrees"]),
        ReceiverLayerInUnclear=count(beside["comparisons"]["unclear"]),
        ReceiverLayerInBest=count(beside["schedules_with_the_same_best_level"]),
        ReceiverLayerBufferLeft=number(fitted["stages"]["buffer"]["rms_ms"], 0),
        ReceiverLayerAgeLeft=number(fitted["stages"]["age"]["rms_ms"], 0),
    )
    for stem, key, digits, scale in NUMBERS:
        rows[f"ReceiverLayer{stem}"] = number(scale * fitted["layer"][key], digits)
    for name, label in LABELS.items():
        rows[f"ReceiverLayerSim{label}"] = number(seen["levels"]["utility"][name]["simulated"], 1)
        rows[f"ReceiverLayerNative{label}"] = number(seen["levels"]["utility"][name]["native"], 1)
    held = report["ablations"]["buffer_held_at_its_base"]["differences_over_all_schedules"]
    rows["ReceiverLayerHeldDisagree"] = count(sum(e["verdict"] == "disagrees" for e in held.values()))
    shares = report["robustness"]["share_of_replicates_agreeing"]
    agreeing = [shares[pair] for pair, e in everywhere.items() if e["verdict"] == "agrees" and pair in shares]
    rows["ReceiverLayerRobustMin"] = "n/a" if not agreeing else number(100 * min(agreeing), 0)
    rows["ReceiverLayerRobustFast"] = "n/a" if FAST not in shares else number(100 * shares[FAST], 0)
    rows["ReceiverLayerReplicates"] = count(report["robustness"]["replicates"])
    return rows


def table_levels(fitted):
    """The fitted layer beside the range pilot, on quantities it was not fitted to."""
    levels, lines = fitted["beside_the_range_pilot"]["levels"], []
    for level in LEVELS:
        cells = [
            number(scale * levels[key][level][side], 1)
            for key, scale in (("utility", 1), ("on_time", 100), ("encoder_over_capacity", 100))
            for side in ("simulated", "native")
        ]
        lines.append(" & ".join([level, *cells]) + " \\\\")
    head = (
        " & \\multicolumn{2}{c}{Utility} & \\multicolumn{2}{c}{On time (\\%)}"
        " & \\multicolumn{2}{c}{Rate over capacity (\\%)} \\\\\n"
        "Level & simulated & native & simulated & native & simulated & native \\\\"
    )
    return _tabular("l" + "r" * 6, head, lines)


def table_arms(report):
    """The controller pilot's arms in the simulator and natively, from the second change on."""
    seen, lines = report["spans"][SPAN]["levels"], []
    for name in ARMS:
        own, timely = seen["utility"][name], seen["on_time"][name]
        lines.append(
            " & ".join(
                [
                    name,
                    number(own["simulated"], 1),
                    number(own["native"], 1),
                    "[" + ", ".join(number(v, 1) for v in own["native_interval95"]) + "]",
                    number(100 * timely["simulated"], 1),
                    number(100 * timely["native"], 1),
                ]
            )
            + " \\\\"
        )
    head = (
        " & \\multicolumn{3}{c}{Utility} & \\multicolumn{2}{c}{On time (\\%)} \\\\\n"
        "Arm & simulated & native & native 95\\% interval & simulated & native \\\\"
    )
    return _tabular("lrrlrr", head, lines)


def table_differences(report):
    """The ten differences of the endpoint over all schedules, as the design judges them."""
    everywhere, lines = report["spans"][SPAN]["differences_over_all_schedules"], []
    for a, b in PAIRS:
        e = everywhere[f"{a} minus {b}"]
        native = signed(e["native"], 2) + " " + span(e["native_interval95"], 2)
        lines.append(" & ".join([f"{a} $-$ {b}", signed(e["simulated"], 2), native, e["verdict"]]) + " \\\\")
    return _tabular("lrll", "Difference & Simulated & Native & Judged \\\\", lines)


def export(layer_path, report_path, out):
    """Write the macros and tables. Refuses anything that is not this study's fitted layer and test."""
    layer_path, report_path, out = Path(layer_path), Path(report_path), Path(out)
    fitted, report = json.loads(layer_path.read_text()), json.loads(report_path.read_text())
    if fitted.get("study") != STUDY + "_layer" or report.get("study") != STUDY + "_test":
        raise ValueError("the fitted layer and its test report are required")
    if report.get("synthetic") is not True or report.get("native_evidence") is not False:
        raise ValueError("the test is synthetic and no native evidence")
    if report.get("learned_controller_promoted") is not False:
        raise ValueError("nothing is promoted")
    if report.get("layer_sha256") != hashlib.sha256(layer_path.read_bytes()).hexdigest():
        raise ValueError("the test was run on another layer")
    evidence = macros(fitted, report)
    out.mkdir(parents=True, exist_ok=True)
    (out / "receiver_layer_levels.tex").write_text(table_levels(fitted))
    (out / "receiver_layer_arms.tex").write_text(table_arms(report))
    (out / "receiver_layer_differences.tex").write_text(table_differences(report))
    lines = ["% Generated by `python -m media_rl.typed_bitrate_native_receiver_report`; do not edit."]
    lines += [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in evidence.items()]
    (out / "evidence.tex").write_text("\n".join(lines) + "\n")
    provenance = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (layer_path, report_path)}
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1, sort_keys=True) + "\n")
    return dict(out=str(out), macros=len(evidence), verdict=report["verdict"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--layer", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = export(args.layer, args.report, args.out)
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
