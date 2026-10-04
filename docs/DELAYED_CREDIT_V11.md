# V11: delayed-return credit, not a SOTA claim

## Evidence and mechanism

Opt-in `TrainingConfig.n_step=3` makes the Double-DQN target

`sum(i=0..h-1, gamma**i * r[t+i]) + gamma**h * (1-done) * Q_target(s[t+h], argmax Q_online(s[t+h]))`.

`h` is the actual prefix length; terminal prefixes are truncated/flushed and never bootstrap into another episode. The default remains **n=1**, with bit-exact policy/log parity tested against the hash-pinned V10 training fixture for both fluid and history/demo/packet recipes. Historical V10 config digests normalize only missing n=1, never n=3. States are captured by value, replay wraps correctly, and each decision still yields exactly one replay sample/TD-update scheduling opportunity.

This is ordinary n-step replay for delayed mixed-cohort reward, **not a novel algorithm, exact frame-action attribution, off-policy correction or a safety certificate**. We use truncated behavior-policy returns without importance corrections; longer returns can add off-policy bias. Only matched empirical evidence can decide whether the change is helpful. No state/future trace or scenario label enters the controller.

## Development pilot

`results/n-step-v11-pilot` uses new model seed 70 / development trace ID 20001. The only training change is n=1→3; history, GCC demonstrations, cohort safety target and all budgets/controls/physics/trace bytes match. Both recipes perform **7,169 TD updates** with the same demonstration warm-start/continuing-update counts.

| Calibrated RLCD metric | n=1 | n=3 |
|---|---:|---:|
| Nominal QoE | 0.8394 | 0.8241 |
| Stress QoE | 0.1074 | 0.1570 |
| Nominal unsafe (%) | 13.542 | 13.646 |
| Stress unsafe (%) | 27.143 | 27.024 |

GCC-like has 0.9744/0.3471 nominal/stress QoE and 23.333/32.857% unsafe frequency on the same panel. Screening/ungated outcomes are preserved in `summary.json`, not promoted post hoc. A helper-only `plots` keyword mistake stopped after baseline training; the baseline was then SHA/config/source-verified and reused, not retrained/overwritten. The original failure log remains in `results/jobs/n-step-v11-pilot.log`. This single seed is **development**, not significance or independent final-test evidence.

## Frozen five-seed protocol

`configs/n_step_v11.json` compares the stronger but unpromoted V10 history/demo/cohort recipe with itself, not with the weaker original-data recipe. Five new model seeds **74/85/96/107/118**, validation trace IDs **20101/20102** and fresh-test IDs **21101–21103** are distinct from development/V10 panels. The **only configured training difference is n_step**. Identical 120 online RL episodes, 30 demo episodes / 20 cloning epochs, exploration, architecture, 60/60 safety/calibration episodes, weighted schedules, action ladder, conventional implementations, gate parameters and packet physics. Risk labels/calibrator can change endogenously with policy visitation; this is an end-to-end recipe effect, not an isolated fixed-gate Q comparison.

Predeclared calibration-method selection (`calibrated` only): nominal QoE drop ≤0.03, nominal/stress unsafe increases ≤0.2/0.5 pp, stress QoE gain ≥0.03 and equal-weight QoE/risk score gain >0.01 (risk weight 2). Selection/model/source/validation hashes are locked **before test**, and both recipes/all six methods are tested regardless of rejection. Twenty paired test intervals use five model-seed clusters, never individual time steps as independent trials. This is still synthetic prototype evidence, not sufficient by itself for SOTA.

Completed panels: **1,320 validation + 1,980 fresh-test episodes**, **792,000 combined raw control rows**, including 475,200 test rows. Censored terminal frame/cohort labels are disclosed and excluded from reliability/fitting, not counted successful. Old canonical studies/PDF and legacy physics remain untouched.

```sh
uv run --frozen media-rl realism-study --config configs/n_step_v11.json --out results/n-step-v11 --no-plots
# For reproduction, choose a new --out; an existing canonical run cannot be reused/overwritten.
```

