# TURN/TCP action V6 clock-gate result

V6 captured and sealed all 32 preregistered sessions. Checksum integrity passed
before any outcome inspection:

- protocol SHA256: d1edb0aca40e9e54ed2f5371671f950d6644df954151ca7e6ed71da79ef99648
- capture-index SHA256: acafe0778cd9c0d67e1c7efa42c26036a6476ae60121d880105093230dbc46bb
- actual-run gate SHA256: 09ed6e6dd17b0aec769f358e791cb341d7e976d447d8d43b08acc609720715f9

The outcome-blind gate failed clock qualification: 11/32 sessions passed the
four held-out exchanges. All 32 passed TURN/queue transport and exact packet
and byte replay. Sender observations, frame outcomes, per-hold relay events,
QoE, and action effects were not opened or estimated.

## Actual-run clock checks

Twenty-one sessions missed the held-out final marker `m0011`; two of those also
missed post-high marker `m0003`. The maximum feasible widths were all below
5.1 ms and therefore within the unchanged 50 ms limit. Coverage still failed.
The final marker was placed in the holdout set after the last training marker
several seconds earlier, so the V6 marker design did not adequately validate
the session-end mapping.

## TURN and queue checks

All 32 sessions completed relay-only TURN/TCP gathering and established
nominated pairs. The managed policy remained `disable_non_proxied_udp` with no
runner modification. Packet and byte replay matched offered, dropped, served,
and forwarded totals in both directions; all source-port, forward-count,
capacity, queue-bound, conservation, and send-error checks passed.

Across the panel, A-to-B recorded 128 accounted overflow packets / 136,140
wire bytes in 15 sessions; B-to-A had no drops. These are transport diagnostics
only because the actual-run clock gate failed.

The diagnostic-only report is
[native-clock-action-turntcp-v6-gate-diagnostic-only.json](../reports/native-clock-action-turntcp-v6-gate-diagnostic-only.json)
(SHA256 eb9917acc4d83c892789cdd17fcbb02e2947583f97f4798d404ce52d8f361269).
It contains no sender, frame, QoE, per-hold relay, or action telemetry.

V6 remains frozen and excluded from V3, V4, V5, archived native, recorded-video,
and synthetic evidence. A new independent design should keep the final marker
in training and use a mid-recovery clock exchange as the fourth held-out check,
with all thresholds unchanged.
