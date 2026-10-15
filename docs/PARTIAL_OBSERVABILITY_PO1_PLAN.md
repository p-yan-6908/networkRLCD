# PO1: bounded observable-history information screen

## Registration and decision

Continue from d0b4467. IF1 failed practical build admission before any compiler
attempt; it did not test the scientific value of instrumented Chromium. IF1,
M5–M11R, all native freezes and untouched allocations remain unchanged. No closed
native telemetry is decoded for this study. M5's causal history evidence remains.

This is a new predictive question, not qualification of native stationary state
or a reopening of per-hold action value. The sender history is an information
set, not assumed sufficient state. Fit simple predictive models, never a policy
or controller. Do not transfer synthetic counterfactual labels to native data.

**Sequential economy rule:** first run the synthetic necessary-condition screen
below. Its preregistered conjunction must pass before spending a new native
panel. Failure closes PO1, preserves the fresh native reservation and prohibits
feature/model/threshold search or more complex models on these validation data.
A negative is bounded to this representation, baselines, simulator and families;
it cannot establish that all observable history is useless in native Chromium.
This rule deliberately allows a cheap negative without unnecessary native data.

`configs/partial_observability_po1.json` and the executable sources are sealed
in `data/partial-observability-po1/registration.json`, committed before generation.
All original episodes, including calibration failures or missing classes, count.
No tuning split, candidate search, recurrent model, retries or optional stopping.

## A. Synthetic evidence only

Reuse the unchanged fluid transport, delayed encoder and simplified AckedBwe
model in `typed_bitrate.py`. These are hypotheses, not Chromium/WebRTC or native
codec mechanisms. Reuse generator definitions with fresh SHA-256-namespaced
seeds. Do not claim the previously published generators are newly sourced network
measurements or independent simulator implementations.

Three separately fitted seed replications each contain:

| Role | Generator families | Independent episodes per family |
| --- | --- | ---: |
| Fitting | multi_step, multi_ramp, drift, loss_episode | 32 |
| Calibration only | dip, deep_queue | 24 |
| Validation, opened once after model lock | sawtooth, square_wave, slow_fade, feedback_flap | 24 |

Total 816 independent 36-second synthetic episodes, 4,896 decision rows. Family
functions, trace seeds and whole episodes are disjoint across roles. Every
decision and both branches from an episode stay in that episode's cluster.
Three seeds test fitting reproducibility; they are not three network campaigns.
Do not pool native observations into any synthetic model or uncertainty fit.

The factual collector runs previously frozen synthetic fixed1.05 with the
existing common governor (`configs/jevbwe_typed_v4_test.json`). Fixed0.65 remains
the native strong baseline and the synthetic action contrast reference/tail;
no native baseline is retuned. The uncommitted fixed0.65 logging draft is
preserved with its supersession reason: analytically, low cap × encoder output
can fall below the1/1.5 ACK growth bound and remove upward estimator excitation.
No new episodes/labels were generated or inspected before that design change.
At 4,9,14,19,24,29 seconds, freeze past-only features, then fork simulator state
for two offline action labels: hold0.65 for5s, versus hold1.05 for3s then0.65 for2s.
An additional factual branch holds the logging ratio1.05 for all5s.
Both use identical exogenous future trace and original governor/encoder state.
No oracle is exposed to the factual collector or a prediction input. Utility,
switch cost, safety and actuator dynamics retain their existing definitions.
Counterfactual branches are simulator labels, never native causal evidence.

### Single representation and strong baselines

Five causally observable channels: current BWE, delivered throughput, RTT,
previously requested cap and actual send rate. Rate channels use log2(rate/500k),
RTT uses200ms units. Store presence masks; invalid delivery/RTT remain missing,
not fabricated zeros. Zero is a numeric placeholder with a separate mask. No
capacity, hidden queue, future service, trace/source identity, QoE or internal
transport timing is an input. At each lag use the latest actually available
sample at/before the cutoff, at most150ms old; never interpolate with future data.

Baselines: current-BWE persistence; trailing3s mean; clipped constant-slope
forecast (future mean at2.55s; slope capped at±0.25 octave/s); train-only constant;
instantaneous linear regression; and **S1**, a strong fixed-history linear model
with current five values/masks, past3s channel means/slopes/missing fractions.
**H1** adds only ordered1/2/3s values/masks to S1. Same H1 representation is
reserved for native factual prediction. One fixed ridge penalty10, train-only
standardization, no hyperparameter selection, interactions or neural network.

Two regression heads: future5s mean log-BWE minus current log-BWE under the
factual1.05 continuation, and synthetic utility advantage of1.05 over0.65.
Three fixed L2 logistic heads: factual future-BWE drop≥0.5octave, synthetic
advantage>0.02, and synthetic1.05 unsafe fraction>0.10. Fit a binary head only
with positive and negative examples in≥20 fitting episodes and≥10 calibration
episodes per class; otherwise record unestimable and fail admission. S1, H1,
instantaneous and constant models all use the same target definitions.

### Frozen uncertainty and acceptance

