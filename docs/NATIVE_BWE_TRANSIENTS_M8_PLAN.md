# M8: native BWE response to controlled service steps

Preregistered October 14, 2026 (America/Toronto), parent
`81be2db9cd1a35a710ce3da6efd604d2badf50e6`. Commit the full plan, executable
instrumentation/analysis, source manifests, panels and successor allocation
before any new native run. No prior frozen file may change.

## Question and boundaries

M7RA is a prospective state-creation failure despite qualified instrumentation.
Its old 128-session panel stays closed. M5's causal early-history result remains
unchanged; M6R is a coverage failure. Do not reopen V13 actions, test new state
definitions on any old validation captures, relax existing state gates, extend
M7RA's schedule or fit a controller. M8 examines fresh support telemetry only.

The questions are the observed delay, rise/fall asymmetry, drift, input-normalized
overshoot, finite-horizon settling and history dependence of native BWE under
known service. A small fixed causal rule is evaluated prospectively against
future support observations. Those later samples are verification labels, never
state inputs. No delivery, QoE, quality pixel, loss outcome or action-value
variable enters the rule, metrics or selection.

This is native Chromium over owned TURN/TCP and a userspace queue, with
**synthetic controlled service**. The two retained licensed productions and one
LTE source prefix/probe are reused. Fresh browser contexts do not make new
content sources or independent network programs. Keep content, prefix, input
order, repetition and plateau separate. Repeated phases and overlapping samples
are nested within their native run; they are not independent samples or sources.

## Fixed, interpretable intervention

Each original lasts nominally 118.6s and uses a verified first-130s, unlooped,
640×360/30fps derivative of Kampar (CC BY 4.0) or Volga (CC BY 3.0). Originals,
credits, licenses and every old derivative remain external and unchanged.

1. **10s early history:** the M5 LTE uplink-lower profile's first ten one-second
   rates, ascending or descending, with identical rate multiset/integral. This
   is a constructed permutation, not a wholly measured network path.
2. **Four 24s plateaus:** exactly one of these predetermined sequences (Mbps):

   | Input order | 0–24s | 24–48s | 48–72s | 72–96s |
   |---|---:|---:|---:|---:|
   | `step_hold_fall_rise` | 0.5 | 1.5 | 0.5 | 1.5 |
   | `hold_hold_fall_rise` | 1.5 | 1.5 | 0.5 | 1.5 |

   There is no BWE feedback or bitrate adaptation by the experiment. At +24s,
   a rise is compared with a no-change control at the same content time.
   Subsequent high/low/high service is common. This distinguishes early
   controlled-service history from current service and separates natural BWE
   drift under a hold from a response coincident with a step. Common fall and
   rise transitions support within-run asymmetry measurements. The 24s horizon
   provides several response/trajectory windows and ≥8s verification after the
   latest selectable entry; it is an identification input, not a longer M7RA
   conditioning recipe. Do not extend a plateau after seeing its response.
3. **12.6s common measured-source probe:** original profile bins 10–21, at 1Hz,
   unscaled/unclipped; final rate held for the last 0.6s. This input is identical
   across history/order within a content/repetition block. It is a provenance/
   alignment check, not an action outcome.

Service commands at +24/+48/+72s are issued after guarded monotonic deadlines,
≤150ms late, with exact applied-service acknowledgement in ≤100ms. A no-change
command is still logged and verified, but does not reset physical service age.
The encoder cap is always 4Mbps, native initialization exactly 1200kbps, receiver
target zero and setup delay zero. Fresh profile, browser, TURN process and empty
queues for each run; no concurrent native captures or reconnect/retry.

## Stages and independence

**Instrumentation: two originals.** Reused Kampar, one ascending-prefix/step
order and one descending-prefix/hold order. Complete both, then require all
technical gates. They qualify the longer recording, commands, clocks and
completion only. Do not estimate response dynamics or select a state from these
two captures. They are excluded from characterization and successor calibration.

**Characterization: 16 fresh originals.** Two contents × two early prefixes ×
two input orders × two fresh repetitions. Each content/repetition is a
randomized four-run 2×2 block. Block and within-block order are frozen by seed
20261132. All 16 original attempts must complete and qualify before analysis.
Retain every failed original; zero retries, replacement traces, substituted
content, favorable subset or optional stopping. Failure is instrumentation
limited, not a response/state result. Two repetitions per factorial cell are
development evidence; they do not replace four-members-per-history validation.

**Successor allocation: 128 untouched originals.** Before M8 begins, assign new
`m9-from-m8-` identities for two contents × two measured-source families × four
profile/target regions × two prefixes × four repetitions (seed 20261133).
This is a new allocation, disjoint from M7RA's permanently closed panel. Its
executable conditioning schedule may be instantiated only by the registered
measurement-based derivation below, then separately frozen/committed before
capture. If no candidate qualifies, keep it uninstantiated and untouched; do not
choose a new duration by inspection. No action stage exists in either study.

