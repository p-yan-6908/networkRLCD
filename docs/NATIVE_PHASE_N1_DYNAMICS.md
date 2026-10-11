# Native Phase N1: what happens inside a hold (exploratory, mechanism only)

**Not part of the N1 registration and not confirmatory.** This is a third exploratory pass
over the one N1 sample. It reads the raw per-peer logs of the stage-one capture and describes
mechanism: the encoder, the browser's estimate and the relay's queue. **It reads no quality
or on-time label**, fits no model, evaluates no controller and changes nothing in
[Native Phase B1](NATIVE_PHASE_B1_BACKOFF_BENEFIT.md), which is frozen.

## Correction (2026-10-10, after the results were recorded)

Two statements in the first version of this record were wrong. The agent found both the same
day, while reading the frozen harness and the repository's earlier native records for a
follow-up. No number in the tables below changes. What changes is what they can be taken to
mean. The wrong sentences are struck through where they stood, and the passages that leaned
on them are reworded and marked.

**1. "A cap can raise delivered quality in only one way", by less queue and loss at the
relay.** The endpoint counts a frame when its pixels are read back within 150 ms of the
capture request. That time passes through the encoder, the relay and the receiver, which
holds frames before it shows them. The earlier records put the cost of a high rate at the
receiver:

- [Repair V5](NATIVE_REPAIR_V5.md), on the Repair V4 peers and a steady 1.48 Mbit/s link: the
  browser under a 4 Mbit/s ceiling had no relay drops and sent about 1 Mbit/s, yet built up
  108 to 121 ms of receiver buffering, against about 38 ms under a fixed cap of 300 kbit/s.
- [Dense probe](NATIVE_DENSE_PROBE.md): "higher adaptive rates can accumulate native playout
  delay and late frames even when they satisfy current BWE".

