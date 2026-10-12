"""Read-only reproduction from saved executed-block labels and closed-loop arrays.

No collection, rollout labels, evaluation retuning or output overwrites.
"""

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from media_rl import typed_bitrate_factual as factual
from media_rl import typed_factual_acceptance as audit
from media_rl.native_margin_pilot_report import compare
from media_rl.typed_bitrate import load_config


def verify(report_root):
    report_root = Path(report_root)
    report = json.loads((report_root / "report.json").read_text())
    raw = Path(report["raw_out"])
    for path, expected in report["input_and_code_sha256"].items():
        if audit.sha(path) != expected:
            raise ValueError("changed study input/source: " + path)
    for name, expected in report["raw_sha256"].items():
        if audit.sha(raw / name) != expected:
            raise ValueError("changed factual evidence: " + name)
    config = replace(
        load_config("results/jevbwe-typed-v4-population/config.json"),
        workers=report["source_config"]["workers"],
    )
    settings = report["settings"]
    refits, proofs = [], {}
    for fit in report["fits"]:
        seed, blocks = fit["seed"], fit["blocks"]
        print(json.dumps(dict(stage="refit_factual_only", seed=seed, blocks=blocks)), flush=True)
        with np.load(raw / f"factual-{seed}.npz") as stored:
            if set(stored.files) != {"states", "arms", "outcomes", "episode"}:
                raise ValueError("executed labels only required")
            data = {key: stored[key] for key in stored.files}
        parts = factual.budget(data, blocks, settings["shares"])
        net, norm, scale, info = factual.train(config, parts, "factual", settings, seed)
        selection = audit.select(config, net, norm, scale, parts, settings["margins"], 0.05)
        compare(info, fit["optimizer"], "retrained optimizer")
        compare(selection, fit["selection"], "reproduced selection")
        for method, chosen in selection["selected"].items():
            name = f"model-{blocks}-{seed}-{method}.json"
            model = factual.package(config, norm, net, scale, chosen["margin"], seed)
            compare(model, json.loads((report_root / name).read_text()), "retrained model")
            if not chosen["accepted"]:
                # Bound every packaged score on the actual clipped input domain.
                w, b, v, c = map(np.asarray, model["heads"]["regress"]["weights"])
                upper = np.maximum(0, 12 * np.abs(w).sum(axis=0) + b) @ np.maximum(v, 0) + c
                base = config.ratios.index(config.base_ratio)
                if np.any(v[:, base]) or c[base] != 0 or np.any(np.delete(upper, base) >= 0):
                    raise ValueError("never-act parity unproven")
                proofs[name] = float(np.delete(upper, base).max())
        refits.append(dict(seed=seed, blocks=blocks, selection_and_weights_reproduced=True))
    with np.load(raw / "closed-loop.npz") as cube:
        for row in report["summaries"]:
            panel, method, blocks = row["panel"], row["selector"], row["blocks"]
            seeds = [f["seed"] for f in report["fits"] if f["blocks"] == blocks]
            for endpoint, reference, key in (
                ("utility", "fixed", "utility_vs_fixed"),
                ("utility", "reactive", "utility_vs_reactive"),
                ("unsafe", "fixed", "unsafe_vs_fixed"),
            ):
                own = np.stack([cube[f"{blocks}__{s}__{method}__{panel}__{endpoint}"] for s in seeds])
                gap = own - cube[f"{reference}__{panel}__{endpoint}"]
                compare(audit.paired_summary(gap), row[key], "recomputed closed-loop summary")
                if method != "point" and reference == "fixed" and np.any(gap):
                    raise ValueError("fallback arrays differ from fixed control")
    return dict(
        abi="typed_factual_acceptance_v1_verification",
        added_after_run=True,
        executed_label_files_verified=3,
        factual_refits=refits,
        packaged_models_reproduced=18,
        summaries_recomputed=len(report["summaries"]),
        numeric_compare_relative_tolerance=1e-12,
        numeric_compare_absolute_tolerance=1e-12,
        never_act_global_upper_scores=proofs,
        closed_loop_arrays_replayed=False,
        interpretation="Recomputes saved-array summaries and refits factual models; does not rerun closed-loop traces.",
        archive_verified=False,
        raw_bytes_pruned=False,
        verifier_sha256=audit.sha(__file__),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("fresh verification receipt required")
    receipt = verify(args.report)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(receipt, sort_keys=True))
