"""Monotonic selected-native calibration on fresh, factual, accepted source actions.

The target is factual request outcome under actual later behavior, NOT a fixed-cap
counterfactual, an episode safety certificate, or held-out performance.
"""

from copy import deepcopy
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from .native_dataset import factual_transitions
from .native_learning import validate_native_bundle
from .native_protocol import digest, read_json, require, seal_directory, write_json
from .networks import MLP, sigmoid

REWARD_FOR_LABELS = dict(on_time_sampled_psnr_divisor=100, miss_penalty=0.2, switch_penalty=0.005)


def accepted_native_samples(sender, quality, episode_id, group):
    transitions, exclusions = factual_transitions(sender, quality, episode_id, REWARD_FOR_LABELS)
    samples = []
    fallback = 0
    for t in transitions:
        row = sender["decisions"][t["step_id"]]
        selected = row["policy_decision"]
        if selected["fallback"]:
            fallback += t["label_count"]
            continue
        require(
            t["action"] == selected["action_index"]
            and row["actuation_readback"]["encoder_max_bitrate_bps"] == selected["encoder_max_bitrate_bps"],
            "calibration must use executed selected action, not a proposal",
        )
        require(
            selected["predicted_frame_miss"][t["action"]] <= 0.5
            and selected["risk_disagreement"][t["action"]] <= 0.2,
            "source accepted-action screens were not preserved",
        )
        samples.append(
            dict(
                group=group,
                episode_id=episode_id,
                step_id=t["step_id"],
                action=t["action"],
                state=t["state"].tolist(),
                miss_fraction=t["miss_fraction"],
                label_count=t["label_count"],
            )
        )
    return samples, dict(**exclusions, fallback_source_requests=fallback)


def raw_native_risk(bundle, rows):
    states = np.asarray([x["state"] for x in rows], dtype=float)
    actions = [x["action"] for x in rows]
    require(
        states.shape == (len(rows), 64)
        and np.isfinite(states).all()
        and np.all(states >= 0)
        and all(type(a) is int and 0 <= a < 7 for a in actions),
        "finite factual native states/actions required",
    )
    inputs = np.column_stack([states, np.eye(7)[actions]])
    return np.asarray([sigmoid(MLP.from_dict(w)(inputs).ravel()) for w in bundle["risk_weights"]]).mean(
        axis=0
    )


def risk_diagnostics(probability, rows):
    p = np.asarray(probability)
    y = np.asarray([x["miss_fraction"] for x in rows])
    weights = np.asarray([x["label_count"] for x in rows])
    bins = []
    for i in range(10):
        selected = np.minimum((p * 10).astype(int), 9) == i
        count = int(weights[selected].sum())
        bins.append(
            dict(
                bin=i,
                source_requests=count,
                predicted_miss=float(np.average(p[selected], weights=weights[selected])) if count else None,
                observed_miss=float(np.average(y[selected], weights=weights[selected])) if count else None,
            )
        )
    ece = (
        sum(
            b["source_requests"] * abs(b["predicted_miss"] - b["observed_miss"])
            for b in bins
            if b["source_requests"]
        )
        / weights.sum()
    )
    return dict(
        mean_predicted_miss=float(np.average(p, weights=weights)),
        observed_miss=float(np.average(y, weights=weights)),
        frame_brier=float(np.average((p - y) ** 2 + y * (1 - y), weights=weights)),
        ece=float(ece),
        reliability=bins,
        in_sample_not_selected_policy_validation=True,
    )


