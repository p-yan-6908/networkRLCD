# M11R direct Perfetto-file metadata probe

Freeze before execution, separately from the closed M11R native originals and
failed console-mode metadata probe. Pinned Chromium's supported
`--trace-perfetto-config-file` accepts a serialized Perfetto TraceConfig.
Its pinned Perfetto schema explicitly supports `write_into_file`, a fresh
`output_path`, `file_write_period_ms` (minimum100ms), and `flush_period_ms` for
quasi-real-time streaming. This is distinct from DevTools' post-stop export and
the rejected console record mode. Do not infer availability from schema alone.

Exactly one fresh metadata-only browser, zero peer connections, no media or
native state. Use the script's fixed protobuf configuration: 1MiB ring buffer;
track_event; disabled category `*`; enabled `blink.user_timing`, `webrtc` and
`disabled-by-default-webrtc`; nonincremental track timestamps; duration6000ms;
file-write100ms; flush100ms; maximum output10MB; fresh external file. Chromium
and the managed browser policy remain unchanged. Run from the external output
directory so a default controller output cannot enter the repository.

After DevTools is available, wait500ms then issue the two script-literal
Performance marks500ms apart. Tail the output every25ms until8s from launch;
record when each literal first becomes visible, request/ACK fences, clock metadata,
raw bytes, process exit/signal and failures. No retry or alternate setting. This
assesses an export mechanism, not native semantic identity, estimator behavior
or state stability. A fast export cannot add SSRC/transport identifiers absent
from trace annotations. It cannot reclassify M11R's gate or open development.

Record unsupported/partial success honestly. Only a separate prospective native
registration could qualify any complete transport-channel set with unchanged
identity, causal-clock, freshness and repeatability gates. No receiver outcome,
future BWE, representation, predictor, action or controller is examined here.
