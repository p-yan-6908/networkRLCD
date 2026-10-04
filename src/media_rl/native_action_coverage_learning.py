"""Explicit legal-role augmentation fitting interface; no legacy loader relaxation.

Factual exact-cap peers supplement their own sealed V5 train/calibration parents.
They share physical groups with those parents. Diagnostic/selected/held-out labels
never become fitting data, and normalization/network weights remain train-only.
"""

from collections import defaultdict
from pathlib import Path

import numpy as np

from .native_action_coverage import SOURCE_KIND, audit_coverage, extra_sources
from .native_action_coverage_control import COVERAGE_CAPS
from .native_action_learning import (
    LEARNER,
    calibrate_cells,
    fit_outcomes,
    held_out_training_check,
    load_role,
    physical_group,
    reconstruct_states,
)
from .native_action_policy import (
    CANDIDATES,
    CONFIG,
    CONTEXTS,
    MODEL_ABI,
    causal_context,
    predict_members,
    validate_bundle,
)
from .native_protocol import digest, read_json, require, write_json
from .native_repair3_policy import FEATURES
from .native_repair5_study import video_overlap

FITTING_ABI = "legal_factual_exact_cap_augmentation_v1"


def _capture_signatures(roots):
    signatures = set()
    for root in roots:
        for trial in read_json(root / "runtime.json")["episodes"]:
            child = root / trial["id"]
            signature = (digest(child / "sender_observations.json"), digest(child / "frame_events.json"))
            require(signature not in signatures, "copied factual capture aliases cannot add support")
            signatures.add(signature)
    return signatures


def load_augmented_role(roots, role):
    require(role in ("train", "calibration"), "diagnostic/selected/validation/test labels cannot fit")
    roots = [Path(p).resolve() for p in roots]
    require(roots and len(set(roots)) == len(roots), "unique fitting parents required")
    protocols = [read_json(p / "protocol.json") for p in roots]
    require(
        all(
            p.get("stage") == role and p.get("source_kind") in ("recorded_video_repair_v5", SOURCE_KIND)
            for p in protocols
        ),
        "only original legal V5 plus declared exact-cap augmentation roles accepted",
    )
    original = [
        r for r, p in zip(roots, protocols, strict=True) if p["source_kind"] == "recorded_video_repair_v5"
    ]
    coverage = [r for r, p in zip(roots, protocols, strict=True) if p["source_kind"] == SOURCE_KIND]
    require(original and coverage, "both sealed original roles and their explicit augmentation required")
    rows, base_protocols, original = load_role(original, role)
    signatures = _capture_signatures(original)
    base = {str(r.resolve()): digest(r / "manifest.json") for r in original}
    augmented = []
    for root in coverage:
        p = read_json(root / "protocol.json")
        require(
            base.get(str(Path(p["augmentation_parent"]["path"]).resolve()))
            == p["augmentation_parent"]["manifest_sha256"],
            "coverage must augment an included identical legal parent",
        )
        audit_coverage(root)
        namespace = digest(root / "manifest.json")
        for trial in read_json(root / "runtime.json")["episodes"]:
            child = root / trial["id"]
            signature = (digest(child / "sender_observations.json"), digest(child / "frame_events.json"))
            require(signature not in signatures, "copied factual capture aliases cannot add support")
            signatures.add(signature)
            sender = read_json(child / "sender_observations.json")
            states = reconstruct_states(sender, read_json(child / "frame_events.json"))
            labels_by_step = defaultdict(list)
            for label in read_json(child / "derived.json")["quality"]["source_labels"]:
                if not label["action_transition_inflight"] and label["decision_id"] is not None:
                    labels_by_step[label["decision_id"]].append(label)
            for decision in sender["decisions"]:
                step = decision["step_id"]
                labels = labels_by_step[step]
                if not labels:
                    continue
                cap = decision["actuation_readback"]["encoder_max_bitrate_bps"]
                require(
                    cap in COVERAGE_CAPS
                    and all(
                        label["encoder_cap_bps"] == cap and label["capture_request_ms"] >= decision["ack_ms"]
                        for label in labels
                    ),
                    "actual acknowledged exact-cap factual association required",
                )
                augmented.append(
                    dict(
                        state=states[step],
                        cap=cap,
                        utility=float(
                            np.mean([label["ontime_sampled_psnr_contribution"] for label in labels])
                        )
                        / 100,
                        miss=float(np.mean([not label["identifiable_ontime"] for label in labels])),
                        weight=len(labels),
                        episode=namespace + "/" + trial["id"],
                        group=physical_group(p, trial),
                        context=causal_context(states[step]),
                        step=step,
                    )
                )
    require(
        augmented and {r["cap"] for r in augmented} == set(COVERAGE_CAPS),
        "all new exact-cap factual labels required",
    )
    require(
        {r["group"] for r in augmented} <= {r["group"] for r in rows},
        "augmentation cannot manufacture independent physical groups",
    )
    rows += augmented
    require(len({(r["episode"], r["step"]) for r in rows}) == len(rows), "duplicate factual steps forbidden")
    return (
        rows,
        protocols,
        roots,
        dict(
            original_parents=len(original),
            augmentation_parents=len(coverage),
            new_exact_cap_rows=len(augmented),
            physical_groups_before=len({r["group"] for r in rows if r["cap"] not in COVERAGE_CAPS}),
            physical_groups_after=len({r["group"] for r in rows}),
            original_measurement_recipe=base_protocols[0]["measurement_recipe"],
        ),
    )


