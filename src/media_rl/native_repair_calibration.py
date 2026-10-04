"""Fresh factual selected-controller calibration, never evaluation-label fitting.

Cluster residuals are empirical uncertainty guards, not pointwise risk certificates.
The final changed policy still needs prospective repeatability and validation.
"""

import shutil
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from .native_calibration import risk_diagnostics
from .native_observations import CAPS
from .native_protocol import digest, finite, read_json, require, seal_directory, write_json
from .native_repair_policy import CONFIG, INPUT_DIM, validate_repair_bundle
from .native_repair_study import audit_repair_study, video_overlap
from .networks import MLP, sigmoid

CALIBRATION_ABI = "native_repair_factual_selected_calibration_v1"
SEAL = "native_repair_selected_calibration_fit_not_promoted"
MUTABLE = {
    "platt",
    "risk_margin",
    "calibration_episodes",
    "calibration_requests",
    "source_reservations",
    "provenance",
    "selected_calibration",
}


def selected_repair_samples(run):
    run = Path(run).resolve()
    p = read_json(run / "protocol.json")
    require(
        p["stage"] == "selected-calibration",
        "evaluation/exploration labels forbidden in selected calibration",
    )
    require(
        p["conditions"] == {"source": {"controller": "repair", "model": "source"}},
        "factual selected repair controller required",
    )
    audit_repair_study(run)
    rows, excluded = [], defaultdict(int)
    for trial in read_json(run / "runtime.json")["episodes"]:
        sender = read_json(run / trial["id"] / "sender_observations.json")
        labels = read_json(run / trial["id"] / "derived.json")["quality"]["source_labels"]
        grouped = defaultdict(list)
        for label in labels:
            if label["action_transition_inflight"] or label["decision_id"] is None:
                excluded["mixed_or_unassigned_requests"] += 1
            else:
                grouped[label["decision_id"]].append(label)
        for step, decision in enumerate(sender["decisions"]):
            values = grouped[step]
            if not values:
                continue
            selected = decision["repair_decision"]
            cap = decision["actuation_readback"]["encoder_max_bitrate_bps"]
            require(
                cap == selected["encoder_max_bitrate_bps"] and CAPS.index(cap) == selected["action_index"],
                "calibration must use executed selected action",
            )
            rows.append(
                dict(
                    group=trial["group"],
                    episode_id=trial["id"],
                    step_id=step,
                    state=selected["history"],
                    action=CAPS.index(cap),
                    miss_fraction=1 - sum(x["identifiable_ontime"] for x in values) / len(values),
                    label_count=len(values),
                    learned=selected["reason"] == "learned" and not selected["fallback"],
                )
            )
    return rows, dict(excluded), p


def _raw_risk(bundle, rows):
    states = np.asarray([r["state"] for r in rows], dtype=float)
    require(
        states.shape == (len(rows), INPUT_DIM) and np.isfinite(states).all() and (states >= 0).all(),
        "finite factual temporal states required",
    )
    require(
        all(type(r["action"]) is int and 0 <= r["action"] < 7 for r in rows),
        "factual action indices required",
    )
    x = np.column_stack([states, np.eye(7)[[r["action"] for r in rows]]])
    return np.asarray([sigmoid(MLP.from_dict(w)(x).ravel()) for w in bundle["risk_weights"]]).mean(axis=0)


def _fit_monotonic(raw, y, weights):
    x = np.column_stack(
        [np.log(np.clip(raw, 1e-6, 1 - 1e-6) / (1 - np.clip(raw, 1e-6, 1 - 1e-6))), np.ones(len(raw))]
    )
    weights = weights / weights.sum()

    def objective(theta):
        z = x @ theta
        delta = theta - [1, 0]
        return float(weights @ (np.logaddexp(0, z) - y * z) + 0.0005 * (delta @ delta)), x.T @ (
            weights * (sigmoid(z) - y)
        ) + 0.001 * delta

    fitted = minimize(
        objective,
        np.array([1.0, 0.0]),
        jac=True,
        method="L-BFGS-B",
        bounds=[(0.001, 100), (-40, 40)],
        options=dict(maxiter=400, ftol=1e-12, gtol=1e-9),
    )
    require(fitted.success and np.isfinite(fitted.x).all(), "monotonic selected calibration fit failed")
    return fitted.x.tolist()


def _probability(raw, platt):
    raw = np.clip(raw, 1e-6, 1 - 1e-6)
    return sigmoid(platt[0] * np.log(raw / (1 - raw)) + platt[1])


