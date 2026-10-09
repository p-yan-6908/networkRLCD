"""Hand-written reactive baselines for the typed-bitrate study (synthetic, analysis only).

The learned head has been compared with one fixed BWE ratio, selected from an option set
whose top edge it hit. This module asks how much of the head's gain a small tuned rule
recovers. Every rule picks from the same options at the same decision cadence, passes through
the same governor and sees only causal telemetry. Rule parameters are selected on the
training-family tune traces; nothing is fitted to a development or test family. A frozen run
is read and never rewritten.

The comparator declared here, before any rule ran on a panel, is the single candidate with the
best mean utility on the tune traces (``rule_best``). The winner of each kind and the best
candidate that is no less safe than the base on the tune traces (``rule_safe``) are detail.
"""

import itertools
import json
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np

from .typed_bitrate import Governor, Link, congested, load_config, split_seed, step
from .typed_bitrate_audit import KEYS, PRIMARY, contrast, cubes, panels_of
from .typed_bitrate_experiment import OUTCOMES, SPLITS, dump, panel_traces

ABI = "typed_bitrate_baselines_v1"
KINDS = ("backoff", "delay", "knee", "ladder")
EXTENDED = (1.1, 1.2, 1.35, 1.5)  # fixed ratios above the frozen option set; sweep only
_WORKER = {}


class Rule:
    """A reactive controller over the typed options.

    ``backoff`` runs ``low`` for ``hold_ms`` after causal congestion evidence, else ``high``.
    ``delay`` switches on RTT excess over the running floor with hysteresis. ``knee`` keeps
    the rate at or below ``scale`` times the delivered rate at the last congestion onset for
    ``hold_ms``. ``ladder`` steps one option down on evidence and one up after ``hold_ms``
    without any. The congestion test and the knee are the ones the head's features use.
    """

    def __init__(self, config, kind, high, low=None, hold_ms=0.0, on_ms=0.0, off_ms=0.0, scale=1.0):
        options = list(config.ratios)
        low = options[0] if low is None else low
        if kind not in KINDS or high not in options or low not in options or low >= high:
            raise ValueError(f"unsupported rule {kind} with high {high} and low {low}")
        if min(hold_ms, on_ms, off_ms) < 0 or off_ms > on_ms or scale <= 0:
            raise ValueError("rule thresholds must be nonnegative and ordered")
        self.kind, self.options, self.high, self.low = kind, options, high, low
        self.hold_ms, self.on_ms, self.off_ms, self.scale = hold_ms, on_ms, off_ms, scale
        self.max_age_ms = config.residual.max_feedback_age_ms
        self.recent = deque()
        self.rtt_floor = self.excess = self.congestion_ms = self.knee_bps = self.bwe_bps = None
        self.was_congested = self.evidence = self.backed = False
        self.level, self.moved_ms, self.ratio = options.index(high), 0.0, high

    def observe(self, sample, decide):
        """Every step, so the memory stays ordered; the ratio changes at decision epochs only."""
        now = sample.sample_ms
        if sample.telemetry_valid() and sample.feedback_age_ms <= self.max_age_ms:
            self.rtt_floor = sample.rtt_ms if self.rtt_floor is None else min(self.rtt_floor, sample.rtt_ms)
            self.excess, self.bwe_bps = sample.rtt_ms - self.rtt_floor, sample.bwe_bps
            hit = congested(sample, self.rtt_floor)
            if hit:
                window = [v for t, v in self.recent if now - t <= 2000]
                if not self.was_congested and window:  # an onset right after a feedback gap shows no knee
                    self.knee_bps = max(window)
                self.congestion_ms, self.evidence = now, True
            self.was_congested = hit
            self.recent.append((now, sample.delivery_bps))
            while now - self.recent[0][0] > 2000:
                self.recent.popleft()
        if decide:
            self.ratio = getattr(self, self.kind)(now)
            self.evidence = False
        return self.ratio

    def quiet(self, now):
        return self.congestion_ms is None or now - self.congestion_ms > self.hold_ms

    def backoff(self, now):
        return self.high if self.quiet(now) else self.low

    def delay(self, now):
        if self.excess is not None:  # a feedback gap keeps the last state
            if self.excess >= self.on_ms:
                self.backed = True
            elif self.excess <= self.off_ms:
                self.backed = False
        return self.low if self.backed else self.high

    def knee(self, now):
        if self.knee_bps is None or self.quiet(now):
            return self.high
        limit = self.scale * self.knee_bps / self.bwe_bps
        return max([r for r in self.options if r <= min(limit, self.high)], default=self.options[0])

    def ladder(self, now):
        bottom, top = self.options.index(self.low), self.options.index(self.high)
        if self.evidence:
            self.level, self.moved_ms = max(self.level - 1, bottom), now
        elif self.quiet(now) and now - self.moved_ms >= self.hold_ms:
            self.level, self.moved_ms = min(self.level + 1, top), now
        return self.options[self.level]


