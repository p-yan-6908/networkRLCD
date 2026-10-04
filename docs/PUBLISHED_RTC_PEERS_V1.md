# Published RTC peers V1 — original models execute, comparison still blocked

## Outcome and scope

The original **Schaferct MMSys 2024 challenge winner** and the organizer's released
**offline-RL baseline** now run through an isolated, optional CPU ONNX interface.
Each executes all **2,074 observations** from one public emulated behavior trace:
**4,148 exact original-reference and read-only audit rows**, with actual label-poison
invariance and rejection of the native RLCD 64-input history. No training, policy
mapping, native cap, feedback feature, risk threshold or prior outcome is changed.

This removes the narrow **published-checkpoint/local-inference** blocker. It is
**not** a closed-loop comparison, counterfactual QoE estimate, independent efficacy
holdout, safety result, deployment certificate or current-SOTA ranking. The public
sample's model training/selection membership is unknown. Replaying another policy's
observations cannot reveal the traffic or video quality these estimators would cause.

## Genuine source pins

| Peer registration | Original commit | Original checkpoint | Size |
|---|---|---|---|
| `schaferct-mmsys2024` | `da49600ba1fb915181081cd8183c7cb13f278bc9` | `n13eho/Schaferct:onnx_model/Schaferct_model.onnx` | 4,639,039 bytes |
| `mmsys2024-baseline` | `fcf857c535b7e5da1bd910bfc889ed1ab58b772c` | `microsoft/RL4BandwidthEstimationChallenge:onnx_models/Offline_RL_baseline_bandwidth_estimator_model.onnx` | 151,491 bytes |

Checkpoint SHA-256s:

- Schaferct: `1638b64aae7e591db17eef793c071d04001b349f6f39697cf6b6f9e9642236a1`
- Organizer: `54e3113e1d0682a2aca5198e7d4f6053a239c45847e7029f48bdfb48c793a90f`

