# V3 validation-selected gate threshold (frozen protocol)

## Motivation and boundary

V2 improved the stress predictor's proper scores but the validation-selected closed-loop controller lost QoE and did not reduce fresh-panel stress violations versus v1. This follow-up asks whether the fixed, original v1 predictor/gate can improve its risk-quality operating point through **validation-only threshold selection**. It changes no policy weights, safety weights, feature set, calibration, fallback, OOD cutoff, or hysteresis policy; only the primary confidence threshold varies. This is hyperparameter selection, not a new learned model, a distribution-free safety guarantee, or a claim of generalization to unseen network mechanisms.

Hugging Face retrieval of Angelopoulos et al., *Conformal Risk Control* (arXiv:2208.02814), and Farinhas et al., *Non-Exchangeable Conformal Risk Control* (arXiv:2310.01262) highlighted important conditions: their guarantees depend on assumptions about monotone bounded losses and the calibration/test sampling process. For the stateful gate here, per-episode violation loss need not be monotone in the confidence threshold: changing fallback timing changes later telemetry, queues and actions. Time steps are serially dependent; scenario families are heterogeneous; mechanisms seen in validation are not unseen at test. We therefore **do not apply CRC or assert conformal/distribution-free risk control**. Instead, use a preregistered finite candidate grid, paired validation traces, fixed feasibility bounds and genuinely fresh trace realizations. The validation mean is a model-selection criterion, not an estimate with a safety guarantee.

## Frozen protocol

- Use all ten already-trained v1 policy/safety bundles [11,22,33,44,55,66,77,88,99,110]. No retraining or refitting.
- Evaluate thresholds [0.50, 0.70, 0.85, 0.90, 0.95], with release margin `min(0.03, 1-threshold)`. The v1 `0.90` gate is the paired reference.
- Validation trace seeds [2601..2610]; final test seeds [3601..3610]. These are disjoint from v1 and v2 evaluation panels. All eleven scenario mechanisms appear in validation; final outcomes therefore test new trace realizations of the same mechanisms, not mechanism OOD.
- Validation requires 10 model seeds × 10 trace seeds × 11 scenarios × 5 thresholds = 5,500 episodes. The fresh final matrix uses the same 10 × 10 × 11 panel and includes conservative/heuristic/GCC-like controls, ungated RL, selected-threshold RLCD, fixed-0.90 RLCD, and raw-confidence control (7,700 episodes).
- A candidate is feasible only if ID QoE is no more than 0.03 below v1; ID violation rate no more than 0.001 above; aggregate stress-panel violation rate no more than 0.005 above; and each of the seven stress-family violation rates no more than 0.02 above v1. These are explicit development tolerances, not safety specifications.
- Among feasible candidates, maximize `0.5*(ID QoE + stress QoE) - 5*stress violation rate`. Require improvement greater than 0.005. If no nonbaseline candidate qualifies, retain threshold 0.90.
- Persist and hash the complete validation ranking before evaluating any final-test seed. Never choose or replace the selected threshold after inspecting final results. Preserve per-threshold runs, the 0.90 paired controller and all deterministic baselines.

## Reproducibility and stop conditions

Run `uv run media-rl tune-threshold --config configs/threshold_select_v3.json --models results/paper-v1 --out results/threshold-selection-v3`. The wrapper audits each validation run before reuse, fingerprints the source checkpoints and implementation, writes `selection.json` before fresh testing, and stores gate overrides beside final run artifacts so replay is portable. Interrupted non-complete stages are preserved but are not silently resumed; use a new output directory after inspecting the failure. The original v1 checkpoints and v2 campaign remain immutable.

A positive threshold result is exploratory evidence conditional on these fixed synthetic scenario families. If the locked candidate fails on fresh traces, report the reversal and keep v1. Continue only with another separately declared validation/fresh-test design; do not recycle these final seeds as untouched evidence.
