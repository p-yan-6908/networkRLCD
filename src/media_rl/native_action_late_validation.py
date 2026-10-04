"""Prospective role-disjoint factual forecast validation, never selected native control."""

import argparse
import copy
import itertools
import json
import subprocess
from pathlib import Path

import numpy as np

from . import native_action_late_forecast as forecast
from . import native_action_settled_hold as hold
from .native_action_learning import physical_group
from .native_protocol import (
    SCHEDULES,
    asset_directory,
    digest,
    read_json,
    require,
    seal_directory,
    verify_seal,
    write_json,
)

ABI = "native_role_disjoint_late_forecast_validation_v3"
CRITERIA = dict(
    minimum_action_utility_skill=0.01,
    minimum_prior_utility_skill=0.01,
    minimum_prior_risk_skill=0.0,
    minimum_original_groups=4,
    pooled_and_each_film_action_information_required=True,
    physical_group_resample_ci95_lower_above_zero_required=True,
    no_validation_tuning_or_calibration=True,
    not_selected_native_control_or_all_request_safety=True,
)
FILMS = ("sintel", "bbb")
FAMILIES = ("stable", "brief-collapse")


def project_collector(text):
    for old, new in (
        (
            "// Independent training-only randomized cap holds; never learned or qualified control.",
            "// Independent validation-only randomized holds; frozen forecasters never control native actions.",
        ),
        ("panel.stage!=='train'", "panel.stage!=='validation'"),
    ):
        require(text.count(old) == 1, "exact validation entry-only projection required")
        text = text.replace(old, new)
    return text


def reservations(results):
    paths = set(Path(results).glob("**/protocol.json"))
    configs = Path(results).resolve().parent / "configs"
    paths |= set(configs.glob("native_*.json"))
    excluded = []
    inputs = {}
    for path in sorted(paths):
        p = read_json(path)
        records = [p] + list(p.get("runtimes", {}).values())
        for q in records:
            if "video_source" not in q or "groups" not in q:
                continue
            inputs[str(path.resolve())] = digest(path)
            for g in q["groups"]:
                excluded.append(dict(sha256=q["video_source"]["sha256"], segment=g["video_segment"]))
    return excluded, inputs


def _templates(entries, replacement):
    result = {}
    for film in FILMS:
        e = entries[film]
        path = Path(e["runtime"])
        require(
            digest(path) == e["runtime_sha256"]
            and digest(path.parent / "manifest.json") == e["manifest_sha256"],
            "original catalog/common-shadow template changed",
        )
        verify_seal(path.parent, hold.ABI + "_complete")
        p = read_json(path)
        require(
            p["stage"] == "train" and p["repair_model"] is None and p["learner"] is None,
            "catalog/shadow-only template required; original labels not reused",
        )
        result[film] = p
    path = Path(replacement["path"])
    require(digest(path) == replacement["sha256"], "new held-out movie catalog changed")
    catalog = hold.base.dense.validate_catalog(read_json(path))
    require(
        catalog["sha256"] not in {p["video_source"]["sha256"] for p in result.values()},
        "replacement movie must be wholly unseen by original training",
    )
    result["bbb"]["video_source"] = catalog
    return result


def _runtimes(templates, excluded, candidate_manifest):
    result = {}
    for film_i, film in enumerate(FILMS):
        p = copy.deepcopy(templates[film])
        catalog = p["video_source"]
        groups = []
        own = []
        seed = 9901 + film_i * 10
        rng = np.random.default_rng(seed)
        for i, family in enumerate(FAMILIES):
            start = next(
                (
                    s
                    for s in range(60000, catalog["duration_ms"] - 20000, 20000)
                    if all(
                        x["sha256"] != catalog["sha256"]
                        or not hold.base.dense.video_overlap([s, s + 20000], x["segment"])
                        for x in [*excluded, *own]
                    )
                ),
                None,
            )
            require(start is not None, "fresh licensed validation source reservations exhausted")
            segment = [start, start + 20000]
            own.append(dict(sha256=catalog["sha256"], segment=segment))
            scale = float(rng.uniform(0.85, 1.15))
            schedule = [[round(cap * scale, 5), label, 6000] for cap, label, _ in SCHEDULES[family]]
            order = list(rng.permutation(list(hold.base.BEHAVIORS)))
            groups.append(
                dict(
                    id=f"val-{film}-{family}",
                    family=family,
                    scene_seed=i * 2000,
                    reservation_frames=1000,
                    video_segment=segment,
                    schedule=schedule,
                    orders=[order, order[1:] + order[:1]],
                )
            )
        for inherited_train_key in (
            "augmentation_parent",
            "late_random_hold_training_v2",
            "excluded_inputs_sha256",
        ):
            p.pop(inherited_train_key, None)
        p.update(
            stage="validation",
            groups=groups,
            repetitions=2,
            order_seed=seed,
            excluded_video_ranges=excluded,
            measurement_recipe=hold.RECIPE,
            existing_physical_groups_reused_not_independent=False,
            no_forecasters_executed_by_native_controller=True,
            frozen_forecast_candidate_manifest_sha256=candidate_manifest,
        )
        p["episodes"] = hold.base.dense.trial_schedule(p)
        p["extra_source_sha256"]["assets/late_validation_episode.mjs"] = digest(
            asset_directory() / "late_validation_episode.mjs"
        )
        result[film] = p
    return result


