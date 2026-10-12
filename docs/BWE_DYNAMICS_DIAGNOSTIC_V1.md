# BWE dynamics from factual native summaries (development diagnostic)

This diagnostic was specified after the three native pilots were read. It uses
their committed BWE and requested-cap sequences to ask whether simple causal
predictors can describe the estimator's next observation. It does not test an
encoder model, action-value model or controller. The pilots are development data;
neither cross-validation nor a frozen fit creates new blind validation here.

The [failed margin forecast](NATIVE_MARGIN_PILOT_V1.md#results-2026-10-11) makes
estimator recovery and startup a concrete modelling question. Raw sender/encoder
histories are absent, but the compact summaries retain each hold's initial BWE and
cap. The target is the log change in BWE at the next actuation epoch. Inputs are
current BWE, the previous BWE change, the previous cap relative to its BWE, and
whether that previous observation exists. The nested cap-aware model adds the
current requested cap relative to current BWE. No schedule, capacity, source,
receiver label, actual encoder rate, future action or future duration enters a
predictor. The arrays are observed factual sequences; no counterfactual is created.

## Fixed before computing this diagnostic

`configs/bwe_dynamics_diagnostic_v1.json` pins the three input summaries, model
features, ridge penalty 0.01, partitions, metrics, weighting and limits.

- Baselines: persist current BWE; continue its previous log change; and a fitted
  pooled log drift. Compare them with state-only ridge and nested cap-aware ridge.
  Both ridge models use only training-fold normalization and one fixed penalty.
- Fit only on the 240 range-pilot sessions. Leave each source out in turn, and
  separately leave each entire authored network regime out. No tuning on these
  partitions, model selection or parameter sweep.
- Fit the same models once on all range sessions and describe prediction on the
  480 ladder and 192 margin sessions. All sources recur, all panels have been read,
  and the latter has a longer and sometimes shortened next-epoch horizon. This is
  a development extrapolation check, not unseen-source or real-network validation.
- Score equal source/regime/arm cells, equal sessions within a cell, and equal
  epochs within a session. Report absolute, squared and signed log errors; paired
  source-mean MAE differences with descriptive t intervals, conditional on the
  fits. Shared fitting data and overlapping CV folds preclude treating those
  intervals as independent training replication.
- Describe clipping of the nominal ratio into the requested cap for fixed arms,
  and how often consecutive nominal choices actually differ. Predictive cap
  information does not identify causal action value or delivered QoE.

This does not update the synthetic estimator or any native freeze. To repair the
simulator, actual sender reports and encoded payload trajectories must be checked
under a separate design, followed by new blind native evidence. No controller is
promoted and no calibration or safety claim is made.

## Results

The diagnostic ran under the fixed specification, with 1,200 factual range-pilot
transitions, 2,496 ladder transitions and 3,687 margin transitions. Source and
regime CV score the same 1,200 range observations twice; they are not additional
independent labels. `reports/bwe-dynamics-diagnostic-v1/` retains every fitted
model, the complete numerical features/targets/predictions, metrics, input/code
hashes and runtime versions. Independent reproduction is bit-exact for models,
predictions and the paper table, and gives an identical report.

Source-balanced mean absolute **log BWE prediction error** (smaller is better):

| Development partition | Persistence | Momentum | Pooled drift | State/history | State + current cap |
|---|---:|---:|---:|---:|---:|
| Range, leave source out | 0.371 | 0.610 | 0.382 | 0.275 | 0.270 |
| Range, leave regime out | 0.371 | 0.610 | 0.386 | 0.330 | 0.335 |
| Ladder, frozen range fit | 0.369 | 0.549 | 0.383 | 0.284 | 0.291 |
| Margin, frozen range fit | 0.161 | 0.244 | 0.239 | 0.181 | 0.181 |

These are errors predicting the next observed BWE, not quality gains. The
state/history model already sees previous requested cap; the nested model adds
only the present cap. That addition has no consistent benefit: cap-minus-state
MAE is −0.0056 on source CV, +0.0051 on regime CV, +0.0069 on ladder and −0.0006 on
margin. All four descriptive source intervals include zero. State/history beats
persistence on short sessions but loses on the long panel by +0.0208 absolute
log error [descriptive source interval +0.0111, +0.0305]. Persistence succeeds
when the estimate stays flat; blindly extending the previous log growth is the
worst comparator everywhere. A simple model fitted on short sessions therefore
does not justify repairing the simulator's long-session dynamics.

### Actual cap domain and action identifiability

The recorded requested cap agrees with the native actuator domain (150 to
4,000 kbit/s). A nominal ratio of 0.25 is clipped in **67.0%** of its range epochs,
**65.8%** of ladder epochs and **76.0%** of margin epochs. These percentages pool
reported epochs, unlike the source-balanced prediction metrics. Fixed 0.65 is
clipped in 0.0%, 0.17% and 0.83%, respectively. Clipping merges distinct nominal
ratios into the same requested action when the estimate is low; the command is
not the same thing as encoded payload.

Range sessions keep a nominal ratio throughout, so there are **zero nominal
changes in 1,200 consecutive pairs**. The ladder and margin have changes in 13.5%
and 3.55% of pairs. Whole-session randomized fixed levels can estimate a total
session-level effect, but the later epochs do not independently randomize a cap
given their endogenous estimator state. Predictive coefficients and good
one-step fits must not become native counterfactual labels or claims about
state-conditioned action value. In particular, adding the current cap cannot
identify what an unexecuted action would have done.

### Decision and remaining uncertainty

No predictor is selected for control or inserted into the simulator. The
diagnostic narrows the question to how native probing/recovery and the actual
encoder evolve under clipped caps, delayed feedback and longer histories.
Compact summaries omit actual encoded-payload sequences and timestamped sender
reports, and variable epoch duration further limits the transfer comparison.
Those missing factual histories are required before an encoder/estimator repair
can be qualified. All three pilots remain development data; any revised model
also needs new blinded native validation.

```sh
uv run --frozen python -m media_rl.bwe_dynamics_diagnostic \
    --spec configs/bwe_dynamics_diagnostic_v1.json \
    --out reports/bwe-dynamics-diagnostic-v1-reproduction
uv run --frozen pytest -q tests/test_bwe_dynamics_diagnostic.py
```
