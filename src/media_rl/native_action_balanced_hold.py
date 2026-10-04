"""Bounded fresh train-only balanced assignment pilot; not a model/deployment result."""

import argparse
import copy
import json
import subprocess
from pathlib import Path
from types import FunctionType

from . import native_action_balanced_control as control
from . import native_action_late_validation as roles
from . import native_action_settled_hold as hold
from .native_protocol import (
    asset_directory,
    digest,
    read_json,
    require,
    seal_directory,
    verify_seal,
    write_json,
)

ABI = "native_three_arm_balanced_hold_pilot_v1"
SEED = 10801
RAW_AUDIT = FunctionType(
    hold.RAW_AUDIT.__code__,
    {**hold.RAW_AUDIT.__globals__, "exploration_cap": control.settled_cap},
    "audit_balanced_raw",
)
build_late = FunctionType(
    hold.build_late_cohorts.__code__,
    {**hold.build_late_cohorts.__globals__, "exploration_cap": control.settled_cap},
    "build_balanced_late",
)
build_early = FunctionType(
    hold.build_reference_cohorts.__code__,
    {**hold.build_reference_cohorts.__globals__, "exploration_cap": control.settled_cap},
    "build_balanced_reference",
)
# A source-entry key is the sole changed code constant. All measurement bytecode,
# nested cohort/sidecar/raw code and historical module globals remain untouched.
_old = "assets/settled_hold_episode.mjs"
_new = "assets/balanced_hold_episode.mjs"
require(hold.audit_peer.__code__.co_consts.count(_old) == 1, "exact source-key-only peer projection required")
_peer_code = hold.audit_peer.__code__.replace(
    co_consts=tuple(_new if x == _old else x for x in hold.audit_peer.__code__.co_consts)
)
audit_peer = FunctionType(
    _peer_code,
    {
        **hold.audit_peer.__globals__,
        "RAW_AUDIT": RAW_AUDIT,
        "build_late_cohorts": build_late,
        "build_reference_cohorts": build_early,
    },
    "audit_balanced_peer",
)


def project_collector(text):
    for old, new, count in [
        (
            "// Independent training-only randomized cap holds; never learned or qualified control.",
            "// Independent train-only arm/transition-balanced pilot; never learned or qualified control.",
            1,
        ),
        ("'/settled_hold_control.mjs'", "'/balanced_hold_control.mjs'", 2),
    ]:
        require(text.count(old) == count, "exact balanced assignment-entry-only projection required")
        text = text.replace(old, new)
    return text


def _runtime(cfg):
    p = copy.deepcopy(roles._templates(cfg["templates"], cfg["catalog"])["bbb"])
    catalog = p["video_source"]
    start = next(
        (
            s
            for s in range(60000, catalog["duration_ms"] - 20000, 20000)
            if all(
                x["sha256"] != catalog["sha256"]
                or not hold.base.dense.video_overlap([s, s + 20000], x["segment"])
                for x in cfg["excluded_video_ranges"]
            )
        ),
        None,
    )
    require(start is not None, "fresh full training source reservation exhausted")
    for key in ("augmentation_parent", "late_random_hold_training_v2", "excluded_inputs_sha256"):
        p.pop(key, None)
    order = list(hold.base.BEHAVIORS)
    group = dict(
        id="balanced-bbb-collapse",
        family="balanced-collapse",
        scene_seed=0,
        reservation_frames=1000,
        video_segment=[start, start + 20000],
        schedule=[[2.0, "high", 6000], [0.5, "collapse", 6000], [2.0, "recovery", 6000]],
        orders=[order[r:] + order[:r] for r in range(3)],
    )
    p.update(
        stage="train",
        groups=[group],
        repetitions=3,
        order_seed=SEED,
        excluded_video_ranges=cfg["excluded_video_ranges"],
        measurement_recipe=hold.RECIPE,
        existing_physical_groups_reused_not_independent=False,
        balanced_assignment_abi=control.ABI,
        balanced_block_seed=SEED,
        no_model_fitted_or_executed=True,
    )
    p["episodes"] = hold.base.dense.trial_schedule(p)
    for t in p["episodes"]:
        t["exploration_seed"] = control.encoded_seed(SEED, t["repetition"])
    p["extra_source_sha256"].update(cfg["source_sha256"])
    return p


