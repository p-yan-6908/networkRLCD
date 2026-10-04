"""Fresh train-only longer random holds and late factual credit, never qualification."""

import argparse
import copy
import json
import subprocess
from pathlib import Path
from types import FunctionType

from . import native_action_excitation as base
from . import native_encoder_response as encoder
from .native_action_excitation_control import assignment
from .native_action_learning import reconstruct_states
from .native_protocol import (
    asset_directory,
    digest,
    finite,
    read_json,
    require,
    seal_directory,
    verify_seal,
    write_json,
)

ABI = "native_late_credit_randomized_hold_v2"
EPOCH_STEPS = 32
START_MS = 1800
END_MS = 2200
CREDIT = {
    **copy.deepcopy(base.CREDIT),
    "abi": ABI,
    "epoch_steps": EPOCH_STEPS,
    "cohort_start_after_ack_ms": START_MS,
    "cohort_end_after_ack_ms": END_MS,
    "actual_target_threshold_is_not_an_eligibility_gate": True,
    "late_window_is_not_guarantee_of_settled_target_or_quality": True,
}
REFERENCE = {
    **copy.deepcopy(CREDIT),
    "abi": ABI + "_early_reference",
    "cohort_start_after_ack_ms": 200,
    "cohort_end_after_ack_ms": 600,
}
RECIPE = {**copy.deepcopy(base.RECIPE), "abi": ABI + "_measurement", "credit": CREDIT}