The original [winner repository](https://github.com/n13eho/Schaferct) identifies
itself as the challenge team's implementation and links its
[paper](https://dl.acm.org/doi/10.1145/3625468.3652183). The
[organizer's final results](https://www.microsoft.com/en-us/research/academic-program/bandwidth-estimation-challenge/results/)
identify Schaferct as winner and Fast and furious as runner-up. This is a historical
challenge outcome, not a claim about the strongest controller in 2026.

`results/jobs/rtc_peer_sources_fetch.py` fetches only nine pinned files, approximately
12.8 MB total: two checkpoints, reference scripts, README/license files and public
`data/02530.json`. It checks exact byte counts and original Git blob hashes before
saving them. `results/jobs/rtc-peer-source-inventory-v1.json` records SHA-256s and
immutable URLs. No downloaded Python or pickle is executed. Model bytes are verified
again **before** optional runtime import and are passed directly to ONNX Runtime,
not reopened by path after verification. Foreign checkpoints are not vendored into
the wheel. Keep original MIT copyright/license notices when redistributing them;
the challenge README separately discusses documentation/data terms, not an assumed
universal dataset license.

## Exact interface, no invented bridge or confidence

Public implementation: `src/media_rl/published_rtc_peer.py`.

- `PeerSpec`, immutable `PEERS`, `list_published_peers()`.
- `PublishedRtcPeer(peer, checkpoint)`, `act(observation)`, `reset()`.
- `inspect_published_peer()`, `replay_published_peer()`, `audit_published_peer_replay()`.
- Optional locked dependency: `calibrated-media-rl[rtc-peers]`, ONNX Runtime **1.23.2**.
- CPU only, sequential execution, one intra/inter-op thread.
- Original float32 inputs: `obs (1,1,150)`, `hidden_states (1,1)`, `cell_states (1,1)`.
- Original float32 graph outputs: `output (1,1,2)`, `state_out (1,1)`, `cell_out (1,1)`.
- Bandwidth is **`output[0,0,0]` in bps**, exactly as both original reference scripts
  select it. No headroom, clamp, sampling, risk gate or codec actuation is added.
- The second scalar is retained as `auxiliary_output`; it is **not interpreted as
  a calibrated risk probability**. Each peer owns zero-initialized, separately
  carried hidden/cell states; never share state across models or calls.
- Only the `observations` field is read for inference. Capacity, loss, quality and
  behavior-policy predictions are not inputs or claimed evaluation outcomes.
- Native 16-feature/64-history arrays, malformed shapes, strings/booleans, non-finite
  float32 inputs, invalid outputs and altered checkpoints fail closed.

Replay is bounded to a declared prefix (default 256, maximum 4,096 rows) and a 16 MiB
JSON source. It hashes the whole source and the actually used float32 observations,
records per-row predictions and host wall times, and refuses existing output files.
Audit re-executes every row with exact predictions and verifies identity, input/scope,
implementation, row ordering, runtime and latency-summary consistency without writing.
Exact audit requires the recorded runtime/host; cross-host equivalence is not certified.
Saved times cannot be proved historically true merely by replay, so audit explicitly
returns `timing_truth_verified: false`.

## Executed probe, not predictive accuracy or QoE

Frozen protocol: `configs/rtc_peer_probe_v1.json`.
Actual evidence: `results/jobs/rtc-peer-probe-evidence-v1.json`.
Predictions: `results/published-rtc-peer-probe-v1/{schaferct-mmsys2024,mmsys2024-baseline}.json`.

| Model | Exact reference/audit rows | Original-reference max difference | Host act median / p99 |
|---|---:|---:|---:|
| Schaferct | 2,074 | 0 | 0.1162 / 0.1371 ms |
| Organizer baseline | 2,074 | 0 | 0.0240 / 0.0274 ms |

Actual full-trace poisoned-label replays have identical prediction hashes. Both real
graphs reject native 64-input histories. All **nine** downloaded source files remain
byte-identical. These wall times exclude initialization, data loading, network, codec
and display, and do not certify the challenge's 5-ms Intel-hardware requirement.

The complete regression suite also passes: **661 Python / 117 native Node tests**,
with changed-file lint/format and locked optional-dependency checks. No deployment
or genuine closed-loop comparison follows from these implementation checks.

Forty-eight portable unit cases cover pins, ABI/CPU checks, state carry/isolation,
label/future-prefix exclusion, malformed data, no overwrite, saved-evidence forgeries
and all CLI registrations. Ninety-seven adjacent native presentation/action-live/guard
regressions pass. `results/jobs/rtc_peer_package_probe.py` checks the built wheel outside
the checkout, optional-free listing, both real models, full replay/audit and rejection
of corrupt checkpoints. Its receipt is `results/jobs/rtc-peer-package-proof-v1.json`.

## Reproduce safely with fresh outputs

```sh
# Listing requires core project dependencies but not ONNX Runtime.
uv run --locked media-rl rtc-peer-list
# Bounded download of pinned artifacts only; no foreign code execution.
uv run --locked python results/jobs/rtc_peer_sources_fetch.py

CACHE=.tools/rtc_peer_research_v2/artifacts
uv run --locked --extra rtc-peers media-rl rtc-peer-inspect \
  --peer schaferct-mmsys2024 --checkpoint "$CACHE/schaferct.onnx"
uv run --locked --extra rtc-peers media-rl rtc-peer-replay \
  --peer schaferct-mmsys2024 --checkpoint "$CACHE/schaferct.onnx" \
  --trace "$CACHE/02530.json" --limit 2074 \
  --out results/published-rtc-peer-reproduction/schaferct.json
uv run --locked --extra rtc-peers media-rl rtc-peer-audit \
  --replay results/published-rtc-peer-reproduction/schaferct.json \
  --checkpoint "$CACHE/schaferct.onnx" --trace "$CACHE/02530.json"
```

Use `mmsys2024-baseline` with `challenge-baseline.onnx` and a separate output to replay
the organizer model. The canonical completed probe refuses reuse/overwrites. CLI
reproduction does not train or select any model.

## Research implications and next blocking interfaces

- [Song and Meo, CNSM 2025](https://dl.ifip.org/db/conf/cnsm/cnsm2025/1571172286.pdf)
  challenge the necessity of reward-based BWE with an offline/online-trained regressor,
  compared to ReCoCo, Schaferct, FARC and Pioneer in AlphaRTC emulation. This motivates
  a **strong supervised BWE baseline**, not an assumption that RL is superior. Known
  capacity can be used for explicitly separated controlled training; it must not
  enter the deployed actor or independent final selection. Paper rate/delay/loss QoE
  scores are not comparable to RLCD's request-to-readback/PSNR utility. No original
  regressor checkpoint/code was located in the bounded primary-source inspection;
  that is an availability uncertainty, not proof no artifact exists.
- [Vidaptive's author page](https://people.csail.mit.edu/pkarimib/research/)
  links the [original WebRTC fork](https://github.com/pkarimib/src). Its main commit
  `5c5805c39aeb6bfb9ce4d5eebfe26046968554e6` and build README were inspected, not built.
  A modified pacing/encoder implementation is not faithfully reproduced by a browser
  scalar `maxBitrate` cap. Do not label such a proxy as original Vidaptive.
- **Observation blocker:** the challenge's receiver-side 150-feature vector is not
  RLCD's sender-side 16×4 history. A causally verified extractor with original units,
  ordering, window/clock/loss semantics and authoritative fixtures is required. Do
  not pad native inputs with zeros or copy capacity/quality/evaluation labels.
- **Actuator blocker:** original receiver bandwidth feedback/encoder integration is
  not established by replay. Applying predicted bps as a cap above Chrome's independent
  GCC would be an adapted/hybrid controller, not automatically the original published
  controller. Declare and validate the exact transport/codec mapping for all peers.
- After these interfaces are independently verified, freeze common content/link
  workloads, equal warmup/compute, repeatability and role-disjoint validation/final
  panels. Include strongest compatible peers and regression/risk-matched baselines;
  preserve negative results and no-risk/quality-harm gates. No oracle fitting, hidden
  retuning, privileged networking installation, paid job or upload is authorized here.

RLCD's unstable deadlines, selected calibration, generalization and decisive genuine
competitor superiority remain open. The active SOTA objective is **not complete**.
