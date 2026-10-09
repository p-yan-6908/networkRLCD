"""Factual-only supervision for the typed bitrate decision (synthetic, development).

Rollout labels compare every option on the same future, which a real network cannot provide.
This module asks what a learner recovers from factual outcomes alone. At random decision
epochs one option is drawn uniformly, held for the commit window and followed by the base
ratio, and the realised utility of that single block is the only label. A masked regression
learns a value per option from it, and a doubly-robust estimate on held-out blocks decides how
large a predicted advantage must be before the head leaves the base ratio.

Every row also carries the hindsight rollout values of all options. They serve two purposes
only: a control head trained on them from the same rows, and scoring. The factual pipeline
never reads them.
"""

import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .jevbwe import STATE_DIM, CausalHistory, number
from .networks import MLP
from .typed_bitrate import ABI, Features, Governor, Link, load_config, rollout_values, split_seed, step
from .typed_bitrate_audit import contrast
from .typed_bitrate_experiment import dump, panel_traces, run_many

STUDY = "typed_bitrate_factual_v1"
NEVER = 1e6  # a margin no prediction exceeds: the head always answers with the base ratio
SOURCES = ("factual", "rollout")
SPEC = dict(kind="typed", head="regress", rule="greedy")
DEFAULTS = dict(
    name="typed-factual-v1",
    blocks=[5000, 20000, 80000, 320000, 1280000],  # nested budgets of factual blocks
    control_blocks=80000,  # largest budget that also gets rollout values and the control head
    seeds=[0, 1, 2],
    block_probability=0.5,  # chance that a free decision epoch starts a block
    shares=[0.7, 0.1, 0.2],  # fit, early stopping, margin selection; split by episode
    margins=[0.0, 0.01, 0.02, 0.05, 0.1, 0.2],
    max_updates=20000,  # at least this many optimiser updates are allowed ...
    min_epochs=30,  # ... and at least this many passes over the fit rows
    check_every=250,
    patience=8,
)
_WORKER = {}


def load_settings(path=None):
    settings = {**DEFAULTS, **(json.loads(Path(path).read_text()) if path else {})}
    if set(settings) != set(DEFAULTS):
        raise ValueError("unknown factual study setting")
    blocks, shares = settings["blocks"], settings["shares"]
    if not blocks or blocks != sorted(set(blocks)) or blocks[0] < 10 or not settings["seeds"]:
        raise ValueError("budgets must be increasing block counts and seeds are required")
    if len(shares) != 3 or min(shares) <= 0 or abs(sum(shares) - 1) > 1e-9:
        raise ValueError("shares must be three positive fractions that sum to one")
    if not 0 < settings["block_probability"] <= 1 or min(settings["margins"]) < 0:
        raise ValueError("block probability must lie in (0, 1] and margins be nonnegative")
    limits = ("control_blocks", "max_updates", "min_epochs", "check_every", "patience")
    if any(type(settings[k]) is not int or settings[k] < 1 for k in limits):
        raise ValueError("positive integer limits required")
    return settings


class DeferredHistory(CausalHistory):
    """``CausalHistory`` that keeps its rows every step and builds the state only on request.

    Building the ordered state is most of an episode's cost, and a factual block needs it at
    block starts only. The row bookkeeping is that of ``CausalHistory.observe``.
    """

    build = True

    def observe(self, sample):
        if self.build:
            return super().observe(sample)
        now, c = sample.sample_ms, self.config
        if not number(now) or now < 0 or (self.last_ms is not None and now <= self.last_ms):
            raise ValueError("JevBWE sample clock must strictly advance")
        reset = self.last_ms is not None and now - self.last_ms > c.reset_gap_ms
        if reset:
            self.rows.clear()
        self.rows.append(sample)
        self.rows = [s for s in self.rows if now - s.sample_ms <= c.max_history_ms]
        self.last_ms = now
        return np.zeros(STATE_DIM), reset


