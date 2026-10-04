import gzip
import json

import pytest

from media_rl.native_protocol import digest
from media_rl.native_wire import replay_native_wire


def fixture(tmp_path):
    """Artificial conserved packet stream; no actual browser/SOTA evidence."""
    events = []
    state = {
        d: dict(last=0, offered=0, served=0, queue=0, budget=0, max_queue=0, sent=0)
        for d in ("a_to_b", "b_to_a")
    }
    capacity = 5

    def service(at):
        for direction, s in state.items():
            budget = (at - s["last"]) * capacity * 125
            used = min(s["queue"], budget)
            events.append(
                dict(
                    kind="service",
                    direction=direction,
                    from_ms=s["last"],
                    at_ms=at,
                    capacity_mbps=capacity,
                    budget_wire_bytes=budget,
                    service_wire_bytes=used,
                    queue_before_wire_bytes=s["queue"],
                    queue_after_wire_bytes=s["queue"] - used,
                )
            )
            s.update(last=at, queue=s["queue"] - used, served=s["served"] + used, budget=s["budget"] + budget)

    for i in range(101):
        at = i * 40 + 1
        service(at)
        events.append(
            dict(
                kind="offer",
                direction="a_to_b",
                packet=i,
                at_ms=at,
                wire_bytes=128,
                payload_bytes=100,
                dropped=False,
                queue_before_wire_bytes=0,
                queue_after_wire_bytes=128,
            )
        )
        s = state["a_to_b"]
        s.update(offered=s["offered"] + 128, queue=128, max_queue=128)
        service(at + 1)
        events.append(
            dict(
                kind="forward",
                direction="a_to_b",
                packet=i,
                at_ms=at + 26,
                serialization_done_ms=at + 1,
                wire_bytes=128,
            )
        )
        s["sent"] += 1
    for i, new in enumerate((2, 0.5, 2)):
        at = 4100 + i * 100
        service(at)
        events.append(dict(kind="phase", at_ms=at, capacity_mbps=new))
        capacity = new
    service(4400)
    relay = dict(one_way_propagation_ms=25)
    for direction, s in state.items():
        relay[direction] = dict(
            offered_wire_bytes=s["offered"],
            dropped_wire_bytes=0,
            served_wire_bytes=s["served"],
            queued_wire_bytes=s["queue"],
            max_queue_wire_bytes=s["max_queue"],
            capacity_integral_wire_bytes=s["budget"],
            overflow_packets=0,
            send_errors=0,
            forwarded_packets=s["sent"],
            forwarded_wire_bytes=s["sent"] * 128,
        )
    summary = dict(
        native_rtc=True,
        userspace_relay_only=True,
        connection="connected",
        transport_cc_negotiated=True,
        collection_config=dict(schedule=[[2, "high", 1000], [0.5, "collapse", 1000], [2, "recovery", 1000]]),
        snapshots=[
            dict(capacity_mbps=c, remote_candidate_address="127.0.0.1", codec="video/VP8", frames_decoded=20)
            for c in (2, 0.5, 2)
        ],
        relay=relay,
        raw_event_count=len(events),
    )
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    (tmp_path / "events.jsonl.gz").write_bytes(
        gzip.compress("".join(json.dumps(x) + "\n" for x in events).encode())
    )
    return events


def test_raw_fifo_replay_is_read_only_and_conserves_bytes(tmp_path):
    fixture(tmp_path)
    before = {p.name: digest(p) for p in tmp_path.iterdir()}
    result = replay_native_wire(tmp_path)
    assert result["opaque_native_udp_packets"] == 101
    assert result["minimum_observed_post_serialization_propagation_ms"] == 25
    assert before == {p.name: digest(p) for p in tmp_path.iterdir()}


@pytest.mark.parametrize("mutation", ["early-forward", "wrong-service", "bool-drop", "reordered-clock"])
def test_corrupt_native_packet_evidence_rejects(tmp_path, mutation):
    events = fixture(tmp_path)
    if mutation == "early-forward":
        next(x for x in events if x["kind"] == "forward")["serialization_done_ms"] = 0
    elif mutation == "wrong-service":
        next(x for x in events if x["kind"] == "service")["budget_wire_bytes"] += 1
    elif mutation == "bool-drop":
        next(x for x in events if x["kind"] == "offer")["dropped"] = 0
    else:
        events[1]["at_ms"] = -1
    (tmp_path / "events.jsonl.gz").write_bytes(
        gzip.compress("".join(json.dumps(x) + "\n" for x in events).encode())
    )
    with pytest.raises(ValueError):
        replay_native_wire(tmp_path)
