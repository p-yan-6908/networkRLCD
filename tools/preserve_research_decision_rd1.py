"""Archive RD1's summary-only synthesis and paper, preserving all old freezes."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rd1_preservation", REPO / "tools/synthesize_research_decision_rd1.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
CACHE = Path.home() / ".cache/networkrlcd"
ROOT = CACHE / "research-decision-rd1"
PREFIX = "research-decision-rd1-20261015-01"
STAGE = CACHE / (PREFIX + "-archive")
DATASET = "p-yan/networkrlcd-results-archive"
RECEIPT = REPO / "docs/storage-receipts" / (PREFIX + ".json")
MAX_RAW, MAX_PEAK = 50_000_000, 150_000_000


def preserve():
    audit = m.audit()
    assert not (ROOT / "archive-bindings.json").exists()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    changes = subprocess.check_output(["git", "diff", m.ANCHOR, head, "--name-status"], cwd=REPO, text=True).splitlines()
    assert changes and all(x.startswith("A\t") for x in changes), "old frozen files must stay unchanged"
    new_files = [x.split("\t", 1)[1] for x in changes]
    assert "docs/RESEARCH_DECISION_RD1.md" in new_files and "paper/negative-result/main.tex" in new_files
    build = m.read(REPO / "reports/research-decision-rd1-paper-build.json")
    assert m.sha(ROOT / "paper-build/main.pdf") == build["pdf_sha256"] and build["unresolved_reference_tokens"] == 0
    for name, digest in build["source_sha256"].items():
        assert m.sha(REPO / name) == digest
    for name, digest in build["compile_logs_sha256"].items():
        assert m.sha(ROOT / "paper-build" / name) == digest
    inputs = set(m.read(m.LEDGER)["sources"])
    snapshots = {}
    for name in sorted(inputs | set(new_files)):
        target = ROOT / "source-snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists()
        shutil.copy2(REPO / name, target)
        snapshots[name] = m.sha(target)
        assert snapshots[name] == m.sha(REPO / name)
    m.write(ROOT / "archive-bindings.json", {"classification": "retrospective research-decision synthesis, not an experiment",
                                             "synthesis_commit": head, "evidence_anchor_commit": m.ANCHOR,
                                             "source_snapshots": snapshots, "audit": audit,
                                             "pdf_sha256": build["pdf_sha256"], "paper_pages": build["pages"],
                                             "raw_native_telemetry_decoded": False, "new_models_or_captures": 0,
                                             "successor_selected": False, "prior_evidence_deleted": 0})
    return {"preserved": True, "source_snapshots": len(snapshots), "paper_pages": build["pages"], **audit}


def archive():
    from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download

    m.audit()
    assert not STAGE.exists() and not RECEIPT.exists(), "fresh immutable namespace required"
    binding = m.read(ROOT / "archive-bindings.json")
    for name, digest in binding["source_snapshots"].items():
        assert m.sha(ROOT / "source-snapshot" / name) == digest
    assert m.sha(ROOT / "paper-build/main.pdf") == binding["pdf_sha256"]
    assert not any(p.is_symlink() for p in ROOT.rglob("*"))
    files = {str(p.relative_to(ROOT)): {"bytes": p.stat().st_size, "sha256": m.sha(p)}
             for p in sorted(ROOT.rglob("*")) if p.is_file()}
    raw = sum(v["bytes"] for v in files.values())
    assert raw <= MAX_RAW
    STAGE.mkdir()
    part = STAGE / "evidence.tar.gz"
    with tarfile.open(part, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for name, meta in files.items():
            assert m.sha(ROOT / name) == meta["sha256"]
            tar.add(ROOT / name, arcname=ROOT.name + "/" + name, recursive=False)
            assert m.sha(ROOT / name) == meta["sha256"]
    m.write(STAGE / "file-index.json", {"abi": "rd1_summary_manuscript_inventory_v1", "member_root": ROOT.name, "files": files})
    (STAGE / "SHA256SUMS").write_text(m.sha(part) + "  " + part.name + "\n")
    (STAGE / "RESTORE.md").write_text(
        "RD1 retrospective decision, manuscript, build artifacts and quoted committed source reports only. "
        "No new experiment, raw native capture, controller or successor panel. Fetch this namespace "
        "at the receipt revision; verify object size/SHA, then every tar member against file-index.json. "
        "Use a fresh external directory; preserve all previous freezes. No licensed media included.\n")
    parts = {p.name: {"bytes": p.stat().st_size, "sha256": m.sha(p)} for p in sorted(STAGE.iterdir()) if p.is_file()}
    staged = sum(v["bytes"] for v in parts.values())
    assert raw + 2*staged <= MAX_PEAK
    api = HfApi()
    info = api.dataset_info(DATASET)
    assert info.private
    assert not any(e.path == PREFIX for e in api.list_repo_tree(DATASET, repo_type="dataset", recursive=False))
    commit = api.create_commit(DATASET, repo_type="dataset", parent_commit=info.sha,
                               operations=[CommitOperationAdd(path_in_repo=PREFIX + "/" + n, path_or_fileobj=str(STAGE/n)) for n in parts],
                               commit_message="Preserve RD1 negative-result research decision and revised manuscript")
    revision = commit.oid
    m.write(STAGE / "upload-commit.json", {"repo_id": DATASET, "prefix": PREFIX, "revision": revision})
    with tempfile.TemporaryDirectory(dir=STAGE) as temporary:
        downloaded = {}
        for name, meta in parts.items():
            path = Path(hf_hub_download(DATASET, repo_type="dataset", filename=PREFIX + "/" + name,
                                       revision=revision, local_dir=temporary, force_download=True))
            assert path.stat().st_size == meta["bytes"] and m.sha(path) == meta["sha256"]
            downloaded[name] = path
        assert m.read(downloaded["file-index.json"])["files"] == files
        with tarfile.open(downloaded[part.name], "r:gz") as tar:
            seen = set()
            for member in tar.getmembers():
                name = str(Path(member.name).relative_to(ROOT.name))
                assert member.isfile() and name in files and name not in seen
                assert member.size == files[name]["bytes"]
                assert hashlib.sha256(tar.extractfile(member).read()).hexdigest() == files[name]["sha256"]
                seen.add(name)
            assert seen == set(files)
        for name, path in downloaded.items():
            assert m.sha(path) == parts[name]["sha256"]
    receipt = {"abi": "rd1_research_decision_manuscript_archive_receipt_v1", "repo_id": DATASET, "private": True,
               "prefix": PREFIX, "revision": revision, "objects": parts,
               "objects_freshly_verified": len(parts), "members_freshly_size_sha256_verified": len(files),
               "archive_and_file_checksums_verified": True, "local_evidence_retained": True,
               "raw_root": str(ROOT), "evidence_deleted": 0, "synthesis_commit": binding["synthesis_commit"],
               "evidence_anchor_commit": m.ANCHOR, "evidence_ledger_sha256": m.sha(m.LEDGER),
               "pdf_sha256": binding["pdf_sha256"], "paper_pages": binding["paper_pages"],
               "prior_files_unchanged": binding["audit"]["prior_files_unchanged"],
               "native_panels_opened": 0, "new_models_or_effect_estimates": 0, "successor_selected": False,
               "raw_bytes": raw, "stage_bytes": staged, "fresh_download_bytes": staged,
               "raw_stage_fresh_bytes": raw + 2*staged, "budget_bytes": MAX_PEAK,
               "archive_helper_sha256": m.sha(Path(__file__))}
    m.write(RECEIPT, receipt)
    m.write(REPO / "reports/research-decision-rd1-storage.json", receipt)
    return {"archive_verified": True, "revision": revision, "members": len(files), "objects": len(parts),
            "paper_pages": binding["paper_pages"], "evidence_deleted": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preserve", "archive"])
    args = parser.parse_args()
    print(json.dumps(globals()[args.command]()))
