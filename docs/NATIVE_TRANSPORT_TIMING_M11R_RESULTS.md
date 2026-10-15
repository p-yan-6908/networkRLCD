# M11R: transport-control timing did not qualify for causal use

Native registration `86ac6f45ffc96e19bb7320c1a9f3f2d14810133c` preceded two fresh
originals. M11's preceding sender-identity failure remains unchanged and excluded.
M10R remains a qualified observability failure; no old capture was searched for
new state representations. This assay used support/instrumentation variables only.
Chromium's version tag resolves to the actual CDP-reported commit
`73c14f6228d7cd537c855007e8f88678969cc0eb`; its pinned WebRTC dependency is
`3a8b0c76e6b7bf0e72141047f82eb2c3f4862c8d`.

The licensed clips and measurement program were reused for instrument qualification,
not independent replication. Native Chromium ran under a constructed equal-integral
prefix, a synthetic0.5-to-1.414Mbps step/plateau, and the original measured-source
probe. Native telemetry, controlled service and measured-source replay retain
their separate meanings; none was pooled as new content/network evidence.

## Acquisition and sender clock coverage qualified

Both native originals passed TURN/TCP, managed policy, initialization, readback,
replay, native sampling, first-phase/full clock, receipt and cleanup gates.
Main native samples:3519/3520; maximum gaps:88.7/45.3ms. Beginning clock holdouts
covered4/4 in each original (maximum widths1.33/1.92ms); full holdouts covered15/15
in each (maximum widths1.08/1.06ms). No offline full-session clock fit was used
for online diagnostic features.

Direct outgoing-header fixed32 SSRC matched the live sender in exactly one RTC
log per original. Configuration SSRC0 remained explicit, unusable metadata;
filename order and trace-thread guesses were never used. All new diagnostic
ordering, complete-record/decode and native-source checks passed. Each original
had111 valid past-only DevTools monotonic-clock ACK fences, maximum widths
16.9/14.1ms before the registered integer-timestamp rounding allowance. Maximum
diagnostic snapshot ACKs were20.5/28.6ms. Acquisition is not channel qualification.

## All three required RTC-log channel families failed freshness

The unchanged gate required >=90% of events available to the sender within250ms,
clock uncertainty<=50ms and no continuous-feedback delivery gap>1000ms.

| Instrumentation measure | Kampar / ascending | Volga / descending |
| --- | ---: | ---: |
| First sender-identified RTC batch, after measurement start |59.023s|59.017s|
| Actual TCC arrivals, uniquely identified and timestamped online |1739|1747|
| TCC events fresh within250ms |31 (1.78%)|33 (1.89%)|
| Median TCC producer-to-sender upper delay |5.026s|5.015s|
| Native delay/loss BWE update events |2110|2090|
| BWE update events fresh within250ms |30 (1.42%)|37 (1.77%)|
| Median BWE-update producer-to-sender upper delay |4.979s|4.932s|
| Probe creation / result events |3 / 13|4 / 27|
| Probe events fresh within250ms |0 / 16|0 / 31|
| Maximum TCC batch delivery gap |5.086s|5.099s|

Native TCC producer gaps had median62ms in both originals. The export delivered
five-second batches after its late first visibility, with startup history up to
about59s old. The source-specified5000ms local output period must not be confused
with the measured startup delay or a guaranteed event freshness bound. Most
diagnostic events first became visible after an intervening getStats BWE change;
this is a delivery-lateness check, not attribution of that change to the event.
Historical records become available at their actual ACK. They are not current
transport state at their earlier producer timestamp.

## Supported alternatives and their exact limitations