def block_episode(config, scenario, seed, behaviour_seed, probability, truth=True, eager=False):
    """The base policy with random factual blocks.

    A block draws one option uniformly, holds it for the commit window and runs the base ratio
    for the tail: the estimand of a rollout label, observed for a single option. Blocks never
    overlap, so a block's outcome depends on no other block's draw. ``truth`` adds the rollout
    value of every option at the block start, for the control head and for scoring. ``eager``
    builds the ordered state at every step, as a controller would; the rows are the same.
    """
    link, rules, features = Link(config, scenario, seed), Governor(config), Features(config)
    features.history = DeferredHistory(config.residual)
    rng = np.random.default_rng(behaviour_seed)
    rows, block, missing = [], None, [np.nan] * len(config.ratios)
    for t in range(config.steps):
        sample = link.sample()
        free = block is None and t % config.decision_steps == 0 and t + config.horizon_steps <= config.steps
        start = bool(free and rng.random() < probability)
        features.history.build = start or eager
        state = features.observe(sample)  # summaries every step; the ordered state where a block starts
        if start:
            values = rollout_values(link, rules, sample, config)[0] if truth else missing
            block = dict(
                start=t, arm=int(rng.integers(len(config.ratios))), state=state, values=values, total=0.0
            )
        ratio = config.base_ratio
        if block is not None and t - block["start"] < config.commit_steps:
            ratio = config.ratios[block["arm"]]
        utility, _ = step(link, rules, sample, ratio, config)
        if block is not None:
            block["total"] += utility
            if t - block["start"] + 1 == config.horizon_steps:
                rows.append(
                    (block["state"], block["arm"], block["total"] / config.horizon_steps, block["values"])
                )
                block = None
    return dict(
        states=np.asarray([r[0] for r in rows], dtype=np.float32).reshape(len(rows), -1),
        arms=np.asarray([r[1] for r in rows], dtype=np.int64),
        outcomes=np.asarray([r[2] for r in rows], dtype=float),
        values=np.asarray([r[3] for r in rows], dtype=float).reshape(len(rows), len(config.ratios)),
    )


def _init(config, probability):
    _WORKER.update(config=config, probability=probability)


def _collect(task):
    return block_episode(_WORKER["config"], *task[:3], _WORKER["probability"], task[3])


def collect(config, data_seed, blocks, probability, truth_blocks=None):
    """At least ``blocks`` factual blocks from fresh training-family traces, in episode order.

    Rollout values are computed until ``truth_blocks`` rows exist (all rows by default); later
    rows carry NaN there, which the factual pipeline never reads.
    """
    truth_blocks = blocks if truth_blocks is None else min(truth_blocks, blocks)
    families, episodes, have = config.train_scenarios, [], 0
    while have < blocks:
        truth = have < truth_blocks
        done, target = len(episodes), truth_blocks if truth else blocks
        rate = max(have / done, 0.1) if done else None  # a short first chunk measures blocks per episode
        more = max(len(families), math.ceil((target - have) / rate * 1.03)) if rate else 4 * len(families)
        tasks = [
            (
                families[i % len(families)],
                split_seed(config.seed, "factual-trace", data_seed, i),
                split_seed(config.seed, "factual-behaviour", data_seed, i),
                truth,
            )
            for i in range(done, done + more)
        ]
        if config.workers == 1 or len(tasks) < 4:
            episodes += [_run(config, task, probability) for task in tasks]
        else:
            with ProcessPoolExecutor(
                config.workers, initializer=_init, initargs=(config, probability)
            ) as pool:
                episodes += list(pool.map(_collect, tasks, chunksize=16))
        have = sum(len(e["arms"]) for e in episodes)
    data = {k: np.concatenate([e[k] for e in episodes]) for k in ("states", "arms", "outcomes", "values")}
    data["episode"] = np.repeat(np.arange(len(episodes)), [len(e["arms"]) for e in episodes])
    return data


def _run(config, task, probability):
    return block_episode(config, *task[:3], probability, task[3])


