"""Causal next-epoch BWE prediction from previously read factual native summaries.

Development diagnostic only. No counterfactuals, simulator update, action-value
labels, safety probability, encoder model or policy deployment. All fitting uses
range-pilot outcomes; cross-validation groups complete sources or regimes.
"""

import argparse
import hashlib
import itertools
import json
import math
import platform
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import t

from . import native_ladder_pilot as ladder
from . import native_margin_pilot as margin
from . import native_range_pilot as native_range

ABI = "bwe_dynamics_diagnostic_v1"
FEATURES = (
    "log_bwe_over_300kbps",
    "previous_log_bwe_change",
    "previous_log_requested_over_bwe",
    "previous_observation_available",
    "log_current_requested_over_bwe",
)
MODELS = ("persistence", "momentum", "pooled_drift", "state_ridge", "cap_ridge")
PILOTS = dict(range=native_range, ladder=ladder, margin=margin)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def features(bwe, requested, epoch):
    """Read only entries available when the present cap is assigned."""
    current = bwe[epoch]
    return [
        math.log(current / 300),
        math.log(current / bwe[epoch - 1]) if epoch else 0.0,
        math.log(requested[epoch - 1] / bwe[epoch - 1]) if epoch else 0.0,
        float(epoch > 0),
        math.log(requested[epoch] / current),
    ]


def read_rows(sessions, pilot, expected_sources, expected_sessions):
    """Require a complete source × regime × arm cell matrix before extracting outcomes."""
    if len(sessions) != expected_sessions or len({s["trial_id"] for s in sessions}) != len(sessions):
        raise ValueError("incomplete sessions or duplicate trial IDs")
    sources = {s["source"] for s in sessions}
    module = PILOTS[pilot]
    n_arms = len(module.NAMES)
    regimes = set(module.REGIMES)
    counts = Counter((s["source"], s["regime"], s.get("arm", s.get("level"))) for s in sessions)
    expected = set(itertools.product(sources, regimes, range(n_arms)))
    if len(sources) != expected_sources or set(counts) != expected or len(set(counts.values())) != 1:
        raise ValueError("missing, unequal or unknown source/regime/arm cells")
    rows, aliases, changes = [], [], []
    for session in sessions:
        bwe, cap = session["estimate_kbps"], session["requested_kbps"]
        if len(bwe) != len(cap) or len(bwe) != session["holds"] or len(bwe) < 2:
            raise ValueError("unmatched or too short factual histories")
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
            for v in [*bwe, *cap]
        ):
            raise ValueError("positive finite BWE and caps are required")
        arm_index = session.get("arm", session.get("level"))
        arm = module.NAMES[arm_index]
        ratios = (
            [native_range.LEVELS[arm_index]] * len(bwe)
            if pilot == "range"
            else [module.LADDER[step] for step in session["steps"]]
        )
        if len(ratios) != len(bwe):
            raise ValueError("unmatched assigned-ratio history")
        for epoch in range(len(bwe)):
            ratio = ratios[epoch]
            if ratio is not None:
                # Histories are rounded to 0.001 kbit/s; do not call rounding an alias.
                nominal = ratio * bwe[epoch]
                if abs(cap[epoch] - min(4000.0, max(150.0, nominal))) > 0.02:
                    raise ValueError("requested cap does not match native clipping domain")
                aliases.append(
                    dict(
                        source=session["source"],
                        regime=session["regime"],
                        arm=arm,
                        trial=session["trial_id"],
                        aliased=abs(cap[epoch] - nominal) > 0.02,
                    )
                )
            elif abs(cap[epoch] - 4000.0) > 0.02:
                raise ValueError("the ceiling arm must request the native 4000 kbit/s cap")
            if epoch:
                changes.append(ratio != ratios[epoch - 1])
            if epoch == len(bwe) - 1:
                continue
            rows.append(
                dict(
                    source=session["source"],
                    regime=session["regime"],
                    arm=arm,
                    trial=session["trial_id"],
                    epoch=epoch,
                    x=features(bwe, cap, epoch),
                    y=math.log(bwe[epoch + 1] / bwe[epoch]),
                )
            )
    return rows, dict(
        share_weighting="pooled reported epochs; descriptive counts, not source-weighted prediction metrics",
        ratio_observations=len(aliases),
        alias_share=float(np.mean([r["aliased"] for r in aliases])),
        alias_share_by_arm={
            arm: float(np.mean([r["aliased"] for r in aliases if r["arm"] == arm]))
            for arm in module.NAMES
            if any(r["arm"] == arm for r in aliases)
        },
        consecutive_nominal_action_changes=sum(changes),
        consecutive_nominal_action_pairs=len(changes),
        nominal_action_change_share=float(np.mean(changes)),
    )


