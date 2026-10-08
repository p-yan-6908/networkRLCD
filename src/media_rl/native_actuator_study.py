"""Fresh role-disjoint native actuator identification, no model fitting/promotion."""

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path
from types import FunctionType

import numpy as np

from . import native_action_excitation as donor
from . import native_action_late_validation as reservations
from . import native_actuator_control as control
from . import native_actuator_statistics as statistics
from .native_encoder_response import summarize_encoder_sidecars
from .native_protocol import (
    DEFAULT_LIMITS,
    SCHEDULES,
    asset_directory,
    digest,
    finite,
    read_json,
    require,
    seal_directory,
    source_identity,
    verify_seal,
    write_json,
)

ABI = "native_actuator_identification_v1"
SOURCE_KIND = "recorded_video_actuator_identification_v1"
ROLES = ("discovery", "replication")
RECIPE = {
    **copy.deepcopy(donor.RECIPE),
    "abi": ABI + "_measurement",
    "instrument_abi": control.ABI,
    "instrument_ratios": list(control.RATIOS),
    "hold_after_ack_ms": control.HOLD_MS,
    "credit_window_after_ack_ms": list(control.WINDOW_MS),
    "max_assignments": control.MAX_EPOCHS,
    "encoded_payload_meter": "native_encoded_payload_meter_v1",
    "no_response_and_non_plateau_not_excluded": True,
}


def project_collector(text):
    # Exact versioned projection. Every existing producer and controller remains immutable.
    anchors = (
        ("native_randomized_cap_hold_study_v1", ABI, 1),
        ("recorded_video_randomized_cap_hold_v1", SOURCE_KIND, 2),
        (
            "!['random-hold-a','random-hold-b','fixed450'].includes(condition.behavior)",
            "condition.behavior!=='instrument'",
            1,
        ),
        ("panel.stage!=='train'", "!['discovery','replication'].includes(panel.stage)", 1),
        ("ms>6000", "ms>6600", 1),
        ("/streamed_excitation_video.mjs", "/streamed_actuator_video.mjs", 2),
        (
            "import {captureEncoderResponse} from '/encoder_response.mjs';",
            "import {captureEncoderResponse} from '/encoder_response.mjs';\nimport {InstrumentSampler,captureLink} from '/actuator_control.mjs';\nimport {installEncodedMeter} from '/actuator_meter.mjs';",
            1,
        ),
        (
            "a=new RTCPeerConnection(),b=new RTCPeerConnection()",
            "a=new RTCPeerConnection({encodedInsertableStreams:true}),b=new RTCPeerConnection()",
            1,
        ),
        (
            "const sender=a.addTrack(stream.getVideoTracks()[0],stream);",
            "const sender=a.addTrack(stream.getVideoTracks()[0],stream);\nconst encodedMeter=installEncodedMeter(sender),instrument=new InstrumentSampler(nativeConfig.exploration_seed);",
            1,
        ),
        (
            "observation.content_features=contentEncoder.snapshot(observation.sample_ms);",
            "observation.content_features=contentEncoder.snapshot(observation.sample_ms);const instrumentStart=performance.now(),encoded_snapshot=encodedMeter.snapshot(observation.sample_ms),instrument_link=captureLink(stats,observation.raw_source),actuator_assignment=await instrument.observe(observation,encoder_response,encoded_snapshot,instrument_link),instrument_compute_ms=performance.now()-instrumentStart;",
            1,
        ),
        (
            "explorationCap(nativeConfig.behavior,decisions.length,nativeConfig.exploration_seed,observation)",
            "(actuator_assignment?.requested_bps??300000)",
            1,
        ),
        (
            "const total_inference_ms=performance.now()-commonStart;",
            "const total_inference_ms=performance.now()-commonStart+instrument_compute_ms;",
            1,
        ),
        (
            "if(changed)repairActor.acknowledge(actual.encoder_max_bitrate_bps,ack_ms);",
            "if(changed)repairActor.acknowledge(actual.encoder_max_bitrate_bps,ack_ms);instrument.acknowledge(ack_ms,actual.encoder_max_bitrate_bps);",
            1,
        ),
        (
            "step_id,observation,encoder_response,",
            "step_id,observation,encoder_response,encoded_snapshot,instrument_link,actuator_assignment,instrument_compute_ms,",
            1,
        ),
        (
            "const senderEvidence={encoder_recipe:encoderRecipe,",
            "const senderEvidence={encoded_meter:encodedMeter.evidence(measurementStart,cutoff),encoder_recipe:encoderRecipe,",
            1,
        ),
        (
            "const moduleRoutes=new Set([",
            "const moduleRoutes=new Set(['/actuator_control.mjs','/actuator_meter.mjs',",
            1,
        ),
    )
    for old, new, count in anchors:
        require(text.count(old) == count, "exact immutable actuator projection anchor changed: " + old)
        text = text.replace(old, new)
    return text


