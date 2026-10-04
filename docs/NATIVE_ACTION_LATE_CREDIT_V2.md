# Native randomized long-hold / late factual credit V2

## Scope and actual conclusion

The [V1 mechanism probe](NATIVE_ENCODER_LONG_HOLD_V1.md) measured upward
encoder-target crossing at 1.16–1.60 seconds, versus 101–112 ms downward. The
old 200–600-ms/~800-ms randomized-hold contract therefore often labeled upward
actions before their encoder response. This **combined hold/credit repair** was
frozen before prospective collection; no old label, source, model or threshold
was edited.

**48 new conventional Chrome/VP8 training peers, 160 late factual cohorts /
1,944 requests and eight original physical groups** complete. With the already
fixed [compact neural recipe](NATIVE_ACTION_COMPACT_HOLD_CV_V1.md), action
conditioning now improves held utility MSE over matched state-only controls by
**1.4258% / 6.8950%**, passing the unchanged **1% necessary development
criterion in both original physical folds**. This is genuine saved neural
prediction evidence, **not independent validation, a native controller, causal
quality acceptance or SOTA**. The first fold clears the threshold only narrowly;
there are still only eight physical groups. Old failed qualifications remain
failed and all old model/default bytes remain unchanged.

## Frozen prospective intervention

- `src/media_rl/native_action_settled_hold.py` and
  `benchmarks/native_rtc/settled_hold_control.mjs` define a new auxiliary
  `native_late_credit_randomized_hold_v2` contract. Despite the implementation
  name, **late is not proof of settled target or quality**.
- Each film retains its complete original 24-peer training protocol: four
  physical video-segment/network schedules, both randomized aliases and
  interleaved fixed450 controls, original order and seeds. Source SHA, nominal
  training/collapse/recovery roles and cropping are bound to original parents.
- Random assignment is the same counter-uint32 seed/epoch-only mixer over
  **300/450/900 kbps**, but with **32-step (~3.2-second) holds**. Aliases share the
  assignment schedule; separate real captures are not counted as new physical
  groups. No content, network oracle, future RGB/quality or target/QP selects
  the action.
- Credit is fixed to **1800–2200 ms after the first held-action ACK**. The
  **200–600-ms early reference** remains on the *same fresh capture* with
  disjoint source IDs. Every last request's unchanged **150-ms deadline** must
  precede the next action observation/cutoff. No future-action mixtures,
  in-flight previous-action outcomes or counterfactual labels enter either
  cohort builder.
- The original native raw/cohort implementation code objects, feedback and
  actor-observation schema, ACK/readback, sampled on-time PSNR utility and
  missed/zero outcomes are reused unchanged. The collector is an exact
  three-anchor projection of the frozen encoder-response producer; the
  independent nullable sidecar is never an actor feature.
- **Target crossing/attainment is diagnostic, never a row eligibility or state
  feature.** All qualifying factual requests—including misses, zero outcomes,
  unsupported/censored or below-target response—are retained. Longer holds
  alone do not establish a universal response horizon.

Configs: `configs/native_action_settled_hold_train_{sintel,tos}_v2.json`.
Actual parents: `results/native-action-settled-hold-train-{sintel,tos}-v2/`.
Both config mtimes precede actual first-peer capture starts; exact source and
config hashes are independently checked during run/replay.

| Actual training film | Late cohorts / requests | Cap counts 300/450/900 | Changed action | Below-90%-target cohorts retained |
|---|---:|---:|---:|---:|
| Sintel | 80 / 969 | 24 / 28 / 28 | 75.0% | 16 |
| Tears of Steel | 80 / 975 | 36 / 24 / 20 | 62.5% | 26 |

All 160 cohorts have observed target samples; **42/160 still have partial or
absent 90%-cap target attainment**. They remain in fitting. Do not describe
this as universally settled encoder behavior or replace maxBitrate readback
with an actual target measurement.

## Fixed once-only new-data neural comparison

`src/media_rl/native_action_late_value_cv.py` has separate public `run` and
`audit` commands and auxiliary model ABI. Its exact fitter/predict code objects
reuse the compact recipe: **92 causal state summaries + three proposal inputs,
8 hidden units, 786 parameters, weight L2=0.01, 1,200 updates, seeds
6601/6602/6603, unchanged loss/request weighting/group bootstrap**. Normalization
uses only actual fit rows. Blind models have exactly zero proposed-action
inputs and first-layer weights; historical own action remains legitimate
state. No encoder target/QP or future label is added to state.

The config `configs/native_action_late_value_cv_v2.json` was frozen before this
once-only fresh-data fit. Both entire source panels undergo complete public
native/raw/credit replay before fitting. Only original train-role randomized
late cohorts enter; old excitation/compact labels and calibration,
diagnostic, independent-validation/test labels do not. The two exact physical
folds are pinned to the original hold-CV receipt
`5cafe0fdff1a6c3527848cfd27f0d4dc1db4c754a44c3931327dde0abc7966e0`.
No post-result horizon, hidden size, seed, fold, cap, threshold or row tuning.

