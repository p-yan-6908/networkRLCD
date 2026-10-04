"""Read-only FIFO/service replay; checks remain active under python -O."""

import gzip
import json
import math
from collections import deque
from pathlib import Path

from .native_protocol import finite, read_json, require


def replay_native_wire(root):
    root = Path(root)
    summary = read_json(root / "summary.json")
    require(
        summary["native_rtc"] is True
        and summary["userspace_relay_only"] is True
        and summary["connection"] == "connected"
        and summary["transport_cc_negotiated"] is True,
        "actual relay/native transport required",
    )
    require(
        [s["capacity_mbps"] for s in summary["snapshots"]]
        == [s[0] for s in summary["collection_config"]["schedule"]],
        "native schedule mismatch",
    )
    require(
        all(
            s["remote_candidate_address"] == "127.0.0.1"
            and s["codec"] == "video/VP8"
            and s["frames_decoded"] > 10
            for s in summary["snapshots"]
        ),
        "relay bypass or stalled decoder",
    )
    require(summary["relay"]["one_way_propagation_ms"] == 25, "pinned propagation required")

    def near(a, b):
        require(finite(a) and finite(b) and abs(a - b) < 1e-4, "native wire conservation/replay mismatch")

    states = {
        d: dict(
            queue=deque(),
            remaining=0.0,
            offered=0,
            dropped=0,
            served=0.0,
            budget=0.0,
            max_queue=0.0,
            last=None,
            sent=0,
            sent_wire=0,
            drops=0,
        )
        for d in ("a_to_b", "b_to_a")
    }
    packets = {}
    capacity, previous, count, minimum = 5, -math.inf, 0, math.inf
    with gzip.open(root / "events.jsonl.gz", "rt") as stream:
        for line in stream:
            event = json.loads(line)
            count += 1
            at = event["at_ms"]
            require(finite(at) and at >= previous, "nonmonotonic wire clock")
            previous = at
            if event["kind"] == "phase":
                require(
                    all(s["last"] == at for s in states.values()), "phase changed without service closure"
                )
                capacity = event["capacity_mbps"]
                require(finite(capacity) and 0 < capacity <= 4, "invalid native capacity")
                continue
            direction = event["direction"]
            require(direction in states, "unknown native packet direction")
            s = states[direction]
            if event["kind"] == "offer":
                index = event["packet"]
                require(type(index) is int and index == len(packets), "nonunique native datagram")
                wire = event["wire_bytes"]
                require(
                    type(wire) is int
                    and wire > 28
                    and type(event["payload_bytes"]) is int
                    and wire == event["payload_bytes"] + 28,
                    "wire/header accounting mismatch",
                )
                near(event["queue_before_wire_bytes"], s["remaining"])
                drop = s["remaining"] + wire > 30000
                require(event["dropped"] is drop, "native drop-tail decision mismatch")
                packets[index] = dict(
                    direction=direction, remaining=float(wire), wire=wire, dropped=drop, done=None, sent=False
                )
                s["offered"] += wire
                if drop:
                    s["dropped"] += wire
                    s["drops"] += 1
                else:
                    s["queue"].append(index)
                    s["remaining"] += wire
                    s["max_queue"] = max(s["max_queue"], s["remaining"])
                near(event["queue_after_wire_bytes"], s["remaining"])
            elif event["kind"] == "service":
                require(
                    event["capacity_mbps"] == capacity
                    and finite(event["from_ms"])
                    and event["from_ms"] <= at,
                    "service/capacity mismatch",
                )
                if s["last"] is not None:
                    near(event["from_ms"], s["last"])
                s["last"] = at
                budget = (at - event["from_ms"]) * capacity * 125
                near(budget, event["budget_wire_bytes"])
                near(s["remaining"], event["queue_before_wire_bytes"])
                expected = min(budget, s["remaining"])
                near(expected, event["service_wire_bytes"])
                s["budget"] += budget
                s["served"] += expected
                available = budget
                while available > 1e-9 and s["queue"]:
                    p = packets[s["queue"][0]]
                    used = min(available, p["remaining"])
                    available -= used
                    p["remaining"] -= used
                    s["remaining"] -= used
                    if p["remaining"] < 1e-9:
                        p["done"] = at
                        s["queue"].popleft()
                if not s["queue"]:
                    s["remaining"] = 0.0
                near(s["remaining"], event["queue_after_wire_bytes"])
            elif event["kind"] == "forward":
                require(
                    type(event["packet"]) is int and event["packet"] in packets, "unknown forwarded packet"
                )
                p = packets[event["packet"]]
                require(
                    p["direction"] == direction
                    and not p["dropped"]
                    and not p["sent"]
                    and p["done"] is not None,
                    "forwarded before service/double forward",
                )
                near(p["done"], event["serialization_done_ms"])
                require(event["wire_bytes"] == p["wire"], "forwarded wire size changed")
                lag = at - p["done"]
                require(lag >= 25 - 1e-6, "native propagation bypass")
                minimum = min(minimum, lag)
                p["sent"] = True
                s["sent"] += 1
                s["sent_wire"] += p["wire"]
            else:
                raise ValueError("unknown wire event")
            near(s["offered"] - s["dropped"] - s["served"], s["remaining"])
    require(count == summary["raw_event_count"], "wire event count mismatch")
    for direction, s in states.items():
        ledger = summary["relay"][direction]
        for key, value in [
            ("offered_wire_bytes", s["offered"]),
            ("dropped_wire_bytes", s["dropped"]),
            ("served_wire_bytes", s["served"]),
            ("queued_wire_bytes", s["remaining"]),
            ("max_queue_wire_bytes", s["max_queue"]),
            ("capacity_integral_wire_bytes", s["budget"]),
            ("overflow_packets", s["drops"]),
        ]:
            near(ledger[key], value)
        require(
            s["max_queue"] <= 30000 and s["served"] <= s["budget"] + 1e-4 and ledger["send_errors"] == 0,
            "invalid bounded native wire service",
        )
        require(
            ledger["forwarded_packets"] <= s["sent"]
            and ledger["forwarded_wire_bytes"] <= s["sent_wire"]
            and s["sent_wire"] <= s["served"] + 1e-4,
            "native forwarding exceeds service",
        )
    require(states["a_to_b"]["sent"] > 100, "no native media progress")
    return dict(
        raw_events_replayed=count,
        opaque_native_udp_packets=len(packets),
        minimum_observed_post_serialization_propagation_ms=minimum,
        fifo_capacity_accounting_verified=True,
        SOTA_achieved=False,
    )
