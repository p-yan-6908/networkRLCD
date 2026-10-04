"""Prospective conventional encoder lag/credit probe, not learned-policy qualification."""

import argparse
import copy
import json
import statistics
import subprocess
from pathlib import Path
from types import FunctionType

from . import native_action_excitation as base
from . import native_encoder_response as encoder
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

ABI = "native_encoder_long_hold_response_v1"
HOLD_STEPS = 16
SEQUENCE = (450000, 300000, 900000, 300000, 900000, 450000, 300000, 900000, 300000, 450000, 900000, 450000)
BANDS = ((200, 600), (600, 1000), (1000, 1400))
DEADLINE_MS = 150
GEOMETRY = dict(
    hold_steps=HOLD_STEPS,
    caps_bps=[300000, 450000, 900000],
    sequence_bps=list(SEQUENCE),
    bands_after_ack_ms=[list(b) for b in BANDS],
    request_deadline_ms=DEADLINE_MS,
    directional_target_threshold_fraction=0.9,
    declared_peers=4,
    order=["fixed450", "random-hold-a", "fixed450", "random-hold-b"],
    repeated_aliases_share_exact_sequence=True,
    original_credit_band_retained=[200, 600],
    full_panels_or_model_fits_permitted=False,
    independent_validation=False,
)
RECIPE = {
    **copy.deepcopy(base.RECIPE),
    "abi": ABI + "_measurement",
    "risk_architecture": "no_learned_actor_prescribed_long_hold_probe",
    "fallback": "fixed_prescribed_conventional_not_learned",
    "credit": {
        "abi": ABI,
        "geometry": GEOMETRY,
        "counterfactual_labels_used": False,
        "future_actions_mixed": False,
        "quality_cutoffs_unchanged": True,
    },
}


