#!/usr/bin/env python3
"""Read-only, checksum-gated probe of the registered 20 range-pilot sessions.

This probe reads sender, cap/readback, encoded-payload meter, feedback, and
userspace-relay packet records. It does not load frame_events.json or compute
quality outcomes, fit a model, or evaluate a controller.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import stat
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from statistics import mean, median

from media_rl.native_protocol import verify_seal
from media_rl.native_range_pilot import replay_assignments


V3_REFERENCE = {
    "source": "docs/NATIVE_TURN_ACTION_ASSAY_V3_RESULTS.md",
    "study": "native localhost TURN/TCP action assay V3",
    "actual_payload_over_preassignment_bwe": {
        "0.65": 0.587,
        "0.85": 0.722,
        "1.05": 0.824,
    },
    "use": "separate context only; no pooling or replication claim",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text())


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def percentile(values: list[float], q: float):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(ordered[low])
    return float(ordered[low] * (high - position) + ordered[high] * (position - low))


def require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def verify_inputs(
    restore_manifest_path: Path,
    plan_path: Path,
    capture: Path,
    archive_stage: Path,
) -> tuple[dict, dict, dict, dict[str, int]]:
    restore_manifest = read_json(restore_manifest_path)
    plan = read_json(plan_path)
    require(
        hashlib.sha256(plan_path.read_bytes()).hexdigest() == restore_manifest["plan_sha256"],
        "registered next-input plan hash mismatch",
    )

    index_path = restore_manifest_path.parent / "file-index.json"
    index_bytes = index_path.read_bytes()
    index_blob = git_blob_sha1(index_bytes)
    require(
        index_blob == restore_manifest["metadata"]["file_index_git_blob_sha1"],
        "pinned file-index Git blob identity mismatch",
    )
    file_index = json.loads(index_bytes)

    sums_path = restore_manifest_path.parent / "SHA256SUMS"
    sums = {}
    for line in sums_path.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})\s+\*?(\S+)", line.strip())
        require(match is not None, "invalid pinned SHA256SUMS line")
        sums[match.group(2)] = match.group(1)

    parts = restore_manifest["archive"]["parts"]
    require(sums == {name: item["sha256"] for name, item in parts.items()}, "SHA256SUMS differs from receipt")
    for name, expected in parts.items():
        path = archive_stage / name
        require(path.is_file() and not path.is_symlink(), f"missing archive part: {name}")
        require(path.stat().st_size == expected["size"], f"archive part size mismatch: {name}")
        require(sha256(path) == expected["sha256"], f"archive part SHA-256 mismatch: {name}")

    destination = capture.parent.parent
    expected_files = restore_manifest["files"]
    indexed_files = file_index["files"]
    expected_paths = set()
    indexed_selected_paths = {
        path
        for path in indexed_files
        if path in restore_manifest["metadata"]["interpretation_metadata"]
        or any(path.startswith(f"results/native-range-pilot-v1/{trial}/") for trial in plan["trials"])
    }
    require(
        set(restore_manifest["metadata"]["selected_sessions"]) == set(plan["trials"]),
        "restore selection differs from the registered trial IDs",
    )
    require(
        set(plan["trials"]) == set(restore_manifest["metadata"]["selected_sessions"])
        and len(plan["trials"]) == 20,
        "registered selection must contain exactly twenty sessions",
    )
    for item in expected_files:
        relative = PurePosixPath(item["path"])
        require(
            not relative.is_absolute() and ".." not in relative.parts,
            "unsafe restored path in manifest",
        )
        indexed = indexed_files.get(relative.as_posix())
        require(indexed is not None, f"restored file is absent from pinned index: {item['path']}")
        require(
            indexed["sha256"] == item["sha256"] and indexed["size"] == item["size"],
            f"restore manifest differs from pinned file index: {item['path']}",
        )
        expected_paths.add(relative.as_posix())
        path = destination.joinpath(*relative.parts)
        require(path.exists() and not path.is_symlink(), f"missing restored file: {item['path']}")
        require(stat.S_ISREG(path.lstat().st_mode), f"non-regular restored file: {item['path']}")
        require(path.stat().st_size == item["size"], f"restored file size mismatch: {item['path']}")
        require(sha256(path) == item["sha256"], f"restored file SHA-256 mismatch: {item['path']}")

    found_paths = {
        path.relative_to(destination).as_posix()
        for path in capture.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    require(found_paths == expected_paths, "restored targeted file set differs from manifest")
    require(
        expected_paths == indexed_selected_paths,
        "restored file set differs from the exact registered selection in the pinned index",
    )
    require(
        restore_manifest["metadata"]["selected_session_count"] == len(plan["trials"]) == 20,
        "registered selection must contain exactly twenty sessions",
    )
    require(
        restore_manifest["metadata"]["selected_file_count"] == 882,
        "unexpected complete targeted file count",
    )
    session_file_counts = {
        trial: sum(path.startswith(f"results/native-range-pilot-v1/{trial}/") for path in expected_paths)
        for trial in plan["trials"]
    }
    require(
        all(count == 44 for count in session_file_counts.values()),
        "unexpected per-session selected file count",
    )
    require(
        sum(item["size"] for item in expected_files) == restore_manifest["metadata"]["selected_bytes"],
        "selected file byte count differs from restore manifest",
    )
    require(
        restore_manifest["archive"]["revision"] == plan["archive"]["revision"],
        "archive revision differs from registered plan",
    )
    seal_artifact_counts = {}
    for trial in plan["trials"]:
        session_root = capture / trial
        require(
            session_root.resolve().is_relative_to(capture.resolve()),
            f"session path escapes restored capture: {trial}",
        )
        seal = verify_seal(session_root)
        seal_artifact_counts[trial] = len(seal["artifacts_sha256"])
    return restore_manifest, plan, file_index, seal_artifact_counts


def read_relay_events(path: Path):
    phases = []
    offers_by_direction = defaultdict(list)
    forwards = {}
    services_by_direction = defaultdict(list)
    kind_counts = Counter()

    with gzip.open(path, "rt") as stream:
        for line in stream:
            event = json.loads(line)
            kind = event["kind"]
            kind_counts[kind] += 1
            if kind == "phase":
                phases.append(event)
            elif kind == "offer":
                offers_by_direction[event["direction"]].append(event)
            elif kind == "forward":
                key = (event["direction"], event["packet"])
                require(key not in forwards, "duplicate relay forward event")
                forwards[key] = event
            elif kind == "service":
                services_by_direction[event["direction"]].append(event)
            else:
                raise ValueError(f"unexpected relay event kind: {kind}")

    require(phases, "relay log has no capacity phases")
    all_offers = {
        (event["direction"], event["packet"]): event
        for events in offers_by_direction.values()
        for event in events
    }
    require(len(all_offers) == sum(map(len, offers_by_direction.values())), "duplicate relay offer event")
    expected_forwards = {key for key, event in all_offers.items() if not event["dropped"]}
    require(set(forwards) == expected_forwards, "relay forwards do not match non-dropped offers")
    for key, offer in all_offers.items():
        require(
            offer["wire_bytes"] == offer["payload_bytes"] + 28,
            "relay wire bytes do not match UDP payload plus IPv4/UDP headers",
        )
        if key in forwards:
            forward = forwards[key]
            require(forward["wire_bytes"] == offer["wire_bytes"], "relay forward wire bytes mismatch")
            require(
                forward["serialization_done_ms"] >= offer["at_ms"],
                "relay serialization completed before offer",
            )
    return phases, offers_by_direction, forwards, services_by_direction, kind_counts


def feedback_summary(sender: dict):
    sends = sender.get("feedback_sends", [])
    receives = sender.get("feedback_events", [])
    send_by_id = {item["source_id"]: item for item in sends}
    receive_by_id = {item["source_id"]: item for item in receives}
    require(len(send_by_id) == len(sends), "duplicate feedback send ID")
    require(len(receive_by_id) == len(receives), "duplicate feedback receive ID")

    orphan_receives = sorted(set(receive_by_id) - set(send_by_id))
    require(not orphan_receives, "feedback receive has no matching recorded send")
    input_references = [
        decision["feedback_input"]
        for decision in sender["decisions"]
        if decision.get("feedback_input") is not None
    ]
    orphan_inputs = [
        item["source_id"]
        for item in input_references
        if item["source_id"] not in receive_by_id
    ]
    require(not orphan_inputs, "sender decision references a feedback event that was not received")
    for item in input_references:
        received = receive_by_id[item["source_id"]]
        require(
            item["received_ms"] == received["received_ms"],
            "decision feedback input differs from the original receive event",
        )

    matched = set(send_by_id) & set(receive_by_id)
    send_receive_ms = [
        receive_by_id[source_id]["received_ms"] - send_by_id[source_id]["sent_ms"]
        for source_id in matched
    ]
    feedback_age_ms = [
        item["received_ms"] - item["capture_request_ms"]
        for item in receives
    ]
    return {
        "send_count": len(sends),
        "receive_count": len(receives),
        "matched_send_receive_count": len(matched),
        "unreceived_send_count": len(set(send_by_id) - set(receive_by_id)),
        "orphan_receive_count": len(orphan_receives),
        "decision_input_reference_count": len(input_references),
        "unlinked_decision_input_count": len(orphan_inputs),
        "recorded_send_to_receive_ms": {
            "min": min(send_receive_ms) if send_receive_ms else None,
            "median": median(send_receive_ms) if send_receive_ms else None,
            "p95": percentile(send_receive_ms, 0.95),
            "max": max(send_receive_ms) if send_receive_ms else None,
            "interpretation": "same-study recorded timestamps; not a network RTT estimate",
        },
        "capture_request_to_feedback_receive_ms": {
            "median": median(feedback_age_ms) if feedback_age_ms else None,
            "p95": percentile(feedback_age_ms, 0.95),
        },
    }


def analyze_session(
    trial_id: str,
    trial: dict,
    runtime: dict,
    capture: Path,
):
    root = capture / trial_id
    sender = read_json(root / "sender_observations.json")
    level = runtime["conditions"][trial["condition"]]["level"]
    _, assignments = replay_assignments(sender, level)
    require(len(assignments) == 6, f"{trial_id}: expected six acknowledged holds")

    decisions = sender["decisions"]
    meter = sender["encoded_meter"]
    meter_events = meter["events"]
    feedback = feedback_summary(sender)
    sample_times = [item["observation"]["sample_ms"] for item in decisions]
    require(
        all(sample_times[index] < sample_times[index + 1] for index in range(len(sample_times) - 1)),
        f"{trial_id}: sender sample clock is not strictly increasing",
    )
    meter_times = [event["at_ms"] for event in meter_events]
    require(
        all(meter_times[index] <= meter_times[index + 1] for index in range(len(meter_times) - 1)),
        f"{trial_id}: encoder meter clock is not monotonic",
    )

    phases, offers_by_direction, forwards, services_by_direction, kind_counts = read_relay_events(
        root / "events.jsonl.gz"
    )
    schedule = trial["schedule"]
    require(len(phases) == len(schedule) == 3, f"{trial_id}: expected three relay phases")
    phase_residuals = []
    cumulative_ms = 0
    for phase, expected in zip(phases, schedule, strict=True):
        require(
            math.isclose(phase["capacity_mbps"], expected[0], rel_tol=0, abs_tol=1e-9),
            f"{trial_id}: relay capacity differs from registered schedule",
        )
        phase_residuals.append(
            phase["at_ms"] - phases[0]["at_ms"] - cumulative_ms
        )
        cumulative_ms += expected[2]

    direction_totals = {
        direction: sum(event["wire_bytes"] for event in events)
        for direction, events in offers_by_direction.items()
    }
    media_direction = max(direction_totals, key=direction_totals.get)
    media_offers = offers_by_direction[media_direction]
    media_services = services_by_direction[media_direction]
    sender_start = sender["measurement_start_ms"]
    first_phase_anchor = phases[0]["at_ms"] - sender_start
    hold_windows = []

    for assignment in assignments:
        start_ms = assignment["ack_ms"]
        low_ms, high_ms = start_ms + 1800, start_ms + 2600
        selected_meter = [
            event for event in meter_events if low_ms <= event["at_ms"] < high_ms
        ]
        selected_decisions = [
            decision
            for decision in decisions
            if low_ms <= decision["observation"]["sample_ms"] < high_ms
        ]
        selected_feedback = [
            event
            for event in sender.get("feedback_events", [])
            if low_ms <= event["received_ms"] < high_ms
        ]
        payload_bytes = sum(event["byte_length"] for event in selected_meter)
        base_bwe = assignment["base_bwe_bps"]
        require(base_bwe > 0, f"{trial_id}: non-positive base BWE")
        payload_bps = payload_bytes * 10.0  # 0.8 s endpoint window
        live_bwe = [
            float(decision["observation"]["raw_source"]["bwe_bps"])
            for decision in selected_decisions
            if finite_number(decision["observation"]["raw_source"]["bwe_bps"])
        ]
        target_bps = []
        for decision in selected_decisions:
            target = decision["encoder_response"]["fields"]["targetBitrate"]
            if target.get("status") == "present" and finite_number(target.get("value")):
                target_bps.append(float(target["value"]))
        require(selected_meter, f"{trial_id}: no encoded-meter event in registered endpoint window")
        require(live_bwe, f"{trial_id}: no live BWE poll in registered endpoint window")
        hold_windows.append(
            {
                "trial_id": trial_id,
                "network_regime": trial["network_regime"],
                "level": level,
                "epoch": assignment["epoch"],
                "nominal_ratio": assignment["ratio"],
                "clipped": assignment["clipped"],
                "assignment_ms": assignment["assignment_ms"],
                "ack_ms": assignment["ack_ms"],
                "cap_ack_delay_ms": assignment["ack_ms"] - assignment["assignment_ms"],
                "preassignment_bwe_bps": base_bwe,
                "readback_cap_bps": assignment["requested_bps"],
                "readback_cap_over_preassignment_bwe": assignment["requested_bps"] / base_bwe,
                "endpoint_window_ms": [1800, 2600],
                "meter_event_count": len(selected_meter),
                "encoded_payload_bytes": payload_bytes,
                "encoded_payload_bps": payload_bps,
                "encoded_payload_over_preassignment_bwe": payload_bps / base_bwe,
                "encoded_payload_over_readback_cap": payload_bps / assignment["requested_bps"],
                "bwe_poll_count": len(live_bwe),
                "mean_live_bwe_over_preassignment_bwe": mean(live_bwe) / base_bwe,
                "encoder_target_sample_count": len(target_bps),
                "mean_encoder_target_bps": mean(target_bps) if target_bps else None,
                "feedback_receive_count": len(selected_feedback),
                "median_feedback_age_ms": median(
                    event["received_ms"] - event["capture_request_ms"]
                    for event in selected_feedback
                )
                if selected_feedback
                else None,
            }
        )

    phase_rows = []
    for index, (phase, registered) in enumerate(zip(phases, schedule, strict=True)):
        start_ms = phase["at_ms"]
        end_ms = (
            phases[index + 1]["at_ms"]
            if index + 1 < len(phases)
            else start_ms + registered[2]
        )
        require(end_ms > start_ms, f"{trial_id}: non-positive relay phase window")
        selected_offers = [
            event
            for event in media_offers
            if start_ms <= event["at_ms"] < end_ms
        ]
        selected_services = [
            event
            for event in media_services
            if start_ms <= event["at_ms"] < end_ms
        ]
        forwarded = [
            forwards[(media_direction, event["packet"])]
            for event in selected_offers
            if not event["dropped"]
        ]
        sojourn = [
            event["serialization_done_ms"] - offer["at_ms"]
            for offer, event in zip(
                [offer for offer in selected_offers if not offer["dropped"]],
                forwarded,
                strict=True,
            )
        ]
        offered_wire = sum(event["wire_bytes"] for event in selected_offers)
        dropped_wire = sum(
            event["wire_bytes"] for event in selected_offers if event["dropped"]
        )
        phase_rows.append(
            {
                "trial_id": trial_id,
                "network_regime": trial["network_regime"],
                "level": level,
                "phase": registered[1],
                "capacity_mbps": registered[0],
                "phase_start_node_ms": start_ms,
                "phase_duration_observed_ms": end_ms - start_ms,
                "udp_datagram_offer_count": len(selected_offers),
                "forwarded_offer_count": len(forwarded),
                "dropped_offer_count": sum(bool(event["dropped"]) for event in selected_offers),
                "udp_payload_bytes": sum(event["payload_bytes"] for event in selected_offers),
                "wire_bytes": offered_wire,
                "dropped_wire_bytes": dropped_wire,
                "dropped_wire_share": dropped_wire / offered_wire if offered_wire else None,
                "median_queue_plus_serialization_ms": median(sojourn) if sojourn else None,
                "p95_queue_plus_serialization_ms": percentile(sojourn, 0.95),
                "max_queue_after_offer_bytes": max(
                    (event["queue_after_wire_bytes"] for event in selected_offers),
                    default=0,
                ),
                "service_event_count": len(selected_services),
            }
        )

    media_schedule_end_ms = phases[-1]["at_ms"] + schedule[-1][2]
    media_pre_phase_offers = [event for event in media_offers if event["at_ms"] < phases[0]["at_ms"]]
    media_post_schedule_offers = [
        event for event in media_offers if event["at_ms"] >= media_schedule_end_ms
    ]
    phase_window_offer_count = sum(row["udp_datagram_offer_count"] for row in phase_rows)
    require(
        phase_window_offer_count + len(media_pre_phase_offers) + len(media_post_schedule_offers)
        == len(media_offers),
        f"{trial_id}: relay offers do not reconcile to registered phase windows",
    )
    total_offers = sum(map(len, offers_by_direction.values()))
    total_dropped = sum(
        bool(event["dropped"])
        for events in offers_by_direction.values()
        for event in events
    )
    return (
        {
            "trial_id": trial_id,
            "network_regime": trial["network_regime"],
            "level": level,
            "decision_count": len(decisions),
            "encoded_meter_event_count": len(meter_events),
            "encoded_meter_unit": meter["unit"],
            "feedback": feedback,
            "relay_event_counts": dict(sorted(kind_counts.items())),
            "relay_media_direction": media_direction,
            "relay_media_direction_offer_count": len(media_offers),
            "relay_media_direction_forward_count": sum(not event["dropped"] for event in media_offers),
            "relay_media_direction_drop_count": sum(bool(event["dropped"]) for event in media_offers),
            "relay_media_direction_phase_window_offer_count": phase_window_offer_count,
            "relay_media_direction_pre_phase_offer_count": len(media_pre_phase_offers),
            "relay_media_direction_post_schedule_offer_count": len(media_post_schedule_offers),
            "relay_udp_offer_count": total_offers,
            "relay_udp_dropped_offer_count": total_dropped,
            "relay_phase_count": len(phases),
            "phase_relative_schedule_residual_ms": phase_residuals,
            "first_phase_anchor_estimate_ms": first_phase_anchor,
        },
        hold_windows,
        phase_rows,
    )


def summarize_levels(hold_windows: list[dict]):
    summary = []
    for level in range(5):
        rows = [row for row in hold_windows if row["level"] == level]
        sessions = sorted({row["trial_id"] for row in rows})
        payload_over_bwe = [row["encoded_payload_over_preassignment_bwe"] for row in rows]
        cap_over_bwe = [row["readback_cap_over_preassignment_bwe"] for row in rows]
        payload_over_cap = [row["encoded_payload_over_readback_cap"] for row in rows]
        live_bwe_ratio = [row["mean_live_bwe_over_preassignment_bwe"] for row in rows]
        summary.append(
            {
                "level": level,
                "nominal_ratio": rows[0]["nominal_ratio"],
                "sessions": len(sessions),
                "hold_windows": len(rows),
                "independent_sources": 1,
                "mean_readback_cap_over_preassignment_bwe": mean(cap_over_bwe),
                "mean_encoded_payload_over_preassignment_bwe": mean(payload_over_bwe),
                "min_encoded_payload_over_preassignment_bwe": min(payload_over_bwe),
                "max_encoded_payload_over_preassignment_bwe": max(payload_over_bwe),
                "mean_encoded_payload_over_readback_cap": mean(payload_over_cap),
                "mean_live_bwe_over_preassignment_bwe": mean(live_bwe_ratio),
                "clipped_hold_count": sum(row["clipped"] for row in rows),
                "inference": "descriptive only; one used source, repeated holds are clustered within sessions",
            }
        )
    return summary


def summarize_relay_phases(relay_phases: list[dict]):
    groups = defaultdict(list)
    for row in relay_phases:
        groups[(row["network_regime"], row["phase"], row["capacity_mbps"])].append(row)
    summary = []
    for (regime, phase, capacity), rows in sorted(groups.items()):
        offer_count = sum(row["udp_datagram_offer_count"] for row in rows)
        wire_bytes = sum(row["wire_bytes"] for row in rows)
        dropped_bytes = sum(row["dropped_wire_bytes"] for row in rows)
        summary.append(
            {
                "network_regime": regime,
                "phase": phase,
                "capacity_mbps": capacity,
                "session_count": len(rows),
                "offer_count": offer_count,
                "forwarded_offer_count": sum(row["forwarded_offer_count"] for row in rows),
                "dropped_offer_count": sum(row["dropped_offer_count"] for row in rows),
                "dropped_offer_share": sum(row["dropped_offer_count"] for row in rows) / offer_count
                if offer_count
                else None,
                "wire_bytes": wire_bytes,
                "dropped_wire_bytes": dropped_bytes,
                "dropped_wire_share": dropped_bytes / wire_bytes if wire_bytes else None,
                "median_session_p95_queue_plus_serialization_ms": median(
                    row["p95_queue_plus_serialization_ms"]
                    for row in rows
                    if row["p95_queue_plus_serialization_ms"] is not None
                ),
                "max_queue_after_offer_bytes": max(row["max_queue_after_offer_bytes"] for row in rows),
                "inference": "descriptive within the Node relay clock; five sessions share one source",
            }
        )
    return summary


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore-manifest", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--archive-stage", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    output_names = {"report.json", "hold-windows.csv", "relay-phase-windows.csv"}
    if args.out.exists():
        require(args.out.is_dir() and not args.out.is_symlink(), "output path must be a regular directory")
        existing_outputs = set()
        for path in args.out.iterdir():
            require(path.is_file() and not path.is_symlink(), "unexpected non-file in output directory")
            existing_outputs.add(path.name)
        require(existing_outputs <= output_names, "output directory contains unrelated files")
    else:
        args.out.mkdir(parents=True)
    restore_manifest, plan, _, seal_artifact_counts = verify_inputs(
        args.restore_manifest,
        args.plan,
        args.capture,
        args.archive_stage,
    )
    protocol = read_json(args.capture / "protocol.json")
    trial_ids = plan["trials"]
    require(len(trial_ids) == len(set(trial_ids)) == 20, "registered session IDs must be unique")
    runtime_id = "rp-" + trial_ids[0].split("-")[1]
    require(runtime_id in protocol["runtimes"], "selected runtime metadata is missing")
    runtime = protocol["runtimes"][runtime_id]
    trials = {trial["id"]: trial for trial in runtime["episodes"]}
    require(set(trial_ids).issubset(trials), "registered trials do not match captured protocol")

    sessions = []
    hold_windows = []
    relay_phases = []
    for trial_id in trial_ids:
        session, holds, phases = analyze_session(
            trial_id,
            trials[trial_id],
            runtime,
            args.capture,
        )
        sessions.append(session)
        hold_windows.extend(holds)
        relay_phases.extend(phases)

    require(len(hold_windows) == 120, "expected 120 acknowledged 1.8–2.6 s windows")
    require(len(relay_phases) == 60, "expected 60 independent relay phase records")
    feedback_sends = sum(item["feedback"]["send_count"] for item in sessions)
    feedback_receives = sum(item["feedback"]["receive_count"] for item in sessions)
    feedback_missing = [
        item["trial_id"]
        for item in sessions
        if item["feedback"]["unreceived_send_count"]
    ]
    phase_residuals = [
        value
        for item in sessions
        for value in item["phase_relative_schedule_residual_ms"]
    ]
    anchor_estimates = [item["first_phase_anchor_estimate_ms"] for item in sessions]
    anchor_feedback = [
        delay
        for item in sessions
        for delay in [
            item["feedback"]["recorded_send_to_receive_ms"]["median"]
        ]
        if delay is not None
    ]
    all_direction_offers = sum(item["relay_udp_offer_count"] for item in sessions)
    all_direction_drops = sum(item["relay_udp_dropped_offer_count"] for item in sessions)
    media_direction_offers = sum(item["relay_media_direction_offer_count"] for item in sessions)
    media_direction_forwards = sum(item["relay_media_direction_forward_count"] for item in sessions)
    media_direction_drops = sum(item["relay_media_direction_drop_count"] for item in sessions)
    phase_window_media_offers = sum(
        item["relay_media_direction_phase_window_offer_count"] for item in sessions
    )
    media_pre_phase_offers = sum(item["relay_media_direction_pre_phase_offer_count"] for item in sessions)
    media_post_schedule_offers = sum(
        item["relay_media_direction_post_schedule_offer_count"] for item in sessions
    )
    output = {
        "abi": "native_range_targeted_telemetry_probe_v1",
        "status": "completed_descriptive_probe",
        "selection": {
            "source_commit": restore_manifest["source_commit"],
            "plan_sha256": restore_manifest["plan_sha256"],
            "source": plan["source"],
            "trial_ids": trial_ids,
            "session_count": len(trial_ids),
            "schedule_count": 4,
            "level_count": 5,
            "source_count": 1,
        },
        "archive_and_restore_verification": {
            "repo": restore_manifest["archive"]["repo"],
            "private": restore_manifest["archive"]["private"],
            "prefix": restore_manifest["archive"]["prefix"],
            "revision": restore_manifest["archive"]["revision"],
            "archive_parts_verified": len(restore_manifest["archive"]["parts"]),
            "archive_bytes_verified": restore_manifest["archive"]["archive_bytes"],
            "file_index_git_blob_sha1": restore_manifest["metadata"]["file_index_git_blob_sha1"],
            "restored_file_count": restore_manifest["metadata"]["selected_file_count"],
            "restored_bytes": restore_manifest["metadata"]["selected_bytes"],
            "restored_file_sha256_checks": restore_manifest["metadata"]["selected_file_count"],
            "original_session_seals_passed": len(seal_artifact_counts),
            "original_session_seal_artifact_counts": seal_artifact_counts,
            "raw_files_read_after_checksums": [
                "sender_observations.json",
                "events.jsonl.gz",
            ],
            "frame_events_parsed": False,
            "quality_outcomes_read": False,
        },
        "native_sender_and_encoder_replay": {
            "sessions": len(sessions),
            "acknowledged_holds": len(hold_windows),
            "all_cap_readbacks_replay": True,
            "all_encoded_meter_streams_cover_capture": True,
            "encoded_meter_unit": "encoded_video_payload_bytes_before_RTP_packetization",
            "endpoint_window_ms_after_ack": [1800, 2600],
            "empty_meter_windows": sum(row["meter_event_count"] == 0 for row in hold_windows),
            "empty_bwe_windows": sum(row["bwe_poll_count"] == 0 for row in hold_windows),
            "empty_feedback_input_windows": sum(row["feedback_receive_count"] == 0 for row in hold_windows),
            "feedback": {
                "sends": feedback_sends,
                "receives": feedback_receives,
                "unreceived_sends": feedback_sends - feedback_receives,
                "sessions_with_unreceived_sends": feedback_missing,
                "decision_input_references": sum(
                    item["feedback"]["decision_input_reference_count"] for item in sessions
                ),
                "all_decision_feedback_references_linked": all(
                    item["feedback"]["unlinked_decision_input_count"] == 0 for item in sessions
                ),
                "unmatched_receives": sum(
                    item["feedback"]["orphan_receive_count"] for item in sessions
                ),
                "recorded_send_receive_ms_median_of_session_medians": median(anchor_feedback),
            },
            "per_level": summarize_levels(hold_windows),
            "hold_windows": hold_windows,
        },
        "relay_history": {
            "sessions": len(sessions),
            "phase_windows": len(relay_phases),
            "all_offers_and_forwards_reconciled": True,
            "media_direction_selection": "direction with the largest aggregate UDP wire-byte total within each session",
            "media_direction_counts": {
                "offers": media_direction_offers,
                "forwarded": media_direction_forwards,
                "dropped": media_direction_drops,
                "inside_registered_phase_windows": phase_window_media_offers,
                "before_first_registered_phase": media_pre_phase_offers,
                "after_registered_schedule_end": media_post_schedule_offers,
                "coverage_reconciles": media_direction_offers
                == phase_window_media_offers + media_pre_phase_offers + media_post_schedule_offers,
            },
            "both_direction_counts": {
                "offers": all_direction_offers,
                "dropped": all_direction_drops,
            },
            "data_semantics": (
                "Relay UDP datagram payload_bytes and wire_bytes (payload plus IPv4/UDP headers); "
                "these are not isolated RTP media payload bytes."
            ),
            "phase_summary_by_regime": summarize_relay_phases(relay_phases),
            "phase_rows": relay_phases,
        },
        "clock_reconstruction": {
            "browser_clock": "sender polls, encoder meter, feedback events, and cap acknowledgments use browser-page performance.now()",
            "relay_clock": "relay phases, service ticks, offers, and forwarding use the Node process performance.now()",
            "first_phase_anchor_estimate_ms": {
                "min": min(anchor_estimates),
                "median": median(anchor_estimates),
                "max": max(anchor_estimates),
                "definition": "first Node relay phase timestamp minus browser measurement_start_ms",
                "calibrated_uncertainty_ms": None,
            },
            "phase_relative_schedule_residual_ms_max_abs": max(abs(x) for x in phase_residuals),
            "cross_clock_hold_level_rtp_join_validated": False,
            "reason": (
                "The captured logs do not store a paired browser timestamp for each /phase request "
                "or a Node/browser clock handshake. The first phase is only a coarse anchor; its "
                "request delay and absolute clock offset cannot be separated."
            ),
        },
        "context_from_v3": V3_REFERENCE,
        "interpretation": [
            "This is a descriptive native UDP telemetry probe on one previously used source; the 20 sessions are one schedule-by-level cell each and are not an independent source panel.",
            "The 0.65, 0.85, and 1.05 encoded-payload/BWE means use the same 1.8–2.6 s post-ack window as the separate TURN/TCP V3 report. They are not pooled and do not constitute a cross-transport replication.",
            "The single unreceived presentation-feedback send is retained; no session or hold was excluded.",
            "Relay packet history is replayed within its Node clock, but it is not joined to sender holds because absolute browser-to-Node clock alignment is uncalibrated.",
            "No quality endpoint, controller, model, or synthetic result was evaluated or changed.",
        ],
        "freeze_status": {
            "new_capture_started": False,
            "model_fitted": False,
            "controller_promoted": False,
            "SOTA_achieved": False,
            "synthetic_results_touched": False,
        },
        "sessions": sessions,
    }
    (args.out / "report.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    write_csv(args.out / "hold-windows.csv", hold_windows)
    write_csv(args.out / "relay-phase-windows.csv", relay_phases)
    print(
        json.dumps(
            {
                "status": output["status"],
                "sessions": len(sessions),
                "hold_windows": len(hold_windows),
                "relay_phase_windows": len(relay_phases),
                "archive_parts_verified": len(restore_manifest["archive"]["parts"]),
                "file_checksums_verified": restore_manifest["metadata"]["selected_file_count"],
                "unreceived_feedback_sends": feedback_sends - feedback_receives,
                "max_phase_schedule_residual_ms": output["clock_reconstruction"][
                    "phase_relative_schedule_residual_ms_max_abs"
                ],
                "cross_clock_hold_level_rtp_join_validated": False,
                "output": str(args.out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
