# Native Phase B1: does backing off help when the sender has seen congestion? (preregistration)

**Registered 2026-10-10, before any B1 data exists.** No source has been downloaded, no rights
have been reviewed and nothing has been captured for this phase. No controller or model is
changed and none is fitted. The 31-file controller freeze, the Native Phase N1 registration and
Phase N2 are untouched.

- Registration: `configs/native_backoff_benefit_b1.json`
- Flag, estimand, test and outcomes: `src/media_rl/native_backoff_benefit.py`
- Planner, capture and final analysis: `src/media_rl/native_backoff_benefit_panel.py`
- Hash record of all of the above and this document: `configs/native_backoff_benefit_b1_freeze.json`

## Question

On the native stack, in holds that the sender can recognise beforehand as congested, does a
lower requested ratio deliver more on-time quality than the top ratio?

B1 answers only that. It fits no model and lets no learned controller act. It is the smallest
native experiment that could show a controller has something to gain by backing off below the
browser's own estimate.

## Why this, and why now

- [N1](NATIVE_PHASE_N1_RESULT.md) qualified the actuator: the requested ratio moves the encoder.
- The [exploratory passes](NATIVE_PHASE_N1_EXPLORATORY.md) over N1's rows found that by
  schedule no lower ratio is better, and that in the third of holds flagged by a stalled
  estimate, high jitter or high RTT the point estimates lean toward backing off by 0.5 to 1.5
  units, with nothing established and no candidate named by the rule fixed there. That was a
  second look at one sample.
- The [headroom study](JEVBWE_TYPED_HEADROOM_V1.md) says that in the simulator most of the
  hindsight opportunity is in backing off.
- Whether that opportunity exists natively is now the largest open question, and twelve
  sources could not answer it. A confirmatory test on fresh sources can.

Phase N2 asks a broader question (rate to quality, per cell, 96 sources) and stays registered
as it is. B1 is narrower and cheaper, and its outcome bears on whether N2 is worth its cost.

## Held fixed from N1

Everything about how data are produced is N1's, unchanged:

- the harness, the collector and the raw auditor, called without modification;
- three arms, 0.65, 0.85 and 1.05 of the sender's estimate, IID with propensity 1/3 from a
  seed sealed in the plan, six 3 s holds per fresh peer;
- the four capacity schedules, ten fresh peers per schedule per source;
- the outcome window from 1.8 to 2.6 s after the request is acknowledged;
- the source rules (rights evidence, lineage, 80 s of native-ready H.264, no overlap with any
  earlier native role), one screening of the whole verified pool for complexity terciles;
- a capture step that computes no outcome statistic.

## The flag

A hold is **flagged** when the frozen estimate at its assignment is less than 1.05 times the
frozen estimate at the previous hold of the same peer: the estimate grew by less than 5%
since the last hold, or fell. Holds 2 to 6 of each peer can be flagged; a peer's first hold
has no previous one and is left out.

- The sender observes it before the hold, so a controller could act on it.
- It is a ratio of the sender's own estimates, so it does not depend on this relay's delay,
  as an RTT or jitter threshold would.
- In N1 it flagged 34% of holds: about 18% under the unconstrained schedule and about 34% to
  42% under the three constrained ones.
- It also depends on the previous request, because a cap below the estimate holds the estimate
  back. In N1 a hold was flagged 51% of the time after a hold at 0.65, 23% after 0.85 and 28%
  after 1.05, and 27% of flagged holds followed the top ratio. These shares use the flag and
  the arms only, no endpoint.

The arm is randomised independently of everything before the hold, so within flagged holds a
difference between arms is a causal effect of the request.

## Endpoint and estimand

**Endpoint:** the on-time sampled RGB-PSNR contribution of the frames captured in the outcome
window, as the unchanged auditor records it. It is a proxy, not perceptual quality.

**Benefit of backing off, per source:** over the source's flagged complete holds, pooling the
four schedules, the mean of the endpoint at ratios 0.65 and 0.85 minus the endpoint at 1.05.
Each arm's mean is taken first and the two lower ones are averaged with equal weight.
Schedules are pooled because a controller sees the state and not the schedule. No model and no
covariate adjustment.

**Estimand:** the mean of that benefit over sources, with the three complexity terciles
weighted equally.

## Test and outcomes

A one-sample t test on the per-source benefits, with every planned source captured before any
analysis and no interim look. The standard error is the unstratified one, which is
conservative when terciles differ. Two statements, each at one-sided 2.5%:

| Statement | Rule |
|---|---|
| Backing off helps | the lower bound of the benefit is above 0 |
| Any benefit is below the practical gate | the upper bound of the benefit is below 1.0 |

The gate of 1.0 is Phase N2's practical-effect gate, in the same units. Exactly one outcome is
reported:

