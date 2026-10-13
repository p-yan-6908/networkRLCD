# Targeted native range-pilot telemetry follow-up

This is a checksum-gated, descriptive replay of the twenty sessions registered in
[`next-input.json`](../reports/bwe-dynamics-diagnostic-v1/next-input.json). It
continues the V3 result with the older native range-pilot record; it does not
replace or pool any prior result.

## Access and restore

In the 2026-10-13 runtime, `HF_TOKEN` was present (its value was not printed or
saved). HTTPS to `huggingface.co` succeeded with certificate verification, and
an authenticated request for the private dataset
`p-yan/networkrlcd-results-archive` returned HTTP 200 with `private=true`. The
pinned revision's tree request also succeeded. No archive access failure was
observed in this runtime. The repository is at commit
`a135f0a9d19f48c74ad623cfe98f1dd71c01dcee`.

The storage receipt pins revision
`36b82e4045dc8f982930839c8528719ed30447ba`. All five archive parts (4,332,759,040
bytes) matched the receipt and `SHA256SUMS`. Before extraction, the pinned tree
metadata and metadata-only tar inventory were checked: the index covers 10,573
archive paths, and the five-part archive inventory matched those paths and
sizes without duplicates or unsafe links. The pinned file index's Git blob
identity is `039fcc4d5c8356cc6d27757bfe0b3616df483c40`. Only the registered
twenty sessions plus `protocol.json` and the selected source runtime metadata
were restored under
`~/.cache/networkrlcd/restored/native-range-pilot-v1-20-20261013/`: 882 files,
359,847,384 bytes. All 882 file SHA-256 values matched the pinned index, and
all twenty original session seals passed (43 sealed artifacts per session).
After replay, the five staging shards were hash-checked again and removed; the
targeted restore and 2.5 MB of plan/index/verification metadata remain under
`~/.cache/networkrlcd/`.

The executable replay is
[`native_range_targeted_telemetry_probe.py`](../tools/native_range_targeted_telemetry_probe.py).
With the pinned shards staged, it rechecks all archive and restored-file hashes,
verifies each original seal, and then reads only `sender_observations.json` and
`events.jsonl.gz` for the selected sessions. It does not parse
`frame_events.json` or read quality outcomes. Machine-readable results and
hold/phase rows are in
[`report.json`](../reports/native-range-pilot-v1-targeted-telemetry-20261013/report.json),
[`hold-windows.csv`](../reports/native-range-pilot-v1-targeted-telemetry-20261013/hold-windows.csv),
and
[`relay-phase-windows.csv`](../reports/native-range-pilot-v1-targeted-telemetry-20261013/relay-phase-windows.csv).

## Sender and encoder replay

All 20 sessions replayed their assigned cap/readback histories. There are 120
acknowledged 1.8–2.6 second post-ack windows, with 24 windows at each of five
levels. Encoded payload is measured before RTP packetization. The table reports
descriptive window means; repeated windows are clustered within four sessions
from one previously used source.

| Level | Nominal cap/BWE | Mean readback cap / preassignment BWE | Mean encoded payload / preassignment BWE | Mean encoded payload / readback cap | Clipped windows |
|---:|---:|---:|---:|---:|---:|
| 0 | 0.25 | 0.329 | 0.311 | 0.963 | 12 / 24 |
| 1 | 0.65 | 0.650 | 0.568 | 0.874 | 0 / 24 |
| 2 | 0.85 | 0.850 | 0.703 | 0.827 | 0 / 24 |
| 3 | 1.05 | 1.043 | 0.790 | 0.757 | 1 / 24 |
| 4 | ceiling | 6.969 | 1.459 | 0.287 | 0 / 24 |

The 0.25 arm is frequently raised by the 300 kbps floor. The 1.05 arm has one
readback clipped by the encoder. The ceiling arm is not a fixed-ratio action.
For separate context, the V3 localhost TURN/TCP means at 0.65, 0.85, and 1.05
were 0.587, 0.722, and 0.824. The side-by-side values are from different
transport panels and designs; they are not pooled and do not establish a
transport replication or difference.

The sender log contains 2,950 presentation-feedback sends and 2,949 receives.
One send in `underutilized-l1` has no recorded receive and remains in the
accounting. There are no orphan receives, and all 3,497 decision feedback
references link to received events. The median of session-level recorded
send-to-receive medians is 27.8 ms; these timestamps are not a network RTT
estimate.

## Relay history and clock limits

Across both relay directions, 43,154 UDP datagram offers were recorded and 310
were dropped. In the per-session direction with the largest aggregate wire-byte
total, there were 33,197 offers: 32,887 forwarded and 310 dropped. The registered
phase windows contain 32,732 of those offers; 404 precede the first phase and
61 follow the scheduled end. These records describe UDP datagrams: `wire_bytes`
is `payload_bytes + 28` for IPv4/UDP headers, not isolated RTP media payload.

All 60 capacity phase records match the registered schedules. The largest
within-Node-clock phase-start residual against the planned relative schedule is
34.61 ms. Drops are concentrated in a few descriptive regime/phase groups:

| Regime | Phase | Capacity (Mbps) | Dropped / offered UDP datagrams |
|---|---|---:|---:|
| collapse-recovery | collapse | 0.35 | 44 / 1,309 |
| queue-building | collapse | 0.60 | 5 / 1,951 |
| underutilized | high | 4.00 | 114 / 3,371 |
| underutilized | collapse | 4.00 | 48 / 4,892 |
| underutilized | recovery | 4.00 | 99 / 6,715 |

The remaining seven regime/phase groups had no dropped offers. Each group has
five sessions on the same source; these counts are descriptive, not independent
network-family evidence.

Sender polls, meter events, cap acknowledgments, and feedback use the browser
page's `performance.now()` clock. Relay phase and packet events use the Node
process's `performance.now()` clock. The first-phase timestamp minus the browser
measurement start ranges from 470 ms to 2,375 ms, but it is only a coarse anchor:
the archived `/phase` request has no paired browser-send, Node-receive,
Node-response, and browser-receive timestamps. Its request delay and clock
offset cannot be separated. Therefore packet counts remain summarized within
the relay clock; this replay does not assign UDP/RTP events to individual sender
holds.

## Interpretation and next measurement

The archive confirms that the cap acknowledgments and pre-RTP payload meter can
be replayed for this one-source native pilot. Its 0.65/0.85/1.05 payload ratios
are close descriptively to V3's values, but the pilot is fixed-level and
single-source while V3 is a separate randomized TURN/TCP panel. Neither result
identifies history-conditioned action value, delivered-quality gain, or
whole-session safety. The V3 1.05-versus-0.85 on-time interval remains
unresolved; this replay cannot narrow it because quality/frame outcomes were
not examined and relay events cannot be aligned to holds.

The next useful measurement is the independently versioned
[clock-marker probe plan](NATIVE_RANGE_CLOCK_MARKER_PROBE_V1_PLAN.md), not a
rewrite of these captures. At each phase transition and at capture
start/end, record a unique request ID, browser send/receive times, and Node
receive/phase-event/response-send times. For a short interval with a common
clock rate, the additive offset `Node time - browser time` is bounded by
`[Node response-send - browser response-receive, Node request-receive - browser
request-send]`. Repeated markers must also bound drift; any hold-to-relay join
must remain ambiguous unless all offsets in the recorded bound give the same
assignment. The new probe should be registered separately and retain every
ambiguous or failed record. No capture was started here, no model or controller
was fitted or promoted, no synthetic result was changed, and existing negative
results and freezes remain in force.
