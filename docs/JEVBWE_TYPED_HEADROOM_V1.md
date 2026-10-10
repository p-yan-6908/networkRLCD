# Typed control: hindsight headroom when the option set stops at the estimate (V1)

**Synthetic, development evidence, no model.** Both population panels used here have been read
before. Nothing is trained, selected or tested, and nothing is promoted.

## Why

[Native Phase N1](NATIVE_PHASE_N1_RESULT.md) qualified the native actuator and showed what kind
of actuator it is: a cap on the encoder's maximum bitrate. A cap cannot push the encoder above
the rate the browser's own congestion controller allots, and at a requested ratio of 1.05 the
encoder sat at 0.83 of the estimate.

The typed-control studies let the simulated sender follow any of six ratios, 0.6 to 1.05 of the
estimate. The fixed ratio selected on training traces is 1.05, the top option, in the broadened
run and in the population run, and the baseline audit found it an interior optimum of an
extended grid. A learned controller's simulated gain could therefore come from two different
places: from backing off below the estimate at the right moments, which a cap can do, or from
sending above it, which a cap cannot.

## Question

How much of the hindsight headroom that the simulator offers a controller survives when the
top options are removed from the option set?

## Design, fixed before the run

- **Simulator and configuration:** those of the population run
  (`results/jevbwe-typed-v4-population/config.json`), unchanged except for the option set.
- **Option sets:** the six options as studied (top 1.05, the reference), the five up to 1.00,
  and the four up to 0.90. In each, the governor's ceiling is the top option times the
  estimate, as it always was.
- **Fixed-ratio baseline per set:** re-selected among that set's options on the 512 tune traces
  of the 64 development-pool families, by the unchanged tuning step.
- **Hindsight oracle per set:** the unchanged greedy oracle over that set's options, with the
  set's own base ratio in the rollout tail.
- **Panels and traces:** the 48 families of `pop_r` with the replication's 16 trace seeds and
  the 48 families of `pop_s` with the sealed test's 16 trace seeds, so every figure pairs with
  the earlier ones.
- **Quantities, per set and panel:** utility and unsafe share of every fixed ratio and of the
  oracle; headroom, defined as oracle minus the set's selected fixed ratio; the share of
  oracle decisions at each option.
- **Against the reference set, on identical traces:** the change in the fixed baseline, in the
  oracle and in the headroom; the truncated oracle minus the reference fixed ratio; and the
  truncated headroom as a share of the reference headroom.
- **Uncertainty:** family-level, as in every typed study: a t interval on family-level mean
  differences, with the family bootstrap alongside.

**Reading, fixed in advance, per panel and truncated set:**

| Reading | Rule |
|---|---|
| the opportunity lies **below** the removed options | the truncated headroom is at least 75% of the reference headroom |
| the opportunity lies **above** | it is under 50%, and the family-level interval of the change in headroom is entirely below zero |
| **mixed** | anything else |

## What it can and cannot show

- The oracle is a hindsight bound. The learned heads captured 18% to 25% of it, so a headroom
  that survives truncation shows an opportunity, not a controller that takes it.
- Removing options is the simulator's nearest equivalent of a cap that cannot exceed the
  estimate. It is not a model of the native stack: the simulator's estimator is a simple
  bounded AIMD, not the browser's congestion controller, and its encoder takes up a request
  exactly.
- It does not test whether a head trained on a truncated set would capture the surviving
  headroom. That would need a new training run and a newly registered panel.

## Command

```sh
make jevbwe-typed-headroom
```

## Results

Run on 2026-10-10 in six minutes. No model was trained or loaded. Output:
`results/typed-headroom-v1/report.json`. Brackets are family-level t intervals over 48
families.

| Top option | Fixed ratio selected | Panel | Fixed | Oracle | Headroom | Share of reference headroom | Reading |
|---:|---:|---|---:|---:|---|---:|---|
| 1.05 | 1.05 | `pop_r` | 0.082 | 0.192 | +0.110 [+0.083, +0.137] | | reference |
| | | `pop_s` | 0.174 | 0.296 | +0.122 [+0.092, +0.153] | | reference |
| 1.00 | 1.00 | `pop_r` | 0.087 | 0.172 | +0.085 [+0.062, +0.109] | 78% | **below** |
| | | `pop_s` | 0.175 | 0.276 | +0.101 [+0.075, +0.128] | 83% | **below** |
| 0.90 | 0.90 | `pop_r` | 0.048 | 0.089 | +0.040 [+0.025, +0.055] | 37% | above |
| | | `pop_s` | 0.140 | 0.202 | +0.062 [+0.042, +0.082] | 51% | mixed |

