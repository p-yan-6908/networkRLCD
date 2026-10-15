# IF1: bounded instrumented Chromium transport observability

## Question and prior boundary

Can a new, pinned Chromium/WebRTC build expose native transport-control events
and mechanism state with enough causal timing and stable identity to justify a
new prospective common-support test? Observability is necessary; it does not
establish sufficient state, repeatability, conditional action value or a controller.

Anchor `14d411530b0f5d6cc06a1493ec33a5a6f1ce50bc`. M11R establishes the current
managed fixture's observability/identifiability boundary. M5's history effect,
all negative results and all previous freezes retain their original meanings.
No closed telemetry is searched. No conditioning duration, feature list, action
study or controller in the managed fixture is reopened.

This is a new fixture called **IF1**, with no inherited native common-support
claim. The source survey, plan, schema, hook map, resource gate and qualification
allocation must be committed before any build or native collection. Static source,
resource and access inspection may precede registration; these contain no native
future response. There is no implemented C++ patch or IF1 binary at registration.

## Pin, effort bound and admission

Chromium154.0.8037.57 commit `73c14f6228d7cd537c855007e8f88678969cc0eb`, its WebRTC
`3a8b0c76e6b7bf0e72141047f82eb2c3f4862c8d`, depot_tools
`382c208a9973e1a6c0867b6d8664dc6dc9116e30`, and Clang package
`llvmorg-24-init-3796-g20e97c4b-27` are pinned. All resolved DEPS/CIPD IDs, OS/package
inventory, GN arguments, source/patch hashes and actual executable hashes must
be sealed before qualification. The baseline and patch use the same build recipe.
See `instrumentation/if1/BUILD_REQUEST.md` and the hash-bound machine contract.

Maximum28 production files,2000 handwritten changed lines, eight engineer-hours,
one initial build plus one compiler-repair cycle, six total build wall-hours,
120GB incremental external peak. Require130GB free,16GiB memory limit and four
effective CPU cores to admit that attempt. The source's independent published
minimum is100GB free. A failure of admission means no checkout, tool installation,
compile or native collection in this attempt. It does not show the hooks are
impossible to implement. A failed build is preserved; no unbounded repair loop.

No managed browser-policy change, estimator/encoder algorithm change, field-trial
change, scheduling-priority change, fake network/clock replacement in native
sessions or extension-allowlist bypass. A new compiled diagnostics endpoint is an
explicit property of IF1. The installed managed Chromium is unchanged. No remote
runner is provisioned or workflow dispatched without an already qualified builder.

## Native event and identity contract

Implement one PC-scoped context before Call creation through the existing per-PC
Environment construction in `PeerConnectionFactory::CreatePeerConnectionOrError`.
Mint opaque nonreused IDs for run/process generation, PeerConnection, transport,
controller, pacer and SSRC assignment generation. Return the PC identity through
the actual JS PeerConnection's native handler. Record explicit registry edges and
creation/retirement sequence numbers. Never infer identity from a pointer value,
thread, filename, temporal correlation or one convenient active stream.

The registry describes transport-scoped controllers and their current primary/RTX
SSRC sets. Aggregate control state is not per-SSRC state. Before native SSRC
assignment, its status is `unassigned`; it is never SSRC0 by imputation. Real RTCP
media SSRC0 can be valid transport-wide metadata and must not be used as sender
identity. Publish each assignment before dependent records; consumers must have
received its registry edge by their decision cutoff. PC/controller-scoped startup
events remain identifiable before an SSRC exists. ID retirement/recreation must
not join two lifetimes, even when a numeric SSRC is reused.

| Required native channel | Producer and exact meaning |
| --- | --- |
| Actual incoming transport feedback | Stamp entry and successful authentication in `SrtpTransport::OnRtcpPacketReceived`; propagate a packet token and ingress stamp across every asynchronous hop. At `RTCPReceiver::HandleTransportFeedback`, require successful PT205/FMT15 parsing. Emit sender/media SSRC, base sequence, feedback count and ingress/parse/dispatch times. Preserve parse failure separately. |
| Controller consumption | `RtpTransportControllerSend::OnTransportFeedback`: record actual worker entry, adapter accepted/rejected and parent feedback token. Arrival, parsing and estimator consumption are separate events. Receiver feedback reference time is not a sender-clock arrival. |
| Estimator timing | Hook actual delay and loss estimator update invocations and results, including periodic updates, before/after estimates and detector/phase state. Record actual producer clock as well as any logical `at_time`. A no-change update and inactive estimator version remain explicit. Target-rate emission is a separate event, not every estimator update. |
| Probe lifecycle | Record controller cluster creation, prober pending/active/start/sent/completed/discard/timeout transitions, and estimator success/failure/insufficient-support result, all with controller generation and cluster ID. Sending completion is not estimation success. Do not infer an active probe from a burst. |
| Pacer/queue/debt | On the owning pacing queue, read actual queued bytes/packets, queue-time source stamp, media and padding debt, configured/adjusted pacing rates, padding rate, pause/congestion flags, prober phase, and last process/send times. Record events and50ms snapshots. |

