"""Bound project storage; archive immutable results to private HF before pruning bytes.

Local commands use the standard library. Archive commands additionally need the HF SDK
for metadata/checksum verification; uploads themselves use the installed `hf` CLI.
"""

import argparse
import hashlib
import json
import os
import re
import select
import subprocess
import tarfile
import tempfile
import time
from contextlib import closing
from pathlib import Path, PurePosixPath

REPO = "p-yan/networkrlcd-results-archive"
LIMIT = 10_000_000_000
PROTECTED_RUNS = {"native-n1-acquisition", "native-action-excitation-train-sintel-v1"}
KEEP_SUFFIXES = {".json", ".mjs", ".cjs", ".py", ".sh", ".md", ".csv", ".txt", ".onnx", ".npz"}
RAW_JSON_NAMES = {"frame_events.json", "sender_observations.json"}


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}), flush=True)


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def relative_name(name):
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or len(p.parts) < 2 or p.parts[0] != "results":
        raise ValueError("Expected a contained results/<run> path")
    return p.as_posix()


def external_root(project, cache):
    project, cache = project.resolve(), cache.expanduser().resolve()
    if cache.is_relative_to(project):
        raise ValueError("Working/archival cache must be outside the project")
    return cache


def project_bytes(root):
    """Count unique allocated/logical bytes, including dotfiles; do not follow links."""
    seen, total, todo = set(), 0, [Path(root)]
    while todo:
        p = todo.pop()
        try:
            s = p.lstat()
        except FileNotFoundError:
            continue
        key = (s.st_dev, s.st_ino)
        if key in seen:
            continue
        seen.add(key)
        total += max(s.st_size, getattr(s, "st_blocks", 0) * 512)
        if p.is_dir() and not p.is_symlink():
            try:
                todo.extend(p.iterdir())
            except FileNotFoundError:
                pass  # A concurrently relocated directory now lives outside the project.
    return total


def externalize(project, cache, name, apply=False):
    project = project.resolve()
    cache = external_root(project, cache)
    name = relative_name(name)
    source, target = project / name, cache / "working" / name
    if source.is_symlink():
        if source.resolve() != target.resolve():
            raise ValueError("Unexpected existing link: " + name)
        return {"path": name, "status": "already_external", "target": str(target)}
    if not source.is_dir() or target.exists() or target.is_symlink():
        raise ValueError("Need an existing real directory and a fresh external target")
    if source.parent.resolve() != source.parent.absolute():
        raise ValueError("Source parent must not traverse a symlink")
    tracked = subprocess.check_output(["git", "-C", str(project), "ls-files", "-z", "--", name])
    if tracked:
        raise ValueError("Refusing to relocate a directory containing tracked files")
    record = {"path": name, "target": str(target), "status": "planned"}
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.stat().st_dev != target.parent.stat().st_dev:
            raise ValueError("Relocation must be a same-filesystem rename, not a copy")
        source.rename(target)
        try:
            source.symlink_to(target, target_is_directory=True)
        except BaseException:
            target.rename(source)
            raise
        record["status"] = "externalized_not_yet_backed_up"
        with (cache / "relocations.jsonl").open("a") as log:
            log.write(json.dumps(record) + "\n")
    return record


def sealed(path):
    try:
        m = json.loads((path / "manifest.json").read_text())
        hashes = m["artifacts_sha256"]
        if not hashes:
            return False
        for name, expected in hashes.items():
            rel = PurePosixPath(name)
            if rel.is_absolute() or ".." in rel.parts:
                return False
            p = path / name
            if p.is_symlink() or not p.resolve().is_relative_to(path.resolve()) or digest(p) != expected:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def externalize_sealed(project, cache, name, apply=False):
    parent = project / relative_name(name)
    moved = []
    for child in sorted(parent.iterdir()):
        if child.is_dir() and not child.is_symlink() and sealed(child):
            moved.append(externalize(project, cache, str(child.relative_to(project)), apply))
    return moved


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def wait_exit(pid, timeout=120):
    """Bounded macOS process-exit notification, not process-table polling."""
    if not alive(pid):
        return
    if not hasattr(select, "kqueue"):
        raise ValueError("--after-pid currently requires macOS kqueue")
    with closing(select.kqueue()) as q:
        event = select.kevent(pid, filter=select.KQ_FILTER_PROC, flags=select.KQ_EV_ADD,
                              fflags=select.KQ_NOTE_EXIT)
        try:
            events = q.control([event], 1, timeout)
        except ProcessLookupError:
            return
        if not events:
            raise TimeoutError("Episode did not exit within the relocation window")


