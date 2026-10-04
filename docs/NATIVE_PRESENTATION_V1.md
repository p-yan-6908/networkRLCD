# Causal identified-readback transport V1

## Blocker and change

The [rejected growth-hold experiment](NATIVE_ACTION_GUARD_V1.md) measured 27.5–28.2-ms peer-median ACK return delay; 707 held ACK-alarm steps refer to a source with on-time first identified readback. Capture-to-ACK receipt is not identical to forward readback delay. This does not prove that retuning a threshold, subtracting RTT or changing a model would fix the deadline/repeatability failures.

A **separately versioned, wire-only instrumentation** transports the actual receiver callback's identified canvas `readback_ms`, alongside source ID, presented-frame count and declared clock domain. The same browser page owns both connections; only `same_browser_page_performance_v1` is supported. It is not remote clock synchronization, physical screen latency, an internet/GCC benchmark or a production safety certificate.

- New channel: `presentation-readback-v1`.
- Wire ABI: `native_presentation_readback_transport_v1`.
- Strict finite, causal, known-source and monotonic receive checks; unknown, stale, duplicate, future, foreign-clock and extra/oracle fields reject.
- Actual packet readback time must match the recorded same-source/same-presented-frame receiver callback. A decision may see the sidecar only after actual sender receipt.
- Separate `forward_readback_delay_ms`, `return_ack_delay_ms` and old capture-to-ACK receipt age.
- **Canonical model inputs stay exactly the original four-field feedback:** source ID, capture request, sender receipt and presented FPS. The extra field is never supplied to the model, guard or cap selector. No weights, probabilities, guards, dwell, rate selection or labels are refitted/redefined.
- The original source ownership, full request denominators, model-score/readback replay, fixed framerate/geometry, zero receiver target and warmup stay unchanged. All arms use the same instrumentation. Small wire/workload effects are not assumed absent.

## Verified implementation and prospective pilot

- **37** new Python invariants; **97** combined presentation/live/guard regressions; **four** Node tests pass.
- `results/jobs/native-presentation-package-proof.json` verifies all **56** planned extracted source hashes, the actual frozen config, three public commands and **160** callback-reconstructed Python/extracted-Python/JS cases. Those cases are mapping checks reconstructed from old recorded callbacks, **not** old native wire transport or oracle model inputs.
- Public commands: `native-presentation-plan`, `native-presentation-study`, `native-presentation-audit`. There are no train/calibrate/validate/test/promote commands.
- Frozen config: `configs/native_presentation_instrumentation_v1.json`; seed **10101**, **eight** peers, **one** collapse source/schedule group, two repeats, unchanged V2 aliases and legacy/continuous BWE controls.
- Fresh Sintel segment **580–600 s**, excluding **50** prior-role files plus fitting reservations. No failed source role is recycled. Original use/risk/budget/alias/timing gates remain fixed.
- The rejected guard experiment, weights, old collectors and canonical artifacts remain unchanged. This collector does not activate the guard.

## Native status

**Completed:** `results/jobs/native-presentation-native-proof.json` binds **eight actual peers / one independent group / 4,330 eligible requests**, **1,200 actually transported readback packets**, and **1,335 decisions with the causally received sidecar available**. Public full raw replay verifies canonical scores, original four-field feedback and actual caps; all **368 saved files** remain unchanged. Runtime **400.29 s**. No new model/actuator inputs were enabled.

This removes the narrowly defined **wire-observability gap**: actual callback readback time can now be observed by the sender after packet receipt instead of reconstructed from future receiver logs. It does **not** remove the broader deadline/repeatability blocker.

On this one new group, original identical-policy spans pass (**0.7213 utility / 1.1091 on-time pp**), genuine use passes (**70 actual genuine steps**) and inference has no >10-ms tail failure. Descriptive utility deltas are **+3.026 vs legacy BWE** and **+0.821 vs continuous BWE**; there is only one independent group and **no confidence interval or causal improvement attribution**. Preserve the high-phase loss **-0.328 utility / -0.824 on-time pp vs continuous BWE** and collapse on-time loss **-0.412 pp vs legacy BWE**. Different source content/histories and changed wire workload prevent attributing these results to new information, which the policy never used.

Next: a separately preregistered causal use of transported readback/system-state information with unchanged-model aliases and strong conventional controls, or further startup/encoder/playout instrumentation. Do not silently replace the old trained ACK-age feature, certify new actions using old probabilities, fit these pilot outcomes, promote from a single group, or discard earlier failed panels.

An incomplete prefix is preserved, not replaced. Even a completed single-group pilot is instrumentation evidence only, not a calibrated new predictor, repeatability improvement or policy gain. Remaining: a defensible causal presentation/system-state intervention, selected-policy confidence calibration, independent role/model-disjoint validation/final tests, representative paths/devices/content and compatible strong learned peers.

**No candidate/selection change, deployment qualification, native improvement or SOTA completion is claimed.**
