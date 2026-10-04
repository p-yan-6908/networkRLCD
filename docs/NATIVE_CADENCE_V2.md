# Native screened cadence V2 — actual live test, no adoption

## Prospective intervention

`configs/native_cadence_v2.json` freezes six new source offsets, three schedule templates (collapse, steady, variable), all six counterbalanced orders and **18 owned Chrome/VP8 executions**. Compare **unchanged native RLCD**, **85% native-BWE** and **prediction-screened cadence RLCD**, with the same frozen `results/native-model-v1/model.json`. No legacy transfer, refit, threshold relaxation or promotion follows. Exact source offsets are disjoint from prior native train/calibration/development roles, not evidence of representative natural-content generalization. Executions are independent, not identical packet traces.

A current cap can dwell for 1,000 ms only while its model probability AND ensemble-disagreement screens still pass. Predicted-unsafe current caps and native fallback release immediately. **Owned initial/changed-command ack time** is adapter state, not an added neural state field or proxy/receiver oracle. All three conditions execute the same neural **and cadence shadow** computations/instrumentation; only the cadence condition actuates guard output. `src/media_rl/native_policy_replay.py` independently recomputes every raw 16-feature/four-step state, seven score vectors, shadow guard, changed-ack age, proposal/readback and source association. Existing V1 return schemas/driver/captures remain unchanged.

## Actual descriptive result

The cadence controller is **not adopted**; V7 remains selected and SOTA is unachieved.

| Control | On-time sampled PSNR utility/request | On time | Cap changes/run |
|---|---:|---:|---:|
| BWE | 18.529 | 67.23% | 3.50 |
| Unchanged RLCD | 16.867 | 58.96% | 20.50 |
| Screened cadence | 16.848 | 59.56% | 19.83 |

Cadence versus unchanged RLCD: **−0.019 utility / +0.608 on-time pp**, but **both steady-link cases lose utility (−0.798, −1.335) and on-time delivery (−2.519, −4.698 pp)**. Cap changes decrease only **0.667/run** on average. First-phase utility loses **1.464** versus unchanged RLCD. Cadence versus BWE: **−1.681 utility / −7.664 on-time pp**, despite **+4.123 first-phase utility**. Preserve all phase/case harms; **no adoption/promotion**. These are short single-model synthetic same-host descriptive means, not uncertainty-controlled superiority, a causal effect estimate, validation/final test or SOTA. Native GCC remains beneath all three cap controllers. Stable cases keep capacity at 2 Mbps; their phase labels are positions, not collapses.

The guard actually holds **29 proposals / 511 cadence decisions**. Among **148 changed base proposals**, mutually exclusive priority reasons are **29 fallback**, **10 current-cap miss-screen rejection**, **77 current-cap disagreement rejection**, **3 dwell expiry**, **29 held**. This diagnoses why retaining the current prediction screens cannot stabilize most churn. It does **not** justify relaxing the cutoff or prove which model/data defect caused disagreement.

## Coverage and verification

- **1,535 total / 1,022 learned / 511 cadence decisions**, **4,846 complete opportunities**, **3,239 sampled RGB pairs**.
- **311,199 raw wire events / 11,999 opaque datagrams**, full FIFO/drop-tail/capacity/propagation replay, **486 sealed child artifacts**.
- Native model discrepancy ≤**4.45e-15**, maximum per-run neural+arbiter p99 **4.42 ms** under the provisional 10 ms check; not a worst-case/deployment certificate.
- **237 Python + 51 Node tests** pass, including 15 new cadence/controller/clock/emergency/forgery cases. No missing/late opportunities removed to improve score.

During repeated export verification, the inherited *sealing* wire CLI overwrote child `manifest.json` files. No raw evidence/metrics/models changed. Every original 27-file seal was reconstructed and **hash-matched to both preexisting parent and summary identities before any restoration**. The full auditor now uses `.tools/replay_native_wire.py`, which performs identical raw physics checks without writing seals. A direct before/after probe verifies **all 507 parent/child/data identities remain unchanged** across full replay. Receipts: `results/jobs/native-cadence-seal-restoration.json` and `native-cadence-read-only-audit-proof.json`. Do not rerun a sealing CLI on completed roots.

## Reproduction and next model/data action

```sh
# Collection only uses new case roots; resumes already sealed rows without replacement.
uv run --frozen .tools/run_native_cadence_v2.py
uv run --frozen .tools/audit_native_cadence_v2.py
uv run --frozen .tools/probe_cadence_read_only_audit.py
uv run --frozen .tools/export_native_cadence_paper.py
make paper
uv run --frozen .tools/verify_native_cadence_paper.py
```

`results/native-cadence-v2/` and `paper/generated-native-cadence/` retain every actual comparator/phase/churn outcome. The unchanged model and V7 legacy selection remain preserved; SOTA is unachieved.

Measured next-data diagnosis (`results/jobs/native-cadence-state-age-diagnosis.json`): after known changed-command acks, **<400 ms states occupy 32.97% of training versus 48.32% of live RLCD**, while **≥1,000 ms states occupy 6.59% of training versus 82.25% of BWE**. The current cap in BWE's long-dwell states fails the model disagreement screen **87.29%** of the time, despite the BWE condition's higher aggregate utility. Current-cap disagreement rejection is already frequent in fitted training states; this is not proof that selection shift alone caused failure. Initial unknown ages are excluded; training predictions are in-sample and all live states are development-only.

Next concrete data task: freeze a **larger fresh mixed-dwell exploration plus native-BWE-demonstration train/calibration panel**, covering both sub-400 ms transitions and multi-second stable conventional-cap states; retain the risk/disagreement gates, native sender-only ABI, independent outcome-complete labels and role-disjoint future validation/test. Retrain/compare fresh weights only after the complete source/wire/action replay. Explicit causal action age and credit-horizon variants need independently isolated ablations, not simultaneous untracked edits. The model has only six one-second-block exploration training episodes; weakening disagreement to force a cadence win is not a defensible fix. Do not fit this development panel or relabel it as final validation/test. Multi-model/group uncertainty, representative natural/measured traces and content, strong published learned peers, native validation gates and untouched final tests remain outstanding.
