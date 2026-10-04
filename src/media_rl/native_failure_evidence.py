"""Bounded diagnostic-only native failure evidence; no training retry or promotion."""

import argparse
import copy
import json
import math
import subprocess
from pathlib import Path
from types import FunctionType

from . import native_action_balanced_matrix as matrix
from .native_protocol import (
    asset_directory,
    digest,
    finite,
    read_json,
    require,
    seal_directory,
    verify_seal,
    write_json,
)

ABI = "native_pre_rejection_failure_evidence_diagnostic_v1"
EVIDENCE_ABI = "native_pre_rejection_failure_evidence_v1"
ENTRY = "native_failure_episode.mjs"
HELPER = "native_failure_evidence.mjs"
TAG = "__native_evidence_number_v1__"
FAILED = "balanced-v2-sintel-collapse-r2-random-hold-a"
REPLACEMENTS = [
    (
        "import {verifiedMovie} from './repair_http.mjs';",
        "import {verifiedMovie} from './repair_http.mjs';\nimport {retainNativeResult} from './native_failure_evidence.mjs';",
    ),
    (
        "panel.stage!=='train'",
        "(panel.stage!=='diagnostic'||panel.native_failure_evidence_diagnostic_only!==true)",
    ),
    (
        " if(links.some(l=>l.unexpected))throw Error('unexpected UDP source endpoint');",
        " await retainNativeResult(root,result,links.some(l=>l.unexpected),events.length);\n if(links.some(l=>l.unexpected))throw Error('unexpected UDP source endpoint');",
    ),
]


def project_collector(text):
    for old, new in REPLACEMENTS:
        require(text.count(old) == 1, "exact diagnostic role/import/retention-only projection required")
        text = text.replace(old, new)
    return text


_old = "assets/balanced_hold_episode.mjs"
_new = "assets/" + ENTRY
require(matrix.pilot.audit_peer.__code__.co_consts.count(_old) == 1, "sole diagnostic producer key required")
_code = matrix.pilot.audit_peer.__code__.replace(
    co_consts=tuple(_new if x == _old else x for x in matrix.pilot.audit_peer.__code__.co_consts)
)
RAW_PEER = FunctionType(_code, matrix.pilot.audit_peer.__globals__, "audit_failure_diagnostic_peer")


def _runtime(cfg):
    original = read_json(Path(cfg["parent"]["path"]) / "protocol.json")
    p = copy.deepcopy(original["runtimes"]["sintel"])
    t = copy.deepcopy(next(t for t in p["episodes"] if t["id"] == FAILED))
    t.update(id="native-stat-diagnostic-" + FAILED, role="diagnostic")
    p.update(
        stage="diagnostic",
        native_failure_evidence_diagnostic_only=True,
        groups=[g for g in p["groups"] if g["id"] == t["group"]],
        episodes=[t],
        conditions={t["condition"]: p["conditions"][t["condition"]]},
        existing_physical_groups_reused_not_independent=True,
    )
    p["extra_source_sha256"].update(cfg["source_sha256"])
    return p


