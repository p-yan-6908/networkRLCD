# RLCD working manuscript

`main.tex` contains nine completed, audited synthetic studies. V7 is an adaptive disagreement-screen follow-up with a narrow validation promotion and a small conditional fresh-test risk effect:

1. V1 scale-up: 10 model seeds, 19,800 episodes / 11.88 million intervals, `results/paper-v1-evaluation/`.
2. Safety-refit follow-up: three fixed original policy seeds, locked validation selection, then 1,188 fresh-test episodes / 712,800 intervals, `results/improvement-v2/test/`.
3. V3 threshold selection: unchanged ten-seed v1 bundles, five predeclared gates, 5,500 validation episodes and 7,700 fresh-test episodes, `results/threshold-selection-v3/`.
4. V4 policy-domain randomization: ten v1-matched seeds, 7,700 validation episodes, validation-locked non-promotion and 7,700 fresh-test episodes, `results/policy-randomization-v4/`.
5. V5 top-five calibrated action screen: ten unchanged v1 model seeds, 2,200 validation episodes, validation-locked promotion, and 8,800 disjoint fresh-test episodes across 11 known scenarios and eight controllers, `results/action-shield-v5/`. The screen changes no learned weights.
6. V6 one-pass Platt recalibration on screen-selected ID actions: 40 calibration episodes per unchanged v1 source seed, 2,200 locked validation episodes, and 8,800 fresh-test episodes across the same 11 known scenarios, `results/action-calibration-v6/final-campaign/`. Policy and safety-network weights are unchanged.
7. V7 ensemble-disagreement abstention uses the same V6 checkpoints and fixed 0.05 raw probability-standard-deviation cutoff. The validation lock narrowly promotes `shielded_uncertainty` (score gain 0.005073). On 8,800 fresh synthetic episodes, paired effects versus V6 are negligible for ID QoE/risk and small for stress/OOD risk (−0.083 pp, model-seed interval [−0.209, −0.0005]); abstention activates on 0.24% of stress steps. The initial partial test remains preserved; the recovered, audited test is `results/uncertainty-shield-v7/final-campaign/test`.

8. V8 causal wire-budget screen: ten unchanged V6-derived bundles, 1,100 validation and 8,800 fresh-test episodes. Validation rejects a 0.0946 ID-QoE drop despite passing all risk bounds; fresh stress violations fall 2.862 pp but QoE falls on ID/stress. The matched confidence ablation has no resolved violation disadvantage. Canonical evidence: `results/budget-shield-v8/test`; 327/386 validation/test artifacts audited.

9. V9 delay-evidence budget/fallback response: ten unchanged bundles, 1,650 validation and 9,900 fresh-test episodes. Validation rejects a 0.1109 nominal-quality decrease. Versus V8 on the paired new panel, burst-loss QoE recovers 1.160 with unchanged violations, while nominal quality remains deficient. Confidence eligibility has a small conditional stress regression against its matched ablation. Canonical evidence: `results/delay-budget-v9/test`; 346/405 validation/test artifacts, all ten bundles, both 159-file source snapshots and 16 contrasts verified.

The v2 refit regresses against matched v1 on fresh traces and is not promoted. V3 retains the original 0.90 gate because its best alternative misses the 0.005 gain margin. V4's fixed 35% stress policy-training mix fails the frozen ID-QoE and per-family-risk promotion constraints; the candidate also loses QoE and has more stress violations than matched v1 on fresh traces. V5 validation promotes the screen; on the fresh ID panel it improves QoE and violation rate against matched calibrated v1, but OOD violation effects are inconclusive. V6 validation promotes the recalibrated screen: on the fresh panel it improves ID QoE by 0.022 and reduces ID violation rate by 0.050 percentage points; OOD QoE rises, but the OOD violation interval includes zero. Selected-action confidence remains 5.09 points optimistic on OOD observations. V7 narrowly passes its validation margin, but the 0.05 screen activates on only 0.24% of stress steps; the fresh-panel paired OOD violation estimate is -0.083 pp with an interval barely excluding zero. GCC-like control remains stronger on OOD QoE/risk. The paper preserves negative and mixed findings, conditional uncertainty, deterministic-baseline advantages and scenario-level evidence. All results are synthetic; v3–v9 final tests use fresh realizations of known mechanisms, not unseen-mechanism evidence.

