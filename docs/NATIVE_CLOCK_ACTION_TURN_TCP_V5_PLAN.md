# Native clock/action study V5 over TURN/TCP

## Question

Under relay-only WebRTC that complies with the managed Chromium setting
WebRtcIPHandling=disable_non_proxied_udp, does selecting sender estimate ratios
0.65 versus 1.05 produce a reproducible difference in per-hold relay delivery
cost or receiver frame delivery across high, collapse, and recovery states?

V5 is a fresh, nonconfirmatory native study. It is not pooled with V3 or V4,
restored range-pilot sessions, recorded-video captures, or synthetic controller
experiments. It does not fit or promote a controller.

## Frozen prior evidence

V3 is preserved as 32 failed collector attempts. The phase acceptance assertion
referenced a remote candidate type that the snapshot did not record. Its
diagnostic-only marker report found 29/32 sessions passed the five-marker
held-out coverage check. V3 was not reclassified and its sender/frame evidence
was not analyzed.

V4 is preserved as 32 sealed sessions whose outcome-blind gate failed. The
seven-marker check passed in 29/32 sessions. The other three missed coverage at
two high-phase requests and one collapse-phase request. Eight sessions had
accounted queue overflow drops; the V4 plan had required zero drops. No V4
sender, frame-quality, or per-hold relay outcome was opened or estimated.

The queue-backed media preflight at
/home/agent/.cache/networkrlcd/native-turn-tcp-queue-preflight-v2.json passed
relay-only TURN/TCP gathering, nominated pairs, bidirectional media, and more
than 100 forwards in each direction. It recorded zero unexpected sources,
queue drops, or send errors and unchanged managed policy. Its SHA256 is
a45a8e2a9fec3303a8c09afb8d44896b8b642692fbc43a37d9917e768c345061.

## Design

- 32 sessions: 8 fresh generated-scene seed clusters, 2 repetitions per ratio
  per seed, with randomized within-block order.
- Scene seeds: 4000 through 4007.
- Assignment-order seed: 20261016.
- Whole-session conditions: ratios 0.65 and 1.05.
- The existing high/collapse/recovery schedule, sender acknowledgement rule,
  frame deadline, and per-hold window remain unchanged.
- The analysis unit is the generated-scene seed cluster. The paired contrast
  is 0.65 minus 1.05 with 7 degrees of freedom and 95% intervals.
- Every failed transport, media, policy, or clock session remains preserved and
  is excluded from treatment interpretation.

## TURN and queue acceptance

Chromium uses relay-only ICE and authenticated TURN/TCP control against local
Coturn. Coturn allocates loopback UDP relay endpoints. The owner-controlled UDP
queue forwards packets to the peer's TURN allocation.

Both peers must gather only TURN/TCP relay candidates, report no ICE candidate
errors, and establish nominated/succeeded pairs. The selected path must retain
loopback and TURN relay evidence, with the managed policy unchanged. Each
direction must forward at least 100 packets from its matching TURN allocation
source port, with zero unexpected sources or send errors. Service must stay
within the capacity integral, the queue high-water must stay within its
registered limit, and offered bytes must reconcile exactly to dropped, served,
and queued bytes.

Queue overflow drops are registered delivery outcomes. A drop does not make a
session unusable when the queue ledger and packet event log account for it
exactly. The gate replays offered, dropped, served, and forwarded totals from
the checksum-verified event log against the queue evidence before opening
sender/frame outcomes. The analysis retains possible and guaranteed dropped
wire bytes per hold.

Every phase must also show more than 10 encoded and decoded frames and a finite
mean encode time. The preflight validates the transport route but evaluates no
action, per-hold delivery, or QoE.

## Actual-run clock qualification

Each session records nine paired sender/Node exchanges in this order:

1. start clock marker;
2. high-phase request;
3. clock marker immediately after the high request;
4. clock marker at the high-to-collapse boundary;
5. collapse-phase request;
6. clock marker immediately after the collapse request;
7. recovery-phase request;
8. clock marker immediately after the recovery request;
9. end clock marker.

Fit the affine map with marker indices [0, 2, 4, 6, 8] and hold out [1, 3, 5,
7]. All four held-out exchanges must be covered by every feasible affine map.
The widest held-out interval remains limited to 50 ms; the held-out
timestamp-order tolerance remains 1 ms. The adjacent markers bracket the phase
requests that missed coverage in V4. The unchanged qualified 120-marker
calibration remains a reference, not a substitute for actual-run qualification.

## Outcome gate and interpretation

The hash-verified clock-gate reads only capture status, TURN/queue evidence,
policy fingerprints, marker files, and transport event logs. It must pass for
all 32 sessions before sender observations, frame outcomes, or per-hold relay
offers are opened. If any session fails transport or clock qualification, the
analysis command refuses to read outcome telemetry.

After that gate, the analysis verifies each assigned action ratio against its
registered session condition, checks the requested cap against the registered
ratio and base estimate, and checks the native actuation readback. Every
session must have at least one complete hold window in each of high, collapse,
and recovery. Missing phase coverage or any
action/readback mismatch stops estimation; incomplete arms are not treated as
zero-cost or zero-QoE observations.

Any resulting estimates remain bounded to this generated-canvas local TURN/TCP
setup. They cannot establish Internet-path performance, human QoE, deployment
safety, or policy superiority. V5 remains separate from all prior native,
archived, recorded-video, simulated, and synthetic evidence.
