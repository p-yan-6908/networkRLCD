# Calibrated RL for Safe Real-Time Media Adaptation

A reproducible **simulation research framework**, not a certified safety system or a WebRTC/GCC implementation. An actual NumPy Double DQN chooses bitrate, FEC and media mode. A separate episode-bootstrap safety ensemble estimates the probability that its proposed action meets next-interval latency/loss constraints. Held-out Platt/temperature calibration, a telemetry-support guard and hysteresis determine when to use a deterministic conservative controller.

## Run

Requires Python 3.11+ (locked reference: Python 3.12) and [uv](https://docs.astral.sh/uv/).

Generated run artifacts under `results/` and large local recorded-video binaries are intentionally not included in this repository. The small source descriptors and attribution pages under `data/native_video/` retain provenance and checksums; native recorded-video workflows require the corresponding local media assets. Tests that depend on omitted research artifacts are skipped in a clean source-only checkout and run when the local evidence bundle is present.

```sh
uv sync --frozen --extra dev
uv run pytest -q
uv run media-rl run --config configs/smoke.json --out results/my-smoke
uv run media-rl audit --run results/my-smoke
# Three-seed exploratory pilot; not confirmatory evidence
uv run media-rl run --config configs/demo.json --out results/my-pilot
# Larger predeclared protocol (not run by default)
uv run media-rl run --config configs/paper.json --out results/my-paper
```

Output directories must be empty/nonexistent; existing evidence is never silently overwritten. CPU training is sufficient for these small networks. The user permits Modal CLI GPU training if needed; see [`GOAL.md`](GOAL.md). No GPU jobs are required or launched by this package.

## What is included

- 42 joint actions: seven bitrates × three FEC levels × normal/low-latency media mode.
- Seeded causal `fluid_v1` (legacy default) plus opt-in `packet_v2`: paced/VBR media packets, headers, competing UDP traffic, shared FIFO/drop-tail service, actual frame delivery/deadlines/FEC accounting and propagation-delayed reports.
- Heuristic, GCC-**like**, conservative safe, identical ungated RL, calibrated RL, four inference-time ablations, and a separate top-five calibrated action-screen candidate; no-FEC and temperature-scaling retraining sweeps.
- Disjoint training, safety-fit, calibration and test seed namespaces; identical test traces across all methods/model seeds.
- QoE, virtual latency tails, loss, deadlines, stability, calibration (ECE/Brier/NLL), selective risk, OOD support AUROC, fallback reasons/duration/harm/prevention, recovery and censoring.
- Raw compressed step logs; checkpoints; resolved configs; source snapshots and artifact hashes; inference-time diagnostics; paired seed-cluster bootstrap contrasts; CSV/LaTeX tables; PDF/PNG figures.
- Unit/integration/regression tests, reproducibility replay, CI, research notes and an academic paper scaffold.

## Commands

```sh
uv run media-rl train --config configs/demo.json --out results/models
uv run media-rl evaluate --config configs/demo.json --models results/models --out results/evaluation
uv run media-rl report --run results/evaluation
uv run media-rl sweep --kind thresholds --config configs/demo.json --models results/models --out results/thresholds --no-plots
uv run media-rl sweep --kind ablations --config configs/demo.json --out results/ablations --no-plots
uv run media-rl trace --scenario collapse --seed 42 --steps 600 --out results/collapse.npz
uv run media-rl --help
```

`--no-plots` retains tables and diagnostics. Physical/action-space changes require retraining. Checkpoints are inference artifacts, not training-resume snapshots. Trace export supports deterministic inspection; `load_trace` is the Python API for replaying NPZ traces, including validated custom `Trace` instances.

## Start reading

| Path | Purpose |
|---|---|
| `GOAL.md` | Objective, boundaries, verification and optional Modal permission |
| `docs/methodology.md` | Equations, confidence semantics, simulator/controller assumptions |
| `docs/experiments.md` | Protocol, scenarios, ablations, metrics and artifact map |
| `docs/acceptance.md` | Acceptance checks and verification evidence |
| `research/RELATED_WORK.md` | Sources actually consulted and design implications |
| `research/references.bib` | Primary-source bibliography |
| `paper/main.tex` | Nine audited synthetic studies, including V8/V9 rejection and matched confidence ablations |
| `src/media_rl/` | Simulator, learning, calibration, controllers, metrics, CLI |
| `tests/` | Behavioral, scientific-correctness and integration tests |

## Fresh native deployment candidate — negative development result

A separate audited **6 training + 2 calibration** Chrome/VP8 exploration panel covers all seven supported zero-target caps. Fresh native conservative RLCD fits **543/180 transitions** from **1,703/567 factual source requests**, without legacy weights or receiver/proxy oracle inputs. Portable JS/Python inference agrees within **3.6e-15**; offline calibration is not policy performance. The frozen candidate subsequently ran in **6 learned + 12 matched conventional** development episodes. It loses **2.51 timing-weighted PSNR units / 11.97 on-time percentage points** versus the BWE control despite first-phase quality gains; **not promoted**. See [`docs/NATIVE_DEVELOPMENT_V1.md`](docs/NATIVE_DEVELOPMENT_V1.md) and the [training provenance](docs/NATIVE_TRAINING_V1.md). The subsequent [screened cadence live study](docs/NATIVE_CADENCE_V2.md) executes 18 fresh runs and 29 actual holds, but harms both steady-link cases and remains 1.68 utility / 7.66 on-time pp behind BWE—**not adopted**. V7 remains selected.

## Fresh mixed-native data — steady gain, transient loss

The [mixed-dwell/BWE data revision](docs/NATIVE_MIXED_V3.md) completes **12 fresh train + four calibration** 30-second native episodes and **18 separate old/new/BWE development runs**. Fresh same-recipe weights retain all risk screens. Known-cap ages ≥1 second grow from **6.59% to 44.31%**. The candidate gains **9.19 utility versus old RLCD** and **10.99 versus BWE** on both steady cases, but loses **1.72 aggregate utility versus old RLCD** and **7.94 on-time pp versus BWE**, with severe collapse/variable losses—**not adopted**. Independent dual-model/raw/source replay verifies 486 live artifact hashes and 517 unchanged before/after hashes. The **38-page** paper preserves all gains/losses; V7 remains selected and SOTA unachieved.

## Temporal native credit V4 — aggregate gain, nominal loss

The [single n=3→20 actor ablation](docs/NATIVE_TEMPORAL_V4.md) reuses exactly the verified V3 fitting data, with **bit-identical risk weights/Platt/cutoffs**, and completes **18 new n=3/n=20/BWE native peers**. Aggregate utility gains **4.09 versus V3 / 2.60 versus BWE**; variable-link utility gains **13.15 versus V3**. But both steady cases regress (**−5.36 utility**) and one collapse case loses **13.37 utility versus BWE**—**not adopted**. Full read-only replay checks 486 child/518 before-after hashes. The updated **38-page** PDF preserves all trade-offs; **127 generated hashes** pass. V7 remains selected, SOTA unachieved.

## Causal context V5 — failed control and repeatability warning

[One frozen sender-only switch](docs/NATIVE_CONTEXT_V5.md) between unchanged n=3/n=20 actors completes **32 actual peers**, adding one-second collapses without phase inputs. It loses **1.896 utility versus short / 1.818 versus long / 1.795 versus BWE**—**not adopted**. Steady mean improves versus long, but one nominal group selects long; two groups never switch and still show substantial separate-run differences, so gains are not causal switching evidence. Full replay verifies **928 child / 977 immutable hashes**. Current paper: **40 pages / 17 references**, every case and timing/ambiguity limit retained, **132 generated hashes** checked. Follow-up: [prospective repeated controls and selected native calibration](docs/NATIVE_RELIABILITY_V1.md); V7 selected, SOTA unachieved.

## Native reliability/calibration — audited workflow, no promotion

The [portable native pipeline](docs/NATIVE_RELIABILITY_V1.md) adds frozen role/source/model/workload plans, complete raw wire/frame/policy replay, group-cluster comparisons, common shadow inference, selected-action calibration, and strict cleanup-only resume without replacing outcomes. **68 new Chrome/VP8 runs** complete: **12 repeated controls + eight separate calibration + 48 untouched validation**. The refit changes only Platt parameters. It gains **0.984 utility versus unchanged V3** but its interval crosses zero, and trails BWE by **1.943 utility / 14.704 on-time pp**, especially on variable links. The frozen gate **rejects** it; canonical models/V7 selection remain unchanged. Native safety/SOTA remain unachieved.

## Recorded-media source — repeatability gate still fails

The [recorded-video extension](docs/NATIVE_RECORDED_V1.md) adds hashed licensed local films, disjoint clip reservations, pre-capture RGB references and immutable native replay without changing sender inputs or risk gates. **24 actual Tears of Steel/Chrome/VP8 runs** complete. RLCD averages **48–54% on-time versus BWE's 87.26%**; identical-policy brief-collapse runs span **16.46 utility / 60.97 on-time pp**, and two inference tails exceed 10 ms. The gate fails; no model is promoted or labels reused for fitting. One live-action/VFX film is not a representative corpus.

## Native controller repair — efficacy still unverified

The [versioned repair path](docs/NATIVE_REPAIR_V2.md) adds seconds-long causal history, transported presentation ACKs, BWE-bounded/dwell control, a stricter supported risk screen, three-seed delayed-credit training, fresh selected-controller calibration, streamed sources and isolated warmup. Eight smoke captures and 96 additional role-disjoint Chrome/VP8 exploration captures complete; a three-seed repair model is now fitted and its actual weights pass 120-step Python/JS parity. **The calibrated V2 controller is rejected before validation:** its 24 fresh controls pass repeatability but deliver 55.8% on-time versus BWE's 81.3%, with zero eligible learned actions in 1,348 actual decisions. The [separate V3 recipe](docs/NATIVE_REPAIR_V3.md) fixes fallback identity and adds causal sender-content features and per-action risk heads; eight untouched native smoke peers now pass full immutable replay (metadata-only recovery after an outer timeout, no recollection); the fitted V3 model is also rejected after selected calibration (zero useful departures in 682 decisions). The [separate V4 GCC-deferring path](docs/NATIVE_REPAIR_V4.md) preserves neural risk/BWE/use gates, keeps the old BWE comparison and adds native-GCC superiority checks; its ten-peer raw audit passes but unlimited GCC fallback is rejected (9.6% on-time versus BWE's 80.9% on that matched diagnostic). The [independent V5 repair](docs/NATIVE_REPAIR_V5.md) restores conservative fallback, requires fixed-framerate preference readback, expires the RTT baseline and implements normalized factual IQL with fresh two-movie fitting roles. All twelve new diagnostic peers pass full immutable replay and actual encoder readback; fixed-600 reaches 91.5% on-time versus matched BWE 85.7% on one group. Both fresh 96-peer two-film/four-family training and calibration panels pass full raw replay with all seven factual actions; the real three-seed checkpoint passes 160-step actual-weight Python/JS and isolated-package parity. Fresh selected calibration rejects the checkpoint: only 2/680 genuine executed decisions (0.29%), then all actions are risk-vetoed. A separate [scalar-control mechanism probe](docs/NATIVE_DENSE_PROBE.md) now tests the quantization/BWE dead zone against continuous 85%-BWE; it is not a learned model. Eight diagnostic peers now complete and raw-replay. A separate [bounded action-outcome candidate](docs/NATIVE_ACTION_MODEL_V1.md) implements causal scalar histories and exact-cap/context calibration; its new neural fit and group-held-out skill checks use only legal train/calibration parents, not diagnostic or selected labels. A separate [legal exact-cap coverage pipeline](docs/NATIVE_ACTION_COVERAGE_V1.md) adds the missing 400/450/500-kb/s factual collection path while preserving source roles, physical-group counting and every original gate. All 96 exact-cap augmentation peers and the separate V2 refit now complete: missing finer-cap factual support is removed, but no native gain is established. V2's recorded-input probe yields **9.14% shadow departure intents**, not executed learned actions. An [isolated live action-outcome probe](docs/NATIVE_ACTION_LIVE_V1.md) adds frozen learned aliases, legacy/continuous-BWE controls and complete raw audit; its first 16-peer/two-group actual comparison now completes and fully raw-replays, with **78/1,358 genuine learned decisions (5.74%)** and zero learned-budget/tail failures. **Repeatability fails** (stable-alias span 14.50 utility / 63.22 on-time pp), and aggregate quality is worse versus legacy BWE despite positive descriptive contrasts with continuous BWE. Stable executes no learned departures; read-only diagnosis identifies a fallback/buffering/deadline-control hypothesis, not a proven neural gain. Native selected-policy calibration, qualification and SOTA remain open. No V5 checkpoint is promoted. Original checkpoints and failed outcomes remain unchanged.