## V8 completed: risk reduction with rejected QoE tradeoff

The budget guard reduces fresh-panel ID/stress violations by 0.680/2.862 percentage points, but lowers QoE by 0.104/0.133. Burst-loss QoE regresses by 1.132 with no violation reduction. Validation retains V7 because the 0.0946 nominal-QoE loss exceeds 0.03; the aggregate score gain does not override this bound. Confidence/disagreement eligibility adds no resolved violation benefit beyond the matched envelope, and accepted stress confidence remains 1.51 pp optimistic. These are conditional known-family results, not a safety guarantee or a post-test promotion.

The paper reports the locked decision, all controller means, paired contrasts, scenario harms, intervention diagnostics and separate accepted-action audits. `make paper-evidence` requires all nine audited studies and refuses partial/corrupted inputs. `paper/generated-budget-shield-v8/budget_results.json` stores the exact estimates with provenance. Protocol/results and fresh-directory reproduction: `docs/BUDGET_SHIELD_V8.md`.

## V9 completed: loss-response repair does not satisfy nominal promotion

V9 removes raw-loss-only backoff from both the warm envelope and its fallback; it is not a reliable congestion/erasure classifier or a same-fallback-only comparison. On the new panel it raises stress QoE 0.1658 [0.1534,0.1801] versus V8, with zero observed risk contrast; burst-loss QoE gains 1.160. ID means equal V8 exactly. Against V7, ID QoE drops 0.1137 and stress risk falls 2.416 pp, but the validation QoE bound still rejects the candidate. Adding confidence eligibility raises stress violations 0.024 pp [0.009,0.047] and slightly lowers QoE; the ablation retains Q/support and cannot be promoted post-test. Accepted stress confidence is 4.64 pp optimistic. The paper preserves these mixed/negative findings and the GCC-like benchmark gap.

Canonical results and protocol: `docs/DELAY_BUDGET_V9.md`; exact estimates: `paper/generated-delay-budget-v9/delay_budget_results.json`. All accepted envelopes, source/model bytes, lock timing and paired contrasts are verified in `results/jobs/delay-budget-v9-evidence-check.json`. Reproduction after source edits must use a fresh output directory; completed canonical data is audited/exported rather than overwritten.

## Separate native training-only evidence

`make paper-evidence` also runs `.tools/export_native_training_paper.py` to verify the frozen fresh-native model/data/source manifests, recompute **543/180 transitions** and **1,703/567 factual requests**, recalculation of source-frame Brier and actual fitted JS/Python parity. It generates `paper/generated-native-training/` macros for a separate fitted-candidate paragraph. Calibration scores are **in-sample**, no learned policy had run in a live peer at that training-only freeze and no promotion/SOTA claim follows. See `docs/NATIVE_TRAINING_V1.md`. Builds do not collect browser data or retrain weights.

## Prospective live native development: negative result

`.tools/export_native_development_paper.py` is also registered in `make paper-evidence`. It reruns independent full replay of **18 episodes, 512 learned decisions and 450 artifact hashes**, exports `paper/generated-native-development/` and reports RLCD's **−2.51 utility / −11.97 on-time pp** against matched BWE, with first-phase/steady harms and no native promotion/SOTA inference. At the V1 checkpoint cadence was only unit/math-tested. The subsequent actual V2 comparison is separately exported by `.tools/export_native_cadence_paper.py` in `make paper-evidence` to `paper/generated-native-cadence/`: 18 fresh runs, 29 actual holds, steady harms and **−1.681 utility / −7.664 on-time pp** versus BWE. It is not adopted; see `docs/NATIVE_CADENCE_V2.md`. See `docs/NATIVE_DEVELOPMENT_V1.md`.

