# JevBWE residual V1 — separate opt-in synthetic candidate

## Design contract

This implements the feedback's **bitrate-first residual**, without replacing GCC/BWE,
changing legacy simulator defaults, adopting a native actor, or reinterpreting the old
42-action/native absolute-cap checkpoints.

Execution is:

`causal GCC-like BWE budget → six-residual utility model → empirical risk/support screen → asymmetric constraints → delayed encoder → delivered QoE`.

The public Python policy `media_rl.jevbwe.JevBWE` receives a `Sample` with an externally
supplied BWE. Its choices are `{0.60, 0.70, 0.80, 0.90, 1.00, 1.05}` times that BWE,
clipped to application bounds and a supplied safety ceiling. If the safety ceiling is
below the application minimum, **safety wins**, including zero. FEC is zero and media
mode/FPS are fixed. The experiment's baseline is the existing **GCC-like heuristic**,
not libwebrtc GCC or an oracle capacity estimate.

Only successful owned command application calls `acknowledge(rate, time)`. Increasing
bitrate waits at least **1,800 ms since the last changed-command acknowledgment**;
repeated same-cap ACKs do not reset that clock. Congestion or stale telemetry suppresses
growth for another 1,800 ms. Reductions, risk rejection and falling safety/BWE ceilings
never wait for an increase dwell. A held, clipped/aliased, fallback, emergency-modified
or BWE-equivalent command does not count as learned residual execution.

## Compact causal model

The model ranks the six candidates using one action-conditioned NumPy MLP. With the
pilot's 16 hidden units, the utility model has **1,857 parameters**. It is a delivered
utility predictor, not a replacement transport congestion controller or a new DQN.

Four ordered causal snapshots (now −3 s, −2 s, −1 s, now) provide a compact three-second
history. Each has values **and explicit presence masks** for BWE, delivery, RTT, RTT
change, loss, jitter, queue trend, requested bitrate, actual output, encoder target,
QP, frame size and reported deadline misses. Snapshot age is also explicit. Selection
uses only samples at/before each lag; gaps >1 s reset the history, and absent/stale lag
samples are masked. Stale/invalid network measurements remain masked inside history even
after fresh feedback returns; locally owned encoder/command fields remain distinct.
Unlike the prior permutation-invariant summaries, ordering matters.

No phase, source ID, absolute clock, hidden capacity or future outcome is a neural input.

Requested cap, observed encoder target and actual output are **different fields**.
Nullable QP/encoder telemetry is not silently replaced with a measured zero. The old
identified native encoder/QP sidecar and actor ABIs remain untouched. New native use
will require a versioned, validated causal adapter and **fresh residual-action data**;
this pilot is not such a native integration.

## Observable delayed credit

`SettledCredit` starts from a factual command with a frozen causal state, BWE and
network-delay estimate. Credit does **not** start after an arbitrary 200–600 ms command
age. It waits until measured encoder target is within 5% of the requested cap, then
waits the issued-time RTT/2 estimate, then integrates **600 ms of delivered QoE**.
The interval discovering target settlement is excluded. Superseded, target-lost and
end-truncated commands retain explicit censored rows with **no reward**. A command
switch cost is charged once in its settled utility label.

This is a deliberately conservative observable attribution rule, not a claim that
cap attainment proves output/perceptual settlement. Content-limited native targets can
remain below the cap: those commands would be censored, and settlement-based missing
labels can introduce selection bias. Censoring and alias/changed-command counts are
retained rather than converting them to zero rewards or concealing failures.

The wrapper's encoder response is a **hypothesis**, with 1,500 ms increases / 100 ms
decreases, not a fitted reproduction of Chrome. A synthetic content factor makes
output differ from target. QP is a synthetic proxy. The legacy fluid simulator's
actual-output log-quality term, latency/loss/deadline penalties plus requested-cap
switch penalty form the reward. **No perceptual quality or real codec gain is claimed.**

## Leakage boundaries and qualification

Stable hash-derived namespaces separate **train, qualification, risk, calibration and
test**. Fitting/qualification roles use only the pre-existing ID scenario schedule;
OOD/evaluation seeds and labels never enter fitting or action-value acceptance.
Random residual permutations with frozen three-second holds collect factual outcomes;
no counterfactual simulator preview/oracle is used as a model input or utility label.

An identically initialized/trained state-only control has the same architecture and
optimizer; its action channels are zeroed. On **changed, non-aliased**, separately
collected qualification cohorts, the conditional model must improve utility MSE by
at least **1% pooled and in both episode-parity folds**, with at least 24 rows and two
examples per residual. A second identically matched pair must also pass on **delivered-only
QoE before the analytically known switch penalty**; a switch-cost shortcut cannot qualify
the controller. These extra models are offline qualification controls, not added runtime
actors. This is a necessary predictive-information check, **not causal native qualification**. Failure disables screened learned residual control and is
reported. No model is promoted regardless of this synthetic check.

Three separately risk-fitted episode-bootstrap models estimate whether **any** interval
in the settled credit window violates the existing latency/loss constraints. Held-out
monotonic Platt calibration, per-action calibration counts, disagreement and a history
support screen control abstention to a deterministic 0.85× BWE fallback. These are
**randomized-hold factual risk labels**, not selected-live-policy calibration or a
certified safety bound; deployment still needs fresh selected-policy calibration.

## Commands and evidence

