# Native growth-hold live comparison V1

## Hypothesis and boundary

The previous [live V2 panel](NATIVE_ACTION_LIVE_V1.md) failed identical-policy repeatability, including zero-learned stable-link failures. The [signals-only preflight](NATIVE_FALLBACK_GROWTH_HOLD_V1.md) found fallback growth under sender/ACK congestion. It did not execute a guard or measure its effect.

This **separate local repeatability experiment**, not a new fitted model, implements the fixed preflight rule:

```
if canonical.fallback and (original_sender_hold or fresh_ACK_delay_ms >= 120):
    effective_cap = min(canonical_cap, actual_acknowledged_own_cap)
else:
    effective_cap = canonical_cap
```

It preserves original <=500-ms ACK freshness, BWE budget, supported-cell/risk screens, dwell/reset, scalar [150000,4000000] domain, zero receiver target, codec/geometry/framerate and 64-iteration disposable warmup. No fitted weights, thresholds or outcome labels are changed. Accepted neural proposals are unchanged **on each peer's own actual history**; different actuation can still change later histories/proposals.

`GuardPolicy`/native `RepairPolicy` always compute the canonical policy **and** hypothetical overlay, including in unguarded/BWE peers. Only declared repair peers with `guarded=true` actuate the overlay. The logged `canonical_decision`, `guard_decision`, guard mode and native readback are separately raw-replayed. Modified fallback receives **zero neural credit**, and no canonical probability certifies its modified rate.

## Immutable prospective panel

- Config: `configs/native_action_guard_repeatability_v1.json`.
- New source/measurement ABIs: `recorded_video_action_guard_v1` / `native_action_guard_measurement_v1`.
- **24 peers**, two independent source/schedule groups, two repetitions, fixed order seed **9101**. Repeats are not independent groups.
- Fresh Sintel segments **540–560 s** (stable) and **560–580 s** (collapse), excluding **48** recorded-role input files and the candidate's fitting reservations. Tears of Steel is exhausted; no old/failed source role is recycled.
- Guarded identical aliases `rlcd-a/b`; unchanged V2 mapping aliases `baseline-a/b`; legacy quantized `bwe` and continuous 85%-BWE `bwe-continuous` controls.
- All original gates stay fixed: alias utility span <=3, on-time span <=15 pp, inference p99 <=10 ms, genuine model use >=5%; selected validation still requires at least eight independent groups.
- Complete whole-panel and high/collapse/recovery contrasts against **every** reference are descriptive. Independent validation, selected-policy calibration, multiple fitted-model uncertainty and external compatible learned peers remain missing.

The collector is a checked namespace/mode/provenance projection of the untouched previous live collector. Isolated Python bindings retain full original raw capture, source ownership, missing-request denominators, readback, feedback-clock, common-predictor and artifact checks. No old module globals or engine files are monkey-patched. An incomplete native prefix is preserved and cannot silently become a replacement/completed panel.

## Verified implementation/package evidence

- **26** new Python invariants; **98** combined guard/primitive/live/canonical Python regressions; **11** combined Node tests (four new guard-control tests).
- `results/jobs/native-action-guard-final-package-proof.json`: **320** actual-weight Python/extracted-Python/extracted-JS mode/step comparisons on recorded fitting-role inputs, three public registrations, **58** planned packaged source hashes and validation of the real frozen config from the extracted wheel. These are software/mapping checks, not guarded native execution.
- Model SHA remains `a4bd1cc2d4e40ce48d32431ea39d70d2a8787cf6692d0711e288ee62e15c5527`. All **601** earlier live parent/raw artifact hashes and all three canonical hashes remain unchanged.
- Final wheel SHA: `3c4733822c2b33236093486b7ac58776be2ad6e521a4c2b0a6c17f59dcd83e29`. The first pre-native wheel/proof is retained separately and byte-exact; the final build adds whole-model decision accounting and frozen-panel verification.

