"""Audit completed M5 preservation and frozen-analysis bindings, without new tests.

Run after archiving. This helper is outside the scientific registration and
never edits raw evidence, changes eligibility, or computes new causal results.
"""
import importlib.util
import json
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("m5_audit_dependencies", REPO / "tools/measure_prefix_memory_m5.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
PREFIX = "native-prefix-memory-m5-20261014-01"
STAGE = m.v.CACHE / (PREFIX + "-archive-stage")
RECEIPT = REPO / "docs/storage-receipts" / (PREFIX + ".json")


def audit():
    verification = m.verify()
    protocol, index = m.v.core.check_capture_integrity(m.ROOT)
    gate_path = m.ROOT / "prefix_memory_qualification_gate.json"
    summary_path = m.ROOT / "prefix_memory_summary.json"
    gate, result = m.v.read(gate_path), m.v.read(summary_path)
    receipt = m.v.read(RECEIPT)
    registration = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", *m.REGISTRATION], cwd=REPO, text=True
    ).strip()
    assert len(registration) == 40
    assert receipt["scientific_registration_commit"] == registration == result["registration_commit"]
    assert len(index["sessions"]) == len({x["trial"] for x in index["sessions"]}) == 84
    assert result["gate_sha256"] == m.v.sha(gate_path)
    assert result["protocol_sha256"] == receipt["protocol_sha256"] == m.v.sha(m.ROOT / "protocol.json")
    assert result["capture_index_sha256"] == receipt["capture_index_sha256"] == m.v.sha(m.ROOT / "capture_index.json")
    assert receipt["prefix_memory_gate_sha256"] == m.v.sha(gate_path)
    assert receipt["prefix_memory_gate_passed"] == gate["passed"] == result["full_gate_passed"]
    assert receipt["gate_sha256"] == m.v.sha(m.ROOT / "mechanism_qualification_gate.json")
    assert receipt["base_gate_sha256"] == m.v.sha(m.ROOT / "support_clock_transport_gate.json")
    assert receipt["private"] and receipt["remote_fresh_download_verified"]
    assert receipt["archive_and_restored_file_checksums_verified"] and receipt["files_deleted"] == 0
    upload = m.v.read(STAGE / "upload-commit.json")
    assert upload["revision"] == receipt["revision"] and upload["prefix"] == PREFIX
    inventory = m.v.read(STAGE / "file-index.json")["files"]
    actual = {p.relative_to(m.ROOT).as_posix(): {"size": p.stat().st_size, "sha256": m.v.sha(p)}
              for p in sorted(m.ROOT.rglob("*")) if p.is_file()}
    assert not any(p.is_symlink() for p in m.ROOT.rglob("*"))
    assert inventory == actual and len(actual) == receipt["files_verified"]
    for name, expected in receipt["parts"].items():
        path = STAGE / name
        assert path.stat().st_size == expected["size"] and m.v.sha(path) == expected["sha256"]
    assert m.v.sha(REPO / "reports/native-prefix-memory-m5-summary.json") == m.v.sha(summary_path)
    assert m.v.sha(REPO / "reports/native-prefix-memory-m5-gate.json") == m.v.sha(gate_path)
    references = []
    if gate["passed"]:
        for content in sorted(result["contents"]):
            for endpoint in m.ENDPOINTS:
                window = result["contents"][content]["windows"][str(endpoint)]
                record = window["randomization"]
                path = m.ROOT / record["reference_file"]
                assert m.v.sha(path) == record["reference_sha256"]
                with np.load(path) as arrays:
                    assert arrays["w1"].shape == (2 ** 20,)
                    assert int(arrays["complementary_weight"]) == 2 and int(arrays["swaps"]) == 2 ** 21
                    assert np.array_equal(arrays["paired_ascending"], window["ascending_x"])
                    assert np.array_equal(arrays["paired_descending"], window["descending_x"])
                references.append(record["reference_file"])
        assert len(references) == 8
    else:
        assert not list(m.ROOT.glob("randomization-*.npz"))
        assert all(not w["estimable"] for c in result["contents"].values() for w in c["windows"].values())
    for key in ("predictors_fitted", "controller_state_redesigned", "controller_fitted",
                "delivery_qoe_action_outcomes_read", "v13_reopened", "prior_or_instrumentation_captures_pooled",
                "native_common_support_established"):
        assert result[key] is False
    assert result["bitrate_actions_assigned"] == 0
    assert protocol["prior_freeze_sha256"] == m.v.read(m.CONFIG)["prior_freeze_sha256"]
    for name, checksum in protocol["prior_freeze_sha256"].items():
        assert m.v.sha(REPO / name) == checksum
    cache_roots = sorted(p for p in m.v.CACHE.iterdir() if p.is_dir() and
                         p.name.startswith(("native-prefix-instrumentation-m4", "native-prefix-memory-m5")))
    storage = {p.name: sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())
               for p in cache_roots}
    workflow_bytes = sum(storage.values())
    project_bytes = sum(p.stat().st_size for p in REPO.rglob("*") if p.is_file() and not p.is_symlink())
    # Fresh downloaded copies were removed only by their TemporaryDirectory;
    # every original capture and archive stage is retained. Bound that peak too.
    fresh_object_bytes = sum(p["size"] for p in receipt["parts"].values())
    assert project_bytes < 10000000000 and workflow_bytes + fresh_object_bytes < 2000000000
    report = {
        "abi": "native_prefix_memory_m5_preservation_audit_v1",
        "scientific_registration_commit": registration,
        "verification": verification,
        "original_attempts": len(index["sessions"]),
        "sealed_sessions": sum(x["status"] == "sealed" for x in index["sessions"]),
        "qualified_sessions": gate["qualified_sessions"],
        "full_prefix_gate_passed": gate["passed"],
        "frozen_exact_reference_arrays_verified": len(references),
        "raw_files_exactly_match_archived_inventory": len(actual),
        "remote_objects_freshly_verified": len(receipt["parts"]),
        "pinned_archive_revision": receipt["revision"],
        "prior_tracked_files_unchanged": len(protocol["prior_freeze_sha256"]),
        "external_new_workflow_bytes": workflow_bytes,
        "external_peak_bound_including_fresh_download_bytes": workflow_bytes + fresh_object_bytes,
        "external_workflow_limit_bytes": 2000000000,
        "external_storage_by_root": storage,
        "project_bytes": project_bytes,
        "project_limit_bytes": 10000000000,
        "files_deleted": 0,
        "predictors_fitted": False,
        "controller_fitted": False,
        "new_inferential_tests": 0,
        "delivery_qoe_action_outcomes_read": False,
        "audit_source_sha256": m.v.sha(Path(__file__).resolve()),
        "receipt_sha256": m.v.sha(RECEIPT),
    }
    output = REPO / "reports/native-prefix-memory-m5-preservation-audit.json"
    assert not output.exists(), "preserve completed audit"
    m.v.write(output, report)
    return {k: report[k] for k in ("original_attempts", "sealed_sessions", "qualified_sessions", "full_prefix_gate_passed",
                                  "raw_files_exactly_match_archived_inventory", "prior_tracked_files_unchanged",
                                  "external_peak_bound_including_fresh_download_bytes", "files_deleted")}


if __name__ == "__main__":
    print(json.dumps(audit()))
