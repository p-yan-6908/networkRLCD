# RLCD manuscript review checklist

## Completed

- [x] Explicit causal telemetry/action contract and proposal-level binary safety target.
- [x] Separate policy, safety fitting, post-hoc scaling, support rejection and stateful fallback.
- [x] Distinguish empirical mitigation from formal shielding and episode safety.
- [x] Traceable calibration, shift, shielding, congestion-control and domain-randomization sources.
- [x] Complete and audit v1: 19,800 episodes, 358 verified artifacts; retain pilot-panel overlap disclosure.
- [x] Freeze original policy weights, train safety refits, and control for ID supervision and fallback composition.
- [x] Dedicated validation namespaces/seeds, persisted selection lock, and genuinely fresh realization seeds before final evaluation.
- [x] Complete and audit v2: 1,188 fresh-test episodes, 218 verified artifacts.
- [x] Evaluate confidence predictors on identical ungated states as well as raw/calibrated scores on selected-controller states.
- [x] Preserve selected-controller regression, ID calibration harm, baseline wins and non-promotion; no post-hoc winner swap. V4 also reports its negative fresh-test QoE/violation contrasts transparently.
- [x] Keep mechanism-overlap terminology honest: historical OOD becomes the v2 stress panel.
- [x] Complete and audit the ten-seed, five-threshold v3 validation sweep; lock 0.90 before the 7,700-episode fresh test when the best alternative gain (0.0009) misses the 0.005 margin.
- [x] Report v3 as fresh-realization evidence on validation-known mechanisms, retain the explicit fixed-0.90 comparator, and make no conformal-risk-control claim.
- [x] Complete and audit the v4 ten-seed policy-randomization study (7,700 validation and 7,700 fresh-test episodes); keep policy-training randomization separate from ID-only risk/calibration fitting.
- [x] Lock the validation candidate decision before opening fresh test traces; reject the v4 candidate on prespecified ID-QoE and individual-family risk bounds and report test evidence without post-test promotion.
- [x] Generate v3 ranking and v4 promotion/family/scenario tables from audited evidence with separate provenance; archive the earlier pilot manuscript.
- [x] Historical v3/v4 PDF compilation and result-page inspection; later V5–V8 evidence is separate, not silently substituted. Current build/diagnostic receipts are in `docs/verification.md`; the Tectonic driver has a documented nonfatal bibliography rerun warning.
- [x] Complete and audit V5/V6/V7 action screening, selected-action recalibration and disagreement-screen studies, preserving negative outcomes, residual optimism and the original partial runs.
- [x] Freeze and complete V8 on ten unchanged bundles: 1,100 validation and 8,800 test episodes, 327/386 artifact audits, validation-lock ordering, all accepted wire-budget constraints and 12 paired contrasts verified.
- [x] Reject V8 on its nominal-QoE bound despite a score gain; report risk reductions, QoE harms, erasure-family regression and confidence ablation without post-test winner selection.
- [x] Keep candidate confidence separate from fallback safety, and state that post-selection/occupancy diagnostics do not establish improved weights, probability calibration or episode guarantees.
- [x] Historical V8 receipt: verify the 29-page / 16-reference draft, eight provenance bundles and 87 generated hashes; review V8 method/result/audit pages, fix layout boxes/float leakage, and preserve the known nonfatal driver bibliography warning. Independent all-page proofreading remains a submission blocker.

- [x] Freeze and complete V9 with unchanged models and old-method parity, fresh 1,650/9,900-episode panels, 346/405 artifact audits and 159 implementation files matched in both snapshots.
- [x] Recompute the locked rejection and all 16 paired estimates; check every accepted V9/ablation envelope and preserve canonical V8 data. Report burst-loss repair alongside unresolved stress-quality effects, nominal rejection, confidence-eligibility regression and remaining GCC-like gaps.
- [x] Cite verified RFC 8868 metadata/passages as evaluation motivation, not justification of thresholds, reliable loss-cause identification or standards compliance.

- [x] Verify the current **34-page / 17-reference** nine-study PDF, **101 generated hashes**, visible tiny interval signs and unchanged canonical V8/V9 data. Render/review V9 pages 23, 24, 31, 32 and 33; fix inline-interval overflow and the heading-only appendix page, while retaining the known nonfatal driver bibliography warning.

## Remaining before submission

- [ ] Correct author/affiliation information and venue/template.
- [ ] Independent proofreading of every page and final signs/units.
- [ ] Assess policy convergence without treating training reward as validation.
- [ ] More model seeds and validation/final trace panels; quantify uncertainty over network populations.
- [ ] Conditional/rare-event calibration and nominal/stress tradeoffs; avoid assuming lower aggregate NLL gives safer control.
- [ ] Fallback-aware/feasibility-aware control; characterize introduced harm and long-horizon safety.
- [ ] Full-budget physical/temperature/threshold ablations; existing physical sweeps remain smoke scale.
- [ ] Packet/FEC/codec validation, real traces, emulator/WebRTC integration, fairness and actual runtime overhead.

Current paper: `paper/main.tex` / `paper/build/main.pdf`. Nine separate empirical sources and export commands are listed in `paper/README.md`, including `results/budget-shield-v8/test`. V2/V4/V8/V9 are not promoted, V3 retains 0.90, and the V9 lock still retains V7. No formal guarantee, independent Internet sampling, real-network validation, submission or publication is claimed.
