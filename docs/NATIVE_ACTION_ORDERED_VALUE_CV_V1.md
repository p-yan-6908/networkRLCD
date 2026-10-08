# Single predeclared ordered-history training ablation V1

**One train-only feature ablation completed. The full action-information gate still fails. No native actor/default, validation, collection or SOTA qualification.** This is the completed experiment after the [fixed-model diagnosis](NATIVE_ACTION_ATOMIC_DIAGNOSIS_V2.md), not an automatic sweep or a selected deployable model.

## Prospective scope and controlled implementation

`src/media_rl/native_action_ordered_value_cv.py` exposes `predeclare`, `fit` and `audit`. The standalone plan `results/native-action-ordered-value-cv-v1-plan.json` was written before any new fit, SHA **`f83a8faade8ba214db12768925872bbe1b9aae36a2f93cf29bc55f615c89344f`**. It binds the fixed contract, executing source hashes, canonical row fingerprint, exact physical folds, all 65 prior role inputs, source manifest `25cd60b6…` and unchanged original 95-input CV manifest `7b9c9d2c…`.

Only the legal **280 training rows / 3,400 requests / 12 physical groups** are reused: 160 old rows plus 120 fresh atomic cohorts. Every state, cap, factual target, weight, group, lossless episode ID and fold matches the original cache. No validation/calibration/diagnostic targets, filtering, new collection or original-model refit is used.

The original 736-state/32-by-23 observations and three proposed-action fields are unchanged. The opt-in projection adds 23 full-history OLS sample-index trends to the original 92 summaries: **115 state summaries / 118 total inputs / 970 parameters** instead of 95 inputs / 786 parameters. It is sample order, not elapsed time or future encoder response.

A naive wider initializer would consume extra random draws and change subsequent minibatches. This experiment instead initializes the exact original seeded 95-input network, then inserts **23 zero, learnable trend-weight rows** between the 92 state and three action rows. All old weights, head weights, biases, zero Adam moments and RNG state are preserved; three-seed tests verify identical subsequent draws and initial predictions. The same minibatch stream is used; the added paths actually learn. This controls the initialization/sampling confound, but does not separately distinguish chronology from the additional representational capacity.

Original fit/predict/evaluation bytecode is reused without changing the optimizer, losses, group-uniform sampler, 128 batch size, eight hidden units, 1,200 updates, seeds 6601/6611/6621, fit-only normalizers, two physical folds, request weights or acceptance thresholds. Only the explicit input-geometry guard is widened. Twelve new auxiliary models are saved, with matched conditional/action-blind controls; every blind proposal input and its last three weight rows remain zero. Original 95-input models are not refitted.

## Actual mixed result — not a green qualification

The new immutable artifact is `results/native-action-ordered-value-cv-v1/`; manifest **`1c63e0d611309114dc1d91d58284ae346d923b182bbf8a89b64add262d91b963`**.

| Request-weighted utility action skill | Original 95 inputs | Ordered 118 inputs |
|---|---:|---:|
| Pooled | −1.077883% | **+1.313493%** |
| New balanced cohorts only | +1.724635% | +2.164054% |
| Sintel | −0.134749% | **+0.145139%** |
| ToS | −4.844507% | +2.497659% |
| BBB | +2.974376% | +14.451924% |

Both ordered folds exceed the unchanged 1% action-skill threshold: **+1.891011% / +1.053226%**. Pooled skill rises by **2.391376 percentage points**; conditional pooled utility MSE decreases **.02341620 → .02301597**. However, conditional MSE on new balanced data **increases .02983483 → .03075883**, and Sintel conditional MSE increases slightly. Better conditional-versus-blind skill alone is not uniformly better prediction or native QoE.

The **full unchanged gate is false**:

- Sintel action skill **+.145139%** is below the required **1%**.
- Sintel prior-utility skill **−1.167682%** is below the required **1%**.
- The fixed physical-group 1,024-resample 95% action-skill interval is **[−4.127676%, +7.984837%]**; its lower endpoint is not positive.

All films/folds/rows and thresholds remain. No failed stratum is dropped and no positive partial metric overrides these failures. These reused training folds are not independent replication, causal counterfactual labels, selected all-request risk calibration, safe native learned-quality improvement or a strong peer/SOTA comparison.

## Verification and preservation

**15 targeted source-only Python cases** cover exact old algorithm/scalar-recipe/gate preservation, three-seed initialization and RNG equivalence, real learnable trend paths, proposal-blindness, normalization, role/recipe/geometry/SOTA rejection, and zero-over-zero false-green protection. Short three-update mathematical fixtures cannot pass the public 1,200-update provenance guard.

The actual public audit checks the complete 17-artifact layout and recomputes canonical rows, fit-only normalizers, model/OOF/prior predictions, all film/fold/physical-group bootstrap metrics and the exact negative gate. It also **deterministically reproduces every weight and the full saved loss trace of all 12 fixed 1,200-update new fits**, and replays the complete original native source. These are verification replays, not additional recipes or original-model refits.

An extracted-wheel **`python -I` / temporary-cwd** replay passes with every relevant module loaded only from the wheel. **Ten fully resealed real semantic forgeries** are rejected: plan role, recipe, cached target, model seed, fit normalizer, held OOF, gate flag, early loss trace, coupled model weights plus all forward-consistent OOF/report numerics, and SOTA flag. The coupled attack passes forward consistency but fails deterministic training reproduction; a green seal alone is insufficient.

Actual proof: **`results/jobs/native-action-ordered-value-package-proof-v1.json`**. Wheel SHA: `8013f10b575a76b0e2b5b59dd8acadb929df7401f502fcd0cd32d12a084cee57`. Before/after checks preserve all actual new artifacts/plan, original source/CV/diagnoses/package receipts, **14 original code hashes and 65 prior role inputs**. Concurrent edits were rechecked; current hashes match, and this session did not restore or overwrite those configurations.

## Public commands

```sh
python -m media_rl.native_action_ordered_value_cv predeclare --source results/native-action-atomic-matrix-v4 --baseline results/native-action-atomic-value-cv-v4 --out results/native-action-ordered-value-cv-v1-plan.json
python -m media_rl.native_action_ordered_value_cv fit --plan results/native-action-ordered-value-cv-v1-plan.json --out results/native-action-ordered-value-cv-v1
python -m media_rl.native_action_ordered_value_cv audit --run results/native-action-ordered-value-cv-v1
```

The first two immutable outputs already exist; do not overwrite them or interpret the commands as authorization for another trial. The module ships through the existing `src/media_rl` wheel package; no actor integration or default CLI/controller selection is added. The separate feature-only module still has no fitter or predictor.

**This experiment is closed; further experiments are not started.** The broader SOTA objective remains unachieved and was cleared by the user. Work stops here as requested.
