# Native margin pilot V1: long sessions, recurring changes, and a rule that remembers a drop

**A development pilot. Not confirmatory, and not part of Native Phase N1 or B1.** The owner
approved designing it on 2026-10-11 ([decisions, section 18](NATIVE_PHASE_N1_DECISIONS.md)).
**The capture is not approved.** The design is fixed here before any session of record and
before the simulator's forecast is computed. It fits no model, promotes nothing and changes
nothing in B1.

## Why

- In the [controller pilot](NATIVE_LADDER_PILOT_V1.md) two rules that wait for lateness lost to
  a tuned fixed level. Its schedules have at most one change of capacity, 6 s into a session of
  18.6 s, so they cannot show what a controller gains from what it has seen.
- The fixed levels split by schedule. In the [range pilot](NATIVE_RANGE_PILOT_V1.md) 0.25 does
  best where capacity falls, 0.65 near capacity and 0.85 with room.
- A rule could therefore gain by standing high while a link is calm and low once the link has
  shown a drop. That needs sessions long enough for a drop to be remembered and to come again.
- The capture is also a blind test of the
  [simulator's receiver layer](JEVBWE_TYPED_RECEIVER_V1.md) on sessions it has not seen.

## Sessions and schedules

A session lasts 60 s: ten capacity phases of 6 s. N1's lasted 18.6 s. All capacities are within
N1's range.

| Schedule | Capacity in the ten phases (Mbit/s) |
|---|---|
| steady-room | 4.0 throughout |
| steady-tight | 0.85 throughout |
| recurring-drops | 1.2, 0.35, 1.2, 1.2, 0.35, 1.2, 1.2, 0.35, 1.2, 1.2 |
| one-drop | 1.2, 0.35, then 1.2 for the remaining eight |

N1's page and audit require its three phase names in every session. Here they name the first
three phases, the next four and the last three, and mean nothing more.

## Arms

Four, through one sampler and one episode script: the rule, and the fixed levels 0.25, 0.65
and 1.05. The first two fixed levels are the tuned ones of the range pilot's headroom pass.

## The rule

It acts through N1's actuator: a cap that is a ratio of the browser's estimate, frozen when a
hold of 3 s begins. It uses three ratios and the top for its start.

**The signal** is the controller pilot's: the mean age of the presentation acknowledgements
the sender saw in the last second. *Late* means that age is 159 ms or more.

| Where it stands | What it sees when a hold begins | Move |
|---|---|---|
| the start, 1.05, for one hold | anything but lateness | to 0.65, *cruise* |
| 0.65 | an age under 104 ms at two holds in a row | up to 0.85 |
| 0.65 | anything else but lateness | stay |
| 0.85 | an age of 132 ms or more | back to 0.65 |
| 0.85 | less | stay |
| above 0.25 | lateness, or no acknowledgement at all | to 0.25, and the drop is counted |
| 0.25 | lateness, or less than the memory since lateness was last seen | stay |
| 0.25 | the memory has passed | back to 0.65 |

- **It also goes to 0.25 inside a hold**, as soon as it sees lateness, once a second has
  passed since its last change. That is the controller pilot's fast cut, which helped there.
- **The memory** is 30 s after the first drop it counts, and doubles with every further one,
  up to 120 s. It runs from the last moment lateness was seen, which at the bottom can be well
  after the drop.
- It never stands at 1.05 after its first hold.

**Where the numbers come from.** The three marks are the controller pilot's, which were tuned
on these twelve sources. Two holds for a step up, 30 s of memory and its doubling are the
author's choices. There is no data to tune them on, and they are not tuned.

**What the rule does not use.** The relay's capacity or queue, the schedule, anything after
the decision, any model.

## Design

**Sources and content.** N1's twelve used sources. Every session of a source plays the same
64 s of its video, starting where N1's clip of that source starts. Two sources are too short
for that; there the 64 s end with the source, and begin 20 s and 29 s into it, before the 60 s
mark N1 kept clear. Nothing is downloaded. N1's reserve sources and B1's candidates are not
touched.

**Sessions.** One or two repetitions of every cell, the owner's choice: 192 or 384 sessions,
in one seeded shuffle.

**Harness.** New files beside the frozen ones.

- `benchmarks/native_rtc/margin_control.mjs`: the sampler for all four arms.
- `benchmarks/native_rtc/margin_episode.mjs`: N1's frozen episode script with nine listed
  replacements, rebuilt and compared by a test. Eight are the controller pilot's kind. The
  ninth lets a session have ten capacity phases instead of three.
- `src/media_rl/native_margin_pilot.py`: plan, capture, audit, report. The audit is the frozen
  study's raw audit with a replay of the rule poll by poll in place of N1's instrument.

**Smoke test, under the owner's standing permission.** Three sessions on used sources into a
temporary directory, about four minutes. The first ran for its minute and failed the frozen
audit, which wants all three phase names in a session; the naming above came from that. The
next two, one of the rule under one-drop and one fixed 0.25 with room, ran, replayed and
sealed. What was read: whether they sealed, the decisions and their times, the ages the rule
acted on, the requests, and each session's duration and size. No timing or quality outcome was
read. In its session the rule cut 1.2 s after the drop began, stood at 0.25 for its memory,
returned at 44 s and stepped up at 53 s.

**Cost, measured in the smoke test.** A session takes 74 s and 54 MB.

| Repetitions | Sessions | Capture | Disk |
|---|---|---|---|
| one | 192 | about 4 hours | about 10.4 GB |
| two | 384 | about 8 hours | about 20.7 GB |

The disk has 21 GB free, beside 12.2 GB of the two earlier pilots' captures. Two repetitions
do not fit unless space is freed first.

## Analysis, fixed here

**Unit.** The source. A cell's repetitions are averaged first.

**Span.** The whole session is the span of the reading. The span from the second change on is
reported beside it.

**Quantities.** As in the controller pilot: the endpoint (on-time sampled RGB-PSNR
contribution per capture request), the share of requests on time, the PSNR of on-time frames,
the shares never encoded and shown late, the median age of shown frames, and the encoder rate
in kbit/s and over capacity.

**Estimates.** Per arm the mean over sources, schedules weighted equally. The rule minus each
fixed level and the fixed levels against each other, within source and schedule, with 95%
intervals over sources, not corrected for the number of comparisons. The same under each
schedule.

**Reading, on the endpoint over all schedules.**

| Statement | Holds when |
|---|---|
| the rule beats the tuned fixed levels | its differences from 0.25 and from 0.65 both have intervals above zero |
| the rule loses to a tuned fixed level | one of those intervals is below zero |
| the rule beats the top ratio | its difference from 1.05 has an interval above zero |

Also reported, and part of this design: with two repetitions, how far two sessions of a cell
lie apart; what the rule did under each schedule, as the share of each move and of each ratio,
the drops it counted and when it first went to the bottom; and a timeline per stretch of 6 s
and per capacity phase, as means over sources without intervals.

**What each outcome would lead to.** Proposals for the owner, not decisions.

- *The rule beats both tuned fixed levels.* It is worth a confirmatory test on fresh sources
  with its numbers frozen as they are.
- *It beats neither and loses to neither.* It matches the better fixed level without being
  told which. Nothing is promoted, and the record under each schedule says where it gained and
  lost.
- *It loses to a tuned fixed level.* A negative result, recorded as such.

## What the author expects, written beforehand

From the two earlier pilots, and nothing more than arithmetic: the rule should come out about
level with the better fixed level under each schedule, less what its first drop costs. Over
the four schedules that would put it ahead of each tuned fixed level by half a point to a
point of the endpoint. The controller pilot's intervals for such differences were 1.2 to 1.9
either side with two repetitions. **This pilot may well not resolve a gain of that size.** It
will show the direction, what the rule does over a minute, and how the fixed levels fare when
drops recur.

## The simulator's forecast

- The simulator runs with the receiver layer exactly as fitted
  (`results/typed-native-receiver-v1/layer.json`), with no refit, on the mirrors of the four
  schedules above, and the rule runs through this pilot's own replay class.
- The forecast is written to `results/typed-margin-forecast-v1/forecast.json` and committed
  before the capture is asked for: each arm's endpoint and share on time under each schedule,
  the six differences, and what the rule does.
- After the capture it is judged by the rule of the receiver layer's design. A native
  difference is *established* when its 95% interval excludes zero. A forecast difference
  *agrees* when it has the same sign and is at least 0.5 in size, *disagrees* with the other
  sign and that size, and is *flat* otherwise. The span is the whole session, as for the
  reading.

| Verdict | Condition |
|---|---|
| The layer forecast the pilot | over all schedules every established difference agrees; and under the four schedules at least 80% of the established differences agree and no difference between the rule and a tuned fixed level disagrees |
| The layer forecast the order only | over all schedules every established difference agrees, and the condition on the schedules fails |
| The layer did not forecast the pilot | over all schedules an established difference is flat or disagrees, or none is established |

The layer's own test ended negative by one difference, and it does not model how an encoder
starts under a low cap. The forecast is given all the same, as it stands, so that this capture
tests it blind.

## Limits

- **The schedules are the author's.** How much a fixed level is worth depends on how often
  capacity falls, and the four schedules decide that here. They are declared before anything
  is run.
- The rule's memory and its two holds for a step up are untuned choices.
- The rule decides on a ratio of the estimate, and at the bottom the estimate sinks. In the
  smoke test, 0.65 of the estimate after 37 s at the bottom was 207 kbit/s.
- The marks were tuned on these twelve sources, which have been looked at many times.
- Two sources contribute video from before N1's 60 s mark.
- One machine carries sender, relay and receiver. A PSNR proxy with a deadline of 150 ms.
- Development evidence. Nothing here can promote a controller.

## Commands

```sh
uv run --frozen python -m media_rl.native_margin_pilot plan \
    --n1-protocol results/native-actuator-qualification-n1-plan/protocol.json \
    --repetitions 1 --out results/native-margin-pilot-v1-plan
uv run --frozen python -m media_rl.native_margin_pilot capture \
    --protocol results/native-margin-pilot-v1-plan/protocol.json \
    --out results/native-margin-pilot-v1
uv run --frozen python -m media_rl.native_margin_pilot status --capture results/native-margin-pilot-v1
uv run --frozen python -m media_rl.native_margin_pilot analyse \
    --capture results/native-margin-pilot-v1 --out results/native-margin-pilot-v1-report
node --test benchmarks/native_rtc/margin_control.test.mjs
```

## Results

Not captured. Waiting for the owner's go-ahead.
