# Native encoder longer-hold response V1 — timing blocker, not policy qualification

## Fixed prospective contract

The [encoder sidecar](NATIVE_ENCODER_RESPONSE_V1.md) established actual target/QP
availability, not a correct reward horizon. This experiment tests the remaining
mechanism **before fitting more forecasters**. The new config was serialized
before any collection; its hash exactly matches the captured protocol and its
mtime precedes the first actual native start by ~27 seconds. No old producer,
source, captures, actor/state ABI, model, risk calibration or default changes.

- `configs/native_encoder_long_hold_response_v1.json`: four conventional native
  peers, interleaved **fixed450 / prescribed-a / fixed450 / prescribed-b**.
  Both prescribed aliases execute the same cap sequence, independent of any
  observation, oracle or learned prediction.
- **16 polling steps per held cap** (nominal ≥1.6 s); legal support remains
  **300/450/900 kbps**. Fixed sequence starts 450→300→900→300→900→450→300→900→300
  →450→900→450. The final partial epochs and all censored/missing/drop outcomes
  are kept, never silently recollected or excluded from reporting.
- One original Sintel **stable-0 training crop**, same scene/18-second schedule
  and nonbinding nominal bottleneck capacity. This is controlled training
  mechanism development, **not both-film/domain/role-disjoint validation**.
- Predeclared ACK-relative bands **200–600 ms** (original reference),
  **600–1000 ms**, **1000–1400 ms**; original **150-ms application deadline**,
  original on-time sampled-PSNR contribution and missed/zero outcomes unchanged.
  Every last request deadline must precede the next action observation/cutoff.
- Target crossing uses the **predeclared directional 10% tolerance**:
  increases ≥90% of assigned cap, decreases ≤110%. Already-met pre-ACK values
  are separate, never a zero response time; missing crossings are censored.
  Results are **sample-quantized target crossings**, not exact encoder latency,
  proof of target equality, per-frame causation or stable settled quality.

## Implementation and full verification boundary

`benchmarks/native_rtc/encoder_hold_control.mjs` exposes `holdProbeCap`;
`benchmarks/native_rtc/encoder_long_hold_episode.mjs` is an exact three-anchor
projection of the unchanged telemetry collector: conventional control import,
explicit cap selector and HTTP route. **Original policy input is identical.**

`src/media_rl/native_encoder_long_hold.py` exposes plan/run/audit plus factual
band and target-response reconstruction. The raw audit retains the **exact
original native verifier code object**, rebinding only the declared conventional
control and measurement recipe. All original packet/service conservation,
movie/source/frame/RGB/deadline/ACK/readback/shadow-model checks still execute.
Encoder support/identity/clocks/counter reset/stale/cap-crossing rules are reused
from the frozen sidecar. QP is frame-weighted over whole same-cap intervals
contained in a band; zero frames or no eligible counters remain null, not zero.
Quality uses **all attributable original requests**, including misses and zero
utility; inflight exclusions and bands with future deadlines/cutoffs are explicit.
Raw outputs/logs and failure receipts are retained if a peer or audit fails.

## Actual result: upward response is much later than the old credit band

**Four native peers / 679 sender samples / 1,494 factual band requests** pass
full original raw and public numerical reconstruction. There are **eight
explicit dropped band records**, primarily final future-deadline/cutoff cases.
Both prescribed aliases complete ten full epochs and retain the eleventh partial
one. No models are fitted; no learned control executes.

| Sampled directional crossing | Events | Observed | Censored | Observed range | Median |
|---|---:|---:|---:|---:|---:|
| Increase, aggregate | 14 | 10 | 4 | **1,162.8–1,602.9 ms** | 1,377.1 ms |
| Decrease, aggregate | 10 | 10 | 0 | **100.9–112.4 ms** | 101.9 ms |
| 300→900 kbps specifically | 6 | 4 | 2 | 1,171.4–1,387.6 ms | 1,283.0 ms |
| 300→450 (including startup) | 6 | 6 | 0 | 1,162.8–1,602.9 ms | 1,546.4 ms |
| 450→900, final partial epochs | 2 | 0 | 2 | undefined | undefined |

Thus **old 200–600-ms factual credit often occurs before the upward encoder
target response**, even under a stable nonbinding path. The old eight-step
(~800-ms) cap holds were often too short to observe it before the next action.
Downward targets cross much earlier. This is a measured **asymmetric
actuation/credit mismatch**, not proof that every upward target settles by
1.6 s: two full 300→900 epochs remain censored, and partial epochs are separate.

Repeated prescribed peers show the same direction of encoder-QP evolution:

