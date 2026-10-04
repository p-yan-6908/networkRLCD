# Training-only diagnosis and balanced action exposure V1

## What was blocked, and what this phase actually repairs

The [frozen prospective forecasts](NATIVE_ACTION_LATE_VALIDATION_V3.md) failed
necessary action-information replication. That failure, its exact thresholds,
validation targets, six old weights and complete old development/native evidence
remain locked. **No validation labels are read or fitted by this phase.**

A new **read-only training-only diagnosis** uses only the externally fixed
`dc863861...` all-training model manifest and `d33bbf...` canonical development
manifest: **160 cohorts / 1,944 requests / eight original physical groups**.

`results/jobs/native_action_late_training_diagnosis.py` and its immutable
`native-action-late-training-diagnosis-v1.json` find:
- **0/40 matched physical-group/epoch strata contain all three 300/450/900-kbps
  actions.** Two genuinely captured aliases intentionally share each assigned
  sequence; the original two repetitions can supply at most two distinct arms
  per matched source/network/epoch context. Global 60/52/48 cap counts do not
  establish local all-arm exposure. Repeated aliases are not new randomized
  treatment trajectories or extra independent physical groups.
- Only **10/40** strata have both 300 and 900 kbps. Their descriptive mean utility
  contrast is **0.0796352**, spanning **0 to 0.3069392**; this is not a paired
  observed counterfactual or identified causal effect.
- **128** same-cap/group/epoch alias pairs have mean absolute utility gap
  **0.0387648**. Frozen conditional model potentials span only **0.02929–0.04374**
  on average across proposed caps. Separate-run clock/content/encoder/network
  state still confounds these quantities; model potentials are not factual labels.
- All six saved objectives still improve **1.68–2.16%** in their last recorded
  199 updates. Full-train weighted regularized gradient norms are
  **0.0270–0.1461**, with utility overprediction **0.0143–0.0198**. No hidden
  units are wholly dead. Only one member has negative shared utility/risk
  gradient alignment (**−0.439**); the others are positive. This is not a
  stochastic-optimizer stationarity certificate or justification for a blind
  update/loss/hyperparameter sweep. The original Adam/fitter remains unchanged.
  Toy all-parameter finite differences independently validate gradient/bias
  calculations for both zero and original 0.01 penalties.

This identifies a **local action-exposure/comparison coverage deficit**, not proof
that it caused the earlier generalization failure. Global randomized support can
still be informative. The specific remedy below removes this local-coverage gap
for new data; it does not establish transferable learned action value.

## Separate seed-only arm/previous-current balanced assignment

`src/media_rl/native_action_balanced_control.py` and
`benchmarks/native_rtc/balanced_hold_control.mjs` implement the new
`native_three_arm_balanced_hold_control_v1` ABI without modifying old samplers.

- Encode `block_seed * 3 + repetition` in the existing bounded uint32 seed.
  Exactly **three distinct repetitions** share a prespecified permutation block.
  They are deliberately **counterbalanced**, not independently sampled treatment
  assignments. Both actual aliases share each repetition's schedule.
- Initial arm permutation is chosen by the original uint32-style counter mixer.
  Every **32-step epoch** gives exactly one 300/450/900-kbps arm per repetition.
  The six real alias peers therefore give **two factual cohorts per cap** per
  matched group/epoch. This is deterministic seeded balancing, not cryptographic
  or exactly-unbiased continuous randomization.
- For each three-postinitial-epoch block, a seed/counter-only permutation of
  offsets 0/1/2 yields **all nine previous/current cap pairs** across the three
  repetitions. Completed offset blocks return to their initial arm mapping.
  Equal arm exposure alone cannot remove preceding-action confounding; explicit
  transition support helps, but history/physical state can still differ.
- Schedule depends on **no sender features, network phase, content, target/QP,
  quality, model potential, validation label or learned state**. Feature validity
  is still checked. `fixed450` remains constant and interleaved.

Python and JS enumerate every bounded epoch and 170 complete transition blocks
for five including boundary seeds. The actual extracted wheel verifies **360**
exact Python/JS seed/epoch/behavior cases, including maximum encoded seed.

## Actual bounded native pilot: local exposure repaired

`src/media_rl/native_action_balanced_hold.py` provides public **plan/run/audit**.
It freezes **nine conventional Chrome/VP8 peers / one new physical source/network
context**, not a large data panel, refit or trained controller experiment.

The comprehensive **58-prior-input role snapshot** reserves a new full licensed
BBB **100–120-second** clip, excluding the locked BBB 60–100-second validation
ranges and every old train/calibration/diagnostic/test reservation. Original
Blender full-film/credits/CC-BY attribution, video SHA and catalogue from the
[licensed source import](NATIVE_ACTION_LATE_VALIDATION_V3.md) are retained. ToS
is only a frozen compatible common-engine/shadow template, not new footage or
labels. BBB is now a legal *new training film* for future versions; do not call
it wholly unseen by a future model that trains on this pilot. The old V3 claim
of wholly held-out BBB remains historically true for its old frozen candidate.

