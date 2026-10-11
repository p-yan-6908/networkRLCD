# Native Phase N1: where a hold's frames and time go (exploratory)

**Not part of the N1 registration and not confirmatory.** This is a fourth exploratory pass
over the one N1 sample. It follows the [within-hold pass](NATIVE_PHASE_N1_DYNAMICS.md), which
read the sender and the relay only and was corrected for calling the relay the only path by
which a cap can act. This pass reads the rest of the path. It fits no model, evaluates no
controller and changes nothing in [Native Phase B1](NATIVE_PHASE_B1_BACKOFF_BENEFIT.md), which
is frozen.

**Unlike the third pass it reads part of the outcome.** For every capture request it reads
what the auditor recorded: whether the frame was read back at the receiver, how old it was,
and whether that was within the 150 ms deadline. It reads no PSNR and does not compute the
registered endpoint.

## Why

- The endpoint counts a frame when its pixels are read back within 150 ms of the capture
  request. That time passes through the encoder, the sender's pacer, the relay and the
  receiver. The third pass looked at the relay.
- Earlier development diagnostics name two other places. At a high rate the receiver held
  frames longer: 108 to 121 ms of buffering under a 4 Mbit/s ceiling against about 38 ms under
  a fixed cap ([Repair V5](NATIVE_REPAIR_V5.md)). At a low cap the encoder skipped frames:
  about 470 encoded from more than 540 requests (same record).
- N1's [exploratory record](NATIVE_PHASE_N1_EXPLORATORY.md) found the on-time fraction nearly
  equal between the three ratios (1.05 minus 0.65: +0.025 [-0.006, +0.055]). One number can
  hide two effects of opposite sign.

## Fixed before any of it was computed by ratio

To write the reader, the files of a few peers were inspected for format, and four things were
checked without splitting anything by ratio:

- On 72 holds of twelve peers the per-request labels reproduce the auditor's rows exactly:
  the frames of the registered window are the requests captured 1.8 to 2.6 s after the
  acknowledgement, and the share on time equals the row's on-time fraction.
- On four peers the encoded-frame meter counts as many frames as the browser's own counter.
- Tying an encoded frame to its capture request by RTP timestamp was tried on four peers and
  is ambiguous by whole frame intervals. So frames are split by counts in a window, not frame
  by frame.
- A pooled count over twelve peers showed that frames read back after the deadline are common.

**Data.** The 480 peers and 2,880 holds of the stage-one capture. Per peer: the auditor's
per-request labels (`native_derived.json`), the sender's polls with the browser's cumulative
counters, the encoded-frame meter, the relay's packet log, and the page's snapshot of both
ends at the close of each capacity phase (`summary.json`). Each peer is bound to its audited
rows by trial, hold, arm, acknowledgement time and frozen estimate, and the reader stops if a
hold's labels do not reproduce the row's on-time fraction.

**Windows.** By capture time since the hold's request was acknowledged: the registered window
of 1.8 to 2.6 s, and the whole hold of 0 to 3.0 s. A window is cut where requests stop
carrying a label, 150 ms before the measurement ends.

**What became of the frames,** as shares of the window's requests R. They sum to one.

| Name | What |
|---|---|
| never encoded | (R - E) / R, with E the frames the meter saw encoded in the window |
| encoded, not shown | (E - S) / R, with S the requests whose frame was read back |
| shown late | (S - O) / R, with O the requests read back within 150 ms |
| on time | O / R |

The first two are differences of counts taken on two clocks of the same page, so in a single
hold either can be slightly negative. "Encoded, not shown" covers loss at the relay, frames
the receiver did not decode and frames it decoded but did not display. The relay's dropped
share of wire bytes in the window is reported beside it.

**How old the shown frames are.** Median and 90th percentile of the readback age in the
window, in ms.

**Where the time goes,** means over the window in ms.

