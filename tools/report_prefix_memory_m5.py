"""Render frozen M5 results and actual-run qualification; no new fitting/tests."""
import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("m5_report_dependencies", REPO / "tools/measure_prefix_memory_m5.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)


def report():
    m.verify()
    m.v.core.check_capture_integrity(m.ROOT)
    summary_path = REPO / "reports/native-prefix-memory-m5-summary.json"
    result = m.v.read(summary_path)
    gate_path = m.ROOT / "prefix_memory_qualification_gate.json"
    gate = m.v.read(gate_path)
    assert result["gate_sha256"] == m.v.sha(gate_path)
    assert result["protocol_sha256"] == m.v.sha(m.CONFIG)
    contents = sorted(result["contents"])
    paths = []
    colors = {"ascending": "#2369a3", "descending": "#c45d24"}
    fig, axes = plt.subplots(2, 4, figsize=(14, 7), constrained_layout=True)
    for ci, content in enumerate(contents):
        name = content.split("_")[1].capitalize()
        all_values = [x for w in result["contents"][content]["windows"].values() if w["estimable"] for key in ("ascending_x", "descending_x") for x in w[key]]
        limits = (min(all_values) - .03, max(all_values) + .03) if all_values else None
        for wi, endpoint in enumerate(m.ENDPOINTS):
            ax = axes[ci, wi]
            w = result["contents"][content]["windows"][str(endpoint)]
            ax.set_title(f"{name}, {endpoint // 1000} s")
            if not w["estimable"]:
                ax.text(.5, .5, "Unestimable\nFull original panel required", ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
                continue
            for prefix in ("ascending", "descending"):
                ax.step(w[prefix + "_order_statistics"], np.arange(1, 22) / 21, where="post", label=prefix + " prefix", color=colors[prefix], lw=1.8)
            ax.text(.03, .05, f"W1={w['randomization']['observed_w1_octaves']:.3f}\np={w['randomization']['exact_randomization_p']:.4g}\nfull convergence: {'pass' if w['convergence_passed'] else 'fail'}",
                    transform=ax.transAxes, fontsize=9, bbox={"facecolor": "white", "alpha": .85, "edgecolor": "none"})
            ax.set(xlabel="log2(BWE / 500 kbps)", ylabel="Empirical cumulative fraction", xlim=limits, ylim=(0, 1.03))
            ax.grid(alpha=.15)
    if result["full_gate_passed"]:
        axes[0, 0].legend(fontsize=8, loc="upper left")
    fig.suptitle("M5: 21 fresh randomized pairs per reused content\nLate p-values require the registered primary/Holm gates for formal persistence", fontsize=11)
    path = REPO / "reports/native-prefix-memory-m5-distributions.png"
    assert not path.exists()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(path)

    if result["full_gate_passed"]:
        fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
        for ci, content in enumerate(contents):
            color, name = ("#2369a3", "#c45d24")[ci], content.split("_")[1].capitalize()
            for endpoint in m.ENDPOINTS:
                w = result["contents"][content]["windows"][str(endpoint)]
                x = endpoint / 1000 + (-.15 if ci == 0 else .15)
                lo, hi = w["uncertainty"]["paired_mean_95pct"]
                axes[0].vlines(x, lo, hi, color=color)
                axes[0].scatter(x, w["paired_mean_octaves"], color=color, label=name if endpoint == 18000 else None)
                lo, hi = w["uncertainty"]["w1_95pct"]
                axes[1].vlines(x, lo, hi, color=color)
                axes[1].scatter(x, w["randomization"]["observed_w1_octaves"], color=color, label=name if endpoint == 18000 else None)
        axes[0].axhline(0, color="gray", lw=.7)
        for value in (-.25, .25):
            axes[0].axhline(value, color="gray", linestyle="--", lw=.8)
        axes[1].axhline(.25, color="gray", linestyle="--", lw=.8)
        axes[0].set(title="Signed paired difference and 95% pair bootstrap", ylabel="Descending minus ascending (BWE octaves)")
        axes[1].set(title="W1 and 95% pair bootstrap", ylabel="Distribution distance (BWE octaves)")
        for ax in axes:
            ax.set_xlabel("Measurement time (s)")
            ax.set_xticks([18, 24, 30, 36])
            ax.legend(fontsize=9)
            ax.grid(alpha=.15)
        fig.suptitle("Dashed lines are registered distance margins; full convergence also requires repeatability", fontsize=10)
        path = REPO / "reports/native-prefix-memory-m5-uncertainty.png"
        assert not path.exists()
        fig.savefig(path, dpi=180)
        plt.close(fig)
        paths.append(path)

    sealed = [r for r in gate["sessions"] if r["capture_status"] == "sealed"]
    figure, axes = plt.subplots(figsize=(11, 3.6), constrained_layout=True)
    ids = np.arange(1, len(sealed) + 1)
    axes.scatter(ids, [r["clock"]["full"]["max_held_out_width_ms"] for r in sealed], s=15, label="Full-session certificate")
    axes.scatter(ids, [r["clock"]["beginning"]["max_held_out_width_ms"] for r in sealed], s=20, marker="x", label="Beginning certificate")
    axes.set(xlabel="Original capture order", ylabel="Maximum clock interval width (ms)", title="M5 actual-run clock bounds; original acceptance limit remains 50 ms")
    axes.legend(fontsize=9)
    axes.grid(alpha=.15)
    path = REPO / "reports/native-prefix-memory-m5-clocks.png"
    assert not path.exists()
    figure.savefig(path, dpi=180)
    plt.close(figure)
    paths.append(path)
    elapsed = {}
    if result["full_gate_passed"]:
        for content in contents:
            elapsed[content] = {}
            rows = [r for r in gate["sessions"] if r["content_id"] == content]
            for endpoint in m.ENDPOINTS:
                times = [r["windows"][str(endpoint)]["history_ms"][-1] for r in rows]
                pair_times = {}
                for r in rows:
                    pair_times.setdefault(r["pair_id"], []).append(r["windows"][str(endpoint)]["history_ms"][-1])
                elapsed[content][str(endpoint)] = {"history_end_elapsed_ms_range": [min(times), max(times)], "maximum_pair_history_end_difference_ms": max(max(v) - min(v) for v in pair_times.values())}
    counts = {}
    for row in gate["sessions"]:
        key = row["content_id"] + "__" + row["prefix"]
        counts.setdefault(key, {"original_attempts": 0, "sealed": 0, "qualified": 0})
        counts[key]["original_attempts"] += 1
        counts[key]["sealed"] += row["capture_status"] == "sealed"
        counts[key]["qualified"] += row["passed"]
    exposure_errors = [w["maximum_exposure_log2_difference"] for pair in gate["pair_suffix_fidelity"].values()
                       for w in pair.values() if w["maximum_exposure_log2_difference"] is not None]
    output = {"abi": "native_prefix_memory_m5_reporting_v1", "summary_sha256": m.v.sha(summary_path), "gate_sha256": m.v.sha(gate_path),
        "tool_sha256": m.v.sha(Path(__file__).resolve()), "plots": {p.relative_to(REPO).as_posix(): m.v.sha(p) for p in paths},
        "actual_clock_full_max_width_ms": max(r["clock"]["full"]["max_held_out_width_ms"] for r in sealed),
        "actual_clock_beginning_max_width_ms": max(r["clock"]["beginning"]["max_held_out_width_ms"] for r in sealed),
        "counts_by_content_prefix": counts,
        "actual_native_initial_bwe_bps_unique": sorted({r["startup"]["native_initial_bwe_bps"] for r in sealed}),
        "actual_first_measured_bwe_bps_unique": sorted({r["startup"]["first_measured_bwe_bps"] for r in sealed}),
        "actual_maximum_startup_poll_gap_ms": max(r["startup"]["maximum_poll_gap_ms"] for r in sealed),
        "maximum_registered_vertex_suffix_exposure_difference_octaves": max(exposure_errors, default=None),
        "all_endpoint_fidelity_pairs_passed": sum(all(w["passed"] for w in pair.values()) for pair in gate["pair_suffix_fidelity"].values()),
        "history_timing_descriptions": elapsed, "new_inferential_tests": 0, "predictors_fitted": False, "controller_state_redesigned": False,
        "delivery_qoe_action_outcomes_read": False, "prefix_test_or_convergence_gate_changed": False}
    m.v.write(REPO / "reports/native-prefix-memory-m5-reporting.json", output)
    m.v.write(m.ROOT / "support_reporting.json", output)
    return {"plots": len(paths), "clock_full_max_ms": output["actual_clock_full_max_width_ms"], "clock_beginning_max_ms": output["actual_clock_beginning_max_width_ms"], "new_inferential_tests": 0}


if __name__ == "__main__":
    print(json.dumps(report()))