## Technical acquisition gates, kept distinct from state gates

- Same binaries, strict TURN/TCP loopback candidate/selected-pair policy,
  bidirectional transport, native media progression, exact 4Mbps/zero-target
  readbacks, no assigned sender actions, unchanged managed browser policy.
- Same startup observability, inactive pre-negotiation encoder, exact first
  native 1200kbps and initialization latency ≤100ms; startup gaps ≤250ms.
- Keep the 12 original/59 extra marker scaffold. Add an independent nine-marker
  bracket at plateau times 12,24,36,48,60,72,84,90s. There are now 128 fixed
  training and **15 held-out** exchanges spread across the actual long session,
  plus the unchanged beginning certificate 35/four. All held-out clock bounds
  ≤50ms, validation tolerance ≤1ms, original affine/slope limits. Never use a
  beginning certificate for late telemetry. State features use browser-native
  timestamps and already received command acknowledgements; relay mapping is
  for instrumentation/fidelity, with all feasible mappings retained.
- Exactly 22 source ticks (ten constructed prefix, twelve original probe),
  ≤150ms timing error. Count synthetic settings separately: one initial plus
  three exact commands, including the no-change control. Map each actual
  application inside its browser request/ack interval with the existing 1ms
  timestamp tolerance. Completion at 96s, ≤250ms overrun; no adaptive waiting.
- Main-plateau sender observation ≥900 samples, all positive/valid, gaps ≤250ms.
  Values outside 240k–3.8M may describe a transient but **cannot qualify a state**.
  This does not change the state-eligibility bounds.
- Common probe exposure difference ≤0.01 octave over probe +1…6/+12s under all
  feasible clock maps. Step-start elapsed spread within each four-run block
  ≤250ms. No per-hold relay effect is estimated.
- Preserve exact post-cutoff terminal drain ≤2s, separate 10Mbps cleanup, empty
  queues, served=forwarded, zero send errors and byte conservation ≤1e-6.
- Verify every sealed member before telemetry projection. The generic archive
  `mechanism_qualification_gate` records acquisition only; a separate settling
  selection decides state/recipe eligibility. An acquisition pass does not
  establish native common support.

## Frozen response definitions

Use `x=log2(BWE/500000)` from native sender observations and known controlled
input history. No model smoothing, interpolated BWE, fitted dynamics or decoder
outcomes. Preserve raw cadence, missingness and censoring.

For each plateau, reconstruct actual service-application bounds with the full
clock map. The pre-step reference is mean x in the **preceding** one second,
ending at the earliest feasible application time (≥7 positive native samples).
The first prefix-to-plateau change is reported separately from transitions
between constant plateaus. No-change controls have drift, not a fabricated
response latency. Use a post-input observation horizon ending at plateau +23.8s.

- **Observed response delay:** first departure ≥0.05 octave in the direction of
  the known input step, sustained for 11 samples spanning ≥900ms. Report the
  onset interval bounded by the last pre-crossing poll, first crossing poll and
  all feasible input times, plus confirmation time. This is an observed native
  threshold response, not an internal estimator timestamp.
- **Input-normalized t10/t50/t90:** analogous sustained crossings at 10%,50%,90%
  of the known log2 service step from that past reference. Report t10–t90 and
  within-run common-rise minus common-fall t50 intervals. Missing crossings are
  right-censored, never replaced with the plateau duration.
- **Overshoot:** maximum directional excess over the input-scaled pre-step BWE
  reference. This is explicitly input-normalized; do not call an unstable late
  sample an equilibrium target. Report late four-second mean/range and final
  two one-second mean drift, eligibility and reference error separately.
- **Trajectories/drift:** fixed census ages 1,2,4,6,9,12,15,18,21,23s, first
  eligible 11 samples within age…age+300ms, span≥900ms, gaps≤250ms. Drift is latest
  one-second mean x minus the preceding one-second mean (≥7 samples each).
- **History/hysteresis:** report descending-minus-ascending prefix differences
  within each content/order/plateau and paired repetition; report initial
  service high-minus-low differences at the same later service/content time
  within each content/prefix/repetition. These matched contrasts are at
  plateau ages 6,12,18,23s, for common plateaus 1–3. The step-versus-held-high
  comparison is an operational hysteresis/history contrast, not isolation of
  a queue, estimator or encoder mechanism. Keep content/order/time heterogeneity.
- Report both independent repetition values/ranges, all censored observations
  and per-run rise/fall contrasts. No pooled p-value or population-equivalence
  claim; two native repeats/cell and reused sources do not support one.

## Causal observable state and genuine settling