def assert_inactive(project, names):
    """Refuse known capture/analysis commands explicitly using the selected trees."""
    table = subprocess.check_output(["ps", "-axo", "command="], text=True)
    for line in table.splitlines():
        if " --out " not in line and " --capture " not in line:
            continue
        if "results_storage.py" in line:
            continue
        if any(" " + n in line or " " + str(project / n) in line for n in names):
            raise ValueError("A running command still uses the selected raw tree")


def archive_paths(project, cache, names):
    """Expand explicit run roots, including our path-preserving completed-peer aliases."""
    files = {}
    cache = external_root(project, cache)
    for name in names:
        name = relative_name(name)
        if PurePosixPath(name).parts[1] in PROTECTED_RUNS:
            raise ValueError("Protected source/donor tree")
        base = project / name
        if not base.is_dir():
            raise ValueError("Missing snapshot tree: " + name)
        todo = [base]
        while todo:
            p = todo.pop()
            if p.is_symlink():
                expected = cache / "working" / p.relative_to(project)
                if p.resolve() != expected.resolve() or not p.is_dir():
                    raise ValueError("Uncontrolled symlink: " + str(p))
            if p.is_dir():
                todo.extend(p.iterdir())
            elif p.is_file():
                files[str(p.relative_to(project))] = {"sha256": digest(p), "size": p.stat().st_size}
    return files


def private_api():
    from huggingface_hub import HfApi
    api = HfApi()
    if not api.dataset_info(REPO).private:
        raise ValueError("Refusing to use a public archive")
    return api


def fetch(repo_path, revision, destination):
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(REPO, repo_path, repo_type="dataset", revision=revision,
                               local_dir=str(destination)))


def remote_verify(api, prefix, revision, parts, small, scratch):
    entries = {Path(e.path).name: e for e in api.list_repo_tree(
        REPO, path_in_repo=prefix, repo_type="dataset", revision=revision, expand=True)
        if hasattr(e, "size")}
    if set(entries) != set(parts) | set(small):
        raise ValueError("Remote inventory is missing files or contains unexpected files")
    for name, value in parts.items():
        entry = entries[name]
        if not entry.lfs or entry.lfs.sha256 != value["sha256"] or entry.size != value["size"]:
            raise ValueError("Remote part checksum/size mismatch: " + name)
    for name, expected in small.items():
        if digest(fetch(prefix + "/" + name, revision, scratch)) != expected:
            raise ValueError("Remote inventory checksum mismatch: " + name)
    probe = min(parts, key=lambda n: parts[n]["size"])
    if digest(fetch(prefix + "/" + probe, revision, scratch)) != parts[probe]["sha256"]:
        raise ValueError("Fresh remote-download checksum mismatch")
    return {"verification": "passed", "private": True, "revision": revision,
            "prefix": prefix, "repo": REPO, "parts": parts, "download_probe": probe}


def retained(name):
    p = PurePosixPath(name)
    return (p.parts[1] in PROTECTED_RUNS
            or any(x in p.parts for x in ("models", "training", "checkpoints"))
            or (p.suffix in KEEP_SUFFIXES and p.name not in RAW_JSON_NAMES))


def file_identity(value):
    # Reads can update atime; that is not evidence drift.
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def prune(project, cache, files, receipt, log_path, apply=False):
    if receipt.get("verification") != "passed" or receipt.get("private") is not True:
        raise ValueError("A verified private remote copy is required")
    if not receipt.get("revision") or receipt.get("repo") != REPO:
        raise ValueError("Missing pinned archive identity")
    removed, kept, logical = 0, 0, 0
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("x") as log:
        for name, expected in files.items():
            name = relative_name(name)
            if retained(name):
                kept += 1
                continue
            p = project / name
            try:
                before = p.lstat()
                resolved = p.resolve()
                if p.is_symlink() or not (resolved.is_relative_to(project.resolve())
                                         or resolved.is_relative_to(cache / "working")):
                    raise ValueError("Unsafe deletion target")
                actual = digest(p)
                after = p.lstat()
                if file_identity(before) != file_identity(after) or after.st_size != expected["size"] or actual != expected["sha256"]:
                    raise ValueError("Local bytes changed")
            except (OSError, ValueError):
                kept += 1
                continue
            event = {"path": name, "sha256": actual, "bytes": after.st_size,
                     "status": "unlink_intent" if apply else "eligible", "revision": receipt["revision"]}
            log.write(json.dumps(event) + "\n")
            log.flush()
            if apply:
                if file_identity(p.lstat()) != file_identity(after) or p.resolve() != resolved:
                    kept += 1
                    continue
                p.unlink()
                log.write(json.dumps({"path": name, "status": "unlinked"}) + "\n")
            removed += 1
            logical += after.st_size
        result = {"files": removed, "retained_or_drifted": kept, "logical_bytes": logical, "applied": apply}
        log.write(json.dumps({"summary": result}) + "\n")
    return result


