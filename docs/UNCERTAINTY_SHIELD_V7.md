# V7: ensemble-disagreement action abstention

## Motivation and research grounding

The completed V6 fresh-test diagnostic found persistent optimism in selected-action confidence under stress, including a larger gap on actions changed by the top-five screen. The shield computes standard deviation across its independently initialized episode-bootstrap safety predictors, but V6 did not use that disagreement when deciding which candidate to execute.

Kenton et al. (2019), *Generalizing from a few environments in safety-critical reinforcement learning* (arXiv:1907.01475), report mixed effects: ensembles/blockers reduced catastrophes in their gridworld, did not reliably improve a more difficult CoinRun policy, and ensemble disagreement carried information useful for predicting near-term catastrophes and requesting intervention. This motivates testing disagreement as an **additional abstention signal**, not assuming that it is a reliable OOD detector or that its behavior transfers to media adaptation. The paper/source notes are recorded in `research/RELATED_WORK.md` and `research/references.bib`.

## Frozen candidate

V7 uses the V6 selected-action-calibrated checkpoints byte-for-byte. Baseline `shielded` and candidate `shielded_uncertainty` share the same policy, safety ensemble, calibrator, top-five Q ranking, 0.90 calibrated-safety threshold, telemetry support check and deterministic fallback. The only candidate intervention is to require ensemble standard deviation `<= 0.05` for a probability-eligible action; if all probability-eligible candidates exceed this cutoff, the controller abstains to the deterministic fallback with reason `uncertainty_abstention`. The value is a fixed five-percentage-point disagreement cutoff, not a calibrated confidence bound. The standard-deviation estimates are computed from raw ensemble probabilities; no OOD guarantee follows.

The fixed cutoff and promotion constraints are recorded in `configs/uncertainty_shield_v7.json`. Validation traces 10701--10710 select whether the candidate is promoted, and fresh test traces 11701--11710 are untouched until the validation decision is locked. Both variants use the same V6 candidate checkpoints and paired trace seeds, isolating only the inference-time screening rule. The selection rule applies the V6 QoE/risk/per-stress-family bounds and validation score margin. Regardless of promotion, the complete test panel is run and reported; no test-driven retuning is permitted.

The V7 evaluation uses 10 model seeds, 10 validation trace seeds, 10 fresh test trace seeds, and all 11 declared scenario families. Step diagnostics separately record replacement interventions, uncertainty abstentions, executed/proposed unsafe labels and the selected candidate's disagreement. All step-level safety frequencies remain descriptive; simulator episodes, not serially correlated steps, are the experimental units for the promotion summaries.

## Reproduction

The trained V6-derived candidate checkpoints already exist in `results/action-calibration-v6/candidate-models`. For a clean checkout, recreate them first with the documented V6 calibration command if absent, then use `make uncertainty-shield-v7` (which writes a new `results/uncertainty-shield-v7` campaign).

The existing campaign was recovered after its first fresh-test process timed out. The following recovery command is only for the case where `final-campaign/` does not yet exist; it preserves the original incomplete run. In this workspace recovery is complete:

```sh
make resume-uncertainty-shield-v7
uv run media-rl status --run results/uncertainty-shield-v7/final-campaign/test
uv run media-rl audit --run results/uncertainty-shield-v7/final-campaign/test
```

Recovery verifies identical settings, checkpoints, validation artifacts and runtime/dependency hashes; it records non-runtime source drift, copies only the audited validation/selection lock, hashes and preserves the original partial `test/`, and runs a fresh complete test under `final-campaign/test`. It never reads partial test metrics for tuning. `selection.json` identifies validation and the disjoint 10701--10710 / 11701--11710 panels. A rejected candidate remains a valid negative finding; do not change the cutoff after inspecting validation/test outcomes or reuse these panels.

## Outcome

Validation audit verified 367 artifacts and selected `shielded_uncertainty` by a score gain of 0.005073, just above the 0.005 promotion margin. The fresh disjoint panel contains 8,800 episodes over 10 model seeds and audited 400 artifacts. Paired V7-minus-V6 effects were ID QoE +0.00043 [−0.00004, 0.00134], ID unsafe rate −0.003 percentage points [−0.018, 0.009], stress/OOD QoE +0.00182 [0.00003, 0.00463], and stress/OOD unsafe rate −0.083 percentage points [−0.209, −0.0005]. Intervals resample model seeds conditional on the fixed trace panel; the stress-risk upper bound only narrowly excludes zero, and the effect is small. Abstention triggered on 0.24% of stress steps (0.04% ID). GCC-like control still had better OOD mean QoE/risk (1.119/7.21%) than V7 (1.071/10.51%). These are synthetic descriptive results, not a guarantee or Internet validation. The original partial test is preserved; completed artifacts and paper tables are in `results/uncertainty-shield-v7/final-campaign/test` and `paper/generated-uncertainty-shield-v7/`.
