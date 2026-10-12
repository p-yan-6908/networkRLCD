# Active scientific status (2026-10-11)

The goal is a Jev/RLCD-inspired bitrate controller whose causal network and encoder
history supports safe BWE-relative actions and reproducible delivered-quality gains
over strong tuned baselines. Synthetic rollout supervision and factual native
validation are separate tracks. No current controller qualifies for promotion.

## What the newest evidence resolves

The [one-minute margin pilot](NATIVE_MARGIN_PILOT_V1.md#results-2026-10-11) completed
192 native browser sessions. Its history rule loses to tuned fixed 0.65 by −1.13
endpoint units [−1.99, −0.27]; it also loses on-time delivery. The loss survives a
post-report six-comparison Holm check and every leave-one-source-out mean check.
These do not constitute new replication or broad safety evidence.

The simulator's unchanged forecast fails its registered blind test on that same
rule-versus-baseline contrast. Broad agreement on arm averages hides a decision-relevant
failure. Raising model complexity or training another policy against that dynamics
model would not resolve whether its apparent opportunity exists natively.

The reports, original forecast, controller freeze and prior negative results are
preserved. `reports/native-margin-validation-v1/audit.json` verifies compact outcomes
and statistics only. It explicitly records that raw seals/frames were not replayed.

A subsequent [factual BWE diagnostic](BWE_DYNAMICS_DIAGNOSTIC_V1.md), specified before
its calculation on the already-read summaries, compares persistence, momentum,
pooled drift, and two small regressions on source/regime CV. A fit on short range
sessions improves short-session prediction but loses to persistence on the
one-minute panel (MAE 0.181 vs 0.161); adding the current cap gives no consistent
benefit. Nominal 0.25 is clipped in 67–76% of its epochs, and range sessions have
no within-session nominal cap changes. Neither these predictive fits nor later
endogenous states identify state-conditioned action value. No simulator revision
or controller follows from this development result.

## Largest current uncertainty

Can sender-observable history identify a *useful and realizable* cap change beyond
what the native estimator already does, rather than merely predict a simulator's
action value? Native cap requests, encoded payload, BWE and receiver timing have
different dynamics. The simulator's floor after a drop and native recovery diverge;
the rule also starts at 1.05 while the stronger fixed comparator starts at 0.65.
Those are hypotheses to distinguish, not identified causes of the observed loss.

## Next informative work

1. The compact-summary BWE diagnostic above is complete. Before policy training,
   restore targeted factual sender/encoder histories under a pinned archive revision
   and register a timestamped estimator/actuator diagnostic. Compare simple models
   of startup, clipping, probing/recovery and delayed feedback. Match requested
   **and actual encoded-rate** trajectories, not solely endpoint order or one-step
   BWE error. The compact summaries cannot supply this missing encoder history.
2. Diagnose the memory rule using a separate, prospectively specified native
   factorial comparison with matched startup, memory enabled/disabled, and repeated
   identical-policy peers. Randomise whole sessions: short crossover blocks have
   already failed carryover identification. Freeze the design before any new outcomes
   and retain all failures. This would distinguish hypotheses; it is not a proposed
   deployment. The existing twelve sources can support development diagnostics,
   never fresh-source generalisation claims.
3. A revised dynamics model needs a new blinded native panel before simulator
   gains inform a native controller claim. Vary network families and content,
   preserve B1/N1 reservations, and use source/capture and network-family uncertainty
   appropriate to the claim. A native learned policy still needs factual randomized
   supervision, held-out action-value skill versus a matched state-only control,
   selected-policy calibration, and closed-loop comparison to tuned baselines.

This checkout contains the compact reports but no original licensed video working
copies or full native raw captures. The managed environment has no configured
private archive credential. Trajectory reconstruction from raw telemetry needs a
targeted, pinned restore with secure read access; new native capture needs the
licensed source dependencies and the native browser/relay harness. No raw downloads
or new captures were substituted for missing inputs in this iteration.

The goal is blocked at that timestamped-evidence boundary. The selected executor's
HTTP policy also omits Hugging Face archive hosts. A concrete minimal input plan is
`reports/bwe-dynamics-diagnostic-v1/next-input.json`: the lexically first used
range-pilot source, its twenty sessions covering all schedules and levels, selected
from identities alone. It pins the verified private archive revision
`36b82e4045dc8f982930839c8528719ed30447ba`. A complete targeted evidence bundle
with retained session/runtime metadata, or securely configured archive read access
and permitted hosts, is needed next. Do not restore all archives automatically,
invent missing telemetry, rewrite seals or place credential values in Git/chat.

The original real-network target remains open. Browser measurements across an
emulated relay on one machine are native-stack evidence, not validation on real
network conditions. Development p-values and simulation utility cannot justify
promotion, a safety guarantee, or an RLCD-specific benefit.
