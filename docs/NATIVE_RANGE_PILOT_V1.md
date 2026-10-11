# Native range pilot V1: whole sessions from a quarter of the estimate to the ceiling

**A development pilot. Not confirmatory, and not part of Native Phase N1 or B1.** The owner
approved it on 2026-10-10 ([decisions record](NATIVE_PHASE_N1_DECISIONS.md), section 15), after
an earlier approval had been voided because it rested on a false statement of the agent's
(section 14). This design is fixed before any session of record. It promotes nothing, fits no
model, evaluates no controller and changes nothing in B1, which stays registered and frozen.

## Why

- B1's registered contrast is between ratios 0.65, 0.85 and 1.05 of the estimate, drawn afresh
  for every 3 s hold. The exploratory passes over N1 found that on-time delivery there is set
  by the capacity schedule, at the receiver, and that these three ratios move it by a point or
  two ([delivery pass](NATIVE_PHASE_N1_DELIVERY.md)).
- N1 never sustains a level. A low request is followed by a high one, so neither the browser's
  estimate nor the receiver's buffer settles to what a level would give if it were kept.
- Earlier development diagnostics found the browser under a 4 Mbit/s ceiling the worst
  condition and fixed caps far below capacity the best, in small panels on other sources and
  earlier versions of the harness (see the correction in
  [NATIVE_PHASE_N1_DYNAMICS.md](NATIVE_PHASE_N1_DYNAMICS.md)).

The question: over the whole range the actuator offers, with a level kept for a whole session,
does any level move on-time delivery and the endpoint on N1's harness and sources? B1 cannot
answer that, whatever its outcome.

## Design

**Sources.** The twelve sources of N1's stage one, which N1 has already used. N1's nine
reserve sources stay reserved to N1, and B1's candidates are not touched. Nothing is
downloaded.

**Schedules.** N1's four: underutilized, near-capacity, queue-building, collapse-recovery.

**Levels.** Five, one per session and the same for all six holds of a session.

| Level | Cap requested at the start of each 3 s hold |
|---|---|
| 0.25 | a quarter of the browser's estimate, frozen as the hold begins |
| 0.65 | N1's lowest ratio |
| 0.85 | N1's middle ratio |
| 1.05 | N1's top ratio; the reference level |
| ceiling | 4 Mbit/s, the top of the cap domain: the browser under the ceiling |

A ratio is applied as in N1: to the estimate frozen when the hold begins, rounded, and kept
inside the cap domain of 150 kbit/s to 4 Mbit/s. As in N1 a session starts under a cap of
300 kbit/s until the browser has an estimate. N1's three ratios are kept so that a sustained
level can be set beside N1's interleaved one.

**Sessions.** One per source, schedule and level: 240. The five sessions of a source and
schedule use the clip segment and scene seed of N1's first peer there, so the levels of a cell
see the same content. All 240 are run in one seeded shuffle, so that no level is tied to a
time of day or to what ran before it.

**Harness.** Two new files beside the frozen ones, and no change to any frozen file.

- `benchmarks/native_rtc/range_control.mjs`: the pilot's sampler, one level per session.
- `benchmarks/native_rtc/range_episode.mjs`: N1's frozen episode script with seven
  replacements and nothing else. They are listed in
  `media_rl.native_range_pilot.EPISODE_CHANGES`, and a test rebuilds the file from the frozen
  one and requires it to be identical. Relay, source, encoder settings, deadline, frame
  marking and labels are N1's.
- `src/media_rl/native_range_pilot.py`: plan, capture, audit and report. The audit of a
  session is the frozen study's raw audit (wire, frames, labels, every applied cap), with the
  pilot's rule for which cap was due in place of N1's instrument. The runtime keeps N1's
  legacy role label because a frozen loader accepts no other, as N1 itself found.

