# Conservative acceptance for factual supervision (synthetic development)

This study was specified while native archive and desktop access were unavailable
and the cloud browser's managed policy disabled non-proxied UDP. The subsequent
[TURN/TCP probe](NATIVE_TURN_PROBE_V1.md) supplies separate fresh native development
telemetry. This synthetic study generates no native outcomes and changes no frozen
controller, model or simulator.

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

Completed on three fresh data/optimizer seeds, with four fresh trace seeds per
family. The original point selector accepted all six fits. The episode and family
lower-bound selectors each rejected all six, at both budgets. Their packaged heads
always answer with the fixed 1.05 base: a post-run ReLU interval bound proves this
on every finite clipped input, supplementing executed sample parity. No nonzero
gain follows from those selectors.

For the original point selector, utility differences against fixed 1.05 are:

| Blocks | Panel | Mean gain | Family-level 95% interval |
| --- | --- | ---: | ---: |
| 20k | 64 training families | −0.01049 | [−0.02761, +0.00662] |
| 20k | 48 read unseen R families | −0.03888 | [−0.07887, +0.00111] |
| 20k | 48 read unseen S families | −0.02731 | [−0.05271, −0.00192] |
| 80k | 64 training families | +0.01798 | [+0.00255, +0.03340] |
| 80k | 48 read unseen R families | +0.00203 | [−0.01792, +0.02198] |
| 80k | 48 read unseen S families | +0.01584 | [−0.00493, +0.03660] |

All three low-budget seed means are negative on each unseen panel. At 80k, two of
three means remain negative on R. Unsafe share falls for the point selector on
every panel/budget, so lower constraint violations do not establish improved
utility. Comparisons to the fixed training-selected best of 204 reactive rules
are similar; every paired result, seed mean and selection curve is retained in
`reports/typed-factual-acceptance-v1/report.json`. The conditional family intervals
are descriptive and unadjusted across these evaluation contrasts, and do not
cover uncertainty over retraining or establish an unseen-population guarantee.

This reproduces the low-data false-approval concern. The conservative selectors
prevent those departures in this study but also discard the positive higher-data
training-family result. Declining every policy does not demonstrate an effective
learned controller or calibrate selected actions. We do not lower the thresholds
using these read outcomes. A useful next test needs to match the block-selection
estimand to continuous closed-loop deployment before increasing model complexity.

`tools/verify_typed_factual_acceptance.py` independently refits all six heads from
the saved executed-label files, reproduces all eighteen packaged models/selections
under the declared numerical comparator, and recomputes all eighteen summaries
from saved closed-loop arrays. It does not rerun those traces. The original
counterfactual-free labels remain externally at
`/workspace/.cache/networkrlcd/working/typed-factual-acceptance-v1`; they are not a
verified archive and are not pruned. Reproduce to fresh paths:

```sh
uv run --frozen python -m media_rl.typed_factual_acceptance \
  --spec configs/typed_factual_acceptance_v1.json \
  --raw-out /external/fresh-acceptance-raw --report-out reports/fresh-acceptance
uv run --frozen python tools/verify_typed_factual_acceptance.py \
  --report reports/typed-factual-acceptance-v1 --out /external/fresh-verification.json
```
