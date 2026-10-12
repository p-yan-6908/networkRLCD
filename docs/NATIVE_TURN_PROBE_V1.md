# Native encoder/BWE observability over localhost TURN/TCP

This is a new development probe on owned procedural content. It does not restore
or replicate the licensed-video UDP pilots. No learned policy acts, no model is
fitted, no native counterfactual label is generated, and nothing is promoted.

## Why this path

The cloud machine has native Chromium, Node and VP8, but its managed browser policy
disables non-proxied UDP. An authenticated localhost TURN/TCP server provides the
supported proxied route without changing that policy. TURN accepts only loopback
clients/peers; native media then crosses the original owned UDP bottleneck code.
Native ICE gathering and a nine-second technical smoke passed with actual encoded
payload and timestamped BWE. That smoke's scene/seed are excluded from the study.
Only connectivity, counts, counter support and replay were inspected, not quality.

TURN/TCP changes transport dynamics. This cannot validate the old simulator
forecast or stand in for native UDP, licensed content or real network conditions.
Its purpose is to obtain the factual sender/encoder history missing from compact
reports and verify the measurement path before more modelling.

## Fixed before the sessions of record

`configs/native_turn_probe_v1.json` pins the collector, page, sampler, meter,
sidecars, source/marker implementation and analysis code. Register this snapshot
before capture. Original native files and recipes remain unchanged.

- Four scene seeds (101–104) under the new deterministic `owned TURN` drawing
  recipe; these are four procedural content settings, not independent licensed
  titles or a representative corpus.
- Two schedules, each 18 seconds in three 6-second phases: steady 4 Mbit/s room,
  and 1.2 → 0.35 → 1.2 Mbit/s. One machine, 25 ms one-way propagation and a
  30,000-byte drop-tail bottleneck, copied exactly from the existing relay.
- Two repetitions, sixteen fresh peers, in a seeded shuffle. The unmodified
  native instrument assigns {0.65, 0.85, 1.05} × current observed BWE, independently
  with known probability 1/3, for six holds of 3 seconds after acknowledgment.
  Its cap domain remains 150–4,000 kbit/s. Aliased/clipped actions stay recorded.
- The browser's own sender/receiver, VP8 encoder, native scalar cap getter/setter,
  and unmodified identity encoded-payload meter provide the measurements. No
  receiver/schedule/capacity oracle chooses the action; there is no neural actor.
- Record every causal sender sample, auxiliary encoder fields, actual pre-RTP
  encoded-frame bytes, native acknowledgment/readback, frame source identity and
  received sampled RGB/timing outcomes. Source pixels are auxiliary diagnostics,
  never learned-policy inputs in this probe.

## Analysis

Verify raw SHA-256 seals, source identities, every sampler decision by independent
Python replay, encoder sidecar clocks and same-snapshot counters, monotonic encoded
event totals, six assigned holds and native localhost path/capacity checks.

For each assigned hold, retain actual encoded payload rate in the predeclared
1.8–2.6-second window after acknowledgment, normalized by the BWE that based the
request. Incomplete windows are explicit; zero output and aliases are not removed.
Report counts and descriptive means per ratio. There is no powered causal effect
test or state×action model qualification with four procedural settings.

Also retain on-time request counts per factual hold under the existing 150 ms
capture-request-to-pixel-readback criterion. Terminal requests whose deadlines
exceed cutoff are censored irrespective of observed outcome. Missing/unknown
markers do not become successful deliveries. Paired sampled RGB-PSNR is a codec
proxy, not human QoE; this probe makes no controller-quality comparison.

At least 95% known-marker coverage is an observability diagnostic, not a safety
guarantee. All failed, censored and weak-response cases remain. No result here
can promote a controller or revise a frozen model. A qualified dynamics repair
still needs explicit development fitting and new blind native validation.

## Storage and reproduction

Sixteen peers are projected at under 200 MB; budget 400 MB externally. Raw captures
remain in a bounded external working directory, with compact reports in Git. No
raw bytes are pruned or claimed backed up before a verified private archive.
Coturn 4.6.1 and its missing libraries were downloaded from permitted official
Debian hosts, SHA-256 verified and unpacked without root or system changes.
Credentials are ephemeral localhost test credentials, not account credentials,
and are never included in reports or Git. Browser policies are preserved.

Use the verified external TURN runtime through `RLCD_TURN_BINARY` and its local
library selector. Both capture and report outputs must be fresh. Commands and
runtime/package provenance are recorded with the completed report.

## Results

Pending the registered capture. The technical smoke is not a session of record.