def budget(data, blocks, shares):
    """The first ``blocks`` rows, split into fit, early-stopping and selection parts by episode."""
    episode = data["episode"][:blocks]
    cuts = [episode[min(blocks - 1, int(round(blocks * share)))] for share in np.cumsum(shares)[:2]]
    part = np.searchsorted(cuts, episode, side="right")
    return [{k: v[:blocks][part == i] for k, v in data.items()} for i in range(3)]


def fit(x, target, mask, stop, settings, hidden, rate, batch, seed):
    """Masked least squares with early stopping; a row's loss covers the options its mask marks."""
    rng = np.random.default_rng(seed)
    net = MLP(x.shape[1], hidden, target.shape[1], rng)
    ids, cursor = np.arange(len(x)), len(x)
    limit = max(settings["max_updates"], math.ceil(settings["min_epochs"] * len(x) / batch))
    best, best_loss, stale = [p.copy() for p in net.params], np.inf, 0
    for update in range(1, limit + 1):
        if cursor + batch > len(ids):
            rng.shuffle(ids)
            cursor = 0
        idx = np.sort(ids[cursor : cursor + batch])
        cursor += batch
        error = (net(x[idx]) - target[idx]) * mask[idx]
        net.train(x[idx].astype(float), 2 * error / len(idx), rate * (1 - 0.9 * update / limit))
        if update % settings["check_every"] == 0 or update == limit:
            loss = float(np.sum(((net(stop[0]) - stop[1]) * stop[2]) ** 2) / stop[2].sum())
            if loss < best_loss - 1e-9:
                best, best_loss, stale = [p.copy() for p in net.params], loss, 0
            else:
                stale += 1
                if stale >= settings["patience"]:
                    break
    net.params = best
    return net, dict(updates=update, stop_loss=best_loss)


def choose(advantage, base, margin):
    """The best other option where its predicted advantage exceeds the margin, else the base."""
    others = advantage.copy()
    others[:, base] = -np.inf
    return np.where(others.max(axis=1) > margin, others.argmax(axis=1), base)


def doubly_robust(value, arms, outcomes, chosen):
    """Block utility of a policy, estimated from uniformly randomised factual blocks only."""
    rows = np.arange(len(arms))
    correction = (arms == chosen) * value.shape[1] * (outcomes - value[rows, arms])
    return float(np.mean(value[rows, chosen] + correction))


def package(config, norm, net, scale, margin, seed):
    """A model bundle whose regression head reports advantage over the base minus the margin.

    Folding both into the output layer lets the frozen ``TypedPolicy`` greedy rule run the
    head unchanged: it leaves the base exactly when ``choose`` does.
    """
    base = config.ratios.index(config.base_ratio)
    w, b, v, c = (p.copy() for p in net.params)
    v, c = v - v[:, [base]], c - c[base]
    c[np.arange(len(c)) != base] -= margin / scale
    head = dict(weights=[p.tolist() for p in (w, b, v, c)], target_scale=float(scale), threshold=0.0)
    return dict(
        abi=ABI,
        ratios=list(config.ratios),
        base_ratio=config.base_ratio,
        mean=norm[0].tolist(),
        scale=norm[1].tolist(),
        support_limit=float(norm[2]),
        heads=dict(regress=head),
        synthetic_only=True,
        model_seed=seed,
    )


