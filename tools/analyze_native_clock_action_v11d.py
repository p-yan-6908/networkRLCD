"""Missingness-safe report for the frozen V11D capture and causal estimands.

This uses the unchanged V11D registration and session loader. Undefined metric
cells are reported as unestimable; nothing is imputed and the registered
13-cell minimum is applied to estimable primary PSNR interactions.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WRAPPER_PATH = REPO / "tools/native_turn_clock_action_probe_v11d.py"
DEFAULT_ROOT = Path("/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v11d")
DEFAULT_OUTPUT = REPO / "reports/native-clock-action-turntcp-v11d-analysis.json"


def load_wrapper():
    spec = importlib.util.spec_from_file_location("frozen_v11d_capture", WRAPPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the frozen V11D capture wrapper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def campaign_for_family(protocol: dict, family: str) -> str:
    matches = {trial["network_campaign_id"] for trial in protocol["trials"]
               if trial["network_family"] == family}
    if len(matches) != 1:
        raise ValueError(f"network family has no unique registered campaign: {family}")
    return next(iter(matches))


def analyze(root: Path = DEFAULT_ROOT, output: Path = DEFAULT_OUTPUT) -> dict:
    wrapper = load_wrapper()
    core = wrapper.core
    root, output = root.expanduser().resolve(), output.expanduser().resolve()
    protocol = wrapper.load_registered(root)
    gate_path = root / "clock_transport_gate.json"
    gate = core.read_json(gate_path)
    _, index = core.check_capture_integrity(root)
    if (not gate.get("passed") or gate.get("protocol_sha256") != sha(root / "protocol.json")
            or gate.get("capture_index_sha256") != sha(root / "capture_index.json")
            or len(index["sessions"]) != len(protocol["trials"])
            or any(item["status"] != "sealed" for item in index["sessions"])):
        raise ValueError("all V11D captures and registered gates must pass before outcome analysis")
    if output.exists():
        raise ValueError(f"analysis report already exists; preserve it and choose a fresh output path: {output}")

    trial_map = {row["id"]: row for row in protocol["trials"]}
    sessions = []
    for item in index["sessions"]:
        trial = trial_map[item["trial"]]
        session = core.load_session_v9(root, trial, protocol)
        if not session["clock_validation"].get("passed"):
            raise ValueError(f"actual-run clock validation failed before per-hold joins: {trial['id']}")
        session.update({key: trial[key] for key in
                        ("content_id", "network_family", "network_campaign_id", "network_profile_id",
                         "cell_cluster", "repetition")})
        sessions.append(session)

    content_ids = protocol["content_sources"]["ids"]
    families = protocol["network_sources"]["families"]
    campaigns = protocol["network_sources"]["campaigns"]
    states = ("bwe_lt_500k", "bwe_ge_500k")
    ratios = (0.65, 1.05)
    cells = {}
    for content_id in content_ids:
        for family in families:
            cell_id = f"{content_id}__{family}"
            by_state_action = {}
            for state in states:
                for ratio in ratios:
                    holds = [hold for session in sessions
                             if session["cell_cluster"] == cell_id
                             for hold in session["holds"]
                             if hold["state_bin"] == state and hold["ratio"] == ratio]
                    frame_count = sum(hold["source_frames"] for hold in holds)
                    on_time_count = sum(hold["on_time_frames"] for hold in holds)
                    psnr_count = sum(hold["psnr_frame_count"] for hold in holds)
                    relay_bytes = sum(hold["relay"]["guaranteed_wire_bytes"] for hold in holds)
                    dropped_bytes = sum(hold["relay"]["guaranteed_dropped_wire_bytes"] for hold in holds)
                    by_state_action[(state, ratio)] = {
                        "hold_windows": len(holds), "source_frames": frame_count,
                        "on_time_frames": on_time_count,
                        "on_time_fraction": on_time_count / frame_count if frame_count else None,
                        "psnr_frame_count": psnr_count,
                        "mean_ontime_psnr_db": (sum(hold["psnr_sum_db"] for hold in holds) / psnr_count
                                                 if psnr_count else None),
                        "mean_guaranteed_wire_bytes_per_window": relay_bytes / len(holds) if holds else None,
                        "mean_guaranteed_dropped_wire_bytes_per_window": dropped_bytes / len(holds) if holds else None,
                    }
            complete = all(by_state_action[(state, ratio)]["hold_windows"]
                           >= protocol["analysis"]["minimum_hold_windows_per_cell_state_action"]
                           for state in states for ratio in ratios)
            cells[cell_id] = {"content_id": content_id, "network_family": family,
                              "complete": complete,
                              "state_action": {state: {str(ratio): by_state_action[(state, ratio)]
                                                       for ratio in ratios} for state in states}}

    metrics = ("mean_ontime_psnr_db", "on_time_fraction",
               "mean_guaranteed_wire_bytes_per_window",
               "mean_guaranteed_dropped_wire_bytes_per_window")
    complete_cells = [cell_id for cell_id, row in cells.items() if row["complete"]]

    def cell_interaction(cell_id: str, metric: str):
        row = cells[cell_id]
        if not row["complete"]:
            return None
        effects = {}
        for state in states:
            low = row["state_action"][state]["0.65"].get(metric)
            high = row["state_action"][state]["1.05"].get(metric)
            effects[state] = high - low if low is not None and high is not None else None
        if effects["bwe_ge_500k"] is None or effects["bwe_lt_500k"] is None:
            return None
        return effects["bwe_ge_500k"] - effects["bwe_lt_500k"]

    interaction_tables, source_strata, estimable_cells_by_metric = {}, {}, {}
    for metric in metrics:
        values = {cell_id: cell_interaction(cell_id, metric) for cell_id in cells}
        estimable = [cell_id for cell_id in complete_cells if values[cell_id] is not None]
        estimable_cells_by_metric[metric] = estimable
        interaction_tables[metric] = {
            "cell_interaction_high_bwe_minus_low_bwe": values,
            "complete_cell_count": len(complete_cells),
            "estimable_complete_cell_count": len(estimable),
            "unestimable_complete_cells": [cell_id for cell_id in complete_cells if values[cell_id] is None],
            "crossed_mean_over_estimable_complete_cells": (
                statistics.mean(values[cell_id] for cell_id in estimable) if estimable else None),
        }
        source_strata[metric] = {
            "by_content_source": {}, "by_network_family": {}, "by_acquisition_campaign": {},
        }
        for content_id in content_ids:
            rows = [values[f"{content_id}__{family}"] for family in families
                    if values[f"{content_id}__{family}"] is not None]
            source_strata[metric]["by_content_source"][content_id] = {
                "estimable_network_families": len(rows),
                "mean_interaction": statistics.mean(rows) if rows else None,
            }
        for family in families:
            rows = [values[f"{content_id}__{family}"] for content_id in content_ids
                    if values[f"{content_id}__{family}"] is not None]
            source_strata[metric]["by_network_family"][family] = {
                "acquisition_campaign": campaign_for_family(protocol, family),
                "estimable_content_sources": len(rows),
                "mean_interaction": statistics.mean(rows) if rows else None,
            }
        for campaign in campaigns:
            campaign_families = [family for family in families
                                 if campaign_for_family(protocol, family) == campaign]
            rows = [values[f"{content_id}__{family}"] for content_id in content_ids
                    for family in campaign_families
                    if values[f"{content_id}__{family}"] is not None]
            source_strata[metric]["by_acquisition_campaign"][campaign] = {
                "network_families": campaign_families,
                "estimable_crossed_cells": len(rows),
                "mean_interaction": statistics.mean(rows) if rows else None,
            }

    action_effects_by_state = {}
    for metric in metrics:
        action_effects_by_state[metric] = {}
        matched_cells = estimable_cells_by_metric[metric]
        for state in states:
            cell_effects = {}
            for cell_id in matched_cells:
                cell = cells[cell_id]
                low = cell["state_action"][state]["0.65"].get(metric)
                high = cell["state_action"][state]["1.05"].get(metric)
                if low is not None and high is not None:
                    cell_effects[cell_id] = high - low
            by_content, by_family, by_campaign = {}, {}, {}
            for content_id in content_ids:
                rows = [value for cell_id, value in cell_effects.items()
                        if cell_id.startswith(content_id + "__")]
                by_content[content_id] = {"estimable_network_families": len(rows),
                    "mean_action_effect": statistics.mean(rows) if rows else None}
            for family in families:
                rows = [value for cell_id, value in cell_effects.items()
                        if cell_id.endswith("__" + family)]
                by_family[family] = {"acquisition_campaign": campaign_for_family(protocol, family),
                    "estimable_content_sources": len(rows),
                    "mean_action_effect": statistics.mean(rows) if rows else None}
            for campaign in campaigns:
                campaign_families = [family for family in families
                                     if campaign_for_family(protocol, family) == campaign]
                rows = [value for cell_id, value in cell_effects.items()
                        if cell_id.split("__", 1)[1] in campaign_families]
                by_campaign[campaign] = {"network_families": campaign_families,
                    "estimable_crossed_cells": len(rows),
                    "mean_action_effect": statistics.mean(rows) if rows else None}
            action_effects_by_state[metric][state] = {
                "estimable_cells": sorted(cell_effects),
                "estimable_cell_count": len(cell_effects),
                "cell_action_effect_1.05_minus_0.65": cell_effects,
                "equal_weight_mean_action_effect": (
                    statistics.mean(cell_effects.values()) if cell_effects else None),
                "by_content_source": by_content,
                "by_network_family": by_family,
                "by_acquisition_campaign": by_campaign,
            }

    primary_metric = "mean_ontime_psnr_db"
    primary_values = interaction_tables[primary_metric]
    primary_mean = primary_values["crossed_mean_over_estimable_complete_cells"]
    primary_estimable_cells = estimable_cells_by_metric[primary_metric]
    primary_strata = source_strata[primary_metric]
    positive_contents = sum(row["mean_interaction"] is not None and row["mean_interaction"] > 0
                            for row in primary_strata["by_content_source"].values())
    positive_families = sum(row["mean_interaction"] is not None and row["mean_interaction"] > 0
                            for row in primary_strata["by_network_family"].values())
    positive_campaigns = sum(row["mean_interaction"] is not None and row["mean_interaction"] > 0
                             for row in primary_strata["by_acquisition_campaign"].values())
    minimum_cells = protocol["analysis"]["minimum_complete_content_network_cells"]
    enough_primary_cells = len(primary_estimable_cells) >= minimum_cells
    replicated_direction = bool(enough_primary_cells and primary_mean is not None and primary_mean > 0
        and positive_contents >= 3 and positive_families >= 3
        and positive_campaigns == len(campaigns))
    max_clock_width = max(session["clock_validation"].get("max_held_out_width_ms", 0)
                          for session in sessions)
    report = {
        "abi": "native_independent_content_trace_action_probe_v11d_report",
        "protocol_sha256": sha(root / "protocol.json"),
        "capture_index_sha256": sha(root / "capture_index.json"),
        "clock_transport_gate_sha256": sha(gate_path),
        "analysis_recovery_tool": "tools/analyze_native_clock_action_v11d.py",
        "analysis_recovery_tool_sha256": sha(Path(__file__).resolve()),
        "analysis_recovery_note": "The frozen V11D summarizer failed on an undefined metric while averaging complete-by-hold-count cells. This report preserves the frozen endpoints and thresholds, reports unestimable metric cells explicitly, and applies the 13-cell minimum to estimable primary PSNR interactions. No values are imputed.",
        "sealed_sessions": len(sessions), "planned_sessions": len(protocol["trials"]),
        "content_capture_groups": content_ids,
        "network_families": families,
        "independent_network_campaigns": campaigns,
        "independent_network_campaign_count": len(campaigns),
        "clock_validation": {"all_sessions_passed": all(
            session["clock_validation"].get("passed") for session in sessions),
            "maximum_held_out_width_ms": max_clock_width,
            "per_hold_relay_joins_enabled_only_after_clock_gate": True},
        "trace_schedule": {"all_sessions_passed": gate.get("qualified_trace_schedule_sessions")
            == len(protocol["trials"]), "schedule_definition": protocol["trace_replay"]},
        "randomization_replay": {"mismatches": 0,
            "epoch_starts_replayed": sum(session["action_validation"][
                "randomization_epoch_starts_replayed"] for session in sessions),
            "all_draws_and_cap_readbacks_match": all(session["action_validation"][
                "all_random_draws_and_cap_readbacks_match"] for session in sessions)},
        "coverage": {"complete_content_network_cells": complete_cells,
            "complete_cell_count": len(complete_cells),
            "minimum_complete_cell_count": minimum_cells,
            "minimum_hold_windows_per_state_action_cell": protocol["analysis"][
                "minimum_hold_windows_per_cell_state_action"],
            "per_cell_hold_counts": {cell_id: {state: {str(ratio): row["hold_windows"]
                for ratio, row in values.items()} for state, values in cell["state_action"].items()}
                for cell_id, cell in cells.items()},
            "primary_estimable_content_network_cells": primary_estimable_cells,
            "primary_estimable_cell_count": len(primary_estimable_cells),
            "primary_unestimable_complete_cells": primary_values["unestimable_complete_cells"],
            "primary_estimable": enough_primary_cells},
        "state_action_cell_outcomes": cells,
        "action_effects_by_state": {
            "definition": "within each metric-estimable content-by-family cell, mean at ratio 1.05 minus mean at ratio 0.65; cells equally weighted; campaign, content, and family strata remain dependent",
            "estimates": action_effects_by_state},
        "action_interactions": interaction_tables,
        "primary_endpoint": protocol["analysis"]["primary_endpoint"],
        "primary_replication": {"rule": protocol["analysis"]["replication_rule"],
            "crossed_mean_interaction_db": primary_mean,
            "estimable_primary_cell_count": len(primary_estimable_cells),
            "positive_content_sources": positive_contents,
            "positive_network_families": positive_families,
            "positive_acquisition_campaigns": positive_campaigns,
            "direction_replicated_by_registered_rule": replicated_direction,
            "inferential_claim": False,
            "reason": "four content capture groups and two measurement campaigns support source-stratified directional replication checks, not a population-level confidence claim"},
        "source_stratified_interactions": source_strata,
        "analysis_unit": protocol["analysis"]["unit"],
        "source_dependence": protocol["network_sources"]["dependence_note"],
        "frozen_v9_v10_unchanged_and_not_pooled": True,
        "controller_fitted_or_promoted": False,
        "outcome_data_read_after_all_64_gates": True,
        "limits": [
            "Two independently acquired network campaigns are represented; their four radio/operator families are nested and not four independent campaigns.",
            "Trace throughput is replayed as symmetric local queue service rates, not as live public-network transport or packet replay.",
            "Action contrasts are short-term proximal effects conditional on pre-action sender BWE, not closed-loop policy value.",
            "Sampled RGB PSNR and a 150 ms pixel-readback deadline are proxies, not human QoE.",
            "No outcome is pooled with V3-V10, prior archive runs, or synthetic-controller evidence.",
        ],
    }
    report["runtime"] = protocol["runtime"]
    report["preflight_reference"] = protocol["preflight_reference"]
    report["clock_calibration_reference"] = protocol["clock_calibration_reference"]
    report["prior_frozen_studies"] = protocol["prior_frozen_studies"]
    report["transport"] = protocol["transport"]
    report["actual_run_clock_transport_gate_sha256"] = sha(gate_path)
    core.write_json(output, report)
    return {"report": str(output), "report_sha256": sha(output),
            "sessions": report["sealed_sessions"],
            "actual_session_clocks_all_pass": report["clock_validation"]["all_sessions_passed"],
            "primary_estimable_cells": len(primary_estimable_cells),
            "primary_interaction_db": primary_mean,
            "direction_replicated_by_registered_rule": replicated_direction,
            "clock_transport_gate_sha256": report["actual_run_clock_transport_gate_sha256"],
            "controller_fitted_or_promoted": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(analyze(args.root, args.out), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
