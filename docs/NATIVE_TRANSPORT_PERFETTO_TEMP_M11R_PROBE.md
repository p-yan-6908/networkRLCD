# M11R prospective temporary-file discovery repair

Freeze this metadata-only repair before execution. Preserve the first direct
Perfetto-file probe unchanged: both mark calls acknowledged, requested file never
appeared; a retained Chromium temporary file contains both names after execution.
No original gate is reclassified and its file has no measured online visibility.
Pinned StartupTracingController opens a temporary file and supplies its descriptor
to the streaming tracing session, then renames at finalization. Requested
`TraceConfig.output_path` alone does not identify that live file in this fixture.

Exactly one fresh browser, no peer connection or media. Keep the first direct
probe's entire pinned configuration and schedule; only discover/read **all**
regular files generated in a new empty external working directory, excluding
the script-created config.pb. Never select a convenient file by filename order.
Record every candidate, read request/completion time, size, first marker visibility,
and SHA inventory. Keep both literal markers fixed in the script. Distinguish
visibility before5s from a post-stop dump. Bound10MB, no retry, policy unchanged.

This tests an export mechanism only. It does not establish native transport
semantics, sender attribution or event freshness/repeatability. The absence of
SSRC/controller/transport identifiers in the pinned pacer/TCC trace annotations
and verbose BWE lines remains a separate limitation. No existing native gate,
future BWE, frame outcome, development panel, predictor, action or controller is
opened. A future native registration requires a complete, uniquely attributed
channel set before any development comparison.
