# What the range pilot leaves for a controller: tuned level, headroom, signals (exploratory)

**Exploratory, on the development pilot's sessions.** The [range pilot](NATIVE_RANGE_PILOT_V1.md)
found that a lower cap level kept for a whole session beats 1.05 of the estimate on N1's
endpoint. Its supplement named the best level per schedule in hindsight, chosen and scored on
the same twelve sources. This pass asks three questions a controller test would need answered,
without that optimism where it can be avoided. It captures nothing, fits no model, evaluates no
controller and promotes nothing. It is a further look at sessions that have been read once.

## Why

- A controller has to beat a tuned fixed level, not 1.05. How good is a fixed level chosen
  without the source it is scored on?
- A controller can only add to that by acting differently in different states. How much
  could knowing the state add, at best?
- A controller sees signals, not schedules. Under a level that is kept, do the sender's own
  signals tell a link with room from a constrained one? A cap far below the estimate stops the
  estimate from moving, so the answer may depend on the level.

## Fixed before any of it was computed

**Data.** The 240 sealed sessions of the pilot. Per session and hold: the endpoint (on-time
sampled PSNR contribution per capture request) over the requests captured from the hold's
acknowledgement to the next one's. The reader stops if a session's holds from the second on do
not add up to the utility the pilot's report has for it.

**Unit.** The source. Everything below is scored from the second hold on, as in the pilot.

**1. A tuned fixed level, leaving one source out.** For each source, the level with the
highest mean utility over the other eleven, schedules weighted equally, is scored on the
source left out. Reported: its mean over the twelve sources, its difference from 1.05 on the
same sources with a 95% t interval, and how often each level was chosen.

**2. Knowing the schedule, leaving one source out.** As above, with one level chosen per
schedule. The schedule is not something a sender sees, so this is a bound on what telling the
schedules apart perfectly could add to a tuned fixed level. Reported: its difference from the
tuned fixed level of part 1.

**3. Switching by hold, leaving one source out, stitched.** One level chosen per schedule and
hold position on the other eleven sources, and scored on the source left out by taking each
hold from the session that was at that level throughout. **This stitches holds from different
sessions and ignores carry-over:** a sender that switched into a level would arrive with
another estimate and another receiver buffer than a sender that had been there all along. It
is reported as an optimistic indication, not as a bound that a controller could reach.

For all three the in-sample versions, chosen and scored on all twelve sources, are reported
beside them so that the optimism of choosing in sample can be seen.

**4. What the sender can see.** For every hold from the second on, three signals known when
the hold begins:

