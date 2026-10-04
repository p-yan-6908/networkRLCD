# Randomized action holds and credit-horizon test V1

## Current status — completed exposure intervention, learning check failed

V2's [action-value check](NATIVE_ACTION_VALUE_SKILL_V1.md) failed: utility skill
relative to an identical action-blind control was +0.7437% / -0.3649%, and
98.0851% of fitting actions matched prior own caps. Neither old weights nor
native failure/diagnostic labels are refitted here.

The separate, prospectively frozen **48 Chrome/VP8 train peers now complete**
and pass full original-code public raw replay: **672 uncontaminated hold-credit
cohorts / 8,071 requests**, all three caps represented and **69.6429%**
changed-action cohorts (Sintel 70.2381%; Tears-of-Steel 69.0476%). Factual
action equals previous own cap in only 30.3571% of new cohorts, versus 98.0851%
of old immediate-horizon rows; these are different credit recipes, not a causal
quality comparison. The data-exposure defect is addressed, **not value learning**.

The fixed 1% action-conditioning test **still fails**: **+0.2274% / -4.4866%**
relative utility skill versus matched action-blind forecasts. Original action-
average-prior utility skill is -14.5683% / +21.1104%, and risk skill -10.4055% /
+50.7174%; that proxy also fails. All six new conditional and six new blind fits
are preserved and numerically replayed. No candidate is promoted or previous
conditional/risk weight refitted.

| Source | Randomized A/B utility | Fixed450 utility |
|---|---:|---:|
| Sintel | 29.7333 / 29.3986 | 31.3700 |
| Tears-of-Steel | 21.2247 / 20.9629 | 20.4523 |

The nominal Sintel harm and contrasting source outcomes are retained. More
excitation and a longer uncontaminated label window alone did not fix the
model's held-out value skill. Encoder-response/credit/representation separation
remains a measured-next-diagnosis question, **not an attributed causal fix**.
The original eight physical source/network groups are reused, not replaced by
48 independent samples. Existing sources, roles, defaults, cutoffs, weights and
negative native/learning results remain unchanged.

## New mechanism and fixed boundaries

- Seed/epoch-only counter mixer assigns **300/450/900 kbps** for eight sender
  decisions at a time. No capacity, evaluation labels or future observation
  values choose the treatment. This is deliberate conventional **training
  exploration**, not learned/safety-qualified control or a deployed policy.
- Two randomized aliases intentionally share each group/repetition's assignment
  sequence; fixed450 is an equal-shadow conventional control. Actual parameter
  readback is verified. A bitrate cap does not prove actual encoder target-rate
  response, original RTC competitor actuation or a causal quality benefit.
- A cohort uses its **pre-action causal state**, a completed acknowledged cap,
  and original source-request labels born **200–600 ms after that ACK**. Every
  included 150-ms request deadline must finish before the next epoch's earliest
  observed control opportunity or capture cutoff. Partial/mixed-future-action
  epochs are dropped with explicit reasons, never reassigned to another action.
- Source IDs, decision/ACK clocks, proposal/readback/source caps and unique,
  non-overlapping requests are checked. Transition-inflight requests are
  explicitly excluded irrespective of outcome; zero utility and missed
  deadlines are retained. Pixel/request/deadline/quality definitions do not
  change. Causal input reconstruction never consumes future source RGB.
- The **entire original Dense raw verifier code object** is retained in a copied
  namespace with the new ABI/recipe/control binding; no existing globals/files
  are monkeypatched. Namespace-only collector/video projections have exact
  anchor counts. Full original transport/admission/source/feedback/actuation
  checks precede the added cohort checks.
- Parent identity, original train role, source/movie reservation, seeded trial
  order, implementation snapshots and child/parent seals are bound. Calibration,
  diagnostic, selected, validation and test parents cannot be relabelled.
- `excitation_observed` is merely a data-exposure check (all three caps and at
  least 40% changed-action cohorts). It is **not model qualification, native
  improvement, selected calibration, causal-effect proof or SOTA**.

## Frozen plans and public APIs

- `configs/native_action_excitation_train_sintel_v1.json`
- `configs/native_action_excitation_train_tos_v1.json`
- Frozen `src/media_rl/native_action_excitation.py`: `plan_excitation`,
  `run_excitation`, `build_cohorts`. Its inherited parent-audit snapshot lookup
  retains a Dense filename and is superseded only for replay by the separate
  `src/media_rl/native_action_excitation_audit.py`: `audit_excitation`.
- `benchmarks/native_rtc/excitation_episode.mjs`, `excitation_control.mjs`,
  `streamed_excitation_video.mjs`: separate collector/control/source namespace.

```sh
.venv/bin/python -m media_rl.native_action_excitation study \
  --config configs/native_action_excitation_train_sintel_v1.json \
  --out results/native-action-excitation-train-sintel-v1
.venv/bin/python -m media_rl.native_action_excitation study \
  --config configs/native_action_excitation_train_tos_v1.json \
  --out results/native-action-excitation-train-tos-v1
```

