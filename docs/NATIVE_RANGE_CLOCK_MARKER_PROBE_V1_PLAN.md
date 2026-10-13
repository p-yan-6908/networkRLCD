# Native range clock-marker probe V1 plan

## Purpose

The restored range-pilot record has sender and encoder timestamps in the
browser-page clock and packet/phase timestamps in the Node relay clock. There
is no paired exchange timestamp in the archive, so UDP datagrams cannot be
assigned to individual cap holds. This plan specifies a new, separately
versioned instrumentation check. It does not revise or repair the old capture,
change the registered V3 result, or collect data now.

The narrow question is: can the browser-to-relay time mapping be bounded tightly
enough to identify which relay datagrams fall inside each recorded sender hold?
This instrumentation check cannot establish delivered-quality benefit,
state-conditioned action value, or safety.

## Recorder changes for a future capture

Use a new capture ABI and new output directory. For every `/phase` request and
for no-op `/clock-marker` exchanges immediately before measurement and after
it, record one unique `marker_id` and:

- Browser `browser_send_ms`, immediately before `fetch`.
- Node `node_receive_ms`, after the request body is read.
- Node `node_phase_ms`, when the phase event is committed (for phase requests).
- Node `node_send_ms`, immediately before the response is sent.
- Browser `browser_receive_ms`, immediately after the response is read.

Echo the ID and browser send time in the response and persist the same record in
both browser evidence and Node relay history. Keep all raw marker records,
including timeouts, retries, and malformed responses. Do not infer a clock
mapping from `measurement_start_ms` and the first phase event. The no-op marker
route must not change capacity or relay state.

## Predeclared clock bounds

Model the short-run mapping as `Node_ms = alpha * Browser_ms + beta`, where
`alpha` is positive. For marker `i`, causal ordering requires:

```text
alpha * browser_send_ms[i] + beta <= node_receive_ms[i]
node_send_ms[i] <= alpha * browser_receive_ms[i] + beta
```

Retain the complete feasible `(alpha, beta)` set satisfying every marker. Do
not collapse it to a point estimate. If the set is empty, unstable, or too broad
to separate the intended sender windows, report the cross-clock join as
unresolved. The marker exchanges also provide a per-request uncertainty width
that exposes transport and event-loop delay.

For each sender hold `[ack_ms + 1800, ack_ms + 2600)`, map its endpoints through
the entire feasible clock set. A Node relay offer belongs to a hold only when
every feasible mapping assigns its Node timestamp to that same hold. Report
guaranteed and possible packet/byte counts separately; leave boundary-ambiguous
events unassigned. Reconcile pre-phase, in-phase, and post-schedule records so
that no relay event silently disappears from the accounting.

## Integrity and stopping rules

- Freeze the recorder source hashes, marker schema, selection, and analysis
  before any capture. Keep this plan separate from the old range and V3
  registrations.
- Write new raw evidence outside the repository and seal its complete file
  inventory before analysis. Verify every file hash before parsing telemetry.
- Preserve all incomplete sessions, missing markers, and ambiguous joins.
- If the clock mapping is unresolved, stop at relay-clock phase summaries. Do
  not tune a policy, select actions from the result, or claim per-hold relay
  effects.
- Do not read frame-quality outcomes in this instrumentation-only check. A
  separate preregistered outcome study would be needed to address delivery cost
  or delivered quality.
- Keep native telemetry separate from simulator/synthetic evidence. Do not fit
  or promote a model or controller from this probe.

## Decision after the check

If the feasible clock bounds support unambiguous hold assignments, the next
study can pre-register a native endpoint analysis that uses them while retaining
an explicit ambiguous-event bound. If not, keep relay data at the phase level
and design a lower-latency paired marker. In either case, this instrument check
alone does not change the V3 delivery conclusion or authorize controller
promotion.
