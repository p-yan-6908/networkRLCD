"""Regenerate every table/figure from saved evidence (headless, no TeX required)."""

import csv
import gzip
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from .config import load_config
from .experiment import write_csv
from .metrics import calibration_metrics, cluster_interval, reliability, risk_coverage

PRIMARY = ["qoe", "latency_p95_ms", "residual_loss", "violation_rate", "fallback_rate", "ece"]


def read_episodes(path):
    with Path(path).open() as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key, value in row.items():
            if key not in {"scenario", "domain", "method"}:
                row[key] = float(value) if value else None
    return rows


def summaries(episodes, samples):
    keys = [k for k in episodes[0] if k not in {"model_seed", "test_seed", "scenario", "domain", "method"}]
    grouped = defaultdict(lambda: defaultdict(list))
    for r in episodes:
        for scope, group in [("domain", r["domain"]), ("scenario", r["scenario"])]:
            for metric in keys:
                if r[metric] is not None:
                    grouped[scope, group, r["method"], metric][r["model_seed"]].append(r[metric])
    result = []
    for (scope, group, method, metric), seed_values in sorted(grouped.items()):
        interval = cluster_interval([np.mean(v) for v in seed_values.values()], samples)
        result.append(dict(scope=scope, group=group, method=method, metric=metric, **interval))
    return result


def paired_comparisons(episodes, samples):
    index = {(r["model_seed"], r["test_seed"], r["scenario"], r["method"]): r for r in episodes}
    grouped = defaultdict(lambda: defaultdict(list))
    for r in episodes:
        if r["method"] == "calibrated":
            continue
        other = index.get((r["model_seed"], r["test_seed"], r["scenario"], "calibrated"))
        if other is None:
            continue
        for metric in PRIMARY:
            if r[metric] is not None and other[metric] is not None:
                grouped[r["domain"], r["method"], metric][r["model_seed"]].append(other[metric] - r[metric])
    return [
        dict(
            domain=d,
            reference=m,
            contrast="calibrated-minus-reference",
            metric=k,
            **cluster_interval([np.mean(v) for v in groups.values()], samples),
        )
        for (d, m, k), groups in sorted(grouped.items())
    ]


def write_table(path, summary, methods):
    index = {(r["scope"], r["group"], r["method"], r["metric"]): r for r in summary}
    bs = chr(92)
    lines = [
        "% Auto-generated. Mean [95% seed-cluster bootstrap CI]; -- = unavailable.",
        bs + "begin{tabular}{llrrrrrr}",
        bs + "toprule",
        "Domain & Method & QoE $" + bs + "uparrow$ & p95 ms & Loss & Unsafe & Fallback & ECE " + bs * 2,
        bs + "midrule",
    ]
    for domain in ["id", "ood"]:
        for method in methods:
            cells = []
            for metric in PRIMARY:
                r = index.get(("domain", domain, method, metric))
                if r is None or r["mean"] is None:
                    cells.append("--")
                else:
                    value = f"{r['mean']:.3f}"
                    if r["low"] is not None:
                        value += f" [{r['low']:.3f}, {r['high']:.3f}]"
                    cells.append(value)
            lines.append(" & ".join([domain.upper(), method.replace("_", bs + "_")] + cells) + " " + bs * 2)
        lines.append(bs + "midrule")
    lines[-1] = bs + "bottomrule"
    lines += [bs + "end{tabular}", ""]
    path.write_text("\n".join(lines))


def stream_diagnostics(out, config):
    probability = defaultdict(lambda: dict(p=[], raw=[], y=[], support=[]))
    trajectory = defaultdict(list)
    with gzip.open(out / "steps.csv.gz", "rt") as f:
        for row in csv.DictReader(f):
            if row["confidence"] and row.get("proposal_label_censored", "0") != "1":
                d = probability[row["domain"], row["method"]]
                d["p"].append(float(row["confidence"]))
                d["raw"].append(float(row["raw_confidence"]))
                d["y"].append(float(row["proposal_safe"]))
                d["support"].append(float(row["support_score"]) if row["support_score"] else 0)
            if (
                int(row["model_seed"]) == config.seeds[0]
                and int(row["test_seed"]) == config.test_seeds[0]
                and row["method"] in {"safe", "gcc", "rl", "calibrated"}
            ):
                trajectory[row["scenario"], row["method"]].append(row)
    bins, curves, diagnostics = [], [], []
    for (domain, method), data in sorted(probability.items()):
        for kind, key in [("reported", "p"), ("raw", "raw")]:
            bins.extend(
                dict(domain=domain, method=method, kind=kind, **r) for r in reliability(data[key], data["y"])
            )
            diagnostics.append(
                dict(
                    domain=domain,
                    method=method,
                    kind=kind,
                    count=len(data[key]),
                    **calibration_metrics(data[key], data["y"]),
                )
            )
        curves.extend(dict(domain=domain, method=method, **r) for r in risk_coverage(data["p"], data["y"]))
    write_csv(out / "reliability.csv", bins)
    write_csv(out / "risk_coverage.csv", curves)
    write_csv(out / "calibration_diagnostics.csv", diagnostics)
    detection = []
    for method in config.methods:
        a, b = probability.get(("id", method)), probability.get(("ood", method))
        if a and b:
            x, y = a["support"], b["support"]
            ranks = rankdata(x + y)
            auc = (ranks[len(x) :].sum() - len(y) * (len(y) + 1) / 2) / (len(x) * len(y))
            detection.append(
                dict(method=method, support_ood_auroc=float(auc), id_samples=len(x), ood_samples=len(y))
            )
    write_csv(out / "ood_detection.csv", detection)
    return bins, curves, trajectory


