# Synthetic Typed-Control V2 (JevBWE typed decisions)

**Synthetic only. Not a native WebRTC result, not a safety certificate.** This is a separate
track from the native actuator study. It does not touch, rewrite or supersede the native
controller freeze (`configs/native_controller_freeze_v1.json`), and it does not answer the
native identifiability problem: its training labels are hindsight rollouts in a forked
simulator, which a real network cannot provide.

A small head answers one typed question per second: which of six BWE-relative bitrate
ratios is best over the next few seconds. It reports a probability for every option in a
single forward pass, is trained on strictly proper scoring rules, and the controller acts on
those probabilities. Among the synthetic JevBWE pilots it replaces the
[supervised residual](JEVBWE_RESIDUAL_V1.md) and the [factual-bandit RLCD](JEVBWE_RLCD_V1.md),
whose code and results are kept. The follow-up with a broadened training distribution and an
untouched test set is [Typed-Control V3](JEVBWE_TYPED_V3_BROAD.md).

**Conclusion.** Simulator counterfactual rollout supervision lets a small probabilistic
bitrate policy outperform fixed-ratio control in distribution. On seven held-out families
its mean gain over the train-selected fixed ratio is positive but is not established once
families, not seeds, are the unit of analysis. Generalisation and calibration degrade on
unseen network families. RLCD-style training shows no clear advantage over exact-gradient or
regression baselines. No native-network gain has been demonstrated.

