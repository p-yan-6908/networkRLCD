# M7: prospective native state creation with controlled network conditioning

Registration: October 14, 2026 (America/Toronto); anchor `6dc05b5`.
The configuration, implementation, source manifest and all stage panels must be
sealed and committed before the first native session. Their hashes determine
the study; this document may not be changed after capture begins.

## Question and evidence boundary

Can a fixed, causal network-service conditioning procedure create predefined
observable BWE regions that reproduce across different early histories, and
remain repeatable after feedback is removed and common measured service begins?
This is a support-only feasibility/validation study, not a fitted bitrate
controller, an action-value assay, or a comparison of QoE. There is no action
stage in this registration.

M5 remains qualified evidence of causal prefix effects under its common suffix,
with content/time heterogeneity and no registered sustained convergence by 36s.
M6R is a prospective coverage failure. Its selected BWE/encode-history state
adds no matching discrimination, and sparse instantaneous BWE overlap binds.
No M6R validation capture is opened for another state search. Only its frozen
summary and archive inventory are used. M3, M4/M4R, M5, M6/M6R, V13/M1/M2 and
every earlier freeze remain unchanged. V13 actions stay closed.

The independent units here are fresh native browser/transport/queue contexts.
The licensed productions and measured trace bundles are reused sources.
Two bundles/families are nested in the same Mahimahi measurement program;
profiles within a bundle may overlap. Repetition does not create independent
content or measurement programs, and no pooled population/general-network
estimate is intended.

## Inputs, predefined regions, and fixed intervention

Two retained Commons productions, Kampar (CC BY 4.0) and Volga (CC BY 3.0), have
new verified first-60s derivatives. The source manifest preserves original
hashes, licenses, credits, provenance, and exact transcode commands. Old 45s
derivatives are untouched. No looping, new downloads, or media in the archive.

Define `x = log2(native BWE / 500000)`. The four target centers are exactly
`0, 0.5, 1, 1.5` (500, 707.107, 1000, 1414.214 kbps). Every region has the
unchanged ±0.125-octave BWE caliper. Within each of the two measured families,
the four source profiles are sorted only by their already frozen input-only
geometric capacity hint, ties by profile ID, then assigned the four centers in
ascending order. No observed BWE or action/outcome is used for this assignment.

Every fresh native run has three phases:

1. **10s prior history:** the assigned original profile's first ten one-second
   rates, ascending or descending. Both orders have the identical multiset and
   service integral. No scaling, clipping, wrapping or interpolation.
2. **32s conditioning:** owned symmetric service starts at the target BWE in
   Mbps. At fixed browser times +1 through +26s, use all available positive,
   valid native BWE samples in the preceding 1000ms (minimum seven; gaps ≤250ms).
   Let `e = target_x - mean(log2(BWE/500000))`. Set
   `service_new = clamp(service_old * 2**clamp(0.25*e, -0.125, +0.125), 0.2, 5)`
   Mbps. Gain, step limit and service bounds are fixed engineering choices,
   with no fitted parameters or data-dependent tuning. A fresh service command
   must be ≤150ms late and acknowledged with exact service readback in ≤100ms.
   At +27s, explicitly record feedback off; hold the last service unchanged
   through the end of this phase. No updates after +26s, no readiness-triggered
   extension, no waiting for a favorable state.
3. **12.6s common probe:** original profile bins 10–21, unscaled and in original
   order, at 1Hz; hold the final value for the last 0.6s. This is identical
   across the two histories in each paired context. No feedback during probe.

The inputs must be labeled separately: constructed early permutations,
**synthetic controlled conditioning**, and a **measured-source probe**. Native
RTP/encoder and recorded video do not make the entire service sequence a
measured network. No comparison with synthetic M1 is pooled as native evidence.

Only previous browser-native BWE drives conditioning. Content identity,
prefix identity, trace capacity, relay queue, future observations, delivery,
loss/QoE and receiver pixels do not enter the feedback rule. The sender cap is
always 4 Mbps, receiver target always zero, initial SDP/native BWE exactly
1200 kbps, setup delay zero. This is an experimental network intervention;
it does not fit or promote a deployed controller.

## Fixed support states and timing

Entry is the first eligible 11-sample census whose final timestamp lies at
conditioning +30,000 through +30,300ms. Eligibility remains BWE 240k–3.8M,
all 11 valid, span ≥900ms and consecutive gaps ≤250ms. If absent, the run fails;
do not search other landmarks. The census scalar is mean log2 BWE.

**B0 baseline:** instantaneous native BWE at that census's last sample lies in
the assigned ±0.125-octave region.

**H1 conditioning state:** B0, plus all samples in the preceding 3000ms lie
inside the same region, with at least 27 valid/eligible samples, gaps ≤250ms,
and at least seven samples in each of the latest two one-second intervals.
The absolute difference between the mean x in those two intervals must be
≤0.05 octave. Feedback must have been explicitly off for at least 3000ms before
entry. This tests sustained target occupancy using causally available history;
no encoder or relay-state candidate is selected after seeing data.

