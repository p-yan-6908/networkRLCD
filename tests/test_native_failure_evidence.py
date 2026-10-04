import json
import subprocess
from pathlib import Path

import pytest

from media_rl import native_failure_evidence as failure
from media_rl.native_protocol import asset_directory, read_json

PLAN = "configs/native_failure_evidence_diagnostic_v1.json"


def test_actual_projection_preserves_old_stats_guard_and_all_original_scalar_windows():
    cfg = read_json(PLAN)
    p = failure.validate_plan(cfg)
    old = read_json(Path(cfg["parent"]["path"]) / "protocol.json")["runtimes"]["sintel"]
    original = next(t for t in old["episodes"] if t["id"] == failure.FAILED)
    actual = p["episodes"][0]
    assert p["stage"] == actual["role"] == "diagnostic" and p["native_failure_evidence_diagnostic_only"]
    assert {k: v for k, v in original.items() if k not in ("id", "role")} == {
        k: v for k, v in actual.items() if k not in ("id", "role")
    }
    assert p["repair_model"] is None and p["learner"] is None
    assert p["measurement_recipe"] == old["measurement_recipe"] and p["source_sha256"] == old["source_sha256"]
    assets = asset_directory()
    assert (assets / failure.ENTRY).read_text() == failure.project_collector(
        (assets / "balanced_hold_episode.mjs").read_text()
    )
    assert failure.RAW_PEER.__code__.co_code == failure.matrix.pilot.audit_peer.__code__.co_code
    assert failure.RAW_PEER.__globals__ is failure.matrix.pilot.audit_peer.__globals__
    assert len(p["groups"]) == len(p["episodes"]) == 1 and p["groups"][0]["video_segment"] == [700000, 720000]


def test_future_scanner_sees_declared_reused_diagnostic_footage_without_train_aliasing():
    cfg = read_json(PLAN)
    p = cfg["runtimes"]["sintel"]
    ranges, inputs = failure.matrix.pilot.roles.reservations("results")
    assert str(Path(PLAN).resolve()) in inputs
    assert dict(sha256=p["video_source"]["sha256"], segment=p["groups"][0]["video_segment"]) in ranges
    assert (
        cfg["does_not_replace_any_failed_training_peer"]
        and cfg["reused_failed_physical_context_not_independent"]
    )
    assert cfg["models_fitted"] == 0 and not Path(cfg["parent"]["path"], "manifest.json").exists()


@pytest.mark.parametrize(
    "case", ["role", "replace-training", "seed", "drop-peer", "window", "source-sha", "fake-complete"]
)
def test_actual_frozen_diagnostic_scope_runtime_and_byte_drift_rejected(case):
    c = read_json(PLAN)
    if case == "role":
        c["role"] = "train"
    elif case == "replace-training":
        c["does_not_replace_any_failed_training_peer"] = False
    elif case == "seed":
        c["runtimes"]["sintel"]["episodes"][0]["exploration_seed"] += 1
    elif case == "drop-peer":
        c["runtimes"]["sintel"]["episodes"] = []
    elif case == "window":
        c["runtimes"]["sintel"]["measurement_recipe"]["settled_future_start_after_ack_ms"] = 200
    elif case == "source-sha":
        c["source_sha256"]["assets/" + failure.HELPER] = "0" * 64
    else:
        c["native_deployment_qualified"] = True
    with pytest.raises(ValueError):
        failure.validate_plan(c)


def _good():
    return dict(
        native_rtc=True,
        connection="connected",
        snapshots=[
            dict(
                remote_candidate_address="127.0.0.1",
                frames_decoded=11,
                frames_encoded=12,
                mean_encode_s=0.003,
            )
        ],
        relay=dict(
            a_to_b=dict(forwarded_packets=100, capacity_integral_upper_bound_ok=True),
            b_to_a=dict(capacity_integral_upper_bound_ok=True),
        ),
    )


def test_python_recomputes_every_actual_original_js_guard_including_special_numeric_semantics():
    cases = []
    for name in (
        "good",
        "endpoint",
        "loopback",
        "forwarded",
        "capacity",
        "rtc",
        "connection",
        "decoded",
        "encoded",
        "missing-mean",
        "null-mean",
        "nan-mean",
        "inf-mean",
        "inf-count",
        "nan-forwarded",
    ):
        r = _good()
        unexpected = name == "endpoint"
        if name == "loopback":
            r["snapshots"][0]["remote_candidate_address"] = "10.0.0.1"
        elif name == "forwarded":
            r["relay"]["a_to_b"]["forwarded_packets"] = 99
        elif name == "capacity":
            r["relay"]["b_to_a"]["capacity_integral_upper_bound_ok"] = False
        elif name == "rtc":
            r["native_rtc"] = False
        elif name == "connection":
            r["connection"] = "disconnected"
        elif name == "decoded":
            r["snapshots"][0]["frames_decoded"] = 10
        elif name == "encoded":
            r["snapshots"][0]["frames_encoded"] = 10
        elif name == "missing-mean":
            r["snapshots"][0].pop("mean_encode_s")
        elif name == "null-mean":
            r["snapshots"][0]["mean_encode_s"] = None
        elif name == "nan-mean":
            r["snapshots"][0]["mean_encode_s"] = {failure.TAG: "NaN"}
        elif name == "inf-mean":
            r["snapshots"][0]["mean_encode_s"] = {failure.TAG: "+Infinity"}
        elif name == "inf-count":
            r["snapshots"][0]["frames_decoded"] = {failure.TAG: "+Infinity"}
        elif name == "nan-forwarded":
            r["relay"]["a_to_b"]["forwarded_packets"] = {failure.TAG: "NaN"}
        cases.append([r, unexpected])
    code = """const {nativeValidation}=await import(process.argv[1]);const cases=JSON.parse(process.argv[2],(_k,v)=>v&&typeof v==='object'&&Object.hasOwn(v,'__native_evidence_number_v1__')?({NaN:NaN,'+Infinity':Infinity,'-Infinity':-Infinity,undefined:undefined}[v.__native_evidence_number_v1__]):v);console.log(JSON.stringify(cases.map(([r,u])=>nativeValidation(r,u))));"""
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            code,
            (asset_directory() / failure.HELPER).as_uri(),
            json.dumps(cases),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == [failure.native_validation(r, u) for r, u in cases]
    assert failure.native_validation(_good())["all_original_guards_passed"]


def test_only_source_key_constant_changes_no_legacy_peer_bytecode_or_measurement_namespace():
    old = failure.matrix.pilot.audit_peer.__code__
    new = failure.RAW_PEER.__code__
    assert old.co_code == new.co_code and old.co_names == new.co_names
    assert sum(a != b for a, b in zip(old.co_consts, new.co_consts, strict=True)) == 1
    assert failure.RAW_PEER.__globals__["RAW_AUDIT"] is failure.matrix.pilot.RAW_AUDIT
    assert failure.RAW_PEER.__globals__["build_late_cohorts"] is failure.matrix.pilot.build_late
    assert failure.RAW_PEER.__globals__["build_reference_cohorts"] is failure.matrix.pilot.build_early
