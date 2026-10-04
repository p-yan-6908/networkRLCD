# Native reliability and selected calibration V1

## Outcome: complete engineering workflow; candidate rejected

The portable native workflow now prospectively freezes models, code, workload, role, source/schedule groups, repetitions, condition order, and acceptance limits before any browser outcomes. It collects owned Chrome/VP8 peers, seals raw artifacts, independently replays them, and locks validation selection before test. This is **local synthetic native RTC evidence**, not representative Internet performance, a safety certificate, or SOTA.

The completed measurement comprises **68 native browser runs**:

| Role | Browser runs | Independent source/schedule groups | Purpose |
|---|---:|---:|---|
| Repeatability | 12 | 2 | Identical V3 RLCD aliases and BWE, two repetitions, stable/collapse |
| Calibration | 8 | 4 | Fresh V3-selected accepted factual actions, all four regimes |
| Validation | 48 | 8 | Unchanged V3, recalibrated V3, BWE; two repetitions, all four regimes |

Repetitions and individual frames are **not independent uncertainty units**. Bootstrap intervals condition on one frozen policy and generated source/schedule families; there are only two groups per validation regime. Matched groups do not imply identical packet trajectories.

## Implemented surfaces

- `benchmarks/native_rtc/episode.mjs`: packaged finite Node 22+/Chrome collector. Uses only its own temporary browser profile and localhost UDP/HTTP sockets, real VP8/transport-cc decoding, application pixel-ID deadlines, and paired sampled synthetic RGB quality. No user browser, camera, privileged `tc`, paid cloud, or upload.
- `src/media_rl/native_protocol.py`: strict versioned roles, model/source hashes, causal-only native contract, source-range exclusion, ordered counterbalanced conditions, explicit predeclared limits, safe artifact paths, and seals. Legacy missing seed metadata is accepted only for exact recognized driver hashes, not invented for arbitrary captures.
- `src/media_rl/native_wire.py`: independent raw datagram replay of admission, FIFO, service, queue limits/conservation, overflow, and propagation.
- `src/media_rl/native_statistics.py`: identical-policy utility/deadline variability, sender-signal variation, group-level paired contrasts, phase/regime diagnostics, and frozen selection. No frame-level pseudo-replication.
- `src/media_rl/native_study.py`: complete capture/qualification/JS–Python policy parity replay, all-model shadow-workload verification, read-only audit, and strict interruption recovery.
- `src/media_rl/native_calibration.py`: only role-declared calibration data can fit monotonic selected-action Platt parameters. It uses accepted factually associated source labels, weights by source-request counts, preserves actor/risk weights and screens, and marks diagnostics as in-sample, not selected-policy validation.
- Public CLI: `native-plan`, `native-study`, `native-audit`, `native-calibrate`. Browser assets are included in the wheel, not dependent on untracked `.tools` scripts.

Both validation models are computed on every causal history in **every condition**, including BWE. BWE does not receive an artificial CPU advantage by skipping policy work. The 16-feature × four-history sender-only ABI, native seven zero-target caps, Platt monotonicity, and **0.5 predicted-miss / 0.2 raw-disagreement screens** remain fixed. No relay capacity/queue, pixels, phase, or future trace enter policy inference. A bitrate ceiling remains a ceiling under native GCC, not a wire-rate command; no FEC/codec-mode actuation is claimed.

## Real results

### Repeatability

`results/native-reliability-v1/report.json` passes its prospectively declared utility-span ≤3.0, on-time-span ≤0.15, and episode-inference-p99 ≤10 ms checks. Identical-policy utility spans are approximately **1.99 stable / 0.84 collapse**. Sender signals, including packet-send delay, still vary substantially. Passing those two groups is not universal repeatability or a causal explanation of prior separate-run differences.

### Selected factual calibration

`results/native-selected-calibration-v1/` contributes **484 accepted transitions / 1,534 factual source requests**, across four independent groups. Only new calibration-role labels were used; repeatability, old development, validation, and final-test labels were not fitted.

The new model at `results/native-selected-model-v1/model.json` changes only Platt parameters and provenance:

- old `(slope, intercept)`: `(0.4263815435, 0.3035463282)`;
- new: `(0.5424720204, 0.3561726501)`;
- predicted miss: **0.366643 → 0.328849**, observed miss **0.329205**;
- in-sample frame Brier: **0.213020 → 0.210531**;
- in-sample binned ECE: **0.065256 → 0.086458** (worse).

Matching the aggregate event rate does not establish conditional calibration, safe ranking, or improved control. Changing eligible actions changes the future selected cohort. Independent rollout is required.

### Untouched native validation

`results/native-selected-validation-v1/` completes all **48 runs / eight groups**. Every regime and loss is retained.

| Condition | Mean timing-weighted synthetic utility | Mean on-time source fraction |
|---|---:|---:|
| Unchanged V3 | 14.976778 | 47.4786% |
| Recalibrated V3 | 15.960740 | 50.6487% |
| Native BWE-headroom control | 17.903262 | 65.3523% |

Candidate minus unchanged V3: **+0.983962 utility**, empirical group-bootstrap interval **[−0.182773, +2.833152]**; on-time **+3.1701 pp**, interval **[−1.1605, +10.0971] pp**. The frozen utility-superiority gate is not met.