def train(config, parts, source, settings, seed):
    """One pipeline on one budget: fit, then pick the acting margin with that pipeline's own labels."""
    if source not in SOURCES:
        raise ValueError(f"unknown label source {source}")
    base, options = config.ratios.index(config.base_ratio), len(config.ratios)
    fitted = parts[0]
    mean = fitted["states"].mean(axis=0, dtype=float)
    spread = np.maximum(fitted["states"].std(axis=0, dtype=float), 0.05)

    def inputs(part, limit=False):  # single precision keeps the largest budget within memory
        x = (part["states"] - mean.astype(np.float32)) / spread.astype(np.float32)
        support = np.quantile(np.sqrt(np.mean(x * x, axis=1)), config.support_quantile) if limit else None
        return np.clip(x, -12, 12, out=x), support

    def targets(part):
        if source == "rollout":  # every option, on the same future
            return (part["values"] - part["values"][:, [base]]) / scale, np.ones((len(part["arms"]), options))
        mask = np.eye(options)[part["arms"]]  # the executed option only
        return mask * ((part["outcomes"] - centre) / scale)[:, None], mask

    if source == "rollout":
        if any(np.isnan(p["values"]).any() for p in parts):
            raise ValueError("the rollout control needs rollout values on every row")
        centre, scale = 0.0, float(max((fitted["values"] - fitted["values"][:, [base]]).std(), 0.05))
    else:
        centre, scale = float(fitted["outcomes"].mean()), float(max(fitted["outcomes"].std(), 0.05))
    x, support = inputs(fitted, limit=True)
    net, info = fit(
        x,
        *targets(fitted),
        (inputs(parts[1])[0], *targets(parts[1])),
        settings,
        config.hidden,
        config.learning_rate,
        config.batch_size,
        split_seed(config.seed, "factual-optimizer", source, seed),
    )
    del x
    held = parts[2]
    output = net(inputs(held)[0])
    advantage = (output - output[:, [base]]) * scale
    rows, curve = np.arange(len(held["arms"])), []
    for margin in settings["margins"]:
        chosen = choose(advantage, base, margin)
        if source == "rollout":
            gain = float(np.mean(held["values"][rows, chosen] - held["values"][:, base]))
        else:
            value = output * scale + centre
            stay = np.full(len(rows), base)
            gain = doubly_robust(value, held["arms"], held["outcomes"], chosen) - doubly_robust(
                value, held["arms"], held["outcomes"], stay
            )
        curve.append(dict(margin=margin, estimated_gain=gain, override_share=float(np.mean(chosen != base))))
    best = max(curve, key=lambda row: row["estimated_gain"])
    margin = best["margin"] if best["estimated_gain"] > 0 else NEVER
    info.update(rows=[len(p["arms"]) for p in parts], scale=scale, margin=margin, margin_curve=curve)
    return net, (mean, spread, float(support)), scale, info


def offline(net, norm, scale, margin, truth, base):
    """Scored against hindsight rollouts on states the base policy visits; evaluation only."""
    x = np.clip((truth["states"] - norm[0]) / norm[1], -12, 12)
    output = net(x)
    advantage = (output - output[:, [base]]) * scale
    actual = truth["values"] - truth["values"][:, [base]]
    chosen, rows = choose(advantage, base, margin), np.arange(len(x))
    others = np.arange(actual.shape[1]) != base
    correlation = np.corrcoef(advantage[:, others].ravel(), actual[:, others].ravel())[0, 1]
    return dict(
        advantage=float(actual[rows, chosen].mean()),
        override_share=float(np.mean(chosen != base)),
        correlation=float(correlation) if np.isfinite(correlation) else 0.0,  # a constant prediction
    )


def truth_set(config):
    """States of the base policy on the validation traces, with the rollout value of every option."""
    tasks = [
        (s, trace, dict(kind="fixed", ratio=config.base_ratio), "data")
        for s, _, trace in panel_traces(config, "validation")
    ]
    rows = [d for episode in run_many(config, None, tasks) for d in episode["decisions"]]
    return dict(states=np.asarray([d["state"] for d in rows]), values=np.asarray([d["values"] for d in rows]))


def closed_loop(config, bundle):
    """Validation-panel utility and unsafe share as [family, trace seed]; no hindsight is computed."""
    traces = panel_traces(config, "validation")
    results = run_many(config, bundle, [(s, trace, SPEC) for s, _, trace in traces])
    shape = (len(config.train_scenarios), len(config.validation_seeds))
    return {k: np.asarray([r[k] for r in results]).reshape(shape) for k in ("utility", "unsafe")}


