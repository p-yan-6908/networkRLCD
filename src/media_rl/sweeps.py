"""Aggregate predeclared sensitivity/physical ablation runs without choosing a winner."""

import csv
from pathlib import Path

from .config import load_config
from .experiment import write_csv


def build_sweep_report(root, plots=True):
    root = Path(root)
    rows = []
    for path in sorted(root.glob("*/summary.csv")):
        config = load_config(path.parent / "config.json")
        with path.open() as f:
            for row in csv.DictReader(f):
                if row["scope"] == "domain":
                    rows.append(
                        dict(
                            variant=path.parent.name,
                            threshold=config.gate.threshold,
                            calibration=config.gate.calibration,
                            fec_levels=str(config.simulator.fec_levels),
                            **row,
                        )
                    )
    write_csv(root / "sweep_summary.csv", rows)
    selected = [r for r in rows if r["method"] == "calibrated"]
    index = {(r["variant"], r["group"], r["metric"]): r for r in selected}
    bs = chr(92)
    lines = [
        bs + "begin{tabular}{llrrr}",
        bs + "toprule",
        "Variant & Domain & QoE & Unsafe & Fallback " + bs * 2,
        bs + "midrule",
    ]
    for variant, domain in sorted({(r["variant"], r["group"]) for r in selected}):
        values = [
            index[variant, domain, metric]["mean"] for metric in ["qoe", "violation_rate", "fallback_rate"]
        ]
        lines.append(
            " & ".join([variant.replace("_", bs + "_"), domain.upper()] + [f"{float(v):.3f}" for v in values])
            + " "
            + bs * 2
        )
    lines += [bs + "bottomrule", bs + "end{tabular}", ""]
    (root / "table_sweep.tex").write_text("\n".join(lines))
    if plots and selected:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3, figsize=(10, 3), layout="constrained")
        variants = sorted({r["variant"] for r in selected})
        for ax, metric in zip(axes, ["qoe", "violation_rate", "fallback_rate"]):
            for domain in ["id", "ood"]:
                values = [
                    float(index[v, domain, metric]["mean"]) if (v, domain, metric) in index else float("nan")
                    for v in variants
                ]
                ax.plot(range(len(variants)), values, "o-", label=domain.upper())
            ax.set_xticks(range(len(variants)), variants, rotation=35, ha="right")
            ax.set_ylabel(metric.replace("_", " "))
            ax.legend()
        for extension in ["pdf", "png"]:
            fig.savefig(root / f"sweep.{extension}", dpi=200, bbox_inches="tight")
        plt.close(fig)
