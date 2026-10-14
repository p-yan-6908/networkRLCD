"""Render registered M6R support results; no new tests, fits or membership rules."""
import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("m6r_report_dependencies", REPO / "tools/measure_history_state_m6r.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)


def report():
    m.verify_validation()
    m.v.core.check_capture_integrity(m.CAPTURE_ROOT)
    summary_path = m.CAPTURE_ROOT / "history_state_summary.json"
    result, selection = m.v.read(summary_path), m.v.read(m.SELECTION)
    selected = selection["selected"]
    candidates = selection["development_candidates"]
    names = list(m.h.CANDIDATES)
    labels = ["BWE only", "+ BWE trend", "+ send rate", "+ RTT drift", "+ RTT level", "+ encode time", "+ FPS",
              "+ relay forward", "+ relay queue", "+ relay drop", "+ trend, send", "+ trend, RTT", "+ trend, queue", "+ forward, queue"]
    colors = ["#7356a6" if n == selected else "#6f7c86" if n == "b0_instantaneous" else "#347ca3" for n in names]
    fig, axes = plt.subplots(1, 3, figsize=(16, 6.2), constrained_layout=True)
    for ax, field, title in zip(axes,
            ("coverage_cells", "worst_future_spread", "mean_future_w1_for_development_selection_only"),
            ("Development coverage strata (six required)", "Worst future within-arm full spread", "Development selection mean W1")):
        ax.barh(np.arange(len(names)), [candidates[n][field] for n in names], color=colors)
        ax.set_yticks(np.arange(len(names)), labels, fontsize=8)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=10)
        ax.grid(axis="x", alpha=.15)
    axes[0].axvline(6, color="black", linestyle="--", lw=.8)
    axes[1].axvline(.25, color="black", linestyle="--", lw=.8)
    axes[0].set_xlim(0, 6.5)
    axes[1].set_xlabel("BWE octaves; fixed repeatability margin 0.25")
    axes[2].set_xlabel("BWE octaves; reused M5 selection score")
    fig.suptitle("M6R development only: selected encode-history state matches BWE-only membership\nPurple is the frozen candidate; reduced coverage cannot be hidden by smaller distances", fontsize=11)
    paths = []
    path = REPO / "reports/native-history-state-m6r-development.png"
    assert not path.exists(); fig.savefig(path, dpi=180); plt.close(fig); paths.append(path)

    diagnostics = {}
    if result["acquisition_gate_passed"]:
        membership = result["membership"]
        cells = list(membership["cells"])
        fig, ax = plt.subplots(figsize=(12, 4.8), constrained_layout=True)
        styles = [("b0_instantaneous", "ascending_prefix", "#aeb7c0", "BWE-only ascending"),
                  ("b0_instantaneous", "descending_prefix", "#657582", "BWE-only descending"),
                  (selected, "ascending_prefix", "#2369a3", "History ascending"),
                  (selected, "descending_prefix", "#c45d24", "History descending")]
        x = np.arange(len(cells))
        for i, (name, prefix, color, label) in enumerate(styles):
            values = [membership["cells"][k][name]["counts_by_prefix"][prefix] for k in cells]
            bars = ax.bar(x + (i - 1.5) * .18, values, width=.18, color=color, label=label)
            ax.bar_label(bars, fontsize=8, padding=1)
        ax.axhline(4, color="black", linestyle="--", lw=1, label="Required four of eight originals")
        ax.set_xticks(x, [k.split("_")[1].capitalize() + " " + str(int(k.rsplit("__", 1)[1]) // 1000) + " s" for k in cells])
        ax.set(ylim=(0, 9.4), ylabel="Matched original sessions per prefix", title=f"Fresh M6R: frozen membership gate {'passed' if membership['passed'] else 'failed'}; retention requirement also remains 80%")
        ax.legend(fontsize=8, loc="upper center", ncol=3)
        ax.grid(axis="y", alpha=.15)
        path = REPO / "reports/native-history-state-m6r-membership.png"
        assert not path.exists(); fig.savefig(path, dpi=180); plt.close(fig); paths.append(path)
        rows = m.v.read(m.CAPTURE_ROOT / "precutoff_support_features.json")
        for key, items in m.h.grouped(rows).items():
            basecenter = selection["centers"]["b0_instantaneous"][key]
            center = selection["centers"][selected][key]
            diagnostics[key] = {}
            for prefix in m.h.PREFIXES:
                arm = [q for q in items if q["prefix"] == prefix]
                baseline = [q for q in arm if m.h.near(q, basecenter, ["x"])]
                diagnostics[key][prefix] = {
                    "originals": len(arm), "baseline_matches": len(baseline),
                    "selected_field_missing_counts": {k: sum(q["features"][k] is None for q in arm) for k in selection["features"]},
                    "extra_caliper_rejections_among_baseline": {k: sum(q["features"][k] is None or abs(q["features"][k] - center[k]) > m.h.CALIPERS[k] + 1e-12 for q in baseline) for k in selection["features"] if k != "x"},
                    "selected_past_feature_ranges": {k: [min(values), max(values)] if values else None for k in selection["features"]
                                                     for values in [[q["features"][k] for q in arm if q["features"][k] is not None]]}}
        if result["support_matching_future_responses_estimable"]:
            fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
            for i, name in enumerate(("b0_instantaneous", selected)):
                values = result["state_results"][name]["cells"]
                axes[0].plot(x, [values[k]["w1"] for k in cells], "o-", label=name)
                axes[1].plot(x, [max(values[k]["ascending_full_spread"], values[k]["descending_full_spread"]) for k in cells], "o-", label=name)
            for ax, title in zip(axes, ("Future cross-prefix W1", "Worst future within-prefix full spread")):
                ax.set_xticks(x, [k.split("_")[1][0].upper() + " " + str(int(k.rsplit("__", 1)[1]) // 1000) for k in cells])
                ax.set(title=title, ylabel="BWE octaves", xlabel="Content/current cutoff (future is six seconds later)")
                ax.axhline(.25, color="gray", linestyle="--"); ax.legend(fontsize=8); ax.grid(alpha=.15)
            path = REPO / "reports/native-history-state-m6r-future-support.png"
            assert not path.exists(); fig.savefig(path, dpi=180); plt.close(fig); paths.append(path)
        max_sequential = max(q["relay_clock_boundary_width_ms"] for q in rows)
        training_counts = sorted({q["causal_clock"]["training"] for q in rows})
        held_counts = sorted({q["causal_clock"]["held_out"] for q in rows})
    else:
        max_sequential, training_counts, held_counts = None, [], []
    gate = m.v.read(m.CAPTURE_ROOT / "history_state_acquisition_gate.json")
    sealed = [q for q in gate["sessions"] if q["capture_status"] == "sealed"]
    output = {"abi": "native_history_state_m6r_reporting_v1", "summary_sha256": m.v.sha(summary_path),
              "selection_sha256": m.v.sha(m.SELECTION), "tool_sha256": m.v.sha(Path(__file__).resolve()),
              "plots": {p.relative_to(REPO).as_posix(): m.v.sha(p) for p in paths},
              "clock_full_max_width_ms": max(q["clock"]["full"]["max_held_out_width_ms"] for q in sealed),
              "clock_beginning_max_width_ms": max(q["clock"]["beginning"]["max_held_out_width_ms"] for q in sealed),
              "past_only_sequential_clock_boundary_max_width_ms": max_sequential,
              "past_only_training_counts": training_counts, "past_only_held_counts": held_counts,
              "precutoff_diagnostics": diagnostics, "conditional_future_bwe_estimated": result["support_matching_future_responses_estimable"],
              "controller_fitted": False, "new_inferential_tests": 0, "delivery_qoe_action_outcomes_read": False}
    m.v.write(REPO / "reports/native-history-state-m6r-reporting.json", output)
    m.v.write(m.CAPTURE_ROOT / "support_reporting.json", output)
    return {"plots": len(paths), "past_only_clock_max_boundary_ms": max_sequential,
            "conditional_future_bwe_estimated": result["support_matching_future_responses_estimable"]}


if __name__ == "__main__":
    import json
    print(json.dumps(report()))