def make_plots(out, summary, bins, curves, trajectories, config):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.bbox": "tight",
            "svg.hashsalt": "media-rl",
        }
    )
    dest = out / "figures"
    dest.mkdir(exist_ok=True)

    def save(fig, name):
        for suffix in ["pdf", "png"]:
            kwargs = {"metadata": {"CreationDate": None, "ModDate": None}} if suffix == "pdf" else {}
            fig.savefig(dest / f"{name}.{suffix}", dpi=200, **kwargs)
        plt.close(fig)

    idx = {(r["scope"], r["group"], r["method"], r["metric"]): r for r in summary}
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5), layout="constrained")
    for ax, domain in zip(axes, ["id", "ood"]):
        for method in config.methods:
            x = idx.get(("domain", domain, method, "violation_rate"))
            y = idx.get(("domain", domain, method, "qoe"))
            if x and y:
                xe = (
                    [[max(0, x["mean"] - x["low"])], [max(0, x["high"] - x["mean"])]]
                    if x["low"] is not None
                    else None
                )
                ye = (
                    [[max(0, y["mean"] - y["low"])], [max(0, y["high"] - y["mean"])]]
                    if y["low"] is not None
                    else None
                )
                ax.errorbar(x["mean"], y["mean"], xerr=xe, yerr=ye, fmt="o", capsize=2, label=method)
        ax.set(title=domain.upper(), xlabel="Safety violation fraction ↓", ylabel="Mean QoE ↑")
        ax.grid(alpha=0.2)
    axes[-1].legend(fontsize=7, loc="best")
    save(fig, "qoe_safety_tradeoff")
    fig, axes = plt.subplots(1, 2, figsize=(7, 3), layout="constrained")
    for ax, domain in zip(axes, ["id", "ood"]):
        ax.plot([0, 1], [0, 1], "k--", lw=0.8)
        for kind in ["raw", "reported"]:
            rows = [
                r
                for r in bins
                if r["domain"] == domain and r["method"] == "calibrated" and r["kind"] == kind and r["count"]
            ]
            ax.plot([r["confidence"] for r in rows], [r["frequency"] for r in rows], "o-", label=kind)
        ax.set(
            title=domain.upper(),
            xlabel="Proposed-action safety probability",
            ylabel="Empirical safe fraction",
            xlim=(0, 1),
            ylim=(0, 1),
        )
        if ax.get_legend_handles_labels()[0]:
            ax.legend()
    save(fig, "reliability")
    fig, ax = plt.subplots(figsize=(4, 3), layout="constrained")
    for domain in ["id", "ood"]:
        for method in ["calibrated", "uncalibrated"]:
            rows = [
                r for r in curves if r["domain"] == domain and r["method"] == method and r["risk"] is not None
            ]
            if rows:
                ax.plot(
                    [r["coverage"] for r in rows], [r["risk"] for r in rows], ".-", label=f"{domain} {method}"
                )
    ax.set(xlabel="Proposal coverage", ylabel="Proposal safety violation risk", xlim=(0, 1), ylim=(0, 1))
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=7)
    save(fig, "risk_coverage")
    for scenario in config.scenarios:
        fig, axes = plt.subplots(3, 1, figsize=(6.5, 5), sharex=True, layout="constrained")
        for method in ["safe", "gcc", "rl", "calibrated"]:
            rows = trajectories.get((scenario, method), [])
            if not rows:
                continue
            x = [float(r["time_s"]) for r in rows]
            axes[0].plot(x, [float(r["bitrate_mbps"]) for r in rows], label=method, lw=1)
            axes[1].plot(x, [float(r["latency_ms"]) for r in rows], lw=1)
            if method == "calibrated":
                axes[0].plot(
                    x, [float(r["capacity_mbps"]) for r in rows], "k--", label="capacity (offline)", lw=0.8
                )
                axes[2].plot(x, [float(r["confidence"]) for r in rows], label="confidence")
                axes[2].fill_between(
                    x, 0, [int(r["fallback"] == "True") for r in rows], alpha=0.2, label="fallback"
                )
        axes[0].set(ylabel="Mbps", title=f"{scenario}: first predeclared seed/trace")
        if axes[0].get_legend_handles_labels()[0]:
            axes[0].legend(ncol=3, fontsize=7)
        axes[1].axhline(config.simulator.safe_latency_ms, color="k", ls=":", lw=0.8)
        axes[1].set(ylabel="Latency (ms)")
        axes[2].axhline(config.gate.threshold, color="k", ls=":", lw=0.8)
        axes[2].set(xlabel="Time (s)", ylabel="Probability / gate", ylim=(0, 1.05))
        if axes[2].get_legend_handles_labels()[0]:
            axes[2].legend(fontsize=7)
        save(fig, f"trajectory_{scenario}")
    matrix = np.array(
        [[idx["scenario", s, m, "violation_rate"]["mean"] for s in config.scenarios] for m in config.methods]
    )
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    im = ax.imshow(matrix, aspect="auto", vmin=0, vmax=1, cmap="magma_r")
    ax.set_xticks(range(len(config.scenarios)), config.scenarios, rotation=40, ha="right")
    ax.set_yticks(range(len(config.methods)), config.methods)
    fig.colorbar(im, ax=ax, label="Safety violation fraction")
    save(fig, "robustness_heatmap")
    logs = sorted(out.glob("training_*.csv"))
    if logs:
        fig, ax = plt.subplots(figsize=(5, 3), layout="constrained")
        for path in logs:
            with path.open() as f:
                rows = list(csv.DictReader(f))
            ax.plot(
                [int(r["episode"]) for r in rows],
                [float(r["mean_qoe"]) for r in rows],
                alpha=0.7,
                label=path.stem,
            )
        ax.set(xlabel="Training episode (exploratory policy)", ylabel="Mean QoE")
        ax.legend(fontsize=7)
        save(fig, "learning_curves")