Completed/partial directories and plans are immutable: do not rerun into them,
replace a failed outcome or modify a frozen source while collecting. Both source
panels must execute serially to avoid competing native captures.

## Preregistered new-data learning experiment — completed negative result

The first public replay stopped **before output creation or any fit**, because
the inherited parent audit looked for `sources/templates/dense_episode.mjs`,
while the frozen producer correctly archived its hash-pinned original coverage
template. A separate read-only auditor changes **exactly that one literal** to
`sources/templates/coverage_episode.mjs` in a copied namespace. Parent verifier
bytecode, complete original raw callback, all other constants/checks, frozen
producer, templates, sealed data and scientific CONFIG remain unchanged. No
compatibility alias files or regenerated outcomes are written. The original
failed log is retained. The new CV loader records the adapter's source SHA.

```sh
.venv/bin/python -m media_rl.native_action_excitation_audit \
  --run results/native-action-excitation-train-sintel-v1
```

Completed output commands below are documentary: **do not rerun fits**.

`configs/native_action_hold_value_cv_v1.json` and
`src/media_rl/native_action_hold_value_cv.py` declare a train-only comparison
before inspecting actual collection outcomes:

- Full public raw replay of both new completed parents is required.
- Only fresh randomized aliases enter fitting; fixed450 and all old immediate-
  horizon/calibration/diagnostic/selected/validation/test rows are excluded.
- Original eight grouped folds, seeds 6601/6611/6621, 1,200 CV updates, request
  weighting, architecture, loss, train-only normalization and **1%** action-value
  minimum are preserved. There are six **new-data** conditional and six matched
  action-blind CV fits, once. Previous completed conditional fits are not redone.
- All twelve actual fit weights are saved. A read-only numerical auditor
  recomputes both fold predictions, utility/risk MSEs, action-average priors,
  normalizations, group identities, proposal-input zeroing, skill and pass flags.
- Even passing predictive skill cannot unlock a native actor: these are auxiliary
  forecasters, **not** an accepted deployment bundle or a reused selected-risk
  calibrator. Actual causal response, sufficient support, new candidate training,
  selected-native calibration, repeated controls, independent validation/final
  tests and genuine published competitors remain separate open requirements.

```sh
# Only after both new native training parents complete and audit.
.venv/bin/python -m media_rl.native_action_hold_value_cv run \
  --config configs/native_action_hold_value_cv_v1.json \
  --train-run results/native-action-excitation-train-sintel-v1 \
  --train-run results/native-action-excitation-train-tos-v1 \
  --out results/native-action-hold-value-cv-v1
.venv/bin/python -m media_rl.native_action_hold_value_cv audit \
  --run results/native-action-hold-value-cv-v1
```

## Verified implementation evidence, not native efficacy

- **67 distinct Python checks**: 21 new control/cohort/role tests, 27 adjacent
  original coverage regressions, 16 positive/negative saved-weight CV/tamper
  invariants and three exact/missing/duplicate parent-path projection checks.
  Six affected CV paths additionally rerun after the adapter fix; no unchanged
  complete fits/captures are repeated. Three new Node checks pass.
- **540 exact Python/JS assignments** match in an independently extracted wheel.
  Both actual 24-peer plans validate; full raw verifier code identity and all
  seven earlier model/qualification source hashes are preserved.
- `results/jobs/native-action-excitation-package-proof.json` records actual
  config/source/wheel hashes and deliberately withholds native/SOTA gain.
- `results/native-action-hold-value-cv-v1/report.json` retains the actual negative
  two-fold new-data result; `results/jobs/native-action-excitation-final-evidence-v1.json`
  verifies all 48 peers, exact source/roles/credit and **1,800 unchanged native
  artifact hashes**, plus both numeric CV folds and old V2/receipt preservation.
- `results/jobs/native-action-excitation-audit-package-proof-v1.json` adds actual
  **12-fit numeric replay from a distinct extracted wheel**, exact imported
  module hashes and unchanged parent bytecode/raw callback with one filename
  adaptation. Original collection wheel/proof remain intact.
- All integrity checks pass; **action-conditioning skill, native deployment,
  causal gain, native improvement, selected calibration and SOTA do not**.

The [official challenge](https://www.microsoft.com/en-us/research/academic-program/bandwidth-estimation-challenge/tips/)
documents the published-peer observation interface. Bounded renewed primary-source
lookup did not supply authoritative paired packet/feature fixtures or an exact
extractor; this is **not proof none exists**. The [receiver contract](RTC_RECEIVER_CONTRACT_V1.md)
still blocks invented/padded/third-party-inconsistent inputs. No foreign SDK,
privileged runtime, cloud/paid job or external upload is used.