def candidates(config):
    """The declared rule class: options from 0.9 up may be the normal ratio, any lower one the reduced."""
    out = []
    for high in (r for r in config.ratios if r >= 0.9):
        lows = [r for r in config.ratios if r < high]
        for low, hold in itertools.product(lows, (1000, 2000, 4000, 8000)):
            out.append(dict(kind="backoff", high=high, low=low, hold_ms=hold))
        for low, on, off in itertools.product(lows, (15, 30, 50), (5, 10)):
            out.append(dict(kind="delay", high=high, low=low, on_ms=on, off_ms=off))
        for scale, hold in itertools.product((0.7, 0.8, 0.9, 1.0), (2000, 5000, 10000, 20000)):
            out.append(dict(kind="knee", high=high, scale=scale, hold_ms=hold))
        for low, hold in itertools.product(lows, (1000, 2000, 4000)):
            out.append(dict(kind="ladder", high=high, low=low, hold_ms=hold))
    return out


def label(spec):
    return spec["kind"] + "(" + ",".join(f"{k}={v:g}" for k, v in spec.items() if k != "kind") + ")"


def run_rule(config, scenario, seed, spec):
    """One closed-loop episode of a fixed ratio or a rule; the outcomes ``run_episode`` reports."""
    link, governor = Link(config, scenario, seed), Governor(config)
    rule = None if spec["kind"] == "fixed" else Rule(config, **spec)
    ratio = spec.get("ratio")
    utility, unsafe, miss, latency, rate = [], [], [], [], []
    for t in range(config.steps):
        sample = link.sample()
        if rule is not None:
            ratio = rule.observe(sample, t % config.decision_steps == 0)
        gained, outcome = step(link, governor, sample, ratio, config)
        utility.append(gained)
        unsafe.append(1 - outcome["safe"])
        miss.append(outcome["deadline_miss"])
        latency.append(outcome["latency_ms"])
        rate.append(link.actual_bps)
    return dict(
        scenario=scenario,
        seed=seed,
        utility=float(np.mean(utility)),
        unsafe=float(np.mean(unsafe)),
        deadline_miss=float(np.mean(miss)),
        latency_p95_ms=float(np.quantile(latency, 0.95)),
        rate_mbps=float(np.mean(rate) / 1e6),
    )


def _init(config):
    _WORKER["config"] = config


def _task(task):
    return run_rule(_WORKER["config"], *task)


def run_rules(config, tasks):
    if config.workers == 1 or len(tasks) < 4:
        return [run_rule(config, *task) for task in tasks]
    with ProcessPoolExecutor(config.workers, initializer=_init, initargs=(config,)) as pool:
        return list(pool.map(_task, tasks, chunksize=32))


def tune_traces(config):
    """The traces the base ratio was selected on."""
    families = config.train_scenarios
    return [
        (families[i % len(families)], split_seed(config.seed, "tune", i)) for i in range(config.tune_episodes)
    ]


