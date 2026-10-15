# M7R: fresh state-creation validation after a scheduler-only repair

Registration: October 14, 2026 (America/Toronto). Parent M7 result:
`85fd656a39cd7deb9582fdc3bac953beecd78cc0`. This registration supplements and
incorporates the frozen [M7 design](/workspace/networkRLCD-a135/docs/NATIVE_STATE_CONDITIONING_M7_PLAN.md).
All numerical scientific rules, stages and counts are identical. M7 itself is
closed as instrumentation limited, its four failures archived and its 128
validation sessions untouched. No M7 data are pooled with M7R.

## Only intervention implementation change

M7's single timer call sometimes returned 0.1–0.7ms before its deadline, violating
the frozen not-before command/release gate. M7R re-reads the monotonic browser
clock after every return and yields again until the original deadline arrives:

```javascript
const deadline = start + elapsed;
while (performance.now() < deadline)
  await sleep(Math.max(1, deadline - performance.now()));
```

This repairs execution of the registered schedule. It changes no deadline,
upper timing bound, feedback input, formula, gain, rate limit, service bound,
target, caliper, conditioning duration, feedback-off duration, landmark, BWE
eligibility, state definition, count, repeatability/overlap threshold or outcome
definition. Existing clock, initialization, TURN/TCP, managed-policy, readback,
media-progression and exact cleanup gates are unchanged.

The reproducible builder verifies frozen M7 source hashes and copies the same
gate implementation and numerical `DESIGN` object. Identifiers, source hashes,
randomization namespace, parent inventory and seeds are new; the two verified
60s licensed derivatives are reused byte for byte, without new acquisition.

## Fresh panels and fixed decision

Before any M7R native session, seal and commit a fresh four-original feasibility
panel (two extreme targets × both prior histories, same reused development
content/profile) and a new untouched 128-original validation panel (two contents
× two measured-source families × four target regions × two histories × four
repeats). Seeds are 20261125/20261126; identifiers begin `m7r-`. M7 and M7R raw
roots and all session inventories are disjoint.

Complete all four feasibility originals before support inspection. The **exact
M7 feasibility gate** decides whether to open validation. If it fails, stop M7R
and retain the 128 untouched registrations. Do not tune this recipe on its
feasibility telemetry, substitute a more favorable landmark, or run the panel
anyway. Any later changed recipe requires a different prospective design.

Passing feasibility is insufficient. Only all-gate success on all 128 fresh
validation originals can establish reproducible native common support for
these conditioned contexts. Preserve target range ≥1 octave, sample SD ≥0.35,
cross-content/family range overlap ≥0.5, full-repeat spread/W-infinity/actual-
census distance ≤0.25, ±0.125 target membership and four original members per
history. Both the instantaneous BWE baseline and sustained causal-history state
are reported. No added state representation is evaluated on M6R validation.

M5's history result is unchanged; M6R remains a prospective coverage failure.
Constructed prefixes, synthetic conditioning and original measured-source
probes remain labeled separately. Reused productions/profiles and two bundles
inside one measurement program do not become independent population evidence.
No action stage, QoE analysis, predictor fitting or controller promotion exists.
V13 actions remain closed. Every original failure is retained, sealed, privately
archived and freshly checksum-verified. The combined new M7/M7R raw/staging/
fresh-verification/derivative footprint stays below the 3GB incremental budget.
