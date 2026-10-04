# Native RTC baseline foundation — smoke only

## Why this matters

SOTA requires genuine transport/media/competitor evidence, not the simplified `gcc` controller. An approved Linux/Docker host is needed for original AlphaRTC/BoB runners, but the installed local Chrome can already provide **actual WebRTC codec/transport feedback** without privileged installation.

## Verified local smoke

```sh
node .tools/native_rtc_smoke.mjs
# Uses a fresh immutable results/native-rtc-smoke directory; change the root for a new run.
```

The helper creates an owned headless Chrome instance with an isolated temporary profile, localhost-only HTTP/CDP and two native RTCPeerConnections, generated canvas video, VP8 preference and **transport-cc negotiation**. It never opens the user's browser profile or uses camera/microphone sources. Three `RTCRtpSender.setParameters` encoder caps (1.0/2.5/0.3 Mbps) exercise actual encoder adaptation. Both peers/stream/browser/server/profile are closed/removed afterward.

Observed reduced user agent: **HeadlessChrome/154.0.0.0**. This is an installed-browser observation, **not proof of exact build, latest release or a named internal GCC variant**; the subsequent instrumented relay run pins **Chrome/154.0.8037.58**, CDP **1.3** and a frozen helper snapshot. Do not retroactively infer a full build from the original reduced UA.

| Encoder cap | Received media Mbps | Cumulative decoded frames | Native BWE Mbps | Candidate-pair RTT |
|---|---:|---:|---:|---:|
| 1.0 Mbps | 0.9723 | 61 | 2.1496 | 1 ms |
| 2.5 Mbps | 1.7893 | 145 | 5.1860 | 1 ms |
| 0.3 Mbps | 0.3200 | 229 | 5.1860 | 1 ms |

All three intervals use **video/VP8**, zero reported loss and zero reported freezes; sender/receiver byte deltas agree. Mean aggregate encode time is roughly 3.5–4.0 ms/frame. These are **loss-free local-loopback synthetic-content** observations, not deadlines, perceptual QoE or representative network performance. Encoder maxBitrate is not a strict instantaneous wire-rate/FEC envelope (the final received rate exceeds the cap slightly).

Evidence: `results/native-rtc-smoke/summary.json`, `manifest.json`, `results/jobs/native-rtc-smoke-evidence-check.json`, `results/jobs/native-rtc-smoke.log`. Independent checks validate actual decoded/frame/BWE/RTT/codec/cap progression and pin the summary/helper SHA; a successful browser launch alone was not used as completion evidence.

## Verified impaired native transport diagnostic

```sh
node .tools/native_rtc_relay_smoke.mjs results/native-rtc-relay-instrumented
uv run --frozen .tools/audit_native_rtc_relay.py results/native-rtc-relay-instrumented
# Those immutable outputs already exist; choose a fresh results/ child to rerun.
```

The relay **strips all direct SDP candidates**, rewrites one local IPv4 host candidate per peer to owned localhost UDP proxies, checks sender endpoints and verifies the selected native remote candidate is `127.0.0.1`. Opaque native STUN/DTLS/SRTP/RTCP datagrams traverse a real-time FIFO/drop-tail queue, **30,000 remaining-wire-byte** limit, **25 ms** propagation per direction and **2→0.5→2 Mbps** service. Native encoder maxBitrate stays **4 Mbps throughout**, so the capacity change is an actual network-service change, not an encoder cap. Wire accounting uses datagram payload + **28 IPv4/UDP bytes**, not Ethernet/link-layer airtime; it is a userspace service model, not kernel netem or a measured Internet path.

Installed build **Chrome/154.0.8037.58**, CDP **1.3**, VP8, native transport-cc, canvas 640×360 nominal 30 fps. The diagnostic observes:

