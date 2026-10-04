# Reproducible experiments and paper artifact map

## Protocol

1. Freeze the config and code; `uv sync --frozen --extra dev` installs the locked environment.
2. In the main v1 reference protocol, train Double DQN on ID traces; fit safety on independent `risk` episodes and calibration on independent ID `calibration` episodes. The separately registered v4 candidate changes only the policy-training scenario schedule; its risk fitting and calibration remain ID-only with the same budgets (see `docs/POLICY_RANDOMIZATION_V4.md`).
3. Freeze all learned components and the predeclared threshold. Evaluate every method on the same test-seed/scenario panel. Test traces do not depend on model seed or controller actions.
4. Save every executed action, RL proposal, probability, fallback reason, observed telemetry and simulator outcome. Current capacity appears only in offline logs.
5. Generate all tables/figures from logs. Report every seed, method, scenario and ablation, including failures. Do not select τ or model checkpoints from test curves.

`configs/smoke.json`: one training seed, two test seeds, 60 intervals, four training episodes. Functional check only. `configs/demo.json`: three training seeds, four test seeds, 160 intervals, 32 training episodes. Exploratory pilot only. `configs/paper.json`: ten training seeds, twenty test seeds, 600 intervals, 160 training episodes; 40 safety-fit and 40 calibration episodes per model. It is a predeclared scale-up configuration, not a promise of convergence or a completed experiment. The larger matrix has 19,800 evaluation episodes and 11,880,000 step records. CPU evaluation and report memory, not the small network, may dominate runtime. No Modal job has been submitted.

## Scenario definitions

Each generator is deterministic given its seed. A seed changes capacity scale (0.85–1.15), base RTT (35–65 ms), base loss (0.002–0.012), and jitter. Event locations use normalized episode time u.

| Family | Split | Mechanism |
|---|---|---|
| steady | ID | 2.8 Mbps times scale |
| step | ID | 3.5→1.1→2.5 Mbps at u=.30/.65 |
| ramp | ID | V-shaped 4→1→4 Mbps ramp |
| wifi | ID | Correlated AR(1) capacity, sinusoidal variation, small loss bursts |
| collapse | OOD | .28 Mbps from u=.30 to .70 |
| burst_loss | OOD | Seeded two-state bursts, .30 erasure in bad state, reduced FEC efficacy |
| bufferbloat | OOD | .8 Mbps after u=.30 with 8× buffer capacity |
| handover | OOD | .08 Mbps interruption at .40–.50; +160 ms RTT and extra jitter thereafter |
| outage | OOD | Zero capacity/full loss from .35 to .50 |
| feedback_gap | OOD | No reports at .30–.55; capacity drops to .6 Mbps at .35–.60 |
| capacity_surge | OOD | Capacity rises to 10 Mbps times scale and base RTT drops to 12 ms |

OOD means a held-out generating mechanism/parameter region, not universal unknown-network coverage. There are no hidden stochastic draws inside `step`: all exogenous variation is fixed in each saved trace.

## Baselines and ablations

| Registry name | Comparison |
|---|---|
| safe | Always use deterministic conservative controller |
| heuristic | Throughput/queue/loss media heuristic |
| gcc | Simplified GCC-like AIMD delay/loss control, not libwebrtc |
| rl | Identical Double DQN, without gate (no-fallback ablation) |
| calibrated | Full calibrated probability + support guard + hysteresis |
| uncalibrated | Same ensemble/proposal/threshold but raw probability |
| no_ood | Remove support-distance rejection only; retain stale-feedback rejection |
| no_hysteresis | Remove hold/release margin, retain all rejection criteria |
| single_model | First safety classifier, with its own calibration |
| sweep/no_fec | Set action space to f=0; retrain policy, safety model and calibrator |
| sweep/temperature | Replace monotone Platt scaling with temperature scaling; rerun pipeline |

Threshold sensitivity uses predeclared τ∈{.50,.70,.85,.90,.95}; all are reported, never ranked to select a deployment threshold on the test set. The default inference ablations appear directly in the main comparison. For pure calibration benefit, compare raw/reported scores on **the same rows** of the main method, not only methods whose gates induce different visited states.

## Metrics and statistical estimands

