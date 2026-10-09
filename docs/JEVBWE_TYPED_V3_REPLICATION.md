# Typed-control V3 replication on a sampled family population

Status: **protocol registered 2026-10-08, before any controller ran on any family of the
population.** Results are appended below the protocol and do not change it.

**Outcome.** Three of the four pre-specified criteria are met. On 48 families drawn from the
stated population the frozen V3 head gains +0.019 utility over the train-selected fixed ratio,
positive in 32 of 48 families, with family-level t interval [+0.005, +0.034] and bootstrap
interval [+0.006, +0.036]. Against the tuned reactive rule the gain is +0.020
[+0.004, +0.035]. Unsafe intervals fall by 0.26 points. Pooled ECE is 0.138, far above the 0.05
threshold: the head is over-confident on unseen families and its probabilities are not
calibrated there. The gain is small. It is about a third of the V3 point estimate, 18% of what
the hindsight oracle gains, and absent in 19 of the 48 families. Against the fixed ratio that
is best on this panel in hindsight (1.00) it is +0.012 with an interval that includes zero.
Exact-gradient and regression controls match the RLCD head again. Synthetic only; the typed
controller is not promoted.

This is a simulator study in the synthetic track. It evaluates the five frozen V3 models. It
fits nothing, changes no option set, decision rule or guard, and is not a V4. The native
controller freeze and the registered native Phase N1 are untouched and are not informed by it.

## Why

V3 (`docs/JEVBWE_TYPED_V3_BROAD.md`) gained +0.054 utility over the train-selected fixed ratio
on twelve untouched families, with a family-level t interval of [-0.005, +0.112]. The gain was
not established. Two readings were open:

1. The comparator was weak. `docs/JEVBWE_TYPED_BASELINE_AUDIT.md` closes this: the fixed ratio
   is an interior optimum and a tuned reactive rule adds at most +0.008.
2. Twelve families are too few to tell +0.05 from zero when families differ by 0.09. That needs
   more families, not a new model.

Twelve hand-written families are also a convenience sample. An interval over them does not say
which families it speaks for. This protocol replaces them with draws from a stated population.

## What is evaluated

The five model files of `results/jevbwe-typed-v3-broad`, identified by SHA-256 in
`configs/jevbwe_typed_v3_replication.json`. The base ratio (1.05), temperatures, payoff tables,
support limit and decision rules are the ones frozen with them on 2026-10-07. The command
`jevbwe-typed transfer` refuses to run if a model file or the population differs from the
registered hash, and refuses to write into an existing directory.

## The population

`src/media_rl/typed_bitrate_population.py`. A family is one draw of family-level parameters;
an episode is one draw of a trace given those parameters. The draws are independent:

| Parameter | Distribution |
|---|---|
| Capacity shape | one of flat, steps, ramps, sine, sawtooth, square, fade, random walk |
| Mean capacity | log-uniform, 0.12 to 1.3 times the 2.8 Mbps base (0.34 to 3.6 Mbps) |
| Trough and crest of the shape | uniform 0.2 to 0.6 and 1.0 to 1.6 of the mean |
| Base round-trip time | log-uniform, 20 to 180 ms |
| Buffer depth | log-uniform, 0.25 to 10 times the default |
| Jitter deviation | uniform, 1 to 4 ms |
| Persistent random loss of 2% to 4.5% | present in 15% of families |
| Capacity surge, delay shift, jitter storm, loss episode, feedback gaps, outages | each present independently in 25% of families, with a family-level severity |

The ranges are those the hand-written training and test families already use. The population
reuses the simulator's seven trace signals: it tests unseen families, not unseen physics.

The population seed is 20261008 and the SHA-256 of the full parameter table is
`fbfb8da0...fdd679c` (pinned in `tests/test_typed_bitrate_population.py` and in the
registration). Three disjoint index spaces:

| Space | Families | Role |
|---|---:|---|
| `pop_r` | 48 | this replication panel; evaluated once |
| `pop_s` | 48 | sealed for the next confirmatory experiment; no controller runs on it here |
| `pop_d` | 64 | development pool; the only space a fitting or tuning step may draw from |

`TypedConfig.validate` rejects a config that trains or develops on `pop_r` or `pop_s`. Unit
tests run controllers on `pop_d` only.

**What the author knew when writing the population.** The V3 results on its twelve test
families, including that three of them (`lossy_link`, `feedback_flap`, `micro_outage`) are
insensitive to the controlled ratio, and the baseline audit. The mechanisms behind those three
are kept in the population at stated rates (persistent loss 15%, feedback gaps 25%, outages
25%); they were not removed to help the head or added to hurt it. Before registration only
parameter counts and trace well-formedness were looked at. No controller, fixed ratio or oracle
was run on any population family.

## The panel

