# Native ladder pilot V1: two rule-based candidates against tuned fixed levels

**A development pilot. Not confirmatory, and not part of Native Phase N1 or B1.** This is the
first native test of a controller in this track against a tuned baseline. The design is fixed
here before any session of record. **No session of record is run until the owner gives the
go-ahead.** It fits no model, promotes nothing and changes nothing in B1.

**Status, 2026-10-11: captured with the owner's go-ahead and analysed. The result is negative:
both rules lose to a tuned fixed level.** See [Results](#results-2026-10-11).

## Why

- The [range pilot](NATIVE_RANGE_PILOT_V1.md) found that a lower cap level kept for a whole
  session beats 1.05 of the estimate on N1's endpoint.
- Its [headroom pass](NATIVE_RANGE_PILOT_HEADROOM_V1.md) put numbers on what a controller
  faces. A fixed level chosen without the scored source is +4.24 [+1.40, +7.08] over 1.05.
  Knowing the schedule would add +2.56 [+0.51, +4.61] to it. And the age of the presentation
  acknowledgements tells a link with room from a constrained one at every ratio level, where
  the estimate's own growth does not at the low levels.
- By the rule fixed in that pass, this is the case in which a simple rule-based controller is
  worth writing down and testing against the tuned fixed level. No controller has been run
  against a tuned baseline on the native stack.

## The candidates

Both act through N1's actuator: a cap that is a ratio of the browser's estimate, frozen when
a hold begins. Both choose among four ratios, the **ladder**: 0.25, 0.65, 0.85, 1.05.

**The signal.** The mean age of the presentation acknowledgements the sender saw in the last
second: the time an acknowledgement arrived minus the time its frame was captured. It is known
to the sender when it decides. It comes from the harness's own acknowledgement channel, which
the receiver sends over the impaired path; a deployed sender has it only if the application's
receiver reports it.

**The ladder.** A session starts at the top, 1.05, because in N1 and in the range pilot a low
cap in the first hold cost frames at the encoder. At the start of every later 3 s hold:

| Age of the last second's acknowledgements | Move |
|---|---|
| below 104 ms | one step up |
| 104 ms to under 132 ms | stay |
| 132 ms to under 159 ms | one step down |
| 159 ms or more, or no acknowledgement at all | to the bottom, 0.25 |

**The fast ladder.** The same, and in addition it goes to the bottom inside a hold, as soon as
the age reaches 159 ms, provided a second has passed since its last change. The reason is
structural. The encoder follows a lower cap in about 0.1 s and a higher one in 1.2 to 1.6 s
([long-hold record](NATIVE_ENCODER_LONG_HOLD_V1.md)), the browser itself cuts within a second
of a drop ([within-hold pass](NATIVE_PHASE_N1_DYNAMICS.md)), and a rule that decides every 3 s
rides out a whole hold of late frames first.

**Where the three marks come from.** From the headroom pass's median ages, by a rule stated
here: the low mark is midway between the medians with room and under constraint at 0.25 (94.5
and 113.9 ms); the high mark is midway between them at 0.85 (109.9 and 153.2 ms); the panic
mark is the median under constraint at 1.05 (159.4 ms). **They are tuned on the twelve sources
this pilot runs on.**

**What the candidates do not use.** The relay's capacity or queue, the schedule, anything
after the decision, any model. They are rules.

## Design

**Arms.** Five, through one sampler and one episode script: the ladder, the fast ladder, and
three fixed levels, 0.25, 0.65 and 1.05. The first two fixed levels are the ones the
leave-one-source-out choice of the headroom pass landed on (ten folds and two). The third is
N1's top ratio.

**Sources, schedules, content.** As in the range pilot: N1's twelve used sources, its four
schedules, and for every arm of a source and schedule the clip segment and scene seed of N1's
first peer there. Nothing is downloaded. N1's reserve sources and B1's candidates are not
touched.

**Sessions.** One or two repetitions of every cell, the owner's choice: 240 sessions and
about 3.2 hours, or 480 and about 6.4 hours. One seeded shuffle of all of them.

**Harness.** New files beside the frozen ones.

- `benchmarks/native_rtc/ladder_control.mjs`: the sampler for all five arms.
- `benchmarks/native_rtc/ladder_episode.mjs`: N1's frozen episode script with eight listed
  replacements, rebuilt and compared by a test. Seven are the range pilot's kind. The eighth
  hands the sampler the acknowledgement the page already holds.
- `src/media_rl/native_ladder_pilot.py`: plan, capture, audit, report. The audit is the
  frozen study's raw audit, with a replay of the rule poll by poll in place of N1's
  instrument: every decision, its input and its cap must follow from the recorded polls and
  acknowledgements.

**Smoke test, under the owner's standing permission.** Five sessions on used sources into a
temporary directory: three with the first version of the harness, two after the fast ladder
was added. All ran, replayed and sealed. What was read: the steps, the decisions, the ages the
rule acted on, the estimates and the caps. No timing or quality outcome was read. Two of the
first three showed the ladder staying at the top through a whole hold before moving, and that
is why the fast ladder was added before this design was fixed. The marks were not changed.

## Analysis, fixed here

**Unit.** The source. A cell's repetitions are averaged first.

**Span.** The whole session is the span of the reading: how a controller starts is its own
doing. The span from the second change on is reported beside it.

**Quantities.** The endpoint (on-time sampled RGB-PSNR contribution per capture request), the
share of requests on time, the PSNR of on-time frames, the shares never encoded and shown
late, the median age of shown frames, and the encoder rate in kbit/s and over capacity.

**Estimates.** Per arm the mean over sources, schedules weighted equally. Each candidate
minus each fixed level, and the fast ladder minus the ladder: within source and schedule,
averaged within source, with a 95% t interval over sources. Over all schedules and per
schedule. Seven contrasts on the endpoint, not corrected.

**Reading, fixed here,** on the endpoint over the whole session and all schedules:

| Statement | When |
|---|---|
| a candidate beats the tuned fixed levels | its differences from 0.25 and from 0.65 both have intervals above zero |
| a candidate loses to a tuned fixed level | either of those intervals is below zero |
| a candidate beats the top ratio | its difference from 1.05 has an interval above zero |
| cutting fast helps or hurts | the fast ladder minus the ladder has an interval above or below zero |

Also reported: the fixed levels against each other, as a second run of the range pilot's
comparison; with two repetitions, how far two sessions of the same cell lie apart; and what
each rule did, as its changes per session and the share of each move per schedule.

**What each outcome would lead to.** Proposals for the owner, not decisions.

- *A candidate beats the tuned fixed levels.* It is worth a confirmatory test on fresh
  sources, with its marks frozen as they are, against the tuned fixed level.
- *Neither beats and neither loses.* A rule then matches a tuned level without being told the
  level. That has some value and is not an improvement. Nothing is promoted and the record of
  what the rule did says where it fell short.
- *A candidate loses.* A negative result, recorded as such. The rule is changed only under a
  new design.

## Limits

- **The pilot may well be inconclusive about beating a tuned level.** In the range pilot the
  spread of a paired difference between levels gave an interval about 2.7 either side with
  one session per cell, and the most that perfect knowledge of the schedule could add was
  estimated at 2.56. It will show direction and what the rules do.
- The marks were tuned on these twelve sources, which have now been looked at many times.
- The signal is this harness's acknowledgement channel.
- The rules decide on a ratio of the estimate, and at the bottom of the ladder the estimate
  stops moving. What the bottom step means in kbit/s depends on how the session got there.
- One machine carries sender, relay and receiver. Four scripted schedules. A PSNR proxy with
  a 150 ms deadline.
- Development evidence. Nothing here can promote a controller.

## Commands

```sh
uv run --frozen python -m media_rl.native_ladder_pilot plan \
    --n1-protocol results/native-actuator-qualification-n1-plan/protocol.json \
    --repetitions 2 --out results/native-ladder-pilot-v1-plan
uv run --frozen python -m media_rl.native_ladder_pilot capture \
    --protocol results/native-ladder-pilot-v1-plan/protocol.json \
    --out results/native-ladder-pilot-v1
uv run --frozen python -m media_rl.native_ladder_pilot status --capture results/native-ladder-pilot-v1
uv run --frozen python -m media_rl.native_ladder_pilot analyse \
    --capture results/native-ladder-pilot-v1 --out results/native-ladder-pilot-v1-report
node --test benchmarks/native_rtc/ladder_control.test.mjs
```

## Results (2026-10-11)

**A negative result. Both rules lose to a tuned fixed level. Nothing is promoted.**

### Capture

- The owner approved the capture with two repetitions
  ([decisions, section 16](NATIVE_PHASE_N1_DECISIONS.md)).
- 480 of 480 planned sessions sealed, 96 per arm, on 12 sources. Captured on 2026-10-11 from
  08:13 to 14:34 EDT. Every sealed session passed the raw audit with the rule replayed poll by
  poll.
- Two first attempts failed and succeeded on the retry. One ran into the 90 s limit
  (`lp-3185a589f56ad4e454458e1d-queue-building-a4-r0`). One did not reach the browser's DevTools
  (`lp-656fe3407af041006f6f16eb-queue-building-a0-r1`). Both are kept under `failed/`.
- Capture: `results/native-ladder-pilot-v1`, 8.1 GB, local and untracked. Plan sha256
  `50d2883b12ebdee95a44c2d7b5256f4bc84b8efe8fa33a7423cdfc767ce24049`.
- Report: `results/native-ladder-pilot-v1-report/` (`report.json`, `sessions.json`,
  `timeline.json`).

### The endpoint

Whole session, all schedules, mean over sources.

| | ladder | fast ladder | 0.25 | 0.65 | 1.05 |
|---|---|---|---|---|---|
| Utility (the endpoint) | 22.79 | 23.94 | 25.34 | 26.06 | 21.87 |
| On time (%) | 67.7 | 72.2 | 83.3 | 80.8 | 63.7 |
| PSNR of on-time frames (dB) | 32.8 | 32.5 | 30.0 | 31.7 | 33.5 |
| Never encoded (%) | 7.0 | 7.3 | 11.7 | 6.7 | 4.3 |
| Shown late (%) | 19.4 | 14.9 | 0.6 | 7.4 | 25.6 |
| Median age of shown frames (ms) | 135 | 124 | 83 | 105 | 147 |
| Encoder rate (kbit/s) | 569 | 539 | 180 | 313 | 705 |
| Encoder rate over capacity (%) | 36 | 34 | 18 | 30 | 48 |
| Utility from the second change on | 21.83 | 23.20 | 26.63 | 26.80 | 20.74 |

Differences within source and schedule, with 95% intervals over sources, uncorrected.

| Difference | Utility | On time (points) | Utility from the second change on |
|---|---|---|---|
| ladder − 0.25 | −2.55 [−3.80, −1.30] | −15.5 [−20.4, −10.7] | −4.80 [−6.51, −3.08] |
| ladder − 0.65 | −3.27 [−4.84, −1.69] | −13.1 [−19.0, −7.2] | −4.97 [−6.92, −3.03] |
| ladder − 1.05 | +0.92 [−0.36, +2.20] | +4.0 [+0.2, +7.8] | +1.09 [−0.47, +2.66] |
| fast ladder − 0.25 | −1.40 [−3.12, +0.32] | −11.1 [−17.2, −4.9] | −3.43 [−5.57, −1.28] |
| fast ladder − 0.65 | −2.12 [−3.99, −0.24] | −8.6 [−15.3, −2.0] | −3.60 [−5.81, −1.39] |
| fast ladder − 1.05 | +2.07 [+0.43, +3.71] | +8.4 [+3.4, +13.5] | +2.46 [+0.50, +4.43] |
| fast ladder − ladder | +1.15 [+0.13, +2.17] | +4.5 [+1.2, +7.7] | +1.37 [+0.17, +2.58] |
| 0.25 − 1.05 | +3.47 [+1.50, +5.44] | +19.5 [+12.5, +26.5] | +5.89 [+3.49, +8.29] |
| 0.65 − 1.05 | +4.19 [+1.94, +6.43] | +17.1 [+9.6, +24.6] | +6.07 [+3.44, +8.70] |
| 0.25 − 0.65 | −0.72 [−1.95, +0.51] | +2.4 [−2.3, +7.2] | −0.17 [−1.53, +1.18] |

### Reading, by the rule fixed above

- **The ladder loses to both tuned fixed levels.** It is not separated from 1.05.
- **The fast ladder loses to 0.65.** Against 0.25 its difference is −1.40, with an interval that
  includes zero. It beats 1.05.
- **Cutting fast helps:** +1.15 [+0.13, +2.17].
- This is the third of the outcomes named in the design: a candidate loses. The rules are
  changed only under a new design.

### By schedule

Utility, whole session.

| Schedule | ladder | fast ladder | 0.25 | 0.65 | 1.05 |
|---|---|---|---|---|---|
| Underutilized | 28.16 | 28.58 | 23.97 | 28.32 | 26.86 |
| Near-capacity | 27.00 | 27.96 | 26.45 | 28.78 | 27.06 |
| Queue-building | 20.81 | 23.07 | 25.85 | 25.45 | 18.70 |
| Collapse-recovery | 15.21 | 16.16 | 25.09 | 21.69 | 14.87 |

- **With room** both rules beat 0.25 (+4.19 [+2.23, +6.14] and +4.61 [+2.04, +7.19]) and are
  level with 0.65.
- **Near capacity** nothing is separated.
- **Where capacity falls** the rules lose. In collapse-recovery the fast ladder is −8.93
  [−11.35, −6.51] against 0.25 and −5.52 [−9.23, −1.82] against 0.65. In queue-building the
  ladder loses to both; the fast ladder's differences, −2.79 [−6.18, +0.61] and −2.38
  [−6.73, +1.97], include zero.

### The fixed levels, a second time

- Against 1.05, the level 0.25 gains +3.47 [+1.50, +5.44] and the level 0.65 gains +4.19
  [+1.94, +6.43] over the whole session. From the second change on they gain +5.89 and +6.07.
  The range pilot had +5.16 [+2.25, +8.06] and +4.92 [+2.17, +7.67] from the second hold on.
- 0.25 and 0.65 are not separated over all schedules (−0.72 [−1.95, +0.51]). They split by
  schedule: 0.65 is better with room (0.25 − 0.65 is −4.35 [−6.02, −2.67]) and near capacity
  (−2.34 [−3.48, −1.19]); in collapse-recovery 0.25 is ahead by +3.40 [−0.06, +6.86].
- Same twelve sources and same machine. A second run, not a replication on fresh sources.

### How far two sessions of a cell lie apart

Mean absolute difference of the endpoint between a cell's two sessions: 0.96 at 0.25, 1.70 at
0.65, 2.78 at 1.05, 2.55 under the fast ladder and 2.89 under the ladder. A higher level is also
a less repeatable one.

### What the rules did

- **Neither rule stepped up once**, in any session of any schedule.
- With room, 79% of the ladder's later assignments and 73% of the fast ladder's were at 1.05.
  In the other three schedules 42% to 60% of the ladder's and 55% to 67% of the fast ladder's
  were at the bottom.
- A fast cut was 17% of the fast ladder's later decisions in collapse-recovery, 15% in
  queue-building, 12% with room and 7% near capacity.
- The report's field `changes_per_session` counts later assignments, not changes of level: 5
  for the ladder and 6 for the fast ladder. The fast ladder's hold clock restarts at a cut.
  Without a cut it assigns once more 0.1 to 0.3 s before the session ends, which the other
  arms do not; that is too late to matter to the endpoint.

### Added after the report was read: where in a session the rules lose

Computed by the `timeline` command of the same module, which was committed after the report
above had been read. It is a description: means over sources, per stretch of 3 s from a
session's first acknowledgement and per capacity phase. It has no intervals, and no statement
of the reading above rests on it.

Utility, all schedules.

| Arm | 0–3 s | 3–6 s | 6–9 s | 9–12 s | 12–15 s | 15–18 s |
|---|---|---|---|---|---|---|
| ladder | 27.6 | 30.6 | 20.3 | 18.9 | 19.0 | 20.5 |
| fast ladder | 27.6 | 30.6 | 20.2 | 20.3 | 23.0 | 22.3 |
| 0.25 | 19.1 | 24.3 | 26.1 | 27.2 | 27.1 | 27.8 |
| 0.65 | 22.4 | 28.3 | 24.8 | 24.8 | 27.0 | 28.5 |
| 1.05 | 27.5 | 30.6 | 19.9 | 18.8 | 18.8 | 16.5 |

Collapse-recovery: capacity 1.2 Mbit/s, 0.35 Mbit/s from 6 s, 1.2 Mbit/s from 12 s. The ratio
is the one in force at the middle of the stretch.

| Quantity | Arm | 0–3 s | 3–6 s | 6–9 s | 9–12 s | 12–15 s | 15–18 s |
|---|---|---|---|---|---|---|---|
| On time (%) | ladder | 85 | 90 | 8 | 8 | 21 | 58 |
| | fast ladder | 85 | 92 | 8 | 12 | 34 | 59 |
| | 0.25 | 58 | 85 | 83 | 85 | 88 | 93 |
| | 0.65 | 68 | 89 | 46 | 48 | 65 | 85 |
| | 1.05 | 86 | 91 | 7 | 7 | 23 | 45 |
| Median age of shown frames (ms) | ladder | 62 | 98 | 576 | 359 | 271 | 177 |
| | fast ladder | 63 | 98 | 492 | 331 | 241 | 175 |
| | 0.25 | 63 | 74 | 108 | 114 | 105 | 97 |
| | 0.65 | 63 | 87 | 225 | 185 | 146 | 122 |
| | 1.05 | 63 | 98 | 736 | 363 | 283 | 211 |
| Ratio in force | ladder | 1.05 | 1.05 | 0.97 | 0.25 | 0.25 | 0.25 |
| | fast ladder | 1.05 | 1.05 | 0.25 | 0.25 | 0.25 | 0.25 |
| Requested rate (kbit/s) | fast ladder | 315 | 876 | 150 | 150 | 150 | 150 |
| | 0.25 | 150 | 262 | 262 | 150 | 150 | 150 |
| | 1.05 | 315 | 922 | 1176 | 297 | 305 | 531 |

The receiver and the relay in the three capacity phases (6 s, 6 s, 6.6 s) of the two schedules
whose capacity falls. Queue-building is 1.2, 0.6 and 0.6 Mbit/s. The jitter buffer is per
decoded frame. The load is the bytes offered to the relay's sender-to-receiver queue over what
its capacity could carry in the phase.

| Schedule | Arm | Jitter buffer (ms) | Offered load over capacity (%) | Dropped by the relay (%) |
|---|---|---|---|---|
| Queue-building | ladder | 26, 87, 118 | 41, 68, 33 | 0.0, 0.0, 0.0 |
| | fast ladder | 26, 88, 73 | 41, 53, 33 | 0.0, 0.2, 0.0 |
| | 0.25 | 15, 24, 35 | 17, 40, 39 | 0.0, 0.0, 0.0 |
| | 0.65 | 23, 54, 68 | 28, 66, 60 | 0.0, 0.0, 0.0 |
| | 1.05 | 26, 111, 111 | 41, 82, 81 | 0.0, 0.3, 0.0 |
| Collapse-recovery | ladder | 26, 240, 172 | 40, 71, 14 | 0.0, 3.6, 0.0 |
| | fast ladder | 26, 207, 157 | 40, 65, 14 | 0.0, 2.4, 0.0 |
| | 0.25 | 16, 38, 50 | 19, 60, 14 | 0.0, 0.0, 0.0 |
| | 0.65 | 23, 102, 79 | 28, 68, 18 | 0.0, 0.4, 0.0 |
| | 1.05 | 26, 275, 191 | 41, 84, 31 | 0.0, 4.6, 0.0 |

What the description shows.

1. **The first 6 s go to the arms that start at the top.** 27.6 and 30.6, against 22.4 and 28.3
   at 0.65 and 19.1 and 24.3 at 0.25. Starting at the top was right.
2. **From 6 s on, an arm that was at the top has lost, whatever it does next.** In
   collapse-recovery the fast ladder is at the bottom by the middle of the third stretch. It
   requests 150 kbit/s against a capacity of 350 kbit/s, and its load is 14% of capacity in the
   last phase. Its share on time is 8, 12, 34 and 59%. The fixed 0.25 has 83, 85, 88 and 93%.
3. **What holds the frames is the receiver.** The fast ladder's jitter buffer holds 207 ms per
   frame in the phase of the drop and still 157 ms in the phase after it. At 0.25 it holds 38
   and 50 ms, at the same 14% load in the last phase. The relay dropped 2.4% of the fast
   ladder's bytes in the phase of the drop and none after it. The median age of its shown
   frames is 492, 331, 241 and 175 ms in the four stretches from the drop on: still over the
   deadline when the session ends.
4. **The browser does most of the cutting itself.** The estimate falls after the drop, and at
   1.05 the requested rate is 297 kbit/s in the fourth stretch. The arm at 1.05 has 7, 7, 23
   and 45% on time, a little behind the rules.
5. **Queue-building shows the same with a milder drop.** In the last phase the ladder offers
   33% of capacity and its buffer holds 118 ms. The fixed 0.25 offers 39% and holds 35 ms.
6. **With room the top arms gain and then lose it.** In the underutilized schedule the arm at
   1.05 reaches a utility of 33.1 and 34.0 in the third and fourth stretches, where 0.65 has
   29.7 and 30.0. Then the estimate reaches the link's 4 Mbit/s: the requested rate is
   3.96 Mbit/s in the fifth stretch, the relay drops 3.7% of the bytes in the last phase, and
   28% of the requests of the last stretch are on time. The rules have cut in part of their
   sessions by then, to a mean ratio of 0.56 and 0.50, and have 43% and 46%.

Arithmetic on the relay's settings, not a measurement: when 900 kbit/s meets a capacity of
350 kbit/s, the 30 kB queue is full after 0.44 s and then holds 0.69 s of delay. An
acknowledgement that shows a frame to be late is itself at least 150 ms old.

### What follows

Proposals for the owner, not decisions.

- **The negative result stands as recorded.** On this harness the tuned fixed level is
  unbeaten: 26.06 at 0.65 and 25.34 at 0.25.
- **Why the rules lost.** This is a reading of the description above, not a tested claim. The
  rules act on lateness. On this stack lateness is seen after the receiver's buffer has grown,
  and the buffer then comes down more slowly than these sessions last. A fixed low level never
  lets it grow. What a low level buys is prevention, and a rule that waits for the signal
  cannot buy it.
- **What these schedules cannot show.** Each has at most one change of capacity, 6 s into a
  session of 18.6 s. Nothing in the history before the change tells that it is coming, and too
  little session is left after it for a reaction to pay. Whether history helps a controller,
  for instance through a margin that widens once a drop has been seen, needs longer sessions
  with recurring changes. That is a new design with new schedules and a new capture.
- **A stitched rule is not a finding.** The first table invites a rule that starts at the top
  and goes to 0.65 at 6 s. The schedules change at exactly 6 s, a third of a session is start-up
  here and little of a real call is, and stretches of different sessions put end to end are
  not a session.
- **The simulator cannot show this effect.** Its receiver is a fixed delay
  ([sustained levels in the simulator](JEVBWE_TYPED_SUSTAINED_LEVELS_V1.md)). Giving it a
  buffer that rises fast and falls slowly would be new modelling, which is the owner's
  decision and has not been started.
- Nothing is promoted. All of this is development evidence on twelve sources that have been
  looked at many times.
