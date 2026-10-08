"""Typed JevBWE study: tune the base, aggregate rollout labels, fit, calibrate, evaluate.

Every fitting step uses in-distribution families only. Held-out families appear
only in the test split, which nothing is tuned on. All evidence is synthetic.
"""

import argparse
import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.special import softmax

from .typed_bitrate import (
    ABI,
    HEADS,
    Features,
    Governor,
    Link,
    TypedModel,
    TypedPolicy,
    choice_labels,
    fit_choice,
    fit_regression,
    fit_temperature,
    load_config,
    payoff_table,
    reliability,
    rollout_values,
    select_threshold,
    split_seed,
    step,
)

LEGACY_FALLBACK = 0.85  # the untuned V1 fallback, kept as a named reference
SPLITS = ("validation", "development", "test")
REASONS = ("base_answer", "ungated", "stale_telemetry", "unsupported_history", "low_confidence", "accepted")
OUTCOMES = ("utility", "unsafe", "deadline_miss", "latency_p95_ms", "rate_mbps")
LEARNED = {
    "choice_rlcd_bayes": ("choice_rlcd", "bayes"),
    "choice_rlcd_gated": ("choice_rlcd", "gated"),
    "choice_rlcd_map": ("choice_rlcd", "map"),
    "choice_analytic_bayes": ("choice_analytic", "bayes"),
    "regress_greedy": ("regress", "greedy"),
}
_WORKER = {}


def run_episode(config, model, scenario, seed, spec, label=None):
    """One closed-loop episode. ``label`` adds hindsight rollouts at each decision epoch:
    "data" keeps the causal state for fitting, "score" keeps only what evaluation needs."""
    link, rules = Link(config, scenario, seed), Governor(config)
    kind = spec["kind"]
    policy = TypedPolicy(model, spec["head"], spec["rule"], config) if kind == "typed" else None
    history = Features(config) if policy is None and label == "data" else None
    rng = np.random.default_rng(spec.get("seed", 0))
    ratio = spec.get("ratio", config.base_ratio)
    totals = dict(utility=[], unsafe=[], deadline_miss=[], latency_ms=[], rate_bps=[])
    decisions, reasons = [], Counter()
    for t in range(config.steps):
        sample = link.sample()
        decide = t % config.decision_steps == 0
        info = state = None
        if policy is not None:
            ratio, info = policy.observe(sample, decide)
        elif history is not None:
            state = history.observe(sample)
        if decide:
            values = None
            if (label or kind == "oracle") and t + config.horizon_steps <= config.steps:
                values, risk = rollout_values(link, rules, sample, config)
            if kind == "oracle":
                best = config.ratios[int(choice_labels(values, config))] if values else config.base_ratio
                ratio = best
            elif kind == "explore":
                ratio = config.base_ratio
            if kind in ("explore", "typed") and rng.random() < spec.get("explore", 0.0):
                ratio = config.ratios[int(rng.integers(len(config.ratios)))]
                if policy is not None:
                    policy.ratio = ratio  # hold the exploratory option until the next decision
            if info is not None:
                reasons[info["reason"]] += 1
            if values is not None and label:
                row = dict(values=values, unsafe=risk, executed=config.ratios.index(ratio), step=t)
                if label == "data":
                    row["state"] = info["state"] if info is not None else state
                if info is not None:
                    row.update({k: info[k] for k in ("scores", "proposal", "reason", "fresh", "supported")})
                decisions.append(row)
        utility, outcome = step(link, rules, sample, ratio, config)
        totals["utility"].append(utility)
        totals["unsafe"].append(1 - outcome["safe"])
        totals["deadline_miss"].append(outcome["deadline_miss"])
        totals["latency_ms"].append(outcome["latency_ms"])
        totals["rate_bps"].append(link.actual_bps)
    return dict(
        scenario=scenario,
        seed=seed,
        utility=float(np.mean(totals["utility"])),
        unsafe=float(np.mean(totals["unsafe"])),
        deadline_miss=float(np.mean(totals["deadline_miss"])),
        latency_p95_ms=float(np.quantile(totals["latency_ms"], 0.95)),
        rate_mbps=float(np.mean(totals["rate_bps"]) / 1e6),
        reasons=dict(reasons),
        decisions=decisions,
    )


def _init(config, bundle):
    _WORKER.update(config=config, model=TypedModel(bundle) if bundle else None)


def _episode(task):
    return run_episode(_WORKER["config"], _WORKER["model"], *task)