def require_final_reports(project, names):
    if any(PurePosixPath(n).parts[1] == "native-margin-pilot-v1" for n in names):
        report_root = project / "results" / "native-margin-pilot-v1-report"
        values = {}
        for name in ("report.json", "sessions.json"):
            path = report_root / name
            if not path.is_file():
                raise ValueError("Margin raw pruning waits for final report and sessions")
            values[name] = json.loads(path.read_text())
        protocol = project / "results" / "native-margin-pilot-v1" / "protocol.json"
        if not protocol.is_file():
            raise ValueError("Margin final report requires its original protocol")
        report, sessions = values["report.json"], values["sessions.json"]
        planned = len(json.loads(protocol.read_text())["order"])
        if (not isinstance(report, dict) or not isinstance(sessions, list) or not sessions
                or report.get("abi") != "native_margin_pilot_v1_report"
                or report.get("plan_sha256") != digest(protocol)
                or report.get("planned_sessions") != planned
                or report.get("sessions") != len(sessions) or len(sessions) > planned):
            raise ValueError("Margin final report must match the capture plan and nonempty session list")


def wait_for_reports(project, names, pid, seconds):
    deadline = time.monotonic() + seconds
    emit("ARCHIVE_waiting_for_capture_and_reports", pid=pid, timeout_seconds=seconds)
    while True:
        if not alive(pid):
            try:
                require_final_reports(project, names)
                assert_inactive(project, names)
                return
            except ValueError:
                pass
        if time.monotonic() >= deadline:
            raise TimeoutError("Final reports not ready; raw evidence retained, archive deferred")
        time.sleep(30)


def upload(path, prefix):
    private_api()
    env = dict(os.environ, HF_XET_CHUNK_CACHE_SIZE_BYTES="0", HF_XET_SHARD_CACHE_SIZE_LIMIT="134217728")
    result = subprocess.run(["hf", "upload", REPO, str(path), prefix + "/" + path.name,
                             "--type", "dataset", "--format", "json"], env=env,
                            capture_output=True, text=True, timeout=3600)
    if result.returncode:
        raise RuntimeError("hf upload failed: " + result.stderr[-2000:])


class Parts:
    """Upload tar shards as they fill: at most one 1 GiB staging file, not a second full tree."""
    def __init__(self, stage, prefix, size=1 << 30):
        self.stage, self.prefix, self.size = stage, prefix, size
        self.parts, self.stream, self.n = {}, None, 0

    def write(self, data):
        count = len(data)
        while data:
            if self.stream is None:
                self.path = self.stage / f"results.tar.part-{self.n:04d}"
                self.stream = self.path.open("xb")
                self.hash, self.used = hashlib.sha256(), 0
            take = min(len(data), self.size - self.used)
            self.stream.write(data[:take])
            self.hash.update(data[:take])
            self.used += take
            data = data[take:]
            if self.used == self.size:
                self.finish()
        return count

    def finish(self):
        if self.stream is None:
            return
        self.stream.close()
        self.stream = None
        saved = {"sha256": self.hash.hexdigest(), "size": self.used}
        emit("ARCHIVE_upload_part", prefix=self.prefix, part=self.path.name, bytes=self.used)
        upload(self.path, self.prefix)
        api = private_api()
        revision = api.dataset_info(REPO).sha
        entry = next(e for e in api.list_repo_tree(REPO, path_in_repo=self.prefix,
                     repo_type="dataset", revision=revision, expand=True) if Path(e.path).name == self.path.name)
        if not entry.lfs or entry.lfs.sha256 != saved["sha256"] or entry.size != self.used:
            raise ValueError("Uploaded shard failed remote checksum verification")
        self.parts[self.path.name] = saved
        self.path.unlink()  # ONLY the upload staging shard; originals are still intact.
        self.n += 1
        emit("ARCHIVE_part_verified", part=self.path.name, revision=revision)