Public commands: `native-action-guard-plan`, `native-action-guard-study`, `native-action-guard-audit`. There are intentionally no guard train/calibrate/validate/test/promote registrations. Existing config/run paths cannot be overwritten.

## Completed native result — guard not adopted

`results/jobs/native-action-guard-native-proof.json` binds **24 completed/raw-replayed peers**, **12,988 eligible requests**, **1,002 saved files unchanged after independent audit**, and **1,182.12 s** runtime. The public `native-action-guard-audit` also verifies the complete panel read-only in `results/jobs/native-action-guard-final-audit.json`.

- **1,007 actual readback-held fallback steps**; these maintain a cap below the canonical growth proposal, not necessarily new setter calls. They receive zero learned credit.
- Guarded genuine model use **94/1,347 = 6.98%**; unchanged mapping **97/1,344 = 7.22%**. All model peers total **191/2,691**. Both original >=5% use gates pass.
- Accepted neural proposals modified: **zero**. Learned BWE-budget violations and >10-ms inference-tail failures: **zero**. Weights, previous failed panel, both versioned wheels and canonical artifacts remain unchanged.
- Stable aliases pass the original spans: guarded **1.052 utility / 2.612 on-time pp**, unchanged **0.744 / 3.490 pp**.
- **Collapse repeatability fails for both mappings:** guarded spans **9.128 utility / 29.413 on-time pp**, unchanged **17.356 / 54.529 pp**. The original limits remain **3 / 15 pp**; a smaller failed span is not a passed gate or established causal improvement.

All repeat-averaged, group-paired descriptive contrasts remain negative:

| Reference | Guarded utility delta | On-time delta (pp) |
|---|---:|---:|
| Same V2, overlay disabled | -1.752 | -3.717 |
| Legacy quantized BWE | -1.233 | -4.292 |
| Continuous 85%-BWE | -3.306 | -7.345 |

High/collapse/recovery losses and gains are retained. The collapse-phase loss is **-14.220 utility / -45.723 on-time pp versus legacy BWE**, **-5.345 / -17.426 pp versus unchanged V2**, and **-6.359 / -19.899 pp versus continuous BWE**; recovery gains do not erase these losses. The two-group conditional bootstrap intervals are descriptive, **not significance, new model independence or causal learned-gain proof**, especially with failed alias controls.

## Read-only diagnosis and remaining blocker

`results/jobs/native-action-guard-repeatability-diagnosis.json` verifies every native file unchanged and joins actual source IDs/presented-frame counts across callback, ACK send and sender receive on the same browser-page clock.

Of the 1,007 holds, **185** use sender alarm alone, **315** both alarms, and **507** ACK alarm alone. **707** held ACK-alarm steps refer to a source whose first identified readback met its deadline. The measured per-peer median readback-to-ACK-send time is only **0.4–0.5 ms**, while ACK-send-to-sender-receive is **27.5–28.2 ms**; capture-to-that-callback medians range **87.4–169.8 ms**. ACK delay includes the return path/scheduling and is not equivalent to first-readback deadline failure. This is **not proof that RGB bookkeeping caused the failures**, or that subtracting RTT/retuning a cutoff would fix them.

The unchanged `collapse-0-r1-baseline-a` fails at **36.97% on-time with zero genuine learned steps**. Thus the remaining startup/encoder/playout/deadline instability cannot be attributed solely to learned actions or removed simply by preventing fallback growth. Neither new weights nor threshold tuning on this panel is justified.

Next defensible check: a **separately declared causal presentation/ACK/system-state instrumentation experiment** with repeated unchanged controls and fresh roles, before selected calibration or validation. Distinguish actual receiver readback from reverse-ACK age rather than silently redefining the old feature or reusing its probability. Preserve all outcomes and original gates; do not promote or allocate performance validation after the failed repeatability gate.

**The guard is not adopted. Native improvement, selected confidence calibration, deployment qualification and SOTA are not established. The broader goal remains unachieved.**
