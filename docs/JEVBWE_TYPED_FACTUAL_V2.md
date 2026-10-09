# Typed-control factual supervision V2: does it carry to unseen families?

Status: **design written 2026-10-09, before the study ran.** Results are appended below the
design and do not change it. Development study, synthetic only. Both population panels it
scores on have already been read, so nothing here is confirmatory.

**Outcome: mixed, and at the smallest budget harmful.** Trained on 64 population families, the
factual pipeline is identified on one of the two unseen-family panels and not on the other. At
571 hours of randomised link time it gains +0.036 [+0.016, +0.057] on `pop_s` and +0.009
[-0.003, +0.020] on `pop_r`, about what the rollout-trained typed head gains there (+0.032 and
+0.012) and well short of a rollout-labelled control with a sixteenth of the data (+0.054 and
+0.026). At 36 hours it loses utility on every panel, -0.033 [-0.062, -0.005] on `pop_r`, and
the doubly-robust selection step that is meant to refuse such a policy approved it in all three
seeds.

## Why

V1 (`docs/JEVBWE_TYPED_FACTUAL_V1.md`) showed that a learner which sees one randomised option
per block can recover most of the rollout-supervised gain in distribution, at about sixty
times the link time. It tested nothing outside the 13 hand-written training families, and it
said so: "a factual learner has no reason to keep more" on unseen families than a
rollout-trained head does.

V4 (`docs/JEVBWE_TYPED_V4_POPULATION.md`) has since shown what rollout-trained heads keep when
the training families are draws from the test population: +0.012 and +0.032 for the typed head
on the two population panels, +0.024 and +0.056 for the regression head. A native learner
would have neither rollouts nor the luxury of training on the links it will meet. The
remaining question is the product of the two: **what does a factual learner trained on some
families of the population gain on other families of it?**

## Design

The V1 pipelines, unchanged (`src/media_rl/typed_bitrate_factual.py`), with two differences.

- **Training links.** The source run is V4, so the factual blocks are collected on fresh
  traces of the 64 development-pool families (`pop_d`), under V4's base ratio (1.05).
- **Scoring.** Besides the pool's own validation panel (in distribution, 64 families by 4
  traces), every head is run closed-loop on the traces of the two population panels, `pop_r`
  and `pop_s` (48 families by 16 traces each), which no fitting step draws from. The outcomes
  are paired with the frozen fixed-ratio outcomes of the V4 transfers there, and the frozen V4
  heads on the same traces are the reference. The code refuses a panel that is not a transfer
  of the same run to families outside its training set.

Budgets: 20,000, 80,000 and 320,000 blocks (36, 143 and 571 hours of link time), nested, three
seeds. The rollout-labelled control is trained on the first two. The largest V1 budget is
dropped: V1's curve was flat beyond 320,000 blocks. Margins are selected as in V1, by the
doubly-robust estimate on held-out factual blocks of the training links; nothing is selected
on a population panel.

## How the outcome will be read

Fixed before the run:

- **Identified on unseen families at a budget, per panel:** the factual pipeline's closed-loop
  gain over the fixed ratio has a family-level t interval that excludes zero on that panel.
  The two panels are reported side by side and are not pooled into a claim.
- **Price of factual supervision on unseen families:** factual pipeline minus rollout control,
  paired, at the two shared budgets.
- **Against what rollouts give:** the frozen V4 regression and typed heads on the same traces.
  They had about 205,000 rollout-labelled decisions and five rounds of on-policy aggregation;
  they are context, as in V1.
- A pipeline that selects "never act" scores exactly the fixed ratio and is reported as zero.

## What this can and cannot show

- Development evidence only. `pop_r` and `pop_s` have both been read, and this study was
  designed after their V4 results were known. A confirmatory version needs a newly registered
  panel.
- One pipeline, one optimiser setting; V1's caution about early stopping applies.
- The simulator's determinism, exact telemetry and exactly observed utility make the link time
  a floor for a real network, as in V1.
- Collection is under the base policy between blocks; no on-policy aggregation.
- Nothing here is a native result.

## Reproduce

```bash
make jevbwe-typed-factual-unseen TYPED=results/regen   # needs the V4 run and its two transfers
```

## Results

