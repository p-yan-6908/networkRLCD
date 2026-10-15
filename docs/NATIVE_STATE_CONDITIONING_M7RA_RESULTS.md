# M7RA: qualified instrumentation, failed prospective state creation

The frozen fixed conditioning recipe did **not** create reliable common support.
All four fresh feasibility originals passed every technical gate, but only
**2/4** met instantaneous BWE target membership and **1/4** met the sustained
causal-history state. Neither target region qualified across both histories.
The registered stop applies: **all 128 validation sessions remain untouched**.
There were no bitrate actions, QoE/action-effect analyses, predictor fits or
controller promotion.

## Registration and acquisition

- M7 scientific design: `c262b151fff4c3aa81835c60b7b0069d36cae73d`.
- M7's sub-millisecond early-timer failures are preserved in `85fd656`; its
  unchanged gate was not relaxed. M7R's recorder-path setup failures are
  preserved in `dd2c17d`; zero native sessions started in that attempt.
- Fresh M7RA registration: `c992058a9d8c0569c5544aea1d22507ca1b7b4f0`.
  It uses the already frozen guarded M7R recorder at its verified actual path.
  Every numeric M7 design/gate parameter is identical; seeds and original IDs
  are new. No data from the failed attempts are pooled with M7RA.

The recipe is 10s ascending/descending prior service history, 32s fixed-rule
causal BWE feedback conditioning with feedback off at +27s, a fixed +30s state
census, then a common 12.6s original measured-source probe. Native encoder cap
stayed 4Mbps, jitter target zero, and initialization exactly 1200kbps. The four
feasibility contexts use reused Kampar content and one reused LTE source
profile; they are not a cross-content/network confirmation.

## All acquisition gates qualified on the actual runs

| Check | Observed maximum | Registered bound |
|---|---:|---:|
| Full-session held-out clock width | 1.306ms | 50ms |
| Beginning held-out clock width | 2.186ms | 50ms |
| Startup polling gap | 31.4ms | 250ms |
| Service-command acknowledgement | 6.4ms | 100ms |
| Service-command lateness | 9.5ms | 150ms, never early |
| Source tick scheduling error | 1.985ms | 150ms |
| Common probe exposure difference, all clock maps | 0.000078 octave | 0.01 octave |

All 104 service updates and four feedback-off markers satisfied the exact
causal formula, input-history, timing and readback checks. Full clock maps used
64 fixed training/seven held-out exchanges per original; beginning maps used
35/four, without late extrapolation. Strict TURN/TCP transport, unchanged
managed browser policy, exact initialization, fixed encoder/jitter readback,
native media progression, bidirectional relay transport and exact post-cutoff
cleanup all passed.
The actual clocks and replay do not explain the failed state gate.

## Frozen membership and repeatability results

Region membership retains the ±0.125-octave BWE caliper. The history state
requires every native sample in the preceding 3s to be in that region, at least
27 samples, fixed eligibility/gaps, ≤0.05-octave recent mean drift, and feedback
off for at least 3s. No region, landmark, bound, state variable or count changed.

| Target | Prior history | Instantaneous BWE baseline | Sustained history state | Failed state components |
|---|---|---|---|---|
| 500kbps | Ascending | Pass | Fail | Recent drift 0.0775 >0.05 octave |
| 500kbps | Descending | Fail | Fail | Outside region; recent range −0.1593…0.3512, drift −0.2685 |
| 1414kbps | Ascending | Fail | Fail | Recent BWE 1.6420…1.7147, above target's upper 1.625 |
| 1414kbps | Descending | Pass | Pass | None |

The two 500kbps **census means** were only 0.0114 octave apart at entry.
That proximity cannot substitute for their failed instantaneous/history
membership or qualify a state with a different post hoc definition.

The registered across-history BWE support distances after the common probe are:

| Target | Probe +6s full spread / W-infinity | Probe +12s full spread / W-infinity | Both ≤0.25? |
|---|---:|---:|---|
| 500kbps | 0.3615 octave | 0.4644 octave | No |
| 1414kbps | 0.0092 octave | 0.2589 octave | No |

Each feasibility arm has one original, so these are deterministic gate
diagnostics, **not population estimates or a new causal prefix-effect test**.
The global range ≥1 octave, sample SD ≥0.35, overlap ≥0.5 and four-members-per-
history validation gates were not assessed on an opened panel. They remain
unchanged and untested because feasibility failed.

## What follows

Prospective native common support is still unestablished for this fixed recipe.
An instantaneous target hit or similar one-second census does not establish
sustained occupancy or reproducible subsequent BWE. This result does not show
that controlled state creation is impossible or that history is irrelevant.
M5 remains the qualified causal prefix-history result; M6R remains a state-
coverage failure. Its validation telemetry was never reopened for a new state.

The next useful support-only question is the transient response from controlled
service to native BWE before choosing another conditioning schedule. The current
data do not justify relaxing drift/calipers/counts, lengthening this frozen
recipe, testing alternative states on its untouched validation, or estimating
conditional action value. No additional recipe is selected or fitted here.
V13 actions and learned control remain closed.

## Artifacts and preservation

- [Frozen plan](/workspace/networkRLCD-a135/docs/NATIVE_STATE_CONDITIONING_M7RA_PLAN.md)
  and [qualification gate](/workspace/networkRLCD-a135/reports/native-state-conditioning-m7ra-feasibility-gate.json).
- [Support-only summary](/workspace/networkRLCD-a135/reports/native-state-conditioning-m7ra-summary.json)
  and [BWE/service trajectories](/workspace/networkRLCD-a135/reports/native-state-conditioning-m7ra-trajectories.png).
- [Checksum-only preservation audit](/workspace/networkRLCD-a135/reports/native-state-conditioning-m7ra-preservation-audit.json).

Constructed prefix, synthetic controlled conditioning, and measured-source probe
remain explicitly separate. Reused content and profiles do not become new
independent source evidence. Raw quality/frame files are retained but unopened
by the analysis. All originals, failures, source snapshots and untouched panel
registrations are privately archived at pinned revisions with fresh object and
member SHA-256 verification. Local raw evidence and licensed media are retained;
zero evidence files were deleted.