This pass reads the sender and the relay. It reads nothing at the receiver and no frame's
time to display. So it describes one path of at least two, and the rule fixed below ("a
mechanism for backing off is present") is a rule about the relay path only.

**2. "The browser without an application cap has never been measured in this harness."** It
has, in development diagnostics, as the browser under a ceiling of 4 Mbit/s. On the
constrained links of those studies that ceiling is no effective cap. Share of frames on time,
and the on-time PSNR utility where the record gives it:

| Record | Conditions | Under the 4 Mbit/s ceiling | Capped senders of the same study |
|---|---|---|---|
| [Development V1](NATIVE_DEVELOPMENT_V1.md) | six source and schedule configurations, 18 executions | 45.66%, 14.891 | cap at 85% of the estimate: 69.45%, 18.921 |
| [Repair V4](NATIVE_REPAIR_V4.md) | one clip, steady 1.48 Mbit/s, two repetitions | 9.61% | 85% of the estimate: 80.87%; fixed 300 kbit/s: 81.16% |
| [Repair V5](NATIVE_REPAIR_V5.md) | one clip, steady 2.31 Mbit/s, two repetitions | 21.98%, 8.182 | fixed 600 kbit/s: 91.50%, 29.366; 85% of the estimate: 85.67%, 25.616; fixed 300 kbit/s: 88.17%, 26.353 |
| [Dense probe](NATIVE_DENSE_PROBE.md) | one group, two repetitions | 51.02% (the two repetitions: 79.85% and 22.18%) | fixed 450 kbit/s: 75.35%; 85% of the estimate: 56.01% and 58.87% |

These were development diagnostics and not confirmatory: mostly one clip and one link, two
repetitions, no intervals, earlier versions of the harness, and the dense probe's two
repetitions under the ceiling lie 58 points apart. They do not give a size. They agree on a
direction. The browser under the ceiling was the worst condition of every one of them, and in
the two that ran a fixed cap of 450 or 600 kbit/s that cap was the best.

**What that changes.**

- On this endpoint the baseline a cap controller has to beat is not the uncapped browser. It
  is a tuned cap: 85% of the estimate, and a fixed cap chosen for the link.
- N1's own rows fit this. Between its three ratios the on-time fraction barely moves: 1.05
  minus 0.65 is +0.025 [-0.006, +0.055] overall and +0.054 [+0.010, +0.098] with room
  ([exploratory record](NATIVE_PHASE_N1_EXPLORATORY.md)). Section 6 below shows that with
  room the top ratio holds the encoder at about half of the browser's live estimate, and the
  lower ratios hold the estimate itself down. N1 and B1 compare caps with each other. Neither
  reaches the rates at which the earlier studies saw delivery fail.
  *Refined later the same day by the [delivery pass](NATIVE_PHASE_N1_DELIVERY.md):* those two
  figures pool the first hold, where a low cap costs frames at the encoder (+21.0 points for
  the top ratio). From the second hold on the contrast is -2.2 points [-5.0, +0.5].
- Where between N1's top ratio and the ceiling the on-time fraction falls, and by which path,
  is not known from any of this.

## Why

- ~~A cap below the estimate can raise delivered quality in only one way: by leaving less in
  the queue and losing fewer packets than the browser would on its own.~~ *Wrong; see the
  correction above. That is one way, and the one this pass looks at.* Whether that happens,
  and when inside a hold, has not been looked at. The earlier passes used one number per hold,
  taken 1.8 to 2.6 s after the request.
- The [simulator's forecast of B1](JEVBWE_TYPED_B1_FORECAST_V1.md) showed that the simulated
  estimator responds to a cap differently from the browser's. Changing it needs to know how
  the browser's estimate moves inside a hold, not only where it ends.
- B1's registered window is late in the hold. This pass shows what that window does and does
  not see of the mechanism.

## Fixed before any of it was computed

To write the reader, the format of one peer's files was inspected: field names, event kinds
and timestamps. No quantity by arm was computed.

**Data.** The 480 peers and 2,880 holds of the stage-one capture. Per peer: the sender's
polls every 100 ms (the browser's live estimate and the encoder's target), the encoded-frame
meter, and the relay's packet log. Each peer's raw logs are bound to its audited rows by
trial, hold, arm, acknowledgement time and frozen estimate.

**Time axis.** Milliseconds since the hold's request was acknowledged, in fifteen bins of
200 ms. Bins that end after the measurement cutoff are left empty. The relay runs on another
clock than the page. The page opens the first capacity phase as its measurement starts, so the
difference between the two clocks is the first phase's relay time minus the measurement start.

**Curves, per hold and bin.** Rates are over the hold's frozen estimate.

| Name | What |
|---|---|
| encoder | encoded payload bytes of the bin, as a rate (the auditor's definition) |
| target | the encoder's own target bitrate, mean over the polls of the bin |
| estimate | the browser's live estimate, mean over the polls of the bin |
| sent | wire bytes offered to the relay in the media direction, as a rate |
| estimate over capacity | the live estimate over the relay capacity in force |
| sojourn | time from a packet's arrival at the relay to the end of its service, mean over the forwarded packets that arrived in the bin; the fixed 25 ms of propagation is not included |
| dropped share | wire bytes the full queue dropped over wire bytes offered |

**Unit and intervals.** The source. Holds are averaged within source and schedule, schedules
are weighted equally, and intervals are two-sided 95% t intervals over the twelve sources,
not corrected for the number of quantities.

**Tables.** Each by requested ratio, with the top ratio minus the mean of the two lower ones.

1. **Encoder settling.** Encoder and target over 0.2 to 0.6 s, 0.8 to 1.2 s and the registered
   window of 1.8 to 2.6 s, holds 2 to 6, all schedules.
2. **The estimate when the link has room.** The estimate over its frozen value at 0.8 to 1.2 s,
   1.8 to 2.2 s and 2.8 to 3.0 s, underutilized schedule, for the first hold and for later ones.
3. **The capacity drop.** The third hold of the queue-building and collapse-recovery
   schedules, where capacity falls shortly before the hold begins: peak sojourn over the hold,
   sojourn in the registered window, dropped share over the hold and in the registered window,
   and the estimate over the new capacity at the end of the hold.
4. **The recovery.** The fifth hold of collapse-recovery, where capacity returns: the estimate
   at the end of the hold and the encoder in the registered window.
5. **Steady constraint.** Near-capacity from the third hold on, and the fourth hold of the two
   schedules with a drop: the same five quantities as in table 3.

The mean curves per schedule, hold and ratio are written out for figures, and the per-hold
curves are kept so that the 8 GB of raw logs are not needed again.

**Reading, fixed here.**

- *A mechanism for backing off is present in a state* when the top ratio carries more queue or
  more loss there than the lower ratios: the contrast in peak sojourn or in dropped share has
  an interval above zero.
- *The registered window sees it* when the same holds for sojourn or dropped share inside 1.8
  to 2.6 s.
- Neither statement is about delivered quality. A mechanism can be present and too small or
  too brief to matter, and this pass cannot tell.
- *Added with the correction:* both statements are about the relay path. "No mechanism" by
  this rule means no more queue or loss at the relay. It does not mean that a cap has nothing
  to act on.

## What this cannot show

- Whether backing off helps delivered quality. That is B1's question, on fresh sources.
- *Added with the correction:* anything at the receiver. How long the receiver holds a frame
  before showing it, and whether a frame is shown at all, are not read.
- Anything beyond one browser build, one relay and four scripted schedules.
- It is a further look at twelve sources that have been looked at three times. The quantities
  here are physical and were not chosen after seeing them, but they are still exploratory.

## Command

```sh
uv run --frozen python -m media_rl.native_actuator_qualification_dynamics \
    --rows results/native-actuator-qualification-n1-stage-one-cohorts.json.gz \
    --capture results/native-actuator-qualification-n1-stage-one \
    --out results/native-actuator-qualification-n1-dynamics
```

It needs the raw capture, which is on this machine and in the private archive described in
[ARCHIVED_RESULTS.md](../ARCHIVED_RESULTS.md).

## Results

Run once on 2026-10-10 over all 480 peers and 2,880 holds, at commit `47601ff`. The first
attempt stopped before reading any log, because the reader appended a suffix that the trial
names already carry; that was fixed and committed before the run. Output:
`results/native-actuator-qualification-n1-dynamics/report.json`, with the per-hold curves in
`holds.json.gz` beside it. The relay's clock ran 0.44 to 2.37 s ahead of the page's (median
0.76 s), measured per peer. Brackets are 95% intervals over the twelve sources.

Holds are numbered 1 to 6. In the two schedules with a drop, capacity falls a few tenths of
a second before hold 3 begins and, in collapse-recovery, returns a few tenths of a second
before hold 5 begins.

### 1. The encoder needs most of a hold to settle

Holds 2 to 6, all schedules, over the frozen estimate:

| | Ratio | 0.2 to 0.6 s | 0.8 to 1.2 s | 1.8 to 2.6 s |
|---|---:|---:|---:|---:|
| Encoder target | 0.65 | 0.536 | 0.533 | 0.616 |
| | 0.85 | 0.687 | 0.683 | 0.768 |
| | 1.05 | 0.772 | 0.776 | 0.889 |
| Encoder output | 0.65 | 0.586 | 0.516 | 0.584 |
| | 0.85 | 0.667 | 0.625 | 0.719 |
| | 1.05 | 0.683 | 0.692 | 0.800 |

The curves with room on the link show the shape. For about a second after a request the
target sits below the new cap: at 0.54, 0.70 and 0.80 of the estimate, which is 0.83, 0.82 and
0.76 of the cap. It reaches the cap at about 1.7 to 1.9 s. The output climbs through the whole hold and reaches the cap only in
the last 0.4 s: 0.65, 0.82 and 1.04 of the estimate at 2.8 to 3.0 s in hold 2.

- **The registered window sees the encoder before it has settled.** N1's finding that 72% and
  47% of the requested steps were realised is a statement about 1.8 to 2.6 s. With room, by
  the end of the hold the steps are nearly complete.
- **At the top ratio the encoder does reach 1.04 of the frozen estimate when the link has
  room,** because by then the live estimate has risen far above the cap (next table). Under
  constraint it does not: the target stays at 0.87 to 0.92, held by the browser's own
  allocation and not by the cap. So "the encoder sat at 0.83 of the estimate at ratio 1.05"
  was a mid-hold average over schedules, and it hides two different regimes.

### 2. With room, a cap above the estimate makes the estimate jump

Underutilized schedule, live estimate over its frozen value:

| Holds | Ratio | 0.8 to 1.2 s | 1.8 to 2.2 s | 2.8 to 3.0 s |
|---|---:|---:|---:|---:|
| first | 0.65 | 1.69 | 1.69 | 1.69 |
| | 0.85 | 1.89 | 1.89 | 1.90 |
| | 1.05 | 2.12 | 2.12 | 2.13 |
| later | 0.65 | 1.03 | 1.04 | 1.05 [1.03, 1.07] |
| | 0.85 | 1.04 | 1.08 | 1.14 [1.12, 1.17] |
| | 1.05 | 1.90 | 1.92 | 1.94 [1.89, 1.98] |

Mean curve in hold 2, by 200 ms bin from the acknowledgement:

| Ratio | 0.1 s | 0.3 | 0.5 | 0.7 | 0.9 | 1.5 | 2.1 | 2.9 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.65 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.01 |
| 0.85 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.03 | 1.06 | 1.11 |
| 1.05 | 1.00 | 1.24 | 1.84 | 1.94 | 1.97 | 1.97 | 1.99 | 2.02 |

- **At the top ratio the estimate nearly doubles within 0.6 s of the request and is then
  flat.** It is a step, not a ramp. In the same first 200 ms the sender puts 0.78 of the
  estimate on the wire while the encoder produces 0.50; at the lower ratios the two differ by
  about 0.05. That is consistent with the browser probing when the cap is raised above its
  estimate, though the logs do not name probes.
- **Below the estimate the cap holds it nearly still:** about +5% per hold at 0.65 and +14% at
  0.85, after the first hold.
- **This refines an earlier statement.** The first pass reported growth of 18%, 24% and 100%
  per hold at the three ratios. Those figures pooled the first hold, in which the estimate
  grows by 70% to 110% at every ratio while the session starts. After the first hold the
  figures are 5%, 14% and 94%.
- **Backing off costs headroom.** After the return of capacity (hold 5 of collapse-recovery)
  the estimate ends the hold at 1.13, 1.24 and 1.80 of its frozen value at the three ratios:
  top minus lower +0.65 [+0.47, +0.83]. Only the top ratio lets it recover.

### 3. When capacity drops, every ratio overshoots and the browser cuts within a second

Hold 3 of the two schedules with a drop. The request is a ratio of an estimate frozen before
the browser could see the drop, so even 0.65 of it is above the new capacity.

| Schedule | Quantity | 0.65 | 0.85 | 1.05 | Top minus lower |
|---|---|---:|---:|---:|---|
| queue-building (1.2 to 0.6) | peak sojourn, ms | 107 | 136 | 142 | +25 [-19, +69] |
| | sojourn at 1.8 to 2.6 s, ms | 28 | 38 | 23 | -11 [-19, -3] |
| | dropped share over the hold | 0.000 | 0.001 | 0.003 | +0.003 [-0.000, +0.005] |
| | estimate over capacity at the end | 0.90 | 0.90 | 0.82 | -0.07 [-0.12, -0.02] |
| collapse-recovery (1.2 to 0.35) | peak sojourn, ms | 332 | 403 | 406 | +39 [-6, +84] |
| | sojourn at 1.8 to 2.6 s, ms | 73 | 131 | 131 | +29 [-70, +128] |
| | dropped share over the hold | 0.019 | 0.052 | 0.050 | +0.015 [-0.024, +0.053] |
| | estimate over capacity at the end | 0.85 | 0.84 | 0.81 | -0.04 [-0.11, +0.03] |

Mean curves in the deeper drop, by 200 ms bin:

| Quantity | Ratio | 0.1 s | 0.3 | 0.5 | 0.7 | 0.9 | 1.3 | 1.7 | 2.1 | 2.5 | 2.9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| estimate over capacity | 0.65 | 2.46 | 2.06 | 1.25 | 1.02 | 0.89 | 0.84 | 0.84 | 0.85 | 0.85 | 0.85 |
| | 0.85 | 2.74 | 2.35 | 1.39 | 1.08 | 0.90 | 0.83 | 0.83 | 0.84 | 0.83 | 0.84 |
| | 1.05 | 2.80 | 2.06 | 1.31 | 1.03 | 0.89 | 0.82 | 0.82 | 0.80 | 0.80 | 0.80 |
| sojourn, ms | 0.65 | 223 | 303 | 313 | 296 | 265 | 204 | 134 | 85 | 36 | 34 |
| | 0.85 | 281 | 386 | 382 | 351 | 314 | 272 | 234 | 153 | 71 | 27 |
| | 1.05 | 279 | 388 | 384 | 361 | 329 | 262 | 199 | 141 | 98 | 66 |
| dropped share | 0.65 | 0.007 | 0.097 | 0.039 | 0.000 | 0 | 0 | 0 | 0 | 0 | 0 |
| | 0.85 | 0.039 | 0.255 | 0.076 | 0.002 | 0 | 0 | 0 | 0 | 0 | 0 |
| | 1.05 | 0.078 | 0.189 | 0.060 | 0.010 | 0 | 0 | 0 | 0 | 0 | 0 |

- **By the rule fixed above, no mechanism for backing off is established in the drop hold:**
  the top ratio does not carry more queue or loss than the two lower ones taken together, in
  either schedule, and the registered window does not show one either.
- **The browser's own controller does the work.** At every ratio the live estimate is below
  the new capacity within 0.4 to 0.6 s in the shallower drop and within about 0.9 s in the
  deeper one. All loss falls in the first 0.8 s.
- **Described, not tested: the lowest ratio stands apart in the deeper drop.** It loses 2% of
  its bytes over the hold against 5% at the other two, and its queue peaks lower and drains
  sooner. The two higher ratios are alike. The contrast fixed in advance does not isolate
  this, and none is added after seeing it.
- **In the shallower drop the top ratio's queue drains faster,** because its estimate was cut
  deeper: in the registered window it has less queue than the lower ratios, not more.

### 4. Under steady constraint the link is not congested at any ratio

Near-capacity from hold 3 on, and hold 4 of the two schedules with a drop:

| Quantity | 0.65 | 0.85 | 1.05 | Top minus lower |
|---|---:|---:|---:|---|
| peak sojourn, ms | 32 | 35 | 37 | +3.6 [-4.7, +11.9] |
| sojourn at 1.8 to 2.6 s, ms | 17.4 | 22.9 | 25.5 | +5.4 [+3.8, +6.9] |
| dropped share | 0.000 | 0.000 | 0.000 | 0 |

- **No packet is dropped at any ratio, and a packet spends about 20 ms in the relay.** That
  is close to the time the link needs to send one frame.
- **By the rule, the registered window sees a difference: 5 ms more at the top ratio.** It is
  established and very small. The rule's first test, on the peak, is not met.
- **The browser's estimate sits near or a little below capacity whatever the cap:** between
  0.9 and 1.0 of it in hold 4 under near-capacity, and 0.94 at the end of the hold after the
  shallower drop, in the curves. The table's own
  figure for this quantity, 0.72 at every ratio, is not usable: in collapse-recovery the last
  bin of hold 4 falls after capacity has returned, so the average mixes two capacities.

### 5. Which holds B1's flag marks (no outcome is read)

Computed from the frozen estimates and the plan with B1's registered flag, by
`python -m media_rl.native_backoff_benefit_positions --composition` on the tracked rows
(`results/native-phase-b1-flag-composition.json`). Share of holds flagged, by schedule and
hold:

| Schedule | Hold 2 | Hold 3 | Hold 4 | Hold 5 | Hold 6 |
|---|---:|---:|---:|---:|---:|
| underutilized | 0% | 32% | 20% | 23% | 19% |
| near-capacity | 0% | 50% | 29% | 55% | 39% |
| queue-building | 0% | 47% | 89% | 32% | 44% |
| collapse-recovery | 0% | 47% | 99% | 46% | 7% |

Of the 814 flagged holds:

| Kind of hold | Share of flagged holds | What the logs show there |
|---|---:|---|
| the hold after a drop (hold 4 of the two drop schedules) | 28% | the browser has already cut; no loss, short queue at every ratio |
| near-capacity, any hold | 26% | no loss, short queue at every ratio |
| later holds of the two drop schedules | 19% | no loss, short queue; after the return of capacity only the top ratio recovers |
| the hold of the drop itself (hold 3) | 14% | the overshoot of section 3 |
| underutilized, any hold | 14% | nothing to relieve; flagged almost only after a request of 0.65 |

- **Hold 2 is never flagged,** because the estimate always grows while the session starts.
- **The hold of the drop is flagged about half the time, and not because the flag sees the
  drop.** Over the two schedules it is flagged 93% of the time after a request of 0.65, and 18%
  and 29% of the time after the other two. The drop comes a few tenths of a second before the hold begins, too late for
  the frozen estimate to show it.
- **The flag does mark the hold after a drop,** almost always. By then the browser has cut.

### 6. Is the top ratio "no cap"? (added after the tables were read)

Not in the design above. It is computed from the saved per-hold curves by
`python -m media_rl.native_actuator_qualification_dynamics --binding` and recorded in
`binding.json` beside the report. A hold's cap binds when the encoder's target at 2.4 to 3.0 s
is at least 0.97 of the cap. Where it does not, the browser's own allocation is the limit and
the cap changes nothing. Share of holds 2 to 6 whose cap binds:

| Schedule | 0.65 | 0.85 | 1.05 | 1.05, over sources |
|---|---:|---:|---:|---|
| underutilized | 99% | 95% | 95% | 96% [93, 98] |
| near-capacity | 95% | 78% | 34% | 33% [21, 45] |
| queue-building | 77% | 73% | 24% | 24% [14, 35] |
| collapse-recovery | 74% | 64% | 49% | 49% [40, 58] |

- **With room the top ratio's cap binds almost always,** and it sits at a median 0.50 of the
  live estimate. The request raised the estimate to twice its frozen value and then holds the
  encoder at 1.05 of that frozen value.
- **Where no cap binds, the browser allots the encoder a median 0.82 of its live estimate**
  (quartiles 0.77 to 0.87).
- **After capacity returns the top ratio binds again:** in 71% and 98% of holds 5 and 6 of
  collapse-recovery.
- **In the hold of a drop it never binds at the top ratio** (2% and 0%). There the top ratio
  is the browser left alone.

What follows:

- **The top ratio is not the browser left alone.** B1's registration says the top ratio
  stands in for "no cap". That holds where the browser's allocation is the limit: in the hold
  of a drop and in most constrained holds. It fails with room and after capacity returns,
  and there B1 compares three caps with each other.
- ~~**Every native condition in this repository has had an application cap.** The browser
  without one has never been measured in this harness. It is the baseline that a cap
  controller would have to beat, and whether any ratio of the estimate does as well as it is
  not known.~~ *Wrong; see the correction at the top.* Earlier development diagnostics ran
  the browser under a 4 Mbit/s ceiling. It delivered 10% to 51% of frames on time, against 56%
  to 92% for the capped senders of the same studies, and was the worst condition of each.
- ~~A cap can only withhold rate from the browser. It can pay only where withholding relieves
  congestion that the browser would not have relieved as fast.~~ *Too narrow.* That holds at
  the relay. Those diagnostics put the cost of a high rate at the receiver, where withholding
  rate may pay without any congestion at the relay.

## Reading

- **Mechanism.** On this stack the logs show one place where a lower cap leaves less queue and
  loss: the first second after capacity collapses, and there it is the lowest ratio that
  differs. Everywhere else the browser keeps the link below capacity by itself and a cap
  lowers the rate without relieving anything at the relay. By the rule fixed in advance, no
  mechanism is established in the drop hold, and under steady constraint the registered window
  sees 5 ms. *Corrected:* this is the relay path. The receiver was not read.
- **What it suggests about B1, and what it does not.** About a seventh of the holds B1's flag
  marks are of the one kind where a mechanism was seen. This pass read no quality label, so it
  cannot say whether that is enough for a benefit, and the earlier pilot leaned toward one in
  flagged holds without establishing it. It does say where a benefit by way of the relay
  would have to come from. *Corrected:* a benefit by way of the receiver could sit in any
  hold. If B1 finds one, the question is whether it sits in the hold of the scripted drop,
  which the flag does not anticipate. An addendum to B1, fixed before B1 has data, splits its
  flagged holds by position to answer that.
- **What a controller could do with a cap.** The drop cannot be seen in the estimate before
  the hold in which it hits, and the browser reacts within a second. At the relay a cap could
  gain only by being faster than the browser inside that second, or by predicting the drop. A
  3 s hold decided at its start can do neither. *Corrected:* whether a cap gains at the
  receiver is a separate question that this pass does not touch.
- **What backing off costs.** After a request below the estimate the estimate barely grows,
  and after capacity returns only the top ratio lets it recover. A controller that backs off
  pays for it in the following holds.
- **For the simulator.** These curves are what a native-like simulated estimator and encoder
  would have to reproduce: a jump of the estimate within 0.6 s of a cap above it, near
  standstill under a cap below it, a cut to below capacity within a second of a drop, a target
  that needs about 1.8 s to reach a new cap, and an output that needs the whole hold.

Nothing here is confirmatory, nothing about delivered quality was measured, and nothing at the
receiver was read.
