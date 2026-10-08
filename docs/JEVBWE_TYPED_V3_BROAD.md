# Synthetic Typed-Control V3: broadened training, family-disjoint test

Status: **protocol written 2026-10-07 while training was running, before any development or
test result of this run existed.** Results are appended below the protocol and do not change it.

**Outcome.** One of the three pre-specified criteria is met. On the 12 untouched test families
the head gains +0.054 utility over the train-selected fixed ratio, positive in 7 of 12
families, but the family-level t interval [-0.005, +0.112] includes zero, so the gain criterion
is not met. The family bootstrap interval [+0.006, +0.107] excludes zero, but the rule required
both intervals; it is a sensitivity figure and does not replace the criterion. Pooled ECE is
0.070, above the 0.05 threshold, with family ECE from 0.010 to 0.427. Unsafe intervals fall
from 1.98% to 1.27%, which meets the constraint criterion. Regression and exact-gradient
controls match the RLCD head, so there is no evidence that RLCD training itself causes the
gain. Synthetic only. The target is not met and the typed controller is not promoted.

**Status of the data.** The twelve test families were untouched until this one evaluation.
They have now been observed and cannot serve as untouched test families again. No V4, wider
option set, recalibration or new architecture has been started, and none may be iterated
against these families; a further confirmatory experiment needs newly defined families.

This is a simulator study. It is a separate track from the native actuator work: the native
controller freeze (`configs/native_controller_freeze_v1.json`) is untouched and remains the
reference for the factual real-system study. Nothing here supersedes the native
identifiability problem, because the training labels are hindsight rollouts in a forked
simulator, which a real network cannot provide.

## Why a new run and a new test set

Typed V2 (`docs/JEVBWE_TYPED_V2.md`) fitted on four families and was evaluated once on a
frozen 11-family panel. On the seven families it never trained on, it beat the fixed ratio
selected on training families but not the ratio that is best there in hindsight, and its
probabilities were over-confident. The obvious response is a broader training distribution.

That response is itself a design choice made after reading the V2 held-out results, and a
fixed-ratio sweep before V2 already covered all 11 families. The seven formerly held-out
families have therefore influenced design. From V3 on they are **development families**: they
are still never trained on, but results on them are not called held-out. A new set of
families that no controller has run on serves as the test set.

## Data roles

| Role | Families | Used for |
|---|---|---|
| Training (13) | `steady`, `step`, `ramp`, `wifi` (legacy), `multi_step`, `multi_ramp`, `drift`, `dip`, `loss_episode`, `deep_queue`, `delay_shift`, `blackout`, `headroom` | base-ratio tuning, rollout labels, aggregation, calibration, validation panel |
| Development (11) | the V2 frozen panel: the four legacy training families plus `collapse`, `burst_loss`, `bufferbloat`, `handover`, `outage`, `feedback_gap`, `capacity_surge` | read before the test panel; same traces as the V2 test panel, so V3 and V2 are paired |
| Test (12, untouched) | `sawtooth`, `square_wave`, `staircase`, `slow_fade`, `low_rate`, `long_path`, `jitter_storm`, `micro_outage`, `feedback_flap`, `shallow_buffer`, `lossy_link`, `compound` | one evaluation, after everything else is frozen |

The nine new training families randomise capacity shape and add the impairments V2 never
trained on (loss episodes, deep queues, delay shifts, feedback gaps, dead links, large
headroom). They knowingly cover the mechanisms of the seven development families.

The test families were written together with the training families and before any controller
ran on them. Each differs from every training family in temporal structure (periodic sawtooth
and square waves, a descending staircase, a smooth fade, many sub-second outages, rapid
feedback flapping, a staged compound event) or in parameter range (capacity below 1 Mbps,
120-180 ms base RTT, a buffer a quarter to half the training depth, persistent 2-4.5% random
loss, jitter storms without a delay shift). They reuse the simulator's seven trace signals,
so they test unseen families, not unseen physics. `TypedConfig.validate` rejects any config
that puts a test family into training or development, and the unit tests only check that
their traces are well formed.

## What changes and what does not