| Name | What |
|---|---|
| encode | the browser's encode time per encoded frame |
| pacer | the browser's packet send delay per packet sent |
| relay | mean sojourn of the packets that arrived at the relay in the window, plus the fixed 25 ms of propagation |
| rest | mean age of the shown frames minus the three above |
| frame wire time | mean encoded frame size over the relay capacity in force: how long the link needs for one frame |

"Rest" is what is left: the receiver's buffering, decoding, display and readback, the time
from the capture request to the encoder, and the part of a frame's own serialisation that the
mean packet sojourn misses, because a frame is complete only with its last packet. Frame wire
time is a guide to that last part. "Rest" is therefore not the receiver alone.

**The receiver, per capacity phase.** The page snapshots both ends when each of the three
capacity phases closes. Each phase holds two holds (1 and 2, 3 and 4, 5 and 6), shifted by a
few tenths of a second. The browser's counters run from the start of the connection, so a
phase is the difference between two snapshots, with decoded frames standing in for the frames
the jitter buffer emitted.

| Name | What |
|---|---|
| jitter buffer | the receiver's jitter-buffer delay per frame, ms |
| jitter target | the delay the receiver's jitter buffer aimed for, per frame, ms |
| decoded share | frames decoded over frames encoded |
| freezes | freezes the receiver counted |

A phase mixes two holds, so these are reported as a slope on the mean requested ratio of the
phase's two holds: least squares within source, schedule and phase position, cells of fewer
than three peers or with one ratio only left out, cells averaged within source, and scaled to
0.40 of ratio, the distance from 0.65 to 1.05. The ratio of a hold was drawn at random, so
the slope is the effect of the requested ratio on the phase.

**Unit and intervals.** The source. Holds are averaged within source and schedule, schedules
are weighted equally, and intervals are two-sided 95% t intervals over the twelve sources, not
corrected for the number of quantities. Tables by requested ratio carry the top ratio minus
the mean of the two lower ones.

**Tables.**

1. **All schedules,** holds 2 to 6: frames, ages and time, in both windows.
2. **Each schedule,** holds 2 to 6: the same.
3. **The hold of a capacity drop,** the third hold of the queue-building and collapse-recovery
   schedules: the same.
4. **The receiver per phase:** levels and slopes over all phases, by schedule and by phase
   position.

**Reading, fixed here.** Per state, in the registered window unless said otherwise.

- *A lower cap costs frames at the encoder* when "never encoded" at the top ratio minus the
  lower ratios has an interval below zero.
- *A higher cap costs time after the relay* when "rest" at the top ratio minus the lower
  ratios has an interval above zero.
- *A higher cap fills the receiver's buffer* when the slope of the jitter-buffer delay on the
  requested ratio has an interval above zero.
- *It reaches the deadline* when "shown late" at the top ratio minus the lower ratios has an
  interval above zero.
- None of these says whether backing off helps. That needs the quality of the frames as well
  as their timing and is B1's question, on fresh sources.

## What this cannot show

- Anything above the top ratio. N1's three ratios are three caps. The rates at which the
  earlier diagnostics saw delivery fail were reached under a 4 Mbit/s ceiling, and with room
  N1's top ratio holds the encoder at about half of the browser's live estimate.
- Which frame met which fate. The split is by counts.
- How much of "rest" is the receiver.
- Anything beyond one browser build, one relay and four scripted schedules.
- It is a fourth look at twelve sources. The quantities are physical and were fixed before
  they were computed by ratio, but the on-time fraction by ratio was already known from the
  first exploratory pass, and the whole pass is exploratory.

## Command

```sh
uv run --frozen python -m media_rl.native_actuator_qualification_delivery \
    --rows results/native-actuator-qualification-n1-stage-one-cohorts.json.gz \
    --capture results/native-actuator-qualification-n1-stage-one \
    --out results/native-actuator-qualification-n1-delivery
# Added after the tables were read (section 5 of the results):
uv run --frozen python -m media_rl.native_actuator_qualification_delivery \
    --first-hold results/native-actuator-qualification-n1-delivery/holds.json.gz \
    --out results/native-actuator-qualification-n1-delivery/first_hold.json
```

