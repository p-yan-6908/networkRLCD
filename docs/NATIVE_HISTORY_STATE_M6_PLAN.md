# M6: prospective observable-history state support screen

Anchor **`ad0bf338b76df23ec190e5bdb71d4cfe822338b2`**. M5 establishes a
randomized prefix effect on later native BWE for two reused contents under one
common LTE-source suffix. Its effects change with content/time and do not pass
registered sustained convergence by 36 seconds. Preserve M5 and every prior
freeze. This study does not claim permanent memory, identify a unique mediator,
reopen V13, analyze bitrate-action value or fit a controller.

## Question, stages and independence

Can a small **observable past-history** matching representation improve
future native BWE repeatability and reduce residual cross-prefix distribution
differences compared with instantaneous BWE alone, without destroying overlap?

1. Commit this design, code, calipers, selection rules and input verification
   **before** extracting new M5 history features or comparing candidate states.
2. Use all qualified M5 captures **only as development**. Select one representation
   through the fixed rule below. No M3, M4/M4R or synthetic M1 data are pooled.
3. Freeze/commit the selected fields, every center and all new allocation/panels
   before any fresh native capture. The new 32-session panel is empty and does
   not exist during candidate selection. No native selection feedback or tuning.
4. Run all 32 originals with the unchanged M4R recorder and all technical gates.
   Freeze the current-state membership gate before opening conditional future
   BWE estimates. Failed coverage closes the screen; no favorable subset rescue.

The finite screen is deliberately support-only. Its future response is observed
BWE under the unchanged 4 Mbps cap, not delivery cost, QoE, frame quality or an
action outcome. Past encoder timing/rate are instrumentation covariates. There
is no fitted prediction or policy model; state centers/calipers define matches.

These are **fresh captures of reused two clips/one LTE source**. Their sampling
unit is a capture pair, not a new source. The new panel does not establish broad
network or independent-content generalization. Fixed landmark/content strata
are retained rather than pooled as independent evidence.

## Existing data, access and integrity

Before permitted telemetry decoding, freshly fetch M5's pinned remote file index
at revision `0f4da165bcd87ace87616d564cfe949eaff95d47`, verify its receipt size/SHA,
then verify every retained local file against it and all session seals. Only the
required namespace is accessed. Record HTTPS/private authentication status and
credential availability without values. Runtime binaries/configuration must
match the qualified M5 runtime; keep managed browser policy and TURN/TCP.

No original media is downloaded, deleted or uploaded anew. Preserve every prior
tracked file at the anchor by SHA-256, all negative studies and native/synthetic
separation. New raw captures, derived support tables and archive staging stay
external under `~/.cache/networkrlcd/native-history-state-m6/`, within a **2 GB
new-workflow plan**; the project must remain below 10 GB.

## Causal information boundary and measured fields

Use the first eligible history at each unchanged window [18000,18300],
[24000,24300], [30000,30300], [36000,36300] ms. The current cutoffs are the actual
history endpoints at 18/24/30 seconds; each future response is the original
eleven-sample mean log2(BWE/500000) at 24/30/36 seconds. Its definition, 240–3800
kbps bounds, eleven samples, 900 ms span and 250 ms maximum gaps stay unchanged.

The baseline **x** is the last native BWE observation at the current cutoff,
in log2(BWE/500000), genuinely instantaneous rather than an averaged baseline.
Every other state field uses only observations at/before that cutoff. Sender
history windows are the last two seconds and preceding two seconds. Each needs
at least 17 samples, gaps ≤250 ms, and ≥80% valid observations for a field.
Unavailable fields remain missing, never filled from an oracle or future data.

| Field | Definition | Fixed caliper |
| --- | --- | ---: |
| x | Current native log2(BWE/500000) | 0.125 octaves |
| trend | Mean log BWE in last 2 s minus mean in preceding 2 s | 0.125 octaves |
| send | log2(mean native RTP payload send bps / 500000), last 2 s | 0.125 octaves |
| rtt | Mean linked RTCP RTT, last 2 s | 10 ms |
| rtt_drift | Last-2-s RTT mean minus preceding-2-s mean | 10 ms |
| fps | Mean native encoded frames/s, last 2 s | 1.5 frames/s |
| encode | Mean native encode ms/frame, last 2 s | 1 ms |
| forward | log2(relay-forwarded wire bps / 500000), guarded past 2 s | 0.125 octaves |
| queue | Time-integrated relay queue / (duration × 30000 bytes) | 0.1 |
| drop | Relay overflow wire bytes / offered wire bytes, guarded past 2 s | 0.005 |