Only the training distribution changes: `train_scenarios` lists 13 families instead of 4, with
1,300 episodes per aggregation round (100 per family; V2 used 200), 208 tune episodes and 260
calibration episodes per head. Features, labels, heads, optimiser, decision rules, guards,
seeds and every other hyperparameter equal V2 (`configs/jevbwe_typed_v3_broad.json`). There is
no new architecture and no Laya head. The fixed ratio that serves as base policy and as the
bar to beat is re-selected on the 13 training families' tune split.

## Pre-specified test-panel endpoints

Primary method: `choice_rlcd_bayes`, as in V2. Comparator for claims: the fixed ratio selected
on training families only. The fixed ratio that is best on the test panel in hindsight is an
oracle and is reported next to it, never as the bar for a causal claim.

Uncertainty is clustered at the network-family level: families are resampled with
replacement, traces are resampled within each drawn family, and model seeds are resampled
crossed with both (5,000 resamples). Because a percentile bootstrap over 12 clusters is
anti-conservative, a t-interval on the 12 family-level mean differences (11 degrees of
freedom) is reported beside it, with the number of families whose difference is positive.

1. **Gain.** Utility difference to the train-selected fixed ratio. "Retains positive gain"
   requires both family-level intervals to exclude zero.
2. **Calibration.** Top-label ECE (10 bins) pooled over test-family decisions, and its
   per-family range. "Reasonable" means pooled ECE at most 0.05; the worst family is reported
   whatever it is. (V2: 0.012 in distribution, 0.152 on its held-out families.)
3. **Constraints.** Difference in the share of unsafe control intervals to the train-selected
   fixed ratio. "Acceptable" means the upper end of the family-clustered interval is at most
   +1.0 percentage point. The policy-independent floor of each family is reported with it.

Secondary, reported whatever the outcome: the difference to the hindsight-best fixed ratio;
the exact-gradient (`choice_analytic_bayes`) and regression (`regress_greedy`) controls and
their differences to the RLCD head with the same intervals (an RLCD-specific advantage is
claimed only if such an interval excludes zero); the `map` and `gated` rules; the paired
V3 minus V2 difference on the development panel.

The thresholds in 2 and 3 are judgment calls fixed here in advance, not derived quantities.

## Rules for the test panel

- The run first produces the validation and development panels. The test panel is added
  afterwards with `jevbwe-typed evaluate --splits test`, which refuses to recompute a panel.
- Between reading the development panel and evaluating the test panel, config and code stay
  as they are unless the development panel exposes a defect. Any such change is recorded in
  this file before the test evaluation.
- After the test panel is read, nothing is tuned against it. A further iteration needs new
  test families.
- No controller receives hindsight at run time. `jevbwe-typed rescore` replays every learned
  episode with rollouts switched off and must reproduce the frozen outcomes exactly.

## Commands

```sh
uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_v3_broad.json \
    --out results/jevbwe-typed-v3-broad --splits validation,development
uv run --frozen jevbwe-typed evaluate --run results/jevbwe-typed-v3-broad --splits test
uv run --frozen jevbwe-typed rescore --run results/jevbwe-typed-v3-broad --split test
uv run --frozen jevbwe-typed audit --run results/jevbwe-typed-v3-broad --split test
```

## Run log

- 2026-10-07. Base-ratio tuning on the 13 training families selected 1.05, the top of the
  option set. The head can therefore only move down from the base. The option set is not
  extended, because only the training distribution changes in this run; a best fixed ratio at
  the edge of the option set is recorded as a limitation.
- 2026-10-07. The first launch stopped during round-one data collection, before any model was
  fitted: `Features.observe` raised on a congestion onset that followed a feedback gap longer
  than two seconds (training family `blackout`), because the knee window was empty. The fix
  keeps the previous knee in that case. It cannot change an episode that ran before, and the
  frozen V2 test panel still replays exactly. No development or test result existed at that
  point.

## Results

Run `results/jevbwe-typed-v3-broad`, 5 model seeds. Audits: `audit_development.json`,
`audit_test.json`. The test panel was evaluated once, with config and code unchanged after
the development panel was read.

### Training families (validation panel, 13 families x 16 trace seeds)

