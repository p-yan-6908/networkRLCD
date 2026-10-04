# Native causal rollout prototype V1 — not a trained RLCD or SOTA result

## Why this comes before native training

The simulator's 42-action checkpoint cannot be treated as a native controller. This prototype defines **actual observables, action acknowledgements, label clocks and a timing/quality proxy** before fitting a fresh policy. It remains owned same-host userspace UDP relay, generated canvas/VP8, native transport-cc/GCC; no kernel netem, real camera, representative content or published learned-peer panel. No RLCD model is loaded or promoted.

## Versioned inputs and actions

- Observation ABI **`native_sender_stats_v1`**, **16** features, recorded scales/clipping, history **4→64** model inputs. Public Node exports: `FEATURE_NAMES`, `OBSERVATION_PROTOCOL`, `selectSenderSource`, `SenderObservationEncoder`, `validateNativeObservationManifest` in `benchmarks/native_rtc/sender_observation.mjs`. Equal width does **not** imply old feature meaning: ABI, ordered names, history and input dimensions must match; old manifests reject.
- Features: native BWE; **linked remote-inbound-rtp media RTT**, observed-counter age; own RTP-payload send rate; encoder FPS/encode time; own packet-send delay; applied encoder cap; applied zero-target flag; BWE/RTT/age/byte/encode/packet validity masks; actual sampling interval. Normalizers/limits are pinned in `OBSERVATION_PROTOCOL` and independently in `src/media_rl/native_observations.py`.
- Media RTT is **not candidate-pair STUN ping RTT**. First cached RTT has unknown age until a measurement-counter advance is observed; query timestamps do not refresh it. Reported age is time since **observing** that advance, not exact RTCP arrival age. Stream/counter resets, absent counters, zero/long intervals and missing fields are explicitly masked; nonfinite or extra raw fields reject.
- No true bottleneck capacity, proxy queue, scenario/phase, future network trace, receiver pixels/deadline labels or absolute episode clock is a policy feature. The policy call receives only `{observation_abi,feature_names,features}`. Absolute times and receiver/proxy diagnostics are offline audit/evaluation metadata.
- Action ABI **`native_encoder_cap_playout_v1`** retains 14 native cap/receiver-target combinations. These runs fix verified receiver target **0** and use the seven supported encoder caps. GCC remains the lower-layer congestion controller; cap is not wire-rate actuation. Every changed command verifies the native sender and inherited receiver property readback.
- A source request logs the last **already acknowledged** decision, current cap/target and action-transition-in-flight flag. The verifier checks `ack≤capture<next_ack`; transition or unassociated requests must not be assigned clean factual action labels for training. This is command-acknowledgement attribution, **not proof of the exact native capture instant or encoder-internal switch time**.

## Quality and timing labels

The actual received source ID is independently decoded from raw 16-ID-bit + CRC-8 pixel luminances. A deterministic reference of that source ID is reconstructed in the same browser renderer. Paired decoded/reference RGB samples use a fixed 16-pixel grid (2,400 RGB channels/frame), excluding marker rows and alpha; raw arrays are saved, not just an opaque quality score. Python independently recomputes MSE/PSNR and rejects forged/NaN values, geometry changes and sample corruption.

The predeclared timing endpoint remains **150 ms request→video-pixel readback**, not native physical capture/scan-out. It includes application measurement overhead. Quality computation occurs on the same copied video canvas after the marker readback; its overhead can affect later frames. New sender/full-image instrumentation is identical across the two new runs but differs from the lighter older `native-rtc-frame-*` probes, so do **not** pool them as paired repeats.

The research utility is **mean on-time sampled RGB PSNR dB per eligible source request**: late/missing/unidentified opportunities contribute **0**, duplicate readbacks cannot inflate it, complete deadlines exclude all terminal-censored requests irrespective of observed outcome, and exact matches are explicit with a **100 dB** utility cap instead of JSON Infinity. This is a synthetic timing/quality research proxy, **not VMAF, human QoE or evidence of real-content perceptual quality**. Raw labels never enter the sender observation vector.

## Fresh development diagnostics: inspect the harms too

