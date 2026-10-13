# Native clock/action study V4 over TURN/TCP

## Question

Under relay-only WebRTC that complies with the managed Chromium setting
WebRtcIPHandling=disable_non_proxied_udp, does selecting sender estimate ratios
0.65 versus 1.05 produce a reproducible difference in per-hold relay delivery
cost or receiver frame delivery across high, collapse, and recovery states?

This is a fresh, nonconfirmatory native study. It is not pooled with prior native
captures, restored range-pilot sessions, recorded-video captures, or synthetic
controller experiments. It does not fit or promote a controller.

## Frozen evidence that motivates V4

The earlier V3 TURN/TCP action acquisition is preserved at
/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v3/. Its 32 sessions
all retain failed status. ICE gathering, TURN/TCP relay candidates, nominated
connections, and policy checks were present, and queue-event logs show more than
100 forwards in both directions in every session. The collector nevertheless
aborted after the schedule because it required remote_candidate_type in phase
snapshots without recording that field. No V3 outcome report was produced.

V3's actual-run marker diagnostic covered all 32 marker inventories. Twenty-nine
sessions passed the registered held-out affine-map coverage check; three did
not. The widest held-out feasible interval was 5.2921 ms, below the 50 ms width
limit, but those three sessions missed the separate full-coverage requirement.
V3 therefore supplies no per-hold relay join or action estimate.

The successful queue-backed media preflight is recorded at
/home/agent/.cache/networkrlcd/native-turn-tcp-queue-preflight-v2.json.
Both peers gathered only TURN/TCP relay candidates, established nominated ICE
pairs, sent and decoded more than 10 video frames in each direction, and moved
at least 100 packets in both directions through the owned queue. The queue
reported zero drops, source mismatches, or send errors and exact byte
conservation within floating-point tolerance. The policy fingerprint remained
unchanged. The earlier short V1 queue preflight remains preserved as a failed
attempt because it stopped before its 100-packet minimum.

## Design

- 32 sessions: 8 fresh generated-scene seed clusters, 2 repetitions per ratio
  per seed, with randomized within-block order.
- Scene seeds: 3000 through 3007.
- Assignment-order seed: 20261015.
- Whole-session conditions: ratios 0.65 and 1.05.
- Each session uses the previously frozen high/collapse/recovery schedule and
  the existing sender acknowledgement and frame-window definitions.
- The analysis unit is the generated-scene seed cluster; the planned paired
  contrast is 0.65 minus 1.05 with 7 degrees of freedom and 95% intervals.
- The collector preserves every planned session. Failed transport, media,
  policy, or clock qualification excludes that session from treatment
  interpretation; no failed ICE or queue attempt is an action outcome.

## Transport and media acceptance

Chromium uses iceTransportPolicy=relay and authenticated TURN/TCP control
against local Coturn. Coturn allocates loopback UDP relay endpoints. The
registered owner-controlled UDP queue rewrites only the remote signalled
candidate address and forwards packets to the other TURN allocation.

The collector requires relay-only gathered candidates with TCP relay metadata,
zero ICE candidate errors, nominated/succeeded selected pairs, loopback
endpoints, and unchanged managed policy. Each phase snapshot must report the
selected remote relay candidate at loopback. The queue evidence must show at
least 100 forwarded packets in each direction, zero unexpected source
endpoints, send errors, or overflow drops, a valid capacity integral, and byte
conservation within 1e-6 bytes. Every phase must include more than 10 encoded
and decoded frames with finite encode-time measurements.

The queue-backed media preflight is a separate transport check; it does not
evaluate a bitrate action, delivery outcome, or QoE.

## Actual-run clock qualification

Each action session records seven paired sender/Node marker exchanges in this
order:

1. start clock marker;
2. high-phase request;
3. clock marker before collapse;
4. collapse-phase request;
5. clock marker before recovery;
6. recovery-phase request;
7. end clock marker.

Fit the affine clock map using marker indices [0, 2, 4, 6]; hold out
[1, 3, 5]. All three held-out exchanges must be covered by every feasible map,
and the widest held-out interval must be no more than 50 ms. The held-out
timestamp-order tolerance stays at 1 ms. A session failing either coverage or
width is unqualified for per-hold relay assignment. The prior qualified
120-marker calibration remains an unchanged reference; it does not replace
actual-session checks.

## Outcome gate and interpretation

Before opening sender observations, frame outcomes, or per-hold relay offers,
the hash-verified clock-gate checks all session seals, TURN/queue evidence,
policy fingerprints, marker order, and the seven-marker held-out map. Outcome
analysis runs only if every planned session is sealed and every session passes
both actual transport and clock gates. If a gate fails, raw evidence remains
preserved and no per-hold estimate is produced.

Any resulting estimates remain bounded to this generated-canvas local TURN/TCP
setup. They cannot establish Internet-path performance, human QoE, deployment
safety, or policy superiority. V4 results remain separate from V3 and all prior
native, archived, recorded-video, simulated, and synthetic evidence.