Pinned `PacingController` stores `media_debt_` and `padding_debt_`; a separate
positive credit counter is not implemented. Expose the actual debt representation
and its update time, with source-verified units/meaning. `credit` is explicitly
not applicable, never synthetic zero. Do not relabel relay backlog as pacer debt.
Counter/queue conservation must use native enqueue, send/drop and debt-update
events. Reads must not advance budgets/queue clocks or call mutating
`CurrentCluster`, `ProcessPackets`, probing or estimator functions.

`hook-map.json` binds proposed symbols/lines to immutable source hashes. The
actual patch must cover every mutation/exit path needed by each channel. If true
ingress lineage, update timing, lifecycle or debt cannot fit the bound, fail the
interface gate rather than substitute a proxy or redefine an event.

## Live delivery and sender causal information

Use one experimental, loopback-enabled, PeerConnection-bound Blink snapshot API.
The endpoint directly binds to the native object; it does not use ordinary
five-second RTC files or post-stop tracing. Producer hooks perform bounded fixed
record copies to a nonblocking ring (8192 records,<=512bytes each per PC). No
filesystem/network I/O, waits, synchronous cross-thread calls, JSON formatting or
native clock advancement on a controller/pacer hot path. Report overflow/pending
publication, per-family producer counts, contiguous committed watermark and ring
generation explicitly. Overflow fails qualification; no silent sampling/truncation.

Collect coherent snapshots on each owning queue. Stamp every read at actual
observation, retain a counter's last mutation time, and do not present cached state
as a new estimator update. The consumer polls every50ms, with bounded serialization
on a noncritical queue. Journal native production, publication, native snapshot
request/completion, browser request and real browser receipt separately. The
sender's available time is the final actual receipt, including registry and clock
information. A later file, mapping, parse result or ID cannot be backdated.

All native stamps are integer microseconds from source-proven Linux
CLOCK_MONOTONIC; record clock domain and process generation. The new endpoint
returns a native clock sample within a sender `performance.now()` request/ACK
fence before media and every1000ms. Use only already received anchors, at most
1500ms old. An event's sender-time interval is its native time plus the past
offset interval and quantization bound. Never use a full-session fit, future
anchor, receiver clock, wall clock, sequence correlation or future BWE response
to create an online feature. If bounds are absent/wide, retain invalid status.

At decision time d, every used record, registry edge and clock anchor must have
actual receipt<=d. Age is computed from a qualified sender-time interval. Future
responses start strictly after d and after any actual command ACK, not at a
backdated event time. Receiver QoE/frame outcomes stay closed during IF1.

## Stage gates, frozen before any build

1. **Admission/source:** exact pins, all required source semantics and a qualified
   builder/artifact path; resource/effort bounds above. No compiler attempt after
   failed admission. Static hook availability is not native observability.
2. **Build/interface:** baseline+patch hashes and same recipe; production diff
   within scope; read-only bounded hooks, complete identity/clock/API schema.
   Scripted native-control parity must preserve exact algorithm outputs for the
   same inputs/clock with diagnostics enabled/disabled. That synthetic check is
   not native support evidence. One compiler-repair cycle is the limit.
3. **Fresh technical qualification:** four untouched ordinary originals, two
   licensed contents × two prior histories, in the reserved order. Require fresh
   TURN/TCP ICE and bidirectional media preflight, unchanged policy, VP8/fixed cap
   and encoder/jitter readback, exact1200kbps initialization within100ms,25ms
   sampler, main>=3168 native observations, gaps<=250ms, scheduling lateness<=150ms,
   replay/command ACK<=100ms, source tick error<=150ms and exact cleanup<=2000ms.
   New native clocks must pass beginning35 training/4 held-out and full128/15
   coverage with widths<=50ms. No M11R calibration result is a substitute.
4. **Fresh observability:** eight separate originals, two contents × two prior
   histories × two repeats, all required. Same unchanged10s prefix,24s initial
   service,64s common plateau and12.6s measured-source probe. Fixed4Mbps cap,
   no randomized bitrate actions. All channels, causal identity and technical
   gates must pass in every original; no replacement/retry or pooled pass rate.
