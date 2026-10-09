# Typed-control factual supervision V1: what one option per decision can teach

Status: **design written 2026-10-08, before the study ran.** Results are appended below the
design and do not change it. Development study on training families, synthetic only. It makes
no confirmatory claim and touches neither sealed population panel.

**Outcome.** Factual supervision is identifiable in this simulator, and expensive. From 20,000
randomised blocks (36 hours of link time) the factual pipeline's closed-loop gain over the
fixed ratio is established at family level, and at 320,000 blocks (571 hours) it reaches
+0.105, positive in 13 of 13 training families. A control trained on rollout labels reaches
+0.109 with 5,000 labelled states (9 hours): the same gain for about a sixtieth of the link
time. At equal budgets the factual pipeline is behind by 0.095, 0.073 and 0.044 at 5,000,
20,000 and 80,000 blocks. The curve is flat between 320,000 and 1,280,000 blocks, and the
optimiser may be the reason. In distribution only; a floor for a real network, not an estimate.

## Why

Every learned result in this track uses hindsight rollouts: at each decision the simulator is
forked and all six options are played against the same future. That gives a label for the
best option and, more importantly, differences between options with the future held fixed.
A real network gives neither. It shows the outcome of the one option that ran.

The native route therefore depends on a question the simulator can answer and the native
system cannot: **how much of the rollout-supervised gain survives when the learner sees only
factual outcomes, and how much randomised link time does that take?** If the answer is tens of
hours, a native learned controller is a data-collection problem. If it is thousands, the native
route needs a different idea, whatever Phase N1 finds about the actuator.

The earlier factual attempt (`docs/JEVBWE_RLCD_V1.md`) used 432 cohorts and an event that
barely depended on the action, so it could not answer this.

## Design

`src/media_rl/typed_bitrate_factual.py`. Network, estimator, governor, options, features,
base ratio (1.05) and validation traces are those of the frozen V3 run, which is only read.

**Factual blocks.** Episodes run the base ratio on fresh traces of the 13 training families. At
a free one-second decision epoch a block starts with probability 0.5: one of the six options is
drawn uniformly, held for the 3 s commit window and followed by the base ratio for the 2 s
tail. The label is the mean utility of those 5 s. This is the estimand of a rollout label,
observed for one option, and the code checks that the two agree exactly for the executed
option. Blocks do not overlap. The propensity is known and uniform.

**Factual pipeline.** Uses states, executed options and block outcomes only.