def plan_validation(candidate, template_sintel, template_tos, replacement_catalog, out, results="results"):
    out = Path(out)
    require(not out.exists(), "immutable validation plan exists")
    candidate = Path(candidate).resolve()
    forecast.audit_forecast(candidate)
    entries = {
        film: dict(
            runtime=str(Path(path).resolve()),
            runtime_sha256=digest(path),
            manifest_sha256=digest(Path(path).resolve().parent / "manifest.json"),
        )
        for film, path in zip(FILMS, (template_sintel, template_tos), strict=True)
    }
    replacement = dict(path=str(Path(replacement_catalog).resolve()), sha256=digest(replacement_catalog))
    excluded, inputs = reservations(results)
    runtimes = _runtimes(_templates(entries, replacement), excluded, digest(candidate / "manifest.json"))
    cfg = dict(
        abi=ABI,
        role="validation",
        criteria=CRITERIA,
        credit=hold.CREDIT,
        early_reference=hold.REFERENCE,
        candidate=dict(path=str(candidate), manifest_sha256=digest(candidate / "manifest.json")),
        templates=entries,
        replacement_catalog=replacement,
        excluded_video_ranges=excluded,
        excluded_inputs_sha256=inputs,
        runtimes=runtimes,
        implementation_sha256=digest(__file__),
        forecast_implementation_sha256=digest(forecast.__file__),
        hold_implementation_sha256=digest(hold.__file__),
        producer_sha256=digest(asset_directory() / "late_validation_episode.mjs"),
        source_content_limit="reserved late-film Sintel plus wholly held-out Big Buck Bunny; small animation-domain validation, not representative corpus",
        no_target_quality_or_result_based_selection=True,
        models_fitted_during_validation=0,
        SOTA_achieved=False,
    )
    validate_plan(cfg)
    write_json(out, cfg)
    return cfg


def validate_plan(cfg):
    require(
        cfg["abi"] == ABI
        and cfg["role"] == "validation"
        and cfg["criteria"] == CRITERIA
        and cfg["credit"] == hold.CREDIT
        and cfg["early_reference"] == hold.REFERENCE
        and cfg["models_fitted_during_validation"] == 0
        and cfg["no_target_quality_or_result_based_selection"] is True
        and cfg["SOTA_achieved"] is False,
        "fixed validation role/criteria/credit/no-fitting required",
    )
    require(
        digest(__file__) == cfg["implementation_sha256"]
        and digest(forecast.__file__) == cfg["forecast_implementation_sha256"]
        and digest(hold.__file__) == cfg["hold_implementation_sha256"],
        "frozen validation/candidate/hold implementation changed",
    )
    require(
        all(digest(k) == v for k, v in cfg["excluded_inputs_sha256"].items()),
        "preexisting role-reservation inputs changed",
    )
    snapshot = []
    for path in sorted(cfg["excluded_inputs_sha256"]):
        saved = read_json(path)
        for record in [saved, *saved.get("runtimes", {}).values()]:
            if "video_source" in record and "groups" in record:
                snapshot.extend(
                    dict(sha256=record["video_source"]["sha256"], segment=g["video_segment"])
                    for g in record["groups"]
                )
    require(snapshot == cfg["excluded_video_ranges"], "complete role-exclusion snapshot changed")
    require(
        digest(Path(cfg["candidate"]["path"]) / "manifest.json") == cfg["candidate"]["manifest_sha256"],
        "frozen candidate changed after validation plan",
    )
    asset = asset_directory()
    require(
        digest(asset / "late_validation_episode.mjs") == cfg["producer_sha256"]
        and (asset / "late_validation_episode.mjs").read_text()
        == project_collector((asset / "settled_hold_episode.mjs").read_text()),
        "exact actual validation-only entry projection required",
    )
    expected = _runtimes(
        _templates(cfg["templates"], cfg["replacement_catalog"]),
        cfg["excluded_video_ranges"],
        cfg["candidate"]["manifest_sha256"],
    )
    require(expected == cfg["runtimes"], "exact role-disjoint source/seed/schedule/order plan required")
    train = read_json(Path(cfg["candidate"]["path"]) / "report.json")["training_physical_groups"]
    groups = [physical_group(p, t) for p in expected.values() for t in p["episodes"]]
    require(
        len(set(groups)) == 4 and not (set(groups) & set(train)), "four truly new physical groups required"
    )
    for p in expected.values():
        require(
            digest(p["video_source"]["path"]) == p["video_source"]["sha256"]
            and all(digest(e["path"]) == e["sha256"] for e in p["models"].values()),
            "actual owned movie/common-shadow model changed",
        )
        require(
            all(t["role"] == "validation" for t in p["episodes"]),
            "runtime cannot relabel original training trials",
        )
    return expected


