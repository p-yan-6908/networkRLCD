"""Storage safety probes: no HF/network or real result deletion."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("results_storage", Path(__file__).parents[1] / "tools/results_storage.py")
storage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(storage)


@pytest.fixture
def layout(tmp_path):
    root, cache = tmp_path / "project", tmp_path / "cache"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    folder = root / "results" / "pilot"
    folder.mkdir(parents=True)
    raw = folder / "frames.bin"
    raw.write_bytes(b"raw captured bytes")
    meta = folder / "cohorts.json"
    meta.write_text("{}")
    return root, cache, folder, raw, meta


def test_externalize_is_dry_by_default_and_preserves_bytes_and_old_path(layout):
    root, cache, folder, raw, _ = layout
    inode = raw.stat().st_ino
    storage.externalize(root, cache, "results/pilot")
    assert not folder.is_symlink()
    before = storage.project_bytes(root)
    storage.externalize(root, cache, "results/pilot", True)
    assert folder.is_symlink()
    assert raw.read_bytes() == b"raw captured bytes"
    assert raw.stat().st_ino == inode
    assert raw.resolve().is_relative_to(cache)
    assert storage.project_bytes(root) < before
    assert storage.externalize(root, cache, "results/pilot", True)["status"] == "already_external"


def test_relocation_rejects_tracked_files_containment_and_existing_target(layout):
    root, cache, _, raw, _ = layout
    subprocess.run(["git", "-C", str(root), "add", str(raw)], check=True)
    with pytest.raises(ValueError, match="tracked"):
        storage.externalize(root, cache, "results/pilot", True)
    with pytest.raises(ValueError):
        storage.externalize(root, root / "cache", "results/pilot", True)
    with pytest.raises(ValueError):
        storage.relative_name("results/../outside")


def test_failed_symlink_creation_rolls_back(layout, monkeypatch):
    root, cache, folder, raw, _ = layout
    def fail(*args, **kwargs):
        raise OSError("fixture")
    monkeypatch.setattr(Path, "symlink_to", fail)
    with pytest.raises(OSError):
        storage.externalize(root, cache, "results/pilot", True)
    assert folder.is_dir() and not folder.is_symlink()
    assert raw.read_bytes() == b"raw captured bytes"


def test_only_fully_sealed_children_move(layout):
    root, cache, folder, _, _ = layout
    done, unfinished = folder / "done", folder / "unfinished"
    done.mkdir()
    unfinished.mkdir()
    raw = done / "frames.bin"
    raw.write_bytes(b"complete evidence")
    (done / "manifest.json").write_text(json.dumps(
        {"artifacts_sha256": {"frames.bin": storage.digest(raw)}}))
    (unfinished / "frames.bin").write_bytes(b"streaming")
    moved = storage.externalize_sealed(root, cache, "results/pilot", True)
    assert len(moved) == 1 and done.is_symlink() and not unfinished.is_symlink()
    assert storage.sealed(done)
    raw.write_bytes(b"drifted")
    assert not storage.sealed(done)


def test_prune_requires_verified_private_pinned_copy(layout):
    root, cache, _, raw, _ = layout
    files = {"results/pilot/frames.bin": {"sha256": storage.digest(raw), "size": raw.stat().st_size}}
    with pytest.raises(ValueError):
        storage.prune(root, cache, files, {}, cache / "log", True)
    assert raw.exists()


def test_prune_keeps_metadata_drift_and_outside_links(layout):
    root, cache, folder, raw, meta = layout
    files = {str(p.relative_to(root)): {"sha256": storage.digest(p), "size": p.stat().st_size}
             for p in (raw, meta)}
    receipt = {"verification": "passed", "private": True, "revision": "pinned", "repo": storage.REPO}
    raw.write_bytes(b"changed")
    result = storage.prune(root, cache, files, receipt, cache / "drift.jsonl", True)
    assert result["files"] == 0 and raw.exists() and meta.exists()
    raw.unlink()
    outside = root.parent / "unrelated.bin"
    outside.write_bytes(b"raw captured bytes")
    raw.symlink_to(outside)
    storage.prune(root, cache, files, receipt, cache / "outside.jsonl", True)
    assert outside.exists() and raw.is_symlink()


@pytest.mark.parametrize("raw_name", ["frames.bin", "frame_events.json", "sender_observations.json"])
def test_checksum_matched_pruning_of_external_alias_retains_metadata(layout, raw_name):
    root, cache, folder, raw, meta = layout
    if raw.name != raw_name:
        raw = raw.rename(folder / raw_name)
    files = {str(p.relative_to(root)): {"sha256": storage.digest(p), "size": p.stat().st_size}
             for p in (raw, meta)}
    storage.externalize(root, cache, "results/pilot", True)
    receipt = {"verification": "passed", "private": True, "revision": "pinned", "repo": storage.REPO}
    result = storage.prune(root, cache, files, receipt, cache / "prune.jsonl", True)
    assert result["files"] == 1 and not raw.exists() and meta.exists()
    assert "unlinked" in (cache / "prune.jsonl").read_text()


def test_protected_sources_donors_and_checkpoints():
    assert storage.retained("results/native-n1-acquisition/movie.mov")
    assert storage.retained("results/native-action-excitation-train-sintel-v1/events.gz")
    assert storage.retained("results/pilot/training/weights.bin")
    assert storage.retained("results/pilot/manifest.json")
    assert not storage.retained("results/pilot/events.jsonl.gz")
    assert not storage.retained("results/pilot/frame_events.json")
    assert not storage.retained("results/pilot/sender_observations.json")
    assert storage.retained("results/pilot/native_derived.json")


def test_shard_boundaries_do_not_require_a_second_full_snapshot(tmp_path, monkeypatch):
    class Entry:
        def __init__(self, path):
            self.path, self.size = path.name, path.stat().st_size
            self.lfs = type("Lfs", (), {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()})()
    remote, uploads = {}, []
    def fake_upload(path, prefix):
        remote[path.name] = Entry(path)
        uploads.append(path.read_bytes())
    class Api:
        def dataset_info(self, repo):
            return type("Info", (), {"sha": "pinned"})()
        def list_repo_tree(self, *args, **kwargs):
            return remote.values()
    monkeypatch.setattr(storage, "upload", fake_upload)
    monkeypatch.setattr(storage, "private_api", lambda: Api())
    writer = storage.Parts(tmp_path, "fixture", 5)
    assert writer.write(b"abcdefghijkl") == 12
    writer.finish()
    assert uploads == [b"abcde", b"fghij", b"kl"]
    assert not list(tmp_path.glob("results.tar.part-*"))
    assert len(writer.parts) == 3


def test_archive_verify_prune_and_restore_end_to_end(layout, tmp_path, monkeypatch):
    root, cache, _, raw, meta = layout
    remote = tmp_path / "remote"
    remote.mkdir()
    class Entry:
        def __init__(self, path, prefix):
            self.path = prefix + "/" + path.name
            self.size = path.stat().st_size
            self.lfs = type("Lfs", (), {"sha256": storage.digest(path)})()
    class Api:
        def dataset_info(self, repo):
            return type("Info", (), {"sha": "immutable", "private": True})()
        def list_repo_tree(self, *args, **kwargs):
            prefix = kwargs.get("path_in_repo")
            return [Entry(p, prefix) for p in remote.iterdir()] if prefix else []
    def fake_upload(path, prefix):
        (remote / path.name).write_bytes(path.read_bytes())
    def fake_fetch(path, revision, dest):
        assert revision == "immutable"
        target = dest / Path(path).name
        target.write_bytes((remote / target.name).read_bytes())
        return target
    monkeypatch.setattr(storage, "private_api", lambda: Api())
    monkeypatch.setattr(storage, "upload", fake_upload)
    monkeypatch.setattr(storage, "fetch", fake_fetch)
    monkeypatch.setattr(storage, "assert_inactive", lambda *args: None)
    storage.externalize(root, cache, "results/pilot", True)
    receipt = storage.archive(root, cache, ["results/pilot"], "fixture", True)
    assert receipt["verification"] == "passed" and receipt["revision"] == "immutable"
    assert not raw.exists() and meta.exists()
    recovery = tmp_path / "recovered"
    recovery.mkdir()
    with tarfile.open(remote / "results.tar.part-0000") as tar:
        tar.extractall(recovery, filter="data")
    assert (recovery / "results/pilot/frames.bin").read_bytes() == b"raw captured bytes"
    index = json.loads((remote / "file-index.json").read_text())["files"]
    assert all(storage.digest(recovery / n) == v["sha256"] for n, v in index.items())


def test_config_agrees_with_budget_and_archive_identity():
    policy = json.loads((Path(__file__).parents[1] / "storage_policy.json").read_text())
    assert policy["max_project_bytes"] == storage.LIMIT
    assert policy["archive_dataset"] == storage.REPO


@pytest.mark.skipif(not hasattr(storage.select, "kqueue"), reason="macOS kqueue")
def test_wait_exit_handles_real_process_and_bounded_timeout():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])
    try:
        with pytest.raises(TimeoutError):
            storage.wait_exit(child.pid, timeout=0.001)
        storage.wait_exit(child.pid, timeout=2)
        assert child.wait(timeout=2) == 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_margin_raw_prune_waits_for_final_reports(layout):
    root, *_ = layout
    with pytest.raises(ValueError, match="final report"):
        storage.require_final_reports(root, ["results/native-margin-pilot-v1"])
    reports = root / "results/native-margin-pilot-v1-report"
    reports.mkdir()
    (reports / "report.json").write_text("{}")
    (reports / "sessions.json").write_text("[]")
    storage.require_final_reports(root, ["results/native-margin-pilot-v1"])


def test_capture_report_wait_is_bounded_and_has_no_side_effects(layout, monkeypatch):
    root, _, _, raw, _ = layout
    monkeypatch.setattr(storage, "alive", lambda pid: True)
    with pytest.raises(TimeoutError, match="raw evidence retained"):
        storage.wait_for_reports(root, ["results/native-margin-pilot-v1"], 123, 0)
    assert raw.exists()


def test_partial_marker_does_not_rewrite_seal(layout):
    root, _, folder, _, _ = layout
    seal = folder / "manifest.json"
    seal.write_text("original seal")
    receipt = {"applied": True, "files": 1, "prefix": "fixture", "revision": "pinned"}
    storage.mark_partial(root, ["results/pilot"], receipt)
    assert seal.read_text() == "original seal"
    assert json.loads((folder / "ARCHIVED_RAW.json").read_text())["partial_evidence"]


def test_invalid_archive_prefix_is_rejected_before_network(layout):
    root, cache, *_ = layout
    with pytest.raises(ValueError, match="prefix"):
        storage.archive(root, cache, ["results/pilot"], "../outside")
