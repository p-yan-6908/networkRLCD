# M9: prospective causal phase state and long-horizon native stability

Status: prospective support-only registration. All analysis code, inputs, original
IDs, gates and this plan must be committed before any M9 browser session. M8 is
development evidence; M9 uses fresh native contexts, not independent new content
or measured-network sources. M8's `m9-from-m8` successor allocation and all older
closed validations remain uninstantiated. There is no action stage.

## Question and finite design

Can a small causal phase-aware state identify future-stable, reproducible native
BWE contexts across the ascending/descending equal-service-multiset prefix
histories? Current BWE (B0) and the unchanged failed M8 D1 rule are baselines.
No controller, action-value, receiver quality or delivery outcomes are analyzed.
No M6R validation or older untouched panel is used for new-state development.

Two reused licensed 130s clips, four prospectively fixed current wire-service
levels `0.5 * 2**x` Mbps for x = 0, 0.5, 1, 1.5, two prefix histories and four
fresh originals/history give **64** validation sessions. This is the minimum
factorial with the existing four-member count, four regions and both contents.
Within each content/repeat block, all eight prefix/input combinations are
randomly ordered; the order is frozen. No retries or replacement originals.

Each run has the same 10s ascending/descending measured-source prefix as M8,
24s of fixed initial service (1.5Mbps for x<1, 0.5Mbps otherwise), then **64s of
common service**, then the original 12.6s measured-source probe. Both prefix
histories have identical service after the prefix. Low input strata therefore
have a fall and high input strata a rise. Direction is intentionally stratified
with current service, not independently identified; no new rise/fall causal
contrast is inferred. The controlled service is an owned experimental input,
not a deployable oracle for Internet capacity. Sender cap remains 4Mbps,
initialization 1200kbps, jitter target zero; browser/profile, TURN and owned queues
are fresh each original. Content is never looped.

## Prospectively chosen horizon, not a conditioning recipe

Read only M8's registered response tables and verified support records. Let R be
the ceiling, in seconds, of the maximum observed common-rise t90 upper bound,
across both contents and all M8 originals: R=16s. The observation horizon is
**4R=64s**. This spans four observed slow response scales and exceeds both M8's
24s plateaus and M5's 36s common suffix. It can observe settling onsets through
55s, followed by at least eight seconds of verification. This finite budget does
not assume stationarity, guarantee convergence or prescribe a fixed wait. It is
never extended after examining M9. Raw source clips need no new derivation.

## Causal features and frozen predictions

At each integer common-plateau age **6..55s**, take the original 11-sample census
(span >=900ms, cutoff within endpoint..endpoint+300ms, gaps <=250ms, eligible BWE
240k..3.8Mbps). State uses only samples/acknowledgements at or before the cutoff.
No full-session clock fit is used to construct an online input feature.

- **B0**: original eligible instantaneous log2(BWE/500k), always tags if census
  exists. Its center is the last native sample, not a future mean.
- **D1**: unchanged M8 rule: past 3s >=27 eligible samples/gaps<=250ms, each within
  +/-0.125 octave of current center, latest 1s mean minus preceding 1s mean
  absolute <=0.05 octave, acknowledged service constant >=3s.
- **P2**, the sole new prediction rule: D1, plus past 6s >=54 eligible samples,
  all within the same +/-0.125 region, absolute latest 3s mean minus preceding
  3s mean <=0.05 octave, known service constant throughout those six seconds,
  and acknowledged last-change age divided by the M8 direction-specific rounded
  t90 envelope >=1 (rise16s, fall2s). The last true change, not a no-change command,
  defines age and direction. All thresholds are frozen; no fit/search on M9.

The compact observable vector for matching is current x, recent 1s mean drift,
the 3s-versus-previous-3s contrast, direction, acknowledged elapsed age, and
past-6/past-16s mean log controlled service. These two service integrals use only
acknowledged inputs; their windows start after the initial-service acknowledgement.
No prefix/content label,
future service/sample, queue, RTT, throughput or encoder feature enters state.
P2's rule is a falsifiable conservative prediction, not a learned state. M8 had
no positive settling labels, so it cannot calibrate a positive predictor.

## Primary future stability and common-support decision

