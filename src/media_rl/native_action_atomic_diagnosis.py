"""Read-only exact fixed train-model diagnosis; never fit, capture or use validation."""

import argparse
import json
from pathlib import Path

import numpy as np

from . import native_action_atomic_portable_audit as portable
from . import native_action_atomic_value_cv as value
from . import native_action_ordered_projection as ordered
from .native_protocol import digest, read_json, require, seal_directory, verify_seal, write_json
from .networks import sigmoid

ABI = "native_atomic_balanced_train_mechanism_diagnosis_v1"
CV_MANIFEST = "7b9c9d2ca80ed97ed81dced89dbb4e009b4640a788a3a36dbc57632625c3a36c"
SOURCE_MANIFEST = "25cd60b661c0f1a0fa26f71b876ae7299ebcd1de2c49f63e10cd8321b06b5a28"
CONTRACT = dict(
    abi=ABI,
    role="diagnostic",
    input_role="train",
    exact_cv_manifest=CV_MANIFEST,
    exact_source_manifest=SOURCE_MANIFEST,
    forecasters=12,
    rows=280,
    requests=3400,
    physical_groups=12,
    diagnostics=[
        "OOF_error_contributions_by_film_and_physical_group",
        "new_balanced_same_cap_alias_variability",
        "matched_group_epoch_high_low_descriptive_contrasts",
        "per_saved_model_fit_held_bias_dead_units_proposal_span_and_shared_head_gradients",
        "group_uniform_sampling_vs_request_weighted_evaluation_mixture",
        "mathematical_temporal_ambiguity_and_opt_in_ordered_projection",
    ],
    gradient_measure="large_batch_group_uniform_request_weighted_population_surrogate; not exact finite_batch expected ratio or stationarity certificate",
    z_diagnostic_threshold=3,
    no_new_fits_or_captures=True,
    no_validation_calibration_diagnostic_test_labels=True,
    no_target_attainment_eligibility=True,
    causal_effect_or_failure_cause_established=False,
    native_deployment_qualified=False,
    SOTA_achieved=False,
)


def load_train(cv):
    cv = Path(cv).resolve()
    require(digest(cv / "manifest.json") == CV_MANIFEST, "exact fixed legal train CV source required")
    verify_seal(cv, value.ABI + "_complete")
    report = read_json(cv / "report.json")
    source = Path(report["source"]["path"])
    require(digest(source / "manifest.json") == SOURCE_MANIFEST, "exact fresh balanced train source required")
    verify_seal(source, portable.ABI + "_complete")
    cfg = read_json(source / "protocol.json")
    portable.validate_plan(cfg)
    require(
        report["no_validation_labels_used"] is True
        and report["training_development_only"] is True
        and report["no_original_models_refitted"] is True,
        "only exact train-development inputs required",
    )
    with np.load(cv / "train_rows.npz", allow_pickle=False) as z:
        data = {k: z[k].copy() for k in z.files}
    require(
        data["state"].shape == (280, 736)
        and data["targets"].shape == (280, 2)
        and int(data["weight"].sum()) == 3400
        and len(set(data["group"].tolist())) == 12
        and data["new_balanced"].sum() == 120
        and len(set(data["episode"].tolist())) == 56,
        "exact complete factual train geometry/identities required",
    )
    models = {
        fold: {
            mode: [
                read_json(cv / "models" / f"fold-{fold}-{mode}-seed-{seed}.json")
                for seed in value.RECIPE["model_seeds"]
            ]
            for mode in ("conditional", "blind")
        }
        for fold in range(2)
    }
    evaluation, oof, prior = value._NS["evaluate"](data, cfg["physical_fold_map"], models)
    require(evaluation == report["evaluation"], "actual fixed numeric evaluation differs")
    with np.load(cv / "held_predictions.npz", allow_pickle=False) as z:
        require(
            set(z.files) == {"conditional", "blind", "prior"}
            and all(np.array_equal(z[k], v) for k, v in {**oof, "prior": prior}.items()),
            "every actual saved prediction differs",
        )
    metadata = {}
    for film, p in cfg["runtimes"].items():
        for t in p["episodes"]:
            if t["condition"] == "fixed450":
                continue
            cohorts = read_json(source / film / t["id"] / "derived.json")["late_credit"]["cohorts"]
            for c in cohorts:
                require(
                    c["role"] == "train"
                    and not c["future_actions_mixed"]
                    and not c["counterfactual_labels_used"]
                    and c["target_status_not_used_to_filter"] is True,
                    "actual factual train-only unfiltered cohort required",
                )
                key = (SOURCE_MANIFEST + ":" + t["id"], c["step"])
                require(key not in metadata, "duplicate canonical native cohort")
                metadata[key] = c
    for i in np.flatnonzero(data["new_balanced"]):
        c = metadata[(str(data["episode"][i]), int(data["step"][i]))]
        require(
            c["state"] == data["state"][i].tolist()
            and c["cap"] == int(data["cap"][i])
            and c["weight"] == int(data["weight"][i])
            and [c["utility"], c["miss"]] == data["targets"][i].tolist(),
            "actual native cohort linkage/state/cap/target/weight differs",
        )
    require(len(metadata) == 120, "complete 120 native cohort metadata required")
    return data, cfg, models, oof, prior, metadata


