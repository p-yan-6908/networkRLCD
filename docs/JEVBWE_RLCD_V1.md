# JevBWE-RLCD numeric V1; optional Laya benchmark

> **Superseded by [JevBWE typed decisions V2](JEVBWE_TYPED_V2.md).** The comparisons
> below use a fixed `0.85 x BWE` fallback over an estimator that grows without bound
> when the sender is below capacity. On ID tune traces a fixed 0.60 ratio scores 1.198
> under that estimator against 0.771 for 0.85, so "no gain over the fallback" was a
> comparison against an untuned baseline. Code and artifacts are kept unchanged.

> This pilot also scored a fixed event (`utility >= 1.0`) that barely depends on the
> action, on 432 factual cohorts (about 72 per option). Its failed qualification does
> not show that proper-score training cannot work here; V2 trains the same kind of
> head on 128,000 rollout-labelled decisions.

**Experimental, synthetic-only, unpromoted.** The supervised JevBWE controller and
checkpoint are the frozen baseline, not renamed RLCD. Legacy 42-action Double
DQN/native models, defaults and `media-rl` commands are unchanged. `jevbwe-rlcd`
is a separately registered command.

## Numeric policy

`src/media_rl/jevbwe_rlcd.py` implements a custom NumPy **RLCD-style probabilistic
forecaster/policy**, trained from scratch with Gaussian REINFORCE and strictly
proper scoring rewards. It is not pretrained Jev, Laya, Double DQN, or supervised
scalar QoE regression/ranking. This is delayed contextual-bandit training, not a
claim of long-horizon Bellman RL. The default head has **1,846 parameters**:
108 causal values/masks → 16 ReLU units → six event logits. Risk remains a separate,
frozen three-member ensemble.

The same `(0.60, 0.70, 0.80, 0.90, 1.00, 1.05)` BWE-relative actions are used.
Original `Sample`, `CausalHistory`, `JevBWE` hard-control logic and `SettledCredit`
are reused without editing their bytes: three seconds of ordered causal history,
nullable/freshness masks, distinct requested/actual/encoder-target telemetry,
QP/frame-size/deadline observations, immediate decreases, **1,800 ms increase
dwell**, owned acknowledgments, and target-settled/network-delayed reward credit.
FEC/media mode are fixed. Encoder/QP/output physics are hypothetical, not native
codec measurements.

## Honest probability semantics and factual-only proper rewards

**Architecture freeze / interpretation update:** `pi(a|s)` is an action-exposure
or policy distribution, **not** a calibrated probability that bitrate `a` is
"correct" or best. This experiment's `q[a]` forecasts the explicitly defined
binary utility-threshold event below; it does not estimate every counterfactual
`Q(s,a)`, and event calibration does not establish optimal-action calibration.
The separate risk model's `P(safe|s,a)` has its own calibration target.
Only factual outcomes are observed. The next research path is the
[causal actuator-identification study](NATIVE_ACTUATOR_IDENTIFICATION_V1.md),
not a larger policy or Laya run. Existing weights, architecture, six-action ABI
and promotion requirements are unchanged.


For predeclared settled utility event `Y = 1[U >= 1.0]`, six logits estimate
`q[a] = P(Y_a=1 | H, do(a))`. Before held-out temperature calibration,

```
pi[a] = q[a] / sum(q)
```

This is the arm distribution **conditional on success under a uniform six-arm
intervention**. It is NOT `P(a is optimal)`: a successful factual arm is not a
winner over unobserved arms. Event probability is a QoE surrogate; actual control
QoE, not surrogate skill, is the promotion endpoint.

Training uses only `(H, factual A, factual Y, known mu(A|H))`. With `lambda=0.5`,
`kappa=0.5`, each stochastic logit report receives

```
R = 1/(6*mu(A|H)) * (
    Y*log(q[A]) + (1-Y)*log(1-q[A])
    + lambda*Y*(log(pi[A]) + kappa*pi[A]/||pi||_2)
)
```

Binary log and categorical log/spherical scores are strictly proper. Under
conditional randomization and positivity, the expected binary term is maximized
at honest arm-event probabilities. The success-weighted categorical term is
maximized at the honest success-conditional arm law; these targets agree at true
`q`. Only the observed arm gets a Bernoulli outcome. On failure the other five
outcomes remain **unknown**, not negative. On success the categorical label is
the *actually sampled arm* in this conditional experiment, not an invented
optimal-action label. IPS changes the target exposure population; it does not
supply counterfactual outcomes. Stable log-space training has no arbitrary reward
floor or propensity clipping.