48 families (`pop_r00` to `pop_r47`) by 16 trace seeds (29301 to 29316): 768 traces, 360
control steps each, identical across methods. Five model seeds for learned methods.

**Power.** The twelve family-level differences of V3 have a standard deviation of 0.092. If
the population has the same spread, 48 families give a t-interval half-width of 0.027 and
power of 0.98, 0.84 and 0.61 against true mean gains of 0.054, 0.040 and 0.030. The population
is broader than the twelve families and its spread may be larger; the panel size is fixed
regardless.

## Pre-specified endpoints

Primary method: `choice_rlcd_bayes`. Uncertainty is clustered at the family level exactly as in
V3: a bootstrap that resamples families, traces within each drawn family and model seeds
(5,000 resamples), and a t interval on the 48 family-level mean differences (47 degrees of
freedom).

1. **Gain over the train-selected fixed ratio (1.05).** "Replicated" requires both family-level
   intervals to exclude zero.
2. **Gain over the tuned rule.** The comparator is
   `delay(high=1.05, low=0.8, on_ms=15, off_ms=5)`, selected on training tune traces before the
   population existed. Same two intervals, both must exclude zero. The audit command refuses to
   run if tuning returns a different rule.
3. **Calibration.** Pooled top-label ECE (10 bins) at most 0.05. The per-family range is
   reported whatever it is.
4. **Constraints.** Upper end of the family-clustered interval of the unsafe-share difference
   to the fixed ratio at most +1.0 percentage point.

Criteria 1, 3 and 4 and their thresholds are V3's. Criterion 2 is new and follows from the
baseline audit.

Secondary, reported whatever the outcome:

- The exact-gradient and regression controls and their differences to the RLCD head. An
  RLCD-specific advantage is claimed only if such an interval excludes zero.
- The hindsight oracle and the hindsight-best fixed ratio, as bounds.
- **Action-sensitive families**, defined without reference to any learned method: families
  where the hindsight oracle gains at least 0.02 (the label margin) over the fixed ratio.
  Criteria 1 and 2 are recomputed on that subset. The subset is diagnostic. It does not
  replace the all-family result, and a criterion met only on the subset is not met.
- The `map` and `gated` rules; the number of families with a positive difference; the
  leave-one-family-out range.

## Rules

- One evaluation. No family is excluded for any reason, including families where every method
  scores the same.
- Models, config, population and analysis code stay as committed with this protocol. If the
  run exposes a defect in the new code (population, transfer, baseline audit), the result is
  reported as obtained, the defect is documented, and any corrected rerun is labelled as such.
  It does not use `pop_s`.
- After the evaluation `pop_r` is a development panel. It cannot serve as an untouched panel
  again.

## How the outcome will be read

| Outcome | Reading |
|---|---|
| 1, 2, 3 and 4 met | V3's gain, calibration and constraint behaviour replicate on the stated population. Still synthetic; no promotion, which needs native evidence. |
| 1 and 2 met, 3 not | The gain replicates; the reported probabilities are not calibrated on unseen families and are not described as such. |
| 1 met, 2 not | The head beats a fixed ratio but not a tuned rule by an established margin. |
| 1 not met | No established gain on unseen families. More families are not the remedy; the next step is a design change, tested on `pop_s`. |

In every case the result is about rollout-supervised training in a forked simulator, which a
real network cannot provide. It says nothing about native feasibility.

## Reproduce

```bash
make jevbwe-typed-replication TYPED=results/regen   # needs the frozen V3 run under results/regen
```

## Results

Run on 2026-10-08 from commit `f305c90`, once, with no source change between the registration
and the last of the four commands (`results/v3-replication.log`). The registered model and
population hashes matched. Replaying all 19,200 learned episodes with rollouts switched off
reproduces every outcome (largest difference 0), and recomputing the payoff-weighted rule from
the recorded probabilities reproduces every executed option.

### Panel means (48 families, 16 traces each, five model seeds)

| Method | Utility | Unsafe intervals |
|---|---:|---:|
| fixed 0.90 | 0.092 | 7.30% |
| fixed 1.00 (best fixed ratio on this panel, in hindsight) | 0.103 | 7.71% |
| **fixed 1.05** (selected on training families; the comparator) | **0.096** | 8.07% |
| fixed 1.10 | 0.095 | 8.27% |
| tuned rule `delay(1.05, 0.8, 15 ms, 5 ms)` | 0.096 | 7.96% |
| RLCD head, payoff-weighted (`choice_rlcd_bayes`) | 0.115 | 7.81% |
| exact-gradient head | 0.115 | 7.83% |
| regression head | 0.117 | 7.81% |
| hindsight oracle | 0.203 | 7.31% |

