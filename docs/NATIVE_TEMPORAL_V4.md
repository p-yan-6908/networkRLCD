# Native temporal-credit V4 — aggregate/variable improvement, nominal regression; not adopted

## Verified single-change contract

`configs/native_temporal_v4.json` prospectively fixed **one n=3 → n=20** actor return change. This reuses the **exact V3 12-train/four-calibration fitting data**, not newly collected fitting episodes or any development labels. Factual reward scalars, gamma 0.97, seed 1301, architecture/update counts and actor input states/actions are unchanged. All three refitted risk weight arrays, Platt pair, metadata and **0.5/0.2** cutoffs match V3 bit-for-bit. Q weights initialize fresh; the reference is read only for verification. Existing terminal/missing-decision/episode boundaries remain strict.

Eight new long-return hand-calculation/integer/gap/terminal tests and existing native dataset/learner tests passed (19 targeted cases). Exact portable JS/Python provisional/all-rejected/all-accepted branches pass **96 histories each**, without mutating trained weights. The risk/state/action/source equality means this ablation changes actor credit/Q selection, **not the safety screen**; it supplies no new safety guarantee.

## Actual prospective native comparison

`configs/native_temporal_development_v4.json` froze all hashes and six balanced **n=3 / n=20 / BWE** orders before actual outcomes. Six new source groups were reserved in 1,000-frame windows excluding every prior audited fitting/development generated-scene range; actual final source ranges independently pass exclusion. Each condition computes n=3 then n=20 on identical causal histories; only the declared controller actuates. Earlier V1/V3 sources/models/captures remain unchanged.

**All 18 actual Chrome/VP8 peers completed**. Independent full raw/feature/both-model/action/clock/marker/source-quality replay checks **1,528 decisions per model stream / 4,843 complete opportunities / 3,492 sampled RGB pairs / 486 child hashes**. **518 artifact/model hashes** remain identical before/after full replay. Every common-history risk/disagreement vector is bit-identical; score error ≤ **7.11e-15**, maximum combined per-run p99 **9.38 ms**, below the unchanged 10-ms provisional budget. All case/phase/cap counts and 12 paired differences/means are verified.

| n=20 minus control | Utility/request | On-time pp |
|---|---:|---:|
| Unchanged n=3, aggregate | +4.094 | +18.84 |
| BWE, aggregate | +2.599 | +4.80 |
| n=3, collapse family | +4.491 | +18.97 |
| BWE, collapse family | −6.473 | −25.70 |
| n=3, both steady groups | −5.356 | −14.50 |
| BWE, steady family | +11.314 | +29.88 |
| n=3, variable family | +13.146 | +52.04 |
| BWE, variable family | +2.955 | +10.22 |
| BWE, collapse-g retained worst case | −13.372 | −49.92 |

**Not adopted**: both steady cases lose utility/on-time delivery versus n=3, and one collapse group has a catastrophic BWE loss. The second collapse case gains utility but still slightly loses on-time delivery versus BWE. No unfavorable case is replaced or omitted. One model seed/two source groups per family are descriptive development evidence, not confidence intervals, native promotion, strong-published-peer or SOTA evidence. Original native V1 was not a control on this new panel.

## Temporal diagnosis and limits

Actual mean train-return windows are **309.5 / 2,002.6 ms** for n=3/n=20; full-horizon fractions **99.31% / 93.42%** retain terminal/gap truncation. Windows containing more than one later behavior cap increase **27.16% → 61.47%**. Longer off-policy returns therefore are **not causal individual-frame attribution**. All high/collapse/recovery phase contrasts and catastrophic case details are preserved in `results/jobs/native-temporal-v4-credit-diagnosis.json`; development outcomes are never fitted.

The next defensible hypothesis is **causal context-sensitive credit/control** that preserves stable quality while responding to transient evidence, with fresh-data/selected-policy calibration and prospective independent evaluation. Do not tune a horizon/gate grid on these cases, add latent queue/capacity/pixel oracles, loosen 0.5/0.2 screens, refit development labels or hide nominal harms. Native selected-policy validation/final tests, multi-model uncertainty, natural/measured content/traces and strong published peers remain required. V7 remains selected; SOTA is unachieved.

## Regression and paper acceptance

**265 Python + 55 Node tests pass**, with source/test lint and formatting. The updated **38-page / 17-reference PDF** retains all V3/cadence claims and incorporates n=20 aggregate/variable gains, both steady losses and collapse-g catastrophe. Four new generated artifacts, **14 provenance sources**, all **17 macros**, both tables and exporter/three TeX input registrations are verified; **127 available generated artifact hashes** pass. Current evidence compiled directly using the Make recipe, without rerunning unchanged heavy formal exporters or data/models. Inherited nonfatal Tectonic bibliography/six-pass warning remains; no unresolved/box errors.

Evidence: `results/jobs/native-temporal-v4-final-evidence.json`, `results/jobs/native-temporal-v4-final-paper-audit.json`, `results/jobs/native-temporal-v4-all-generated-hashes.json`. Outputs: `results/native-model-v4/`, `results/native-temporal-development-v4/`, `paper/generated-native-temporal-v4/`. Scripts: `.tools/train_native_temporal_v4.py`, `.tools/probe_native_v4_parity.py`, `.tools/freeze_native_temporal_v4_panel.py`, `.tools/native_temporal_episode.mjs`, `.tools/audit_native_temporal_episode.py`, `.tools/run_native_temporal_v4.py`, `.tools/audit_native_temporal_v4.py`, `.tools/diagnose_native_temporal_v4.py`, `.tools/export_native_temporal_v4_paper.py`, `.tools/verify_native_temporal_v4_paper.py`.
