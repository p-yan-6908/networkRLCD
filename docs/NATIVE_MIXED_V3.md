# Native mixed-dwell V3 — measured steady gain, severe transition loss; not adopted

## Frozen intervention

`configs/native_mixed_training_v3.json` declares **12 fresh train + four separate calibration** owned Chrome/VP8 episodes, 30 seconds each. Three training schedule families each have four behaviors: **250 ms / 1,000 ms / 4,000 ms** seeded permutations of all seven zero-target caps, plus unchanged **85% causal native-BWE** behavior. Calibration uses separate source groups and a separate schedule, with all four behavior types.

This changes **data coverage**, not model architecture/learning recipe/screens: the old 16-feature/four-step/7-action ABI, CQL architecture, seed 1301, 2,400 actor/1,200 risk updates, reward and 0.5/0.2 risk/disagreement cutoffs remain fixed. Fresh weights will be fitted only after independent complete data replay; no V1/V2 development labels or legacy checkpoint weights enter fitting. BWE examples are factual off-policy transitions, not a new future/receiver/proxy oracle or an added supervised expert-loss change.

New paths: `benchmarks/native_rtc/mixed_explorer.mjs`, `src/media_rl/native_mixed_evidence.py`, `src/media_rl/native_mixed_dataset.py`, `.tools/native_mixed_collect_episode.mjs`, `.tools/audit_native_mixed_episode.py`, `.tools/collect_native_mixed_v3.py`, `.tools/train_native_mixed_v3.py`. Original native V1/V2 implementations/captures/models remain unchanged.

## Current status

**All 16 declared fitting/calibration peers are independently sealed (368 child artifacts)**. The strict loader's exact role/behavior/hash/complete-label and prior/new actual scene-frame range checks passed. Fresh V3 weights were fitted on **3,465 train / 1,152 calibration transitions**, from **10,864 / 3,621 factual source opportunities**. Recipe, seed, reward and 0.5/0.2 screens remain unchanged; no legacy weights or development labels were loaded. Fitted calibration source-frame Brier is 0.273308 raw / 0.233301 after Platt; this fitted-fold reduction is **not controller performance**.

JS/Python portable inference matches on **96 histories × three branches** (provisional, all rejected, all accepted), max absolute score difference **5.33e-15**. Trained weights were not changed by the probe. Targeted new tests pass **12 behavior + eight two-model Python tests and four Node dwell tests**; full regression totals have not yet been rerun while browsers measure outcomes.

The outer collection's 700-second deadline interrupted the final calibration peer before any summary/sender/frame/raw event data was saved. Its exact nine setup snapshots and all 15 previously sealed children were hashed before preserving the aborted root at `results/native-mixed-v3-interruptions/cal-bwe-d-outer-timeout`. Only the same missing frozen case was rerun. `results/jobs/native-mixed-v3-outer-timeout-evidence.json` records this infrastructure-only exception; no completed outcomes were replaced.

**All 18 separate actual development runs completed**: `configs/native_model_development_v3.json` froze six fresh scene groups, all old-native/V3/BWE conditions and six balanced orders before outcomes. Every condition always computes old V1 then fresh V3 on the same causal feature/history stream; only the declared controller actuates. Independent raw/feature/both-model/action/clock/source-marker/quality replay verifies **1,522 decisions per model stream, 4,848 complete opportunities, 3,204 sampled RGB pairs, 486 child artifacts** and **517 unchanged before/after hashes**. Actual scene ranges exclude all old/mixed fitting/development groups; max score error is **7.11e-15**, max combined two-model per-run p99 **6.35 ms**. All phase/cap counts, means and 12 paired contrasts are checked; **not adopted**.

| V3-minus control | Utility/request | On-time pp |
|---|---:|---:|
| Old RLCD, aggregate | −1.715 | −12.58 |
| BWE, aggregate | +0.122 | −7.94 |
| Old RLCD, both steady groups | +9.191 | +21.38 |
| BWE, both steady groups | +10.993 | +24.11 |
| Old RLCD, collapse | −5.644 | −24.22 |
| BWE, collapse | −1.294 | −8.47 |
| Old RLCD, variable | −8.692 | −34.89 |
| BWE, variable | −9.334 | −39.46 |

Known changed-ack cap ages ≥1 second increase **6.59% → 44.31%** in new train data. This supports the intended coverage change, not a causal explanation or generalization guarantee. On factually associated V3 collapse/variable labels, mean current-cap predicted miss is **0.575/0.578** versus observed **0.703/0.705**. Fallback/high-cap phase and named sender packet-send-delay diagnostics are descriptive; no hidden queue/capacity/pixel signal is added to policy, and development labels are not refit. Next: fresh transition/backlog-sensitive credit assignment and selected-policy calibration while preserving steady quality and fixed screens; independent validation/final tests remain outstanding.

**257 Python + 55 Node tests pass** with source/test lint and formatting. Eight in-memory resealed loader attacks reject; no canonical data or weights were mutated. The **38-page / 17-reference PDF** verifies four new artifacts/11 provenance hashes, all 22 macros and both tables; all **123 available generated hashes** plus legacy cadence rendered claims pass. The full make chain timed out in unchanged V9 re-export at 240 s after eight successful formal stages; complete unchanged V9 hashes were verified and TeX compiled directly using the exact Make recipe. The inherited nonfatal bibliography/six-pass warning persists, with no unresolved or box errors.

## Acceptance ledger and next commands

1. Complete all 16 frozen executions with **23 sealed artifacts per episode**. Reuse only already sealed rows; refuse partial/replacement roots. Use read-only raw-wire verification and preserve coarse initial-ack ties as in-flight/unassigned.
2. The strict loader verifies all hashes, behavior/seed/dwell, actual native feature/action reconstruction and complete outcome labels; it rejects validation/test fitting roles, duplicate IDs, old source offsets and **actual generated-scene frame-range overlap** within or against every previously sealed native train/calibration/development source group. Verify all seven caps have factual source coverage in both fitting roles; BWE individual episodes need not visit every cap.
3. Measure actual short/long known-ack state coverage and factual label counts. Do not replace failure/missing labels to improve metrics.
4. Fit `results/native-model-v3/` fresh through `.tools/train_native_mixed_v3.py`, verify unchanged recipe/gates, sealed source/model provenance and portable JS/Python action/score parity. Calibration scores are fitted-fold evidence, not controller performance.
5. **Before outcomes**, freeze independent fresh old/new/BWE native comparisons with common shadow compute and report all nominal/steady/collapse/deadline harms. No promotion or SOTA claim from these synthetic single-model development trials.
6. Update the paper only with independently checked actual artifacts; broader multi-model uncertainty, natural/measured content/traces, strong published peers, native validation gates and untouched final tests remain necessary.

```sh
uv run --frozen .tools/collect_native_mixed_v3.py
uv run --frozen .tools/train_native_mixed_v3.py
```

The fitted V3 candidate is not selected. `paper/build/main.pdf` is **38 verified pages** and includes the completed mixed-data wins/losses. V7 remains selected, cadence is not adopted and SOTA is unachieved.

Additional independent-comparison paths: `src/media_rl/native_model_comparison.py`, `.tools/native_model_compare_episode.mjs`, `.tools/audit_native_model_compare_episode.py`, `.tools/run_native_model_development_v3.py`; outputs will be sealed under `results/native-model-development-v3/`. Portable evidence is `results/jobs/native-model-v3-parity.json`.
