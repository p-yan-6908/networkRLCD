# Typed-control factual supervision V1: what one option per decision can teach

Status: **design written 2026-10-08, before the study ran.** Results are appended below the
design and do not change it. Development study on training families, synthetic only. It makes
no confirmatory claim and touches neither sealed population panel.

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

## Results

None yet. The study has not been run.
