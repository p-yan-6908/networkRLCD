# Native temporal/controller repair V2 — implemented, efficacy unverified

## Status

The user requested fixes to training coverage, temporal observability, interaction with Chrome's controller, optimistic risk screening, and startup/runtime variability. This version implements changes to all five surfaces. **The three-seed model is now fitted on 96 sealed Chrome/VP8 exploration episodes. Fresh selected-policy calibration and repeatability are complete. Repeatability passes, but the calibrated controller is inactive and unsuitable for performance validation. This does not establish that RLCD works better or is SOTA.**

The existing failed recorded-media panel, divergent runs and canonical checkpoints/selection remain immutable. New code lives in `native_repair_*.py` and separate `repair*.mjs` collectors; the legacy model/controller/label engines remain unchanged.

## Changes and boundaries

1. **Relevant training:** dedicated prospective train and exploration-calibration roles, four cap behaviors (BWE, fixed300, sweep and bounded exploration), independent movie/schedule groups and multiple repeated peers. Three-seed CQL uses 10-step delayed factual returns, not just immediate rewards; evaluation labels are rejected. Default eight train groups mean 64 eighteen-second episodes rather than the old 12-episode fitting panel. This is still small compared with real-world coverage, and correlated repeated frames are not independent samples.
2. **Temporal/receiver state:** 32 samples ×20 causal features (640 inputs), typically about 3.2 seconds at 100 ms, with a 4-second maximum time window and gap resets. Sixteen causal sender features plus four features from received presentation ACKs. ACKs traverse the same impaired WebRTC connection; only source identity/count is returned, joined to the sender's already-known capture record on receipt. No movie pixels, future labels, hidden capacity/phase, receiver oracle, or absolute clock enters the model.
3. **Controller integration:** seven supported native cap actions, learned cap no greater than 95% of observed BWE (subject to the native 150 kb/s minimum), 85% BWE fallback, one-step upward recovery/dwell, congestion cuts/hold, initial 300 kb/s and genuine zero receiver jitter-buffer target. Chrome's own controller remains active. These are guard heuristics, not proven stability or bandwidth guarantees; observed BWE is endogenous to prior caps.
4. **Risk screening:** 10% miss budget versus the old provisional 50%; ensemble disagreement and factual-action support required. Fresh `selected-calibration` executes the actual frozen repair controller, including its fallback, on untouched clips. The calibrator is monotonic, residuals are leave-one-source-group-out, and unsupported actions (fewer than three independent groups, three episodes or 60 requests) receive margin 1. Actor/risk weights/controller limits cannot change during calibration. Evaluation requires exact evidence provenance and deterministic recomputation. Empirical clustered residuals are **not pointwise or counterfactual safety certificates**; updating the screen changes the eventual policy distribution, so held-out validation remains mandatory.
5. **Measurement variability:** hash-verified bounded HTTP Range streaming avoids loading the entire film as a browser ArrayBuffer; disposable warmup does not seed real histories; startup cap is read back before playback; every condition runs common shadow inference. All timings and failures are retained. Explicit resume verifies complete prefix captures, archived sources, runtime and model hashes before any missing peer runs; incomplete captures are never recollected. Read-only replay checks pinned archived collector bytes and independent Python behavior; a collection-only stage-registration change does not invalidate archived data. Live execution still requires current engine hashes.

## Actual smoke evidence, not learned-policy performance

`configs/native_repair_smoke_v2b.json` / `results/native-repair-smoke-v2b` has eight complete Chrome/VP8 captures in **one** fresh stable source/schedule group. Every packet, source RGB/deadline label, transported feedback join, temporal state, command and model output independently replays. There were no >10 ms common inference-tail failures.

| Exploration behavior | Mean utility | Identifiable on-time |
|---|---:|---:|
| BWE-headroom | 31.3053 | 92.6063% |
| Fixed 300 kb/s | 30.8200 | 91.4972% |
| Sweep | 32.4117 | 91.3124% |
| Bounded exploration | 27.7429 | 86.7184% |

There is no fitted repair model in these captures. Bounded exploration intentionally chooses varied cap indices; it is **not the repaired learned controller** and the table is not an efficacy/repeatability study.

The first setup attempt failed due to Node 26 FileHandle garbage-collection ownership during ranged serving. The per-response streams now own raw numeric descriptors; the verified owner handle is explicitly retained/closed. The next complete first capture was initially rejected by an auditor plumbing error (the legacy bundle validator returns `True`, not the model). That capture was independently replayed and reused without recollection; the original failure records remain sealed. Relative CLI paths now canonicalize before runtime comparisons.

## Evidence and source scope

- Full regressions: **364 Python tests / 67 Node tests**, Ruff/format pass.
- `results/jobs/native-repair-v2-pipeline-checks.json` records finite package, role-refusal, byte-identical historical/new raw replay and canonical-hash probes when completed.
- Tears of Steel: licensed live-action/VFX film; Sintel: separately licensed animated film. Official rights/source pages are retained in `data/native_video/`. Sintel video-only SHA: `45331b1ba03cb28aaf35ac0438e91fb2f2d5011c9351c1f85073fcc0d3952eef`, 888.032 seconds, H.264 1280×544, 24 fps. This is new film content, not a remux of the existing film used to evade reservations.
- Movie reservations are half-open `[start,end)` playback ranges, not inclusive generated-frame-ID ranges; all complete/failed/planned prior role reservations remain excluded.
- Two films, one host/browser/codec, userspace loopback bottleneck families and sampled RGB/marker/application readback deadlines are not representative Internet paths, physical capture/scan-out, perceptual assessment or a published-controller comparison.