**Smoke test, under the owner's standing permission for short ones.** Before this was
committed, ten sessions were run on N1's used sources into a temporary directory. The first
four failed within seconds on the role label and showed the fix above. The next six sealed
and passed the audit, one at least at 0.25, 0.85, 1.05 and the ceiling. Only the audit result,
the number of holds, the requested caps, the frozen estimates and the encoded rate were read:
no timing or quality outcome. The levels above had been fixed before; 0.45 had been dropped
in favour of 0.85 on the expectation that 0.25 and 0.45 would both sit at the 150 kbit/s
floor. The smoke test showed 0.25 clear of the floor after the first hold (about 206 kbit/s
under near-capacity), and the levels were left as they were. The smoke sessions are not part
of the capture.

**Capture.** From a sealed plan, on an otherwise idle machine, about 49 s per session. A
sealed session is never repeated. A session that fails is kept whole with its error and run
once more after all the others; a second failure leaves its cell empty. Nothing is analysed
during the capture.

## Analysis, fixed here

**Unit.** The source. A session's outcomes are taken over two spans: the whole session, and
from the acknowledgement of the second hold to the end. **The second span is the one the
reading uses,** because the first hold is start-up under a 300 kbit/s cap and behaved as a
regime of its own in N1.

**Quantities per session and span.**

| Name | What |
|---|---|
| utility | the endpoint: on-time sampled RGB-PSNR contribution per capture request (late and missing frames count zero) |
| on time | share of capture requests read back within 150 ms |
| PSNR on time | mean PSNR of the frames that were on time |
| never encoded, encoded and not shown, shown late | the other three fates of a request, by counts as in the delivery pass |
| median age, relay, rest | of the shown frames, as in the delivery pass |
| relay dropped share | of wire bytes |
| encoder rate | encoded payload in kbit/s, and over the mean relay capacity of the span |
| jitter buffer | the receiver's jitter-buffer delay per frame in the second and third capacity phases, and in the first |

The reader stops if a session's labels do not reproduce its audited utility and on-time
fraction.

**Estimates.** Per level, the mean over sources, a source's schedules weighted equally, with
a two-sided 95% t interval over sources. Each level minus the reference level 1.05: the
difference within source and schedule where both sessions exist, averaged within source, with
the same interval. Over all schedules and per schedule. Four comparisons per quantity, not
corrected.

**Reading, fixed here,** from the second hold on, over all schedules, against 1.05:

| Statement | When |
|---|---|
| a level moves on-time delivery | the interval of its on-time difference excludes zero |
| a level pays on the endpoint | the interval of its utility difference is above zero |
| a level costs on the endpoint | that interval is below zero |
| a lower level empties the receiver's buffer | for 0.25, 0.65 or 0.85, the interval of the jitter-buffer difference is below zero |
| the ceiling is the worst | its mean utility is the lowest of the five and its interval against 1.05 is below zero |

The same statements are reported per schedule, as description.

**What each would lead to.** These are proposals the agent would put to the owner, not
decisions.

- *A level below 1.05 pays, overall or under a constrained schedule.* B1's range may be too
  narrow to find what a cap can do. A confirmatory design over a wider range, on fresh
  sources, would be worth proposing.
- *The lower levels cost.* On this endpoint more rate is better up to the estimate, and what
  is left for a controller is the top end.
- *Only the ceiling differs.* Any cap in the range does about as well. The controller's job
  on this endpoint is then to stay capped, and a learned choice among ratios has little to
  gain here.
- *Nothing differs.* With one session per cell the pilot may be too small. The widths of its
  intervals are then its result, as sizing for anything larger.

## Limits

- One session per source, schedule and level. In an earlier diagnostic two repetitions under
  the ceiling differed by 58 points of on-time delivery.
- The twelve sources have been looked at four times, and what was seen in them led to this
  design. Whatever the pilot finds is development evidence on used sources.
- A level kept for a whole session is not a controller, and the ceiling is the top of this
  harness's cap domain, not a browser with no cap at all.