## Mixed-native data V3: stable gain, transition loss

`.tools/export_native_model_v3_paper.py` is registered in `make paper-evidence`. It independently checks 16 source/role-disjoint fresh fitting/calibration peers, unchanged architecture/seed/update/reward/screens, and 18 actual old/new/BWE development peers under common two-model shadow compute. `paper/generated-native-mixed-v3/` binds fitting/age/parity/forgery evidence and all native source/phase/gain/loss metrics: **+9.191 steady utility versus old RLCD, −1.715 aggregate**, and **−7.94 on-time pp versus BWE**. Four generated artifacts and 11 provenance sources, all 22 rendered macro values and both tables are verified in the **38-page** PDF. The candidate is **not adopted**; natural/measured data, selected-policy native calibration/validation/final tests and representative peers remain required. See `docs/NATIVE_MIXED_V3.md`.

The full registered `make paper` re-export timed out at 240 seconds during unchanged V9 auditing after eight completed formal exports. All **123 available generated artifact hashes** (including complete V9 evidence) were then verified, and the exact Make TeX recipe compiled the current evidence directly. No model/data collection was rerun. The existing nonfatal Tectonic bibliography-consistency/six-pass warning remains; final output has no unresolved or box errors.

## Pure native temporal-credit V4: aggregate gain, nominal regression

`.tools/export_native_temporal_v4_paper.py` is registered in `make paper-evidence`, generating `paper/generated-native-temporal-v4/`. Exactly the same V3 train/calibration data, architecture/seed/updates/reward scalars and bit-identical risk weights/Platt/screens are used; only actor returns change n=3→20. All 18 fresh n=3/n=20/BWE native peers and 486 child/518 immutable hashes are independently replayed. Aggregate utility improves **4.094 versus n=3 / 2.599 versus BWE**, but both steady cases regress (**−5.356**) and collapse-g loses **13.372 versus BWE**. **Not adopted**, with all family/phase/nominal/catastrophic losses preserved. Longer off-policy return mixtures are not causal frame credit. See `docs/NATIVE_TEMPORAL_V4.md`.

Four new artifacts/14 provenance hashes, all 17 macros and two tables, public exporter/import registration, **265 Python + 55 Node** regressions and all **127 available generated hashes** pass in the updated **38-page / 17-reference PDF**. Build uses the same Make TeX recipe on current verified evidence, not an unchanged expensive full re-export; inherited nonfatal bibliography/six-pass warning persists with no unresolved/box errors.

## Causal native context V5: losses and zero-switch ambiguity

`.tools/export_native_context_v5_paper.py` is registered in `make paper-evidence`; `paper/generated-native-context-v5/` contains five artifacts and 19 bound provenance sources. One frozen causal selector, no fitting/grid/cutoff override, completes **32 actual context/short/long/BWE peers** on eight source-disjoint groups, including one-second collapse. Exact raw/two-model/context/action/quality replay verifies **928 child / 977 immutable hashes**. Aggregate utility changes **−1.896 versus short / −1.818 versus long / −1.795 versus BWE**; not adopted. Two no-switch groups still differ from separate fixed-short executions, so no causal switching effect is inferred.

All **21 macros**, four means/families, every **24 case contrast**, 7.185-ms candidate versus 16.092-ms control-tail distinction, zero-switch ambiguity and public config/exports/Make/four TeX inputs are checked in the current **40-page / 17-reference PDF**. **287 Python + 59 Node tests** and all **132 generated hashes** pass; current-PDF temporal/mixed/cadence legacy audits preserve every prior claim. Build uses current evidence and the Make TeX recipe, not expensive unchanged re-export/recollection. See `docs/NATIVE_CONTEXT_V5.md`; V7 remains selected, SOTA unachieved.

## Ancillary native diagnostics: explicit claim boundary

