"""Archive completed M11 evidence privately, verifying a fresh restoration.

This storage helper is outside the frozen scientific instrumentation. It never
decodes frame outcomes or raw event logs and never deletes local evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATASET = "p-yan/networkrlcd-results-archive"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def archive(root: Path, prefix: str, stage: Path):
    from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download
    root, stage = root.expanduser().resolve(), stage.expanduser().resolve()
    if not prefix or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in prefix):
        raise ValueError("fresh simple archive prefix required")
    protocol = json.loads((root / "protocol.json").read_text())
    index = json.loads((root / "capture_index.json").read_text())
    expected = {t["id"] for t in protocol["trials"]}
    if index["protocol_sha256"] != sha(root / "protocol.json") or {r["trial"] for r in index["sessions"]} != expected:
        raise ValueError("completed original session inventory required before archiving")
    if len(index["sessions"]) != len(expected):
        raise ValueError("duplicate session IDs")
    for item in index["sessions"]:
        directory = root / "sessions" / item["trial"]
        if sha(directory / "integrity.json") != item["integrity_manifest_sha256"]:
            raise ValueError("session seal drift")
        seal = json.loads((directory / "integrity.json").read_text())
        for name, checksum in seal["files"].items():
            if sha(directory / name) != checksum:
                raise ValueError(f"sealed evidence checksum mismatch: {item['trial']}/{name}")
    gate_path = root / "support_clock_transport_gate.json"
    gate = json.loads(gate_path.read_text())
    if gate["protocol_sha256"] != sha(root / "protocol.json") or gate["capture_index_sha256"] != sha(root / "capture_index.json"):
        raise ValueError("completed gate is not bound to this capture")
    stage.mkdir(parents=True, exist_ok=False)
    files = {str(p.relative_to(root)): {"size": p.stat().st_size, "sha256": sha(p)}
             for p in sorted(root.rglob("*")) if p.is_file()}
    if any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("raw archive tree must not contain symlinks")
    part = stage / "results.tar.part-000"
    with tarfile.open(part, "w", format=tarfile.PAX_FORMAT) as tar:
        for name, metadata in files.items():
            path = root / name
            if sha(path) != metadata["sha256"]:
                raise ValueError("source drift before archive packing")
            tar.add(path, arcname=root.name + "/" + name, recursive=False)
            if sha(path) != metadata["sha256"]:
                raise ValueError("source drift during archive packing")
    write(stage / "file-index.json", {"abi": "native_m11_raw_archive_inventory_v1", "member_root": root.name, "files": files})
    (stage / "SHA256SUMS").write_text(sha(part) + "  " + part.name + "\n")
    (stage / "RESTORE.md").write_text(
        "Fetch this namespace at the receipt's pinned revision. Verify SHA256SUMS, "
        "extract into a new empty external directory, then verify every member's "
        "size and SHA-256 against file-index.json before use. Never replace an "
        "existing frozen capture. This archive preserves its original protocol, "
        "failed checks and outcome-access restrictions. No licensed originals or "
        "media clips are included; local raw evidence is retained.\n")
    parts = {p.name: {"size": p.stat().st_size, "sha256": sha(p)} for p in sorted(stage.iterdir()) if p.is_file()}
    api = HfApi()
    info = api.dataset_info(DATASET)
    if not info.private:
        raise ValueError("private archive required")
    if any(entry.path == prefix for entry in api.list_repo_tree(DATASET, repo_type="dataset", recursive=False)):
        raise ValueError("archive namespace already exists; preserve it")
    operations = [CommitOperationAdd(path_in_repo=prefix + "/" + name, path_or_fileobj=str(stage / name)) for name in parts]
    commit = api.create_commit(DATASET, repo_type="dataset", operations=operations,
        commit_message="Preserve frozen M11 execution evidence", parent_commit=info.sha)
    revision = commit.oid
    # Record the exact committed revision before any fresh-download verification.
    write(stage / "upload-commit.json", {"repo_id": DATASET, "prefix": prefix, "revision": revision})
    with tempfile.TemporaryDirectory(dir=stage) as scratch:
        downloaded = {}
        for name, metadata in parts.items():
            path = Path(hf_hub_download(DATASET, repo_type="dataset", filename=prefix + "/" + name,
                                      revision=revision, local_dir=scratch, force_download=True))
            if path.stat().st_size != metadata["size"] or sha(path) != metadata["sha256"]:
                raise ValueError("fresh remote object checksum mismatch")
            downloaded[name] = path
        with tarfile.open(downloaded[part.name], "r") as tar:
            seen = set()
            for member in tar.getmembers():
                name = str(Path(member.name).relative_to(root.name))
                metadata = files.get(name)
                if not member.isfile() or metadata is None or member.size != metadata["size"]:
                    raise ValueError("unexpected restored archive member")
                if hashlib.sha256(tar.extractfile(member).read()).hexdigest() != metadata["sha256"]:
                    raise ValueError("restored file checksum mismatch")
                seen.add(name)
            if seen != set(files):
                raise ValueError("restored archive inventory incomplete")
    receipt = {"abi": "native_m11_execution_archive_receipt_v1", "repo_id": DATASET, "private": True,
        "prefix": prefix, "revision": revision, "parts": parts, "files_verified": len(files),
        "remote_fresh_download_verified": True, "archive_and_restored_file_checksums_verified": True,
        "local_raw_evidence_retained": True, "files_deleted": 0, "raw_capture_root": str(root),
        "protocol_sha256": sha(root / "protocol.json"), "capture_index_sha256": sha(root / "capture_index.json"),
        "gate_sha256": sha(gate_path), "registered_gate_passed": gate["passed"],
        "scientific_registration_commit": "fba94f71da4cc3be308b7ac88476b45935e8319c", "archive_helper_sha256": sha(Path(__file__).resolve())}
    receipt_path = REPO / "docs/storage-receipts" / (prefix + ".json")
    if receipt_path.exists():
        raise ValueError("preserve existing storage receipt")
    write(receipt_path, receipt)
    return {"archive_verified": True, "revision": revision, "files_verified": len(files), "files_deleted": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--stage", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(archive(args.root, args.prefix, args.stage)))