| Original physical fold | Conditional held utility MSE | Matched blind MSE | Necessary action utility skill | Action-prior utility / risk skill |
|---|---:|---:|---:|---:|
| 0 | 0.0116371555 | 0.0118054734 | **+1.4258%** | +25.1128% / +32.8325% |
| 1 | 0.0137454111 | 0.0147633504 | **+6.8950%** | +22.4738% / +30.7757% |

Twelve new forecasts are saved at `results/native-action-late-value-cv-v2/`.
The original prior proxy also passes, but the relevant necessary criterion is
**conditional versus matched blind**, not beating the action prior. The
combined temporal intervention passes this training-development check; it
does not separately identify the causal contribution of hold length versus
credit timing or prove repeatable deployed control.

## Physical diagnostic, not counterfactual quality

`results/jobs/native-action-late-credit-diagnosis-v2.json` is a separate
read-only matched-same-hold, different-time analysis, not a new fit or selected
native experiment. For 900 kbps, mean within-epoch target attainment increases
**0.116→0.750 Sintel / 0.100→0.563 Tears of Steel**, and whole-interval
frame-weighted VP8 QP decreases **63.15→46.15 / 69.98→54.06** between the fixed
early and late windows. Factual utility/miss also evolves, but **content/time/
network-phase confounding remains**. Different-time bands are not paired
counterfactuals, target/QP evolution is not causal quality proof and no weak
or censored cohort is screened away.

## Verified evidence and replay

- Original implementation/native future-action/quality/deadline guards are
  reused; pure collection tests cover exact identity, seed-only aliases,
  support and late/reference source/window/deadline separation.
- **30 Python / two Node checks pass** across the new collection/control/CV
  surface. Thirteen additional CV tests cover actual neural synthetic action learning,
  matched blind invariance, exact 786-parameter geometry, unchanged
  role/credit/threshold/source/recipe guards and native ABI rejection.
- Public saved-model audit regenerates every fresh canonical row, checks exact
  cache/source/fit-fold normalization and all twelve model shapes/provenance,
  recomputes both errors/priors/flags, then independently replays **all 48
  complete original native peers** before success. No refits/captures.
- The actual **extracted-wheel / `-I` / temporary-cwd** replay covers those same
  complete source semantics, 160/1944 rows and twelve saved models. All twelve
  fail the actual native actor ABI. **Seven resealed forgeries** are rejected:
  MSE, pass flag, fit normalization, blind action weights, early credit,
  network geometry and dropped cache row. No manifest-only or actor-stub
  acceptance.
- `results/jobs/native-action-late-value-package-proof-v2.json` binds actual CV
  manifest `d33bbf484f15d90af7875ac0d6baad52ca192c0222cdc8c8cfe7ff3ad7c67ddf`
  and both full training-parent manifests. It verifies earlier source hashes,
  old V2/failed qualification, availability, negative compact and timing
  artifacts remain unchanged. The original new-data negative remains negative.

```sh
# Read-only complete native/credit data replay:
.venv/bin/python -m media_rl.native_action_settled_hold audit \
  --run results/native-action-settled-hold-train-sintel-v2
.venv/bin/python -m media_rl.native_action_settled_hold audit \
  --run results/native-action-settled-hold-train-tos-v2
# Read-only actual saved neural and complete source replay; no refit:
.venv/bin/python -m media_rl.native_action_late_value_cv audit \
  --run results/native-action-late-value-cv-v2
```

Do not rerun/overwrite immutable completed collection/fit/proof artifacts.

## Subsequent immutable prospective validation

The separate [V3 frozen all-training forecast check](NATIVE_ACTION_LATE_VALIDATION_V3.md) now completes **24 fresh conventional peers / 80 late cohorts / 971 requests / four new physical contexts**, preserving this version's recipe/credit/thresholds and exact old artifacts. **It fails replication: +0.5366% pooled / −2.2405% held-out Sintel / +1.5466% wholly unseen BBB**, physical-group interval **[−6.7420%, +2.5261%]** crosses zero; risk also loses to matched blind. All-role source reservations find ToS exhausted; a new original licensed full-credit BBB source supplies held-out content without relabeling old roles. Complete raw/public/isolated-wheel/numerical and resealed-forgery proof passes, not the science gate. This positive development result is not transferable native action-value acceptance; no retuning/promotion/default change or SOTA follows.

## Remaining acceptance boundary

**Necessary training action information is now observed under the versioned
late-credit recipe.** This removes the previous *development* learning failure
for this corpus, not every model/data/native-control blocker. Next, predeclare
and freeze a complete candidate and decision/hold/credit ABI, verify it on
role-disjoint prospective physical contexts without retuning, and assess
selected-action confidence on the actual early/transient as well as late
request distribution before any native controller promotion. This auxiliary
late-only risk forecast is **not** safety calibration for all requests.
Repeated safe native gain (including steady quality), independent/final
evidence, representative natural/measured panels and genuine published
learned-peer comparisons are still required. **V7/defaults and previous
negative evidence remain unchanged; `native_deployment_qualified=false` and
`SOTA_achieved=false`.**