def group_population_weights(weight, group):
    sizes = {g: int((group == g).sum()) for g in set(group.tolist())}
    q = np.asarray([w / sizes[g] for w, g in zip(weight, group, strict=True)], dtype=float)
    return q / q.sum()


def shared_gradients(x, weights, target, q):
    w, b, v, c = map(np.asarray, weights)
    h = np.maximum(x @ w + b, 0)
    p = sigmoid(h @ v + c)
    du = 2 * (p[:, 0] - target[:, 0]) * p[:, 0] * (1 - p[:, 0]) * q
    dr = (p[:, 1] - target[:, 1]) * q
    gu = x.T @ ((du[:, None] * v[:, 0]) * (h > 0))
    gr = x.T @ ((dr[:, None] * v[:, 1]) * (h > 0))
    nu, nr = np.linalg.norm(gu), np.linalg.norm(gr)
    return dict(
        utility_shared_gradient_l2=float(nu),
        risk_shared_gradient_l2=float(nr),
        risk_to_utility_shared_gradient_norm_ratio=float(nr / nu) if nu else None,
        shared_gradient_cosine=float(np.sum(gu * gr) / (nu * nr)) if nu and nr else None,
    )


def model_diagnostics(data, cfg, models):
    result = []
    design = value.base.frozen.development.neural.design
    for fold in range(2):
        held = np.asarray([cfg["physical_fold_map"][g] == fold for g in data["group"]])
        fit = ~held
        for mode, members in models[fold].items():
            for m in members:
                raw = design(data["state"], data["cap"], m["blind"])
                x = (raw - m["normalization"]["mean"]) / m["normalization"]["scale"]
                w, b, v, c = map(np.asarray, m["weights"])
                h = np.maximum(x @ w + b, 0)
                p = sigmoid(h @ v + c)
                q = group_population_weights(data["weight"][fit], data["group"][fit])
                potential = np.column_stack(
                    [
                        value.PREDICT(m, data["state"][held], np.full(held.sum(), cap, dtype=np.int64))[:, 0]
                        for cap in (300000, 450000, 900000)
                    ]
                )
                trace = m["fit_trace"][-3:]
                losses = [t["utility_mse"] + t["miss_log_loss"] + 0.005 * t["weight_l2"] for t in trace]
                result.append(
                    dict(
                        fold=fold,
                        mode=mode,
                        seed=m["seed"],
                        fit_utility_mse=float(
                            np.average(
                                (p[fit, 0] - data["targets"][fit, 0]) ** 2, weights=data["weight"][fit]
                            )
                        ),
                        held_utility_mse=float(
                            np.average(
                                (p[held, 0] - data["targets"][held, 0]) ** 2, weights=data["weight"][held]
                            )
                        ),
                        held_utility_bias=float(
                            np.average(p[held, 0] - data["targets"][held, 0], weights=data["weight"][held])
                        ),
                        fit_dead_hidden_units=int(np.all(h[fit] == 0, axis=0).sum()),
                        held_dead_hidden_units=int(np.all(h[held] == 0, axis=0).sum()),
                        held_compact_abs_z_gt3_fraction=float((np.abs(x[held, :92]) > 3).mean()),
                        held_model_proposed_utility_span_mean=float(
                            np.average(np.ptp(potential, axis=1), weights=data["weight"][held])
                        ),
                        held_model_high_low_proposed_utility_mean=float(
                            np.average(potential[:, -1] - potential[:, 0], weights=data["weight"][held])
                        ),
                        model_proposals_not_observed_counterfactuals=True,
                        last_three_full_row_request_weighted_objectives=losses,
                        loss_tail_relative_improvement=float((losses[0] - losses[-1]) / losses[0]),
                        **shared_gradients(x[fit], m["weights"], data["targets"][fit], q),
                    )
                )
    return result


