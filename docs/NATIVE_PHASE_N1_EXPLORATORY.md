# Native Phase N1: exploratory description of the cohort rows

**Not registered and not confirmatory.** The N1 outcome is the one in
[NATIVE_PHASE_N1_RESULT.md](NATIVE_PHASE_N1_RESULT.md), and nothing here changes it. This is a
description of the same 2,880 audited cohort rows, run after the final analysis, to see what
they say about three questions the registration left to later phases. At best it is an
external pilot for those phases. No model or controller is fitted.

## Fixed before any of it was computed

This section and the code (`src/media_rl/native_actuator_qualification_explore.py`) were
committed before the first run on native rows. At that point the registered final report had
been read and the field names of the rows had been listed; no value of any quantity below had
been seen. The code had run on synthetic test rows only.

**Unit and intervals.** The source, twelve of them. Cohorts are averaged within source, regime
and arm, contrasts are formed per source, and intervals are two-sided 95% t intervals over
sources (11 degrees of freedom). With four sources per tercile, equal source weights are equal
tercile weights. There is no correction for the number of quantities reported, except where
stated.

**Questions.**

1. **Response level.** Mean encoded rate over frozen BWE at each assigned ratio, over the
   four regimes with equal weight and within each regime. The registered analysis reports
   differences only; the levels say where the encoder sits against its cap.
2. **Does the cap move the next estimate?** For each hold with a successor in its peer, the
   log of the next hold's frozen BWE over this hold's, by this hold's arm. The arm is
   randomised independently of everything before it, so a difference between arms is a causal
   effect of the cap on the estimate about 3 s later, averaged over the hold's history.
3. **Delivered-quality proxy.** The rows carry two per-hold quantities for the frames
   captured in the outcome window: `utility`, the on-time sampled RGB-PSNR contribution, and
   `ontime_fraction`. For each of the two:
   - arm means and the three contrasts (0.85 - 0.65, 1.05 - 0.85, 1.05 - 0.65), overall and
     by regime;
   - the regime interaction: the 1.05 - 0.65 contrast under the underutilized schedule minus
     the same contrast under each other schedule, with Holm over those three tests;
   - a tally of how many sources have their highest mean at each ratio, per regime;
   - the 1.05 - 0.65 contrast per regime and pair of holds (1-2, 3-4, 5-6), which fall mostly
     in the first, second and third capacity phase. A source with an empty cell drops out of
     that cell.

**How it will be read.** Question 3 is the registered Phase N2's question, asked of N1's data
without N2's sample, gates or quality stage. Whatever it shows is a pilot observation. A
regime interaction here would say that the ratio with the best on-time PSNR in a 0.8 s window
differs between schedules. It would not show that a controller could exploit it: the proxy is
not perceptual quality, the window is short and sits late in a 3 s hold, holds within a peer
carry over into each other, and the schedule label is the configured one, which a controller
does not observe.

## Command

```sh
uv run --frozen python -m media_rl.native_actuator_qualification_explore \
    --rows results/native-actuator-qualification-n1-stage-one-cohorts.json.gz \
    --out results/native-actuator-qualification-n1-exploratory.json
```

## Results

Run on 2026-10-10 on the 2,880 complete cohort rows of the stage-one capture (the tracked
gzip; SHA-256 of the rows `037aaa7e...`, which is the hash the capture manifest records).
Output: `results/native-actuator-qualification-n1-exploratory.json`. Brackets are 95%
intervals over the twelve sources.

### 1. Response level

Encoded rate over frozen BWE, by assigned ratio:

| Schedule | 0.65 | 0.85 | 1.05 |
|---|---:|---:|---:|
| all, equal weight | 0.588 | 0.732 | 0.825 |
| underutilized | 0.602 | 0.777 | 0.922 |
| near-capacity | 0.611 | 0.762 | 0.822 |
| queue-building | 0.585 | 0.738 | 0.782 |
| collapse-recovery | 0.556 | 0.651 | 0.776 |

The encoder runs below each cap: at about 90%, 86% and 79% of it. At the top ratio it stays
below the estimate itself, at 0.92 with an unconstrained link and at 0.78 to 0.82 otherwise.

### 2. The cap moves the next estimate

Log of the next hold's frozen BWE over this hold's, by this hold's arm:

| Schedule | 0.65 | 0.85 | 1.05 | 0.85 - 0.65 | 1.05 - 0.85 |
|---|---:|---:|---:|---|---|
| all, equal weight | +0.123 | +0.128 | +0.310 | +0.004 [-0.053, +0.062] | +0.182 [+0.121, +0.242] |
| underutilized | +0.165 | +0.216 | +0.693 | +0.051 [+0.002, +0.100] | +0.477 [+0.443, +0.510] |
| near-capacity | +0.209 | +0.141 | +0.213 | -0.068 [-0.166, +0.031] | +0.072 [-0.047, +0.190] |
| queue-building | +0.090 | +0.161 | +0.158 | +0.071 [-0.061, +0.202] | -0.003 [-0.092, +0.087] |
| collapse-recovery | +0.029 | -0.008 | +0.174 | -0.036 [-0.231, +0.158] | +0.182 [+0.024, +0.339] |