| Outcome | When |
|---|---|
| **Helps** | the first statement holds and the second does not |
| **Helps, below the practical gate** | both hold |
| **No practically relevant benefit** | the second holds and the first does not |
| **Inconclusive** | neither holds, or a capture-support gate fails |

One confirmatory sample, one endpoint, one flag, one analysis. The final routine refuses to
run until every planned source has been captured, and writes its report once.

## Sample

- **Sources:** every candidate the N1 queue did not draw from Discovery V2, in the
  continuation of the registered seeded order: 74 candidates, 31 CC BY 3.0, 24 CC BY 4.0 and
  19 CC0 1.0. None of N1's 36 is offered again, and N1's nine reserve sources stay reserved
  to N1. Discovery is not expanded.
- **Number planned:** all verified eligible sources, as many whole tercile-balanced blocks as
  the thinnest complexity tercile allows, drawn by a seeded order within terciles. There is no
  reserve and nothing is added later. At N1's rate of 21 eligible from 36 queued, about 43.
- **Minimum:** 30 (ten per tercile). With fewer the planner refuses, and B1 is not run.
- **Per source:** 40 fresh peers and 240 holds, as in N1.

## Power, from N1's rows

Planning assumptions, not measurements of B1. In N1 the per-source benefit under this flag
has a standard deviation of 2.27 over twelve sources. Its mean there, +1.27 [-0.17, +2.71],
comes from a third look at one sample and is not evidence.

| Sources | Half-width of the interval | Power at a benefit of 1.0 | At 1.5 | If the SD were 2.8: at 1.0 | At 1.5 |
|---:|---:|---:|---:|---:|---:|
| 30 | 0.85 | 0.65 | 0.94 | 0.47 | 0.81 |
| 36 | 0.77 | 0.73 | 0.97 | 0.55 | 0.88 |
| 42 | 0.71 | 0.80 | 0.99 | 0.62 | 0.92 |
| 54 | 0.62 | 0.89 | 1.00 | 0.73 | 0.97 |

- With about 42 sources B1 has 80% power for a benefit at the practical gate and is nearly
  certain to detect 1.5.
- It reaches "no practically relevant benefit" only if the estimate is near zero: at 42
  sources the upper bound falls below 1.0 when the estimate is under about 0.3.
- The candidate pool cannot supply much more than 42, so B1 cannot be made much stronger
  without new discovery. That is a limit of this design, stated in advance.

## Capture-support gates

N1's gates, by N1's own frozen function: at least 95% complete cohorts, at most 10% aliased, a
completeness gap between arms of at most 5 points, and arm shares compatible with one third
each. In addition:

- **Evaluable source:** at least three flagged complete holds in each arm. In N1 the smallest
  such cell held 13.
- **Sources not evaluable:** at most one planned source in ten.
- **Analysed sources:** the first evaluable sources of each tercile in the planned order, the
  same number from each, so the tercile weights stay equal. At least 30.

Evaluability depends on the flag and on completeness, never on an outcome by arm. If a gate
fails the outcome is inconclusive, not negative.

## Secondary analyses, fixed in advance

None of them changes the outcome. Each is a mean over the analysed sources with a 95% interval.

- **Each lower ratio on its own:** 0.65 minus 1.05 and 0.85 minus 1.05 among flagged holds.
- **Unflagged holds and the difference:** the same benefit among unflagged holds, and flagged
  minus unflagged.
- **What backing off costs the next hold:** the same contrast on the *next* hold's endpoint,
  by this hold's arm, among holds flagged now. N1 showed that a cap below the estimate holds
  the estimate back; this measures whether that cost outlasts the hold. The sum of the
  immediate and the next-hold benefit is reported with it.
- **On-time fraction** in place of the PSNR proxy.
- **Alternative flags:** jitter above 12.0 ms and RTT above 57.0 ms, the thresholds found in
  N1, reported for comparison only.
- **By the previous hold's ratio:** the benefit among flagged holds that follow a hold at 1.05,
  and among those that follow a lower ratio. The first is the closest B1 comes to what a sender
  that normally requests the top ratio would see. It holds about a quarter of the flagged
  holds, so fewer sources will be evaluable for it, and their number is reported with it.
- **By schedule,** descriptively.
- **N1's two actuator contrasts** on encoded rate, as a replication on fresh sources.

## What each outcome leads to

- **Helps:** a native controller that backs off under this flag is worth building and testing
  against the top ratio, under its own registration. That would be the first native evidence
  for the premise of the synthetic track.
- **Helps, below the practical gate:** the effect is real and small. A controller built on it
  alone would not clear N2's gate.
- **No practically relevant benefit:** on this stack, backing off below the browser's estimate
  under this flag is not worth pursuing, and the case for a learned cap controller here is
  closed unless a different actuator or signal is proposed.