def fit_selected_native_calibration(bundle, rows):
    validate_native_bundle(bundle)
    require(
        rows and len({x["group"] for x in rows}) >= 2, "two independent calibration source groups required"
    )
    require(
        all(type(x["label_count"]) is int and x["label_count"] > 0 for x in rows),
        "positive factual frame counts required",
    )
    raw = raw_native_risk(bundle, rows)
    y = np.asarray([x["miss_fraction"] for x in rows], dtype=float)
    weight = np.asarray([x["label_count"] for x in rows], dtype=float)
    require(
        np.isfinite(y).all()
        and np.all((0 <= y) & (y <= 1))
        and weight.sum() >= 64
        and 0 < weight @ y < weight.sum(),
        "both outcomes and adequate factual calibration required",
    )
    x = np.column_stack(
        [np.log(np.clip(raw, 1e-6, 1 - 1e-6) / (1 - np.clip(raw, 1e-6, 1 - 1e-6))), np.ones(len(rows))]
    )
    weight /= weight.sum()

    def objective(theta):
        z = x @ theta
        pred = sigmoid(z)
        delta = theta - [1, 0]
        return (
            float(weight @ (np.logaddexp(0, z) - y * z) + 0.0005 * (delta @ delta)),
            x.T @ (weight * (pred - y)) + 0.001 * delta,
        )

    fitted = minimize(
        objective,
        np.array([1.0, 0.0]),
        jac=True,
        bounds=[(0.001, 100), (-40, 40)],
        method="L-BFGS-B",
        options=dict(maxiter=400, ftol=1e-12, gtol=1e-9),
    )
    require(fitted.success and np.isfinite(fitted.x).all(), "native monotonic calibration fit failed")
    candidate = deepcopy(bundle)
    candidate["platt"] = fitted.x.tolist()
    validate_native_bundle(candidate)
    original = sigmoid(x @ bundle["platt"])
    recalibrated = sigmoid(x @ fitted.x)
    report = dict(
        accepted_transitions=len(rows),
        factual_source_requests=int(sum(x["label_count"] for x in rows)),
        independent_source_groups=len({x["group"] for x in rows}),
        old_platt=bundle["platt"],
        new_platt=candidate["platt"],
        monotonic=True,
        original=risk_diagnostics(original, rows),
        fitted=risk_diagnostics(recalibrated, rows),
        actions={str(a): sum(x["label_count"] for x in rows if x["action"] == a) for a in range(7)},
        actor_risk_weights_and_cutoffs_unchanged=True,
        eventual_recalibrated_policy_distribution_not_validated=True,
        policy_improved=False,
        native_safety_certificate=False,
        SOTA_achieved=False,
    )
    return candidate, report


def recalibrate_native_study(run, out):
    from .native_study import audit_native_study

    run, out = Path(run).resolve(), Path(out).resolve()
    audit_native_study(run)
    protocol = read_json(run / "protocol.json")
    require(protocol["stage"] == "calibration", "validation/test/development labels forbidden in calibration")
    key = protocol["conditions"]["source"]["model"]
    bundle = read_json(run / "models" / (key + ".json"))
    samples, exclusions = [], {}
    for episode in read_json(run / "episodes.json"):
        child = run / episode["id"]
        sender = read_json(child / "sender_observations.json")
        quality = read_json(child / "derived.json")["quality"]
        selected, rejected = accepted_native_samples(sender, quality, episode["id"], episode["group"])
        samples.extend(selected)
        exclusions[episode["id"]] = rejected
    candidate, report = fit_selected_native_calibration(bundle, samples)
    candidate["selected_calibration"] = dict(
        abi="native_factual_selected_calibration_v1",
        source_model_sha256=protocol["models"][key]["sha256"],
        calibration_run=str(run),
        calibration_manifest_sha256=digest(run / "manifest.json"),
        source_scene_ranges=[
            [g["scene_seed"], g["scene_seed"] + g["reservation_frames"]] for g in protocol["groups"]
        ],
        target="factual complete request outcomes under actual subsequent native behavior",
        cutoffs_unchanged=True,
        held_out_policy_validation_required=True,
    )
    # Only the calibrator and explicit provenance can change, never the actor/safety screen.
    require(
        {k: v for k, v in candidate.items() if k not in ("platt", "selected_calibration")}
        == {k: v for k, v in bundle.items() if k not in ("platt", "selected_calibration")},
        "frozen native policy changed",
    )
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "model.json", candidate)
    write_json(out / "calibration_samples.json", samples)
    write_json(out / "report.json", dict(**report, excluded_labels=exclusions))
    seal_directory(
        out,
        ["model.json", "calibration_samples.json", "report.json"],
        "native_selected_calibration_fit_not_promoted",
        source_model_sha256=protocol["models"][key]["sha256"],
        calibration_manifest_sha256=digest(run / "manifest.json"),
        SOTA_achieved=False,
    )
    return report
