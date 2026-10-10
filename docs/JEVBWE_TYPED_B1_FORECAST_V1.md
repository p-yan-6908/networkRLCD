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

Run once on 2026-10-10, 38 s, at commit `b5bccb5` (design, module and tests, committed before
the run), with B1's freeze `9b3ac6ca...` verified and no B1 data in existence. Output:
`results/typed-b1-forecast-v1/report.json`. Brackets are 95% intervals over the 48 replicates
of the sampled panel. Units are those of the simulator's on-time quality term.

### The forecast

| Description of the actuator | Exact panel | Sampled panel | Relative to the top arm | Class |
|---|---:|---|---:|---|
| As built (0.65 / 0.85 / 1.05) | -0.123 | -0.114 [-0.134, -0.094] | -13% | **hurts** |
| N1-realised (0.653 / 0.813 / 0.917) | -0.108 | -0.107 [-0.116, -0.098] | -12% | **hurts** |

Under both descriptions the simulator forecasts that backing off lowers the on-time quality
term in flagged holds, by about an eighth of the top arm's level. The exact panels agree in
sign, so neither forecast is unstable.

### Secondary contrasts

Sampled panel. The exact panel gives the same sign for every contrast whose interval here
excludes zero.

| Contrast | As built | N1-realised |
|---|---|---|
| 0.65 minus 1.05, flagged holds | -0.166 [-0.187, -0.146] | -0.157 [-0.167, -0.147] |
| 0.85 minus 1.05, flagged holds | -0.061 [-0.083, -0.039] | -0.056 [-0.066, -0.046] |
| Benefit in unflagged holds | -0.112 [-0.128, -0.095] | -0.117 [-0.125, -0.108] |
| Flagged minus unflagged | -0.002 [-0.031, +0.026] | +0.010 [-0.003, +0.022] |
| Same contrast on the next hold | -0.067 [-0.087, -0.048] | -0.076 [-0.088, -0.063] |
| Immediate plus next hold | -0.181 [-0.215, -0.147] | -0.183 [-0.202, -0.164] |
| On-time fraction as endpoint | +0.042 [+0.030, +0.054] | +0.008 [+0.003, +0.014] |
| Simulator's own QoE as endpoint | +0.039 [-0.020, +0.097] | -0.078 [-0.101, -0.055] |
| Flagged holds after a lower ratio | -0.125 [-0.145, -0.106] | -0.109 [-0.117, -0.101] |
| Flagged holds after the top ratio | exact -0.028; one replicate evaluable | exact 0.000; none evaluable |
| underutilized | -0.188 [-0.218, -0.158] | -0.113 [-0.129, -0.098] |
| near-capacity | -0.171 [-0.203, -0.140] | -0.123 [-0.141, -0.105] |
| queue-building | -0.097 [-0.133, -0.061] | -0.100 [-0.117, -0.082] |
| collapse-recovery | -0.008 [-0.052, +0.036] | -0.069 [-0.093, -0.046] |

- **The flag separates nothing in the simulator.** Backing off costs about the same in
  flagged and unflagged holds; flagged minus unflagged is zero within its interval.
- **Backing off buys a little timeliness and loses more rate.** The on-time fraction is
  slightly higher at the lower ratios, and the on-time quality term is lower.
- **The cost carries into the next hold.**
- **On the simulator's own QoE**, which also charges for latency and loss, the contrast in
  flagged holds is about zero as built and negative at N1's levels. This is why the forecast
  does not contradict the headroom study: a hindsight oracle picks its moments on that QoE,
  with the governor in the loop and on other families. This flag does not find those moments.

### The simulator beside N1 (retrodiction: these native figures were known)

Arms are 0.65 / 0.85 / 1.05. Simulator figures are from the exact panel.

| Quantity | As built | N1-realised | Native (N1) |
|---|---|---|---|
| Encoder over the frozen estimate | 0.603 / 0.777 / 0.954 | 0.597 / 0.740 / 0.833 | 0.588 / 0.732 / 0.825 |
| Estimate growth per hold, unconstrained schedule | 0% / 19% / 47% | 0% / 14% / 28% | 18% / 24% / 100% |
| Log growth, four schedules equally weighted | +0.007 / +0.114 / +0.218 | +0.006 / +0.123 / +0.212 | +0.123 / +0.128 / +0.310 |
| Holds flagged | 37% | 41% | 34% |
| Holds flagged, by schedule | 33% to 41% | 40% to 42% | about 18% unconstrained, 34% to 42% constrained |
| Flagged after each arm | 96% / 4% / 10% | 98% / 21% / 3% | 51% / 23% / 28% |

- **In the simulator the flag is close to a restatement of the previous request.** After a
  request of 0.65 nearly every hold is flagged, because the simulated estimator cannot grow
  while the acked rate stays below two thirds of it. Natively the estimate still grew by 18%
  per hold at 0.65, and only half of those holds were flagged.
- **The simulated estimator grows too slowly when the link has room,** at every arm.
- **The overall flagged share is similar (37% against 34%) for different reasons.** In the
  simulator it barely depends on the schedule; natively it is twice as high under the
  constrained schedules.
- **As built, the simulated top arm sends at 0.95 of the estimate** against 0.83 natively.
  The N1-realised description removes that by construction and the forecast does not change.

### A check made after the run

Not part of the design. When the estimate is low, a request below 150 kbit/s is raised to the
application minimum, which pulls the arms together. In the exact panel the lowest arm is
raised in 14.5% of flagged holds as built and 2.9% at N1's levels, and all three arms coincide
in 0% and 2.8% of flagged holds. The 129 flagged holds that follow the top ratio at N1's
levels are all of that kind, which is why that contrast is exactly zero. The effect shrinks the
forecast contrasts slightly and does not change a sign.

## Reading

- **Forecast.** The simulator predicts that B1 will not find a benefit of backing off in
  flagged holds, and that it would find a cost if its endpoint behaved like the simulator's
  on-time quality term. By the rule above: if B1's outcome is "no practically relevant
  benefit", the simulator agrees in sign; if it is "helps" or "helps, below the practical
  gate", the simulator misses a benefit that exists natively; if it is inconclusive, nothing is
  assessed. Both descriptions of the actuator forecast the same class, so B1 cannot tell them
  apart.
- **Against the pilot.** In N1's exploratory second pass the point estimates in flagged holds
  leaned toward backing off, without being established. The simulator leans the other way.
  Neither is evidence about the native stack. B1 is the test.
- **What is already settled without B1.** The retrodiction uses known native figures, and it
  shows that this simulator produces the flag differently from the browser. A controller for
  the native stack should not be designed around this flag in this simulator until the
  simulated estimator's coupling to the send rate is changed, and any such change is a new
  simulator whose earlier results do not carry over.
- **Nothing is promoted and nothing about the native stack is claimed.**