- The endpoint is a PSNR proxy on sampled pixels with a 150 ms deadline, not perceptual
  quality. One browser build, one relay, four scripted schedules, one machine.
- Four comparisons per quantity and many quantities, none corrected.

## Commands

```sh
uv run --frozen python -m media_rl.native_range_pilot plan \
    --n1-protocol results/native-actuator-qualification-n1-plan/protocol.json \
    --out results/native-range-pilot-v1-plan
uv run --frozen python -m media_rl.native_range_pilot capture \
    --protocol results/native-range-pilot-v1-plan/protocol.json \
    --out results/native-range-pilot-v1
uv run --frozen python -m media_rl.native_range_pilot status --capture results/native-range-pilot-v1
uv run --frozen python -m media_rl.native_range_pilot analyse \
    --capture results/native-range-pilot-v1 --out results/native-range-pilot-v1-report
node --test benchmarks/native_rtc/range_control.test.mjs
# Added after the report was read (section 4 of the results):
uv run --frozen python -m media_rl.native_range_pilot supplement \
    --sessions results/native-range-pilot-v1-report/sessions.json \
    --out results/native-range-pilot-v1-report/supplement.json
```

## Results

Captured from 2026-10-10 21:35 to 2026-10-11 00:47 from the design committed as `bf73026` and
the plan sealed with sha256 `bd332aac278564764ae7e20ca830a7c02fb52adc2c00444a51bdd2b394f2e034`.
**All 240 sessions sealed and passed the audit; none failed.** The capture is 4.1 GB.

The first run of the analysis stopped at the reader's own check before any outcome was
computed. One session has a request captured exactly 150 ms before the cutoff. The audit
labels it, and the reader's half-open span left it out. The span now ends a microsecond later
(commit `d9b1b1f`), and the analysis was then run once. The report, the per-session outcomes
and the supplement of section 4 are in `results/native-range-pilot-v1-report/`.

Brackets are 95% t intervals over the twelve sources. Differences are from the level 1.05,
within source and schedule.

### 1. From the second hold on, all schedules: the span of the reading

| | 0.25 | 0.65 | 0.85 | 1.05 | ceiling |
|---|---:|---:|---:|---:|---:|
| **utility** | 26.60 | 26.36 | 23.85 | 21.44 | 13.07 |
| minus 1.05 | +5.16 [+2.25, +8.06] | +4.92 [+2.17, +7.67] | +2.41 [-0.38, +5.19] | | -8.37 [-11.15, -5.60] |
| **on time** | 88.5% | 82.2% | 70.4% | 61.8% | 36.3% |
| minus 1.05, points | +26.6 [+16.8, +36.5] | +20.4 [+10.7, +30.1] | +8.5 [+0.0, +17.1] | | -25.6 [-32.9, -18.3] |
| PSNR of on-time frames, dB | 29.8 | 31.7 | 33.0 | 34.0 | 36.0 |
| shown late | 1.1% | 10.6% | 21.8% | 28.4% | 48.9% |
| never encoded | 6.5% | 2.7% | 2.8% | 3.9% | 8.1% |
| encoded, not shown | 3.9% | 4.5% | 5.0% | 5.8% | 6.8% |
| median age of shown frames, ms | 83 | 107 | 141 | 156 | 204 |
| encoder rate, kbit/s | 182 | 335 | 468 | 784 | 1,072 |
| encoder rate over capacity | 19% | 34% | 44% | 53% | 65% |
| **receiver jitter buffer, ms** | 30 | 53 | 85 | 110 | 190 |
| minus 1.05 | -80 [-106, -54] | -56 [-86, -27] | -25 [-48, -3] | | +80 [+42, +118] |
| relay dropped share | 0.00% | 0.01% | 0.14% | 0.85% | 1.88% |

By the rule fixed in advance:

- **Every level moves on-time delivery.** At 0.85 the lower end of the interval is just above
  zero.
