# Native encoder response sidecar V1 — actual availability, not lag/quality proof

## Blocker removed and limits

The [compact hold-model investigation](NATIVE_ACTION_COMPACT_HOLD_CV_V1.md) showed
that no encoder target/QP counters existed in the previous frozen sender ABI.
Higher `bytesSent` after a configured cap was therefore not evidence of the
encoder's actual instantaneous target or its response horizon. That information
gap is now addressed by a **separate identified native encoder-stat sidecar**.
It never augments the 16 sender features, 23-step causal state, trained models,
risk calibration, controller inputs, ACK-age semantics or native defaults.

[W3C statistics](https://www.w3.org/TR/webrtc-stats/) distinguish encoder target
settings from payload sent and specify codec-dependent QP semantics. Optional
stats and historical `totalEncodedBytesTarget` are **measured for availability**,
not assumed supported. QP is not PSNR or a new controller reward; aggregate
stats do not identify frame-specific causal encoding changes.

## Implementation and exact boundaries

- `benchmarks/native_rtc/encoder_response.mjs`: `captureEncoderResponse` matches
  the **same unique outbound id/SSRC and VP8 codec** selected by the original
  observation encoder. It preserves target bitrate, QP/frame/keyframe/payload/
  retransmission/header-byte/encoding-time/legacy-target-byte/resolution counters
  and quality-limitation reason with **present / absent / invalid** status.
  Missing or invalid values are null, not synthetic zeros; observed zero stays zero.
- Raw RTCStats timestamp, original monotonic sample timestamp, time origin and
  capture cost are recorded separately. No RTCStats/performance clock equality
  or exact encoded-frame-to-source-frame causal attribution is assumed.
- `benchmarks/native_rtc/encoder_response_episode.mjs` is an **exact four-anchor
  auxiliary-only projection** of the frozen excitation collector: import,
  sidecar capture, auxiliary decision property, HTTP route. All existing native
  source/relay/packet/RGB/quality/frame/deadline/actuation/shadow-inference code
  is unchanged. In particular the original policy input construction is identical.
- `src/media_rl/native_encoder_response.py` validates the exact schema, clocks,
  same-snapshot original sender counters and source identity. Interval accounting
  excludes changed streams, missing/reset mandatory counters, stale stats,
  invalid poll intervals and cap crossings. Zero-frame QP is undefined, not zero.
  Optional missing/reset/impossible retransmission counters make the corresponding
  non-retransmitted payload rate **null**, without discarding valid QP samples.
- `audit_encoder_probe` first runs the **entire original native raw verifier**,
  preserving its exact code object and scientific checks, then recomputes every
  sidecar support count and interval. Runtime, source hashes, actual producer
  snapshot, movie/model/trial identity and saved reports are checked. The outer
  sidecar manifest is a new ABI, never the original collection's qualification.

## Actual bounded Chrome/VP8 probe

One **fixed450 conventional explore peer**, no learned executed control and no
refits, reuses the original Sintel stable-0 **training reservation** and 18-second
three-phase schedule. `results/native-encoder-availability-v1/probe.json` freezes
the trial/source/auditor/sidecar/collector hashes before collection. This is not
new role independence or a representative video/network test.

The actual complete native raw replay passes. Chrome supplied **all twelve
fields on all 169 samples**, including target bitrate and QP, and produced **167
valid same-cap intervals**. One initial 300→450 cap crossing was excluded.

- Reported encoder target: **232,500–450,000 bps** despite the fixed 450,000-bps
  applied cap after initial startup. Configured/readback maxBitrate is **not the
  actual target measurement**.
- Interval mean VP8 QP: **38.25–106.0** (codec-specific).
- Short-interval sent payload: **0.1769–1.0749 Mbps**. This is buffered/packetized
  payload over ~100-ms sample intervals, not a strict per-interval cap violation
  or an encoding-target guarantee.
- `totalEncodedBytesTarget` happened to be present in this browser build; no
  future implementation or spec support is inferred from that fact.

**Availability is established on this owned conventional peer. Response lag,
frame-specific encoder effects, causal quality gain and learned action value
are NOT established.** Earlier −3.3981%/+0.0615% action-skill failures remain
untouched, as do old models/captures/selected calibration/defaults and the SOTA flag.

## Verification

- **19 Python tests + four Node tests**: unique selected stream/VP8, valid zero,
  unsupported versus invalid fields, bool/negative/noninteger rejection,
  exact sample/source/counter/role boundary, fail-closed projection, unchanged
  actor feature ABI, true delta units, reset/stale/cap-change rejection, undefined
  zero-frame QP and nullable optional retransmissions.
- Actual full native raw and sidecar replay from a **separate extracted wheel,
  `-I`, temporary cwd**, with exact imported source hashes.
- **Six resealed forgeries rejected**: numeric report, absent target padded to
  zero, sample clock, same-source counter, controller-use flag and actual actor
  feature. No peer was recollected or model refitted for these tests.
- Original seven source hashes, original V2 weights/failed qualification and
  compact-development manifest remain unchanged.
- Evidence: `results/native-encoder-availability-v1/report.json` and
  `results/jobs/native-encoder-availability-package-proof-v1.json`.

```sh
# Read-only public packaged audit; no collection/refit:
.venv/bin/python -m media_rl.native_encoder_response audit \
  --run results/native-encoder-availability-v1
# The completed runner is reference only; immutable output must not be rerun:
# .venv/bin/python results/jobs/native_encoder_availability_probe.py
```

## Longer-hold mechanism test completed — prospective credit repair next

The [preregistered four-peer longer-hold experiment](NATIVE_ENCODER_LONG_HOLD_V1.md) now records **679 samples / 1,494 factual band requests**. Ten of fourteen target increases cross the declared threshold after **1.16–1.60 s** (four censored), versus all ten decreases after **101–112 ms**. Both prescribed aliases show later QP response, while quality variability/confounding remain. The old 200–600-ms credit and ~800-ms holds are often too early/short for increases; no old labels or model are changed. Full native/extracted-wheel replay and seven resealed-forgery rejections pass. Next is a separately versioned prospective longer-hold/credit contract, with both films/multiple contexts and all censored outcomes retained.

### Original rationale and still-required causal boundaries

Availability permits a separately preregistered, bounded **conventional
cap-response/lag** protocol with longer safe holds and repeated identical-policy
controls. Preserve the existing 300/450/900 support, original application
request/deadline/quality cutoffs and old fixed 200–600-ms credit window as a
reported reference. Bind target/QP/frame deltas to control ACK and source clocks;
predeclare lag bands and capture limits, report every failed/missing/crossed
interval, and distinguish target changes from QP/packet-buffering changes. Use
multiple transitions in both directions and retain source identity, codec,
content and resolution context. Do not fit a model, choose a reward horizon from
held-out labels or augment the existing feature ABI merely because a support
counter is green. Only measured, repeatable context-sensitive response can
justify a new causal feature/credit contract. **Selected-native calibration,
safe native improvements, role-disjoint tests, genuine learned-peer comparison
and SOTA remain open.**
