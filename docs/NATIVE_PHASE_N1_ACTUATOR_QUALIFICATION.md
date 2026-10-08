# Native Phase N1: actuator qualification (preregistration)

**Registered 2026-10-07, before any N1 data exists. Nothing has been collected, no controller
or model is changed, and none is fitted.** The 31-file controller freeze
(`configs/native_controller_freeze_v1.json`) applies unchanged. The 96-unit source panel
([Phase N2](NATIVE_ACTUATOR_POWERED_PANEL_V1.md)) keeps its config, gates and reserved units.

- Registration: `configs/native_actuator_qualification_n1.json`
- Estimator, test and blinded rule: `src/media_rl/native_actuator_qualification.py`
- Planner, blinded capture, interim and final analysis: `src/media_rl/native_actuator_qualification_panel.py`
- Hash record of all of the above and this document: `configs/native_actuator_qualification_n1_freeze.json`

## Question

Does the requested bitrate ratio separate the actual encoded output rate on the native stack?
N1 answers only that. It makes no claim about delivered quality, about a scalar
rate-to-QoE effect, or about any state-by-action preference. Those stay in N2 and later.

N1 exists because N2 is expensive: 96 independent licensed sources and a QoE study. If the
three requested ratios do not move the encoder apart, that acquisition is not worth making.
Under N2's own planning assumptions its first stage has simulated power 1.0 at 16 sources per
cell, so the 96 is driven by its cell structure and its QoE stage, not by the question here.

## Protocol held fixed

Everything below is the existing diagnostic
([identification V1](NATIVE_ACTUATOR_IDENTIFICATION_V1.md)), unchanged:

- Frozen controller; common legacy inference shadow-only, never the physical actor.
- Arms IID from {0.65, 0.85, 1.05} x the sender's BWE observed at assignment, propensity 1/3
  each, BWE frozen for the 3,000 ms ACK-relative hold, six holds per fresh native peer.
- Outcome window ACK+1,800 to ACK+2,600 ms. Zero-output, aliased and non-plateau windows stay
  in. Censored cohorts are kept as assigned rows with a reason.
- The four configured network regimes and their 6/6/6.6 s phases.
- The same collector, raw auditor and screening tool, called without modification.

The only design counts N1 sets are how many sources, and how many fresh peers per source.

## Confirmatory endpoint

The sole confirmatory actuator endpoint is **actual encoded video payload rate before RTP
packetisation, divided by the frozen BWE**. RTP send rate, first-stage F, partial R-squared,
settling and plateau diagnostics are secondary and never change the outcome.

## Clustering unit

The unit of inference is the **source cluster**, defined exactly as in N2: a connected
component of title, capture group and parent/media lineage. Each source cluster contributes
one representative 20-second window and one bivariate observation, its two adjacent contrasts.
Every degree of freedom below counts source clusters.

Peers and holds are repeated measurements inside a source. There are ten fresh peers per
regime, each with six holds, and their only role is to reduce within-source noise. Excerpts,
encodes, resolutions, regimes, peers, holds and cohorts never add independent units.

## Minimum content and capture requirements

| Requirement | Stage 1 (minimum) | Maximum after the blinded rule |
|---|---:|---:|
| Independent source clusters | **12** (4 / 4 / 4 by complexity tercile) | **24** (8 / 8 / 8) |
| Fresh native peers (4 regimes x 10 per source) | 480 | 960 |
| Assigned cohorts (6 holds per peer) | 2,880 | 5,760 |
| Expected cohorts per source x arm | 80 | 80 |

Each source must satisfy N2's existing asset rules: explicit per-asset rights evidence
(CC BY 4.0, CC BY 3.0 or CC0 1.0), reviewed lineage, at least 80 seconds of native-ready
H.264 media, and no overlap with any earlier native role. In addition:

- **Disjoint from N2.** A sealed N1 plan reserves its sources through the existing
  reservation scan, so N2's unchanged planner excludes them, and a second N1 plan cannot draw
  them again.
- **Complexity strata** are terciles of the existing preassignment screening score, one vote
  per source cluster. One screening of the whole N1 pool fixes them before any capture.
- **Allocation.** Sources are drawn by a seeded random draw within terciles and interleaved
  into balanced blocks of three, one per tercile. The first four blocks are stage one. Later
  blocks are the reserve, so any extension keeps the terciles at 5/5/5, 6/6/6, 7/7/7 or 8/8/8.