def error_contributions(data, oof):
    w = data["weight"]
    y = data["targets"][:, 0]
    delta = w * ((oof["conditional"][:, 0] - y) ** 2 - (oof["blind"][:, 0] - y) ** 2)
    total = float(delta.sum())
    rows = []
    for kind, values in (("film", data["film"]), ("physical_group", data["group"])):
        for val in sorted(set(values.tolist())):
            mask = values == val
            part = float(delta[mask].sum())
            rows.append(
                dict(
                    kind=kind,
                    key=val,
                    rows=int(mask.sum()),
                    requests=int(w[mask].sum()),
                    weighted_conditional_minus_blind_utility_SSE=part,
                    fraction_of_signed_total_SSE_gap=part / total if total else None,
                    not_causal_attribution=True,
                )
            )
    return dict(total_weighted_conditional_minus_blind_utility_SSE=total, strata=rows)


def alias_support(data, oof, metadata):
    new = data["new_balanced"]
    pairs = []
    strata = []
    groups = []
    response = []
    for g in sorted(set(data["group"][new].tolist())):
        local = []
        for step in sorted(set(data["step"][new & (data["group"] == g)].tolist())):
            ix = np.flatnonzero(new & (data["group"] == g) & (data["step"] == step))
            means = {}
            for cap in (300000, 450000, 900000):
                j = ix[data["cap"][ix] == cap]
                require(
                    len(j) == 2, "exactly two actual shared-schedule aliases per cap/physical epoch required"
                )
                a, b = map(int, j)
                means[cap] = float(np.average(data["targets"][j, 0], weights=data["weight"][j]))
                pairs.append(
                    dict(
                        group=g,
                        step=int(step),
                        cap=cap,
                        observed_abs_utility_gap=float(abs(data["targets"][a, 0] - data["targets"][b, 0])),
                        OOF_conditional_abs_utility_gap=float(
                            abs(oof["conditional"][a, 0] - oof["conditional"][b, 0])
                        ),
                        OOF_blind_abs_utility_gap=float(abs(oof["blind"][a, 0] - oof["blind"][b, 0])),
                        full_history_arrays_identical=bool(
                            np.array_equal(data["state"][a], data["state"][b])
                        ),
                        same_cap_and_stratum_not_same_model_input=True,
                    )
                )
            contrast = means[900000] - means[300000]
            local.append(contrast)
            strata.append(
                dict(
                    group=g,
                    step=int(step),
                    film=str(data["film"][ix[0]]),
                    high_minus_low_utility=contrast,
                    weighted_mean_utility_by_cap={str(k): v for k, v in means.items()},
                    not_causal_effect=True,
                )
            )
        groups.append(
            dict(
                group=g,
                film=str(data["film"][ix[0]]),
                mean_high_minus_low_utility=float(np.mean(local)),
                physical_epochs=len(local),
            )
        )
        for cap in (300000, 450000, 900000):
            ix = np.flatnonzero(new & (data["group"] == g) & (data["cap"] == cap))
            c = [metadata[(str(data["episode"][i]), int(data["step"][i]))] for i in ix]
            fr = [r["target_at_least_90pct_cap_fraction"] for r in c]
            response.append(
                dict(
                    group=g,
                    cap=cap,
                    cohorts=len(c),
                    observed_target_samples=sum(r["observed_target_samples"] for r in c),
                    target_partial_cohorts=sum(f is not None and f < 1 for f in fr),
                    mean_target_at_least_90pct_cap_fraction=float(np.mean([f for f in fr if f is not None]))
                    if any(f is not None for f in fr)
                    else None,
                    all_cohorts_retained=True,
                    target_response_not_eligibility_or_direct_action_effect=True,
                )
            )
    require(
        len(pairs) == 60 and len(strata) == 20 and len(groups) == 4 and len(response) == 12,
        "complete balanced descriptive support required",
    )
    return dict(
        alias_pairs=pairs,
        actual_same_cap_alias_pairs=60,
        observed_abs_utility_gap_mean=float(np.mean([p["observed_abs_utility_gap"] for p in pairs])),
        OOF_conditional_abs_utility_gap_mean=float(
            np.mean([p["OOF_conditional_abs_utility_gap"] for p in pairs])
        ),
        OOF_blind_abs_utility_gap_mean=float(np.mean([p["OOF_blind_abs_utility_gap"] for p in pairs])),
        identical_full_history_alias_pairs=sum(p["full_history_arrays_identical"] for p in pairs),
        matched_group_epoch_strata=strata,
        physical_group_high_low=groups,
        actual_encoder_target_response=response,
        alias_dispersion_not_irreducible_noise_floor=True,
    )


