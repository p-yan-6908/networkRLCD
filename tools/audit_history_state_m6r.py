"""Final M6R provenance/storage audit, without new support tests or fits."""
import importlib.util
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("m6r_audit_dependencies", REPO / "tools/measure_history_state_m6r.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
PREFIX = "native-history-state-m6r-20261014-01"
STAGE = m.v.CACHE / (PREFIX + "-archive-stage")
RECEIPT = REPO / "docs/storage-receipts" / (PREFIX + ".json")


def audit():
    verify = m.verify_validation()
    protocol, index = m.v.core.check_capture_integrity(m.CAPTURE_ROOT)
    summary_path = m.CAPTURE_ROOT / "history_state_summary.json"
    result = m.v.read(summary_path)
    receipt, inventory = m.v.read(RECEIPT), m.v.read(STAGE / "file-index.json")["files"]
    original = m.v.read(m.DESIGN)
    selection = m.v.read(m.SELECTION)
    registration = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", str(m.CONFIG.relative_to(REPO))], cwd=REPO, text=True).strip()
    assert len(registration) == 40 and receipt["scientific_registration_commit"] == registration
    assert receipt["state_design_registration_commit"] == selection["selection_registration_commit"]
    assert receipt["history_state_acquisition_gate_sha256"] == result["acquisition_gate_sha256"]
    assert result["acquisition_gate_sha256"] == m.v.sha(m.CAPTURE_ROOT / "history_state_acquisition_gate.json")
    assert result["protocol_sha256"] == receipt["protocol_sha256"] == m.v.sha(m.CONFIG)
    assert result["selected_state_sha256"] == receipt["selected_state_sha256"] == m.v.sha(m.SELECTION)
    assert result["design_sha256"] == receipt["state_design_sha256"] == m.v.sha(m.DESIGN)
    assert receipt["history_state_screen_qualified"] == result["history_state_qualified_for_this_support_screen"]
    assert receipt["private"] and receipt["remote_fresh_download_verified"] and receipt["archive_and_restored_file_checksums_verified"]
    assert receipt["files_deleted"] == 0 and receipt["local_raw_evidence_retained"]
    assert len(index["sessions"]) == len({x["trial"] for x in index["sessions"]}) == 32
    actual = {p.relative_to(m.CAPTURE_ROOT).as_posix(): {"size": p.stat().st_size, "sha256": m.v.sha(p)}
              for p in m.CAPTURE_ROOT.rglob("*") if p.is_file()}
    assert actual == inventory and len(actual) == receipt["files_verified"]
    assert not any(p.is_symlink() for p in m.CAPTURE_ROOT.rglob("*"))
    for name, metadata in receipt["parts"].items():
        p = STAGE / name
        assert p.stat().st_size == metadata["size"] and m.v.sha(p) == metadata["sha256"]
    assert m.v.read(STAGE / "upload-commit.json")["revision"] == receipt["revision"]
    assert m.v.sha(REPO / "reports/native-history-state-m6r-summary.json") == m.v.sha(summary_path)
    if result["acquisition_gate_passed"]:
        membership_path = m.CAPTURE_ROOT / "state_membership_gate.json"
        assert result["state_membership_gate_sha256"] == receipt["state_membership_gate_sha256"] == m.v.sha(membership_path)
        membership = m.v.read(membership_path)
        assert not membership["future_bwe_used_for_matching"]
        if not membership["passed"]:
            assert not result["support_matching_future_responses_estimable"]
            assert "state_results" not in result and not (m.CAPTURE_ROOT / "qualified_future_support_responses.json").exists()
        assert m.v.sha(m.CAPTURE_ROOT / "precutoff_support_features.json") == membership["precutoff_features_sha256"]
    for name, checksum in original["prior_freeze_sha256"].items():
        assert m.v.sha(REPO / name) == checksum
    # Preserve every failed M6 development byte in this new verified snapshot.
    failed = m.v.CACHE / "native-history-state-m6"
    for p in failed.rglob("*"):
        if p.is_file():
            target = m.CAPTURE_ROOT / "closed_m6_development" / p.relative_to(failed)
            assert target.is_file() and m.v.sha(target) == m.v.sha(p)
    # Reconfirm M5 itself was neither rewritten nor supplemented with new files.
    old = m.v.read(m.v.CACHE / "history-state-m6-input-verification/native-prefix-memory-m5-20261014-01/file-index.json")["files"]
    oldactual = {p.relative_to(m.m5.ROOT).as_posix(): {"size": p.stat().st_size, "sha256": m.v.sha(p)}
                 for p in m.m5.ROOT.rglob("*") if p.is_file()}
    assert oldactual == old
    roots = sorted(p for p in m.v.CACHE.iterdir() if p.is_dir() and p.name.startswith(("native-history-state-m6", "history-state-m6-input-verification")))
    storage = {p.name: sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink()) for p in roots}
    peak = sum(storage.values()) + sum(x["size"] for x in receipt["parts"].values())
    assert peak < 2000000000
    report = {"abi": "native_history_state_m6r_preservation_audit_v1", "verification": verify,
              "scientific_capture_registration_commit": registration,
              "state_design_registration_commit": selection["selection_registration_commit"],
              "new_original_attempts": len(index["sessions"]), "sealed": sum(x["status"] == "sealed" for x in index["sessions"]),
              "prior_frozen_files_unchanged": len(original["prior_freeze_sha256"]),
              "m5_archive_members_unchanged": len(old), "closed_m6_failed_development_preserved": True,
              "new_raw_members_match_verified_archive": len(actual), "remote_objects_freshly_verified": len(receipt["parts"]),
              "pinned_revision": receipt["revision"], "new_external_storage_by_root": storage,
              "new_external_peak_bound_with_fresh_download_bytes": peak, "planned_workflow_limit_bytes": 2000000000,
              "receipt_sha256": m.v.sha(RECEIPT), "audit_source_sha256": m.v.sha(Path(__file__).resolve()),
              "controller_fitted": False, "action_values_estimated": False, "files_deleted": 0,
              "delivery_qoe_action_outcomes_read": False, "new_inferential_tests": 0}
    out = REPO / "reports/native-history-state-m6r-preservation-audit.json"
    assert not out.exists(); m.v.write(out, report)
    return {k: report[k] for k in ("new_original_attempts", "sealed", "prior_frozen_files_unchanged", "m5_archive_members_unchanged",
                                  "new_raw_members_match_verified_archive", "new_external_peak_bound_with_fresh_download_bytes", "files_deleted")}


if __name__ == "__main__":
    print(json.dumps(audit()))