def sweep(config, specs):
    traces = tune_traces(config)
    results = run_rules(config, [(s, seed, spec) for spec in specs for s, seed in traces])
    table = []
    for i, spec in enumerate(specs):
        rows = results[i * len(traces) : (i + 1) * len(traces)]
        table.append(
            dict(
                name=label(spec),
                spec=spec,
                utility=float(np.mean([r["utility"] for r in rows])),
                unsafe=float(np.mean([r["unsafe"] for r in rows])),
            )
        )
    return table


def tune(config):
    """Every candidate on the tune traces: the winner of each kind, overall, and under the base's risk."""
    fixed = sweep(config, [dict(kind="fixed", ratio=r) for r in config.ratios])
    rules = sweep(config, candidates(config))
    base = next(row for row in fixed if row["spec"]["ratio"] == config.base_ratio)

    def best(rows):
        return max(rows, key=lambda row: row["utility"]) if rows else None

    selected = {f"rule_{kind}": best([r for r in rules if r["spec"]["kind"] == kind]) for kind in KINDS}
    selected["rule_best"] = best(rules)
    selected["rule_safe"] = best([r for r in rules if r["unsafe"] <= base["unsafe"]])
    return dict(
        traces=config.tune_episodes,
        candidates=len(rules),
        fixed=fixed,
        best_fixed=best(fixed)["spec"]["ratio"],
        base=base,
        selected=selected,
        rules=sorted(rules, key=lambda row: -row["utility"]),
    )


def extended(config):
    """Fixed ratios above the option set on the tune traces, with the governor ceiling raised to match.

    The ceiling is the largest option times the estimate, so ratios inside the frozen set must
    score the same under either ceiling; ``ceiling_effect`` is the largest difference found.
    """
    wide = replace(config, ratios=sorted({*config.ratios, *EXTENDED}))
    table = sweep(wide, [dict(kind="fixed", ratio=r) for r in wide.ratios])
    frozen = {
        row["spec"]["ratio"]: row
        for row in sweep(config, [dict(kind="fixed", ratio=r) for r in config.ratios])
    }
    effect = max(
        abs(row["utility"] - frozen[row["spec"]["ratio"]]["utility"])
        for row in table
        if row["spec"]["ratio"] in frozen
    )
    return wide, dict(ratios=wide.ratios, sweep=table, ceiling_effect=float(effect))


def panel(config, specs, split):
    """The frozen panel's traces under each named spec, as episode rows the audit cubes accept."""
    traces = panel_traces(config, split)
    rows = []
    for name, spec in specs.items():
        results = run_rules(config, [(s, trace, spec) for s, _, trace in traces])
        rows += [dict(r, method=name, model_seed=None, trace_seed=t[1]) for r, t in zip(results, traces)]
    return rows


def compare(config, families, cube, wide, rng, samples, margin=None):
    base = f"fixed_{config.base_ratio:.2f}"
    rules = [n for n in cube if n.startswith("rule_")]
    pairs = {f"{rule}_vs_train_fixed": (rule, base) for rule in rules}
    pairs.update({"head_vs_train_fixed": (PRIMARY, base), "oracle_vs_train_fixed": ("oracle", base)})
    for rule in ("rule_best", "rule_safe"):
        if rule in cube:
            pairs.update({f"head_vs_{rule}": (PRIMARY, rule), f"oracle_vs_{rule}": ("oracle", rule)})
    groups = dict(panels_of(config, families))
    if margin is not None:  # only where a registration declared the subset before the panel ran
        headroom = (cube["oracle"]["utility"] - cube[base]["utility"]).mean(axis=(1, 2))
        groups["sensitive"] = [i for i in groups["all"] if headroom[i] >= margin]
    out = {}
    for name, index in groups.items():
        if not index:
            continue
        out[name] = dict(
            families=[families[i] for i in index],
            contrasts={
                pair: {
                    k: contrast(cube[a][k][index] - cube[b][k][index], rng, samples)
                    for k in ("utility", "unsafe")
                }
                for pair, (a, b) in pairs.items()
            },
            by_family={
                method: {k: [float(v) for v in cube[method][k][index].mean(axis=(1, 2))] for k in KEYS}
                for method in (base, *rules, PRIMARY, "oracle")
            },
            wide_fixed={
                method.removeprefix("wide_"): float(cube[method]["utility"][index].mean()) for method in wide
            },
        )
    return out


