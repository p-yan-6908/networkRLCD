"""Descriptive step/episode metrics and training-seed-cluster uncertainty."""

import numpy as np


def reliability(probabilities, labels, bins=10):
    p, y = np.asarray(probabilities, dtype=float), np.asarray(labels, dtype=float)
    if (
        p.shape != y.shape
        or p.ndim != 1
        or not np.all(np.isfinite(p))
        or np.any((p < 0) | (p > 1))
        or not np.all(np.isin(y, [0, 1]))
        or bins < 1
    ):
        raise ValueError("invalid probability/label arrays")
    indices = np.minimum((p * bins).astype(int), bins - 1)
    rows = []
    for i in range(bins):
        mask = indices == i
        rows.append(
            dict(
                bin=i,
                lower=i / bins,
                upper=(i + 1) / bins,
                count=int(mask.sum()),
                confidence=float(p[mask].mean()) if mask.any() else None,
                frequency=float(y[mask].mean()) if mask.any() else None,
            )
        )
    return rows


def calibration_metrics(probabilities, labels):
    rows = reliability(probabilities, labels)
    p, y = np.asarray(probabilities, dtype=float), np.asarray(labels, dtype=float)
    if len(p) == 0:
        return dict(ece=None, brier=None, nll=None)
    ece = sum(r["count"] * abs(r["confidence"] - r["frequency"]) for r in rows if r["count"]) / len(p)
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return dict(
        ece=float(ece),
        brier=float(np.mean((np.asarray(probabilities) - y) ** 2)),
        nll=float(-np.mean(y * np.log(p) + (1 - y) * np.log1p(-p))),
    )


def risk_coverage(probabilities, labels):
    p, y = np.asarray(probabilities), np.asarray(labels)
    rows = []
    for threshold in np.linspace(0, 1, 21):
        keep = p >= threshold
        rows.append(
            dict(
                threshold=float(threshold),
                coverage=float(keep.mean()) if len(p) else 0,
                risk=float(1 - y[keep].mean()) if keep.any() else None,
                count=int(keep.sum()),
            )
        )
    return rows


def runs(flags):
    lengths, start = [], None
    for i, flag in enumerate(list(flags) + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            lengths.append(i - start)
            start = None
    return lengths


def episode_metrics(rows, dt_s):
    def arr(key):
        return np.array([r[key] for r in rows], dtype=float)

    qoe, latency, fallback, safe = arr("qoe"), arr("latency_ms"), arr("fallback").astype(bool), arr("safe")
    proposal_safe = arr("proposal_safe")
    labeled = np.array([not r.get("proposal_label_censored", False) for r in rows])
    accepted = ~fallback & labeled
    labeled_fallback = fallback & labeled
    durations = np.array(runs(fallback)) * dt_s
    confidence_rows = [
        r for r in rows if r["confidence"] is not None and not r.get("proposal_label_censored", False)
    ]
    cal = calibration_metrics(
        [r["confidence"] for r in confidence_rows], [r["proposal_safe"] for r in confidence_rows]
    )
    raw_cal = calibration_metrics(
        [r["raw_confidence"] for r in confidence_rows], [r["proposal_safe"] for r in confidence_rows]
    )
    cap = arr("capacity_mbps")
    shocks = np.flatnonzero(cap[1:] < cap[:-1] * 0.65) + 1
    recovery, censored = [], 0
    for shock in shocks:
        hits = [
            i
            for i in range(shock, len(safe) - 2)
            if np.all(safe[i : i + 3]) and np.all(arr("deadline_miss")[i : i + 3] < 0.1)
        ]
        if hits:
            recovery.append((hits[0] - shock) * dt_s)
        else:
            censored += 1
    metrics = dict(
        qoe=float(qoe.mean()),
        qoe_worst_decile=float(np.sort(qoe)[: max(1, int(np.ceil(len(qoe) * 0.1)))].mean()),
        latency_mean_ms=float(latency.mean()),
        latency_p95_ms=float(np.quantile(latency, 0.95)),
        latency_p99_ms=float(np.quantile(latency, 0.99)),
        raw_loss=float(arr("raw_loss").mean()),
        residual_loss=float(arr("residual_loss").mean()),
        deadline_miss=float(arr("deadline_miss").mean()),
        violation_rate=float(1 - safe.mean()),
        goodput_mbps=float(arr("goodput_mbps").mean()),
        bitrate_mbps=float(arr("bitrate_mbps").mean()),
        fec_overhead=float(np.mean(arr("wire_mbps") - arr("bitrate_mbps"))),
        switch_magnitude=float(arr("switch_magnitude").mean()),
        switches_per_s=float(np.count_nonzero(np.diff(arr("action"))) / (len(rows) * dt_s)),
        bitrate_cv=float(arr("bitrate_mbps").std() / max(arr("bitrate_mbps").mean(), 1e-9)),
        fallback_rate=float(fallback.mean()),
        fallback_entries=len(durations),
        fallback_mean_duration_s=float(durations.mean()) if len(durations) else 0.0,
        fallback_max_duration_s=float(durations.max()) if len(durations) else 0.0,
        fallback_end_censored=int(fallback[-1]),
        coverage=float((~fallback).mean()),
        accepted_risk=float(1 - proposal_safe[accepted].mean()) if accepted.any() else None,
        fallback_precision=float(1 - proposal_safe[labeled_fallback].mean())
        if labeled_fallback.any()
        else None,
        fallback_safe_rate=float(safe[fallback].mean()) if fallback.any() else None,
        prevented_violations=float(np.mean(labeled_fallback & (proposal_safe == 0) & (safe == 1))),
        fallback_harm=float(np.mean(labeled_fallback & (proposal_safe == 1) & (safe == 0))),
        recovery_time_s=float(np.mean(recovery)) if recovery else None,
        recovery_events=len(shocks),
        recovery_censored=censored,
        **cal,
        **{"raw_" + k: v for k, v in raw_cal.items()},
    )
    if "frames_completed" in rows[0]:
        metrics.update(
            frames_completed=sum(int(r["frames_completed"]) for r in rows),
            terminal_censored_frames=int(rows[-1]["terminal_censored_frames"]),
            proposal_labels_censored=int((~labeled).sum()),
            fec_overhead=float(np.mean(arr("parity_offered_mbit") + arr("headers_offered_mbit")) / dt_s),
        )
        if rows[0].get("proposal_label_horizon_steps", 1) > 1:
            # Different outcome windows/cohorts cannot support a prevention attribution.
            metrics["prevented_violations"] = metrics["fallback_harm"] = None
    for reason in ["low_confidence", "ood_support", "missing_feedback", "hysteresis"]:
        metrics["fallback_" + reason] = sum(r["reason"] == reason for r in rows) / len(rows)
    return metrics


def cluster_interval(values, samples=2000, seed=0):
    """Input is one mean per independent training seed, NOT individual time steps."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return dict(mean=None, low=None, high=None, n=0)
    if len(values) < 2:
        return dict(mean=float(values.mean()), low=None, high=None, n=len(values))
    rng = np.random.default_rng(seed)
    means = rng.choice(values, (samples, len(values)), replace=True).mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return dict(mean=float(values.mean()), low=float(lo), high=float(hi), n=len(values))
