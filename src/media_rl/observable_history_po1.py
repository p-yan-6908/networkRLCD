"""PO1 frozen, simple predictive assay. No policy or controller implementation.

Only `synthetic_episode` sees a simulator. Observable inputs are snapshotted
before hindsight labels. No native telemetry is loaded by this module.
"""
from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import asdict

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import expit

from .typed_bitrate import Governor, Link, TypedConfig, step


def namespaced_seed(namespace, *parts):
    key = namespace + ":" + ":".join(map(str, parts))
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "little")


def channels(sample, floor):
    """Values known at sample_ms; invalid remote reports have explicit masks."""
    raw = [sample.bwe_bps, sample.delivery_bps, sample.rtt_ms,
           sample.requested_bps, sample.actual_bps]
    present = [v is not None and math.isfinite(v) and v >= 0 for v in raw]
    for j in (1, 2):
        present[j] = present[j] and sample.valid and sample.feedback_age_ms <= 500
    values = [0.0] * 5
    for j, (value, valid) in enumerate(zip(raw, present, strict=True)):
        if valid:
            values[j] = value / 200 if j == 2 else math.log2(max(floor, value) / 500000)
    return values, list(map(float, present))


def causal_features(history, design):
    """Past-only summary and ordered lags, with availability audit evidence."""
    now = history[-1]["sample_ms"]
    current = history[-1]
    recent = [s for s in history if now - design["summary_window_ms"] <= s["sample_ms"] <= now]
    assert len(recent) >= design["minimum_summary_samples"]
    instant = current["values"] + current["masks"]
    means, slopes, missing = [], [], []
    for j in range(5):
        valid = [s for s in recent if s["masks"][j]]
        missing.append(1 - len(valid) / len(recent))
        if len(valid) < 3:
            means.append(0.0)
            slopes.append(0.0)
            continue
        x = np.array([(s["sample_ms"] - now) / 1000 for s in valid])
        y = np.array([s["values"][j] for s in valid])
        means.append(float(y.mean()))
        slopes.append(float(np.sum((x - x.mean()) * (y - y.mean())) / np.sum((x - x.mean()) ** 2)))
    summary = instant + means + slopes + missing
    ordered, audits = [], []
    for lag in design["lag_ms"][1:]:
        cutoff = now - lag
        eligible = [s for s in history if s["sample_ms"] <= cutoff]
        chosen = eligible[-1] if eligible else None
        available = chosen is not None and cutoff - chosen["sample_ms"] <= design["maximum_lag_age_ms"]
        ordered.extend(chosen["values"] + chosen["masks"] if available else [0.0] * 10)
        audits.append({"cutoff_ms": cutoff, "source_ms": chosen["sample_ms"] if available else None})
    assert all(a["source_ms"] is None or a["source_ms"] <= a["cutoff_ms"] <= now for a in audits)
    return {"instant_linear": instant, "summary_linear": summary, "history_linear": summary + ordered}, {
        "persistence": 0.0,
        "trailing_mean": means[0] - current["values"][0],
        "clipped_trend": float(np.clip(slopes[0], -.25, .25)) * 2.55,
    }, {"decision_ms": now, "latest_feature_receipt_ms": now, "lags": audits,
        "summary_first_ms": recent[0]["sample_ms"], "summary_samples": len(recent)}


def branch(link, governor, sample, ratio, config, *, factual=False):
    """Offline oracle, only called after causal_features has returned."""
    twin, rules = link.fork(), copy.copy(governor)
    current, utilities, unsafe, future_bwe = sample, [], [], []
    for k in range(config.horizon_steps):
        chosen = ratio if factual or k < config.commit_steps else config.base_ratio
        utility, outcome = step(twin, rules, current, chosen, config)
        utilities.append(utility)
        unsafe.append(1 - outcome["safe"])
        current = twin.sample()
        future_bwe.append(math.log2(current.bwe_bps / 500000))
    return {"utility": float(np.mean(utilities)), "unsafe_fraction": float(np.mean(unsafe)),
            "future_bwe_mean": float(np.mean(future_bwe)), "future_bwe_min": min(future_bwe)}


