"""Post-capture, read-only causal-feature and FIFO audit of the registered TURN probe.

Adds verification without changing the committed collector, spec or raw seals.
"""

import argparse
import gzip
import json
import tempfile
from pathlib import Path

import numpy as np

from .native_margin_pilot_report import compare
from .native_observations import FEATURE_NAMES, NATIVE_OBSERVATION_ABI, NativeSenderObservationEncoder
from .native_turn_probe import sha, summarize, validate_peer
from .native_wire import replay_native_wire


def audit_sender(peer):
    encoder, last_ack, last_cap = NativeSenderObservationEncoder(), -np.inf, None
    events = peer["encoded_meter"]["events"]
    times = np.array([e["at_ms"] for e in events])
    start, cutoff = peer["measurement_start_ms"], peer["measurement_cutoff_ms"]
    present = {}
    for index, row in enumerate(peer["decisions"]):
        obs, snapshot = row["observation"], row["encoded_snapshot"]
        sample, raw = obs["sample_ms"], obs["raw_source"]
        if row["step_id"] != index or not start <= sample <= cutoff or sample < last_ack:
            raise ValueError("noncausal sample/ack clock")
        if obs["observation_abi"] != NATIVE_OBSERVATION_ABI or tuple(obs["feature_names"]) != FEATURE_NAMES:
            raise ValueError("sender feature ABI mismatch")
        compare(obs["features"], encoder.observe(raw, sample), "causal sender feature reconstruction")
        if last_cap is not None and raw["encoder_cap_bps"] != last_cap:
            raise ValueError("unacknowledged encoder cap discontinuity")
        last = np.searchsorted(times, sample, side="right") - 1
        expected = dict(
            abi="native_encoded_payload_meter_v1",
            status="active",
            sample_ms=sample,
            total_bytes=events[last]["total_bytes"] if last >= 0 else 0,
            total_frames=events[last]["total_frames"] if last >= 0 else 0,
        )
        compare(snapshot, expected, "causal encoded snapshot")
        ack = row["ack_ms"]
        if ack is not None:
            if not sample <= ack <= cutoff or row["assignment"] is None:
                raise ValueError("noncausal native acknowledgment")
            readback = row["actuation_readback"]
            if (
                readback["encoder_max_bitrate_bps"] != row["assignment"]["requested_bps"]
                or readback["receiver_jitter_buffer_target_ms"] != 0
            ):
                raise ValueError("native cap/receiver readback mismatch")
            last_cap, last_ack = readback["encoder_max_bitrate_bps"], ack
        elif row["actuation_readback"] is not None:
            raise ValueError("readback without acknowledgment")
        else:
            last_cap = raw["encoder_cap_bps"]
        for name, field in row["encoder_response"]["fields"].items():
            present[name] = present.get(name, 0) + (field["status"] == "present")
    return dict(
        causal_sender_features_replayed=len(peer["decisions"]),
        encoded_snapshots_replayed=len(peer["decisions"]),
        auxiliary_content_excluded_from_feature_vector=True,
        encoder_field_present_counts=present,
        rtt_present_samples=sum(
            r["observation"]["raw_source"]["rtcp_rtt_s"] is not None for r in peer["decisions"]
        ),
    )


