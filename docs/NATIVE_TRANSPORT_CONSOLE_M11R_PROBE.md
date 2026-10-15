# M11R supported console-route metadata probe

Freeze this probe before execution. M11R's two fresh capability originals are
complete, acquired successfully and failed the registered channel freshness gate.
Do not rerun them, reclassify them or open development. A later static survey
found `trace-to-console` in TraceConfig as a record-mode value, with a Perfetto
ConsoleInterceptor in base TraceLog. Binary presence is not an independent switch
or proof that Chromium's multiprocess tracing configuration activates that sink.

Run exactly one fresh **metadata-only** browser, no peer connections, media,
native contexts, BWE or receiver outcomes. Use pinned Chromium and unchanged
managed policy. Exact additional arguments:

```
--enable-logging=stderr
--trace-startup=blink.user_timing,disabled-by-default-webrtc,webrtc
--trace-startup-record-mode=trace-to-console
--trace-startup-duration=5
--trace-startup-format=proto
--trace-startup-file=<fresh external probe directory>/startup.pftrace
```

After attaching DevTools, produce the two literal Performance marks specified in
the script, 500ms apart, and record their request/acknowledgement fences. Retain
timestamped Node stderr chunks and observed trace-file availability for 6.5s.
Bound the probe to 10MB and retain failure evidence; do not retry. Check whether
known markers appear in live stderr before stop, and whether the output file
contains the marker names, distinguishing a missing console sink from absence
of recorded events. The file is inspected only for these artificial markers.

This cannot qualify native transport channels. A successful console sink still
needs exact native event semantics, unique sender identity, clock and freshness
qualification under a separate preregistration. Existing TransportFeedback::Parse
and pacer trace schemas expose no SSRC/transport identity; generic RTCP entry is
not accepted as an actual transport-CC arrival. No development, stability labels,
matching, state search, bitrate actions or controller follow from this probe.

Retain exact pinned implementation sources and acquisition failures in the
external additional-reference directory and include them in the M11R archive.
No prior freeze or original is changed.
