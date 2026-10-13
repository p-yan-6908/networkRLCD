"""Resume only the unindexed tail of the frozen V11D capture after interruption.

This preserves every indexed session, seals an already-started but unindexed
session as failed, and executes only the remaining original randomized IDs.
It does not open action, frame-quality, or relay outcome telemetry.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WRAPPER = REPO / "tools/native_turn_clock_action_probe_v11d.py"


def load_wrapper():
    spec = importlib.util.spec_from_file_location("frozen_v11d_capture", WRAPPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the frozen V11D capture wrapper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resume() -> dict:
    wrapper = load_wrapper()
    core, base, v2 = wrapper.core, wrapper.base, wrapper.v2
    root = wrapper.CAPTURE_ROOT.expanduser().resolve()
    protocol = wrapper.load_registered(root)
    protocol_path = root / "protocol.json"
    index_path = root / "capture_index.json"
    index = core.read_json(index_path)
    order = protocol["randomized_order"]
    rows = index.get("sessions", [])
    if (index.get("protocol_sha256") != wrapper.sha(protocol_path)
            or [row.get("trial") for row in rows] != order[:len(rows)]):
        raise ValueError("capture index is not a prefix of the frozen randomized order")
    runtime_now, preflight_now = base.runtime_provenance(Path(protocol["preflight_reference"]["path"]))
    if runtime_now != protocol["runtime"]:
        raise ValueError("V11D runtime differs from the frozen registration")
    if preflight_now["sha256"] != protocol["preflight_reference"]["sha256"]:
        raise ValueError("V11D TURN/TCP preflight differs from the frozen registration")
    v2.set_runtime_env({"runtime": runtime_now})

    indexed = set()
    for row in rows:
        child = root / "sessions" / row["trial"]
        stage = "native_action_session" if row["status"] == "sealed" else "native_action_session_failed"
        manifest = core.verify_directory(child, stage)
        if (wrapper.sha(child / "integrity.json") != row.get("integrity_manifest_sha256")
                or manifest.get("file_count") != row.get("file_count")):
            raise ValueError(f"indexed session seal changed: {row['trial']}")
        indexed.add(row["trial"])

    remaining = order[len(rows):]
    sessions_root = root / "sessions"
    unindexed_dirs = {p.name for p in sessions_root.iterdir() if p.is_dir()} - indexed
    allowed_interruption = remaining[:1] if remaining else []
    if unindexed_dirs - set(allowed_interruption):
        raise ValueError("unexpected unindexed session directories; preserve and inspect the capture index first")

    starting_index_sha = wrapper.sha(index_path)
    interrupted_id = None
    if remaining and (sessions_root / remaining[0]).exists():
        interrupted_id = remaining[0]
        child = sessions_root / interrupted_id
        if (child / "integrity.json").exists():
            raise ValueError("unindexed interrupted session already has a seal; manual recovery is required")
        note = {
            "abi": "native_action_capture_runtime_interruption_v1",
            "trial_id": interrupted_id,
            "reason": "execution environment was replaced while the registered capture process was active",
            "recovery": "preserve this attempt as failed; do not replay or replace its trial ID",
            "outcome_telemetry_read": False,
        }
        (child / "runtime_interruption.json").write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8", errors="strict")
        seal = core.seal_directory(child, "native_action_session_failed")
        rows.append({"trial": interrupted_id, "status": "failed",
                     "error": "execution environment interrupted the in-progress registered session",
                     "integrity_manifest_sha256": wrapper.sha(child / "integrity.json"),
                     "file_count": seal["file_count"]})
        core.write_json(index_path, index)
        remaining = remaining[1:]

    trials = {trial["id"]: trial for trial in protocol["trials"]}
    for trial_id in remaining:
        trial = trials[trial_id]
        child = sessions_root / trial_id
        panel_path = root / trial["panel"]
        if child.exists():
            raise ValueError(f"refusing to overwrite an unindexed capture directory: {trial_id}")
        if wrapper.sha(panel_path) != trial["panel_sha256"]:
            raise ValueError(f"frozen V11D panel checksum mismatch: {trial_id}")
        command = ["node", str(wrapper.RECORDER), str(child), str(panel_path), trial_id, trial["condition"]]
        env = os.environ.copy()
        env.setdefault("RLCD_CHROME", "/usr/bin/chromium")
        try:
            proc = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                                  text=True, timeout=110)
            stdout, stderr = proc.stdout, proc.stderr
            status = "sealed" if proc.returncode == 0 else "failed"
            error = None if proc.returncode == 0 else f"exit code {proc.returncode}"
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
            status, error = "failed", "bounded 110-second timeout"
        child.mkdir(parents=True, exist_ok=True)
        (child / "capture_stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
        (child / "capture_stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
        seal = core.seal_directory(child, "native_action_session" if status == "sealed"
                                   else "native_action_session_failed")
        rows.append({"trial": trial_id, "status": status, "error": error,
                     "integrity_manifest_sha256": wrapper.sha(child / "integrity.json"),
                     "file_count": seal["file_count"]})
        core.write_json(index_path, index)
        print(json.dumps({"completed": len(rows), "planned": len(order),
                          "latest_status": status, "remaining": len(order) - len(rows)}), flush=True)

    return {"planned": len(order), "indexed": len(rows),
            "sealed": sum(row["status"] == "sealed" for row in rows),
            "failed": sum(row["status"] == "failed" for row in rows),
            "interrupted_session_id": interrupted_id,
            "starting_capture_index_sha256": starting_index_sha,
            "capture_index_sha256": wrapper.sha(index_path),
            "protocol_sha256": wrapper.sha(protocol_path),
            "outcome_telemetry_read": False}


if __name__ == "__main__":
    print(json.dumps(resume(), indent=2))
