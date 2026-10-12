"""New factual native telemetry over policy-permitted authenticated localhost TURN/TCP.

Owned procedural content, a real VP8 encoder and the unchanged randomized native
instrument. This is a development observability probe, not a replication of the
licensed-video UDP pilots, real-network validation or learned-controller evidence.
"""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np

from . import native_actuator_control as control
from .native_encoder_response import validate_encoder_sidecar
from .native_frame_metrics import summarize_native_frames
from .native_margin_pilot_report import compare
from .native_protocol import asset_directory
from .native_quality import compute_rgb_quality

ABI = "native_turn_probe_v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_peer(root, trial):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["trial"] != trial or not manifest["complete"] or manifest["policy_modified"]:
        raise ValueError("complete unchanged-policy peer required")
    if (
        sha(root / "peer.json") != manifest["peer_sha256"]
        or sha(root / "events.jsonl.gz") != manifest["events_sha256"]
    ):
        raise ValueError("native evidence hash mismatch")
    peer = json.loads((root / "peer.json").read_text())
    if (
        peer["abi"] != ABI.replace("_v1", "_peer_v1")
        or not peer["native_rtc"]
        or peer["learned_policy"]
        or peer["native_counterfactuals"]
    ):
        raise ValueError("factual conventional native probe required")
    if peer["scene_seed"] != trial["scene_seed"] or peer["exploration_seed"] != trial["exploration_seed"]:
        raise ValueError("wrong native source or randomization seed")
    meter = peer["encoded_meter"]
    if (
        meter["error"] is not None
        or not meter["pass_through_no_frame_mutation"]
        or meter["unit"] != "encoded_video_payload_bytes_before_RTP_packetization"
    ):
        raise ValueError("actual pass-through encoded payload meter required")
    total, frames, previous = 0, 0, -np.inf
    for event in meter["events"]:
        total += event["byte_length"]
        frames += 1
        if event["at_ms"] < previous or event["total_bytes"] != total or event["total_frames"] != frames:
            raise ValueError("encoded-event clock/counter mismatch")
        previous = event["at_ms"]
    sampler = control.InstrumentSampler(trial["exploration_seed"])
    assignments = []
    for i, row in enumerate(peer["decisions"]):
        if row["step_id"] != i:
            raise ValueError("unordered native decisions")
        validate_encoder_sidecar(row["encoder_response"], row["observation"], peer["time_origin_epoch_ms"])
        expected = sampler.observe(
            row["observation"], row["encoder_response"], row["encoded_snapshot"], row["instrument_link"]
        )
        compare(row["assignment"], expected, "native assignment")
        if row["ack_ms"] is not None:
            if (
                expected is None
                or row["actuation_readback"]["encoder_max_bitrate_bps"] != expected["requested_bps"]
            ):
                raise ValueError("native acknowledgment/readback mismatch")
            sampler.acknowledge(row["ack_ms"], expected["requested_bps"])
            assignments.append(dict(expected, ack_ms=row["ack_ms"]))
    if len(assignments) != 6:
        raise ValueError("six complete native assignments required")
    if any(not s["remote_candidate_address"] == "127.0.0.1" for s in peer["snapshots"]):
        raise ValueError("media left the owned loopback path")
    for direction in ("a_to_b", "b_to_a"):
        if not peer["relay"][direction]["capacity_integral_upper_bound_ok"]:
            raise ValueError("wire service exceeded the declared bottleneck")
    summarize_native_frames(
        dict(
            protocol=peer["frame_protocol"],
            measurement_start_ms=peer["measurement_start_ms"],
            measurement_cutoff_ms=peer["measurement_cutoff_ms"],
            sources=peer["sources"],
            observations=peer["observations"],
            read_errors=0,
        )
    )
    for row in peer["observations"]:
        if row["quality"] is not None:
            own = row["quality"]
            expected = compute_rgb_quality(own["observed_rgb"], own["reference_rgb"])
            compare({k: own[k] for k in expected}, expected, "native RGB replay")
    return peer, assignments


def summarize(peer, assignments, trial):
    cutoff, start = peer["measurement_cutoff_ms"], peer["measurement_start_ms"]
    observed = {}
    known = 0
    for row in peer["observations"]:
        if row["known_source"]:
            known += 1
            observed.setdefault(row["source_id"], row)
    eligible = [
        s
        for s in peer["sources"]
        if start <= s["capture_request_ms"] and s["capture_request_ms"] + 150 <= cutoff
    ]
    cohorts = []
    for i, assignment in enumerate(assignments):
        ack = assignment["ack_ms"]
        end = assignments[i + 1]["ack_ms"] if i + 1 < len(assignments) else cutoff
        low, high = ack + control.WINDOW_MS[0], ack + control.WINDOW_MS[1]
        events = [e for e in peer["encoded_meter"]["events"] if low <= e["at_ms"] < high]
        complete = high <= end
        rate = sum(e["byte_length"] for e in events) * 8000 / (high - low) if complete else None
        sources = [s for s in eligible if ack <= s["capture_request_ms"] < end]
        timely = [
            s
            for s in sources
            if s["source_id"] in observed
            and observed[s["source_id"]]["readback_ms"] <= s["capture_request_ms"] + 150
        ]
        cohorts.append(
            dict(
                epoch=assignment["epoch"],
                arm=assignment["arm"],
                ratio=assignment["ratio"],
                propensity=assignment["propensity"],
                requested_bps=assignment["requested_bps"],
                base_bwe_bps=assignment["base_bwe_bps"],
                clipped_or_aliased=assignment["clipped_or_aliased"],
                ack_ms=ack,
                window_complete=complete,
                encoded_payload_bps=rate,
                realized_ratio=rate / assignment["base_bwe_bps"] if rate is not None else None,
                capture_requests=len(sources),
                on_time_requests=len(timely),
                on_time_share=len(timely) / len(sources) if sources else None,
            )
        )
    return dict(
        trial=trial,
        samples=len(peer["decisions"]),
        encoded_frames=len(peer["encoded_meter"]["events"]),
        resolved_capture_requests=len(eligible),
        known_marker_share=known / len(peer["observations"]) if peer["observations"] else 0,
        cohorts=cohorts,
        browser=peer["browser_build"],
    )


