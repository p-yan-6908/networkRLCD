"""Family-level audit of a frozen typed-bitrate panel. Analysis only: nothing is refitted.

Reads the episode outcomes and decision records a run already wrote and answers four
questions: how each network family fares, how wide the uncertainty is once families are the
unit of resampling, what each decision rule does with the same reported probabilities, and
how utility trades against constraint violations.
"""

import json
from pathlib import Path

import numpy as np
from scipy import stats

from .typed_bitrate import Link, choice_labels, load_config, reliability, split_seed
from .typed_bitrate_experiment import LEARNED, crossed_interval, dump, group, panel_traces

KEYS = ("utility", "unsafe", "deadline_miss")
PIPELINE_MS = 8  # fixed low-latency pipeline delay of the fluid environment
PRIMARY = "choice_rlcd_bayes"
PAIRS = dict(
    rlcd_vs_exact_gradient=(PRIMARY, "choice_analytic_bayes"),
    rlcd_vs_regression=(PRIMARY, "regress_greedy"),
    payoff_weighted_vs_map=(PRIMARY, "choice_rlcd_map"),
    payoff_weighted_vs_gated=(PRIMARY, "choice_rlcd_gated"),
)


def cubes(config, episodes, split):
    """outcome[method][key] as [family, model seed, trace seed]; fixed methods are broadcast."""
    traces = panel_traces(config, split)
    families = list(dict.fromkeys(s for s, _, _ in traces))
    seeds = list(dict.fromkeys(seed for _, seed, _ in traces))
    models = list(config.model_seeds)
    shape = (len(families), len(models), len(seeds))
    out = {}
    for r in episodes:
        cube = out.setdefault(r["method"], {k: np.full(shape, np.nan) for k in KEYS})
        model = slice(None) if r["model_seed"] is None else models.index(r["model_seed"])
        for k in KEYS:
            cube[k][families.index(r["scenario"]), model, seeds.index(r["trace_seed"])] = r[k]
    if any(np.isnan(cube[k]).any() for cube in out.values() for k in KEYS):
        raise ValueError("panel is incomplete")
    return families, out


def family_interval(diff, rng, samples):
    """95% interval resampling families, traces within each drawn family, and model seeds."""
    f, m, s = diff.shape
    boots = np.empty(samples)
    for b in range(samples):
        family = rng.integers(f, size=f)[:, None, None]
        model = rng.integers(m, size=m)[None, :, None]
        boots[b] = diff[family, model, rng.integers(s, size=(f, 1, s))].mean()
    return [float(v) for v in np.quantile(boots, [0.025, 0.975])]


def contrast(diff, rng, samples):
    """A paired difference with seed-level and family-level uncertainty.

    ``seed_interval95`` holds the families fixed (the procedure of ``report.json``).
    ``family_interval95`` and ``family_t_interval95`` treat the families as a sample.
    """
    by_family = diff.mean(axis=(1, 2))
    count, mean = len(by_family), float(diff.mean())
    entry = dict(
        mean=mean,
        seed_interval95=crossed_interval(diff.mean(axis=0), rng, samples)[1],
        families=count,
        positive_families=int(np.sum(by_family > 0)),
        by_family=[float(v) for v in by_family],
    )
    if count > 1:
        half = float(stats.t.ppf(0.975, count - 1) * by_family.std(ddof=1) / np.sqrt(count))
        rest = (by_family.sum() - by_family) / (count - 1)
        entry.update(
            family_interval95=family_interval(diff, rng, samples),
            family_t_interval95=[mean - half, mean + half],
            leave_one_family_out=[float(rest.min()), float(rest.max())],
        )
    return entry