## Results

Run on 2026-10-10 from the design committed as `e553c60`: 480 peers, 2,880 holds, 1,440
capacity phases, 12 sources. Every hold's labels reproduced its audited on-time fraction.
Report, per-hold figures and the split of section 5 are in
`results/native-actuator-qualification-n1-delivery/`. Brackets are 95% t intervals over
sources. "Top minus lower" is the top ratio minus the mean of the two lower ones.

### 1. All schedules, holds 2 to 6, registered window

| | 0.65 | 0.85 | 1.05 | Top minus lower |
|---|---:|---:|---:|---|
| never encoded | 2.8% | 4.1% | 2.8% | -0.7 pt [-1.8, +0.4] |
| encoded, not shown | 3.6% | 3.5% | 3.7% | +0.2 pt [-0.2, +0.5] |
| shown late | 17.3% | 17.5% | 19.5% | +2.1 pt [-0.6, +4.7] |
| on time | 76.3% | 74.9% | 74.0% | -1.5 pt [-4.1, +1.0] |
| median age, ms | 136 | 149 | 145 | +2.0 [-4.6, +8.6] |
| 90th percentile age, ms | 147 | 160 | 156 | +2.2 [-4.8, +9.1] |
| encode, ms | 1.9 | 2.0 | 2.0 | +0.1 [+0.0, +0.1] |
| pacer, ms | 2.7 | 9.0 | 6.3 | +0.4 [-6.1, +6.9] |
| relay, ms | 40.9 | 48.5 | 45.9 | +1.2 [-2.7, +5.0] |
| rest, ms | 91.0 | 89.9 | 90.8 | +0.4 [-5.9, +6.7] |
| frame wire time, ms | 14.5 | 17.6 | 18.1 | +2.1 [+1.7, +2.4] |

The ages are means over sources of per-hold figures, across four very different schedules.

- **None of the three statements about the window holds.** Never encoded, rest and shown late
  do not differ between the top ratio and the lower ones by the rule.
- **A request that misses the deadline was mostly shown, late.** 17% to 20% of requests,
  against 3% to 4% never encoded and under 4% encoded and not shown. The relay dropped nothing
  in the window.
- **Most of the age is after the relay.** Of about 140 ms, the relay accounts for 41 to 49 ms,
  25 of them propagation, the encoder and the pacer for under 12 ms, and about 90 ms is left.
- Over the whole hold the picture is the same, with one difference: "rest" is 4.0 ms [+0.6,
  +7.3] larger at the top ratio. The rule was fixed on the registered window, so this is noted
  and not counted as a statement.

### 2. By schedule, holds 2 to 6, registered window

| Schedule | On time, 0.65 / 0.85 / 1.05 | Top minus lower | Shown late | Median age, ms | Relay, ms | Rest, ms |
|---|---|---|---|---|---|---|
| underutilized | 93.9% / 93.3% / 92.7% | -0.9 pt [-3.2, +1.4] | 1.2% / 1.7% / 2.1% | 80 / 82 / 83 | 30 / 31 / 32 | 49 / 49 / 49 |
| near-capacity | 89.4% / 86.3% / 86.5% | -1.3 pt [-3.9, +1.2] | 6.2% / 9.3% / 8.5% | 115 / 121 / 119 | 41 / 49 / 48 | 72 / 69 / 69 |
| queue-building | 69.2% / 67.5% / 66.2% | -2.1 pt [-8.6, +4.4] | 25.8% / 27.8% / 29.5% | 137 / 141 / 140 | 44 / 48 / 47 | 90 / 90 / 90 |
| collapse-recovery | 52.5% / 52.5% / 50.7% | -1.8 pt [-9.1, +5.5] | 36.1% / 31.3% / 37.8% | 213 / 253 / 237 | 49 / 67 / 57 | 153 / 151 / 156 |

