# M4R: prospective startup and clock instrumentation qualification

Anchor **`472ed01`**; scientific M3 registration `f435507` stays unchanged.
M3 is instrumentation-limited and unestimable. Its incomplete comparisons
are not evidence for or against prefix memory or convergence. M4R reads only
support/instrumentation variables. It fits no predictors, redesigns no controller
state, and opens no action, quality, delivery-cost or controller analysis.

Commit this plan, implementation, runtime preflight and complete two-stage
registration before the first capture. All files at `472ed01` are hash-pinned
and preserved. No M3 capture is repaired, replaced or requalified.

## Separate revision after the closed M4 feasibility failure

M4 at `ad9b4da` qualified two of four feasibility originals. Two failed before
prefix service because native selected-pair stats remained `in-progress` after
`connectionState=connected`. Its 28-session qualification stayed untouched.
The failed result and verified archive are frozen at `472ed01`.

M4R is a fresh 32-session panel. No M4 success enters its counts. The sole
acquisition change is a **bounded inactive readiness wait**: poll both native
selected-pair records every 25 ms for at most **2,000 ms**, requiring the original
nominated, `succeeded`, loopback TURN/TCP relay endpoints and positive bidirectional
byte counters. Record every probe incrementally in `transport_readiness.jsonl`
and the instrumentation stream. The encoder stays inactive; no reconnect,
new peer, native-estimator reset, changed predicate or original-trial retry is
permitted. The registered 0/750 ms challenge begins only after strict readiness.
All initialization, clock, media, support, replay, readback and cleanup gates
below are unchanged. Failure at the deadline remains a failed original.

## Question and smallest staged panel

Can a new acquisition sequence observe the actual startup estimator, satisfy
clock mapping from the beginning, and complete every registered content/prefix
condition under the existing technical and support thresholds?

Use the same two reused 45-second Kampar/Volga clips and source-derived
ascending/descending first-ten-rate prefixes as M3, with their identical
original measured suffix from bin 10 onward. These are instrumentation
development sources. No source is treated as new independent evidence.

There are **32 fresh sessions**, eight in each content × prefix cell:
four with **0 ms** and four with **750 ms** additional inactive setup delay.
The delay deliberately challenges acquisition scheduling while media encoding
is held inactive; it is not an extra conditioning period for later BWE.

1. **Feasibility:** four sessions, one per content/prefix condition, all with
   the 750 ms challenge. Complete all four original attempts even after failure.
2. Only if all four qualify, run **qualification:** 28 more original sessions,
   seven per cell (four immediate, three delayed). All must qualify.

Use seed **20261113**, fresh native processes/connections/queues per session,
content-pair order shuffled within each repetition, and fair complementary
prefix slot order within each pair. Freeze every panel and order before capture.
No retries, replacements, added attempts or favorable subsets. Failure in the
first stage leaves the second stage untouched and closes M4R as failed. Any
second-stage failure closes the overall qualification after completing its
28 original attempts. Qualification requires all 32 and all four cells, with
the exact four-plus-four delay counts.

M3 had five clock failures among 41 sealed Kampar sessions. At that development
rate, 16 new Kampar sessions have probability `1-(36/41)^16 = 0.8752` of detecting
at least one failure. An 80% detection target needs at least 13 Kampar sessions;
balancing both prefixes and both delay conditions makes 16 the smallest multiple
of four meeting it, hence 32 total sessions. This is a design calculation from
limited development evidence, not a reliable estimate of the true failure rate.
Zero failures among 32 has a one-sided 95% binomial upper failure bound of about
8.94%, with wider cell-specific bounds. It cannot guarantee future 84-session
completion. Actual gates remain mandatory in any subsequent causal panel.
Rare initialization failures are addressed directly by the setup-delay challenge,
continuous observability and exact native-readback requirements, not a claimed
powered estimate of a rare failure probability.

## Acquisition change and explicit estimator evolution

New recorder: `benchmarks/native_m4r/prefix_instrumentation_episode_m4r.mjs`,
derived from the immutable M2 recorder in a separate directory. Do not modify
the frozen RTC/M2/M3 files or the managed browser policy.

Negotiate a VP8 send-only transceiver with its RTP encoding **inactive** and
4 Mbps ceiling. Gather and nominate authenticated TURN/TCP, verify selected
relay-backed pairs, then exercise the registered 0/750 ms delay while inactive.
Require the pre-activation readback to remain inactive at 4 Mbps, with no
encoded frames/payload bytes (explicitly absent counters are recorded).

Configure the unchanged fixed encoder and recorded-video playback before
activation. Activate the encoder, request frames, and observe initialization
immediately. While no positive native estimate/unique outbound stream is yet
observable, sample at 5 ms intervals for **at most 100 ms**. Record every missing
or available value. The **first positive active native BWE** must already equal
**1,200,000 ±1 bps**. A positive wrong value fails immediately; never wait for a
wrong value to return to the target. A missing estimate/stream at the deadline
fails. Then begin the original measurement immediately and require the first
measured sender BWE and measurement-start native snapshot to equal the same
target, with the same selected pair and active 4 Mbps encoder readbacks.
This preserves the actual native initialization requirement. SDP acceptance
alone is insufficient, and no missing value is replaced with the requested
target. The inactive setup is a prospectively different common acquisition
history; M4R/M5 cannot be pooled with M3 as exchangeable startup replicates.