| Route | What was observed | Remaining limitation |
| --- | --- | --- |
| Targeted WebRTC verbose v1 |639/608 timestamped target-update lines acknowledged before cutoff; all within250ms; p90 upper delays95.8/97.3ms|No SSRC, PeerConnection, transport or controller identity in the lines. The native target-rate emission is not every delay/loss estimator update. No actual incoming-TCC arrival schema or identified probe lifecycle was exposed.|
| DevTools ReportEvents |19688/19769 pacer events;1767/1774 `TransportFeedback::Parse` events retained|Zero trace events acknowledged by sender during measurement. Export followed stop. Pacer/TCC annotations lack SSRC/controller identity; TCC parsing is distinct from raw arrival and exposes no parse result/packet key.|
| Console record mode |Fresh metadata-only browser failed before DevTools; no peers or marks created|Pinned multiprocess Perfetto configuration rejects ECHO_TO_CONSOLE with `NOTREACHED()`. Frozen probe did not record process exit status, so no exact signal claim is made.|
| Direct Perfetto file configuration |Two artificial marks acknowledged; requested path absent; retained temporary file contains both names in final inventory|Original probe did not observe that temporary file online. This is a file-discovery limitation, not proof that streaming is impossible.|
| Separately frozen temporary-file discovery repair |Two artificial marks acknowledged; actual temporary file observed|Neither marker present live or in final file. Recording control did not reproduce; no export-latency estimate or native channel qualification follows.|
| Public local flag / webrtc-internals |Actual RTCP TCC, native delay/loss updates and probe records decoded|Share the fixed5000ms local output path. No supported per-page immediate-output parameter.|
| Private extension API |Pinned IDL supports `outputPeriodMs=0`|`webrtcLoggingPrivate` permission explicitly requires an allowlisted extension identity; absent from normal page API. No approved extension access is available in this environment.|

Metadata registrations were `4b7cd10` (console), `971af24` (direct file), and
`369dcad` (temporary-file repair), each committed before execution. They created
zero native contexts and did not alter M11R's native gate. Original failures,
temporary files, raw diagnostic bytes, source URLs/hashes and HTTP source-path
failures are retained. Source presence alone never qualified a channel.

Relay enqueue/forward times and socket arrival do not expose browser feedback
decryption/parse/dispatch or estimator consumption time. Some SRTCP common-header
bytes may remain visible; this does not make relay receipt an equivalent internal
clock event. RTP bursts do not uniquely identify native probing or pacer credit.
Polled BWE/RTT counters remain the existing censored observations/proxies.
No equivalent external proxy was justified. Full internal pacer queue/credit/cwnd
and probe-active state were not obtained. No clock or identity learned later was
inserted into an earlier online feature.

## Decision and identifiability boundary

Required transport channels qualified in **0/2** originals. The conditional
four-original qualification and eight-original development panel were not
instantiated. No future-stability label, compact-state matching, timing/BWE
association, classifier, new representation, trajectory efficacy, bitrate action,
or controller was opened. Receiver frame/QoE outcome files and event-log frame
bodies remained closed. Diagnostic schema discovery inspected event-name and
argument-key metadata; no receiver argument values or frame-response estimates
entered this assay.

The transport-timing explanation of residual future-BWE divergence remains
untested. This result does not imply that history is irrelevant or that native
conditional action value is impossible in every setup. M5's qualified causal
history effect and the frozen M6R–M10R support/observability failures retain their
original meanings. This single measurement program supplies no broad network
replication.

Fine-grained native conditional action comparison is **not currently established
as identifiable through the available observable context and this fixture**.
Repeated prospective common support and future repeatability remain unmet.
Randomization alone would not establish the reproducible state conditioning
required by the registered target. No controller follows from these failures.

Further work needs a demonstrably complete live transport-control interface:
for example approved immediate event logging, or a verified instrumented browser
with stable connection/SSRC IDs, actual feedback/pacer/estimator event clocks and
causal sender receipts. Such a build/interface is a new fixture requiring fresh
technical and channel qualification before a fresh development panel. A different
export sink or a single-peer process could remove individual ambiguities but has
not established the complete required channel set here. Do not append more state
variables or choose a longer wait to bypass the unresolved mechanism boundary.

## Preservation

Checksum-only audit verified1614 prior tracked files and19243 members across the
M5–M11 pinned archives, without decoding their telemetry. All earlier freezes and
untouched allocations, including M10 development and the old successor schedules,
remain unchanged. No raw or licensed original was deleted. Private archive access
is healthy; this limitation is internal diagnostic observability, with no archive
access blocker. The immutable revision and fresh object/member size/SHA verification
are recorded in the separate
[M11R storage receipt](storage-receipts/native-transport-timing-m11r-20261015-01.json).
