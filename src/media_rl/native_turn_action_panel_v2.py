"""Read-only analysis of a frozen prospective factual native action panel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .native_turn_action_diagnostic import ARMS, _fit, _holm
from .native_turn_probe import summarize, validate_peer
from .native_turn_probe_v2 import verify_analysis_spec, verify_trials

ABI = "native_turn_probe_v2_action_assay_v1"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def verify_inventory(capture: Path, inventory_path: Path) -> dict:
    inventory = json.loads(inventory_path.read_text())
    if (
        inventory.get("abi") != ABI + "_local_evidence_inventory"
        or inventory.get("archive_verified") is not False
        or inventory.get("raw_bytes_pruned") is not False
        or Path(inventory.get("raw_capture", "")).resolve() != capture.resolve()
    ):
        raise ValueError("the unarchived local V2 evidence inventory is required")
    expected = {row["path"]: row for row in inventory.get("files", [])}
    actual = {}
    total = 0
    for path in sorted(capture.rglob("*")):
        if path.is_symlink():
            raise ValueError("raw evidence contains an unexpected symlink")
        if path.is_file():
            relative = path.relative_to(capture).as_posix()
            actual[relative] = path
    if actual.keys() != expected.keys():
        raise ValueError("V2 raw file inventory changed")
    for relative, path in actual.items():
        size = path.stat().st_size
        if expected[relative].get("bytes") != size or expected[relative].get("sha256") != sha(path):
            raise ValueError("V2 raw evidence hash mismatch: " + relative)
        total += size
    if total != inventory.get("total_bytes"):
        raise ValueError("V2 raw evidence byte count changed")
    return {
        "capture_file_count": len(actual),
        "capture_total_bytes": total,
        "inventory_sha256": sha(inventory_path),
        "capture_bytes_unmodified": True,
        "archive_verified": False,
        "raw_bytes_pruned": False,
    }


def _rows(sessions: list[dict], spec: dict) -> list[dict]:
    rows = []
    trial_by_id = {trial["id"]: trial for trial in spec["trials"]}
    if len(sessions) != 64:
        raise ValueError("the full prospectively registered 64-peer panel is required")
    for session in sessions:
        trial = session["trial"]
        if trial not in spec["trials"] or trial["id"] not in trial_by_id:
            raise ValueError("session is outside the frozen trial schedule")
        for epoch, cohort in enumerate(session["cohorts"]):
            if cohort["epoch"] != epoch:
                raise ValueError("native hold epochs must remain in recorded order")
            arm = int(cohort["arm"])
            if arm < 0 or arm >= len(ARMS) or cohort["ratio"] != ARMS[arm]:
                raise ValueError("native assigned arm does not match its frozen ratio")
            if not np.isclose(cohort["propensity"], 1 / 3, rtol=0, atol=1e-12):
                raise ValueError("the registered per-hold assignment probability changed")
            if (
                cohort["capture_requests"] < 0
                or cohort["on_time_requests"] < 0
                or cohort["on_time_requests"] > cohort["capture_requests"]
            ):
                raise ValueError("invalid request-level endpoint counts")
            rows.append(
                {
                    "peer": trial["id"],
                    "epoch": epoch,
                    "arm": arm,
                    "ratio": ARMS[arm],
                    "actual_payload_ratio": (
                        float(cohort["realized_ratio"]) if cohort["window_complete"] else None
                    ),
                    "window_complete": bool(cohort["window_complete"]),
                    "on_time_requests": int(cohort["on_time_requests"]),
                    "capture_requests": int(cohort["capture_requests"]),
                    "on_time_share": (
                        float(cohort["on_time_share"]) if cohort["on_time_share"] is not None else None
                    ),
                    "scene_seed": int(trial["scene_seed"]),
                    "regime": trial["regime"],
                    "repetition": int(trial["repetition"]),
                    "capture_order": int(trial["capture_order"]),
                    "clipped_or_aliased": bool(cohort["clipped_or_aliased"]),
                }
            )
    if len(rows) != 384 or len({row["peer"] for row in rows}) != 64:
        raise ValueError("the registered 64-peer / 384-hold panel is required")
    if any(sum(row["peer"] == peer for row in rows) != 6 for peer in {r["peer"] for r in rows}):
        raise ValueError("every peer must retain all six randomized assignments")
    return rows


def _arm_means(rows: list[dict], regime: str | None = None) -> list[dict]:
    result = []
    for arm, ratio in enumerate(ARMS):
        own = [row for row in rows if row["arm"] == arm and (regime is None or row["regime"] == regime)]
        complete = [row for row in own if row["actual_payload_ratio"] is not None]
        requests = sum(row["capture_requests"] for row in own)
        result.append(
            {
                "ratio": ratio,
                "holds": len(own),
                "complete_payload_windows": len(complete),
                "mean_actual_payload_ratio": (
                    float(np.mean([row["actual_payload_ratio"] for row in complete])) if complete else None
                ),
                "on_time_requests": sum(row["on_time_requests"] for row in own),
                "capture_requests": requests,
                "request_weighted_on_time_share": (
                    sum(row["on_time_requests"] for row in own) / requests if requests else None
                ),
                "aliased_assignments": sum(row["clipped_or_aliased"] for row in own),
            }
        )
    return result


def _outcomes(rows: list[dict]) -> list[dict]:
    payload = _fit(rows, "actual_payload_ratio", None)
    payload["name"] = "actual_payload_ratio"
    delivery = _fit(rows, "on_time_share", "capture_requests")
    delivery["name"] = "on_time_share"
    results = [payload, delivery]
    _holm(results)
    return results


def run(
    spec_path: Path,
    capture: Path,
    compact: Path,
    inventory_path: Path,
    audit_path: Path,
    out: Path,
) -> dict:
    spec_path, capture, compact = Path(spec_path), Path(capture), Path(compact)
    inventory_path, audit_path, out = Path(inventory_path), Path(audit_path), Path(out)
    if out.exists():
        raise ValueError("fresh V2 action-panel analysis directory required")
    project = Path(__file__).resolve().parents[2]
    spec = json.loads(spec_path.read_text())
    verify_trials(spec)
    verify_analysis_spec(spec)
    expected_capture = Path(spec["storage"]["raw_capture_root"]).expanduser().resolve()
    expected_compact = (project / spec["storage"]["compact_report_root"]).resolve()
    report = json.loads((compact / "report.json").read_text())
    reference = json.loads((compact / "sessions.json").read_text())
    audit = json.loads(audit_path.read_text())
    if (
        spec.get("abi") != ABI
        or spec.get("capture_role") != "prospective_development"
        or spec.get("native_counterfactuals") is not False
        or spec.get("controller_promoted") is not False
        or report.get("abi") != ABI + "_report"
        or report.get("analysis_status") != "prospective_native_development"
        or capture.resolve() != expected_capture
        or compact.resolve() != expected_compact
        or report.get("raw_capture") != str(capture.resolve())
        or report.get("spec_sha256") != sha(spec_path)
        or report.get("sessions") != 64
        or report.get("holds") != 384
        or audit.get("registered_spec_sha256") != sha(spec_path)
        or audit.get("registered_source_hashes_unchanged") is not True
        or audit.get("summaries_recomputed") is not True
        or audit.get("native_factual_only") is not True
        or audit.get("real_network_validation") is not False
        or audit.get("controller_promoted") is not False
        or len(audit.get("sessions", [])) != 64
        or any(
            row.get("wire", {}).get("raw_evidence_modified") is not False for row in audit.get("sessions", [])
        )
    ):
        raise ValueError("matching complete factual V2 report and independent audit are required")
    for relative, expected_sha in spec["source_sha256"].items():
        source = project / relative
        if not source.is_file() or sha(source) != expected_sha:
            raise ValueError("registered V2 source changed: " + relative)

    raw_provenance = verify_inventory(capture, inventory_path)
    sessions = []
    for trial in spec["trials"]:
        peer, assignments = validate_peer(capture / trial["id"], trial)
        sessions.append(summarize(peer, assignments, trial))
    if canonical(sessions) != canonical(reference):
        raise ValueError("raw factual replay differs from the compact V2 summaries")

    rows = _rows(sessions, spec)
    full_payload = all(row["window_complete"] and row["actual_payload_ratio"] is not None for row in rows)
    endpoint_complete = all(row["capture_requests"] > 0 and row["on_time_share"] is not None for row in rows)
    qualified = full_payload and endpoint_complete
    outcomes = _outcomes(rows) if qualified else []
    by_regime = {
        regime: _arm_means(rows, regime) for regime in sorted({trial["regime"] for trial in spec["trials"]})
    }
    action_support = []
    for regime in sorted({row["regime"] for row in rows}):
        for epoch in range(6):
            action_support.append(
                {
                    "regime": regime,
                    "epoch": epoch,
                    "assigned_by_ratio": {
                        f"{ratio:.2f}": sum(
                            row["regime"] == regime and row["epoch"] == epoch and row["ratio"] == ratio
                            for row in rows
                        )
                        for ratio in ARMS
                    },
                }
            )
    result = {
        "abi": ABI + "_action_diagnostic_report",
        "analysis_status": "prospective_native_development" if qualified else "unqualified_incomplete_panel",
        "native_factual_only": True,
        "native_counterfactuals": False,
        "controller_promoted": False,
        "real_network_validation": False,
        "controller_model_fitted": False,
        "sessions": len(sessions),
        "holds": len(rows),
        "peer_clusters": len({row["peer"] for row in rows}),
        "scene_seeds": len({row["scene_seed"] for row in rows}),
        "capacity_trace_patterns": len({row["regime"] for row in rows}),
        "complete_payload_windows": sum(row["window_complete"] for row in rows),
        "aliased_assignments": sum(row["clipped_or_aliased"] for row in rows),
        "all_assigned_rows_retained": True,
        "primary_endpoints_qualified": qualified,
        "arms": _arm_means(rows),
        "descriptive_by_trace_pattern": by_regime,
        "randomized_action_support": action_support,
        "outcomes": outcomes,
        "fixed_effects": spec["analysis"]["fixed_effects"],
        "covariance": spec["analysis"]["covariance"],
        "holm_family_size": 6 if qualified else 0,
        "familywise_alpha": spec["analysis"]["familywise_alpha"],
        "claim_limits": spec["claim_limits"],
        "spec_sha256": sha(spec_path),
        "report_sha256": sha(compact / "report.json"),
        "sessions_sha256": sha(compact / "sessions.json"),
        "inventory_sha256": raw_provenance["inventory_sha256"],
        "independent_audit_sha256": sha(audit_path),
        "raw_evidence_provenance": raw_provenance,
        "raw_capture": str(capture.resolve()),
        "no_capture_training_or_counterfactual_launched": True,
    }
    out.mkdir(parents=True)
    (out / "report.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    provenance = {
        "abi": ABI + "_action_diagnostic_provenance",
        "report_sha256": sha(out / "report.json"),
        "analysis_code_sha256": sha(Path(__file__)),
        "analysis_dependency_sha256": sha(project / "src/media_rl/native_turn_action_diagnostic.py"),
        "spec_sha256": sha(spec_path),
        "raw_evidence_provenance": raw_provenance,
        "registered_capture_sources_sha256": spec["source_sha256"],
        "project_root": str(project),
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    if qualified:
        lines = []
        for outcome in outcomes:
            for contrast in outcome["contrasts"]:
                lines.append(
                    {
                        "outcome": outcome["name"],
                        "contrast": contrast["contrast"],
                        "estimate": contrast["estimate"],
                        "ci95_low": contrast["ci95_low"],
                        "ci95_high": contrast["ci95_high"],
                        "p_value": contrast["p_value_two_sided"],
                        "p_value_holm": contrast["p_value_holm_all_six"],
                    }
                )
        (out / "contrasts.json").write_text(
            json.dumps(lines, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--compact", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            run(args.spec, args.capture, args.compact, args.inventory, args.audit, args.out),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
