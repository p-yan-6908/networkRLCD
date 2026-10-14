"""Plot preserved outcome-free V13 repeatability, without opening raw outcomes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "reports/native-v13-support-census-summary.json"
OUTPUT = REPO / "reports/native-v13-support-repeatability.png"


def main():
    if OUTPUT.exists():
        raise ValueError("preserve the completed support figure")
    report = json.loads(SOURCE.read_text())
    assert not report["outcomes_opened"] and not report["action_effects_estimated"]
    rows = sorted(report["profiles"].values(), key=lambda p: (p["family"], p["content"], p["profile"]))
    assert len(rows) == 16 and all(p["all_session_qualified_repeats"] == 2 for p in rows)
    labels = []
    for p in rows:
        family = "LTE" if p["family"] == "att_lte_driving_2016" else "EVDO"
        content = "Kampar" if p["content"] == "content_kampar_boating_01" else "Volga"
        direction = p["profile"].split("-")[-2].replace("downlink", "DL").replace("uplink", "UL")
        labels.append(f"{family} / {content} / {direction} {p['profile'].split('-')[-1]}")
    fig, (left, right) = plt.subplots(1, 2, figsize=(10.4, 7.2), gridspec_kw={"width_ratios": [1.4, 1]}, sharey=True)
    ys = np.arange(len(rows))
    for y, p in enumerate(rows):
        values = [500 * 2 ** x for x in p["replicate_x"]]
        color = "#2874a6" if p["family"] == "att_lte_driving_2016" else "#b9770e"
        left.plot(values, [y, y], color=color, linewidth=2, alpha=.65)
        left.scatter(values, [y, y], color=color, s=25, zorder=3)
    left.set_xscale("log", base=2)
    left.set_xticks([250, 500, 1000, 2000, 4000], labels=["250", "500", "1000", "2000", "4000"])
    left.set_xlabel("Native census BWE geometric mean (kbps; log scale)")
    left.set_yticks(ys, labels=labels)
    left.set_ylim(len(rows) - .4, -.6)
    left.grid(axis="x", alpha=.2)
    diffs = [p["repeat_log2_difference"] for p in rows]
    right.barh(ys, diffs, color=["#b03a2e" if d > .25 else "#5d6d7e" for d in diffs], height=.58)
    right.axvline(.25, color="#b03a2e", linestyle="--", linewidth=1.3, label="Frozen 0.25-octave limit")
    right.set_xlim(0, .5)
    right.set_xlabel("Absolute fresh-repeat difference (octaves)")
    right.tick_params(axis="y", left=False, labelleft=False)
    right.grid(axis="x", alpha=.2)
    right.legend(loc="lower right", fontsize=8)
    for ax in (left, right):
        for boundary in (3.5, 7.5, 11.5):
            ax.axhline(boundary, color="#d5d8dc", linewidth=.8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("V13 support only: 32 eligible sessions; 6/16 contexts fail repeatability", fontsize=12)
    fig.text(.5, .015, "Selected repeated contexts in two bundles from one measurement program. No action sessions or outcome estimates.", ha="center", fontsize=8)
    fig.tight_layout(rect=[0, .035, 1, .965])
    fig.savefig(OUTPUT, dpi=180)
    plt.close(fig)
    metadata = {"abi": "native_v13_support_figure_v1", "source": str(SOURCE.relative_to(REPO)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "figure_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "outcomes_read": False, "matplotlib_version": matplotlib.__version__}
    (OUTPUT.with_suffix(".json")).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