The prospective native producer is an exact entry projection: **two import/route
filename replacements and one truthful comment** only. Original full native
wire/feedback/owned RGB/content/ACK/inference/maxBitrate readback/150-ms deadline/
PSNR/event/observation/controller bodies are unchanged. The raw, late/reference
cohort functions use their **identical code objects**, rebound only to the new
sampler. The peer verifier has identical bytecode and changes just **one source
entry-key constant**. Historical module globals are not patched.

Original **1800–2200-ms after-ACK factual credit / 200–600-ms reference / 32-step
holds / 150-ms requests** remain unchanged. Encoder target/QP remains a nullable
identified sidecar, never actor input or row-selection gate. No old trial outcome
is copied or relabeled; no current validation/calibration target fits anything.

Actual fresh pilot `results/native-action-balanced-hold-pilot-v1/` supplies:
- **9 actual native peers, 30 randomized factual late cohorts / 365 requests**;
  10 cohorts at each cap, **5/5** matched group/epoch strata with all three arms.
- **All nine actual previous/current transition pairs**, 73.3333% changed actions,
  exact repeated-alias assignment agreement, interleaved conventional fixed450.
- All **9 target-partial/below-90%-cap cohorts** retained, plus all early-reference,
  zero/missed/censored outcomes, encoder sidecars and complete original native
  episode metrics. Configured cap is not proof of attained encoder target.
- **Zero models fitted and zero learned native actions**. One physical group is
  only an engineering/data-coverage pilot, never learning, model generalization,
  safe policy improvement, representative content or SOTA acceptance.

## Verification and concrete evidence

- **18 Python / 3 Node checks**: every-arm/every-block/boundary/32-step/alias/
  feature-independent/fixed450 behavior, actual five provenance negatives,
  code-object/producer projection identity, finite-difference gradients and
  factual support versus predicted-potential scope.
- Complete public audit independently replays **every original nine-native-peer
  source, exact sender/frames/cohort/reference/encoder/ACK/own-cap/feature record,
  actual snapshot, complete native metric and numerical support report**.
- Independent extracted-wheel / `-I` / temporary-cwd public replay, **360 exact
  Python/JS assignment cases** and **seven resealed actual forgeries** pass:
  role relabel, credit window, role exclusions, replica seed, native promotion,
  numeric support count and actual actor feature. No new fit/capture is performed
  by proof; one temporary negative clone is retained at a time.
- Actual immutable pilot manifest:
  `da623dbebecdf05f315e17e7ae17b90cd10d9795eb41b25ab141d9ecde165539`.
- Concrete independent receipt:
  `results/jobs/native-action-balanced-hold-package-proof-v1.json`.
- Frozen plan: `configs/native_action_balanced_hold_pilot_v1.json`.
- Exact old candidate/failed validation/positive development/both training-source
  bytes are preserved. Old default weights/controller/model recipes do not change.

Read-only public command (do not overwrite or recollect):

```sh
.venv/bin/python -m media_rl.native_action_balanced_hold audit \
  --run results/native-action-balanced-hold-pilot-v1
```

## Future consumed-role registration: another discovered gap closed

The completed pilot's outer config contains a **singular `runtime`**; the frozen
V3 scanner understands flat records and plural `runtimes`, not this new wrapper.
A green nine-peer audit alone would therefore not prevent a future collector
from accidentally reusing the consumed BBB 100–120-second range. This structural
registration blind spot is detected before any subsequent collection.

Rather than mutate the completed scanner/study/plan/runtime or pretend it handled
this shape, `results/jobs/native_action_balanced_role_receipt.py` publishes
`configs/native_action_balanced_hold_pilot_v1_role_receipt.json`: a flat
**train-role consumed-source receipt bound to the actual da623d manifest, exact
original runtime/catalog/groups and fully replayed independent package proof**.
The immutable registry is checked numerically and its SHA becomes a future input.

One isolated test reproduces the missing range with the actual singular protocol,
then proves the exact flat receipt makes it visible in both a copied environment
and the real role registry. A direct actual probe verifies **59 current role
inputs** exclude locked validation and consumed training, choosing BBB
**120–140 seconds**, never 100–120, as the next free complete range. No labels,
model parameters, old bytes or original verdicts are changed. Keep this bound
registry in all future role exclusions; any newer wrapper also needs explicit
reservation-schema coverage, not just a green artifact manifest.

## Next boundary

The **new sampler and this actual pilot remove the local all-arm/transition
exposure blocker**, not the unresolved learned generalization failure. Do not
promote the unchanged failed candidate, cherry-pick pilot outcomes, alter old
credit/cutoffs, treat cap potentials as labels, count aliases as independent
physical groups, tune on locked validation or refit on one favorable source.

Any next model/data study must predeclare bounded **multiple genuinely new
training contexts** and a fixed neural-versus-matched-blind training recipe
before labels, preserving complete role reservations and weak/censored outcomes.
Only new prospective independent/final data—not reused failed V3 validation—can
subsequently establish generalization. Selected transient/all-request confidence,
a complete trained native actor, safe repeated causal quality/deadline gains,
representative/measured panels and real original learned-peer closed loops remain
open. **V7/defaults unchanged; native_deployment_qualified=false;
SOTA_achieved=false.**
