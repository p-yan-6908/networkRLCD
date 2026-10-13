# Native clock/action TURN/TCP V8 baseline validation

## Question

On fresh generated-scene seeds and the registered local queue schedule, does
the existing sender-only 0.85-BWE headroom rule improve receiver delivery
and/or relay cost over the fixed 0.65 BWE-ratio baseline?

V8 is a fresh randomized native validation. The BWE rule receives only the
versioned sender observation. It does not receive scheduled phase names,
queue capacity, relay events, receiver pixels, absolute episode time, or future
labels. It selects the largest supported scalar encoder cap no greater than
0.85 of the current Chrome BWE estimate and holds that cap for 3 seconds.
The fixed baseline uses the existing 0.65 BWE ratio with the same hold
duration. No fitted policy or controller is introduced.

V8 is not pooled with V3–V7, archived range sessions, recorded-video results,
or simulator/synthetic evidence. V7's phase labels motivated this validation
but are not controller inputs.

## Randomization and endpoints

- 48 whole-session trials: 12 fresh generated-scene seeds (7000–7011), two
  repetitions per policy per seed, randomized within seed/repetition blocks.
- Policies: fixed 0.65 BWE ratio and the existing sender-only 0.85-BWE
  headroom selector.
- The network schedule, content generator, frame deadline, transport and
  3-second action hold cadence are unchanged from V7.
- Primary endpoint: BWE-rule minus fixed-0.65 difference in the on-time
  receiver frame fraction, computed over the six registered 800 ms windows
  per session. Average repetitions within each scene-seed cluster, then form
  the paired estimate across 12 clusters (11 degrees of freedom, 95% t
  interval).
- Secondary endpoints: on-time fraction by scheduled state; sampled RGB PSNR
  among on-time frames; guaranteed and possible offered relay wire bytes;
  queue overflow/drop bytes; and collapse-minus-high on-time interaction.
- These endpoints are local receiver/transport proxies. The V8 policy contrast
  is a direct baseline validation, not a deployment or generalization claim.

## Clock, media, transport, and outcome gates

Reuse the qualified 120-exchange clock calibration and successful queue-backed
TURN/TCP preflight by their pinned hashes. Every V8 session records the same 12
actual-run markers as V7 and uses the same 8-fit/4-held-out split. Require
100% held-out coverage, at most 1 ms timestamp-order tolerance, and at most
50 ms feasible mapped-time width. Verify sender-action assignment, requested
cap, proposal, and native readback for every decision; replay the BWE selector
from its saved pre-action observation at every assignment.

The outcome-blind gate first verifies every file checksum, immutable browser
policy fingerprint, relay-only ICE and selected pairs, two-way queue/event
replay, media progress, and actual-run clock map. All 48 sessions must pass.
Failed or incomplete sessions remain sealed and documented; they are not
replaced and are not treatment outcomes. Do not open sender observations,
frame outcomes, or relay offers before the complete gate passes. Do not
estimate per-hold relay effects unless that session's actual-run clock map
passes.

The managed Chromium policy remains
`WebRtcIPHandling=disable_non_proxied_udp`. TURN control uses loopback TCP;
the existing owned relay/queue path uses loopback UDP. No policy or queue
mechanism changes are allowed.

## Decision rule and limits

Report the prespecified paired contrasts and intervals, including negative or
inconclusive results. No model fitting, controller promotion, source pooling,
or claim of Internet-path/human QoE validation is allowed. A positive interval
would support only this fixed BWE rule on this local setup. It would still need
independent content and measured-network validation before any broader claim.

The raw capture is retained outside Git at
`/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v8/`; versioned
protocol and compact checksummed report are kept in the repository.
