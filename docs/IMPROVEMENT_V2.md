# RLCD v2 development protocol (frozen before candidate evaluation)

## Diagnosis and scope

The completed v1 scale-up is now development evidence, not an untouched final test: its confidence models were fitted/calibrated almost entirely on safe ID proposals; collapse/bufferbloat failures remain poorly predicted, and calibration does not consistently beat raw scores. V1 is preserved. We will improve the **learned safety model and fallback composition**, while freezing and reusing the already-trained Double DQN weights. This is not new policy training and must not be described as such.

## Frozen candidate set

`configs/improve_v2.json` declares the first three model seeds [11,22,33], not the best three. All candidates use the original 600-step simulator/reward/action space and the same DQN checkpoints, safety-MLP width, ensemble size, optimizer, epoch count and fixed gate threshold 0.90.

1. `id_refit`: matched-budget safety refit on ID episodes only, with richer random-action labels. Controls for additional safety data rather than attributing all change to stress coverage.
2. `stress_safe`: same refit budget, with half the risk/calibration episodes drawn from a new randomized stress generator; original deterministic conservative fallback.
3. `stress_gcc`: exactly the stress-safe learned weights/calibrator, but deterministic GCC-like fallback. Isolates fallback composition without claiming a new neural policy.

Stress training randomizes change times, capacity, RTT, queue scale, erasures and feedback gaps; it does not replay old or fresh evaluation traces. The old `ood` scenario group will be called the **stress panel** for v2, because these mechanisms are no longer wholly outside safety-model training support. Fresh seeds mean new realizations, not new mechanisms or Internet-population validation.

## Data separation and selection

- Original policy training remains untouched.
- Safety refit and calibration get new disjoint `risk_v2` / `calibration_v2` namespaces.
- Validation uses seeds [501,502], namespace `validation`.
- Final follow-up uses seeds [1501,1502,1503,1504], namespace `test`, and is inaccessible to selection.
- Validation includes all eleven existing scenario families. Candidate selection sees no fresh-test outcomes.
- Selection requires ID QoE no more than 0.08 below v1, ID violation rate no more than 0.002 above v1, and stress-panel violation rate no worse than v1. Among feasible candidates, maximize `0.5*(ID QoE + stress QoE) - 5*stress violation rate`. Require score gain >0.01; otherwise keep v1 and record that no candidate qualified.
- Persist the complete validation ranking and selected candidate in `selection.json` **before** final testing. Do not reselect after viewing test outcomes.
- Evaluate the selected model, v1 reference, matched-budget ID refit, stress-safe ablation, ungated RL, conservative/heuristic/GCC-like controls and raw confidence on identical fresh traces. Preserve all outcomes, including negative effects.

This is an adaptive follow-up prompted by known v1 failures. Even with fresh trace seeds and a locked selection rule, three model seeds and synthetic families support exploratory improvement claims only.

## Acceptance ledger

- [x] Preserve v1 model/checkpoint compatibility and immutable result artifacts.
- [x] Add deterministic randomized stress data and independent refit/calibration/validation streams.
- [x] Train safety-model candidates and isolate data versus fallback effects with matched-weight controls.
- [x] Implement explicit reference-model mapping and validation split in CLI evaluation, including provenance.
- [x] Add resumable per-run campaign milestones; do not rerun completed training if a later evaluation fails.
- [x] Select using validation only; lock selection before fresh testing and test the separation mechanically.
- [x] Run targeted tests and actual validation/fresh-test experiments; audit evidence.
- [x] Update the paper with the completed v1 scale-up and the measured v2 follow-up, without carrying forward stale pilot-only claims.

## Runtime policy

Use local CPU; these are small NumPy models. Persist completed candidate/refit artifacts and run each evaluation in an independent immutable directory. A campaign restart may reuse only hash-audited completed runs with matching settings; no mid-episode/mid-training resume claim. Logs and progress live outside experiment directories. Stop with an explicit blocker rather than claim unmeasured improvement. No Modal job is necessary for this experiment.

## Completed outcome and promotion decision

The campaign completed successfully at `results/improvement-v2/`; its log is `results/jobs/improvement-v2.log` and exit code is 0. All six newly fitted safety ensembles (two data profiles × three policy seeds) completed; the GCC-fallback variant shares stress-safe weights exactly. Policy weights remain unchanged. Calibration safe-label prevalence changes from about 99.45–99.89% in the ID-only refits to 77.43–85.05% in the stress mixture, exposing the confidence model to substantially more failure examples.

Validation selected **stress_gcc**: score 1.17087 versus 1.02506 for v1; ID refit also qualified (1.08512), while stress_safe failed the declared ID-QoE tolerance. The locked choice was persisted before fresh testing and was not changed afterward.

Fresh evaluation completed **1,188 episodes / 712,800 intervals**. All **218 final artifacts** passed audit. On the same fresh panel, the selected controller has stress QoE **1.0272 vs 1.1083** for v1 and violation frequency **10.571% vs 10.081%**. The QoE contrast is -0.081 with conditional 95% interval [-0.144,-0.012]; the violation contrast is +0.490 percentage points with interval [-1.357,2.238]. ID results also regress. **V1 is retained; the selected refit is not promoted.**

On identical ungated stress states, the calibrated stress predictor improves Brier **0.07984 → 0.06249** (~21.7%) and NLL **0.80904 → 0.33088** (~59.1%), while ID scoring worsens. Stress + safe fallback reduces stress violations to **8.653%**, but loses QoE and more than doubles fallback duty cycle versus v1. This is a tradeoff, not a dominating controller. Promising ID-refit test point estimates are not used to choose a post-hoc winner.

The updated manuscript includes the complete v1 study, validation-selection reversal, matched controls, same-state predictor benchmark, and explicit limitations. The promotion review is `results/improvement-v2/PROMOTION_REVIEW.md`. Future iteration requires a new validation/final-panel protocol; prioritize more validation realizations, nominal/stress calibration balance, fallback-state coupling and infeasibility-aware behavior rather than tune against this final panel.
