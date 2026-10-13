# Active scientific status (2026-10-13 UTC)

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

A [post-capture proximal action diagnostic](NATIVE_TURN_ACTION_DIAGNOSTIC_V1.md)
now recomputes the actual randomized-hold effects from the unchanged capture.
Its peer/epoch-adjusted, peer-clustered 1.05-minus-0.65 contrast raises actual
encoded payload by 0.279 normalized units [0.187, 0.372] (Holm p=0.000063 over
six endpoint/contrast tests). The corresponding 150 ms on-time proxy changes by
only +7.2 percentage points [-11.2, +25.5] (adjusted p=0.833); all three delivery
intervals include zero. This is exploratory actuator evidence, not a delivered
QoE gain, policy comparison, safety result or state-conditioned action value.
The diagnostic verified all 82 files in the selected raw capture against the
matching entries of the retained inventory and reproduced all 16 session
summaries. It did not modify or archive raw evidence.

The stronger FIFO audit finds a preserved V1 bookkeeping defect: closing-ledger
metadata precedes 10–36 empty timer ticks per peer. Every raw event is checked,
using exact ledger-prefix replay and explicit zero-service suffix verification.
A separate prospective collector V2 and excluded technical peer remove that
defect without rewriting the original captures. This is a new transport/content
development track, not a replication of the UDP pilots or real-network evidence.

The scratch-isolated V2b action assay completed 64 peers and all 384 assigned
holds, with no aliased assignments and complete payload/readback endpoints.
Independent sender and FIFO replay passed across all peers, and the exact
323-file / 669,573,522-byte raw inventory remains unmodified. The registered
1.05-versus-0.85 contrast lowers the 150 ms on-time proxy by 3.785 pp
[-6.711, -0.858], Holm p=0.0483; all six registered comparisons are retained.
The capture command exposed its unadjusted arm summaries before the audit, so
V2b is exploratory despite the pre-capture estimator/contrast freeze. It
indicates an action-to-payload response and a delivery-risk hypothesis, not a
QoE benefit or policy effect. The independent V3 replication is registered
with new scene, treatment-assignment and trial-order seeds and keeps the full
six-test family; its outcome summaries remain unopened until its inventory and
audit pass. See the [V2b results](NATIVE_TURN_ACTION_ASSAY_V2B_RESULTS.md)
and [V3 registration](NATIVE_TURN_ACTION_ASSAY_V3_REGISTRATION.md).


## Largest current uncertainty

Can sender-observable history identify a useful and realizable cap change that
improves delivered quality over a strong controller without trading away safety?
V2b verifies only that randomized caps move actual payload, while its exploratory
readback estimate raises a replication question. Native cap requests, encoded
payload, BWE and receiver timing have different dynamics. The simulator's floor
after a drop and native recovery diverge; the rule also starts at 1.05 while the
stronger fixed comparator starts at 0.65. These are hypotheses to distinguish,
not identified causes of the observed loss.

## Next informative work

1. Complete the new V3 blinded replication of the exploratory V2b proxy effect
   with the frozen full contrast family and audit-before-analysis order. Keep
   V1, V2a and V2b raw evidence and negative findings intact. Regardless of
   replication outcome, these local capacity schedules do not establish unseen
   physical network families, policy value or whole-session QoE. Restore only
   the pinned range-pilot records in reports/bwe-dynamics-diagnostic-v1/next-input.json
   after archive access is actually ready; use them to reconstruct original
   UDP/encoder history, not to tune against held-out data. Do not equate TURN
   dynamics with the archived UDP/licensed-video transport.
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
still absent: no original UDP trajectory has been reconstructed.

The receipt-pinned archive restore was attempted in the current managed runtime.
The huggingface_hub 2.2.0 SDK and its hf CLI were installed and verified through
uv, but the SDK found no usable token. A current environment-status read lists no
secret, runtime-variable or outbound-identity bindings, and its enforced policy
excludes Hugging Face hosts. Listing the private dataset at the range receipt's
pinned revision and downloading only its SHA256SUMS both failed with ProxyError;
zero archive bytes were downloaded. Thus the user's stated HF_TOKEN is not
visible to this task runtime, and the policy blocks the exact restore route. No
token was inspected, placed in the repository or sent to chat.

A concrete targeted input plan is
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

New native TURN raw captures and their inventories remain outside the repository;
the raw bytes are unarchived and no unarchived evidence is pruned. These working
copies are not verified backups. The project remains far below its 10 GB limit.
Original controller freezes and all negative results are retained.