From **before SDP** through 1,500 ms after measurement start, sample startup
stats at 25 ms, with no overlapping polling requests and a maximum allowed
poll-response gap of **250 ms**. Require an explicit pre-SDP sample and observed
evolution through at least 1,000 ms after measurement start. Record request/
response times, connection/ICE state, media and actual encoder activation/cap,
selected-pair identity/state/nomination, native stats timestamp/BWE, outbound
stream count, encoded frames, payload bytes/packets, and errors. Missing values
remain null. The first sample, initialization success/failure and latency are
explicit. Native stats errors fail qualification.

Persist startup samples and both sides of extra clock exchanges incrementally
to `instrument_stream.jsonl` as they arrive. Successful captures also preserve
the complete startup timeline and separate clock arrays. Failed and interrupted
evidence is sealed and retained. This avoids depending solely on an end-of-run
summary for startup observability.

## Independent clock training from the beginning

Keep all twelve original marker exchanges and their original four held-out
phase/midpoint markers. Add fixed training brackets, not extra fitted tolerance:

- At session open, before SDP, and after connection/delay while inactive:
  four training exchanges, one independent held-out exchange, four training
  exchanges at each location.
- Immediately before and after each of the three original phase exchanges,
  and the existing final-block midpoint exchange: four training exchanges on
  each side. The original phase/midpoint exchanges remain held out.

This gives **71 total exchanges: 64 training and seven independent holdouts**.
All roles and locations are fixed before capture. Preserve slope **[0.98,1.02]**,
100% held-out coverage for **every training-feasible affine vertex**, maximum
interval width **50 ms**, timestamp tolerance **1 ms**, and the unchanged affine
constraint implementation. Never fit with held-out exchanges or substitute
post hoc marker selections. Tightening the training envelope with new independent
measurements changes acquisition information, not these acceptance criteria.

Also require a **beginning-of-session certificate**, without later training:
35 training exchanges (the startup brackets, the first-phase brackets, and
original training markers m0001/m0002/m0004) must cover the three startup
holdouts and original first phase marker m0003, using all the same thresholds.
The full-session certificate must cover all seven holdouts. Both must pass.
The old eight-training/four-holdout M3 map is retained only as a diagnostic
for this new acquisition version; it does not change M3's failed decisions.

## Inherited technical/support gates

Preserve authenticated relay-only TURN/TCP under managed
`WebRtcIPHandling=disable_non_proxied_udp`, selected-pair readbacks, and native
media progress in every phase. No direct-UDP fallback or policy change.
Keep 45-second licensed clips without looping, the fixed VP8 recipe, 4 Mbps
measurement cap, zero jitter, 100 ms standard sender polls, 5 Mbps pre-trace
service, 25 ms propagation, 30,000-byte queue and three phases
**[12000,12000,12600] ms**. Require all 36 exact source rates with ≤150 ms tick
error. No bitrate assignments.

The original admission history remains eleven valid samples in **[18000,18300]
ms**, span ≥900 ms, positive gaps ≤250 ms, each BWE in **[240000,3800000] bps**.
Also verify identical eligibility at the predeclared 24/30/36-second windows
needed by the future prefix-memory protocol. M4R checks eligibility only: it
does not compare later BWE values, distributions, prefix effects or repeat spreads.
Existing 0.25-octave repeatability and future full-panel range/common-support
requirements remain unchanged and cannot be supplied by this technical screen.

Preserve the post-measurement 10 Mbps drain, ≤2 seconds, empty queues, exact
served/forwarded counts, zero send errors and ≤1e-6-byte conservation error.
Verify every session file seal before decoding permitted instrumentation data.
No failed session is a treatment or quality outcome.

## Prospective fresh prefix-memory validation

Only an overall **32/32 M4R pass** authorizes creating a new validation root,
allocation, protocol or capture. Keep it absent and untouched beforehand.
Use the qualified instrument with a common 0 ms setup delay, and freeze a fresh
21-pair-per-content allocation (**84 sessions**) before capture. Keep M3's
prefix rates, identical later measured suffix, continuous BWE definition,
18/24/30/36-second histories, all-original-42-per-content rule, pair suffix
capacity-exposure bound ≤0.01 octaves, 0.25-octave full-spread/convergence limits,
exact paired W1 randomization, primary alpha 0.025 per content, late Holm
gatekeeping and pair-bootstrap uncertainty. Prespecify fresh seeds and all
implementation before its first session. Do not fit any predictor in that
validation, even after a significant prefix effect. It tests history and
convergence only. Fresh captures on these reused sources are not an independent
content/network population panel, and no earlier captures enter its estimates.

If the fresh panel fails qualification, retain all originals and report the
registered comparisons unestimable. If estimable, report each content and
registered time separately; nonsignificance is not convergence. A valid history
result does not by itself establish causal action value or controller readiness.

## Execution, durability and storage

Run prepare/verify, commit, then feasibility. Launch the capture coordinator
in a separate process session with file-backed stdout/stderr so an exec-client
disconnect does not terminate it. Capture remains sequential, original-order
and bounded at 110 seconds per native attempt. Never start a second coordinator
for an existing sessions root or stop an active capture. A real platform failure
remains a failed original; it cannot be replaced or hidden by a new seal.

Only a passing feasibility gate permits the frozen qualification stage. Only
the complete passing overall gate permits preparing the fresh causal panel.

Raw roots: `~/.cache/networkrlcd/native-prefix-instrumentation-m4r/feasibility`
and `.../qualification`. Reserve **2 GB** new external working/archive/fresh-
verification bytes for this workflow; keep the project below 10 GB and all
licensed originals external. Archive every completed stage, including failures,
in fresh immutable private `p-yan/networkrlcd-results-archive` namespaces. Pin
revisions and freshly verify every archive object and member checksum. Delete
no active or unarchived evidence. Keep compact protocols, qualification reports,
source hashes and receipts in Git. No outcomes or sources are pooled.
