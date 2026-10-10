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
