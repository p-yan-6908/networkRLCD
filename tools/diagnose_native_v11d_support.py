"""Diagnose V11D hold coverage from an explicit support-only projection.

Frame/outcome files are hashed to verify their seals, never decoded. Only the
randomized assignments, BWE feature zero, action readback, and timing in the
sender file are accessed. This does not import an outcome-analysis loader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path.home() / ".cache/networkrlcd/native-clock-action-turntcp-v11d"
STATES = ("bwe_lt_500k", "bwe_ge_500k")
RATIOS = (0.65, 1.05)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def support_projection(path: Path, trial: dict, seed: int) -> list[dict]:
    sender = read(path)
    by_epoch = {}
    for decision in sender["decisions"]:
        a = decision.get("actuator_assignment")
        if not isinstance(a, dict):
            continue
        epoch = a["epoch"]
        if epoch in by_epoch:
            continue
        bwe = a["base_bwe_bps"]
        draw = int.from_bytes(hashlib.sha256(
            f"networkrlcd-native-v9:{seed}:{trial['id']}:{epoch}".encode()).digest()[:4], "big")
        ratio = 1.05 if draw & 1 else 0.65
        state = STATES[int(bwe >= 500000)]
        cap = max(150000, min(4000000, math.floor(ratio * bwe + 0.5)))
        feature_bwe = decision["policy_input"]["features"][0] * 4000000
        assert a["randomization_seed"] == seed and a["trial_id"] == trial["id"]
        assert a["draw_uint32"] == draw and a["ratio"] == ratio and a["state_bin"] == state
        assert a["propensity"] == 0.5 and a["requested_bps"] == cap
        assert abs(feature_bwe - bwe) < 0.01
        assert decision["sample_ms"] == a["assignment_ms"]
        assert decision["proposed_action"]["encoder_max_bitrate_bps"] == cap
        assert decision["actuation_readback"]["encoder_max_bitrate_bps"] == cap
        by_epoch[epoch] = {
            "epoch": epoch, "state_bin": state, "ratio": ratio,
            "pre_action_bwe_bps": bwe, "requested_cap_bps": cap,
            "assignment_offset_ms": a["assignment_ms"] - sender["measurement_start_ms"],
            "ack_offset_ms": decision["ack_ms"] - sender["measurement_start_ms"],
        }
    assert sorted(by_epoch) == list(range(6))
    return [by_epoch[i] for i in range(6)]


def diagnose(root: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError(f"preserve existing diagnosis: {output}")
    protocol = read(root / "protocol.json")
    assert sha(root / "protocol.json") == sha(REPO / "configs/native_clock_action_probe_turn_tcp_v11d.json")
    index = read(root / "capture_index.json")
    trials = {trial["id"]: trial for trial in protocol["trials"]}
    sessions, verified_files = [], 0
    for item in index["sessions"]:
        assert item["status"] == "sealed"
        trial = trials[item["trial"]]
        directory = root / "sessions" / item["trial"]
        assert sha(directory / "integrity.json") == item["integrity_manifest_sha256"]
        manifest = read(directory / "integrity.json")
        for name, expected in manifest["files"].items():
            assert sha(directory / name) == expected, (trial["id"], name)
            verified_files += 1
        holds = support_projection(directory / "sender_observations.json", trial,
                                   protocol["randomization"]["seed"])
        sessions.append({**{key: trial[key] for key in (
            "id", "cell_cluster", "content_id", "network_family", "network_campaign_id",
            "network_profile_id", "repetition")}, "holds": holds})
    assert len(sessions) == len(trials) == 64
    minimum = protocol["analysis"]["minimum_hold_windows_per_cell_state_action"]
    cells = {}
    for cell in protocol["cell_clusters"]["ids"]:
        rows = [hold for session in sessions if session["cell_cluster"] == cell
                for hold in session["holds"]]
        counts = Counter((row["state_bin"], row["ratio"]) for row in rows)
        state_counts = Counter(row["state_bin"] for row in rows)
        missing = [{"state": state, "ratio": ratio, "count": counts[state, ratio],
                    "shortfall": minimum - counts[state, ratio]}
                   for state in STATES for ratio in RATIOS if counts[state, ratio] < minimum]
        first = next(s for s in sessions if s["cell_cluster"] == cell)
        cells[cell] = {
            "content_id": first["content_id"], "network_family": first["network_family"],
            "network_campaign_id": first["network_campaign_id"],
            "counts": {state: {str(ratio): counts[state, ratio] for ratio in RATIOS} for state in STATES},
            "state_totals": {state: state_counts[state] for state in STATES},
            "missing_groups": missing, "complete": not missing,
            "failure_class": (None if not missing else "insufficient_state_visits" if any(
                state_counts[state] < 2 * minimum for state in STATES) else "random_arm_imbalance"),
        }
    epochs = {}
    for epoch in range(6):
        rows = [session["holds"][epoch] for session in sessions]
        epochs[str(epoch)] = {
            "low_state": sum(row["state_bin"] == STATES[0] for row in rows),
            "high_state": sum(row["state_bin"] == STATES[1] for row in rows),
            "bwe_min_median_max_bps": [min(row["pre_action_bwe_bps"] for row in rows),
                statistics.median(row["pre_action_bwe_bps"] for row in rows),
                max(row["pre_action_bwe_bps"] for row in rows)],
            "assignment_offset_min_max_ms": [min(row["assignment_offset_ms"] for row in rows),
                                             max(row["assignment_offset_ms"] for row in rows)],
        }
    by_family, by_content = {}, {}
    for field, destination in (("network_family", by_family), ("content_id", by_content)):
        for key in sorted({session[field] for session in sessions}):
            selected = [row for row in cells.values() if row[field] == key]
            holds = [hold for session in sessions if session[field] == key for hold in session["holds"]]
            destination[key] = {"complete_cells": sum(row["complete"] for row in selected),
                "cells": len(selected), "low_holds": sum(h["state_bin"] == STATES[0] for h in holds),
                "high_holds": sum(h["state_bin"] == STATES[1] for h in holds),
                "failure_classes": dict(Counter(row["failure_class"] for row in selected if not row["complete"]))}
    profiles = read(REPO / "data/native-v11d/network_profiles.json")
    report = {
        "abi": "native_v11d_design_support_diagnosis_v1",
        "anchor_commit": "92a6ae3", "tool_sha256": sha(Path(__file__).resolve()),
        "protocol_sha256": sha(root / "protocol.json"),
        "capture_index_sha256": sha(root / "capture_index.json"),
        "verified_session_files": verified_files,
        "input_projection": {
            "decoded": ["protocol.json", "capture_index.json", "integrity.json",
                        "sender_observations.json assignments, BWE feature zero, action readback, timing",
                        "registered network_profiles.json and panel source schedules"],
            "outcome_files_decoded": [], "outcome_analysis_loaders_imported": False,
            "frozen_hold_count_minimum": minimum,
            "frozen_required_complete_cells": protocol["analysis"]["minimum_complete_content_network_cells"],
        },
        "hold_count": sum(len(session["holds"]) for session in sessions),
        "complete_cells": sum(row["complete"] for row in cells.values()),
        "failed_cells": sum(not row["complete"] for row in cells.values()),
        "failure_classes": dict(Counter(row["failure_class"] for row in cells.values() if not row["complete"])),
        "cells": cells, "by_family": by_family, "by_content": by_content, "by_epoch": epochs,
        "sessions": sessions,
        "registered_trace_source_checksum": sha(REPO / "data/native-v11d/network_profiles.json"),
        "registered_trace_document_keys": list(profiles),
        "interpretation_limits": [
            "Replay-rate threshold crossings are not browser BWE state visits.",
            "Later pre-action BWE reflects content, transport adaptation and prior randomized actions; associations are development diagnostics, not causal effects.",
            "The initial 300kbps BWE is startup initialization rather than proof of steady low-network support.",
            "No PSNR, frame delivery, relay delivery/drop cost or treatment effect was examined by this diagnosis.",
            "Coverage thresholds are unchanged; no missing holds or outcomes are imputed.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=REPO / "reports/native-v11d-support-diagnosis.json")
    args = parser.parse_args()
    result = diagnose(args.root, args.out)
    print(json.dumps({key: result[key] for key in ("complete_cells", "failed_cells", "failure_classes", "by_family", "by_content", "by_epoch")}))