def synthetic_episode(design, replication, role, family, episode):
    sim = design["simulation"]
    seed = namespaced_seed(design["seed_namespace"], replication, role, family, episode)
    config = TypedConfig(steps=sim["steps"], dt_ms=sim["dt_ms"], bwe=sim["bwe"],
                         base_ratio=sim["base_ratio"], ratios=sim["ratios"],
                         encoder_up_ms=sim["encoder_up_ms"], encoder_down_ms=sim["encoder_down_ms"],
                         switch_weight=sim["switch_weight"], commit_ms=sim["commit_ms"], tail_ms=sim["tail_ms"])
    link, governor = Link(config, family, seed), Governor(config)
    trace = link.env.trace
    digest = hashlib.sha256()
    for name in ("capacity", "base_rtt", "loss", "jitter", "feedback", "burst", "buffer_scale"):
        digest.update(np.asarray(getattr(trace, name)).tobytes())
    trace_sha = digest.hexdigest()
    episode_id = f"po1-r{replication}-{role}-{family}-{episode:03d}"
    history, rows = [], []
    for _ in range(config.steps):
        sample = link.sample()
        values, masks = channels(sample, design["representation"]["log_floor_bps"])
        history.append({"sample_ms": sample.sample_ms, "values": values, "masks": masks})
        if sample.sample_ms in sim["decision_ms"]:
            features, baselines, audit = causal_features(history, design["representation"])
            # The live state must not change while producing the label.
            before = (link.now, link.env.t, link.env.queue, asdict(sample), vars(link.bwe).copy(),
                      vars(link.encoder).copy(), vars(governor).copy())
            low, high = [branch(link, governor, sample, ratio, config) for ratio in config.ratios]
            factual = branch(link, governor, sample, sim["logging_ratio"], config, factual=True)
            after = (link.now, link.env.t, link.env.queue, asdict(sample), vars(link.bwe).copy(),
                     vars(link.encoder).copy(), vars(governor).copy())
            assert before == after, "oracle mutated factual collector"
            advantage = high["utility"] - low["utility"]
            rows.append({"id": episode_id, "replication": replication, "role": role,
                         "family": family, "seed": seed, "trace_sha256": trace_sha,
                         "decision_ms": sample.sample_ms, "features": features, "baselines": baselines,
                         "causal_audit": audit, "current_bwe_log2": values[0],
                         "regression": [factual["future_bwe_mean"] - values[0], advantage],
                         "binary": [int(factual["future_bwe_min"] <= values[0] - .5),
                                    int(advantage > design["targets"]["beneficial_margin"]),
                                    int(high["unsafe_fraction"] > .1)],
                         "branch_labels_synthetic_only": {"0.65": low, "1.05": high, "factual_fixed1.05": factual}})
        step(link, governor, sample, sim["logging_ratio"], config)
    assert len(rows) == len(sim["decision_ms"])
    return rows, {"id": episode_id, "seed": seed, "trace_sha256": trace_sha, "family": family,
                  "role": role, "replication": replication, "rows": len(rows)}


def matrix(rows, model):
    return np.asarray([r["features"][model] for r in rows], dtype=float)


def standardized(x, mean, scale):
    return np.column_stack([np.ones(len(x)), (x - mean) / scale])


def class_support(rows, head):
    return {str(label): len({r["id"] for r in rows if r["binary"][head] == label}) for label in (0, 1)}