def audit(run, out, samples=5000):
    """Tune the rule class on training families, then replay each frozen panel's traces under it."""
    run, out = Path(run), Path(out)
    if out.exists():
        raise FileExistsError(out)
    config = load_config(run / "config.json")
    if config.base_ratio is None:
        raise ValueError("the run's config must record its selected base ratio")
    tuning = tune(config)
    wide, sweep_wide = extended(config)
    specs = {name: row["spec"] for name, row in tuning["selected"].items() if row is not None}
    registered = json.loads((run / "report.json").read_text()).get("transfer", {}).get("registration", {})
    if "rule_best" in registered and registered["rule_best"] != specs.get("rule_best"):
        raise ValueError("the tuned rule differs from the registered comparator")
    specs["replay_base"] = dict(kind="fixed", ratio=config.base_ratio)
    report = dict(abi=ABI, run=str(run), synthetic_only=True, tuning=tuning, extended=sweep_wide, panels={})
    out.mkdir(parents=True)
    for split in SPLITS:
        path = run / f"{split}_episodes.json"
        if not path.exists():
            continue
        frozen = json.loads(path.read_text())
        rows = panel(config, specs, split)
        above = {f"wide_{r:.2f}": dict(kind="fixed", ratio=r) for r in wide.ratios}
        rows += panel(wide, above, split)
        reference = {
            (r["scenario"], r["trace_seed"]): r
            for r in frozen
            if r["method"] == f"fixed_{config.base_ratio:.2f}"
        }
        pairing = max(
            abs(r[k] - reference[(r["scenario"], r["trace_seed"])][k])
            for r in rows
            if r["method"] == "replay_base"
            for k in OUTCOMES
        )
        families, cube = cubes(config, frozen + [r for r in rows if r["method"] != "replay_base"], split)
        rng = np.random.default_rng(split_seed(config.seed, "baseline-audit", split))
        report["panels"][split] = dict(
            pairing_max_difference=float(pairing),
            panels=compare(
                config, families, cube, list(above), rng, samples, registered.get("sensitive_margin")
            ),
        )
        dump(out / f"{split}_rule_episodes.json", rows)
    dump(out / "report.json", report)
    return report


def headline(report):
    tuning = report["tuning"]
    lines = [f"tune: base {tuning['base']['name']} {tuning['base']['utility']:.3f}"]
    for name, row in tuning["selected"].items():
        if row is not None:
            lines.append(f"tune: {name} {row['name']} {row['utility']:.3f} unsafe {row['unsafe']:.4f}")
    wide = "  ".join(f"{r['spec']['ratio']:g}:{r['utility']:.3f}" for r in report["extended"]["sweep"])
    lines.append(f"tune: wide fixed {wide} (ceiling effect {report['extended']['ceiling_effect']:.1e})")
    for split, data in report["panels"].items():
        for name, entry in data["panels"].items():
            for pair, c in entry["contrasts"].items():
                u = c["utility"]
                t = u.get("family_t_interval95", [float("nan")] * 2)
                lines.append(
                    f"[{split}/{name}] {pair} {u['mean']:+.3f} family t [{t[0]:+.3f}, {t[1]:+.3f}]"
                    f" {u['positive_families']}/{u['families']} unsafe {c['unsafe']['mean'] * 100:+.2f} pt"
                )
    return "\n".join(lines)
