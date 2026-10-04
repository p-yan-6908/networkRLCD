# Causal readback fallback growth hold V1

## Preregistered hypothesis and boundaries

The [rejected ACK growth hold](NATIVE_ACTION_GUARD_V1.md) confused capture-to-ACK receipt with forward video readback. The [new wire-only sidecar](NATIVE_PRESENTATION_V1.md) makes actual callback readback time causally available. On its 1,346 recorded decision histories, substituting only that observable at the **unchanged 120-ms alarm** changes 208 one-step hold intents (586 ACK-based versus 378 readback-based). These are recorded-context intents, **not counterfactual outcomes or a utility estimate**.

A **new experimental fallback consumer**, not a model refit:

- Reuse original canonical V2 actor, weights, 500-ms feedback freshness, risk/support/dwell/budget gates, source-ID deadlines, full request denominators and encoder recipe.
- Compute all old four-field model feedback and scores unchanged. Do not replace the trained ACK-age feature or subtract estimated RTT.
- During canonical fallback only, if the existing sender-congestion hold or fresh transported **forward callback readback >=120 ms** alarms, cap output at `min(canonical_cap, actual_acknowledged_cap)`; permit decreases.
- Never alter accepted neural caps, grant modified fallback neural credit, or reuse canonical probabilities as a safety certificate for the modified action.
- New wire ABI `native_readback_guard_transport_v1`, channel `presentation-readback-guard-v1`, fixed consumer ABI `native_readback_fallback_growth_hold_v1`. Acting/nonacting usage is explicit per peer. Only the same-browser-page performance clock is supported; not remote synchronization or physical scan-out.
- Reject extra/oracle, wrong-source, missing, malformed, future, foreign-clock or inconsistent delay fields before actor history mutation. Replay every transported timestamp against its actual source/callback and actual sender receipt.

## Frozen comparison

`configs/native_readback_guard_repeatability_v1.json`: seed **11101**, **24 peers**, **two independent source/schedule groups** (stable and collapse), two repeats. Two readback-guard aliases, two unchanged canonical aliases, legacy and continuous BWE controls. All peers run the same new wire protocol and canonical+guard shadow workload on their own actual histories.

Fresh Sintel **600–620 / 620–640 s**, excluding **52** prior-role input files plus original fitting reservations. No rejected/pilot role is recycled, no probability, alarm, risk limit, deadline, original repeatability tolerance, timing limit or minimum genuine-use gate is tuned. Two groups are insufficient for independent validation or a SOTA claim; preserve both phase losses and alias/genuine-use failures.

Old modules, collectors, outcome directories and candidate selection remain byte-preserved. New files only; public entry point is isolated so no historical CLI source binding changes:

```sh
python -m media_rl.native_readback_guard_cli plan --help
python -m media_rl.native_readback_guard_cli study --config configs/native_readback_guard_repeatability_v1.json --out results/native-readback-guard-repeatability-v1
python -m media_rl.native_readback_guard_cli audit --run results/native-readback-guard-repeatability-v1
```

There are no fitting, selected-calibration, validation, final-test or promotion commands here. Those remain required on fresh, correctly separated roles, as do representative paths/devices/content and faithful strong learned peers.

## Verification/status

**43 new Python cases and four Node tests pass**, including full stateful Python/JS score/history/ack/reset parity and invalid-input state preservation. Extracted wheel checks match all **71 planned source bindings**, the frozen config and three public module commands. **256 actual recorded-context** Python/extracted-Python/JS cases include 27 genuine bypasses and 73 fallback-hold intents. These software checks are not new native actuation.

**Completed:** `results/jobs/native-readback-guard-native-proof.json` binds **24 actual native peers / two groups / 12,986 eligible requests**, **3,625 transported readback packets**, **4,005 decisions with causally received readback**, and **495 actual fallback holds**. Public read-only full raw wire/model/cap replay preserves all **1,183 saved files**. Runtime **1,200.47 s**; zero accepted-neural cap changes or modified-fallback neural credit/certification.

Original alias, genuine-use and timing gates pass locally for **both** new guard and unchanged canonical mappings. Guarded spans: stable **0.996 utility / 2.957 on-time pp**, collapse **0.450 / 1.479 pp**. Unchanged spans: stable **0.782 / 2.403 pp**, collapse **1.314 / 4.076 pp**. Genuine use is **223/1,343 = 16.60% guarded / 244/1,343 = 18.17% unchanged** (original 5% minimum); there are no >10-ms inference-tail failures. Because unchanged aliases also pass on these different source segments, **do not attribute restored local repeatability to the guard or erase earlier failures**.

Paired descriptive guard-minus-control aggregates (two clusters, not a validation/significance claim):

| Control | Utility delta | On-time delta (pp) |
| --- | ---: | ---: |
| Unchanged canonical V2 | **-0.392** | **-1.156** |
| Legacy BWE | +1.423 | +0.693 |
| Continuous BWE | **-1.395** | **-1.944** |

Preserve all phase harms in the raw report: stable high phase is **-1.784 utility / -4.808 on-time pp vs unchanged**, and **-2.986 / -6.868 pp vs continuous BWE**. Positive legacy-BWE results do not override the canonical/strong-control quality losses. **The readback guard is not adopted; the broader deadline/quality blocker remains.** The strictly causal fallback-consumer plumbing is verified, not a calibrated better policy.

The original `docs/acceptance.md` is left byte-unchanged because it is bound by a preserved prior receipt. This section is the new-stage acceptance addendum: implementation, package and actual intervention/replay are checked; performance improvement, selected confidence calibration, independent validation/final tests and SOTA remain unchecked. All previous negative/wire panels and 17 current/21 prior receipt bindings remain preserved.

**No selection change, calibrated new action certificate, deployment qualification, native improvement or SOTA completion is claimed.**
