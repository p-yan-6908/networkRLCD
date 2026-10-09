# Typed-control V4: training on the family population, tested on a sealed panel

Status: **protocol registered 2026-10-08, before any V4 model was trained.** Results are
appended below the protocol and do not change it.

Simulator study in the synthetic track. It trains new typed heads with the V3 method and
changes the training distribution only. The native controller freeze and the registered native
Phase N1 are untouched and are not informed by it.

## Why

The V3 replication (`docs/JEVBWE_TYPED_V3_REPLICATION.md`) found, on 48 families drawn from a
stated population:

- a gain over the train-selected fixed ratio that is established and small (+0.019, 18% of the
  hindsight oracle's gain, against +0.126 in distribution);
- over-confident probabilities (ECE 0.138);
- a train-selected fixed ratio (1.05) that is not the best fixed ratio on the population
  (1.00), so that part of the gain is a lower average ratio.

All three point at one cause. The V3 heads, their calibration and their base ratio were fitted
on 13 hand-written families, and the claim is about a population those families were not drawn
from. V4 removes that mismatch and nothing else: the training families are draws from the same
population as the test families. The estimand becomes the ordinary one for generalisation:
train on a sample of families, test on unseen families of the same population.

## What changes and what does not

Only the training distribution (`configs/jevbwe_typed_v4_population.json`):

| | V3 | V4 |
|---|---|---|
| Training families | 13 hand-written | the 64 families of the development pool `pop_d` |
| Episodes per aggregation round | 1,300 (100 per family) | 1,280 (20 per family) |
| Rollout-labelled episodes per model seed | 6,500 | 6,400 |
| Tune episodes (base ratio and rule) | 208 | 512 (8 per family) |
| Calibration episodes per head | 260 | 256 |
| Validation panel | 13 families by 16 seeds | 64 families by 4 seeds |

Features, labels, margin, heads, optimiser, aggregation rounds, exploration, decision rules,
guards, option set, estimator, governor and the five model seeds are V3's. There is no new
architecture, no recalibration method and no wider option set. The fixed ratio that serves as
base policy and as the bar is re-selected on the `pop_d` tune traces, and the tuned rule is
re-selected on the same traces from the class declared in `typed_bitrate_baselines.py`.

## Data roles

| Space | Families | Role in V4 |
|---|---:|---|
| `pop_d` | 64 | every fitting step: tuning, rollout labels, aggregation, calibration, validation |
| `pop_r` | 48 | development. Already read by the V3 replication. Evaluated after training on the replication's traces, so V4 and V3 are paired |
| `pop_s` | 48 | sealed test. One evaluation, after models and comparators are frozen by hash |

No controller, fixed ratio or oracle has run on `pop_s` at registration.

## Sequence

1. **Train** five model seeds and evaluate the validation panel
   (`jevbwe-typed run --splits validation`).
2. **Development.** Evaluate the V4 models on `pop_r` with `jevbwe-typed transfer`, audit them
   paired with the V3 replication, and replay the tuned rule.
3. **Freeze.** Record the SHA-256 of the five model files, the selected base ratio and the
   tuned rule in `configs/jevbwe_typed_v4_test.json` and commit it.
4. **Test.** Evaluate the V4 models once on `pop_s` (16 trace seeds, 29401 to 29416). Evaluate
   the frozen V3 models once on the same traces (`configs/jevbwe_typed_v3_on_sealed.json`,
   registered with this protocol). Replay, audit and rule comparison follow as for the
   replication.

Rules:

- The test is run whatever the development panel shows. A model that looks worse than V3 on
  `pop_r` is still tested, and the result is reported.
- Between steps 1 and 4 config and code stay as committed unless a step exposes a defect. Any
  such change is recorded here before the test.
- No family is excluded for any reason.
- After the test `pop_s` is a development panel.

## Pre-specified test endpoints (`pop_s`)

Primary method: `choice_rlcd_bayes`. Comparators: the fixed ratio and the tuned rule selected
on `pop_d` tune traces. Family-level uncertainty as before: a bootstrap over families, traces
within families and model seeds (5,000 resamples), and a t interval over the 48 family-level
mean differences.

1. **Gain over the train-selected fixed ratio.** Both family-level intervals exclude zero.
2. **Gain over the tuned rule.** Both family-level intervals exclude zero.
3. **Calibration.** Pooled top-label ECE (10 bins) at most 0.05.
4. **Constraints.** Upper end of the family-clustered interval of the unsafe-share difference
   to the fixed ratio at most +1.0 percentage point.

The criteria and thresholds are those of the V3 replication.

Secondary, reported whatever the outcome:

- **V4 minus V3 on the sealed panel**, paired on identical traces. "Training on the population
  generalises better than training on hand-written families" is claimed only if both
  family-level intervals exclude zero. Each head is run with its own base ratio.
- The frozen V3 models against their own fixed ratio on `pop_s`: a second replication of V3.
- The difference to the fixed ratio that is best on the panel in hindsight, and the hindsight
  oracle, as bounds.
- The exact-gradient and regression controls. An RLCD-specific advantage is claimed only if
  such an interval excludes zero.
- Action-sensitive families (hindsight oracle gains at least 0.02 over the fixed ratio):
  criteria 1 and 2 recomputed, diagnostic only.
- Per-family ECE range; `map` and `gated` rules; leave-one-family-out range.

**Precision.** The family-level gains of the V3 replication have a standard deviation of 0.049.
With the same spread, 48 families give a t-interval half-width of 0.014.

## How the outcome will be read

| Outcome | Reading |
|---|---|
| 1 to 4 met | With training families drawn from the test population, rollout-supervised typed control generalises to unseen families with calibrated probabilities, in this simulator. No promotion: that needs native evidence. |
| 1, 2 and 4 met, 3 not | The gain generalises and the probabilities do not. Calibration is then a property to fix or to stop claiming, not a consequence of the training distribution alone. |
| 1 met, 2 not | The head beats a fixed ratio but not a tuned rule by an established margin. |
| 1 not met | Even with matched training families there is no established gain on unseen families. Further iteration on the training distribution is not justified. |

The size of the gain is reported next to the hindsight oracle's and next to the in-distribution
gain on the validation panel, whatever the verdicts.

In every case the labels are hindsight rollouts in a forked simulator. The result says nothing
about what a real network can supply (`docs/JEVBWE_TYPED_FACTUAL_V1.md` addresses that) and
nothing about a native system.

## Reproduce

```bash
make jevbwe-typed-population TYPED=results/regen        # steps 1 and 2
make jevbwe-typed-population-test TYPED=results/regen   # step 4, after the freeze
```

## Run log

- 2026-10-08, training launched from commit `04f13b4`. Since the registration commit
  (`c1e7192`) the code gained the `register` and `followup` commands and a guard in the factual
  module; nothing V4 executes changed except that the development registration is written by
  `register`. The base ratio selected on the 512 `pop_d` tune traces is 1.05.

- 2026-10-09, training, validation and the development panel completed (training and
  validation 72 minutes, development 46). Between the training launch and the freeze, commit
  `c811b0a` changed the evidence exporter, documents and the paper only.
- 2026-10-09, freeze: `configs/jevbwe_typed_v4_test.json` written by `jevbwe-typed register`
  from the five trained model files and committed with these development results, before any
  controller ran on `pop_s`.

## Results

### Validation: the 64 training families, fresh traces (4 each)

| Quantity | Result (family-level t interval) |
|---|---|
| Base ratio selected on 512 tune traces | 1.05 (0.1556 against 0.1548 for 1.00) |
| Tuned rule selected on the same traces | `delay(high=1.05, low=1.0, on_ms=50, off_ms=10)` |
| RLCD head minus fixed 1.05 | +0.029 [+0.007, +0.052], 33 of 64 families |
| Regression head minus fixed 1.05 | +0.046 [+0.023, +0.069], 40 of 64 |
| RLCD minus regression head | -0.017 [-0.025, -0.008] |
| RLCD minus exact-gradient head | -0.000 [-0.002, +0.002] |
| Hindsight oracle minus fixed 1.05 | +0.087 [+0.062, +0.113] |
| Pooled ECE of the RLCD head | 0.008 |
| Unsafe intervals, RLCD head | -0.73 points |

In distribution the population is a harder target than the 13 hand-written families were. V3
gained +0.126 of an oracle headroom of +0.248 on its own training families; V4 gains +0.029 of
+0.087 on its own.

### Development: `pop_r`, the traces of the V3 replication (48 families by 16 traces)

Not confirmatory: `pop_r` had been read. All 19,200 learned episodes replay exactly without
rollouts, and the fixed-ratio outcomes are identical to the replication's (largest difference
0), so the last column is paired.