A [separate fallback-growth-hold comparison](docs/NATIVE_ACTION_GUARD_V1.md) completes and raw-replays **24 fresh Sintel peers / 12,988 requests**, preserving all **1,002 saved files**. It executes 1,007 held-growth fallback steps with zero neural credit; genuine use and timing pass, but **both guarded/unchanged mappings fail collapse repeatability**, and the guard loses to unchanged V2 and both BWE references. All negative phases are retained. **The guard is not adopted; native deadline instability, selected calibration and SOTA remain unresolved.**

[Causal identified-readback transport](docs/NATIVE_PRESENTATION_V1.md) now supplies a separately logged sender sidecar without changing the trained ACK-age feature or policy. Eight new native peers actually transport 1,200 readback packets and pass public raw replay; 368 saved files remain unchanged. This fixes wire observability only, **not** a proven deadline/controller gain, selected calibration or SOTA.

A [train-only action-value qualification check](docs/NATIVE_ACTION_VALUE_SKILL_V1.md) finds a learning blocker hidden by the original action-average-prior proxy: on **24,335 factual training rows**, proposed action adds only **+0.7437% / -0.3649%** utility skill over an identically trained state-only control, failing the unchanged 1% requirement in both physical folds. **98.0851%** of factual actions equal the previous cap already in state. An independently recomputed, externally receipt-pinned **opt-in** actor interface rejects actual V2 before initialization; 32 new invariants, 57 adjacent checks and actual extracted-wheel rejection pass. Old weights, defaults and native outcomes remain unchanged. **The missing qualification check is removed, not the model/data/native-control or SOTA blockers.**