Against the reference set on identical traces:

| Top option | Panel | Fixed | Oracle | Headroom | Truncated oracle minus reference fixed |
|---:|---|---|---|---|---|
| 1.00 | `pop_r` | +0.005 [-0.003, +0.012] | -0.020 [-0.027, -0.013] | -0.024 [-0.032, -0.017] | +0.090 [+0.064, +0.115] |
| | `pop_s` | +0.002 [-0.005, +0.008] | -0.020 [-0.026, -0.013] | -0.021 [-0.027, -0.015] | +0.103 [+0.074, +0.132] |
| 0.90 | `pop_r` | -0.034 [-0.052, -0.015] | -0.103 [-0.130, -0.076] | -0.069 [-0.088, -0.051] | +0.007 [-0.024, +0.038] |
| | `pop_s` | -0.034 [-0.050, -0.019] | -0.094 [-0.114, -0.074] | -0.060 [-0.077, -0.043] | +0.028 [-0.003, +0.059] |

The oracle sits at its set's top option in most decisions: 76% and 75% at 1.05 in the
reference set (3% at 1.00), 80% and 78% at 1.00, 89% and 87% at 0.90. Against its own fixed
ratio it lowers the unsafe share by 0.80 and 0.70 points in the reference set, 0.43 and 0.50
with the top at 1.00, and 0.22 and 0.28 with the top at 0.90.

## Reading

- **The option above the estimate is not where the opportunity is.** With the top option at
  1.00, a fixed policy loses nothing (fixed 1.00 scores +0.005 and +0.002 against fixed 1.05,
  intervals include zero), the oracle loses 0.020, and 78% and 83% of the hindsight headroom
  remain. By the rule fixed in advance the reading is *below* on both panels: what hindsight
  offers a controller in this simulator is mostly the chance to back off at the right moment.
  A cap can do that.
- **So the native cap's ceiling does not by itself void the synthetic results.** It removes
  about a fifth of the hindsight headroom. This agrees with the earlier finding that fixed
  1.00 is the hindsight-best fixed ratio on `pop_r`.
- **Running persistently under the estimate is costly in the simulator.** With the top at
  0.90 the fixed policy loses 0.034 and the headroom falls to 37% and 51% of the reference.
  Part of this is a side effect and not a removal of options: the governor's ceiling is the
  top option times the estimate, and when the estimate sits at its floor of 150 kbit/s a
  ceiling of 0.90 holds the sender under the application's minimum rate. On a sample of 24
  `pop_r` traces that happens in about 15% of the control steps of a fixed 0.90 policy, and
  it lowers the utility of every fixed ratio in that set (0.90 itself scores 0.077 on `pop_r` under the two wider sets and 0.048
  under this one). The 0.90 row is therefore an upper bound on the cost of a lower ceiling in
  this simulator, not a clean measurement of it.

## Against the native pilot

The two pieces of evidence point in different directions and are not reconciled.

- Here, in hindsight and in a simulator, most of the opportunity is in backing off below the
  estimate at chosen moments.
- In the [native pilot](NATIVE_PHASE_N1_EXPLORATORY.md), under four configured schedules, no
  lower ratio scored better than a higher one, and the encoder sat at 0.83 of the estimate
  even at the top ratio.

Both can hold. A hindsight oracle picks moments, and the pilot averaged over whole schedules.
The simulator's estimator is a simple bounded AIMD, and the browser's own congestion
controller may already take the backoff that the oracle exploits. The simulator's encoder
takes up a request exactly, and the native one did not. Which of these explains the
difference is what a state-conditional native measurement would answer. Nothing here shows
that a learned controller would gain on a native stack.

## Note on the code

After the run, the share of the reference headroom was made undefined when the reference set
offers none (a case a tiny test panel produced, and the run did not). The report above was
not regenerated and is unaffected.