def plan_diagnostic(parent, proof, out, results="results"):
    require(not Path(out).exists(), "immutable diagnostic plan exists")
    parent = Path(parent).resolve()
    proof = Path(proof).resolve()
    previous = read_json(proof)
    require(
        previous["failed_peer"] == FAILED
        and previous["actual_complete_peers"] == 16
        and previous["actual_models_fitted"] == 0
        and previous["source_protocol_sha256"] == digest(parent / "protocol.json")
        and previous["source_failure_sha256"] == digest(parent / "failure.json"),
        "exact previously audited partial/failed native source required",
    )
    matrix.validate_plan(read_json(parent / "protocol.json"))
    assets = asset_directory()
    _, inputs = matrix.pilot.roles.reservations(results)
    cfg = dict(
        abi=ABI,
        role="diagnostic",
        parent=dict(
            path=str(parent),
            protocol_sha256=digest(parent / "protocol.json"),
            failure_sha256=digest(parent / "failure.json"),
            proof=str(proof),
            proof_sha256=digest(proof),
        ),
        prior_reserved_inputs_sha256=inputs,
        implementation_sha256=digest(__file__),
        original_producer_sha256=digest(assets / "balanced_hold_episode.mjs"),
        source_sha256={"assets/" + n: digest(assets / n) for n in (ENTRY, HELPER)},
        planned_native_peers=1,
        reused_failed_physical_context_not_independent=True,
        does_not_replace_any_failed_training_peer=True,
        models_fitted=0,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    cfg["runtimes"] = {"sintel": _runtime(cfg)}
    validate_plan(cfg)
    write_json(out, cfg)
    return cfg


def validate_plan(cfg):
    require(
        cfg["abi"] == ABI
        and cfg["role"] == "diagnostic"
        and cfg["planned_native_peers"] == 1
        and cfg["models_fitted"] == 0
        and cfg["reused_failed_physical_context_not_independent"] is True
        and cfg["does_not_replace_any_failed_training_peer"] is True
        and cfg["native_deployment_qualified"] is False
        and cfg["SOTA_achieved"] is False,
        "one diagnostic-only reused-context/no-training scope required",
    )
    parent = Path(cfg["parent"]["path"])
    require(not (parent / "manifest.json").exists(), "original failed train matrix must stay incomplete")
    require(
        digest(parent / "protocol.json") == cfg["parent"]["protocol_sha256"]
        and digest(parent / "failure.json") == cfg["parent"]["failure_sha256"]
        and digest(cfg["parent"]["proof"]) == cfg["parent"]["proof_sha256"],
        "actual original failed source/proof changed",
    )
    matrix.validate_plan(read_json(parent / "protocol.json"))
    assets = asset_directory()
    require(
        digest(__file__) == cfg["implementation_sha256"]
        and digest(assets / "balanced_hold_episode.mjs") == cfg["original_producer_sha256"]
        and set(cfg["source_sha256"]) == {"assets/" + ENTRY, "assets/" + HELPER}
        and all(digest(assets / k.split("/")[1]) == v for k, v in cfg["source_sha256"].items()),
        "exact diagnostic/old producer/helper implementation changed",
    )
    require(
        (assets / ENTRY).read_text() == project_collector((assets / "balanced_hold_episode.mjs").read_text()),
        "full role/import/post-browser retention-only producer projection changed",
    )
    require(
        all(digest(p) == sha for p, sha in cfg["prior_reserved_inputs_sha256"].items()),
        "old all-role reservation input changed",
    )
    p = _runtime(cfg)
    require(cfg["runtimes"] == {"sintel": p}, "complete diagnostic source/role/seed/window/control differs")
    return p


def _number(v):
    if v is None:
        return 0.0
    if type(v) in (int, float):
        return v
    if isinstance(v, dict) and set(v) == {TAG}:
        return {"NaN": math.nan, "undefined": math.nan, "+Infinity": math.inf, "-Infinity": -math.inf}[v[TAG]]
    raise ValueError("invalid typed native numeric evidence")


def _truthy(v):
    if isinstance(v, dict) and set(v) == {TAG}:
        return v[TAG] in ("+Infinity", "-Infinity")
    if v is None:
        return False
    if isinstance(v, (list, dict)):
        return True
    return bool(v)


def native_validation(result, unexpected=False):
    snapshots = result["snapshots"]
    relay = result["relay"]
    checks = [
        dict(code="no_unexpected_udp_endpoint", passed=not unexpected),
        dict(
            code="all_remote_candidates_loopback",
            passed=all(s.get("remote_candidate_address") == "127.0.0.1" for s in snapshots),
        ),
        dict(
            code="at_least_100_forwarded_packets", passed=_number(relay["a_to_b"]["forwarded_packets"]) >= 100
        ),
        dict(
            code="a_to_b_capacity_integral",
            passed=_truthy(relay["a_to_b"]["capacity_integral_upper_bound_ok"]),
        ),
        dict(
            code="b_to_a_capacity_integral",
            passed=_truthy(relay["b_to_a"]["capacity_integral_upper_bound_ok"]),
        ),
        dict(code="native_rtc", passed=_truthy(result["native_rtc"])),
        dict(code="connected", passed=result["connection"] == "connected"),
    ]
    for i, s in enumerate(snapshots):
        checks.extend(
            [
                dict(
                    code=f"snapshot_{i}_frames_decoded_gt_10",
                    passed=_number(s.get("frames_decoded", {TAG: "undefined"})) > 10,
                ),
                dict(
                    code=f"snapshot_{i}_frames_encoded_gt_10",
                    passed=_number(s.get("frames_encoded", {TAG: "undefined"})) > 10,
                ),
                dict(code=f"snapshot_{i}_mean_encode_finite", passed=finite(s.get("mean_encode_s"))),
            ]
        )
    guards = [
        dict(message="unexpected UDP source endpoint", passed=not unexpected),
        dict(
            message="media bypassed relay or did not progress",
            passed=checks[1]["passed"] and not (_number(relay["a_to_b"]["forwarded_packets"]) < 100),
        ),
        dict(
            message="service exceeded capacity integral", passed=checks[3]["passed"] and checks[4]["passed"]
        ),
        dict(
            message="native media stats not valid",
            passed=checks[5]["passed"] and checks[6]["passed"] and all(c["passed"] for c in checks[7:]),
        ),
    ]
    return dict(
        abi=EVIDENCE_ABI,
        diagnostic_only=True,
        checks=checks,
        guards=guards,
        all_original_guards_passed=all(g["passed"] for g in guards),
        first_rejection=next((g["message"] for g in guards if not g["passed"]), None),
    )


def _report(child, p, exit_code):
    raw = read_json(child / "native_result_before_validation.json")
    validation = read_json(child / "native_validation.json")
    t = p["episodes"][0]
    require(
        raw["abi"] == EVIDENCE_ABI
        and raw["diagnostic_only"] is True
        and type(raw["unexpected_udp"]) is bool
        and type(raw["raw_event_count"]) is int
        and raw["raw_event_count"] > 0,
        "identified retained actual native evidence required",
    )
    result = raw["native_result"]
    require(
        result["collection_config"]
        == dict(panel_abi=p["panel_abi"], panel_sha256=digest(child / "panel_snapshot.json"), **t),
        "actual diagnostic trial/panel changed",
    )
    require(
        validation == native_validation(result, raw["unexpected_udp"]),
        "every actual retained native predicate/rejection differs",
    )
    accepted = validation["all_original_guards_passed"]
    require(
        type(exit_code) is int
        and (exit_code == 0) == accepted
        and (child / "summary.json").exists() == accepted,
        "original native rejection/summary gate changed",
    )
    require(
        digest(child / "source_snapshot.mjs") == p["extra_source_sha256"]["assets/" + ENTRY],
        "actual retention producer changed",
    )
    derived = None
    if accepted:
        summary = read_json(child / "summary.json")
        require(
            summary.pop("raw_event_count") == raw["raw_event_count"] and summary == result,
            "retained actual full result differs from successful original summary",
        )
        bundles = {k: matrix.pilot.hold.base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
        _, derived = RAW_PEER(child, p, t, bundles)
        require(
            all(c["role"] == "diagnostic" for c in derived["late_credit"]["cohorts"]),
            "diagnostic footage became training rows",
        )
    report = dict(
        abi=ABI,
        role="diagnostic",
        actual_native_peers=1,
        node_exit_code=exit_code,
        all_actual_original_native_guards_passed=accepted,
        full_original_raw_cohort_encoder_replay_passed=accepted,
        failed_checks=[c["code"] for c in validation["checks"] if not c["passed"]],
        first_rejection=validation["first_rejection"],
        snapshot_count=len(result["snapshots"]),
        full_pre_rejection_native_result_retained=True,
        actual_native_summary_available=accepted,
        diagnostic_factual_cohorts=len(derived["late_credit"]["cohorts"]) if derived else None,
        models_fitted=0,
        reused_failed_physical_context_not_independent=True,
        original_failed_matrix_recovered=False,
        original_failed_peer_exact_predicate_recovered=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    return report, derived


def run_diagnostic(config, out):
    cfg = read_json(config)
    p = validate_plan(cfg)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "protocol.json", cfg)
    write_json(out / "runtime.json", p)
    t = p["episodes"][0]
    try:
        with (out / "native.log").open("x") as log:
            r = subprocess.run(
                [
                    "node",
                    str(asset_directory() / ENTRY),
                    str(out / "peer"),
                    str(out / "runtime.json"),
                    t["id"],
                    t["condition"],
                ],
                timeout=120,
                check=False,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        require(
            (out / "peer/panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
            "actual predeclared diagnostic runtime differs",
        )
        report, derived = _report(out / "peer", p, r.returncode)
        if derived is not None:
            write_json(out / "derived.json", derived)
        validate_plan(cfg)
        write_json(out / "report.json", report)
        seal_directory(
            out,
            sorted(str(x.relative_to(out)) for x in out.rglob("*") if x.is_file()),
            ABI + "_diagnostic_complete",
            native_training_source_complete=False,
            SOTA_achieved=False,
        )
        return report
    except Exception as error:
        write_json(
            out / "failure.json",
            dict(error=str(error), diagnostic_attempt_retained=True, models_fitted=0, SOTA_achieved=False),
        )
        raise


def audit_diagnostic(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_diagnostic_complete")
    cfg = read_json(out / "protocol.json")
    p = validate_plan(cfg)
    require(
        p == read_json(out / "runtime.json")
        and (out / "peer/panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
        "complete actual diagnostic runtime differs",
    )
    report, derived = _report(out / "peer", p, read_json(out / "report.json")["node_exit_code"])
    require(
        report == read_json(out / "report.json"), "every actual diagnostic status/predicate/scope differs"
    )
    require(
        (out / "derived.json").exists() == (derived is not None),
        "rejected native peer acquired nominal cohort completion",
    )
    if derived is not None:
        require(
            derived == read_json(out / "derived.json"),
            "every actual original raw/cohort/encoder path differs",
        )
    return dict(read_only=True, **report)


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_failure_evidence")
    sub = p.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--parent", required=True)
    plan.add_argument("--proof", required=True)
    plan.add_argument("--out", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "plan":
        c = plan_diagnostic(a.parent, a.proof, a.out)
        r = dict(abi=ABI, role=c["role"], planned_native_peers=1, models_fitted=0, SOTA_achieved=False)
    elif a.command == "run":
        r = run_diagnostic(a.config, a.out)
    else:
        r = audit_diagnostic(a.run)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