- **The schedule moves on-time delivery from 93% to 52%. The ratio moves it by one or two
  points,** and no interval excludes zero.
- **"Rest" follows the schedule and not the ratio:** 49 ms with room, then 70, 90 and 153 ms,
  alike at the three ratios. Under collapse-recovery it alone exceeds the deadline.
- At the relay the top ratio waits a little longer where the within-hold pass also saw it:
  +3.2 ms [+1.0, +5.4] under near-capacity, +1.4 ms [+0.8, +2.0] with room, +1.4 ms [+0.0,
  +2.9] under queue-building.
- Under collapse-recovery the encoder skips more: 7.6%, 13.2% and 8.0% never encoded, and the
  pacer holds packets for 9, 33 and 24 ms. Neither contrast is established.

### 3. The receiver per capacity phase

Level, and slope per 0.40 of requested ratio.

| Phases | Jitter buffer, ms | Slope | Jitter target, ms | Slope |
|---|---:|---|---:|---|
| all | 64.9 | +10.5 [+4.6, +16.3] | 56.1 | +4.7 [-1.7, +11.0] |
| underutilized | 27.2 | +0.6 [-3.7, +4.9] | 37.5 | -2.1 [-12.6, +8.3] |
| near-capacity | 48.8 | +2.5 [-2.6, +7.5] | 50.7 | +0.5 [-3.4, +4.4] |
| queue-building | 60.1 | +2.8 [-11.0, +16.5] | 52.7 | -1.6 [-20.2, +17.1] |
| collapse-recovery | 123.6 | +36.0 [+15.1, +56.9] | 83.6 | +21.8 [+1.0, +42.7] |
| first phase (holds 1 and 2) | 23.6 | +3.8 [+0.6, +7.0] | 29.6 | +2.7 [-0.2, +5.6] |
| second phase (holds 3 and 4) | 87.0 | +23.6 [+3.7, +43.6] | 63.4 | +7.2 [-5.1, +19.6] |
| third phase (holds 5 and 6) | 84.2 | +3.9 [-14.1, +22.0] | 75.4 | +4.1 [-12.8, +20.9] |

- **A higher cap fills the receiver's buffer,** by the rule: +10.5 ms [+4.6, +16.3] from the
  lowest to the top ratio over all phases. The slope comes from collapse-recovery (+36 ms) and
  from the phase that contains the drop (+24 ms). With room and under near-capacity it is
  near zero.
- **The buffer's level follows the schedule** as "rest" does: 27 ms with room, then 49, 60 and
  124 ms. The two differ by 20 to 30 ms throughout, so most of what grows in "rest" is the
  receiver's jitter buffer. (The buffer is per phase over all six holds, "rest" is the
  registered window of holds 2 to 6, so the comparison is rough.)
- The decoded share falls slightly with the ratio (-0.003 [-0.006, -0.001] overall) and the
  second phase has more freezes at a higher ratio (+0.31 [+0.05, +0.56] per phase).

### 4. The hold of a capacity drop, whole hold

| | 0.65 | 0.85 | 1.05 | Top minus lower |
|---|---:|---:|---:|---|
| **collapse-recovery,** on time | 34.5% | 25.1% | 20.1% | -9.7 pt [-21.9, +2.5] |
| never encoded | 18.8% | 30.4% | 29.3% | +4.7 pt [-3.0, +12.4] |
| shown late | 38.9% | 35.8% | 42.9% | +5.6 pt [-11.4, +22.5] |
| median age, ms | 335 | 523 | 562 | +133 [-164, +429] |
| pacer, ms | 21 | 57 | 59 | +19 [-37, +75] |
| relay, ms | 219 | 284 | 279 | +28 [-32, +87] |
| rest, ms | 114 | 191 | 229 | +76 [-87, +240] |
| **queue-building,** on time | 57.2% | 53.8% | 55.4% | -2.5 pt [-14.0, +9.0] |
| encoded, not shown | 4.2% | 4.4% | 7.3% | +3.2 pt [+0.4, +6.0] |
| median age, ms | 148 | 166 | 167 | +12 [-19, +43] |