Eight Gaussian reports (`std=0.2`) per context are scored. REINFORCE uses
`(R - leave-one-out group mean) * noise/std^2`, with Adam on the numeric network.
Forecast noise is **distinct from physical arm exploration**. Replay/deployment
takes the MAP probability among risk-eligible actions, then applies unchanged
emergency/ceiling/dwell rules. The reported distribution is pre-projection, not a
post-gate execution propensity.

## Identification, calibration, and qualification

`src/media_rl/jevbwe_rlcd_experiment.py` collects **IID uniform** arms with
three-second holds. Full propensity vectors, chosen propensities, behavior ABI,
and assignment seeds independent of exogenous trace RNG are logged. The inspector
replays assignment sequences. Censored outcomes keep null rewards and never
become failures. Hashed namespaces separate:

- `train`: policy weights and feature normalization only;
- `calibration`: factual IPW monotone binary Platt calibration and success-
  conditional Choice temperature, no policy-weight updates;
- `qualification`: untouched changed/unaliased factual proper-score evaluation.

The old collector's **without-replacement permutations** are not IID conditional
on history: previously used arms have zero reassignment probability within a
block. Marginal `1/6` frequencies are not valid conditional propensities. Legacy
logs are not retrofitted with `1/6`, winners, or dense negative labels.
`train --data-run` accepts only matched factual ABI/known IID provenance;
unsupported logs save `data_support.json` and **no fitted model**. Arbitrary
native logs require a future matched telemetry/propensity adapter, not relabeling.

Arm-aware versus otherwise matched arm-blind calibrated Bernoulli forecasts must
show >=1% proper-log-loss skill for **utility and delivered-only** events overall
and in both episode-parity folds. Choice must also beat its uniform arm-blind
law on factual successful arms. All-arm counts, independent episodes and positive
episode-cluster gain intervals are required. Identification censoring blocks
qualification. Structural identifiability, demonstrated action skill, and actual
control superiority are separate checks.

The risk weights/calibration/normalization are copied unchanged from the baseline;
the old scalar QoE head is never called by the numeric controller. Existing risk,
spread, support, calibration-count and fresh-telemetry thresholds remain, with
additional factual policy-calibration support per action. Inference over the
100 ms default control budget forces fallback and cannot claim neural credit.
Aliases, clipping, holds and emergency projections retain original attribution
semantics.

## Frozen control panels and promotion

Validation/test seeds and scenario panels are bound before fitting; they cannot
be swapped afterward to cherry-pick a holdout. Identical exogenous traces compare:
`fallback_only` (0.85 BWE headroom, no neural eligibility), `supervised` (original
checkpoint), and `numeric_rlcd` (separate policy and unchanged gate).

When qualification fails, the inherited **unqualified BWE-reference branch** is
replayed, as in supervised JevBWE. Its difference from 0.85 fallback-only is not
an NN action effect. Actual neural execution counts are explicitly reported.

Eligibility requires:

1. Uncensored action-discrimination qualification.
2. Actual delivered QoE minus requested-cap switch cost beats fallback-only on
   **both** panels: >=8 independent paired seed clusters, positive cluster
   interval and one-sided sign-flip significance. Scenarios stay within seeds.
   Bonferroni `alpha/4` reserves two candidates × two panels even without Laya.
3. No hard-rate/dwell/inference violation and no seed/scenario regression in
   unsafe fraction or deadline misses.
4. >=24 complete genuinely changed learned cohorts, >=8 safety seed clusters,
   no selected-action censoring, and an exact one-sided **any-unsafe seed-cluster**
   upper bound <= the existing risk budget.

An all-zero small-sample bootstrap does NOT certify zero risk. Correlated cohorts
are not independent trials; additional seed clusters may be necessary for rare-
event safety. Randomized-hold calibration alone is not selected-live-policy
certification. Artifacts always retain `promoted=false`: even eligible simulation
evidence is not automatic native deployment. Existing evidence is never overwritten.
Baseline bytes, configs, source snapshots, raw logs and full hashes are sealed.

## Reproduce

Obtain a supervised baseline with the unchanged command if necessary:

```sh
uv run --frozen media-rl jevbwe-run \
  --config configs/jevbwe_smoke_v1.json --out results/my-supervised-jevbwe
uv run --frozen jevbwe-rlcd run \
  --config configs/jevbwe_rlcd_smoke_v1.json \
  --baseline-model results/my-supervised-jevbwe/training/model.json \
  --out results/my-rlcd-smoke
uv run --frozen jevbwe-rlcd audit --run results/my-rlcd-smoke
uv run --frozen benchmarks/jevbwe/verify_rlcd.py --run results/my-rlcd-smoke
```