Train on fitting families only; calibrate one logistic intercept per head on the
separate calibration families. For each regression, calibration scores are the
maximum absolute residual across all six decisions of an episode. Use the
ceil(0.9(n+1))-th score for nominal90% sequence intervals; infinity if the rank
exceeds n. This is an empirical transport check across families, **not** an OOD
conformal or safety guarantee. Report interval scores and widths as well as
coverage; arbitrarily wide intervals cannot pass. Lock every model, calibrator,
class-count check and interval radius to checksums before decoding validation.

The necessary gate is a conjunction, separately for each of four validation
families; no pooled mean can rescue a failed family:

1. H1 improves factual and advantage MAE by≥5% relative to **every applicable**
   baseline. Each replication's point improvement must be positive. A paired
   episode bootstrap (10,000, equal replication weights, resampling episodes
   within replication) must have one-sided95% lower improvement>0. This is an
   intersection-union screen; family-specific intervals are not simultaneous
   claims over a wider network population.
2. Both H1 sequence intervals cover≥80% of validation episodes in each family,
   ≥75% within each replication. Full width≤1octave for BWE and≤0.50 utility
   units for advantage, in every replication. Report row coverage too.
3. All three binary H1 heads have five-bin ECE≤0.10, with Brier loss no worse
   than the calibrated constant head within each family. Report event counts,
   log loss and calibration-bin counts, including empty bins, and worst-family
   results. Lack of events is not proof of calibration.
4. An **offline assertion**, not an executed action, requires advantage interval
   lower bound>0.02, benefit probability≥0.90 and unsafe probability≤0.10. Each
   family needs assertions in≥30 distinct episodes across three replications.
   Count an episode erroneous if **any** asserted decision has nonbenefit or
   unsafe fraction>0.10. One-sided95% Wilson upper error bound must be≤0.10.
   No assertions means insufficient supported discrimination, not perfect safety.

Report all original rows, per-family/per-replication metrics, all baseline
comparisons, calibration failures and safety assertions. No test-derived model
selection or model-level execution of learned actions. Hash raw shards before
loading them for analysis, verify disjoint source/episode inventories and causal
cutoffs, then preserve models, raw labels, scores, provenance and negative gates.

Sample size is a bounded falsification screen:72 validation episodes/family,
three independent fits, six correlated decisions/episode. It can detect gross
failure and bound rare assertion error only if enough episodes qualify. It is
not a precision study of small benefits. An inconclusive gate also stops.

## B. Fresh native factual panel, only if A passes in full

The committed reservation contains64 new native session IDs and disjoint roles:
NordicDat5G-NSA fitting, RomeLTE calibration, IrishLTE and Murcia5G validation;
four existing licensed measured profiles/family, two independent content source
groups/role, two fresh process repeats/context. Do not acquire from any old
session or open any old allocation. The content split is cicada/Vižanice,
Schmilka/D3 tutorial, penguins/waterfall. All prior sources are reused apparatus,
not new independent replication of an earlier result. Repeats/content crosses
do not multiply the number of independent measured-source traces or campaigns.
Retain source-member/run clustering and campaign-level heterogeneity.

Only if A qualifies, separately finalize and commit a full acquisition protocol
before any native capture. It must use the exact H1/S1 representation, future
factual BWE/drop targets, and fixed4Mbps support cap regime, without randomized
actions or receiver QoE. No synthetic regression coefficients are transferred.
Prediction is conditional on this factual logging regime, not a policy effect.
Use the existing18-second measured profiles without scaling, three6-second
phases, and past-only decisions at4,9,13 seconds with a5-second future target.
Retain fresh TURN/TCP preflight, unchanged managed policy, exact1200kbps startup
within100ms, fixed cap/jitter readback,25ms sampling, gaps≤250ms, replay tick
lateness≤150ms, sender-to-relay clock uncertainty≤50ms including first phase,
and exact cleanup≤2000ms. Prove receipt≤decision for all feature records; offline
full-session clock fits cannot create online features. No actual TCC-age or
pacer counter is assumed observable. All originals are required; no retry.

The native acquisition/analysis code and a cluster-aware uncertainty protocol
must be registered separately before this reservation is instantiated. Its
calibration/coverage precision must reflect only four profile clusters/family;
it cannot inherit the synthetic episode-level confidence guarantees. No result
of A can waive native technical, calibration or factual prediction gates.

Native labels contain only subsequent **observed** BWE sequences under the
factual regime. No action-difference label, branch, utility oracle or causal
action recommendation. Receiver frames/QoE stay closed. Failure of A leaves
this reservation completely untouched and supplies no native predictive result.

## Subsequent decision

If A or a later independently registered native factual screen fails, stop this
representation/model route, preserve the negative, and reassess the experimental
question without escalating complexity. If both qualify, define a **separate**
safe-policy protocol: episode-boundary assignment, strong frozen fixed0.65
baseline, supported-advantage gating, otherwise fallback, calibrated uncertainty,
campaign-specific risk bounds and fresh untouched episodes. Native factual
prediction alone still does not identify a native counterfactual advantage; that
protocol must justify its causal identification independently before capture.

Raw data stay under `~/.cache/networkrlcd/partial-observability-po1`,≤50MB;
raw+archive+fresh verification≤150MB. Archive privately with every object and
member size/SHA verified at an immutable HF revision. Retain all local evidence.
