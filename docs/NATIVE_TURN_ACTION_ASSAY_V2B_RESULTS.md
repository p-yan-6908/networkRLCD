# Native TURN randomized-hold action assay V2b results

V2b completed 64 factual WebRTC peers and all 384 registered randomized holds.
The capture's local inventory contains 323 regular files / 669,573,522 bytes;
its SHA-256 receipt is
`e5ebab2725a8643246e2b9804a8498ec1ae99bec6bcaec63dffcb17e5e50ea2b`.
Independent replay checked all 64 sender and wire histories, matched every
compact session summary, verified the FIFO/capacity accounting, and confirmed
the V2 closing ledger reaches the end of each raw event stream. The full raw
capture remains external at `/home/agent/.cache/networkrlcd/working/v2b/`; it is
unarchived and has not been pruned.

## Outcome-exposure qualification

The capture command printed unadjusted per-arm payload and on-time summaries
after collection, and those values were seen before the independent audit ran.
This was an avoidable process leak. Although V2's endpoint family and estimator
were frozen before capture, the analysis is classified here as exploratory
development evidence, not a confirmatory result. The V3 registration adds a
strict blind reading order and uses new scene and assignment seeds. V2b is not
pooled with V3 or used to tune a controller.

## Registered proximal outcomes

All assigned rows were retained, there were no clipped/aliased assignments, and
both endpoints were complete for every hold. The fixed-effects model uses peer
and within-peer phase effects, peer-clustered CR1 covariance with 63 degrees of
freedom, and one Holm adjustment across six endpoint-by-contrast tests.

| Assigned BWE ratio | Holds | Actual payload / BWE | On-time / eligible requests | On time |
|---:|---:|---:|---:|---:|
| 0.65 | 116 | 0.582 | 9,519 / 10,399 | 91.5% |
| 0.85 | 135 | 0.745 | 11,416 / 12,219 | 93.4% |
| 1.05 | 133 | 0.802 | 10,896 / 12,031 | 90.6% |

| Outcome | Contrast | Difference (95% conditional interval) | Raw $p$ | Holm $p$ |
|---|---|---:|---:|---:|
| Actual payload / assigned BWE | 0.85 − 0.65 | +0.1845 [+0.1487, +0.2203] | 3.88e−15 | 2.33e−14 |
| Actual payload / assigned BWE | 1.05 − 0.65 | +0.2369 [+0.1908, +0.2831] | 4.51e−15 | 2.33e−14 |
| Actual payload / assigned BWE | 1.05 − 0.85 | +0.0524 [+0.0021, +0.1028] | 0.0416 | 0.1247 |
| On-time requests (percentage points) | 0.85 − 0.65 | +2.304 [−1.001, +5.610] | 0.1685 | 0.3370 |
| On-time requests (percentage points) | 1.05 − 0.65 | −1.481 [−4.851, +1.890] | 0.3834 | 0.3834 |
| On-time requests (percentage points) | 1.05 − 0.85 | −3.785 [−6.711, −0.858] | 0.0121 | 0.0483 |

The action request moved encoded output on this stack. The on-time estimate for
1.05 versus 0.85 was lower and narrowly passed this exploratory six-test
adjustment; the 1.05-versus-0.65 delivery interval includes zero. This is a
single-run proximal 150 ms pixel-readback proxy. It is not human QoE, a learned
controller effect, an episode-level safety result, selected-policy calibration,
or an advantage over whole-session baselines. Pattern-specific arm summaries
are descriptive only and do not identify treatment-effect modification.

The assay uses one cloud machine, one Chromium build, one localhost TURN/TCP
relay and one userspace queue mechanism with 25 ms propagation. Four authored
capacity shapes do not constitute distinct physical network families; the
content is procedural rather than licensed natural video. It provides no UDP,
archived-pilot, unseen-family or real-network validation. No controller was
fitted or promoted, and no native counterfactuals were generated.

The independent compact analysis is in
[`reports/native-turn-action-assay-v2b-analysis/report.json`](../reports/native-turn-action-assay-v2b-analysis/report.json),
with the separate audit and inventory under
[`reports/native-turn-action-assay-v2b/`](../reports/native-turn-action-assay-v2b/).
The V2 capture output-path and inventory failures remain preserved in
[`NATIVE_TURN_ACTION_ASSAY_V2A_FAILURE_AND_V2B.md`](NATIVE_TURN_ACTION_ASSAY_V2A_FAILURE_AND_V2B.md).
The blind independent replication is registered in
[`NATIVE_TURN_ACTION_ASSAY_V3_REGISTRATION.md`](NATIVE_TURN_ACTION_ASSAY_V3_REGISTRATION.md).
The V3 capture, full inventory and independent replay passed. Its delivery-proxy contrast did not reproduce the V2b estimate; see the complete [V3 result record](NATIVE_TURN_ACTION_ASSAY_V3_RESULTS.md).
