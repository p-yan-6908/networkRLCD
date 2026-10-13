# Native clock/action TURN/TCP V7 results

## Scope and gates

V7 was a fresh, nonconfirmatory, whole-session randomized comparison of
sender-estimate ratios 0.65 and 1.05. Its eight generated-scene seed clusters
are analyzed as paired clusters. It is not pooled with V3–V6, the archived
range sessions, recorded-video studies, or synthetic evidence.

The frozen V7 protocol is
[`configs/native_clock_action_probe_turn_tcp_v7.json`](../configs/native_clock_action_probe_turn_tcp_v7.json)
(SHA256 `2eeaf29d04fdfdd63de57132bbec8308957a330180f3f9beeb6b123a1e75b85e`).
The raw capture remains at
`/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v7/`. Its capture
index SHA256 is
`8bbcc5de8b6d7e2f79dffb2abb07d85418a54dc8867deb2e865658cc9683f037`; the
outcome-blind clock/transport gate SHA256 is
`48af59918b64103ec050f9ada709b94f8f813ca671d617ea64dbfa856e38aa9b`.

All 32 sessions passed checksum, TURN/queue transport, exact queue replay, and
actual-run clock qualification before outcomes were opened. All 32 sender-to-
relay maps covered the four held-out markers; there were no clock failures.
The separate qualified calibration covered 60/60 held-out exchanges, with a
maximum mapped-time interval width of 2.6424 ms. The managed Chromium policy
remained `WebRtcIPHandling=disable_non_proxied_udp` and its fingerprint did not
change. Each session had 183–184 registered sender assignments, every cap
readback matched, and all sessions had at least one complete hold window in
each of high, collapse, and recovery.

All per-session file hashes were checked before sender, frame, or relay
telemetry was read. The prespecified queue replay was exact. No queue overflow
or dropped wire bytes occurred in either arm. Per-hold relay bytes below are
offered wire volume, with boundary-ambiguous events included in the possible
count; they are not a measure of Internet-path cost.

## Paired contrasts

The estimator is 0.65 minus 1.05 at each scheduled state. Interactions are the
collapse or recovery contrast minus the high-state contrast. Intervals are
unadjusted 95% t intervals over eight generated-scene seed clusters (7 degrees
of freedom). They are development estimates; the V7 plan did not register a
multiple-comparison adjustment.

| State / interaction | On-time fraction | Offered wire bytes | Mean PSNR on on-time frames |
|---|---:|---:|---:|
| High: 0.65 − 1.05 | −0.0424 [−0.0748, −0.0100] | −10,923 [−18,523, −3,323] | −0.479 dB [−1.003, 0.045], n=8 |
| Collapse: 0.65 − 1.05 | +0.2152 [+0.0958, +0.3346] | +4,776 [+913, +8,639] | Not estimable; almost no on-time frames at 1.05 |
| Recovery: 0.65 − 1.05 | +0.1439 [−0.1064, +0.3941] | −15,663 [−21,080, −10,246] | −0.658 dB [−0.895, −0.422], n=7 |
| Collapse − high interaction | +0.2576 [+0.1222, +0.3930] | +15,699 [+4,779, +26,619] | Not estimable |
| Recovery − high interaction | +0.1863 [−0.0809, +0.4534] | −4,740 [−13,226, +3,747] | −0.176 dB [−0.968, +0.616], n=7 |

The collapse-versus-high interaction intervals exclude zero for both the
150 ms on-time frame fraction and relay offered bytes. In this registered
capacity schedule, 0.65 had more on-time frames and more offered bytes during
collapse, while 1.05 had more on-time frames and offered bytes during high
capacity. Recovery remains mixed: 0.65 used fewer relay bytes and its on-time
interval is wide, while delivered-frame PSNR favored 1.05 among the seven
clusters with an estimable contrast.

These contrasts establish action-by-scheduled-state differences in this local
setup. They do not establish a sender-observable state rule, a full-session
policy gain, Internet-path behavior, human QoE, or deployment safety. The
one-sided tradeoffs and unadjusted intervals also do not justify fitting or
promoting a controller. The eight clusters are seeds from one generated scene
algorithm, not independent content families or network sources.

The machine-readable analysis is
[`reports/native-clock-action-turntcp-v7-analysis.json`](../reports/native-clock-action-turntcp-v7-analysis.json)
(SHA256 `3e78b850e351f8f34fea6afb244376931e4cffd7c50bdf9c8ec8b3743e5c725c`).
V3 and all earlier frozen evidence remain unchanged.

## Next validation

The next test should randomize a sender-observable, pre-action state rule
against the strong fixed 0.65 baseline on fresh scene seeds. It should score
whole-session receiver delivery/quality and relay cost, verify every native cap
readback, and retain the same actual-run clock and queue gates. The rule must be
fixed before the new capture; V7's scheduled phase labels cannot be treated as
sender observations. Any such comparison remains a validation of that rule,
not automatic controller promotion.
