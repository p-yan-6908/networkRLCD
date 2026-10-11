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
```

## Results

Not yet computed when this was committed.
