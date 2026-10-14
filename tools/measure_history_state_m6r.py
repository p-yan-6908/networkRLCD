"""Preregister/select on M5 development; fresh M6R support matching only."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("m6_support_matching", REPO / "tools/history_state_support_m6r.py")
h = importlib.util.module_from_spec(s)
s.loader.exec_module(h)
m5, v, r = h.m5, h.v, h.r
ROOT = v.CACHE / "native-history-state-m6r"
CAPTURE_ROOT = ROOT / "validation"
DESIGN = REPO / "configs/native_history_state_m6r_design.json"
CONFIG = REPO / "configs/native_history_state_m6r_validation.json"
SELECTION = REPO / "reports/native-history-state-m6r-selection.json"
N, SEED = 8, 20261121
SCIENCE = ["tools/build_history_state_m6r.py", "tools/history_state_support_m6r.py", "tools/measure_history_state_m6r.py", "docs/NATIVE_HISTORY_STATE_M6R_PLAN.md",
           "reports/native-history-state-m6r-access-preflight.json", "reports/native-history-state-m6r-runtime-preflight.json",
           "reports/native-history-state-m6r-input-verification.json"]


def source_inventory():
    result = m5.inventory()
    for name in SCIENCE + [str(DESIGN.relative_to(REPO)), "configs/native_prefix_memory_m5.json",
                           "docs/NATIVE_PREFIX_MEMORY_M5_RESULTS.md", "reports/native-prefix-memory-m5-summary.json",
                           "reports/native-prefix-memory-m5-gate.json"]:
        result[name] = v.sha(REPO / name)
    return result


def initialize():
    assert not ROOT.exists() and not DESIGN.exists()
    m5.verify()
    value = {"abi": "native_history_state_m6r_design_v1", "anchor_commit": '2cdd630275669c3098707bd1193e3dced1212acd',
             "source_sha256": {name: v.sha(REPO / name) for name in SCIENCE},
             "prior_freeze_sha256": {name: v.sha(REPO / name) for name in subprocess.check_output(
                 ["git", "ls-tree", "-r", "--name-only", "2cdd630"], cwd=REPO, text=True).splitlines()},
             "development_input_gate_sha256": v.sha(m5.ROOT / "prefix_memory_qualification_gate.json"),
             "development_input_summary_sha256": v.sha(m5.ROOT / "prefix_memory_summary.json"),
             "candidate_features": h.CANDIDATES, "physical_calipers": h.CALIPERS,
             "transitions_ms": h.TRANSITIONS, "new_originals": 32, "repeats_per_content_prefix": N,
             "matched_originals_per_prefix_per_landmark": 4, "minimum_baseline_retention": .8,
             "fresh_native_seed": SEED, "selection_rule": "best two-dimensional state; third dimension requires >=20% reduction in worst future spread and no loss of coverage cells",
             "common_support_bounds_octaves": .25, "improvement_required_each_content": .2,
             "maximum_landmark_w1_worsening": .1, "native_common_support_established": False,
             "action_sessions_authorized": 0, "controller_fitted": False, "delivery_qoe_action_outcomes_read": False}
    v.write(DESIGN, value); v.write(ROOT / "design.json", value)
    return {"design_frozen": True, "fresh_panel_exists": False, "m5_features_opened": False, "native_sessions": 0}


def verify_design(require_committed=True):
    m5.verify()
    p = v.read(DESIGN)
    assert v.sha(DESIGN) == v.sha(ROOT / "design.json")
    for name, checksum in p["prior_freeze_sha256"].items():
        assert v.sha(REPO / name) == checksum, name
    for name in SCIENCE:
        assert v.sha(REPO / name) == p["source_sha256"][name]
    if require_committed:
        for name in SCIENCE + [str(DESIGN.relative_to(REPO))]:
            assert subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=REPO) == (REPO / name).read_bytes()
    return p


def develop():
    verify_design()
    assert not SELECTION.exists() and not (ROOT / "development").exists()
    g = v.read(m5.ROOT / "prefix_memory_qualification_gate.json")
    assert g["passed"]
    rows = h.project(m5.ROOT, g, include_future=True)
    v.write(ROOT / "development/support_features.json", rows)
    chosen = h.select(rows)
    chosen.update({"design_sha256": v.sha(DESIGN), "development_feature_sha256": v.sha(ROOT / "development/support_features.json"),
                   "development_capture_count": 84, "development_is_reused_m5_only": True,
                   "selection_registration_commit": subprocess.check_output(["git", "log", "-1", "--format=%H", "--", *SCIENCE, str(DESIGN.relative_to(REPO))], cwd=REPO, text=True).strip()})
    v.write(SELECTION, chosen); v.write(ROOT / "development/selection.json", chosen)
    return {"selected": chosen["selected"], "features": chosen["features"], "relay_assisted": chosen["relay_assisted"],
            "baseline_development": chosen["development_candidates"]["b0_instantaneous"],
            "selected_development": chosen["development_candidates"][chosen["selected"]], "new_native_sessions": 0}


def prepare():
    verify_design()
    selection = v.read(SELECTION)
    assert v.sha(SELECTION) == v.sha(ROOT / "development/selection.json")
    assert not CAPTURE_ROOT.exists() and not CONFIG.exists()
    assets = v.verify_assets(); parent = v.read(m5.CONFIG)
    rng, trials = random.Random(SEED), []
    for rep in range(N):
        contents = list(enumerate(assets["content_sources"]))
        rng.shuffle(contents)
        for ci, content in contents:
            pair, bit = f"m6r-r{rep:02d}-c{ci:02d}", rng.getrandbits(1)
            for slot in (0, 1):
                prefix = h.PREFIXES[slot ^ bit]
                profile = parent["prefix_profiles"][prefix]
                tid = f"{pair}-s{slot}-support"
                panel = v.panel_for(tid, content, profile, pair, slot, SEED, True)
                panel["episodes"][0].update({"support_initial_bwe_kbps": 1200, "setup_delay_ms": 0})
                panel["measurement_recipe"].update({"scientific_role": "fresh frozen history-state support matching; zero bitrate actions", "instrumentation_version": "M4R"})
                relative = f"panels/{tid}.json"; v.write(CAPTURE_ROOT / relative, panel)
                trials.append({"id": tid, "condition": "micro", "panel": relative, "panel_sha256": v.sha(CAPTURE_ROOT / relative),
                               "pair_id": pair, "pair_slot": slot, "repetition": rep, "support_only": True,
                               "content_id": content["content_id"], "prefix": prefix, "setup_delay_ms": 0,
                               "network_family": profile["family_id"], "network_campaign_id": profile["campaign_id"],
                               "network_profile_id": profile["profile_id"], "cell_cluster": content["content_id"] + "__" + prefix})
    p = v.protocol_for(CAPTURE_ROOT, trials, "development", SEED)
    p.update({"abi": "native_history_state_m6r_validation_protocol_v1", "stage": "history_state_support_validation",
              "anchor_commit": v.read(DESIGN)["anchor_commit"], "source_hashes": source_inventory(),
              "design_sha256": v.sha(DESIGN), "selected_state_sha256": v.sha(SELECTION), "selected_state": selection,
              "prefix_profiles": parent["prefix_profiles"], "parent_profile": parent["parent_profile"],
              "clock_instrumentation": parent["clock_instrumentation"], "startup": parent["startup"],
              "randomization": {"seed": SEED, "namespace": "networkrlcd-history-state-m6", "marginal_prefix_propensity": .5},
              "scientific_role": "Fresh native fixed-cap history-state common-support falsification; not an action effect or controller study.",
              "source_separation": "Reused two licensed clips and one LTE source; M5 development excluded from validation estimates; constructed prefix plus original measured suffix; M1 synthetic separate.",
              "analysis": {"delivery_qoe_action_outcomes_read": False, "controller_fitted": False, "support_state_selection_only": True}})
    v.seal(CAPTURE_ROOT, p); v.write(CONFIG, p)
    return verify_validation(False)


def verify_validation(require_committed=True):
    p = verify_design(require_committed)
    config = v.read(CONFIG)
    assert v.sha(CONFIG) == v.sha(CAPTURE_ROOT / "protocol.json")
    assert config["source_hashes"] == source_inventory()
    assert config["design_sha256"] == v.sha(DESIGN) and config["selected_state_sha256"] == v.sha(SELECTION)
    assert config["selected_state"] == v.read(SELECTION) == v.read(ROOT / "development/selection.json")
    assert len(config["trials"]) == 32
    assert config["randomized_order"] == [x["id"] for x in config["trials"]]
    for t in config["trials"]:
        assert v.sha(CAPTURE_ROOT / t["panel"]) == t["panel_sha256"]
        panel = v.read(CAPTURE_ROOT / t["panel"])
        assert v.sha(Path(panel["video_source"]["path"])) == panel["video_source"]["sha256"]
        assert t["support_only"] and panel["episodes"][0]["setup_delay_ms"] == 0
        rates = [x for block in panel["episodes"][0]["schedule"] for x in block[3]]
        assert rates == config["prefix_profiles"][t["prefix"]]["rates_mbps"]
        assert rates[10:] == config["parent_profile"]["rates_mbps"][10:]
    if require_committed:
        for path in (CONFIG, SELECTION):
            name = path.relative_to(REPO).as_posix()
            assert subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=REPO) == path.read_bytes()
    v.core.source_inventory = source_inventory
    v.core.RECORDER = r.RECORDER
    return {"verified": True, "planned_originals": 32, "selected_state": config["selected_state"]["selected"],
            "prior_frozen_files_unchanged": len(p["prior_freeze_sha256"]), "started": (CAPTURE_ROOT / "sessions").exists()}


def gate():
    verify_validation()
    base = r.gate(CAPTURE_ROOT, values=True)
    p, index = v.core.check_capture_integrity(CAPTURE_ROOT)
    pairs = {}
    for row in base["sessions"]:
        pairs.setdefault(row["pair_id"], []).append(row)
        if row["passed"]:
            directory = CAPTURE_ROOT / "sessions" / row["trial"]
            row["suffix_fidelity"] = m5.suffix(directory, v.read(directory / "sender_observations.json"))
    fidelity = {}
    for pair, members in pairs.items():
        fidelity[pair] = {}
        assert len(members) == 2 and {x["prefix"] for x in members} == set(h.PREFIXES)
        for endpoint in r.ENDPOINTS:
            available = all(x["passed"] and x["suffix_fidelity"]["common_before_11000"] for x in members)
            error = None
            if available:
                a, b = [x["suffix_fidelity"]["capacity_exposure_bytes_bounds"][str(endpoint)] for x in members]
                error = max(abs(math.log2(a[0] / b[1])), abs(math.log2(a[1] / b[0])))
            fidelity[pair][str(endpoint)] = {"passed": bool(available and error <= .01), "maximum_exposure_log2_difference": error}
    result = {**base, "abi": "native_history_state_m6r_acquisition_qualification_v1", "sessions": base["sessions"],
              "pair_suffix_fidelity": fidelity, "passed": base["passed"] and len(pairs) == 16 and all(w["passed"] for ws in fidelity.values() for w in ws.values()),
              "source_capture_count": 32, "new_matching_stage_not_yet_opened": True}
    v.write(CAPTURE_ROOT / "history_state_acquisition_gate.json", result)
    v.write(REPO / "reports/native-history-state-m6r-acquisition-gate.json", result)
    return result


def capture():
    verify_validation()
    p = v.read(CONFIG)
    current, _ = v.frozen.base.runtime_provenance(Path(p["preflight_reference"]["path"]))
    assert current == p["runtime"]
    v.frozen.v2.set_runtime_env(p)
    captured = v.core.capture(CAPTURE_ROOT)
    g = gate()
    return {"capture": captured, "qualified_originals": g["qualified_sessions"], "acquisition_gate_passed": g["passed"]}


def analyze():
    verify_validation()
    out = REPO / "reports/native-history-state-m6r-summary.json"
    assert not out.exists()
    p, index = v.core.check_capture_integrity(CAPTURE_ROOT)
    g = v.read(CAPTURE_ROOT / "history_state_acquisition_gate.json")
    selection = v.read(SELECTION)
    result = {"abi": "native_history_state_m6r_summary_v1", "acquisition_gate_passed": g["passed"],
              "design_sha256": v.sha(DESIGN), "protocol_sha256": v.sha(CONFIG), "selected_state_sha256": v.sha(SELECTION),
              "acquisition_gate_sha256": v.sha(CAPTURE_ROOT / "history_state_acquisition_gate.json"),
              "planned_originals": 32, "qualified_originals": g["qualified_sessions"], "selected_state": selection["selected"],
              "history_state_qualified_for_this_support_screen": False, "broad_native_common_support_established": False,
              "v13_reopened": False, "action_values_estimated": False, "controller_fitted": False,
              "delivery_qoe_action_outcomes_read": False, "old_or_synthetic_captures_pooled": False,
              "support_matching_future_responses_estimable": False,
              "post_prefix_conditioning_identifies_a_direct_causal_effect": False}
    if g["passed"]:
        rows = h.project(CAPTURE_ROOT, g, include_future=False)
        v.write(CAPTURE_ROOT / "precutoff_support_features.json", rows)
        membership = h.support_membership_gate(rows, selection)
        membership.update({"precutoff_features_sha256": v.sha(CAPTURE_ROOT / "precutoff_support_features.json"),
                           "selection_sha256": v.sha(SELECTION)})
        v.write(CAPTURE_ROOT / "state_membership_gate.json", membership)
        v.write(REPO / "reports/native-history-state-m6r-membership-gate.json", membership)
        result.update({"state_membership_gate_passed": membership["passed"],
                       "state_membership_gate_sha256": v.sha(CAPTURE_ROOT / "state_membership_gate.json"),
                       "membership": membership})
        if membership["passed"]:
            lookup = {x["trial"]: x for x in g["sessions"]}
            for item in rows:
                item["future_x"] = lookup[item["trial"]]["windows"][str(item["later"])]["x"]
            result.update(h.evaluate(rows, selection, membership))
            result["support_matching_future_responses_estimable"] = True
            v.write(CAPTURE_ROOT / "qualified_future_support_responses.json", rows)
        else:
            result["closure"] = "Frozen state coverage/retention gate failed; no conditional future BWE estimates, no retuning or replacements."
    else:
        result["closure"] = "All 32 original acquisition and 16 suffix-pair gates required; no subset state analysis."
    v.write(out, result); v.write(CAPTURE_ROOT / "history_state_summary.json", result)
    return {k: result[k] for k in ("acquisition_gate_passed", "selected_state", "support_matching_future_responses_estimable",
                                  "history_state_qualified_for_this_support_screen", "broad_native_common_support_established", "controller_fitted")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("initialize", "develop", "prepare", "verify", "capture", "analyze"))
    args = parser.parse_args()
    result = verify_validation() if args.command == "verify" else globals()[args.command]()
    print(json.dumps(result))