def exogenous_floor(config, split):
    """Share of control steps per family that violate a constraint whatever the sender does."""
    shares = {}
    for scenario, _, seed in panel_traces(config, split):
        env = Link(config, scenario, seed).env
        trace, sim = env.trace, env.config
        forced = (trace.capacity == 0) | (trace.loss > sim.safe_loss)
        forced |= trace.base_rtt / 2 + trace.jitter + PIPELINE_MS > sim.safe_latency_ms
        shares.setdefault(scenario, []).append(float(forced.mean()))
    return {k: float(np.mean(v)) for k, v in shares.items()}


def panels_of(config, families):
    out = {}
    for panel in ("id", "ood", "all"):
        index = [i for i, f in enumerate(families) if panel in ("all", group(config, f))]
        if index:
            out[panel] = index
    return out


def best_fixed(cube, index):
    fixed = [n for n in cube if n.startswith("fixed_")]
    return max(fixed, key=lambda n: cube[n]["utility"][index].mean())


def panel_contrasts(config, families, cube, rng, samples):
    base = f"fixed_{config.base_ratio:.2f}"
    out = {}
    for panel, index in panels_of(config, families).items():
        hindsight = best_fixed(cube, index)
        entry = dict(
            families=[families[i] for i in index],
            train_fixed=base,
            hindsight_fixed=hindsight,
            methods={},
            pairs={},
        )
        for name in [*LEARNED, "oracle"]:
            entry["methods"][name] = {
                f"{key}_vs_{label}": contrast(cube[name][key][index] - cube[ref][key][index], rng, samples)
                for key in ("utility", "unsafe")
                for label, ref in (("train_fixed", base), ("hindsight_fixed", hindsight))
            }
        for label, (a, b) in PAIRS.items():
            entry["pairs"][label] = {
                key: contrast(cube[a][key][index] - cube[b][key][index], rng, samples)
                for key in ("utility", "unsafe")
            }
        out[panel] = entry
    return out


def bin_sums(confidence, correct, bins=10):
    index = np.minimum((confidence * bins).astype(int), bins - 1)
    sums = np.zeros((bins, 3))
    for column, weight in enumerate((np.ones(len(index)), confidence, correct.astype(float))):
        sums[:, column] = np.bincount(index, weights=weight, minlength=bins)
    return sums


def pooled_ece(sums):
    total = sums.sum(axis=0)
    return float(np.abs(total[:, 2] - total[:, 1]).sum() / max(total[:, 0].sum(), 1))


def calibration(config, families, decisions, labels, rng, samples):
    """Top-label calibration per family, and pooled per panel with a family-resampled interval."""
    names = list(decisions["scenarios"])
    out = {}
    for m, method in enumerate(decisions["methods"]):
        if not str(method).startswith("choice"):
            continue
        per_family, sums = {}, []
        for family in families:
            mask = (decisions["method"] == m) & (decisions["scenario"] == names.index(family))
            scores = decisions["scores"][mask].astype(float)
            stats_ = reliability(scores, labels[mask])
            per_family[family] = {k: stats_[k] for k in ("rows", "accuracy", "confidence", "ece", "nll")}
            sums.append(bin_sums(scores.max(axis=1), scores.argmax(axis=1) == labels[mask]))
        sums, pooled = np.asarray(sums), {}
        for panel, index in panels_of(config, families).items():
            chosen = sums[index]
            boots = [pooled_ece(chosen[rng.integers(len(index), size=len(index))]) for _ in range(samples)]
            total = chosen.sum(axis=0)
            pooled[panel] = dict(
                ece=pooled_ece(chosen),
                family_interval95=[float(v) for v in np.quantile(boots, [0.025, 0.975])],
                accuracy=float(total[:, 2].sum() / total[:, 0].sum()),
                confidence=float(total[:, 1].sum() / total[:, 0].sum()),
                worst_family=max(index, key=lambda i: per_family[families[i]]["ece"] or 0.0),
            )
            pooled[panel]["worst_family"] = families[pooled[panel]["worst_family"]]
        out[str(method)] = dict(families=per_family, panels=pooled)
    return out