- **Inconclusive:** no claim in either direction.

No outcome promotes a controller.

## Limits, stated in advance

- The endpoint is a pixel proxy in a 0.8 s window late in a 3 s hold. The next-hold secondary
  is the only view of longer consequences.
- One machine, one browser build, VP8 at 640x360, a userspace relay with four scripted
  schedules. It is not a real network path.
- The top ratio stands in for "no cap". At 1.05 the cap sits above the estimate, and in N1 the
  encoder ran at 0.83 of the estimate there.
- The flag and its threshold come from N1's rows. B1's sources are fresh, so that does not
  bias B1, but a better flag may exist.
- A benefit under a randomised 3 s hold does not show that a controller acting on the flag
  continuously would gain; its own actions would change which holds are flagged. That is
  already visible in N1: half of the holds after a request of 0.65 are flagged, against a
  quarter after the other two, so many flagged holds are flagged because the previous hold
  was capped and not because the path was congested. The primary estimate averages over
  both kinds. The split by the previous hold's ratio is secondary and thin.
- The blinding is procedural, as in N1: one owner, and an AI agent with file access running
  every step. There is no interim, so there is no sealed record and no custodian.

## Choices the owner confirmed on 2026-10-10

| Choice | Confirmed | Alternatives declined |
|---|---|---|
| Flag | estimate grew by less than 5% since the previous hold | jitter above 12 ms; RTT above 57 ms |
| Primary contrast | mean of 0.65 and 0.85 against 1.05 | 0.85 against 1.05 only; 0.65 against 1.05 only |
| Practical gate | 1.0, as in N2 | no gate |
| Minimum sources | 30 | 36; 42 |

Not asked, and registered as proposed: the next-hold cost is a secondary analysis, not a
co-primary one. Added by the agent before the freeze and not asked: the split by the previous
hold's ratio, a secondary analysis that changes no outcome.

## Left to the acquisition gate

These are not part of the analysis and are the owner's to set before any download:

| | |
|---|---|
| Rights review | 74 candidates in `acquisition/native-b1/rights-review/rights-review-manifest.csv`, the same columns as N1's manifest; 20 name an external origin. The owner's explicit adoption of the review is needed before ingest |
| Download budget | 18.6 GB by catalogue size if every candidate were fetched; 9.65 GB for the 70 under 1 GB each |
| Storage | about 29 GB of raw capture at N1's 17 MB per peer, plus media. The machine had 33 GB free at registration, with N1 holding 17 GB |
| Capture time | about 42 sources x 40 peers x 48 s, roughly 22 hours, in blocks of six sources (about 3.2 hours each) so that one failure costs one block |

## Implementation, and what has been exercised

| Step | Command | What it does |
|---|---|---|
| Show | `show` | the registered plan, secondary flags and planning power table |
| Plan | `plan` | seals sources, runtimes and every planned arm; observes no outcome |
| Capture | `capture` | runs the unchanged collector and raw auditor for planned blocks; computes no outcome statistic |
| Status | `status` | outcome-free: what is captured, capture support, how many holds the flag marks |
| Final | `final` | the confirmatory analysis and the secondaries; refuses until every planned source is captured, writes once |
| Dry run | `dry-run` | planner to outcome on mock sources and synthetic rows |

The planner reuses the unchanged runtime builder, and the capture loop is N1's, line for line,
under B1's names. What the plan checks before sealing, and re-derives at every later step, is
what N1's did: each planned arm equals the frozen assignment function of its peer's seed and
hold; seeds are distinct; every source has ten peers in each schedule; no source x schedule x
arm cell is planned below three cohorts; no title, capture group or lineage is shared across
clusters; and each audited row matches its planned arm, seed, source and schedule.

The collector and auditor ran natively for N1. B1's planner, capture loop and analysis have
run only on mock sources, synthetic rows and test doubles. A defect found on first native use
is a tooling fix, and any fix to the four frozen files needs a new freeze record committed
before an outcome is observed.

## Commands

```sh
uv run --frozen media-backoff-benefit show
uv run --frozen media-backoff-benefit verify-freeze
uv run --frozen media-backoff-benefit dry-run --out results/my-b1-dry-run   # mock rows only

# Only after sources are verified, on the owner's instruction:
uv run --frozen media-backoff-benefit plan --screen results/my-screen/screen.json \
    --out results/native-backoff-benefit-b1-plan
uv run --frozen media-backoff-benefit capture --protocol results/native-backoff-benefit-b1-plan/protocol.json \
    --start 0 --stop 6 --out results/native-backoff-benefit-b1-block-1
uv run --frozen media-backoff-benefit status --protocol ... --capture ... [--capture ...]
uv run --frozen media-backoff-benefit final --protocol ... --capture ... [--capture ...] \
    --out results/native-backoff-benefit-b1-final.json
```