def fit_model(train, calibration, model, design):
    if model == "constant":
        x, cx = np.zeros((len(train), 0)), np.zeros((len(calibration), 0))
    else:
        x, cx = matrix(train, model), matrix(calibration, model)
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.where(scale < 1e-8, 1.0, scale)
    tx, calx = standardized(x, mean, scale), standardized(cx, mean, scale)
    penalty = np.eye(tx.shape[1]) * design["models"]["regression_penalty"]
    penalty[0, 0] = 0
    y = np.asarray([r["regression"] for r in train])
    coefficient = np.linalg.solve(tx.T @ tx + penalty, tx.T @ y)
    residuals = np.abs(np.asarray([r["regression"] for r in calibration]) - calx @ coefficient)
    by_episode = {}
    for r, error in zip(calibration, residuals, strict=True):
        by_episode.setdefault(r["id"], []).append(error)
    maximum = np.array([np.max(x, axis=0) for x in by_episode.values()])
    rank = math.ceil(design["gates"]["nominal_sequence_interval_coverage"] * (len(maximum) + 1))
    radius = np.sort(maximum, axis=0)[rank - 1] if rank <= len(maximum) else np.full(2, np.inf)
    heads = []
    gate = design["gates"]
    for head in range(3):
        support = {"train": class_support(train, head), "calibration": class_support(calibration, head)}
        qualified = (min(support["train"].values()) >= gate["minimum_positive_and_negative_train_episodes_per_binary_head"]
                     and min(support["calibration"].values()) >= gate["minimum_positive_and_negative_calibration_episodes_per_binary_head"])
        if not qualified:
            heads.append({"qualified": False, "support": support, "reason": "insufficient positive/negative episode support"})
            continue
        target = np.asarray([r["binary"][head] for r in train], dtype=float)
        lam = design["models"]["logistic_penalty"]

        def objective(beta):
            z = tx @ beta
            value = np.sum(np.logaddexp(0, z) - target * z) + lam / 2 * np.sum(beta[1:] ** 2)
            gradient = tx.T @ (expit(z) - target)
            gradient[1:] += lam * beta[1:]
            return value, gradient

        result = minimize(objective, np.zeros(tx.shape[1]), jac=True, method="L-BFGS-B",
                          options={"maxiter": design["models"]["logistic_maxiter"], "ftol": 1e-12})
        beta = result.x
        ctarget = np.asarray([r["binary"][head] for r in calibration], dtype=float)
        logits = calx @ beta
        intercept = minimize_scalar(lambda b: float(np.sum(np.logaddexp(0, logits + b) - ctarget * (logits + b))),
                                    bounds=(-10, 10), method="bounded")
        heads.append({"qualified": bool(result.success and intercept.success), "support": support,
                      "coefficient": beta.tolist(), "calibration_intercept": float(intercept.x),
                      "optimizer_message": str(result.message)})
    return {"model": model, "mean": mean.tolist(), "scale": scale.tolist(),
            "coefficient": coefficient.tolist(), "sequence_radius": radius.tolist(),
            "calibration_episodes": len(maximum), "calibration_rank": rank, "binary": heads,
            "calibration_distribution_free_ood_guarantee": False}


def predictions(rows, spec):
    x = np.zeros((len(rows), 0)) if spec["model"] == "constant" else matrix(rows, spec["model"])
    z = standardized(x, np.asarray(spec["mean"]), np.asarray(spec["scale"]))
    regression = z @ np.asarray(spec["coefficient"])
    binary = np.full((len(rows), 3), np.nan)
    for head, fitted in enumerate(spec["binary"]):
        if fitted["qualified"]:
            binary[:, head] = expit(z @ np.asarray(fitted["coefficient"]) + fitted["calibration_intercept"])
    return regression, binary


def calibration_metrics(probability, y, bins):
    if not np.isfinite(probability).all():
        return {"qualified": False, "reason": "binary head not estimable"}
    table, ece = [], 0.0
    index = np.minimum((probability * bins).astype(int), bins - 1)
    for b in range(bins):
        mask = index == b
        n = int(mask.sum())
        expected = float(probability[mask].mean()) if n else None
        observed = float(y[mask].mean()) if n else None
        if n:
            ece += n / len(y) * abs(expected - observed)
        table.append({"bin": b, "n": n, "predicted": expected, "observed": observed})
    p = np.clip(probability, 1e-12, 1 - 1e-12)
    return {"qualified": True, "rows": len(y), "positive_rows": int(y.sum()),
            "accuracy": float(np.mean((p >= .5) == y)), "brier": float(np.mean((p - y) ** 2)),
            "log_loss": float(np.mean(-y * np.log(p) - (1 - y) * np.log1p(-p))),
            "ece": float(ece), "bins": table}


def wilson_upper(errors, n):
    if not n:
        return 1.0
    z = 1.6448536269514722
    p = errors / n
    return float((p + z*z / (2*n) + z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1 + z*z/n))
