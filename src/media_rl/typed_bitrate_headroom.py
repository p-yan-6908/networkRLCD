"""Hindsight headroom when the option set stops at or below the estimate (synthetic, development).

Native Phase N1 showed that the native actuator is a cap on the encoder: it cannot push the
encoder above the browser's own estimate. The typed studies let the simulated sender follow
ratios up to 1.05 of the estimate, and their train-selected base ratio is 1.05. This study asks
how much of what the simulator offers a controller survives when the top options are removed.
For each truncated option set it re-selects the fixed ratio on the training tune traces, then
scores every fixed ratio and the hindsight oracle on identical traces of the population panels.

No model is trained, selected or evaluated, and both panels have been read before: this is
development evidence about the simulator, not a test of any controller.
"""

import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from .typed_bitrate import load_config, split_seed
from .typed_bitrate_audit import contrast
from .typed_bitrate_experiment import dump, run_many, tune_base
from .typed_bitrate_population import names

STUDY = "typed_bitrate_headroom_v1"
DEFAULTS = dict(
    name="typed-headroom-v1",
    tops=[1.05, 1.0, 0.9],  # the highest option kept; the first is the reference
    panels={"r": list(range(29301, 29317)), "s": list(range(29401, 29417))},  # panel: its trace seeds
    samples=5000,
    below_share=0.75,  # headroom kept at or above this share: the opportunity lies below the top option
    above_share=0.5,  # headroom kept below this share, with an established loss: it lies above
)


def load_settings(path=None):
    settings = {**DEFAULTS, **(json.loads(Path(path).read_text()) if path else {})}
    if set(settings) != set(DEFAULTS):
        raise ValueError("unknown headroom study setting")
    tops = settings["tops"]
    if len(tops) < 2 or tops != sorted(set(tops), reverse=True):
        raise ValueError("tops must be distinct and descending, the reference first")
    if not settings["panels"] or any(len(set(seeds)) < 2 for seeds in settings["panels"].values()):
        raise ValueError("every panel needs at least two distinct trace seeds")
    if not 0 < settings["above_share"] < settings["below_share"] <= 1 or settings["samples"] < 1:
        raise ValueError("shares must satisfy 0 < above < below <= 1 and samples must be positive")
    return settings


def truncated(config, top):
    """The option set cut off at ``top``, with the fixed ratio re-selected on the tune traces."""
    ratios = [r for r in config.ratios if r <= top]
    if top not in config.ratios or len(ratios) < 2:
        raise ValueError("a top must be one of the options and leave at least two")
    return tune_base(replace(config, ratios=ratios, base_ratio=None))


def score(config, families, seeds):
    """Per family and trace: utility and unsafe share of every fixed ratio and of the hindsight oracle."""
    traces = [(family, seed) for family in families for seed in seeds]
    shape = (len(families), len(seeds))

    def grid(rows, key):
        return np.asarray([r[key] for r in rows], dtype=float).reshape(shape)

    out = {}
    for ratio in config.ratios:
        rows = run_many(config, None, [(f, s, dict(kind="fixed", ratio=ratio)) for f, s in traces])
        out[ratio] = dict(utility=grid(rows, "utility"), unsafe=grid(rows, "unsafe"))
    rows = run_many(config, None, [(f, s, dict(kind="oracle"), "score") for f, s in traces])
    chosen = np.bincount([d["executed"] for r in rows for d in r["decisions"]], minlength=len(config.ratios))
    out["oracle"] = dict(
        utility=grid(rows, "utility"),
        unsafe=grid(rows, "unsafe"),
        option_share=[float(v) for v in chosen / max(chosen.sum(), 1)],
    )
    return out


def reading(share, loss, settings):
    """Where the hindsight opportunity lies, by thresholds fixed before the run."""
    if share is None:  # the reference set offers no headroom to compare with
        return "mixed"
    if share >= settings["below_share"]:
        return "below"
    if share < settings["above_share"] and loss["family_t_interval95"][1] < 0:
        return "above"
    return "mixed"