def audit_wire(root, peer, trial):
    """Replay the closing-ledger prefix and require an empty, valid timer-only suffix.

    The collector obtains browser version after saving its closing ledger, before
    stopping the timer. Preserve that defect and all raw bytes. The original FIFO
    auditor verifies the prefix; independently verify every trailing service tick.
    Never accept new packets or byte service beyond the recorded ledger.
    """
    root = Path(root)
    phases, count, prefix_end, suffix = [], 0, None, 0
    budgets = {d: 0.0 for d in ("a_to_b", "b_to_a")}
    last = {}
    previous = -np.inf
    with gzip.open(root / "events.jsonl.gz", "rt") as stream:
        for line in stream:
            event = json.loads(line)
            count += 1
            at = event["at_ms"]
            if not np.isfinite(at) or at < previous:
                raise ValueError("nonmonotonic wire clock")
            previous = at
            if prefix_end is not None:
                d = event.get("direction")
                if (
                    event["kind"] != "service"
                    or d not in budgets
                    or event["capacity_mbps"] != phases[-1]
                    or event["from_ms"] != last[d]
                    or event["from_ms"] > at
                    or any(
                        event[k] != 0
                        for k in ("queue_before_wire_bytes", "queue_after_wire_bytes", "service_wire_bytes")
                    )
                ):
                    raise ValueError("packet/byte service after closing ledger")
                expected = (at - event["from_ms"]) * event["capacity_mbps"] * 125
                if abs(expected - event["budget_wire_bytes"]) > 1e-4:
                    raise ValueError("trailing empty service budget mismatch")
                last[d] = at
                suffix += 1
                continue
            if event["kind"] == "phase":
                phases.append(event["capacity_mbps"])
            elif event["kind"] == "service":
                d = event["direction"]
                budgets[d] += event["budget_wire_bytes"]
                last[d] = at
                if (
                    len(last) == 2
                    and len(set(last.values())) == 1
                    and all(
                        abs(budgets[k] - peer["relay"][k]["capacity_integral_wire_bytes"]) < 1e-4
                        for k in budgets
                    )
                ):
                    prefix_end = count
    if prefix_end is None:
        raise ValueError("no exact closing-ledger prefix in raw log")
    if (
        phases != [s[0] for s in trial["schedule"]]
        or peer["transport"] != "authenticated localhost TURN/TCP plus owned UDP bottleneck"
    ):
        raise ValueError("native transport/schedule mismatch")
    if any(r["encoder_response"]["mime_type"] != "video/VP8" for r in peer["decisions"]):
        raise ValueError("native codec mismatch")
    summary = dict(
        native_rtc=peer["native_rtc"],
        userspace_relay_only=True,
        connection=peer["connection"],
        transport_cc_negotiated=peer["transport_cc_negotiated"],
        collection_config=dict(schedule=trial["schedule"]),
        raw_event_count=prefix_end,
        relay=peer["relay"],
        snapshots=[
            dict(s, capacity_mbps=c, codec="video/VP8")
            for s, c in zip(peer["snapshots"], phases, strict=True)
        ],
    )
    with tempfile.TemporaryDirectory(prefix="networkrlcd-turn-readonly-") as temp:
        adapter = Path(temp)
        with gzip.open(root / "events.jsonl.gz", "rt") as original:
            with gzip.open(adapter / "events.jsonl.gz", "wt") as prefix:
                for index, line in enumerate(original):
                    if index >= prefix_end:
                        break
                    prefix.write(line)
        (adapter / "summary.json").write_text(json.dumps(summary))
        return dict(
            replay_native_wire(adapter),
            full_raw_event_count=count,
            trailing_empty_service_events=suffix,
            trailing_timer_ticks_independently_verified=True,
            closing_ledger_precedes_raw_end=suffix > 0,
            raw_evidence_modified=False,
        )


def verify(capture, compact):
    capture, compact = Path(capture), Path(compact)
    spec = json.loads((capture / "spec.json").read_text())
    report = json.loads((compact / "report.json").read_text())
    if sha(capture / "spec.json") != report["spec_sha256"]:
        raise ValueError("spec changed after capture")
    for path, expected in spec["source_sha256"].items():
        if sha(path) != expected:
            raise ValueError("registered source changed: " + path)
    rows, summaries = [], []
    for trial in spec["trials"]:
        root = capture / trial["id"]
        peer, assignments = validate_peer(root, trial)
        rows.append(
            dict(
                trial=trial["id"],
                sender=audit_sender(peer),
                wire=audit_wire(root, peer, trial),
                manifest_sha256=sha(root / "manifest.json"),
            )
        )
        summaries.append(summarize(peer, assignments, trial))
    compare(summaries, json.loads((compact / "sessions.json").read_text()), "native summaries")
    return dict(
        abi="native_turn_probe_v1_independent_audit",
        added_after_capture=True,
        sessions=rows,
        summaries_recomputed=True,
        numeric_compare_relative_tolerance=1e-12,
        numeric_compare_absolute_tolerance=1e-12,
        native_factual_only=True,
        real_network_validation=False,
        controller_promoted=False,
        registered_source_hashes_unchanged=True,
        registered_spec_sha256=report["spec_sha256"],
        audit_source_sha256=sha(__file__),
        dependency_sha256={
            p: sha(p) for p in ("src/media_rl/native_wire.py", "src/media_rl/native_observations.py")
        },
        archive_verified=False,
        raw_bytes_pruned=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--compact", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("fresh independent audit receipt required")
    report = verify(args.capture, args.compact)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(dict(verified_sessions=len(report["sessions"]), out=str(args.out))))


if __name__ == "__main__":
    main()