def extra_sources():
    result = {k: v for k, v in donor.extra_sources().items() if k != "assets/dense_episode.mjs"}
    result.update(
        {
            "python/" + name: Path(__file__).with_name(name)
            for name in (
                "native_actuator_control.py",
                "native_actuator_statistics.py",
                "native_actuator_study.py",
            )
        }
    )
    result.update(
        {
            "assets/" + name: asset_directory() / name
            for name in (
                "encoder_response.mjs",
                "encoder_response_episode.mjs",
                "streamed_actuator_video.mjs",
                "actuator_control.mjs",
                "actuator_meter.mjs",
                "actuator_episode.mjs",
            )
        }
    )
    return result


def _runtime(template, catalog, role, groups):
    p = copy.deepcopy(template)
    model = template["conditions"]["random-hold-a"]["model"]
    p.update(
        panel_abi=ABI,
        source_kind=SOURCE_KIND,
        stage=role,
        video_source=catalog,
        groups=groups,
        repetitions=1,
        measurement_recipe=RECIPE,
        conditions={"instrument": dict(controller="explore", behavior="instrument", model=model)},
        repair_model=None,
        learner=None,
        SOTA_achieved=False,
        common_shadow_inference=True,
        controller_config=donor.CONFIG,
        limits=DEFAULT_LIMITS,
        extra_source_sha256={k: digest(v) for k, v in extra_sources().items()},
        source_sha256=source_identity(),
        learned_controller_promoted=False,
    )
    p["episodes"] = donor.dense.trial_schedule(p)
    for trial in p["episodes"]:
        group = next(g for g in groups if g["id"] == trial["group"])
        trial["exploration_seed"] = group["instrument_seed"]
        trial["block_id"] = group["block_id"]
    return p


def plan_study(settings_path, out):
    settings = read_json(settings_path)
    require(
        settings["abi"] == ABI and type(settings["seed"]) is int and 0 <= settings["seed"] <= 2**32 - 1,
        "versioned prospective settings/seed required",
    )
    require(
        type(settings["contexts_per_film"]) is int
        and 1 <= settings["contexts_per_film"] <= 8
        and type(settings["iv_assumptions_explicitly_assumed"]) is bool,
        "bounded prospective contexts and explicit IV assumption choice",
    )
    out = Path(out).resolve()
    require(not out.exists(), "prospective plan directory must be fresh")
    template_path = Path(settings["template"]).resolve()
    template = read_json(template_path)
    require(
        donor.compatible_engines(template)
        and template["repair_model"] is None
        and template["learner"] is None,
        "unchanged no-learned-actor template required; never reuse its outcomes",
    )
    verify_seal(template_path.parent, donor.PARENT_SEAL)
    excluded, inputs = reservations.reservations(settings["reservation_root"])
    catalogs = []
    for path in settings["catalogs"]:
        catalog = donor.dense.validate_catalog(read_json(path))
        catalog["path"] = str(Path(catalog["path"]).resolve())
        require(digest(catalog["path"]) == catalog["sha256"], "licensed recorded video changed")
        catalogs.append(catalog)
    require(
        len(catalogs) in (1, 2) and len({c["sha256"] for c in catalogs}) == len(catalogs),
        "one or two distinct licensed sources",
    )
    used, runtimes = [], {}
    group_index = 0
    for role in ROLES:
        for film, catalog in enumerate(catalogs):
            groups = []
            for index in range(settings["contexts_per_film"]):
                start = next(
                    (
                        s
                        for s in range(60000, catalog["duration_ms"] - 19999, 20000)
                        if all(
                            e["sha256"] != catalog["sha256"]
                            or not donor.dense.video_overlap([s, s + 20000], e["segment"])
                            for e in [*excluded, *used]
                        )
                    ),
                    None,
                )
                require(start is not None, "fresh discovery/replication content reservations exhausted")
                segment = [start, start + 20000]
                used.append(dict(sha256=catalog["sha256"], segment=segment))
                family = ("stable", "collapse")[index % 2]
                schedule = [
                    [cap, label, 6000 if label != "recovery" else 6600] for cap, label, _ in SCHEDULES[family]
                ]
                block = f"{catalog['sha256'][:12]}-{start}-{start + 20000}"
                seed = int.from_bytes(
                    hashlib.sha256(f"{settings['seed']}:{block}".encode()).digest()[:4], "big"
                )
                groups.append(
                    dict(
                        id=f"{role}-f{film}-{family}-{index}",
                        family=family,
                        scene_seed=group_index * 2000,
                        video_segment=segment,
                        reservation_frames=1000,
                        schedule=schedule,
                        orders=[["instrument"]],
                        block_id=block,
                        instrument_seed=seed,
                    )
                )
                group_index += 1
            runtimes[f"{role}-f{film}"] = _runtime(template, catalog, role, groups)
    cfg = dict(
        abi=ABI,
        settings=copy.deepcopy(settings),
        template=dict(path=str(template_path), sha256=digest(template_path)),
        excluded_video_ranges=excluded,
        excluded_inputs_sha256=inputs,
        runtimes=runtimes,
        criteria=statistics.CRITERIA,
        recipe=RECIPE,
        policy_models_fitted=0,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )
    validate_plan(cfg)
    out.mkdir()
    write_json(out / "protocol.json", cfg)
    seal_directory(out, ["protocol.json"], ABI + "_plan", policy_models_fitted=0, SOTA_achieved=False)
    return cfg