def run_many(config, bundle, tasks):
    if config.workers == 1 or len(tasks) < 4:
        model = TypedModel(bundle) if bundle else None
        return [run_episode(config, model, *task) for task in tasks]
    with ProcessPoolExecutor(config.workers, initializer=_init, initargs=(config, bundle)) as pool:
        return list(pool.map(_episode, tasks, chunksize=4))


def tune_base(config):
    """Best fixed ratio on training-family tune traces: the base policy, fallback and bar to beat."""
    if config.base_ratio is not None:
        return config, dict(selected=config.base_ratio, source="configured", sweep=[])
    families = config.train_scenarios
    traces = [
        (families[i % len(families)], split_seed(config.seed, "tune", i)) for i in range(config.tune_episodes)
    ]
    sweep = []
    for ratio in config.ratios:
        rows = run_many(config, None, [(s, seed, dict(kind="fixed", ratio=ratio)) for s, seed in traces])
        sweep.append(
            dict(
                ratio=ratio,
                utility=float(np.mean([r["utility"] for r in rows])),
                unsafe=float(np.mean([r["unsafe"] for r in rows])),
            )
        )
    selected = max(sweep, key=lambda row: row["utility"])["ratio"]
    return replace(config, base_ratio=selected), dict(selected=selected, source="id_tune_split", sweep=sweep)


def stack(episodes):
    rows = [d for e in episodes for d in e["decisions"]]
    states = np.asarray([d["state"] for d in rows], dtype=float)
    values = np.asarray([d["values"] for d in rows], dtype=float)
    return states, values


def fit_heads(config, states, values, model_seed, heads=HEADS):
    mean, scale = states.mean(axis=0), np.maximum(states.std(axis=0), 0.05)
    raw = (states - mean) / scale
    x = np.clip(raw, -12, 12)
    base = config.ratios.index(config.base_ratio)
    labels = choice_labels(values, config)
    advantage = values - values[:, [base]]
    target_scale = float(max(advantage.std(), 0.05))
    seed = split_seed(config.seed, "optimizer", model_seed)
    fitted = {}
    for head in heads:
        if head == "regress":
            net = fit_regression(x, advantage / target_scale, config, seed)
            fitted[head] = dict(weights=net.to_dict(), target_scale=target_scale, threshold=0.0)
        else:
            net = fit_choice(x, labels, config, seed, estimator=head.removeprefix("choice_"))
            fitted[head] = dict(
                weights=net.to_dict(),
                temperature=1.0,
                threshold=0.0,
                payoff=payoff_table(advantage, labels).tolist(),
            )
    return dict(
        abi=ABI,
        ratios=list(config.ratios),
        base_ratio=config.base_ratio,
        mean=mean.tolist(),
        scale=scale.tolist(),
        support_limit=float(np.quantile(np.sqrt(np.mean(raw * raw, axis=1)), config.support_quantile)),
        heads=fitted,
        synthetic_only=True,
    )


def calibrate(config, bundle, model_seed):
    """Fresh training-family episodes run by each head: temperature, acting threshold, payoff table."""
    base, families = config.ratios.index(config.base_ratio), config.train_scenarios
    traces = [
        (families[i % len(families)], split_seed(config.seed, "calibration", model_seed, i))
        for i in range(config.calibration_episodes)
    ]
    report = {}
    for head, spec in bundle["heads"].items():
        rule = "greedy" if head == "regress" else "bayes"  # the states the deployed rule visits
        tasks = [(s, seed, dict(kind="typed", head=head, rule=rule), "data") for s, seed in traces]
        states, values = stack(run_many(config, bundle, tasks))
        if head == "regress":
            report[head] = dict(rows=len(values))
            continue
        labels = choice_labels(values, config)
        x = np.clip((states - bundle["mean"]) / np.asarray(bundle["scale"]), -12, 12)
        output = TypedModel(bundle).heads[head](x)
        before = reliability(softmax(output, axis=1), labels)
        spec["temperature"] = fit_temperature(output, labels)
        scores = softmax(output / spec["temperature"], axis=1)
        proposal = scores.argmax(axis=1)
        rows = np.arange(len(labels))
        advantage = values - values[:, [base]]
        spec["threshold"], curve = select_threshold(
            scores[rows, proposal], advantage[rows, proposal], proposal != base, config.thresholds
        )
        spec["payoff"] = payoff_table(advantage, labels).tolist()
        report[head] = dict(
            rows=len(labels),
            temperature=spec["temperature"],
            raw=before,
            scaled=reliability(scores, labels),
            threshold=spec["threshold"],
            threshold_curve=curve,
            label_rows=[int(np.sum(labels == b)) for b in range(len(config.ratios))],
        )
    return report