| Phase / capacity | Received Mbps | Native BWE Mbps | RTT ms | Cumulative decoded | Cumulative freezes | Proxy overflow packets |
|---|---:|---:|---:|---:|---:|---:|
| High / 2 | 1.4617 | 2.2305 | 60 | 100 | 0 | 0 |
| Collapse / 0.5 | 0.3951 | 0.3755 | 452 | 136 | 3 | 108 |
| Recovery / 2 | 0.2929 | 0.4494 | 56 | 224 | 7 | 108 |

Native bandwidth response and decoder stalls are real, but recovery remains underutilized over this short 4-second phase. **Native receiver `packetsLost` stays zero despite 108 proxy drops**; the opaque datagram/link and aggregate RTP counters have different scope and temporal/repair semantics. Do not substitute either for capture-cohort deadline/quality loss. No unique repair mechanism is inferred from these counters.

`results/jobs/native-rtc-relay-evidence-check.json` independently reconstructs **23,847 raw timestamped events / 1,527 datagrams**, every FIFO admission/drop/partial service and capacity integral, final byte ledgers and forwarding-after-serialization timestamps. Minimum recorded post-serialization propagation is **25.001 ms**, queue stays ≤30,000 bytes and send errors are zero. Raw forwarding records are socket-send initiation; terminal asynchronous send callbacks can remain pending, so neither logs nor final counters imply every pending packet reached the receiver. Actual decoder progress is separately required.

Raw evidence: `results/native-rtc-relay-instrumented/{summary.json,events.jsonl.gz,source_snapshot.mjs,manifest.json}`; frozen source/summary/event hashes are sealed. The earlier uninstrumented `results/native-rtc-relay-smoke` source is archived separately. The event trace proves more than internal green counters or Chrome launch success, but **does not** prove frame capture-to-render deadlines, perceptual quality, comparable RLCD performance or SOTA.

## Measured application-frame deadlines and compatible native actuation

```sh
node .tools/native_rtc_frame_probe.mjs results/native-rtc-frame-probe auto
node .tools/native_rtc_frame_probe.mjs results/native-rtc-frame-min-jitter min-jitter
uv run --frozen .tools/audit_native_frame_probe.py results/native-rtc-frame-probe
uv run --frozen .tools/audit_native_frame_probe.py results/native-rtc-frame-min-jitter
# Captures already exist and are sealed. Reruns must use fresh results/ children.
```

`benchmarks/native_rtc/frame_marker.mjs` stamps each manually requested canvas frame with **16 ID bits + CRC-8/SMBUS** in high-contrast pixels. Receiver `requestVideoFrameCallback` triggers scaled decoded-video pixel readback, with raw marker luminances saved; Python independently recomputes IDs/CRC. Both source request and readback completion use **one browser document's monotonic clock**, not Node relay clocks or estimated remote capture timestamps. The predeclared deadline is **150 ms capture-request→video-pixel-readback**, a measured application endpoint including callback/render/readback overhead. It does **not** identify the exact native capture instant, physical screen scan-out or human perceptual quality.

All source requests with deadlines past the cutoff are terminal-censored regardless of outcome. Warmup is separately excluded, repeated readbacks do not inflate deliveries, invalid/unknown markers are never imputed safe, and conservative miss-rate bounds allow unknown identities. Qualification requires ≥95% known-ID callback coverage, ≥30 samples, no read errors and complete deadlines. Missing identifiable readbacks can include capture/encoder omissions and render/callback behavior, **not just link loss**. These semantics are enforced by `src/media_rl/native_frame_metrics.py`.

Two **independent single-run diagnostics**, not a paired or inferential effect:

| Receiver playout | Eligible requests | Identifiable on-time | Identified late | No identifiable readback | On-time fraction |
|---|---:|---:|---:|---:|---:|
| Browser default | 361 | 21 | 170 | 170 | 5.82% |
| Genuine zero target | 360 | 116 | 51 | 193 | 32.22% |

