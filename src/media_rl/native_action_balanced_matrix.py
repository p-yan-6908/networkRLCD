"""Prospective four-context balanced train data; no model action or validation fitting."""

import argparse
import copy
import json
import subprocess
from pathlib import Path

from . import native_action_balanced_hold as pilot
from . import native_action_late_forecast as frozen
from .native_action_learning import physical_group
from .native_protocol import (
    asset_directory,
    digest,
    read_json,
    require,
    seal_directory,
    verify_seal,
    write_json,
)

ABI = "native_four_context_balanced_training_v2"
FILMS = ("sintel", "bbb")
FAMILIES = ("stable", "collapse")


def _runtimes(cfg):
    templates = pilot.roles._templates(cfg["templates"], cfg["catalog"])
    result = {}
    new_folds = {}
    for fi, film in enumerate(FILMS):
        p = copy.deepcopy(templates[film])
        catalog = p["video_source"]
        own = []
        groups = []
        for gi, family in enumerate(FAMILIES):
            start = next(
                (
                    s
                    for s in range(60000, catalog["duration_ms"] - 20000, 20000)
                    if all(
                        x["sha256"] != catalog["sha256"]
                        or not pilot.hold.base.dense.video_overlap([s, s + 20000], x["segment"])
                        for x in [*cfg["excluded_video_ranges"], *own]
                    )
                ),
                None,
            )
            require(start is not None, "fresh full training ranges exhausted")
            segment = [start, start + 20000]
            own.append(dict(sha256=catalog["sha256"], segment=segment))
            order = list(pilot.hold.base.BEHAVIORS)
            groups.append(
                dict(
                    id=f"balanced-v2-{film}-{family}",
                    family=family,
                    scene_seed=gi * 2000,
                    reservation_frames=1000,
                    video_segment=segment,
                    schedule=[
                        [2.0, "high", 6000],
                        [2.0 if family == "stable" else 0.5, "collapse", 6000],
                        [2.0, "recovery", 6000],
                    ],
                    orders=[order[r:] + order[:r] for r in range(3)],
                    balanced_block_seed=11301 + fi * 10 + gi,
                )
            )
        for key in ("augmentation_parent", "late_random_hold_training_v2", "excluded_inputs_sha256"):
            p.pop(key, None)
        p.update(
            stage="train",
            groups=groups,
            repetitions=3,
            order_seed=11301 + fi * 10,
            excluded_video_ranges=cfg["excluded_video_ranges"],
            measurement_recipe=pilot.hold.RECIPE,
            existing_physical_groups_reused_not_independent=False,
            balanced_assignment_abi=pilot.control.ABI,
            no_forecaster_executed_by_native_controller=True,
        )
        p["episodes"] = pilot.hold.base.dense.trial_schedule(p)
        for trial in p["episodes"]:
            g = next(g for g in groups if g["id"] == trial["group"])
            trial["exploration_seed"] = pilot.control.encoded_seed(
                g["balanced_block_seed"], trial["repetition"]
            )
            new_folds[physical_group(p, trial)] = (FAMILIES.index(g["family"]) + fi) % 2
        p["extra_source_sha256"].update(cfg["source_sha256"])
        result[film] = p
    return result, new_folds


