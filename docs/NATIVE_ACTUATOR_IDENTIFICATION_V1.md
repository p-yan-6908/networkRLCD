# Native causal actuator identification V1

**Diagnostic only. Architecture frozen; no controller trained, selected or promoted.**
The supervised JevBWE baseline, numeric RLCD policy, optional Laya adapter, six
controller actions, safety weights, 1.8 s dwell and promotion gates are untouched.
Do not run Laya or change policy architecture to compensate for weak actuation.

The powered follow-up is a separate workflow: [powered content/regime panel](NATIVE_ACTUATOR_POWERED_PANEL_V1.md). The original smoke and its architecture remain unchanged.

## Experiment

`media-actuator` is a separate CLI (`native_actuator_study.py`). Its collector is
an exact checked projection of the unchanged native encoder-response collector.
All common legacy inference remains **shadow-only**, never the physical actor.

For each assigned cohort it records `(s, Z, A, Y, mu)`:

- `Z`: pseudorandom IID arm from **{0.65, 0.85, 1.05} × BWE**, rejection-sampled
  SHA-256 counter draws, independently replayable seed, `mu = 1/3` for every arm.
  Unlike arm permutations, repeated arms are allowed and no history-dependent
  structural zeros are introduced. Seeds are audit metadata, not model inputs.
- BWE is the **observed native sender estimate at assignment**, frozen for the
  entire **3,000 ms ACK-relative hold**. Do not continuously recompute its cap.
  Missing BWE causes no assignment; it is not guessed. Native scalar caps remain
  150–4,000 kbps; candidate aliasing is recorded, never silently filtered.
- `s`: BWE, RTT, signed RTT change, loss, jitter, previous requested bitrate,
  encoder target, actual encoded/send interval rates, QP, encoded frame size,
  causal RGB gradient/motion complexity and previous arm. Unsupported fields
  are explicitly absent/invalid, never treated as measured zero.
- `A`: **actual encoded video payload output before RTP packetization**, measured
  using an identity `createEncodedStreams()` transform on the owned sender.
  The same frame and data pass through unmodified. Missing API/pipeline failure
  stops capture; targetBitrate/totalEncodedBytesTarget/RTP bytes are NOT substitutes.
  RTP payload send rate (including retransmissions) and encoder target are separate.
  RTP rate uses cumulative native counters with proportional interval-boundary
  allocation; it is an approximation, not an exact packet-timestamp wire meter.
- `Y`: future delivered on-time sampled RGB-PSNR contribution per **all eligible
  source opportunities**, including lost/late requests as zero contributions.
  This is the existing research QoE proxy, not human QoE or physical scan-out.

The fixed post-wash-in window is **ACK+1,800 through ACK+2,600 ms**, with the
unchanged 150 ms delivery deadline. This is not a guarantee of encoder settling.
Four 200 ms output bins report a descriptive plateau check. **Non-plateau and
zero-output responses remain included.** Do not condition causal eligibility on
reaching the target, observed bitrate or QoE. Clock/ACK/counter-coverage failures
are retained as censored assigned rows with a reason; no negative labels or
unobserved counterfactual outcomes are manufactured.

Fresh licensed 20-second content reservations are disjoint across **discovery**
and **replication** and all scanned earlier native roles. One physical content
context is one inference cluster, not each frame/epoch. Three 6/6/6.6-second
network phases provide six holds plus a deadline drain. Stable/collapse contexts
are prospectively alternated. Loopback userspace relay and VP8 geometry remain
unchanged; these are not real Internet-path or representative-corpus trials.

## Qualification stages

1. **Requested arm → actual encoder AND RTP send rates.** Per-arm distributions,
   block/pretreatment-adjusted adjacent contrasts, `ΔA/ΔZ`, CR1 clustered CIs,
   joint first-stage F and partial R². Both roles must pass separately. Fixed
   thresholds: ≥8 physical blocks/role, ≥12 complete observations/arm/role,
   ≥95% complete, ≤10% cap aliasing, F≥10, partial R²≥0.05, and each adjacent
   normalized-rate CI lower bound >0.03. Rate contrasts use Bonferroni correction
   across two roles × three pairs × two rate endpoints.