Post-release support censuses are fixed at probe +6000…6300 and
+12000…12300ms, using exactly the same 11-sample eligibility. These are BWE
support measurements, not action outcomes. They need not remain in the entry
target region under varying probe service. They must reproduce across fresh
runs and prior histories. Entry elapsed times must agree within 250ms within
each randomized history pair to limit content-time/timing mismatch.

## Stages, original counts, and stopping

All panels for both stages are generated and hashed before either starts.
Prefix order within pairs and validation context order are randomized using
fixed seeds 20261123 and 20261124. Each run gets a fresh browser profile, fresh
TURN process and empty owned queues. No retry/replacement, discarded original,
extra repeat, caliper change, threshold change, alternate state or optional
stopping after inspecting a stage.

**Feasibility: four original sessions.** Reused Kampar content and the M5 LTE
uplink-lower source profile, two extreme target centers (0 and 1.5), both
prefix histories, once each. Complete all four before support inspection.
Every technical gate, both B0/H1 memberships, fixed entry/probe census,
cross-history repeatability and pair exposure/timing check must pass. No
range/SD inference is made from two feasibility targets. Failure closes M7
before validation; its 128 sealed panels remain untouched. Feasibility data
may diagnose the failed recipe but may not be pooled with validation.

**Untouched validation: 128 originals.** Two contents × two measured-source
families × four predefined target/profile regions × two prior histories ×
four fresh repeats. This retains the existing minimum **four members per
history**, unlike a sparse retrospective match. Every original must qualify;
there is no retrospective subset or favorable matching center. H1 membership
therefore retains 100% of B0 if the complete panel passes. The two-repeat V13
repeatability requirement is exceeded, not weakened.

## Unchanged gates and prospective acceptance

- TURN/TCP loopback relay, selected pair nomination/success and positive
  bidirectional transport, unchanged managed browser policy, no bypass.
- M4R exact startup/initialization/25ms observation and ≤250ms gap gates,
  fixed encoder/jitter readback, no assigned bitrate actions, and positive
  encoded/decoded media progression in all three phases.
- M4R 12 original +59 extra clock exchanges, 64 fixed training/7 independent
  held-out markers, plus beginning certificate 35/4. All independent held-out
  clock bounds ≤50ms, tolerance ≤1ms and original slope constraints. Beginning
  coverage is used only at session start, never extrapolated to later windows.
  Feedback uses the browser clock directly. Any relay/source alignment uses
  the actual full-session certificate. Do not infer per-hold relay effects.
- Exactly ten constructed-prefix source ticks and twelve measured-probe ticks,
  original values/order, ≤150ms scheduling error. Conditioning is counted
  separately: one initial setting, 26 exact causal commands and one release.
- Across each prior-history pair, integrate actual common probe service from
  probe +1000ms to +6000/+12000ms using **all** feasible full-session clock
  mappings. Worst endpoint exposure ratio difference must be ≤0.01 octave,
  as in the prefix-memory work. Keep uncertainty rather than selecting a map.
- Exact post-cutoff terminal drain, separate 10Mbps cleanup ≤2000ms, zero queue,
  served=forwarded, no send errors, byte conservation ≤1e-6, cleanup excluded.
- At entry and both probe endpoints, all original values in every target cell
  must have full repeat spread ≤0.25 octave and empirical cross-history
  W-infinity ≤0.25. Every actual value must be within 0.25 of its cell census.
  These thresholds preserve the original repeatability/common-support limits;
  two small empirical distributions cannot establish population equivalence.
- In each content × family validation stratum, the four target census means
  must have range ≥1 octave and **sample** SD ≥0.35 octave. Intersection of the
  four content × family ranges must have width ≥0.5 octave. All four target
  regions and both histories need all four original members. No pooling across
  sources substitutes for a failed cell, family or content.

Only all-gate success in the untouched validation panel establishes native
common support for these conditioned contexts. Reaching a target once, a
pooled mean, a technical-only pass, or feasibility success is insufficient.
No primary causal action interaction, confidence-driven model selection,
predictor or controller fit is registered. B0 and H1 counts and all per-cell
repeatability results are reported, including failures. No binary BWE cutoff
is introduced. A successful panel can justify a separately preregistered
future randomized action assay; this code cannot launch one.

## Preservation, access, and budget

Access preflight records HF_TOKEN availability without its value, HTTPS 200,
authenticated private-dataset 200 at the M6R receipt's revision, and verified
inventory metadata. Runtime hashes match qualified M5, and the managed policy
is unchanged. New raw evidence lives under `~/.cache/networkrlcd/` with a 3GB
incremental working/staging/fresh-verification budget, including new clips.
The project remains below 10GB. All original attempts, failures, clock data,
conditioning readbacks, registered panels and compact gates are sealed.
No archived quality/frame file is opened for this study's analysis.

At completion, upload to a fresh private archive namespace, pin the immutable
revision, freshly download every object and verify every archive member size
and SHA-256. Retain local raw evidence and licensed media; delete zero files.
Rehash every file tracked at the M6R result and every prior M5/M6R archive
member against its pinned inventory. Commit results separately from design.