def derive(cv):
    data, cfg, models, oof, prior, metadata = load_train(cv)
    del prior
    history = ordered.temporal_ambiguity_fixture()
    base = ordered.original.project_state(history)
    new = ordered.project_state(history)
    require(
        np.array_equal(base[0], base[1]) and not np.array_equal(new[0], new[1]),
        "actual old summary temporal ambiguity/new opt-in distinction required",
    )
    sampling = []
    for fold in range(2):
        fit = np.asarray([cfg["physical_fold_map"][g] != fold for g in data["group"]])
        q = group_population_weights(data["weight"][fit], data["group"][fit])
        sampling.append(
            dict(
                fold=fold,
                fit_rows=int(fit.sum()),
                fit_groups=6,
                old_rows=int((fit & ~data["new_balanced"]).sum()),
                new_rows=int((fit & data["new_balanced"]).sum()),
                request_weighted_new_mass=float(
                    data["weight"][fit & data["new_balanced"]].sum() / data["weight"][fit].sum()
                ),
                group_uniform_large_batch_request_weighted_new_mass=float(q[data["new_balanced"][fit]].sum()),
                original_group_uniform_sampler_unchanged=True,
                finite_minibatch_normalized_ratio_not_exactly_population_surrogate=True,
            )
        )
    return dict(
        abi=ABI,
        contract=CONTRACT,
        read_only=True,
        cv=dict(path=str(Path(cv).resolve()), manifest_sha256=CV_MANIFEST),
        source_manifest_sha256=SOURCE_MANIFEST,
        implementation_sha256=digest(__file__),
        ordered_projection_sha256=digest(ordered.__file__),
        models=model_diagnostics(data, cfg, models),
        error_contributions=error_contributions(data, oof),
        support_and_response=alias_support(data, oof, metadata),
        sampling_mixture=sampling,
        temporal_projection=dict(
            original_summary_dim=92,
            ordered_summary_dim=115,
            proposed_input_dim=118,
            old_fixture_summary_identical=True,
            complete_histories_different=True,
            old_two_histories_model_prediction_identical_for_every_legal_cap=True,
            ordered_packet_delay_index_slopes=ordered.temporal_trends(history)[:, 6].tolist(),
            exact_original_92_summary_prefix_preserved=True,
            actual_train_ordered_shape=list(ordered.project_state(data["state"]).shape),
            mathematical_feature_invariance_removed_only=True,
            actual_observed_collision_or_cause_of_failure_proven=False,
            performance_or_generalization_gain_proven=False,
            opt_in_no_fits_actors_defaults=True,
        ),
        no_new_fits_or_captures=True,
        no_validation_calibration_diagnostic_test_labels_read=True,
        no_quality_or_encoder_target_selection=True,
        causal_effect_or_failure_cause_established=False,
        training_action_information_passed=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def diagnose(cv, out):
    out = Path(out).resolve()
    require(not out.exists(), "immutable exact train-only diagnosis exists")
    r = derive(cv)
    out.mkdir(parents=True)
    write_json(out / "contract.json", CONTRACT)
    write_json(out / "report.json", r)
    seal_directory(out, ["contract.json", "report.json"], ABI + "_complete", SOTA_achieved=False)
    return r


def audit(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    r = read_json(out / "report.json")
    require(
        read_json(out / "contract.json") == CONTRACT and r == derive(r["cv"]["path"]),
        "actual exact train-model diagnosis differs",
    )
    return dict(
        read_only=True,
        actual_forecasters=12,
        actual_rows=280,
        actual_requests=3400,
        actual_physical_groups=12,
        actual_alias_pairs=60,
        actual_all_arm_strata=20,
        every_numeric_diagnostic_recomputed=True,
        mathematical_ordered_projection_distinction=True,
        new_fits=0,
        new_captures=0,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    p = argparse.ArgumentParser(prog="python -m media_rl.native_action_atomic_diagnosis")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("diagnose")
    d.add_argument("--cv", required=True)
    d.add_argument("--out", required=True)
    a = sub.add_parser("audit")
    a.add_argument("--run", required=True)
    args = p.parse_args()
    r = diagnose(args.cv, args.out) if args.command == "diagnose" else audit(args.run)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