2. **Actuator → delivered outcome.** Only tested after Stage 1 replicates. Report
   randomized assigned-arm ITT effects, plus explicitly assumption-conditional
   scalar-rate 2SLS and **full-real-line Anderson–Rubin confidence sets**, including
   disconnected/unbounded sets. Weak instruments never get a misleading finite
   delta-method Wald interval. Inference uses approximate CR1 small-sample t/F,
   not exact randomization tests. State adjustment uses preassignment covariates
   with explicit missingness; it is not a fitted controller.
3. **State × action preference:** deferred; **no ML fitted**. No policy promotion
   can be earned by this diagnostic, even if both stages pass.

Randomization identifies `Z→A` and `Z→Y`, NOT automatically a scalar `A→Y` effect.
Exclusion/mediation, a well-defined bitrate treatment, washout/history and effect
assumptions must also hold. QP/frame timing can violate scalar-rate exclusion.
The presets explicitly set `iv_assumptions_explicitly_assumed=false`; declaring
assumptions does not empirically verify them. No "bitrate is correct" categorical
truth is implied: distinguish `pi(a|s)`, utility `Q(s,a)`, and `P(safe|s,a)`.

## Commands and artifacts

Requires Node/Chrome, a compatible sealed no-actor native template, and locally
licensed hashed movie catalogs. Paths in presets refer to existing local assets;
this is not a movie downloader or automatic training workflow.

```sh
uv run --frozen media-actuator plan \
  --config configs/native_actuator_identification_smoke_v1.json \
  --out results/my-actuator-plan
uv run --frozen media-actuator run \
  --protocol results/my-actuator-plan/protocol.json --out results/my-actuator
uv run --frozen media-actuator audit --root results/my-actuator
```

`configs/native_actuator_identification_v1.json` prescribes a larger single-film
8-block/role panel (not representative). Check available **fresh** source clips
first; the local corpus is heavily reserved. Add a licensed catalog rather than
relabel old validation clips or alter source hashes to disguise reuse. The
planner fails closed on exhaustion. Even unused failed-plan leases remain
excluded; reclamation needs a separate explicit review, not silent reuse.

Plans are sealed before collection; captures never overwrite an existing path.
Failures retain a prefix and collector stderr. Successful parent/child manifests
bind all raw files. Read-only audit repeats original UDP wire, source ownership,
frame identities, causal observations, common-model shadow outputs, cap readback,
encoder sidecars, instrument assignments, encoded-byte prefixes, QoE and report.

## Verified native smoke (not a powered causal result)

`results/native-actuator-identification-smoke-v3`:

- Four real Chrome/loopback peers, two fresh films and independent roles.
- **2,009 actual encoded-frame events; 24 assigned/complete factual cohorts**.
- Requested 255–2,852.895 kbps versus actual encoded output 214.93–1,745.19 kbps.
  These pooled ranges are descriptive, **not** a causal contrast or evidence of
  collapsed action classes; BWE/content differ between cohorts.
- **13/24 non-plateau windows**, all retained. A three-second hold alone does not
  establish settled actual bitrate, and this smoke does not estimate a settling
  time. Plan a separate longer-hold timing diagnostic if non-plateau persists.
- Preassignment support: BWE/target/previous request 24/24; RTT/trend/loss/jitter/
  actual encoded/send rate 20/24; QP/frame size 19/24. Missing values stay missing.
- Stage 1 **not qualified**: only **2 blocks per role**, insufficient support.
  This is not a statistically established negative actuator-effect result.
  Stage 2 is deferred, Stage 3 not fitted, no controller promoted.
- Independent registered audit passed full original native raw replay and exact
  factual cohort/report reconstruction. Failed earlier plan/capture prefixes are
  preserved; the video adapter failure was fixed in a separate diagnostic wrapper.

Focused preservation regressions: 137 passing checks before two additional
sensor-integrity probes; final focused actuator suite: 19 passing checks.
Lint, registered CLI and wheel build passed. All legacy controller/model bytes
and old native collectors remain unchanged by this study.