def capture(spec_path, out):
    spec_path, out = Path(spec_path), Path(out)
    if out.exists() or out.resolve().is_relative_to(Path.cwd().resolve()):
        raise ValueError("fresh external raw capture directory required")
    spec = json.loads(spec_path.read_text())
    if (
        spec.get("abi") != ABI + "_spec"
        or spec.get("native_counterfactuals") is not False
        or spec.get("controller_promoted") is not False
    ):
        raise ValueError("the factual development spec is required")
    for path, expected in spec["source_sha256"].items():
        if sha(path) != expected:
            raise ValueError("changed registered probe source: " + path)
    if not os.environ.get("RLCD_TURN_BINARY"):
        raise ValueError("configured verified local TURN runtime required")
    out.mkdir(parents=True)
    (out / "spec.json").write_bytes(spec_path.read_bytes())
    summaries = []
    for trial in spec["trials"]:
        config = out / (trial["id"] + ".json")
        config.write_text(json.dumps(trial, sort_keys=True) + "\n")
        child = out / trial["id"]
        print(json.dumps(dict(stage="native_capture", trial=trial["id"])), flush=True)
        with (out / (trial["id"] + ".log")).open("w") as log:
            subprocess.run(
                ["node", str(asset_directory() / "turn_probe.mjs"), str(child), str(config)],
                check=True,
                timeout=120,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        peer, assignments = validate_peer(child, trial)
        summaries.append(summarize(peer, assignments, trial))
        print(
            json.dumps(dict(stage="native_sealed", trial=trial["id"], samples=summaries[-1]["samples"])),
            flush=True,
        )
    (out / "summaries.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    return dict(sessions=len(summaries), cohorts=sum(len(s["cohorts"]) for s in summaries), raw=str(out))


def analyse(capture_path, out):
    capture_path, out = Path(capture_path), Path(out)
    if out.exists():
        raise ValueError("fresh compact report directory required")
    spec = json.loads((capture_path / "spec.json").read_text())
    summaries = []
    for trial in spec["trials"]:
        peer, assignments = validate_peer(capture_path / trial["id"], trial)
        summaries.append(summarize(peer, assignments, trial))
    cohorts = [c for s in summaries for c in s["cohorts"]]
    levels = {}
    for arm, ratio in enumerate(control.RATIOS):
        own = [c for c in cohorts if c["arm"] == arm]
        values = [c["realized_ratio"] for c in own if c["window_complete"]]
        levels[str(ratio)] = dict(
            assigned_holds=len(own),
            complete_windows=len(values),
            mean_realized_ratio=float(np.mean(values)) if values else None,
            aliased_holds=sum(c["clipped_or_aliased"] for c in own),
        )
    report = dict(
        abi=ABI + "_report",
        development_only=True,
        native_stack_factual=True,
        real_network_validation=False,
        controller_promoted=False,
        models_fitted=0,
        native_counterfactuals=False,
        raw_sender_encoder_replayed=True,
        sessions=len(summaries),
        cohorts=len(cohorts),
        levels=levels,
        samples=sum(s["samples"] for s in summaries),
        encoded_frames=sum(s["encoded_frames"] for s in summaries),
        min_known_marker_share=min(s["known_marker_share"] for s in summaries),
        spec_sha256=sha(capture_path / "spec.json"),
        source_sha256=spec["source_sha256"],
        raw_capture=str(capture_path),
        limitations=[
            "Generated procedural content, one Chromium build and one cloud machine.",
            "TURN/TCP adds transport dynamics; this does not replicate the original UDP/native pilots.",
            "Descriptive randomized-hold actuator evidence only; no learned action-value or QoE gain claim.",
        ],
    )
    out.mkdir(parents=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (out / "sessions.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    first = sub.add_parser("capture")
    first.add_argument("--spec", type=Path, required=True)
    second = sub.add_parser("analyse")
    second.add_argument("--capture", type=Path, required=True)
    for command in (first, second):
        command.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = capture(args.spec, args.out) if args.command == "capture" else analyse(args.capture, args.out)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
