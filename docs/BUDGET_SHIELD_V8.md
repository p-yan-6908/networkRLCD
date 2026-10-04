# V8: causal wire-budget action screening

## Frozen hypothesis and boundaries

V7's raw ensemble-disagreement guard activates rarely and does not close the deterministic-baseline gap. V8 tests a complementary, stateful congestion signal: restrict screened candidate **wire rate**, including FEC overhead, to the existing deterministic fallback's warm probing budget. This is a controller refinement, not new trained weights, a capacity oracle, a calibrated lower bound, or a formal shield. This protocol is written before opening its validation/final panels; prior V1–V7 behavior informed the hypothesis, so it remains an adaptive synthetic follow-up.

For each decision, the shadow conservative controller updates once from causal telemetry. Its budget starts at 0.6 Mbps. With RTT excess >35 ms, raw loss >0.06, or RTT trend >15 ms, it backs off to max(0.15, min(0.7 × budget, 0.8 × acknowledged throughput)); otherwise it probes additively by 0.5 Mbps/s, capped at the largest configured wire rate. Missing/stale/nonfinite feedback follows the existing fallback rule. The budget is persistent, not capped by application-limited ACK throughput in uncongested states. No dynamics or constants are fitted in V8.

Candidate `shielded_budget` and reference `shielded_uncertainty` use the exact same frozen V6-derived checkpoints, calibrator, top-five Q ranking, 0.90 probability threshold, 0.05 raw ensemble-standard-deviation cutoff, support/feedback guards and fallback. Only the candidate additionally requires `bitrate × (1 + FEC) <= warm budget`. It picks the first jointly eligible ranked action; if probability/disagreement-eligible candidates all exceed the envelope, it uses deterministic fallback with reason `budget_abstention`. It never searches beyond the five declared candidates. The probability remains an empirical one-step estimate; the budget does not multiply or recalibrate it.

The **test-only** `budget_only` ablation removes probability and disagreement eligibility, retaining the same frozen Q ranking, support/feedback guards, envelope and fallback. Safety scores are still computed for diagnostics. Thus this is not a model-free baseline or an inference-cost comparison. This ablation is reported regardless of the validation decision and cannot become a post-test winner. Conservative, heuristic, GCC-like, ungated RL and the V6-checkpoint proposal gate are also retained.

## Panels and locked promotion

`configs/budget_shield_v8.json` freezes ten source model seeds, **five validation trace seeds 12701–12705**, ten disjoint fresh test seeds **13701–13710**, all eleven known families and 600 intervals per episode. All panel seeds are distinct from earlier declared studies. Validation has 1,100 paired episodes (two screens); final evaluation has 8,800 episodes (eight methods), even if V8 is rejected. Known stress families are not unseen mechanisms.

Promotion compares V8 with V7 on validation only. Reuse the V7 bounds: ID QoE drop <=0.03; ID violation increase <=0.01; aggregate stress violation increase <=0.02; each stress-family increase <=0.03 (all violation limits are rate fractions). Score = 0.5 × (ID QoE + stress QoE) − 5 × stress violation rate; feasible candidates must improve score by strictly more than 0.005. The checkpoint hashes and validation-manifest hash are persisted in `selection.json` **before** test traces are generated. Test effects cannot modify this lock.

## Reproduction and evidence

```sh
# Inspect the existing immutable evidence; no re-evaluation is needed.
uv run media-rl audit --run results/budget-shield-v8/validation
uv run media-rl audit --run results/budget-shield-v8/test
uv run media-rl export-paper --run results/budget-shield-v8/test \
  --out paper/generated-budget-shield-v8 --macro-prefix Budget
# Fresh reproduction under the current runtime; do not overwrite canonical evidence.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  uv run --frozen media-rl budget-shield --config configs/budget_shield_v8.json \
  --models results/action-calibration-v6/candidate-models \
  --out results/budget-shield-v8-reproduction --no-plots
```

