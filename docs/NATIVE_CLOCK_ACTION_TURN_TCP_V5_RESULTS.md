# TURN/TCP action V5 clock-gate result

V5 captured and sealed all 32 preregistered sessions. Checksum integrity passed
before any outcome inspection:

- protocol SHA256: 394ae78949257e5ffb6f38a0802970c201e8b869bbb5a854dd505ea5bde9f7cb
- capture-index SHA256: 1b2f6c59d369131ef9625c5be6c5546370bdfc274d2f3d326f4e175591223143
- actual-run gate SHA256: 632494e98c4c2906e61ec36b0a09f64ba363e3d85381490f4160033bec21e6b8

The gate failed the registered requirement that all four held-out clock
markers pass in every session. Thirty of 32 sessions qualified on clock
alignment; all 32 passed the TURN/queue transport gate. Sender observations,
frame-quality outcomes, per-hold relay events, and action effects were not
opened or estimated.

## Actual-run clock checks

The two failures were `turntcp5-scene00-rep0-r065` and
`turntcp5-scene04-rep0-r105`. Both missed held-out marker `m0002`, the initial
high-phase request. Each session covered three of four held-out markers. The
widest feasible intervals were 2.90 ms and 2.62 ms, within the unchanged 50 ms
width limit; the independent coverage rule still failed.

## TURN and queue checks

All 32 sessions completed relay-only TURN/TCP candidate gathering and
connected through nominated pairs. Managed Chromium policy remained
`disable_non_proxied_udp` with no runner modification. Event replay matched the
queue ledger in both directions for offered, dropped, served, and forwarded
wire bytes; source-port, forward-count, capacity, queue-bound, conservation,
and send-error checks passed.

Across the panel, A-to-B recorded 97 accounted overflow packets / 103,460
wire bytes in 12 sessions; B-to-A had no drops. Those queue records remain
transport diagnostics, not treatment effects, because clock coverage failed.

The diagnostic-only report is
[native-clock-action-turntcp-v5-gate-diagnostic-only.json](../reports/native-clock-action-turntcp-v5-gate-diagnostic-only.json)
(SHA256 05eae9136a0b19617847c030289eaa156639d04d35088c73f88c48949842ade0).
It contains no sender, frame, QoE, per-hold relay, or action telemetry.

V5 remains frozen and excluded from all other native and synthetic evidence.
A fresh marker design should add independent clock exchanges immediately
before the initial high and recovery phase requests, while retaining the same
coverage, width, timestamp-order, transport, and ledger acceptance criteria.