1. Split the blocks by episode: 70% fit, 10% early stopping, 20% selection.
2. Fit one network (the V3 regression head's size and optimiser) with six outputs, one value
   per option; each row contributes loss on its executed option only. Stop on held-out loss.
3. On the selection blocks, estimate with a doubly-robust estimator the value of acting
   whenever the best predicted advantage over the base exceeds a margin, for margins 0 to
   0.2. Take the best margin; if no margin has a positive estimated gain, never act.
4. Deploy through the unchanged V3 greedy rule and guards.

**Rollout control.** The same rows, split and network, but trained on the rollout advantage of
all six options and with its margin chosen from rollout values. The two pipelines differ in
the label source and in nothing else, so their difference is the price of factual supervision
at a given number of labelled states.

**Budgets.** 5,000, 20,000, 80,000, 320,000 and 1,280,000 blocks, nested, three
data-and-optimiser seeds. At about 5.3 blocks per 36 s episode these are roughly 9, 38, 150,
600 and 2,400 hours of link time. V3 used 65 hours of simulated link time with 208,000
rollout-labelled decisions. Rollout values cost about forty times a factual block to compute,
so the control is trained on the first three budgets only; the factual pipeline needs none.
Both pipelines may take 20,000 optimiser updates or 30 passes over the fit rows, whichever is
more, with early stopping.

**Scoring.** Evaluation only; no pipeline step reads it.

- Closed loop on the 208 validation traces (13 training families by 16 seeds), paired with the
  frozen fixed ratio: utility and unsafe share with family-level intervals, the three seeds
  taking the place of model seeds.
- Offline on the states the base policy visits on those traces: the true rollout advantage of
  the option each head would choose, and the correlation of predicted with true advantage.
- Both with the selected margin and with margin zero.

References on the same traces: the frozen V3 regression head and RLCD head. They had five
rounds of on-policy aggregation, which neither pipeline here has, so they are context and not
a like-for-like bar.

## How the outcome will be read

Fixed before the run:

- **Identified at a budget:** the factual pipeline's closed-loop gain over the fixed ratio has
  a family-level t interval that excludes zero.
- **Price of factual supervision at a budget:** rollout control minus factual pipeline, paired,
  with the same interval.
- A factual pipeline that selects "never act" scores exactly the fixed ratio. That is a correct
  outcome of the procedure, not a failure of it, and is reported as zero gain.
- No budget beyond 1,280,000 blocks is planned. A curve still rising there is reported as
  rising.

## What this can and cannot show

- It measures one reasonable factual pipeline. A better one may exist; the rollout control
  bounds what any learner could get from these states.
- In distribution only. Unseen families are a separate axis and are not tested here.
- The simulator is deterministic given the trace, the telemetry is exact and the utility is
  observed without error. A real network adds measurement noise, non-stationarity and an
  encoder that may not follow the request. The link time found here is therefore a floor for
  the native requirement, not an estimate of it.
- Collection runs the base ratio between blocks. A deployed system would aggregate under its
  own policy, as V3 did; that is not tested.
- Nothing here is a native or real-network result.

## Reproduce

```bash
make jevbwe-typed-factual TYPED=results/regen   # needs the frozen V3 run under results/regen
```

## Run log

- 2026-10-08, first launch from commit `7ecfb9b`: stopped after 34 minutes, during data
  collection for the first seed. Building the ordered history state at every control step made
  a factual episode cost about 0.1 s, so the largest budget alone needed 45 minutes per seed.
  No model had been fitted and no result existed or was read. The collector now builds that
  state only where a block starts; a test checks that the rows are identical either way, and
  seeds, budgets, pipelines and reading rules are unchanged.

- 2026-10-08, second launch from commit `9cb660d`: completed in 63 minutes.

## Results

Three seeds, each with about 1.32 million factual blocks in 235,000 episodes (5.6 blocks per
episode) and rollout values on the first 82,000 blocks. Checks: a factual block's outcome
equals the rollout value of its option on every row that has both (largest difference 0), and a
packaged head that never acts reproduces the frozen fixed-ratio validation outcomes exactly.

### Learning curves (13 training families, 16 validation traces each; family-level t intervals)

| Blocks | Link hours | Factual minus fixed | Families above zero | Rollout control minus fixed | Factual minus control | Offline advantage, factual / control | Margins chosen by the factual pipeline |
|---:|---:|---|---:|---|---|---|---|
| 5,000 | 9 | +0.014 [-0.006, +0.034] | 9/13 | +0.109 [+0.057, +0.160] | -0.095 [-0.128, -0.062] | +0.004 / +0.047 | 0.05, never, never |
| 20,000 | 36 | +0.047 [+0.015, +0.078] | 11/13 | +0.119 [+0.071, +0.168] | -0.073 [-0.095, -0.050] | +0.018 / +0.050 | 0.05, 0.2, never |
| 80,000 | 143 | +0.078 [+0.029, +0.127] | 9/13 | +0.122 [+0.073, +0.170] | -0.044 [-0.058, -0.030] | +0.026 / +0.052 | 0.1, 0, 0.2 |
| 320,000 | 571 | +0.105 [+0.052, +0.159] | 13/13 | not run | | +0.040 | 0.05, 0.05, 0.02 |
| 1,280,000 | 2,283 | +0.106 [+0.059, +0.153] | 13/13 | not run | | +0.045 | 0, 0.01, 0.02 |

References on the same traces: frozen V3 regression head +0.116 [+0.061, +0.171], frozen V3
RLCD head +0.126 [+0.079, +0.173]. Offline, the hindsight oracle's advantage over the base
ratio is +0.123 per decision on the 6,656 states the base policy visits.

The factual pipeline lowers the unsafe share at every budget (-0.33, -0.59, -0.84, -0.75 and
-0.99 points against the fixed ratio).

### Reading, by the rules fixed in the design

- **Identified from 20,000 blocks.** The family-level t interval of the factual gain excludes
  zero at 20,000 blocks and at every larger budget. At 20,000 the family bootstrap interval is
  [+0.000, +0.103], so that budget is the edge. At 5,000 blocks the gain is not identified; in
  two of three seeds the selection step found no margin with a positive estimated gain and the
  head never acted, which is the procedure working as intended.
- **Price of factual supervision.** At 5,000, 20,000 and 80,000 blocks the factual pipeline is
  0.095, 0.073 and 0.044 below the rollout control on identical rows, and every interval
  excludes zero. The gap narrows as data grows.
- **The curve.** +0.105 at 320,000 blocks and +0.106 at 1,280,000.

### Observations made after the result

These were not specified in advance.

- **About sixty times the link time.** The rollout control reaches +0.109 with 5,000 labelled
  states. The factual pipeline first matches that at 320,000 blocks.
- **Choosing when to act matters as much as predicting.** With the margin fixed at zero the
  factual pipeline gains -0.012, +0.037, +0.040, +0.079 and +0.105 across the five budgets.
  The doubly-robust margin adds 0.03 to 0.04 in the middle of the curve and removes the loss at
  the smallest budget.
- **The plateau may be the optimiser's.** Early stopping ended every fit after 2,500 to 9,500
  updates. At 1,280,000 blocks that is under three passes over the fit rows, at a learning rate
  that had barely decayed. Offline advantage and correlation still rise between the last two
  budgets (+0.040 to +0.045, 0.47 to 0.51). "More data stops helping" is therefore not
  established; "this pipeline stops improving" is.
- **Rollout supervision saturates very early in distribution.** A control with 5,000 labelled
  states and no on-policy aggregation is within 0.01 of the frozen V3 regression head, which
  used 208,000 labelled decisions over five aggregation rounds. Collection under the base
  policy was not a visible handicap on this panel.

### What this means for the native route

Not results; consequences to weigh.

- A randomised-block design with known propensities can identify a useful bitrate policy from
  factual outcomes, and a doubly-robust selection step can decline to act when the data are
  too thin. The native route is not blocked in principle by the absence of rollouts.
- It is costly. Tens of hours of randomised link time were needed to see any gain and hundreds
  to approach rollout quality, in a deterministic simulator with exact telemetry, an exactly
  observed utility, thirteen known families and an actuator that follows the request. Each of
  those is easier than the native case. The requirement found here is a floor.
- Nothing here tests unseen families. The rollout-trained heads keep +0.019 of their +0.126 on
  the population panel (`docs/JEVBWE_TYPED_V3_REPLICATION.md`); a factual learner has no reason
  to keep more.
- Phase N1 still comes first: none of this helps if the encoder does not follow a
  BWE-relative request.

Tracked summary: `results/typed-factual-v1/report.json` and `settings.json`.
