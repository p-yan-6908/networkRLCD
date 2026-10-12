"""Synthetic development audit of clustered acceptance for factual bitrate learning.

Training sees executed randomized block outcomes only. This changes the acting
margin selector, not the original trainer, simulator, action semantics or native
controller. Previously read family panels are development evidence only.
"""

import argparse
import hashlib
import json
import math
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.stats import t

from . import typed_bitrate_baselines as baselines
from . import typed_bitrate_factual as factual
from .typed_bitrate import load_config, split_seed
from .typed_bitrate_experiment import run_many
from .typed_bitrate_population import names

ABI = "typed_factual_acceptance_v1"
METHODS = ("point", "episode_lcb", "family_lcb")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dr_gap(value, arms, outcomes, chosen, base):
    """One DR policy-minus-base contribution per uniformly randomized block."""
    value = np.asarray(value, dtype=float)
    arms, chosen = np.asarray(arms, dtype=int), np.asarray(chosen, dtype=int)
    outcomes = np.asarray(outcomes, dtype=float)
    if value.ndim != 2 or len(value) != len(arms) or len(chosen) != len(arms) or len(outcomes) != len(arms):
        raise ValueError("matched factual rows required")
    options = value.shape[1]
    if np.any((arms < 0) | (arms >= options)) or np.any((chosen < 0) | (chosen >= options)):
        raise ValueError("unknown factual option")
    if not np.isfinite(value).all() or not np.isfinite(outcomes).all():
        raise ValueError("finite factual predictions/outcomes required")
    rows = np.arange(len(arms))
    residual = outcomes - value[rows, arms]
    return (
        value[rows, chosen]
        - value[:, base]
        + options * ((arms == chosen) - (arms == base).astype(int)) * residual
    )


def lower_bound(scores, clusters, alpha, comparisons):
    """Approximate one-sided cluster-robust t bound with fixed multiplicity correction."""
    scores, clusters = np.asarray(scores, dtype=float), np.asarray(clusters)
    if not len(scores) or len(scores) != len(clusters) or not np.isfinite(scores).all():
        raise ValueError("matched finite scores and clusters required")
    groups, inverse = np.unique(clusters, return_inverse=True)
    if len(groups) < 2:
        raise ValueError("at least two independent clusters required")
    mean = float(scores.mean())
    sums = np.bincount(inverse, weights=scores - mean)
    se = math.sqrt(len(groups) / (len(groups) - 1) * float(sums @ sums)) / len(scores)
    critical = float(t.ppf(1 - alpha / comparisons, len(groups) - 1))
    return dict(
        mean=mean, standard_error=se, clusters=len(groups), lower=mean - critical * se, critical=critical
    )


def select(config, net, norm, scale, parts, margins, alpha):
    held = parts[2]
    mean, spread, _ = norm
    x = (held["states"] - mean.astype(np.float32)) / spread.astype(np.float32)
    output = net(np.clip(x, -12, 12))
    base = config.ratios.index(config.base_ratio)
    centre = float(parts[0]["outcomes"].mean())
    value = output * scale + centre
    advantage = (output - output[:, [base]]) * scale
    curve = []
    for margin in margins:
        chosen = factual.choose(advantage, base, margin)
        scores = dr_gap(value, held["arms"], held["outcomes"], chosen, base)
        curve.append(
            dict(
                margin=margin,
                estimated_gain=float(scores.mean()),
                override_share=float(np.mean(chosen != base)),
                episode=lower_bound(scores, held["episode"], alpha, len(margins)),
                family=lower_bound(
                    scores, held["episode"] % len(config.train_scenarios), alpha, len(margins)
                ),
            )
        )
    selected = {}
    for method in METHODS:
        key = (
            (lambda c: c["estimated_gain"])
            if method == "point"
            else (lambda c: c[method.split("_")[0]]["lower"])
        )
        best = max(curve, key=key)
        selected[method] = dict(
            margin=best["margin"] if key(best) > 0 else factual.NEVER,
            accepted=key(best) > 0,
            selection_score=key(best),
            estimated_gain=best["estimated_gain"],
        )
    return dict(curve=curve, selected=selected)


