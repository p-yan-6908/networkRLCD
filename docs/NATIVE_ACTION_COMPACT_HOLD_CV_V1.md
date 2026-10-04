# Compact regularized hold forecasters V1 — development, not deployment

## Measured blocker and boundaries

The [fresh randomized-hold experiment](NATIVE_ACTION_EXCITATION_V1.md) broke
near-total previous-cap coupling but failed 1% action-conditioned utility skill.
Its 23,746-parameter neural forecasters fit utility MSE 0.0001508 / 0.0001226,
versus 0.0135382 / 0.0163073 on held physical groups: **89.75× / 133.02×** gaps.
Both fit/held folds contain **both films**, not simple leave-one-film-out tests.
This is measured poor generalization, not unique causal attribution to width.

`results/jobs/native_action_hold_response_diagnosis.py` reuses already verified
raw and numeric evidence, hashing the 118 actual inputs it consumes. All **672
cohorts / 8,071 requests** have native-valid, same-stream/same-cap counter
intervals wholly inside the frozen 200–600-ms post-ACK window: observed coverage
305.2–345.1 ms (mean 319.09 ms). There are **45 matched group/epoch/phase**
900-vs-300 strata. Descriptive mean sender payload differences are positive
across both films/all phases (0.1202–0.2970 Mbps); quality differs by context,
including a negative Tears-of-Steel recovery contrast. Matched captures still
have preceding-action/clock confounding: these are **not paired causal quality
estimates or observed counterfactual labels**.

The preserved sender schema has **no encoder target bitrate or QP sum**.
`bytesSent` is RTP payload sent, not a frame-specific encoding target or proof
that 200–600 ms is the correct encoder-response horizon. Model-only within-state
900-minus-300 potential predictions were negative in both old folds; these are
forecaster estimates, never counterfactual truth. No diagnosis label is added to
a controller and no old capture, fit, selected calibration or default is changed.

## A single versioned model repair, not a hidden hyperparameter sweep

- `configs/native_action_compact_hold_cv_v1.json` freezes one data-informed
  **training-development** recipe before this fit. The already inspected training
  folds informed it; they are **not new independent validation**.
- `src/media_rl/native_action_compact_hold_cv.py` projects causal 32×23 sender
  history into latest step, last-eight mean, full-history mean and standard
  deviation: **92 features**, no source/group ID, phase, capacity, future RGB,
  evaluation labels or augmented observation meaning.
- Three proposed-cap features are standardized along with compact state, using
  **fit-fold-only** statistics and the same 0.05 scale floor. Blind inputs are
  zero before normalization and their three input-weight rows stay exactly zero.
- Width **8**, explicit weight L2 **0.01**, original weighted utility-MSE plus
  miss-log-loss, same 1,200 updates, batch 128, learning rate 0.001 and seeds
  6601/6611/6621. Each forecaster has **786 parameters versus 23,746**, a 30.21×
  reduction. Biases are not regularized; original shared network code is untouched.
- The exact old hold-CV cache/manifest, original eight physical-group folds,
  all zero-utility/missed outcomes and 1% necessary action-skill threshold remain
  fixed. **Six new conditional and six matched blind forecasters** are saved;
  no prior forecaster is refitted or replaced, and no native peer is recollected.
- The forecasts are an auxiliary ABI. The real native action-outcome bundle
  validator rejects **all twelve actual compact models**. They are not an actor,
  trained critic, selected risk calibrator or an accepted deployment bundle.

## Actual result — generalization improved, action information still fails

| Metric | Fold 0 | Fold 1 |
|---|---:|---:|
| Old conditional held utility MSE | 0.0135382 | 0.0163073 |
| Compact conditional held utility MSE | 0.0055787 | 0.0073386 |
| Relative held utility MSE reduction | **58.7932%** | **54.9981%** |
| Compact held/fit utility MSE ratio | 1.3248× | 2.3482× |
| Compact blind held utility MSE | 0.0053953 | 0.0073431 |
| Conditional-versus-blind action utility skill | **−3.3981%** | **+0.0615%** |
| Action-prior utility skill | +52.7901% | +64.4982% |
| Action-prior risk skill | +50.0521% | +68.4640% |