def plan_balanced(template_sintel, template_tos, catalog, out, results="results"):
    require(not Path(out).exists(), "immutable balanced plan exists")
    templates = {
        film: dict(
            runtime=str(Path(path).resolve()),
            runtime_sha256=digest(path),
            manifest_sha256=digest(Path(path).resolve().parent / "manifest.json"),
        )
        for film, path in zip(roles.FILMS, (template_sintel, template_tos), strict=True)
    }
    excluded, inputs = roles.reservations(results)
    assets = asset_directory()
    require(
        (assets / "balanced_hold_episode.mjs").read_text()
        == project_collector((assets / "settled_hold_episode.mjs").read_text()),
        "full exact producer projection required",
    )
    cfg = dict(
        abi=ABI,
        role="train",
        assignment_abi=control.ABI,
        credit=hold.CREDIT,
        early_reference=hold.REFERENCE,
        templates=templates,
        catalog=dict(path=str(Path(catalog).resolve()), sha256=digest(catalog)),
        excluded_video_ranges=excluded,
        excluded_inputs_sha256=inputs,
        implementation_sha256=digest(__file__),
        control_sha256=digest(control.__file__),
        hold_sha256=digest(hold.__file__),
        role_scanner_sha256=digest(roles.__file__),
        source_sha256={
            "assets/" + n: digest(assets / n)
            for n in ("balanced_hold_episode.mjs", "balanced_hold_control.mjs")
        },
        models_fitted=0,
        locked_prior_validation_never_used_for_training=True,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    cfg["runtime"] = _runtime(cfg)
    validate_plan(cfg)
    write_json(out, cfg)
    return cfg


def validate_plan(cfg):
    require(
        cfg["abi"] == ABI
        and cfg["role"] == "train"
        and cfg["assignment_abi"] == control.ABI
        and cfg["credit"] == hold.CREDIT
        and cfg["early_reference"] == hold.REFERENCE
        and cfg["models_fitted"] == 0
        and cfg["locked_prior_validation_never_used_for_training"] is True
        and cfg["native_deployment_qualified"] is False
        and cfg["SOTA_achieved"] is False,
        "fixed training-only balanced scope required",
    )
    require(
        all(
            digest(p) == cfg[k]
            for p, k in [
                (__file__, "implementation_sha256"),
                (control.__file__, "control_sha256"),
                (hold.__file__, "hold_sha256"),
                (roles.__file__, "role_scanner_sha256"),
            ]
        ),
        "balanced/source/credit/role implementation changed",
    )
    require(
        all(digest(path) == sha for path, sha in cfg["excluded_inputs_sha256"].items()),
        "prior-role reservation inputs changed",
    )
    exclusions = []
    for path in cfg["excluded_inputs_sha256"]:
        raw = read_json(path)
        for p in [raw, *raw.get("runtimes", {}).values()]:
            if "video_source" in p and "groups" in p:
                exclusions.extend(
                    dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]
                )
    require(exclusions == cfg["excluded_video_ranges"], "complete all-role exclusions changed")
    assets = asset_directory()
    require(
        set(cfg["source_sha256"]) == {"assets/balanced_hold_episode.mjs", "assets/balanced_hold_control.mjs"}
        and all(digest(assets / k.split("/")[1]) == v for k, v in cfg["source_sha256"].items()),
        "balanced actual entry/sampler changed",
    )
    require(
        (assets / "balanced_hold_episode.mjs").read_text()
        == project_collector((assets / "settled_hold_episode.mjs").read_text()),
        "full producer body projection changed",
    )
    expected = _runtime(cfg)
    require(
        expected == cfg["runtime"] and len(expected["episodes"]) == 9,
        "exact complete nine-peer/three-replica seeded runtime required",
    )
    return expected


def _report(rows, deriveds, p):
    report = hold._report(rows, deriveds)
    strata = {}
    trajectories = {}
    for trial, derived in zip(p["episodes"], deriveds, strict=True):
        if trial["condition"] == "fixed450":
            continue
        require(
            len(derived["late_credit"]["cohorts"]) == 5,
            "all five factual epochs required, no target or quality selection",
        )
        for c in derived["late_credit"]["cohorts"]:
            strata.setdefault(c["epoch"], []).append(c["cap"])
            trajectories[(trial["condition"], trial["repetition"], c["epoch"])] = c["cap"]
    pairs = {
        (trajectories[("random-hold-a", r, e - 1)], trajectories[("random-hold-a", r, e)])
        for r in range(3)
        for e in range(1, 4)
    }
    expected_pairs = {(a, b) for a in control.CAPS for b in control.CAPS}
    require(
        set(strata) == set(range(5))
        and all(sorted(caps) == sorted(list(control.CAPS) * 2) for caps in strata.values())
        and pairs == expected_pairs,
        "actual local all-arm/complete transition overlap failed",
    )
    require(
        all(
            trajectories[("random-hold-a", r, e)] == trajectories[("random-hold-b", r, e)]
            for r in range(3)
            for e in range(5)
        ),
        "actual alias assignments differ",
    )
    report.update(
        abi=ABI,
        assignment_abi=control.ABI,
        original_physical_groups=1,
        matched_group_epoch_strata=5,
        actual_all_three_arm_strata=5,
        actual_previous_current_transition_pairs=9,
        all_three_arm_counts_per_epoch={
            str(e): {str(c): caps.count(c) for c in control.CAPS} for e, caps in strata.items()
        },
        actual_full_episode_rows_retained=True,
        all_request_safety_or_counterfactual_gain_established=False,
        one_group_pilot_not_learning_or_generalization_acceptance=True,
    )
    return report