def frozen_panel(config, run, method):
    """A frozen method's validation outcomes as [family, model seed, trace seed]."""
    rows = [r for r in json.loads((run / "validation_episodes.json").read_text()) if r["method"] == method]
    models = sorted({r["model_seed"] for r in rows}, key=lambda m: -1 if m is None else m)
    families, seeds = config.train_scenarios, config.validation_seeds
    out = {k: np.full((len(families), len(models), len(seeds)), np.nan) for k in ("utility", "unsafe")}
    for r in rows:
        cell = families.index(r["scenario"]), models.index(r["model_seed"]), seeds.index(r["trace_seed"])
        for k in out:
            out[k][cell] = r[k]
    if any(np.isnan(v).any() for v in out.values()):
        raise ValueError(f"frozen validation panel is incomplete for {method}")
    return out


def study(run, out, settings=None, samples=5000):
    """Learning curves of the factual pipeline and its rollout-labelled control on shared rows."""
    run, out = Path(run), Path(out)
    if out.exists():
        raise FileExistsError(out)
    config, settings = load_config(run / "config.json"), load_settings(settings)
    if config.base_ratio is None:
        raise ValueError("the run's config must record its selected base ratio")
    base, started = config.ratios.index(config.base_ratio), time.time()
    out.mkdir(parents=True)
    dump(out / "settings.json", settings)
    truth = truth_set(config)
    fixed = frozen_panel(config, run, f"fixed_{config.base_ratio:.2f}")
    replay = closed_loop(config, package(config, *_idle(config), NEVER, 0))  # a head that never acts
    rng = np.random.default_rng(split_seed(config.seed, "factual-bootstrap"))
    actual = truth["values"] - truth["values"][:, [base]]
    report = dict(
        abi=STUDY,
        run=str(run),
        synthetic_only=True,
        settings=settings,
        truth=dict(states=len(actual), oracle_advantage=float(actual.max(axis=1).mean())),
        never_acting_head_matches_fixed=float(np.abs(replay["utility"] - fixed["utility"][:, 0]).max()),
        reference={},
        collection=[],
        budgets=[],
    )
    for name, method in (("v3_regress", "regress_greedy"), ("v3_head", "choice_rlcd_bayes")):
        panel = frozen_panel(config, run, method)
        report["reference"][name] = {k: contrast(panel[k] - fixed[k], rng, samples) for k in panel}
    cells = {}  # (blocks, source, variant) -> per-seed entries and panels
    for seed in settings["seeds"]:
        data = collect(
            config, seed, settings["blocks"][-1], settings["block_probability"], settings["control_blocks"]
        )
        episodes, known = int(data["episode"][-1]) + 1, ~np.isnan(data["values"]).any(axis=1)
        executed = data["values"][known, data["arms"][known]]
        report["collection"].append(
            dict(
                seed=seed,
                episodes=episodes,
                blocks=len(data["arms"]),
                blocks_per_episode=len(data["arms"]) / episodes,
                rollout_rows=int(known.sum()),
                factual_matches_rollout=float(np.abs(data["outcomes"][known] - executed).max()),
            )
        )
        for blocks in settings["blocks"]:
            parts = budget(data, blocks, settings["shares"])
            for source in SOURCES if blocks <= settings["control_blocks"] else SOURCES[:1]:
                net, norm, scale, info = train(config, parts, source, settings, seed)
                for variant, margin in (("selected", info["margin"]), ("zero", 0.0)):
                    bundle = package(config, norm, net, scale, margin, seed)
                    panel = closed_loop(config, bundle)
                    entry = dict(
                        seed=seed,
                        margin=margin,
                        offline=offline(net, norm, scale, margin, truth, base),
                        utility=float(panel["utility"].mean()),
                        unsafe=float(panel["unsafe"].mean()),
                    )
                    if variant == "selected":
                        entry["fit"] = info
                        dump(out / f"model_{source}_{blocks}_seed_{seed}.json", bundle)
                    cell = cells.setdefault((blocks, source, variant), dict(seeds=[], panels=[]))
                    cell["seeds"].append(entry)
                    cell["panels"].append(panel)
            del parts
        del data
    seconds = config.steps * config.dt_ms / 1000
    per_episode = float(np.mean([c["blocks_per_episode"] for c in report["collection"]]))
    for blocks in settings["blocks"]:
        entry = dict(
            blocks=blocks, link_hours=blocks / per_episode * seconds / 3600, pipelines={}, contrasts={}
        )
        cube = {}
        for source in SOURCES:
            for variant in ("selected", "zero"):
                if (blocks, source, variant) not in cells:
                    continue
                cell = cells[(blocks, source, variant)]
                name = source if variant == "selected" else f"{source}_zero_margin"
                cube[name] = {
                    k: np.stack([p[k] for p in cell["panels"]], axis=1) for k in ("utility", "unsafe")
                }
                entry["pipelines"][name] = dict(
                    seeds=cell["seeds"],
                    offline_advantage=float(np.mean([s["offline"]["advantage"] for s in cell["seeds"]])),
                    correlation=float(np.mean([s["offline"]["correlation"] for s in cell["seeds"]])),
                )
                entry["contrasts"][f"{name}_vs_fixed"] = {
                    k: contrast(cube[name][k] - fixed[k], rng, samples) for k in ("utility", "unsafe")
                }
        for name, (a, b) in dict(
            factual_vs_rollout=("factual", "rollout"),
            factual_vs_rollout_zero_margin=("factual_zero_margin", "rollout_zero_margin"),
        ).items():
            if a in cube and b in cube:
                entry["contrasts"][name] = {
                    k: contrast(cube[a][k] - cube[b][k], rng, samples) for k in ("utility", "unsafe")
                }
        report["budgets"].append(entry)
    report["elapsed_s"] = time.time() - started
    dump(out / "report.json", report)
    return report