```sh
# Fast executable smoke, not confirmatory evidence; output must not already exist.
uv run --frozen media-rl jevbwe-run --config configs/jevbwe_smoke_v1.json --out results/my-jevbwe-smoke
uv run --frozen media-rl jevbwe-audit --run results/my-jevbwe-smoke

# Fixed, larger CPU pilot; do not choose/tune this recipe using its evaluation results.
uv run --frozen media-rl jevbwe-run --config configs/jevbwe_pilot_v1.json --out results/my-jevbwe-pilot

# Separate fitting and evaluation; inference weights stay unchanged.
uv run --frozen media-rl jevbwe-train --config configs/jevbwe_pilot_v1.json --out results/my-jevbwe-model
uv run --frozen media-rl jevbwe-evaluate --config configs/jevbwe_pilot_v1.json --model results/my-jevbwe-model/model.json --out results/my-jevbwe-eval
```

Outputs retain resolved configs, source snapshots/hashes, actual weights, matched-blind
qualification, complete/censored cohorts, causal samples, raw evaluation decisions and
metric rows, and artifact-inventory seals. Evaluation rejects changed fitting physics,
policy configuration or source hashes. `jevbwe-audit` verifies hashes/inventory only;
it is not independent native raw replay. Source-only checkouts do not need local films,
Chrome, cloud compute or the excluded historical research bundle.

Evaluation compares **raw BWE, BWE with identical dwell/emergency constraints, screened
JevBWE and an explicitly unscreened/unqualified residual diagnostic ablation** on the
same exogenous traces. Both BWE contrasts are retained, including per-scenario losses;
seed-cluster intervals are descriptive exploratory evidence, not superiority claims.
This makes gains from timing distinguishable from gains attributable to the NN.

## Executed evidence and explicit negative diagnosis

The completed final source-bound run is `results/jevbwe-feedback-pilot-v1-verified/`:
**90 synthetic fitting/qualification episodes**, **1,080 complete factual cohorts**,
**32,400 fitting samples**, and **80 paired evaluation episodes / 28,800 decisions**.
Of the 216 qualification cohorts, **170 changed, non-aliased commands** enter the
fixed necessary check. Utility action skill is **21.03% pooled / 11.39% / 30.63%**;
delivered-only action skill is **37.41% pooled / 30.33% / 44.57%**. Both matched checks
pass without evaluation labels. Runtime utility-model size remains 1,857 parameters.

Exploratory utility effects for screened JevBWE:

| Comparison | Mean effect | Four-seed descriptive interval |
|---|---:|---:|
| vs raw BWE | +1.3372 | [1.2772, 1.3972] |
| vs dwell-matched BWE | +0.4413 | [0.3861, 0.4965] |

**These gains are not evidence of NN superiority.** Only **241/7,200 screened
decisions (3.35%)** are genuine unaliased, non-BWE-equivalent neural executions. A
separate, explicitly **post-hoc** fallback-only diagnosis on the same evaluation
traces retains all weights/physics/timing/headroom and disables neural eligibility
by zeroing calibration support. JevBWE minus this unchanged **0.85× BWE fallback** is
**−0.00199 utility**, interval **[−0.03017, +0.02620]**. Scenario effects are +0.05584
steady, −0.06205 step, −0.06670 Wi-Fi, +0.11765 collapse and −0.05466 feedback gap.
Thus the observed BWE gains can be explained largely by timing/headroom, **not a
demonstrated learned-control gain**. No model is promoted. The diagnostic neither
refits/tunes the NN nor provides a fresh holdout; its 20 simulator replays and raw
logs are sealed separately in `results/jevbwe-feedback-fallback-diagnosis-v1/`.

The smoke deliberately retains its failed utility fold and executes **zero** screened
neural actions; its gain versus raw BWE is exactly reproduced by the dwell reference.
Initial smoke/pilot and intermediate hardening runs remain unchanged. Hardening added
stale-history masks and delivered-only qualification, not evaluation-driven recipe
tuning. Full replay also found 36 **raw-reference metadata-only** base/ceiling errors
during startup/feedback gaps. Correcting those logs changed neither weights nor
comparative outcomes; the corrected source-bound run is the one above.

Verification: **26 new behavioral/integration cases**, **78 adjacent existing
regressions**, lint/format checks, artifact integrity for **107 final files**, complete
factual simulation/settled-credit replay, actual-weight decision parity, all increase
dwell and rate-envelope checks, qualification recomputation, and unchanged checkpoint
bytes. Scripts are shipped with the source distribution:

```sh
uv run --frozen benchmarks/jevbwe/verify.py --run results/jevbwe-feedback-pilot-v1-verified --out results/jobs/my-jevbwe-replay.json
uv run --frozen benchmarks/jevbwe/diagnose_fallback.py --run results/jevbwe-feedback-pilot-v1-verified --out results/my-fallback-diagnosis
```

Artifacts remain local/ignored. These are reproducible **synthetic** model and control
checks, not native codec measurements, calibrated live-policy safety or causal native
efficacy. Improving selected-policy risk data/usefulness and native residual exposure
is more defensible than claiming that the favorable BWE contrast proves a learned win.

## Next boundary

Before native adoption: independently capture residual arms over causal BWE with
balanced changed-action exposure; validate identified encoder target/QP availability;
check propagation-aware factual action value on disjoint contexts; calibrate actual
selected-controller risk; then compare with genuine native BWE on variable/collapse
links. FEC and resolution/FPS remain out of scope until bitrate action value is reliable.