def paired_summary(values):
    """Family-level descriptive t interval, conditional on the fitted models."""
    values = np.asarray(values, dtype=float)
    family = values.mean(axis=(0, 2))
    half = float(t.ppf(0.975, len(family) - 1) * family.std(ddof=1) / math.sqrt(len(family)))
    return dict(
        mean=float(family.mean()),
        family_interval95=[float(family.mean() - half), float(family.mean() + half)],
        families=len(family),
        positive_families=int(np.sum(family > 0)),
        means_by_model_seed=values.mean(axis=(1, 2)).tolist(),
    )


def panel_tasks(config, families, trace_seeds, namespace, policy):
    return [
        (family, split_seed(config.seed, namespace, family, seed), policy)
        for family in families
        for seed in trace_seeds
    ]


def evaluate(config, bundle, families, spec, trace_seeds, namespace):
    rows = run_many(config, bundle, panel_tasks(config, families, trace_seeds, namespace, spec))
    shape = len(families), len(trace_seeds)
    return {key: np.array([row[key] for row in rows]).reshape(shape) for key in ("utility", "unsafe")}


def run(spec_path, raw_out, report_out):
    started = time.monotonic()
    spec_path, raw_out, report_out = Path(spec_path), Path(raw_out), Path(report_out)
    if raw_out.exists() or report_out.exists():
        raise ValueError("fresh raw and compact-report directories required")
    if raw_out.resolve().is_relative_to(Path.cwd().resolve()):
        raise ValueError("raw factual logs belong outside the repository")
    spec = json.loads(spec_path.read_text())
    if (
        spec.get("abi") != ABI + "_spec"
        or spec.get("synthetic_only") is not True
        or spec.get("native_validation") is not False
    ):
        raise ValueError("the synthetic development spec is required")
    for role in ("source_config", "baseline_report"):
        if sha(spec[role]["path"]) != spec[role]["sha256"]:
            raise ValueError("changed pinned " + role)
    config = replace(load_config(spec["source_config"]["path"]), workers=spec["workers"])
    if config.train_scenarios != names("d") or config.base_ratio is None:
        raise ValueError("the population-pool config with training-selected base is required")
    settings = factual.load_settings()
    if settings["margins"] != spec["margins"] or tuple(spec["selection_methods"]) != METHODS:
        raise ValueError("the fixed margin grid and selectors must match")
    tuned = json.loads(Path(spec["baseline_report"]["path"]).read_text())["tuning"]["selected"]["rule_best"][
        "spec"
    ]
    panels = dict(training_families=names("d"), read_population_r=names("r"), read_population_s=names("s"))
    raw_out.mkdir(parents=True)
    report_out.mkdir(parents=True)
    fixed, reactive, saved = {}, {}, {}
    for name, families in panels.items():
        print(json.dumps(dict(stage="baselines", panel=name)), flush=True)
        fixed[name] = evaluate(
            config,
            None,
            families,
            dict(kind="fixed", ratio=config.base_ratio),
            spec["evaluation_trace_seeds"],
            spec["trace_namespace"],
        )
        rows = baselines.run_rules(
            config,
            panel_tasks(config, families, spec["evaluation_trace_seeds"], spec["trace_namespace"], tuned),
        )
        reactive[name] = {
            key: np.array([r[key] for r in rows]).reshape(len(families), -1) for key in ("utility", "unsafe")
        }
        for key in ("utility", "unsafe"):
            saved[f"fixed__{name}__{key}"] = fixed[name][key]
            saved[f"reactive__{name}__{key}"] = reactive[name][key]
    fits, results = [], {}
    for data_seed in spec["data_seeds"]:
        print(
            json.dumps(dict(stage="collect_factual_only", seed=data_seed, blocks=max(spec["blocks"]))),
            flush=True,
        )
        data = factual.collect(
            config, data_seed, max(spec["blocks"]), settings["block_probability"], truth_blocks=0
        )
        if not np.isnan(data["values"]).all():
            raise ValueError("counterfactual labels must not be collected")
        np.savez_compressed(
            raw_out / f"factual-{data_seed}.npz", **{k: v for k, v in data.items() if k != "values"}
        )
        for blocks in spec["blocks"]:
            print(json.dumps(dict(stage="fit_and_select", seed=data_seed, blocks=blocks)), flush=True)
            parts = factual.budget(data, blocks, settings["shares"])
            ids = [set(p["episode"]) for p in parts]
            if any(ids[i] & ids[j] for i in range(3) for j in range(i)):
                raise ValueError("episode leakage between fit/early-stop/selection")
            net, norm, scale, info = factual.train(config, parts, "factual", settings, data_seed)
            selection = select(config, net, norm, scale, parts, spec["margins"], spec["familywise_alpha"])
            if selection["selected"]["point"]["margin"] != info["margin"]:
                raise ValueError("point selector failed to reproduce original helper")
            fit = dict(
                seed=data_seed,
                blocks=blocks,
                optimizer=info,
                selection=selection,
                rows=[len(p["arms"]) for p in parts],
            )
            for method, chosen in selection["selected"].items():
                bundle = factual.package(config, norm, net, scale, chosen["margin"], data_seed)
                model_path = report_out / f"model-{blocks}-{data_seed}-{method}.json"
                model_path.write_text(json.dumps(bundle, sort_keys=True, allow_nan=False) + "\n")
                for name, families in panels.items():
                    if chosen["margin"] == factual.NEVER:
                        # Execute a sample to prove never-act parity; reuse the remaining fixed outcomes.
                        own = evaluate(
                            config,
                            bundle,
                            families[:1],
                            factual.SPEC,
                            spec["evaluation_trace_seeds"],
                            spec["trace_namespace"],
                        )
                        if any(not np.array_equal(own[key], fixed[name][key][:1]) for key in own):
                            raise ValueError("never-act head failed exact fixed parity")
                        own = fixed[name]
                    else:
                        own = evaluate(
                            config,
                            bundle,
                            families,
                            factual.SPEC,
                            spec["evaluation_trace_seeds"],
                            spec["trace_namespace"],
                        )
                    results.setdefault((blocks, method, name), []).append(own)
                    for key, value in own.items():
                        saved[f"{blocks}__{data_seed}__{method}__{name}__{key}"] = value
            fits.append(fit)
            print(
                json.dumps(
                    dict(
                        stage="selected",
                        seed=data_seed,
                        blocks=blocks,
                        margins={m: v["margin"] for m, v in selection["selected"].items()},
                    )
                ),
                flush=True,
            )
    summaries = []
    for (blocks, method, name), rows in results.items():
        cube = {key: np.stack([r[key] for r in rows]) for key in ("utility", "unsafe")}
        summaries.append(
            dict(
                blocks=blocks,
                selector=method,
                panel=name,
                utility_vs_fixed=paired_summary(cube["utility"] - fixed[name]["utility"]),
                utility_vs_reactive=paired_summary(cube["utility"] - reactive[name]["utility"]),
                unsafe_vs_fixed=paired_summary(cube["unsafe"] - fixed[name]["unsafe"]),
            )
        )
    np.savez_compressed(raw_out / "closed-loop.npz", **saved)
    provenance = {
        str(p): sha(p)
        for p in [
            spec_path,
            Path(spec["source_config"]["path"]),
            Path(spec["baseline_report"]["path"]),
            Path(__file__),
            Path(factual.__file__),
            Path(baselines.__file__),
        ]
    }
    report = dict(
        abi=ABI,
        synthetic_only=True,
        development_only=True,
        native_validation=False,
        controller_promoted=False,
        counterfactual_labels_collected=False,
        closed_loop_hindsight_disabled=True,
        fits=fits,
        summaries=summaries,
        tuned_reactive_spec=tuned,
        settings=settings,
        source_config=config.to_dict(),
        input_and_code_sha256=provenance,
        elapsed_s=time.monotonic() - started,
        raw_out=str(raw_out),
        raw_sha256={p.name: sha(p) for p in raw_out.iterdir()},
        limitations=[
            "Previously read family definitions; development evidence only.",
            "Conditional approximate cluster bounds do not guarantee closed-loop or native value.",
            "Five-second randomized block estimand differs from continuous state occupancy and actuation.",
            "Family intervals condition on three fitted seeds; per-seed means are also reported.",
        ],
    )
    (report_out / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    return dict(out=str(report_out), elapsed_s=report["elapsed_s"], summaries=summaries)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--raw-out", required=True, type=Path)
    parser.add_argument("--report-out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.spec, args.raw_out, args.report_out)
    except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
