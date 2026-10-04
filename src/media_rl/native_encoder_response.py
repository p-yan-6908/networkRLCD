"""Identified nullable encoder-stat sidecar; never augments the native actor ABI."""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from .native_protocol import require

ABI = "native_encoder_response_sidecar_v1"
NUMERIC_FIELDS = {
    "targetBitrate": False,
    "qpSum": True,
    "framesEncoded": True,
    "keyFramesEncoded": True,
    "bytesSent": True,
    "retransmittedBytesSent": True,
    "headerBytesSent": True,
    "totalEncodeTime": False,
    "totalEncodedBytesTarget": True,
    "frameWidth": True,
    "frameHeight": True,
}
FIELDS = (*NUMERIC_FIELDS, "qualityLimitationReason")
KEYS = {
    "abi",
    "used_by_controller",
    "stream_key",
    "stats_id",
    "ssrc",
    "codec_id",
    "mime_type",
    "stats_timestamp_ms",
    "sample_ms",
    "time_origin_epoch_ms",
    "capture_cost_ms",
    "fields",
}


def numeric(v, integer=False):
    return (
        isinstance(v, (int, float))
        and not isinstance(v, bool)
        and math.isfinite(v)
        and v >= 0
        and (not integer or (v <= 2**53 - 1 and int(v) == v))
    )


def validate_encoder_sidecar(s, observation, time_origin):
    require(
        set(s) == KEYS and s["abi"] == ABI and s["used_by_controller"] is False,
        "exact auxiliary-only encoder ABI required",
    )
    require(
        all(isinstance(s[k], str) for k in ("stream_key", "stats_id", "ssrc"))
        and s["stream_key"] == observation["raw_source"]["stream_key"] == s["stats_id"] + ":" + s["ssrc"],
        "encoder outbound id/SSRC differs from selected actor source",
    )
    require(
        all(isinstance(s[k], str) for k in ("stream_key", "stats_id", "ssrc", "codec_id", "mime_type"))
        and s["codec_id"]
        and s["mime_type"].lower() == "video/vp8",
        "identified VP8 encoder required",
    )
    require(
        s["sample_ms"] == observation["sample_ms"]
        and numeric(s["sample_ms"])
        and s["time_origin_epoch_ms"] == time_origin
        and numeric(time_origin)
        and numeric(s["capture_cost_ms"]),
        "sidecar sample/origin clocks differ",
    )
    require(
        s["stats_timestamp_ms"] is None or numeric(s["stats_timestamp_ms"]),
        "raw stats timestamp invalid; no clock conversion implied",
    )
    require(set(s["fields"]) == set(FIELDS), "exact encoder field/status set required")
    for key, item in s["fields"].items():
        require(
            set(item) == {"status", "value"} and item["status"] in ("present", "absent", "invalid"),
            "encoder support status required",
        )
        value = item["value"]
        valid = (
            numeric(value, NUMERIC_FIELDS[key])
            if key in NUMERIC_FIELDS
            else value in ("none", "cpu", "bandwidth", "other")
        )
        require(
            valid if item["status"] == "present" else value is None,
            "missing/invalid encoder field cannot be padded or treated as zero",
        )
    for key, raw in (
        ("bytesSent", "bytes_sent"),
        ("framesEncoded", "frames_encoded"),
        ("totalEncodeTime", "total_encode_s"),
    ):
        require(
            s["fields"][key]["value"] == observation["raw_source"][raw],
            "sidecar disagrees with same-snapshot sender counter",
        )
    return True


