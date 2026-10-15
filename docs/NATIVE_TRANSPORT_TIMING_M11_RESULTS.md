# M11: sender-identity instrumentation limitation

Scientific registration `fba94f71da4cc3be308b7ac88476b45935e8319c`.
Both fresh capability originals passed existing native clocks, initialization,
TURN/TCP, policy, replay, readback, sampling, receipt and cleanup gates. New
snapshot/clock ordering, binary completeness and decode checks passed.

The registered channel gate failed for all three families because the logged
VideoSendStreamConfig contained SSRC **0**, whereas the live sender used nonzero
SSRCs. No native event passed the frozen exact-SSRC association. Zero qualified
events does **not** mean native events were absent: 4292 and 4304 RTC-log support
records decoded. The original gate remains failed; no future-BWE stability label,
compact match, mechanism effect or receiver outcome was opened.

A support-only header diagnostic found an exact native SSRC in outgoing RTP
fixed32 field6 in exactly one log file per original. The other peer's log had no
outgoing RTP. This is a direct identity repair supported by the pinned schema;
it does not rely on filename order, a guessed thread, or SSRC0 as a real sender.
Packet payloads and frame-event bodies remain unopened. This diagnostic does
not backdate a feature or reclassify either original as qualified.

DevTools tracing recorded 19659 and 19882 pacer events, but none was acknowledged
by the sender during measurement. Source inspection of TracingHandler shows
ReadTrace/DataCollected follows session stop. These are offline diagnostics;
their producer timestamps do not establish live availability or sender identity.

The bounded verbose fallback was specified but not instantiated under M11.
A fresh M11R registration will retain all technical, causal and freshness gates,
use exact outgoing-packet SSRC linkage to a unique log file, and enable the
already source-qualified verbose diagnostics on two fresh capability originals.
The old originals are excluded and preserved. No development or trajectory
state panel is opened. This is an instrumentation repair, not evidence for or
against the transport-timing explanation of future divergence.
