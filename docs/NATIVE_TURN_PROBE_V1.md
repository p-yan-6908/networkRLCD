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

The registration was committed as `d952e9a` before capture. All **16/16 peers**
completed without failures or retries: **96 assigned holds, 2,832 sender samples,
8,669 encoded frames**. All windows complete, no clipped/aliased assignments, and
known-marker coverage is 100% in each session. Descriptive actual payload rates:

| Assigned BWE ratio | Assigned/complete holds | Mean actual payload / assignment BWE |
| ---: | ---: | ---: |
| 0.65 | 37 / 37 | 0.580 |
| 0.85 | 34 / 34 | 0.721 |
| 1.05 | 25 / 25 | 0.881 |

These unbalanced IID counts and pooled means are observability evidence. They are
not the registered N1 effect, a state-conditioned causal value, a safety estimate,
or evidence that choosing one ratio improves delivered QoE. Each randomized hold's
factual delivery count is retained, but no QoE effect test or model fit is made.

Independent post-capture verification reconstructs all 2,832 causal sixteen-field
sender vectors and pre-RTP snapshots from raw counters/encoded events, in addition
to the original assignment, cap-readback, sidecar, marker and RGB replay. Optional
RTT is present in 2,625 samples; missing observations remain explicit. Actual
target, QP, RTP/header/retransmission bytes and encoder timing are recorded, but
counter presence does not establish semantic usefulness: e.g. the browser reports
`totalEncodedBytesTarget` as zero. Eight semantic forgeries against an actual peer
are rejected even after recomputing their seals. All registered source hashes and
original native experiments remain unchanged.

### Preserved bookkeeping defect and prospective correction

The stronger packet audit initially rejected closing-ledger equality. The V1
collector records that ledger before fetching browser-version metadata and
stopping the relay timer. Across all peers the immutable logs retain 10–36 extra
empty service ticks. A read-only adapter identifies the exact closing-ledger
prefix, runs the unchanged FIFO auditor on it, and independently checks every
remaining tick's monotonic timing, capacity budget and zero queue/service. The
full **617,496 raw events** are accounted for; no suffix adds packets or byte
service. This is a documented post-capture audit, not a repaired raw seal or
unqualified original-auditor pass.

`turn_probe_v2.mjs` prospectively stops packet/timer production before taking the
closing ledger. One separate excluded technical peer (scene 9001) verifies that
correction with 37,630 raw events, six holds and **zero** trailing ticks. The V1
collector, protocol and sixteen sessions of record are preserved. Neither
technical smoke enters the table or any efficacy estimate. A future study must
register the new collector hash before capture.

### Reproduction and retained evidence

Compact reports, independent audit, semantic-forgery receipt, package provenance,
technical registrations and raw-file inventory are under
`reports/native-turn-probe-v1`. The first registered trial, selected without
reading outcomes, supplies `figure/trajectory.pdf`: BWE, requested cap, native
target and causal trailing encoded rate are separate quantities. The figure is
illustrative, not a fitted dynamics model.

```sh
# After configuring the verified external TURN binary and local library path:
uv run --frozen python -m media_rl.native_turn_probe capture \
  --spec configs/native_turn_probe_v1.json --out /external/fresh-native-raw
uv run --frozen python -m media_rl.native_turn_probe analyse \
  --capture /workspace/.cache/networkrlcd/working/native-turn-probe-v1 \
  --out reports/fresh-native-turn-report
uv run --frozen python -m media_rl.native_turn_audit \
  --capture /workspace/.cache/networkrlcd/working/native-turn-probe-v1 \
  --compact reports/native-turn-probe-v1 --out /external/fresh-native-audit.json
```

The inventory covers approximately 230 MB of fresh native/synthetic raw evidence
and excluded technical captures outside the project. Private archive access is
still unavailable; no bytes have been uploaded, verified remotely or pruned.
Original licensed-video raw history still needs the targeted pinned restore.
The fresh native path now works, and the next uncertainty is whether its observed
estimator/encoder dynamics and action-dependent value generalize beyond four
procedural settings and this TURN/TCP transport. No real-network validation or
controller promotion follows.
