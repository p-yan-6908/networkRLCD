# Fresh native RLCD training V1 — fitted candidate, not promoted

## What is actually complete

`configs/native_training_v1.json` froze **six training plus two calibration** owned Chrome/VP8 episodes before collection. Traces vary high/collapse/recovery rates and phase duration; independent generated-scene time offsets vary motion/content phase. These are still synthetic same-host traces and generated content, not natural-video or measured-link generalization.

Each episode uses an independent seeded permutation of **all seven supported caps** in one-second blocks, with verified zero native receiver target. All eight captures cover every cap. Independent wire, pixel-ID/CRC, quality and sender replay audits seal **20 artifacts per episode** plus a panel manifest. The original conventional runs and legacy promotion/test artifacts are not modified.

Actual panel totals: **736 causal decisions**, **2,273 outcome-complete source opportunities**. Clean acknowledged-action labels produce **543 training / 180 calibration transitions** and **1,703 / 567 source requests**; transition/unassociated source labels are excluded, never reassigned to future decisions. Late/missing/unidentified requests remain zero-quality, missed-deadline opportunities. No outcomes means no transition, not fabricated zero reward.

## Native-only model and learning

- `src/media_rl/native_dataset.py`: frozen panel/episode/source checks, raw sender/quality recomputation, causal zero-padded **4×16→64** history and factual action labels. Three-step returns stop at missing/terminal decisions and never cross episodes. State excludes proxy capacity/queue, phase, source/receiver pixels and future outcomes.
- `src/media_rl/native_learning.py`: fresh **64→64→7** Double-DQN/CQL actor, **2,400** updates, batch 64, CQL alpha **0.05**, target copy every 80; **three 71→32→1** factual frame-miss risk models, **1,200** updates each with whole-episode bootstrap. Native model seed **1301**; no simulator/legacy weights loaded.
- Reward is on-time sampled RGB PSNR/100 minus **0.2×miss fraction** and **0.005×cap change**, gamma **0.97**, n=**3** per observation step. This timing/quality proxy is not human QoE or VMAF.
- Calibration uses only the two declared calibration episodes. Frame-miss probabilities concern factual source requests beyond the **150 ms application readback deadline** or remaining unidentified, not an episode safety guarantee.
- **In-sample calibration** frame Brier goes **0.2247→0.1685** after Platt fitting. This includes the per-frame Bernoulli variance, unlike fraction MSE. The fitted-fold score is not held-out performance, an RL improvement or promotion evidence.
- Provisional predicted miss/disagreement screens **0.5/0.2** are not validation-selected. Unsupported predictions use the causal BWE-headroom rule. All actor outputs are the seven verified zero-target caps within the **14-action native ABI**, not simulator actions.

`benchmarks/native_rtc/native_policy.mjs` exports native-only manifest/matrix validation, matching portable JS inference and past-only history. Legacy equal-width/42-action manifests reject. Real fitted-weight parity covers **31 causal histories × 3 screen branches**, with exact action/fallback equality and worst numerical difference **3.55e-15**; this runs in Node, not a live WebRTC peer.

The training-only checkpoint passed **203 Python + 49 Node tests**; the subsequent live/cadence work passes **222 Python + 51 Node tests**. Prototype caveats remain: a tiny single-model data panel, current native GCC as lower-layer controller, command-ack versus exact internal encoder timing, synthetic sampled-pixel labels, simple collapse schedules and no frozen native quality/risk comparison. At this training-only freeze the policy had **not run online**. The later [18-episode live development panel](NATIVE_DEVELOPMENT_V1.md) executes the frozen model, finds a BWE-relative deficit and does not promote it. No model promotion or SOTA statement is justified; V7 remains the selected legacy model.

## Artifacts and commands

- Data: `results/native-training-v1/{panel.json,summary.json,manifest.json}` and eight frozen episode subdirectories.
- Candidate: `results/native-model-v1/{model.json,training_report.json,manifest.json}` plus exact training/source snapshots.
- Receipts: `results/jobs/native-policy-v1-parity.json`, `native-model-v1-{python,node}-tests.log`, `native-training-paper-evidence-check.json`.
- Paper-only macros: `paper/generated-native-training/`, independently recomputed by `.tools/export_native_training_paper.py`; `make paper` registers this exporter alongside all existing formal studies. A paper build does not collect Chrome runs or refit weights.

```sh
# Current completed panel can be verified/resumed without recollecting sealed episodes.
uv run --frozen .tools/collect_native_panel_v1.py
# Trainer refuses an existing output rather than overwrite the frozen candidate.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run --frozen .tools/train_native_v1.py
uv run --frozen .tools/probe_native_policy_parity.py
uv run --frozen .tools/export_native_training_paper.py
make paper
```

Subsequently completed: the [live development comparison](NATIVE_DEVELOPMENT_V1.md) is negative versus BWE. Next, test cadence-matched control/selected-action calibration on fresh independent cases, not these development outputs. The original pre-live plan was to freeze a prospective live-peer development comparison with identical observations/instrumentation, source/traces and conventional controls; verify every learned decision against frozen Python inference and raw outcome/wire evidence. Inspect high-phase quality harm as well as aggregate deadlines. Only then design role-disjoint native validation/promotion and final tests; genuine published learned peers and representative natural/measured panels remain unmet SOTA requirements.
