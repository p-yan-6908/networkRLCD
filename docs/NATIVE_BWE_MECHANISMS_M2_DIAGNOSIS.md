# Outcome-free V13/M1 diagnosis for M2

Anchor `7427f48`. V13 is permanently closed as a repeatability/common-support
failure; its action directory is untouched. M1 is preserved as a separate
synthetic development reliability result. Every file in both raw session
inventories was verified before expanding the permitted support projection:
**1,312 V13 files and 328 M1 files**. No quality, frame deadline, receiver
feedback, encoded-frame meter or action-effect outcome was decoded.

The user requested transport/queue and sender support variables. The new
diagnostic projects native sender RTT, payload sending demand, encoding/poll
timing and clock-aligned queue/service/forward-timer history **before the
support decision only**. These are baseline support dynamics, not per-hold
delivery-cost/QoE estimates. The old support reports and access decisions
remain unchanged. The full reproducible projection and every original
context appear in `reports/native-bwe-mechanisms-m2-diagnosis.json`.

## Contributions that the finite panel can quantify

All 32 sessions start with an observed 300 kbps BWE, the same native cap and
jitter target, the same TURN/TCP path and qualified fresh/empty-queue recipe.
Within each content/profile, compare repetition one minus repetition zero.
The 16 signed differences are nested in eight profiles and share two content
productions. Correlations below are descriptive associations, not causal
variance allocations or population estimates. The variables are correlated
and several are mediators in the estimator/network feedback loop.

| Explanation | Quantitative support evidence | Interpretation and limit |
| --- | --- | --- |
| Measured-rate replay | 36 exact ticks/run; maximum absolute tick error 2.764 ms. In the six failed contexts, service-exposure differences were at most 0.001724 octaves; their median was 0.000375. Exposure difference versus BWE difference: r=0.120, descriptive r²=0.014. | No gross rate substitution or exposure drift. Small timing differences could still trigger nonlinear feedback; equal mean exposure does not imply equal queue dynamics. |
| Phase/poll timing | Phase onset 7.592–34.072 ms after sender origin; paired onset r=0.186. First sample timing r=0.363; mean 6–12-second poll gap r=−0.327. | Timing varies, but the failing contexts do not have uniquely large replay drift. Correlation does not isolate CPU or scheduling causes. |
| Initial estimator state | First native BWE exactly 300 kbps in every V13/M1 run. Paired startup peak r=−0.199; first departure timing r=0.387. | Observed initialization has no between-run variance to allocate. Internal probe/history state is not recorded by this Chromium build and remains latent. Manipulate the initial estimator target prospectively. |
| Conditioning/history | Paired BWE differences at 6–12 s correlate r=0.440 with the eventual support difference; 12–16 s r=0.770; 16–18 s r=0.991. Across one-second bins, correlation increases from −0.300 at 0–1 s to 0.999 at 17–18 s. | Most final divergence is established later, not evident from the initial scalar. Adjacent BWE histories overlap the process being explained; the high late correlation is persistence, not an independent causal contribution. |
| Queue/transport feedback | Paired 12–18 s average queue difference r=0.763 (leave-one-profile r=0.657–0.793). Median absolute difference: 1,215 bytes in failures versus 126 in passes. Bootstrap-duration r=0.003; forward-timer p95 r=0.125. | Late queue histories co-vary with BWE. Higher BWE can itself cause greater queue demand; this cannot identify queue→BWE versus BWE→queue. |
| Scheduler/transport timing | V13 pump gaps reached 40.077 ms; M1 reached 33.167 ms. Forward-timer p95: V13 1.092–1.341 ms, M1 1.120–1.297 ms beyond the 25 ms propagation timer. Pump-gap p95 r=−0.172 with BWE repeat difference. | Stable synthetic BWE exists despite similar timer imperfections. This weakens a universal timer-fault explanation but does not exclude rate-dependent amplification. |
| Content and sending demand | Balanced finite-panel BWE SS: profile main 98.609%, content main 0.0097%, content×profile 0.258%, within-context repeat 1.123%. Paired initial encode-time r=−0.557; 6–12 s send-demand r=0.457. | Profile choice dominates the wide between-context range. Small content main SS does not show content is irrelevant to repeat noise; encode/demand are entangled with estimator feedback. |

The sum-of-squares decomposition separates between-context structure from
repeat deviations; it is not a partition of the six failures among
mechanisms. The repeat deviations are scientifically decisive even though
they are a small fraction of a deliberately wide total BWE range.
All associations and all leave-one-profile sensitivities are retained,
including weak/negative ones; no fitted controller or explanatory model
selection is used.

## Direct experiment rather than a longer wait

M1's synthetic constant was run in a separate batch, so its comparison with
V13 alone cannot identify a causal effect of dynamic history. M2 therefore
randomizes two orthogonal startup factors in interleaved fresh sessions:

1. **Early rate history:** the original measured first 12 seconds versus a
   flat synthetic first block with exactly the same 12-second service
   integral. Every subsequent measured rate, phase duration and the
   decision-window capacity history is identical. This isolates earlier
   rate-history shape from current measured service and total early capacity.
2. **Estimator initialization:** native codec start target 300 versus
   1,200 kbps. Verify the actual initial native BWE, not merely SDP text.
   Both arms use the same 4 Mbps ceiling before and during measurement, so
   the initialization comparison does not introduce a different cap arm.

Use the original LTE uplink-lower profile that failed for **both** clips,
with both reused V13 clips and four fresh repeats per factorial context.
The original measured suffix, 18-second decision boundary, history sample
checks, action eligibility, clock, TURN/TCP, readback and cleanup limits
are retained. A flattened prefix is explicitly hybrid synthetic development,
not a measured trace or independent confirmatory source.

This tests feedback sensitivity to initial target and early rate history,
while randomized blocks limit batch/run-order confounding. It does not
directly randomize queue depth or codec workload: measured queue, demand,
RTT and probe dynamics are mediators, and causal shares among those
mediators remain unidentified. A successful startup manipulation must first
pass a separate support-only instrument check before any M2 mechanism run.
The prospective design and decision are in `NATIVE_BWE_MECHANISMS_M2_PLAN.md`.