def audit_peer(child, p, trial, bundles):
    child = Path(child)
    require(
        p["stage"] == trial["role"] == "validation"
        and digest(child / "source_snapshot.mjs")
        == p["extra_source_sha256"]["assets/late_validation_episode.mjs"],
        "actual validation-role producer/source required",
    )
    # Same entire V2 native guard code object; only entry permits real validation.
    row, derived = hold.RAW_AUDIT(child, p, trial, bundles, None)
    sender = read_json(child / "sender_observations.json")
    frames = read_json(child / "frame_events.json")
    states = hold.reconstruct_states(sender, frames)
    labels = derived["quality"]["source_labels"]
    late = hold.build_late_cohorts(sender, labels, states, trial)
    early = hold.build_reference_cohorts(sender, labels, states, trial)
    # V1 builders hardcode a train metadata label, not eligibility. Truthful role
    # is assigned only after the actual validation panel/source/raw guards above.
    for records in (late, early):
        for c in records["cohorts"]:
            c["role"] = "validation"
            c["target_status_not_used_to_filter"] = True
    derived.update(
        late_credit=late,
        early_reference=early,
        encoder_sidecar=hold.encoder.summarize_encoder_sidecars(sender, frames),
    )
    return row, derived


def data_from(cfg, all_derived):
    rows = []
    for film, p in cfg["runtimes"].items():
        for trial in p["episodes"]:
            if trial["condition"] == "fixed450":
                continue
            derived = all_derived[(film, trial["id"])]
            for c in derived["late_credit"]["cohorts"]:
                require(
                    c["role"] == "validation"
                    and c["future_actions_mixed"] is False
                    and c["counterfactual_labels_used"] is False
                    and c["target_status_not_used_to_filter"] is True,
                    "all factual validation rows required",
                )
                rows.append(
                    dict(
                        state=c["state"],
                        cap=c["cap"],
                        targets=[c["utility"], c["miss"]],
                        weight=c["weight"],
                        group=physical_group(p, trial),
                        film=film,
                    )
                )
    d = {
        k: np.asarray([r[k] for r in rows], dtype=np.int64 if k in ("weight", "cap") else None)
        for k in ("state", "cap", "targets", "weight", "group", "film")
    }
    n = len(rows)
    require(
        n > 0
        and d["state"].shape == (n, 736)
        and d["targets"].shape == (n, 2)
        and set(d["cap"].tolist()) == {300000, 450000, 900000}
        and set(d["film"].tolist()) == set(FILMS)
        and len(set(d["group"].tolist())) == 4,
        "complete four-group/two-film/all-cap factual validation matrix required",
    )
    require(
        np.isfinite(d["state"]).all()
        and np.isfinite(d["targets"]).all()
        and ((d["targets"] >= 0) & (d["targets"] <= 1)).all()
        and (d["weight"] > 0).all(),
        "finite original history/bounded factual utility/miss/positive weights required",
    )
    return d


def _skill(error, baseline):
    # A perfect blind/prior baseline provides no room for improvement. Never
    # convert zero/zero into apparent 100% skill through a denominator floor.
    if baseline <= 1e-12:
        return 0.0 if error <= 1e-12 else -float(error / 1e-12)
    return float(1 - error / baseline)


