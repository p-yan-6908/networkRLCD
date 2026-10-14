"""Report completed instrumentation variables only; no later BWE contrasts."""
import importlib.util
import json
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("m4r_support_report", REPO / "tools/measure_prefix_instrumentation_m4r.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)


def stats(xs):
    return {"n": len(xs), "minimum": min(xs) if xs else None, "median": st.median(xs) if xs else None, "maximum": max(xs) if xs else None}


def report():
    m.verify()
    overall = m.v.read(m.ROOT / "instrumentation_qualification.json")
    rows = []
    for stage in ("feasibility", "qualification"):
        root = m.ROOT / stage
        p, index = m.v.core.check_capture_integrity(root)
        gate = m.v.read(root / "mechanism_qualification_gate.json")
        assert overall["stage_gate_sha256"][stage] == m.v.sha(root / "mechanism_qualification_gate.json")
        for row in gate["sessions"]:
            result = {"trial": row["trial"], "content_id": row["content_id"], "prefix": row["prefix"], "setup_delay_ms": row["setup_delay_ms"], "qualified": row["passed"], "stage": stage}
            if row["capture_status"] == "sealed":
                directory = root / "sessions" / row["trial"]
                startup = m.v.read(directory / "support_startup.json")
                samples = m.v.read(directory / "startup_samples.json")
                stamps = sorted({x["native_stats_timestamp_ms"] for x in samples if isinstance(x["native_stats_timestamp_ms"], (float, int))})
                advances = [b - a for a, b in zip(stamps, stamps[1:]) if b > a]
                result.update({"full_clock_width_ms": row["clock"]["full"]["max_held_out_width_ms"],
                    "beginning_clock_width_ms": row["clock"]["beginning"]["max_held_out_width_ms"],
                    "full_clock_covered_holdouts": row["clock"]["full"]["covered_count"], "beginning_clock_covered_holdouts": row["clock"]["beginning"]["covered_count"],
                    "legacy_clock_passed_diagnostic": row["clock"]["legacy_diagnostic"]["passed"],
                    "readiness_wait_ms": startup["transport_readiness_wait_ms"], "readiness_probes": startup["transport_readiness_probes"],
                    "initialization_latency_ms": startup["initialization_latency_ms"],
                    "actual_initial_bwe_bps": startup["initial_native_source"]["bwe_bps"], "first_measured_bwe_bps": startup["first_measured_bwe_bps"],
                    "startup_samples": len(samples), "startup_max_poll_gap_ms": row["startup"]["maximum_poll_gap_ms"],
                    "native_timestamp_positive_steps_ms": stats(advances), "missing_bwe_samples_retained": sum(x["bwe_bps"] is None for x in samples),
                    "preactivation_frames_encoded": startup["pre_activation"]["frames_encoded"], "preactivation_payload_bytes": startup["pre_activation"]["bytes_sent"]})
            rows.append(result)
    sealed = [x for x in rows if "full_clock_width_ms" in x]
    figure = REPO / "reports/native-prefix-instrumentation-m4r-qualification.png"
    assert not figure.exists()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    positions = list(range(1, len(sealed) + 1))
    axes[0].scatter(positions, [x["full_clock_width_ms"] for x in sealed], label="Full-session: 7 independent holdouts", s=24)
    axes[0].scatter(positions, [x["beginning_clock_width_ms"] for x in sealed], label="Beginning: 4 independent holdouts", marker="x", s=30)
    axes[0].set(xlabel="Original capture order", ylabel="Maximum clock interval width (ms)", title="Clock bounds; registered limit remains 50 ms")
    axes[0].legend(fontsize=8)
    for delay, color in ((0, "#2369a3"), (750, "#c45d24")):
        subset = [(i, x) for i, x in zip(positions, sealed) if x["setup_delay_ms"] == delay]
        axes[1].scatter([i for i, x in subset], [x["readiness_wait_ms"] for i, x in subset], color=color, label=f"{delay} ms inactive challenge", s=25)
    axes[1].set(xlabel="Original capture order", ylabel="Strict selected-pair readiness wait (ms)", title="Readiness before media activation; limit 2,000 ms")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.15)
    fig.suptitle("M4R instrumentation only: no later BWE effects or state fitting", fontsize=11)
    fig.savefig(figure, dpi=180)
    plt.close(fig)
    result = {"abi": "native_prefix_instrumentation_m4r_reporting_v1", "overall_gate_sha256": m.v.sha(m.ROOT / "instrumentation_qualification.json"),
        "source_tool_sha256": m.v.sha(Path(__file__).resolve()), "figure_sha256": m.v.sha(figure), "planned_originals": 32,
        "qualified_originals": sum(x["qualified"] for x in rows), "passed": overall["passed"], "sessions": rows,
        "summary": {key: stats([x[key] for x in sealed]) for key in ("full_clock_width_ms", "beginning_clock_width_ms", "readiness_wait_ms", "initialization_latency_ms", "startup_max_poll_gap_ms")},
        "legacy_clock_passed_diagnostic": sum(x["legacy_clock_passed_diagnostic"] for x in sealed),
        "native_stats_polling_is_not_assumed_to_equal_native_timestamp_update_frequency": True,
        "later_bwe_distributions_examined": False, "prefix_effects_estimated": False, "predictors_fitted": False, "outcomes_read": False}
    m.v.write(REPO / "reports/native-prefix-instrumentation-m4r-reporting.json", result)
    m.v.write(m.ROOT / "qualification/instrumentation_reporting.json", result)
    return {"passed": result["passed"], "qualified": result["qualified_originals"], "summary": result["summary"], "predictors_fitted": False}


if __name__ == "__main__":
    print(json.dumps(report()))
