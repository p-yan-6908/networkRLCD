# Post-capture randomized-hold action diagnostic

This is an explicitly exploratory secondary analysis of the already completed
[native TURN/TCP probe](NATIVE_TURN_PROBE_V1.md). Its analysis specification was
committed after the probe's descriptive arm means had been read, so neither its
tests nor intervals are confirmatory. No controller, model, simulator dynamics,
frozen native recipe or counterfactual outcome was changed.

## Question and evidence boundary

The probe assigned 0.65, 0.85 or 1.05 times the sender-observed BWE at each
acknowledged three-second hold, independently with probability 1/3. This analysis
asks whether the **current** randomized assignment moves actual pre-RTP encoded
payload and the existing capture-request-to-pixel-readback endpoint during that
hold. The estimand averages over the factual histories produced by earlier IID
assignments. It does not estimate a history-conditioned action value or compare
whole-session policies.

The two outcomes were already defined by the probe: mean actual payload rate
divided by the pre-assignment BWE in its complete 1.8--2.6-second window, and
the share of eligible source requests read back within the fixed 150 ms
criterion. Every one of the 96 holds is retained; all windows are complete and
none of the assignments is clipped or aliased. The on-time denominator counts
unknown/missing readbacks as not on time, as in the probe.

Before recomputing this analysis, the runner checked all 82 files in the
registered raw capture directory against their entries in the 92-file local
evidence inventory, reconstructed all 16 peer summaries, and matched the
committed session summary byte-for-byte after canonical JSON serialization. The
independent audit was also rerun over all 16 raw wire logs. No raw file was
changed, removed or merged into the project.

The fixed-effect model includes peer and within-peer epoch indicators. Inference
uses a peer-clustered CR1 sandwich with a t reference on 15 degrees of freedom.
The three pairwise treatment contrasts for both outcomes form one six-test
Holm family at 0.05. These intervals are conditional on this small probe and
assume independent peer clusters; they do not quantify uncertainty over content,
network populations, transports, machines or browsers.

## Results

| Assigned BWE ratio | Holds | Actual payload / assignment BWE | On time |
|---:|---:|---:|---:|
| 0.65 | 37 | 0.580 | 78.8% |
| 0.85 | 34 | 0.721 | 68.3% |
| 1.05 | 25 | 0.881 | 83.0% |

The randomized action separated actual encoded output. The 1.05 arm exceeded
0.65 by **0.279** normalized payload units (95% conditional CI
**[0.187, 0.372]**, Holm-adjusted p **0.000063**). The 0.85--0.65 and
1.05--0.85 contrasts were also positive after the same correction. This is
actuator evidence on the tested stack.

No on-time contrast was resolved. For 1.05 versus 0.65, the estimated difference
was **+7.2 percentage points** (95% conditional CI **[-11.2, +25.5]**; adjusted
p **0.833**). The intervals for the other two contrasts also include zero. This
is inconclusive about delivered benefit or harm; actual encoded throughput is
not a QoE outcome.

## Decision

The findings support only a proximal factual conclusion: randomized requested
ratios move actual encoded payload on this probe, while this panel does not
resolve whether those changes improve its one-step delivery endpoint. They do
not establish safety, calibration, a useful state-dependent action choice,
episode-level value, benefit over a tuned whole-session baseline, or generality
to the earlier UDP experiments, different physical network mechanisms, or real
networks. Four procedural scene seeds, two authored capacity schedules, one
Chromium build, one machine and TURN/TCP remain the entire scope.

No candidate is promoted. The next useful evidence must vary native-observable
state and previously unused trace/content settings under a frozen prospective
design, then use independent roles for state-action value and selected-policy
calibration. Real-network testing remains necessary before any promotion.

## Reproduction

First rerun the full read-only wire audit into a **fresh path outside the
repository**. Then the analysis itself verifies the selected raw-file inventory,
source hashes, per-peer assignments and exact summary replay:

    uv run --frozen python -m media_rl.native_turn_audit \
      --capture /workspace/.cache/networkrlcd/working/native-turn-probe-v1 \
      --compact reports/native-turn-probe-v1 \
      --out /external/fresh-native-turn-audit.json

    uv run --frozen python -m media_rl.native_turn_action_diagnostic \
      --config configs/native_turn_action_diagnostic_v1.json \
      --out reports/native-turn-action-diagnostic-v1-reproduction

    uv run --frozen python tools/export_development_updates.py \
      --action-only \
      --action-out paper/generated-native-turn-action-diagnostic-v1-reproduction

The frozen analysis specification is
[configs/native_turn_action_diagnostic_v1.json](../configs/native_turn_action_diagnostic_v1.json).
Its numerical report and input/code provenance are under
[reports/native-turn-action-diagnostic-v1/](../reports/native-turn-action-diagnostic-v1/).
The manuscript tables and their export receipts are under
[paper/generated-native-turn-action-diagnostic-v1/](../paper/generated-native-turn-action-diagnostic-v1/).
