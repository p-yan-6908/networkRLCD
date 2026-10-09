# Per-link crossover identification V1: which ratio is better on this link?

Status: **design written 2026-10-09, before the study ran.** Results are appended below the
design and do not change it. Development study on the development pool of the family
population, synthetic only. It builds no controller and touches no sealed panel.

**Outcome: negative.** Within-session crossover does not identify the per-link ratio effect in
this simulator. With blocks of 3 to 9 s the crossover contrast is unrelated to the difference
between constant ratios, or opposed to it (slopes from -0.95 to +0.53 where 1 is correct). With
18 s blocks, one half-session per ratio, the bias mostly goes and the variance comes back: the
only two designs that meet the usability rule need over 1,000 sessions per link, more than
randomising whole sessions (437 per ratio for the primary pair). On identical traces 16 would
do. No design tested is both unbiased and cheaper than whole-session randomisation.

## Why

Three results point here.

- On the population, a constant ratio chosen per family in hindsight gains +0.030 over the
  fixed 1.05 on the replication panel: 28% of the hindsight oracle's headroom, and more than
  either trained head keeps on families it has not seen (+0.019 for V3, +0.012 for V4, on the
  same panel). Much of what a controller can gain on an unseen link is knowing which constant
  suits that link.
- A real network recurs. A sender meets the same access link session after session, and it can
  learn about that link from its own outcomes without any offline training.
- Factual supervision of a population-level head costs hundreds of hours
  (`docs/JEVBWE_TYPED_FACTUAL_V1.md`), because one option runs per decision and futures are not
  shared. The same problem appears per link: sessions on one link differ far more than the
  ratios do.

A feasibility probe on 32 development-pool families (12 sessions each, fixed ratios only, run
before this design was written) put numbers on the last point. Between sessions on one link the
utility at a fixed ratio has a standard deviation of 0.155, while the effect of moving from 1.05
to 1.00 has a median size of 0.013. Comparing sessions run at one ratio with sessions run at
another would need a median of about 250 sessions per ratio to place the per-link effect two
standard errors from zero. On identical traces, which only a simulator has, 12 would do.

A crossover session is the classical way to get between those two numbers: alternate blocks of
the two ratios within one session, in a random order, and compare within the session. Whether
it works here is not obvious. The estimator and the encoder carry state from one block into
the next, so the crossover contrast need not equal the difference between running each ratio
throughout.

## Question

On one link, from factual outcomes only: does a crossover session estimate the difference
between running ratio B throughout and running ratio A throughout, and how many sessions does a
link need before that difference stands clear of zero?

## Design

`src/media_rl/typed_bitrate_crossover.py`. Network, estimator, governor and options are those
of the V4 run, whose 64 training families (the development pool `pop_d`) are the links. Each
link gets 32 sessions of 36 s on fresh traces.

**Yardstick (simulator only).** Every session's trace is run at each constant ratio. The true
effect of a pair on a link is the mean over its sessions of the difference on identical traces.

**Crossover sessions (factual).** Blocks alternate between A and B; which ratio runs first is
drawn per session. The estimate is the mean utility of the measured B steps minus that of the
measured A steps, where the first part of every block (the washout) is left out. Switch costs
fall inside the washout or the measured part as they occur; nothing is corrected by hand.

| Factor | Levels |
|---|---|
| Pair (A, B) | (1.05, 1.00), (1.00, 0.90), (0.90, 0.80), (1.05, 0.80) |
| Block length | 3, 6, 9, 18 s |
| Washout | 0, 1, 2 s |

The first pair is the primary one: the base ratio and its lower neighbour, the first step of
any per-link search and the pair with the smallest effects.

## How the outcome will be read

Fixed before the run:

- **Usable design.** Across the 64 links, regress the per-link mean crossover estimate on the
  true effect. A design is usable for a pair if the slope lies in [0.8, 1.2] and the intercept
  within 0.005 of zero. Outside that, the crossover contrast is measuring something other than
  the constant-ratio difference, and a controller built on it would be steering by a biased
  signal.
- **Sessions needed.** For links whose true effect is at least 0.01 in size, the number of
  sessions at which the per-link effect is two standard errors of the crossover estimate from
  zero; the median over links. Reported beside the same number for whole sessions at one ratio
  and for identical traces.
- **Cost of experimenting.** The session utility of a crossover minus that of staying at A.
- Sign agreement on links whose true effect is at least 0.02 in size, and the correlation.

No design is selected for a later claim on the strength of this study alone. If a usable
design exists, a per-link controller built on it is a separate experiment with its own
registration and its own untouched links.

## What this can and cannot show

- It measures identification, not control. Nothing here shows a per-link controller's gain.
- A session is 36 s. Real sessions are longer, which allows longer blocks and more of them;
  the block lengths here are bounded by the episode.
- The simulator is deterministic given the trace and observes utility exactly. On a real
  network utility is itself estimated, and a link changes over hours and days.
- The yardstick exists only in simulation. A native study could run a crossover but could not
  check it this way, which is the reason to check it here first.
- Synthetic only; nothing here is a native result.

## Reproduce

```bash
make jevbwe-typed-crossover TYPED=results/regen   # needs the V4 run under results/regen
```

## Results

Run on 2026-10-09 from commit `e951156`: 64 links, 32 sessions each, 48 pair-by-design
combinations. Between sessions on one link the utility at a fixed ratio has a median standard
deviation of 0.171.