def rule_analysis(config, run, families, decisions, labels):
    """What each rule does with the probabilities the deployed payoff-weighted policy reported.

    Every rule is recomputed on the same visited states from the recorded probabilities, the
    frozen payoff table and the frozen threshold, then scored by the hindsight advantage of
    its one decision over the base ratio. The recomputed payoff-weighted choice must equal the
    action that actually ran: the runtime rule uses nothing else.
    """
    base = config.ratios.index(config.base_ratio)
    heads = [
        json.loads((Path(run) / f"model_seed_{s}.json").read_text())["heads"]["choice_rlcd"]
        for s in config.model_seeds
    ]
    payoff = np.asarray([h["payoff"] for h in heads], dtype=float)
    mine = decisions["method"] == list(decisions["methods"]).index(PRIMARY)
    scores, values = decisions["scores"][mine].astype(float), decisions["values"][mine].astype(float)
    model = np.asarray([config.model_seeds.index(s) for s in decisions["model_seed"][mine]])
    guard = decisions["fresh"][mine] & decisions["supported"][mine]
    rows = np.arange(len(scores))
    ranking = np.einsum("nab,nb->na", payoff[model], scores)
    top, mode = ranking.argmax(axis=1), scores.argmax(axis=1)
    threshold = np.asarray([h["threshold"] for h in heads])[model]
    choices = dict(
        payoff_weighted=np.where((top != base) & (ranking[rows, top] > 0) & guard, top, base),
        map=mode,
        gated=np.where((mode != base) & guard & (scores[rows, mode] >= threshold), mode, base),
        hindsight_best=values.argmax(axis=1),
    )
    y, executed = labels[mine], decisions["executed"][mine]
    advantage = values - values[:, [base]]
    names = list(decisions["scenarios"])
    scenario = decisions["scenario"][mine]
    out = dict(
        ratios=list(config.ratios),
        base_ratio=config.base_ratio,
        payoff_mean=payoff.mean(axis=0).tolist(),
        thresholds=[float(h["threshold"]) for h in heads],
        temperatures=[float(h["temperature"]) for h in heads],
        recomputed_equals_executed=float(np.mean(choices["payoff_weighted"] == executed)),
        panels={},
    )
    for panel, index in panels_of(config, families).items():
        mask = np.isin(scenario, [names.index(families[i]) for i in index])
        r = rows[mask]
        picked = choices["payoff_weighted"][mask]
        differ = picked != mode[mask]
        moved = picked != base
        entry = dict(
            decisions=int(mask.sum()),
            label_is_base=float(np.mean(y[mask] == base)),
            guard_blocks=float(np.mean(~guard[mask])),
            rules={
                name: dict(
                    leaves_base=float(np.mean(choice[mask] != base)),
                    matches_label=float(np.mean(choice[mask] == y[mask])),
                    advantage=float(advantage[r, choice[mask]].mean()),
                    below_base=float(np.mean(choice[mask] < base)),
                    above_base=float(np.mean(choice[mask] > base)),
                )
                for name, choice in choices.items()
            },
            payoff_weighted_differs_from_map=float(np.mean(differ)),
            where_they_differ=dict(
                payoff_weighted_advantage=float(advantage[r, picked][differ].mean())
                if differ.any()
                else None,
                map_advantage=float(advantage[r, mode[mask]][differ].mean()) if differ.any() else None,
                payoff_weighted_leaves_base=float(np.mean(moved[differ])) if differ.any() else None,
            ),
            predicted_advantage_when_leaving=float(ranking[r, picked][moved].mean()) if moved.any() else None,
            realised_advantage_when_leaving=float(advantage[r, picked][moved].mean())
            if moved.any()
            else None,
        )
        out["panels"][panel] = entry
    return out


