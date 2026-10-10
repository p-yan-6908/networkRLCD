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

Not yet run at this commit.