def settled_cap(behavior, step, seed, features):
    require(
        type(step) is int
        and 0 <= step <= EPOCH_STEPS * 512
        and len(features) == 16
        and all(finite(v) and v >= 0 for v in features)
        and features[9] in (0, 1),
        "bounded causal 32-step random hold required",
    )
    return assignment(behavior, step // EPOCH_STEPS, seed)


RAW_AUDIT = FunctionType(
    base._RAW_AUDIT.__code__,
    {**base._RAW_AUDIT.__globals__, "exploration_cap": settled_cap, "RECIPE": RECIPE},
    "audit_late_hold_raw",
)


def _cohort_function(start, stop, credit):
    return FunctionType(
        base.build_cohorts.__code__,
        {
            **base.build_cohorts.__globals__,
            "EPOCH_STEPS": EPOCH_STEPS,
            "COHORT_START_MS": start,
            "COHORT_END_MS": stop,
            "CREDIT": credit,
            "exploration_cap": settled_cap,
        },
        "build_late_hold_cohorts",
    )


build_late_cohorts = _cohort_function(START_MS, END_MS, CREDIT)
build_reference_cohorts = _cohort_function(200, 600, REFERENCE)


def project_collector(text):
    anchors = (
        (
            "import {captureEncoderResponse} from '/encoder_response.mjs';",
            "import {settledHoldCap} from '/settled_hold_control.mjs';\nimport {captureEncoderResponse} from '/encoder_response.mjs';",
        ),
        (
            "explorationCap(nativeConfig.behavior,decisions.length,nativeConfig.exploration_seed,observation)",
            "settledHoldCap(nativeConfig.behavior,decisions.length,nativeConfig.exploration_seed,observation)",
        ),
        ("const moduleRoutes=new Set([", "const moduleRoutes=new Set(['/settled_hold_control.mjs',"),
    )
    for old, new in anchors:
        require(text.count(old) == 1, "exact late-hold-only collector projection anchor required")
        text = text.replace(old, new)
    return text


def _original(entry):
    root = Path(entry["runtime"]).resolve().parent
    require(
        digest(root / "manifest.json") == entry["manifest_sha256"]
        and digest(root / "runtime.json") == entry["runtime_sha256"],
        "original training captures changed",
    )
    verify_seal(root, base.PARENT_SEAL)
    p = read_json(root / "runtime.json")
    require(
        p["stage"] == "train"
        and p["repair_model"] is None
        and p["learner"] is None
        and len(p["episodes"]) == 24
        and base.compatible_engines(p),
        "complete original training-only physical/source protocol required",
    )
    return p


def plan_settled_hold(runtime, out):
    runtime = Path(runtime).resolve()
    entry = dict(
        runtime=str(runtime),
        manifest_sha256=digest(runtime.parent / "manifest.json"),
        runtime_sha256=digest(runtime),
    )
    p = _original(entry)
    assets = asset_directory()
    require(
        (assets / "settled_hold_episode.mjs").read_text()
        == project_collector((assets / "encoder_response_episode.mjs").read_text()),
        "exact late random-hold producer required",
    )
    prerequisite = runtime.parent.parent / "native-encoder-long-hold-response-v1"
    verify_seal(prerequisite, "native_encoder_long_hold_response_v1_complete")
    cfg = dict(
        abi=ABI,
        credit=CREDIT,
        early_reference=REFERENCE,
        role="train",
        parent=entry,
        trials=[{**t, "id": "late-" + t["id"]} for t in p["episodes"]],
        implementation_sha256=digest(__file__),
        source_sha256={
            "assets/" + n: digest(assets / n)
            for n in (
                "encoder_response.mjs",
                "encoder_response_episode.mjs",
                "settled_hold_control.mjs",
                "settled_hold_episode.mjs",
            )
        },
        timing_prerequisite_path=str(prerequisite),
        timing_prerequisite_manifest_sha256=digest(prerequisite / "manifest.json"),
        existing_physical_groups_reused_not_independent=True,
        encoder_target_qp_not_actor_inputs=True,
        no_target_or_quality_based_cohort_selection=True,
        models_fitted=0,
        SOTA_achieved=False,
    )
    write_json(out, cfg)
    return cfg


def validate_config(cfg):
    require(
        cfg["abi"] == ABI
        and cfg["credit"] == CREDIT
        and cfg["early_reference"] == REFERENCE
        and cfg["role"] == "train"
        and cfg["models_fitted"] == 0
        and cfg["SOTA_achieved"] is False
        and all(
            cfg[k] is True
            for k in (
                "existing_physical_groups_reused_not_independent",
                "encoder_target_qp_not_actor_inputs",
                "no_target_or_quality_based_cohort_selection",
            )
        ),
        "fixed late-credit scope/role required",
    )
    require(digest(__file__) == cfg["implementation_sha256"], "late credit collector module changed")
    p = copy.deepcopy(_original(cfg["parent"]))
    require(
        cfg["trials"] == [{**t, "id": "late-" + t["id"]} for t in p["episodes"]],
        "full prospective 24-trial role/group/order plan required",
    )
    assets = asset_directory()
    require(
        set(cfg["source_sha256"])
        == {
            "assets/" + n
            for n in (
                "encoder_response.mjs",
                "encoder_response_episode.mjs",
                "settled_hold_control.mjs",
                "settled_hold_episode.mjs",
            )
        }
        and all(digest(assets / k.split("/")[1]) == v for k, v in cfg["source_sha256"].items()),
        "late collector/sidecar/control sources changed",
    )
    require(
        (assets / "settled_hold_episode.mjs").read_text()
        == project_collector((assets / "encoder_response_episode.mjs").read_text()),
        "exact full producer projection required",
    )
    require(
        digest(Path(cfg["timing_prerequisite_path"]) / "manifest.json")
        == cfg["timing_prerequisite_manifest_sha256"],
        "timing-mechanism prerequisite changed",
    )
    p["episodes"] = cfg["trials"]
    p["measurement_recipe"] = RECIPE
    p["late_random_hold_training_v2"] = True
    p["extra_source_sha256"].update(cfg["source_sha256"])
    return p


def audit_peer(child, p, trial, bundles):
    child = Path(child)
    require(
        digest(child / "source_snapshot.mjs") == p["extra_source_sha256"]["assets/settled_hold_episode.mjs"],
        "actual late-hold producer changed",
    )
    row, derived = RAW_AUDIT(child, p, trial, bundles, None)
    sender = read_json(child / "sender_observations.json")
    frames = read_json(child / "frame_events.json")
    states = reconstruct_states(sender, frames)
    labels = derived["quality"]["source_labels"]
    late = build_late_cohorts(sender, labels, states, trial)
    early = build_reference_cohorts(sender, labels, states, trial)
    telemetry = encoder.summarize_encoder_sidecars(sender, frames)
    # Preserve every quality cohort regardless of target attainment or encoder/QP support.
    for c in late["cohorts"]:
        samples = [
            d["encoder_response"]["fields"]["targetBitrate"]["value"]
            for d in sender["decisions"]
            if c["window_start_ms"] <= d["observation"]["sample_ms"] < c["window_end_ms"]
        ]
        present = [v for v in samples if v is not None]
        c["observed_target_samples"] = len(present)
        c["target_at_least_90pct_cap_fraction"] = (
            sum(v >= 0.9 * c["cap"] for v in present) / len(present) if present else None
        )
        c["target_status_not_used_to_filter"] = True
    derived.update(late_credit=late, early_reference=early, encoder_sidecar=telemetry)
    row["late_credit"] = {
        k: late[k] for k in ("completed_epochs", "requests", "action_changed_epochs", "cap_counts")
    }
    return row, derived


def _report(rows, derived):
    randomized = [
        d["late_credit"] for r, d in zip(rows, derived, strict=True) if r["condition"] != "fixed450"
    ]
    cohorts = [c for d in randomized for c in d["cohorts"]]
    n = len(cohorts)
    counts = {str(c): sum(x["cap"] == c for x in cohorts) for c in base.CAPS}
    changes = sum(x["cap"] != x["previous_cap"] for x in cohorts)
    target = [
        x["target_at_least_90pct_cap_fraction"]
        for x in cohorts
        if x["target_at_least_90pct_cap_fraction"] is not None
    ]
    return dict(
        abi=ABI,
        credit=CREDIT,
        early_reference=REFERENCE,
        actual_native_peers=len(rows),
        randomized_cohorts=n,
        randomized_requests=sum(c["weight"] for c in cohorts),
        randomized_cap_counts=counts,
        factual_action_change_fraction=changes / max(1, n),
        seeded_support_established=bool(n and all(counts.values())),
        cohorts_with_observed_target=len(target),
        cohorts_below_90pct_target=sum(x < 1 for x in target),
        target_attainment_is_not_eligibility=True,
        all_quality_cohorts_retained=True,
        models_fitted=0,
        original_credit_labels_or_actor_or_calibration_changed=False,
        independent_validation=False,
        causal_quality_effect_proven=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def run_settled_hold(config, out):
    cfg = read_json(config)
    p = validate_config(cfg)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "protocol.json", cfg)
    write_json(out / "runtime.json", p)
    bundles = {k: base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    rows = []
    deriveds = []
    try:
        for i, trial in enumerate(cfg["trials"]):
            child = out / trial["id"]
            print(f"late-credit {i + 1}/24 {trial['id']}", flush=True)
            with (out / (trial["id"] + ".log")).open("x") as log:
                subprocess.run(
                    [
                        "node",
                        str(asset_directory() / "settled_hold_episode.mjs"),
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
            row, derived = audit_peer(child, p, trial, bundles)
            require(
                (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
                "actual runtime differs",
            )
            write_json(child / "derived.json", derived)
            rows.append(row)
            deriveds.append(derived)
        require(
            len(rows) == 24
            and all(rows[i]["cutoff_epoch_ms"] < rows[i + 1]["start_epoch_ms"] for i in range(23)),
            "complete prospective nonoverlapping 24-peer panel required",
        )
        validate_config(cfg)
        report = _report(rows, deriveds)
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


def audit_settled_hold(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    cfg = read_json(out / "protocol.json")
    p = validate_config(cfg)
    require(p == read_json(out / "runtime.json"), "frozen late-credit runtime differs")
    bundles = {k: base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    rows = []
    deriveds = []
    for trial in cfg["trials"]:
        child = out / trial["id"]
        require(
            (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
            "actual late runtime snapshot differs",
        )
        row, derived = audit_peer(child, p, trial, bundles)
        require(
            derived == read_json(child / "derived.json"),
            "full native/late-credit/reference/sidecar replay differs",
        )
        rows.append(row)
        deriveds.append(derived)
    require(
        rows == read_json(out / "native_rows.json")
        and all(rows[i]["cutoff_epoch_ms"] < rows[i + 1]["start_epoch_ms"] for i in range(23)),
        "complete native rows/clocks differ",
    )
    r = _report(rows, deriveds)
    require(r == read_json(out / "report.json"), "late-credit panel report differs")
    return dict(
        read_only=True,
        full_original_native_raw_and_credit_replay=True,
        actual_peers=24,
        cohorts=r["randomized_cohorts"],
        requests=r["randomized_requests"],
        no_target_based_filtering=True,
        original_credit_reference_retained=True,
        SOTA_achieved=False,
    )


def main():
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_action_settled_hold")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--base-runtime", required=True)
    plan.add_argument("--out", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--run", required=True)
    a = parser.parse_args()
    if a.command == "plan":
        r = plan_settled_hold(a.base_runtime, a.out)
        result = dict(peers=24, credit=r["credit"], SOTA_achieved=False)
    elif a.command == "run":
        result = run_settled_hold(a.config, a.out)
    else:
        result = audit_settled_hold(a.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
