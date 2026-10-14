"""Standalone plot of registered M2 support states; never reads outcomes."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "reports/native-bwe-mechanisms-m2-summary.json"
OUTPUT = REPO / "reports/native-bwe-mechanisms-m2-repeatability.png"


def main():
    if OUTPUT.exists():
        raise ValueError("preserve completed support figure")
    s = json.loads(SOURCE.read_text())
    g = json.loads((Path.home() / ".cache/networkrlcd/native-bwe-mechanisms-m2/mechanism_qualification_gate.json").read_text())
    assert not s["outcomes_read"] and s["prospective_replication_candidate_initial_kbps"] is None
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), sharey=True)
    for ax, content, title in zip(axes, ("content_kampar_boating_01", "content_volga_lock_01"), ("Kampar boating", "Volga lock"), strict=True):
        for x, (history, initial) in enumerate([(h, i) for h in ("measured_original", "hybrid_flat_prefix") for i in (300, 1200)]):
            key = f"{content}::{history}::initial{initial}"
            c = s["contexts"][key]
            rows = sorted([r for r in g["sessions"] if r["mechanism_context"] == key], key=lambda r: r["repetition"])
            color = "#1d8348" if c["repeatability_passed"] else "#b03a2e"
            if c["full_spread_octaves"] is not None:
                ax.plot([x, x], [min(c["replicate_x"]), max(c["replicate_x"])], color=color, linewidth=2)
            for offset, value, row in zip((-.09, -.03, .03, .09), c["replicate_x"], rows, strict=True):
                if value is not None:
                    ax.scatter(x + offset, value, color=color if row["passed"] else "#566573", marker="o" if row["passed"] else "x", s=35)
            text = f"spread {c['full_spread_octaves']:.3f}" if c["full_spread_octaves"] is not None else "unqualified\n3/4 startup checks"
            ax.text(x, 1.83, text, ha="center", fontsize=8, color=color)
        ax.set_xticks(range(4), ["Measured\nstart 300", "Measured\nstart 1200", "Flat prefix\nstart 300", "Flat prefix\nstart 1200"])
        ax.set_title(title)
        ax.set_ylim(.85, 1.96)
        ax.grid(axis="y", alpha=.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Native census log2(BWE / 500 kbps), octaves")
    fig.suptitle("M2 support only: no initialization qualifies both measured-content contexts")
    fig.text(.5, .02, "Four original attempts per context. Green: full spread ≤0.25 octaves and all gates pass. Red: failure. ×: failed initialization readback.\nFlat prefixes are hybrid synthetic development; every subsequent measured rate is unchanged. No bitrate treatments or QoE analysis.", ha="center", fontsize=8)
    fig.tight_layout(rect=[0, .075, 1, .94])
    fig.savefig(OUTPUT, dpi=180)
    plt.close(fig)
    receipt = {"source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "figure_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "outcomes_read": False}
    OUTPUT.with_suffix(".figure.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
