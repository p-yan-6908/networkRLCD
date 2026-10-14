# M2 result: no qualifying measured-network startup recipe

M2 was preregistered at **`b704c5a`** before capture. The two synthetic
manipulation checks and all **32 original randomized mechanism sessions**
completed, with no replacements, changed thresholds or extended conditioning.
There were no capture failures. The instrument checks confirmed actual
native initial BWE of exactly 300,000 and 1,200,000 bps, beyond merely
accepting the SDP parameters.

The complete mechanism panel did **not** qualify: all 32 passed the inherited
native support/conditioning, TURN/TCP, clock, exact replay, readback and cleanup
checks, but **31/32** passed the additional frozen initialization check.
Only **four of eight** factorial contexts met the registered full four-repeat
spread ≤0.25 octaves and all session gates. Neither initial target qualified
the **original measured history for both clips**. The prospectively registered
full measured-support replication was therefore **not prepared or run**.

V13 remains a repeatability/common-support failure; its 64 action sessions
are unrun. M1 remains a separate positive synthetic development check. M2
does not establish reproducible native common support, causal action value,
delivery/QoE benefit or controller superiority. No controller was fitted,
tuned or promoted, and no prior source was pooled as independent evidence.

## What the diagnosis could quantify

The preserved expanded V13/M1 support diagnosis is documented separately in
`NATIVE_BWE_MECHANISMS_M2_DIAGNOSIS.md`. It verified both entire session
inventories before projecting baseline sender and clock-aligned pre-decision
transport/queue variables. Exact source arrays and service timing did not
show a gross replay fault: V13's largest tick error was 2.764 ms, and failed
contexts differed in cumulative service exposure by at most 0.001724 octaves,
versus final BWE repeat differences of 0.271–0.447 octaves.

All first V13/M1 BWE readings were 300 kbps. Their early peaks weakly tracked
terminal deviations (r=−0.199), while late BWE history (12–16 s r=0.770) and
queue history (12–18 s r=0.763) tracked them more strongly. Observed content
main effects contributed only 0.0097% of the deliberately wide total BWE SS;
profile selection contributed 98.609%, while repeat deviations contributed
1.123%. These are finite-panel associations/decompositions, not additive
causal shares. Internal GCC probe state is latent, and queue/demand/BWE
affect each other. Every association and sensitivity is preserved, not just
the largest ones.

## Direct randomized support experiment

M2 crossed two clips, early history, initial target and four fresh repeats.
For the history manipulation, the first twelve measured rates were replaced
by a flat **1.429 Mbps** prefix with exactly the same first-block service
integral (17.148 Mbps·s). Bins 12–35, all phase lengths, the 18-second decision
window and every original eligibility/technical threshold remained identical.
The flattened prefix is **hybrid synthetic development**, not a fully measured
trace. All 32 sessions used a common 4 Mbps preconnection/measurement ceiling;
the earlier V13/M1 temporary 300 kbps preconnection cap was not retained.
That common startup change is not separately randomized against V13.

| Content | History | Initial target (kbps) | Qualified sessions | Full spread (octaves) | Sample SD (octaves) | Context |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Kampar | Original measured | 300 | 4/4 | 0.36974 | 0.17354 | Fail |
| Kampar | Original measured | 1,200 | 4/4 | 0.17636 | 0.07948 | Pass |
| Kampar | Hybrid flat prefix | 300 | 4/4 | 0.04471 | 0.02029 | Pass |
| Kampar | Hybrid flat prefix | 1,200 | 4/4 | 0.43673 | 0.20775 | Fail |
| Volga | Original measured | 300 | 3/4 | Unqualified | Unqualified | Fail |
| Volga | Original measured | 1,200 | 4/4 | 0.56119 | 0.25944 | Fail |
| Volga | Hybrid flat prefix | 300 | 4/4 | 0.02101 | 0.00896 | Pass |
| Volga | Hybrid flat prefix | 1,200 | 4/4 | 0.03949 | 0.01664 | Pass |

Every original state and all registered six pairwise differences for complete
contexts are in `reports/native-bwe-mechanisms-m2-summary.json`.
The support-only figure is `reports/native-bwe-mechanisms-m2-repeatability.png`.
No four-repeat spread was replaced by an average of favorable pairs.

The unqualified run was **`m2-r1-c01-hm-i300-s0-support`**. SDP requested/read
back 300 kbps and the ceiling read back 4 Mbps, but both the pre-measurement
and first measured native BWE were **301,000 bps**, outside the registered
300,000 ±1 bps initialization requirement. The ordinary BWE history,
transport, clock and cleanup still passed. This small live estimator update
is retained as a qualification failure; the tolerance was not relaxed.
All Volga factorial contrasts are gated off, rather than deleting that run
or treating its failure as a treatment/quality result.

## Uncertainty and mechanism interpretation

The preregistered Kampar support-state mean contrasts are estimable from all
four complete randomized blocks; Volga's are unestimable under the registered
qualification rule. Mean contrasts are in **BWE octaves**, not PSNR or action
value. The reference intervals below are exact **sharp-null randomization
reference intervals**, not confidence intervals for a population effect.

