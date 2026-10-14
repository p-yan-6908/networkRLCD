# M3 result: prefix-history inference is unestimable

M3 was preregistered at **`f43550787386a4f5bfbaf2329f02b43cbf05a154`**,
before any new capture, from M2 result commit `7cf6ae5`. All **84 original
attempts** are preserved: **83 sealed captures and one platform-interrupted
failure**, with zero replacements. The frozen overall gate qualified **77/84**.
Both content-specific all-42 gates failed. Every registered prefix-effect and
convergence comparison is **unestimable**. No randomization test, bootstrap
effect estimate or support-state predictor was fitted.

This is a **qualification failure**. It supplies no estimate of the causal
prefix effect, no evidence of distribution convergence, and no negative test
of history dependence. M2's measured-history repeatability result remains
unchanged. V13 actions stay unrun, V10 stays closed, and no controller was fitted,
tuned or promoted.

## Frozen intervention and separation

M3 ordered the first ten rates of the reused
`att_lte_driving_2016-uplink-lower` profile ascending versus descending. The
prefixes have the same sample multiset, ten-second duration and **14.112 Mbps·s**
service integral. From bin 10 through bin 35 both arms use the exact original
measured sequence. Content is identical within each adjacent randomized pair.
Both arms request native initial BWE **1,200,000 bps**, with a common 4 Mbps
encoder ceiling and unchanged native VP8, TURN/TCP, jitter and cleanup recipe.

Twenty-one fresh pairs per content were registered using seed 20261108. This
was the smallest integer reaching the 80% normal location-power planning target
for a 0.25-octave shift using M2's largest qualified development SD. That planning
calculation does not supply power after qualification fails, or guarantee power
for arbitrary distribution alternatives.

The two Kampar/Volga clips and LTE source are **reused development sources**.
The prefixes are constructed permutations; the later service is a common
original measured suffix. These captures are neither an untouched independent
content/network validation nor evidence of broad network generalization.
No prior or synthetic study was pooled as a new independent source.

## Original inventory and qualification

| Content | Original attempts | Sealed | All session gates | Complete suffix-qualified pairs | Primary / later windows |
| --- | ---: | ---: | ---: | ---: | --- |
| Kampar | 42 | 41 | 36/42 | 16/21 | Unestimable at 18, 24, 30 and 36 s |
| Volga | 42 | 42 | 41/42 | 20/21 | Unestimable at 18, 24, 30 and 36 s |

The ordinary support, bidirectional native media, authenticated relay-only
TURN/TCP, exact rate replay, 4 Mbps/zero-jitter readback and terminal cleanup
checks passed in **all 83 sealed sessions**. All four registered eleven-sample
BWE histories met their original eligibility/span/gap bounds in those sessions.
Clock qualification passed in **78/83**. The extra actual-native initialization
check passed in **82/83**, giving 77 fully qualified sessions after their union.
The interrupted attempt has no completed technical qualification.

The all-originals rule was enforced separately for each content. Neither the
36 qualifying Kampar sessions nor the 41 qualifying Volga sessions supplies a
permitted subset comparison. The original 0.25-octave full-repeat spread and
finite-panel convergence screens were not evaluated on reduced samples. The
summary's `convergence_passed=false` fields reflect unestimability, not an
observed causal difference or measured failure to converge.

The exact-randomization references were never generated. The conditional
raw-BWE versus augmented-history prediction analysis was **gated off**. Thus
M3 cannot establish either that raw BWE is causally sufficient or that a richer
state has passed the registered development-candidate requirements.

## Clock failures: training-bound coverage at the first phase

Every clock failure was at held-out **`m0003`**, the first phase marker. The other
three held-out markers were covered. All maximum interval widths remained
below the unchanged 50 ms limit; the maximum over all sealed sessions was
**4.611009 ms**. The failures concern the required **every-training-feasible-map
coverage with 1 ms tolerance**, rather than excessive interval width.

| Original trial | Held-out coverage | Maximum width (ms) | Miss beyond the existing 1 ms allowance (ms) |
| --- | ---: | ---: | --- |
| `m3-r04-c00-s0-support` | 3/4 | 3.806444 | Late 0.855215 |
| `m3-r07-c00-s1-support` | 3/4 | 3.562699 | Late 0.071162 |
| `m3-r10-c00-s0-support` | 3/4 | 3.180935 | Late 0.004847 |
| `m3-r10-c00-s1-support` | 3/4 | 2.787534 | Late 0.214524 |
| `m3-r14-c00-s0-support` | 3/4 | 3.343264 | Early 0.358390 |

Outcome-free geometry diagnosis found a nonempty joint affine feasible polygon
using all twelve marker exchanges in **every one of these five sessions**.
That means the observed exchanges remain compatible with an affine clock map.
The training-only feasible envelope nevertheless includes maps that miss the
held-out first-phase exchange beyond the registered allowance. This supports
investigating tighter independent training brackets around the first phase;
it does not demonstrate physical clock drift or identify a unique timing cause.

Using held-out markers to narrow the map retrospectively would change the
validation rule. **Zero sessions were requalified.** Even the 0.004847 ms excess
remains a failure. Four failures occurred before the platform restart, one
after it. Their occurrence cannot be assigned solely to that restart. All five
were Kampar captures; this is a descriptive workload/context difference, not a
causal estimate of a content effect.

## Initialization failure: SDP did not pin the actual estimator

