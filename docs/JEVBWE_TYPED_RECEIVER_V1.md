# A receiver for the simulator, fitted on the range pilot and tested on the controller pilot (V1)

**Synthetic modelling. Nothing here is native evidence, and nothing is promoted.** The owner
approved this step on 2026-10-11 ([decisions, section 17](NATIVE_PHASE_N1_DECISIONS.md)). This
design is fixed before anything is fitted and before any rule is run in the simulator.

## Why

- The simulator ranks the fixed ratios in the reverse order of the native range pilot
  ([sustained levels](JEVBWE_TYPED_SUSTAINED_LEVELS_V1.md)). Its receiver is a fixed delay.
- On the native stack the receiver's jitter buffer grows with the rate over capacity, jumps
  when capacity falls, and comes down slowly
  ([delivery pass](NATIVE_PHASE_N1_DELIVERY.md), [range pilot](NATIVE_RANGE_PILOT_V1.md),
  [controller pilot](NATIVE_LADDER_PILOT_V1.md)).
- As long as the simulator disagrees with the native endpoint about fixed levels, nothing
  learned in it carries over. This step asks whether a small, explicit receiver layer closes
  that gap, and tests it on sessions it was not fitted on.

## What is known beforehand, stated plainly

The results of both pilots are known to the author of this design. The idea of a buffer that
rises fast and falls slowly comes from the controller pilot's own timeline. So the structure
below is not blind to the test data. What protects the test is narrower: every number in the
layer is fitted on the range pilot only, by the procedure below, and the endpoint and the share
on time are never fitting targets. The test is run once.

## The layer

New code beside the simulator. `environment.py`, `typed_bitrate.py` and every earlier study
stay as they are. The simulator runs as built, on the exact mirror of a native schedule (25 ms
each way, a 30 kB queue, no path noise), in steps of 100 ms for 18.6 s.

Per step the simulator gives the encoder's rate, the capacity, the queue's delay and the share
of bytes dropped. The layer adds the following.

**Start-up.** In the first hold the request is the ratio of 300 kbit/s, as natively. During
that hold the simulated estimate is led from 300 kbit/s to `E0`, because the browser's
start-up probing is not in the simulator's estimator. From the second hold on the estimator
runs free.

**The cap is a cap.** The encoder's target in a step is the smaller of the requested cap and
the simulator's estimate at that step. Natively the browser's encoder does not exceed its own
estimate and follows it down inside a hold ([within-hold pass](NATIVE_PHASE_N1_DYNAMICS.md));
the sustained-levels check held the simulated sender at the hold's request whatever the
estimate did. *Added on 2026-10-11 before any code of this design was run and before anything
was fitted. It is not the one revision allowed below.*

**The receiver's buffer**, in ms, with four numbers `b0`, `gu`, `gq`, `tau`:

- its target is `b0 + gu * min(1, rate / capacity) + gq * queue delay`;
- it rises to a higher target at once;
- towards a lower target it falls exponentially with time constant `tau`.

**The age of a shown frame** is the simulator's one-way delay plus the buffer plus
`c0 + cu * min(1, rate / capacity)`.

**Frames shown.** A frame is shown unless the queue dropped it or the encoder never made it.
The share never made is read off a table of the range pilot's levels, by encoder rate.

**Frames on time.** Ages within a step are spread normally around the step's age, with standard
deviation `s0 + s1 * age`. A shown frame is on time when its age is at most 150 ms.

**The endpoint** of a step is the share on time times the PSNR of an on-time frame. That PSNR
is read off a second table of the range pilot's levels, by encoder rate.

**The acknowledgement** of a shown frame reaches the sender its age plus `r` after capture. The
rules run as `PolicyReplay`, the class that audited the native sessions, fed one poll per step.

## Fitting, on the range pilot only

Each number is fitted to the observable it stands for. Cells are means over sources of a level
and schedule. Nothing is fitted to the endpoint or to the share on time.

| Stage | Numbers | Fitted to | How |
|---|---|---|---|
| 1 | `E0` | the estimate at the start of the second hold | mean over the 20 cells |
| 2 | two tables | PSNR of on-time frames and share never encoded, by encoder rate, from the second hold on | the five level means, interpolated linearly in log rate, held constant outside |
| 3 | `b0`, `gu`, `gq`, `tau` | the jitter buffer per capacity phase (60 cells) | least squares from the start `15, 60, 0.3, 10 s`, within `[0, 60]`, `[0, 300]`, `[0, 3]`, `[0.5, 120] s` |
| 4 | `c0`, `cu` | the median age of shown frames per stretch of 3 s (120 cells), less the simulated delay and buffer | ordinary least squares |
| 5 | `s0`, `s1` | half the distance between the 16th and 84th percentile of the ages of shown frames in a stretch, against their median | ordinary least squares over sessions and stretches, the spread not below 5 ms |
| 6 | `r` | the age of an acknowledgement at the sender less the age of its frame | median over polls |

