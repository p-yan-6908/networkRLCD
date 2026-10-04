"""Fresh train-only randomized cap holds with future-action-free factual credit.

Reuse owned original training reservations, not calibration/diagnostic labels or
new independence. Entire original Dense raw verifier is rebound into an isolated
namespace. Existing files/globals/weights/defaults/measurements are unchanged.
Only experimental cap assignments differ; no controller efficacy is claimed.
"""

import argparse
import copy
import json
from pathlib import Path
from types import CodeType, FunctionType

import numpy as np

from . import native_action_coverage as coverage
from . import native_dense_study as dense
from .native_action_excitation_control import (
    ABI,
    BEHAVIORS,
    CAPS,
    COHORT_END_MS,
    COHORT_START_MS,
    CONFIG,
    DEADLINE_MS,
    EPOCH_STEPS,
    exploration_cap,
)
from .native_action_learning import reconstruct_states
from .native_protocol import asset_directory, digest, finite, read_json, require
from .native_repair3_policy import INPUT_DIM

STUDY_ABI = "native_randomized_cap_hold_study_v1"
SOURCE_KIND = "recorded_video_randomized_cap_hold_v1"
PARENT_SEAL = "native_randomized_cap_hold_complete"
CHILD_SEAL = "native_randomized_cap_hold_episode_verified"
CREDIT = dict(
    abi=ABI,
    epoch_steps=EPOCH_STEPS,
    caps_bps=list(CAPS),
    cohort_start_after_ack_ms=COHORT_START_MS,
    cohort_end_after_ack_ms=COHORT_END_MS,
    request_deadline_ms=DEADLINE_MS,
    future_action_before_last_deadline_forbidden=True,
    target="mean_factual_request_utility_and_miss_within_held_action",
    schedule="counter_uint32_mixer_seed_epoch_only; aliases_share_schedule",
    assigned_max_bitrate_is_not_proof_of_encoder_target_response=True,
)
RECIPE = {
    **copy.deepcopy(coverage.RECIPE),
    "abi": "native_randomized_cap_hold_measurement_v1",
    "risk_architecture": "no_learned_actor_randomized_hold_exploration",
    "fallback": "preregistered_random_cap_hold_not_learned",
    "credit": CREDIT,
}
PROJECTION = (
    (
        "// Independent legal-role augmentation: fixed scalar coverage is not a learned policy.",
        "// Independent training-only randomized cap holds; never learned or qualified control.",
        1,
    ),
    ("native_exact_cap_coverage_v1", STUDY_ABI, 1),
    ("['fixed400','fixed450','fixed500']", "['random-hold-a','random-hold-b','fixed450']", 1),
    ("!['train','calibration'].includes(panel.stage)", "panel.stage!=='train'", 1),
    ("recorded_video_exact_cap_coverage_v1", SOURCE_KIND, 2),
    ("'/coverage_control.mjs'", "'/excitation_control.mjs'", 2),
    ("'/streamed_coverage_video.mjs'", "'/streamed_excitation_video.mjs'", 2),
)


def project_collector(text):
    for old, new, count in PROJECTION:
        require(text.count(old) == count, "frozen hold-collector projection anchor changed")
        text = text.replace(old, new)
    return text


def extra_sources():
    return {
        **coverage.extra_sources(),
        **{
            "python/" + name: Path(__file__).with_name(name)
            for name in (
                "native_action_excitation.py",
                "native_action_excitation_control.py",
                "native_action_learning.py",
            )
        },
        **{
            "assets/" + name: asset_directory() / name
            for name in ("excitation_control.mjs", "excitation_episode.mjs", "streamed_excitation_video.mjs")
        },
    }


def _train_parent(entry):
    root, p = coverage._parent(entry)
    require(p["stage"] == "train", "only original sealed training parents may supply hold exploration")
    return root, p


def validate_excitation(p):
    require(p.get("stage") == "train", "randomized hold collection is train-only")
    return _VALIDATE(p)


def compatible_engines(p):
    return _COMPATIBLE(p)