def evaluate(data, models, train):
    prediction = {
        mode: np.mean([forecast.PREDICT(m, data["state"], data["cap"]) for m in members], axis=0)
        for mode, members in models.items()
    }
    prior = {
        int(c): np.average(
            train["targets"][train["cap"] == c], axis=0, weights=train["weight"][train["cap"] == c]
        )
        for c in set(train["cap"].tolist())
    }
    pp = np.asarray([prior[int(c)] for c in data["cap"]])
    out = {}
    for label, mask in [
        ("pooled", np.ones(len(data["cap"]), dtype=bool)),
        *[(s, data["film"] == s) for s in FILMS],
    ]:
        e = {
            mode: np.average((pr[mask] - data["targets"][mask]) ** 2, axis=0, weights=data["weight"][mask])
            for mode, pr in prediction.items()
        }
        pe = np.average((pp[mask] - data["targets"][mask]) ** 2, axis=0, weights=data["weight"][mask])
        out[label] = dict(
            rows=int(mask.sum()),
            requests=int(data["weight"][mask].sum()),
            conditional_utility_mse=float(e["conditional"][0]),
            blind_utility_mse=float(e["blind"][0]),
            conditional_risk_brier=float(e["conditional"][1]),
            blind_risk_brier=float(e["blind"][1]),
            prior_utility_mse=float(pe[0]),
            prior_risk_brier=float(pe[1]),
            action_utility_skill=_skill(e["conditional"][0], e["blind"][0]),
            prior_utility_skill=_skill(e["conditional"][0], pe[0]),
            prior_risk_skill=_skill(e["conditional"][1], pe[1]),
        )
    groups = sorted(set(data["group"].tolist()))
    sums = []
    for group in groups:
        mask = data["group"] == group
        w = data["weight"][mask]
        sums.append(
            [
                float(np.sum((prediction[mode][mask, 0] - data["targets"][mask, 0]) ** 2 * w))
                for mode in ("conditional", "blind")
            ]
        )
    values = [
        _skill(sum(sums[i][0] for i in indices), sum(sums[i][1] for i in indices))
        for indices in itertools.product(range(4), repeat=4)
    ]
    lo, hi = np.quantile(values, [0.025, 0.975])
    passed = (
        all(
            v["action_utility_skill"] >= 0.01
            and v["prior_utility_skill"] >= 0.01
            and v["prior_risk_skill"] >= 0
            for v in out.values()
        )
        and lo > 0
    )
    return dict(
        metrics=out,
        physical_group_action_skill_ci95=[float(lo), float(hi)],
        exact_physical_group_resamples=256,
        source_groups=groups,
        prospective_forecast_replication_passed=bool(passed),
    )