def build_report(out, plots=True):
    out = Path(out)
    config = load_config(out / "config.json")
    episodes = read_episodes(out / "episodes.csv")
    if not episodes:
        raise ValueError("no evaluation episodes")
    summary = summaries(episodes, config.bootstrap_samples)
    paired = paired_comparisons(episodes, config.bootstrap_samples)
    write_csv(out / "summary.csv", summary)
    write_csv(out / "paired_differences.csv", paired)
    write_table(out / "table_main.tex", summary, config.methods)
    bins, curves, trajectories = stream_diagnostics(out, config)
    idx = {(r["scope"], r["group"], r["method"], r["metric"]): r["mean"] for r in summary}
    robustness = []
    for method in config.methods:
        id_qoe, ood_qoe = idx.get(("domain", "id", method, "qoe")), idx.get(("domain", "ood", method, "qoe"))
        robustness.append(
            dict(
                method=method,
                id_qoe=id_qoe,
                ood_qoe=ood_qoe,
                ood_minus_id_qoe=ood_qoe - id_qoe if id_qoe is not None and ood_qoe is not None else None,
                worst_scenario_qoe=min(idx["scenario", s, method, "qoe"] for s in config.scenarios),
            )
        )
    write_csv(out / "robustness.csv", robustness)
    if plots:
        make_plots(out, summary, bins, curves, trajectories, config)
    lines = [
        f"# {config.name}",
        "",
        f"{len(episodes)} episodes; {len(config.seeds)} training seeds; {len(config.test_seeds)} held-out trace seeds per scenario.",
        "",
        "All results are synthetic. A completed pipeline is not evidence that the proposed method wins.",
        "Intervals resample training-seed means and are conditional on this fixed test-trace panel. Baselines are deterministic on that panel; their between-training-seed intervals can be degenerate. One-seed runs have no interval. Fewer than ten training seeds should be treated as pilot evidence.",
        "",
        "Calibration tables score proposed actions using evaluation-only counterfactual labels on each method's own visited states; fallback outcomes are NOT substituted as labels. Reliability and risk-coverage curves are pooled descriptive diagnostics, not independent-time-step inference. Risk-coverage curves do not simulate the hysteretic gate.",
        "",
        "Latency is a virtual fluid completion-delay proxy (including stalled intervals), not measured packet latency. Per-episode p95 is averaged across episodes, not pooled. Blank metrics mean undefined (e.g., zero accepted actions). Recovery is conditional on observed recoveries; inspect censor counts. See docs/methodology.md for definitions.",
        "",
        "## Main comparison (means; intervals in table_main.tex)",
        "| Domain | Method | QoE | p95 ms | Unsafe | Fallback | ECE |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for domain in ["id", "ood"]:
        for method in config.methods:
            vals = [
                idx.get(("domain", domain, method, k))
                for k in ["qoe", "latency_p95_ms", "violation_rate", "fallback_rate", "ece"]
            ]
            lines.append(
                "| "
                + " | ".join([domain, method] + [f"{v:.4f}" if v is not None else "—" for v in vals])
                + " |"
            )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")
    return summary
