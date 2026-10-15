"""RD1 summary-only provenance and paper tables. No raw telemetry or models.

Only committed project reports are read. Values are copied/rounded, not refit,
pooled, re-estimated or used to select a successor experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ANCHOR = "f109ab2"
DATA = REPO / "data/research-decision-rd1"
FREEZE = DATA / "prior-freeze-sha256.json"
LEDGER = DATA / "evidence-ledger.json"
AUDIT = REPO / "reports/research-decision-rd1-audit.json"
TABLE = REPO / "paper/negative-result/evidence-tables.tex"

# A source citation is not an independent sample or an authorization to reopen it.
CATALOG = [
    ("native_v9", "local_secondary_signal_primary_unresolved", "NATIVE_CLOCK_ACTION_TURN_TCP_V9_RESULTS.md",
     "native-clock-action-turntcp-v9-analysis.json", "48 sessions; 12 generated-scene clusters, 11 complete for cell analysis"),
    ("native_v10", "specific_policy_superiority_contradicted", "NATIVE_CLOCK_ACTION_TURN_TCP_V10_RESULTS.md",
     "native-clock-action-turntcp-v10-analysis.json", "48 sessions; 12 scene clusters; whole-session policy contrast"),
    ("v11d", "negative_undercovered_replication", "NATIVE_CLOCK_ACTION_TURN_TCP_V11D_RESULTS.md",
     "native-clock-action-turntcp-v11d-analysis-final.json", "64 sessions; 4 content groups; 4 nested strata in 2 measured campaigns; 9 complete cells, 7 PSNR-estimable"),
    ("v12", "support_design_failure_no_actions", "NATIVE_SUPPORT_VALIDATION_V12_RESULTS.md",
     "native-v12-support-census-gate.json", "24 support originals; 23 ordinary sealed and one failed media-statistics original; 0/6 complete cells"),
    ("v13", "repeatability_common_support_failure_no_actions", "NATIVE_CONTINUOUS_VALIDATION_V13_RESULTS.md",
     "native-v13-support-census-gate.json", "32 support originals; 16 repeated contexts, 4 cells; 2 bundles in one measurement program"),
    ("m5", "qualified_finite_horizon_causal_history_effect", "NATIVE_PREFIX_MEMORY_M5_RESULTS.md",
     "native-prefix-memory-m5-summary.json", "84 originals; 21 randomized pairs per reused content; 2 contents and one reused LTE source"),
    ("m6", "clock_instrumentation_limited_before_comparison", "NATIVE_HISTORY_STATE_M6_CLOSURE.md",
     "native-history-state-m6-clock-closure.json", "252 failed development clock bounds; no candidate or native validation comparison"),
    ("m6r", "state_coverage_failure", "NATIVE_HISTORY_STATE_M6R_RESULTS.md",
     "native-history-state-m6r-membership-gate.json", "32 originals; 16 suffix pairs; 4/6 membership strata; no conditional future comparison"),
    ("m7", "scheduler_instrumentation_failure", "NATIVE_STATE_CONDITIONING_M7_RESULTS.md",
     "native-state-conditioning-m7-summary.json", "4 originals; 39/104 early service commands; validation unopened"),
    ("m7r", "launcher_failure_zero_native_sessions", "NATIVE_STATE_CONDITIONING_M7R_RESULTS.md",
     "native-state-conditioning-m7r-summary.json", "4 failed attempts before browser/transport; separate validation unopened"),
    ("m7ra", "prospective_state_creation_failure", "NATIVE_STATE_CONDITIONING_M7RA_RESULTS.md",
     "native-state-conditioning-m7ra-summary.json", "4 technically qualified feasibility originals; 2 instantaneous and 1 sustained member; validation unopened"),
    ("m8", "qualified_native_dynamics_failed_settling_rule", "NATIVE_BWE_TRANSIENTS_M8_RESULTS.md",
     "native-bwe-transients-m8-selection.json", "2 qualification plus 16 characterization originals; 64 nested plateau occurrences"),
    ("m9", "sampling_instrumentation_limited_unestimable", "NATIVE_PHASE_STATE_M9_RESULTS.md",
     "native-phase-state-m9-scientific-stop.json", "2 instrumentation originals; 64 validation sealed, 62 technically qualified; no scientific comparison"),
    ("m9r", "qualified_prospective_state_coverage_stability_failure", "NATIVE_PHASE_STATE_M9R_RESULTS.md",
     "native-phase-state-m9r-summary.json", "8 instrumentation plus 64 validation originals; 64s common plateau; landmarks nested"),
    ("m10", "cleanup_instrumentation_limited", "NATIVE_MECHANISM_OBSERVABILITY_M10_RESULTS.md",
     "native-mechanism-observability-m10-instrumentation-gate.json", "4 originals fail cleanup; development unopened"),
    ("m10r", "qualified_observability_failed_mechanism_discrimination", "NATIVE_MECHANISM_OBSERVABILITY_M10R_RESULTS.md",
     "native-mechanism-observability-m10r-summary.json", "4 instrumentation plus 8 development originals; 96 contrasts and 400 stationary queries are nested"),
    ("m11", "sender_identity_instrumentation_limited", "NATIVE_TRANSPORT_TIMING_M11_RESULTS.md",
     "native-transport-timing-m11-channel-qualification.json", "2 native capability originals; decoded events but no exact SSRC binding"),
    ("m11r", "causal_timing_observability_boundary", "NATIVE_TRANSPORT_TIMING_M11R_RESULTS.md",
     "native-transport-timing-m11r-channel-qualification.json", "2 acquisition-qualified capability originals; 0 qualify all required channels"),
    ("if1", "practical_fixture_admission_failure_build_unattempted", "NATIVE_INSTRUMENTED_FIXTURE_IF1_RESULT.md",
     "native-instrumented-fixture-if1-build-admission.json", "static design and resource audit; zero build or native-session attempts"),
    ("po1", "synthetic_screen_failure_no_native_result", "PARTIAL_OBSERVABILITY_PO1_RESULTS.md",
     "partial-observability-po1-result.json", "816 synthetic episodes; 3 fits; 72 validation episodes per held-out family; no native captures"),
]

EXTRA_INPUTS = [
    "paper/main.tex", "research/references.bib", "reports/figures/partial-observability-po1.png",
    "reports/native-v13-support-census-summary.json",
    "docs/NATIVE_PHASE_STATE_M9R_INTERPRETATION.md", "docs/NATIVE_MECHANISM_OBSERVABILITY_M10R_INTERPRETATION.md",
    "docs/NATIVE_INSTRUMENTED_FIXTURE_IF1_PLAN.md", "docs/NATIVE_RESEARCH_DECISION_IF1.md",
    "docs/PARTIAL_OBSERVABILITY_PO1_PLAN.md", "configs/partial_observability_po1.json",
    "data/partial-observability-po1/registration.json", "data/partial-observability-po1/native-reservation.json",
    "data/native-m8/next-validation-allocation.json", "data/native-if1/qualification-allocation.json",
]
RECEIPTS = ["native-prefix-memory-m5-20261014-01", "native-history-state-m6r-20261014-01",
            "native-state-conditioning-m7ra-20261015-01", "native-bwe-transients-m8-20261015-01",
            "native-phase-state-m9r-20261015-01", "native-mechanism-observability-m10r-20261015-01",
            "native-transport-timing-m11r-20261015-01", "native-instrumented-fixture-if1-20261015-01",
            "partial-observability-po1-20261015-01", "native-support-validation-v12-support-20261014-01",
            "native-continuous-validation-v13-support-20261014-01"]

HYPOTHESES = [
    {"id": "causal_prefix_history", "status": "supported_bounded", "studies": ["m5"],
     "claim": "Early service order changes later native BWE under the registered common measured-source suffix.",
     "not_claimed": "permanent memory, broad independent-source replication, or a unique queue/estimator mediator"},
    {"id": "stable_native_quality_interaction", "status": "not_confirmed_undercovered_replication", "studies": ["native_v9", "v11d"],
     "claim": "V9 has a local secondary signal; V11D descriptive directions reverse but coverage fails.",
     "not_claimed": "population reversal, equivalence, or portable conditional quality value"},
    {"id": "threshold_policy_superiority", "status": "contradicted_in_local_randomized_trial", "studies": ["native_v10"],
     "claim": "The specific fixed BWE-threshold policy harms the primary timely-delivery endpoint versus fixed0.65.",
     "not_claimed": "all policies are harmful or fixed0.65 is universally optimal"},
    {"id": "measured_capacity_guarantees_bwe_support", "status": "registered_recipe_failed", "studies": ["v12"],
     "claim": "Capacity-based source hints did not create required native BWE occupancy.",
     "not_claimed": "an action effect from support sessions"},
    {"id": "observable_common_native_state", "status": "tested_recipes_not_qualified", "studies": ["v13", "m6r", "m7ra", "m8", "m9r"],
     "claim": "The tested matching, conditioning and dynamic-state recipes do not qualify prospective support/repeatability.",
     "not_claimed": "universal insufficiency of every history representation or impossible native policy inference"},
    {"id": "available_mechanisms_resolve_divergence", "status": "no_registered_repeatable_discrimination", "studies": ["m10r"],
     "claim": "Available channels did not pass the frozen repeat/control contrasts.",
     "not_claimed": "zero causal role of queues/RTT/encoder behavior or an identified mediator"},
    {"id": "internal_transport_timing_explains_divergence", "status": "untested_fixture_limited", "studies": ["m11", "m11r"],
     "claim": "Actual timing could not be exposed with jointly qualified sender identity and causal freshness.",
     "not_claimed": "events absent, timing irrelevant, or instrumentation universally impossible"},
    {"id": "instrumented_chromium_scientific_value", "status": "untested_practical_admission_limit", "studies": ["if1"],
     "claim": "The planned build was never attempted because admission failed.",
     "not_claimed": "failed compiled interface or scientific evidence against a new instrumented fixture"},
    {"id": "po1_robust_incremental_prediction", "status": "frozen_package_failed_heldout_families", "studies": ["po1"],
     "claim": "Ordered-history linear H1 failed the conjunction against strong simple baselines, especially under feedback shift.",
     "not_claimed": "zero information in all observable history or any native prediction result"},
    {"id": "po1_action_discrimination", "status": "frozen_synthetic_gate_failed", "studies": ["po1"],
     "claim": "No reproducible qualifying advantage-prediction improvement or supported action assertion.",
     "not_claimed": "native counterfactual value, executed learned-policy performance, or no simulator oracle headroom"},
    {"id": "po1_useful_uncertainty_calibration", "status": "frozen_synthetic_gates_failed", "studies": ["po1"],
     "claim": "Excessively wide intervals and failed calibration conjunction; zero assertions do not prove safety.",
     "not_claimed": "native calibration failure or distribution-free OOD coverage"},
    {"id": "fine_grained_learned_native_control", "status": "not_currently_identified_and_robust_under_fixture_assumptions", "studies": ["native_v9", "native_v10", "v11d", "v12", "v13", "m5", "m6r", "m7ra", "m8", "m9r", "m10r", "m11r", "if1", "po1"],
     "claim": "Stop the current transferable state-conditioned control objective and publish the bounded negative.",
     "not_claimed": "an impossibility theorem or inability to identify every randomized marginal/episode native contrast"},
]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def anchor_files():
    tree = subprocess.check_output(["git", "ls-tree", "-rz", ANCHOR], cwd=REPO)
    files = {}
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        header, raw_name = entry.split(b"\t", 1)
        mode, kind, expected = header.decode().split()
        name = raw_name.decode()
        assert kind == "blob" and mode in ("100644", "100755"), name
        data = (REPO / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        assert actual == expected, "prior artifact changed: " + name
        files[name] = hashlib.sha256(data).hexdigest()
    return files


def quantities():
    v9 = read(REPO / "reports/native-clock-action-turntcp-v9-analysis.json")
    v10 = read(REPO / "reports/native-clock-action-turntcp-v10-analysis.json")
    vd = read(REPO / "reports/native-clock-action-turntcp-v11d-analysis-final.json")
    v12 = read(REPO / "reports/native-v12-support-census-gate.json")
    v13 = read(REPO / "reports/native-v13-support-census-gate.json")
    m5 = read(REPO / "reports/native-prefix-memory-m5-summary.json")
    m11 = read(REPO / "reports/native-transport-timing-m11r-channel-qualification.json")
    if1 = read(REPO / "reports/native-instrumented-fixture-if1-build-admission.json")
    po1 = read(REPO / "reports/partial-observability-po1-result.json")
    assert v9["sealed_sessions"] == v10["sealed_sessions"] == 48
    assert vd["coverage"]["complete_cell_count"] == 9 and vd["coverage"]["minimum_complete_cell_count"] == 13
    assert vd["coverage"]["minimum_hold_windows_per_state_action_cell"] == 2
    assert vd["primary_replication"]["estimable_primary_cell_count"] == 7
    assert v12["qualified_sessions"] == 10 and not v12["complete_cells"] and not v12["outcome_telemetry_read"]
    assert v13["qualified_sessions"] == 32 and not v13["passed"] and not v13["common_support_at_least_half_octave"]
    v13_summary = read(REPO / "reports/native-v13-support-census-summary.json")
    assert all(x["passed"] for x in v13["cells"].values()), "range/SD alone passed in all cells"
    assert v13_summary["fully_supported_cell_count"] == 1 and len(v13_summary["repeatability_failed_profiles"]) == 6
    assert v13_summary["official_gate_sha256"] == sha(REPO / "reports/native-v13-support-census-gate.json")
    assert m5["qualified_sessions"] == 84 and m5["qualified_primary_rejections"] == 2
    assert not m11["passed"] and m11["acquisition_passed"] and m11["originals"] == 2
    assert not if1["admitted"] and if1["compiler_invocations"] == if1["native_sessions"] == 0
    assert po1["synthetic_episodes"] == 816 and not po1["synthetic_passed"] and po1["native_sessions"] == 0
    assert po1["native_reservation_untouched"] and all(not f["passed"] for f in po1["families"])
    assert all(f["safety_assertions_not_actions"]["claimed_episodes"] == 0 for f in po1["families"])
    return {"v9_primary": v9["primary_interaction"],
            "v9_secondary_psnr": v9["action_effects"]["mean_ontime_psnr_db"]["interaction_high_bwe_minus_low_bwe"],
            "v10_primary": v10["primary_effect"], "v11d_descriptive_primary": vd["primary_replication"],
            "m5_primary_by_content": {c: {"mean": x["windows"]["18000"]["paired_mean_octaves"],
                                          "ci95": x["windows"]["18000"]["uncertainty"]["paired_mean_95pct"],
                                          "p": x["windows"]["18000"]["randomization"]["exact_randomization_p"]}
                                     for c, x in m5["contents"].items()},
            "po1_families": [{"family": f["family"], "gates": f["gates"],
                               "history_mae": f["metrics"]["history_linear"]["mae"],
                               "summary_mae": f["metrics"]["summary_linear"]["mae"],
                               "persistence_bwe_mae": f["comparisons"]["factual_bwe"]["persistence"]["baseline_mae"],
                               "constant_advantage_mae": f["metrics"]["constant"]["mae"][1],
                               "history_binary_ece": [h["ece"] for h in f["metrics"]["history_linear"]["binary"]],
                               "asserted_episodes": f["safety_assertions_not_actions"]["claimed_episodes"]}
                              for f in po1["families"]]}


def paper_table(q):
    lines = ["% Rounded existing report values only. No reanalysis or model search."]
    def macro(name, value, precision=3):
        lines.append("\\newcommand{\\" + name + "}{" + f"{value:.{precision}f}" + "}")
    x = q["v9_secondary_psnr"]
    for suffix, value in [("", x["mean"]), ("Low", x["ci95"][0]), ("High", x["ci95"][1])]:
        macro("NVNinePSNR" + suffix, value)
    x = q["v10_primary"]
    for suffix, value in [("Delta", x["mean"]), ("Low", x["ci95"][0]), ("High", x["ci95"][1])]:
        macro("NVTen" + suffix, 100*value, 1)
    for short, content in [("Kampar", "content_kampar_boating_01"), ("Volga", "content_volga_lock_01")]:
        x = q["m5_primary_by_content"][content]
        for suffix, value in [("", x["mean"]), ("Low", x["ci95"][0]), ("High", x["ci95"][1])]:
            macro("MFive" + short + suffix, value, 5)
    lines.extend([r"\newcommand{\POOneTable}{%", r"\begin{table}[ht]", r"\centering\small",
                  r"\begin{tabular}{lrrrrrr}\toprule",
                  r"&\multicolumn{3}{c}{Factual BWE MAE (octaves)}&\multicolumn{3}{c}{Synthetic advantage MAE}\\",
                  r"Family&Persistence&S1&H1&Constant&S1&H1\\\midrule"])
    for f in q["po1_families"]:
        cells = [f["persistence_bwe_mae"], f["summary_mae"][0], f["history_mae"][0],
                 f["constant_advantage_mae"], f["summary_mae"][1], f["history_mae"][1]]
        lines.append(f["family"].replace("_", r"\_") + " & " + " & ".join(f"{x:.3f}" for x in cells) + r"\\")
    lines.extend([r"\bottomrule\end{tabular}",
                  r"\caption{PO1 frozen validation values: 72 episodes/family across three fixed fits, six nested decisions/episode. S1 is the fixed-history summary baseline; H1 adds ordered lags. Lower is better. These are simulator results, not native effects.}\label{tab:po1}",
                  r"\end{table}}", ""])
    return "\n".join(lines)


def render():
    assert not TABLE.exists(), "preserve the existing table"
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    with TABLE.open("x") as stream:
        stream.write(paper_table(quantities()))
    return {"table_rendered": True, "new_scientific_estimate": False}


def create():
    assert not FREEZE.exists() and not LEDGER.exists() and not AUDIT.exists() and TABLE.exists()
    old = anchor_files()
    inputs, studies = set(EXTRA_INPUTS), []
    for study, status, document, report, unit in CATALOG:
        document, report = "docs/" + document, "reports/" + report
        assert document in old and report in old
        inputs.update([document, report])
        studies.append({"study": study, "status": status, "document": document, "report": report,
                        "unit_and_scope": unit, "pooled_into_new_effect": False})
    inputs.update("docs/storage-receipts/" + r + ".json" for r in RECEIPTS)
    assert inputs <= old.keys()
    q = quantities()
    write(FREEZE, {"evidence_anchor_commit": ANCHOR, "files": old})
    write(LEDGER, {"abi": "rd1_retrospective_research_decision_v1", "evidence_anchor_commit": ANCHOR,
                   "new_experiment_preregistered": False, "new_scientific_estimates": False,
                   "decision": "stop current fine-grained transferable learned native control under available fixture/data assumptions",
                   "sources": {n: {"sha256": old[n], "bytes": (REPO/n).stat().st_size} for n in sorted(inputs)},
                   "studies": studies, "hypotheses": HYPOTHESES, "critical_frozen_values": q,
                   "independence": "Do not pool studies, reused source groups, trace directions/windows, crossed cells or nested landmarks as independent campaigns.",
                   "native_randomized_contrasts_remain_possible": True,
                   "universal_impossibility_claim": False, "successor_selected": False,
                   "conditional_future_directions": ["admitted new instrumented fixture with fresh qualification/support/effect evidence",
                                                     "independently justified episode/sequence estimand, no PO1 representation or allocation"],
                   "closed_panels": {"native_v12_actions": "48 unrun", "native_v13_actions": "64 unrun",
                                     "m7_m7r_m7ra_validations": "separate 128-original panels unopened",
                                     "m8_successor": "128 originals uninstantiated", "m10_development": "8 originals unopened",
                                     "m11r_conditional_stages": "not instantiated after failed capability gate",
                                     "if1": "4 ordinary technical, 2 identity and 8 observability reserved; support uninstantiated",
                                     "po1_native_factual": "64 reserved, unopened"},
                   "panel_status_basis": "Inherited pinned result reports; no raw session-directory/telemetry audit or capture in RD1.",
                   "po1_stop_unchanged": ["no representation expansion", "no sequence-model complexity escalation", "no refit or calibration/threshold tuning",
                                          "no reserved native panel", "no controller", "no safe-policy efficacy from PO1"]})
    assert TABLE.read_text() == paper_table(q)
    new_sources = ["docs/RESEARCH_DECISION_RD1.md", "paper/negative-result/README.md", "paper/negative-result/main.tex",
                   "paper/negative-result/references.tex", "paper/negative-result/evidence-tables.tex",
                   "tools/synthesize_research_decision_rd1.py", str(LEDGER.relative_to(REPO)), str(FREEZE.relative_to(REPO))]
    write(AUDIT, {"abi": "rd1_summary_only_preservation_audit_v1", "evidence_anchor_commit": ANCHOR,
                  "prior_files_unchanged": len(old), "sources_checked": len(inputs), "new_source_hashes": {n: sha(REPO/n) for n in new_sources},
                  "source_documents_and_committed_reports_only": True,
                  "raw_telemetry_restored_or_decoded": False, "receiver_outcomes_opened": False,
                  "new_capture_or_panel_instantiation": False, "new_model_or_calibration_fit": False,
                  "new_effect_estimate_or_cross_study_pooling": False, "successor_selected": False,
                  "old_paper_unchanged_new_edition_created": True, "prior_evidence_deleted": 0})
    return audit()


def audit():
    ledger, audit_record = read(LEDGER), read(AUDIT)
    old = anchor_files()
    assert old == read(FREEZE)["files"]
    for name, meta in ledger["sources"].items():
        assert sha(REPO/name) == meta["sha256"] and (REPO/name).stat().st_size == meta["bytes"], name
    assert ledger["critical_frozen_values"] == quantities()
    assert TABLE.read_text() == paper_table(ledger["critical_frozen_values"])
    for name, digest in audit_record["new_source_hashes"].items():
        assert sha(REPO/name) == digest, "synthesis source drift: " + name
    return {"verified": True, "prior_files_unchanged": len(old), "cited_source_files": len(ledger["sources"]),
            "studies_separately_classified": len(ledger["studies"]), "hypotheses_separately_classified": len(HYPOTHESES),
            "new_models_native_sessions_or_effect_estimates": 0, "successor_selected": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["render", "create", "audit"])
    args = parser.parse_args()
    print(json.dumps(globals()[args.command]()))