The new appendix measures generated-video application request-to-pixel-readback deadlines in actual Chrome/VP8/transport-cc through an owned UDP bottleneck. It compares **native browser default versus a verified zero receiver jitter-buffer target**, not RLCD or published learned peers. Native 14-action cap/receiver-target ABI is not the old 42-action simulator ABI. Both independent short runs have 100% known-marker coverage and terminal censoring; their on-time opportunity counts are 21/361 and 116/360. These are not paired confidence intervals, physical capture/scan-out or perceptual-quality evidence; collapse/recovery remain poor.

`make paper-evidence` still audits/exports all **nine formal synthetic studies**, and now also invokes `.tools/export_native_frame_paper.py` for the **separate ancillary** appendix. It checks sealed eight/nine-artifact native manifests, current-versus-frozen metric source identity and full recomputation before writing `paper/generated-native-rtc/{evidence.tex,native_diagnostics.json,provenance.json}`. No browser experiment or training is launched by a paper build, and no old study or promotion decision is changed. Protocol/details: `docs/NATIVE_RTC_BENCHMARK.md`.

## Study 10: typed bitrate decisions (separate testbed)

Section "Study 10" of `main.tex` reports the synthetic typed-control track: [V2](../docs/JEVBWE_TYPED_V2.md), its family-level audit, and the broadened run [V3](../docs/JEVBWE_TYPED_V3_BROAD.md) with its untouched test families. It is bitrate-only, uses a corrected (acked-rate-bounded) estimator, and is **not** one of the nine hash-audited studies. Its numbers come from `report.json` and the `audit_*.json` files under `results/jevbwe-typed-v2` and `results/jevbwe-typed-v3-broad` through `jevbwe-typed export`, which writes `paper/generated-jevbwe-typed-v2/` (macros, tables, figures, source hashes).

Claim boundary: counterfactual rollout supervision lets a small probabilistic bitrate policy beat fixed-ratio control in distribution; on unseen families the mean gain over the train-selected fixed ratio is positive but not established at family level, before and after broadened training; calibration degrades on unseen families; no advantage for RLCD-style training over exact-gradient or regression controls; no native, real-network or safety claim. The hindsight-best fixed ratio is an oracle and is never the comparator for a claim. "RLCD" in that section means reinforcement learning for calibrated decisions, the typed-decision training recipe, and is unrelated to the project name used elsewhere in the paper.

```sh
make jevbwe-typed            # diagnosis, main study, ablation and replication (about two hours on 8 cores)
make jevbwe-typed-evidence   # regenerate paper/generated-jevbwe-typed-v2/
make paper-pdf               # compile from the evidence already exported under paper/generated-*
```

`make paper` re-exports the nine archived studies first and needs their pruned results restored (see `ARCHIVED_RESULTS.md`). `make paper-pdf` only compiles.

Build state after the Study 10 audit and broadened run (2026-10-07): 53 pages, 24 bibliography entries, no undefined references and no overfull boxes under the bundled Tectonic. The Study 10 pages were proofread from extracted text; they have not been reviewed visually, and several of its tables are scaled to the line width. The page and bibliography counts in the "Verified PDF" note below predate this section.

## Rebuild audited tables and PDF