def hold_cap(behavior, step, seed=None, observation=None):
    require(
        behavior in ("random-hold-a", "random-hold-b", "fixed450") and type(step) is int and step >= 0,
        "legal conventional hold behavior/step required",
    )
    return 450000 if behavior == "fixed450" else SEQUENCE[(step // HOLD_STEPS) % len(SEQUENCE)]


def project_long_collector(text):
    anchors = (
        (
            "import {captureEncoderResponse} from '/encoder_response.mjs';",
            "import {holdProbeCap} from '/encoder_hold_control.mjs';\nimport {captureEncoderResponse} from '/encoder_response.mjs';",
        ),
        (
            "explorationCap(nativeConfig.behavior,decisions.length,nativeConfig.exploration_seed,observation)",
            "holdProbeCap(nativeConfig.behavior,decisions.length)",
        ),
        ("const moduleRoutes=new Set([", "const moduleRoutes=new Set(['/encoder_hold_control.mjs',"),
    )
    for old, new in anchors:
        require(text.count(old) == 1, "exact long-hold-only projection anchor required")
        text = text.replace(old, new)
    return text


RAW_AUDIT = FunctionType(
    base._RAW_AUDIT.__code__,
    {**base._RAW_AUDIT.__globals__, "exploration_cap": hold_cap, "RECIPE": RECIPE},
    "audit_prescribed_hold_raw",
)


def summarize_response(sender, frames, labels, behavior):
    counters = encoder.summarize_encoder_sidecars(sender, frames)
    decisions = sender["decisions"]
    require(
        len({x["source_id"] for x in labels}) == len(labels), "unique original factual source labels required"
    )
    epochs = []
    dropped = []
    used = []
    for first in range(0, len(decisions), HOLD_STEPS):
        end = min(first + HOLD_STEPS, len(decisions))
        d = decisions[first]
        cap = hold_cap(behavior, first)
        require(
            all(
                r["actuation_readback"]["encoder_max_bitrate_bps"]
                == r["proposed_action"]["encoder_max_bitrate_bps"]
                == cap
                for r in decisions[first:end]
            ),
            "prescribed held cap/readback differs",
        )
        ack = d["ack_ms"]
        require(finite(ack) and ack >= d["observation"]["sample_ms"], "acknowledged causal epoch required")
        boundary = (
            decisions[end]["observation"]["sample_ms"]
            if end < len(decisions)
            else sender["measurement_cutoff_ms"]
        )
        previous = d["observation"]["raw_source"]["encoder_cap_bps"]
        direction = "increase" if cap > previous else "decrease" if cap < previous else "unchanged"

        def reached(value):
            return value is not None and (
                value >= 0.9 * cap if direction == "increase" else value <= 1.1 * cap
            )

        before = d["encoder_response"]["fields"]["targetBitrate"]["value"]
        after = [
            r
            for r in decisions[first:end]
            if ack <= r["observation"]["sample_ms"] < boundary
            and reached(r["encoder_response"]["fields"]["targetBitrate"]["value"])
        ]
        already = direction != "unchanged" and reached(before)
        latency = (
            None
            if direction == "unchanged" or already or not after
            else after[0]["observation"]["sample_ms"] - ack
        )
        event = dict(
            epoch=first // HOLD_STEPS,
            first_step=first,
            cap_bps=cap,
            previous_cap_bps=previous,
            direction=direction,
            ack_ms=ack,
            next_action_or_cutoff_ms=boundary,
            full_epoch=end - first == HOLD_STEPS,
            pre_ack_target_bps=before,
            threshold_already_met_before_ack=already,
            sampled_directional_target_latency_ms=latency,
            target_latency_censored=direction != "unchanged" and not already and not after,
            bands=[],
        )
        for start_age, stop_age in BANDS:
            start, stop = ack + start_age, ack + stop_age
            if stop + DEADLINE_MS > boundary:
                dropped.append(
                    dict(
                        epoch=event["epoch"],
                        band=[start_age, stop_age],
                        reason="future_action_or_cutoff_before_last_deadline",
                    )
                )
                continue
            candidates = [x for x in labels if start <= x["capture_request_ms"] < stop]
            require(
                all(
                    x["encoder_cap_bps"] == cap
                    and type(x["decision_id"]) is int
                    and first <= x["decision_id"] < end
                    and x["capture_request_ms"] >= decisions[x["decision_id"]]["ack_ms"]
                    for x in candidates
                ),
                "band source/ACK/cap attribution differs",
            )
            keep = [x for x in candidates if not x["action_transition_inflight"]]
            if not keep:
                dropped.append(
                    dict(
                        epoch=event["epoch"],
                        band=[start_age, stop_age],
                        reason="no_attributable_factual_requests",
                    )
                )
                continue
            require(
                all(
                    type(x["identifiable_ontime"]) is bool
                    and finite(x["ontime_sampled_psnr_contribution"])
                    and 0 <= x["ontime_sampled_psnr_contribution"] <= 100
                    for x in keep
                ),
                "original deadline/quality outcome semantics required",
            )
            intervals = [
                v
                for v in counters["valid_intervals"]
                if first <= v["from_step"] < v["to_step"] < end
                and start
                <= decisions[v["from_step"]]["observation"]["sample_ms"]
                < decisions[v["to_step"]]["observation"]["sample_ms"]
                <= stop
            ]
            samples = [
                r["encoder_response"]["fields"]["targetBitrate"]["value"]
                for r in decisions[first:end]
                if start <= r["observation"]["sample_ms"] < stop
                and r["encoder_response"]["fields"]["targetBitrate"]["status"] == "present"
            ]
            count = sum(v["frames"] for v in intervals)
            ids = [x["source_id"] for x in keep]
            used.extend(ids)
            event["bands"].append(
                dict(
                    band=[start_age, stop_age],
                    window_start_ms=start,
                    window_end_ms=stop,
                    last_request_deadline_before_ms=stop + DEADLINE_MS,
                    requests=len(keep),
                    source_ids=ids,
                    inflight_requests_excluded=len(candidates) - len(keep),
                    utility=statistics.mean(x["ontime_sampled_psnr_contribution"] for x in keep) / 100,
                    miss=statistics.mean(not x["identifiable_ontime"] for x in keep),
                    encoder_frames=count,
                    whole_interval_count=len(intervals),
                    frame_weighted_mean_vp8_qp=sum(
                        v["mean_vp8_qp"] * v["frames"] for v in intervals if v["mean_vp8_qp"] is not None
                    )
                    / count
                    if count
                    else None,
                    sampled_target_mean_bps=statistics.mean(samples) if samples else None,
                )
            )
        epochs.append(event)
    require(len(used) == len(set(used)), "disjoint epoch/lag bands cannot duplicate factual requests")
    return dict(
        abi=ABI,
        geometry=GEOMETRY,
        samples=counters["samples"],
        support=counters["support"],
        epochs=epochs,
        dropped_bands=dropped,
        counter_interval_drop_reasons=counters["dropped_intervals"],
        total_band_requests=len(used),
        actual_executed_learned_steps=0,
        descriptive_only=True,
        target_latency_sample_quantized=True,
        source_frame_causal_encoder_effect_identified=False,
        causal_quality_effect_proven=False,
        new_models_fitted=0,
        independent_validation=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def _trials(original):
    donor = next(
        t
        for t in original["episodes"]
        if t["group"] == "stable-0" and t["condition"] == "fixed450" and t["repetition"] == 0
    )
    require(
        donor["role"] == "train"
        and len({c for c, _, _ in donor["schedule"]}) == 1
        and donor["schedule"][0][0] > 0.9,
        "original stable nonbinding-capacity training reservation required",
    )
    return [
        {
            **donor,
            "id": f"encoder-lag-{i}-{behavior}",
            "condition": behavior,
            "position": i,
            "repetition": i // 2,
        }
        for i, behavior in enumerate(GEOMETRY["order"])
    ]


def plan_long_hold(base_runtime, out):
    original = read_json(base_runtime)
    verify_seal(Path(base_runtime).parent, base.PARENT_SEAL)
    require(base.compatible_engines(original), "base native sources changed")
    assets = asset_directory()
    require(
        (assets / "encoder_long_hold_episode.mjs").read_text()
        == project_long_collector((assets / "encoder_response_episode.mjs").read_text()),
        "exact long-hold collector required",
    )
    cfg = dict(
        abi=ABI,
        geometry=GEOMETRY,
        base_runtime=str(Path(base_runtime).resolve()),
        base_runtime_sha256=digest(base_runtime),
        trials=_trials(original),
        implementation_sha256=digest(__file__),
        additional_sources={
            "assets/" + n: digest(assets / n)
            for n in (
                "encoder_response.mjs",
                "encoder_response_episode.mjs",
                "encoder_hold_control.mjs",
                "encoder_long_hold_episode.mjs",
            )
        },
        availability_manifest_sha256=digest(
            Path(base_runtime).parent.parent / "native-encoder-availability-v1/manifest.json"
        ),
        training_reservation_reused_not_new_independence=True,
        models_fitted=0,
        SOTA_achieved=False,
    )
    write_json(out, cfg)
    return cfg


def validate_long_hold(cfg):
    require(
        cfg["abi"] == ABI
        and cfg["geometry"] == GEOMETRY
        and cfg["models_fitted"] == 0
        and cfg["SOTA_achieved"] is False
        and cfg["training_reservation_reused_not_new_independence"] is True,
        "fixed prospective conventional geometry/scope required",
    )
    require(
        digest(__file__) == cfg["implementation_sha256"]
        and digest(cfg["base_runtime"]) == cfg["base_runtime_sha256"],
        "lag code or original runtime changed",
    )
    original = read_json(cfg["base_runtime"])
    require(
        base.compatible_engines(original) and cfg["trials"] == _trials(original),
        "base engines or prescribed four trials changed",
    )
    assets = asset_directory()
    require(
        set(cfg["additional_sources"])
        == {
            "assets/" + n
            for n in (
                "encoder_response.mjs",
                "encoder_response_episode.mjs",
                "encoder_hold_control.mjs",
                "encoder_long_hold_episode.mjs",
            )
        }
        and all(digest(assets / k.split("/")[1]) == v for k, v in cfg["additional_sources"].items()),
        "new collector/control/sidecar changed",
    )
    require(
        digest(Path(cfg["base_runtime"]).parent.parent / "native-encoder-availability-v1/manifest.json")
        == cfg["availability_manifest_sha256"],
        "availability prerequisite changed",
    )
    p = copy.deepcopy(original)
    p["episodes"] = cfg["trials"]
    p["measurement_recipe"] = RECIPE
    p["encoder_long_hold_probe_only"] = True
    p["extra_source_sha256"].update(cfg["additional_sources"])
    return p


def _aggregate(responses):
    records = []
    for index, response in enumerate(responses):
        records.extend(dict(peer=index, behavior=GEOMETRY["order"][index], **e) for e in response["epochs"])
    latency = {}
    for direction in ("increase", "decrease"):
        events = [e for e in records if e["direction"] == direction]
        observed = [
            e["sampled_directional_target_latency_ms"]
            for e in events
            if e["sampled_directional_target_latency_ms"] is not None
        ]
        latency[direction] = dict(
            transitions=len(events),
            observed=len(observed),
            censored=sum(e["target_latency_censored"] for e in events),
            already_met=sum(e["threshold_already_met_before_ack"] for e in events),
            range_ms=[min(observed), max(observed)] if observed else None,
            median_ms=statistics.median(observed) if observed else None,
        )
    table = []
    for index, response in enumerate(responses):
        for cap in (300000, 450000, 900000):
            for band in BANDS:
                rows = [
                    b
                    for e in response["epochs"]
                    if e["cap_bps"] == cap
                    for b in e["bands"]
                    if b["band"] == list(band)
                ]
                n = sum(b["requests"] for b in rows)
                frames = sum(b["encoder_frames"] for b in rows)
                if rows:
                    table.append(
                        dict(
                            peer=index,
                            behavior=GEOMETRY["order"][index],
                            cap_bps=cap,
                            band=list(band),
                            epochs=len(rows),
                            requests=n,
                            utility=sum(b["utility"] * b["requests"] for b in rows) / n,
                            miss=sum(b["miss"] * b["requests"] for b in rows) / n,
                            frames=frames,
                            mean_vp8_qp=sum(
                                b["frame_weighted_mean_vp8_qp"] * b["encoder_frames"]
                                for b in rows
                                if b["frame_weighted_mean_vp8_qp"] is not None
                            )
                            / frames
                            if frames
                            else None,
                        )
                    )
    return dict(
        abi=ABI,
        geometry=GEOMETRY,
        actual_native_peers=len(responses),
        total_samples=sum(r["samples"] for r in responses),
        total_band_requests=sum(r["total_band_requests"] for r in responses),
        directional_sampled_target_latency=latency,
        per_peer_cap_band=table,
        all_drop_records=[dict(peer=i, **d) for i, r in enumerate(responses) for d in r["dropped_bands"]],
        original_credit_window_not_replaced=True,
        quality_differences_not_paired_counterfactuals=True,
        no_model_fit_or_promotion=True,
        causal_quality_effect_proven=False,
        independent_validation=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def run_long_hold(config, out):
    cfg = read_json(config)
    p = validate_long_hold(cfg)
    out = Path(out).resolve()
    out.mkdir(exist_ok=False)
    write_json(out / "protocol.json", cfg)
    write_json(out / "runtime.json", p)
    bundles = {k: base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    responses = []
    rows = []
    try:
        for trial in cfg["trials"]:
            child = out / trial["id"]
            with (out / (trial["id"] + ".log")).open("x") as log:
                subprocess.run(
                    [
                        "node",
                        str(asset_directory() / "encoder_long_hold_episode.mjs"),
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
                digest(child / "source_snapshot.mjs")
                == cfg["additional_sources"]["assets/encoder_long_hold_episode.mjs"],
                "actual long-hold producer changed",
            )
            row, derived = RAW_AUDIT(child, p, trial, bundles, None)
            response = summarize_response(
                read_json(child / "sender_observations.json"),
                read_json(child / "frame_events.json"),
                derived["quality"]["source_labels"],
                trial["condition"],
            )
            write_json(child / "native_derived.json", derived)
            write_json(child / "response.json", response)
            rows.append(row)
            responses.append(response)
        require(
            len(rows) == 4
            and all(rows[i]["cutoff_epoch_ms"] < rows[i + 1]["start_epoch_ms"] for i in range(3)),
            "four prospective nonoverlapping peers required",
        )
        validate_long_hold(cfg)
        report = _aggregate(responses)
        write_json(out / "native_rows.json", rows)
        write_json(out / "report.json", report)
        seal_directory(
            out, sorted(str(x.relative_to(out)) for x in out.rglob("*") if x.is_file()), ABI + "_complete"
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


def audit_long_hold(out):
    out = Path(out).resolve()
    verify_seal(out, ABI + "_complete")
    cfg = read_json(out / "protocol.json")
    p = validate_long_hold(cfg)
    require(p == read_json(out / "runtime.json"), "prospective runtime changed")
    bundles = {k: base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    responses = []
    rows = []
    for trial in cfg["trials"]:
        child = out / trial["id"]
        require(
            digest(child / "source_snapshot.mjs")
            == cfg["additional_sources"]["assets/encoder_long_hold_episode.mjs"]
            and (child / "panel_snapshot.json").read_bytes() == (out / "runtime.json").read_bytes(),
            "actual producer/runtime snapshot changed",
        )
        row, derived = RAW_AUDIT(child, p, trial, bundles, None)
        require(derived == read_json(child / "native_derived.json"), "full original native replay differs")
        response = summarize_response(
            read_json(child / "sender_observations.json"),
            read_json(child / "frame_events.json"),
            derived["quality"]["source_labels"],
            trial["condition"],
        )
        require(
            response == read_json(child / "response.json"),
            "target/QP/quality/lag/drop numeric response differs",
        )
        rows.append(row)
        responses.append(response)
    require(
        rows == read_json(out / "native_rows.json")
        and all(rows[i]["cutoff_epoch_ms"] < rows[i + 1]["start_epoch_ms"] for i in range(3)),
        "native rows/clocks differ",
    )
    report = _aggregate(responses)
    require(report == read_json(out / "report.json"), "complete lag report differs")
    return dict(
        read_only=True,
        full_original_native_raw_replay=True,
        actual_peers=4,
        samples=report["total_samples"],
        requests=report["total_band_requests"],
        all_bands_and_drops_recomputed=True,
        original_credit_window_not_replaced=True,
        causal_quality_effect_proven=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_encoder_long_hold")
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
        r = plan_long_hold(a.base_runtime, a.out)
        result = dict(abi=ABI, peers=4, config=str(a.out), geometry=r["geometry"], SOTA_achieved=False)
    elif a.command == "run":
        r = run_long_hold(a.config, a.out)
        result = dict(
            peers=r["actual_native_peers"],
            samples=r["total_samples"],
            requests=r["total_band_requests"],
            SOTA_achieved=False,
        )
    else:
        result = audit_long_hold(a.run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