With an unconstrained link the estimate grows by 18%, 24% and 100% over one hold at the three
ratios. A cap below the estimate holds the estimate back; a cap just above it lets it double.
With a constrained link the arms are not distinguished, except for the top step under
collapse-recovery.

This is a causal effect of the randomised cap. It means that on this stack a ratio of the
estimate is not a fixed reference: a low request now lowers the base to which later requests
are relative, whenever the link has room.

### 3. Delivered-quality proxy

`utility`, the on-time sampled RGB-PSNR contribution of frames captured in the outcome window:

| Schedule | 0.65 | 0.85 | 1.05 | 0.85 - 0.65 | 1.05 - 0.85 | 1.05 - 0.65 |
|---|---:|---:|---:|---|---|---|
| all, equal weight | 24.63 | 25.65 | 25.89 | +1.02 [+0.15, +1.90] | +0.24 [-0.53, +1.01] | +1.26 [+0.33, +2.18] |
| underutilized | 29.12 | 30.88 | 31.47 | +1.76 [+0.43, +3.08] | +0.59 [-0.19, +1.37] | +2.34 [+1.07, +3.62] |
| near-capacity | 27.71 | 28.50 | 29.05 | +0.79 [-0.76, +2.34] | +0.55 [-0.33, +1.44] | +1.35 [-0.35, +3.04] |
| queue-building | 23.12 | 23.59 | 23.64 | +0.47 [-1.12, +2.05] | +0.05 [-1.36, +1.46] | +0.51 [-1.53, +2.56] |
| collapse-recovery | 18.57 | 19.64 | 19.40 | +1.08 [-0.85, +3.00] | -0.24 [-2.01, +1.53] | +0.83 [-1.38, +3.04] |

`ontime_fraction`, 1.05 - 0.65: +0.025 [-0.006, +0.055] overall; +0.054 [+0.010, +0.098]
underutilized; +0.027 [-0.025, +0.079] near-capacity; +0.002 [-0.062, +0.067] queue-building;
+0.015 [-0.062, +0.091] collapse-recovery.

**Regime interaction** (the 1.05 - 0.65 utility contrast under the underutilized schedule
minus the same contrast under each other schedule):

| Against | Difference | p | Holm p |
|---|---|---:|---:|
| near-capacity | +1.00 [-0.07, +2.07] | 0.065 | 0.195 |
| queue-building | +1.83 [-0.81, +4.47] | 0.155 | 0.311 |
| collapse-recovery | +1.51 [-0.98, +4.00] | 0.208 | 0.311 |

Not established.

**Sources whose highest mean utility is at each ratio** (0.65 / 0.85 / 1.05): underutilized
1 / 2 / 9; near-capacity 4 / 3 / 5; queue-building 4 / 4 / 4; collapse-recovery 4 / 4 / 4.

**The 1.05 - 0.65 utility contrast by pair of holds:**

| Schedule | Holds 1-2 | Holds 3-4 | Holds 5-6 |
|---|---|---|---|
| underutilized | +5.14 [+2.27, +8.00] | +1.17 [+0.24, +2.09] | -0.32 [-1.81, +1.17] |
| near-capacity | +3.54 [+1.44, +5.65] | -0.98 [-4.63, +2.67] | -0.41 [-3.11, +2.29] |
| queue-building | +3.34 [+0.32, +6.36] | -2.17 [-5.37, +1.04] | +1.36 [-3.55, +6.26] |
| collapse-recovery | +4.38 [+1.53, +7.24] | -0.59 [-2.81, +1.62] | -0.38 [-4.81, +4.06] |

## Reading

- **No schedule shows a lower ratio to be better.** Of the twelve schedule-level utility
  contrasts, none favours the lower ratio with an interval that excludes zero. Where the
  ratios differ, the higher one is ahead.
- **The advantage of the top ratio is at session start and with a free link.** It is
  established in the first two holds under all four schedules and, later, only in the middle
  holds of the underutilized schedule. In the middle holds of the three constrained schedules
  the point estimates are below zero (-0.6 to -2.2) and their intervals include zero.
- **With a constrained link, after the start, the pilot cannot tell the ratios apart.** The
  intervals there are 4 to 10 units wide.
- **The cap is not neutral toward the estimator.** Capping below the estimate slows the
  estimate's recovery when capacity is available, which is a cost of backing off that a
  per-hold quality window does not show.

## What this does and does not mean

