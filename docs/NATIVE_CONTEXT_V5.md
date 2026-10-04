# Causal native context V5 — failed control, repeatability warning; not adopted

## Frozen hypothesis and constraints

`configs/native_context_v5.json` and the source/hash-bound `configs/native_context_development_v5.json` fix **one sender-only hysteretic switch** between unchanged V3 n=3 and V4 n=20 actors. No actor/risk fitting, calibration refit, horizon/gate grid or cutoff relaxation. The short actor is default. Two consecutive alarms use either a **20%** drop from causal two-second BWE peak under offered load ≥ **1.05× BWE**, fresh linked-RTCP RTT rise ≥ **30 ms**, or sender packet delay ≥ **25 ms**. Hold long for two seconds after the last alarm, then require one second of continuously valid clean telemetry. Stream/gap resets and invalid/stale semantics are strict.

`NativeContextSwitch`, `CONTEXT_PROTOCOL`, `CONTEXT_CONTROLLER` are exported in JS/Python. Inputs remain current/past normalized 16-feature sender telemetry, stream identity and relative sample clocks; actors retain the 16×4 ABI. No queue/capacity/pixels/trace-phase/future labels enter control. Risk members/Platt/0.5 and 0.2 screens remain exactly unchanged, never overridden; neither fallback nor prediction screening certifies native safety.

## Actual prospective evidence

A fresh closure checks **525 prior hashes** despite Fovea ring retirement. Eight excluded 1,000-frame source reservations and **32 actual native Chrome/VP8 peers** cover context/short/long/BWE. Two Latin cycles place every condition at every execution position twice; actual absolute capture clock order is verified. Two new brief-collapse groups use **four-second high / one-second collapse / four-second recovery**, without phase input. All conditions run both models and context, with only the declared controller actuating. Original models/data/captures remain unchanged.

Independent read-only replay verifies **2,718 decisions per model stream, 8,610 complete opportunities, 6,240 sampled RGB pairs, 619,472 raw events / 30,239 opaque UDP datagrams, 928 child artifact hashes and 977 before/after source/model/artifact hashes**. All actual source ranges are disjoint from fit/prior development groups and stay within their declared reservation. Every model/context/action/readback/capture acknowledgment, all 32 phase/cap rows and all **24** paired case contrasts/means are checked. Worst model score error ≤ **1.94e-14**, no first-ack ties. The separate strict integrity wrapper rejects numeric booleans/counters without altering any frozen live inference source.

| Context minus control, aggregate | Utility/request | On-time pp |
|---|---:|---:|
| Fixed short n=3 | −1.896 | −6.38 |
| Fixed long n=20 | −1.818 | −8.86 |
| BWE | −1.795 | −13.41 |

Steady utility improves **4.056 versus long** but changes **−0.727 versus short**. Brief-collapse utility changes **−6.038 versus short**. Collapse-j loses **11.640 utility / 45.81 on-time pp versus short**; variable-j loses **9.834 utility / 38.91 on-time pp versus BWE**. Every positive and negative case remains in the actual PDF. **Not adopted; no native promotion or SOTA claim.**

## Activation and repeatability limit

Stable-i selects long on **19/85** observations after two sender-delay alarms despite constant capacity; this does not prove absence of endogenous congestion or identify a nuisance mechanism. Stable-j and variable-i use long on **zero** observations. Yet variable-i changes **+11.043 utility / +46.47 on-time pp** versus a separate fixed-short run with the exact same frozen policy mapping. That contrast cannot be caused by a horizon switch that never occurred. Browser/feedback/actual history/media/packet trajectories differ; matched template/counterbalance is not identical-trajectory causal evidence.

Candidate context max combined p99 is **7.185 ms**, below provisional 10 ms; selector-only max p99 is **0.840 ms**. Across every condition, max is **16.092 ms**, specifically collapse-j long. Do not hide that control tail failure behind average latency or falsely ascribe it to candidate context.

Next: **prospective repeated identical-policy controls and sender-signal repeatability**, then selected-policy calibration and independent role-disjoint evaluation. Do not tune the gate on these eight groups, loosen screens, fit development labels or omit losses. Natural/measured content/traces, multi-model uncertainty and strong published peers remain required. V7 remains selected; SOTA remains unachieved.

## Acceptance and files

**22 focused tests / 287 full Python + 59 Node tests pass** with lint/format; **600 JS/Python context states agree exactly**. New public symbols, all config entries, exporter/Make/four TeX inputs are verified. The updated `paper/build/main.pdf` has **40 pages / 17 references**, all **21** macros, four means/families and all 24 cases, zero-switch ambiguity and timing distinctions. Five new generated artifacts / **19 provenance sources**, all **132 generated artifact hashes**, and current-PDF V4/V3/cadence preservation audits pass. Current evidence builds directly by the Make TeX recipe, not an unchanged heavy full re-export; inherited nonfatal bibliography/six-pass warning remains, no unresolved/box errors.

During collection, inherited aggregator-only 18-peer/stage metadata was found and corrected by reaggregating all existing sealed captures after completion, **without recollecting, changing frozen controls, or altering outcomes**. Historical test/paper receipts remain; only current-PDF derived text/info/log inputs were refreshed for legacy verifiers.

Evidence: `results/jobs/native-context-v5-final-evidence.json`, `results/jobs/native-context-v5-repeatability-diagnosis.json`, `results/jobs/native-context-v5-final-paper-audit.json`, `results/jobs/native-context-v5-all-generated-hashes.json`. Capture root: `results/native-context-development-v5/`; paper: `paper/generated-native-context-v5/`. Production: `src/media_rl/native_context.py`, `native_context_replay.py`, `native_context_integrity.py`, `benchmarks/native_rtc/native_context.mjs`. Execution/audit/export scripts: `.tools/freeze_native_context_v5_panel.py`, `probe_native_context_parity.py`, `native_context_episode.mjs`, `audit_native_context_episode.py`, `run_native_context_v5.py`, `audit_native_context_v5.py`, `diagnose_native_context_v5.py`, `export_native_context_v5_paper.py`, `verify_native_context_v5_paper.py`.