Native RTT must be valid with known observed feedback age ≤2000 ms. This is
linked RTCP RTT, not STUN RTT or exact feedback arrival time. Native packet-loss
counters and end-to-end delivered-throughput counters were not retained in M5;
do not invent them. Relay overflow is not receiver loss, and relay forwarding is
not timely delivery or QoE. Native RTP send rate is not delivered throughput.

Relay-derived fields are explicitly **relay-assisted**, not sender-only state.
Use only the independent **35-training beginning clock polygon**, whose exchanges
finish before the first cutoff. Future clock markers, trace capacities, prefix
identity, future service, receiver pixels and quality labels cannot be features.
At each cutoff retain only complete relay events in the conservative mapped
interval [cutoff−2100,cutoff−100] ms: lower node bound is the maximum mapped
lower boundary, upper node bound is the minimum mapped upper boundary. Require
boundary uncertainty ≤50 ms; queue integration needs ≥99% complete-interval
coverage. This 100 ms guard enforces temporal order, not a demonstrated online
feedback latency guarantee. Relay-assisted success would require a separately
qualified feedback path before a sender action study.

Cap readbacks (4 Mbps), receiver target (zero), elapsed landmark, initial native
BWE (1.2 Mbps) and setup delay (zero) are fixed controls, recorded and audited.
Their invariance cannot supply evidence for a learned cap/history effect.
Elapsed time is an exact 18/24/30-second stratum; no absolute session identifier,
content identity, run order or prefix label enters a distance. Content strata
remain separate, and different times cannot be matched to exploit future service.

## Finite candidates and development selection

Keep `b0_instantaneous={x}` as baseline. Two-dimensional candidates add exactly
one of: trend, send, rtt_drift, rtt, encode, fps, forward, queue, drop. Three-
dimensional candidates add exactly: (trend,send), (trend,rtt_drift),
(trend,queue), or (forward,queue). No other features, transforms, bandwidths,
calipers, representations or predictors may be tried in this registration.

For each content × current-landmark stratum, choose a baseline x center from
observed development current x values. Maximize the smaller prefix count within
±0.125; then maximize total count; then use trial-ID lexical order. For each
history candidate keep that exact x center. Propose its extra coordinate values
only from baseline-eligible current observations. Maximize smaller prefix count,
then total count, then the first lexical trial proposal. Future BWE does not
select centers. Match by the conjunction of all physical calipers, with no
distance-weight fitting, no extrapolation and no nearest-neighbor backoff.

Development coverage requires ≥6 matches in each prefix and ≥80% of the baseline
count in **each** prefix, separately for all six strata. Rank candidates first
by the number of strata meeting coverage, then number with both prefixes
nonempty, then smallest worst future within-prefix full spread, then smallest
equal-stratum mean future W1, then sender-only preference and fixed candidate
name. The equal-stratum number is a development selection score, not a pooled
effect or generalization estimate. Report every candidate, missing field,
coverage and future metric, including negative results.

Choose the best two-dimensional candidate. Permit the best three-dimensional
candidate only if it loses no coverage/nonempty strata and reduces worst future
spread by **at least 20%**. Otherwise retain the smaller representation. This
selects a falsifiable candidate, not a qualified state. Even a development failure
may be challenged once on the fixed fresh panel; that cannot authorize action
work. Freeze all six centers for the selected state and baseline in Git before
fresh capture. No alternative gets a confirmatory turn if the selection fails.

## Fresh native allocation and entire-panel acquisition gates

Run **eight original adjacent prefix pairs per content**, 32 sessions total,
seed **20261117**. Each repetition shuffles the two content pairs and uses a
fair complementary prefix slot bit. Every session uses new native processes,
TURN server, peer connection and empty queue. Keep M5's identical constructed
prefixes, 14.112 Mbps·s prefix integral and unchanged measured suffix bins 10–35.
Keep common 0 ms inactive delay, 1.2 Mbps native initialization, 4 Mbps ceiling,
zero jitter, 5 Mbps pre-trace service, 25 ms propagation, 30000-byte queue,
36 rate ticks and phases [12000,12000,12600] ms. No bitrate actions are assigned.