def measure(config, settings, panels):
    """Headroom per truncated option set and its change against the widest set, on identical traces."""
    rng = np.random.default_rng(split_seed(config.seed, "headroom"))
    samples, sets, scores = settings["samples"], [], {}
    for top in settings["tops"]:
        tuned, tune = truncated(config, top)
        scores[top] = {name: score(tuned, families, seeds) for name, (families, seeds) in panels.items()}
        entry = dict(top=top, ratios=list(tuned.ratios), base_ratio=tuned.base_ratio, tune=tune, panels={})
        for name, scored in scores[top].items():
            base, oracle = scored[tuned.base_ratio], scored["oracle"]
            entry["panels"][name] = dict(
                fixed={
                    f"{r:g}": dict(
                        utility=float(scored[r]["utility"].mean()), unsafe=float(scored[r]["unsafe"].mean())
                    )
                    for r in tuned.ratios
                },
                base_utility=float(base["utility"].mean()),
                oracle_utility=float(oracle["utility"].mean()),
                oracle_option_share=oracle["option_share"],
                headroom=contrast((oracle["utility"] - base["utility"])[:, :, None], rng, samples),
                oracle_unsafe_points=contrast(
                    100 * (oracle["unsafe"] - base["unsafe"])[:, :, None], rng, samples
                ),
            )
        sets.append(entry)
    wide, wide_base = scores[settings["tops"][0]], sets[0]["base_ratio"]
    for entry in sets[1:]:
        entry["against_widest"] = {}
        for name, scored in scores[entry["top"]].items():
            base, oracle = scored[entry["base_ratio"]]["utility"], scored["oracle"]["utility"]
            far_base, far_oracle = wide[name][wide_base]["utility"], wide[name]["oracle"]["utility"]
            loss = contrast(((oracle - base) - (far_oracle - far_base))[:, :, None], rng, samples)
            reference = float((far_oracle - far_base).mean())
            share = float((oracle - base).mean()) / reference if reference > 0 else None
            entry["against_widest"][name] = dict(
                base=contrast((base - far_base)[:, :, None], rng, samples),
                oracle=contrast((oracle - far_oracle)[:, :, None], rng, samples),
                headroom=loss,
                oracle_minus_widest_base=contrast((oracle - far_base)[:, :, None], rng, samples),
                headroom_share=share,
                reading=reading(share, loss, settings),
            )
    return sets


def study(run, out, settings=None):
    """Headroom under truncated option sets on the population panels of a finished run's config."""
    run, out = Path(run), Path(out)
    if out.exists():
        raise FileExistsError(out)
    config, settings, started = load_config(run / "config.json"), load_settings(settings), time.time()
    panels = {name: (names(name), seeds) for name, seeds in settings["panels"].items()}
    out.mkdir(parents=True)
    dump(out / "settings.json", settings)
    report = dict(
        abi=STUDY,
        run=str(run),
        synthetic_only=True,
        development_evidence=True,
        models_trained=0,
        settings=settings,
        families={name: len(families) for name, (families, _) in panels.items()},
        sets=measure(config, settings, panels),
    )
    report["elapsed_s"] = time.time() - started
    dump(out / "report.json", report)
    return report


def headline(report):
    lines = []
    for entry in report["sets"]:
        lines.append(f"top {entry['top']:g}: fixed ratio selected on tune traces {entry['base_ratio']:g}")
        for name, panel in entry["panels"].items():
            low, high = panel["headroom"]["family_t_interval95"]
            line = (
                f"  panel {name}: fixed {panel['base_utility']:.3f}, oracle {panel['oracle_utility']:.3f}, "
                f"headroom {panel['headroom']['mean']:+.3f} [{low:+.3f}, {high:+.3f}]"
            )
            if "against_widest" in entry:
                change = entry["against_widest"][name]
                share = "n/a" if change["headroom_share"] is None else f"{change['headroom_share']:.2f}"
                line += (
                    f"; share of the widest set's headroom {share} ({change['reading']}), "
                    f"fixed {change['base']['mean']:+.3f}, oracle {change['oracle']['mean']:+.3f}, "
                    f"oracle minus widest fixed {change['oracle_minus_widest_base']['mean']:+.3f}"
                )
            lines.append(line)
    return "\n".join(lines)