def train_seed(config, model_seed, out=None):
    """Dataset aggregation: later rounds label the states the learned policy itself visits."""
    states, values, bundle, rounds = [], [], None, []
    for r in range(config.rounds):
        behaviour = (
            dict(kind="explore", explore=0.5)
            if bundle is None
            else dict(kind="typed", head="choice_rlcd", rule="bayes", explore=config.explore)
        )
        tasks = [
            (
                config.train_scenarios[i % len(config.train_scenarios)],
                split_seed(config.seed, "train", model_seed, r, i),
                dict(behaviour, seed=split_seed(config.seed, "behaviour", model_seed, r, i)),
                "data",
            )
            for i in range(config.train_episodes)
        ]
        s, v = stack(run_many(config, bundle, tasks))
        states.append(s)
        values.append(v)
        last = r == config.rounds - 1
        bundle = fit_heads(
            config,
            np.concatenate(states),
            np.concatenate(values),
            model_seed,
            heads=HEADS if last else ("choice_rlcd",),
        )
        labels = choice_labels(v, config)
        rounds.append(
            dict(
                round=r,
                rows=len(s),
                label_share=[float(np.mean(labels == a)) for a in range(len(config.ratios))],
                mean_best_advantage=float(
                    np.mean(v.max(axis=1) - v[:, config.ratios.index(config.base_ratio)])
                ),
            )
        )
    calibration = calibrate(config, bundle, model_seed)
    bundle.update(model_seed=model_seed, config=config.to_dict())
    if out is not None:
        np.savez_compressed(
            out / f"data_seed_{model_seed}.npz",
            states=np.concatenate(states).astype(np.float32),
            values=np.concatenate(values).astype(np.float32),
            round=np.concatenate([np.full(len(s), r) for r, s in enumerate(states)]),
        )
        dump(out / f"model_seed_{model_seed}.json", bundle)
    parameters = {h: sum(np.asarray(p).size for p in spec["weights"]) for h, spec in bundle["heads"].items()}
    return bundle, dict(model_seed=model_seed, rounds=rounds, calibration=calibration, parameters=parameters)


def methods(config):
    fixed = sorted({*config.ratios, LEGACY_FALLBACK})
    table = {f"fixed_{r:.2f}": dict(kind="fixed", ratio=r) for r in fixed}
    table["oracle"] = dict(kind="oracle")
    learned = {name: dict(kind="typed", head=head, rule=rule) for name, (head, rule) in LEARNED.items()}
    return table, learned


def group(config, scenario):
    """A family is in distribution only if some fitting step may draw from it."""
    return "id" if scenario in config.train_scenarios else "ood"


def panel_traces(config, split):
    """Scenario, trace seed and simulator seed of every trace in a split.

    The development panel shares the test seed namespace, so configuring the legacy families
    there replays exactly the traces of the earlier frozen test panel.
    """
    if split not in SPLITS:
        raise ValueError(f"unknown split {split}")
    if split == "validation":
        scenarios, seeds, role = config.train_scenarios, config.validation_seeds, "validation"
    else:
        scenarios = config.scenarios if split == "test" else config.development_scenarios
        seeds, role = config.test_seeds, "test"
    if not scenarios:
        raise ValueError(f"no {split} scenarios configured")
    return [(s, seed, split_seed(config.seed, role, s, seed)) for s in scenarios for seed in seeds]


def evaluate(config, bundles, split):
    """Paired closed-loop panel: every method sees identical exogenous traces."""
    traces = panel_traces(config, split)
    fixed, learned = methods(config)
    rows = []
    for name, spec in fixed.items():
        results = run_many(config, None, [(s, trace, spec) for s, _, trace in traces])
        rows += [dict(r, method=name, model_seed=None, trace_seed=t[1]) for r, t in zip(results, traces)]
    for bundle in bundles:
        for name, spec in learned.items():
            results = run_many(config, bundle, [(s, trace, spec, "score") for s, _, trace in traces])
            rows += [
                dict(r, method=name, model_seed=bundle["model_seed"], trace_seed=t[1])
                for r, t in zip(results, traces)
            ]
    return rows


def crossed_interval(matrix, rng, samples):
    """Mean and 95% interval, resampling model seeds (rows) and trace seeds (columns)."""
    m = np.asarray(matrix, dtype=float)
    r, c = m.shape
    boots = [m[np.ix_(rng.integers(r, size=r), rng.integers(c, size=c))].mean() for _ in range(samples)]
    return float(m.mean()), [float(v) for v in np.quantile(boots, [0.025, 0.975])]