Utilities are lower than on the hand-written panels because the population is harsher: its
median capacity is about 1.0 Mbps and 6.9% of control intervals violate a constraint whatever
the sender does (more than 10% in 14 families).

### Pre-specified criteria

| # | Criterion | Result | Met |
|---|---|---|---|
| 1 | Gain over fixed 1.05; both family-level intervals exclude zero | +0.019; bootstrap [+0.006, +0.036]; t [+0.005, +0.034]; 32/48 families positive | yes |
| 2 | Gain over the tuned rule; both intervals exclude zero | +0.020; bootstrap [+0.005, +0.036]; t [+0.004, +0.035]; 30/48 | yes |
| 3 | Pooled ECE at most 0.05 | 0.138 (accuracy 0.816 at confidence 0.947); family-level interval [0.098, 0.188] | **no** |
| 4 | Upper end of the unsafe-share difference at most +1.0 point | -0.26 points; family-level interval [-0.38, -0.16] | yes |

By the table fixed in advance this is the row "1 and 2 met, 3 not": the gain replicates, and
the reported probabilities are not calibrated on unseen families.

### Secondary

| Quantity | Result |
|---|---|
| Head minus the hindsight-best fixed ratio (1.00) | +0.012, t [-0.005, +0.029]: includes zero |
| RLCD minus exact-gradient head | +0.000, t [-0.001, +0.001] |
| RLCD minus regression head | -0.002, t [-0.006, +0.003] |
| Payoff-weighted minus `map` and `gated` rules | +0.002, t [-0.012, +0.015] |
| Hindsight oracle minus fixed 1.05 | +0.108, t [+0.080, +0.136]; the head realises 18% of it |
| Tuned rule minus fixed 1.05 | -0.000, t [-0.004, +0.004] |
| Leave-one-family-out range of the gain | +0.014 to +0.021 |
| Family ECE | 0.004 to 0.660, median 0.116; above 0.05 in 35 of 48 families |
| Decisions that leave the base ratio | 7.1% |

**Action-sensitive families** (hindsight oracle gains at least 0.02 over fixed 1.05): 36 of 48.
On them the head gains +0.026 over the fixed ratio (t [+0.008, +0.045], bootstrap
[+0.009, +0.047], 30/36 positive) and +0.026 over the tuned rule (t [+0.006, +0.046], 23/36).
Diagnostic only, as registered.

### What the result does and does not show

- **An established but small gain on unseen families.** This is the first panel in the track
  where the family-level t interval excludes zero for families the head never trained on, and
  it does so against a tuned reactive rule as well as against the fixed ratio. The estimate,
  +0.019, is about a third of the +0.054 measured on V3's twelve hand-written families and far
  below the +0.126 measured in distribution.
- **Part of the gain is a lower average ratio.** On this population the ratio selected on
  training families (1.05) is no longer the best fixed ratio: 1.00 scores 0.007 higher. Against
  1.00 the head's gain is +0.012 and not established. The train-selected ratio is the
  registered comparator and the hindsight-best ratio is an oracle, but the reading "the head
  adapts where a fixed ratio cannot" is supported for only part of the +0.019.
- **The gain is concentrated.** Nineteen families differ from the fixed ratio by less than
  0.005, eleven gain more than 0.02, one loses more than 0.02 (-0.047), and one family supplies
  +0.265. The seven families with persistent loss gain nothing on average (-0.001), as the
  estimator pins the rate there. The four largest gains are on links with a buffer well below
  the default depth. Split by buffer depth, the 15 families below 0.7 times the default gain
  +0.046 of an oracle headroom of +0.142; the 18 between 0.7 and 2 gain +0.004 of +0.069; the
  15 above 2 gain +0.011 of +0.119. These observations were made after the result and are a
  description, not a finding.
- **Calibration fails.** Confidence 0.947 against accuracy 0.816. Pooled ECE doubles relative
  to V3's test families (0.070 to 0.138). The payoff-weighted rule still acts sensibly because
  it weighs probabilities by payoffs, but nothing here supports calling the probabilities
  calibrated outside the training distribution.
- **No evidence for RLCD-specific training**, for the third time: exact-gradient and regression
  controls are indistinguishable from the RLCD head.
- **The spread was overestimated.** The power calculation assumed a family standard deviation
  of 0.092; the population's is 0.049, so the interval half-width is 0.014, not 0.027.
- Simulator only. The labels behind these models are hindsight rollouts, which a real network
  cannot provide. Nothing here is a native result and the typed controller is not promoted.

### Status of the data

`pop_r` has now been read and is a development panel. `pop_s` remains sealed: no controller,
fixed ratio or oracle has run on it. `pop_d` remains the development pool.

Tracked summaries: `results/jevbwe-typed-v3-replication/{config,report,audit_test,test_isolation}.json`
and `results/jevbwe-typed-v3-replication-baselines/report.json`.