`make budget-shield-v8` is the original canonical launch target, not permission to overwrite the completed study. Post-run paper/documentation edits change the source identity, so rerunning into its existing directory deliberately refuses source drift; use a fresh reproduction directory. The immutable source snapshots retain the pre-evaluation protocol and implementation.

All outputs are immutable. The runner reuses complete stages only under identical audited source/settings/checkpoint hashes and refuses partial/tampered/changed campaigns. There is no mid-evaluation resume; preserve a failed directory rather than overwrite it. CPU only; no cloud/GPU job is required.

Step logs record the warm wire budget, number of top-five candidates over budget, whether the envelope changes the otherwise-eligible highest-Q choice, and separate fallback reasons. Reports aggregate by model seed, with matched seed-cluster contrasts against V7, the confidence-ablated budget screen, and GCC-like. Selected-action audits exclude rejected-candidate probabilities on fallback steps: those scores must not be matched to fallback outcomes. Generated tables and `budget_results.json` bind to the audited selection, step log, diagnostic files and complete manifest.

## Completed result: V8 not promoted

The CPU campaign completed in approximately 24.5 minutes. Validation audited **327 artifacts / 1,100 episodes**; the fresh test audited **386 artifacts / 8,800 episodes / 5,280,000 intervals**. Validation retains `shielded_uncertainty`: V8's ID QoE drops **0.0946**, exceeding the frozen 0.03 limit, despite passing every violation bound and gaining **0.047619** in score. The saved decision was not changed after test.

Paired V8-minus-V7 fresh-test effects (95% model-seed intervals, conditional on this fixed panel) are:

| Domain | QoE change | Violation change (percentage points) |
|---|---|---|
| ID | −0.1038 [−0.1851, −0.0346] | −0.680 [−1.010, −0.372] |
| Stress | −0.1328 [−0.1949, −0.0765] | −2.862 [−3.724, −1.986] |

The envelope changes otherwise-eligible choices on 56.90% ID / 50.24% stress steps; budget abstention occurs on 16.46% / 23.40%. Collapse and bufferbloat improve QoE (+0.373/+0.299) and reduce violations (−10.310/−7.638 pp), but burst-loss QoE falls **1.132** with unchanged **17.15%** violations. This is consistent with raw-loss budget backoff reacting to erasures as well as congestion; it is not a long-run causal effect estimate. The budget was not retuned to remove this harm.

Adding confidence/disagreement eligibility to `budget_only` changes ID/stress violations by +0.003/−0.009 pp, with intervals [−0.013, +0.016] / [−0.054, +0.017] that include zero. QoE falls by 0.0194/0.0131; thus this panel provides **no resolved incremental violation benefit from confidence eligibility under this envelope**. The ablation still uses learned Q ranking and support rejection, so it does not establish that all learned components are unnecessary. No ablation or other post-test winner is promoted. GCC-like offers greater mean ID/stress QoE (2.130/1.101 versus 1.952/0.941 for V8).

Accepted stress actions remain **1.51 probability points optimistic [0.99, 2.07]**; the ablated screen has the same rounded optimism. Both use unchanged calibrators. This is post-selection/occupancy evidence, not a newly improved probability estimator or a safety guarantee. Rejected-candidate scores are excluded from the accepted-action audit.

A direct full-data probe reproduces all **12 paired contrasts**, verifies the lock predates test-trace files, confirms all **ten source bundles are byte-identical**, and checks every accepted budget action: **482,299 V8 plus 483,396 ablation steps**. Complete-stage reuse succeeded without re-evaluation before post-run reporting edits. Receipts: `results/jobs/budget-shield-v8-evidence-check.json`, `results/jobs/budget-shield-v8-preflight.json`, and `results/jobs/budget-shield-v8.log`. Generated tables and `budget_results.json` are in `paper/generated-budget-shield-v8/` with separate provenance.

The minimum feasible wire rate can exceed the budget and fallback can fail. These are adaptive known-mechanism synthetic findings, not independent Internet sampling. Intervals resample model seeds, not network populations. No test-driven retuning, cloud/GPU job, real-network validation, deployment, upload or submission occurred.