def _idle(config):
    """Normalisation, network and scale of a placeholder head; with the NEVER margin it only answers base."""
    from .typed_bitrate import FEATURE_DIM

    net = MLP(FEATURE_DIM, config.hidden, len(config.ratios), np.random.default_rng(0))
    return (np.zeros(FEATURE_DIM), np.ones(FEATURE_DIM), np.inf), net, 1.0


def headline(report):
    lines = [
        f"truth: {report['truth']['states']} base-policy states, oracle advantage "
        f"{report['truth']['oracle_advantage']:.3f}; never-acting head vs fixed "
        f"{report['never_acting_head_matches_fixed']:.1e}"
    ]
    for name, entry in report["reference"].items():
        u = entry["utility"]
        t = u["family_t_interval95"]
        lines.append(f"reference {name} vs fixed {u['mean']:+.3f} family t [{t[0]:+.3f}, {t[1]:+.3f}]")
    for c in report["collection"]:
        lines.append(
            f"seed {c['seed']}: {c['blocks']} blocks in {c['episodes']} episodes; factual outcome vs "
            f"rollout of the executed option {c['factual_matches_rollout']:.1e}"
        )
    for entry in report["budgets"]:
        lines.append(f"{entry['blocks']} blocks ({entry['link_hours']:.0f} h of link time)")
        for name, pipeline in entry["pipelines"].items():
            u = entry["contrasts"][f"{name}_vs_fixed"]["utility"]
            t = u["family_t_interval95"]
            margins = ",".join(
                "never" if s["margin"] == NEVER else f"{s['margin']:g}" for s in pipeline["seeds"]
            )
            lines.append(
                f"  {name}: offline advantage {pipeline['offline_advantage']:+.3f} corr {pipeline['correlation']:.2f}"
                f"  closed loop {u['mean']:+.3f} family t [{t[0]:+.3f}, {t[1]:+.3f}] {u['positive_families']}/{u['families']}"
                f"  margins {margins}"
            )
    return "\n".join(lines)
