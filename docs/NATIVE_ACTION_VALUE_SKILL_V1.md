# Train-only action-value skill and qualification V1

## Blocker found

V2's original `training_skill_passed` compares conditional outcomes to an
**action-only average prior**, not to an equally trained state-only predictor.
That green flag establishes prognostic prediction but cannot establish that
**proposing a different action adds utility information**. It is not native
policy gain, a causal effect or a SOTA certificate.

The new `results/native-action-value-skill-v1/report.json` compares the saved
conditional CV with six new action-blind controls on exactly the original
**24,335 train rows / 77,929 request weights / eight physical groups**:

| Original physical fold | Conditional utility MSE | State-only utility MSE | Conditional-over-state-only skill |
|---|---:|---:|---:|
| 0 | 0.009000767477 | 0.009068209054 | **+0.7437%** |
| 1 | 0.008465783099 | 0.008435005031 | **-0.3649%** |

**Both folds fail** the unchanged original **1%** minimum skill. The old proxy
still passes. In **23,869 / 24,335 rows (98.0851%)**, the factual cap equals the
previous own cap already encoded in causal state. That overlap is descriptive
weak excitation/support evidence, not by itself proof of confounding, missing
causal effect or a causal remedy. No counterfactual outcomes are available.

The missing qualification check is removed; **the model/data identifiability
and native-control blockers are not fixed**. V2 is rejected by the new explicit
qualification interface. All legacy experiments/defaults remain unchanged;
there is no promotion, new selected calibration, native gain or SOTA claim.

## Exact scope and safeguards

- Fixed `configs/native_action_value_skill_v1.json`: original two physical-group
  folds, seeds 6601/6611/6621, 1,200 CV updates, learner/loss/request weighting,
  architecture and train-only normalization. No retuning to these outcomes.
- Isolated copy of the original fitter replaces the **three proposed-action
  inputs** by exact zero and fixes their input weights to zero. Full temporal
  sender state, including previous cap, is preserved. The old source function
  and all deployed/candidate/risk weights are untouched.
- Original sealed conditional CV is reused, **not refitted**. Only six new
  utility+risk state-only controls are fitted. No calibration, selected,
  diagnostic, repeatability, validation or test labels enter fitting.
- Four candidate-pinned training parents, **144 child seals / 4,176 artifact
  hashes**, are revalidated. The exact original loaders retain causal state,
  role/schema/cap/request/source/clock/alias checks. Prior public raw replay is
  explicitly reused; **this does not rerun or pretend to be a new native audit**.
- Fresh immutable output contains factual `train_rows.npz`, six controls,
  provenance, report and a complete artifact seal.
- `audit_model_value_skill()` independently recomputes weighted held-out
  predictions, utility/risk MSEs, skill, groups, overlap and train-only
  normalizations from the cache and saved controls. It checks candidate and
  original-CV hashes; metadata saying `passed` is insufficient.
- `load_value_qualified_candidate()` and `ValueQualifiedActionPolicy()` require
  a **caller-frozen external manifest SHA** and both-fold utility skill before
  actor initialization. Resealing cannot replace that caller's receipt. Passing
  remains necessary, **not sufficient** for causal gain or native qualification.
- `configs/native_action_value_qualification_v1.json` pins the actual V2 model
  and negative receipt for direct verification. This is an external explicit
  config, not a deployment/default replacement. The existing wheel already
  includes all Python modules; there is no new dependency or native mapping.

## Public commands

Reproduce the auxiliary comparison only into a **new** output directory:

```bash
.venv/bin/python -m media_rl.native_action_value_skill run \
  --model-dir results/native-action-model-v2 \
  --config configs/native_action_value_skill_v1.json \
  --out results/native-action-value-skill-v1-REPRO

.venv/bin/python -m media_rl.native_action_value_skill audit \
  --run results/native-action-value-skill-v1

.venv/bin/python -m media_rl.native_action_value_qualified \
  --model-dir results/native-action-model-v2 \
  --skill-run results/native-action-value-skill-v1 \
  --expected-manifest-sha256 8395df439a62cc57895f4a6da6d0c120cafa5f94ed67e1788d73d569f53f089d
```

A completed negative audit exits successfully as evidence. The actual qualified
actor constructor instead **raises** `action-conditioned utility skill is not
established`. Never interpret a command's success or a sealed directory as a
passing model/SOTA result.

## Verification surfaces

- `tests/test_native_action_value_skill.py`: 19 exact-action-independence,
  fixed-configuration, role rejection, fold isolation, factual-row and false
  proxy-positive invariants.
- `tests/test_native_action_value_qualified.py`: 13 numerical re-verification,
  read-only/positive-constructor, early negative rejection, external receipt
  pinning, reseal replacement and candidate/MSE/normalization/action-weight/
  fold/role corruption cases. Synthetic fixtures are software checks only.
- `results/jobs/native_action_value_skill_package_probe.py`: independently
  extracted-wheel imports, actual original candidate/cache, numeric check,
  actual failed constructor and before/after hashes. No editable-import
  fallback, candidate inference/refit, native recollection or label reuse.

```bash
.venv/bin/pytest -q tests/test_native_action_value_skill.py \
  tests/test_native_action_value_qualified.py
uv build --wheel --out-dir results/jobs/native-action-value-skill-dist
.venv/bin/python results/jobs/native_action_value_skill_package_probe.py
```

Actual verification completes: **89 distinct targeted Python checks** pass
(32 new invariants plus 57 adjacent actor/live checks). The isolated actual-wheel
probe preserves all seven checked source files, old candidate and frozen skill
receipt while rejecting actual V2 before actor initialization. Evidence:
`results/jobs/native-action-value-skill-package-proof.json`. This is software
and necessary learning-qualification evidence, **not new native gain**.

## Next intervention boundary

Do not rerun these completed conditional fits, reinterpret old green proxy
metrics as action value, tune thresholds on native failures, or promote the
existing model after a metadata-only gate. A future version needs separately
preregistered training-only, causally available state/action excitation and
matched credit/response horizons, with no diagnostic/selected/validation/test
label reuse. It must first pass this necessary predictive comparison; action
support, actual encoder actuation, native repeated controls, selected-native
calibration, fresh validation/final tests and original published-peer controls
remain independently required. None is supplied by this stage.