def tradeoff(config, families, cube, floors):
    """Utility against violations for every method, and the fixed ratio that is no less safe."""
    out = {}
    for panel, index in panels_of(config, families).items():
        table = {name: {k: float(c[k][index].mean()) for k in KEYS} for name, c in cube.items()}
        fixed = [n for n in table if n.startswith("fixed_")]
        matched = {}
        for name in [*LEARNED, "oracle"]:
            safe = [n for n in fixed if table[n]["unsafe"] <= table[name]["unsafe"] + 1e-12]
            if safe:
                rival = max(safe, key=lambda n: table[n]["utility"])
                matched[name] = dict(
                    fixed=rival,
                    utility_difference=table[name]["utility"] - table[rival]["utility"],
                    unsafe_difference=table[name]["unsafe"] - table[rival]["unsafe"],
                )
        out[panel] = dict(
            methods=table,
            floor=float(np.mean([floors[families[i]] for i in index])),
            no_less_safe_fixed=matched,
        )
    return out


def family_rows(config, families, cube, floors, calibrated, rng, samples):
    base = f"fixed_{config.base_ratio:.2f}"
    out = {}
    for i, family in enumerate(families):
        hindsight = best_fixed(cube, [i])
        entry = dict(group=group(config, family), floor=floors[family], hindsight_fixed=hindsight, methods={})
        for name, c in cube.items():
            row = {k: float(c[k][i].mean()) for k in KEYS}
            if name in LEARNED or name == "oracle":
                diff = c["utility"][i] - cube[base]["utility"][i]
                row["utility_vs_train_fixed"] = float(diff.mean())
                row["utility_vs_train_fixed_seed_interval95"] = crossed_interval(diff, rng, samples)[1]
                row["utility_vs_hindsight_fixed"] = float(
                    (c["utility"][i] - cube[hindsight]["utility"][i]).mean()
                )
                row["unsafe_vs_train_fixed"] = float((c["unsafe"][i] - cube[base]["unsafe"][i]).mean())
            if name in calibrated:
                row.update(calibrated[name]["families"][family])
            entry["methods"][name] = row
        out[family] = entry
    return out


def paired_runs(config, families, cube, reference, reference_split, rng, samples):
    """This run minus another run on identical traces (the same panel replayed by both)."""
    reference = Path(reference)
    other_config = load_config(reference / "config.json")
    episodes = json.loads((reference / f"{reference_split}_episodes.json").read_text())
    other_families, other = cubes(other_config, episodes, reference_split)
    shared = [n for n in cube if n.startswith("fixed_") and n in other]
    if other_families != families or other_config.bwe != config.bwe or not shared:
        raise ValueError("reference run does not cover the same panel")
    identity = max(float(np.abs(cube[n][k] - other[n][k]).max()) for n in shared for k in KEYS)
    names = dict(train_fixed=(f"fixed_{config.base_ratio:.2f}", f"fixed_{other_config.base_ratio:.2f}"))
    names.update({n: (n, n) for n in LEARNED})
    out = dict(reference=str(reference), fixed_ratio_identity=identity, panels={})
    for panel, index in panels_of(other_config, families).items():
        out["panels"][panel] = {
            label: {
                key: contrast(cube[mine][key][index] - other[theirs][key][index], rng, samples)
                for key in ("utility", "unsafe")
            }
            for label, (mine, theirs) in names.items()
        }
    return out


def cross_estimator(config, families, cube, robustness, split, rng, samples):
    """The typed head over the bounded estimator against the other estimator's best constant cap."""
    robustness = Path(robustness)
    other_config = load_config(robustness / "config.json")
    episodes = json.loads((robustness / f"{split}_episodes.json").read_text())
    other_families, other = cubes(other_config, episodes, split)
    if other_families != families or other_config.test_seeds != config.test_seeds:
        raise ValueError("robustness run does not cover the same panel")
    floors = exogenous_floor(other_config, split)
    out = dict(bwe=other_config.bwe, tradeoff=tradeoff(other_config, families, other, floors), panels={})
    for panel, index in panels_of(config, families).items():
        cap = best_fixed(other, index)
        out["panels"][panel] = dict(
            constant_cap=cap,
            typed_minus_cap={
                key: contrast(cube[PRIMARY][key][index] - other[cap][key][index], rng, samples)
                for key in ("utility", "unsafe")
            },
            other_typed_minus_cap={
                key: contrast(other[PRIMARY][key][index] - other[cap][key][index], rng, samples)
                for key in ("utility", "unsafe")
            },
        )
    return out