- **Reserve coverage is fixed at planning.** Ideally the pool holds 24 eligible sources. If
  it holds fewer, the blinded rule's maximum is the number the sealed plan holds, fixed before
  any capture and never changed afterwards. With no reserve at all N1 is the fixed-12 design
  of the power table.

**Acquisition is N1-first.** The inventory holds zero verified eligible source clusters, and
Discovery V2 lists 110 unverified candidate clusters. The N1 queue
(`media-actuator-qualification queue`) puts 36 of them in a seeded random order, about 6.5 GB
by catalogue sizes, to be verified in that order until four, then eight, sources per tercile
are eligible. Nothing in the queue has been downloaded, rights-reviewed or measured. Many
Commons originals are WebM, so producing native-ready H.264 is part of verification. The
further 96 sources for N2 are not pursued until N1 has an outcome.

## Estimand

For source cluster `j`, regime `r` and arm `z`, let `m_j(r, z)` be the expected value of
`encoded rate / frozen BWE` over fresh peers, holds and the randomisation. The two
confirmatory estimands weight the three complexity strata equally and the four network
regimes equally:

```text
theta_lower = (1/3) * sum over strata s of  E[ (1/4) * sum over regimes r of ( m_j(r, 0.85) - m_j(r, 0.65) ) | j in s ]
theta_upper = (1/3) * sum over strata s of  E[ (1/4) * sum over regimes r of ( m_j(r, 1.05) - m_j(r, 0.85) ) | j in s ]
```

These are intention-to-treat effects of the **assigned** ratio. Cap aliasing, encoder ramp,
carry-over from the previous hold and non-plateau responses are part of the actuator being
qualified and are not adjusted away. A requested step is 0.20 x BWE, so a contrast of 0.10
means half the requested step was realised.

## Estimator and test

1. Per source, regime and arm: the mean of the normalised rate over complete cohorts.
   No model and no covariate adjustment; with IID arms of equal propensity inside every peer,
   a difference of means is unbiased as it stands.
2. Per source: average the four regime means per arm with equal weight, then take the two
   adjacent differences `d_j = (d_j_lower, d_j_upper)`.
3. Across sources: the mean of the three stratum means, which requires equal numbers of
   sources per stratum and is refused otherwise.
4. Stein's two-stage test of `H0: theta <= 0.03` for each contrast. The mean uses all `J`
   sources. The standard error is `S1 / sqrt(J)`, where `S1` is the standard deviation of the
   contrast over the 12 first-stage sources, with 11 degrees of freedom.

Using the unstratified variance with a stratum-balanced sample is conservative when strata
differ.

## The three outcomes

Exactly one of these is reported.

| Outcome | Rule |
|---|---|
| **Qualified** | both lower bounds above 0.03 |
| **Not separable at the registered threshold** | either upper bound below 0.03 |
| **Inconclusive** | neither condition is met, or a capture-support gate fails |

- **Qualification is an intersection-union test.** It requires both adjacent contrasts to
  exceed 0.03, so each is tested at the full registered one-sided 0.025. No Bonferroni
  correction is applied to qualification. The chance of qualifying when either true contrast
  is at or below 0.03 is at most 0.025.
- **Not separable** needs only one contrast, which is a union. Each upper bound is therefore
  taken at one-sided 0.0125, so that this outcome is also wrong at most 2.5% of the time when
  both true contrasts are at or above 0.03. This is the only place the level is split.
- **A variance-based decision not to extend beyond 12 is never evidence of no actuator
  effect.** Only an upper bound below 0.03 supports that outcome.
- **One confirmatory sample.** N1 has no internal discovery/replication split. It performs no
  model selection and every inferential choice is fixed here. N2 remains a separate
  fresh-source stage.

## Capture-support gates

| Gate | Threshold | Origin |
|---|---|---|
| Complete cohorts | at least 95% of assigned | inherited |
| Cap aliasing | at most 10% of assigned | inherited |
| Completeness gap between arms | at most 5 percentage points | new |
| Arm shares | chi-square p at least 0.001 against 1/3 each | new, randomisation integrity |
| Evaluable source | at least 3 complete cohorts in each regime x arm cell | new |
| Sources passed over | at most 4 not evaluable | new |
| Freeze and audit | controller freeze and N1 freeze verified; raw replay audit passes | inherited |

The margin of 0.03 is inherited from the earlier stage-one gate. The support gates look at no
outcome by arm. If one fails, the outcome is inconclusive, not negative.

A source that is not evaluable is passed over, and the next source of the same tercile in the
pre-drawn order takes its place. Evaluability depends on completeness alone.

## Complexity terciles are a diagnostic

