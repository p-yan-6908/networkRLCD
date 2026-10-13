# Native clock/action probe V3: fresh TURN/TCP panel

## Why this is a new panel

The first TURN/TCP continuation is preserved at
`~/.cache/networkrlcd/native-clock-action-turntcp-v2/`. Its 32 sessions all
completed relay-only ICE gathering with one TURN/TCP candidate per peer,
connected, and retained an unchanged managed Chromium policy. The collector
then stopped before the registered sender action and measurement start because
its transport assertion required the selected local candidate type to remain
`relay`. The owned Node UDP queue rewrites the remote relay candidate to its
local socket; Chromium correctly reports that selected local endpoint as
peer-reflexive (`prflx`) while retaining `relayProtocol=tcp`. The complete
session inventories and this checker abort are retained. The run produced no
sender-observation files, summaries, or action assignments and contributes no
treatment outcomes.

This V3 panel uses eight fresh generated-scene seeds (2000–2007), two
repetitions, a new balanced whole-session arm order using seed 20261014, and the
same frozen 0.65-versus-1.05 action schedule and endpoints. It is a new
prospective capture, not a replacement or retry of V2 sessions. Failed V1 and
V2 acquisitions, the existing V3 assay result, the targeted restore/replay,
and all synthetic evidence remain separate and unchanged.

## Transport qualification

The managed `WebRtcIPHandling=disable_non_proxied_udp` policy is unchanged.
Both peers use `iceTransportPolicy: "relay"` and authenticated localhost
TURN/TCP. The browser must gather only relay candidates, with
`relayProtocol=tcp`, and report zero candidate errors. Each selected pair must
be nominated and succeeded, point to a loopback local endpoint and remote TURN
relay candidate, and retain `relayProtocol=tcp` on the local endpoint. The
local candidate may be `relay` or `prflx`: the registered instrumentation
rewrites the remote relay candidate to its owned Node UDP queue socket, which
causes Chromium to describe that local socket as peer-reflexive.

Every session must also pass the collector's existing media checks: more than
ten encoded and decoded frames in every capacity phase, the selected remote
candidate remains a relay candidate, at least 100 A-to-B datagrams are
forwarded by the queue, the queue capacity integral is respected, and both
queue directions reconcile. The separate preflight already established
bidirectional video through TURN/TCP without the shaping queue. This
path-specific candidate rule does not admit a direct host or nonproxied UDP
route, does not alter action or outcome thresholds, and does not qualify a
session without completed media delivery.

## Clock gate and analysis

The existing 120-exchange affine calibration is reused only after its pinned
protocol, report, and complete raw inventory pass their hashes. Each actual
session records the same five browser/Node markers around measurement start,
three phase transitions, and measurement end. After all raw session inventories
pass checksum verification, the clock/transport gate reads only ICE,
transport, policy, and marker evidence. The registered marker fit/holdout
rules remain unchanged: every held-out marker must be covered, the feasible
polygon must be nonempty, and its maximum mapped-time width must be at most
50 ms.

The outcome analysis cannot run unless all 32 sessions pass the transport and
actual-run clock gates. Only then does it read sender assignments, frame
readbacks, sampled image quality, and relay event windows. Relay offers count
as guaranteed within a hold only when every feasible clock map places them
inside that hold; ambiguous events remain in the possible bound. Any failed
session blocks the registered contrast analysis; no session in this panel is
replaced or retried.

The estimator remains paired 0.65-minus-1.05 within the eight generated-scene
clusters (`df=7`), with separate high, collapse, and recovery estimates and
action-by-state contrasts. Pixel readback and sampled RGB PSNR are synthetic
proxies, not human QoE. Relay byte cost comes from one localhost userspace
queue, not an Internet or physical network measurement.

No controller is fit or promoted by this study. If the fresh panel produces a
state-dependent signal, the next validation is a separately registered
multi-trace native replication on new scene clusters before any policy work.
The current single collapse/recovery trace and eight synthetic scene clusters
cannot establish generalization or deployment value.

## Reproduction

The frozen protocol is
[`native_clock_action_probe_turn_tcp_v3.json`](../configs/native_clock_action_probe_turn_tcp_v3.json).
It uses the separate collector
[`clock_action_turn_tcp_episode_v2.mjs`](../benchmarks/native_rtc/clock_action_turn_tcp_episode_v2.mjs)
and versioned runner
[`native_turn_clock_action_probe_v3.py`](../tools/native_turn_clock_action_probe_v3.py).
The raw capture stays outside Git at
`~/.cache/networkrlcd/native-clock-action-turntcp-v3/`.
