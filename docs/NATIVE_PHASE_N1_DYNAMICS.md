# Native Phase N1: what happens inside a hold (exploratory, mechanism only)

**Not part of the N1 registration and not confirmatory.** This is a third exploratory pass
over the one N1 sample. It reads the raw per-peer logs of the stage-one capture and describes
mechanism: the encoder, the browser's estimate and the relay's queue. **It reads no quality
or on-time label**, fits no model, evaluates no controller and changes nothing in
[Native Phase B1](NATIVE_PHASE_B1_BACKOFF_BENEFIT.md), which is frozen.

## Why

- A cap below the estimate can raise delivered quality in only one way: by leaving less in
  the queue and losing fewer packets than the browser would on its own. Whether that happens,
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

## What this cannot show

- Whether backing off helps delivered quality. That is B1's question, on fresh sources.
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

Not run at this commit. The design, the reader and its tests are committed first.
