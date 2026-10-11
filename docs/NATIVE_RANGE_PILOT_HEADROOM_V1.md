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

Not yet computed when this was committed.
