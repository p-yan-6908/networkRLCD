# Native TURN randomized-hold action assay V3 results

V3 is the independent replication registered before its capture in
[the V3 registration](NATIVE_TURN_ACTION_ASSAY_V3_REGISTRATION.md). It uses
64 fresh native peers, 8 new procedural scene seeds, new per-hold assignment
seeds and a new randomized trial order. The outcome family and estimator are
unchanged from V2b. Capture stdout/stderr were suppressed; no arm summaries
were opened before the inventory and independent audit passed.

## Integrity and completeness

All 64 peers and 384 assigned holds completed. Payload and readback endpoints
are complete for every hold; no assignment clipped or aliased. The independently
rehashed external raw inventory has 323 files / 665,844,656 bytes, with SHA-256
0990a57d8d74067d9ba560b44ce1e438502a57d976aa8cdcbb56cd993482dda9.
All 64 sender summaries were recomputed. Independent wire replay passed FIFO and
capacity accounting for all peers; all raw files remained unchanged and every
closing ledger reaches the end of its raw event stream with zero service suffix.
The capture remains external at /home/agent/.cache/networkrlcd/working/v3/;
it is unarchived and no raw evidence was pruned.

## Registered outcomes

The analysis retains every assigned row and uses peer and within-peer-phase
fixed effects, peer-clustered CR1 covariance with 63 degrees of freedom, and one
Holm adjustment over all six outcome-by-contrast tests.

| Assigned BWE ratio | Holds | Actual payload / BWE | On-time / eligible requests | On time |
|---:|---:|---:|---:|---:|
| 0.65 | 130 | 0.587 | 10,666 / 11,720 | 91.0% |
| 0.85 | 134 | 0.722 | 10,943 / 12,036 | 90.9% |
| 1.05 | 120 | 0.824 | 9,845 / 10,898 | 90.3% |

| Outcome | Contrast | Difference (95% conditional interval) | Raw $p$ | Holm $p$ |
|---|---|---:|---:|---:|
| Actual payload / assigned BWE | 0.85 − 0.65 | +0.1449 [+0.1104, +0.1793] | 7.01e−12 | 3.51e−11 |
| Actual payload / assigned BWE | 1.05 − 0.65 | +0.2578 [+0.2181, +0.2975] | 1.92e−19 | 1.15e−18 |
| Actual payload / assigned BWE | 1.05 − 0.85 | +0.1129 [+0.0630, +0.1629] | 2.79e−5 | 1.12e−4 |
| On-time requests (percentage points) | 0.85 − 0.65 | +2.208 [−1.763, +6.179] | 0.2707 | 0.8122 |
| On-time requests (percentage points) | 1.05 − 0.65 | +0.801 [−3.129, +4.732] | 0.6851 | 1.0000 |
| On-time requests (percentage points) | 1.05 − 0.85 | −1.407 [−5.917, +3.104] | 0.5354 | 1.0000 |

The action-to-payload result reproduces. The V2b 1.05-versus-0.85 on-time
contrast was −3.785 pp [−6.711, −0.858], Holm $p=0.0483$, but V3 estimates
−1.407 pp [−5.917, +3.104], Holm $p=1.000$. This is a failed replication of
the adjusted V2b delivery contrast, not evidence that a delivery cost is absent:
the V3 interval still admits a reduction of nearly six percentage points.
V2b and V3 remain separate; no pooled or post-hoc combined estimate is used.

The on-time outcome is the registered 150 ms capture-request-to-pixel-readback
proxy, not human QoE. This independent replication uses the same one-machine,
one-Chromium, localhost TURN/TCP and userspace-queue setup with fixed 25 ms
propagation. New procedural scenes and authored capacity schedules are not
unseen physical network families or real-network conditions. The panel does
not identify history-conditional action value, a learned controller effect,
episode-level safety, selected-policy calibration or whole-session advantage
over tuned baselines. No model was fitted or promoted and no native
counterfactual outcomes were created.

The compact capture, local inventory, independent audit and analysis receipts
are under
[the V3 capture reports](../reports/native-turn-action-assay-v3/) and
[the V3 analysis reports](../reports/native-turn-action-assay-v3-analysis/).