def plan_matrix(template_sintel, template_tos, catalog, old_train, out, results="results"):
    from . import native_action_balanced_value_cv as value

    require(not Path(out).exists(), "immutable prospective balanced matrix exists")
    old, data = frozen.training_source(old_train)
    templates = {
        film: dict(
            runtime=str(Path(path).resolve()),
            runtime_sha256=digest(path),
            manifest_sha256=digest(Path(path).resolve().parent / "manifest.json"),
        )
        for film, path in zip(FILMS, (template_sintel, template_tos), strict=True)
    }
    excluded, inputs = pilot.roles.reservations(results)
    assets = asset_directory()
    cfg = dict(
        abi=ABI,
        role="train",
        credit=pilot.hold.CREDIT,
        early_reference=pilot.hold.REFERENCE,
        assignment_abi=pilot.control.ABI,
        templates=templates,
        catalog=dict(path=str(Path(catalog).resolve()), sha256=digest(catalog)),
        excluded_video_ranges=excluded,
        excluded_inputs_sha256=inputs,
        old_train=dict(path=str(old), manifest_sha256=frozen.SOURCE_MANIFEST),
        cv_contract=value.CONTRACT,
        implementation_sha256=digest(__file__),
        value_implementation_sha256=digest(value.__file__),
        pilot_implementation_sha256=digest(pilot.__file__),
        control_sha256=digest(pilot.control.__file__),
        role_scanner_sha256=digest(pilot.roles.__file__),
        source_sha256={
            "assets/" + n: digest(assets / n)
            for n in ("balanced_hold_episode.mjs", "balanced_hold_control.mjs")
        },
        models_fitted_during_collection=0,
        locked_validation_labels_used=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    cfg["runtimes"], extra = _runtimes(cfg)
    old_report = read_json(old / "report.json")
    original = {g: i for i, f in enumerate(old_report["folds"]) for g in f["held_out_groups"]}
    require(
        set(original) == set(data["group"].tolist()) and not set(extra) & set(original),
        "old physical folds/new context independence changed",
    )
    cfg["physical_fold_map"] = {**original, **extra}
    validate_plan(cfg)
    write_json(out, cfg)
    return cfg


def validate_plan(cfg):
    from . import native_action_balanced_value_cv as value

    require(
        cfg["abi"] == ABI
        and cfg["role"] == "train"
        and cfg["credit"] == pilot.hold.CREDIT
        and cfg["early_reference"] == pilot.hold.REFERENCE
        and cfg["assignment_abi"] == pilot.control.ABI
        and cfg["cv_contract"] == value.CONTRACT
        and cfg["models_fitted_during_collection"] == 0
        and cfg["locked_validation_labels_used"] is False
        and cfg["native_deployment_qualified"] is False
        and cfg["SOTA_achieved"] is False,
        "fixed prospective training/credit/recipe scope required",
    )
    require(
        all(
            digest(path) == cfg[key]
            for path, key in [
                (__file__, "implementation_sha256"),
                (value.__file__, "value_implementation_sha256"),
                (pilot.__file__, "pilot_implementation_sha256"),
                (pilot.control.__file__, "control_sha256"),
                (pilot.roles.__file__, "role_scanner_sha256"),
            ]
        ),
        "prospective source/collector/sampler/role/model implementation changed",
    )
    require(
        all(digest(path) == sha for path, sha in cfg["excluded_inputs_sha256"].items()),
        "prior role inputs changed",
    )
    exclusions = []
    for path in cfg["excluded_inputs_sha256"]:
        raw = read_json(path)
        for p in [raw, *raw.get("runtimes", {}).values()]:
            if "video_source" in p and "groups" in p:
                exclusions.extend(
                    dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]
                )
    require(exclusions == cfg["excluded_video_ranges"], "full role exclusion snapshot changed")
    assets = asset_directory()
    require(
        set(cfg["source_sha256"]) == {"assets/balanced_hold_episode.mjs", "assets/balanced_hold_control.mjs"}
        and all(digest(assets / k.split("/")[1]) == v for k, v in cfg["source_sha256"].items()),
        "exact native entry/sampler changed",
    )
    require(
        (assets / "balanced_hold_episode.mjs").read_text()
        == pilot.project_collector((assets / "settled_hold_episode.mjs").read_text()),
        "full original producer projection changed",
    )
    expected, extra = _runtimes(cfg)
    require(
        expected == cfg["runtimes"] and all(len(p["episodes"]) == 18 for p in expected.values()),
        "full fresh four-group/36-peer runtime differs",
    )
    root, data = frozen.training_source(cfg["old_train"]["path"])
    require(
        cfg["old_train"]["manifest_sha256"] == frozen.SOURCE_MANIFEST, "old training external receipt changed"
    )
    original = {
        g: i for i, f in enumerate(read_json(root / "report.json")["folds"]) for g in f["held_out_groups"]
    }
    require(
        cfg["physical_fold_map"] == {**original, **extra}
        and len(original) == 8
        and len(extra) == 4
        and all(list(cfg["physical_fold_map"].values()).count(i) == 6 for i in range(2)),
        "old folds changed or new physical folds selected after labels",
    )
    return expected