Candidate minus BWE: **−1.942522 utility**, interval **[−7.593345, +3.880360]**; on-time **−14.7036 pp**, interval **[−33.4718, +3.6902] pp**. In variable-link groups its mean utility deficit is **13.201241** and on-time deficit **52.2529 pp**. It gains steady-link utility against this particular BWE-headroom overlay but fails transition/variable robustness. These small conditional intervals are not precise population failure guarantees.

All individual episode inference-p99 checks meet the 10 ms limit, under the common two-model workload. `selection.json` selects **baseline** and records all 13 failed acceptance checks. The candidate is **not adopted**. No candidate final-test panel was opened to overturn validation. Native V3/V4 model bytes and the existing V7 simulation-selection lock remain unchanged; no native winner or SOTA claim replaces them.

## Cleanup interruption: no outcomes replaced

The original validation task stopped after eight sealed runs when Node reported `ENOTEMPTY` while deleting a still-closing owned Chrome profile. The ninth capture had already written complete raw outcomes. The interruption and original log are preserved in the final parent seal.

- New collectors use bounded `fs.rm` cleanup retries.
- Explicit `native-study --resume` first verifies the original plan/models, every archived source hash, and complete previously sealed peers. It uses the **original archived driver**, not a new policy or new collector version mid-panel.
- Only the specific complete **post-outcome owned-temporary-profile cleanup** failure is recoverable. The ninth capture was independently qualified and sealed without recollection. Only the remaining 39 peers ran.
- Unknown failures, incomplete raw outcomes, failed frame qualifications, changed roles/models/order, and arbitrary/non-owned profile paths stop. No outcome-conditioned replacement is allowed.
- Existing seals, outcome files, logs, and original failure receipt are never overwritten. Recovery receipts bind original hashes and no-recollection status.

Read-only audits allow collector/auditor plumbing changes but require byte-identical policy, feature, clock/label, wire, calibration, and statistical modules, as well as exact rederivation of all saved metrics and selection. Changing those semantic modules requires the frozen implementation, not silent reinterpretation of prior evidence.

## Reproduction and use

Generate **new plans and output directories** for current code; the checked-in V1 configurations are frozen historical evidence, not mutable presets. Source namespaces are excluded before collection, and changing code/models after planning is rejected.

```sh
# Foundational repeated-control check; expands coverage before a broad claim.
uv run --frozen media-rl native-plan --model results/native-model-v3/model.json \
  --out configs/native_repeat_fresh.json --stage repeatability \
  --families stable collapse --groups-per-family 1 --repetitions 2
uv run --frozen media-rl native-study --config configs/native_repeat_fresh.json \
  --out results/native-repeat-fresh
uv run --frozen media-rl native-audit --run results/native-repeat-fresh

# Independent calibration, never the repeatability/development/validation labels.
uv run --frozen media-rl native-plan --model results/native-model-v3/model.json \
  --out configs/native_calibration_fresh.json --stage calibration \
  --groups-per-family 1 --repetitions 2 --exclude-run results/native-repeat-fresh
uv run --frozen media-rl native-study --config configs/native_calibration_fresh.json \
  --out results/native-calibration-fresh
uv run --frozen media-rl native-calibrate --run results/native-calibration-fresh \
  --out results/native-selected-model-fresh

# Freeze candidate/control comparison before opening fresh validation outcomes.
uv run --frozen media-rl native-plan --model results/native-model-v3/model.json \
  --candidate results/native-selected-model-fresh/model.json --stage validation \
  --repeatability-run results/native-repeat-fresh --exclude-run results/native-calibration-fresh \
  --groups-per-family 2 --repetitions 2 --out configs/native_validation_fresh.json
uv run --frozen media-rl native-study --config configs/native_validation_fresh.json \
  --out results/native-validation-fresh
uv run --frozen media-rl native-audit --run results/native-validation-fresh

# Only for the strictly supported complete cleanup-interrupted panel:
# uv run --frozen media-rl native-study --config <original-plan> --out <original-run> --resume
```

Test-stage planning requires the hashed validation `--validation-lock`; it does not let later test outcomes change selection. Stage leakage and edited locks are rejected. Insufficient fresh source namespace is a blocker, not permission to reuse held-out source IDs. `RLCD_CHROME` may point to an installed Chrome binary; otherwise it uses the platform-default Chrome path/command.

## Verification and remaining work

**328 Python tests**, **59 native Node tests**, Ruff checks/format, packaged-asset/CLI probes, immutable-checkpoint hashes, and full raw replay of **12 + 8 + 48 runs** pass. New tests cover role/range leakage, boolean/nonfinite/malformed configuration, independent wire faults, selected-cohort fitting, source-request weighting, JS/Python parity, changed statistics/locks, incomplete capture refusal, cleanup-only resume and owned-profile bounds.

The refit does not repair the core native temporal/variable-link policy deficit. Next work needs a predeclared causal credit/observability intervention with matched training/compute, reliable nominal-quality preservation and separate source groups—not a cutoff relaxation or a fit to these validation labels. Broader repeatability and multiple training seeds are still necessary.

Representative natural content, measured Internet holdouts, device/browser/codec diversity, fairness/competing flows, physical end-to-end timing, and compatible strong published learned-controller runs remain missing. The local BWE-headroom overlay is not an exhaustive genuine-GCC/learned-SOTA comparison. Original AlphaRTC/BoB runners need an appropriate Linux/Docker interface/runtime, unavailable here. This work creates the auditable route to those tests; it does not manufacture that evidence.