**Result on the frozen test panel** (5 model seeds x 24 trace seeds x 11 families; audited
2026-10-07, see [Audit of the frozen panel](#audit-of-the-frozen-panel)):

- **In distribution (4 families) the head beats every fixed ratio.** Utility 1.249 against
  1.036 for the fixed ratio selected on training families (0.90): **+0.213**, positive in
  4 of 4 families, family-level 95% interval [+0.066, +0.361]. Against the ratio that is
  best on the test panel in hindsight (0.85, an oracle over constants) it is +0.193
  [+0.085, +0.302].
- **On seven held-out families the gain is not established.** The mean difference to the
  train-selected ratio is +0.047. Holding the families fixed, its interval is
  [+0.040, +0.055]. Resampling families, it is [-0.027, +0.122], and the difference is
  positive in 4 of 7 families. Against the hindsight-best ratio (1.05) the head is 0.035
  behind, family-level [-0.208, +0.139].
- **Calibration is marginal, and fails under shift.** Pooled ID ECE is 0.012, but per ID
  family it ranges from 0.026 to 0.181: the head is calibrated for the training mixture,
  not for each family. Pooled held-out ECE is 0.152 and the worst family reaches 0.359.
- **The RLCD recipe is not what helps.** RLCD minus an exact-gradient control is -0.008
  [-0.021, +0.007] in distribution; RLCD minus plain advantage regression is +0.019
  [-0.006, +0.045]. Both are zero on held-out families. What all three share is rollout
  supervision on the learner's own trajectories.
- **The decision rule matters.** Multiplying the probabilities by a fixed payoff table gains
  +0.213 over the train-selected ratio in distribution; executing the most probable option
  gains +0.095 and confidence gating +0.057.
- **Constraint violations.** In distribution 0.13% of control intervals are unsafe, against
  0.31% for the train-selected ratio. On held-out families 7.07% against 6.59%, of which
  5.01% are unsafe whatever is sent.
- **Legacy estimator.** Rerun unchanged, the head beats that testbed's best fixed ratio by
  +0.047 in distribution. That ratio acts as a constant cap and scores higher utility than
  the typed head over the bounded estimator (0.636 against 0.527) with more unsafe intervals
  (7.20% against 4.55%); neither dominates.
- **No hindsight at run time.** Replaying all 6,600 learned test episodes with rollouts
  switched off reproduces every frozen outcome exactly.

Nothing is promoted, and nothing here has run against a real network.

## What "Jev-like" and "RLCD" mean here

Jev (Typesafe) and Laya (Convai Innovations, open weights) are *typed decision
models*. They take a state and a schema-constrained question (a choice among
listed options, an ordinal score, or a yes/no) and return a probability per
option without generating text. Their training recipe is called **reinforcement
learning for calibrated decisions (RLCD)**. Jev's recipe is unpublished. The
[Laya model card](https://huggingface.co/convaiinnovations/laya) describes it as:
the policy reports a distribution, exploration adds zero-mean Gaussian noise to
the logits, the reward is a strictly proper scoring rule (log + spherical), and
updates are REINFORCE with a group-mean baseline.

This is unrelated to the paper's project name, which also abbreviates to RLCD and
refers to the older gated Double DQN controller. No pretrained Jev or Laya weights
are used here. The head is a 119 -> 64 -> 6 NumPy MLP trained from scratch.

## Why V1 found nothing

V1 compared a learned ratio against a fixed `0.85 x BWE` fallback and concluded
that the network added nothing. Two problems made that comparison uninformative.

1. **The estimator was unbounded.** The legacy GCC-like budget grows whenever
   delay and loss are low, however little the sender delivers. A sender below
   capacity drives the estimate to the 4 Mbps ladder maximum, so `ratio x BWE`
   silently becomes an absolute cap.
2. **The fallback was untuned and the option set was truncated.** Under that
   estimator the best fixed ratio is the lowest option, far ahead of 0.85.

Mean utility of each fixed ratio on the 64 ID tune episodes
(`results/jevbwe-typed-v2-diagnosis/diagnosis.json`):

| Policy | Legacy unbounded estimator | Acked-rate-bounded estimator |
|---|---:|---:|
| Fixed 0.60 x BWE | **1.198** | 0.345 |
| Fixed 0.70 x BWE | 1.127 | 0.408 |
| Fixed 0.80 x BWE | 0.926 | 0.749 |
| Fixed 0.85 x BWE (the V1 fallback) | 0.771 | 1.050 |
| Fixed 0.90 x BWE | 0.675 | **1.080** |
| Fixed 1.00 x BWE | 0.464 | 0.987 |
| Fixed 1.05 x BWE | 0.451 | 1.046 |
| Hindsight oracle (non-causal) | 1.364 | 1.407 |

Under the legacy estimator a 0.60 ratio is in effect a constant 2.4 Mbps cap. That
suits these families, whose capacity sits mostly between 2.4 and 3.5 Mbps, for a
reason that has nothing to do with estimating bandwidth. It is also a strong
simple controller in this simulator, which is why the whole pipeline is replicated
under the legacy estimator below.

V2 adds one bound from the GCC draft (section 5.5): the estimate may not exceed
1.5 times the measured delivered rate. Ratios below about 0.75 then stall the
estimate, the best fixed ratio becomes interior, and the choice of ratio depends
on context. `bwe: "legacy"` in a config restores the old estimator. The corrected
estimator is still a simplified model, not libwebrtc.

V1 also trained on 432 factual cohorts, about 72 per option, and scored an event
(`utility >= 1.0`) that barely depends on the action. V2 uses rollout labels at
every decision and tens of thousands of them.

## Design

| Piece | Choice |
|---|---|
| Action | One of `{0.60, 0.70, 0.80, 0.90, 1.00, 1.05} x BWE`; bitrate only, FEC off |
| Decision cadence | Once per second; the ratio is held in between |
| Hard rules (all methods) | 1.8 s dwell on increases, immediate decreases, 0.7x emergency cut with a 1.8 s hold, minimum rate on stale feedback |
| State | 108 ordered history values and masks over 3 s, plus 11 long-memory summaries |
| Label | Best option by hindsight rollout: hold the option 3 s, then the base ratio 2 s; the base wins inside a 0.02 margin |
| Base ratio | Best fixed ratio on 64 ID tune episodes |
| Training data | Dataset aggregation: 5 rounds x 800 ID episodes, later rounds on the learner's own trajectories with 20% exploration |
| Objective | `log p[y] + 0.5 * p[y] / ||p||`, strictly proper |
| Estimator | REINFORCE over 8 Gaussian logit reports (std 0.2), leave-one-out baseline |
| Calibration | One temperature per head on 200 held-out ID episodes run by the deployed rule |

The long-memory summaries are causal: delivered rate at the last congestion onset
(a capacity knee), time since congestion and since the last cap change, rates
relative to the estimate, and RTT above its floor. There is no clock, scenario
identity, capacity or future outcome in the state.

Labels replay the true future trace in a forked simulator, so they are hindsight
labels for fitting and evaluation. No controller receives them.

### Acting on the answer

Three rules use the same calibrated probabilities `p`:

- **`map`** runs the most probable option with no guard. Ablation.
- **`gated`** runs it only when its probability reaches a threshold chosen on the
  calibration episodes, otherwise the base ratio. This is the usage pattern
  advertised for typed decision models.
- **`bayes`** runs `argmax_a sum_b p[b] * M[a][b]`, where `M[a][b]` is the mean
  advantage over the base of running option `a` when option `b` turned out best,
  measured on the calibration episodes. The base row is zero, so the rule returns
  to the base by itself when nothing has positive expected advantage.

`gated` and `bayes` also return to the base on stale telemetry or when the
standardised state is beyond the 99.5th percentile of training support.

Two controls share the data and network size: `choice_analytic` trains the same
objective with the exact gradient instead of REINFORCE, and `regress` fits the
advantage of each option by least squares and runs its argmax.

## Protocol

All fitting, calibration and tuning use the four ID families (steady, step, ramp,
wifi). The seven other families appear only in the test split.

- The estimator bound, the ratio set and the rollout horizon were settled from a
  fixed-ratio and oracle sweep before any model was trained. That sweep used seeds
  disjoint from every later split but covered all eleven families, so the held-out
  families informed those three choices.
- The long-memory summaries, the `bayes` rule, the rollout tail, network width and
  number of rounds were developed on one model seed using the ID validation panel.
- The configuration was then frozen, five model seeds were trained, and the test
  panel (24 trace seeds x 11 families) was evaluated once.

Every method sees identical traces. Contrasts subtract matched outcomes, and their
intervals resample model seeds and trace seeds jointly. `best_fixed` is the fixed
ratio (the six options and 0.85) with the highest utility on the same panel,
chosen in hindsight, which favours the baseline. `oracle` re-plans every second
with the true future trace and is a non-causal bound.

Those intervals hold the 11 families fixed. Family-level intervals, and the
comparison against the fixed ratio selected on training families only, are in
[Audit of the frozen panel](#audit-of-the-frozen-panel). The seven held-out families
have now been read once and motivated the next design step, so from V3 on they are
development families and a new untouched test set is used.

## Commands

```sh
# Seconds-scale smoke; not evidence.
uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_smoke_v2.json --out results/my-typed-smoke

# Estimator diagnosis: fixed-ratio sweep and oracle under both estimators.
uv run --frozen jevbwe-typed diagnose --config configs/jevbwe_typed_v2.json --out results/my-typed-diagnosis

# Full study. Train and look at the ID validation panel first, then add the test panel once.
uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_v2.json --out results/my-typed --splits validation
uv run --frozen jevbwe-typed evaluate --run results/my-typed --splits test

# Paper macros, tables and figure. --ablation and --robustness are optional extra runs.
uv run --frozen jevbwe-typed export --run results/my-typed --diagnosis results/my-typed-diagnosis --out paper/generated-jevbwe-typed-v2
```

`make jevbwe-typed` runs the diagnosis, the main study, the summaries ablation
(`configs/jevbwe_typed_v2_no_summaries.json`) and the legacy-estimator replication
(`configs/jevbwe_typed_v2_legacy.json`). `make jevbwe-typed-evidence` exports all four.

Output directories must not exist. `evaluate` refuses to recompute a panel that is
already in `report.json`. The main study takes about an hour on 8 cores.

Source: `src/media_rl/typed_bitrate.py` (head, estimator, governor, rollouts,
training, decision rules), `typed_bitrate_experiment.py` (pipeline and CLI),
`typed_bitrate_report.py` (paper export). Tests: `tests/test_typed_bitrate.py`.

### What is tracked, and regenerating the rest

`results/` is ignored. Only the small summaries that the paper's numbers are read from are
tracked there: `config.json`, `report.json`, `audit_*.json` and `*_isolation.json` of each
run, and `diagnosis.json` (about 1.2 MB in total). Models, aggregated training data,
per-episode outcomes and decision records (about 260 MB) are not tracked.
`paper/generated-jevbwe-typed-v2/outputs_manifest.json` lists every file of the five run
directories with its size and sha256, and `provenance.json` hashes the summaries the export
read.

The configs fix every seed, so the Makefile targets regenerate everything. A run refuses to
write into an existing directory, and on a clone the tracked summaries already occupy
`results/jevbwe-typed-*`, so regenerate into a fresh root and export from it:

```sh
make jevbwe-typed jevbwe-typed-audit jevbwe-typed-broad jevbwe-typed-broad-test TYPED=results/regen
make jevbwe-typed-evidence TYPED=results/regen   # then: git diff paper/generated-jevbwe-typed-v2
```

Checked on the machine that produced the runs (2026-10-07): retraining V2 model seed 0 from
`configs/jevbwe_typed_v2.json` with the committed code reproduces the frozen model exactly,
and replaying both frozen panels reproduces every episode outcome. `report.json` differs
between runs in its two timing fields (`elapsed_s`, `inference_us`). Bit-identical floating
point on another platform or NumPy build is not guaranteed.

### Relation to the native controller freeze

The native actuator panel hash-freezes 31 controller, model and actuator source
files in `configs/native_controller_freeze_v1.json` and refuses to run if any of
them changes or if a new file appears matching `jevbwe*.py`, `*policy*.py`,
`*learning*.py` or `*model*.py`. This study modifies none of the frozen files
and lives in `typed_bitrate*.py`, outside that inventory, so
`media-panel-assets verify-freeze` still passes and the freeze record is
untouched.

It is still a new model iteration, which the freeze was written to discourage
while actuator identification was the milestone. It was built as a separate,
synthetic-only study. Running this head natively needs its own freeze and
protocol; it must not be slipped into the frozen panel.

## Results

Run: `results/jevbwe-typed-v2` (8,712 test episodes, 2,112 validation episodes,
42,240 labelled test decisions per learned rule). Utility is mean delivered QoE
minus switch cost. Unsafe is the share of 100 ms intervals violating the latency
or loss constraint. Intervals are 95%, resampling model seeds and trace seeds
jointly.

### Test outcomes

| Method | ID utility | ID unsafe % | Held-out utility | Held-out unsafe % | All utility |
|---|---:|---:|---:|---:|---:|
| Fixed 0.60 x BWE | 0.352 | 0.00 | -0.233 | 6.39 | -0.021 |
| Fixed 0.70 x BWE | 0.417 | 0.00 | -0.199 | 6.39 | 0.025 |
| Fixed 0.80 x BWE | 0.759 | 0.00 | -0.062 | 6.40 | 0.237 |
| Fixed 0.85 x BWE | 1.056 | 0.04 | -0.005 | 6.42 | 0.381 |
| Fixed 0.90 x BWE (base) | 1.036 | 0.31 | 0.066 | 6.59 | 0.419 |
| Fixed 1.00 x BWE | 1.018 | 0.86 | 0.147 | 7.17 | 0.464 |
| Fixed 1.05 x BWE | 1.016 | 1.59 | 0.148 | 7.63 | 0.464 |
| Typed choice, RLCD, **payoff-weighted** (primary) | 1.249 | 0.13 | 0.114 | 7.07 | 0.527 |
| Typed choice, RLCD, confidence-gated | 1.092 | 0.56 | 0.144 | 7.20 | 0.489 |
| Typed choice, RLCD, most probable (no guard) | 1.131 | 0.93 | 0.116 | 7.61 | 0.485 |
| Typed choice, exact gradient, payoff-weighted | 1.257 | 0.13 | 0.115 | 7.05 | 0.530 |
| Advantage regression (untyped) | 1.230 | 0.27 | 0.115 | 7.15 | 0.521 |
| Hindsight oracle (non-causal bound) | 1.387 | 0.46 | 0.262 | 6.53 | 0.671 |

### Paired contrasts

| Method | ID vs best fixed (0.85) | Held-out vs best fixed (1.05) | Held-out vs base (0.90) | All vs best fixed (1.05) |
|---|---:|---:|---:|---:|
| Typed choice, RLCD, **payoff-weighted** (primary) | +0.193 [+0.167, +0.217] | -0.035 [-0.044, -0.024] | +0.047 [+0.040, +0.055] | +0.063 [+0.051, +0.073] |
| Typed choice, RLCD, confidence-gated | +0.036 [+0.016, +0.058] | -0.004 [-0.013, +0.006] | +0.078 [+0.073, +0.083] | +0.025 [+0.014, +0.036] |
| Typed choice, RLCD, most probable (no guard) | +0.075 [+0.047, +0.102] | -0.033 [-0.038, -0.028] | +0.049 [+0.039, +0.059] | +0.021 [+0.012, +0.029] |
| Typed choice, exact gradient, payoff-weighted | +0.201 [+0.177, +0.224] | -0.033 [-0.043, -0.023] | +0.049 [+0.041, +0.056] | +0.066 [+0.055, +0.079] |
| Advantage regression (untyped) | +0.174 [+0.151, +0.198] | -0.033 [-0.044, -0.022] | +0.049 [+0.040, +0.058] | +0.057 [+0.046, +0.069] |
| Hindsight oracle (non-causal bound) | +0.331 [+0.315, +0.348] | +0.114 [+0.106, +0.123] | +0.196 [+0.192, +0.200] | +0.207 [+0.199, +0.215] |

"Best fixed" is picked on the same panel after the fact. No fixed ratio matches the
head on both panels: 1.05 is best on held-out families but scores 1.016 on ID
families against the head's 1.249.

### Calibration of the typed answer

| Rule | Panel | Accuracy % | Mean confidence % | ECE | NLL |
|---|---|---:|---:|---:|---:|
| RLCD, payoff-weighted | ID | 75.0 | 74.7 | 0.012 | 0.716 |
| RLCD, payoff-weighted | Held-out | 76.6 | 90.1 | 0.152 | 2.476 |
| RLCD, most probable (no guard) | ID | 78.9 | 79.1 | 0.023 | 0.591 |
| RLCD, most probable (no guard) | Held-out | 71.3 | 89.3 | 0.180 | 2.728 |
| Exact gradient, payoff-weighted | ID | 74.5 | 74.5 | 0.013 | 0.725 |
| Exact gradient, payoff-weighted | Held-out | 76.5 | 90.1 | 0.150 | 2.823 |

Fitted temperatures are 1.04 to 1.21. On held-out families the support guard
rejects only 2.5% of decisions, so it does not catch the shift.

### By family

| Family | Split | Base 0.90 | Fixed 1.05 | Typed (payoff) | Typed (gated) | Regression | Oracle |
|---|---|---:|---:|---:|---:|---:|---:|
| steady | ID | 1.167 | 1.160 | 1.372 | 1.204 | 1.480 | 1.476 |
| step | ID | 0.935 | 0.930 | 1.276 | 1.069 | 1.170 | 1.330 |
| ramp | ID | 1.109 | 1.069 | 1.227 | 1.115 | 1.164 | 1.494 |
| wifi | ID | 0.932 | 0.907 | 1.123 | 0.981 | 1.105 | 1.248 |
| collapse | held-out | 0.493 | 0.345 | 0.489 | 0.443 | 0.437 | 0.723 |
| burst_loss | held-out | 0.104 | 0.152 | 0.129 | 0.129 | 0.128 | 0.141 |
| bufferbloat | held-out | 0.735 | 0.626 | 0.716 | 0.686 | 0.706 | 0.989 |
| handover | held-out | -1.197 | -1.217 | -1.123 | -1.118 | -1.122 | -1.103 |
| outage | held-out | -1.684 | -1.441 | -1.522 | -1.522 | -1.521 | -1.457 |
| feedback_gap | held-out | 0.550 | 0.743 | 0.690 | 0.688 | 0.695 | 0.722 |
| capacity_surge | held-out | 1.464 | 1.831 | 1.417 | 1.704 | 1.483 | 1.820 |

The held-out shortfall against 1.05 is mostly capacity surge, where capacity jumps
to about 10 Mbps and the most aggressive option is right almost throughout.

### What the comparisons say

- **Payoff weighting beats thresholding in distribution.** The most probable
  option is not the option with the best expected outcome when overshoot is costly:
  running it gains +0.075 with seven times the unsafe frequency. Thresholding at the
  calibration-selected 0.8 keeps +0.036. Payoff weighting gets +0.193.
- **No rule is distinguishable from another on held-out families.** Against the
  train-selected ratio the gated, most-probable and payoff-weighted rules end +0.078,
  +0.049 and +0.047; once families are resampled, the intervals of their pairwise
  differences contain zero.
- **The RLCD recipe is not where the gain comes from.** The exact-gradient head
  matches it (+0.201 against +0.193) and plain advantage regression is not
  distinguishable from it (+0.174); the intervals of both differences contain zero.
  What the three share is rollout supervision on the learner's own trajectories.
  Typing adds a probability report, not utility.

The contrasts in this section are against the hindsight-best fixed ratio with seed-level
intervals. The comparator for claims is the train-selected ratio with family-level
intervals; see [Audit of the frozen panel](#audit-of-the-frozen-panel).
- **The long-memory summaries barely matter.** Zeroing them changes single-seed ID
  validation utility from 1.272 to 1.260
  (`results/jevbwe-typed-v2-ablation-no-summaries`).
- **Cost.** 8,070 parameters; about 15 microseconds per answer in NumPy.

### Replication over the legacy estimator

The diagnosis table shows that a 0.60 ratio over the legacy estimator, in effect a
constant 2.4 Mbps cap, is a strong simple controller on these traces. So the frozen
pipeline was rerun unchanged with `bwe: "legacy"`: same hyperparameters and traces,
a separately tuned base (0.60) and separately trained models
(`results/jevbwe-typed-v2-legacy`).

| Estimator | Method | ID utility | Held-out utility | All | Unsafe % (all) |
|---|---|---:|---:|---:|---:|
| Unbounded (legacy) | Best fixed ratio (0.60) | 1.189 | 0.319 | 0.636 | 7.20 |
| | Typed choice, RLCD, payoff-weighted | 1.236 | 0.336 | 0.663 | 7.33 |
| | Advantage regression (untyped) | 1.251 | 0.330 | 0.665 | 7.21 |
| | Hindsight oracle (non-causal bound) | 1.375 | 0.530 | 0.838 | 5.80 |
| Acked-rate-bounded | Best fixed ratio (1.05) | 1.016 | 0.148 | 0.464 | 5.43 |
| | Typed choice, RLCD, payoff-weighted | 1.249 | 0.114 | 0.527 | 4.55 |
| | Advantage regression (untyped) | 1.230 | 0.115 | 0.521 | 4.65 |
| | Hindsight oracle (non-causal bound) | 1.387 | 0.262 | 0.671 | 4.33 |

- The typed head again beats the best fixed ratio: **+0.047 [+0.031, +0.062]** on
  ID families and **+0.016 [+0.006, +0.027]** on held-out families. The gains are
  smaller because the hindsight headroom is smaller (+0.186 on ID).
- Held-out confidence is again over-optimistic (ECE 0.299 against 0.011 in
  distribution). Regression again matches the typed head.
- **By this QoE function the legacy estimator is the higher-scoring testbed.** Its
  constant cap alone reaches 0.636 over all families, above the typed head over the
  bounded estimator (0.527). It gets there with more violations: 7.20% of intervals
  against 4.55%, and 3.13% against 0.13% in distribution.

The bound makes the estimator a more faithful model of GCC. It does not make it a
better controller under this reward, and a cap matched to these traces' capacity
range should not be expected to transfer to links of a different scale. The claim
that survives both testbeds is the narrow one: a typed head trained on rollout
labels improves on the best fixed ratio over the same estimator.

## Audit of the frozen panel

Added 2026-10-07. The audit re-derives extra diagnostics from the frozen models and the
frozen test traces. Nothing was refitted or retuned, and the frozen `report.json` and
`test_episodes.json` are unchanged.

```sh
# Replay the frozen panel: identity checks plus decision-level records (about 12 minutes).
uv run --frozen jevbwe-typed rescore --run results/jevbwe-typed-v2 --split test
# Family tables, family-level intervals, rule analysis, utility against violations.
uv run --frozen jevbwe-typed audit --run results/jevbwe-typed-v2 --split test \
    --robustness results/jevbwe-typed-v2-legacy
```

### Two fixed-ratio references

- **Train-selected fixed ratio**: 0.90, chosen on 64 training-family tune episodes before
  any model was fitted. This is the comparator for claims.
- **Hindsight-best fixed ratio**: the best constant on the evaluated panel itself (0.85 on
  ID families, 1.05 on held-out families). It is an oracle and is reported as a bound.

### Uncertainty

The intervals in `report.json` resample model seeds and trace seeds and hold the 11 families
fixed. They say how well a difference is measured on these families. A statement about
unseen families needs the families to be the sample, so the audit adds a hierarchical
bootstrap (families, traces within each drawn family, model seeds) and, because a percentile
bootstrap over 4 or 7 clusters is anti-conservative, a t interval on the family-level mean
differences.

| Typed head minus | Panel | Difference | Seeds (families fixed) | Family bootstrap | Family t | Families > 0 |
|---|---|---:|---|---|---|---:|
| train-selected fixed | ID | +0.213 | [+0.185, +0.240] | [+0.135, +0.303] | [+0.066, +0.361] | 4/4 |
| | held-out | +0.047 | [+0.040, +0.055] | [-0.008, +0.103] | [-0.027, +0.122] | 4/7 |
| | all | +0.108 | [+0.097, +0.118] | [+0.046, +0.177] | [+0.030, +0.186] | 8/11 |
| hindsight-best fixed | ID | +0.193 | [+0.168, +0.218] | [+0.125, +0.252] | [+0.085, +0.302] | 4/4 |
| | held-out | -0.035 | [-0.045, -0.024] | [-0.173, +0.075] | [-0.208, +0.139] | 3/7 |
| exact-gradient control | ID | -0.008 | [-0.021, +0.007] | [-0.028, +0.016] | [-0.033, +0.018] | 1/4 |
| | held-out | -0.001 | [-0.005, +0.003] | [-0.008, +0.006] | [-0.007, +0.004] | 3/7 |
| regression control | ID | +0.019 | [-0.006, +0.045] | [-0.066, +0.100] | [-0.128, +0.167] | 3/4 |
| | held-out | -0.002 | [-0.011, +0.008] | [-0.028, +0.025] | [-0.033, +0.030] | 3/7 |

### By family

Utility, then the share of unsafe 100 ms control intervals. The floor is the share that is
unsafe whatever is sent (zero capacity, random loss above 5%, or base delay above the limit).

| Family | Split | Train-sel. 0.90 | Hindsight-best fixed | Typed | Typed minus train-sel. [seeds] | Regression | Oracle | Unsafe %: floor / train-sel. / typed | ECE |
|---|---|---:|---:|---:|---|---:|---:|---|---:|
| steady | ID | 1.167 | 1.167 (0.90) | 1.372 | +0.204 [+0.160, +0.247] | 1.480 | 1.476 | 0.00 / 0.13 / 0.00 | 0.181 |
| step | ID | 0.935 | 1.104 (0.85) | 1.276 | +0.341 [+0.276, +0.401] | 1.170 | 1.330 | 0.00 / 0.13 / 0.05 | 0.169 |
| ramp | ID | 1.109 | 1.115 (0.85) | 1.227 | +0.118 [+0.037, +0.197] | 1.164 | 1.494 | 0.00 / 0.13 / 0.08 | 0.033 |
| wifi | ID | 0.932 | 0.939 (1.00) | 1.123 | +0.191 [+0.153, +0.233] | 1.105 | 1.248 | 0.00 / 0.87 / 0.40 | 0.026 |
| collapse | held-out | 0.493 | 0.499 (0.80) | 0.489 | -0.003 [-0.040, +0.031] | 0.437 | 0.723 | 0.00 / 1.13 / 3.72 | 0.271 |
| burst_loss | held-out | 0.104 | 0.152 (1.05) | 0.129 | +0.026 [+0.016, +0.036] | 0.128 | 0.141 | 15.22 / 15.22 / 15.22 | 0.359 |
| bufferbloat | held-out | 0.735 | 0.776 (0.80) | 0.716 | -0.020 [-0.043, +0.005] | 0.706 | 0.989 | 0.00 / 0.13 / 0.93 | 0.227 |
| handover | held-out | -1.197 | -1.136 (1.00) | -1.123 | +0.074 [+0.074, +0.075] | -1.122 | -1.103 | 4.86 / 14.34 / 14.36 | 0.035 |
| outage | held-out | -1.684 | -1.441 (1.05) | -1.522 | +0.162 [+0.159, +0.165] | -1.521 | -1.457 | 15.00 / 15.28 / 15.28 | 0.111 |
| feedback_gap | held-out | 0.550 | 0.743 (1.05) | 0.690 | +0.140 [+0.137, +0.144] | 0.695 | 0.722 | 0.00 / 0.00 / 0.00 | 0.220 |
| capacity_surge | held-out | 1.464 | 1.831 (1.05) | 1.417 | -0.047 [-0.076, -0.017] | 1.483 | 1.820 | 0.00 / 0.00 / 0.00 | 0.219 |

Pooled ID ECE is 0.012 only because under-confidence on `steady` (90% correct at 72%
confidence) and over-confidence on `step` (58% at 75%) cancel. The head cannot see which
family it is in, so it is calibrated for the training mixture and not per family.

### From six probabilities to a bitrate

Once per second, with causal inputs only:

1. Standardise the 119 inputs with the training mean and scale, clip to +-12.
2. One forward pass gives logits `z`; `p = softmax(z / T)` with the frozen temperature.
3. Expected advantage of each option `e = M p`; the proposal is `argmax e`.
4. Run the base ratio instead if the proposal is the base, if its expected advantage is not
   positive, if feedback is invalid or older than 500 ms, or if the RMS standardised input
   exceeds the support limit.
5. Hold the ratio until the next decision. Every 100 ms the shared governor turns
   `ratio x BWE` into the requested cap under the hard rules (floor, ceiling, increase dwell,
   emergency cut, stale-feedback floor).

"Weighting by measured payoffs" is step 3. `M[a][b]` is the mean rollout advantage over the
base of running option `a` when option `b` turned out best, averaged over ID calibration
decisions. It is built from simulator rollouts at fitting time and is a constant at run time.
Mean over the five model seeds (rows: option run; columns: option that turned out best):

| | 0.60 | 0.70 | 0.80 | 0.90 | 1.00 | 1.05 |
|---|---:|---:|---:|---:|---:|---:|
| 0.60 | +0.590 | +0.484 | +0.148 | -0.195 | -0.176 | -0.219 |
| 0.70 | +0.312 | +0.584 | +0.244 | -0.117 | -0.079 | -0.142 |
| 0.80 | +0.122 | +0.216 | +0.336 | -0.047 | -0.006 | -0.070 |
| 0.90 (base) | 0 | 0 | 0 | 0 | 0 | 0 |
| 1.00 | -0.070 | -0.144 | -0.213 | -0.111 | +0.117 | +0.037 |
| 1.05 | -0.130 | -0.226 | -0.361 | -0.177 | -0.038 | +0.112 |

Run-time isolation was checked three ways. Recomputing steps 3 and 4 from the recorded
probabilities and the frozen table reproduces 100% of the options that ran. Replaying all
6,600 learned test episodes with rollouts switched off reproduces every frozen outcome with
maximum absolute difference 0. A unit test makes the rollout and fork functions raise and
runs a typed episode. Hindsight rollouts enter the training labels, the payoff table, the
calibration fits, the oracle rows and the scoring of accuracy and calibration, and nothing
else.

### Why the most probable answer keeps so little

Each rule applied to the same reported probabilities, on the states the deployed policy
visited (ID families). "One decision" is the rollout advantage over the base of the single
choice; "closed loop" is test utility minus the train-selected ratio.

| Rule | Below base % | Above base % | Agrees with label % | One decision | Closed loop |
|---|---:|---:|---:|---:|---:|
| Most probable option | 2.6 | 79.6 | 75.0 | +0.017 | +0.095 |
| Most probable, if confidence >= 0.8 | 0.0 | 37.2 | 54.6 | +0.045 | +0.057 |
| Payoff-weighted (runs) | 39.5 | 50.4 | 61.3 | +0.068 | +0.213 |
| Best in hindsight (non-causal) | 16.6 | 69.3 | 96.0 | +0.135 | +0.351 |

The frequent answer, go higher, gains at most +0.117 when right and loses up to -0.361 when a
lower ratio was best. The rare answer, go lower, gains +0.336 to +0.590 when right. The most
probable option follows the frequent low-stakes answer. Payoff weighting acts on the rare
high-stakes answer at modest probability: it goes below the base in 39.5% of decisions, is
"right" less often and earns four times as much per decision. Confidence gating never goes
below the base, because downward answers rarely reach 0.8. Where the two rules differ (41% of
ID decisions) the most probable option loses 0.084 against the base and the payoff-weighted
choice gains 0.039.

On held-out families the payoff table predicts +0.093 for the decisions that leave the base
and the rollouts deliver +0.036 (in distribution: +0.066 predicted, +0.075 delivered). The
payoffs are out of distribution there as well as the probabilities, 19.3% of decisions are
returned to the base by a guard (3.4% in distribution), and the three rules end within
family-level noise of each other.

### Utility against constraint violations

Utility / unsafe % for both estimators on identical traces.

| Estimator | Method | ID | Held-out | All |
|---|---|---|---|---|
| Unbounded (legacy) | Fixed 0.60 (constant cap) | 1.189 / 3.13 | 0.319 / 9.53 | 0.636 / 7.20 |
| | Typed head | 1.236 / 2.86 | 0.336 / 9.88 | 0.663 / 7.33 |
| | Regression | 1.251 / 2.70 | 0.330 / 9.79 | 0.665 / 7.21 |
| | Hindsight oracle | 1.375 / 1.83 | 0.530 / 8.07 | 0.838 / 5.80 |
| Acked-rate-bounded | Fixed 0.85 | 1.056 / 0.04 | -0.005 / 6.42 | 0.381 / 4.10 |
| | Fixed 0.90 (train-selected) | 1.036 / 0.31 | 0.066 / 6.59 | 0.419 / 4.30 |
| | Fixed 1.00 | 1.018 / 0.86 | 0.147 / 7.17 | 0.464 / 4.88 |
| | Fixed 1.05 | 1.016 / 1.59 | 0.148 / 7.63 | 0.464 / 5.43 |
| | Typed head | 1.249 / 0.13 | 0.114 / 7.07 | 0.527 / 4.55 |
| | Regression | 1.230 / 0.27 | 0.115 / 7.15 | 0.521 / 4.65 |
| | Hindsight oracle | 1.387 / 0.46 | 0.262 / 6.53 | 0.671 / 4.33 |
| Either | Floor | - / 0.00 | - / 5.01 | - / 3.19 |

- In distribution the typed head is above the fixed-ratio frontier of its estimator: +0.193
  utility at fewer unsafe intervals than the train-selected ratio.
- On held-out families it is 0.020 below the line joining the fixed ratios, and adds 0.49
  percentage points of unsafe intervals over the train-selected ratio (family-level
  [0.00, 1.25]).
- Typed head (bounded) minus the legacy constant cap, all families: -0.109 utility
  (family-level [-0.369, +0.151], positive in 5 of 11 families) and -2.65 points of unsafe
  intervals (family-level [-4.76, -0.81]). The cap's utility lead is confined to held-out
  families (-0.206 for the typed head) and reverses in distribution (+0.060); the typed head
  has fewer unsafe intervals on both panels. Neither dominates.

## What this does not show

- **No real network or codec.** The fluid simulator, the 1.5 s encoder response
  and the QoE function are modelling assumptions.
- **Hindsight labels need a simulator.** On a real network only the executed
  option has an outcome. A native version needs factual, propensity-logged data;
  the V1 factual pilot was far too small to say whether that works.
- **Fixed event timing.** ID families place their events at fixed fractions of an
  episode. Features such as time since congestion can exploit that, so ID gains
  may overstate what transfers. The held-out families are the check on this.
- **The payoff table is coarse.** It assumes an option's payoff depends on the
  history only through which option is best.
- **Single flow, simplified estimator.** No competing traffic, no libwebrtc probing.

## Next steps

1. Train on a broader, randomised trace distribution and test on families no
   controller has run on: [Typed-Control V3](JEVBWE_TYPED_V3_BROAD.md).
2. Replace hindsight labels with factual propensity-logged outcomes at the same
   data scale, to see how much of the gain survives without a simulator.
3. Run the frozen head in the native Chrome harness against native BWE.
4. Add a per-option yes/no safety question to the same head.

No Laya head or other architecture is planned. The weakness is generalisation to
unseen families, not model capacity. Steps 2 and 3 belong to the native track and
need its factual data; nothing in this document substitutes for them.