def _report(rows, deriveds, cfg):
    report = pilot.hold._report(rows, deriveds)
    support = {}
    pairs = {}
    trajectories = {}
    trials = [(film, t) for film in FILMS for t in cfg["runtimes"][film]["episodes"]]
    for (film, t), d in zip(trials, deriveds, strict=True):
        if t["condition"] == "fixed450":
            continue
        require(
            len(d["late_credit"]["cohorts"]) == 5,
            "all factual epochs retained without quality/target screening",
        )
        for c in d["late_credit"]["cohorts"]:
            support.setdefault((t["group"], c["epoch"]), []).append(c["cap"])
            trajectories[(t["group"], t["condition"], t["repetition"], c["epoch"])] = c["cap"]
    for group in {g for g, e in support}:
        pairs[group] = {
            (trajectories[(group, "random-hold-a", r, e - 1)], trajectories[(group, "random-hold-a", r, e)])
            for r in range(3)
            for e in range(1, 4)
        }
        require(
            pairs[group] == {(a, b) for a in pilot.control.CAPS for b in pilot.control.CAPS},
            "actual per-group previous/current overlap missing",
        )
        require(
            all(
                trajectories[(group, "random-hold-a", r, e)] == trajectories[(group, "random-hold-b", r, e)]
                for r in range(3)
                for e in range(5)
            ),
            "actual alias assignments differ",
        )
    require(
        len(rows) == 36
        and len(support) == 20
        and all(sorted(c) == sorted(list(pilot.control.CAPS) * 2) for c in support.values()),
        "actual four-context all-arm data overlap failed",
    )
    report.update(
        abi=ABI,
        original_physical_groups=4,
        matched_group_epoch_strata=20,
        actual_all_three_arm_strata=20,
        per_group_previous_current_pairs={g: len(x) for g, x in pairs.items()},
        actual_full_episode_metrics_retained=True,
        plural_runtime_role_registration=True,
        model_generalization_or_safety_established=False,
    )
    return report


def collect_matrix(config, out):
    cfg = read_json(config)
    runtimes = validate_plan(cfg)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "protocol.json", cfg)
    rows = []
    deriveds = []
    try:
        for film in FILMS:
            p = runtimes[film]
            parent = out / film
            parent.mkdir()
            write_json(parent / "runtime.json", p)
            bundles = {k: pilot.hold.base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
            for trial in p["episodes"]:
                print(f"balanced-matrix {len(rows) + 1}/36 {trial['id']}", flush=True)
                child = parent / trial["id"]
                with (parent / (trial["id"] + ".log")).open("x") as log:
                    subprocess.run(
                        [
                            "node",
                            str(asset_directory() / "balanced_hold_episode.mjs"),
                            str(child),
                            str(parent / "runtime.json"),
                            trial["id"],
                            trial["condition"],
                        ],
                        timeout=120,
                        check=True,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                require(
                    (child / "panel_snapshot.json").read_bytes() == (parent / "runtime.json").read_bytes(),
                    "actual predeclared native panel differs",
                )
                row, derived = pilot.audit_peer(child, p, trial, bundles)
                write_json(child / "derived.json", derived)
                rows.append(row)
                deriveds.append(derived)
        require(
            all(rows[i]["cutoff_epoch_ms"] < rows[i + 1]["start_epoch_ms"] for i in range(35)),
            "complete nonoverlapping native peers required",
        )
        validate_plan(cfg)
        report = _report(rows, deriveds, cfg)
        write_json(out / "native_rows.json", rows)
        write_json(out / "report.json", report)
        seal_directory(
            out,
            sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()),
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


def audit_matrix(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    cfg = read_json(out / "protocol.json")
    runtimes = validate_plan(cfg)
    rows = []
    deriveds = []
    for film in FILMS:
        p = runtimes[film]
        parent = out / film
        require(p == read_json(parent / "runtime.json"), "actual runtime differs")
        bundles = {k: pilot.hold.base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
        for trial in p["episodes"]:
            child = parent / trial["id"]
            require(
                (child / "panel_snapshot.json").read_bytes() == (parent / "runtime.json").read_bytes(),
                "actual source snapshot differs",
            )
            row, derived = pilot.audit_peer(child, p, trial, bundles)
            require(
                derived == read_json(child / "derived.json"),
                "full actual native/late/reference/encoder replay differs",
            )
            rows.append(row)
            deriveds.append(derived)
    require(
        rows == read_json(out / "native_rows.json")
        and all(rows[i]["cutoff_epoch_ms"] < rows[i + 1]["start_epoch_ms"] for i in range(35)),
        "complete native rows/clocks differ",
    )
    report = _report(rows, deriveds, cfg)
    require(report == read_json(out / "report.json"), "actual matrix support/numeric flags differ")
    return dict(
        read_only=True,
        actual_peers=36,
        physical_groups=4,
        cohorts=report["randomized_cohorts"],
        requests=report["randomized_requests"],
        actual_all_three_arm_strata=20,
        complete_original_native_raw_and_cohort_encoder_replayed=True,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_balanced_matrix")
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
            planned_groups=4,
            fixed_cv_contract=c["cv_contract"],
            SOTA_achieved=False,
        )
    elif a.command == "collect":
        r = collect_matrix(a.config, a.out)
    else:
        r = audit_matrix(a.run)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