- **0.25 and 0.65 pay on the endpoint.** 0.85 does not by the rule. **The ceiling costs.**
- **All three lower levels empty the receiver's buffer.**
- **The ceiling is the worst.**

Two facts about the levels as realised. The level 0.25 asked for the 150 kbit/s floor in 193
of its 288 holds, so it is mostly a fixed cap of 150 kbit/s. And 1.05 asked for the 4 Mbit/s
ceiling in 18 of its 288 holds.

### 2. By schedule, from the second hold on

Utility, with the differences from 1.05 whose interval excludes zero:

| Schedule | 0.25 | 0.65 | 0.85 | 1.05 | ceiling | Differences established |
|---|---:|---:|---:|---:|---:|---|
| underutilized | 25.31 | 29.68 | 31.69 | 28.14 | 8.60 | 0.25: -2.83 [-5.24, -0.42]; 0.85: +3.55 [+1.41, +5.70]; ceiling: -19.54 [-26.37, -12.72] |
| near-capacity | 27.01 | 29.11 | 26.50 | 26.26 | 27.23 | none (0.65: +2.85 [-0.75, +6.44]) |
| queue-building | 28.03 | 22.79 | 20.26 | 19.16 | 9.29 | 0.25: +8.87 [+3.63, +14.11]; ceiling: -9.87 [-16.33, -3.41] |
| collapse-recovery | 26.05 | 23.87 | 16.95 | 12.20 | 7.15 | 0.25: +13.84 [+9.46, +18.22]; 0.65: +11.66 [+5.31, +18.02]; ceiling: -5.06 [-10.09, -0.02] |

On time:

| Schedule | 0.25 | 0.65 | 0.85 | 1.05 | ceiling |
|---|---:|---:|---:|---:|---:|
| underutilized | 85.4% | 93.5% | 95.0% | 79.0% | 20.7% |
| near-capacity | 89.8% | 90.0% | 78.9% | 78.7% | 78.8% |
| queue-building | 91.9% | 69.3% | 58.8% | 55.2% | 25.4% |
| collapse-recovery | 86.8% | 76.1% | 48.8% | 34.4% | 20.2% |

- **After a drop of capacity the lowest level does best by far:** 87% of requests on time
  against 34% at 1.05 under collapse-recovery, and 92% against 55% under queue-building.
- **With room the best level is 0.85, and the ends both lose.** The quarter is too little:
  10.8% of its requests are never encoded and its PSNR is 5.9 dB lower. A sustained 1.05
  doubles the estimate hold after hold, runs at 1.8 Mbit/s, 45% of capacity, and shows 14% of
  its frames late. The ceiling runs at 2.8 Mbit/s, 69% of capacity, with 21% on time. In N1,
  where the ratio changed every hold, all three ratios were on time about 93% with room.
- **Under near-capacity nothing is established.** There the ceiling and 1.05 coincide (79% on
  time both): the browser's own estimate limits the rate under either.

### 3. The whole session, start-up included

| | 0.25 | 0.65 | 0.85 | 1.05 | ceiling |
|---|---:|---:|---:|---:|---:|
| utility | 25.34 | 25.73 | 24.15 | 22.49 | 16.03 |
| minus 1.05 | +2.86 [+0.36, +5.35] | +3.25 [+0.96, +5.53] | +1.67 [-0.71, +4.05] | | -6.45 [-9.19, -3.72] |
| on time | 83.4% | 80.1% | 71.9% | 65.8% | 44.7% |
| never encoded | 11.5% | 6.2% | 4.5% | 4.2% | 7.2% |

The same order, with smaller differences: in the first hold a low cap costs frames at the
encoder, as in N1.

### 4. Added after the report was read

Not in the design. Computed by the `supplement` command from the saved session outcomes and
recorded in `supplement.json`. From the second hold on.

