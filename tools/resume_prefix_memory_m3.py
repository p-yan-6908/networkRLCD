"""Complete unattempted M3 trials after a platform restart, without replacements.

The scientific protocol/instrumentation are unchanged. The interrupted original
attempt is sealed as failed and remains in every gate and archive inventory.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("frozen_m3_recovery", REPO / "tools/measure_prefix_memory_m3.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
RECOVERY = REPO / "reports/native-prefix-memory-m3-recovery-registration.json"


def recover():
    m.verify()
    p = m.v.read(m.CONFIG)
    recovery = m.v.read(RECOVERY)
    assert recovery["resume_tool_sha256"] == m.v.sha(Path(__file__).resolve())
    assert recovery["protocol_sha256"] == m.v.sha(m.CONFIG)
    for name in ("tools/resume_prefix_memory_m3.py", "docs/NATIVE_PREFIX_MEMORY_M3_RECOVERY.md", str(RECOVERY.relative_to(REPO))):
        assert subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=REPO) == (REPO / name).read_bytes()
    current, _ = m.v.frozen.base.runtime_provenance(Path(p["preflight_reference"]["path"]))
    assert current == p["runtime"]
    m.v.frozen.v2.set_runtime_env(p)
    index_path = m.ROOT / "capture_index.json"
    assert m.v.sha(index_path) == recovery["completed_capture_index_sha256"]
    index = m.v.read(index_path)
    assert [r["trial"] for r in index["sessions"]] == p["randomized_order"][:49]
    for r in index["sessions"]:
        directory = m.ROOT / "sessions" / r["trial"]
        assert m.v.sha(directory / "integrity.json") == r["integrity_manifest_sha256"]
        m.v.core.verify_directory(directory)
    interrupted = p["trials"][49]
    assert interrupted["id"] == recovery["interrupted_trial"]
    directory = m.ROOT / "sessions" / interrupted["id"]
    assert not (directory / "integrity.json").exists()
    observed = {str(x.relative_to(directory)): m.v.sha(x) for x in directory.rglob("*") if x.is_file()}
    assert observed == recovery["interrupted_original_files_sha256"]
    assert all(not (m.ROOT / "sessions" / t["id"]).exists() for t in p["trials"][50:])
    m.v.write(directory / "runtime_interruption.json", recovery)
    (directory / "capture_stdout.log").write_text("Original output pipe unavailable after platform restart; no completed output asserted.\n")
    (directory / "capture_stderr.log").write_text("Platform restart terminated the original capture runner and native processes; attempt retained as failed.\n")
    seal = m.v.core.seal_directory(directory, "native_action_session_failed")
    index["sessions"].append({"trial": interrupted["id"], "status": "failed", "error": "platform restart; original attempt interrupted; not replaced",
        "integrity_manifest_sha256": m.v.sha(directory / "integrity.json"), "file_count": seal["file_count"]})
    m.v.core.write_json(index_path, index)
    m.v.write(m.ROOT / "operational_recovery_registration.json", recovery)
    for trial in p["trials"][50:]:
        child = m.ROOT / "sessions" / trial["id"]
        panel = m.ROOT / trial["panel"]
        assert not child.exists()
        assert m.v.sha(panel) == trial["panel_sha256"]
        env = os.environ.copy()
        env.setdefault("RLCD_CHROME", "/usr/bin/chromium")
        command = ["node", str(m.RECORDER), str(child), str(panel), trial["id"], trial["condition"]]
        try:
            proc = subprocess.run(command, cwd=m.v.core.HERE, env=env, capture_output=True, text=True, timeout=110)
            stdout, stderr = proc.stdout, proc.stderr
            status = "sealed" if proc.returncode == 0 else "failed"
            error = None if proc.returncode == 0 else f"exit code {proc.returncode}"
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
            status, error = "failed", "bounded 110-second timeout"
        child.mkdir(parents=True, exist_ok=True)
        (child / "capture_stdout.log").write_text(stdout)
        (child / "capture_stderr.log").write_text(stderr)
        seal = m.v.core.seal_directory(child, "native_action_session" if status == "sealed" else "native_action_session_failed")
        index["sessions"].append({"trial": trial["id"], "status": status, "error": error,
            "integrity_manifest_sha256": m.v.sha(child / "integrity.json"), "file_count": seal["file_count"]})
        m.v.core.write_json(index_path, index)
    assert [r["trial"] for r in index["sessions"]] == p["randomized_order"]
    gate = m.gate()
    m.v.write(REPO / "reports/native-prefix-memory-m3-gate.json", gate)
    return {"original_attempts": len(index["sessions"]), "sealed": sum(r["status"] == "sealed" for r in index["sessions"]),
        "failed": sum(r["status"] == "failed" for r in index["sessions"]), "qualified_sessions": gate["qualified_sessions"],
        "gate_passed": gate["passed"], "replacements": 0, "outcomes_read": False}


if __name__ == "__main__":
    print(json.dumps(recover()))