def audit(run, split="test", robustness=None, reference=None, reference_split="test", samples=5000):
    run = Path(run)
    config = load_config(run / "config.json")
    report = json.loads((run / "report.json").read_text())
    episodes = json.loads((run / f"{split}_episodes.json").read_text())
    decisions = dict(np.load(run / f"{split}_decisions.npz"))
    rng = np.random.default_rng(split_seed(config.seed, "audit", split))
    families, cube = cubes(config, episodes, split)
    labels = choice_labels(decisions["values"].astype(float), config)
    floors = exogenous_floor(config, split)
    calibrated = calibration(config, families, decisions, labels, rng, samples)
    isolation = run / f"{split}_isolation.json"
    frozen = report["panels"][split]
    drift = max(
        abs(calibrated[PRIMARY]["panels"][p]["ece"] - frozen[p]["methods"][PRIMARY]["reliability"]["ece"])
        for p in calibrated[PRIMARY]["panels"]
    )
    result = dict(
        run=str(run),
        split=split,
        synthetic_only=True,
        train_scenarios=list(config.train_scenarios),
        bootstrap_samples=samples,
        isolation=json.loads(isolation.read_text()) if isolation.exists() else None,
        ece_difference_to_report=drift,
        families=family_rows(config, families, cube, floors, calibrated, rng, samples),
        panels=panel_contrasts(config, families, cube, rng, samples),
        calibration={name: entry["panels"] for name, entry in calibrated.items()},
        rules=rule_analysis(config, run, families, decisions, labels),
        tradeoff=tradeoff(config, families, cube, floors),
    )
    if robustness:
        result["cross_estimator"] = cross_estimator(config, families, cube, robustness, split, rng, samples)
    if reference:
        result["paired"] = paired_runs(config, families, cube, reference, reference_split, rng, samples)
    result["headline"] = headline(result)
    dump(run / f"audit_{split}.json", result)
    return result


def headline(result):
    lines = {}
    for panel, entry in result["panels"].items():
        c = entry["methods"][PRIMARY]
        gain, risk = c["utility_vs_train_fixed"], c["unsafe_vs_train_fixed"]
        lines[panel] = dict(
            families=entry["families"],
            train_fixed=entry["train_fixed"],
            hindsight_fixed=entry["hindsight_fixed"],
            gain_vs_train_fixed=gain["mean"],
            gain_seed_interval95=gain["seed_interval95"],
            gain_family_interval95=gain.get("family_interval95"),
            gain_family_t_interval95=gain.get("family_t_interval95"),
            positive_families=f"{gain['positive_families']}/{gain['families']}",
            gain_vs_hindsight_fixed=c["utility_vs_hindsight_fixed"]["mean"],
            unsafe_vs_train_fixed=risk["mean"],
            unsafe_family_interval95=risk.get("family_interval95"),
            ece=result["calibration"][PRIMARY][panel]["ece"],
            worst_family_ece=result["calibration"][PRIMARY][panel]["worst_family"],
            rlcd_vs_exact_gradient=entry["pairs"]["rlcd_vs_exact_gradient"]["utility"]["mean"],
            rlcd_vs_regression=entry["pairs"]["rlcd_vs_regression"]["utility"]["mean"],
        )
    lines["isolation"] = result["isolation"]
    lines["recomputed_rule_equals_executed"] = result["rules"]["recomputed_equals_executed"]
    return lines
