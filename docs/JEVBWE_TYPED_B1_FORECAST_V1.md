# Typed simulator: what it predicts Native Phase B1 will find (forecast V1)

**Synthetic. A forecast written down before any B1 data exist.** No model is trained or
evaluated, no controller acts, and nothing here is native evidence.

## Why

[Native Phase B1](NATIVE_PHASE_B1_BACKOFF_BENEFIT.md) is registered and has not been run. It
asks whether, on the native stack, backing off below the browser's estimate delivers more
on-time quality in holds flagged beforehand by a stalled estimate.

The synthetic track rests on the fluid simulator, and its
[headroom study](JEVBWE_TYPED_HEADROOM_V1.md) says that most of what the simulator offers a
controller lies in backing off. If the simulator is a usable guide to the native stack, it
should be able to say beforehand what B1 will find. Written down now, its answer makes B1 a
test of the simulator as well as of the premise. Written down afterwards it could not be one.

## Question

Under B1's protocol and B1's registered estimator, does the simulator show a benefit of
backing off in flagged holds? And how close does it come to what
[N1 already measured](NATIVE_PHASE_N1_EXPLORATORY.md)?

## Design, fixed before the run

- **Simulator:** the typed fluid simulator as built: its estimator whose growth is bounded by
  1.5 times the acked rate, its delayed encoder, its default quality and deadline terms, 100 ms
  steps. Nothing is tuned to N1.
- **Protocol:** a fresh sender and six 3 s holds. The arm is uniform and independent per hold.
  The request is the arm's ratio of the estimate frozen at the start of the hold, held for the
  whole hold and clipped to the application's range of 150 kbit/s to 4 Mbit/s. The synthetic
  governor (emergency cut, increase dwell) is not in the loop, because the native protocol has
  none.
- **Paths:** mirrors of the four native capacity schedules, each 6.0 s, 6.0 s and 6.6 s:

  | Schedule | Capacity in Mbit/s |
  |---|---|
  | underutilized | 4.0, 4.0, 4.0 |
  | near-capacity | 0.85, 0.85, 0.85 |
  | queue-building | 1.2, 0.6, 0.6 |
  | collapse-recovery | 1.2, 0.35, 1.2 |

  with the relay's 50 ms round trip and 30 kB (0.24 Mbit) queue, and no random loss or jitter.
- **Two descriptions of the actuator:**
  - *as built:* requests of 0.65, 0.85 and 1.05 of the estimate, which the simulated encoder
    follows, also above the estimate;
  - *N1-realised:* requests of 0.653, 0.813 and 0.917, which put the simulated encoder's mean
    output at the 0.588, 0.732 and 0.825 of the estimate that N1's encoder realised (the
    simulated encoder emits 0.90 of its target on average). Three N1 figures enter here by
    construction; nothing else is fitted.
- **Two panels per description:**
  - *exact:* all 729 arm sequences on each schedule's mirror, 2,916 sessions. This is the
    randomisation distribution itself, with no sampling error;
  - *sampled:* 48 replicates shaped like a native source, each with ten random senders per
    schedule, on mirrors with the path noise the simulator's own families draw (capacity scale
    0.85 to 1.15, base delay 35 to 65 ms, loss 0.2% to 1.2%, jitter of about 2 ms). Arm
    sequences and paths are the same for both descriptions.
- **Scoring:** B1's registered flag and estimator, imported from the frozen module (freeze
  `9b3ac6ca...`): a hold is flagged when its frozen estimate is below 1.05 times the previous
  hold's, and the benefit is the mean of the two lower arms minus the top arm among flagged
  holds.
- **Endpoint:** the simulator's delivered on-time quality term, log(1 + rate / 0.15 Mbit/s)
  times 0.82, times the share not lost, times the share inside the 150 ms deadline, averaged
  over 1.8 to 2.6 s of the hold. It stands in for B1's on-time PSNR proxy and is in different
  units, so only the sign and the relative size can be compared.
- **Quantities:** the primary benefit; B1's secondaries (each lower ratio, unflagged holds,
  flagged minus unflagged, the next hold, the on-time fraction, by the previous hold's ratio,
  by schedule) and the simulator's own QoE as endpoint; how often the flag marks a hold; and,
  for comparison with N1, the encoder's output over the frozen estimate and the estimate's
  growth to the next hold, by arm and schedule.

## Forecast class and reading, fixed before the run

Per description of the actuator, the forecast class comes from the sampled panel's 95%
interval over replicates:

| Class | When |
|---|---|
| helps | the interval is above zero |
| hurts | the interval is below zero |
| no clear benefit | the interval spans zero |

The exact panel has to agree in sign. If it does not, the forecast is reported as unstable.

When B1 has an outcome, it is read against each forecast as follows:

| B1 outcome | Forecast "helps" | Forecast "hurts" or "no clear benefit" |
|---|---|---|
| helps; helps, below the practical gate | agrees in sign | simulator misses the benefit |
| no practically relevant benefit | simulator overstates the benefit | agrees in sign |
| inconclusive | not assessed | not assessed |

If the two descriptions forecast differently, B1 says which description of the actuator is
closer. The comparison with N1's figures is a retrodiction, since those are known, and is
reported as one.

## What this cannot show

- The simulator has no content, no real encoder and a simplified estimator. Its quality term
  is a function of rate, not a PSNR.
- One agreement in sign would not validate the simulator. A disagreement would count against
  using it to design a native controller without changing it first.
- The forecast is of the simulator as built and of one correction to it. A different
  simulator could forecast differently.
- The flag marks different holds in the simulator and natively to the extent that the two
  estimators differ. The flag shares below show by how much.

## Command

```sh
make jevbwe-typed-b1-forecast   # about one minute
```

## Results

Not run at this commit. The design, the module and its tests are committed first.