A [separate randomized-hold/credit intervention](docs/NATIVE_ACTION_EXCITATION_V1.md) now completes **48 train-only Chrome/VP8 peers** with **672 uncontaminated cohorts / 8,071 requests**, all three caps and **69.64% changed-action** cohorts. This addresses near-total prior-cap coupling, not a proven encoder/quality effect. The once-only new-data six-conditional/six-blind grouped comparison still fails fixed 1% utility skill (**+0.2274% / -4.4866%**); its original proxy also fails. Complete public raw replay, 1,800 preserved native artifact hashes, saved-weight numerical replay and actual extracted-wheel evidence pass. A separate filename-only read-only auditor repairs replay without changing frozen producer/data. **Learning, causal native control, selected calibration and SOTA remain blocked; no old/default model is changed or promoted.**

A [read-only response diagnosis and compact neural development recipe](docs/NATIVE_ACTION_COMPACT_HOLD_CV_V1.md) identifies 89.75×/133.02× fit-versus-held utility error gaps on those actual cohorts. A separately frozen **786-parameter** model mitigates that generalization defect, lowering held utility MSE **58.7932% / 54.9981%**, with held/fit ratios 1.32×/2.35×. **Action information still fails 1% (−3.3981% / +0.0615%)**, even though the original action-prior proxy becomes green. This is reused-training-fold development, not independent/native/SOTA validation; all twelve forecasts fail the actual native actor ABI. Seventeen response plus eighteen model tests, numeric/extracted-wheel replay and five resealed-forgery rejections pass. Old weights/defaults remain unchanged; actual encoder target/QP response still needs separate measurement.