All **32** original acquisitions must pass all M4R startup/readback/media/
transport/clock/support/replay/cleanup gates, including the full 64-training/
seven-held and beginning 35-training/four-held certificates. Keep the unchanged
slope [0.98,1.02], every-vertex held-out coverage, 1 ms timestamp tolerance and
50 ms width limit. Keep strict TURN/TCP readiness ≤2000 ms, first positive active
native initialization ±1 bps within 100 ms, startup gaps ≤250 ms and existing
exact cleanup/byte-conservation gates. Preserve failed attempts; never treat them
as state responses or retry/replace them. Complete all originals before closing.

All **16 original suffix pairs** must pass M5's exact unchanged suffix-array and
actual mapped [11000,T] capacity-exposure bound ≤0.01 octaves at all four endpoints.
No state analysis if the entire acquisition/fidelity gate fails.

## Frozen membership before future-response estimates

Apply baseline and selected-state centers/predicates to fresh **precutoff**
features only. For every one of six content/landmark strata require:

1. At least **four of the eight** originals in **each prefix** match the baseline
   and at least four match the selected history state (≥50% original occupancy).
2. Selected-state occupancy retains **≥80% of the baseline count in each prefix**.
3. All qualifying matches are retained, without selecting a favorable four or
   removing a later extreme. Every unmatched original remains in the denominator
   and archive. Missing selected features count as unmatched, not failed ICE.

The 32 count is the smallest balanced eight-per-condition screen providing
four matched native repeats per prefix at 50% occupancy, with the same capture
also checking all three future horizons. It is a finite technical/conditional
support screen, not powered population equivalence or broad state sufficiency.
It does not reinterpret M5's unconditional 21-repeat convergence failure.

Write/hash the full membership gate before conditional future values are joined.
If any stratum fails, all conditional future response comparisons are unestimable
in this validation. Diagnose only past support/missingness/occupancy; no retuning,
re-centering, altered calipers, dropped strata or additional sessions.

## Registered future support and comparison with baseline

Only after every previous gate passes, retain all matched future BWE responses
for each stratum/representation separately. Report arm counts, all values and
full spreads, descending-minus-ascending mean, empirical W1 and empirical W∞.
Use exact empirical CDF/quantile distances also for unequal match counts.

Resample the **eight original capture pairs**, keeping both prefix slots and
the fixed membership, for 10000 bootstrap draws with seed **20261120 +
100×representation-index + stratum-index** (baseline first, content lexical,
then 18/24/30 seconds). Report empty-arm draw counts; require ≥9500 valid draws.
Publish mean percentile 95% intervals and W1 upper 97.5% percentiles. These are
fixed-recipe capture uncertainty, not population intervals or a randomization
test after conditioning on a post-prefix variable.

All six selected-state future strata must satisfy unchanged **0.25-octave**
numerical requirements: each prefix's full matched-repeat spread ≤0.25,
W∞ ≤0.25, mean 95% interval wholly within ±0.25 and W1 upper 97.5% ≤0.25.
Report every component for baseline and history state. A nonsignificant
prefix comparison, good average fit or per-stratum success cannot replace these.

Separately in each content, require mean W1 across its three landmarks to fall
by **≥20%** versus its baseline, with no individual landmark W1 worsening by
more than 10%. This fixed summary is not a pooled content estimate. State-screen
qualification requires both contents' improvement rules and every selected
state's coverage and repeatability component. No fallback winner or new fit.

This evaluates conditional predictive reproducibility. Prefix is randomized,
but matching variables occur after that prefix. A smaller conditional prefix
difference is **not** an identified direct causal effect, proof of mediation,
Markov sufficiency or stable bitrate action value.

## Decision and preservation

Any failure closes this registered screen without relaxing its gates or
reopening prior studies. If the finite screen passes, carry only the frozen
representation into a separately preregistered **untouched multi-profile native
support census**. The original four-profile range ≥1 octave, SD ≥0.35,
cross-context overlap ≥0.5, actual repeatability and all transport/clock/readback/
cleanup requirements remain necessary before any action experiment. One LTE
suffix cannot establish them. Relay-assisted state additionally needs an actual
qualified causal feedback path. Do not fit or promote a controller.

Keep new raw captures, all development candidate results, failed/unmatched
sessions, memberships, source hashes and logs in the external root. Archive
complete new evidence in a fresh private HF namespace, pin the revision, freshly
download every archive object and verify every member checksum. Preserve prior
archives/freezes and licensed media. Commit compact reports, figures, receipts
and the final preservation audit. Zero action/QoE outcomes are opened.
