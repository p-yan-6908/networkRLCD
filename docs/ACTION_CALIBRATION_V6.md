# V6: Selection-aware action calibration

## Motivation

The post-lock v5 fresh-test audit found that the OOD action screen reduced the one-step unsafe rate among replacements (60.69% proposal to 26.35% executed) but the selected-action confidence still overstated observed one-step safety by 21.83 percentage points on changed-action steps. The calibrator had been fit on the original proposal distribution. Do not use those locked v5 test labels to tune v6.

## Frozen candidate

V6 holds each v1 policy and safety-ensemble checkpoint fixed and changes only the post-hoc probability calibrator. For each model seed, collect a new ID-only calibration panel under the existing top-five, 0.90-threshold screen. At every valid observation, execute the screen's selected action (or deterministic fallback); for accepted actions, record the ensemble's raw safety probability and the one-step safety outcome. Fit the existing Platt calibrator to these selected-action pairs. Fallback rows have no candidate action score and are excluded. The samples target screen-selected actions under the frozen source controller, rather than only greedy proposals. Because refitting can change later screen decisions and state visitation, this one-pass fit need not match the candidate’s eventual closed-loop distribution; the disjoint validation/test panels measure that feedback.

The panel is 40 ID episodes per source-model seed, balanced across the four ID families, under the independent `action_calibration_v6` seed namespace. Rollouts use frozen v1 policy/safety weights and the original calibrator with the existing top-five/0.90 screen. All accepted selected-action rows fit Platt (no within-panel holdout), so fit ECE/Brier values are in-sample only. Features, action ranking, top-k, support check, confidence threshold and deterministic fallback remain unchanged; source weights and original calibrator are immutable.

## Validation and test

`configs/selection_calibration_v6.json` freezes the same ten source-model seeds, top-five/0.90 screen and v5 promotion limits. Validation traces are 8701--8710 and fresh test traces are 9701--9710; neither overlaps v1's source test panel or v5's 6701--6710/7701--7710 panels. Validation compares the candidate screen against the original calibrated v1 checkpoints and locks the decision before the final run. The final test includes the full deterministic, learned, calibrated and action-screen controls on all eleven scenario families. No threshold or calibrator tuning is permitted after final-test generation.

Promotion requires every v5 predeclared QoE/risk/family constraint and score margin. Failure to improve ID selected-action calibration or excessive stress/OOD harm is a reportable negative result, not grounds to adjust the locked test. Report selected-action confidence against the executed one-step safety label separately from proposal confidence; these time-step reliability estimates are descriptive, not episode-safety guarantees. This ID-only recalibration has no OOD guarantee and does not turn the v5 screen into a formal shield.

## Completed outcome

Validation promoted the candidate (score 1.0774 to 1.1083; gain 0.03094). On the 8,800-episode fresh panel, the recalibrated screen versus calibrated v1 changed ID QoE by +0.022 [0.009, 0.036] and ID unsafe rate by -0.050 percentage points [-0.100, -0.007]. Stress/OOD QoE changed by +0.023 [0.010, 0.040]; the unsafe-rate change was -0.263 percentage points [-0.749, 0.105], which includes zero. The calibration-only, no-screen control did not produce a resolved QoE or unsafe-rate change. In the fresh selected-action diagnostics, ID confidence matched observed safety on average; OOD confidence remained optimistic by 5.09 points [4.51, 5.71], and by 16.50 points [3.94, 35.07] among 1,417 changed-action steps. These are clustered descriptive one-step estimates, not episode-safety guarantees.

An initial foreground attempt under `results/action-calibration-v6/campaign` timed out after five final-test model seeds; that partial test is preserved and excluded. The completed run under `results/action-calibration-v6/final-campaign` reuses the byte-identical locked validation/selection artifacts and evaluates the full predeclared test panel. No partial outcomes were used for tuning.

## Reproduction

```sh
uv run media-rl calibrate-actions \
  --config configs/action_calibration_v6.json \
  --models results/paper-v1 \
  --out results/action-calibration-v6/candidate-models
uv run media-rl safety-shield \
  --config configs/selection_calibration_v6.json \
  --models results/action-calibration-v6/candidate-models \
  --reference-models results/paper-v1 \
  --out results/action-calibration-v6/final-campaign
```

The first command must verify identical policy/safety weights and persist calibration seeds/sample counts. The second command records hashes for both candidate and reference checkpoints, validation selection, fresh-test artifacts and generated paper provenance. If the candidate is not promoted, preserve it and its evidence; do not rewrite v5.
