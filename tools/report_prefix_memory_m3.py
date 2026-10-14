"""Render completed M3 support projections without opening raw outcome telemetry.

This descriptive reporting tool is outside the frozen scientific instrumentation.
It uses only the registered gate and summary, preserves their bytes, and never
changes qualification or inferential rules.
"""
from __future__ import annotations

import hashlib
import json
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "reports"
ROOT = Path.home() / ".cache/networkrlcd/native-prefix-memory-m3"
COLORS = {"ascending_prefix": "#2369a3", "descending_prefix": "#c45d24"}
WINDOWS = (18000, 24000, 30000, 36000)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    if path.exists():
        raise ValueError(f"preserve completed reporting artifact: {path}")
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def summarize(values):
    v = [x for x in values if isinstance(x, (float, int))]
    return {"n": len(v), "mean": st.mean(v) if v else None,
            "median": st.median(v) if v else None,
            "min": min(v) if v else None, "max": max(v) if v else None}


def report():
    summary_path = REPORTS / "native-prefix-memory-m3-summary.json"
    gate_path = ROOT / "mechanism_qualification_gate.json"
    protocol_path = REPO / "configs/native_prefix_memory_m3.json"
    summary, gate, protocol = read(summary_path), read(gate_path), read(protocol_path)
    assert summary["gate_sha256"] == sha(gate_path)
    assert summary["protocol_sha256"] == sha(protocol_path) == sha(ROOT / "protocol.json")
    assert summary["capture_index_sha256"] == sha(ROOT / "capture_index.json")
    assert len(gate["sessions"]) == summary["planned_sessions"] == 84
    contents = sorted(summary["contents"])
    paths = []
    fig, ax = plt.subplots(figsize=(10, 3.8), constrained_layout=True)
    for prefix, p in protocol["prefix_profiles"].items():
        ax.step(np.arange(37), p["rates_mbps"] + [p["rates_mbps"][-1]], where="post",
                color=COLORS[prefix], label=prefix.replace("_", " "), lw=1.8,
                linestyle="--" if prefix == "descending_prefix" else "-")
    ax.axvline(10, color="#333", lw=1)
    ax.text(10.35, 2.18, "common original measured suffix", fontsize=9)
    ax.set(xlabel="Nominal replay time (s)", ylabel="Registered service (Mbps)",
           title="M3: equal early sample multiset; common service from 10 s", xlim=(0, 36.6))
    ax.legend(loc="lower right", fontsize=9)
    path = REPORTS / "native-prefix-memory-m3-service.png"
    if path.exists():
        raise ValueError("preserve completed figure")
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(path)

    fig, axes = plt.subplots(2, 4, figsize=(14, 7), constrained_layout=True)
    for ci, content in enumerate(contents):
        name = content.split("_")[1].capitalize()
        for wi, endpoint in enumerate(WINDOWS):
            ax = axes[ci, wi]
            w = summary["contents"][content]["windows"][str(endpoint)]
            ax.set_title(f"{name}, {endpoint // 1000} s", fontsize=11)
            if not w["estimable"]:
                ax.text(.5, .5, "Unqualified\nAll original pairs required", ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
                continue
            for prefix, key in (("ascending_prefix", "ascending_order_statistics"),
                                ("descending_prefix", "descending_order_statistics")):
                ax.step(w[key], np.arange(1, 22) / 21, where="post", color=COLORS[prefix],
                        label=prefix.replace("_", " "), lw=1.8)
            r = w["randomization"]
            ax.text(.03, .05, f"W1={r['observed_w1_octaves']:.3f}\np={r['exact_randomization_p']:.4g}\nconvergence: {'pass' if w['convergence_passed'] else 'fail'}",
                    transform=ax.transAxes, fontsize=9, bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none"})
            ax.set(xlabel="log2(BWE / 500 kbps)", ylabel="Empirical cumulative fraction", ylim=(0, 1.03))
            ax.grid(alpha=.15)
    axes[0, 0].legend(fontsize=8, loc="upper left")
    fig.suptitle("M3 support distributions: 21 randomized pairs per reused content\nLate p-values are formal only when the registered primary and gatekeeping conditions pass", fontsize=11)
    path = REPORTS / "native-prefix-memory-m3-distributions.png"
    if path.exists():
        raise ValueError("preserve completed figure")
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(path)

    diagnostic = {}
    for content in contents:
        rows = [r for r in gate["sessions"] if r["content_id"] == content]
        diagnostic[content] = {"original_sessions": len(rows), "native_qualified": sum(r["passed"] for r in rows),
            "startup_passed": sum(r["startup_passed"] for r in rows), "readback_passed": sum(r["readback_passed"] for r in rows),
            "windows": {str(t): {"qualified_histories": sum(r["passed"] and r["windows"].get(str(t), {}).get("passed", False) for r in rows),
                "qualified_suffix_pairs": sum(gate["pair_suffix_fidelity"][p][str(t)]["passed"] for p in {r["pair_id"] for r in rows}),
                "exposure_error_octaves": summarize(gate["pair_suffix_fidelity"][p][str(t)]["maximum_exposure_log2_difference"] for p in {r["pair_id"] for r in rows})} for t in WINDOWS}}
        arm_queues = {}
        for prefix in COLORS:
            valid = [r["suffix_fidelity"] for r in rows if r["prefix"] == prefix and "suffix_fidelity" in r]
            arm_queues[prefix] = {"actual_run_clock_max_heldout_width_ms": summarize(x["clock_max_heldout_width_ms"] for x in valid),
                "rate_tick_error_ms": summarize(abs(tick["at_ms"] - next(t["at_ms"] for t in x["actual_rate_ticks"] if t["phase"] == tick["phase"] and t["sample_index"] == 0) - 1000 * tick["sample_index"])
                    for x in valid for tick in x["actual_rate_ticks"]),
                "phase_start_error_ms": summarize(abs(x["actual_rate_ticks"][i]["at_ms"] - x["actual_rate_ticks"][0]["at_ms"] - 1000 * i) for x in valid for i in (12, 24)),
                "directions": {direction: {"bytes_at_common_tick": summarize(x["support_queue_history"][direction]["queued_bytes_at_common_tick"] for x in valid),
                    "first_empty_after_common_tick_ms": summarize(x["support_queue_history"][direction]["first_empty_after_common_tick_ms"] for x in valid),
                    "windows": {key: {metric: summarize(x["support_queue_history"][direction]["windows"][key][metric] for x in valid)
                        for metric in ("mean_queue_bytes", "positive_queue_fraction", "mean_pump_gap_ms", "maximum_pump_gap_ms")}
                        for key in ("0_10000", "10000_18000", "18000_24000", "24000_30000", "30000_36000")}}
                    for direction in ("a_to_b", "b_to_a")}}
        diagnostic[content]["arm_queue_descriptions"] = arm_queues
    result = {"abi": "native_prefix_memory_m3_reporting_v1", "summary_sha256": sha(summary_path),
        "gate_sha256": sha(gate_path), "protocol_sha256": sha(protocol_path), "report_tool_sha256": sha(Path(__file__).resolve()),
        "plots": {p.relative_to(REPO).as_posix(): sha(p) for p in paths}, "support_diagnostics": diagnostic,
        "new_inferential_tests": 0, "outcomes_read": False, "controller_fitted": False,
        "queue_statistics_are_causal_mediator_shares": False,
        "source_scope": summary["scope"]}
    path = REPORTS / "native-prefix-memory-m3-reporting.json"
    write(path, result)
    write(ROOT / "support_reporting.json", result)
    return {"report": str(path), "plots": len(paths), "new_inferential_tests": 0, "outcomes_read": False}


if __name__ == "__main__":
    print(json.dumps(report()))