def summarise(config, rows, split):
    seeds = config.validation_seeds if split == "validation" else config.test_seeds
    base = config.ratios.index(config.base_ratio)
    names = list(dict.fromkeys(r["method"] for r in rows))
    learned = [n for n in names if any(r["method"] == n and r["model_seed"] is not None for r in rows)]
    model_seeds = sorted({r["model_seed"] for r in rows if r["model_seed"] is not None})
    rng = np.random.default_rng(split_seed(config.seed, "bootstrap", split))
    panels = {}
    for panel in ("id", "ood", "all"):
        present = dict.fromkeys(r["scenario"] for r in rows)
        scenarios = [s for s in present if panel in ("all", group(config, s))]
        if not scenarios:
            continue
        chosen = [r for r in rows if r["scenario"] in scenarios]

        def matrix(method, key="utility"):
            cells = {}
            for r in chosen:
                if r["method"] == method:
                    cells.setdefault((r["model_seed"], r["trace_seed"]), []).append(r[key])
            owners = model_seeds if method in learned else [None]
            return np.asarray([[np.mean(cells[(m, s)]) for s in seeds] for m in owners])

        table = {}
        for name in names:
            mine = [r for r in chosen if r["method"] == name]
            decisions = [d for r in mine for d in r["decisions"]]
            reasons = Counter()
            for r in mine:
                reasons.update(r["reasons"])
            entry = dict(
                utility=float(matrix(name).mean()),
                unsafe=float(matrix(name, "unsafe").mean()),
                deadline_miss=float(matrix(name, "deadline_miss").mean()),
                latency_p95_ms=float(matrix(name, "latency_p95_ms").mean()),
                rate_mbps=float(matrix(name, "rate_mbps").mean()),
                per_scenario={
                    s: float(np.mean([r["utility"] for r in mine if r["scenario"] == s])) for s in scenarios
                },
            )
            if name in learned:
                entry["per_model_seed"] = [float(v) for v in matrix(name).mean(axis=1)]
            if decisions:
                values = np.asarray([d["values"] for d in decisions])
                executed = np.asarray([d["executed"] for d in decisions])
                index = np.arange(len(decisions))
                labels = choice_labels(values, config)
                entry.update(
                    decisions=len(decisions),
                    override_share=float(np.mean(executed != base)),
                    executed_accuracy=float(np.mean(executed == labels)),
                    executed_advantage=float(np.mean(values[index, executed] - values[:, base])),
                    executed_regret=float(np.mean(values.max(axis=1) - values[index, executed])),
                    reasons=dict(reasons),
                )
                if name.startswith("choice"):
                    entry["reliability"] = reliability([d["scores"] for d in decisions], labels)
            table[name] = entry
        fixed_names = [n for n in names if n.startswith("fixed_")]
        best_fixed = max(fixed_names, key=lambda n: table[n]["utility"])
        references = dict(
            base=f"fixed_{config.base_ratio:.2f}",
            best_fixed=best_fixed,
            legacy_fallback=f"fixed_{LEGACY_FALLBACK:.2f}",
        )
        contrasts = {}
        for name in [*learned, "oracle"]:
            contrasts[name] = {}
            for label, reference in references.items():
                mean, interval = crossed_interval(
                    matrix(name) - matrix(reference), rng, config.bootstrap_samples
                )
                unsafe = float((matrix(name, "unsafe") - matrix(reference, "unsafe")).mean())
                contrasts[name][label] = dict(
                    reference=reference, utility=mean, interval95=interval, unsafe=unsafe
                )
        panels[panel] = dict(
            scenarios=scenarios,
            trace_seeds=len(seeds),
            model_seeds=len(model_seeds),
            methods=table,
            references=references,
            contrasts=contrasts,
        )
    return panels


def inference_latency(bundle, head="choice_rlcd", calls=2000):
    """Microseconds for one typed answer: normalise, forward pass, softmax."""
    model, state = TypedModel(bundle), np.asarray(bundle["mean"])
    start = time.perf_counter()
    for _ in range(calls):
        model.answer(state, head)
    return (time.perf_counter() - start) / calls * 1e6


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=1, sort_keys=True, allow_nan=False) + "\n")


