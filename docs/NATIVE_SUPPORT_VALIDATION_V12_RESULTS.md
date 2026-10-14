# V12 execution: support qualification failed

V12 was run from the unchanged registration at `aed3afa`. All 24 registered
support checks were attempted in their frozen order, with the original
content, measured-rate windows, nine-second decision boundary, BWE bounds,
threshold, conditioning, clock markers, TURN/TCP transport and cleanup recipe.
The census produced 23 sealed captures and one sealed failed capture.

The official all-session gate failed: **10/24** checks passed all gates.
Thirteen sealed captures lacked the registered BWE support; one additional
capture failed the native media-statistics check. The failed capture is
`v12-p05-s0-support` (Shirlan Waterfall × Murcia, high-BWE target), with the
preserved error `Error: native media stats not valid`.

## Support by measured campaign and content

The required support was two checks per content/campaign/state, with every
registered check qualifying. No crossed cell had complete low/high support.

| Measured campaign | Low-BWE checks passing all gates | High-BWE checks passing all gates | All checks passing | Capture failures |
| --- | ---: | ---: | ---: | ---: |
| UCC Irish LTE | 2/4 | 2/4 | 4/8 | 0 |
| NYU metropolitan LTE | 0/4 | 4/4 | 4/8 | 0 |
| Murcia private campus TCP upload | 0/4 | 2/4 | 2/8 | 1 |

Both content groups qualified 5/12 checks: one low-target and four high-target
checks each. The penguin group sealed all 12 captures; the waterfall group
sealed 11 and retained the one media-statistics failure. At the cell level,
each content's Irish cell qualified 1/2 low and 1/2 high checks, its NYU cell
qualified 0/2 low and 2/2 high, and its Murcia cell qualified 0/2 low and 1/2
high. Thus **0/6 cells** met the complete support rule. Windows and shared
content remain nested within these campaigns; these counts are not independent
population replicates.

## Fixed-window support diagnosis

The diagnostic verified every session SHA-256 seal and projected only sender
time, BWE feature zero, support qualification, assignment/readback and capture
failure messages. It replayed the original eleven-sample, 900 ms history,
250 ms maximum gap, `[9000,9300]` ms decision window, 500 kbps state split and
`[240,000,3,800,000]` bps eligibility range. It did not inspect alternative
decision times, thresholds, source windows or outcome measurements.

All registered-window candidate histories met the sample-count, span and gap
conditions. Among the thirteen sealed BWE failures, eleven failed the eligible
bitrate range throughout the fixed decision window, and three failed the
target-state condition; one failed both. The separate failed media capture
also lacked high-state and bitrate-range support. These categories overlap.

Every rejected bitrate range was below the 240 kbps lower bound. Examples
include approximately 59–78 kbps for the waterfall/Irish low target,
91–164 kbps for NYU low targets, and 30–167 kbps for rejected Murcia checks.
The two rejected Irish high-target histories stayed below or crossed the
500 kbps split: one was approximately 410–460 kbps, while another mixed
401–611 kbps before settling near 402 kbps. Recorded-rate source hints did
not establish stable eligible native BWE at the frozen decision boundary.
The lower bound preserves distinct unclipped ratio actions and was not relaxed.

All 24 saved sender traces retained the common 4 Mbps native ceiling at every
decision. **Zero randomized bitrate actions** were assigned. Source and
instrumentation checksums remained pinned throughout the census.

## Transport, clocks and outcome access

All 23 sealed captures passed the registered TURN/TCP, media, exact trace,
clock and terminal-cleanup gates. Each actual-run clock map covered all four
held-out markers; maximum held-out interval width was **3.746 ms**, below the
unchanged 50 ms limit. The failed capture remains failed and is excluded from
the qualified counts.

The 48-session action study was gated off. No treatment session started;
the registered primary and secondary outcome analyzers were not invoked.
No frame-quality, timely-delivery fraction or per-hold relay-cost telemetry
was opened. Census failures are preserved as support/liveness failures.

Consequently V12 yields no estimate of the registered PSNR interaction,
campaign-specific conditional action effects, policy value or superiority
over fixed 0.65. Stable conditional action value remains unestablished.
V10 stays closed; no controller was fitted, tuned or promoted. V11D and all
prior native/synthetic evidence and freezes remain unchanged and unpooled.
V12 is closed as a qualification failure under this registration; no source
substitution, threshold change, added session or replacement was used.

## Preserved evidence

- Frozen confirmatory protocol SHA-256:
  `b96f1aed7d0001dcb6f28faf7d41af4dd0f936534d1b80114189199db9d35929`.
- Support capture index SHA-256:
  `e51b50caf1bc6aeef793badc0fbc7f6f942bd3af23f13e4083913bed91976fbf`.
- Official support gate SHA-256:
  `0f8aa75807507d93f3054a0bdeeda71534a5b23d4465b8a3fa4828d7ce2ef6a2`.
- Official gate: `reports/native-v12-support-census-gate.json`.
- Support-only replay and every campaign/content/cell:
  `reports/native-v12-support-census-summary.json`.
- Raw evidence remains in the external cache and in the private HF dataset
  `p-yan/networkrlcd-results-archive`, namespace
  `native-support-validation-v12-support-20261014-01`, pinned revision
  `489aaefd8d0738745acd9e35d81ed2a24be9ec93`.
- Archive receipt:
  `docs/storage-receipts/native-support-validation-v12-support-20261014-01.json`.
  A fresh remote download verified every archive object and all **1,038 files**;
  no local evidence was deleted, and licensed originals were excluded.
