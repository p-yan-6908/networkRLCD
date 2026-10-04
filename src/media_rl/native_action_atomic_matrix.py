"""Fresh all-role-disjoint balanced train matrix with atomic pre-guard diagnostics."""

import argparse
import json
from pathlib import Path
from types import FunctionType, SimpleNamespace

from . import native_action_balanced_matrix as original
from . import native_failure_evidence as diagnostics
from . import native_failure_evidence_replay as serialization
from . import native_failure_snapshot as snapshot
from .native_protocol import asset_directory, digest, read_json, require, write_json

ABI = "native_atomic_four_context_balanced_training_v4"
ENTRY = "atomic_balanced_hold_episode.mjs"
FILMS = original.FILMS
FAMILIES = original.FAMILIES
# Stage remains original train: only the verified host-side atomic recording changes.
REPLACEMENTS = [x for x in snapshot.REPLACEMENTS if x[0] != "panel.stage!=='train'"]


def project_collector(text):
    for old, new in REPLACEMENTS:
        require(text.count(old) == 1, "exact train-only atomic recorder projection required")
        text = text.replace(old, new)
    return text


_old = "assets/balanced_hold_episode.mjs"
_new = "assets/" + ENTRY
require(
    original.pilot.audit_peer.__code__.co_consts.count(_old) == 1,
    "one atomic producer identity constant required",
)
_code = original.pilot.audit_peer.__code__.replace(
    co_consts=tuple(_new if x == _old else x for x in original.pilot.audit_peer.__code__.co_consts)
)
RAW_PEER = FunctionType(_code, original.pilot.audit_peer.__globals__, "audit_atomic_train_raw")


def audit_peer(child, p, t, bundles):
    child = Path(child)
    require(p["stage"] == t["role"] == "train", "actual train-only atomic trial required")
    raw = read_json(child / "native_result_before_validation.json")
    result = raw["native_result"]
    checks = diagnostics.native_validation(result, raw["unexpected_udp"])
    require(
        raw["abi"] == diagnostics.EVIDENCE_ABI
        and raw["diagnostic_only"] is True
        and checks == read_json(child / "native_validation.json")
        and checks["all_original_guards_passed"],
        "all actual independent pre-guard native checks required",
    )
    summary = read_json(child / "summary.json")
    later = dict(summary)
    count = later.pop("raw_event_count")
    require(
        count == raw["raw_event_count"] and later == serialization.legacy_json(result),
        "exact atomic ledger/count/full native return differs",
    )
    row, derived = RAW_PEER(child, p, t, bundles)
    require(
        all(
            c["role"] == "train"
            for field in ("late_credit", "early_reference")
            for c in derived[field]["cohorts"]
        ),
        "only genuine train cohort role required",
    )
    derived["atomic_pre_guard_native"] = dict(
        abi=diagnostics.EVIDENCE_ABI,
        actual_snapshot_count=len(result["snapshots"]),
        raw_event_count=count,
        all_original_guards_recomputed=True,
        used_by_controller=False,
    )
    return row, derived


_PILOT = SimpleNamespace(**{**original.pilot.__dict__, "audit_peer": audit_peer})
_NS = {**original.__dict__, "__file__": __file__, "ABI": ABI, "pilot": _PILOT}
_runtimes = FunctionType(original._runtimes.__code__, _NS, "atomic_fresh_runtimes")
_NS["_runtimes"] = _runtimes
_report = FunctionType(original._report.__code__, _NS, "atomic_overlap_report")
_NS["_report"] = _report


def _dependencies(value):
    return {
        str(Path(p).resolve()): digest(p)
        for p in [
            __file__,
            value.__file__,
            original.__file__,
            original.pilot.__file__,
            original.pilot.control.__file__,
            original.pilot.hold.__file__,
            original.pilot.roles.__file__,
            diagnostics.__file__,
            serialization.__file__,
            snapshot.__file__,
            value.base.__file__,
            value.identity.__file__,
            value.base.frozen.__file__,
            value.base.frozen.development.neural.__file__,
        ]
    }


