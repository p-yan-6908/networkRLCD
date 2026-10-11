# The simulator on sustained cap levels, set beside the native pilot (synthetic)

**Synthetic, and a comparison, not a forecast.** The [native range pilot](NATIVE_RANGE_PILOT_V1.md)
had already been read when this was written. Its record, the paper and the README say that the
simulator orders the fixed ratios the other way round from the native stack. That statement
rested on two indirect facts: the simulator's train-selected fixed ratio is 1.05, and its
[forecast of B1](JEVBWE_TYPED_B1_FORECAST_V1.md), a per-hold contrast, says backing off lowers
the quality term. This checks the statement directly. No model is fitted, no controller acts,
and the simulator is used as built.

## Fixed before it was run

- **Levels.** The pilot's five, kept for a whole simulated session of six 3 s holds: 0.25,
  0.65, 0.85 and 1.05 of the simulated estimate frozen at the start of each hold, inside the
  simulator's rate limits of 150 kbit/s to 4 Mbit/s, and the upper limit throughout for the
  ceiling.
- **Schedules.** The forecast's mirrors of the four native capacity schedules, with its
  settings: the relay's fixed delay and queue, the same seed, 48 replicates with the path
  noise the simulator's own families draw. The five levels of a replicate and schedule run on
  the same path.
- **Outcome.** From the second hold on, as in the pilot's reading: the simulator's delivered
  on-time quality term, the share of steps that meet the deadline, and the sent rate over
  capacity. The quality term is the simulator's own and is not on the native endpoint's scale,
  so only orders and signs are compared.
- **Estimates.** Per level the mean over replicates, schedules weighted equally, and its
  difference from 1.05 on the same paths, with 95% t intervals over replicates. Also the
  noise-free values on the relay's mirror.
- **Comparison with the pilot, fixed here.** For each level other than 1.05, over all schedules
  and per schedule: the simulator *agrees* with the pilot when both differences in utility
  exclude zero on the same side, *disagrees* when they exclude it on opposite sides, and the
  comparison is *unclear* otherwise. A schedule has *the same best level* when the level with
  the highest mean utility is the same in both.

## What this cannot show

- Anything native. It is a description of the simulator.
- Whether a simulator with other settings would do better. The mirror's queue and delay were
  fixed for the forecast, before the pilot.
- The two utilities are different quantities. Only their orders and signs are set side by side.

## Command

```sh
uv run --frozen python -m media_rl.typed_bitrate_sustained_levels \
    --settings configs/jevbwe_typed_b1_forecast_v1.json \
    --pilot results/native-range-pilot-v1-report/report.json \
    --out results/typed-sustained-levels-v1/report.json
```

## Results

Run on 2026-10-11 from the design committed as `5cc48a6`, against the pilot's report. Report:
`results/typed-sustained-levels-v1/report.json`. Brackets are 95% t intervals over the 48
replicates; differences are from 1.05 on the same paths.

### 1. The simulator's levels, from the second hold on

| | 0.25 | 0.65 | 0.85 | 1.05 | ceiling |
|---|---:|---:|---:|---:|---:|
| **all schedules,** quality term | 0.523 | 0.628 | 0.944 | 0.979 | 0.648 |
| minus 1.05 | -0.456 [-0.462, -0.449] | -0.351 [-0.357, -0.345] | -0.035 [-0.042, -0.027] | | -0.331 [-0.339, -0.324] |
| on time | 100.0% | 100.0% | 99.5% | 91.0% | 24.9% |
| sent rate over capacity | 16% | 20% | 39% | 46% | 414% |
| underutilized | 0.523 | 0.628 | 0.983 | 1.454 | 2.591 |
| near-capacity | 0.523 | 0.628 | 0.983 | 1.007 | 0.000 |
| queue-building | 0.523 | 0.628 | 0.982 | 0.828 | 0.000 |
| collapse-recovery | 0.523 | 0.628 | 0.829 | 0.626 | 0.000 |

For comparison, the pilot's endpoint over all schedules is 26.60, 26.36, 23.85, 21.44 and
13.07, with 88%, 82%, 70%, 62% and 36% of requests on time at 19%, 34%, 44%, 53% and 65% of
capacity.

### 2. Against the pilot, by the rule fixed above

| | Best level, simulator | Best level, pilot | 0.25 | 0.65 | 0.85 | ceiling |
|---|---|---|---|---|---|---|
| all schedules | 1.05 | 0.25 | disagrees | disagrees | unclear | agrees |
| underutilized | ceiling | 0.85 | agrees | unclear | disagrees | disagrees |
| near-capacity | 1.05 | 0.65 | unclear | unclear | unclear | unclear |
| queue-building | 0.85 | 0.25 | disagrees | unclear | unclear | agrees |
| collapse-recovery | 0.85 | 0.25 | disagrees | unclear | unclear | agrees |

Of 20 comparisons 4 agree, 6 disagree and 10 are unclear. **No schedule has the same best
level.** Nine of the ten "unclear" come from the pilot's side, whose intervals rest on twelve
sources. The tenth is 0.65 under collapse-recovery, where the simulator sees no difference from
1.05 and the pilot a gain.

## Reading

- **Over all schedules the simulator ranks the four ratios in the reverse order of the
  pilot.** The simulator has 0.25 < 0.65 < 0.85 < 1.05 and the pilot 0.25 > 0.65 > 0.85 > 1.05,
  the first two close together. The statement in the pilot's record holds.
- **It is not the rates that differ.** Kept at a ratio, the simulated sender ends up at 16%,
  20%, 39% and 46% of capacity, the native one at 19%, 34%, 44% and 53%. What differs is what
  a rate is worth. The simulator's quality term nearly doubles from the lowest ratio to 1.05,
  where the native PSNR of on-time frames rises by 4 dB in 30. And the simulator's frames are
  all on time until the queue fills, at 1.05, where natively the share on time already falls
  from 88% to 62% over the same range, at the receiver.
- **After a drop of capacity the simulator also prefers a level below 1.05.** It puts 0.85
  first under both schedules with a drop, where 1.05 loses frames to the queue. The pilot goes
  further down, to 0.25. So the simulator has the direction of that effect and not its extent.
- **With room they are opposed.** The simulator rewards rate without limit and rates the
  ceiling best; natively the ceiling is the worst level with room and 0.85 the best.
- **The two ceilings are different things.** The simulated sender under the ceiling sends
  4 Mbit/s into any link, four to six times a constrained capacity. Natively the browser's own
  congestion control still sets the rate under the ceiling, at 65% of capacity. They agree
  that the ceiling is bad under constraint, for different reasons.
- **What follows for the synthetic track.** Its learned controllers were trained and judged on
  a utility that prefers the top ratio. On this evidence that preference does not carry to the
  native endpoint, so neither do their gains, whatever their size in the simulator. Making the
  simulator's valuation native-like (a receiver buffer that grows with the rate, a flatter
  quality term) would be new modelling and is the owner's decision.

This describes the simulator. It is not native evidence, and it was made after the pilot was
read.
