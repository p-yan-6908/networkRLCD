# Native ladder pilot V1: two rule-based candidates against tuned fixed levels

**A development pilot. Not confirmatory, and not part of Native Phase N1 or B1.** This is the
first native test of a controller in this track against a tuned baseline. The design is fixed
here before any session of record. **No session of record is run until the owner gives the
go-ahead.** It fits no model, promotes nothing and changes nothing in B1.

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

## Results

Not captured. Waiting for the owner's go-ahead.