def plan_matrix(template_sintel, template_tos, catalog, old_train, out, results="results"):
    from . import native_action_atomic_value_cv as value

    require(not Path(out).exists(), "immutable fresh atomic train plan exists")
    old, data = original.frozen.training_source(old_train)
    entries = {
        film: dict(
            runtime=str(Path(path).resolve()),
            runtime_sha256=digest(path),
            manifest_sha256=digest(Path(path).resolve().parent / "manifest.json"),
        )
        for film, path in zip(FILMS, (template_sintel, template_tos), strict=True)
    }
    excluded, inputs = original.pilot.roles.reservations(results)
    assets = asset_directory()
    cfg = dict(
        abi=ABI,
        role="train",
        credit=original.pilot.hold.CREDIT,
        early_reference=original.pilot.hold.REFERENCE,
        assignment_abi=original.pilot.control.ABI,
        templates=entries,
        catalog=dict(path=str(Path(catalog).resolve()), sha256=digest(catalog)),
        excluded_video_ranges=excluded,
        excluded_inputs_sha256=inputs,
        old_train=dict(path=str(old), manifest_sha256=original.frozen.SOURCE_MANIFEST),
        cv_contract=value.CONTRACT,
        dependencies_sha256=_dependencies(value),
        source_sha256={
            "assets/" + n: digest(assets / n)
            for n in (ENTRY, "balanced_hold_control.mjs", diagnostics.HELPER)
        },
        models_fitted_during_collection=0,
        locked_validation_labels_used=False,
        failed_or_diagnostic_source_reused=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    cfg["runtimes"], extra = _runtimes(cfg)
    original_folds = {
        g: i for i, f in enumerate(read_json(old / "report.json")["folds"]) for g in f["held_out_groups"]
    }
    require(
        set(original_folds) == set(data["group"].tolist()) and not set(extra) & set(original_folds),
        "old fold identities/new physical independence changed",
    )
    cfg["physical_fold_map"] = {**original_folds, **extra}
    validate_plan(cfg)
    write_json(out, cfg)
    return cfg


def validate_plan(cfg):
    from . import native_action_atomic_value_cv as value

    require(
        cfg["abi"] == ABI
        and cfg["role"] == "train"
        and cfg["credit"] == original.pilot.hold.CREDIT
        and cfg["early_reference"] == original.pilot.hold.REFERENCE
        and cfg["assignment_abi"] == original.pilot.control.ABI
        and cfg["cv_contract"] == value.CONTRACT
        and cfg["models_fitted_during_collection"] == 0
        and cfg["locked_validation_labels_used"] is False
        and cfg["failed_or_diagnostic_source_reused"] is False
        and cfg["native_deployment_qualified"] is False
        and cfg["SOTA_achieved"] is False,
        "fixed fresh atomic train/recipe/role scope required",
    )
    require(
        cfg["dependencies_sha256"] == _dependencies(value),
        "all actual collector/fitter/identity/credit/role/diagnostic dependencies changed",
    )
    require(
        all(digest(p) == v for p, v in cfg["excluded_inputs_sha256"].items()),
        "prior all-role reservation input changed",
    )
    excluded = []
    for path in cfg["excluded_inputs_sha256"]:
        raw = read_json(path)
        for p in [raw, *raw.get("runtimes", {}).values()]:
            if "video_source" in p and "groups" in p:
                excluded.extend(
                    dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]
                )
    require(excluded == cfg["excluded_video_ranges"], "full all-role exclusions changed")
    assets = asset_directory()
    require(
        set(cfg["source_sha256"])
        == {"assets/" + ENTRY, "assets/balanced_hold_control.mjs", "assets/" + diagnostics.HELPER}
        and all(digest(assets / k.split("/")[1]) == v for k, v in cfg["source_sha256"].items()),
        "exact atomic native entry/sampler/helper changed",
    )
    require(
        (assets / ENTRY).read_text() == project_collector((assets / "balanced_hold_episode.mjs").read_text()),
        "full original train producer/atomic projection changed",
    )
    expected, extra = _runtimes(cfg)
    require(
        cfg["runtimes"] == expected
        and all(len(p["episodes"]) == 18 and p["stage"] == "train" for p in expected.values()),
        "full fresh atomic 36-peer runtime changed",
    )
    old, data = original.frozen.training_source(cfg["old_train"]["path"])
    require(
        cfg["old_train"]["manifest_sha256"] == original.frozen.SOURCE_MANIFEST,
        "fixed original d33 train receipt changed",
    )
    old_folds = {
        g: i for i, f in enumerate(read_json(old / "report.json")["folds"]) for g in f["held_out_groups"]
    }
    require(
        set(old_folds) == set(data["group"].tolist())
        and not set(old_folds) & set(extra)
        and len(old_folds) == 8
        and len(extra) == 4
        and cfg["physical_fold_map"] == {**old_folds, **extra}
        and all(list(cfg["physical_fold_map"].values()).count(i) == 6 for i in range(2)),
        "fixed original eight/four fresh pre-label physical folds differ",
    )
    return expected


_NS["validate_plan"] = validate_plan
require(
    original.collect_matrix.__code__.co_consts.count("balanced_hold_episode.mjs") == 1,
    "sole atomic entry constant required",
)
_code = original.collect_matrix.__code__.replace(
    co_consts=tuple(
        ENTRY if x == "balanced_hold_episode.mjs" else x for x in original.collect_matrix.__code__.co_consts
    )
)
collect_matrix = FunctionType(_code, _NS, "collect_atomic_train")
audit_matrix = FunctionType(original.audit_matrix.__code__, _NS, "audit_atomic_train")


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_atomic_matrix")
    sub = p.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--template-sintel", required=True)
    plan.add_argument("--template-tos", required=True)
    plan.add_argument("--catalog", required=True)
    plan.add_argument("--old-train", required=True)
    plan.add_argument("--out", required=True)
    run = sub.add_parser("collect")
    run.add_argument("--config", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "plan":
        c = plan_matrix(a.template_sintel, a.template_tos, a.catalog, a.old_train, a.out)
        r = dict(
            abi=ABI,
            planned_peers=36,
            physical_groups=4,
            prior_reserved_inputs=len(c["excluded_inputs_sha256"]),
            models_fitted=0,
            SOTA_achieved=False,
        )
    elif a.command == "collect":
        r = collect_matrix(a.config, a.out)
    else:
        r = audit_matrix(a.run)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