`configs/jevbwe_rlcd_pilot_v1.json` freezes a 36/18/18-episode, 80-epoch study with
eight validation and eight test seeds. `train`, `evaluate`, `audit`, `laya` are
separate subcommands. The read-only verifier regenerates every factual sample/
cohort, independently refits four proper-score policies/calibrators, recomputes
qualification, and replays all control decisions using logged monotonic durations.

## Optional genuine Laya benchmark (not run by default)

`src/media_rl/jevbwe_laya.py` lazily loads inspected **laya==0.3.20** from an explicit
local checkpoint. No SDK/Torch import, checkpoint download, paid inference or GPU
launch occurs on the numeric/default path.

The same 108 values/masks, feature names/scales, history lags and six ratios become
a typed `choice` question with the same success-conditional target, not a best-
action label. Offline qualification adds twelve binary typed event forecasts
(utility/delivered-only for each arm); **only factual outcomes are scored**.
Online control asks one six-option Choice question. Pretrained weights are not
updated; only factual held-out calibration is fitted. Numeric actor outputs are
never substituted for Laya responses.

Typed exact-option probabilities are required. Malformed or zero-support answers
are rejected, not silently smoothed into evidence. An explicit 8,192-token budget
and tokenizer preflight prevent silent history truncation. Real duration, raw
typed control requests/responses, separate calibration artifacts and checkpoint
file hashes are retained. Test-stub/unverified backends cannot be eligible
pretrained evidence. The Hub revision is operator-claimed; local weight contents
are hashed, not falsely asserted verified against remote bytes.

Explicit optional setup (may download a large checkpoint/install Torch):

```sh
hf download convaiinnovations/laya \
  --revision 7b928d828b7b0e022f929d9bd2e44165aa270148 \
  --include 'config.json' 'rl_agent_config.json' 'encoder/*' 'tokenizer/*' 'model.safetensors' \
  --local-dir /tmp/laya-jevbwe-root
uv run --frozen --with laya==0.3.20 jevbwe-rlcd laya \
  --config configs/jevbwe_rlcd_pilot_v1.json \
  --training results/my-rlcd-pilot/training \
  --model-dir /tmp/laya-jevbwe-root --device cpu --out results/my-laya-benchmark
```

The same qualification, control, timing and safety gates apply. Contract tests
use an explicitly labeled **test stub**, not fabricated pretrained performance.
Genuine Laya inference remains unmeasured here. Checkpoint reference:
https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148

## Actual V1 findings (not tuned to force a pass)

Using unchanged `results/jevbwe-feedback-pilot-v1-verified/training/model.json`:

| Check | Pilot result |
|---|---:|
| Known IID randomization/positivity | yes |
| Factual train/calibration/qualification cohorts | 432 / 216 / 216 |
| Changed factual train commands | 427 / 432 |
| Identification censoring | zero |
| Utility-event log-loss skill vs arm-blind | **−3.2395%** |
| Delivered-only event log-loss skill vs arm-blind | **−7.9795%** |
| Choice log-loss skill vs uniform | **+0.3590%**, below 1% |
| Causal action-discrimination qualification | **failed** |
| Validation/test paired utility difference vs fallback-only | −0.39111 / −0.38354 |
| Genuine learned settled control cohorts | **zero (gate disabled)** |
| Hard rate/dwell/inference-overrun violations | zero |
| Promotion eligible / promoted | **false / false** |
| Genuine Laya checkpoint inference | **not run** |

The data supports *identification*, but this model/data combination does not
establish the required discrimination. Weak positive Choice skill is insufficient.
There is no learned-control gain; the disabled BWE-reference branch also loses
to conservative fallback. These are synthetic findings, not native codec/network
safety evidence.

Verification: **25 new tests**, 26 unchanged JevBWE tests, 24 adjacent learning/
legacy simulator/CLI-artifact regressions. Exact read-only pilot refit/replay checks
**864 cohorts, 25,920 fitting samples, 86,400 decisions, 27,360 six-action probability
rows and 512 artifact hashes**. Baseline controller/credit/experiment/CLI/networks/
checkpoint checksums remain unchanged. Generated local receipt:
`results/jobs/jevbwe-rlcd-pilot-v1-verified.json`.
