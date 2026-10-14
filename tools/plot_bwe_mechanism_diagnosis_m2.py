"""Plot the frozen expanded support diagnosis; no raw outcome access."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "reports/native-bwe-mechanisms-m2-diagnosis.json"
OUTPUT = REPO / "reports/native-bwe-mechanisms-m2-diagnosis.png"


def main():
    if OUTPUT.exists():
        raise ValueError("preserve the completed diagnosis figure")
    data = json.loads(SOURCE.read_text())
    assert not data["outcomes_read"]
    pairs = data["v13_repeat_pairs"]
    fig, (history, queue) = plt.subplots(1, 2, figsize=(11.6, 5), gridspec_kw={"width_ratios": [1.45, 1]})
    for p in pairs:
        failed = not p["repeatability_passed"]
        label = None
        if failed:
            content = "Kampar" if "kampar" in p["content"] else "Volga"
            family = "LTE" if p["family"].startswith("att") else "EVDO"
            profile = p["profile"].split("-")[-2:]
            label = f"{content} {family} {'DL' if profile[0]=='downlink' else 'UL'} {profile[1]}"
        history.plot([i + .5 for i in range(18)], p["per_second_delta_x"], color="#b03a2e" if failed else "#85929e",
            alpha=.8 if failed else .35, linewidth=1.5 if failed else .8, label=label)
        queue.scatter(p["deltas"]["transport_queue.queue_12_18s_bytes"] / 1000, p["delta_x"],
            color="#b03a2e" if failed else "#5d6d7e", s=35 if failed else 25)
    for ax in (history, queue):
        ax.axhline(0, color="#566573", linewidth=.7)
        ax.grid(alpha=.16)
        ax.spines[["top", "right"]].set_visible(False)
    history.axhline(.25, color="#566573", linestyle="--", linewidth=.8)
    history.axhline(-.25, color="#566573", linestyle="--", linewidth=.8)
    history.set_xlabel("Elapsed measurement time (seconds)")
    history.set_ylabel("Repeat 1 − repeat 0 BWE difference (octaves)")
    history.set_title("Divergence builds during measured conditioning", fontsize=11)
    history.legend(fontsize=7, loc="lower left", ncol=2)
    history.set_xlim(0, 18)
    queue.set_xlabel("Repeat difference in 12–18 s mean queue (kB)")
    queue.set_ylabel("Support-window BWE repeat difference (octaves)")
    queue.set_title("Late queue/BWE association: r = 0.763", fontsize=11)
    fig.suptitle("V13 outcome-free mechanism diagnosis", fontsize=13)
    fig.text(.5, .015, "Red: six failed terminal repeatability contexts. Gray: ten passing contexts. Dashed lines: frozen terminal 0.25-octave reference.\nOne-second curves are descriptive; qualification uses the original 18-second window. Queue association does not identify causal direction.", ha="center", fontsize=8)
    fig.tight_layout(rect=[0, .065, 1, .95])
    fig.savefig(OUTPUT, dpi=180)
    plt.close(fig)
    receipt = {"source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "figure_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "outcomes_read": False}
    OUTPUT.with_suffix(".figure.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