| Signal | What |
|---|---|
| estimate growth | this hold's frozen estimate over the previous hold's (B1's flag is this below 1.05) |
| feedback age | mean age of the presentation acknowledgements received in the second before the hold begins: receipt time minus the frame's capture time |
| round-trip time | mean RTCP round-trip time polled in that second |

Per level and signal: how well the signal separates holds of the schedule with room from holds
of the three constrained schedules, as the probability that a hold with room has the more
favourable value than a constrained one (0.5 is no separation; ties count half). It is computed
within source and averaged over sources with a 95% t interval. The share of holds B1's flag
marks is reported per schedule and level.

**Reading, fixed here.**

| Statement | When |
|---|---|
| tuning the fixed level pays out of sample | the interval of part 1's difference from 1.05 is above zero |
| knowing the schedule adds to a tuned fixed level | the interval of part 2's difference from part 1 is above zero |
| switching by hold could add more, at best | the interval of part 3's difference from part 2 is above zero |
| a signal tells room from constraint at a level | the interval of its separation is above 0.5 |

What each would lead to, as proposals for the owner:

- *Tuning pays and knowing the schedule does not add.* The pilot gives no support for a
  state-dependent choice between schedules. A confirmatory test would then be of the tuned
  fixed level against 1.05, and a controller would have to justify itself by switching within
  a session, which this pilot cannot assess.
- *Knowing the schedule adds, and a signal tells the states apart at the levels involved.* A
  simple rule-based controller is then worth writing down as a candidate, to be tested against
  the tuned fixed level on fresh sources.
- *Knowing the schedule adds, and no signal tells them apart at the low levels.* A controller
  would have to probe upward to learn that there is room, and the cost of probing becomes the
  question.

## What this cannot show

- Anything confirmatory. Twelve used sources, one session per cell, levels chosen after the
  pilot was read. Leaving a source out removes the optimism of choosing and scoring on the
  same source, not the rest.
- What a controller would deliver. No session switched levels. Part 3 stitches.
- That the schedules of this harness are the states a real path would be in.

## Command

```sh
uv run --frozen python -m media_rl.native_range_pilot_headroom \
    --capture results/native-range-pilot-v1 \
    --sessions results/native-range-pilot-v1-report/sessions.json \
    --out results/native-range-pilot-v1-report/headroom.json
```

## Results

Run on 2026-10-11 from the design committed as `3dd7e08`, on all 240 sessions. Every session's
holds from the second on add up to the utility the pilot's report has for it. Report:
`results/native-range-pilot-v1-report/headroom.json`. Brackets are 95% t intervals over the
twelve sources.

### 1 to 3. A tuned fixed level and what could be added to it

| Plan | Utility, one source left out | Difference | Utility, in sample |
|---|---:|---|---:|
| 1.05, the reference | 21.44 | | 21.44 |
| a tuned fixed level | 25.68 | from 1.05: +4.24 [+1.40, +7.08] | 26.60 |
| a level per schedule | 28.24 | from the tuned fixed level: +2.56 [+0.51, +4.61] | 28.72 |
| a level per schedule and hold, stitched | 28.92 | from a level per schedule: +0.68 [-0.41, +1.77] | 29.58 |

- **Tuning the fixed level pays out of sample.** The level is 0.25 in ten folds and 0.65 in
  two. Leaving the scored source out costs about a fifth of the in-sample gain (5.16 to 4.24).
- **Knowing the schedule adds to a tuned fixed level,** by about a tenth of it. The choice is
  the same in nearly every fold: 0.85 with room and 0.25 under both schedules with a drop in
  all twelve, 0.65 under near-capacity in eleven.
- **Switching by hold is not established,** and its figure is the stitched one. In sample it
  would take 1.05 in the second hold under every schedule, 0.25 from the hold of a drop on,
  and with room 1.05 until the fourth hold and 0.85 after.

### 4. What the sender can see as a hold begins

Separation of holds with room from holds under a constrained schedule; 0.5 is none.

| Level | Estimate growth | Feedback age | Round-trip time | Holds B1's flag marks: room / constrained |
|---|---|---|---|---|
| 0.25 | 0.51 [0.48, 0.54] | 0.86 [0.79, 0.92] | 0.73 [0.66, 0.80] | 78% / 75% to 78% |
| 0.65 | 0.60 [0.57, 0.64] | 0.86 [0.80, 0.92] | 0.83 [0.76, 0.89] | 50% / 55% to 62% |
| 0.85 | 0.68 [0.64, 0.73] | 0.84 [0.76, 0.91] | 0.84 [0.79, 0.90] | 3% / 23% to 28% |
| 1.05 | 0.73 [0.71, 0.76] | 0.78 [0.72, 0.83] | 0.70 [0.61, 0.79] | 3% / 33% to 45% |
| ceiling | 0.55 [0.51, 0.58] | 0.55 [0.41, 0.69] | 0.59 [0.47, 0.71] | 65% / 37% to 57% |

Median feedback age with room and under constraint: 95 and 114 ms at 0.25, 100 and 131 ms at
0.65, 110 and 153 ms at 0.85, 120 and 159 ms at 1.05.

- **Held at a quarter of its estimate, a sender cannot learn from the estimate that there is
  room.** The estimate stands still under every schedule (median growth 1.00), so its growth
  separates nothing and B1's flag marks three quarters of all holds whatever the schedule.
- **The age of the presentation feedback tells the two apart at every ratio level,** and best
  at the low ones. The round-trip time does too, more weakly at the ends.
- **The estimate's growth tells them apart only where the cap lets the estimate move,** at
  0.85 and 1.05. That is where B1's flag works as intended: 3% of holds with room against a
  quarter to a half under constraint.
- **Under the ceiling no signal tells much.**

## Reading

- **The baseline to beat.** A fixed level chosen on other sources is worth about 20% over
  1.05 on the source left out. That, not 1.05, is the fair comparator for a controller on this
  endpoint, and the level it lands on is the low end of the range.
- **The prize for a controller.** Telling the schedules apart perfectly would add about 10%
  to the tuned fixed level. That is a bound from a label a sender does not have. A rule acting
  on a noisy signal would get part of it and pays for its mistakes.
- **Which case of the three fixed above.** The second: knowing the schedule adds, and a signal
  tells the states apart at the levels involved, the lowest included. A simple rule-based
  controller is worth writing down as a candidate and testing against the tuned fixed level.
- **A caution about the signal.** The feedback age comes from this harness's own
  presentation acknowledgements, sent by the receiver over the impaired path. A deployed
  sender has it only if the application's receiver reports it. The round-trip time is a
  standard statistic and separates less well at the lowest level.
- **What stays unknown.** Whether a sender that changes level arrives where a sender kept at
  that level is: no session here switched. Whether the separation survives on sources that did
  not suggest it. And the schedules are four scripts.

Nothing here is confirmatory, no controller was run, and nothing is promoted.