def validate_plan(cfg):
    require(
        cfg["abi"] == ABI
        and cfg["criteria"] == statistics.CRITERIA
        and cfg["recipe"] == RECIPE
        and cfg["policy_models_fitted"] == 0
        and cfg["native_deployment_qualified"] is False
        and cfg["SOTA_achieved"] is False,
        "fixed diagnostic-only criteria/scope required",
    )
    require(digest(cfg["template"]["path"]) == cfg["template"]["sha256"], "catalog/shadow donor changed")
    exclusions = []
    for path, sha in cfg["excluded_inputs_sha256"].items():
        require(digest(path) == sha, "frozen all-role reservation changed")
        obj = read_json(path)
        for p in [obj, *obj.get("runtimes", {}).values()]:
            if "video_source" in p and "groups" in p:
                exclusions.extend(
                    dict(sha256=p["video_source"]["sha256"], segment=g["video_segment"]) for g in p["groups"]
                )
    require(exclusions == cfg["excluded_video_ranges"], "complete all-role source exclusions required")
    require(
        (asset_directory() / "actuator_episode.mjs").read_text()
        == project_collector((asset_directory() / "encoder_response_episode.mjs").read_text()),
        "exact observer/instrument-only collector projection required",
    )
    used = []
    for p in cfg["runtimes"].values():
        require(
            p["stage"] in ROLES
            and p["panel_abi"] == ABI
            and p["source_kind"] == SOURCE_KIND
            and p["repair_model"] is None
            and p["learner"] is None
            and p["measurement_recipe"] == RECIPE
            and p["limits"] == DEFAULT_LIMITS
            and p["controller_config"] == donor.CONFIG
            and p["source_sha256"] == source_identity()
            and p["extra_source_sha256"] == {k: digest(v) for k, v in extra_sources().items()},
            "frozen diagnostic runtime/source mismatch",
        )
        expected = _runtime(read_json(cfg["template"]["path"]), p["video_source"], p["stage"], p["groups"])
        require(p == expected, "exact projected runtime differs")
        require(digest(p["video_source"]["path"]) == p["video_source"]["sha256"], "movie binding changed")
        for g in p["groups"]:
            segment = g["video_segment"]
            require(
                g["orders"] == [["instrument"]] and segment[1] - segment[0] == 20000,
                "one randomized three-arm peer per fresh physical content block",
            )
            require(
                all(
                    e["sha256"] != p["video_source"]["sha256"]
                    or not donor.dense.video_overlap(segment, e["segment"])
                    for e in [*cfg["excluded_video_ranges"], *used]
                ),
                "content/role/source reservation overlap",
            )
            used.append(dict(sha256=p["video_source"]["sha256"], segment=segment))
    require({p["stage"] for p in cfg["runtimes"].values()} == set(ROLES), "both independent roles required")
    return cfg


