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
```

## Results

Not yet captured when this was committed.
