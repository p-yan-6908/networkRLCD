# M9: instrumentation-limited phase-state validation

Scientific registration: `96ada5a290b3807629bf28bf5d74183aff35a9c3`.
The two instrumentation originals qualified. All **64/64** validation originals
sealed, but only **62/64** met the registered technical gate. The scientific
comparison is **unestimable**. No phase-state prediction, later-settling label,
conditional residual, bitrate action effect or controller was evaluated.

## Exact failure

| Original | Content / prefix | Current service | Main-phase gap | Limit |
|---|---|---:|---:|---:|
| m9-phase-v-020 | Volga / ascending |0.5Mbps|301.2ms|250ms|
| m9-phase-v-026 | Kampar / descending |0.5Mbps|296.8ms|250ms|

Each original had one excessive gap and no invalid/nonpositive BWE samples. The
gaps occurred at main-phase86.880..87.181s and55.143..55.440s, respectively.
Counts were856 and858 samples (registered minimum792). The gap criterion alone
failed. No sample was interpolated, omitted, replaced or accepted at a wider gap.

All64 passed full and beginning clocks, exact native1200kbps initialization,
TURN/TCP, unchanged managed-policy hashes, fixed4Mbps cap/jitter0 readback,
media progression, exact service commands/source replay and terminal cleanup.
Maximum full held-out width was1.468ms; beginning3.021ms, both below50ms.
The common-probe group gate correctly also failed the two blocks containing
unqualified originals. A sealed capture is not a qualified scientific original.

## Frozen design and scientific limit

The64s common-service horizon remains the prospectively frozen4×16s M8 rise-t90
envelope. B0, D1 and the single P2 rule, first-tag selection, future calipers,
drift, coverage, range/SD/overlap and repeatability requirements are unchanged.
The explicit inherited H1/probe veto is preserved. Neither the original phase
comparison nor a revised state is tested on these captures. M9 supplies only
instrumentation development evidence; it does not show that phase information
is irrelevant, that later settling is absent or that a compact state fails.

The source sampler waits100ms after its preceding processing/getStats cycle.
The saved metadata identifies long observation intervals but lacks a separate
getStats-request timestamp or main-thread scheduling delay. It therefore cannot
attribute these gaps to garbage collection, getStats, rendering or host pauses.
Their excess above the nominal100ms period is201.2ms/196.8ms. This motivates a
prospective denser actual-observation/anchored-scheduling qualification, with
request/response/deadline timing recorded. It does not motivate relaxing250ms,
carrying values forward, changing state thresholds or a longer conditioning wait.

## Preservation and next step

All66 originals and technical failures are retained. All1471 tracked files at
completed M8 and9076 members of the six prior pinned evidence archives were
rehashed unchanged. Both old successor allocations remain untouched. M5's causal
history result, M8's asymmetry and every prior frozen negative result remain intact.

Preregister an instrumentation-only sampler qualification, keeping the same media,
inputs, clock/TURN/readback/cleanup gates,250ms actual-observation limit and64s
common-service observation horizon. Any state-validation successor must have new
original IDs, remain untouched until that qualification passes, and retain the
same state predicates and coverage/repeatability gates. Bitrate actions and
learned control remain closed. Do not estimate residual history effects from M9.

- [Frozen plan](NATIVE_PHASE_STATE_M9_PLAN.md), [inherited-gate clarification](NATIVE_PHASE_STATE_M9_INHERITED_GATES.md).
- [Exact instrumentation diagnostic](../reports/native-phase-state-m9-instrumentation-failure.json), [technical gate](../reports/native-phase-state-m9-validation-gate.json).
- [Preservation audit](../reports/native-phase-state-m9-preservation-audit.json), [private archive receipt](storage-receipts/native-phase-state-m9-20261015-01.json).
