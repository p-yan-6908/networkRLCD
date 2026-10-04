# Native RLCD live development V1 — negative versus BWE, not promoted

## Frozen comparison and real execution

`configs/native_development_v1.json` declares **six** new source/schedule configurations, counterbalanced orders and **18** independent owned Chrome/VP8 executions: fixed 4 Mbps cap, 85% causal native-BWE cap and the **unchanged** fresh native RLCD model. All use the native 16-feature/4-step input and seven zero-target cap subset, with native GCC underneath. The original model SHA remains `46824918cb01fe65f3107fe808b0f9fcd7f583cf9dfab9df500a63698b8a6a64`.

Every control performs the same neural **shadow inference** and frame/quality/sender instrumentation; only the RLCD condition actuates model output. These are matched source/schedule templates, **not identical stochastic packet traces**, natural-video/Internet-path observations or a published learned-peer panel. Stable cases keep capacity at 2 Mbps throughout; their middle/last phase labels are positions, not real collapse/recovery events. No threshold/model/gate is changed after seeing outcomes.

Independent native replay covers **1,536 decisions**, including **512 actually actuated learned decisions**, **4,846 complete source opportunities** and **3,220 paired sampled-pixel observations**. All **450 episode artifact hashes**, raw packet FIFO/service/admission/propagation, CRC identity, source/ack clocks, terminal censoring, native command readbacks, four-step histories and all seven neural score vectors are checked. Maximum model-score discrepancy is **7.11e-15**; maximum per-run inference p99 **3.98 ms**, under a provisional 10 ms target, not a deployment/worst-case certificate.

One capture was genuinely unassociated/in-flight at **exactly** the first acknowledgment's coarse browser timestamp. The audit stopped, inspected immutable raw evidence, then quarantined that initial-action tie without recollecting a run or manufacturing a clean factual label. Future unassociated requests, clean/assigned boundary forgeries and stale next-ack assignments reject. Existing capture outcomes are unchanged.

## Actual descriptive tradeoff

Means give each source/schedule case equal weight; one model and short independent executions do **not** provide statistical superiority, native validation/promotion or unseen generalization.

| Control | On-time sampled PSNR utility / eligible request | On-time opportunities |
|---|---:|---:|
| Fixed cap | 14.891 | 45.66% |
| BWE-headroom | 18.921 | 69.45% |
| Fresh native RLCD | 16.413 | 57.49% |

RLCD versus BWE: **−2.508 utility**, **−11.969 on-time percentage points**, despite **+7.353 first-phase utility**. Versus fixed cap, aggregate utility is **+1.522**, but first-phase utility is **−8.532** and both steady-link runs lose overall quality. Choosing a winning aggregate or comparator would conceal harms. **No promotion; V7 remains selected; SOTA is unachieved.**

The utility is mean on-time sampled synthetic RGB PSNR dB per source opportunity; late/missing/unidentified outcomes contribute zero. It is neither VMAF/human QoE nor the fluid simulator's QoE scale. The endpoint remains **150 ms application request→pixel readback**, not physical capture/scan-out.

## Measured failure hypotheses and next intervention

The risk ensemble predicts **35.84%** misses on clean factual RLCD requests; **42.32%** actually miss. First-phase predictions **16.82%** versus observed **30.15%** are optimistic. Candidate caps exceed the causal BWE-headroom/minimum-cap budget on **9.88%** of factual requests (BWE control **0%** after correct Mbps→bps conversion). These are descriptive, selected-policy development metrics, not proof of causal failure or a safety bound.

RLCD makes **149** cap changes. **134/143** changed-command intervals are shorter than its **1,000 ms training exploration blocks**; median intervals range **110–219 ms**, with **35** changes in each steady-link run. A plausible training/live cadence and selected-action confidence shift must be investigated rather than just train longer.

A provisional **prediction-screened cadence arbiter** now exists as `native_cadence_action` in `src/media_rl/native_cadence.py` and `nativeCadenceAction` in `benchmarks/native_rtc/native_cadence.mjs`. It holds a still-predicted-eligible current cap until 1,000 ms since its owned changed-command acknowledgment, but **immediately releases** fallback or predicted-unsafe current caps. Owned elapsed command time is arbiter state, not an added neural/oracle feature. Eight Python/two Node boundary/forgery tests and exact cross-language parity on **512 actual fixed inputs** pass; Only **27** same-input proposals would change, so this restricted guard cannot be assumed to resolve most observed churn. That is **not a counterfactual trajectory/outcome estimate**. At this V1 checkpoint the prototype had not run in a live peer. The subsequent [actual V2 study](NATIVE_CADENCE_V2.md) tests it, finds steady-link harms and does not adopt it. No safety/performance guarantee follows.

Subsequently completed: [V2 live cadence comparison](NATIVE_CADENCE_V2.md), without adoption. The original prospective plan was to integrate and independently replay that arbiter, freeze fresh source/schedule cases comparing unchanged native RLCD/BWE/cadence candidate, and check actual nominal/steady/collapse quality and deadlines. Also collect separate selected-policy confidence calibration data; do not fit on this development panel or reuse it as final validation/test. Genuine published learned peers, representative natural/measured panels, multi-model/group uncertainty and native validation/final-test gates remain unmet SOTA requirements.

## Commands and evidence

```sh
# Completed roots are immutable; fresh outputs are required for collection.
uv run --frozen .tools/run_native_development_v1.py
uv run --frozen .tools/audit_native_development_v1.py
uv run --frozen .tools/diagnose_native_development_v1.py
uv run --frozen .tools/probe_native_cadence.py
uv run --frozen .tools/export_native_development_paper.py
make paper
uv run --frozen .tools/verify_native_development_paper.py
```

`results/native-development-v1/` seals the panel and 25 artifacts per run. Receipts: `results/jobs/native-development-v1-final-evidence.json`, `native-development-v1-diagnosis.json`, `native-cadence-prototype-evidence.json`. Full regressions: **222 Python + 51 Node pass**. `paper/generated-native-development/` is independently regenerated from the full replay/diagnosis; paper builds never recollect or retrain. Historical training/model and legacy promotion/test artifacts remain unchanged.