def archive(project, cache, names, prefix, apply=False):
    cache = external_root(project, cache)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", prefix):
        raise ValueError("Archive prefix must be a fresh simple folder name")
    cache.mkdir(parents=True, exist_ok=True)
    assert_inactive(project, names)
    api = private_api()
    existing = list(api.list_repo_tree(REPO, repo_type="dataset", recursive=False))
    if any(e.path == prefix for e in existing):
        raise ValueError("Fresh archive prefix required; existing snapshots are never overwritten")
    stage = cache / "staging" / prefix
    stage.mkdir(parents=True, exist_ok=False)
    files = archive_paths(project, cache, names)
    if not files:
        raise ValueError("Empty snapshot")
    writer = Parts(stage, prefix)
    emit("ARCHIVE_snapshot_start", prefix=prefix, files=len(files), bytes=sum(f["size"] for f in files.values()))
    with tarfile.open(fileobj=writer, mode="w|", format=tarfile.PAX_FORMAT, dereference=False) as tar:
        for name, expected in sorted(files.items()):
            path = project / name
            if digest(path) != expected["sha256"]:
                raise ValueError("Snapshot drift before packing: " + name)
            tar.add(path, arcname=name, recursive=False)
            if digest(path) != expected["sha256"]:
                raise ValueError("Snapshot drift while packing: " + name)
    writer.finish()
    index = stage / "file-index.json"
    write_json(index, {"files": files, "scopes": names})
    sums = stage / "SHA256SUMS"
    sums.write_text("".join(v["sha256"] + "  " + n + "\n" for n, v in sorted(writer.parts.items())))
    restore = stage / "RESTORE.md"
    restore.write_text("Download this folder at its pinned revision, verify SHA256SUMS, then concatenate "
                       "results.tar.part-* in lexical order and extract with tar into a NEW EMPTY directory. "
                       "Verify restored files against file-index.json before use. Never merge over current results.\n")
    small = {p.name: digest(p) for p in (index, sums, restore)}
    for p in (index, sums, restore):
        upload(p, prefix)
    revision = private_api().dataset_info(REPO).sha
    with tempfile.TemporaryDirectory(dir=cache) as temp:
        receipt = remote_verify(api, prefix, revision, writer.parts, small, Path(temp))
    receipt.update(scopes=names, archive_bytes=sum(v["size"] for v in writer.parts.values()), applied=False)
    write_json(stage / "verified-receipt.json", receipt)
    write_json(project / "docs" / "storage-receipts" / (prefix + ".json"), receipt)
    emit("ARCHIVE_verified", prefix=prefix, revision=revision)
    assert_inactive(project, names)
    if apply:
        require_final_reports(project, names)
    outcome = prune(project, cache, files, receipt, stage / "prune-receipt.jsonl", apply)
    receipt.update(outcome, scopes=names, archive_bytes=sum(v["size"] for v in writer.parts.values()))
    mark_partial(project, names, receipt)
    write_json(project / "docs" / "storage-receipts" / (prefix + ".json"), receipt)
    emit("ARCHIVE_complete", **receipt)
    return receipt


def mark_partial(project, names, receipt):
    if receipt.get("applied") and receipt.get("files", 0):
        for name in names:
            write_json(project / relative_name(name) / "ARCHIVED_RAW.json",
                       {"partial_evidence": True, "restore_before_raw_audit": True,
                        "repo": REPO, "prefix": receipt["prefix"], "revision": receipt["revision"],
                        "removed_raw_files": receipt["files"]})