def _meter(sender):
    meter = sender["encoded_meter"]
    require(
        meter["abi"] == "native_encoded_payload_meter_v1"
        and meter["owner"] == "unique_owned_video_sender"
        and meter["pass_through_no_frame_mutation"] is True
        and meter["error"] is None
        and meter["unit"] == "encoded_video_payload_bytes_before_RTP_packetization"
        and meter["measurement_start_ms"] == sender["measurement_start_ms"]
        and meter["measurement_cutoff_ms"] == sender["measurement_cutoff_ms"]
        and meter["started_ms"] <= meter["measurement_start_ms"]
        and (meter["ended_ms"] is None or meter["ended_ms"] >= meter["measurement_cutoff_ms"]),
        "actual encoded output observer must cover entire factual capture",
    )
    count = total = 0
    last = meter["started_ms"]
    for event in meter["events"]:
        require(
            finite(event["at_ms"])
            and last <= event["at_ms"] <= meter["measurement_cutoff_ms"]
            and type(event["byte_length"]) is int
            and event["byte_length"] >= 0,
            "encoded event clock/byte size invalid",
        )
        count += 1
        total += event["byte_length"]
        require(
            event["total_bytes"] == total and event["total_frames"] == count,
            "encoded cumulative bytes/frames do not replay",
        )
        last = event["at_ms"]
    return meter


def replay_assignments(sender, trial):
    meter = _meter(sender)
    sampler = control.InstrumentSampler(trial["exploration_seed"])
    caps, assignments = [], []
    events = meter["events"]
    index = total = count = 0
    for row in sender["decisions"]:
        now = row["observation"]["sample_ms"]
        while index < len(events) and events[index]["at_ms"] <= now:
            total = events[index]["total_bytes"]
            count = events[index]["total_frames"]
            index += 1
        snapshot = dict(
            abi=meter["abi"], status="active", sample_ms=now, total_bytes=total, total_frames=count
        )
        require(row["encoded_snapshot"] == snapshot, "encoded snapshot contains future or substituted bytes")
        assignment = sampler.observe(
            row["observation"], row["encoder_response"], snapshot, row["instrument_link"]
        )
        donor.dense._close(row["actuator_assignment"], assignment)
        cap = 300000 if assignment is None else assignment["requested_bps"]
        caps.append(cap)
        if assignment is not None and (not assignments or assignments[-1]["epoch"] != assignment["epoch"]):
            assignments.append(dict(assignment, ack_ms=row["ack_ms"], first_step_id=row["step_id"]))
        sampler.acknowledge(row["ack_ms"], row["actuation_readback"]["encoder_max_bitrate_bps"])
        require(
            finite(row["instrument_compute_ms"])
            and 0 <= row["instrument_compute_ms"] <= row["total_inference_ms"],
            "instrument compute unaccounted",
        )
    return caps, assignments


def _send_window(decisions, start, stop):
    amount = coverage = 0.0
    for left, right in zip(decisions, decisions[1:], strict=False):
        a, b = left["observation"], right["observation"]
        dt = b["sample_ms"] - a["sample_ms"]
        overlap = max(0, min(stop, b["sample_ms"]) - max(start, a["sample_ms"]))
        before, after = a["raw_source"]["bytes_sent"], b["raw_source"]["bytes_sent"]
        if (
            overlap
            and 0 < dt <= 1000
            and a["raw_source"]["stream_key"] == b["raw_source"]["stream_key"]
            and finite(before)
            and finite(after)
            and after >= before
        ):
            amount += (after - before) * overlap / dt
            coverage += overlap
    return amount * 8000 / (stop - start) if coverage >= 0.95 * (stop - start) else None


