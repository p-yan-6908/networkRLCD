# Typed-control baseline audit: is the fixed ratio a weak comparator?

Status: **analysis of frozen runs, 2026-10-08. Synthetic only.** No model was fitted or
changed. Rule parameters were selected on the 208 training-family tune traces that selected
the base ratio. The development and test panels of V3 had already been read, so everything
reported on them here is post hoc; it qualifies the V3 comparison and replaces none of it.

**Outcome.** The comparator was not weak in either way that was open. The fixed ratio 1.05 is
an interior optimum, not an edge of the grid: utility falls for every ratio above it. A tuned
reactive rule over the same options adds at most +0.008 on any panel, with every family-level
interval including zero. With the tuned rule as the bar instead of the fixed ratio, the V3
head's gain on its twelve former test families is +0.049 with family t interval
[-0.005, +0.104]: the same conclusion as before, not established.

## Why

`docs/JEVBWE_TYPED_V3_BROAD.md` compares the learned head with one fixed BWE ratio selected on
training families. Two things about that comparator were unresolved:

1. The selected ratio, 1.05, is the top of the six-option set. A higher ratio might have been
   better, in which case the bar was truncated by the grid.
2. A fixed ratio never reacts. A few hand-written lines that back off after congestion might
   recover the head's gain, in which case learning is not what produces it.

## What was run

`src/media_rl/typed_bitrate_baselines.py`, command `jevbwe-typed baselines`. It reads a
finished run and writes to a new directory; the frozen run is not rewritten.

**Extended fixed ratios.** 1.10, 1.20, 1.35 and 1.50 on the tune traces, with the governor's
ceiling (largest option times the estimate) raised to 1.5 so that they can take effect. For
the six frozen options the raised ceiling changes nothing (largest utility difference 0).

**A declared class of reactive rules.** Each rule picks from the head's six options at the
head's one-second decision cadence, passes through the same governor and sees only causal
telemetry. The congestion test and the capacity knee are the ones the head's features use.

| Kind | Behaviour | Grid |
|---|---|---|
| `backoff` | the reduced ratio for `hold_ms` after congestion evidence, otherwise the normal one | hold 1, 2, 4, 8 s |
| `delay` | hysteresis on RTT excess over the running floor: reduce at `on_ms`, restore at `off_ms` | on 15, 30, 50 ms; off 5, 10 ms |
| `knee` | for `hold_ms`, stay at or below `scale` times the delivered rate at the last congestion onset | scale 0.7 to 1.0; hold 2, 5, 10, 20 s |
| `ladder` | one option down on evidence, one up after `hold_ms` without any | hold 1, 2, 4 s |

The normal ratio is any option from 0.9 up and the reduced ratio any lower option: 204
candidates. The comparator, declared in the module before any rule ran on a panel, is the
single candidate with the best mean utility on the tune traces (`rule_best`). Per-kind winners
are detail.

Each selected rule was then replayed on the traces of the three frozen V3 panels. Replaying
the fixed ratio 1.05 through the new runner reproduces the frozen episodes exactly on all three
(largest difference 0), so the comparisons with the frozen head are paired.

## Results

### Tune traces (13 training families, 208 traces)

| Controller | Utility | Unsafe intervals |
|---|---:|---:|
| fixed 0.90 | 0.788 | 3.07% |
| fixed 1.00 | 0.817 | 3.66% |
| **fixed 1.05** (the base) | **0.825** | 3.94% |
| fixed 1.10 | 0.824 | 4.22% |
| fixed 1.20 | 0.796 | 4.68% |
| fixed 1.35 | 0.742 | 5.47% |
| fixed 1.50 | 0.698 | 6.41% |
| best `backoff`: 1.05 / 0.60, hold 1 s | 0.831 | 3.82% |
| best `delay`: 1.05 / 0.80, on 15 ms, off 5 ms (`rule_best`) | 0.839 | 3.87% |
| best `knee`: 1.05, scale 0.7, hold 2 s | 0.828 | 3.87% |
| best `ladder`: 1.05 / 1.00, hold 1 s | 0.825 | 3.92% |

