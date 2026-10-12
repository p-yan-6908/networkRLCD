"""Plot the first registered native peer; no outcome-based example selection."""

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from media_rl.native_turn_probe import sha, validate_peer


def export(capture, output):
    capture, output = Path(capture), Path(output)
    if output.exists():
        raise ValueError("fresh figure directory required")
    trial = json.loads((capture / "spec.json").read_text())["trials"][0]
    root = capture / trial["id"]
    peer, assignments = validate_peer(root, trial)
    rows, events = peer["decisions"], peer["encoded_meter"]["events"]
    sample = np.array([r["observation"]["sample_ms"] for r in rows])
    at = np.array([e["at_ms"] for e in events])
    payload = np.r_[0, np.cumsum([e["byte_length"] for e in events])]
    now = np.searchsorted(at, sample, side="right")
    before = np.searchsorted(at, sample - 1000, side="right")
    actual = (payload[now] - payload[before]) * 8 / 1e6
    actual[sample - peer["measurement_start_ms"] < 1000] = np.nan
    bwe = np.array([r["observation"]["raw_source"]["bwe_bps"] for r in rows]) / 1e6
    cap = np.array([r["observation"]["raw_source"]["encoder_cap_bps"] for r in rows]) / 1e6
    target = (
        np.array(
            [
                r["encoder_response"]["fields"]["targetBitrate"]["value"]
                if r["encoder_response"]["fields"]["targetBitrate"]["status"] == "present"
                else np.nan
                for r in rows
            ]
        )
        / 1e6
    )
    time = (sample - peer["measurement_start_ms"]) / 1000
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.8), sharex=True, constrained_layout=True)
    axes[0].plot(time, bwe, label="Observed BWE", color="#136f63")
    axes[0].step(time, cap, where="post", label="Observed encoder cap", color="#344da0")
    axes[1].plot(time, target, label="Native encoder target", color="#8053a6", linestyle="--")
    axes[1].plot(time, actual, label="Encoded payload, trailing 1 s", color="#ca6a23")
    for axis in axes:
        axis.set_ylabel("Mbit/s")
        axis.set_ylim(bottom=0)
        axis.grid(alpha=0.18)
        axis.legend(frameon=False, loc="upper left", fontsize=8)
        for assignment in assignments:
            axis.axvline(
                (assignment["ack_ms"] - peer["measurement_start_ms"]) / 1000,
                color="black",
                alpha=0.14,
                linewidth=0.7,
            )
    axes[1].set_xlabel("Seconds since measurement start")
    axes[0].set_title("First registered peer: procedural scene 102, steady 4 Mbit/s, TURN/TCP", fontsize=10)
    output.mkdir(parents=True)
    for extension in ("png", "pdf"):
        fig.savefig(output / ("trajectory." + extension), dpi=200)
    plt.close(fig)
    receipt = dict(
        abi="native_turn_probe_v1_trajectory",
        added_after_capture=True,
        example_selection="first registered trial, independent of outcomes",
        trial=trial,
        manifest_sha256=sha(root / "manifest.json"),
        source_sha256=sha(__file__),
        actual_rate="causal trailing 1000 ms pre-RTP payload; first incomplete second omitted",
        model_fitted=False,
        controller_gain_claim=False,
        files_sha256={p.name: sha(p) for p in output.iterdir()},
    )
    (output / "provenance.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    export(args.capture, args.out)
