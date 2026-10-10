# Native Phase B1: does backing off help when the sender has seen congestion?

**Draft for the owner's review. Nothing here is registered or frozen.** No source has been
downloaded, no rights have been reviewed and nothing has been captured for this phase. The
N1 registration, the 31-file controller freeze and Phase N2 are untouched.

What exists today:

| | |
|---|---|
| This draft | choices marked **to confirm** are listed at the end |
| Sizing record | `results/native-phase-b1-sizing.json`, from the N1 rows, for planning only |
| Rights-review manifest | `acquisition/native-b1/rights-review/rights-review-manifest.csv`, 74 candidates, every review field empty |
| Queue | `acquisition/native-b1/queue.json`, the continuation of the registered seeded N1 order |

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
  units, with nothing established. That was a second look at one sample.
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

The arm is randomised independently of everything before the hold, so within flagged holds a
difference between arms is a causal effect of the request.

## Endpoint and estimand

**Endpoint:** the on-time sampled RGB-PSNR contribution of the frames captured in the outcome
window, as the unchanged auditor records it. It is a proxy, not perceptual quality.

**Benefit of backing off, per source:** over the source's flagged complete holds, pooling the
four schedules, the mean of the endpoint at ratios 0.65 and 0.85 minus the endpoint at 1.05.
Schedules are pooled because a controller sees the state and not the schedule.

**Estimand:** the mean of that benefit over sources, with the three complexity terciles
weighted equally.

## Test and outcomes

A one-sample t test on the per-source benefits, with the number of sources fixed in advance
and no interim look. Two statements, each at one-sided 2.5%:

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

One confirmatory sample, one endpoint, one flag, one analysis.

## Sample

- **Sources:** every candidate the N1 queue did not draw from Discovery V2, in the
  continuation of the registered seeded order: 74 candidates, 31 CC BY 3.0, 24 CC BY 4.0 and
  19 CC0 1.0. None of N1's 36 is offered again, and N1's nine reserve sources stay reserved
  to N1. Discovery is not expanded.
- **Number analysed:** all verified eligible sources, trimmed in the seeded order to equal
  numbers per complexity tercile. At N1's rate of 21 eligible from 36 queued, about 43.
- **Minimum:** 30 (ten per tercile). With fewer, B1 is not run as a confirmatory study.
- **Per source:** 40 fresh peers and 240 holds, as in N1.

## Power, from N1's rows

Planning assumptions, not measurements of B1. In N1 the per-source benefit under this flag
has a standard deviation of 2.27 over twelve sources. Its mean there, +1.27 [-0.17, +2.71],
comes from a third look at one sample and is not evidence.

| Sources | Half-width of the 95% interval | Power at a benefit of 1.0 | At 1.5 | If the SD were 2.8: at 1.0 | At 1.5 |
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
  without new discovery.

## Capture-support gates

N1's gates, unchanged: at least 95% complete cohorts, at most 10% aliased, a completeness gap
between arms of at most 5 points, and arm shares compatible with one third each. In addition:

- **Evaluable source:** at least three flagged complete holds in each arm. In N1 the smallest
  such cell held 13.
- **Sources passed over:** at most one in ten. A source that is not evaluable is replaced by
  the next of its tercile in the seeded order, and evaluability looks at no outcome.

If a gate fails the outcome is inconclusive, not negative.

## Secondary analyses, fixed in advance

None of them changes the outcome.

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
- **By schedule,** descriptively.
- **N1's two actuator contrasts** on encoded rate, as a replication on fresh sources.

## What each outcome would lead to

- **Helps:** a native controller that backs off under this flag is worth building and testing
  against the top ratio, under its own registration. That would be the first native evidence
  for the premise of the synthetic track.
- **Helps, below the practical gate:** the effect is real and small. A controller built on it
  alone would not clear N2's gate.
- **No practically relevant benefit:** on this stack, backing off below the browser's estimate
  under this flag is not worth pursuing, and the case for a learned cap controller here is
  closed unless a different actuator or signal is proposed.
- **Inconclusive:** no claim in either direction.

## Cost

| | |
|---|---|
| Rights review | 74 candidates, the same columns as N1's manifest; 20 name an external origin |
| Download | 18.6 GB by catalogue size if every candidate were fetched; 9.65 GB for the 70 under 1 GB each |
| Capture | about 42 sources x 40 peers x 48 s, roughly 22 hours, in blocks of six sources (about 3.2 hours each) so that one failure costs one block |
| Storage | about 29 GB of raw capture at N1's 17 MB per peer, plus media. The machine has 33 GB free, and N1 holds 17 GB of media and capture |

Storage is a real constraint: B1 does not fit next to N1's raw files as things stand.

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
  continuously would gain; its own actions would change which holds are flagged.
- The blinding is procedural, as in N1, and the rights review needs the owner's explicit
  adoption before ingest, as N1 learned.

## Choices to confirm

| Choice | Proposed | Alternatives |
|---|---|---|
| Flag | estimate grew by less than 5% since the previous hold | jitter or RTT threshold from N1 (relay-specific); a combination |
| Primary contrast | mean of 0.65 and 0.85 against 1.05 | 0.85 against 1.05 only (looked best in N1, so chosen by peeking); 0.65 against 1.05 only |
| Practical gate | 1.0, as in N2 | none (a single "helps" test) |
| Minimum sources | 30 | 36 or 42, at the risk of not running |
| Per-file download cap | 1 GB (drops 4 of 74 candidates, saves 9 GB) | none |
| Storage | move N1's raw capture off this machine, or delete rejected candidates' media after review | a larger disk |
| Next-hold cost | secondary | co-primary, which would need a multiplicity rule |

## After approval, in order

1. Fix the choices above and write the registration config.
2. Implement the planner, the estimator and the final analysis as a new module that reuses
   the unchanged runtime builder, collector and auditor, with a mock dry run and tests.
3. Hash-freeze registration and code, commit, and tag before any B1 data exist.
4. Rights review of the manifest by the owner's reviewer, and the owner's explicit adoption.
5. Set a budget; fetch, ingest and screen with the unchanged tools; seal the plan.
6. Capture in blocks, outcome-free status, one final analysis.

Nothing in steps 4 to 6 starts without the owner's instruction.

## Commands behind the two records

Both read existing local files and download nothing.

```sh
# sizing, from the tracked N1 cohort rows
uv run --frozen python -m media_rl.native_actuator_qualification_explore --sizing \
    --rows results/native-actuator-qualification-n1-stage-one-cohorts.json.gz \
    --out results/native-phase-b1-sizing.json

# queue and manifest, from the Discovery V2 inventory and the N1 queue
uv run --frozen python -m media_rl.native_backoff_acquisition \
    --inventory results/native-panel-acquisition-discovery-v2-final/inventory.json \
    --n1-queue acquisition/native-n1/queue.json --out acquisition/native-b1
```