| Method | Utility | Unsafe % | Minus train-selected fixed [seeds] | ECE |
|---|---:|---:|---|---:|
| Fixed 1.05 (train-selected) | 0.863 | 3.52 | | |
| Typed head (RLCD, payoff-weighted) | 0.989 | 2.50 | +0.126 [+0.108, +0.143] | 0.023 |
| Exact-gradient control | 0.989 | 2.49 | +0.126 [+0.110, +0.142] | 0.020 |
| Regression control | 0.979 | 2.71 | +0.116 [+0.100, +0.132] | |
| Most probable option | 0.946 | 3.18 | +0.083 [+0.068, +0.099] | 0.020 |
| Hindsight oracle | 1.111 | 3.09 | +0.248 [+0.234, +0.262] | |

Fixed-ratio tune sweep on training families: 0.60 0.230, 0.70 0.282, 0.80 0.554, 0.90 0.788,
1.00 0.817, 1.05 0.825. The selected confidence threshold was 0.0 for every seed, so the
gated rule coincides with the most probable option.

### Untouched test families (12 families x 24 trace seeds, one evaluation)

The train-selected fixed ratio (1.05) is also the hindsight-best fixed ratio on this panel.

| Pre-specified endpoint | Result | Criterion | Met |
|---|---|---|---|
| Gain over train-selected fixed | +0.054; seeds [+0.045, +0.063]; family bootstrap [+0.006, +0.107]; family t [-0.005, +0.112]; 7 of 12 families positive | both family-level intervals exclude zero | **no** (t interval includes zero) |
| Calibration | pooled ECE 0.070, family-level [0.016, 0.153]; worst family `low_rate` 0.427 | pooled ECE <= 0.05 | **no** |
| Constraints | unsafe 1.27% against 1.98%: -0.72 points, family-level [-1.24, -0.26]; floor 0.94% | upper end <= +1.0 point | **yes** |

| Contrast (utility) | Difference | Seeds | Family bootstrap | Family t | Families > 0 |
|---|---:|---|---|---|---:|
| Typed head minus train-selected fixed | +0.054 | [+0.045, +0.063] | [+0.006, +0.107] | [-0.005, +0.112] | 7/12 |
| Exact-gradient control minus train-selected | +0.057 | [+0.048, +0.066] | [+0.004, +0.113] | [-0.006, +0.120] | 7/12 |
| Regression control minus train-selected | +0.050 | [+0.044, +0.056] | [+0.014, +0.091] | [+0.005, +0.095] | 8/12 |
| Most probable option minus train-selected | +0.027 | [+0.018, +0.035] | [+0.001, +0.062] | [-0.008, +0.061] | 6/12 |
| Hindsight oracle minus train-selected | +0.148 | [+0.137, +0.158] | [+0.080, +0.216] | [+0.070, +0.227] | 10/12 |
| RLCD minus exact gradient | -0.003 | [-0.008, +0.002] | [-0.013, +0.006] | [-0.009, +0.003] | 4/12 |
| RLCD minus regression | +0.004 | [-0.005, +0.013] | [-0.020, +0.030] | [-0.023, +0.031] | 7/12 |

The regression control clears the gain rule that the RLCD head narrowly misses. The three
learned methods are within noise of one another, so this says nothing about the recipe.

