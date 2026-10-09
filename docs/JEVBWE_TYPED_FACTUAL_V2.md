# Typed-control factual supervision V2: does it carry to unseen families?

Status: **design written 2026-10-09, before the study ran.** Results are appended below the
design and do not change it. Development study, synthetic only. Both population panels it
scores on have already been read, so nothing here is confirmatory.

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

None yet. The study has not been run.
