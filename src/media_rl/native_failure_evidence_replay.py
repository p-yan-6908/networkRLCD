"""Read-only actual native evidence replay; distinct snapshot/final UDP counter phases."""

import argparse
import gzip
import json
from pathlib import Path

from . import native_failure_evidence as capture
from .native_protocol import digest, read_json, require, seal_directory, verify_seal, write_json

ABI = "native_lossless_pre_rejection_evidence_replay_v2"
_DROP = object()


def legacy_json(value, array=False):
    """Precisely reproduce original JSON.stringify omission/null, never alter full evidence."""
    if isinstance(value, dict) and set(value) == {capture.TAG}:
        require(value[capture.TAG] in ("undefined", "NaN", "+Infinity", "-Infinity"), "unknown typed number")
        return _DROP if value[capture.TAG] == "undefined" and not array else None
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            converted = legacy_json(v)
            if converted is not _DROP:
                result[k] = converted
        return result
    if isinstance(value, list):
        return [legacy_json(v, True) for v in value]
    return value


def verify_summary(raw, summary, event_count):
    result = raw["native_result"]
    later = dict(summary)
    final = later.pop("raw_event_count")
    require(
        type(raw["raw_event_count"]) is int
        and type(final) is int
        and 0 < raw["raw_event_count"] <= final == event_count,
        "before-persistence/final-gzip event counter ordering/count differs",
    )
    require(later == legacy_json(result), "entire actual original JSON native summary differs")
    return final


def _source_hashes(source):
    return {str(x.relative_to(source)): digest(x) for x in sorted(source.rglob("*")) if x.is_file()}


def inspect_source(source):
    source = Path(source).resolve()
    cfg = read_json(source / "protocol.json")
    p = capture.validate_plan(cfg)
    t = p["episodes"][0]
    child = source / "peer"
    require(
        p == read_json(source / "runtime.json")
        and (child / "panel_snapshot.json").read_bytes() == (source / "runtime.json").read_bytes(),
        "actual diagnostic panel differs",
    )
    require(
        digest(child / "source_snapshot.mjs") == p["extra_source_sha256"]["assets/" + capture.ENTRY],
        "actual diagnostic producer differs",
    )
    for name, sha in p["extra_source_sha256"].items():
        if name.startswith("assets/"):
            require(digest(child / name.split("/")[1]) == sha, "actual recorded source/helper bytes changed")
    raw = read_json(child / "native_result_before_validation.json")
    actual = read_json(child / "native_validation.json")
    require(
        raw["abi"] == capture.EVIDENCE_ABI
        and raw["diagnostic_only"] is True
        and type(raw["unexpected_udp"]) is bool,
        "identified diagnostic-only native return required",
    )
    result = raw["native_result"]
    require(
        result["collection_config"]
        == dict(panel_abi=p["panel_abi"], panel_sha256=digest(child / "panel_snapshot.json"), **t),
        "actual diagnostic role/trial identity differs",
    )
    validation = capture.native_validation(result, raw["unexpected_udp"])
    require(validation == actual, "every actual independently recomputed native check/guard differs")
    accepted = validation["all_original_guards_passed"]
    require(
        (child / "summary.json").exists() == accepted, "original native rejection/summary boundary differs"
    )
    derived = None
    final_count = None
    if accepted:
        events = gzip.decompress((child / "events.jsonl.gz").read_bytes()).splitlines()
        require(all(line for line in events), "empty actual UDP event")
        final_count = verify_summary(raw, read_json(child / "summary.json"), len(events))
        bundles = {
            k: capture.matrix.pilot.hold.base.dense._base_bundle(e["path"]) for k, e in p["models"].items()
        }
        _, derived = capture.RAW_PEER(child, p, t, bundles)
        require(
            all(c["role"] == "diagnostic" for c in derived["late_credit"]["cohorts"]),
            "diagnostic data relabeled for training",
        )
    report = dict(
        abi=ABI,
        role="diagnostic",
        source=dict(path=str(source), artifacts_sha256=_source_hashes(source)),
        implementation_sha256=digest(__file__),
        capture_implementation_sha256=digest(capture.__file__),
        actual_native_peers=1,
        all_actual_original_native_guards_passed=accepted,
        full_original_raw_cohort_encoder_replay_passed=accepted,
        full_pre_rejection_native_result_retained=True,
        actual_snapshot_count=len(result["snapshots"]),
        actual_failed_checks=[c["code"] for c in validation["checks"] if not c["passed"]],
        actual_first_rejection=validation["first_rejection"],
        actual_pre_persistence_event_count=raw["raw_event_count"],
        actual_final_gzip_event_count=final_count,
        snapshot_vs_final_event_counter_phases_explicit=True,
        diagnostic_factual_cohorts=len(derived["late_credit"]["cohorts"]) if derived else None,
        diagnostic_factual_requests=derived["late_credit"]["requests"] if derived else None,
        native_process_exit_code_not_persisted_not_inferred=True,
        original_capture_wrapper_failure_preserved=(source / "failure.json").exists(),
        original_capture_nominally_sealed=(source / "manifest.json").exists(),
        original_failed_matrix_recovered=False,
        original_failed_peer_exact_predicate_recovered=False,
        reused_failed_physical_context_not_independent=True,
        models_fitted=0,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    return report, derived


def replay(source, out):
    report, derived = inspect_source(source)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "report.json", report)
    if derived is not None:
        write_json(out / "derived.json", derived)
    seal_directory(
        out,
        sorted(str(x.relative_to(out)) for x in out.rglob("*") if x.is_file()),
        ABI + "_diagnostic_complete",
        native_training_source_complete=False,
        SOTA_achieved=False,
    )
    return report


def audit_replay(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_diagnostic_complete")
    saved = read_json(out / "report.json")
    source = Path(saved["source"]["path"])
    require(
        saved["implementation_sha256"] == digest(__file__)
        and saved["capture_implementation_sha256"] == digest(capture.__file__)
        and saved["source"]["artifacts_sha256"] == _source_hashes(source),
        "actual immutable replay/source bytes changed",
    )
    actual, derived = inspect_source(source)
    require(saved == actual, "every actual native diagnostic count/scope/replay flag differs")
    require(
        (out / "derived.json").exists() == (derived is not None),
        "rejected native result acquired nominal quality completion",
    )
    if derived is not None:
        require(
            read_json(out / "derived.json") == derived,
            "every actual original raw/cohort/encoder replay differs",
        )
    return dict(read_only=True, **actual)


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_failure_evidence_replay")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("replay")
    run.add_argument("--source", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "replay":
        r = replay(a.source, a.out)
    else:
        r = audit_replay(a.run)
    print(json.dumps({k: v for k, v in r.items() if k != "source"}, indent=2))


if __name__ == "__main__":
    main()
