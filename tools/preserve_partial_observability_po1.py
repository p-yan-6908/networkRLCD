"""Preserve PO1, including its negative gates, without altering prior freezes."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("po1_preservation", REPO / "tools/partial_observability_po1.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
PREFIX = "partial-observability-po1-20261015-01"
DATASET = "p-yan/networkrlcd-results-archive"
STAGE = m.CACHE / (PREFIX + "-archive")
RECEIPT = REPO / "docs/storage-receipts" / (PREFIX + ".json")


def preserve():
    audit = m.verify()
    result = m.read(m.ROOT / "analysis.json")
    assert result == m.read(REPO / "reports/partial-observability-po1-result.json")
    assert result["native_sessions"] == 0 and result["controller_fitted"] is False
    draft = m.read(m.DATA / "draft-01-supersession.json")
    for name, digest in draft["draft_source_sha256"].items():
        assert m.sha(Path(draft["draft_root"]) / name) == digest
    shutil.copytree(draft["draft_root"], m.ROOT / "superseded-pre-data-draft")
    for name in ["docs/PARTIAL_OBSERVABILITY_PO1_RESULTS.md", "reports/partial-observability-po1-result.json",
                 "reports/partial-observability-po1-runtime.json", "tools/preserve_partial_observability_po1.py",
                 "tools/report_partial_observability_po1.py", "reports/figures/partial-observability-po1.png"]:
        target = m.ROOT / "provenance" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists()
        shutil.copy2(REPO / name, target)
    shutil.copy2(m.CACHE / "po1-collect-console.log", m.ROOT / "collect-console.log")
    snapshots = {str(p.relative_to(m.ROOT)): m.sha(p) for p in sorted((m.ROOT / "provenance").rglob("*")) if p.is_file()}
    m.write(m.ROOT / "preservation-audit.json", {**audit, "protocol_sha256": m.sha(m.REGISTRATION),
                                                "result_sha256": m.sha(m.ROOT / "analysis.json"), "source_snapshots": snapshots,
                                                "native_sessions": 0, "native_reservation_untouched": True,
                                                "closed_native_telemetry_opened": False, "raw_evidence_deleted": 0})
    return {"preserved": True, **audit}


def archive():
    from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download

    m.verify()
    assert not STAGE.exists() and not RECEIPT.exists(), "fresh immutable namespace required"
    root = m.ROOT
    result = m.read(root / "analysis.json")
    lock = m.read(root / "model-lock.json")
    assert lock["protocol_sha256"] == m.sha(root / "protocol.json") == m.sha(m.REGISTRATION)
    assert lock["capture_index_sha256"] == m.sha(root / "capture-index.json")
    assert result["model_lock_sha256"] == m.sha(root / "model-lock.json")
    assert result["prediction_shard_sha256"] == m.sha(root / "validation-predictions.jsonl.gz")
    for name, digest in lock["models"].items():
        assert m.sha(root / name) == digest
    for name, meta in m.read(root / "capture-index.json")["shards"].items():
        assert (root / name).stat().st_size == meta["bytes"] and m.sha(root / name) == meta["sha256"]
    audit = m.read(root / "preservation-audit.json")
    for name, digest in audit["source_snapshots"].items():
        assert m.sha(root / name) == digest
    assert not any(p.is_symlink() for p in root.rglob("*"))
    files = {str(p.relative_to(root)): {"bytes": p.stat().st_size, "sha256": m.sha(p)} for p in sorted(root.rglob("*")) if p.is_file()}
    raw = sum(v["bytes"] for v in files.values())
    bounds = m.read(m.CONFIG)["storage"]
    assert raw <= bounds["maximum_raw_bytes"]
    STAGE.mkdir()
    part = STAGE / "evidence.tar.gz"
    with tarfile.open(part, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for name, meta in files.items():
            path = root / name
            assert m.sha(path) == meta["sha256"]
            tar.add(path, arcname=root.name + "/" + name, recursive=False)
            assert m.sha(path) == meta["sha256"]
    m.write(STAGE / "file-index.json", {"abi": "po1_synthetic_screen_inventory_v1", "member_root": root.name, "files": files})
    (STAGE / "SHA256SUMS").write_text(m.sha(part) + "  " + part.name + "\n")
    (STAGE / "RESTORE.md").write_text(
        "PO1 synthetic predictive/action-discrimination screen only. No native captures or controller. "
        "Fetch only this namespace at the receipt revision. Verify each object size/SHA, then "
        "each archive member size/SHA against file-index.json before reading targets. "
        "Use a fresh external directory; retain old freezes and failed gates. "
        "No licensed video originals or clips are included.\n")
    parts = {p.name: {"bytes": p.stat().st_size, "sha256": m.sha(p)} for p in sorted(STAGE.iterdir()) if p.is_file()}
    staged = sum(v["bytes"] for v in parts.values())
    assert raw + 2*staged <= bounds["maximum_raw_stage_fresh_bytes"]
    api = HfApi()
    info = api.dataset_info(DATASET)
    assert info.private
    assert not any(e.path == PREFIX for e in api.list_repo_tree(DATASET, repo_type="dataset", recursive=False))
    commit = api.create_commit(DATASET, repo_type="dataset", parent_commit=info.sha,
                               operations=[CommitOperationAdd(path_in_repo=PREFIX + "/" + name, path_or_fileobj=str(STAGE / name)) for name in parts],
                               commit_message="Preserve preregistered PO1 observable-history screen and stopping decision")
    revision = commit.oid
    m.write(STAGE / "upload-commit.json", {"repo_id": DATASET, "prefix": PREFIX, "revision": revision})
    with tempfile.TemporaryDirectory(dir=STAGE) as temporary:
        downloaded = {}
        for name, meta in parts.items():
            p = Path(hf_hub_download(DATASET, repo_type="dataset", filename=PREFIX + "/" + name,
                                     revision=revision, local_dir=temporary, force_download=True))
            assert p.stat().st_size == meta["bytes"] and m.sha(p) == meta["sha256"]
            downloaded[name] = p
        restored_index = m.read(downloaded["file-index.json"])
        assert restored_index["files"] == files
        with tarfile.open(downloaded[part.name], "r:gz") as tar:
            seen = set()
            for member in tar.getmembers():
                name = str(Path(member.name).relative_to(root.name))
                assert member.isfile() and name in files and name not in seen
                meta = files[name]
                assert member.size == meta["bytes"]
                assert hashlib.sha256(tar.extractfile(member).read()).hexdigest() == meta["sha256"]
                seen.add(name)
            assert seen == set(files)
        for name, path in downloaded.items():
            assert m.sha(path) == parts[name]["sha256"]
    receipt = {"abi": "po1_verified_synthetic_screen_archive_receipt_v1", "repo_id": DATASET, "private": True,
               "prefix": PREFIX, "revision": revision, "objects": parts, "objects_freshly_verified": len(parts),
               "members_freshly_size_sha256_verified": len(files), "archive_and_file_checksums_verified": True,
               "raw_evidence_retained": True, "raw_root": str(root), "evidence_deleted": 0,
               "protocol_sha256": m.sha(m.REGISTRATION), "registration_commit": result["registration_commit"],
               "result_sha256": m.sha(root / "analysis.json"), "preservation_audit_sha256": m.sha(root / "preservation-audit.json"),
               "synthetic_episodes": result["synthetic_episodes"], "synthetic_passed": result["synthetic_passed"],
               "native_sessions": 0, "native_reservation_untouched": True, "closed_native_data_opened": False,
               "controller_fitted": False, "prior_tracked_files_unchanged": audit["prior_files_unchanged"],
               "raw_bytes": raw, "stage_bytes": staged, "fresh_download_bytes": staged,
               "raw_stage_fresh_bytes": raw + 2*staged, "budget_bytes": bounds["maximum_raw_stage_fresh_bytes"],
               "archive_helper_sha256": m.sha(Path(__file__))}
    m.write(RECEIPT, receipt)
    m.write(REPO / "reports/partial-observability-po1-storage.json", receipt)
    return {"archive_verified": True, "revision": revision, "members": len(files), "objects": len(parts),
            "native_sessions": 0, "raw_deleted": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preserve", "archive"])
    args = parser.parse_args()
    print(json.dumps(globals()[args.command]()))
