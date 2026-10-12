# Active scientific status (2026-10-12 UTC)

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

The separate [synthetic factual-acceptance audit](TYPED_FACTUAL_ACCEPTANCE_V1.md)
uses only executed randomized block labels, three new training seeds and fresh
trace realizations of read families. The point selector approves all six fits:
at 20k blocks both unseen-panel means are negative, while at 80k only the training
family interval establishes gain. Episode/family lower-bound selectors decline
every fit and exactly reproduce fixed control. This prevents the observed
low-data departures but discards the positive higher-data ID result. It is no
controller improvement or selected-action calibration. All six refits and
eighteen packaged models reproduce from the saved factual labels.

Fresh native capture is now available through a policy-permitted authenticated
localhost TURN/TCP relay. A separately registered [observability probe](NATIVE_TURN_PROBE_V1.md)
completes sixteen peers and 96 IID randomized holds on four owned procedural
settings, with 2,832 causal sender samples and actual encoded payload histories.
All registered source hashes, assignment/feature/encoder/marker/RGB replay and
eight resealed-forgery checks pass. The actual normalized rates average 0.580,
0.721 and 0.881 at requested ratios 0.65, 0.85 and 1.05; these pooled descriptive
means do not qualify a state-conditioned effect or model.

The stronger FIFO audit finds a preserved V1 bookkeeping defect: closing-ledger
metadata precedes 10–36 empty timer ticks per peer. Every raw event is checked,
using exact ledger-prefix replay and explicit zero-service suffix verification.
A separate prospective collector V2 and excluded technical peer remove that
defect without rewriting the original captures. This is a new transport/content
development track, not a replication of the UDP pilots or real-network evidence.

## Largest current uncertainty

Can sender-observable history identify a *useful and realizable* cap change beyond
what the native estimator already does, rather than merely predict a simulator's
action value? Native cap requests, encoded payload, BWE and receiver timing have
different dynamics. The simulator's floor after a drop and native recovery diverge;
the rule also starts at 1.05 while the stronger fixed comparator starts at 0.65.
Those are hypotheses to distinguish, not identified causes of the observed loss.

## Next informative work

1. Use the new factual TURN histories for explicitly developmental measurement and
   simple estimator/encoder diagnostics, without altering the failed simulator.
   Preserve missing counters, distinguish encoder target, actual pre-RTP bytes,
   RTP/header/retransmission bytes and cap readback, and compare causal history
   with matched history-plus-action inputs. Four procedural settings are too few
   for action-value qualification or generalization. Freeze a prospective V2
   study before collecting a broader panel, vary previously unseen network
   mechanisms/content, and match requested **and actual encoded-rate** trajectories.
   In parallel, the targeted pinned restore below remains the route to original
   UDP/licensed-video history; do not equate TURN dynamics with that transport.
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

The fresh native-capture access blocker is removed without modifying the browser's
managed policies. Native factual telemetry and the synthetic study continue
locally. Original licensed video working copies and old native raw captures are
still absent: no original UDP trajectory has been reconstructed. The managed
environment has no private archive credential, the old desktop session ended,
and its HTTP policy omits Hugging Face archive hosts. A concrete targeted input plan is
`reports/bwe-dynamics-diagnostic-v1/next-input.json`: the lexically first used
range-pilot source, its twenty sessions covering all schedules and levels, selected
from identities alone. It pins the verified private archive revision
`36b82e4045dc8f982930839c8528719ed30447ba`. A complete targeted evidence bundle
with retained session/runtime metadata, or securely configured archive read access
and permitted hosts, is needed for that original-history audit. Do not restore all archives automatically,
invent missing telemetry, rewrite seals or place credential values in Git/chat.

The original real-network target remains open. Browser measurements across an
emulated relay on one machine are native-stack evidence, not validation on real
network conditions. Development p-values and simulation utility cannot justify
promotion, a safety guarantee, or an RLCD-specific benefit.

Approximately 230 MB of new raw evidence is retained outside the repository, with
compact sealed inventories in Git. It is not a verified backup; private archival
is pending and no unarchived raw bytes are pruned. The project remains far below
its 10 GB limit. Original controller freezes and all negative results are retained.
