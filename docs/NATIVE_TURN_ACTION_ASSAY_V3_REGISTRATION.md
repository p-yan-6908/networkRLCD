# Native TURN action-assay V3 replication registration

V3 is an independent factual replication of the V2b proximal randomized-hold
action assay. V2b's capture command printed arm summaries before the independent
wire audit; those outcomes are therefore exploratory, as recorded in its result
report. The V2b estimate that motivates this repeat is the lower 150 ms on-time
share at 1.05 versus 0.85 BWE (−3.785 percentage points, 95% conditional
interval [−6.711, −0.858], Holm-adjusted $p=0.0483$). V3 tests whether the
registered six-contrast pattern is reproducible on newly generated peers. It
does not pool V2b with V3 or narrow the family to the contrast that motivated
replication.

The design, seeds, source hashes, endpoint definitions, estimator and reading
rule are registered in
[`native_turn_probe_v3_action_replication.json`](../configs/native_turn_probe_v3_action_replication.json)
before capture. V3 uses 8 new procedural scene seeds (301–308), four unchanged
authored capacity-trace shapes, two repetitions per scene/trace cell, and a new
trial order. Each of 64 peers has six 3-second phases; every trace-by-phase cell
has at least two assignments to each of the 0.65, 0.85 and 1.05 BWE-relative
actions. New pseudo-randomization seeds change the assignments. No action,
endpoint, estimator, confidence, exclusion or promotion rule changes.

The primary endpoints remain (1) equal-hold actual pre-RTP encoded payload per
second divided by pre-assignment BWE in the 1.8–2.6 second window, and (2) the
request-weighted share read back within 150 ms, with missing or late readbacks
counted as failures. The peer- and within-peer-phase fixed-effects estimator,
peer-clustered CR1 covariance, $t_{63}$ reference, all six endpoint-by-contrast
tests and one Holm adjustment at familywise 0.05 remain unchanged. All 384 holds
must retain both endpoint definitions; no replacement peers or per-protocol
rescue are allowed.

`tools/native_turn_action_assay_v3.py` checks the new crossing, order, assignment
support and seeds, then delegates to the byte-frozen V2 capture and analysis
implementations. The V2 audit implementation independently replays the factual
sender and queue histories. The capture runner prints endpoint summaries at
completion, so its stdout and stderr must be suppressed and left unread until
the full inventory has been rehashed and the independent audit has passed. If
capture fails, preserve and inspect only the failure receipt and file inventory;
do not open outcome-bearing session summaries before the audit. The required
sequence is:

    uv run --frozen python tools/native_turn_action_assay_v3.py capture \
      --spec configs/native_turn_probe_v3_action_replication.json \
      --raw-out /home/agent/.cache/networkrlcd/working/v3 \
      --report-out reports/native-turn-action-assay-v3 >/dev/null 2>&1

    uv run --frozen python -m media_rl.native_turn_audit \
      --capture /home/agent/.cache/networkrlcd/working/v3 \
      --compact reports/native-turn-action-assay-v3 \
      --out reports/native-turn-action-assay-v3/independent-audit.json

    uv run --frozen python tools/native_turn_action_assay_v3.py analyze \
      --spec configs/native_turn_probe_v3_action_replication.json \
      --capture /home/agent/.cache/networkrlcd/working/v3 \
      --compact reports/native-turn-action-assay-v3 \
      --inventory reports/native-turn-action-assay-v3/local-evidence-inventory.json \
      --audit reports/native-turn-action-assay-v3/independent-audit.json \
      --out reports/native-turn-action-assay-v3-analysis

The replication remains development evidence on the same machine, Chromium
build, localhost TURN/TCP path, userspace queue and 25 ms propagation setting.
New procedural scenes and capacity schedules are not new physical network
families. The outcomes are not human QoE, episode-level safety, a learned-policy
effect, selected-action calibration, whole-session baseline advantage, UDP
transfer or real-network validation. No simulator counterfactuals or controller
promotion are involved. Raw evidence stays external and unarchived until a
receipt-pinned archive restore verifies its full inventory; no existing capture
is overwritten or pruned.
The completed independent analysis is documented in the [V3 results](NATIVE_TURN_ACTION_ASSAY_V3_RESULTS.md). It confirms the cap-to-payload response but does not reproduce the V2b on-time contrast.
