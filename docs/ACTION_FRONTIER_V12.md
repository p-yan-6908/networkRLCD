# V12 development: full frontier and cohort-correct selected calibration

This is **development**, not a promotion or SOTA claim. V11 n=3 alone remains rejected; current legacy defaults and the nine-study paper remain unchanged.

## Completed full-frontier probe

Frozen model seed 70, new trace ID **22001**; compare K=5 and all K=42 actions, separately for n=1/n=3. Original weights, probability threshold **0.9**, disagreement cutoff **0.05**, state-support/feedback guards, physical traces and all conventional controls stay unchanged.

| Uncertainty screen | Nominal QoE | Stress QoE | Nominal unsafe (%) | Stress unsafe (%) |
|---|---:|---:|---:|---:|
| n=1, K=5 | 1.0146 | 0.1355 | 10.313 | 25.833 |
| n=1, K=42 | 1.0236 | 0.1278 | 7.604 | 24.881 |
| n=3, K=5 | 1.1057 | 0.2706 | 11.250 | 26.250 |
| n=3, K=42 | 1.1868 | 0.2949 | 10.521 | 26.071 |
| GCC-like | 0.9817 | 0.3616 | 23.750 | 32.262 |

Full search does not universally improve quality: n=1 stress QoE worsens. n=3 full search improves nominal/stress QoE by **0.0810/0.0243** versus its own top-five screen and lowers unsafe by **0.729/0.179 pp**. These single-model synthetic point estimates cannot establish superiority or justify adopting the rejected n=3 recipe.

`results/jobs/action-frontier-v12-evidence-check.json` audits all **63,360 rows**, four immutable panels and **10,560 exact replay steps**. Under matched observations, expansion changes **680** decisions and **never** changes an action when K=5 accepts. No accepted-action probability/disagreement guard violation is observed. New-counterfactual labels target the **executed selected action**, not its different proposal; censored terminal labels are excluded.

## Selection-induced calibration gap

| Model / frontier | Accepted label coverage | Mean confidence | Cohort-safe rate | ECE |
|---|---:|---:|---:|---:|
| n=1, K=5 | 0.7181 | 0.9340 | 0.9255 | 0.00847 |
| n=1, K=42 | 0.7937 | 0.9356 | 0.9259 | 0.00966 |
| n=3, K=5 | 0.7047 | 0.9311 | 0.9198 | 0.01128 |
| n=3, K=42 | 0.7930 | 0.9285 | 0.9066 | 0.02196 |

Those probabilities/labels describe the new capture cohort under **fixed candidate continuation to deadlines**, not factual online execution with subsequent action changes. Accepted probabilities are all ≥0.9, so the default ten-bin ECE places them in one bin; it is a mean gap, not subgroup/pointwise calibration or safety certification. The full-frontier target remains mildly optimistic and worse for the n=3 source model. Existing raw pipeline labels are proposal-oriented; the separate replay audit intentionally checks selected actions.

## Next data correction: separate selected-cohort calibration

`src/media_rl/frontier_calibration.py` adds `FrontierCalibrationProtocol`, `collect_frontier_samples` and `recalibrate_frontier_bundle`, using dedicated **`frontier_calibration_v12`** seeds, existing declared weighted safety families and only genuinely accepted source-screen actions. Unlike the frozen V6 collector, it uses profile-aware packet traces and **h=3 new-capture-cohort labels**, drops terminal censoring, excludes fallback/rejected-candidate score proxies and keeps actor, safety ensemble/scaler and single-model calibrator frozen. Only the main monotonic Platt calibrator changes. Original V6 one-step/ID/namespace behavior is untouched.

The development test fits **30 source-selected calibration episodes** for frozen n=3 model seed70 and compares source versus derived calibrators on new trace ID **23001**, both K=42 with unchanged thresholds/guards. No final test or previously seen trace is used for fitting. Newly selected actions after recalibration can have a different distribution, so one-pass calibration is not a guarantee; quality/risk/accepted coverage must be checked on new data. Helper: `.tools/pilot_frontier_calibration_v12.py`; expected outputs: `results/frontier-calibration-v12-pilot`.

Tests cover selected action versus proposal, deadline horizon, accepted-only sampling, terminal censoring, seed isolation, deterministic record reproduction, unchanged source policy/ensemble/single-calibrator/metadata and derived checkpoint roundtrips. The development pilot completes; **158 tests** and Ruff lint/format pass. From 6,011 accepted source actions, **49 terminal labels** are censored and **5,962** remain for a monotonic Platt fit. Source slope/bias 0.95952/0.05980 becomes 0.91320/0.07318. This is not a fitted quality/safety improvement by itself.

On new ID **23001**, full-frontier source versus recalibrated screen:

| Metric | Source calibrator | Selected-cohort calibrator |
|---|---:|---:|
| Nominal QoE | 1.08690 | 1.13675 |
| Stress QoE | 0.18653 | 0.16520 |
| Nominal unsafe (%) | 14.479 | 14.896 |
| Stress unsafe (%) | 32.024 | 32.202 |

Nominal quality improves **0.04985**, but stress quality worsens **0.02133** and unsafe frequency increases **0.417/0.179 pp**. The proposal-only calibrated variant also loses nominal/stress QoE (0.91846→0.88468 / 0.03784→−0.02862). **Do not adopt** this data correction or weaken thresholds to hide the failure. It is development evidence, not a formal validation decision or new SOTA result.

`results/jobs/frontier-calibration-v12-evidence-check.json` recomputes all fit parameters from saved raw scores/labels, checks 49 exclusions and split separation, proves frozen actor/ensemble/single-calibrator/source checkpoint, verifies 387 trained artifacts and both panel hashes, all **31,680 queue-accounting rows**, and matched physical/conventional outputs. Original V6 semantics and old studies are unchanged.

## Outstanding claim boundary

A stronger result still needs a predeclared multi-seed validation/fresh-test protocol, selection-specific reliability and risk-matched baselines. Genuine modern GCC/published RTC controllers, compatible packet feedback/actuation, natural/measured held-out media/network data and end-to-end codec/network evidence remain missing. See [SOTA_TRACK.md](SOTA_TRACK.md). No cloud/privileged installation/upload/deployment or publication submission is authorized or performed by these experiments.