def build_cohorts(sender, labels, states, trial):
    decisions = sender["decisions"]
    require(
        decisions
        and len(states) == len(decisions)
        and [d["step_id"] for d in decisions] == list(range(len(decisions)))
        and all(len(s) == INPUT_DIM and np.isfinite(s).all() for s in states),
        "complete causal epoch states/ordered decision IDs required",
    )
    require(
        len({label["source_id"] for label in labels}) == len(labels), "unique factual source labels required"
    )
    cohorts, dropped = [], []
    for first in range(0, len(decisions), EPOCH_STEPS):
        d = decisions[first]
        end = min(first + EPOCH_STEPS, len(decisions))
        cap = exploration_cap(
            trial["condition"], first, trial["exploration_seed"], d["observation"]["features"]
        )
        require(
            all(
                row["actuation_readback"]["encoder_max_bitrate_bps"] == cap
                and row["proposed_action"]["encoder_max_bitrate_bps"] == cap
                for row in decisions[first:end]
            ),
            "randomized hold action/readback changed within epoch",
        )
        require(
            all(
                finite(row["ack_ms"]) and row["ack_ms"] >= row["observation"]["sample_ms"]
                for row in decisions[first:end]
            ),
            "causal acknowledged epoch action required",
        )
        ack = d["ack_ms"]
        start, stop = ack + COHORT_START_MS, ack + COHORT_END_MS
        boundary = (
            decisions[end]["observation"]["sample_ms"]
            if end < len(decisions)
            else sender["measurement_cutoff_ms"]
        )
        if stop + DEADLINE_MS > boundary:
            dropped.append(
                dict(epoch=first // EPOCH_STEPS, reason="future_action_or_cutoff_before_last_deadline")
            )
            continue
        candidate = [label for label in labels if start <= label["capture_request_ms"] < stop]
        require(
            all(
                label["encoder_cap_bps"] == cap
                and type(label["decision_id"]) is int
                and first <= label["decision_id"] < end
                and label["capture_request_ms"] >= decisions[label["decision_id"]]["ack_ms"]
                for label in candidate
            ),
            "cohort source/decision/action attribution changed",
        )
        keep = [label for label in candidate if not label["action_transition_inflight"]]
        if not keep:
            dropped.append(dict(epoch=first // EPOCH_STEPS, reason="no_attributable_factual_requests"))
            continue
        require(
            all(
                type(label["identifiable_ontime"]) is bool
                and finite(label["ontime_sampled_psnr_contribution"])
                and 0 <= label["ontime_sampled_psnr_contribution"] <= 100
                for label in keep
            ),
            "original bounded utility/deadline outcomes required",
        )
        cohorts.append(
            dict(
                epoch=first // EPOCH_STEPS,
                step=first,
                state=states[first],
                cap=cap,
                previous_cap=round(d["observation"]["features"][7] * 4e6),
                observation_ms=d["observation"]["sample_ms"],
                ack_ms=ack,
                window_start_ms=start,
                window_end_ms=stop,
                last_request_deadline_before_ms=stop + DEADLINE_MS,
                next_action_observation_or_cutoff_ms=boundary,
                utility=float(np.mean([label["ontime_sampled_psnr_contribution"] for label in keep])) / 100,
                miss=float(np.mean([not label["identifiable_ontime"] for label in keep])),
                weight=len(keep),
                source_ids=[label["source_id"] for label in keep],
                excluded_inflight_requests=len(candidate) - len(keep),
                role="train",
                episode=trial["id"],
                counterfactual_labels_used=False,
                future_actions_mixed=False,
            )
        )
    ids = [sid for c in cohorts for sid in c["source_ids"]]
    require(len(ids) == len(set(ids)), "overlapping randomized credit cohorts cannot reuse request labels")
    return dict(
        credit=copy.deepcopy(CREDIT),
        cohorts=cohorts,
        dropped=dropped,
        completed_epochs=len(cohorts),
        requests=sum(c["weight"] for c in cohorts),
        action_changed_epochs=sum(c["cap"] != c["previous_cap"] for c in cohorts),
        cap_counts={str(cap): sum(c["cap"] == cap for c in cohorts) for cap in CAPS},
        actual_executed_learned_steps=0,
        causal_effect_proven=False,
        native_improvement_proven=False,
    )


_RAW_AUDIT = FunctionType(
    dense.audit_dense_episode.__code__,
    {
        **dense.audit_dense_episode.__globals__,
        "STUDY_ABI": STUDY_ABI,
        "RECIPE": RECIPE,
        "exploration_cap": exploration_cap,
    },
    "audit_randomized_hold_raw",
)


def audit_excitation_episode(root, p, trial, bundles):
    require(
        p["panel_abi"] == STUDY_ABI
        and p["stage"] == "train"
        and p["repair_model"] is None
        and p["conditions"][trial["condition"]]["behavior"] in BEHAVIORS,
        "train-only exploratory hold trial required",
    )
    require(
        digest(Path(root) / "source_snapshot.mjs")
        == p["extra_source_sha256"]["assets/excitation_episode.mjs"],
        "actual randomized hold collector changed",
    )
    row, derived = _RAW_AUDIT(root, p, trial, bundles, None)
    sender = read_json(Path(root) / "sender_observations.json")
    frames = read_json(Path(root) / "frame_events.json")
    credit = build_cohorts(
        sender, derived["quality"]["source_labels"], reconstruct_states(sender, frames), trial
    )
    derived["excitation"] = credit
    row["excitation"] = {
        key: credit[key] for key in ("completed_epochs", "requests", "action_changed_epochs", "cap_counts")
    }
    return row, derived


def _report(rows, p):
    result = _BASE_REPORT(rows, p)
    random = [r["excitation"] for r in rows if r["condition"] != "fixed450"]
    n = sum(r["completed_epochs"] for r in random)
    changes = sum(r["action_changed_epochs"] for r in random)
    counts = {str(cap): sum(r["cap_counts"][str(cap)] for r in random) for cap in CAPS}
    result.update(
        credit=copy.deepcopy(CREDIT),
        randomized_cohorts=n,
        randomized_requests=sum(r["requests"] for r in random),
        randomized_cap_counts=counts,
        factual_action_change_fraction=changes / max(1, n),
        excitation_observed=bool(n and changes / max(1, n) >= 0.4 and all(counts.values())),
        training_data_not_model_qualification=True,
        candidate_or_risk_models_fitted=False,
        future_action_mixtures_used=False,
        SOTA_achieved=False,
    )
    return result


# Name-only constant rewrites for unchanged complete plan/run/audit mechanics.
# The raw verifier above retains its EXACT original code object.
_NAMES = {
    "coverage_episode.mjs": "excitation_episode.mjs",
    "dense_episode.mjs": "coverage_episode.mjs",
    "templates/dense_episode.mjs": "templates/coverage_episode.mjs",
    "coverage_caps": "excitation_caps",
}


def _code(code):
    return code.replace(
        co_consts=tuple(
            _code(c) if isinstance(c, CodeType) else _NAMES.get(c, c) if isinstance(c, str) else c
            for c in code.co_consts
        )
    )


_CONTEXT = {
    **coverage.__dict__,
    "__file__": __file__,
    "STUDY_ABI": STUDY_ABI,
    "SOURCE_KIND": SOURCE_KIND,
    "PARENT_SEAL": PARENT_SEAL,
    "CHILD_SEAL": CHILD_SEAL,
    "COVERAGE_CAPS": CAPS,
    "BEHAVIORS": BEHAVIORS,
    "RECIPE": RECIPE,
    "CONFIG": CONFIG,
    "extra_sources": extra_sources,
    "project_collector": project_collector,
    "_parent": _train_parent,
    "validate_coverage": validate_excitation,
    "compatible_engines": compatible_engines,
    "audit_coverage_episode": audit_excitation_episode,
    "_report": _report,
    "exploration_cap": exploration_cap,
}


def _clone(function):
    clone = FunctionType(
        _code(function.__code__),
        _CONTEXT,
        function.__name__ + "_hold",
        function.__defaults__,
        function.__closure__,
    )
    clone.__kwdefaults__ = copy.deepcopy(function.__kwdefaults__)
    return clone


_VALIDATE = _clone(coverage.validate_coverage)
_COMPATIBLE = _clone(coverage.compatible_engines)
_BASE_REPORT = _clone(coverage._report)
plan_excitation = _clone(coverage.plan_coverage)
run_excitation = _clone(coverage.run_coverage)
audit_excitation = _clone(coverage.audit_coverage)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_action_excitation")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser(
        "plan", help="fresh training-only randomized action holds using original training reservations"
    )
    plan.add_argument("--parent", required=True)
    plan.add_argument("--out", required=True)
    plan.add_argument("--seed", type=int, default=8101)
    plan.add_argument("--repetitions", type=int, default=2)
    study = sub.add_parser("study")
    study.add_argument("--config", required=True)
    study.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    if args.command == "plan":
        p = plan_excitation(args.parent, args.out, repetitions=args.repetitions, seed=args.seed)
        result = dict(
            config=str(args.out),
            role=p["stage"],
            peers=len(coverage.trial_schedule(p)),
            original_training_groups_reused=True,
            SOTA_achieved=False,
        )
    elif args.command == "study":
        result = run_excitation(args.config, args.out)
    else:
        result = audit_excitation(args.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
