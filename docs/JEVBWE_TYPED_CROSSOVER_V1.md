# Per-link crossover identification V1: which ratio is better on this link?

Status: **design written 2026-10-09, before the study ran.** Results are appended below the
design and do not change it. Development study on the development pool of the family
population, synthetic only. It builds no controller and touches no sealed panel.

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

None yet. The study has not been run.