```sh
make paper
# Equivalent evidence commands:
uv run media-rl export-paper --run results/paper-v1-evaluation --out paper/generated-scaleup
uv run media-rl export-paper --run results/improvement-v2/test --out paper/generated-followup --macro-prefix Followup
uv run media-rl export-paper --run results/threshold-selection-v3/test --out paper/generated-threshold --macro-prefix Threshold
uv run media-rl export-paper --run results/policy-randomization-v4/test --out paper/generated-randomization --macro-prefix Random
uv run media-rl export-paper --run results/action-shield-v5/test --out paper/generated-shield --macro-prefix Shield
uv run media-rl export-paper --run results/action-calibration-v6/final-campaign/test --out paper/generated-action-calibration-v6 --macro-prefix ActionCal
# V7 recovered test: audit/export; make paper repeats all nine evidence exports
uv run media-rl audit --run results/uncertainty-shield-v7/final-campaign/test
uv run media-rl export-paper --run results/uncertainty-shield-v7/final-campaign/test --out paper/generated-uncertainty-shield-v7 --macro-prefix Disagreement
uv run media-rl audit --run results/budget-shield-v8/test
uv run media-rl export-paper --run results/budget-shield-v8/test --out paper/generated-budget-shield-v8 --macro-prefix Budget
uv run media-rl audit --run results/delay-budget-v9/test
uv run media-rl export-paper --run results/delay-budget-v9/test --out paper/generated-delay-budget-v9 --macro-prefix DelayBudget
# Ancillary native diagnostics, not a tenth formal study or an RLCD comparison:
uv run --frozen .tools/export_native_frame_paper.py
```

The V7 recovery is complete: it reused only the audited validation/selection, verified runtime/checkpoint hashes, preserved the original incomplete test, and ran the full fresh panel in `final-campaign/test`. No partial-test outcomes were used for tuning. `make paper` re-exports and audits all nine studies before compilation; the PDF is **`paper/build/main.pdf`** (using `latexmk`, or the ignored local `.tools/tectonic` binary). Export directories have separate provenance files; v1 macros use `Evidence`, follow-up macros use `Followup`, threshold macros use `Threshold`, v4 macros use `Random`, v5 macros use `Shield`, v6 macros use `ActionCal`, V7 macros use `Disagreement`, V8 macros use `Budget`, and V9 macros use `DelayBudget`. Figures/tables are copied only from corresponding audited runs. V7's paired-effect table barely excludes zero for stress/OOD unsafe rate, but its absolute change is small and the cutoff rarely triggers; conclusions remain conditional on the fixed synthetic trace panel.
The original pilot manuscript is retained as `pilot-archived.tex`, paired with `paper/generated/`; it is historical, not the current paper.

## Reproduce the validation-selected gate study

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  uv run media-rl tune-threshold --config configs/threshold_select_v3.json \
  --models results/paper-v1 --out results/threshold-selection-v3
```

The v3 threshold study uses unchanged ten-seed v1 bundles, five predeclared thresholds, 10 independent validation trace seeds, and 10 disjoint final seeds. The selection lock precedes fresh testing and retains 0.90 because no alternative passes the declared gain margin. All eleven scenario families occur in validation, so the test measures fresh realizations—not unseen-mechanism generalization. It is empirical validation tuning, **not conformal risk control or a safety guarantee**: changing a stateful gate's threshold need not produce a monotone episode-risk function. Final artifacts carry method-specific threshold overrides for exact replay. Details: `docs/THRESHOLD_SELECTION_V3.md`.

## Reproduce the v4 policy-randomization study

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  uv run media-rl policy-randomization --config configs/policy_randomization_v4.json \
  --models results/paper-v1 --out results/policy-randomization-v4
```

The v4 schedule, promotion tolerances, and validation/final seeds are frozen in `docs/POLICY_RANDOMIZATION_V4.md` and `configs/policy_randomization_v4.json`. The final decision is to retain v1: the candidate fails ID-QoE and stress-family risk bounds and underperforms matched v1 on new realizations. `results/policy-randomization-v4/PROMOTION_REVIEW.md` records the locked metrics and audit hashes. Use a new output directory after any source/config change; the runner never overwrites partial results.

## Reproduce the v5 action-screen study

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  uv run media-rl safety-shield --config configs/safety_shield_v5.json \
  --models results/paper-v1 --out results/action-shield-v5-reproduction