def _report(cfg, rows, derived, models, train):
    data = data_from(cfg, derived)
    metrics = evaluate(data, models, train)
    return dict(
        abi=ABI,
        criteria=CRITERIA,
        credit=hold.CREDIT,
        role="validation",
        actual_native_peers=24,
        rows=len(data["cap"]),
        requests=int(data["weight"].sum()),
        candidate=cfg["candidate"],
        evaluation=metrics,
        all_missed_zero_and_target_censored_cohorts_retained=True,
        original_complete_episode_native_metrics=rows,
        role_disjoint_prospective_forecast_validation=True,
        not_representative_content=True,
        source_content_limit=cfg["source_content_limit"],
        model_fits_during_validation=0,
        actual_native_learned_steps=0,
        selected_action_calibration=False,
        actual_models=6,
        implementation_sha256=digest(__file__),
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def run_validation(config, out):
    cfg = read_json(config)
    runtimes = validate_plan(cfg)
    models = forecast.load_forecasts(cfg["candidate"]["path"])
    training = read_json(Path(cfg["candidate"]["path"]) / "report.json")["training_source"]
    _, train = forecast.training_source(training)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "protocol.json", cfg)
    rows = []
    derived = {}
    try:
        for film, p in runtimes.items():
            root = out / film
            root.mkdir()
            write_json(root / "runtime.json", p)
            bundles = {k: hold.base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
            for trial in p["episodes"]:
                child = root / trial["id"]
                print(f"validation {len(rows) + 1}/24 {film}/{trial['id']}", flush=True)
                with (root / (trial["id"] + ".log")).open("x") as log:
                    subprocess.run(
                        [
                            "node",
                            str(asset_directory() / "late_validation_episode.mjs"),
                            str(child),
                            str(root / "runtime.json"),
                            trial["id"],
                            trial["condition"],
                        ],
                        timeout=120,
                        check=True,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                require(
                    (child / "panel_snapshot.json").read_bytes() == (root / "runtime.json").read_bytes(),
                    "actual validation runtime differs",
                )
                row, d = audit_peer(child, p, trial, bundles)
                write_json(child / "derived.json", d)
                rows.append(row)
                derived[(film, trial["id"])] = d
        require(
            len(rows) == 24
            and all(a["cutoff_epoch_ms"] < b["start_epoch_ms"] for a, b in zip(rows, rows[1:]))
            and Path(config).stat().st_mtime * 1000 < rows[0]["start_epoch_ms"]
            and (Path(cfg["candidate"]["path"]) / "manifest.json").stat().st_mtime * 1000
            < rows[0]["start_epoch_ms"],
            "complete ordered validation captured after fixed config required",
        )
        validate_plan(cfg)
        report = _report(cfg, rows, derived, models, train)
        write_json(out / "report.json", report)
        np.savez_compressed(out / "validation_rows.npz", **data_from(cfg, derived))
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


def audit_validation(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    cfg = read_json(out / "protocol.json")
    runtimes = validate_plan(cfg)
    models = forecast.load_forecasts(cfg["candidate"]["path"])
    training = read_json(Path(cfg["candidate"]["path"]) / "report.json")["training_source"]
    _, train = forecast.training_source(training)
    rows = []
    derived = {}
    for film, p in runtimes.items():
        root = out / film
        require(read_json(root / "runtime.json") == p, "actual validation runtime changed")
        bundles = {k: hold.base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
        for trial in p["episodes"]:
            child = root / trial["id"]
            require(
                (child / "panel_snapshot.json").read_bytes() == (root / "runtime.json").read_bytes(),
                "raw validation runtime differs",
            )
            row, d = audit_peer(child, p, trial, bundles)
            require(
                d == read_json(child / "derived.json"),
                "every actual validation native/frame/cohort/sidecar record differs",
            )
            rows.append(row)
            derived[(film, trial["id"])] = d
    report = _report(cfg, rows, derived, models, train)
    require(
        report == read_json(out / "report.json"),
        "actual frozen-model validation errors/priors/CI/flags differ",
    )
    data = data_from(cfg, derived)
    with np.load(out / "validation_rows.npz", allow_pickle=False) as cache:
        require(
            set(cache.files) == set(data) and all(np.array_equal(cache[k], v) for k, v in data.items()),
            "actual factual validation cache changed",
        )
    require(
        len(rows) == 24
        and all(a["cutoff_epoch_ms"] < b["start_epoch_ms"] for a, b in zip(rows, rows[1:]))
        and (out / "protocol.json").stat().st_mtime * 1000 < rows[0]["start_epoch_ms"]
        and (Path(cfg["candidate"]["path"]) / "manifest.json").stat().st_mtime * 1000
        < rows[0]["start_epoch_ms"],
        "predeclared complete ordered validation required",
    )
    return dict(
        read_only=True,
        actual_peers=24,
        actual_forecasters=6,
        complete_original_native_sources_replayed=True,
        all_factual_rows_and_saved_predictions_recomputed=True,
        prospective_forecast_replication_passed=report["evaluation"][
            "prospective_forecast_replication_passed"
        ],
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_late_validation")
    sub = p.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--candidate", required=True)
    plan.add_argument("--template-sintel", required=True)
    plan.add_argument(
        "--template-tos", required=True, help="common-shadow engine template only; ToS footage is not reused"
    )
    plan.add_argument(
        "--replacement-catalog", required=True, help="new wholly held-out licensed BBB video catalog"
    )
    plan.add_argument("--out", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = p.parse_args()
    if a.command == "plan":
        c = plan_validation(a.candidate, a.template_sintel, a.template_tos, a.replacement_catalog, a.out)
        result = dict(abi=ABI, actual_peers_planned=24, role=c["role"], SOTA_achieved=False)
    elif a.command == "run":
        r = run_validation(a.config, a.out)
        result = dict(
            rows=r["rows"],
            requests=r["requests"],
            evaluation=r["evaluation"],
            native_deployment_qualified=False,
            SOTA_achieved=False,
        )
    else:
        result = audit_validation(a.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