- **How many sources agree.** Utility is above the 1.05 level's in 10 of 12 sources at 0.25,
  10 of 12 at 0.65 and 8 of 12 at 0.85, and in none of 12 under the ceiling.
- **The best level per schedule.** 0.85 with room, 0.65 under near-capacity, 0.25 under the
  two schedules with a drop. A sender that had each schedule's best level would reach 28.72.
  The best single level reaches 26.60 (0.25) or 26.36 (0.65), and 1.05 reaches 21.44. So a
  lower level kept for every schedule is worth 23% to 24% over 1.05, and knowing the schedule
  in hindsight adds another 8%.
- **Where the time of the shown frames goes,** in ms:

| | 0.25 | 0.65 | 0.85 | 1.05 | ceiling |
|---|---:|---:|---:|---:|---:|
| encode | 1.6 | 1.8 | 2.0 | 2.3 | 2.7 |
| pacer | 1.1 | 1.4 | 3.3 | 6.6 | 19.4 |
| relay, with 25 ms of propagation | 33 | 42 | 49 | 57 | 77 |
| rest | 48 | 65 | 88 | 98 | 138 |
| one frame's wire time | 9.7 | 15.8 | 20.3 | 24.8 | 31.3 |

  The encoder's own time hardly changes. Every stage after it grows with the rate, and the
  receiver's side most of all.

## Reading

- **What moves delivery here is the rate relative to capacity.** From 19% to 65% of capacity,
  the share on time falls from 88% to 36% and the receiver's buffer grows from 30 to 190 ms,
  in order over the five levels. The frames that do arrive on time are better at a higher
  level, by 6 dB from end to end, but a frame that misses the deadline counts nothing. On this
  endpoint the trade goes to the low end, until the cap is so low that frames are skipped.
- **Why N1 saw so little of this.** N1 draws the ratio afresh every hold. After a hold at the
  top ratio the estimate is high, and the next 0.65 is 0.65 of a high estimate. A level that
  is kept also sets the estimate it is a ratio of: kept at 0.65 the sender runs at 335 kbit/s,
  34% of capacity, and kept at 1.05 at 784 kbit/s, 53%. A contrast between ratios within a
  hold leaves out the part of a cap's effect that passes through the estimate. B1's registered
  contrast is of that kind.
- **For B1.** Nothing changes in it. But this pilot bears on how its outcome can be read: if
  B1 finds no benefit of backing off within a hold, that would not show that a lower cap does
  not help. What the pilot points to is a sustained level, and testing that needs sessions
  randomised whole, on fresh sources. That is a proposal for the owner, not a decision.
- **For baselines.** On this endpoint the strong fixed baseline is neither the top ratio nor
  the browser left under its ceiling. It is a lower fixed ratio, between a quarter and two
  thirds of the estimate, as the fixed caps of the earlier diagnostics suggested. A controller
  has to beat that, and the hindsight figure above puts what a schedule-aware choice could add
  at about 8%.
- **For the simulator.** The simulator orders the fixed ratios the other way round: its
  train-selected fixed ratio is 1.05, and its forecast for B1 is that backing off lowers the
  quality term by about 12%. The forecast is of B1's per-hold contrast and B1 has not run, so
  the two are not the same quantity. But the simulator's "more rate is better up to the
  estimate" does not hold natively for a sustained level, and the place that makes the
  difference, a receiver buffer that grows with the rate, is not in the simulator. Which ratio
  is best is not something the synthetic studies can be trusted on.
- **What this does not show.** One session per cell, on sources that were already used and
  that led to this design. One machine carries sender, relay and receiver: the encoder's time
  per frame does not grow with the level, but the pilot cannot separate the receiver's cost of
  a high rate from this machine's load. The endpoint has a 150 ms deadline and counts late
  frames as nothing, which rewards low delay more than a viewer might. "0.25" is mostly the
  floor of the cap domain. None of this is confirmatory and nothing is promoted.