## Status

The study completes in **1,009 seconds**; **151 tests** and Ruff lint/format pass. Ten model bundles perform exactly **7,169 TD updates each**; the only configured training difference is n_step.

### Validation rejects n=3

Nominal QoE gain is 0.00603; stress gain **0.00635 < 0.03** and score gain **0.00817 < 0.01** fail the frozen gates. All risk/nominal-quality bounds pass, but that does not override the two failures. **n=1 remains selected** for this ablation, and the V7/fluid-paper choice remains untouched. The strong history/demo reference is itself an unpromoted V10 recipe, not silently a new product default.

### Fresh-test gated effects remain inconclusive

| Calibrated RLCD metric | n=1 | n=3 | n=3 minus n=1 [five-model-seed interval] |
|---|---:|---:|---:|
| Nominal QoE | 0.86635 | 0.88383 | +0.01749 [-0.02321,0.05819] |
| Stress QoE | 0.20438 | 0.20448 | +0.00010 [-0.03024,0.03119] |
| Nominal unsafe (%) | 12.208 | 12.153 | -0.0556 pp [-0.5486,0.3542] |
| Stress unsafe (%) | 24.806 | 24.825 | +0.0198 pp [-0.7143,0.5119] |

GCC-like still wins quality: 1.02436/0.33645 nominal/stress QoE versus gated n=3 0.88383/0.20448, with higher unsafe frequency (23.160/32.143%). Ungated n=3 reaches stress QoE **0.33536** versus GCC-like **0.33645**, but risk is **33.698% versus 32.143%**. The top-five uncertainty screen yields 0.94367/0.24285 QoE and 10.951/23.544% unsafe frequency; it is diagnostic here, not a post-test-promoted method.

The single-seed pilot stress gain **does not replicate reliably in gated performance**. Preserve the refuted hypothesis and optional mechanism; do not retune n/gamma/threshold on these final IDs. A new development panel can investigate whether top-five candidate truncation/gating causes underutilization; it cannot retrospectively convert this rejection into success.

### Independent acceptance receipt

`results/jobs/n-step-v11-evidence-check.json` verifies **2,138 study artifacts**, **422/434** artifacts in each validation/test recipe, **28 implementation files**, ten equal-update/policy-distinct models, **all 792,000 raw rows**, **960 exact runtime replay steps**, and **20 five-seed paired estimates**. Trace/control equality, validation/test separation, label censoring and pre-test model/validation/selection locking all pass. Each recipe excludes 1,320/1,980 censored validation/test proposal labels. All V10 study artifact hashes and canonical V8/V9/PDF bytes are preserved.

### Independent realism/runtime diagnostics

- `results/codec-realism-probe`: fourteen CPU-real-time H.264/VP8 encodes at seven ladder rates on a generated 640×360/30fps/6s pattern. `results/jobs/codec-realism-evidence-check.json` verifies 44 artifact hashes, 2,520 aligned metric frames and exact repeated VP8 payload/PTS/flags. Keyframe/other-frame mean ratios span **1.46–6.21**, showing fixed synthetic 2.5× bursts are not generally calibrated. SSIM/PSNR/VMAF are loss-free, synthetic-content diagnostics, not human QoE/network validation; historical physics/rewards are not changed.
- `results/rlcd-inference-probe`: 9,680 closed-loop warm act() calls on frozen development models. `results/jobs/rlcd-inference-check.json` recomputes all saved percentiles; p99 is **0.12–0.45 ms** below provisional 10 ms. Model loading, receiver callbacks, encoding and end-to-end RTC are excluded; no worst-case certificate or final-model deployment claim.

Exact locked results: `results/n-step-v11/results.json`, `selection.json`, `study_manifest.json`; read-only helper `.tools/verify_n_step_v11.py`. Remaining genuine-baseline/codec/measured-network/generalization/interface/paper requirements are in [SOTA_TRACK.md](SOTA_TRACK.md). **SOTA is not achieved.**