def weights(rows):
    """Equal cells, equal sessions within cells, and equal rows within sessions."""
    source_regimes, cell_arms, trials = defaultdict(set), defaultdict(set), defaultdict(set)
    row_count = Counter(r["trial"] for r in rows)
    for r in rows:
        source_regimes[r["source"]].add(r["regime"])
        cell_arms[r["source"], r["regime"]].add(r["arm"])
        trials[r["source"], r["regime"], r["arm"]].add(r["trial"])
    w = np.array(
        [
            1.0
            / (
                len(source_regimes)
                * len(source_regimes[r["source"]])
                * len(cell_arms[r["source"], r["regime"]])
                * len(trials[r["source"], r["regime"], r["arm"]])
                * row_count[r["trial"]]
            )
            for r in rows
        ]
    )
    if not np.isclose(w.sum(), 1.0):
        raise ValueError("unbalanced weights")
    return w


def fit(rows, penalty):
    x, y, w = np.array([r["x"] for r in rows]), np.array([r["y"] for r in rows]), weights(rows)
    drift = float(w @ y)
    fitted = dict(
        persistence=dict(kind="persist"),
        momentum=dict(kind="momentum"),
        pooled_drift=dict(kind="constant", value=drift),
    )
    for name, n in (("state_ridge", 4), ("cap_ridge", 5)):
        mean = w @ x[:, :n]
        scale = np.sqrt(w @ ((x[:, :n] - mean) ** 2))
        scale = np.where(scale > 1e-12, scale, 1.0)
        normal = (x[:, :n] - mean) / scale
        coef = np.linalg.solve(
            normal.T @ (w[:, None] * normal) + penalty * np.eye(n), normal.T @ (w * (y - drift))
        )
        fitted[name] = dict(
            kind="ridge",
            mean=mean.tolist(),
            scale=scale.tolist(),
            coef=coef.tolist(),
            intercept=drift,
            penalty=penalty,
            features=list(FEATURES[:n]),
        )
    return dict(
        models=fitted,
        training_sources=sorted({r["source"] for r in rows}),
        training_regimes=sorted({r["regime"] for r in rows}),
        rows=len(rows),
    )


def predict(fitted, rows):
    x = np.array([r["x"] for r in rows])
    out = {}
    for name, model in fitted["models"].items():
        if model["kind"] == "persist":
            out[name] = np.zeros(len(rows))
        elif model["kind"] == "momentum":
            out[name] = x[:, 1].copy()
        elif model["kind"] == "constant":
            out[name] = np.full(len(rows), model["value"])
        else:
            n = len(model["mean"])
            out[name] = ((x[:, :n] - model["mean"]) / model["scale"]) @ model["coef"] + model["intercept"]
        if not np.isfinite(out[name]).all():
            raise ValueError("nonfinite predictions")
    return out


def cross_validate(rows, key, penalty):
    predictions = {name: np.full(len(rows), np.nan) for name in MODELS}
    fits = {}
    for held in sorted({r[key] for r in rows}):
        training = [r for r in rows if r[key] != held]
        indices = [i for i, r in enumerate(rows) if r[key] == held]
        fitted = fit(training, penalty)
        if held in fitted["training_sources" if key == "source" else "training_regimes"]:
            raise ValueError("group leakage")
        fits[held] = fitted
        own = predict(fitted, [rows[i] for i in indices])
        for name in MODELS:
            predictions[name][indices] = own[name]
    if not all(np.isfinite(p).all() for p in predictions.values()):
        raise ValueError("missing out-of-fold prediction")
    return predictions, fits


def descriptive(values):
    values = np.asarray(values, dtype=float)
    mean = float(values.mean())
    half = float(t.ppf(0.975, len(values) - 1) * values.std(ddof=1) / math.sqrt(len(values)))
    return dict(mean=mean, source_interval95=[mean - half, mean + half], sources=len(values))


def score(rows, predictions):
    target = np.array([r["y"] for r in rows])
    by_source = {}
    for source in sorted({r["source"] for r in rows}):
        indices = [i for i, r in enumerate(rows) if r["source"] == source]
        w = weights([rows[i] for i in indices])
        by_source[source] = {}
        for name in MODELS:
            error = predictions[name][indices] - target[indices]
            by_source[source][name] = dict(
                mae=float(w @ np.abs(error)), mse=float(w @ (error**2)), bias=float(w @ error)
            )
    return dict(
        rows=len(rows),
        metrics={
            name: {
                metric: descriptive([s[name][metric] for s in by_source.values()])
                for metric in ("mae", "mse", "bias")
            }
            for name in MODELS
        },
        contrasts={
            f"{name} minus {baseline} MAE": descriptive(
                [s[name]["mae"] - s[baseline]["mae"] for s in by_source.values()]
            )
            for baseline in ("persistence", "state_ridge")
            for name in MODELS
            if name != baseline
        },
        by_source=by_source,
    )


