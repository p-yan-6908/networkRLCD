"""Render only PO1's registered metrics; no raw features, labels or new models."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "reports/partial-observability-po1-result.json"


def main():
    result = json.loads(REPORT.read_text())
    families = result["families"]
    labels = [f["family"].replace("_", "\n") for f in families]
    positions = np.arange(len(families))
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    colors = ["#88939c", "#247c9c", "#b34e23"]

    def bars(axis, values, names):
        width = .23
        for j, (v, name) in enumerate(zip(values, names, strict=True)):
            axis.bar(positions + (j-1)*width, v, width, label=name, color=colors[j])
        axis.set_xticks(positions, labels)
        axis.grid(axis="y", alpha=.2)
        axis.set_axisbelow(True)

    persistence = [f["comparisons"]["factual_bwe"]["persistence"]["baseline_mae"] for f in families]
    summary_bwe = [f["metrics"]["summary_linear"]["mae"][0] for f in families]
    history_bwe = [f["metrics"]["history_linear"]["mae"][0] for f in families]
    bars(axes[0, 0], [persistence, summary_bwe, history_bwe], ["Persistence", "S1: fixed summaries", "H1: ordered history"])
    axes[0, 0].set(title="Factual BWE prediction error — synthetic only", ylabel="MAE (octaves; lower is better)")
    axes[0, 0].legend(fontsize=8)
    bars(axes[0, 1], [[f["metrics"][m]["mae"][1] for f in families] for m in ["constant", "summary_linear", "history_linear"]],
         ["Constant advantage", "S1", "H1"])
    axes[0, 1].set(title="Counterfactual advantage error — simulator only", ylabel="MAE (utility units; lower is better)")
    axes[0, 1].legend(fontsize=8)

    for j, (name, color) in enumerate(zip(["BWE", "Advantage"], [colors[1], colors[2]], strict=True)):
        values = [f["metrics"]["history_linear"]["sequence_coverage"][j] for f in families]
        axes[1, 0].bar(positions + (j-.5)*.3, values, .3, label=name, color=color)
    axes[1, 0].axhline(.8, color="black", linestyle="--", label="Registered minimum")
    axes[1, 0].set_xticks(positions, labels)
    axes[1, 0].set(title="H1 full-sequence interval coverage", ylabel="Fraction of episodes", ylim=(0, 1.08))
    axes[1, 0].legend(fontsize=8, loc="lower right")
    widths = [f["metrics"]["history_linear"]["replications"][str(rep)]["interval_width"] for f in families[:1] for rep in range(3)]
    axes[1, 1].bar(np.arange(3)-.15, [v[0] for v in widths], .3, color=colors[1], label="BWE (octaves)")
    axes[1, 1].bar(np.arange(3)+.15, [v[1] for v in widths], .3, color=colors[2], label="Advantage (utility units)")
    axes[1, 1].axhline(1, color=colors[1], linestyle="--", label="BWE maximum 1.0")
    axes[1, 1].axhline(.5, color=colors[2], linestyle="--", label="Advantage maximum 0.5")
    axes[1, 1].set_xticks(np.arange(3), ["Fit 0", "Fit 1", "Fit 2"])
    axes[1, 1].set(title="H1 interval widths fail the usefulness gates", ylabel="Full width (separate target units)")
    axes[1, 1].legend(fontsize=8)
    bars(axes[2, 0], [[f["metrics"]["history_linear"]["binary"][h]["ece"] for f in families] for h in range(3)],
         ["Future BWE drop", "Beneficial advantage", "Unsafe candidate"])
    axes[2, 0].axhline(.1, color="black", linestyle="--")
    axes[2, 0].set(title="H1 calibration error", ylabel="Five-bin ECE; maximum 0.10")
    axes[2, 0].legend(fontsize=8)
    axes[2, 1].axis("off")
    axes[2, 1].text(.03, .9,
        "PO1: STOP\n\n816 independent synthetic episodes; 3 fits\n72 validation episodes per held-out family\n\n0 supported action assertions in every family\n64 reserved native sessions remain untouched\nNo native action-value claim or controller\n\nCalibration across families is empirical.\nCoverage alone cannot rescue unusably wide intervals.\nFeedback-flap has 0 positive unsafe labels;\nthat cannot establish risk sensitivity.", va="top", fontsize=12)
    fig.suptitle("PO1 — ordered history fails beyond strong fixed-history baselines", fontsize=15)
    path = REPO / "reports/figures/partial-observability-po1.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), "preserve rendered evidence"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print(json.dumps({"figure": str(path), "registered_metrics_only": True, "new_model_or_state_search": False}))


if __name__ == "__main__":
    main()
