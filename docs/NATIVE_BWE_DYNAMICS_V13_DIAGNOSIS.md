# Outcome-free diagnosis after the V12 support-design failure

Anchor: `a7ea1b0`. V12 remains a support-design failure. Its failed census is
not a negative action-effect result. V11D and V12 are development evidence
only in this diagnosis. No controller, outcome regression or renewed V10
policy is fitted.

## Evidence boundary

`tools/diagnose_native_bwe_dynamics_v13.py` verified **3,607 session files**
(983 V12, 2,624 V11D), including the bytes of unopened outcome files, against
their existing seals before projecting permitted telemetry. It decodes only
sender times, BWE feature zero/validity, native cap readback/assignments,
standalone clock markers, frozen panel schedules and source identifiers.
Frame events, summary/QoE telemetry, encoded-meter and receiver feedback,
queue/event outcome telemetry and prior outcome reports are excluded.

The compact diagnosis is `reports/native-v13-bwe-dynamics-diagnosis.json`.
The complete support-only sample projection stays outside Git; its hash/path
is recorded there. The diagnostic figure is
`reports/figures/native-v13-bwe-development.png`.

Capacity/BWE comparisons use each successful capture's validated actual-run
affine map. Samples within the feasible clock uncertainty plus the existing
150 ms trace-tick tolerance of any scheduled transition are excluded from
state-disagreement calculations. The one failed V12 media capture has BWE
diagnostics only; it receives no sender/relay capacity join. No per-hold
relay effects are inferred.

## Startup and conditioning

All **24 V12** and **64 V11D** sessions first report 300 kbps. Every session
then leaves that value after approximately 105–121 ms. The recorder initially
sets a 300 kbps ceiling during connection establishment and raises it to
4 Mbps before measurement; GCC's initial availableOutgoingBitrate is still
300 kbps at the first measured observation. That first value supplies no
evidence of a settled low-bandwidth network state.

V12's entire support census subsequently retains the common 4 Mbps ceiling,
with zero randomized actions. A ceiling permits traffic; it does not force
that payload rate or reset GCC to trace capacity. V11D changes caps throughout
its six holds. Its later BWE is consequently a mixture of content, network,
estimator history and prior treatments. It cannot be used as an untreated
response curve or pooled with V12.

## The source screen did not describe the causal conditioning history

The V12 source hint averaged seconds **3–12**, including seconds after the
second-9 treatment boundary. It neither bounded every pre-treatment rate nor
ensured an eligible observed BWE history. A mean obscured deep troughs and
allowed late bursts to determine the hint:

- Murcia `high-01` is approximately **64 kbps through second 10**, then jumps
  above 6 Mbps at second 11. The later burst raises its 3–12 mean into the
  high-hint range. Native BWE at second 9 is about **30–33 kbps**, and remains
  about **30–38 kbps** in seconds 15–18.6. This is not a supported high-BWE
  conditioning history. One of its two content captures also failed media
  validation and stays a technical failure.
- Irish `low-02` includes 22 kbps troughs at seconds 6 and 8. Its second-9
  BWE is approximately **59–60 kbps** and is still only **60–97 kbps** late
  in the run, despite the final rise in scheduled rate.
- NYU low hints mix early megabit rates with 0–206 kbps troughs. Their
  second-9 BWE is about **91–164 kbps** and later falls further. A ten-second
  source average never guarantees an eleven-observation eligible native
  history.
- Irish `high-02` starts above 1 Mbps but its later drops coincide with a
  roughly **402–412 kbps** second-9 BWE. The registered high-state history
  fails even though the observed rate is inside the action eligibility range.

All original history sample-count, 900 ms span and 250 ms gap requirements
were satisfied at the registered window. Sampling cadence was not the cause
of the thirteen sealed BWE failures.

## Campaign-specific dynamics and finite duration

Fractions below are medians of existing session time fractions within each
campaign, including the preserved failed capture's sender trace where
available. They are descriptive summaries, not independent-source or
population estimates.

| Campaign | Eligible BWE time, whole run | BWE below 240 kbps | Time in 450–550 kbps boundary neighborhood | Original second-9 BWE support | Same-window continuous range support |
| --- | ---: | ---: | ---: | ---: | ---: |
| Irish LTE | 56.9% | 43.1% | 0% | 4/8 | 6/8 |
| NYU LTE | 57.1% | 36.0% | 0% | 4/8 | 4/8 |
| Murcia campus upload | 15.4% | 78.6% | 0% | 2/8 | 2/8 |