This new formulation is preregistered on fresh M8 data, not tested on any prior
validation captures. It is a diagnostic of bounded settling; existing fixed
target-region/common-support requirements are still required in the successor.

At fixed candidate ages **6,9,12,15s**, take the first eligible 11-sample census
in the next 300ms. Eligibility stays native BWE 240k–3.8M, all valid, span≥900ms,
gaps≤250ms. The causal center is instantaneous x at that census's final sample.

**B0 baseline:** current BWE is observable/eligible; predict settling using only
that instantaneous center at the registered age.

**D1 dynamic rule:** additionally, all previous 3s samples (≥27, gaps≤250ms) are
eligible and within **±0.125 octave of the causal current center**, absolute
latest-two-one-second mean drift ≤0.05 octave, and acknowledged applied service
has been constant ≥3s. Features also record current known applied service,
elapsed time since its last actual change and last change direction. They use
only inputs already acknowledged and samples already collected before cutoff.
No prefix/content label, future input, future BWE or relay queue enters the rule.
Known service is an owned experiment input, not assumed observable Internet
capacity or a deployable-controller oracle.

**Genuine finite-horizon settling label:** from the cutoff through plateau
+23.8s, at least eight subsequent seconds must be observed with original
eligibility/gaps, every future x inside the **same ±0.125** causal-center region,
and absolute two-one-second mean drift ≤0.05 at each whole future second
beginning at +2s. Coverage extends to within 250ms of both boundaries. A tag
that later drifts, leaves the region or loses eligibility is false. Future data
are labels only. This validates bounded remaining-plateau settling, not permanent
memorylessness, asymptotic equilibrium or reliability under a different input.

Retrospective verified onset is scanned only on the registered 3…15s integer
grid, using the same causal rule and future label. If none passes, verified
onset is censored at 15s given the required ≥8s subsequent observation; do not
claim that no later settling exists. Report B0/D1 tags, true/false tags and
per-native-run/cell coverage. Rejecting all contexts is not a successful state.

## Measurement-based successor rule, frozen before outcomes

Select the **earliest** candidate age with all of the following:

1. All 64 nested plateau occurrences in all 16 qualified originals have D1 tags
   and genuine future labels. Full baseline retention, no favorable subset.
2. Within each content × current service stratum, full repeat/visit spread and
   empirical cross-prefix W-infinity are each ≤0.25 octave. Do not count visits
   as independent evidence; this is a worst-case engineering gate.
3. The full range of `current_x-log2(service/0.5Mbps)` across those occurrences
   is ≤0.25 octave. For a single static input calibration, take each of the four
   content/service cell median biases, then their equally weighted median.
   This is a stated engineering calibration from support observations, not a
   fitted action model or controller. No content-specific calibrated gains.
4. The four proposed constant service settings
   `0.5 * 2**fixed_target_x / 2**bias` are all within the existing 0.2…5Mbps
   service range. Fixed BWE target centers remain `0,0.5,1,1.5`; no new threshold.

For an eligible age `a`, derive a fresh constant-service conditioning duration
**`a + 9s`**, from the measured verified onset plus the eight-second verification
horizon and one second for the 300ms decision window/clock guard. Entry is at
`a…a+300ms`; no online wait-for-success or extended deadline. Then use the assigned
original measured probe and existing +6/+12s repeatability checks. Freeze the
derived plan and executable gates before opening the new 128-run allocation.
Its four target regions, two measured-source families, four members/history,
±0.125 membership, 3s occupancy/≤0.05 drift, range≥1, sample SD≥0.35,
overlap≥0.5, repeatability/W-infinity/census distance≤0.25 and original technical
gates remain mandatory. No M8 result alone qualifies that independent panel.

If no candidate qualifies, emit **no selected age, no derived duration and no
executable successor schedule**. Preserve the new allocation untouched and
document exactly which causal-state, future-verification, repeatability or
calibration condition failed. Do not try more states or a longer dwell post hoc.
No conditional action-value or controller work is enabled in either branch.

## Preservation and budget

Access preflight at environment revision149 records HF_TOKEN availability
without its value, HTTPS/authenticated private-dataset 200, runtime/policy match
to M7RA and checksum-only verification of its 585 pinned archive members. No old
validation telemetry is projected. Raw runs and 130s derivatives are external,
under a **3GB incremental raw/media/staging/fresh-verification budget**. Check
storage before runs and archives; keep the project below 10GB.

Archive each completed stage, all failures, frozen source/configs and successor
allocation in fresh private namespaces; pin immutable revisions, freshly fetch
every archive object and verify every member size/SHA-256. Retain raw and licensed
files, delete zero evidence. Rehash prior tracked freezes and M5/M6R/M7/M7R/M7RA
archive inventories without decoding them. Commit results separately from design.
