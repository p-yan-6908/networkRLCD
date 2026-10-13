# Native clock/action TURN/TCP V9 results

## Capture and qualification

V9 micro-randomized the 0.65 and 1.05 sender-BWE-relative cap actions at six
three-second hold boundaries in each of 48 sessions. The pre-action Chrome BWE
split was fixed at 500 kbps. The study used twelve fresh generated-scene seed
clusters, with four session repetitions per seed. This estimates proximal
action effects under the V9 state distribution; it is not a whole-session
policy comparison.

The registered protocol is
[`configs/native_clock_action_probe_turn_tcp_v9.json`](../configs/native_clock_action_probe_turn_tcp_v9.json)
(SHA256 `fff551a003c703e1dc38886e9f70a7df700c9d0904a2efc88ac7062492c93484`).
Raw sessions remain outside Git at
`/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v9/`. The capture
index SHA256 is
`6e794eb49b55cbc2b927330eb581c54f4be5f08500242d31e878906b171abe6f`; the
outcome-blind clock/transport gate SHA256 is
`8246730530a9667892b1a22319893e9c06aaf6b54d35d39379bdb3e158b0c5a3`.

All 48 sessions sealed and passed checksum, relay-only TURN/TCP, bidirectional
queue replay, policy fingerprint, and actual-run clock checks. All held-out
marker exchanges were covered; the widest feasible mapped-time interval was
3.633 ms. The 288 epoch-start assignments replayed exactly, and requested caps
matched both native proposals and readbacks. The pre-outcome gates passed
before sender, receiver, and relay-hold outcomes were analyzed.

Eleven of twelve scene-seed clusters met the registered minimum of two hold
windows in each state/action cell. Seed 8001 lacked that coverage and was
excluded from the paired cell analysis. The primary interval therefore uses
eleven clusters (10 degrees of freedom), while keeping every session in the
sealed evidence record. There were no guaranteed queue-drop bytes.

## State-conditional action estimates

Estimates are 1.05 minus 0.65, formed within each seed and then summarized
across the eleven complete clusters with unadjusted 95% t intervals. The
primary endpoint is the high-BWE action effect minus the low-BWE action effect
on the 150 ms on-time fraction.

| Outcome | BWE >= 500 kbps | BWE < 500 kbps | High minus low interaction |
|---|---:|---:|---:|
| On-time fraction | +17.6 pp [−11.9, +47.1] | +19.4 pp [+5.7, +33.1] | −1.8 pp [−29.4, +25.8] |
| Sampled RGB PSNR among on-time frames | +1.495 dB [+1.149, +1.841] | +0.987 dB [+0.781, +1.193] | +0.508 dB [+0.077, +0.938] |
| Guaranteed relay wire bytes per hold | +20.6 kB [+7.2, +34.0] | +9.17 kB [+7.71, +10.62] | +11.45 kB [−1.93, +24.83] |

The preregistered primary delivery interaction is inconclusive. The secondary
PSNR interaction is positive in this local panel, while the differential
relay-byte cost remains uncertain. The separate within-state estimates show
that 1.05 increased sampled PSNR in both BWE strata; it also increased local
relay bytes in both. The on-time estimate is positive in both strata, but its
high-BWE interval is wide. These results motivate a direct whole-session
comparison of a fixed BWE-threshold rule against fixed 0.65. They do not
justify a fitted controller or a policy-value claim by themselves.

The machine-readable report is
[`reports/native-clock-action-turntcp-v9-analysis.json`](../reports/native-clock-action-turntcp-v9-analysis.json)
(SHA256 `a20a40e4417cbd2992af71b695d0972b601dc6178394e7dbe41d544c67a12617`).
V3–V8, archived sessions, recorded-video results, and synthetic evidence stay
frozen and are not pooled with V9. This remains one local Chromium build, one
scene-generation algorithm, and one queue/capacity schedule; sampled RGB PSNR
and the pixel deadline are proxies, not human QoE or measured-Internet
validation.
