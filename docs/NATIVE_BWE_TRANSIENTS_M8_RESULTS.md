# M8: native BWE response to controlled service

Scientific registration: `cbbafc4f6846d6ad0a5eaf064d09750c7e4d26fa`; long-session instrumentation qualified in `0e5987b`.
The two qualification originals and all **16/16 characterization originals** qualified. Characterization is two reused content productions × two prefixes × two initial service orders × two fresh repeats. All results below are support telemetry; there were no bitrate actions or QoE outcomes analyzed.

## Decision

**No registered candidate qualified. No conditioning duration or executable successor schedule was derived.** The new 128-original successor allocation remains untouched and uninstantiated. M7RA’s separate 128-session panel remains closed. Native reproducible common support is still unestablished; action-value estimation and controller fitting remain closed.

## Fixed intervention and interpretation

After the equal-multiset 10s measured-source prefix, four 24s synthetic service plateaus were `[0.5, 1.5, 0.5, 1.5]` or `[1.5, 1.5, 0.5, 1.5]` Mbps. Service was therefore common high/low/high from 24s onward. At the first common high plateau, one order stepped up and the other held high at the same content time. The encoder ceiling stayed 4Mbps, initialization 1200kbps and receiver target zero. A common original measured-source probe followed.

These are responses of Chromium together with its encoder, content and owned symmetric path. The known input is wire-service capacity, not controlled encoder output. The measurements do not isolate GCC internals, queue history or encoder behavior. The no-change control helps distinguish natural estimator drift from a change coincident with a service step. Synthetic service is not measured-network replication; reused source groups and repeated visits are not independent new evidence.

## Actual-run instrumentation

These maxima cover the sixteen characterization originals; the two earlier qualification originals are preserved separately.

| Check | Maximum observed | Registered limit |
|---|---:|---:|
| Full clock held-out width | 1.260ms | 50ms |
| Beginning clock held-out width | 2.590ms | 50ms |
| Main sender observation gap | 133.000ms | 250ms |
| Service acknowledgement | 7.500ms | 100ms |
| Command lateness | 8.100ms | 0…150ms |
| Source tick error | 1.647ms | 150ms |
| Common probe exposure difference | 0.000208 octave | 0.01 octave |

Each actual long-session map used 128 fixed training and 15 independent held-out exchanges; beginning certificates used 35/four. Strict TURN/TCP, managed-policy hashes, inactive/exact startup, fixed readback, native media progression, known service commands and exact post-cutoff queue cleanup all passed. No failed ICE session was interpreted as a response.

## Response delay and rise/fall asymmetry

The following envelopes cover the eight specific native contexts within each content group. They are measurement ranges, not population intervals; all history/order/repetition cells are retained below.

| Content | Fall departure onset (s) | Rise departure onset (s) | Fall t50 (s) | Rise t50 (s) | Fall t90 (s) | Rise t90 (s) |
|---|---:|---:|---:|---:|---:|---:|
| Kampar | 0.39–0.79 | 0.00–0.34 | 0.39–0.79 | 7.44–10.02 | 0.83–1.20 | 13.25–15.90 |
| Volga | 0.40–0.74 | 0.00–1.06 | 0.40–0.74 | 9.13–10.16 | 0.81–1.02 | 14.84–15.85 |

Each entry below contains **both independent repeat values**, in seconds, for the registered input-normalized t50 onset interval. Intervals include polling and input-clock uncertainty. “Unconfirmed” means the required sustained crossing was not confirmed inside the finite observation window; it does not establish a latent estimator delay beyond that window. Common fall/rise transitions are within the same native run. No repeated phase is counted as an independent run.

| Content | Prefix | Initial service | Fall t50, repeats 0/1 (s) | Rise t50, repeats 0/1 (s) |
|---|---|---|---|---|
| Kampar | ascending | low | 0.50–0.60, 0.47–0.57 | 8.77–8.87, 8.56–8.67 |
| Kampar | ascending | high | 0.68–0.79, 0.40–0.50 | 8.78–8.88, 7.44–7.55 |
| Kampar | descending | low | 0.39–0.50, 0.56–0.66 | 7.60–7.70, 7.94–8.04 |
| Kampar | descending | high | 0.51–0.62, 0.69–0.79 | 9.92–10.02, 9.12–9.22 |
| Volga | ascending | low | 0.51–0.61, 0.40–0.50 | 9.60–9.70, 9.70–9.80 |
| Volga | ascending | high | 0.60–0.71, 0.57–0.67 | 9.49–9.60, 10.05–10.16 |
| Volga | descending | low | 0.56–0.66, 0.50–0.60 | 9.94–10.04, 9.63–9.73 |
| Volga | descending | high | 0.63–0.74, 0.54–0.65 | 9.91–10.01, 9.13–9.24 |

The full tables preserve departure/t10/t50/t90 censoring, t10–t90 intervals and per-native-run rise-minus-fall contrasts. Input-normalized overshoot is relative to the input-scaled **past** BWE reference, not an assumed equilibrium.

## Overshoot, late variation and drift

Values below are the two repeat values in octaves. Late range is the final four-second native BWE range. Final drift is the latest one-second mean minus the preceding one-second mean; all detailed values remain in the JSON tables.

