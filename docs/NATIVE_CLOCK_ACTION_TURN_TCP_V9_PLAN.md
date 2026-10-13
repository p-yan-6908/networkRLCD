# Native clock/action TURN/TCP V9 micro-randomized state-action study

## Question and separation

Does the pre-action sender BWE estimate identify different causal effects of
the 0.65 and 1.05 BWE-relative cap actions on receiver delivery or relay cost?

V9 is a fresh native micro-randomized study. At each three-second action
boundary it first observes Chrome's current sender BWE, places that value into
one of two pre-registered strata (`<500 kbps` or `>=500 kbps`), and then assigns
ratio 0.65 or 1.05 with propensity 0.5. The assignment is drawn from the
registered SHA256 counter stream keyed by randomization seed, trial ID, and
epoch. The cap is rounded from the pre-action BWE and clipped to the existing
150 kbps–4 Mbps scalar range. The selected cap is held for 3 seconds.

The 500 kbps split was selected before V9 capture from the sender-state
distribution seen in V7/V8. The rule uses only current pre-action BWE; it does
not use phase labels, queue capacity, relay events, receiver pixels, or future
labels. This is a causal measurement of action-by-observed-state response, not
a fitted or promoted controller. V9 will not be pooled with V3–V8, archived
range sessions, recorded-video results, or synthetic evidence.

## Randomization and outcomes

- 48 sessions from 12 fresh generated-scene seeds (8000–8011), four
  repetitions per seed, randomized session order.
- Six action holds per session, with an independent 0.5/0.5 action draw at
  each valid pre-action BWE observation.
- Measure each action in the same registered 800 ms receiver/relay window
  1.8–2.6 seconds after native cap acknowledgement.
- Primary endpoint: the `1.05 − 0.65` contrast in the 150 ms on-time frame
  fraction for `BWE >= 500 kbps`, minus the same action contrast for
  `BWE < 500 kbps`. First aggregate action/state cells within each generated
  scene seed; form the interval across 12 seeds (11 degrees of freedom, 95%
  t interval).
- Secondary endpoints: the two within-BWE-stratum action contrasts for on-time
  fraction, sampled RGB PSNR among on-time frames, offered relay wire bytes,
  and queue drops.
- A seed contributes to the primary interaction only if it has at least two
  valid hold windows in each of the four BWE-state/action cells. Require at
  least 8 of 12 contributing seeds; otherwise report insufficient coverage
  and no primary interval. Do not add sessions after capture.

## Clock, media, transport, and outcome gates

Reuse the qualified 120-exchange clock calibration and the successful
queue-backed TURN/TCP preflight by pinned hashes. Record and validate the same
12 actual-run clock markers per session, with 8 training and 4 held-out
exchanges. Require full held-out coverage, at most 1 ms timestamp-order
tolerance, and at most 50 ms feasible mapped-time width.

First verify all checksums, policy fingerprints, relay-only candidates,
nominated TURN-backed pairs, bidirectional media, exact queue-event/ledger
replay, and each actual-run clock map. Every planned session must pass before
sender, receiver, or per-hold relay outcomes are opened. Preserve every failed
capture; failed ICE sessions are not action outcomes and are not replaced.
Do not estimate a sender/relay hold join unless that session's clock map passes.

Keep `WebRtcIPHandling=disable_non_proxied_udp` unchanged. TURN control remains
loopback TCP; relay and queue remain on the existing loopback UDP path. Do not
change queue or propagation settings.

## Interpretation rule

Report the pre-registered interaction even if it is negative or inconclusive.
A nonzero interaction establishes only causal heterogeneity across these two
sender-BWE strata on this local setup. It does not establish full-session
policy value. Any state rule must still beat fixed 0.65 in a separate
whole-session randomized validation before a controller claim; no fitting or
promotion is part of V9.

Raw sessions are retained outside Git at
`/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v9/`.