- **Nothing is established in the deeper drop.** The lowest ratio is ahead on every line and
  every interval is wide: a hold of this kind occurs once per peer.
- In the shallower drop the top ratio has more frames encoded and not shown over the whole
  hold (+3.2 pt [+0.4, +6.0]), one interval among many that were not corrected.

### 5. The first hold (added after the tables were read)

Not in the design above. The on-time contrast of section 1 has the opposite sign from the
first exploratory pass (1.05 minus 0.65: +0.025). The estimator is the same. That pass pooled
all six holds and the tables here start at the second. The split is computed by
`--first-hold` from the saved per-hold figures and recorded in `first_hold.json`.

| Holds | 0.65 | 0.85 | 1.05 | 1.05 minus 0.65 |
|---|---:|---:|---:|---|
| all six | 74.0% | 76.5% | 76.5% | +2.5 pt [-0.6, +5.5] |
| the first | 67.0% | 82.6% | 87.9% | +21.0 pt [+8.8, +33.1] |
| the second to the sixth | 76.3% | 74.9% | 74.0% | -2.2 pt [-5.0, +0.5] |

- **In the first hold a low cap costs frames at the encoder.** The session starts under a cap
  of 300 kbit/s, so the lowest ratio asks for 195 kbit/s. Never encoded: 28.7%, 12.8% and 5.5%
  of requests (1.05 minus 0.65: -23.2 pt [-37.6, -8.7]). Almost nothing is shown late.
- **From the second hold on the sign is the other way,** at every position (-0.2 to -4.2 pt)
  and under every schedule (-1.2 to -3.0 pt), and never established. At the fourth hold the
  top ratio minus the lower ones is -5.2 pt [-9.7, -0.6], one of six positions, not corrected.
- The first pass's own table by pair of holds shows the same for the utility: +3.3 to +5.1 in
  holds 1 and 2, mixed and mostly negative afterwards.

## Reading

- **On-time delivery in N1 is set by the schedule, at the receiver.** From 93% of requests on
  time with room to 52% under collapse-recovery, the frames are encoded, cross the relay and
  are shown, too late. What grows is the time after the relay, and most of that is the
  receiver's jitter buffer: 27 ms with room, 124 ms under collapse-recovery. This agrees with
  where the earlier diagnostics put the cost.
- **Between N1's three ratios the cap moves little of it.** One statement of four holds by the
  rule: a higher cap fills the receiver's buffer, after a collapse. The share on time differs
  by a point or two against the top ratio from the second hold on, with intervals that include
  zero.
- **The first hold is a different regime.** There a low cap makes the encoder skip frames, and
  the top ratio is 21 points ahead. The earlier statement that the top ratio is no worse on
  timing was an average of this and of a small disadvantage afterwards.
- **For B1.** B1's flag handles holds 2 to 6, so the first hold's effect is outside it. B1's
  endpoint weighs each on-time frame by its PSNR. On these sources the timing side of backing
  off is a point or two with an interval that includes zero; whether the quality of the frames
  outweighs that is what B1 measures. This pass does not predict it.
- **For a controller.** A choice among 0.65, 0.85 and 1.05 of the estimate does not reach what
  makes frames late here. The receiver's buffer followed the schedule at all three. Whether a
  cap well below 0.65 of the estimate would shrink it under constraint was not tested: N1
  varied the ratio over a narrow range. The earlier diagnostics, in which fixed caps far below
  capacity did best, point that way and do not establish it.
- **For the simulator.** The simulator's latency is half the round trip, the relay queue, the
  trace's jitter and a fixed 8 or 25 ms at the receiver (`environment.py`). Natively the
  receiver's buffer ran from 27 to 124 ms with the schedule. On this evidence the simulator
  leaves out the place where most native frames are lost to the deadline.

Nothing here is confirmatory. It is a fourth look at one sample, and section 5 was added
after the tables were read.