| Quantity | V4 (trained on `pop_d`) | V3 (replication) | V4 minus V3 |
|---|---|---|---|
| RLCD head minus fixed 1.05 | +0.012 [-0.014, +0.038], 25 of 48 | +0.019 [+0.005, +0.034], 32 of 48 | -0.008 [-0.038, +0.023] |
| RLCD head minus tuned rule | +0.012 [-0.014, +0.038] | +0.020 [+0.004, +0.035] | |
| Regression head minus fixed 1.05 | +0.024 [+0.006, +0.041], 35 of 48 | +0.021 [+0.005, +0.037], 29 of 48 | +0.002 [-0.020, +0.025] |
| RLCD minus regression head | -0.012 [-0.024, +0.001] | -0.002 [-0.006, +0.003] | |
| Pooled ECE | 0.037 | 0.138 | |
| Families with ECE above 0.05 | 39 of 48 | 35 of 48 | |
| Unsafe intervals, points | -0.86 [-1.14, -0.62] | -0.26 [-0.38, -0.16] | -0.60 |
| Decisions that leave the base ratio | 32% | 7% | |

Reading, for development only:

- Training on draws from the population did not raise the typed head's gain on other draws.
  The point estimate is lower than V3's and its interval now includes zero, because the head
  acts in a third of decisions instead of a fourteenth and families spread further apart.
- Pooled calibration improved to within the threshold. Family by family it did not: ECE exceeds
  0.05 in 39 of 48 families.
- Unsafe intervals fall by more than under V3.
- The regression control is ahead of the typed head in distribution and on the development
  panel, which is a first in this track. The typed label says which option is best; the
  regression target says by how much.

As registered, the test is run whatever this panel shows.

### Test: `pop_s`

Not run yet.
