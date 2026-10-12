# Conservative acceptance for factual supervision (synthetic development)

Native archive and desktop access remain unavailable, and the cloud browser's
managed policy disables non-proxied UDP. This study advances the independent
synthetic track while those access paths are being restored. It generates no
native outcomes and changes no frozen controller, model or simulator.

The factual V2 pipeline approved three low-data policies that then lost utility
on unseen-family panels. It maximizes six noisy doubly robust point estimates on
held-out randomized blocks, then deploys the head continuously on states it
creates. This study separates a tractable uncertainty: can multiplicity-aware,
clustered lower bounds reject false approvals while retaining useful higher-data
policies? It cannot fix an off-policy estimand or certify safety by statistics.

## Design fixed before this run

`configs/typed_factual_acceptance_v1.json` pins the original V4 configuration and
the 204-rule training-family baseline audit. Fit the original factual regression
helper unchanged on 20,000 and 80,000 blocks, nested, with three fresh data/optimizer
seeds (501–503). One uniformly randomized executed option per block supplies the
only outcome label. Counterfactual values are not computed or read. Keep the
original fit/early-stopping/selection split by complete episode and optimizer
defaults. No new hyperparameters are chosen from evaluation panels.

Compare three acting-margin selectors on the same fitted head and selection rows:

- Original maximum positive doubly robust point estimate over six fixed margins.
- Maximum strictly positive lower bound, clustering block residual scores by
  episode and applying a one-sided Student t bound at alpha/6 for the six margins.
- The same bound clustered by training-family identity.

Cluster standard errors use the summed centered DR contributions within each
cluster. A bound at or below zero selects the existing never-act fallback.
Those are approximate conditional bounds, not finite-sample safety guarantees.
The family clustering view shares fitted-family contexts and does not create
new unseen-family calibration.

Evaluate all selectors once, closed loop with hindsight disabled, on four fresh
trace seeds of the 64 training families and the two already-read 48-family
population panels. The latter remain development evidence on unseen fitting
families, not fresh blind panels. Comparators are the original training-selected
fixed ratio and the best reactive rule of the pinned training-only grid; both use
the same options, governor and paired traces. Report utility, unsafe share, every
selected margin and estimated bound, source/model seed variation, and family-level
paired intervals conditional on those fits. A never-act selector must exactly
reproduce fixed control.

Interpretation: less noise-induced acceptance is useful only with transparent
rejection rates and higher-budget effects. A selector that declines everything
demonstrates no controller gain. Positive block-value bounds need not imply
positive continuous closed-loop value, because deployment changes state occupancy,
action sequences, commit timing and guarding. Nothing is promoted by this study.

## Results

Pending this run. Prior family panels and factual-study outcomes were already read.
