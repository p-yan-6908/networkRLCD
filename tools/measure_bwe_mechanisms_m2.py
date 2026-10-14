"""Preregistered support-only history/initialization experiment; no action or outcome commands."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import random
import statistics as st
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("m2_dependencies_v13", REPO / "tools/design_native_v13.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
ROOT = v.CACHE / "native-bwe-mechanisms-m2"
DEV = v.CACHE / "native-bwe-mechanisms-m2-instrument-check"
REPLICATION = v.CACHE / "native-bwe-mechanisms-m2-replication"
CONFIG = REPO / "configs/native_bwe_mechanisms_m2.json"
REPLICATION_CONFIG = REPO / "configs/native_bwe_mechanisms_m2_replication.json"
PLAN = REPO / "docs/NATIVE_BWE_MECHANISMS_M2_PLAN.md"
RECORDER = REPO / "benchmarks/native_m2/bwe_mechanism_support_episode_m2.mjs"
SUMMARY = REPO / "reports/native-bwe-mechanisms-m2-summary.json"
SEED = 20261105
REGISTRATION = ["tools/measure_bwe_mechanisms_m2.py", str(PLAN.relative_to(REPO)), str(RECORDER.relative_to(REPO)), str(CONFIG.relative_to(REPO))]


def inventory():
    result = v.inventory()
    for name in [*REGISTRATION[:3], "tools/diagnose_bwe_mechanisms_m2.py",
        "docs/NATIVE_BWE_MECHANISMS_M2_DIAGNOSIS.md", "reports/native-bwe-mechanisms-m2-diagnosis.json",
        "reports/native-bwe-mechanisms-m2-runtime-preflight.json", "data/native-v13/sources.json"]:
        result[name] = v.sha(REPO / name)
    return result


def committed(names):
    for name in names:
        proc = subprocess.run(["git", "show", f"HEAD:{name}"], cwd=REPO, capture_output=True)
        if proc.returncode or hashlib.sha256(proc.stdout).hexdigest() != v.sha(REPO / name):
            return False
    return True


def preserve_prior():
    v.core.source_inventory = v.inventory
    checked = v.verify()
    assert not checked["confirmatory_started"]
    assert not v.read(v.SUPPORT_ROOT / "support_clock_transport_gate.json")["passed"]
    v.core.source_inventory = inventory
    v.core.RECORDER = RECORDER
    return checked


def trial(root, content, profile, pair, repeat, initial, history):
    tid = pair + "-s0-support"
    panel = v.panel_for(tid, content, profile, pair, 0, SEED, True)
    panel["episodes"][0]["support_initial_bwe_kbps"] = initial
    panel["measurement_recipe"].update({"initial_estimator_target_kbps": initial,
        "preconnection_encoder_ceiling_bps": 4000000, "history_kind": history,
        "support_only": True, "scientific_role": "reused-source mechanism development"})
    relative = f"panels/{tid}.json"
    v.write(root / relative, panel)
    return {"id": tid, "condition": "micro", "panel": relative, "panel_sha256": v.sha(root / relative),
        "pair_id": pair, "pair_slot": 0, "repetition": repeat, "support_only": True,
        "content_id": content["content_id"], "network_family": profile["family_id"],
        "network_campaign_id": profile["campaign_id"], "network_profile_id": profile["profile_id"],
        "cell_cluster": content["content_id"] + "__" + profile["family_id"],
        "initial_bwe_kbps": initial, "history_kind": history,
        "mechanism_context": content["content_id"] + f"::{history}::initial{initial}",
        "input_is_fully_measured": history == "measured_original"}


def protocol(root, trials, stage):
    p = v.protocol_for(root, trials, "support_census" if stage == "replication" else "development", SEED)
    p.update({"abi": "native_bwe_mechanisms_m2_protocol_v1", "anchor_commit": "7427f48",
        "source_hashes": inventory(), "confirmatory": False, "stage": stage,
        "source_separation": "Reused V13 content/traces, separate support-only development; hybrid prefixes and synthetic instrument checks never count as measured confirmation.",
        "startup": {"targets_kbps": [300, 1200], "native_initial_bwe_tolerance_bps": 1,
            "preconnection_and_measurement_ceiling_bps": 4000000,
            "sdp_start_parameters_and_native_bwe_required": True},
        "reliability": {"mechanism_repeats_per_context": 4, "maximum_full_repeat_spread_octaves": .25,
            "candidate_rule": "Prefer 300 only if both original measured content contexts qualify all four repeats; otherwise 1200 if both qualify; otherwise stop.",
            "replication_repeats_per_content_profile": 2, "require_all_original_attempts": True,
            "replication_cell_range_octaves": 1.0, "replication_cell_sd_octaves": .35,
            "replication_common_overlap_octaves": .5},
        "analysis": {"outcomes_read": False, "controller_fitted": False,
            "mechanism_bwe_contrasts_only": True, "population_ci": False,
            "main_factor_randomization_reference": "256 conditional within-other-factor allocations across four blocks, per content",
            "interaction_randomization_reference": "joint no-recipe-effect sharp null; 24 factorial permutations/block, reduced to six equally repeated partitions"}})
    return p


def prepare():
    preserve_prior()
    if any(p.exists() for p in [ROOT, DEV, CONFIG]):
        raise ValueError("preserve any existing M2 registration/capture")
    source = v.verify_assets()
    measured = next(p for p in source["network_profiles"] if p["profile_id"] == "att_lte_driving_2016-uplink-lower")
    flat = {**measured, "profile_id": "hybrid_flat_prefix__" + measured["profile_id"],
        "family_id": "hybrid_synthetic_prefix__" + measured["family_id"],
        "campaign_id": "hybrid_development__" + measured["campaign_id"],
        "rates_mbps": [st.mean(measured["rates_mbps"][:12])] * 12 + measured["rates_mbps"][12:]}
    assert abs(sum(flat["rates_mbps"][:12]) - sum(measured["rates_mbps"][:12])) < 1e-10
    assert flat["rates_mbps"][12:] == measured["rates_mbps"][12:]
    synthetic = {"profile_id": "synthetic_m1_constant", "family_id": "synthetic_instrument_check",
        "campaign_id": "no_measured_campaign", "rates_mbps": [1.4523718338280722] * 36}
    dev_trials = [trial(DEV, source["content_sources"][0], synthetic, f"m2-instrument-i{initial}", 0, initial, "synthetic_constant") for initial in (300, 1200)]
    dev = protocol(DEV, dev_trials, "instrument_check")
    v.seal(DEV, dev)
    trials, rng = [], random.Random(SEED)
    for rep in range(4):
        cells = list(itertools.product(range(2), ("measured_original", "hybrid_flat_prefix"), (300, 1200)))
        rng.shuffle(cells)
        for ci, history, initial in cells:
            profile = measured if history == "measured_original" else flat
            pair = f"m2-r{rep}-c{ci:02d}-h{'m' if history=='measured_original' else 'f'}-i{initial}"
            trials.append(trial(ROOT, source["content_sources"][ci], profile, pair, rep, initial, history))
    p = protocol(ROOT, trials, "mechanism")
    p.update({"development_protocol_sha256": v.sha(DEV / "protocol.json"),
        "original_measured_profile": measured, "hybrid_profile": flat,
        "ordering": {"seed": SEED, "blocks": 4, "one_trial_per_factorial_context_per_block": True},
        "prior_evidence_sha256": {name: v.sha(REPO / name) for name in subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "7427f48"], cwd=REPO, text=True).splitlines()}})
    v.seal(ROOT, p)
    v.write(CONFIG, p)
    return verify()


def verify(root=ROOT):
    preserve_prior()
    main = v.read(CONFIG)
    assert v.sha(CONFIG) == v.sha(ROOT / "protocol.json")
    for name, expected in main["prior_evidence_sha256"].items():
        assert v.sha(REPO / name) == expected, name
    assert main["development_protocol_sha256"] == v.sha(DEV / "protocol.json")
    for target in (ROOT, DEV, *([REPLICATION] if REPLICATION.exists() else [])):
        p = v.read(target / "protocol.json")
        v.core.verify_sources(p)
        assert (target / "protocol.sha256").read_text().split()[0] == v.sha(target / "protocol.json")
        assert p["support"] == v.read(v.CONFIG)["support"]
        for t in p["trials"]:
            assert t["support_only"] and t["initial_bwe_kbps"] in (300, 1200)
            assert v.sha(target / t["panel"]) == t["panel_sha256"]
            panel = v.read(target / t["panel"])
            assert panel["episodes"][0]["support_config"]["support_only"]
            assert v.sha(Path(panel["video_source"]["path"])) == panel["video_source"]["sha256"]
    assert len(main["trials"]) == 32 and len(v.read(DEV / "protocol.json")["trials"]) == 2
    return {"verified": True, "protocol_sha256": v.sha(CONFIG), "registration_matches_head": committed(REGISTRATION),
        "mechanism_started": (ROOT / "sessions").exists(), "v13_actions_started": False}


def gate(root):
    verify(root)
    p, index = v.core.check_capture_integrity(root)
    base = v.gate(root)
    native = {r["trial"]: r for r in base["sessions"]}
    rows = []
    for t in p["trials"]:
        row = {**native[t["id"]], "initial_bwe_kbps": t["initial_bwe_kbps"], "history_kind": t["history_kind"],
            "mechanism_context": t["mechanism_context"], "startup_passed": False, "readback_passed": False}
        directory = root / "sessions" / t["id"]
        if native[t["id"]]["capture_status"] == "sealed":
            startup = v.read(directory / "support_startup.json")
            requested = t["initial_bwe_kbps"] * 1000
            actual_initial = startup["initial_native_source"]["bwe_bps"]
            row["startup"] = startup
            row["startup_passed"] = all([startup["requested_initial_bwe_bps"] == requested,
                startup["local_start_parameter"] == t["initial_bwe_kbps"], startup["remote_start_parameter"] == t["initial_bwe_kbps"],
                startup["preconnection_cap_readback_bps"] == 4000000,
                isinstance(actual_initial, (int, float)) and abs(actual_initial - requested) <= 1,
                isinstance(startup["first_measured_bwe_bps"], (int, float)) and abs(startup["first_measured_bwe_bps"] - requested) <= 1])
            sender = v.read(directory / "sender_observations.json")
            row["readback_passed"] = not sender["support_screen"]["action_assigned"] and all(
                d["actuator_assignment"] is None and d["actuation_readback"]["encoder_max_bitrate_bps"] == 4000000
                and d["actuation_readback"]["receiver_jitter_buffer_target_ms"] == 0 for d in sender["decisions"])
        row["passed"] &= row["startup_passed"] and row["readback_passed"]
        rows.append(row)
    passed = base["passed"] and all(r["passed"] for r in rows)
    if p["stage"] == "replication":
        passed &= base["common_support_at_least_half_octave"]
    result = {"abi": "native_bwe_mechanisms_m2_qualification_v1", "stage": p["stage"], "passed": bool(passed),
        "protocol_sha256": v.sha(root / "protocol.json"), "capture_index_sha256": v.sha(root / "capture_index.json"),
        "base_gate_sha256": v.sha(root / "support_clock_transport_gate.json"),
        "planned_sessions": len(p["trials"]), "qualified_sessions": sum(r["passed"] for r in rows),
        "sessions": rows, "census_states": base["census_states"], "cells": base["cells"],
        "common_support_log2_interval": base["common_support_log2_interval"],
        "common_support_at_least_half_octave": base["common_support_at_least_half_octave"],
        "outcomes_read": False, "controller_fitted": False, "v13_reopened": False}
    v.write(root / "mechanism_qualification_gate.json", result)
    return result


def run(root):
    checked = verify(root)
    if not checked["registration_matches_head"]:
        raise ValueError("commit all M2 scientific registration files before captures")
    if root == ROOT and not gate(DEV)["passed"]:
        raise ValueError("original instrument check failed; mechanism panel remains untouched")
    if root == REPLICATION and not committed([str(REPLICATION_CONFIG.relative_to(REPO))]):
        raise ValueError("commit the prospective replication protocol before capture")
    p = v.read(root / "protocol.json")
    current, _ = v.frozen.base.runtime_provenance(Path(p["preflight_reference"]["path"]))
    assert current == p["runtime"]
    v.frozen.v2.set_runtime_env(p)
    capture = v.core.capture(root)
    result = gate(root)
    v.write(REPO / f"reports/native-bwe-mechanisms-m2-{p['stage']}-gate.json", result)
    return {"capture": capture, "qualified_sessions": result["qualified_sessions"], "gate_passed": result["passed"], "outcomes_read": False}


def randomization_reference(blocks, factor):
    possibilities, observed = [], []
    for b in blocks:
        if factor == "history":
            diffs = [b[f"hybrid_flat_prefix::{i}"] - b[f"measured_original::{i}"] for i in (300, 1200)]
            observed.append(st.mean(diffs))
            possibilities.append([st.mean(s * d for s, d in zip(signs, diffs)) for signs in itertools.product((-1, 1), repeat=2)])
        elif factor == "initial":
            diffs = [b[f"{h}::1200"] - b[f"{h}::300"] for h in ("measured_original", "hybrid_flat_prefix")]
            observed.append(st.mean(diffs))
            possibilities.append([st.mean(s * d for s, d in zip(signs, diffs)) for signs in itertools.product((-1, 1), repeat=2)])
        else:
            values = [b[f"{h}::{i}"] for h, i in itertools.product(("measured_original", "hybrid_flat_prefix"), (300, 1200))]
            observed.append(b["hybrid_flat_prefix::1200"] - b["measured_original::1200"] - b["hybrid_flat_prefix::300"] + b["measured_original::300"])
            possibilities.append([sum(values[i] if i in plus else -values[i] for i in range(4)) for plus in itertools.combinations(range(4), 2)])
    null = np.array([st.mean(draw) for draw in itertools.product(*possibilities)])
    actual = st.mean(observed)
    return {"block_contrasts_octaves": observed, "equal_block_mean_octaves": actual,
        "sharp_null_reference_sd_octaves": float(np.std(null)), "sharp_null_reference_95pct": np.quantile(null, [.025, .975]).tolist(),
        "exact_two_sided_sharp_null_p": float(np.mean(np.abs(null) >= abs(actual) - 1e-12)),
        "equally_weighted_reference_allocations": len(null),
        "sharp_null": "No effect of this factor conditional on other-factor labels" if factor != "interaction" else "No recipe effect at all; not an isolated interaction-null test",
        "limits": "Finite randomized development support-state contrast; assumes no session carryover. No population interval or action effect."}


def summarize():
    verify()
    if SUMMARY.exists():
        raise ValueError("preserve the completed mechanism summary")
    p, index = v.core.check_capture_integrity(ROOT)
    g = gate(ROOT)
    trials = {t["id"]: t for t in p["trials"]}
    contexts = defaultdict(list)
    for r in g["sessions"]:
        contexts[r["mechanism_context"]].append(r)
    summaries = {}
    for context, rows in sorted(contexts.items()):
        rows.sort(key=lambda r: r["repetition"])
        xs = [r.get("support", {}).get("continuous_log2_bwe") for r in rows]
        complete = len(rows) == 4 and all(r["passed"] for r in rows)
        summaries[context] = {"content": rows[0]["content_id"], "history": rows[0]["history_kind"],
            "initial_bwe_kbps": rows[0]["initial_bwe_kbps"], "qualified_sessions": sum(r["passed"] for r in rows),
            "replicate_x": xs, "replicate_bwe_geo_bps": [500000 * 2 ** x if x is not None else None for x in xs],
            "full_spread_octaves": max(xs) - min(xs) if complete else None,
            "sample_sd_octaves": st.stdev(xs) if complete else None,
            "six_pairwise_differences": [abs(a - b) for a, b in itertools.combinations(xs, 2)] if complete else None,
            "repeatability_passed": complete and max(xs) - min(xs) <= .25}
    contents = sorted({t["content_id"] for t in p["trials"]})
    candidates = [initial for initial in (300, 1200) if all(summaries[f"{c}::measured_original::initial{initial}"]["repeatability_passed"] for c in contents)]
    candidate = candidates[0] if candidates else None
    comparisons = {}
    for content in contents:
        selected = [r for r in g["sessions"] if r["content_id"] == content]
        if not all(r["passed"] for r in selected):
            comparisons[content] = {"estimable": False, "reason": "an original session failed technical/native qualification"}
            continue
        blocks = [{f"{r['history_kind']}::{r['initial_bwe_kbps']}": r["support"]["continuous_log2_bwe"] for r in selected if r["repetition"] == rep} for rep in range(4)]
        comparisons[content] = {"estimable": True, **{factor: randomization_reference(blocks, factor) for factor in ("history", "initial", "interaction")}}
        comparisons[content]["within_context_variances"] = {f"{h}::{i}": st.variance([b[f"{h}::{i}"] for b in blocks]) for h, i in itertools.product(("measured_original", "hybrid_flat_prefix"), (300, 1200))}
    projection_spec = importlib.util.spec_from_file_location("m2_permitted_projection", REPO / "tools/diagnose_bwe_mechanisms_m2.py")
    projection = importlib.util.module_from_spec(projection_spec)
    projection_spec.loader.exec_module(projection)
    support_rows = [projection.project_session(ROOT, trials[r["trial"]], i) for i, r in enumerate(g["sessions"]) if r["passed"]]
    v.write(ROOT / "mechanism_support_projection.json", {"outcomes_read": False, "sessions": support_rows,
        "selection": "Only gate-qualified support histories; all failed captures remain in the complete qualification gate and cannot supply a passing context."})
    result = {"abi": "native_bwe_mechanisms_m2_summary_v1", "protocol_sha256": v.sha(CONFIG),
        "registration_commit": subprocess.check_output(["git", "log", "-1", "--format=%H", "--", *REGISTRATION], cwd=REPO, text=True).strip(),
        "capture_index_sha256": v.sha(ROOT / "capture_index.json"), "gate_sha256": v.sha(ROOT / "mechanism_qualification_gate.json"),
        "verified_session_files": sum(v.read(ROOT / "sessions" / s["trial"] / "integrity.json")["file_count"] for s in index["sessions"]),
        "planned_sessions": 32, "sealed_sessions": sum(s["status"] == "sealed" for s in index["sessions"]),
        "qualified_sessions": g["qualified_sessions"], "technical_gate_passed": g["passed"],
        "contexts": summaries, "content_factorial_comparisons": comparisons,
        "prospective_replication_candidate_initial_kbps": candidate,
        "outcomes_read": False, "bitrate_actions_assigned": 0, "controller_fitted": False,
        "v13_reopened": False, "common_measured_support_established": False,
        "independent_sources_pooled": False, "source_separation": p["source_separation"],
        "scope": "Randomized support-state mechanism development on one reused measured profile and two reused clips. Hybrid prefix is synthetic development. Full prospective measured support must still qualify before claiming reproducibility."}
    v.write(SUMMARY, result)
    v.write(ROOT / "mechanism_summary.json", result)
    return {"qualified_sessions": g["qualified_sessions"], "context_spreads": {k: r["full_spread_octaves"] for k, r in summaries.items()},
        "candidate_initial_kbps": candidate, "outcomes_read": False}


def prepare_replication():
    verify()
    if REPLICATION.exists() or REPLICATION_CONFIG.exists():
        raise ValueError("preserve any prior prospective replication")
    s = v.read(SUMMARY)
    candidate = s["prospective_replication_candidate_initial_kbps"]
    if candidate not in (300, 1200):
        raise ValueError("neither measured-history initialization met both content reliability gates")
    assert s["protocol_sha256"] == v.sha(CONFIG) and s["gate_sha256"] == v.sha(ROOT / "mechanism_qualification_gate.json")
    source = v.verify_assets()
    trials = [trial(REPLICATION, c, profile, f"m2b-c{ci:02d}-p{pi:02d}-r{rep}", rep, candidate, "measured_original")
        for ci, c in enumerate(source["content_sources"]) for pi, profile in enumerate(source["network_profiles"]) for rep in range(2)]
    p = protocol(REPLICATION, trials, "replication")
    p.update({"selected_initial_bwe_kbps": candidate, "mechanism_summary_sha256": v.sha(SUMMARY),
        "mechanism_protocol_sha256": v.sha(CONFIG), "preregistered_selection_rule_unchanged": True,
        "required_complete_cells": 4, "minimum_common_overlap_octaves": .5})
    v.seal(REPLICATION, p)
    v.write(REPLICATION_CONFIG, p)
    return {"sessions": len(trials), "protocol_sha256": v.sha(REPLICATION_CONFIG), "initial_kbps": candidate, "untouched": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "verify", "instrument-check", "capture", "summarize", "prepare-replication", "replication"])
    args = parser.parse_args()
    handlers = {"prepare": prepare, "verify": verify, "instrument-check": lambda: run(DEV), "capture": lambda: run(ROOT),
        "summarize": summarize, "prepare-replication": prepare_replication, "replication": lambda: run(REPLICATION)}
    print(json.dumps(handlers[args.command]()))