- **QoE**: episode mean synthetic reward and worst 10% interval mean. Not perceptual MOS/VMAF.
- **Latency**: mean/p95/p99 of virtual interval latency, including stalled intervals. Domain tables average episode quantiles, not pooled packet quantiles.
- **Loss/deadlines**: interval-mean raw loss, post-FEC residual loss, deadline miss fraction, and union safety-violation rate. Fractions are interval-weighted, not byte/packet-weighted.
- **Throughput/overhead**: source bitrate, timely-goodput proxy and mean wire-minus-source Mbps (the legacy column `fec_overhead` has units Mbps).
- **Stability**: mean absolute log bitrate change, source-rate CV, and joint-action changes/second. FEC/mode changes count in joint switches.
- **Calibration**: ten fixed equal-width bins covering endpoints 0 and 1; weighted ECE; Brier score; binary NLL with numerical clipping. Empty bins have count zero and missing means. Confidence targets next-step proposal safety, including rejected proposals. `calibration_diagnostics.csv` is pooled; `summary.csv` averages per-episode metrics. These different estimands need not match.
- **Selective prediction**: probability-threshold risk/coverage on proposals. No accepted samples means risk is undefined, not zero. These descriptive curves do not replay the hysteresis/support gate; actual `coverage`/`accepted_risk` do.
- **Fallback**: fraction of decisions, entries, observed run-length mean/max, final-run censor flag, reasons, unsafe-proposal precision, fallback safe rate, one-step prevented violations and one-step introduced harm. Precision does not include a claim about long-term effects. Rates of prevention/harm divide by all intervals.
- **Recovery**: after a capacity decrease of >35%, time until three consecutive safe intervals with deadline miss<.1. Report number of shock events and unrecovered/censored events; mean time conditions on recovered events. Multiple shocks are descriptive and may have overlapping recovery windows.
- **Robustness**: OOD minus ID QoE and worst-scenario mean QoE, scenario heatmap, plus pooled AUROC for support score discriminating ID versus OOD labels. OOD-minus-ID compares different scenario mixtures, not a paired causal shift effect.
- **Compute**: `timing.csv` reports CPU wall-clock decision latency in microseconds. It includes safety diagnostics even for ungated RL; it is not a pure-policy benchmark, GPU timing, or part of QoE. Timing is deliberately excluded from reproducibility comparisons.

For each method/domain/scenario metric, average the fixed trace panel within each model seed, then bootstrap **training-seed means** (2.5/97.5 percentiles, fixed bootstrap RNG). Paired contrasts subtract calibrated minus reference on the same model-seed/test-seed/scenario before averaging and bootstrapping. No independent-time-step confidence intervals or unpaired seed matching. All CIs are conditional on the fixed trace panel; they do not quantify Internet-population uncertainty. Deterministic baselines have no variation across training seeds and may yield degenerate intervals. n=1 has no CI; n=3 is exploratory. Undefined metrics use available episodes and the output `n` counts contributing model seeds. No multiple-comparison-adjusted hypothesis claims are made.

## Artifact map