```

The immutable published outputs are `results/action-shield-v5/validation` and `results/action-shield-v5/test`; audit them with the commands in `docs/SAFETY_SHIELD_V5.md`. The fixed validation/test seeds, top-five screen, threshold and promotion limits are in `configs/safety_shield_v5.json`. Validation selected the candidate before the disjoint test; do not rerun into the existing output directory. Results are synthetic and all stress families are known.

## Reproduce the V6 selected-action-calibration study

Run `make action-calibration-v6` to fit the calibrators on 40 ID episodes per source seed and execute the locked validation/fresh-test campaign. The complete audited panel is `results/action-calibration-v6/final-campaign/test`; the separate paper export is `paper/generated-action-calibration-v6`. A first foreground attempt in `results/action-calibration-v6/campaign` timed out partway through its test and is preserved but excluded. The completed campaign reuses the identical validation lock; no partial test outcomes informed tuning. V6 changes only the calibrator, not policy or safety-network weights. See `docs/ACTION_CALIBRATION_V6.md` for the exact data distribution, results and limitations.

## Reproduce the follow-up

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  uv run media-rl improve --config configs/improve_v2.json \
  --models results/paper-v1 --out results/improvement-v2
```

The command reuses only completed, audited subruns with identical protocol, source checkpoints and implementation hashes. Otherwise use a new output directory. It does not resume mid-training/evaluation. Each final evaluation carries a relative model map and copied reference checkpoints for self-contained replay. `docs/IMPROVEMENT_V2.md` records the pre-evaluation protocol and measured results; `results/improvement-v2/selection.json` records the locked validation ranking. The promotion review is `results/improvement-v2/PROMOTION_REVIEW.md`.

The local engine is Tectonic 0.15.0 (aarch64-apple-darwin), downloaded from its official pinned release, archive SHA-256 `24bd46566fa30d41101848405e9cbc4645edb92d8f857c9d21262174fb70cd33`. This is a retrieved-bytes checksum, not independent signature verification. Tectonic runs with `--untrusted`; no global TeX installation was changed.

## Verified PDF and toolchain note

The verified final PDF is **34 pages** with **17 bibliography entries**. All **nine** evidence bundles were re-exported and **101 generated hashes** verified; canonical V8/V9 selections, manifests and raw step logs are unchanged. Native TeX diagnostics contain no unresolved citations/references or overfull/underfull boxes. V9 methods/results and audit pages **23, 24, 31, 32 and 33** were rendered and visually reviewed; wide full-score audits use landscape layout, tiny interval signs are preserved, and scenario tables remain with their appendix heading. This is targeted review, not independent all-page proofreading.

Tectonic 0.15.0's known **nonfatal bibliography consistency/rerun warning** remains documented in `paper/build.log`, not suppressed or described as warning-free. Current receipt: `results/jobs/delay-budget-v9-paper-check.json` (the separate V8 receipt is historical); complete verification: `docs/verification.md`. Independent all-page proofreading and author/venue metadata remain outstanding.

Author/affiliation and venue/template are still placeholders. Real traces, packet/codec validation, WebRTC integration, fairness, stronger uncertainty analysis and full-budget physical/threshold ablations remain future work. Nothing has been submitted or published.

## Long-session native pilot and blind forecast validation (2026-10-11)

Study 13 now includes the completed 192-session development pilot and its unchanged
registered forecast test. The rule loses to tuned fixed 0.65; the simulator misses
that contrast and fails. No model is fitted or controller promoted.
`paper/generated-native-margin-pilot/` contains two tables, macros and input/code
provenance from `media_rl.native_margin_pilot_report`. The factual report is fully
recomputed from committed compact session summaries; raw frames/seals are not
restored or replayed. Holm and source-omission checks are explicitly post-report
supplements, not independent confirmation or policy selection.