Complexity is not a qualification gate. N1 reports, for low, medium and high complexity
separately, the estimate of each contrast with a 95% interval from the pooled within-tercile
variance. These intervals are descriptive and are not adjusted for the two-stage design.

One designation is registered: **qualified on average, heterogeneous by complexity**. It is
attached to a *qualified* outcome only when a one-way test that the three tercile means are
equal rejects for either contrast (the smaller of the two p-values, doubled, below 0.05).
It reports evidence that terciles differ. It does not change the outcome.

Nothing is concluded from a tercile mean alone. With four to eight sources per tercile, a
tercile estimate below 0.03 is not a finding without its interval, and the absence of the
designation is not evidence that the actuator behaves alike across complexity.

## Power assumptions

These are planning assumptions, not measurements.

- **Design effect 0.10**: the smallest adjacent separation N1 is powered for, half the
  requested step. N2 planned on 0.15 for both contrasts.
- **Inherited noise** (N2's power model): source-to-source SD of an adjacent contrast 0.02
  (N2's slope SD 0.10 times the 0.20 step), peer SD 0.08, cohort SD 0.08.
- **Pilot information.** The only native data is the 24-cohort smoke: two films, four
  blocks, stable contexts only. Block-adjusted contrasts were about +0.09 and +0.21, and the
  residual SD was 0.138 on 18 degrees of freedom. That is too little to estimate anything,
  and it says nothing about source-to-source variation, but it suggests that 0.08 cohort noise
  and 0.15 for the lower contrast are optimistic. The stress scenarios use cohort SD 0.14 and
  larger source variation for that reason.

Simulated outcomes, 20,000 studies per row (`media-actuator-qualification power`). "Per-source
SD" is the SD of a per-source contrast, between-source and within-source parts together.

| Scenario | Adjacent effects | Source SD | Cohort SD | Per-source SD | Qualified | Mean sources | Fixed 6 | Fixed 9 | Fixed 12 | Fixed 24 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N2 assumptions | 0.15 / 0.15 | 0.02 | 0.08 | 0.027 | 1.000 | 12.0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Design effect, N2 noise | 0.10 / 0.10 | 0.02 | 0.08 | 0.027 | 1.000 | 12.0 | 0.997 | 1.000 | 1.000 | 1.000 |
| Design effect, smoke noise | 0.10 / 0.10 | 0.05 | 0.14 | 0.056 | 0.986 | 14.4 | 0.553 | 0.848 | 0.957 | 1.000 |
| Smoke-like | 0.09 / 0.21 | 0.05 | 0.14 | 0.056 | 0.962 | 14.4 | 0.559 | 0.800 | 0.917 | 0.999 |
| Design effect, heterogeneous | 0.10 / 0.10 | 0.08 | 0.14 | 0.084 | 0.923 | 21.7 | 0.283 | 0.498 | 0.679 | 0.961 |
| Design effect, very heterogeneous | 0.10 / 0.10 | 0.12 | 0.14 | 0.123 | 0.639 | 22.4 | 0.158 | 0.271 | 0.379 | 0.721 |
| One regime dead | 0.15 / 0.15 in three regimes | 0.05 | 0.14 | 0.045 | 1.000 | 12.4 | 0.892 | 0.994 | 1.000 | 1.000 |
| One tercile saturates | 0.15 / 0.15, upper 0 in one tercile | 0.05 | 0.14 | 0.056 / 0.086 | 0.997 | 22.7 | 0.085 | 0.570 | 0.889 | 1.000 |

What the table supports:

- **Twelve is the minimum that holds up.** At the design effect with smoke-level noise, a
  fixed 12 qualifies 96% of the time, 9 only 85% and 6 only 55%. Under N2's assumptions any of
  them would do, but those assumptions are the ones the smoke puts in doubt.
- **The rule buys robustness to heterogeneity.** With source SD 0.08, a fixed 12 qualifies
  68% of the time; the adaptive design 92%, using 21.7 sources on average.
- **Beyond source SD of about 0.10, N1 at 24 is underpowered** (64% at 0.12). That is a limit
  of this design, stated in advance.
- **Averages hide structure, and the diagnostics are there for it.** With one tercile
  saturating, N1 still qualifies on average 99.7% of the time, and the heterogeneity
  designation is attached in 99.8% of studies. Where terciles do not differ it is attached in
  4 to 5%. With one regime dead, the pooled contrast still qualifies; the regime map shows it.

Error rates at and beyond the margin:

| Truth | Qualified | Not separable |
|---|---:|---:|
| Both contrasts exactly 0.03 | 0.006 | 0.021 |
| Lower exactly 0.03, upper 0.15, heterogeneous (65% of studies extend to 24) | 0.026 | 0.013 |
| Upper mean exactly 0.03 through one saturating tercile | 0.005 | 0.005 |
| No actuation at all | 0.000 | 0.914 |

The least favourable case sits at 0.026 with Monte Carlo standard error 0.001, consistent
with the nominal 0.025.

Peers per regime, at the design effect with smoke noise: 5 peers qualify 97.9% using 16.8
sources on average, 10 peers 98.7% using 14.4, and 20 peers 98.9% using 13.4. Ten is where
the return flattens.

## Blinded sample-size re-estimation

Re-estimation is used for exactly one quantity: the variance across sources of the per-source
contrast. It decides the sample size, nothing measures it today, and the required number of
sources is proportional to it. It is not used for the effect size, for peers per source, or
for anything in N2.

**Rule.** With `S` the larger first-stage SD of a per-source contrast:

```text
J = (t[0.975, 11] + t[0.95, 11])^2 * S^2 / (0.10 - 0.03)^2      = 3260 * S^2
rounded up to a multiple of 3, at least 12, at most the planned maximum (24)
```

| Larger first-stage SD of a per-source contrast | Total sources |
|---|---:|
| up to 0.0607 | 12 (no extension) |
| up to 0.0678 | 15 |
| up to 0.0743 | 18 |
| up to 0.0803 | 21 |
| up to 0.1558 | 24 |
| above 0.1558 | 12 (precision futility) |

**Precision futility.** The last row is information futility, not treatment-effect futility.
If the variance is so large that even the maximum would leave less than an even chance of
qualifying at the design effect, no sources are added and the analysis runs on the first 12.
The decision uses only the blinded variance. It supports no conclusion about the sign or the
magnitude of the mean effect, and the outcome is still read from the bounds alone.

**What the interim exposes.** The interim routine returns one number that anyone may see: the
prescribed final source count, 12, 15, 18, 21 or 24. With it come outcome-free capture-support
metrics and the hashes below. It does not expose the two contrast variances, and a count of
12 reads the same whether the variance was small or precision was futile.

**Sealed record.** The routine writes a second file for the custodian, opened only by the
final analysis. It holds the two variances, the uncapped requirement, the precision-futility
flag, the decision, the first-stage source list, and hashes of the stage-one capture, the
sealed plan, the registration and every N1 source file. The public record carries the hash of
the sealed one. The final analysis refuses to run unless the sealed record matches that hash
and its variances reproduce from the data.

**Custodian.** The planner refuses to seal a plan without a named interim custodian, and the
name is bound into the plan and both records. The custodian runs the interim and keeps the
sealed file. Nobody is named yet.

**Why the level holds.** For normally distributed per-source contrasts, the variance across
sources is independent of their mean. A total chosen from first-stage variances alone,
followed by Stein's statistic with the first-stage variance and 11 degrees of freedom, gives
an exact level for any such rule. No efficacy look is taken, so no alpha is spent. The
simulation above confirms the level with cohort-level data and 65% of studies extending.

**Limits of the blinding.**

- N2's document warns that hiding the action column and pooling is not a valid blinded
  estimator, because the lumped variance contains the treatment effect. This rule does not do
  that. The contrast variance is computed with arm labels inside the routine, and neither
  record contains a mean, a per-source contrast or anything labelled by arm.
- The firewall is procedural. Capture computes no outcome statistic, the interim is the only
  permitted look, and raw captures are sealed by hash manifests. Nothing cryptographic stops
  someone with file access from looking. A custodian who is not the analyst is the safeguard.

**Not allowed.** Resizing from observed contrasts; reducing the sample because acquisition is
hard; re-estimating the design effect; any look not listed here; analysing a number of sources
other than the one the rule prescribed (the final analysis refuses).

## Secondary analyses, fixed in advance

None of these changes the outcome.

- **RTP send rate**: the same two contrasts and test.
- **Regime map**: the two contrasts within each of the four regimes, with the same two-stage
  standard error and Holm correction over the eight tests. Every source sees every regime, so
  these have the same number of clusters as the confirmatory analysis.
- **First-stage F and partial R-squared**, source-clustered, computed with the earlier code.
  They are instrument-strength heuristics for a QoE stage and are reported as N2-readiness
  indicators.
- **Prevalence**: the number of sources whose own two contrasts both exceed 0.03, with an
  exact one-sided 97.5% lower bound on that share. Twelve of twelve gives 0.735.
- **Heterogeneity**: the SD of per-source contrasts with its chi-square interval. This is the
  quantity N2's power calculation assumed.
- **Settling and plateau**: plateau share by arm, descriptive only.

## What each outcome leads to

- **Qualified**: the actuator argument for acquiring N2's 96 units holds. N2 runs unchanged,
  with its own gates on its own units. If the heterogeneity designation is attached, decide
  N2's scope separately and in advance of its data.
- **Not separable at the registered threshold**: do not acquire for N2 as designed. The open
  question becomes the actuator itself, for example a longer-hold timing diagnostic, with
  controllers still frozen.
- **Inconclusive**: no claim, in either direction. A further native phase needs its own
  registration.

N1's variance estimates may inform a separately registered review of N2's sample size. Since
N1's sources are disjoint from N2's, that would be an external pilot and needs no blinding.
It is not enabled by this document and N2's 96 stays as registered.

## Implementation, and what has been exercised

| Step | Command | What it does |
|---|---|---|
| Queue | `queue` | seeded order in which to verify discovered candidates; verifies nothing |
| Plan | `plan` | seals sources, runtimes and every planned arm; needs a custodian; observes no outcome |
| Capture | `capture` | runs the unchanged collector and raw auditor for planned blocks; computes no outcome statistic |
| Status | `status` | outcome-free: what is captured and evaluable, whether the interim can run |
| Interim | `interim` | prints the prescribed total; writes the sealed record |
| Final | `final` | the confirmatory analysis and the secondary analyses; unseals the interim |
| Dry run | `dry-run` | planner to outcome on mock sources and synthetic rows |

The planner reuses the unchanged runtime builder, so a runtime differs from the earlier
studies only in its peer groups. The frozen collector accepts only its two legacy stage
labels; N1 passes `discovery` for every source as a technical label. It does not denote a
discovery role.

What the plan checks before sealing, and re-derives at every later step:

- **Randomisation.** Each planned arm equals the frozen assignment function of its peer's
  seed and hold. Seeds are distinct across all peers. Arms stay IID with propensity 1/3; the
  seed is never redrawn to improve balance.
- **Regime and arm balance.** Every source has ten peers in each of the four regimes. Arm
  counts are random by design, so the plan reports them, tests them against equal shares, and
  refuses a plan in which any source x regime x arm cell is assigned fewer than three cohorts.
- **Per-cell minima after capture.** Complete cohorts per cell are checked again on audited
  rows, and decide evaluability.
- **Source-cluster independence.** Shared title, capture group or lineage across clusters is
  refused at allocation, in the plan, and again on audited rows. Each audited row must match
  its planned arm, seed, source and regime, with propensity 1/3.

None of this has run against a browser. The planner and capture loop are exercised with the
real runtime builder and with doubles for the collector and raw auditor; the dry run uses
synthetic rows. A defect found on first native use is a tooling fix, and any fix needs a new
freeze record committed before an outcome is observed.

## Before any collection

1. Verify at least 12 eligible source clusters, ideally 24, through the unchanged ingest and
   screening tools, following the queue. This needs the importer's rights review and a
   download budget.
2. Name the interim custodian.
3. Seal the plan and run `verify-freeze`.

## Commands

```sh
uv run --frozen media-actuator-qualification show            # plan and rule thresholds
uv run --frozen media-actuator-qualification verify-freeze
uv run --frozen media-actuator-qualification power --out results/native-actuator-qualification-n1-power.json
uv run --frozen media-actuator-qualification dry-run --out results/my-n1-dry-run
uv run --frozen media-actuator-qualification queue \
    --inventory results/native-panel-acquisition-discovery-v2-final/inventory.json \
    --out results/native-actuator-qualification-n1-queue.json

# Only after sources are verified and a custodian is named:
uv run --frozen media-actuator-qualification plan --screen results/my-screen/screen.json \
    --custodian "NAME" --out results/native-actuator-qualification-n1-plan
uv run --frozen media-actuator-qualification capture --protocol results/native-actuator-qualification-n1-plan/protocol.json \
    --start 0 --stop 12 --out results/native-actuator-qualification-n1-stage-one
uv run --frozen media-actuator-qualification interim --protocol ... --capture ... \
    --public results/n1-interim-public.json --sealed /custodian/n1-interim-sealed.json
uv run --frozen media-actuator-qualification final --protocol ... --capture ... [--capture ...] \
    --public ... --sealed ... --out results/native-actuator-qualification-n1-final.json
```

`power` and `dry-run` simulate and read no native data.