| Kampar support-state contrast | Equal-block mean (octaves) | Sharp-null reference 95% | Exact two-sided p |
| --- | ---: | --- | ---: |
| Flat prefix minus original history | 0.00221 | [−0.08228, 0.08228] | 0.9141 |
| Initial 1,200 minus 300 | 0.05757 | [−0.12815, 0.12815] | 0.4766 |
| History×initialization difference of differences | 0.11390 | [−0.24409, 0.24409] | 0.4599 |

Main-factor references enumerate 256 conditional label allocations. The
interaction reference enumerates 1,296 equivalent balanced partitions under
the **joint no-recipe-effect sharp null**; it is not an isolated interaction
test in the presence of unknown main effects. All block contrasts, reference
SDs, assignments and permutations are retained.

The observed Kampar repeat-variance ratio for flat versus measured history
at the 300 kbps target was **0.01368**; for 1,200 versus 300 kbps on measured
history it was **0.20975**. These are descriptive four-repeat variance ratios,
with little precision and no population CI. Raising the target then failed
Kampar under the hybrid prefix and failed Volga under full measured history.
Thus an initial BWE scalar alone is insufficient to ensure repeatability,
and a recipe that passes one content/context cannot be promoted across the
panel. The randomized design provides controlled comparisons of history
and initialization sensitivity. Stable variance reductions and causal shares
of queue, workload, probe phase and scheduling noise remain unestablished
with these four-repeat samples.

Pre-decision RTT, sending/encoding/poll timing, queue/service and forwarding
timer histories for every gate-qualified run are preserved in the raw
archive's `mechanism_support_projection.json`. All unqualified captures remain
in the complete gate/inventory. No causal mediator shares are assigned, no
binary BWE split is introduced and no timer or source selection is retuned.

## Decision and remaining uncertainty

The original measured history has no candidate satisfying both content
contexts' strict four-repeat gate. The registered candidate rule therefore
returns **null**, closing M2 before its conditional 32-session replication.
The repeatability failures alone reject both targets: 300 kbps fails Kampar,
and 1,200 kbps fails Volga under the original measured history.
Neither a synthetic prefix nor Kampar's isolated measured/1,200 result can
supply native common-support qualification. The old V13 common-support
failure remains unresolved; no controller or frozen action stage opens.

The remaining development question is the reproducibility of the **full
estimator/feedback state**, rather than its initial scalar or cumulative
trace capacity alone. A next experiment should observe native probing,
RTCP/pacing timing and workload more directly, or preregister a richer
measured pre-action support context on reused sources. It must distinguish
those mechanisms prospectively and retain the existing eligibility,
repeatability, common-support, clock, TURN/TCP, readback and cleanup standards.
Another longer conditioning wait, favorable pair selection or target retuning
is not justified by these results. New untouched independent validation is
still required before interpreting a conditional action effect.

## Integrity, transport, clocks and private preservation

All **1,344 sealed mechanism-session files** were verified before support
analysis. All 32 actual-run clock maps covered four held-out markers, with
maximum interval width **4.203 ms** under the original 50 ms limit. TURN/TCP,
managed browser policy, zero jitter, exact rates and terminal conservation
qualified in every original session. Zero bitrate treatments were assigned.
Quality/frame-deadline, receiver-feedback, encoded-frame meter and per-hold
delivery/QoE/cost outcomes remain unopened.

- Main protocol SHA-256:
  `b2f3babb2f91818544072d821d2103bf23ec68b5ed0e0564f524c09b208bb83b`.
- Main capture index SHA-256:
  `4ebc1a4b6b2b3a74eb3c836d7aac54c1197da9a5bdad3a67b5556ab8ce146d7d`.
- Complete qualification/summary:
  `reports/native-bwe-mechanisms-m2-mechanism-gate.json` and
  `reports/native-bwe-mechanisms-m2-summary.json`.
- Main private namespace `native-bwe-mechanisms-m2-20261014-01`, pinned
  revision **`272aecdf4403e2ba173fd05b493b865c40de794f`**. Fresh remote
  verification covered all archive objects and **1,416 files**, including
  failed qualifications and support projections.
- Instrument namespace `native-bwe-mechanisms-m2-instrument-20261014-01`,
  pinned revision **`71787a08f8c54cce86af07ca96df5e1efcf16a55`**, with all
  **94 files** freshly verified. Its archive CLI registration argument had
  a metadata typo; the original receipt is retained byte-for-byte and
  `docs/storage-receipts/native-bwe-mechanisms-m2-instrument-20261014-01-registration-corrected.json`
  supplies the audited correct registration commit. Remote data, revision,
  protocols and archive/file checksums were unchanged.
- The repository remains below 10 GB. Raw evidence and licensed originals
  remain external; **zero local files were deleted**. All 1,266 files at
  `7427f48`, including V13/M1 and prior failed/frozen studies, remain unchanged.
