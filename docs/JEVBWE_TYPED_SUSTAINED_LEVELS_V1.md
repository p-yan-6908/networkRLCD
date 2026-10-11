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

Not yet run when this was committed.