def fit_selected_repair_calibration(bundle, rows):
    validate_repair_bundle(bundle)
    require(
        rows and len({r["group"] for r in rows}) >= 3,
        "three independent selected calibration groups required",
    )
    require(
        all(
            type(r["label_count"]) is int
            and r["label_count"] > 0
            and finite(r["miss_fraction"])
            and 0 <= r["miss_fraction"] <= 1
            for r in rows
        ),
        "valid factual request counts/outcomes required",
    )
    y = np.asarray([r["miss_fraction"] for r in rows])
    weight = np.asarray([r["label_count"] for r in rows], dtype=float)
    require(
        weight.sum() >= 64 and 0 < weight @ y < weight.sum(),
        "adequate selected requests and both outcomes required",
    )
    raw = _raw_risk(bundle, rows)
    platt = _fit_monotonic(raw, y, weight)
    groups = np.asarray([r["group"] for r in rows])
    actions = np.asarray([r["action"] for r in rows])
    held_out = np.zeros(len(rows))
    folds = []
    for group in sorted(set(groups)):
        ix = groups == group
        fitted = _fit_monotonic(raw[~ix], y[~ix], weight[~ix])
        held_out[ix] = _probability(raw[ix], fitted)
        folds.append(dict(held_out_group=str(group), fit_groups=sorted(set(groups[~ix])), platt=fitted))
    margins, episodes, requests, support = [], [], [], []
    for action in range(7):
        ix = actions == action
        action_groups = sorted(set(groups[ix]))
        ep = len({r["episode_id"] for r in rows if r["action"] == action})
        count = int(weight[ix].sum())
        supported = (
            len(action_groups) >= 3
            and ep >= CONFIG["min_calibration_episodes"]
            and count >= CONFIG["min_calibration_requests"]
        )
        residuals = [
            float(np.average((y - held_out)[j], weights=weight[j]))
            for g in action_groups
            if (j := ix & (groups == g)).any()
        ]
        # Worst cross-fitted source-group residual avoids fitting and testing a
        # calibration intercept on the same group. No i.i.d. frame-count claim.
        margin = float(np.clip(max(residuals) + 0.02, 0, 1)) if supported else 1.0
        margins.append(margin)
        episodes.append(ep)
        requests.append(count)
        support.append(
            dict(
                action=action,
                independent_groups=len(action_groups),
                episodes=ep,
                requests=count,
                supported=supported,
                held_out_group_residuals=residuals,
                margin=margin,
            )
        )
    candidate = deepcopy(bundle)
    candidate.update(
        platt=platt, risk_margin=margins, calibration_episodes=episodes, calibration_requests=requests
    )
    validate_repair_bundle(candidate)
    require(
        {k: v for k, v in candidate.items() if k not in MUTABLE}
        == {k: v for k, v in bundle.items() if k not in MUTABLE},
        "frozen actor/risk/config changed during calibration",
    )
    report = dict(
        accepted_transitions=len(rows),
        factual_requests=int(weight.sum()),
        learned_selected_requests=sum(r["label_count"] for r in rows if r.get("learned")),
        independent_groups=len(set(groups)),
        old_platt=bundle["platt"],
        new_platt=platt,
        support=support,
        leave_one_source_group_out=folds,
        original=risk_diagnostics(_probability(raw, bundle["platt"]), rows),
        fitted=risk_diagnostics(_probability(raw, platt), rows),
        cross_fitted=risk_diagnostics(held_out, rows),
        actor_risk_weights_and_controller_limits_unchanged=True,
        empirical_margins_not_pointwise_safety_guarantees=True,
        target="factual complete request outcomes under actual subsequent controller behavior, including fallback",
        recalibrated_policy_distribution_requires_fresh_validation=True,
        policy_improved=False,
        SOTA_achieved=False,
    )
    return candidate, report


def _candidate_for_run(run):
    rows, excluded, p = selected_repair_samples(run)
    bundle = read_json(Path(run) / "models/repair.json")
    require(
        digest(Path(run) / "models/repair.json") == p["repair_model"]["sha256"],
        "selected source model changed",
    )
    old = bundle.get("source_reservations", [])
    new = [dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]]
    require(
        all(
            a["sha256"] != b["sha256"] or not video_overlap(a["segment"], b["segment"])
            for a in old
            for b in new
        ),
        "selected calibration source leakage",
    )
    candidate, report = fit_selected_repair_calibration(bundle, rows)
    candidate["source_reservations"] = old + new
    candidate["provenance"] = dict(
        bundle.get("provenance", {}),
        **{str(Path(run) / "manifest.json"): digest(Path(run) / "manifest.json")},
    )
    candidate["selected_calibration"] = dict(
        abi=CALIBRATION_ABI,
        source_model_sha256=p["repair_model"]["sha256"],
        calibration_run=str(Path(run).resolve()),
        calibration_manifest_sha256=digest(Path(run) / "manifest.json"),
        implementation_sha256=digest(__file__),
        target=report["target"],
        held_out_policy_validation_required=True,
        independent_groups=report["independent_groups"],
        limits_unchanged=True,
    )
    return candidate, dict(**report, excluded_labels=excluded), rows


def recalibrate_repair_study(run, out):
    run = Path(run).resolve()
    candidate, report, rows = _candidate_for_run(run)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "model.json", candidate)
    write_json(out / "calibration_samples.json", rows)
    write_json(out / "report.json", report)
    shutil.copyfile(__file__, out / "calibration_source.py")
    seal_directory(
        out,
        ["model.json", "calibration_samples.json", "report.json", "calibration_source.py"],
        SEAL,
        SOTA_achieved=False,
    )
    return report


def verify_selected_repair_calibration(bundle):
    validate_repair_bundle(bundle)
    meta = bundle.get("selected_calibration", {})
    require(
        meta.get("abi") == CALIBRATION_ABI
        and meta.get("implementation_sha256") == digest(__file__)
        and meta.get("held_out_policy_validation_required") is True,
        "locked selected-controller calibration required before evaluation",
    )
    run = Path(meta["calibration_run"]).resolve()
    require(
        digest(run / "manifest.json") == meta["calibration_manifest_sha256"],
        "selected calibration evidence changed",
    )
    expected, _, _ = _candidate_for_run(run)
    require(bundle == expected, "selected calibrated model/provenance changed")
    return True
