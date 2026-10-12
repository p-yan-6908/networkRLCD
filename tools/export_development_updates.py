"""Export compact, verified synthetic acceptance and native observability tables."""

import argparse
import json
from pathlib import Path

import numpy as np

from media_rl.native_margin_pilot_report import compare
from media_rl.native_turn_probe import sha


def write_export(root, inputs, table):
    root = Path(root)
    if root.exists():
        raise ValueError("fresh paper export required")
    root.mkdir()
    (root / "table.tex").write_text(table)
    provenance = dict(
        abi="development_update_paper_export_v1",
        input_sha256={p: sha(p) for p in inputs},
        exporter_sha256=sha(__file__),
        table_sha256=sha(root / "table.tex"),
        no_capture_or_training_launched=True,
    )
    (root / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")


def main(factual_out, native_out):
    factual_root = "reports/typed-factual-acceptance-v1/"
    factual = json.loads(Path(factual_root + "report.json").read_text())
    verification = json.loads(Path(factual_root + "verification.json").read_text())
    if verification["packaged_models_reproduced"] != 18 or verification["summaries_recomputed"] != 18:
        raise ValueError("complete factual reproduction required")
    rows = []
    labels = dict(
        training_families="Training families",
        read_population_r="Read unseen R",
        read_population_s="Read unseen S",
    )
    for row in factual["summaries"]:
        if row["selector"] != "point":
            continue
        mean = row["utility_vs_fixed"]["mean"]
        low, high = row["utility_vs_fixed"]["family_interval95"]
        rows.append(
            f"{row['blocks'] // 1000}k & {labels[row['panel']]} & {mean:+.5f} & "
            f"[{low:+.5f}, {high:+.5f}] & {100 * row['unsafe_vs_fixed']['mean']:+.3f} \\\\\n"
        )
    table = (
        "\\begin{tabular}{llrrr}\n\\toprule\nBlocks & Panel & Utility vs fixed & Family interval & Unsafe pp \\\\\n"
        "\\midrule\n" + "".join(rows) + "\\bottomrule\n\\end{tabular}\n"
    )
    write_export(
        factual_out,
        [
            factual_root + "report.json",
            factual_root + "verification.json",
            "configs/typed_factual_acceptance_v1.json",
        ],
        table,
    )
    native_root = "reports/native-turn-probe-v1/"
    native = json.loads(Path(native_root + "report.json").read_text())
    audit = json.loads(Path(native_root + "independent-audit.json").read_text())
    sessions = json.loads(Path(native_root + "sessions.json").read_text())
    if len(audit["sessions"]) != native["sessions"] or not audit["summaries_recomputed"]:
        raise ValueError("complete native audit required")
    cohorts = [c for s in sessions for c in s["cohorts"]]
    rows = []
    for ratio, level in native["levels"].items():
        own = [c for c in cohorts if c["ratio"] == float(ratio)]
        compare(len(own), level["assigned_holds"], "native counts")
        compare(
            float(np.mean([c["realized_ratio"] for c in own if c["window_complete"]])),
            level["mean_realized_ratio"],
            "native means",
        )
        rows.append(
            f"{ratio} & {level['assigned_holds']} & {level['complete_windows']} & "
            f"{level['aliased_holds']} & {level['mean_realized_ratio']:.3f} \\\\\n"
        )
    table = (
        "\\begin{tabular}{rrrrr}\n\\toprule\nRequested ratio & Assigned & Complete & Aliased & Realised ratio \\\\\n"
        "\\midrule\n" + "".join(rows) + "\\bottomrule\n\\end{tabular}\n"
    )
    write_export(
        native_out,
        [
            native_root + "report.json",
            native_root + "sessions.json",
            native_root + "independent-audit.json",
            "configs/native_turn_probe_v1.json",
        ],
        table,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factual-out", type=Path, default=Path("paper/generated-typed-factual-acceptance"))
    parser.add_argument("--native-out", type=Path, default=Path("paper/generated-native-turn-probe"))
    args = parser.parse_args()
    main(args.factual_out, args.native_out)
