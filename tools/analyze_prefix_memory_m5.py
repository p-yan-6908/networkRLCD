"""Registered M5 BWE distribution tests only. No predictor/state/controller fitting."""
from __future__ import annotations
import importlib.util
import json
import subprocess
from pathlib import Path
import numpy as np
REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("m5_frozen_runner",REPO/"tools/measure_prefix_memory_m5.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
SUMMARY=REPO/"reports/native-prefix-memory-m5-summary.json"


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
    uncertainty = bootstrap(a, b, 20261116 + content_index * 10 + m.ENDPOINTS.index(endpoint))
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

def analyze():
    m.verify()
    if SUMMARY.exists():
        raise ValueError("preserve completed M5 analysis")
    p,index=m.v.core.check_capture_integrity(m.ROOT)
    g=m.v.read(m.ROOT/"prefix_memory_qualification_gate.json")
    assert g["protocol_sha256"]==m.v.sha(m.CONFIG)
    assert g["capture_index_sha256"]==m.v.sha(m.ROOT/"capture_index.json")
    contents,rejections={},[]
    for ci,content in enumerate(sorted({r["content_id"] for r in g["sessions"]})):
        rows=[r for r in g["sessions"] if r["content_id"]==content]
        if g["passed"]:
            windows={str(t):window_analysis(rows,g["pair_suffix_fidelity"],ci,t) for t in m.ENDPOINTS}
            assert all(w["estimable"] for w in windows.values())
        else:
            windows={str(t):{"estimable":False,"convergence_passed":False,"reason":"Full prospective 84-session acquisition and 42-pair suffix gate required; no subset analysis"} for t in m.ENDPOINTS}
        primary=windows["18000"]
        rejected=primary["estimable"] and primary["randomization"]["exact_randomization_p"]<=.025
        primary.update({"primary_rejected":bool(rejected),"family_alpha":.025})
        rejections.append(bool(rejected))
        later={str(t):windows[str(t)]["randomization"]["exact_randomization_p"] for t in m.ENDPOINTS[1:] if windows[str(t)]["estimable"]}
        if rejected and len(later)==3:
            formal=holm(later)
            for t in later:windows[t]["formal_persistence"]=formal[t]
        for t in m.ENDPOINTS[1:]:
            windows[str(t)].setdefault("formal_persistence",{"gated_off":True,"reason":"Qualified primary rejection required; late p-values remain descriptive"})
        contents[content]={"windows":windows,"sustained_convergence":all(windows[str(t)]["convergence_passed"] for t in (30000,36000))}
    result={"abi":"native_prefix_memory_m5_summary_v1","registration_commit":subprocess.check_output(["git","log","-1","--format=%H","--",*m.REGISTRATION],cwd=REPO,text=True).strip(),
        "protocol_sha256":m.v.sha(m.CONFIG),"capture_index_sha256":m.v.sha(m.ROOT/"capture_index.json"),"gate_sha256":m.v.sha(m.ROOT/"prefix_memory_qualification_gate.json"),
        "full_gate_passed":g["passed"],"planned_originals":84,"sealed_sessions":sum(x["status"]=="sealed" for x in index["sessions"]),"qualified_sessions":g["qualified_sessions"],
        "verified_session_payload_files":sum(m.v.read(m.ROOT/"sessions"/x["trial"]/"integrity.json")["file_count"] for x in index["sessions"]),
        "contents":contents,"qualified_primary_rejections":sum(rejections),"prefix_effect_detected_in_at_least_one_content":any(rejections),"prefix_effect_replicated_across_both_contents":all(rejections),
        "sustained_distribution_convergence_both_contents":all(x["sustained_convergence"] for x in contents.values()),
        "bwe_response_effects_estimated":g["passed"],"delivery_qoe_action_outcomes_read":False,"outcomes_read":False,"predictors_fitted":False,"controller_state_redesigned":False,"controller_fitted":False,
        "bitrate_actions_assigned":0,"v13_reopened":False,"prior_or_instrumentation_captures_pooled":False,"native_common_support_established":False,"scope":p["source_separation"],"negative_difference_test_is_convergence":False}
    m.v.write(SUMMARY,result);m.v.write(m.ROOT/"prefix_memory_summary.json",result)
    return {"full_gate_passed":g["passed"],"primary_results":{c:{"estimable":x["windows"]["18000"]["estimable"],"p":x["windows"]["18000"].get("randomization",{}).get("exact_randomization_p"),"w1":x["windows"]["18000"].get("randomization",{}).get("observed_w1_octaves"),"sustained_convergence":x["sustained_convergence"]} for c,x in contents.items()},"predictors_fitted":False}

if __name__=="__main__":
    print(json.dumps(analyze()))