def build_cohorts(sender, frames, quality, trial):
    _, assignments = replay_assignments(sender, trial)
    labels = quality["source_labels"]
    cohorts = []
    events = sender["encoded_meter"]["events"]
    for index, a in enumerate(assignments):
        start, stop = [a["ack_ms"] + ms for ms in control.WINDOW_MS]
        next_assignment = (
            assignments[index + 1]["assignment_ms"]
            if index + 1 < len(assignments)
            else frames["measurement_cutoff_ms"]
        )
        deadline_stop = stop + control.DEADLINE_MS
        reason = None
        if deadline_stop > min(frames["measurement_cutoff_ms"], next_assignment):
            reason = "window_or_deadline_crosses_cutoff_or_next_assignment"
        cohort = [s for s in labels if start <= s["capture_request_ms"] < stop]
        send = _send_window(sender["decisions"], start, stop)
        if not cohort:
            reason = reason or "no_factual_source_opportunities"
        if send is None:
            reason = reason or "RTP_counter_clock_coverage"
        if a["ack_ms"] - a["assignment_ms"] > control.DEADLINE_MS:
            reason = reason or "actuation_ack_deadline"
        output = [e for e in events if start <= e["at_ms"] < stop]
        encoded = sum(e["byte_length"] for e in output) * 8000 / (stop - start)
        bins = [
            sum(e["byte_length"] for e in output if start + n * 200 <= e["at_ms"] < start + (n + 1) * 200)
            * 40
            for n in range(4)
        ]
        mean = float(np.mean(bins))
        plateau = mean > 0 and max(bins) - min(bins) <= 0.4 * mean
        rows = [r for r in sender["decisions"] if start <= r["observation"]["sample_ms"] < stop]
        targets = [r["encoder_response"]["fields"]["targetBitrate"]["value"] for r in rows]
        targets = [v for v in targets if finite(v)]
        cohorts.append(
            dict(
                **a,
                block_id=trial["block_id"],
                role=trial["role"],
                trial_id=trial["id"],
                complete=reason is None,
                censor_reason=reason,
                window_ms=[start, stop],
                encoder_bps=encoded if reason is None else None,
                send_bps=send if reason is None else None,
                target_bps_mean=float(np.mean(targets)) if targets else None,
                response_bins_bps=bins,
                plateau_observed=plateau,
                non_plateau_is_not_exclusion=True,
                eligible=len(cohort),
                utility=float(np.mean([s["ontime_sampled_psnr_contribution"] for s in cohort]))
                if cohort and reason is None
                else None,
                ontime_fraction=float(np.mean([s["identifiable_ontime"] for s in cohort]))
                if cohort and reason is None
                else None,
                source_ids=[s["source_id"] for s in cohort],
                encoded_rate_unit="actual_encoded_payload_output_before_RTP_not_target",
                send_rate_method="raw_RTP_payload_counter_intervals_proportional_boundary_overlap_includes_retransmissions",
                only_factual_outcome=True,
            )
        )
    return cohorts