For each method use its **first causal tag** on the grid in each original. No
future-guided choice, retrospective retry or best age. Truth uses the unchanged
M8 +/-0.125 causal-center caliper, original BWE bounds and sample/gap gates, and
absolute adjacent 1s-mean drift <=0.05 at every fixed whole second from +2s.
Verification continues to common age63.8s and must last >=8s. All later samples
are labels only. Predictions at every grid point are also reported, with their
nested dependence explicit. They cannot rescue a failed first-tag rule.

Qualification requires all 64 originals technically qualified; a first tag and
verified future for every original; four members/history in every content/input
cell; original fixed target membership +/-0.125 at entry; within-cell full
current-census repeat spread <=0.25 octave, ascending/descending empirical
W-infinity <=0.25, actual-current versus census difference <=0.25; matched entry
elapsed spread <=250ms; and future empirical BWE-distribution W-infinity <=0.25.
Future distributions use the next eight seconds, all native samples, separately
by original and prefix; W-infinity uses the exact inverse empirical CDF over all
probability-mass intervals (101 fixed quantiles are retained for display only).
The pooled prefix distribution gives equal weight to each of
its four originals; it never supplies independent sample counts. Within-prefix
pairwise future W-infinity must also <=0.25.

For each content/prefix/repetition, the four input-cell census means must have
range >=1 octave and sample SD >=0.35; the intersection of all these profile
intervals must be >=0.5 octave. Preserve the known-input/probe fidelity gates
(<=0.01 octave exposure difference), exact readback, full and beginning held-out
clock <=50ms, sender gaps<=250ms, strict TURN/TCP, managed-policy hashes, startup
and exact post-cutoff cleanup. Any failed original fails the technical stage;
all allocated originals are still attempted, retained and counted. If machinery
fails, stop state interpretation. Do not count failed ICE as state evidence.

This is a conservative state-support experiment, not action permission. Even a
qualified P2 supplies a design for a **new** independent conditioning validation;
it does not authorize opening either old successor panel or fitting a controller.
No new fixed duration is inferred from a favorable late window.

## Registered diagnostics if compact state fails

Report per-content/input/history first-tag retention, false tags, future-caliper
excursions, drift failures and first future-verified D1 onset on the 6..55 grid
(right-censored if none). An onset found using future labels is descriptive,
never a prospective state. Report all trajectories/late-window drift/range at
ages16,24,32,40,48,56,63 seconds without changing the protocol.

At fixed ages **6,12,18,24,32,40,48,55s**, compare the four prepaired independent
repeat pairs in each content/input cell. B0 matching: |current-x difference|
<=0.25. Compact matching additionally requires drift/long-contrast differences
<=0.05 each, direction equal, acknowledged age difference<=250ms, and both past
service-mean differences<=0.01 octave. Eligibility/sampling remain unchanged.
All four pairs are required for a covered stratum. No replacement matching.
For each matched pair, report subsequent eight-second mean-x difference, change
from current x, empirical W-infinity and maximum 1s-bin future-mean difference.
Quantify the unexplained prefix residual after this causal matching, separately
by content/service/age, including all dropped counts. Conditional residuals are
descriptive selected-context comparisons, not new randomized causal estimates.
Unconditional prefix differences retain randomized-history interpretation under
this specific controlled schedule. Four paired values, their range, and exact
sign-flip mean uncertainty (16 assignments) are retained; neither native polls
nor repeated landmarks are independent replications. No pooling into broad
network/content populations and no claims of permanent memory.

If none qualifies, quantify these residuals before considering a separate,
prospectively registered queue/RTT/encoder study. No additional feature search
on these validation captures and no follow-on action sessions.

## Qualification, storage and preservation

Two separate instrumentation originals (one falling, one rising, both contents)
must qualify the modified schedule and clocks before the 64 untouched validation
originals. These two are excluded from state estimates. Acquisition/analysis
programs and all configurations are source-hashed and committed beforehand.
Rehash complete session seals before telemetry; frame/receiver-quality files
remain opaque. Preserve failures without resealing them to hide missing files.
All tracked files at completed M8 `b707226` are frozen by SHA-256. Record all old
closed panel/config hashes and verify no session directory was created.

Raw data/staging stay under `~/.cache/networkrlcd/`, bounded incremental budget
3GB including one tar and one fresh verification download; planned native output
<=1GB, with disk/storage checks first. Fresh private archive namespace, immutable
revision, every object and every member SHA/size freshly verified. Keep licensed
originals, all old derivatives and all raw evidence; delete zero evidence files.
Commit the result, preservation audit, archive receipt and next decision cleanly.