def project_encoder_collector(text):
    anchors = (
        (
            "import {OBSERVATION_PROTOCOL,selectSenderSource,SenderObservationEncoder}",
            "import {captureEncoderResponse} from '/encoder_response.mjs';\nimport {OBSERVATION_PROTOCOL,selectSenderSource,SenderObservationEncoder}",
        ),
        (
            "const observation=encoder.observe(selectSenderSource(stats,own),performance.now());",
            "const observation=encoder.observe(selectSenderSource(stats,own),performance.now());const encoder_response=captureEncoderResponse(stats,observation.raw_source,observation.sample_ms,performance.timeOrigin);",
        ),
        (
            "decisions.push({step_id,observation,feedback_input",
            "decisions.push({step_id,observation,encoder_response,feedback_input",
        ),
        ("const moduleRoutes=new Set([", "const moduleRoutes=new Set(['/encoder_response.mjs',"),
    )
    for old, new in anchors:
        require(text.count(old) == 1, "exact encoder-only collector projection anchor required")
        text = text.replace(old, new)
    return text


def summarize_encoder_sidecars(sender, frames):
    decisions = sender["decisions"]
    require(decisions and not sender["learned_policy"], "bounded conventional availability probe only")
    status = {key: Counter() for key in FIELDS}
    samples = []
    intervals = []
    dropped = Counter()
    last = None
    for index, row in enumerate(decisions):
        require(row["step_id"] == index, "ordered distinct encoder sample association required")
        s = row["encoder_response"]
        validate_encoder_sidecar(s, row["observation"], frames["time_origin_epoch_ms"])
        for key in FIELDS:
            status[key][s["fields"][key]["status"]] += 1
        samples.append(s)
        if last:
            previous, p = last
            dt = s["sample_ms"] - p["sample_ms"]
            reasons = []
            if s["stream_key"] != p["stream_key"]:
                reasons.append("stream_change")
            if not 0 < dt <= 1000:
                reasons.append("sample_interval")
            if (
                s["stats_timestamp_ms"] is None
                or p["stats_timestamp_ms"] is None
                or s["stats_timestamp_ms"] <= p["stats_timestamp_ms"]
            ):
                reasons.append("stats_timestamp_missing_or_stale")
            if (
                row["observation"]["raw_source"]["encoder_cap_bps"]
                != previous["observation"]["raw_source"]["encoder_cap_bps"]
            ):
                reasons.append("cap_change")
            values = {}
            for key in ("qpSum", "framesEncoded", "bytesSent"):
                a, b = p["fields"][key]["value"], s["fields"][key]["value"]
                if a is None or b is None:
                    reasons.append(key + "_missing")
                elif b < a:
                    reasons.append(key + "_reset")
                else:
                    values[key] = b - a
            ra, rb = (
                p["fields"]["retransmittedBytesSent"]["value"],
                s["fields"]["retransmittedBytesSent"]["value"],
            )
            retransmitted = rb - ra if ra is not None and rb is not None and rb >= ra else None
            if retransmitted is not None and retransmitted > values.get("bytesSent", 0):
                retransmitted = None
            if reasons:
                dropped.update(set(reasons))
            else:
                intervals.append(
                    dict(
                        from_step=previous["step_id"],
                        to_step=index,
                        dt_ms=dt,
                        frames=values["framesEncoded"],
                        mean_vp8_qp=values["qpSum"] / values["framesEncoded"]
                        if values["framesEncoded"]
                        else None,
                        sent_payload_mbps=values["bytesSent"] * 8 / dt / 1000,
                        sent_nonretransmitted_payload_mbps=(values["bytesSent"] - retransmitted)
                        * 8
                        / dt
                        / 1000
                        if retransmitted is not None
                        else None,
                        encoder_target_bps=s["fields"]["targetBitrate"]["value"],
                        cap_bps=row["observation"]["raw_source"]["encoder_cap_bps"],
                    )
                )
        last = row, s
    targets = [
        s["fields"]["targetBitrate"]["value"]
        for s in samples
        if s["fields"]["targetBitrate"]["status"] == "present"
    ]
    return dict(
        abi=ABI,
        samples=len(samples),
        support={k: dict(v) for k, v in status.items()},
        unique_streams=sorted({s["stream_key"] for s in samples}),
        valid_intervals=intervals,
        dropped_intervals=dict(dropped),
        observed_target_range_bps=[min(targets), max(targets)] if targets else None,
        actual_encoder_target_and_qp_available=bool(targets and intervals),
        raw_stats_clock_not_assumed_equal_to_sample_clock=True,
        zero_frame_qp_undefined=True,
        telemetry_not_actor_observation=True,
        encoder_response_lag_established=False,
        causal_quality_effect_proven=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def audit_encoder_probe(root):
    """Full original packet/source/frame/quality/actor replay plus encoder evidence."""
    from . import native_action_excitation as base
    from .native_protocol import asset_directory, digest, read_json, verify_seal

    root = Path(root).resolve()
    verify_seal(root, ABI + "_probe_complete")
    cfg = read_json(root / "probe.json")
    p = read_json(root / "runtime.json")
    require(
        cfg["abi"] == ABI and cfg["conventional_only"] is True and cfg["models_fitted"] == 0,
        "encoder availability scope drift",
    )
    require(
        digest(Path(__file__)) == cfg["auditor_sha256"]
        and digest(asset_directory() / "encoder_response.mjs") == cfg["sidecar_sha256"],
        "current sidecar/auditor changed",
    )
    original = read_json(cfg["base_runtime"])
    require(
        digest(cfg["base_runtime"]) == cfg["base_runtime_sha256"] and base.compatible_engines(original),
        "frozen parent/source inputs changed",
    )
    expected = dict(original)
    expected["episodes"] = [cfg["trial"]]
    expected["encoder_availability_probe_only"] = True
    expected["extra_source_sha256"] = {
        **original["extra_source_sha256"],
        "assets/encoder_response.mjs": cfg["sidecar_sha256"],
        "assets/encoder_response_episode.mjs": cfg["collector_sha256"],
    }
    require(
        p == expected
        and (root / "peer/panel_snapshot.json").read_bytes() == (root / "runtime.json").read_bytes(),
        "exact runtime snapshot changed",
    )
    trial = cfg["trial"]
    require(
        trial in original["episodes"]
        and trial["condition"] == "fixed450"
        and trial["role"] == "train"
        and p["repair_model"] is None
        and p["conditions"]["fixed450"]["controller"] == "explore",
        "one original-reservation conventional availability trial required",
    )
    collector = asset_directory() / "encoder_response_episode.mjs"
    require(
        digest(root / "peer/source_snapshot.mjs") == digest(collector) == cfg["collector_sha256"],
        "actual encoder producer changed",
    )
    require(
        collector.read_text()
        == project_encoder_collector((asset_directory() / "excitation_episode.mjs").read_text()),
        "exact auxiliary-only collector projection changed",
    )
    bundles = {k: base.dense._base_bundle(e["path"]) for k, e in p["models"].items()}
    row, derived = base._RAW_AUDIT(root / "peer", p, trial, bundles, None)
    require(
        read_json(root / "native_row.json") == row and read_json(root / "native_derived.json") == derived,
        "full original native raw replay differs",
    )
    result = summarize_encoder_sidecars(
        read_json(root / "peer/sender_observations.json"), read_json(root / "peer/frame_events.json")
    )
    require(result == read_json(root / "report.json"), "actual encoder numeric/status report differs")
    return dict(
        read_only=True,
        full_original_native_raw_replay=True,
        samples=result["samples"],
        valid_intervals=len(result["valid_intervals"]),
        support=result["support"],
        actual_encoder_target_and_qp_available=result["actual_encoder_target_and_qp_available"],
        encoder_response_lag_established=False,
        native_deployment_qualified=False,
        SOTA_achieved=False,
    )


def main():
    parser = argparse.ArgumentParser(prog="python -m media_rl.native_encoder_response")
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_encoder_probe(args.run), indent=2))


if __name__ == "__main__":
    main()
