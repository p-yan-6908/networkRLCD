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

Not yet run at this commit.
