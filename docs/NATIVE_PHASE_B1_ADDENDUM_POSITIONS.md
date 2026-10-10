# Native Phase B1 addendum: where in the schedule a benefit sits

**Fixed on 2026-10-10, before any B1 data exist and after B1's registration was frozen.**
It is not part of the [registration](NATIVE_PHASE_B1_BACKOFF_BENEFIT.md). It changes no
registered quantity, test or outcome and touches none of the four frozen files; the freeze
`9b3ac6ca...` still verifies. The agent added it without being asked, after an exploratory
look at N1's raw logs, and its results are to be labelled as an addendum wherever they appear.

## Why

The [within-hold description of N1](NATIVE_PHASE_N1_DYNAMICS.md) found one place where a
lower cap left less queue and loss: the first second after capacity collapses. It also found
that B1's flag does not anticipate that hold. The flag marks it about half the time, mostly
because the previous request was 0.65, and that hold makes up about a seventh of all flagged
holds. Elsewhere the browser keeps the link below capacity by itself.

So if B1 finds that backing off helps, its registered analysis cannot say whether the benefit
sits in the hold of the scripted drop or in a state the sender can recognise. A split chosen
after seeing B1's data would be worth little. Chosen now, it is a pre-specified secondary.

## 1. The registered contrast, by position of the hold

Run only after the registered final report has been written, on the sources that report
analysed and on the holds the registered flag handles (holds 2 to 6 of each peer).

| Kind | Holds |
|---|---|
| before the drop | hold 2 of queue-building and collapse-recovery |
| the drop | hold 3 of those two schedules; capacity falls shortly before it begins |
| after the drop | hold 4 of those two schedules |
| later, drop schedules | holds 5 and 6 of those two schedules |
| near-capacity | holds 2 to 6 of near-capacity |
| room | holds 2 to 6 of underutilized |

Per kind:

- the registered contrast, the mean of ratios 0.65 and 0.85 minus ratio 1.05, on the
  registered endpoint and on the on-time fraction;
- among the kind's flagged holds, and among all of its holds whether flagged or not;
- per source first, then the mean with a 95% t interval over sources;
- the number of holds, of flagged holds, their share of all flagged holds, and the number of
  sources that could be scored.

The cells are thin: in N1 a source had about nine flagged holds of the drop kind. For this
split only, a source is scored when it has one complete hold in every arm of the cell, where
the registration asks for three.

**Reading, fixed here.** Intervals are per kind at 95% and are not corrected for the six kinds.

| Statement | When |
|---|---|
| The benefit sits in the hold of the drop | among flagged holds the interval is above zero in the drop kind and in no other |
| The flag finds a usable state | among flagged holds the interval is above zero after the drop, later in the drop schedules, or under near-capacity |
| Backing off helps in the drop hold whatever the flag | among all holds of the drop kind the interval is above zero |

What each would mean:

- **Sits in the hold of the drop:** a benefit that B1 reports is one a controller acting on
  the flag could not count on, because the flag does not see the drop coming. It would exist
  only for a sender that happened to be capped when capacity fell.
- **The flag finds a usable state:** the estimate's stall marks holds in which a lower cap
  pays, which is what a controller would need.
- **Helps in the drop hold whatever the flag:** the mechanism seen in N1's logs reaches
  delivered quality. That is about the actuator, not about the flag.

None of these changes B1's outcome or what the registration says each outcome leads to.

## 2. The within-hold description, repeated on B1's capture

The reader and the five tables of the N1 pass are run unchanged on B1's capture blocks, with
the same reading rule: a mechanism is present in a state when the top ratio carries more
queue or loss there than the two lower ones, and the registered window sees it when that
holds inside 1.8 to 2.6 s. On N1 these tables were exploratory. On B1 they are fixed in
advance, on fresh sources. They remain mechanism only and read no quality label.

## Limits

- The positions are positions in four scripted schedules. There is a "hold of the drop"
  because the schedules script a drop at a fixed time.
- Six kinds, thin cells and no correction: an interval above zero in one kind can be chance.
- The kinds were chosen from N1. B1's sources are fresh, so that does not bias B1's
  estimates, but another choice of kinds was possible.

## Commands

```sh
# After the registered final report exists:
uv run --frozen python -m media_rl.native_backoff_benefit_positions \
    --protocol results/native-backoff-benefit-b1-plan/protocol.json \
    --capture results/native-backoff-benefit-b1-block-1 [--capture ...] \
    --final results/native-backoff-benefit-b1-final.json \
    --out results/native-backoff-benefit-b1-positions.json
uv run --frozen python -m media_rl.native_actuator_qualification_dynamics \
    --capture results/native-backoff-benefit-b1-block-1 [--capture ...] \
    --out results/native-backoff-benefit-b1-dynamics
```

The split has run on invented rows and on the mock dry run. The within-hold reader has run on
N1's capture.