`make native-margin-pilot-evidence` reproduces into fresh `*-reproduction` directories
without downloading raw evidence. Set `MARGIN_VALIDATION` and `MARGIN_PAPER` to new
paths for further reproductions. The manuscript reads the committed canonical
export. See [results and limitations](../docs/NATIVE_MARGIN_PILOT_V1.md#results-2026-10-11)
and [active research status](../docs/RESEARCH_STATUS.md).

Cloud verification of the margin section, before the BWE diagnostic: 116 Python tests passed, one macOS-only storage test skipped,
and nine Node controller tests passed. An independent export reproduced the audit
and judgement and produced bit-exact tables/macros. All 464 pre-existing research
code/config/result files remain unchanged. The 77-page PDF compiled with XeLaTeX,
with no undefined references, box warnings or missing characters in the final log.
The installed pdfLaTeX cannot render the manuscript's existing Unicode minus;
XeLaTeX is the compatible engine. BibTeX was invoked from `paper/` to preserve the
existing relative bibliography path, then `latexmk -g -xelatex -bibtex-` completed
the build. Full commands and the PDF checksum are in
`reports/native-margin-validation-v1/verification.json`.

## Factual BWE dynamics diagnostic (development only)

Study 13 also includes the small grouped prediction experiment documented in
[BWE_DYNAMICS_DIAGNOSTIC_V1.md](../docs/BWE_DYNAMICS_DIAGNOSTIC_V1.md). Its table
comes directly from `reports/bwe-dynamics-diagnostic-v1/table_bwe_dynamics.tex`,
bound by the report's checksum. Source/regime CV are partitions of previously
read development data, and ladder/margin reuse the same sources. The short-session
fit loses to persistence on the one-minute panel; current cap gives no consistent
predictive improvement. Predictive coefficients do not identify causal action value.
No simulator, native controller or safety calibration is revised.

`make native-bwe-diagnostic` reproduces into a fresh directory; set `BWE_DIAGNOSTIC`
to another fresh path for further runs. Every model, factual numerical feature,
target, prediction and table reproduces bit-exactly. The extended regression suite
passes 126 Python tests with one macOS-only skip. The current PDF has 78 pages and
no undefined-reference, box or missing-character warnings. Its checksum and checks
are in `reports/bwe-dynamics-diagnostic-v1/verification.json`; the earlier 77-page
checksum is a historical build receipt. Timestamped encoder/sender reconstruction
of the original UDP pilots still needs raw evidence access, documented in
`next-input.json` alongside that historical verification receipt. A separate new
TURN/TCP native history track is available below.

## Factual acceptance and new native observability (2026-10-12 UTC)

The Study 12 follow-up documents the synthetic factual-only acceptance experiment:
three new seeds, 20k/80k nested blocks, original point selection versus episode/family
lower bounds. Both stricter selectors reject all six fits and reproduce fixed
control; low-data point policies again lose on the read unseen-family panels.
All six refits/eighteen packaged models reproduce from executed labels alone.
The table is `paper/generated-typed-factual-acceptance/table.tex`.

Study 13 adds a distinct native TURN/TCP development probe: sixteen registered
procedural peers, 96 randomized holds, actual encoder history and full causal
feature replay. A closing-ledger timer defect is preserved and explicitly audited;
the new collector version passes a separate excluded technical check. The
descriptive table is `paper/generated-native-turn-probe/table.tex`, and the first
registered peer provides an illustrative trajectory figure. Neither section
changes frozen native experiments or makes a learned gain/real-network claim.

The new post-capture action diagnostic is a secondary exploratory analysis of the
same native holds, not new validation: the 1.05 versus 0.65 assigned ratio moves
actual payload by +0.279 [0.187, 0.372], while the on-time contrast remains
unresolved at +7.2 pp [-11.2, +25.5]. The manuscript's arm/contrast tables and
their input hashes are under
paper/generated-native-turn-action-diagnostic-v1/. They do not qualify action value,
safety or controller promotion.

`tools/export_development_updates.py` binds tables to the compact reports and
independent verification receipts; exports require fresh directories and launch
no fitting/capture. Protocols, commands, complete negative results and storage
status: [acceptance](../docs/TYPED_FACTUAL_ACCEPTANCE_V1.md),
[native probe](../docs/NATIVE_TURN_PROBE_V1.md),
[active status](../docs/RESEARCH_STATUS.md). The new build receipt is
`reports/native-turn-probe-v1/verification.json`; older PDF hashes remain historical.
