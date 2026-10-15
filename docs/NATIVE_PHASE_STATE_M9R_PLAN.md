# M9R: actual-observation timing qualification, then fresh phase-state validation

Prospective registration after M9's instrumentation-limited stop at `26ab4ac`.
M9's64 originals and two qualification runs are frozen, privately archived and
unestimable for phase-state prediction. No M9 future labels, state effects,
matched residuals or new representation were analyzed. Its two observation gaps
(301.2/296.8ms) are the only new development evidence used here.

## Instrumentation intervention

The old sampler waited100ms after its preceding observation/processing cycle.
Its excessive intervals exceeded that nominal wait by201.2/196.8ms. These are
unattributed timing excesses, not identified GC or network delays. Of the
prospectively enumerated power-of-two periods100/50/25ms, **25ms** is the largest
for which the maximum observed excess plus the period is below the unchanged
250ms actual-observation limit (201.2+50 exceeds it;201.2+25 does not). This is a
falsifiable timing repair, not a promise that future scheduling pauses are bounded.
The same25ms getStats period already has qualified startup use in M4R/M8/M9.

Use absolute25ms deadlines, skip expired schedule slots without catch-up bursts,
and record scheduled/request/response/sample/ack times and scheduling/getStats
durations for every actual observation. Observe only real getStats returns.
No interpolation, carried values, missing-sample filling or revised gap limit.
Retain rendering, receiver instrumentation, fixed4Mbps encoder/jitter0, exact
native1200kbps startup, source media, controlled service inputs, clocks, TURN/TCP
and cleanup unchanged. The observation fixture has a new cadence; M9R is fresh
native evidence under that declared fixture, not additional independent content
or a continuation/replacement of M9 originals.

The main88s phase requires >=3168 actual observations (90% of nominal40Hz), valid
positive BWE and gaps<=250ms; every request/response must satisfy the recorded
causal ordering and every deadline must lie on the declared25ms grid. This is
stricter acquisition coverage than M9, whose numerical gap/eligibility limits
remain unchanged. Record actual maxima, scheduling lateness and request duration.

## First gate: eight instrumentation-only originals

Fresh2 contents ×2 prefix histories ×2 extreme current-input strata (0.5 and
1.414Mbps; falling/rising) give eight originals, randomized in advance. All must
pass beginning/full clocks, replay, exact initialization/readback, TURN/TCP,
native media progression, actual-observation timing and exact cleanup. They are
excluded from state estimates. Inspect only those support/instrumentation fields.
Do not evaluate phase-state predictions on these runs. A small qualification
panel does not guarantee the64-run gate: every later original must pass itself.
If qualification fails, stop before opening the fresh64-original panel.

## Fresh untouched phase-state panel

Freeze64 new IDs before any M9R capture: two reused licensed contents ×four
unchanged current service inputs ×ascending/descending prefixes ×four independent
originals/history. This panel stays untouched until all eight instrumentation
originals qualify. Randomized within content/repetition blocks, no retries or
replacement originals. Attempt all64; any failed technical original stops state
interpretation. Old M7-family and M8 successor allocations remain closed.

All scientific inputs and candidate predicates are inherited from frozen M9:
10s equal-multiset prefix,24s initial service,64s common service,12.6s original
probe; current wire rates0.5×2**[0,.5,1,1.5]Mbps, initial1.5Mbps for the lower two
and0.5Mbps for the upper two. The horizon remains4×M8's16s rise-t90 envelope.
There is no new fixed conditioning duration, adaptive service recipe or time
extension. Direction remains stratified with current service, not independently
identified. Reuse the unchanged verified130s clips, without looping or new sources.

## Same state definitions and temporal census

B0 is current eligible native BWE. D1 retains the exact M8/M9 past3s >=27 valid
samples/gaps<=250ms, +/-0.125 causal-center caliper, <=0.05 adjacent-second drift
and acknowledged service constant>=3s. P2 retains D1 plus past6s >=54 eligible
samples, the same caliper and <=0.05 last3s-minus-prior3s mean contrast, known
constant service>=6s and age beyond the frozen rise16s/fall2s envelope. All raw
observations enter the past-window and future tests, increasing scrutiny at the
denser cadence. No queue, RTT, encoder, receiver-quality or new state feature.

For the inherited11-sample temporal census, at each prospective cutoff candidate
select eleven **actual** observations backward, with >=90ms spacing
(900ms/(11-1)). Enforce the same >=900ms total span, <=250ms each gap and original
240k..3.8M eligibility; cutoffs remain within endpoint..endpoint+300ms. No
fabricated/coarsened value is introduced. On the legacy >=100ms cadence this
selects the exact same eleven-sample tail. Check equivalence only on verified M8
development observations before capture. The extra observations never count as
additional independent originals or hold members.

First tags on the same6..55s grid remain binding. Future truth uses all actual
native observations through common age63.8s, >=8s verification, the same
causal-center +/-0.125 region and <=0.05 adjacent-second drift. Eight-second
empirical future distributions retain exact inverse-CDF W-infinity, equal weight
per original and the same0.25 bound; higher polling density creates no independent
replication. All original coverage/fixed-target/range/SD/overlap/repeatability,
entry elapsed, clock/replay/probe/readback/cleanup thresholds remain unchanged.
The exact inherited fixed-target H1 and6s/12s probe veto is registered from the
outset (see the accompanying inherited-gate document).

Reuse M9's frozen residual diagnostics, landmark grid, matching calipers,
four-prepaired-member requirement and uncertainty definitions without searching
new features or landmarks. M9R outcomes cannot tune another representation.
If no compact state qualifies, report residuals and coverage before considering
a separate fresh omitted-history study. Conditional residuals remain descriptive
selected-context comparisons; M5's causal result is preserved. No broad network
generalization, permanent-memory claim, bitrate action or controller fitting.

## Provenance, storage and preservation

All main sources, copied analysis, build derivation, protocols, panel IDs, gate
definitions and this plan must be committed before capture. Actual clocks remain
128 training/15 held-out and beginning35/four, <=50ms, with unchanged strict
source/command timing, TURN/TCP and cleanup. Rehash complete seals before
telemetry. Frame/receiver-quality files remain opaque. Source-hash every prior
tracked file at completed M9 and audit its new pinned archive as well as the
earlier six. Preserve every failure and all prior freezes without deletions.

Native data and archive staging remain external. Denser logging is prospectively
budgeted at <=3GB native output and <=10GB incremental external peak including
one tar and one fresh verification download. Require >=12GB free before capture
and account for projected bytes with the storage helper. The repository remains
below the owner-approved10GB cap. Check footprint after instrumentation before
opening validation. No licensed original/derivative is pruned. New private archive
namespace, immutable revision, fresh size/SHA checks for every object and member;
commit the complete result and preservation receipt cleanly.