| Content | Prefix / initial service | Fall overshoot | Rise overshoot | Fall late range | Rise late range |
|---|---|---|---|---|---|
| Kampar | ascending/low | 0.239, 0.381 | 0.275, 0.288 | 0.448, 0.463 | 0.110, 0.110 |
| Kampar | ascending/high | 0.078, 0.720 | 0.269, 0.216 | 0.494, 0.247 | 0.113, 0.115 |
| Kampar | descending/low | 0.741, 0.177 | 0.238, 0.227 | 0.297, 0.303 | 0.112, 0.565 |
| Kampar | descending/high | 0.400, 0.450 | 0.559, 0.242 | 0.495, 0.245 | 0.588, 0.114 |
| Volga | ascending/low | 0.239, 0.322 | 0.511, 0.506 | 0.507, 0.478 | 0.567, 0.586 |
| Volga | ascending/high | 0.352, 0.441 | 0.509, 0.442 | 0.487, 0.524 | 0.587, 0.549 |
| Volga | descending/low | 0.339, 0.355 | 0.061, 0.504 | 0.268, 0.510 | 0.120, 0.572 |
| Volga | descending/high | 0.421, 0.408 | 0.494, 0.571 | 0.507, 0.517 | 0.513, 0.604 |

## Matched history / hysteresis contrasts

The following registered contrasts compare **initial service high minus low** while current service is the same high and content time is matched (first common plateau). Both repeat differences are shown; no pooled population estimate or p-value is inferred. They are operational history contrasts, not attribution to a particular estimator mechanism.

| Content | Prefix | Common-high age | Two paired differences (octaves) |
|---|---|---:|---|
| Kampar | ascending | 6s | 1.265, 1.151 |
| Kampar | descending | 6s | 1.093, 1.044 |
| Kampar | ascending | 23s | 0.364, 0.181 |
| Kampar | descending | 23s | 0.135, 0.013 |
| Volga | ascending | 6s | 1.555, 1.370 |
| Volga | descending | 6s | 1.281, 1.118 |
| Volga | ascending | 23s | 0.152, 0.202 |
| Volga | descending | 23s | 0.075, 0.049 |

Initial ascending/descending-prefix contrasts remain separate in the complete report at all registered common-service ages, contents and input orders. Two repetitions per cell give empirical ranges, not precise population uncertainty or a convergence/equivalence claim. M5 remains the qualified causal prefix-history result.

## Prospective causal settling rule

B0 used current eligible native BWE as its causal center. D1 additionally required three seconds inside ±0.125 octave, ≥27 eligible samples, gaps ≤250ms, absolute recent mean drift ≤0.05 octave and acknowledged service constant ≥3s. The state used only past samples and acknowledgements. The initial last-change-direction value is an initialization sentinel; direction is reported, not a D1 decision threshold. Actual initial input direction remains in the response metrics.

A true label required at least eight later observed seconds, through plateau +23.8s, inside the **same** causal-center caliper with the original eligibility and drift bounds. Those later samples were labels only. The 64 occurrences are nested in 16 native runs.

| Candidate age | B0 tags / verified | D1 tags / verified | D1 false tags | Worst content/service spread | Full calibration-bias range |
|---|---:|---:|---:|---:|---:|
| 6s | 64 / 0 | 20 / 0 | 20 | 1.646 | 1.646 |
| 9s | 64 / 0 | 16 / 0 | 16 | 1.491 | 1.491 |
| 12s | 64 / 0 | 12 / 0 | 12 | 1.135 | 1.181 |
| 15s | 64 / 0 | 11 / 0 | 11 | 0.946 | 0.946 |

**64/64** plateau occurrences had no verified D1 settling onset on the registered 3…15s grid. These onsets are censored at 15s because ≥8s subsequent verification is required; this does not rule out later settling. Rejecting contexts or being locally flat is insufficient. A selectable age needed all 64 valid future-verified tags, full retention and ≤0.25-octave repeatability/hysteresis/calibration spread.

All future verification windows were observable and stayed within the original BWE eligibility bounds. At each candidate age, all 64 left their causal ±0.125-octave region during verification. The fixed future-drift test also failed in 64/64 at 6s, 64/64 at 9s, 61/64 at 12s, 59/64 at 15s. These are failures of future stability, not missing observations or clock coverage. [Registered-component diagnostic](../reports/native-bwe-transients-m8-support-failure-diagnostic.json).

## Successor design and unchanged gates

The preregistered measurement rule did not supply an admissible age/calibration, so **no heuristic duration was substituted**. The concrete new allocation and conditional derivation remain frozen and untouched, without executable native panels. Another conditioning recipe or dynamic state would need fresh prospective justification; none is fitted or searched here.

The successor still requires the original four fixed BWE regions, both content groups and measured-source families, four original members/history, ±0.125 target membership, sustained history/≤0.05 drift, range≥1 octave, sample SD≥0.35, overlap≥0.5 and repeatability/W-infinity/census distance≤0.25. No threshold or count was relaxed. M8 alone establishes neither reproducible native common support nor conditional action value.

## Evidence and preservation

- [Frozen plan](NATIVE_BWE_TRANSIENTS_M8_PLAN.md), [summary](../reports/native-bwe-transients-m8-summary.json), [response tables](../reports/native-bwe-transients-m8-response-tables.json), [selection](../reports/native-bwe-transients-m8-selection.json).
- [All native trajectories](../reports/native-bwe-transients-m8-trajectories.png), [settling tags](../reports/native-bwe-transients-m8-settling.png).
- [Preservation audit](../reports/native-bwe-transients-m8-preservation-audit.json), [private archive receipt](storage-receipts/native-bwe-transients-m8-20261015-01.json).

Every original, failed check, source snapshot and successor allocation is retained. The private archive is pinned and freshly verified object by object and member by member. Raw frame/quality outcomes stay unopened by analysis; licensed originals and old derivatives remain unchanged. M5, M6R, M7/M7R/M7RA, V13 and all prior freezes are preserved. Zero evidence files deleted.