def audit_peer(root, p, trial):
    root = Path(root)
    sender = read_json(root / "sender_observations.json")
    caps, _ = replay_assignments(sender, trial)

    # Isolated closure: shared legacy auditor globals are never mutated.
    def replay_cap(behavior, step, seed, features):
        require(
            behavior == "instrument" and seed == trial["exploration_seed"], "wrong instrument replay identity"
        )
        return caps[step]

    audit = FunctionType(
        donor.dense.audit_dense_episode.__code__,
        {
            **donor.dense.audit_dense_episode.__globals__,
            "STUDY_ABI": ABI,
            "RECIPE": RECIPE,
            "exploration_cap": replay_cap,
        },
        "audit_actuator_raw",
    )
    bundles = {k: donor.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    row, derived = audit(root, p, trial, bundles, None)
    require(
        digest(root / "source_snapshot.mjs") == p["extra_source_sha256"]["assets/actuator_episode.mjs"],
        "actual instrument producer changed",
    )
    summarize_encoder_sidecars(sender, read_json(root / "frame_events.json"))
    cohorts = build_cohorts(sender, read_json(root / "frame_events.json"), derived["quality"], trial)
    return row, derived, cohorts


def run_study(protocol_path, out):
    verify_seal(Path(protocol_path).resolve().parent, ABI + "_plan")
    cfg = validate_plan(read_json(protocol_path))
    out = Path(out).resolve()
    require(not out.exists(), "native capture directory must be fresh; failed prefixes are never overwritten")
    out.mkdir()
    write_json(out / "protocol.json", cfg)
    cohorts, episode_hashes = [], {}
    try:
        for key, p in cfg["runtimes"].items():
            runtime = out / (key + ".json")
            write_json(runtime, p)
            for trial in p["episodes"]:
                root = out / trial["id"]
                subprocess.run(
                    [
                        "node",
                        str(asset_directory() / "actuator_episode.mjs"),
                        str(root),
                        str(runtime),
                        trial["id"],
                        "instrument",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                row, derived, child = audit_peer(root, p, trial)
                write_json(root / "native_row.json", row)
                write_json(root / "native_derived.json", derived)
                write_json(root / "cohorts.json", child)
                seal_directory(
                    root,
                    sorted(str(f.relative_to(root)) for f in root.rglob("*") if f.is_file()),
                    ABI + "_peer_verified",
                    role=trial["role"],
                    policy_models_fitted=0,
                    SOTA_achieved=False,
                )
                episode_hashes[trial["id"]] = digest(root / "manifest.json")
                cohorts.extend(child)
        report = statistics.analyze_cohorts(cohorts, cfg["settings"]["iv_assumptions_explicitly_assumed"])
        write_json(out / "cohorts.json", cohorts)
        write_json(out / "report.json", report)
        seal_directory(
            out,
            sorted(str(f.relative_to(out)) for f in out.rglob("*") if f.is_file()),
            ABI + "_complete",
            episodes=episode_hashes,
            policy_models_fitted=0,
            SOTA_achieved=False,
        )
        return report
    except Exception as error:
        write_json(
            out / "failure.json",
            dict(
                abi=ABI + "_failed_prefix",
                error=str(error),
                collector_stderr=error.stderr[-6000:]
                if isinstance(error, subprocess.CalledProcessError) and error.stderr
                else None,
                completed=episode_hashes,
                rerun_requires_fresh_path=True,
                native_deployment_qualified=False,
                SOTA_achieved=False,
            ),
        )
        raise


def audit_study(root):
    root = Path(root).resolve()
    seal = verify_seal(root, ABI + "_complete")
    cfg = validate_plan(read_json(root / "protocol.json"))
    cohorts = []
    expected_ids = {t["id"] for p in cfg["runtimes"].values() for t in p["episodes"]}
    require(set(seal["episodes"]) == expected_ids, "complete prospective native peer inventory required")
    for key, p in cfg["runtimes"].items():
        require(read_json(root / (key + ".json")) == p, "runtime snapshot changed")
        for trial in p["episodes"]:
            child = root / trial["id"]
            verify_seal(child, ABI + "_peer_verified")
            require(
                digest(child / "manifest.json") == seal["episodes"][trial["id"]], "child peer binding changed"
            )
            row, derived, rows = audit_peer(child, p, trial)
            require(
                row == read_json(child / "native_row.json")
                and derived == read_json(child / "native_derived.json")
                and rows == read_json(child / "cohorts.json"),
                "full original raw replay/cohort mismatch",
            )
            cohorts.extend(rows)
    report = statistics.analyze_cohorts(cohorts, cfg["settings"]["iv_assumptions_explicitly_assumed"])
    require(
        cohorts == read_json(root / "cohorts.json") and report == read_json(root / "report.json"),
        "physical study report does not replay exactly",
    )
    return dict(
        read_only=True,
        original_native_raw_replay=True,
        actual_encoded_payload_observer=True,
        peers=len(expected_ids),
        cohorts=len(cohorts),
        stage1_qualified=report["stage1"]["qualified"],
        policy_models_fitted=0,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    plan = subs.add_parser("plan")
    plan.add_argument("--config", required=True)
    plan.add_argument("--out", required=True)
    run = subs.add_parser("run")
    run.add_argument("--protocol", required=True)
    run.add_argument("--out", required=True)
    audit = subs.add_parser("audit")
    audit.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    if args.command == "plan":
        cfg = plan_study(args.config, args.out)
        result = dict(
            protocol=str(Path(args.out).resolve() / "protocol.json"),
            peers=sum(len(p["episodes"]) for p in cfg["runtimes"].values()),
            policy_models_fitted=0,
        )
    elif args.command == "run":
        result = run_study(args.protocol, args.out)
    else:
        result = audit_study(args.root)
    print(json.dumps(result, sort_keys=True))