The 450–550 kbps neighborhood is a diagnostic band only. Neither the 500 kbps
state split nor any frozen V12 threshold is changed. Most failures occurred
far below eligibility, rather than through lingering near the split.

Changing only the state formulation would produce **12/24 BWE-qualified
checks**, not a qualified census: eleven sealed captures still have no
eligible range and one capture remains failed. Of the fourteen original
nonqualifying checks, **none** acquires its target eligible history after
9300 ms and before the unchanged 18.6-second cutoff. The ten late target
visits all belong to checks that had already qualified. Late-window counts
are diagnosis only, never replacements or a V12 reanalysis.

Every high NYU profile and the supported Murcia high profile retain eligible
BWE late in the run. Every low-target profile is below eligibility by the
15–18.6-second window, including the two Irish low checks that qualified at
second 9. Thus extending this particular trace briefly does not generally
improve low-state support. There is no evidence about convergence beyond the
recorded duration, and no trace was looped to invent it.

## Estimator lag and memory: what is observed and what remains unidentified

Unchanged BWE plateaus last up to **8.18 seconds** in V12; plateau duration
alone does not establish stale RTCP, because a refreshed estimate may remain
numerically unchanged. Low-rate troughs can precede a low BWE that persists
after capacity increases. Conditioning on the preceding BWE state also
changes BWE distributions within the same diagnostic capacity band. These
are history-dependent associations compatible with estimator lag/hysteresis.

For capacity transitions across 500 kbps that persist at least two seconds,
the diagnostic separately reports instantaneous tracking and an eligible
one-second history. It does not mistake the required history duration for
GCC latency. Restricting to transitions whose pre-transition BWE is in the
opposite state gives:

| Campaign | Opposite-start transitions | No instantaneous BWE match before next capacity-state change/cutoff | Observed first-match delays |
| --- | ---: | ---: | --- |
| Irish LTE | 9 | 6 | 0.206–1.543 s |
| NYU LTE | 6 | 4 | 0.466–0.704 s |
| Murcia campus upload | 5 | 3 | 1.209–1.213 s |

These are serial episodes nested in existing sessions. Right-censored
episodes are retained. No lag population estimate, causal GCC attribution,
or treatment cost is calculated. Sender BWE alone cannot distinguish
probing, congestion feedback, offered-load limitations and estimator
update rules. Qualified clocks resolve timestamp ambiguity, not those
mechanisms. A causal estimator experiment would require separate,
prospectively varied histories and additional permitted estimator telemetry.

## Decision for the next validation

Capacity-only trace selection cannot guarantee unknown browser BWE. A new
binary panel would need an actual outcome-free native screen and all original
state/action requirements; changing rate means or waiting later cannot be
called a guarantee. The diagnosis provides no justification for relaxing V12.

The next question uses **continuous log2 BWE-by-action value**, under an
explicitly different registration. This avoids assigning a discontinuity at
500 kbps and wasting eligible observations at approximately 400 kbps, but it
retains the **240–3,800 kbps** unclipped action range. It must separately
establish within-family variation and repeatability; a continuous covariate
does not repair below-range occupancy.

V13 uses new licensed productions and new packet-service traces. Source
screening requires every second of each uninterrupted 36-second window to
lie in **0.3–10 Mbps**, with no scaling, zero substitution, wrapping or
interpolation. Selection uses the first nineteen source bins (indices 0–18)
for its input hint; its last bin straddles the nominal decision boundary.
It remains a prospective input summary, not proof of causal native BWE
support. The support census supplies the actual measured modifier.
The new source floor is a prospective input-screen choice, not a change to
V12 or to native action eligibility. Conditioning is extended to a fixed
**18–18.3 s** decision window, with no adaptive waiting. Its new 32-session
support census must establish all gates, repeated continuous-state agreement,
at least one octave of within-cell state range and adequate variation before
any of 64 randomized sessions can start.

The confirmatory modifier is the census BWE context, frozen before all
randomized actions and checked against every action run. This avoids making
paired sessions' modifier depend on a later treatment-influenced history.
It estimates a finite-panel quality gradient under common conditioning,
not a literal replication of the old dichotomized V9 interaction. Campaign
slopes, observed ranges and common overlap remain explicit. Disjoint ranges
cannot establish transportable conditional action value. See the separately
preregistered V13 plan; all new confirmatory combinations remain untouched.