def run(config, out, splits=("validation", "test")):
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    started = time.time()
    config, tuning = tune_base(config.validate())
    dump(out / "config.json", config.to_dict())  # panels and base are fixed before any fitting
    bundles, training = [], []
    for model_seed in config.model_seeds:
        bundle, report = train_seed(config, model_seed, out)
        bundles.append(bundle)
        training.append(report)
    report = dict(
        abi=ABI,
        synthetic_only=True,
        base_tuning=tuning,
        training=training,
        inference_us=inference_latency(bundles[0]),
        panels={},
    )
    add_panels(config, bundles, report, out, splits)
    report["elapsed_s"] = time.time() - started
    dump(out / "report.json", report)
    return report


def decision_arrays(rows):
    """Decision-level record of the learned methods: what was reported, run and best in hindsight."""
    scored = [(r, d) for r in rows for d in r["decisions"] if "scores" in d]
    names = {key: list(dict.fromkeys(r[key] for r, _ in scored)) for key in ("method", "scenario")}
    index = {key: {name: i for i, name in enumerate(values)} for key, values in names.items()}
    arrays = dict(methods=np.asarray(names["method"]), scenarios=np.asarray(names["scenario"]))
    arrays["reasons"] = np.asarray(REASONS)
    for key in ("method", "scenario"):
        arrays[key] = np.asarray([index[key][r[key]] for r, _ in scored], dtype=np.int16)
    for key in ("model_seed", "trace_seed"):
        arrays[key] = np.asarray([r[key] for r, _ in scored], dtype=np.int64)
    for key in ("step", "executed", "proposal"):
        arrays[key] = np.asarray([d[key] for _, d in scored], dtype=np.int32)
    arrays["reason"] = np.asarray([REASONS.index(d["reason"]) for _, d in scored], dtype=np.int8)
    for key in ("fresh", "supported"):
        arrays[key] = np.asarray([d[key] for _, d in scored], dtype=bool)
    for key in ("scores", "values", "unsafe"):
        arrays[key] = np.asarray([d[key] for _, d in scored], dtype=np.float32).reshape(len(scored), -1)
    return arrays


def add_panels(config, bundles, report, out, splits):
    for split in splits:
        rows = evaluate(config, bundles, split)
        report["panels"][split] = summarise(config, rows, split)
        slim = [{k: v for k, v in r.items() if k != "decisions"} for r in rows]
        dump(out / f"{split}_episodes.json", slim)
        np.savez_compressed(out / f"{split}_decisions.npz", **decision_arrays(rows))


def evaluate_run(out, splits):
    """Add panels to a finished run from its frozen models; a panel is never recomputed."""
    out = Path(out)
    config = load_config(out / "config.json")
    report = json.loads((out / "report.json").read_text())
    if set(splits) & set(report["panels"]):
        raise ValueError("panel already evaluated; frozen results are not overwritten")
    bundles = [json.loads((out / f"model_seed_{s}.json").read_text()) for s in config.model_seeds]
    add_panels(config, bundles, report, out, splits)
    dump(out / "report.json", report)
    return report


def rescore(out, split="test"):
    """Replay a frozen panel's learned methods without overwriting it.

    A replay with hindsight rollouts switched off must reproduce the frozen episode outcomes:
    the labels score a controller and never reach it. If the panel predates decision-level
    records, a labelled replay must reproduce the outcomes too and supplies those records.
    """
    out = Path(out)
    config = load_config(out / "config.json")
    frozen = {
        (r["method"], r["model_seed"], r["scenario"], r["trace_seed"]): r
        for r in json.loads((out / f"{split}_episodes.json").read_text())
    }
    bundles = [json.loads((out / f"model_seed_{s}.json").read_text()) for s in config.model_seeds]
    traces, target = panel_traces(config, split), out / f"{split}_decisions.npz"
    kinds = (
        {"unlabelled_replay": ()}
        if target.exists()
        else {"unlabelled_replay": (), "labelled_replay": ("score",)}
    )
    rows, checks = [], dict(split=split, episodes=0, **dict.fromkeys(kinds, 0.0))
    for bundle in bundles:
        for name, spec in methods(config)[1].items():
            for kind, label in kinds.items():
                results = run_many(config, bundle, [(s, trace, spec, *label) for s, _, trace in traces])
                for (s, seed, _), r in zip(traces, results):
                    reference = frozen[(name, bundle["model_seed"], s, seed)]
                    checks[kind] = max(checks[kind], *(abs(r[k] - reference[k]) for k in OUTCOMES))
                    if label:
                        rows.append(dict(r, method=name, model_seed=bundle["model_seed"], trace_seed=seed))
            checks["episodes"] += len(traces)
    if rows:
        np.savez_compressed(target, **decision_arrays(rows))
    dump(out / f"{split}_isolation.json", checks)
    return checks