A [separate native encoder sidecar](docs/NATIVE_ENCODER_RESPONSE_V1.md) removes the previous missing target/QP telemetry: **169/169 actual Chrome samples**, **167 valid same-cap intervals**, one conventional fixed450 train-reservation peer and zero refits. Actual target spans **232.5–450 kbps** under a 450-kbps cap. Full original native/extracted-wheel replay, 19 Python/four Node checks and six resealed-forgery rejections pass. The original actor observation/defaults/models remain unchanged; availability does **not** prove encoder response lag, causal quality gain or SOTA.

A [preregistered four-peer longer-hold test](docs/NATIVE_ENCODER_LONG_HOLD_V1.md) identifies an **asymmetric credit-timing blocker**: observed encoder-target increases take **1.16–1.60 s** (10/14, four censored), versus **101–112 ms** decreases (10/10). The old 200–600-ms window often precedes upward response. Both repeated sequences show later QP evolution; quality variance/confounding still prevents causal-value acceptance. **679 actual samples / 1,494 band requests**, 16 Python/two Node tests, full native/extracted-wheel replay and seven forged-case rejections pass. No model refit or old credit/threshold/default change within that timing probe; the separate prospective repair below now completes.

A [separate prospective 32-step/1800–2200-ms hold/credit repair](docs/NATIVE_ACTION_LATE_CREDIT_V2.md) now supplies **48 actual train-only peers / 160 late factual cohorts / 1,944 requests / eight original physical groups**, retaining all **42 target-unsettled cohorts**. The fixed twelve **786-parameter** neural comparison passes the unchanged **1% conditional-versus-matched-blind development criterion (+1.4258% / +6.8950%)** on the exact old physical folds. Complete native/raw/credit and actual extracted-wheel model/numeric replay, seven resealed-forgery rejections and twelve actual native-actor ABI rejections pass. This is **necessary training-development action information, not independent validation, universally settled targets, selected transient-risk calibration, safe native control or SOTA**. Earlier negative artifacts/models/defaults remain unchanged.