5. **Fresh support only, conditional:** after all preceding gates, commit a
   separate complete protocol and one predeclared native-state formulation using
   qualified resolution/semantics only. Reserve a new untouched64-context panel:
   two contents × two histories × four service levels × four repeats. No old
   allocation or IF1 technical/observability capture enters support estimates.
   Freeze state/census, matching and future-stability rules before capture; no
   predictor, representation search or outcome-led threshold selection.

The technical/interface stage additionally needs two short, separate live identity
controls: concurrent independent senders, then close/recreate one PeerConnection
while another remains live. There must be zero cross-attribution or ID reuse;
use actual source registration and native SSRC readback. This does not compare BWE
responses or receiver outcomes. Native hot-hook p99<=50us and maximum<=1000us,
no event losses, no blocking producer work, no changed algorithm outputs in the
scripted parity check. Native BWE equality between independent runs is not an
instrumentation-overhead test; IF1 is a new fixture.

### Required observability thresholds

- Every retained control event has unambiguous PC/transport/controller identity
  known to the sender at receipt; pacer/probe events also have the proper pacer
  identity. Registry transitions and sequence counts reconcile exactly. No
  cross-attribution, drops, silent overwrites or unexplained count gaps.
- Every event used online has past-clock interval width<=50ms and actual snapshot
  ACK<=100ms. >=90% of each family's producer events arrive at the sender within
  250ms, **in each original**, including startup; no continuous TCC delivery gap
  >1000ms. Late/post-stop events remain late and stay in the denominator.
- Each original has>=10 actual TCC events,>=10 delay/loss update invocations,
  >=1 probe creation and>=1 execution/result terminal event. Pacer snapshots have
  >=90% of the1760 nominal main samples, no gap>250ms and all required counters
  present. Legitimately inactive modules are explicit; their status cannot stand
  in for an entirely missing required channel family.
- Qualify source-clock error and producer-to-sender intervals quantitatively.
  Diagnostic liveness does not imply event freshness. Reconcile arrival→parse→
  dispatch→consumption tokens; require causal ordering and separate clocks for
  receiver-generated feedback reference times. No synthetic successful channel
  may fill a native gap.

## Fresh support and action boundary

The exact inherited range/SD/overlap/repeatability gates are copied without change
into the machine contract: profile range>=1.0octave, sample SD>=0.35, common
overlap>=0.5, repeat spread<=0.25, prefix W-infinity<=0.25, census difference<=0.25,
and at least four independent members per history, along with every original
census/caliper/eligibility/exposure/timing condition. Failed D1 and instantaneous
BWE remain baselines. A different native mechanism state must be declared before
the new support panel; qualifying its counters is not evidence it creates overlap.
No conditioning extension or post-hoc rule relaxation is permitted.

Technical/observability contexts reuse licensed content and one measured program
for apparatus qualification. Constructed prefixes, controlled synthetic service
and measured-source probe stay separate; this is no new content/campaign replication.
Any later action experiment requires a separate untouched allocation and registered
estimand. Controller fitting/promotion remains closed until independent randomized
evidence establishes stable conditional value over a strong fixed0.65 baseline.

## Stop decision and alternative research question

Classify failures by stage: unavailable build resources/access; unbuilt/unverified
patch; failed technical acquisition; failed observable interface; failed common
support. None is an action-effect estimate. In particular, insufficient local
build disk does not demonstrate that a source-level channel is impossible or
that transport timing is irrelevant.

If the required complete interface cannot be implemented/qualified within the
bound, preserve the negative/unknown statuses and stop this fine-grained native
state route. Move the research question to partially observed, uncertainty-aware
control: what **policy/sequence-level** performance or risk can be identified under
an explicitly specified distribution of hidden histories? No new state expansion,
stability predictor or bitrate controller is fitted on any closed panel. The
separate research-decision document specifies the pivot and its data boundaries.
This is a bounded practical identifiability limit, not an impossibility theorem.

## Preservation and storage

Freeze every file tracked at14d4115 and checksum the relevant pinned M11R archive
inventory without decoding telemetry. Do not change old reports, seals, protocols,
allocations or original media. New design/source evidence lives externally under
`~/.cache/networkrlcd/native-instrumented-fixture-if1`; no previous path is reused.
Bound current static evidence to10MB and20MB including archive/fresh verification.
An admitted later build has its separate120GB bound; fresh technical/observability
capture has2GB raw/6GB archive-verification peak and must start with>=8GB free.
Stop on a threatened bound and preserve the failed original. No raw truncation or
unverified deletion. Upload a fresh private namespace, pin its immutable revision,
and freshly verify all object/member size/SHA checksums. No native capture or
support allocation is instantiated unless its preceding stage passes.