def run_balanced(config, out):
    cfg = read_json(config)
    p = validate_plan(cfg)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "protocol.json", cfg)
    write_json(out / "runtime.json", p)
    bundles = {k: hold.base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    rows = []
    deriveds = []
    try:
        for i, trial in enumerate(p["episodes"]):
            print(f"balanced {i + 1}/9 {trial['id']}", flush=True)
            child = out / trial["id"]
            with (out / (trial["id"] + ".log")).open("x") as log:
                subprocess.run(
                    [
                        "node",
                        str(asset_directory() / "balanced_hold_episode.mjs"),
                        str(child),
                        str(out / "runtime.json"),
                        trial["id"],
                        trial["condition"],
                    ],
                    timeout=120,
                    check=True,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            require(
                (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
                "actual balanced native snapshot differs",
            )
            row, derived = audit_peer(child, p, trial, bundles)
            write_json(child / "derived.json", derived)
            rows.append(row)
            deriveds.append(derived)
        require(
            all(rows[i]["cutoff_epoch_ms"] < rows[i + 1]["start_epoch_ms"] for i in range(8)),
            "nonoverlapping complete native clocks required",
        )
        validate_plan(cfg)
        report = _report(rows, deriveds, p)
        write_json(out / "native_rows.json", rows)
        write_json(out / "report.json", report)
        seal_directory(
            out,
            sorted(str(x.relative_to(out)) for x in out.rglob("*") if x.is_file()),
            ABI + "_complete",
            SOTA_achieved=False,
        )
        return report
    except Exception as error:
        write_json(
            out / "failure.json",
            dict(
                error=str(error),
                completed_peers=len(rows),
                all_raw_and_logs_retained=True,
                SOTA_achieved=False,
            ),
        )
        raise


def audit_balanced(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    cfg = read_json(out / "protocol.json")
    p = validate_plan(cfg)
    require(p == read_json(out / "runtime.json"), "actual balanced runtime changed")
    bundles = {k: hold.base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    rows = []
    deriveds = []
    for trial in p["episodes"]:
        child = out / trial["id"]
        require(
            (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
            "actual balanced snapshot changed",
        )
        row, derived = audit_peer(child, p, trial, bundles)
        require(
            derived == read_json(child / "derived.json"),
            "complete actual raw/cohort/reference/encoder replay changed",
        )
        rows.append(row)
        deriveds.append(derived)
    require(
        rows == read_json(out / "native_rows.json")
        and all(rows[i]["cutoff_epoch_ms"] < rows[i + 1]["start_epoch_ms"] for i in range(8)),
        "original native rows/nonoverlapping clocks changed",
    )
    report = _report(rows, deriveds, p)
    require(report == read_json(out / "report.json"), "actual numerical balanced support report changed")
    return dict(
        read_only=True,
        actual_peers=9,
        complete_original_native_raw_and_cohort_and_encoder_replay=True,
        actual_all_three_arm_strata=report["actual_all_three_arm_strata"],
        actual_previous_current_transition_pairs=9,
        cohorts=report["randomized_cohorts"],
        requests=report["randomized_requests"],
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_balanced_hold")
    sub = p.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--template-sintel", required=True)
    plan.add_argument("--template-tos", required=True)
    plan.add_argument("--catalog", required=True)
    plan.add_argument("--out", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "plan":
        r = plan_balanced(a.template_sintel, a.template_tos, a.catalog, a.out)
        result = dict(abi=ABI, actual_peers_planned=len(r["runtime"]["episodes"]), SOTA_achieved=False)
    elif a.command == "run":
        result = run_balanced(a.config, a.out)
    else:
        result = audit_balanced(a.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
