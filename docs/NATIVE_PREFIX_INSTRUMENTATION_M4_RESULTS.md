# M4: feasibility failure before prefix replay

Registration **`ad9b4da0da473e2453b61dcce520a92ccd7b80c8`** preceded all four
feasibility attempts. Two completed and qualified; two failed before prefix
service. The 28-session qualification stage is **untouched**. M4 is closed as
failed. No fresh causal validation was prepared, no predictor was fitted, and
no prefix effect, later BWE distribution or QoE result was examined.

| Original trial | Content / prefix | Result |
| --- | --- | --- |
| `m4-r00-c01-s0-support` | Volga / descending | Qualified |
| `m4-r00-c01-s1-support` | Volga / ascending | Failed selected-pair readiness |
| `m4-r00-c00-s0-support` | Kampar / descending | Qualified |
| `m4-r00-c00-s1-support` | Kampar / ascending | Failed selected-pair readiness |

The failed sessions had `connectionState=connected` while the selected sender
candidate-pair stats still said **`in-progress`**. The nominated loopback
TURN/TCP endpoints and nonzero bidirectional byte counters were present; the
receiver pair already said `succeeded`. M4 checked the full unchanged predicate
once immediately after connection state. It correctly failed these sessions.
Their prefixes had not begun, so this allocation pattern cannot be interpreted
as a prefix effect. Incremental startup records preserve the discrepancy.

Both completed sessions held encoding inactive through the 750 ms challenge,
observed actual native BWE **1,200,000 bps** at initialization and measurement
start, and passed every startup component. Maximum startup poll-response gaps
were 30.9/29.8 ms. The augmented clocks covered **7/7 full-session and 4/4
beginning holdouts**, under the original slope, 1 ms tolerance and 50 ms width
criteria. Full widths were 1.0889/1.1978 ms; beginning widths 1.3715/1.8620 ms.
All ordinary native support, transport, readback, replay and cleanup requirements
passed in these two sessions. Two successes do not qualify every condition or
demonstrate reliable completion of a larger panel.

The next acquisition revision, **M4R**, will prospectively wait at most 2,000 ms
with encoding still inactive for the same actual nominated/succeeded TCP-backed
selected-pair predicate, recording every readiness probe. It will not reconnect,
retry an original attempt, replace data, relax a predicate or change startup,
clock, support or cleanup thresholds. It needs a separate registration and fresh
32-session staged panel; these two M4 successes cannot enter its counts.

All four original seals and startup streams, the full frozen registration,
unstarted qualification panels, source copies and coordinator logs are preserved
in the verified private feasibility archive. The receipt pins the revision and
fresh object/member checksums. Its registration commit metadata was audited and
corrected before its first Git commit: the initial CLI argument had a transcription
error; the full commit matches every frozen protocol source hash. Remote objects,
protocol, revision and member checksums were unchanged. The audit and original
receipt digest are retained in the receipt.

Gate: `reports/native-prefix-instrumentation-m4-feasibility-gate.json`.
Closure: `reports/native-prefix-instrumentation-m4-closure.json`.
Receipt: `docs/storage-receipts/native-prefix-instrumentation-m4-feasibility-20261014-01.json`.
M3 and all earlier freezes remain unchanged. Zero original attempts were replaced
and zero evidence files were pruned.