It gives no support to the premise that backing off below the browser's own estimate improves
delivered quality under any of these configured schedules, and it shows one cost of doing so.
The typed controllers of the synthetic track drew their simulated gain from choosing among
ratios of 0.6 to 1.05 against a simple estimator that the sender could exceed. Here the
estimator is the browser's congestion controller, the cap cannot exceed it, and the top ratio
is the best or indistinguishable everywhere.

It does not show that such a gain is absent. The pilot averages a 0.8 s window late in each
3 s hold over whole schedules, on twelve sources, with a proxy that is not perceptual quality.
A gain confined to the seconds after a capacity drop would not be resolved, and the three
negative point estimates in the middle holds are where it would be. Measuring it is the
registered Phase N2's job. The pilot suggests that the effect N2 would look for is at most a
few units under constrained schedules, and that a study aimed at it should condition on the
moment within a session and not only on the schedule. Any change to N2 on that basis needs
its own registration, and is the owner's decision.

## Planning note, added afterwards

This section was added after the results above had been read. It is for sizing a later study
and supports no claim. `--planning` on the same command writes
`results/native-actuator-qualification-n1-planning.json`.

It asks how many sources a later study would need, with N1's design per source (ten peers per
schedule, six holds per peer), for a two-sided 5% test of a mean difference in the on-time
PSNR proxy.

| Contrast | Per-source SD | Sources for a difference of 1 (80% / 90% power) | For a difference of 2 |
|---|---:|---:|---:|
| All schedules, ratio 1.05 minus 0.65 | 1.46 | 19 / 25 | 7 / 8 |
| Constrained schedules, holds 3-4, ratio 0.65 minus 1.05 | 2.22 | 41 / 54 | 12 / 15 |

The second contrast pools the three constrained schedules in the middle pair of holds, where
a benefit of backing off would be expected. It was defined after seeing that the pilot's
point estimates there were below zero, so its mean in N1, +1.25 [-0.16, +2.66] in favour of
the lower ratio, is biased toward an effect and is not evidence of one. Only its spread is
used.

Read with that caution: a study aimed at the benefit of backing off after a capacity drop
needs on the order of 40 to 55 fresh sources to detect a difference of 1 unit, the size of
the powered panel's practical-effect gate, and 12 to 15 to detect 2 units. The nine reserve
sources of the sealed N1 plan are reserved to N1 and are not available for it.

## Second pass: is backing off better in holds that the sender could tell apart?

**A second look at the same rows, so weaker evidence than the first.** The first pass asked
by configured schedule, which a controller does not observe. This pass asks by what the
sender had observed before each hold. Its design below and its code were committed before
it was run on native rows; the first pass's results had been read.

### Fixed before it was computed

**Holds.** Holds 2 to 6 of every peer (2,400), which have a pre-hold state and a previous hold.

**Signals**, all available to a controller at decision time:

| Signal | Source | Congestion side |
|---|---|---|
| `rtt_trend_ms` | the row's pre-hold state | top third |
| `rtt_ms` | pre-hold state | top third |
| `loss_fraction` | pre-hold state | top third |
| `jitter_ms` | pre-hold state | top third |
| estimate growth | log of this hold's frozen BWE over the previous hold's | bottom third |

The thresholds are the pooled 2/3 quantile (1/3 for estimate growth) over all holds with the
signal present. A hold is flagged when it lies strictly beyond the threshold, so a signal
with many ties flags fewer than a third. Absent values are left out, not imputed.

**Quantity.** The benefit of backing off: the on-time PSNR proxy at ratio 0.65 minus the proxy
at ratio 1.05. Per source, over its flagged holds and over its other holds, pooling the four
schedules, because a controller sees the state and not the schedule. Then:

- the benefit among flagged holds, with a 95% t interval over sources;
- the benefit among the other holds;
- their difference (the interaction), with Holm over the five signals;
- the same for the middle ratio (0.85 minus 1.05) among flagged holds, and everything again
  for the on-time fraction, as secondary.

The arm is randomised independently of the pre-hold state, so the benefit among flagged holds
is a causal effect in that subpopulation. The interaction describes effect modification; the
flag is not randomised.

**Candidate rule.** A signal is named a candidate for a confirmatory study if its interaction
on the PSNR proxy has a Holm-adjusted p below 0.10 and the benefit among its flagged holds is
positive. If none qualifies, no candidate is named. A candidate is a hypothesis for fresh
sources with the threshold frozen at the value found here. It is not a finding.

### Command

```sh
uv run --frozen python -m media_rl.native_actuator_qualification_explore --conditional \
    --rows results/native-actuator-qualification-n1-stage-one-cohorts.json.gz \
    --out results/native-actuator-qualification-n1-conditional.json
```

### Results

Run on 2026-10-10 on the same rows. Output:
`results/native-actuator-qualification-n1-conditional.json`.