Default: 381 requests minus 15 warmup and 5 terminal censored. Zero target: 382 minus 17 and 5. Both have **100% known marker coverage**, no read errors and frozen JS/Python/verifier snapshots. Known eligible readback median age is 423.0 versus 114.4 ms, **conditional on a known readback**; missing-frame age is not estimated. High-phase on-time rates are 17.21% versus 95.08%, but both have **zero** identifiable on-time opportunities for collapse/recovery. The zero-target native jitter-buffer mean still reaches 417 ms by the final phase: getter acceptance is not a hard latency bound. These short same-host generated-content points are not broad quality/risk conclusions.

The zero command uses a genuine inherited native `RTCRtpReceiver.jitterBufferTarget` getter/setter and verifies readback, not a freely created JS shadow property. `benchmarks/native_rtc/native_actuation.mjs` defines **`native_encoder_cap_playout_v1`**: seven scalar encoder bitrate caps crossed with automatic/null or zero receiver target (**14 actions**). FEC ratios, encoder-latency modes, pacing/BWE overrides and legacy 42-action manifests reject. `validateNativeActionManifest` verifies the **action ABI only**, not observations/labels or policy safety; no old checkpoint or native RLCD policy is loaded by these probes. Native encoder maxBitrate is not a wire-rate bound and receiver playout target is not simulator encoder low-latency mode.

Evidence: `results/native-rtc-frame-probe`, `results/native-rtc-frame-min-jitter`; receipts `results/jobs/native-rtc-frame-evidence-check.json` and `results/jobs/native-rtc-frame-min-jitter-evidence-check.json` audit packet events, raw pixel identities, clocks, opportunities, censoring and eight/nine artifact hashes. The latter replays **23,939 packet events / 1,538 datagrams** and verifies actual native command fields. Tests: **171 Python** (including 13 frame-metric tests), **18 Node** marker/action tests. Native appendix evidence is exported separately to `paper/generated-native-rtc` by `.tools/export_native_frame_paper.py`, with SHA/method/metric consistency checks, not passed off as another formal controller study.

## Causal native learning-data prototype (separate instrumented runs)

`docs/NATIVE_ROLLOUT_V1.md` specifies the new **16-feature sender-only observation ABI**, linked RTCP feedback-age masks, four-step/64-input model manifest and raw paired synthetic RGB-quality labels. A conventional BWE-headroom encoder-cap baseline now executes with genuine native command readbacks. Its independent short diagnostic improves overall on-time utility, **but harms high-phase quality/timeliness**; it is not promoted, and no native learned policy is trained. Current full suite: **192 Python + 42 Node tests**. The new telemetry/full-image instrumentation is shared within those two runs, **not identical to the lighter old frame probes above**; do not splice their numbers into paired claims.

## Next concrete benchmark work

1. **Done as a diagnostic:** owned local UDP relay, capacity collapse, drop-tail queue, full raw-event FIFO/service/propagation replay and native BWE/decoder response. Expand to predeclared independent trace/content/workload panels and validation; these two short relay runs do not establish general performance.
2. Pin full browser version/source/runtime and protocol/codec negotiation; log actual monotonic packet service, receive feedback, codec/render timing and content identities.
3. **Actuation partial, not a deployed model:** native 14-action cap/receiver-target ABI now executes with genuine accessors and readbacks. Causal sender-feedback observation ABI and source-to-acknowledged-action/quality label timing now exist as verified prototypes (`docs/NATIVE_ROLLOUT_V1.md`). Still collect adequate exploratory training coverage, train/load a fresh compatible native policy and predeclare held-out validation. The old 42-action bitrate/FEC/encoder-latency checkpoint is incompatible; receiver target is not the old encoder mode, and native cap is not wire-rate actuation.
4. Add actual published learned/hybrid competitors on the same supported interface/runtime, risk-matched strong conventional controls, independent real/measured trace/content panels and claim-level statistics/validation locks.

The original smoke is unimpaired; subsequent relay diagnostics add verified userspace impairment. The frame probes add source-ID verified application request-to-readback deadline measurements, not the exact native capture instant or physical scan-out. None supplies RLCD/browser comparison, natural-content quality validation, cross-platform reproducibility or a SOTA claim. The active goal remains open in [SOTA_TRACK.md](SOTA_TRACK.md).