def paper_tables(panels):
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Panel & Persistence & Momentum & Pooled drift & State & State + cap \\",
        r"\midrule",
    ]
    for name, panel in panels.items():
        values = [f"{panel['metrics'][model]['mae']['mean']:.3f}" for model in MODELS]
        lines.append(" & ".join([name.replace("_", " "), *values]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def run(spec_path, out):
    spec_path, out = Path(spec_path), Path(out)
    if out.exists():
        raise ValueError("fresh output directory required")
    spec = json.loads(spec_path.read_text())
    if (
        spec.get("abi") != ABI + "_spec"
        or spec.get("development_only") is not True
        or spec.get("controller_promoted") is not False
        or tuple(spec["feature_names"]) != FEATURES
        or tuple(spec["models"]) != MODELS
        or spec["state_features"] != 4
        or not math.isfinite(spec["ridge_penalty"])
        or spec["ridge_penalty"] <= 0
    ):
        raise ValueError("the fixed development diagnostic spec is required")
    rows, aliases, input_hashes = {}, {}, {}
    for pilot in PILOTS:
        path = Path(spec["inputs"][pilot]["path"])
        if sha(path) != spec["inputs"][pilot]["sha256"]:
            raise ValueError(f"changed pinned {pilot} input")
        input_hashes[str(path)] = sha(path)
        rows[pilot], aliases[pilot] = read_rows(
            json.loads(path.read_text()), pilot, spec["sources"], spec["sessions"][pilot]
        )
    if len({tuple(sorted({r["source"] for r in own})) for own in rows.values()}) != 1:
        raise ValueError("these pilot panels must share the same source identities")
    source_pred, source_fits = cross_validate(rows["range"], "source", spec["ridge_penalty"])
    regime_pred, regime_fits = cross_validate(rows["range"], "regime", spec["ridge_penalty"])
    full_fit = fit(rows["range"], spec["ridge_penalty"])
    predictions = dict(
        range_source_cv=(rows["range"], source_pred),
        range_regime_cv=(rows["range"], regime_pred),
        ladder_transfer=(rows["ladder"], predict(full_fit, rows["ladder"])),
        margin_transfer=(rows["margin"], predict(full_fit, rows["margin"])),
    )
    panels = {name: score(own, pred) for name, (own, pred) in predictions.items()}
    arrays = {}
    for name, (own, pred) in predictions.items():
        for key in ("source", "regime", "arm", "trial", "epoch", "x", "y"):
            arrays[name + "__" + key] = np.array([r[key] for r in own])
        arrays.update({name + "__" + model: values for model, values in pred.items()})
    out.mkdir(parents=True)
    np.savez_compressed(out / "predictions.npz", **arrays)
    models = dict(full_range_fit=full_fit, source_cv=source_fits, regime_cv=regime_fits)
    (out / "models.json").write_text(json.dumps(models, indent=2, sort_keys=True, allow_nan=False) + "\n")
    provenance = dict(input_hashes)
    for path in [spec_path, Path(__file__), *(Path(m.__file__) for m in PILOTS.values())]:
        key = (
            str(path.resolve().relative_to(Path.cwd()))
            if path.resolve().is_relative_to(Path.cwd())
            else str(path)
        )
        provenance[key] = sha(path)
    report = dict(
        abi=ABI,
        development_only=True,
        all_panels_previously_read=True,
        controller_promoted=False,
        native_counterfactuals=False,
        raw_replay_performed=False,
        synthetic_estimator_changed=False,
        native_controller_changed=False,
        panels=panels,
        aliasing=aliases,
        features=list(FEATURES),
        partitions=spec["partitions"],
        limitations=spec["limitations"],
        models_sha256=sha(out / "models.json"),
        predictions_sha256=sha(out / "predictions.npz"),
        paper_table_sha256=hashlib.sha256(paper_tables(panels).encode()).hexdigest(),
        input_and_code_sha256=provenance,
        runtime=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
    )
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (out / "table_bwe_dynamics.tex").write_text(paper_tables(panels))
    return dict(
        out=str(out),
        development_only=True,
        mae={
            name: {model: p["metrics"][model]["mae"]["mean"] for model in MODELS}
            for name, p in panels.items()
        },
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.spec, args.out)
    except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