The rule figures are the maximum over 204 candidates on the traces that selected them, so they
are optimistic. The six best candidates are all `delay` rules with the 15 ms threshold and
differ by 0.001.

### Panels (family-level, paired; utility difference, family t interval, families above zero)

| Panel | Tuned rule minus fixed 1.05 | Head minus tuned rule | Head minus fixed 1.05 | Oracle minus tuned rule |
|---|---|---|---|---|
| Validation, 13 training families | +0.008 [-0.009, +0.026], 8/13 | +0.118 [+0.075, +0.161], 13/13 | +0.126 [+0.079, +0.173], 13/13 | +0.240 [+0.181, +0.299] |
| Development, 4 legacy training families | +0.002 [-0.012, +0.017], 3/4 | +0.200 [+0.113, +0.287], 4/4 | +0.202 [+0.125, +0.280], 4/4 | +0.332 [+0.249, +0.415] |
| Development, 7 families never trained on | +0.004 [-0.002, +0.010], 2/7 | +0.005 [-0.088, +0.097], 3/7 | +0.008 [-0.088, +0.104], 3/7 | +0.111 [-0.035, +0.257] |
| Former test, 12 families | +0.004 [-0.005, +0.014], 5/12 | +0.049 [-0.005, +0.104], 5/12 | +0.054 [-0.005, +0.112], 7/12 | +0.144 [+0.071, +0.217] |

The head is `choice_rlcd_bayes`, five model seeds. The "head minus fixed" column reproduces
the V3 audit. Family bootstrap intervals for "head minus tuned rule" are [+0.075, +0.161],
[+0.149, +0.251], [-0.068, +0.069] and [+0.003, +0.098]. On the former test families the rule
lowers the unsafe share by 0.07 points and the head by 0.72 points against the fixed ratio.

The ten fixed ratios on each panel, as a check on the first question:

| Panel | 0.90 | 1.00 | 1.05 | 1.10 | 1.20 | 1.50 |
|---|---:|---:|---:|---:|---:|---:|
| Validation | 0.816 | 0.855 | 0.863 | 0.851 | 0.804 | 0.733 |
| Development (11) | 0.419 | 0.464 | 0.464 | 0.456 | 0.413 | 0.285 |
| Former test (12) | 0.490 | 0.540 | 0.550 | 0.534 | 0.521 | 0.492 |

## Reading

- **The fixed ratio was not truncated.** Utility peaks at 1.05 on the tune traces and on every
  panel, and falls on both sides. "The train-selected ratio is the top of the option set"
  remains true of the option set, and the head can still only move down from its base, but the
  bar itself would not have been higher with a wider grid.
- **A simple reactive rule does not reproduce the head's gain.** The best of 204 candidates
  adds +0.014 on the traces that selected it and +0.002 to +0.008 elsewhere. In distribution
  the head is +0.118 above it in 13 of 13 families.
- **The V3 conclusion does not move.** Against the tuned rule the head's gain on the twelve
  former test families is +0.049, positive in 5 of 12, with a t interval that includes zero.
  Rollout supervision buys something in distribution that these rules do not; whether it
  carries to unseen families is exactly as open as it was.

## Limits

- The class is four kinds of rule and 204 candidates. A better hand-written controller may
  exist; what is shown is that this declared class does not close the gap.
- The rules act at the head's cadence over the head's options. A rule that could change the
  rate every 100 ms, or pick any ratio, would be a different actuator and is not tested.
- Under every method the estimator already reacts to delay and loss and the governor already
  cuts on congestion evidence. "Fixed ratio" is therefore a reactive controller with a fixed
  gain, which is why a second reactive layer adds little. It is not a tuned libwebrtc GCC.
- The development and former test families had been read before this audit. Rule selection
  did not use them, but the choice to run the audit and its design came after.
- Simulator only. Nothing here is a native or real-network result.

## Reproduce

```bash
make jevbwe-typed-baselines TYPED=results/regen   # needs the frozen V3 run under results/regen
```

Outputs: `results/typed-baseline-audit-v1/report.json` (tracked) and the per-episode rule
outcomes beside it (not tracked).