**No candidate is named.** No signal's interaction reaches a Holm-adjusted p below 0.10.

Benefit of backing off (PSNR proxy at 0.65 minus at 1.05), 95% intervals over sources:

| Signal before the hold | Flagged when | Flagged | Benefit, flagged | Benefit, other holds | Difference | p | Holm p |
|---|---|---:|---|---|---|---:|---:|
| Estimate growth (log) | below +0.047 | 33% | +0.50 [-0.84, +1.84] | -0.76 [-1.78, +0.27] | +1.26 [-0.13, +2.64] | 0.072 | 0.27 |
| Jitter | above 12.0 ms | 33% | +1.52 [-0.20, +3.25] | -0.76 [-2.32, +0.80] | +2.34 [-0.20, +4.89] | 0.068 | 0.27 |
| RTT | above 57.0 ms | 33% | +1.04 [-0.67, +2.74] | -0.94 [-2.42, +0.53] | +1.98 [-0.58, +4.54] | 0.116 | 0.27 |
| RTT trend | above 0 ms | 5% | too few holds | +0.13 [-1.06, +1.32] | | | |
| Loss fraction | above 0 | 0.2% | too few holds | +0.04 [-1.02, +1.11] | | | |

Two signals are unusable. The RTT trend is zero in most holds, so its top third is the 5%
of holds where it is positive, and loss is positive in 0.2% of holds.

Secondary, among flagged holds:

| Signal | Middle ratio (0.85 minus 1.05), PSNR proxy | On-time fraction, 0.65 minus 1.05 | On-time fraction, 0.85 minus 1.05 |
|---|---|---|---|
| Estimate growth | +1.82 [+0.20, +3.43] | +0.037 [-0.012, +0.086] | +0.072 [+0.020, +0.123] |
| Jitter | +1.26 [-0.93, +3.45] | +0.063 [+0.006, +0.120] | +0.044 [-0.028, +0.117] |
| RTT | +1.08 [-0.64, +2.79] | +0.048 [-0.008, +0.105] | +0.042 [-0.011, +0.096] |

Share of holds flagged by schedule (underutilized / near-capacity / queue-building /
collapse-recovery): estimate growth 18% / 34% / 42% / 40%; jitter 8% / 52% / 47% / 26%; RTT
5% / 36% / 47% / 45%.

### Reading

- **By the rule fixed in advance, there is no candidate.** That is the result.
- **The direction is the one the hypothesis predicts, in all three usable signals.** Among
  flagged holds the point estimate favours backing off by 0.5 to 1.5; among the others it
  favours the top ratio by 0.8 to 0.9; the differences are +1.3 to +2.3 with unadjusted p of
  0.07 to 0.12.
- **That is one observation, not three.** The three signals flag overlapping holds, mostly
  under the constrained schedules.
- **Some secondary intervals exclude zero** (the middle ratio under a stalled estimate, for
  both outcomes; the on-time fraction under high jitter). They are unadjusted, secondary and
  come from a second look, and are not counted as findings.
- **The first pass and this one do not conflict.** By schedule the top ratio is ahead or
  level; within the flagged third of holds the lean reverses. Averaging over a schedule mixes
  the two.

### Sizing a confirmatory study

From the spread over sources of the benefit among flagged holds, with N1's design per source
and a two-sided 5% test:

| Flag | Per-source SD | Sources for a benefit of 1 (80% / 90%) | Of 1.5 | Of 2 |
|---|---:|---:|---:|---:|
| Estimate growth below +0.047 | 2.11 | 37 / 49 | 18 / 23 | 11 / 14 |
| Jitter above 12.0 ms | 2.57 | 54 / 72 | 26 / 33 | 16 / 20 |
| RTT above 57.0 ms | 2.69 | 59 / 78 | 28 / 36 | 17 / 21 |

A confirmatory test of whether backing off helps in holds the sender can flag would
therefore need roughly 40 to 60 fresh sources to detect a benefit of 1 unit and 20 to 30 for
1.5 units. Discovery V2 holds 74 candidates that the N1 queue did not draw; at N1's rate of
21 eligible from 36 queued, that is about 43 eligible sources, with no new discovery.

## Third pass: what happens inside a hold

Recorded separately in [NATIVE_PHASE_N1_DYNAMICS.md](NATIVE_PHASE_N1_DYNAMICS.md). It reads
the raw per-peer logs for mechanism only and no quality label. Two statements above are
refined there. The growth of the estimate by 18%, 24% and 100% per hold in section 2 pools
the first hold; after it the figures are 5%, 14% and 94%, and at the top ratio the growth is a
jump within 0.6 s. And the encoder levels of section 1 are taken 1.8 to 2.6 s into a hold,
before the encoder has settled; with room it reaches the cap by the end of the hold.