The fitted layer is written to a file and committed before the test.

**If the fit is poor.** The layer's structure may be revised once, on the range pilot's
residuals alone, with the reason recorded here before the test is run. After the test is run
nothing is revised under this design.

## Checks on the range pilot (in sample)

Reported, and no part of the verdict on the controller pilot:

- the fit's own residuals per stage;
- the share on time and the endpoint per level and schedule against the pilot, which the layer
  was not fitted to;
- the comparison the [sustained-levels check](JEVBWE_TYPED_SUSTAINED_LEVELS_V1.md) made, on the
  same 20 level-against-1.05 comparisons, where the simulator as built had 4 agreements,
  6 disagreements and 10 unclear. A simulated difference counts as a difference from 0.5 of
  the endpoint on.

## The test on the controller pilot (out of sample)

The five arms of the controller pilot run in the simulator with the fitted layer: the ladder
and the fast ladder through `PolicyReplay`, and the fixed levels 0.25, 0.65 and 1.05.

**Span.** From the second change on, which both pilots report. The whole session is reported
beside it; the layer does not model the frames an encoder skips while it starts under a low
cap, so the whole session is not the span of the verdict.

**What counts.** The pilot has ten differences between arms. A native difference is
*established* when its 95% interval excludes zero. A simulated difference *agrees* when it has
the same sign and is at least 0.5 of the endpoint in size, *disagrees* when it has the other
sign and that size, and is *flat* otherwise.

**The verdict, fixed here.**

| Verdict | Condition |
|---|---|
| The layer predicts the controller pilot | over all schedules every established difference agrees; and under the four schedules at least 80% of the established differences agree and no difference between a rule and a tuned fixed level disagrees |
| The layer predicts the order only | over all schedules every established difference agrees, and the condition on the schedules fails |
| The layer does not predict the controller pilot | over all schedules an established difference is flat or disagrees |

**Also reported, not part of the verdict.**

- Each arm's simulated endpoint and share on time beside the native ones, and how many of the
  five simulated endpoints lie inside the native 95% interval.
- What the rules do in the simulator: the share of upward moves, which was zero natively, and
  the share of assignments at each ratio.
- **Two ablations**, to see what the buffer itself adds: the layer with the buffer held at
  `b0`, and the simulator as built with its own utility.
- **Robustness**: 48 replicates with the path noise of the simulator's own families, and for
  each established difference the share of replicates in which it agrees.

## What each verdict would lead to

Proposals for the owner, not decisions.

- *Predicts the pilot.* The simulator with the layer is then a place to look for a rule worth a
  capture, for example one with a margin that widens after a drop, on longer sessions with
  recurring changes. Any rule found there is a hypothesis for a native pilot and nothing more.
- *Predicts the order only.* It may serve to rank candidates over all schedules, and what it
  gets wrong by schedule is recorded as a limit.
- *Does not predict.* A negative result, recorded as such. The synthetic track stays set aside
  for native claims.

## Limits

- Both pilots ran on the same twelve sources, one machine and four scripted schedules. A layer
  that passes has been tested on other sessions and other policies, not on other content or
  networks.
- The layer is fitted to cell means. It has no content, and no variation between sources.
- The two tables stand in for an encoder and a quality measure the simulator does not have.
- Whatever the verdict, synthetic results stay synthetic.

## Commands

```sh
uv run --frozen python -m media_rl.typed_bitrate_native_receiver targets \
    --capture results/native-range-pilot-v1 --out results/typed-native-receiver-v1/targets.json
uv run --frozen python -m media_rl.typed_bitrate_native_receiver fit \
    --targets results/typed-native-receiver-v1/targets.json \
    --pilot results/native-range-pilot-v1-report/report.json \
    --out results/typed-native-receiver-v1/layer.json
uv run --frozen python -m media_rl.typed_bitrate_native_receiver test \
    --layer results/typed-native-receiver-v1/layer.json \
    --pilot results/native-ladder-pilot-v1-report/report.json \
    --out results/typed-native-receiver-v1/report.json
```

## Results

Not fitted and not run.