Original Volga trial **`m3-r01-c01-s1-support`** requested and read back
1,200 kbps in both SDP start parameters, with the correct 4,000,000 bps encoder
ceiling. Actual native BWE before measurement and at its first measured
reading was **5,358,769 bps**, outside the frozen **1,200,000 ±1 bps** requirement.
The pre-measurement native sample was at 1,218.8 ms; measurement began at
1,238 ms. Three frames had already been encoded. The other **82** sealed
sessions read back exactly 1,200,000 bps at these initialization checks.

The unchanged recorder has live media and a 5 Mbps pre-trace bootstrap before
the initial snapshot. A probe/feedback update during that setup is a plausible
explanation for the estimator already having evolved, but that mechanism was
not separately randomized. The failure preceded the prefix intervention and
the platform restart. It is preserved as an initialization failure; neither
SDP acceptance nor later eligible BWE overrides it.

## Platform interruption and original-order recovery

The runtime restarted from environment specification 132 to 133 after 49
original sessions had sealed. The original capture runner/native processes
were terminated. Attempt **`m3-r12-c00-s1-support`**, Kampar descending prefix,
had created 27 source/setup files and no completed telemetry/seal. All original
files were individually hashed and retained. No clock, ICE, media, readback
or drain result is asserted for that attempt.

The operational recovery was frozen separately at
**`c595edce7c79d7284af7f97d05f2006699f91029`** before another capture. It sealed
the interrupted original as failed and completed exactly the remaining **34
untouched original IDs**, in their original order, using the unchanged recorder
and 110-second timeout. The original 49 seals stayed unchanged. No native
processes survived into the resumed captures; runtime and source hashes still
matched the scientific registration. No scientific protocol, gate, threshold,
allocation, hold count, content or trace changed.

The original configuration version and enforced network policy stayed the
same. HTTPS and authenticated private-dataset access on `huggingface.co`
returned HTTP **200** again after restart. `HF_TOKEN` availability was checked
without logging its value. This interruption was not an archive-access failure
or a treatment/QoE outcome.

## Replay fidelity and permitted telemetry

All **83 sealed replays** used all **36 exact registered rates** and the exact
common measured suffix. The maximum Node-domain tick error was **8.493894 ms**
under the original 150 ms limit. This calculation does not require a failed
session's sender clock to be qualified.

For the **36 complete pairs** whose original session and alignment checks
qualified, the largest paired common-suffix capacity-exposure discrepancy over
the registered sender intervals was **0.000366264 octaves**, below 0.01. This
confirms input fidelity for those pairs; it supplies no reduced-sample BWE
effect estimate. Invalid clock sessions have no asserted sender-aligned replay
or relay effect. Queue histories remain descriptive support projections, with
no causal mediator shares, per-hold delivery costs or quality estimates.

## Decision and next development step

The randomized causal history question remains **unestimated**. M3 cannot
settle whether prefix memory persists, whether later distributions converge,
or which support-state representation is sufficient. M2 remains development
evidence of path dependence under accurate replay; M3 adds acquisition-reliability
evidence. All prior freezes and negative results retain their original scope.

The next development step is to qualify a new acquisition version with tighter
independent clock-training brackets around the first phase and a native
initialization snapshot/service-start sequence that precedes estimator evolution
during bootstrap. Register and check those instrument changes prospectively,
preserving held-out coverage, width, timestamp tolerance, actual initialization,
TURN/TCP, readback, cleanup and support requirements. Then freeze a fresh
prefix-intervention panel before examining its later BWE. Another longer wait,
retrospective all-marker fit, dropped session or relaxed tolerance cannot
supply the missing M3 comparisons.

Any richer-state evaluation remains conditional on a qualifying causal history
result. Native common support and independent conditional action value remain
requirements before returning to learned control. M3 opens no V13 action stage
or controller work.

## Integrity, storage and reproducibility

All **3,516 session payload files** across the successful and failed seals,
plus their 84 manifest hashes, were verified before permitted telemetry decoding. Reporting and gate
diagnosis add **zero inferential tests** and change no qualification decisions.
Frame quality, deadline/QoE, receiver-feedback, action cost and controller
outcome analyses remained unopened; zero bitrate treatments were assigned.

- Protocol SHA-256:
  `e3a2791090e7a495609895a76af1bfced1c3554fb6fb77ce70289e8db78f39f0`.
- Capture index SHA-256:
  `77ae45aa4634618fd7ea0f967a9fdd52186663f6434131346a34968df65ba62a`.
- Main gate and summary: `reports/native-prefix-memory-m3-gate.json` and
  `reports/native-prefix-memory-m3-summary.json`.
- Exact failure diagnosis: `reports/native-prefix-memory-m3-gate-diagnosis.json`.
- Source/service figure: `reports/native-prefix-memory-m3-service.png`.
  The distribution figure explicitly marks all eight windows unqualified.
- Private namespace **`native-prefix-memory-m3-20261014-01`**, immutable revision
  **`ecdf7f14bfaef244c8572b49f1ee1641da52531e`**. Fresh downloads verified all
  **four objects** and every one of **3,708 files**, including all failures,
  original panels, recovery provenance, logs and frozen/reporting source copies.
- Receipt: `docs/storage-receipts/native-prefix-memory-m3-20261014-01.json`.
  All raw evidence and licensed originals remain external. Zero evidence files
  were deleted. The project remains below 10 GB and the new task's bounded
  capture/archive staging stays within its 1 GB plan.
- Every **1,289 tracked files at `7cf6ae5`** remains byte-for-byte unchanged.
  The M3 scientific registration and operational recovery files also remain
  unchanged. A clean result commit preserves the complete qualification failure.
