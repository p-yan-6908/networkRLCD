# Native clock/action study V7 over TURN/TCP

## Question and separation

Under relay-only WebRTC compliant with the managed Chromium setting
`WebRtcIPHandling=disable_non_proxied_udp`, does selecting sender estimate
ratios 0.65 versus 1.05 produce differences in per-hold relay delivery cost or
receiver frame delivery across high, collapse, and recovery states?

V7 is a fresh nonconfirmatory panel. It is not pooled with V3, V4, V5, V6,
archived native sessions, recorded-video captures, or simulator/synthetic
controller evidence. It does not fit or promote a controller.

V5 sealed 32 sessions and passed transport in all 32, but only 30 passed clock
qualification at the initial high request. V6 sealed 32 and passed transport
and exact queue replay in all 32, but 21 failed the final held-out marker and
two also failed the post-high marker. Both panels remain frozen with treatment
telemetry unopened.

## Design

- 32 sessions: 8 fresh generated-scene seed clusters, 2 repetitions per ratio
  per seed, with randomized within-block order.
- Scene seeds: 6000 through 6007.
- Assignment-order seed: 20261018.
- Whole-session conditions: ratios 0.65 and 1.05.
- Preserve the existing high/collapse/recovery schedule, sender acknowledgement
  rule, frame deadline, and per-hold window.
- Analyze paired effects at the generated-scene seed-cluster level with 7
  degrees of freedom and 95% intervals.

## TURN, media, and queue acceptance

Use the qualified queue-backed TURN/TCP runtime and bidirectional media
preflight. Both peers must gather only loopback TURN relay candidates, report
zero candidate errors, and establish nominated/succeeded pairs. Preserve the
managed browser policy without modification.

Each direction must forward at least 100 packets from its matching TURN
allocation source port, with zero unexpected sources and send errors. Keep the
queue within its registered limit and service capacity. Replaying the
checksum-verified transport event log must exactly match offered, dropped,
served, and forwarded packet and wire-byte totals. Conservation error remains
at most 1e-6 bytes. Correctly accounted overflow drops remain delivery
outcomes. Each phase must show more than 10 encoded and decoded frames and a
finite mean encode time.

## Actual-run clock qualification

Record 12 paired sender/Node exchanges in this order:

1. session-start clock marker;
2. clock marker immediately before the high request;
3. high-phase request;
4. clock marker immediately after the high request;
5. high-to-collapse boundary clock marker;
6. collapse-phase request;
7. clock marker immediately after the collapse request;
8. collapse-to-recovery boundary clock marker;
9. recovery-phase request;
10. clock marker immediately after the recovery request;
11. mid-recovery clock marker, scheduled 3.3 seconds after recovery begins;
12. session-end clock marker.

Fit the affine sender-to-Node map with indices `[0, 1, 3, 4, 6, 7, 9, 11]`
and hold out `[2, 5, 8, 10]`. This retains four independent holdouts and all
existing acceptance thresholds: 100% held-out coverage, 1 ms timestamp-order
tolerance, and 50 ms maximum feasible width. The session-end exchange remains
in training; the new mid-recovery exchange is bracketed by the post-recovery
and session-end training exchanges. Retain the qualified 120-marker calibration
as reference only.

## Outcome gate

First verify all session checksums. The outcome-blind gate reads only capture
status, policy fingerprints, ICE/TURN evidence, queue ledgers and transport
events, and paired clock markers. All 32 sessions must pass transport and
actual-run clock qualification before sender observations, frame outcomes, or
per-hold relay offers are opened. Any failed session stays sealed and is
excluded from treatment interpretation; the all-session gate then fails and
produces no action estimates.

After that gate, verify each assigned action ratio against the registered arm
and base estimate, and each requested sender cap against the native actuation
readback. Every session must have at least one complete hold window in each
state. Any mismatch or missing phase window stops estimation; it does not
become a zero-cost or zero-QoE observation.

All estimates remain bounded to this generated-canvas local TURN/TCP setup.
They cannot establish Internet-path performance, human QoE, deployment safety,
or policy superiority. No controller is fit or promoted by this study.