### What each pair looks like on identical traces (the yardstick)

| Pair (A to B) | Mean true effect | Spread over links | Links with an effect of at least 0.01 | Sessions needed, identical traces | Sessions needed per ratio, whole sessions |
|---|---:|---:|---:|---:|---:|
| 1.05 to 1.00 (primary) | +0.003 | 0.025 | 39 | 16 | 437 |
| 1.00 to 0.90 | -0.019 | 0.043 | 41 | 8 | 189 |
| 0.90 to 0.80 | -0.059 | 0.065 | 50 | 2 | 50 |
| 1.05 to 0.80 | -0.076 | 0.107 | 55 | 2 | 48 |

"Sessions needed" is the median, over links with an effect of at least 0.01, of the number of
sessions at which the per-link effect is two standard errors from zero. At 36 s a session, 437
sessions per ratio is 4.4 hours of link time per ratio.

### Crossover designs (washout 1 s; the other washouts differ little)

Slope and intercept of the per-link crossover estimate regressed on the true effect, and their
correlation. A usable design has a slope in [0.8, 1.2] and an intercept within 0.005 of zero.

| Pair | Block | Slope | Intercept | Correlation | Sessions needed | Usable |
|---|---:|---:|---:|---:|---:|---|
| 1.05 to 1.00 | 3 s | -0.48 | -0.020 | -0.16 | 236 | no |
| | 6 s | -0.91 | -0.011 | -0.24 | 495 | no |
| | 9 s | +0.49 | -0.007 | +0.14 | 835 | no |
| | 18 s | +0.86 | +0.001 | +0.24 | 1,031 | yes |
| 1.00 to 0.90 | 3 s | +0.17 | +0.010 | +0.09 | 155 | no |
| | 6 s | +0.20 | -0.014 | +0.15 | 303 | no |
| | 9 s | +0.04 | -0.007 | +0.02 | 413 | no |
| | 18 s | +1.23 | -0.010 | +0.43 | 509 | no |
| 0.90 to 0.80 | 3 s | +0.01 | -0.015 | +0.01 | 12 | no |
| | 6 s | -0.02 | -0.010 | -0.02 | 34 | no |
| | 9 s | -0.12 | -0.040 | -0.07 | 37 | no |
| | 18 s | +0.18 | -0.020 | +0.14 | 126 | no |
| 1.05 to 0.80 | 3 s | +0.06 | +0.009 | +0.08 | 22 | no |
| | 6 s | +0.13 | +0.012 | +0.17 | 48 | no |
| | 9 s | +0.03 | -0.016 | +0.04 | 62 | no |
| | 18 s | +0.83 | -0.015 | +0.60 | 94 | no |

Of the 48 combinations, two meet the rule: the primary pair with 18 s blocks and a washout of
1 s (slope 0.86) or 2 s (slope 1.04). They need 1,031 and 1,238 sessions.

### Reading, by the rules fixed in the design

- **Short blocks measure the wrong thing.** With blocks of 3 to 9 s the slope ranges from -0.95
  to +0.53 across pairs and washouts, and the correlation from -0.24 to +0.28. For 0.90 to 0.80,
  where the lower ratio costs 0.059 on average, 3 s crossovers report a cost near 0.01. The
  estimator and the encoder carry the other ratio's state across the block boundary, and a
  washout of up to 2 s does not remove it. The low session counts in those rows are the danger
  the usability rule exists for: a precise estimate of a different quantity.
- **Half-session blocks trade the bias for the variance.** At 18 s the slope is 0.74 to 1.28
  for three pairs and the sign agrees on 68% to 94% of links with a large effect, but the
  intercept is off by 0.010 to 0.020 for three pairs, and for 0.90 to 0.80 the slope is still
  0.10 to 0.26. The two halves of a 36 s session differ more than two sessions do, because
  every session starts cold and its trace is not stationary.
- **No design is both usable and cheaper.** The two usable designs need 1,031 and 1,238
  sessions on a link. Whole sessions at one ratio need 437 per ratio, 874 for the pair. Their
  correlations with the truth are 0.24 and 0.30 over 64 links, so their slopes are loosely
  determined; "usable" here means only that the rule is met.
- **Experimenting is not free.** Crossing over between 0.90 and 0.80 in 3 s blocks costs 0.039
  of utility per session against staying at 0.90; for the primary pair the cost is under 0.01.

### What this means

Not results; consequences to weigh.

- The per-family constant that would gain +0.030 on the population is not cheap to find from
  factual outcomes either. For adjacent ratios a link needs on the order of 200 to 450
  sessions per ratio with whole-session randomisation, hours of link time for one comparison.
- A native experiment that alternates BWE-relative caps within a call and compares quality
  between the blocks would produce a tight interval around the wrong number. Any such design
  needs its carryover checked first, and this simulator is one place to check it.
- This does not bear on Phase N1. N1's endpoint is the encoder's response to a command, where
  carryover is the object of study and not a nuisance.

Limits specific to this study: sessions are 36 s and start cold, and the population defines
its time scales relative to the session, so sessions of several minutes with a warm estimator
were not tested and may behave differently; 64 links; one utility; simulator only.

Tracked summary: `results/typed-crossover-v1/report.json` and `settings.json`.