## Prospective workflow

Currently frozen: `configs/native_repair_train_v2.json` (seed 2701, eight groups / 64 episodes, Sintel clips [60,220) seconds) and `configs/native_repair_calibration_v2.json` (seed 2801, four groups / 32 episodes, [220,300) seconds). Both fitting roles completed without dropped peers: 64 train episodes / eight groups / 10,730 accepted transitions and 32 exploration-calibration episodes / four groups / 5,361 transitions. All seven caps have factual training support. `results/native-repair-model-v2/model.json` SHA-256 is `4e6afd07fbbf46440604eb886017bd555e1ee3907cc518aafe40d7bb59ca885b`; it binds the two sealed input manifests. The three Bellman-loss traces are noisy, not proof of convergence or performance. No evaluation labels were used.

The actual fitted weights pass a 120-step Python/JS parity probe including a history-gap reset (`results/jobs/native-repair-v2-fitted-parity.json`). The current wheel in `results/jobs/native-repair-v2-fit-dist` also refuses existing plan files/directories/dangling links before loading inputs; three new regression cases cover that immutability guard. Canonical checkpoints/selection are unchanged.

`configs/native_repair_selected_calibration_v2.json` freezes seed 2901, four Tears of Steel groups (stable/collapse/variable/brief-collapse), two repeats each and untouched clips [160,180), [200,220), [220,240), [240,260) seconds. All eight completed. Recalibration uses 663 accepted transitions / 2,151 factual requests in four independent groups. Exact recomputation verifies provenance, frozen actor/risk weights and controller limits; the calibrated model SHA is `0bd33608b309e4cfd19de430d797f2bb021378b88c344380c61adf80a4759ae2`.

**The calibration exposes unresolved control problems, not model improvement.** Only 150/300 kb/s have factual three-group support. The 300 kb/s residual margin alone is 0.132, above the unchanged 0.10 miss budget; all higher caps are unsupported and blocked. On these source-controller runs, 502/676 decisions executed 150 kb/s and 487 were congestion holds. Original risk predicted 20.784% miss against 30.869% observed; fitted diagnostics are in-sample, not a safety certificate. The 69.132% on-time source-controller mean is not a matched BWE comparison or the recalibrated controller's outcome.

`results/jobs/native-repair-v2-selected-diagnosis.json` retains factual histories and explicitly non-closed-loop predictions: the calibrated model's 150 kb/s risk passed no recorded-state screen. BWE often falls from early ~1.5–2 Mb/s estimates to ~0.44–0.58 Mb/s while this controller is app-limited; ACK delay alarms also occur on already-on-time frames. These are potential interacting mechanisms, not isolated causal estimates. Five source steps had a learned flag although a guard executed a different, ineligible action; any future promotion accounting must count genuinely executed learned actions, not this pre-guard flag.

All 24 calibrated-model alias/BWE peers complete and independently pass full raw replay. Original repeatability limits pass (largest utility/ontime spans 2.6904 / 9.2937 pp); there are no >10 ms inference-tail failures. However, the two actual repair aliases average **55.776% on-time / 16.253 utility versus BWE 81.320% / 24.232**. None of their **1,348 decisions** has an eligible learned action. They spend 1,176 steps at 150 kb/s and 1,154 in congestion holds. The poor controller is therefore the guarded fallback path, not executed neural decisions. These four-group repeatability comparisons are descriptive, not >=8-group performance validation or causal policy-gain estimates.

`results/jobs/native-repair-v2-repeatability-diagnosis.json` preserves the sealed source-manifest hash, actual activation/cap histories, and prevalidation rejection. No validation is allocated to this inactive candidate; no checkpoint is promoted or evaluation labels fitted. Historical flags/rows and all V2 engines remain unchanged. Existing reason-based source accounting already excludes congestion overrides; the [independent V3 path](NATIVE_REPAIR_V3.md) additionally checks the exact eligible/executed action and excludes baseline-equivalent choices from its >=5% coverage gate.

The commands below are a reproduction template, not permission to overwrite those plans. Use fresh output/config paths; never overwrite a completed or failed study.

```sh
media-rl native-repair-plan --source-model results/native-model-v3/model.json \
  --video-source data/native_video/sintel_source.json --stage train \
  --groups-per-family 2 --out configs/native_repair_train_reproduction.json
media-rl native-repair-study --config configs/native_repair_train_reproduction.json \
  --out results/native-repair-train-reproduction
# Collect a separate exploration calibration plan/run, then:
media-rl native-repair-train --train-run results/native-repair-train-v2 \
  --calibration-run results/native-repair-calibration-v2 --out results/native-repair-model-v2
media-rl native-repair-plan --source-model results/native-model-v3/model.json \
  --model results/native-repair-model-v2/model.json --stage selected-calibration \
  --video-source data/native_video/tears_of_steel_source.json --groups-per-family 1 \
  --out configs/native_repair_selected_calibration_v2.json
media-rl native-repair-study --config configs/native_repair_selected_calibration_v2.json \
  --out results/native-repair-selected-calibration-v2
media-rl native-repair-calibrate --run results/native-repair-selected-calibration-v2 \
  --out results/native-repair-selected-model-v2
# Only this calibrated model may enter fresh repeatability, then >=8-group validation.
```

Original promotion/repeatability limits remain exact. Candidate validation additionally rejects insufficient learned coverage (<5%) or non-minimum BWE-envelope violations. No failed outcome may be dropped, no validation/test labels refitted, and no gate weakened to obtain success. A failed gate requires diagnosis and a new defensible prospectively frozen recipe on fresh data, or a blocked report with the evidence and next required input.