def diagnose(config, out):
    """Fixed-ratio sweep and hindsight oracle under both estimators, on training tune traces only."""
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    families = config.train_scenarios
    traces = [
        (families[i % len(families)], split_seed(config.seed, "tune", i)) for i in range(config.tune_episodes)
    ]
    report = {}
    for bwe in ("legacy", "acked"):
        variant, tuning = tune_base(replace(config, bwe=bwe, base_ratio=None))
        sweep = {f"fixed_{row['ratio']:.2f}": row for row in tuning["sweep"]}
        specs = {f"fixed_{LEGACY_FALLBACK:.2f}": dict(kind="fixed", ratio=LEGACY_FALLBACK)}
        specs["oracle"] = dict(kind="oracle")
        for name, spec in specs.items():
            rows = run_many(variant, None, [(s, seed, spec) for s, seed in traces])
            sweep[name] = dict(
                utility=float(np.mean([r["utility"] for r in rows])),
                unsafe=float(np.mean([r["unsafe"] for r in rows])),
            )
        report[bwe] = dict(best_fixed=tuning["selected"], methods=sweep)
    dump(out / "diagnosis.json", report)
    return report


def headline(report):
    lines = []
    for split, panels in report["panels"].items():
        for panel, data in panels.items():
            lines.append(f"[{split}/{panel}] " + "  ".join(f"{k}={v}" for k, v in data["references"].items()))
            for name, entry in data["methods"].items():
                extra = ""
                if name in data["contrasts"]:
                    c = data["contrasts"][name]["best_fixed"]
                    extra = f"  vs best fixed {c['utility']:+.3f} [{c['interval95'][0]:+.3f}, {c['interval95'][1]:+.3f}]"
                if "override_share" in entry:
                    extra += f"  override {entry['override_share']:.2f} acc {entry['executed_accuracy']:.2f}"
                if "reliability" in entry:
                    extra += f" ece {entry['reliability']['ece']:.3f}"
                if "executed_regret" in entry:
                    extra += f" regret {entry['executed_regret']:.3f}"
                lines.append(f"  {name:26s} U={entry['utility']:+.3f} unsafe={entry['unsafe']:.3f}{extra}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Typed (Jev-like) JevBWE study; synthetic only")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "diagnose"):
        p = sub.add_parser(command)
        p.add_argument("--config", required=True, type=Path)
        p.add_argument("--out", required=True, type=Path)
        if command == "run":
            p.add_argument("--splits", default="validation,test")
    p = sub.add_parser("evaluate", help="Add a frozen panel to a finished run")
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--splits", default="test")
    p = sub.add_parser("rescore", help="Replay a frozen panel: identity checks and decision records")
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--split", default="test")
    p = sub.add_parser("audit", help="Family-level audit of a finished run's frozen panel")
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--split", default="test")
    p.add_argument("--robustness", type=Path, help="Finished run of the same config with bwe=legacy")
    p.add_argument("--reference", type=Path, help="Finished run whose test panel has the same traces")
    p = sub.add_parser("export", help="LaTeX macros, tables and figure from a finished run")
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--diagnosis", type=Path, help="Directory written by the diagnose command")
    p.add_argument("--ablation", type=Path, help="Validation-only run with summaries disabled")
    p.add_argument("--robustness", type=Path, help="Finished run of the same config with bwe=legacy")
    p.add_argument("--broadened", type=Path, help="Finished run trained on the broadened families")
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            from .typed_bitrate_report import export

            evidence = export(
                args.run, args.out, args.diagnosis, args.ablation, args.robustness, args.broadened
            )
            print(json.dumps(evidence, indent=1))
            return
        if args.command == "audit":
            from .typed_bitrate_audit import audit

            result = audit(args.run, args.split, args.robustness, args.reference)
            print(json.dumps(result["headline"], indent=1))
            return
        if args.command == "rescore":
            print(json.dumps(rescore(args.run, args.split), indent=1))
            return
        if args.command == "evaluate":
            print(headline(evaluate_run(args.run, tuple(args.splits.split(",")))))
            return
        config = load_config(args.config)
        if args.command == "diagnose":
            print(json.dumps(diagnose(config, args.out), indent=1))
        else:
            print(headline(run(config, args.out, tuple(args.splits.split(",")))))
    except (ValueError, FileExistsError, FileNotFoundError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