Both rows are independent single browser executions; no paired statistical effect, confidence interval, trained policy, held-out native promotion or SOTA statement.

| Conventional control | Eligible | On time | Paired pixel samples | Sender decisions / cap changes | Overall utility |
|---|---:|---:|---:|---:|---:|
| Fixed 4 Mbps cap, zero target | 361 | 111 | 178 | 116 / 0 | 10.1047 |
| 85% native-BWE cap headroom, zero target | 360 | 208 | 213 | 116 / 4 | 15.6211 |

The BWE rule consumes **only normalized causal sender features**, maps 85% of native BWE down to a supported cap, and holds its applied cap when BWE is missing. It does not query true capacity. It is a stronger conventional comparator, not RLCD.

| Source phase | Fixed on time / eligible | BWE on time / eligible | Fixed utility | BWE utility |
|---|---:|---:|---:|---:|
| High | 111 / 121 | 73 / 122 | 30.1470 | 16.9261 |
| Collapse | 0 / 122 | 50 / 121 | 0 | 11.1182 |
| Recovery | 0 / 117 | 85 / 117 | 0 | 18.9172 |

**Nominal harm:** conditional on-time sampled PSNR falls **32.863→28.287 dB** in the high phase; its on-time count also falls. BWE's collapse/recovery gains do not establish acceptable quality/risk tradeoffs or promotion. One additional complete pre-phase source request in the fixed run contributes zero to the overall denominator. Training should explicitly seek recovery of nominal quality while reacting faster to actual congestion feedback—not overfit the single collapse schedule or choose a winning aggregate from these development captures.

## Commands and immutable evidence

```sh
# Already completed: replace output paths with fresh results/ children for reruns.
node .tools/native_rtc_rollout_probe.mjs results/native-rollout-v1-fixed min-jitter fixed
node .tools/native_rtc_rollout_probe.mjs results/native-rollout-v1-bwe min-jitter bwe
uv run --frozen .tools/audit_native_rollout.py results/native-rollout-v1-fixed
uv run --frozen .tools/audit_native_rollout.py results/native-rollout-v1-bwe
uv run --frozen .tools/probe_native_rollout_guards.py
node --test benchmarks/native_rtc/*.test.mjs
uv run --frozen pytest -q
```

Each completed run seals **18 artifacts**: raw packet/frames/sender records, frame/quality/replay summaries, all five browser helper modules, driver snapshot, Python metric/replay sources and both verifier snapshots. `audit_native_rollout_wire.py` independently replays FIFO/admission/remaining-wire budgets/propagation; unlike the original packet-only diagnostic, it does **not** require a controller to worsen RTT/BWE or produce drops. Rollout audit also verifies raw CRC identity, all source opportunities/censoring, independent input/decision replay, actual native action fields, and capture-to-ack association. A cryptographic manifest alone is not enough: seven in-memory corruptions of features, oracle fields, freshness, proposals, readbacks and raw pixel math reject without touching canonical inputs.

Receipts: `results/jobs/native-rollout-v1-{fixed,bwe}-evidence-check.json`, `native-rollout-guard-evidence-check.json`; tests **192 Python + 42 Node**, including unit/anti-forgery checks and actual two-run replay. The formal nine policy-study exports, original native appendix inputs and V7 selection are unchanged. `paper/build/main.pdf` is verified **35 pages** with its separate earlier native diagnostic appendix; the existing nonfatal bibliography/rerun warning remains.

## Next defensible learning step

Predeclare a separate exploratory training panel with enough action/history coverage and independent trace/content variation. Train a **fresh native** model using versioned inputs and factual, outcome-complete labels (transition/unknown assignments excluded); do not transfer legacy weights or fit to receiver/proxy oracle fields. Freeze validation/quality-risk gates before a fresh test panel, include this BWE control and other strong conventional controls, and run published learned peers on a common observable/actuation surface. Natural-content perceptual metrics, cross-platform clocks/measurement validation, paired multi-seed uncertainty and risk/quality-matched comparisons remain necessary. These two runs are **development diagnostics**, never the final promotion test.
