"""Register, collect, lock and evaluate PO1; never load closed native telemetry."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import scipy

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from media_rl.observable_history_po1 import (calibration_metrics, fit_model, namespaced_seed,
                                           predictions, synthetic_episode, wilson_upper)

CACHE = Path.home() / ".cache/networkrlcd"
ROOT = CACHE / "partial-observability-po1"
CONFIG = REPO / "configs/partial_observability_po1.json"
DATA = REPO / "data/partial-observability-po1"
REGISTRATION = DATA / "registration.json"
FREEZE = DATA / "prior-freeze-sha256.json"
RESERVATION = DATA / "native-reservation.json"
SOURCES = ["src/media_rl/observable_history_po1.py", "tools/partial_observability_po1.py",
           "configs/partial_observability_po1.json", "docs/PARTIAL_OBSERVABILITY_PO1_PLAN.md",
           "data/partial-observability-po1/prior-freeze-sha256.json",
           "data/partial-observability-po1/native-reservation.json",
           "data/partial-observability-po1/draft-01-registration.json",
           "data/partial-observability-po1/draft-01-supersession.json"]
MODELS = ("constant", "instant_linear", "summary_linear", "history_linear")


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def inventory():
    return {n: sha(REPO / n) for n in SOURCES}


def prepare():
    assert not REGISTRATION.exists() and not ROOT.exists(), "preserve existing registration"
    design = read(CONFIG)
    old = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", design["anchor_commit"]], cwd=REPO, text=True).splitlines()
    prior = {}
    for name in old:
        blob = subprocess.check_output(["git", "show", design["anchor_commit"] + ":" + name], cwd=REPO)
        assert hashlib.sha256(blob).hexdigest() == sha(REPO / name), name
        prior[name] = sha(REPO / name)
    write(FREEZE, {"anchor_commit": design["anchor_commit"], "files": prior,
                   "closed_native_panels_decoded": False})
    content = {}
    for name in ("data/native-v11d/content_sources.json", "data/native-v12/content_sources.json"):
        for c in read(REPO / name)["sources"]:
            content[c["content_id"]] = {**c, "manifest": name, "manifest_sha256": sha(REPO / name)}
    profiles, family_sources = {}, {}
    for name in ("data/native-v11d/network_profiles.json", "data/native-v12/network_profiles.json"):
        source = read(REPO / name)
        for p in source["profiles"]:
            family = p.get("network_family", p.get("family_id"))
            profiles.setdefault(family, []).append({**p, "manifest": name, "manifest_sha256": sha(REPO / name)})
        family_sources.update(source["families"])
    reservation, content_sources, network_sources = [], {}, {}
    native = design["native_reservation"]
    for role, families in native["role_families"].items():
        for family in families:
            chosen = sorted(profiles[family], key=lambda p: p["profile_id"])
            assert len(chosen) == native["profiles_per_family"]
            network_sources[family] = family_sources[family]
            for p in chosen:
                for content_id in native["role_content"][role]:
                    c = content[content_id]
                    path = CACHE / c["clip_cache_path"]
                    assert path.stat().st_size == c["clip_bytes"] and sha(path) == c["clip_sha256"]
                    content_sources[content_id] = c
                    for rep in range(native["repeats"]):
                        reservation.append({"id": f"po1-native-{role}-{len(reservation):03d}", "role": role,
                                            "family": family, "campaign": family_sources[family]["campaign_id"],
                                            "profile": p, "content_id": content_id, "repetition": rep,
                                            "factual_only": True, "captured": False})
    assert len(reservation) == native["sessions_if_admitted"]
    write(RESERVATION, {"abi": "po1_fresh_native_factual_reservation_v1", "sessions": reservation,
                        "content_sources": content_sources, "network_sources": network_sources,
                        "new_allocation_not_a_previous_untouched_panel": True,
                        "existing_sources_reused_apparatus_not_new_independent_evidence": True,
                        "capture_requires_synthetic_pass_and_separate_registration": True})
    return register()


def register():
    assert not REGISTRATION.exists() and not ROOT.exists(), "no registration replacement"
    design = read(CONFIG)
    plan = []
    for rep in design["replications"]:
        for role, spec in design["roles"].items():
            for family in spec["families"]:
                for episode in range(spec["episodes_per_family"]):
                    plan.append({"replication": rep, "role": role, "family": family, "episode": episode,
                                 "seed": namespaced_seed(design["seed_namespace"], rep, role, family, episode)})
    assert len(plan) == 816 and len({x["seed"] for x in plan}) == len(plan)
    write(REGISTRATION, {"abi": "po1_registered_information_screen_v1", "anchor_commit": design["anchor_commit"],
                         "source_hashes": inventory(), "design_sha256": sha(CONFIG), "episodes": plan,
                         "native_reservation_sha256": sha(RESERVATION), "new_data_observed": False,
                         "native_factual_stage_conditionally_admitted": False,
                         "runtime": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}})
    return verify()


def verify():
    registration = read(REGISTRATION)
    assert registration["source_hashes"] == inventory()
    for name, digest in read(FREEZE)["files"].items():
        assert sha(REPO / name) == digest, name
    assert registration["design_sha256"] == sha(CONFIG)
    families = [set(s["families"]) for s in read(CONFIG)["roles"].values()]
    assert all(not a & b for i, a in enumerate(families) for b in families[i+1:])
    assert registration["runtime"] == {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}
    return {"verified": True, "prior_files_unchanged": len(read(FREEZE)["files"]),
            "synthetic_episodes": len(registration["episodes"]), "native_reserved": len(read(RESERVATION)["sessions"])}


def committed():
    for name in SOURCES + [str(REGISTRATION.relative_to(REPO))]:
        assert subprocess.check_output(["git", "show", "HEAD:" + name], cwd=REPO) == (REPO / name).read_bytes(), "commit before acquisition: " + name


def collect():
    verify()
    committed()
    assert not ROOT.exists(), "no rerun or replacement"
    ROOT.mkdir()
    shutil.copyfile(REGISTRATION, ROOT / "protocol.json")
    write(ROOT / "capture-start.json", {"registration_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                                        "protocol_sha256": sha(REGISTRATION), "started_unix_s": time.time(),
                                        "synthetic_only": True, "closed_native_data_opened": False})
    design, entries, paths = read(CONFIG), [], {}
    started = time.monotonic()
    # Generate all fitting/calibration shards first. Validation is never used to fit.
    for role in ("train", "calibration", "validation"):
        for rep in design["replications"]:
            for family in design["roles"][role]["families"]:
                path = ROOT / "synthetic" / role / f"r{rep}-{family}.jsonl.gz"
                path.parent.mkdir(parents=True, exist_ok=True)
                assert not path.exists()
                with gzip.open(path, "wt") as stream:
                    for episode in range(design["roles"][role]["episodes_per_family"]):
                        rows, metadata = synthetic_episode(design, rep, role, family, episode)
                        entries.append(metadata)
                        for row in rows:
                            stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
                paths[str(path.relative_to(ROOT))] = {"sha256": sha(path), "bytes": path.stat().st_size}
                assert sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file()) <= design["storage"]["maximum_raw_bytes"]
                print(json.dumps({"event": "sealed_shard", "role": role, "replication": rep, "family": family,
                                  "episodes_completed": len(entries), "seconds": round(time.monotonic() - started, 1)}), flush=True)
    assert len(entries) == len(read(REGISTRATION)["episodes"])
    assert len({e["seed"] for e in entries}) == len(entries)
    assert len({e["trace_sha256"] for e in entries}) == len(entries), "duplicate traces; do not pool"
    write(ROOT / "capture-index.json", {"protocol_sha256": sha(REGISTRATION), "episodes": entries, "shards": paths,
                                        "all_originals_complete": True, "native_sessions": 0})
    return {"episodes": len(entries), "shards": len(paths), "native_sessions": 0}


def load_role(role, replication=None):
    index = read(ROOT / "capture-index.json")
    assert index["protocol_sha256"] == sha(REGISTRATION)
    data = []
    for relative, metadata in index["shards"].items():
        path = ROOT / relative
        if Path(relative).parts[1] != role:
            continue
        # Check every byte before decoding features/targets.
        assert path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"]
        with gzip.open(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                assert row["role"] == role
                if replication is None or row["replication"] == replication:
                    data.append(row)
    return data


def lock_models():
    verify()
    assert not (ROOT / "model-lock.json").exists(), "no refit"
    spec = read(CONFIG)
    locked = {}
    for rep in spec["replications"]:
        train, cal = load_role("train", rep), load_role("calibration", rep)
        for model in MODELS:
            fitted = fit_model(train, cal, model, spec)
            path = ROOT / "models" / f"r{rep}-{model}.json"
            write(path, fitted)
            locked[str(path.relative_to(ROOT))] = sha(path)
    # Validation labels have not been decoded by this command.
    write(ROOT / "model-lock.json", {"protocol_sha256": sha(REGISTRATION), "capture_index_sha256": sha(ROOT / "capture-index.json"),
                                     "models": locked, "validation_decoded_during_fit": False,
                                     "fit_unix_s": time.time(), "controller_fitted": False})
    return {"locked_models": len(locked), "validation_decoded": False}


def episode_values(rows, values):
    result = {}
    for row, value in zip(rows, values, strict=True):
        result.setdefault((row["replication"], row["id"]), []).append(float(value))
    return {key: float(np.mean(v)) for key, v in result.items()}


def paired_comparison(rows, candidate_error, baseline_error, design, tag):
    ce, be = episode_values(rows, candidate_error), episode_values(rows, baseline_error)
    means = {}
    differences = []
    rng = np.random.default_rng(namespaced_seed(design["seed_namespace"], "bootstrap", tag))
    count = design["gates"]["paired_episode_bootstraps"]
    bootstrap = np.zeros(count)
    for rep in design["replications"]:
        keys = sorted(k for k in ce if k[0] == rep)
        delta = np.array([be[k] - ce[k] for k in keys])
        means[str(rep)] = float(delta.mean())
        differences.extend(delta.tolist())
        bootstrap += delta[rng.integers(len(delta), size=(count, len(delta)))].mean(axis=1) / len(design["replications"])
    base_mae = float(np.mean(list(be.values())))
    gain = float(np.mean(differences))
    lower, upper = np.quantile(bootstrap, [.05, .95])
    relative = gain / base_mae if base_mae > 0 else 0.0
    passed = (relative >= design["gates"]["minimum_relative_mae_improvement"] and lower > 0 and all(x > 0 for x in means.values()))
    return {"candidate_mae": float(np.mean(list(ce.values()))), "baseline_mae": base_mae,
            "absolute_improvement": gain, "relative_improvement": relative,
            "one_sided_95_lower": float(lower), "one_sided_95_upper": float(upper),
            "replication_absolute_improvement": means, "passed": bool(passed)}


def evaluate_family(rows, specs, design, family):
    gates = design["gates"]
    actual = np.asarray([r["regression"] for r in rows])
    binary = np.asarray([r["binary"] for r in rows])
    pred, probs, radii = {}, {}, {}
    for model in MODELS:
        pred[model], probs[model], radii[model] = np.zeros_like(actual), np.zeros_like(binary, dtype=float), np.zeros_like(actual)
        for rep in design["replications"]:
            mask = np.array([r["replication"] == rep for r in rows])
            sub = [r for r, ok in zip(rows, mask, strict=True) if ok]
            pred[model][mask], probs[model][mask] = predictions(sub, specs[(rep, model)])
            radii[model][mask] = specs[(rep, model)]["sequence_radius"]
    # Persistence/mean/trend forecasts apply to factual BWE only.
    factual = {name: np.asarray([r["baselines"][name] for r in rows]) for name in ("persistence", "trailing_mean", "clipped_trend")}
    comparisons = {"factual_bwe": {}, "synthetic_advantage": {}}
    candidate_error = np.abs(actual - pred["history_linear"])
    for head, target in enumerate(comparisons):
        baselines = {m: pred[m][:, head] for m in MODELS if m != "history_linear"}
        if head == 0:
            baselines.update(factual)
        for name, value in baselines.items():
            comparisons[target][name] = paired_comparison(rows, candidate_error[:, head], np.abs(actual[:, head] - value),
                                                         design, (family, target, name))
    all_metrics = {}
    for model in MODELS:
        error = np.abs(actual - pred[model])
        per_rep = {}
        sequence_coverage = []
        for rep in design["replications"]:
            mask = np.array([r["replication"] == rep for r in rows])
            rrows = [r for r, ok in zip(rows, mask, strict=True) if ok]
            rerror, radius = error[mask], np.asarray(specs[(rep, model)]["sequence_radius"])
            episode_pass = {}
            for r, er in zip(rrows, rerror, strict=True):
                episode_pass.setdefault(r["id"], []).append(er <= radius)
            seq = np.array([np.all(items, axis=0) for items in episode_pass.values()]).mean(axis=0)
            sequence_coverage.append(seq)
            interval_score = 2 * radius + 2 / .1 * np.maximum(0, rerror - radius)
            per_rep[str(rep)] = {"episodes": len(episode_pass), "mae": rerror.mean(axis=0).tolist(),
                                 "sequence_coverage": seq.tolist(), "row_coverage": (rerror <= radius).mean(axis=0).tolist(),
                                 "interval_width": (2*radius).tolist(), "mean_interval_score": interval_score.mean(axis=0).tolist(),
                                 "binary": [calibration_metrics(probs[model][mask, h], binary[mask, h], gates["calibration_bins"]) for h in range(3)]}
        bin_metrics = [calibration_metrics(probs[model][:, h], binary[:, h], gates["calibration_bins"]) for h in range(3)]
        all_metrics[model] = {"mae": error.mean(axis=0).tolist(), "sequence_coverage": np.mean(sequence_coverage, axis=0).tolist(),
                              "replications": per_rep, "binary": bin_metrics}
    hm = all_metrics["history_linear"]
    width_limits = np.array([gates["maximum_bwe_interval_width_octaves"], gates["maximum_advantage_interval_width_utility"]])
    interval_pass = (all(x >= gates["minimum_validation_sequence_coverage"] for x in hm["sequence_coverage"])
                     and all(min(r["sequence_coverage"]) >= gates["minimum_per_replication_sequence_coverage"]
                             and np.all(np.asarray(r["interval_width"]) <= width_limits) for r in hm["replications"].values()))
    constant = all_metrics["constant"]
    calibration_pass = all(m["qualified"] and b["qualified"] and m["ece"] <= gates["maximum_ece"] and m["brier"] <= b["brier"]
                           for m, b in zip(hm["binary"], constant["binary"], strict=True))
    lower = pred["history_linear"][:, 1] - radii["history_linear"][:, 1]
    claims = (lower > design["targets"]["beneficial_margin"]) & (probs["history_linear"][:, 1] >= .9) & (probs["history_linear"][:, 2] <= .1)
    episodes = {}
    for row, claim in zip(rows, claims, strict=True):
        if claim:
            incorrect = row["binary"][1] == 0 or row["binary"][2] == 1
            episodes[row["id"]] = episodes.get(row["id"], False) or incorrect
    errors, n = sum(episodes.values()), len(episodes)
    safety = {"claimed_rows": int(claims.sum()), "claimed_episodes": n, "erroneous_episodes": errors,
              "one_sided_95_wilson_upper": wilson_upper(errors, n),
              "passed": bool(n >= gates["minimum_claimed_episodes_per_validation_family"] and wilson_upper(errors, n) <= .1)}
    gate = {"mae_and_reproducibility": all(c["passed"] for head in comparisons.values() for c in head.values()),
            "useful_sequence_uncertainty": bool(interval_pass), "binary_calibration": bool(calibration_pass),
            "supported_action_discrimination": safety["passed"]}
    return {"family": family, "episodes": len({r["id"] for r in rows}), "rows": len(rows), "comparisons": comparisons,
            "metrics": all_metrics, "safety_assertions_not_actions": safety, "gates": gate,
            "passed": all(gate.values())}, {"predictions": pred, "probabilities": probs, "radii": radii, "claims": claims}


def analyze():
    verify()
    lock = read(ROOT / "model-lock.json")
    assert lock["protocol_sha256"] == sha(REGISTRATION) and lock["capture_index_sha256"] == sha(ROOT / "capture-index.json")
    for n, digest in lock["models"].items():
        assert sha(ROOT / n) == digest
    report_path = ROOT / "analysis.json"
    assert not report_path.exists(), "validation opens once; no representation search"
    write(ROOT / "validation-opened.json", {"model_lock_sha256": sha(ROOT / "model-lock.json"), "opened_unix_s": time.time()})
    rows = load_role("validation")
    design = read(CONFIG)
    specs = {(rep, model): read(ROOT / "models" / f"r{rep}-{model}.json") for rep in design["replications"] for model in MODELS}
    support = {f"r{rep}-{model}": [s["qualified"] for s in spec["binary"]] for (rep, model), spec in specs.items()}
    families = []
    predictions_path = ROOT / "validation-predictions.jsonl.gz"
    with gzip.open(predictions_path, "wt") as stream:
        for family in design["roles"]["validation"]["families"]:
            sub = [r for r in rows if r["family"] == family]
            result, detail = evaluate_family(sub, specs, design, family)
            families.append(result)
            for i, row in enumerate(sub):
                out = {"id": row["id"], "family": family, "replication": row["replication"], "decision_ms": row["decision_ms"],
                       "regression": row["regression"], "binary": row["binary"], "offline_claim": bool(detail["claims"][i]),
                       "predictions": {m: detail["predictions"][m][i].tolist() for m in MODELS},
                       "probabilities": {m: [float(v) if np.isfinite(v) else None for v in detail["probabilities"][m][i]] for m in MODELS}}
                stream.write(json.dumps(out, separators=(",", ":"), allow_nan=False) + "\n")
    counts = read(ROOT / "capture-index.json")
    assert len(rows) == 3*4*24*6
    assert {r["trace_sha256"] for r in rows}.isdisjoint({r["trace_sha256"] for r in load_role("train") + load_role("calibration")})
    passed = all(all(x) for x in support.values()) and all(f["passed"] for f in families)
    audit = {"all_originals": len(counts["episodes"]) == 816,
             "unique_episode_seeds": len({e["seed"] for e in counts["episodes"]}) == 816,
             "unique_trace_hashes": len({e["trace_sha256"] for e in counts["episodes"]}) == 816,
             "family_role_disjoint": True, "oracle_mutation_assertions_passed": True,
             "past_only_cutoffs": all(r["causal_audit"]["latest_feature_receipt_ms"] <= r["decision_ms"] and
                                      all(a["source_ms"] is None or a["source_ms"] <= a["cutoff_ms"] <= r["decision_ms"] for a in r["causal_audit"]["lags"]) for r in rows)}
    passed = passed and all(audit.values())
    report = {"abi": "po1_frozen_synthetic_screen_result_v1", "protocol_sha256": sha(REGISTRATION),
              "registration_commit": read(ROOT / "capture-start.json")["registration_commit"],
              "capture_index_sha256": sha(ROOT / "capture-index.json"), "model_lock_sha256": sha(ROOT / "model-lock.json"),
              "prediction_shard_sha256": sha(predictions_path), "audit": audit, "binary_support": support,
              "families": families, "synthetic_passed": bool(passed), "synthetic_episodes": 816,
              "native_stage_admitted": bool(passed), "native_sessions": 0, "closed_native_panels_opened": False,
              "native_counterfactual_evidence": False, "controller_fitted": False, "learned_actions_executed": 0,
              "native_reservation_untouched": True,
              "decision": "separately register fresh native factual stage" if passed else "STOP: bounded history screen failed; no model complexity escalation, native capture or policy study",
              "limitations": ["one simplified fluid/AckedBwe simulator, not native Chromium", "previously used generator definitions with new episodes",
                              "empirical calibration across disjoint families has no distribution-free OOD guarantee",
                              "negative gate is not universal history irrelevance or native scientific failure"]}
    write(report_path, report)
    write(REPO / "reports/partial-observability-po1-result.json", report)
    for name in SOURCES + [str(REGISTRATION.relative_to(REPO))]:
        target = ROOT / "provenance" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / name, target)
    return {"synthetic_passed": bool(passed), "family_gates": {f["family"]: f["gates"] for f in families},
            "native_stage_admitted": bool(passed), "decision": report["decision"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "register", "verify", "collect", "lock_models", "analyze"])
    args = parser.parse_args()
    print(json.dumps(globals()[args.command](), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
