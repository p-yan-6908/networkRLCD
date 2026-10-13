# Native clock/action probe V2: policy-compatible TURN/TCP

## Purpose and evidence boundary

This prospectively registered transport continuation reruns the existing
32-session native comparison of sender-estimate caps 0.65 and 1.05. It keeps
the same eight generated-scene seed clusters, two repetitions, balanced
whole-session arm order, collapse/recovery capacity schedule, per-hold timing,
pixel-readback endpoints, relay accounting, and seed-cluster inference. The
1.05 arm remains the strong fixed-action reference. This is not a new controller
or a replacement for V3.

The prior 32 no-candidate attempts remain sealed transport failures with no
treatment outcomes. They are not replaced, pooled, or treated as zero delivery.
V3, its prior frozen evidence, the targeted archive restore/replay, and the
qualified marker-only calibration remain unchanged. Synthetic, recorded-video,
archived-session, and native generated-canvas evidence stay separate.

## Policy-compatible transport

Chromium remains under the managed
`WebRtcIPHandling=disable_non_proxied_udp` policy. Each peer is configured with
`iceTransportPolicy: "relay"` and one authenticated `turn:127.0.0.1:<port>?transport=tcp`
server. Coturn listens on loopback TCP and allocates loopback UDP relay ports;
the browser sends TURN control and media over TCP, while the relay server uses
UDP for peer-facing relay traffic. The existing Node userspace queue receives
the media datagrams and forwards them to the two Coturn relay allocations. The
queue limit, serialization service, 25 ms propagation, and three capacity
phases are unchanged. There is no direct browser UDP candidate fallback.

Coturn 4.6.1 is kept in the user cache with the exact binary and runtime-library
hashes recorded in the protocol. Each process has a random short-lived
credential, loopback listener and relay address, a bounded relay port range,
loopback-only peer permissions, and UDP listening disabled. The credential and
TURN configuration are not copied into the evidence report.

Before action capture, a separate native preflight requires both peers to
complete gathering with relay-only candidates, select TURN/TCP backed relay
pairs, connect, and exchange encoded and decoded video in both directions. The
preflight records the managed policy hash before and after. Its first runner
attempt is retained as a technical failure caused by an evidence-reporting
variable error after media had already flowed; the corrected attempt passed all
six registered transport checks.

## Clock gate and outcome order

The previously qualified 120-marker calibration is copied byte-for-byte and
reused after its full calibration inventory, report, and protocol hashes are
verified. Each actual action session also repeats the five paired browser/Node
markers at measurement start, the three phase changes, and measurement end.
After all session inventories pass checksum verification, a clock/transport
gate reads only candidate, policy, and marker evidence. Every session must have
complete TURN/TCP relay-only ICE evidence, unchanged managed policy, and a
nonempty feasible affine mapping with all held-out markers covered and mapped
time width at most 50 ms. It must also retain the expected marker sequence.

Only after all 32 sessions pass that gate may the analysis read sender actions,
frame readbacks, image-quality samples, or per-hold relay events. Relay offers
are assigned to an action window only when every feasible mapping puts the
event inside it. Boundary-ambiguous packets and bytes remain in the possible
bound and are not silently assigned to the treatment window. Any failed or
incomplete session keeps its sealed files and blocks the registered contrast
analysis; no cell is retried or replaced.

## Frozen estimand and decision boundary

The analysis remains paired 0.65-minus-1.05 within the eight scene-seed
clusters after averaging the two repetitions per seed and action. It reports
high, collapse, and recovery states separately, along with the collapse/high
and recovery/high action-by-state contrasts. The registered endpoints are
on-time source-frame readback share, sampled RGB PSNR among on-time frames, and
guaranteed/possible A-to-B relay wire bytes and drops. Pixel readback and RGB
quality are synthetic proxies, not human QoE.

No controller is fit or promoted. A state-specific signal is a development
finding on one Chromium build, one loopback TURN service, one userspace queue,
one generated-scene algorithm, and one capacity schedule. It cannot establish
deployment value, physical-network generalization, safety, or an advantage over
a tuned controller. Any follow-up that could support conditional action value
must use newly generated independent scene clusters and a prospectively frozen
replication over multiple capacity traces; it will remain separate from V3 and
all archived and synthetic evidence.

## Reproduction

The committed protocol is
[`native_clock_action_probe_turn_tcp_v2.json`](../configs/native_clock_action_probe_turn_tcp_v2.json).
The versioned collector and gated runner are
[`clock_action_turn_tcp_episode_v1.mjs`](../benchmarks/native_rtc/clock_action_turn_tcp_episode_v1.mjs)
and [`native_turn_clock_action_probe_v2.py`](../tools/native_turn_clock_action_probe_v2.py).
Raw sessions remain outside Git at the protocol's pinned cache path.

    uv run --frozen python tools/native_turn_clock_action_probe_v2.py capture \
      --root /home/agent/.cache/networkrlcd/native-clock-action-turntcp-v2

Verify the full session inventory before the clock/transport gate. Run the
registered analysis only if that gate reports all 32 sessions qualified.