| Artifact | Use in paper |
|---|---|
| config.json / manifest.json | Exact settings, runtime/dependencies, original training source hashes, current source hashes, checkpoint hashes, artifact checksums |
| models/seed_*.json | Frozen policy, safety ensemble, calibration parameters, fit split seeds and training log; safe JSON, no pickle |
| traces/*.npz | Identical exogenous test traces, replayable with `load_trace` |
| steps.csv.gz | Full causal action/telemetry and evaluation-only proposal/outcome evidence |
| episodes.csv | Unit of evaluation; all QoE/safety/stability/fallback/calibration metrics |
| calibration_*.csv | Held-out fit scores/labels (not test metrics) |
| training_*.csv | Exploration/training/TD-loss diagnostics |
| summary.csv / table_main.tex | Mean estimates and seed-cluster CIs, booktabs table |
| paired_differences.csv | Paired calibrated-minus-reference effect estimates |
| reliability.csv / calibration_diagnostics.csv | Bin counts and same-row raw versus reported confidence diagnostics |
| risk_coverage.csv / ood_detection.csv / robustness.csv | Selectivity and robustness evidence |
| figures/qoe_safety_tradeoff.* | ID/OOD QoE versus constraint violations with conditional CIs |
| figures/reliability.* / risk_coverage.* | Calibration and proposal-selectivity plots |
| figures/trajectory_<scenario>.* | First **predeclared** seed/trace, not a hand-selected success case |
| figures/robustness_heatmap.* / learning_curves.* | All methods/scenarios and exploratory learning curves |
| REPORT.md | Automatically generated neutral result digest and caveats |

`source_snapshot/` archives code, configs, tests, documentation and the lockfile at run initialization, including when no Git repository exists. Standalone evaluations also copy checkpoints and `training_source/`, so the original training directory is not required to re-evaluate. Sweep roots include `sweep_summary.csv`, `table_sweep.tex`, and optional combined PDF/PNG sensitivity plots.

`media-rl audit` recomputes artifact hashes. Manifests are integrity evidence, not a signature against an adversary who can rewrite the manifest. Reports may be regenerated intentionally and their hashes refreshed. Source hashes preserve training lineage when later reporting code changes. Exact CSV/checkpoint reproducibility is tested in the locked CPU environment; BLAS/platform differences may affect last-bit arithmetic. Timestamps, wall-clock timing and platform metadata are nondeterministic by design.

## v4 policy-randomization campaign

`configs/policy_randomization_v4.json` freezes the 19-entry schedule, matching v1's 10 policy seeds, 10 disjoint validation traces, 10 disjoint final-test traces, safety/score thresholds and confidence-interval sample count. The single intervention randomizes the policy-training scenario mix (104 ID and 56 stress episodes of 160); safety fitting and calibration remain ID-only. The command `make policy-randomization-v4` audits original checkpoints, trains the candidate, evaluates validation against the frozen v1 checkpoints, writes `selection.json`, then opens the fresh test panel. All seven methods are evaluated on 11 scenarios and paired traces. Test outcomes never alter selection. Full rationale and limits: `docs/POLICY_RANDOMIZATION_V4.md`.

## V5 action-level shield study

`configs/safety_shield_v5.json` freezes the top-five action screen, 0.90 risk threshold, ten v1 model seeds, validation trace seeds 6701–6710, fresh-test seeds 7701–7710, and promotion limits. The controller ranks the v1 Q-values, accepts the first of the five highest-ranked joint bitrate/FEC/mode actions whose existing calibrated one-step safety probability and telemetry-support test pass, and uses the original deterministic fallback otherwise. Policy, safety predictor, calibrator, reward and fallback are unchanged. This is an empirical action-selection ablation, not a formal shield or an ACS reproduction; the calibration distribution was collected for the original proposals and selecting alternatives can induce bias. A one-trace smoke probe on seed 6601 is excluded from the official panels.

`make safety-shield-v5` runs the validation comparison and locks selection before opening fresh test traces. Promotion requires all preregistered ID-QoE, ID-risk, aggregate stress-risk and per-family stress-risk bounds plus a score gain greater than 0.005; if any fail, v1 remains selected. The test comparison runs regardless of the validation choice and cannot change it. Results are fresh realizations of known synthetic mechanisms, not unseen-mechanism or network-population generalization. The completed validation promoted `shielded` (score gain 0.02582); the 8,800-episode test improved paired ID QoE by 0.0259 and reduced ID violation rate by 0.00144 versus calibrated v1, while OOD QoE/violation effects were inconclusive. Heuristic/GCC-like baselines remained stronger on the ID tradeoff. See `docs/SAFETY_SHIELD_V5.md` for the complete protocol and artifacts.

## V6 selected-action calibration

## V7 ensemble-disagreement screen (audited fresh-test results)

`configs/uncertainty_shield_v7.json` freezes a 0.05 maximum raw ensemble-probability standard deviation, top-five/0.90 safety screening, ten V6-calibrated source checkpoints, validation traces 10701–10710 and fresh test traces 11701–11710. The baseline is V6's selected-action screen; the candidate changes only the additional disagreement criterion. If every probability-eligible action exceeds 0.05, the candidate uses the same deterministic fallback and records `uncertainty_abstention`. It is not a calibrated safety bound. Validation applies the same QoE, aggregate-risk, per-family-risk and score-gain promotion rule; fresh testing always proceeds only after the validation selection lock is saved. Both panels contain new realizations of the same known scenarios, not unseen mechanisms.

Validation narrowly promoted `shielded_uncertainty` (score gain 0.005073 versus the 0.005 minimum). The recovered fresh 8,800-episode test is audited at `results/uncertainty-shield-v7/final-campaign/test`; the initial partial run remains preserved at `results/uncertainty-shield-v7/test`. Against V6, paired ID effects were negligible; stress/OOD QoE changed by +0.00182 and unsafe rate by -0.083 percentage points (10-seed model-bootstrap interval [-0.209, -0.0005], conditional on the fixed trace panel). Uncertainty abstention occurred on 0.24% of stress steps. The small conditional effect does not establish robust risk reduction, real-network safety or unseen-mechanism generalization. Tables and provenance are in `paper/generated-uncertainty-shield-v7/`.

`configs/action_calibration_v6.json` fits only the Platt calibrator using 40 ID episodes per v1 source-model seed, collected under the frozen v1 weights and original top-five/0.90 screen. It uses accepted screen-selected actions rather than only greedy proposals; all collected samples are used for fitting, so fit diagnostics are in-sample. Refitting may change future screen decisions, and therefore does not exactly calibrate the candidate’s own eventual state distribution. Policy and safety-network weights remain unchanged.

`configs/selection_calibration_v6.json` freezes validation seeds 8701–8710, final seeds 9701–9710, all eleven known scenario families, and the v5 promotion bounds. The candidate was promoted on validation (score gain 0.03094). The complete 8,800-episode fresh-test panel shows +0.022 ID QoE [0.009, 0.036] and -0.050 percentage-point ID violation change [-0.100, -0.007] versus v1. Stress/OOD QoE changes by +0.023 [0.010, 0.040], while the violation effect [-0.749, 0.105] percentage points includes zero. Selected-action confidence remains overoptimistic by 5.09 points [4.51, 5.71] on OOD steps and 16.50 points [3.94, 35.07] on 1,417 replacements. These are seed-clustered descriptive one-step metrics; the panel contains fresh realizations of known synthetic families, not Internet or unseen-mechanism evidence. Full protocol and artifact paths: `docs/ACTION_CALIBRATION_V6.md`; completed evidence: `results/action-calibration-v6/final-campaign/test`.

## Submission checklist

Run the large protocol without test-driven tuning; inspect convergence and seed variance; archive all outputs with source/lockfile; run no-FEC/temperature and threshold sweeps; add multiple independent trace panels and packet/WebRTC validation; measure multi-flow fairness, codec/FEC realism and real inference overhead; report both calibration failures and baseline wins. Do not submit the smoke/pilot run as confirmatory deployment evidence.