The model repair **mitigates memorization on reused training development folds**.
It does not establish reliable action value: both folds still fail 1%. The
original action-average-prior proxy becomes green, despite this failure. **Do
not promote this model on that proxy or present the development improvement as
native/controller/causal/SOTA gain.** Independent future native calibration,
repeatability, held-out testing and genuine published-peer comparison remain open.

## Verification and commands

- **17 new pure response-diagnostic tests**: exact whole-window sampling,
  missing/reset counters, stream/cap changes, real zero FPS, valid clocks, bias
  decomposition and distinct rate/request denominators.
- **18 new compact-model tests**: causal projection, invalid support/config/role,
  L2 weights, actual synthetic neural action learning, train-only normalization,
  blind invariance, strict native-auxiliary boundary and no input mutation.
- Public numeric audit recomputes both original folds from all twelve actual saved
  weights: projected normalization, groups/seeds, errors/action priors/pass flags.
- A separate **extracted-wheel `-I` / temporary-cwd** probe checks exact imported
  source/dependency hashes, actual numeric replay, all twelve native-ABI
  rejections, and **five resealed forgeries** (MSE, pass flag, normalization,
  blind-action weights, groups). Old seven source hashes, V2 weights, failed
  qualification and earlier negative CV/hold artifacts remain unchanged.
- `results/native-action-compact-hold-cv-v1/report.json` and
  `results/jobs/native-action-compact-hold-cv-package-proof-v1.json` contain actual
  frozen results. `results/jobs/native-action-hold-response-diagnosis-v1.json`
  retains the counter/group/model decomposition and its limitations.

```sh
# Completed output: reference only; DO NOT rerun fitting into it.
.venv/bin/python -m media_rl.native_action_compact_hold_cv run \
  --config configs/native_action_compact_hold_cv_v1.json \
  --source-cv results/native-action-hold-value-cv-v1 \
  --out results/native-action-compact-hold-cv-v1
# Read-only saved-model verification, no refit:
.venv/bin/python -m media_rl.native_action_compact_hold_cv audit \
  --run results/native-action-compact-hold-cv-v1
```

## Follow-up availability implemented — response lag still open

The [separate encoder sidecar and one conventional native probe](NATIVE_ENCODER_RESPONSE_V1.md) now supply actual target/QP on **169/169 samples** and **167 valid same-cap intervals**, with complete original native raw/extracted-wheel replay and six resealed-forgery rejections. Under fixed 450-kbps control the target spans **232.5–450 kbps**. This removes the missing-telemetry blocker for future experiments without altering the old ABI or these negative models. The following motivation remains historical; the next mechanism check is preregistered response lag/repeatability, not another availability panel.

### Original motivation and still-required causal boundaries

[Current W3C WebRTC statistics](https://www.w3.org/TR/webrtc-stats/) define
`targetBitrate` as an instantaneous encoder setting; actual sent payload only
correlates with it. `qpSum` is codec-dependent and needs encoded-frame deltas;
aggregate stats do not identify a specific source frame's causal response.
[The peer-connection specification](https://www.w3.org/TR/webrtc/) does not
promise every statistic exists. The historical
[`totalEncodedBytesTarget` removal discussion](https://github.com/w3c/webrtc-stats/issues/653)
means it must not be presumed current or supported.

Before more models or full capture panels, add a **separate, identified,
nullable encoder-stat sidecar** to a new collector namespace and run one bounded
conventional availability/response probe. Preserve the exact existing 16/23-step
observation and ACK-age semantics. Bind stream/SSRC/stats timestamp, sample and
control ACK clocks, target bitrate, encoded-frame/QP/byte counters, resolution,
quality-limitation reason and supported/absent statuses. Do not pad missing
fields or call `maxBitrate` readback a target measurement. If actual target/QP
are available, prospectively compare response lag bands under longer safe holds;
retain identical-policy controls, all failures and original request/quality
cutoffs. Until then, no defensible encoder-horizon or learned-policy promotion
follows from this experiment. **The SOTA goal remains unachieved.**