Run on 2026-10-09 from commit `791caf4` in 65 minutes: three seeds, about 327,000 factual
blocks each on fresh traces of the 64 `pop_d` families, rollout values on the first 82,000.
Checks: a factual block's outcome equals the rollout value of its option wherever both exist
(largest difference 0), and a head that never acts reproduces the frozen fixed-ratio outcomes
exactly on the validation panel and on both population panels.

### Closed-loop gain over the fixed ratio (family-level t intervals)

| Blocks | Link hours | Pipeline | Training families (`pop_d`, 64) | Unseen: `pop_r` (48) | Unseen: `pop_s` (48) |
|---:|---:|---|---|---|---|
| 20,000 | 36 | factual | -0.013 [-0.031, +0.004] | **-0.033 [-0.062, -0.005]** | -0.017 [-0.040, +0.007] |
| | | rollout control | +0.043 [+0.022, +0.064] | +0.026 [+0.010, +0.042] | +0.054 [+0.031, +0.078] |
| 80,000 | 143 | factual | +0.020 [+0.002, +0.037] | +0.004 [-0.011, +0.018] | +0.027 [+0.008, +0.046] |
| | | rollout control | +0.046 [+0.024, +0.068] | +0.024 [+0.006, +0.042] | +0.056 [+0.031, +0.082] |
| 320,000 | 571 | factual | +0.029 [+0.012, +0.046] | +0.009 [-0.003, +0.020] | +0.036 [+0.016, +0.057] |

References on the same traces, the frozen V4 heads (rollout labels, five aggregation rounds):
regression head +0.046, +0.024 and +0.056; typed head +0.029, +0.012 and +0.032.

Factual pipeline minus rollout control on identical rows: -0.056, -0.060 and -0.071 at 20,000
blocks; -0.026 [-0.034, -0.019], -0.020 [-0.028, -0.013] and -0.029 [-0.037, -0.020] at 80,000.
Every interval excludes zero.

The factual pipeline lowers the unsafe share against the fixed ratio at every budget and on
every panel (by 0.25 to 0.72 points). Its losses at the smallest budget are losses of utility,
not constraint violations.

### Reading, by the rules fixed in the design

- **Identified on one unseen panel, not on the other.** On `pop_s` the factual gain's interval
  excludes zero at 80,000 and 320,000 blocks. On `pop_r` it does not at any budget. The panels
  are not pooled into a claim; they disagree in the same direction as they did for the
  rollout-trained heads, where `pop_r` is the harder panel throughout.
- **Price on unseen families.** At 80,000 blocks the factual pipeline is 0.020 and 0.029 below
  the rollout control on the two panels.
- **Against what rollouts give.** At 571 hours the factual pipeline gains about what the
  rollout-trained typed head gains on each unseen panel, and about 40% and 65% of what the
  rollout-trained regression head gains.

### Observations made after the result

- **The safeguard failed where it was needed.** At 20,000 blocks the doubly-robust estimate
  on held-out factual blocks promised gains of +0.008 to +0.036 in the three seeds, each seed
  chose to act, and the deployed policies lost utility on every panel. V1's selection step
  declined to act in two of three seeds at its smallest budget; on the 64 population families
  it never did. The estimate takes the best of six margins on a few thousand blocks and scores
  states that the base policy visits, while the deployed head decides every second from states
  it has itself produced. A never-act fallback chosen this way is not a safety guarantee.
- **With more data the pipeline becomes cautious.** At 320,000 blocks every seed selects the
  largest margin and acts in 6% to 7% of states, where the rollout control acts in 14% to 24%.
- **Rollout supervision saturates early here too.** The control with 14,000 fitted states and
  no aggregation matches the frozen V4 regression head on both unseen panels.
- **In distribution the population is hard for both.** The factual pipeline reaches +0.029 of
  an oracle headroom of +0.087 at 571 hours; on the 13 hand-written families V1 reached +0.105
  of +0.248.

### What this means for the native route

Not results; consequences to weigh.

- A factual learner trained on some links can gain on others, in this simulator, after
  hundreds of hours of randomised link time, by an amount comparable to the best typed head
  and smaller than a regression trained on rollouts.
- Below that budget it can do harm, and the procedure that was supposed to detect this did
  not. A native learning phase would need a more conservative acceptance test than a
  doubly-robust point estimate: an interval, a held-out deployment check, or both.
- The two panels differ by more than the effect on either. Any native claim of the form
  "gains on unseen networks" needs enough independent networks to survive that.

Tracked summary: `results/typed-factual-v2-unseen/report.json` and `settings.json`.
