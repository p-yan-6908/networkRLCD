"""Frozen prefix/BWE distribution analysis and conditional support-state diagnostic.

No quality, action outcome, receiver-feedback or controller fitting is exposed.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
import statistics as st
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("m3_distribution_runner", REPO / "tools/measure_prefix_memory_m3.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SUMMARY = REPO / "reports/native-prefix-memory-m3-summary.json"
TRANSITIONS = ((18000, 24000), (24000, 30000), (30000, 36000))


def exact_w1(a, b, output):
    n = len(a)
    observed = float(np.mean(np.abs(np.sort(a) - np.sort(b))))
    # Global complementary swaps have identical W1; fix pair zero unswapped.
    count = 2 ** (n - 1)
    null = np.empty(count)
    bit = np.arange(n - 1, dtype=np.uint64)
    for start in range(0, count, 16384):
        ids = np.arange(start, min(start + 16384, count), dtype=np.uint64)
        swaps = np.zeros((len(ids), n), dtype=bool)
        swaps[:, 1:] = ((ids[:, None] >> bit) & 1) == 1
        pa = np.sort(np.where(swaps, b, a), axis=1)
        pb = np.sort(np.where(swaps, a, b), axis=1)
        null[start:start + len(ids)] = np.mean(np.abs(pa - pb), axis=1)
    np.savez_compressed(output, w1=null, paired_ascending=a, paired_descending=b,
        complementary_weight=np.array(2), swaps=np.array(2 ** n))
    return {"observed_w1_octaves": observed, "exact_randomization_p": float(np.mean(null >= observed - 1e-12)),
        "enumerated_unique_complement_classes": count, "equally_weighted_full_allocations": 2 ** n,
        "sharp_null_reference_95pct": np.quantile(null, [.025, .975]).tolist(),
        "reference_file": output.relative_to(m.ROOT).as_posix(), "reference_sha256": m.v.sha(output)}


def bootstrap(a, b, seed):
    rng = np.random.default_rng(seed)
    ids = rng.integers(0, len(a), (10000, len(a)))
    aa, bb = a[ids], b[ids]
    mean_delta = np.mean(bb - aa, axis=1)
    w1 = np.mean(np.abs(np.sort(aa, axis=1) - np.sort(bb, axis=1)), axis=1)
    return {"paired_mean_95pct": np.quantile(mean_delta, [.025, .975]).tolist(),
        "w1_95pct": np.quantile(w1, [.025, .975]).tolist(), "w1_upper_975": float(np.quantile(w1, .975)),
        "replicates": 10000, "seed": seed,
        "limits": "Pair bootstrap of repeated fixed-recipe captures; not independent-source or broad network population uncertainty."}


def holm(values, alpha=.025):
    ordered = sorted(values.items(), key=lambda p: p[1])
    out, running, allowed = {}, 0.0, True
    for i, (key, value) in enumerate(ordered):
        running = max(running, min(1, (len(ordered) - i) * value))
        allowed &= value <= alpha / (len(ordered) - i)
        out[key] = {"adjusted_p": running, "rejected": bool(allowed), "family_alpha": alpha}
    return out


def window_analysis(content_rows, fidelity, content_index, endpoint):
    pairs = {}
    for r in content_rows:
        pairs.setdefault(r["pair_id"], {})[r["prefix"]] = r
    qualified = all(r["passed"] and r["windows"].get(str(endpoint), {}).get("passed") for r in content_rows)
    qualified &= len(content_rows) == 42 and len(pairs) == 21 and all(fidelity[p][str(endpoint)]["passed"] for p in pairs)
    if not qualified:
        return {"estimable": False, "original_sessions": 42,
            "qualified_session_histories": sum(r["passed"] and r["windows"].get(str(endpoint), {}).get("passed", False) for r in content_rows),
            "qualified_fidelity_pairs": sum(fidelity[p][str(endpoint)]["passed"] for p in pairs),
            "reason": "Every original session/history and suffix-fidelity pair is required; no replacements or subset analysis.", "convergence_passed": False}
    ordered = sorted(pairs)
    a = np.array([pairs[p]["ascending_prefix"]["windows"][str(endpoint)]["x"] for p in ordered])
    b = np.array([pairs[p]["descending_prefix"]["windows"][str(endpoint)]["x"] for p in ordered])
    reference = m.ROOT / f"randomization-content{content_index}-t{endpoint}.npz"
    if reference.exists():
        raise ValueError("preserve completed exact randomization reference")
    randomization = exact_w1(a, b, reference)
    uncertainty = bootstrap(a, b, 20261109 + content_index * 10 + m.ENDPOINTS.index(endpoint))
    spread_a, spread_b = float(np.ptp(a)), float(np.ptp(b))
    winf = float(np.max(np.abs(np.sort(a) - np.sort(b))))
    components = {"every_original_session_history_and_fidelity_passed": True,
        "ascending_full_spread_at_most_025": spread_a <= .25,
        "descending_full_spread_at_most_025": spread_b <= .25, "w_infinity_at_most_025": winf <= .25,
        "paired_mean_interval_inside_margin": uncertainty["paired_mean_95pct"][0] >= -.25 and uncertainty["paired_mean_95pct"][1] <= .25,
        "w1_upper_975_at_most_025": uncertainty["w1_upper_975"] <= .25}
    return {"estimable": True, "pairs": [{"pair": p, "ascending_x": float(x), "descending_x": float(y),
            "descending_minus_ascending": float(y - x)} for p, x, y in zip(ordered, a, b, strict=True)],
        "ascending_x": a.tolist(), "descending_x": b.tolist(), "paired_mean_octaves": float(np.mean(b - a)),
        "paired_median_octaves": float(np.median(b - a)),
        "ascending_sample_sd_octaves": float(np.std(a, ddof=1)), "descending_sample_sd_octaves": float(np.std(b, ddof=1)),
        "ascending_full_spread_octaves": spread_a, "descending_full_spread_octaves": spread_b,
        "ascending_order_statistics": np.sort(a).tolist(), "descending_order_statistics": np.sort(b).tolist(),
        "w_infinity_octaves": winf, "randomization": randomization, "uncertainty": uncertainty,
        "convergence_components": components, "convergence_passed": all(components.values()),
        "maximum_suffix_exposure_difference_octaves": max(fidelity[p][str(endpoint)]["maximum_exposure_log2_difference"] for p in ordered)}


def kernel_prediction(x_train, z_train, y_train, x_test, z_test, augmented):
    raw = np.exp(-.5 * ((x_train[:, None] - x_train[None, :]) / .25) ** 2)
    test = np.exp(-.5 * ((x_test[:, None] - x_train[None, :]) / .25) ** 2)
    if augmented:
        mean, scale = np.mean(z_train, axis=0), np.std(z_train, axis=0)
        scale[scale < 1e-12] = 1
        z, zz = (z_train - mean) / scale, (z_test - mean) / scale
        d = z.shape[1]
        raw += np.exp(-.5 * np.sum((z[:, None, :] - z[None, :, :]) ** 2, axis=2) / d)
        test += np.exp(-.5 * np.sum((zz[:, None, :] - z[None, :, :]) ** 2, axis=2) / d)
    center = float(np.mean(y_train))
    coefficients = np.linalg.solve(raw + .1 * np.eye(len(x_train)), y_train - center)
    return center + test @ coefficients


def state_evaluation(content_rows, windows, content_index):
    if not all(windows[str(t)]["estimable"] for t in m.ENDPOINTS):
        return {"estimable": False, "reason": "All original current/future histories and fidelity checks are required", "candidate_passed": False}
    pairs = sorted({r["pair_id"] for r in content_rows})
    rows = sorted(content_rows, key=lambda r: (r["pair_id"], r["prefix"]))
    results, pair_losses = {}, []
    for now, future in TRANSITIONS:
        x = np.array([r["windows"][str(now)]["x"] for r in rows])
        z = np.array([r["windows"][str(now)]["state_extra"] for r in rows])
        y = np.array([r["windows"][str(future)]["x"] for r in rows])
        predicted = {"raw": np.empty(len(rows)), "augmented": np.empty(len(rows))}
        for pair in pairs:
            held = np.array([r["pair_id"] == pair for r in rows])
            for model, augmented in (("raw", False), ("augmented", True)):
                predicted[model][held] = kernel_prediction(x[~held], z[~held], y[~held], x[held], z[held], augmented)
        losses = {name: (p - y) ** 2 for name, p in predicted.items()}
        rmse = {name: float(np.sqrt(np.mean(loss))) for name, loss in losses.items()}
        residual_prefix = {}
        for name, prediction in predicted.items():
            errors = y - prediction
            differences = []
            for pair in pairs:
                a = next(i for i, r in enumerate(rows) if r["pair_id"] == pair and r["prefix"] == "ascending_prefix")
                b = next(i for i, r in enumerate(rows) if r["pair_id"] == pair and r["prefix"] == "descending_prefix")
                differences.append(errors[b] - errors[a])
            residual_prefix[name] = {"paired_residual_prefix_mean_octaves": float(np.mean(differences)),
                "pair_residual_differences": [float(d) for d in differences],
                "causal_conditional_sufficiency_test": False}
        results[f"{now}_{future}"] = {"rmse_octaves": rmse, "residual_prefix_diagnostic": residual_prefix,
            "predictions": [{"trial": r["trial"], "pair": r["pair_id"], "prefix": r["prefix"], "current_x": float(xx),
                "future_x": float(yy), "raw_prediction": float(rr), "augmented_prediction": float(aa)}
                for r, xx, yy, rr, aa in zip(rows, x, y, predicted["raw"], predicted["augmented"], strict=True)]}
        pair_losses.append(np.array([[np.mean(losses[name][[i for i, r in enumerate(rows) if r["pair_id"] == pair]])
            for name in ("raw", "augmented")] for pair in pairs]))
    average = np.mean(pair_losses, axis=0)
    raw_rmse, aug_rmse = np.sqrt(np.mean(average, axis=0))
    rng = np.random.default_rng(20261110 + content_index)
    ids = rng.integers(0, len(pairs), (10000, len(pairs)))
    loss_diff = np.mean((average[:, 1] - average[:, 0])[ids], axis=1)
    interval = np.quantile(loss_diff, [.025, .975]).tolist()
    improvement = float(1 - aug_rmse / raw_rmse) if raw_rmse > 0 else None
    components = {"content_rmse_improvement_at_least_20pct": improvement is not None and improvement >= .2,
        "no_transition_worsens_more_than_10pct": all(t["rmse_octaves"]["augmented"] <= 1.1 * t["rmse_octaves"]["raw"] for t in results.values()),
        "loss_difference_upper_975_below_zero": interval[1] < 0}
    return {"estimable": True, "transitions": results, "equal_transition_raw_rmse_octaves": float(raw_rmse),
        "equal_transition_augmented_rmse_octaves": float(aug_rmse), "relative_rmse_improvement": improvement,
        "paired_squared_loss_difference_95pct": interval, "candidate_components": components,
        "candidate_passed": all(components.values()), "support_prediction_only": True,
        "limits": "Out-of-pair future BWE prediction on reused development; no causal/Markov sufficiency, action value or controller claim."}


def analyze():
    m.verify()
    if SUMMARY.exists():
        raise ValueError("preserve completed M3 analysis")
    p, index = m.v.core.check_capture_integrity(m.ROOT)
    g = m.v.read(m.ROOT / "mechanism_qualification_gate.json")
    assert g["protocol_sha256"] == m.v.sha(m.CONFIG)
    assert g["capture_index_sha256"] == m.v.sha(m.ROOT / "capture_index.json")
    contents, primary_rejections = {}, []
    content_ids = sorted({r["content_id"] for r in g["sessions"]})
    for ci, content in enumerate(content_ids):
        rows = [r for r in g["sessions"] if r["content_id"] == content]
        windows = {str(t): window_analysis(rows, g["pair_suffix_fidelity"], ci, t) for t in m.ENDPOINTS}
        primary = windows["18000"]
        rejected = primary["estimable"] and primary["randomization"]["exact_randomization_p"] <= .025
        primary["primary_rejected"] = bool(rejected)
        primary["family_alpha"] = .025
        primary_rejections.append(bool(rejected))
        later = {str(t): windows[str(t)]["randomization"]["exact_randomization_p"] for t in m.ENDPOINTS[1:] if windows[str(t)]["estimable"]}
        if rejected and len(later) == 3:
            formal = holm(later)
            for t in later:
                windows[t]["formal_persistence"] = formal[t]
        for t in m.ENDPOINTS[1:]:
            windows[str(t)].setdefault("formal_persistence", {"gated_off": True, "reason": "Qualified primary rejection and all three later tests required; late p-values remain descriptive."})
        contents[content] = {"windows": windows,
            "sustained_convergence": all(windows[str(t)]["convergence_passed"] for t in (30000, 36000))}
    state_enabled = any(primary_rejections)
    state = {}
    if state_enabled:
        for ci, content in enumerate(content_ids):
            state[content] = state_evaluation([r for r in g["sessions"] if r["content_id"] == content], contents[content]["windows"], ci)
    state_candidate = state_enabled and len(state) == 2 and all(r["candidate_passed"] for r in state.values())
    result = {"abi": "native_prefix_memory_m3_summary_v1", "registration_commit": subprocess.check_output(["git", "log", "-1", "--format=%H", "--", *m.REGISTRATION], cwd=REPO, text=True).strip(),
        "protocol_sha256": m.v.sha(m.CONFIG), "capture_index_sha256": m.v.sha(m.ROOT / "capture_index.json"),
        "gate_sha256": m.v.sha(m.ROOT / "mechanism_qualification_gate.json"), "planned_sessions": 84,
        "sealed_sessions": sum(s["status"] == "sealed" for s in index["sessions"]), "qualified_sessions": g["qualified_sessions"],
        "technical_gate_passed": g["passed"], "verified_session_files": sum(m.v.read(m.ROOT / "sessions" / s["trial"] / "integrity.json")["file_count"] for s in index["sessions"]),
        "contents": contents, "qualified_primary_rejections": sum(primary_rejections),
        "prefix_effect_detected_in_at_least_one_content": any(primary_rejections),
        "prefix_effect_replicated_across_both_contents": all(primary_rejections),
        "sustained_distribution_convergence_both_contents": all(c["sustained_convergence"] for c in contents.values()),
        "state_evaluation_enabled": state_enabled, "state_evaluation": state,
        "augmented_state_development_candidate_passed": bool(state_candidate),
        "outcomes_read": False, "bitrate_actions_assigned": 0, "controller_fitted": False,
        "causal_state_sufficiency_established": False, "native_common_support_established": False,
        "v13_reopened": False, "prior_or_synthetic_sources_pooled": False,
        "scope": p["source_separation"], "negative_difference_test_is_convergence": False}
    m.v.write(SUMMARY, result)
    m.v.write(m.ROOT / "prefix_memory_summary.json", result)
    return {"qualified_sessions": g["qualified_sessions"], "primary_results": {c: {"estimable": r["windows"]["18000"]["estimable"],
        "p": r["windows"]["18000"].get("randomization", {}).get("exact_randomization_p"),
        "w1": r["windows"]["18000"].get("randomization", {}).get("observed_w1_octaves"),
        "sustained_convergence": r["sustained_convergence"]} for c, r in contents.items()},
        "state_evaluation_enabled": state_enabled, "state_candidate_passed": bool(state_candidate), "outcomes_read": False}


if __name__ == "__main__":
    print(json.dumps(analyze()))