| Assigned cap / peer | QP 200–600 ms | QP 600–1000 ms | QP 1000–1400 ms |
|---|---:|---:|---:|
| 900 kbps / prescribed-a | 60.08 | 41.28 | 31.70 |
| 900 kbps / prescribed-b | 61.36 | 41.16 | 36.92 |
| 300 kbps / prescribed-a | 73.55 | 83.92 | 92.47 |
| 300 kbps / prescribed-b | 74.74 | 85.35 | 92.59 |
| 450 kbps / fixed control 0 | 86.39 | 82.86 | 84.95 |
| 450 kbps / fixed control 2 | 86.77 | 83.99 | 85.47 |

QP is VP8-specific and is **not quality utility**. Late 900-kbps quality is
also not perfectly repeatable: its 1000–1400-ms utility is 0.32259 / 0.35018,
miss fraction 8.33% / 0%; the two fixed controls' corresponding utility is
0.31319 / 0.30975. Same-policy quality variance and deterministic content/order
confounding remain. These are **not paired counterfactual quality estimates**,
not a causal quality-gain gate and not reliable learned action value. No
post-hoc reward horizon is promoted and the original reference remains intact.

## Evidence and public commands

- **16 Python + two Node tests**: legal non-oracle prescribed aliases and exact
  boundaries, original raw audit code identity, unchanged actor-input projection,
  all factual missed/zero outcomes, ACK/whole-counter/window attribution,
  duplicate/cap/decision/utility failures, future-action/inflight exclusion,
  zero-frame null QP and censored/pre-ACK target thresholds.
- Public read-only audit recomputes **all four actual peers**, every target/QP/
  utility/miss/source/request-band/clock/drop record and aggregate report.
- Separate **extracted-wheel / `-I` / temporary-cwd** replay passes with exact
  implementation/source hashes and **seven resealed forgeries rejected**:
  utility, last deadline, absent target padded to zero, sample clock, actual actor
  feature, hold geometry and omitted/replaced drop records.
- Old seven source hashes, V2 weights/failed qualification, original availability
  and negative compact-development manifests remain unchanged.
- Real artifacts: `results/native-encoder-long-hold-response-v1/report.json`,
  per-peer `response.json`/`native_derived.json`, and
  `results/jobs/native-encoder-long-hold-package-proof-v1.json`.

```sh
# Read-only; no collection/refit:
.venv/bin/python -m media_rl.native_encoder_long_hold audit \
  --run results/native-encoder-long-hold-response-v1
# Completed immutable plan/run reference; do not overwrite/recollect it:
# .venv/bin/python -m media_rl.native_encoder_long_hold plan \
#   --base-runtime results/native-action-excitation-train-sintel-v1/runtime.json \
#   --out configs/native_encoder_long_hold_response_v1.json
# .venv/bin/python -m media_rl.native_encoder_long_hold run \
#   --config configs/native_encoder_long_hold_response_v1.json \
#   --out results/native-encoder-long-hold-response-v1
```

## Next repair boundary

The measured upward target/QP response justifies a **separately versioned
longer-hold/credit contract** for prospective training, not hidden edits to old
labels. Predeclare longer holds and later bands using this training mechanism
result, retain 200–600 ms as reference and all censored/failed/zero outcomes, and
repeat across **both films and collapse/recovery contexts** before claiming a
universal response horizon. Longer waiting alone is not proof of settled target
or stable quality. Any encoder-feature addition must be a new causal ABI, never
stuffed into old weights; chosen-state future RGB/quality/oracle fields remain
forbidden. Recheck action-conditioned-versus-blind learning on new grouped data
before selected-native calibration or a candidate comparison. **Action value,
selected-native confidence calibration, safe repeated native gain, independent
held-out/final evidence, genuine learned peers and SOTA remain unachieved.**

## Subsequent prospective repair (new version, old artifacts intact)

The [V2 combined hold/credit repair](NATIVE_ACTION_LATE_CREDIT_V2.md) now
completes both original 24-peer training-film panels with 32-step random holds,
fixed 1800–2200-ms credit and same-capture 200–600-ms reference. All 160 late
cohorts / 1,944 requests, including 42 partial/below-target cohorts, remain.
The unchanged compact neural recipe passes the fixed 1% conditional-versus-blind
**development** test on the exact original physical folds (+1.4258% / +6.8950%).
This is a new necessary learning result, not universal settlement, independent
validation, selected-native transient confidence, causal quality or SOTA.
This timing probe and all earlier negative/model/default bytes remain unchanged;
see the V2 actual full-native/extracted-wheel/model/tamper proof for its scope.
