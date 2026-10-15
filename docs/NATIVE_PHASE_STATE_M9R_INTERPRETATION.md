# M9R: interpretation and registered residual audit

The frozen M9R analysis is unchanged. This report summarizes its registered components and paired values; it evaluates no additional state, feature, threshold or outcome.

## Classification

**Prospective state-coverage failure with qualified acquisition.** All eight instrumentation and64 validation originals passed. Validation maximum actual observation gap99.4ms (limit250), full held-out clock1.385ms and beginning3.269ms (limit50). The sampling repair is qualified on this panel. M9 remains separately frozen and unestimable; its two failed observations are never pooled into M9R.
P2 emitted **zero** eligible first tags. Its positive predictive accuracy is **unestimable**, not0%. B0 tagged64 originals and D1 tagged55; none of those first predictions was future-verified. There were **zero future-stability labels** at any of the3200 registered native-run/grid combinations. These are50 nested measurements per original, not3200 independent replications.
Every original lacked a future-verified D1 settling onset on6..55s. All64 onset records are right-censored at55s, with observation through63.8s. This extends M8’s finite censoring window and does not show permanent nonsettling or permanent memory. There is no selected conditioning duration.

## Binding constraints

| Registered P2 component | Passing /3200 nested measurements |
|---|---:|
|D1|1070|
|past_M8_response_envelope|2864|
|six_second_acknowledged_service|3180|
|six_second_contrast|315|
|six_second_eligible|3200|
|six_second_frozen_caliper|2|

All3200 past six-second windows had eligible actual observations. Only **two** met the unchanged current-centered six-second caliper; neither met the complete P2 conjunction. The six-second mean contrast passed315 times and the D1 subrule1070 times. The shortage is observable state support, not missing clock/sample coverage. Extra measurements or another classifier cannot manufacture positive labels in this closed panel.

## Remaining future variation after causal matching

**42/64** registered strata had all four BWE-only matched pairs; **13/64** retained all four with the compact vector. The vector uses current BWE, recent/longer contrasts, direction/acknowledged age and past controlled-service means. No queue, RTT or encoder variable was added.
Of the13 fully covered compact strata, **six** kept all four eight-second marginal distributions within the original0.25-octave W-infinity bound. **Seven** failed that bound in at least one pair. Repeatable moving distributions and future stability are different registered requirements: even the six marginal matches left their frozen causal-center stability regions. Neither observation qualifies an action study.
The table retains every fully covered compact stratum. Ranges are across its four prepaired native contexts; repeated landmarks share originals. No pooled population estimate is formed.

| Content | Input Mbps | Age s | Current prefix difference range | Subsequent-change residual range | Future W-infinity range | All four <=0.25 |
|---|---:|---:|---|---|---|---|
|content_kampar_boating_01|1.000|24|-0.049..0.178|-0.237..-0.009|0.155..0.275|no|
|content_kampar_boating_01|1.414|6|-0.009..0.009|-0.002..0.024|0.038..0.052|yes|
|content_kampar_boating_01|1.414|12|-0.009..0.038|-0.020..0.037|0.036..0.073|yes|
|content_kampar_boating_01|1.414|24|-0.000..0.032|-0.014..0.010|0.014..0.029|yes|
|content_kampar_boating_01|1.414|32|-0.007..0.020|0.006..0.093|0.292..0.344|no|
|content_kampar_boating_01|1.414|48|-0.046..0.012|-0.000..0.119|0.263..0.304|no|
|content_volga_lock_01|0.707|24|-0.103..0.057|-0.028..0.149|0.152..0.268|no|
|content_volga_lock_01|1.000|6|-0.021..0.054|-0.021..0.131|0.056..0.211|yes|
|content_volga_lock_01|1.000|24|-0.027..0.040|-0.039..0.038|0.215..0.234|yes|
|content_volga_lock_01|1.000|32|-0.066..0.008|-0.005..0.007|0.026..0.111|yes|
|content_volga_lock_01|1.000|55|-0.156..-0.081|0.165..0.244|0.169..0.305|no|
|content_volga_lock_01|1.414|32|0.019..0.035|-0.254..0.018|0.203..0.382|no|
|content_volga_lock_01|1.414|48|-0.005..0.026|-0.004..0.113|0.018..0.348|no|

For example, at Kampar/1.414Mbps/32s, all four current differences were within about0.020 octave, yet future W-infinity was0.292..0.344, above0.25 in every pair. At Volga/1Mbps/55s, all four pairs met compact matching but subsequent-change residuals were **+0.165..+0.244 octave**, and two future-distribution distances exceeded0.25. Complete paired values remain in the diagnostic JSON.
These selected-context residuals do **not** isolate a causal prefix effect or separate systematic prefix memory from within-history native/run variability. Matching conditions on endogenous observations. Unconditional randomized-prefix comparisons and their four paired values/16 exact sign assignments remain separately reported; minimum attainable two-sided p is0.125. M5’s qualified causal history result remains intact.

## Consequences and next development design

The tested compact package provides no prospectively eligible future-stable common state under the frozen contract. It does not establish that history is irrelevant, that all compact states fail, or that no trajectory can be predicted. Some moving marginal distributions were reproducible. Existing calipers, duration, counts, range/SD/overlap, timing and probe gates remain unchanged; action-value estimation and learned control remain closed.
The completed residual audit permits considering additional history information on **fresh development data**. The next useful preparation is a causal-observability/mechanism assay, not another fit to these validation captures. A concrete minimal proposal is eight fresh originals: two contents ×two prefix histories ×two repeats at the1.414Mbps common input where matched contexts diverged. Retain the24s initial/64s common schedule,25ms actual sampler, clock/TURN/readback/cleanup gates and250ms limit.
Record owned relay queue/service-counter snapshots using a request/response acknowledgement fence in the sender clock, linked native RTCP RTT and feedback-counter age, and previous cap/send-rate/encoder behavior from getStats returns. A relay snapshot becomes usable only after its browser receipt; never construct an online feature with a clock fit trained on later markers. Preserve missing/invalid counters explicitly. Receiver quality/deadline outcomes remain unopened. This is an instrumentation proposal, not a registered executable follow-on or a selected representation.
Qualify those channels prospectively before collecting a separate development panel. Any later representation requires fresh untouched confirmation and actual positive stable-context coverage under the existing gates. If that development again has no positive stable labels, do not fit a stability classifier or promote an action study. Queue/RTT/encoder information may explain moving trajectories; it cannot retroactively create stable states in M9R. No new definition, threshold, fixed conditioning wait or favorable late window is selected here.
M9R validation is closed to additional state searches. M8’s successor allocation and all older closed panels remain untouched.

- [Frozen result](NATIVE_PHASE_STATE_M9R_RESULTS.md), [complete primary summary](../reports/native-phase-state-m9r-summary.json).
- [Registered-component diagnostic and all13 matched strata](../reports/native-phase-state-m9r-support-failure-diagnostic.json).
