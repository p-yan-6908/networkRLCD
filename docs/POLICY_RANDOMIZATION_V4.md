# v4 policy-domain-randomization protocol

**Status:** frozen before candidate training and v4 validation/test. The machine-readable schedule and thresholds are in `configs/policy_randomization_v4.json`; do not tune them using final-test results.

## Motivation and scope

The v3 threshold sweep found no supported reason to promote a different confidence threshold, so v4 does not change the gate, safety predictor, calibrator, fallback, reward, or controller architecture. It tests a narrower change: broaden the *policy's* scenario exposure during the same fixed 160-episode training budget. The previously trained `results/paper-v1` checkpoints are retained as the frozen comparator. This is a new synthetic-simulator training distribution, not sim-to-real evidence and not an unseen-mechanism OOD test: every named stress family is present in the v4 policy-training schedule.

The schedule was informed by Tiboni et al., *Domain Randomization via Entropy Maximization* (arXiv:2311.01885, retrieved/read with the Hugging Face papers CLI). That work studies adaptive parameter distributions for robotic sim-to-real transfer, not media/network control. It cautions against treating broader randomization as automatically beneficial and motivates a bounded, fixed comparison rather than adaptive curriculum tuning. This experiment cannot claim that the cited robotics findings transfer to our simulator.

## Frozen intervention

- Policy initialization seeds: `[11, 22, 33, 44, 55, 66, 77, 88, 99, 110]`, matching v1.
- Training algorithm, 160 policy episodes, optimizer, reward, action space, model size, simulator, and all other training parameters: unchanged from `configs/paper.json`.
- Policy schedule: 19 entries (three cycles of the four ID scenarios, then each of seven stress scenarios once). Across the fixed 160 episodes, this yields 104 ID episodes (65%) and 56 stress episodes (35%); each ID scenario occurs 26 times and each stress scenario eight times. Episode-to-schedule assignment and trace generation are deterministic from the declared seed.
- The risk/safety ensemble's 40 episodes per seed and probability-calibrator's 40 episodes per seed remain ID-only, using the existing split-specific data generation. Thus this tests policy-training randomization while retaining the established ID safety/calibration protocol; it does **not** train or calibrate those components on stress traces.
- No additional hyperparameter search or curriculum adaptation is permitted in this study. Gate threshold and hold/release settings remain exactly those from v1.

## Selection and evaluation

Validation and final-test trace seeds are separate frozen panels (`4601–4610` and `5601–5610` respectively), disjoint from one another and the original v1 test panel. Both candidates share each generated trace. The method panel is `safe`, `heuristic`, `gcc`, v1 `rl` and `calibrated_v1`, and v4 `calibrated` and `uncalibrated`. Original v1 checkpoints supply both `rl` and `calibrated_v1`; the new checkpoints supply v4 policy methods. Each panel contains 10 model seeds × 10 trace seeds × 11 scenarios × 7 methods = 7,700 episode runs.

Only v4 validation outcomes determine promotion. The predeclared score is

`0.5 * (mean_ID_QoE + mean_stress_QoE) - 5 * mean_stress_violation_rate`.

Promotion requires **all** of the following versus v1's `calibrated_v1`: ID QoE drop ≤0.03; ID violation-rate increase ≤0.01; aggregate stress violation-rate increase ≤0.02; every individual stress family's violation-rate increase ≤0.03; and score gain >0.005. Otherwise, v1 remains the selected controller. These are empirical selection constraints, not statistical safety guarantees. Means are computed over the paired model-seed/trace-seed/scenario episode panel; all panels, scenario-level results, and uncertainty summaries remain reportable.

The runner writes `selection.json` after the validation evaluation has a complete hash-audited manifest and **before** opening the fresh final-test panel. The file locks the decision, rule, protocol, validation-manifest hash, and baseline checkpoint hashes. Final test evaluates both v1 and v4 regardless of promotion, but test outcomes cannot change the locked selected-controller field. A new output directory is required if a campaign was interrupted or its input/source hashes change; completed artifacts are never overwritten.

## Interpretation limits

All environments are synthetic and deterministic conditional on their declared seeds. The seven stress families are explicitly used during v4 policy training, while risk fitting and calibration remain ID-only. This supports a controlled policy-training-distribution comparison and stress-regime evaluation, not claims of generalization to unseen mechanisms, calibrated OOD probabilities, deployment safety, standards compliance, or real-world QoE. Any promotion is scoped to this benchmark and requires independent validation before deployment.
