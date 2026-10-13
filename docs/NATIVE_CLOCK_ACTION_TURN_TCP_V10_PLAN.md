# Native clock/action TURN/TCP V10 threshold-rule validation

## Question and separation

Does the fixed sender-only BWE-threshold rule identified before V9 improve
whole-session delivery or quality over a fixed 0.65 BWE-relative action?

The candidate rule uses only the current pre-action Chrome sender BWE at each
three-second action boundary. It requests `1.05 × BWE` when BWE is at least
500 kbps and `0.65 × BWE` otherwise. The comparator requests `0.65 × BWE` at
every boundary. Each requested cap is rounded and clipped to the existing
150 kbps–4 Mbps scalar range, then held for three seconds. Neither policy reads
phase labels, queue capacity, relay events, receiver pixels, or future labels.

The 500 kbps boundary and the two candidate ratios were registered before V9
capture. V10 is a direct whole-session comparison of that frozen rule against
the strong fixed-0.65 baseline. It does not search thresholds or fit a policy.
V10 remains separate from V3–V9, archived native sessions, recorded-video
results, and simulator/synthetic-controller evidence.

## Randomization and endpoints

- 48 native sessions: twelve fresh generated-scene seeds (8100–8111), two
  repetitions per policy per seed.
- Within each seed/repetition block, randomize the order of the threshold rule
  and fixed-0.65 session. Balance the first-policy order across the 24 blocks.
- Use the existing three-phase queue schedule, generated canvas source,
  150 ms receiver deadline, three-second action holds, and six 800 ms
  post-acknowledgment windows per session.
- Primary endpoint: the session's on-time receiver frame fraction over the
  six registered windows. Average the two repetitions per policy within each
  seed, then form the paired threshold-rule minus fixed-0.65 interval across
  twelve seed clusters (11 degrees of freedom, 95% t interval).
- Secondary endpoints: sampled RGB PSNR among on-time frames, guaranteed and
  possible offered relay wire bytes, queue drop bytes, and the same outcomes by
  scheduled phase. These are reported separately; no utility weights combine
  quality and relay volume.
- A positive primary result requires the full two-sided 95% interval to exceed
  zero. Report all endpoints and intervals regardless. Lower relay volume by
  itself is not a delivery or QoE gain.

## Clock, media, transport, and outcome gates

Reuse the qualified 120-exchange sender/Node clock calibration and the
queue-backed TURN/TCP preflight by pinned hashes. Every session records twelve
actual-run marker exchanges using the existing eight-fit/four-held-out split.
Require full held-out coverage, at most 1 ms timestamp-order tolerance, and at
most 50 ms feasible mapped-time width.

Before opening sender, frame, or relay-hold outcomes, verify all file
checksums, the unchanged managed browser-policy fingerprint,
relay-only candidate gathering, nominated TURN-backed pairs, bidirectional
media, exact queue event/ledger replay, and every actual-run clock map. All 48
sessions must pass. Preserve failed or incomplete sessions, do not replace
them, and do not interpret failed ICE or clock-gate sessions as policy
outcomes. Only join per-hold relay events for sessions whose actual-run clock
map passes.

Keep Chromium's `WebRtcIPHandling=disable_non_proxied_udp` policy unchanged.
TURN control remains loopback TCP, and the existing loopback UDP relay/queue
and propagation mechanism remain unchanged.

## Interpretation rule

Report the paired whole-session contrasts without pooling them with prior
studies. V10 can establish value only for this fixed rule against fixed 0.65
on this local generated-scene/queue setup. No model fitting or controller
promotion is part of the study. Even a positive local result would need
independent content and measured-network validation before a broader claim.

Raw sessions are retained outside Git at
`/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v10/`.