def train_coverage_model(train_runs, calibration_runs, out):
    out = Path(out)
    require(not out.exists() and not out.is_symlink(), "immutable independent new candidate output required")
    train, tps, tr, ti = load_augmented_role(train_runs, "train")
    cal, cps, cr, ci = load_augmented_role(calibration_runs, "calibration")
    require(not set(tr) & set(cr), "distinct fitting-role parents required")
    require(
        ti["original_measurement_recipe"] == ci["original_measurement_recipe"],
        "identical frozen base native physics required",
    )
    for p in tps:
        for q in cps:
            if p["video_source"]["sha256"] == q["video_source"]["sha256"]:
                require(
                    all(
                        not video_overlap(a["video_segment"], b["video_segment"])
                        for a in p["groups"]
                        for b in q["groups"]
                    ),
                    "train/calibration physical source leakage forbidden",
                )
    for rows, ps in ((train, tps), (cal, cps)):
        require(
            len({r["group"] for r in rows}) >= 8
            and len({r["episode"] for r in rows}) >= 32
            and len({p["video_source"]["sha256"] for p in ps}) >= 2,
            "two movies/eight actual physical groups required per fitting role",
        )
        require(
            {g["family"] for p in ps for g in p["groups"]}
            == {"stable", "collapse", "variable", "brief-collapse"}
            and {r["cap"] for r in rows} == set(CANDIDATES),
            "all four families/all ten exact factual candidates required",
        )
    cv = held_out_training_check(train)
    members = []
    normalizations = []
    traces = []
    for seed in LEARNER["model_seeds"]:
        m, n, trace = fit_outcomes(train, seed, LEARNER["updates"])
        members.append(m)
        normalizations.append(n)
        traces.append(trace)
    require(
        normalizations[0] == normalizations[1] == normalizations[2],
        "train-only normalization identical across members required",
    )
    cells = calibrate_cells(members, cal)
    protocols = tps + cps
    bindings = {
        **extra_sources(),
        **{
            "python/" + n: Path(__file__).with_name(n)
            for n in (
                "native_action_policy.py",
                "native_action_learning.py",
                "native_repair3_policy.py",
                "native_repair5_policy.py",
                "native_observations.py",
                "native_protocol.py",
                "native_repair5_calibration.py",
                "networks.py",
            )
        },
    }
    bundle = dict(
        model_abi=MODEL_ABI,
        fitting_interface=FITTING_ABI,
        config=CONFIG.copy(),
        feature_names=FEATURES,
        candidates=list(CANDIDATES),
        training_roles=["train", "calibration"],
        members=members,
        cells=cells,
        training_skill_passed=cv["passed"],
        native_deployment_qualified=False,
        state_normalization=normalizations[0],
        learner=LEARNER.copy(),
        provenance={str(r / "manifest.json"): digest(r / "manifest.json") for r in tr + cr},
        source_reservations=[
            dict(sha256=sha, segment=list(segment))
            for sha, segment in sorted(
                {
                    (p["video_source"]["sha256"], tuple(g["video_segment"]))
                    for p in protocols
                    for g in p["groups"]
                }
            )
        ],
        source_sha256={k: digest(v) for k, v in bindings.items()},
        no_new_independent_groups_from_augmentation=True,
    )
    validate_bundle(bundle)
    predictions = [predict_members(bundle, r["state"]) for r in cal[:: max(1, len(cal) // 100)]]
    require(
        all(np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all() for p in predictions),
        "bounded actual fitted action outputs required",
    )
    report = dict(
        model_abi=MODEL_ABI,
        fitting_interface=FITTING_ABI,
        rows=dict(train=len(train), calibration=len(cal)),
        requests=dict(train=sum(r["weight"] for r in train), calibration=sum(r["weight"] for r in cal)),
        physical_groups=dict(
            train=len({r["group"] for r in train}), calibration=len({r["group"] for r in cal})
        ),
        augmentation=dict(train=ti, calibration=ci),
        training_cv=cv,
        fit_traces=traces,
        unsupported_new_caps=[
            cap for cap in COVERAGE_CAPS if not any(cells[f"{cap}/{ctx}"]["supported"] for ctx in CONTEXTS)
        ],
        supported_cells=sum(c["supported"] for c in cells.values()),
        minimum_supported_margins={
            ctx: min(
                (cells[f"{cap}/{ctx}"]["margin"] for cap in CANDIDATES if cells[f"{cap}/{ctx}"]["supported"]),
                default=1,
            )
            for ctx in CONTEXTS
        },
        actual_native_learned_improvement_proven=False,
        native_deployment_qualified=False,
        not_long_horizon_return_model=True,
        diagnostic_selected_validation_test_labels_used=False,
    )
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "model.json", bundle)
    write_json(out / "training_report.json", report)
    write_json(
        out / "manifest.json",
        dict(
            stage="bounded_action_candidate_fitted",
            artifacts_sha256={n: digest(out / n) for n in ("model.json", "training_report.json")},
            SOTA_achieved=False,
        ),
    )
    return report