A [new frozen role-disjoint forecast validation](docs/NATIVE_ACTION_LATE_VALIDATION_V3.md) now checks six once-only all-training forecasts against **24 fresh conventional peers / 80 factual late cohorts / 971 requests / four original groups**. The complete 56-input role scanner finds **ToS exhausted**; a wholly new [official CC-BY Blender Big Buck Bunny source](https://peach.blender.org/about/) preserves original credits and remedies that bounded data-access blocker without reusing role footage. **Action information does not replicate: +0.5366% pooled / −2.2405% Sintel / +1.5466% unseen BBB; physical-group interval [−6.7420%, +2.5261%] crosses zero.** Risk is also worse than matched blind despite green prior-proxy skill. Complete original native/public/extracted-wheel replay, seven resealed-forgery rejections and six actual native-ABI rejections pass. **No validation fit/retuning, learned native steps, promotion, selected calibration or SOTA; out-of-training-context value generalization remains blocked.** Old development evidence/models/defaults remain unchanged.

A [training-only diagnosis and separate balanced-assignment pilot](docs/NATIVE_ACTION_BALANCED_HOLD_V1.md) now removes a concrete **local data-exposure gap**: the old two shared-alias repetitions give **0/40 matched group/epoch contexts with all three arms**. The new seed-only three-repetition arm/previous-current-balanced sampler completes **9 genuine native peers / 30 factual cohorts / 365 requests**, **5/5 all-arm contexts / all nine transitions**, retaining all nine target-partial cohorts. **18 Python/3 Node**, full original public/extracted-wheel raw replay, 360 exact Python/JS cases and seven resealed-forgery rejections pass. **No refit, validation-target use, learned native action, causal/generalization/safety/SOTA claim**; one physical-group pilot does not repair the frozen model's failed replication. Original models/defaults/development/validation bytes remain unchanged.

A [prospective multi-context balanced training study](docs/NATIVE_ACTION_BALANCED_MATRIX_V2.md) is **blocked at native peer 17/36**: 16 independently replayed complete peers / 50 partial cohorts / 603 requests, no complete source or model fits. A separately versioned metadata-only adapter repairs actual episode-ID truncation **U103→U109** without changing numeric inputs/folds/recipe; **19 Python checks** and isolated actual partial replay/public no-fit rejection pass. The failed native snapshot summary was not persisted, so its exact stats predicate is unknown. No retries, gate relaxation, partial fitting, new generalization or SOTA claim; old weights/evidence/defaults remain fixed.

[Native before-rejection evidence is now preserved](docs/NATIVE_FAILURE_EVIDENCE_V3.md) without weakening original validity gates. Atomic host-side ledger/count/gzip capture fixes a real four-event diagnostic observer effect; read-only role metadata repair keeps diagnostic cohorts out of training. **23 Python / 15 Node**, one actual corrected native diagnosis (**3 snapshots / 5 diagnostic cohorts / 60 requests / 39,596 events**), full original raw/quality/encoder installed-wheel replay, seven source-aware resealed forgeries and diagnostic-as-training rejection pass. Original failed panel/validation/models remain unchanged; this is observability, **not generalization/native improvement/SOTA**.

A [fresh atomic four-context balanced training study](docs/NATIVE_ACTION_ATOMIC_MATRIX_V4.md) now completes **36 conventional peers / 120 cohorts / 1,456 requests**, all-arm exposure in **20/20 strata** and all nine transitions per group, outside **65 earlier role inputs**. The once-only unchanged twelve-forecaster comparison uses **280 rows / 3,400 requests / 12 groups**. **Action information still fails: −1.07788% pooled; group interval [−5.61132%, +2.18487%]; both folds are negative.** **19 Python / four Node**, actual full native/numeric/extracted-wheel replay, fourteen executing-source hashes, sixteen resealed semantic rejections and twelve native-actor ABI rejections pass. No old model/default/validation change, tuning, native promotion or SOTA; completed balanced exposure is not sufficient evidence of generalization.

A [training-only diagnosis of the fixed negative models](docs/NATIVE_ACTION_ATOMIC_DIAGNOSIS_V2.md) now attributes the net error gap mainly to ToS, rules out dead hidden units, and verifies alias/encoder/gradient/sampling variability. A separate **opt-in ordered32-step projection** removes provable summary-order invariance while preserving old92 features/state/actions; **no model is fitted or default changed**. Actual full/current/ordered inputs have the same26 duplicate pairs, so no real collision or performance improvement is claimed. **17 Python checks**, isolated actual12-model replay andeight semantic reseal rejections pass; action generalization/native/SOTA remain blocked.

## Published RTC peers — original checkpoints, offline replay only

The [pinned published-peer interface](docs/PUBLISHED_RTC_PEERS_V1.md) now runs the original **Schaferct MMSys 2024 winner** and organizer ONNX baseline locally. **4,148 public observation rows** match the original reference feed/channel exactly, pass read-only audit and remain invariant to poisoned capacity/quality labels. Native 64-input histories are rejected rather than padded. Optional `rtc-peers` installs the locked CPU runtime; `rtc-peer-list`, `rtc-peer-inspect`, `rtc-peer-replay` and `rtc-peer-audit` are public CLI commands. **This is not closed-loop QoE evidence or a SOTA claim**: compatible receiver features and transport/encoder actuation remain unverified.

## Verified local evidence

The current implementation passes **661 Python tests** and **117 native Node tests**. Completed evidence includes the **10-seed v1 scale-up (19,800 episodes / 11.88 million intervals)**, v2 safety refit, v3 threshold selection (5,500 validation and **7,700 fresh-test episodes**), v4 policy randomization (**7,700 validation plus 7,700 fresh-test episodes**), v5 action screening (**2,200 validation plus 8,800 fresh-test episodes**) and v6 selected-action recalibration (**40 ID calibration episodes per source seed, 2,200 validation and 8,800 fresh-test episodes**). V2–v4 candidates retained v1; v5 and v6 validation selected their screen variants. See [`docs/verification.md`](docs/verification.md), [`docs/IMPROVEMENT_V2.md`](docs/IMPROVEMENT_V2.md), [`docs/THRESHOLD_SELECTION_V3.md`](docs/THRESHOLD_SELECTION_V3.md), [`docs/POLICY_RANDOMIZATION_V4.md`](docs/POLICY_RANDOMIZATION_V4.md), [`docs/SAFETY_SHIELD_V5.md`](docs/SAFETY_SHIELD_V5.md), [`docs/ACTION_CALIBRATION_V6.md`](docs/ACTION_CALIBRATION_V6.md), and the stage reports.

**Measured outcome:** relative to matched calibrated v1, the v5 screen improved ID QoE by 0.0259 (95% model-seed interval [0.0135, 0.0387]) and reduced ID violation rate by 0.00144 on the fixed synthetic panel. OOD QoE and violation effects were inconclusive; GCC-like and heuristic baselines still offer better ID tradeoffs. V2–v4 candidate outcomes remain negative or unpromoted. The original v1 weights/gate remain the learned reference, while v5 adds a validation-selected action-screen variant. All findings are synthetic; the screen is not a safety guarantee. Do not use the final traces for further tuning.

**V6 measured outcome:** recalibrating on screen-selected ID actions while freezing policy/safety weights was promoted on validation. On its disjoint 8,800-episode synthetic test, the recalibrated screen improved ID QoE by 0.022 [0.009, 0.036] and reduced ID violations by 0.050 percentage points [0.007, 0.100] versus v1. Stress/OOD QoE improved, but its violation interval includes zero. OOD selected-action confidence remains 5.09 points optimistic [4.51, 5.71]; this is not an OOD safety guarantee.

- **V7 audited result:** validation promoted `shielded_uncertainty` by a narrow score gain of 0.005073. The 8,800-episode fresh panel found negligible ID effects and a small OOD violation change of -0.083 percentage points (10-seed interval [-0.209, -0.0005]); the cutoff activated on just 0.24% of stress steps. This conditional result does not close the GCC-like OOD gap or establish a safety guarantee. Audited outputs: `results/uncertainty-shield-v7/final-campaign/test` and `paper/generated-uncertainty-shield-v7/`.

**V8 audited outcome: not promoted.** The 1,100-validation / 8,800-test episode wire-budget study keeps all ten V6-derived bundles unchanged. Validation rejects its 0.0946 ID-QoE drop (limit 0.03). On the fresh panel, stress violations fall 2.862 percentage points [1.986, 3.724 reduction], but ID/stress QoE falls 0.104/0.133; confidence eligibility adds no resolved violation benefit over the matched budget-only ablation. V7 remains the locked choice. See [`docs/BUDGET_SHIELD_V8.md`](docs/BUDGET_SHIELD_V8.md), `results/budget-shield-v8/test` and `paper/generated-budget-shield-v8/`. All intervals condition on the fixed synthetic panel.

**V9 audited outcome: partial repair, not promoted.** The delay-evidence budget/fallback variant completes 1,650 validation and 9,900 fresh-test episodes with unchanged models. Compared with V8 on this new panel, burst-loss QoE recovers **1.160** with unchanged observed violations, but ID quality still fails validation (0.1109 drop; limit 0.03), so V7 remains selected. Confidence eligibility adds a small conditional stress-risk regression versus the matched ablation. Protocol, exact effects and limitations: [`docs/DELAY_BUDGET_V9.md`](docs/DELAY_BUDGET_V9.md).

## Realistic transport and model retraining (V10)

```sh
# Choose a fresh output directory; the completed canonical study is immutable.
uv run --frozen media-rl realism-study --config configs/realism_v10.json --out results/realism-v10-reproduction --no-plots
```

The completed **three-seed / 1,188 fresh-test episode** study adds a causal 16-feature history policy, GCC-only demonstrations, broader stress data and deadline-resolved capture-cohort safety labels. Compared with matched retrained RLCD on the same packet physics, nominal QoE gains **0.1395** and nominal/stress unsafe frequency drops **8.623/7.030 pp**. GCC-like still leads quality; validation **rejects** the candidate because stress-quality gain misses the frozen bound. Test data does not override that choice. `fluid_v1`, old model behavior, V7 selection and the nine-study PDF remain unchanged.

Details and remaining realism/conventional gaps: [docs/REALISM_V10.md](docs/REALISM_V10.md). Canonical numerical results: `results/realism-v10/results.json`; independent all-row/statistic/replay/provenance receipt: `results/jobs/realism-v10-evidence-check.json`. Extra demonstration compute, bundled changes, trained stress families and synthetic codec/FEC/quality proxies limit the claim.

## Continuing competitiveness work (V11)

Opt-in `training.n_step` supports delayed-return credit while **n=1 remains bit-exact and the default**. The completed five-seed study (`configs/n_step_v11.json`) covers **1,320 validation + 1,980 fresh-test episodes** with equal TD/demo budgets. Validation **rejects n=3**; gated fresh-test effects are inconclusive, and GCC-like still leads quality. All **792,000 rows**, ten models, twenty intervals and historical artifact preservation are independently audited.

Details: [docs/DELAYED_CREDIT_V11.md](docs/DELAYED_CREDIT_V11.md). Independent real-codec burst/quality and inference diagnostics are recorded separately—not substituted for genuine RTC/SOTA evidence. The active evidence checklist and next development intervention are in [docs/SOTA_TRACK.md](docs/SOTA_TRACK.md).

## Paper and model refinement

```sh
# Audited nine-study tables, figures and PDF
make paper
# Reproduce/reuse hash-audited completed studies under identical settings/code
uv run media-rl improve --config configs/improve_v2.json \
  --models results/paper-v1 --out results/improvement-v2
uv run media-rl tune-threshold --config configs/threshold_select_v3.json \
  --models results/paper-v1 --out results/threshold-selection-v3
# Frozen v4 domain-randomized policy training; validation locks promotion before fresh test
uv run media-rl policy-randomization --config configs/policy_randomization_v4.json \
  --models results/paper-v1 --out results/policy-randomization-v4
uv run media-rl audit --run results/policy-randomization-v4/test
# V5 action-level screen; validation lock precedes a disjoint fresh test
make safety-shield-v5
uv run media-rl audit --run results/action-shield-v5/test
# V6 one-pass selected-action recalibration (policy/safety weights frozen)
make action-calibration-v6
uv run media-rl audit --run results/action-calibration-v6/final-campaign/test
# V7 complete; the initial partial test is preserved separately
uv run media-rl audit --run results/uncertainty-shield-v7/final-campaign/test
# V8 is complete but rejected; audit preserved test evidence, not a retuned candidate.
uv run media-rl audit --run results/budget-shield-v8/test
# V9 repairs burst-loss quality but still fails the nominal-quality promotion bound.
uv run media-rl audit --run results/delay-budget-v9/test
```

The updated draft is **`paper/build/main.pdf`**, source `paper/main.tex`. Separate evidence directories (`paper/generated-scaleup`, `paper/generated-followup`, `paper/generated-threshold`, `paper/generated-randomization`, `paper/generated-shield`, `paper/generated-action-calibration-v6`, `paper/generated-uncertainty-shield-v7`, `paper/generated-budget-shield-v8`, `paper/generated-delay-budget-v9`) prevent mixing studies; each has a provenance record. The pilot manuscript is archived. See `paper/README.md` for reproduction and remaining submission blockers.

`evaluate` also supports `--split validation` and `--model-map FILE` for explicit per-method checkpoint references (relative paths resolve against the map file). Evaluated runs retain copied references and a portable model map. `improve`, `tune-threshold`, the v4 policy-randomization and v5 safety-shield campaigns hash inputs, lock validation selection before opening test traces, and refuse to reuse partial stages or changed code/settings. The v4/v5/v6 protocols are frozen in [`docs/POLICY_RANDOMIZATION_V4.md`](docs/POLICY_RANDOMIZATION_V4.md), [`docs/SAFETY_SHIELD_V5.md`](docs/SAFETY_SHIELD_V5.md), and [`docs/ACTION_CALIBRATION_V6.md`](docs/ACTION_CALIBRATION_V6.md); all results remain synthetic.

## Interpretation boundaries

A probability of 0.9 means an **estimated next-step constraint-satisfaction probability**, not 90% confidence in optimality or a guarantee of long-horizon safety. Calibration on ID data need not transfer to OOD conditions or the gate-induced state distribution. A conservative fallback cannot repair an outage or create bandwidth. Report all baselines and negative findings; do not assume calibrated RL beats GCC-like control. Synthetic QoE is not MOS/VMAF, latency is a fluid virtual-delay proxy, and FEC is not a codec implementation. Real WebRTC, packet-level emulation, real traces, multi-flow fairness and human perceptual validation are future work.