| Family | Train-sel. 1.05 | Hindsight-best fixed | Typed | Typed minus train-sel. [seeds] | Regression | Oracle | Unsafe %: floor / train-sel. / typed | ECE |
|---|---:|---:|---:|---|---:|---:|---|---:|
| sawtooth | 0.877 | 0.945 (0.85) | 1.077 | +0.199 [+0.156, +0.245] | 0.996 | 1.110 | 0.00 / 3.08 / 0.81 | 0.093 |
| square_wave | 0.774 | 0.862 (0.85) | 0.977 | +0.203 [+0.150, +0.256] | 0.895 | 1.105 | 0.00 / 1.88 / 0.59 | 0.240 |
| staircase | 1.012 | 1.012 (1.05) | 0.948 | -0.063 [-0.123, -0.002] | 1.014 | 1.164 | 0.00 / 1.03 / 1.32 | 0.100 |
| slow_fade | 0.763 | 0.763 (1.05) | 0.771 | +0.008 [-0.010, +0.029] | 0.789 | 0.963 | 0.00 / 0.49 / 0.19 | 0.120 |
| low_rate | 0.489 | 0.567 (0.80) | 0.495 | +0.006 [-0.001, +0.014] | 0.490 | 0.690 | 0.00 / 0.91 / 0.72 | 0.427 |
| long_path | 0.708 | 0.708 (1.05) | 0.834 | +0.126 [+0.068, +0.187] | 0.869 | 0.984 | 0.00 / 2.22 / 0.01 | 0.078 |
| jitter_storm | 0.623 | 0.623 (1.05) | 0.597 | -0.026 [-0.061, +0.010] | 0.608 | 0.651 | 0.06 / 0.19 / 0.06 | 0.054 |
| micro_outage | -1.246 | -1.246 (1.05) | -1.247 | -0.000 [-0.002, +0.000] | -1.248 | -1.241 | 11.19 / 11.20 / 11.19 | 0.088 |
| feedback_flap | 0.433 | 0.433 (1.05) | 0.428 | -0.006 [-0.012, -0.000] | 0.425 | 0.433 | 0.00 / 0.00 / 0.00 | 0.029 |
| shallow_buffer | 1.134 | 1.134 (1.05) | 1.288 | +0.154 [+0.106, +0.200] | 1.302 | 1.422 | 0.00 / 1.47 / 0.10 | 0.055 |
| lossy_link | 0.419 | 0.419 (1.05) | 0.419 | +0.000 [+0.000, +0.000] | 0.419 | 0.419 | 0.00 / 0.00 / 0.00 | 0.010 |
| compound | 0.616 | 0.616 (1.05) | 0.661 | +0.045 [+0.023, +0.066] | 0.642 | 0.679 | 0.00 / 1.34 / 0.20 | 0.040 |

In `lossy_link`, `feedback_flap` and `micro_outage` every method, the hindsight oracle
included, is within 0.01 of the fixed ratio: the estimator or the governor pins the rate and
the ratio is immaterial. These families were written blind, they carry no information about
the controller, and they pull every family-level mean toward zero. They stay in every
headline result. An analysis restricted to action-sensitive families would be post hoc and
diagnostic only; none is reported.

Run-time isolation: replaying all 7,200 learned test episodes (and all 6,600 development
episodes) with rollouts switched off reproduces every outcome with maximum difference 0, and
recomputing the payoff-weighted rule from the recorded probabilities reproduces 100% of the
options that ran.

### Development families (the V2 frozen panel's traces; not held-out)

| Panel | V3 typed minus its train-selected 1.05 | Family t | Families > 0 | Pooled ECE (V2 -> V3) | V3 minus V2 typed head, paired [seeds] | Family t |
|---|---:|---|---:|---|---|---|
| 7 development families | +0.008 | [-0.088, +0.104] | 3/7 | 0.152 -> 0.058 | +0.043 [+0.036, +0.050] | [-0.039, +0.124] |
| 4 legacy training families | +0.202 | [+0.125, +0.280] | 4/4 | 0.012 -> 0.054 | -0.031 [-0.054, -0.004] | [-0.092, +0.031] |
| all 11 | +0.079 | [-0.008, +0.166] | 7/11 | 0.094 -> 0.040 | +0.016 [+0.007, +0.026] | [-0.038, +0.070] |

Fixed-ratio outcomes on these traces are identical in both runs (maximum difference 0), which
confirms the pairing. Broadening helps the development families on average and costs a little
on the original four, where the same network and half the per-family data are spread over 13
families. `capacity_surge` is the largest loss: the head moves below a base that is right
almost throughout (1.652 against 1.831).

## What this run does and does not show

- A positive mean gain on untouched families (+0.054), fewer unsafe intervals and better
  calibration than V2 had on its held-out families. Not an established gain: the family-level
  t interval includes zero and the calibration threshold is missed.
- No advantage for RLCD-style training over exact-gradient or regression controls.
- The train-selected ratio is the top of the option set, so the head could only move down.
  Whether a wider option set changes the picture is open, and testing it needs new test
  families: these twelve have now been read.
- Three of twelve test families are insensitive to the controlled ratio. A future test set
  should be checked for sensitivity with a policy-independent criterion fixed in advance.
- The test families reuse the simulator's trace signals. They are unseen families, not
  unseen physics, and nothing here is a native or real-network result.

## Next steps (none started)

1. New untouched test families before any further iteration; these twelve are now
   development families.
2. Per-family or context-conditional calibration, since pooled calibration hides
   family-level error even in distribution.
3. An option set whose upper edge is not the train-selected ratio.
4. The native track stays separate: factual labels and the frozen native controller study
   are not replaced by anything in this document.
