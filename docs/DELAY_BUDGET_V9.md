# V9: delay-evidence wire-budget screening (completed, not promoted)

## Motivation and intervention
V8 reduces aggregate unsafe frequency but fails nominal QoE promotion and harms burst-loss quality. This adaptive follow-up tests **removing raw-loss-only budget backoff**, not a reliable congestion/erasure classifier. RTT excess >35 ms or RTT trend >15 ms still triggers backoff. Raw loss still influences the unchanged FEC preference. The budget starts at 0.6 Mbps, probes at 0.5 Mbps/s, backs off by the existing 0.7/0.8 rule, and retains the same floor, cap and missing-feedback handling.

This changes **both the warm shadow budget and its deterministic fallback dynamics** for the two new opt-in methods. It is not an envelope-only same-fallback comparison with V8. All old methods retain their original raw-loss response. V9's `shielded_delay_budget` uses the same frozen V6-derived Q policy, risk ensemble, calibrator, top-five candidates, probability threshold 0.90, raw disagreement cutoff 0.05, feedback/support guards and FEC-inclusive wire-rate screen. `delay_budget_only` removes probability/disagreement eligibility but retains the same Q ranking, support guard, new budget/fallback and logged scores; it is not model-free or a runtime ablation. Latent capacity, simulator loss causes and scenario identity are never controller inputs. No policy, safety weights or calibrator are retrained here.

## Frozen validation and test
`configs/delay_budget_v9.json` declares ten model seeds, validation trace seeds **14701–14705** and fresh test seeds **15701–15710**. These identifiers are disjoint from previous declared panels. All eleven known families and 600 intervals per episode are retained. Validation compares V7, V8 and V9 (**1,650 episodes**); promotion compares **only V9 versus V7**, the retained prior controller. V8 is a paired mechanistic comparator, never a promotion alternative. Test retains all three, the matched confidence ablation, conservative, heuristic, GCC-like, ungated RL and the proposal gate (**9,900 episodes / 5,940,000 intervals**), whether or not V9 is promoted.

The unchanged promotion bounds are ID QoE decrease <=0.03, ID unsafe increase <=0.01, stress unsafe increase <=0.02, and each stress-family unsafe increase <=0.03 (rates are fractions). Score is 0.5*(ID QoE + stress QoE) - 5*stress unsafe rate; a feasible candidate must gain strictly more than 0.005. Checkpoint hashes and the validation-manifest hash are locked before generating any test traces. No test-driven retuning or post-test replacement is allowed.

## Reproduction and acceptance
```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  uv run --frozen media-rl delay-budget --config configs/delay_budget_v9.json \
  --models results/action-calibration-v6/candidate-models --out results/delay-budget-v9 --no-plots
uv run --frozen media-rl audit --run results/delay-budget-v9/test
uv run --frozen media-rl export-paper --run results/delay-budget-v9/test \
  --out paper/generated-delay-budget-v9 --macro-prefix DelayBudget
```
Use a **new directory** for reproduction after source/reporting edits. Preserve partial/tampered/changed directories; no mid-evaluation resume is claimed. Complete-stage reuse requires identical audited source/settings/checkpoints. Verify registration and guard behavior, legacy parity, immutable models and lock timing, all accepted wire constraints, paired model-seed contrasts and artifact hashes. Export V9-minus-V7, V8, confidence ablation and GCC-like contrasts, separate scenario comparisons and accepted-action/proper-score audits for both screens.

Preflight: **99 tests pass**, format/lint checks pass, and the real-checkpoint probe matches **118,800 legacy decisions exactly**. It checks **39,600 V9/ablation decisions**, including **31,108 accepted wire constraints**, without computing selection performance on validation/test panels. Receipt: `results/jobs/delay-budget-v9-preflight.json`.

The protocol above was frozen before either panel was opened; completed findings follow. Intervals condition on ten model seeds and the fixed known-family trace panel, not network-population or episode safety. Standards motivate diverse loss/delay tests, not these thresholds or standards compliance. CPU only; no cloud job, private upload or deployment occurred.

## Completed result: partial repair, still not promoted
The CPU campaign took **18.4 minutes** (real 1103.96 s). **1,650 validation / 9,900 test episodes / 5,940,000 final intervals** pass **346/405 artifact** audits. Validation rejects V9's **0.1109 ID-QoE loss** (2.1495 to 2.0386; limit 0.03), despite passing every risk bound and gaining **0.090963** in score. The persisted choice remains `shielded_uncertainty` (V7).

| V9 minus V7 | Mean | 95% model-seed interval |
|---|---:|---:|
| ID QoE | -0.1137 | [-0.1938, -0.0471] |
| ID unsafe (pp) | -0.376 | [-0.574, -0.187] |
| Stress QoE | +0.0127 | [-0.0434, +0.0684] |
| Stress unsafe (pp) | -2.416 | [-3.371, -1.273] |

Versus **V8 on this new panel**, ID QoE/violation means are exactly equal. Stress QoE gains **0.1658 [0.1534, 0.1801]**, with **zero observed violation difference**. Burst-loss QoE recovers **1.160** (0.776 to 1.937), with unchanged **19.75%** violations; every other scenario mean is unchanged. This removes the targeted loss-response harm here but does not fix nominal quality or identify loss causes reliably. Both budget and fallback changed, and these are paired controller trajectories, not same-state counterfactuals or a safety-preservation guarantee.

Adding confidence/disagreement eligibility to `delay_budget_only` changes stress QoE by **-0.00278 [-0.00552, -0.00093]** and violations by **+0.024 pp [+0.009, +0.047]**: a small resolved conditional regression, not incremental protection. ID effects are tiny with intervals containing zero: QoE **-0.00143 [-0.00393, +0.00004]**, violations **+0.005 pp [-0.0004, +0.0100]**. The ablation still uses learned Q/support and is not a post-test promotion choice. V9 QoE endpoints use five decimals to avoid rounding the small positive ID endpoint to zero.

Accepted stress confidence is **4.64 pp optimistic [4.17, 5.17]**, versus **4.62 [4.15, 5.14]** for the ablation on its own states. This is changed occupancy, not improved safety weights/calibration. GCC-like control retains higher ID QoE (2.186 vs 2.027) and lower stress unsafe rate (7.590% vs 8.108%); paired V9-minus-GCC stress risk is **+0.517 pp [0.112, 1.011]**.

The read-only full-data verifier reproduces **all 16 paired estimates**, recomputes the validation decision, verifies **all ten bundle bytes** and **159 frozen implementation files in both stage snapshots**, checks the lock predates every test trace and checks **529,189 V9 / 530,245 ablation accepted wire constraints**. V8's canonical selection, manifest and raw step log are unchanged. Complete-stage reuse succeeded before post-run rendering/documentation edits; no full evaluation was repeated. Receipts: `results/jobs/delay-budget-v9-preflight.json`, `results/jobs/delay-budget-v9-evidence-check.json`, `results/jobs/delay-budget-v9-reuse.log`, `results/jobs/delay-budget-v9.log`. Exact estimates and provenance: `paper/generated-delay-budget-v9/delay_budget_results.json`. The final nine-study PDF is `paper/build/main.pdf` (**34 pages / 17 references**); **101 generated hashes** and unchanged canonical V8/V9 data are verified in `results/jobs/delay-budget-v9-paper-check.json`. Methods/results and appendix pages 23, 24, 31, 32 and 33 were rendered and reviewed. Native TeX has no unresolved/box warnings; the known nonfatal driver bibliography warning remains. Independent all-page proofreading, author/venue metadata and external-network validation remain outstanding.