def existing_n1(project, cache, apply=False):
    prefix = "n1-stage-one-2026-10-10"
    revision = "aa1b8d80fd66a3f52e88b59d589825f50d5e5dd2"
    names = ["results/native-actuator-qualification-n1-stage-one"]
    assert_inactive(project, names)
    api = private_api()
    stage = cache / "receipts" / (prefix + "-prune-" + str(time.time_ns()))
    stage.mkdir(parents=True)
    with tempfile.TemporaryDirectory(dir=cache) as temp:
        scratch = Path(temp)
        sums = fetch(prefix + "/SHA256SUMS", revision, scratch)
        inventory = fetch(prefix + "/file-sha256.txt", revision, scratch)
        remote = {Path(e.path).name: e for e in api.list_repo_tree(REPO, path_in_repo=prefix,
                  repo_type="dataset", revision=revision, expand=True) if hasattr(e, "size")}
        parts = {line.split()[1]: {"sha256": line.split()[0], "size": remote[line.split()[1]].size}
                 for line in sums.read_text().splitlines()}
        small_names = {"SHA256SUMS", "original-file-list.txt", "file-sha256.txt",
                       "snapshot-created-utc.txt", "README.md", "restore.sh"}
        original = project / ".tools" / "results-archive-receipts-n1-v1"
        original_stage = project / ".tools" / "results-archive-stage-n1-v1"
        small = {n: digest((original / n) if (original / n).is_file() else original_stage / n)
                 for n in small_names}
        receipt = remote_verify(api, prefix, revision, parts, small, scratch)
        files = {}
        for line in inventory.read_text().splitlines():
            sha, name = line.split(maxsplit=1)
            if not name.startswith(names[0] + "/"):
                continue
            path = project / relative_name(name)
            if path.is_file():
                files[name] = {"sha256": sha, "size": path.stat().st_size}
    assert_inactive(project, names)
    result = prune(project, cache, files, receipt, stage / "prune-receipt.jsonl", apply)
    receipt.update(result, scopes=names)
    mark_partial(project, names, receipt)
    write_json(project / "docs" / "storage-receipts" / "n1-stage-one-pruning-2026-10-11.json", receipt)
    emit("ARCHIVE_existing_N1", **receipt)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "networkrlcd")
    sub = p.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--check", action="store_true")
    status.add_argument("--planned-bytes", type=int, default=0)
    move = sub.add_parser("externalize")
    move.add_argument("paths", nargs="+")
    move.add_argument("--apply", action="store_true")
    move.add_argument("--after-pid", type=int)
    watch = sub.add_parser("watch-sealed")
    watch.add_argument("path")
    watch.add_argument("--pid", type=int, required=True)
    watch.add_argument("--max-seconds", type=int, default=14400)
    pack = sub.add_parser("archive")
    pack.add_argument("paths", nargs="+")
    pack.add_argument("--prefix", required=True)
    pack.add_argument("--prune", action="store_true")
    pack.add_argument("--wait-for-pid", type=int)
    pack.add_argument("--wait-seconds", type=int, default=7200)
    prune_cmd = sub.add_parser("prune-existing-n1")
    prune_cmd.add_argument("--apply", action="store_true")
    args = p.parse_args()
    root, cache = args.project.resolve(), external_root(args.project, args.cache)
    if args.command == "status":
        if args.planned_bytes < 0:
            p.error("--planned-bytes must be nonnegative")
        size = project_bytes(root)
        within = size + args.planned_bytes <= LIMIT
        emit("STORAGE_budget", project_bytes=size, limit_bytes=LIMIT, planned_bytes=args.planned_bytes,
             within_budget=within, external_cache=str(cache), symlinks_followed=False)
        if args.check and not within:
            raise SystemExit(2)
    elif args.command == "externalize":
        if args.after_pid:
            wait_exit(args.after_pid)
        for name in args.paths:
            emit("STORAGE_relocation", **externalize(root, cache, name, args.apply))
    elif args.command == "watch-sealed":
        deadline = time.monotonic() + args.max_seconds
        while True:
            moved = externalize_sealed(root, cache, args.path, True)
            emit("STORAGE_capture_scan", moved=len(moved), collector_alive=alive(args.pid),
                 project_bytes=project_bytes(root))
            if not alive(args.pid):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Storage watcher deadline reached; raw files retained")
            time.sleep(30)
    elif args.command == "prune-existing-n1":
        cache.mkdir(parents=True, exist_ok=True)
        existing_n1(root, cache, args.apply)
    else:
        if args.wait_for_pid:
            wait_for_reports(root, args.paths, args.wait_for_pid, args.wait_seconds)
        archive(root, cache, args.paths, args.prefix, args.prune)


if __name__ == "__main__":
    main()
