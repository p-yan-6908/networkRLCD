# Native clock/action TURN/TCP V8 results

## Capture and action qualification

V8 compared two whole-session randomized policies on twelve fresh generated
scene seeds, with two repetitions per policy per seed. The strong comparator
was fixed sender-estimate ratio 0.65. The candidate was the existing native
sender-only 0.85-BWE headroom rule, applied once per registered three-second
hold. It received no capacity, queue, scheduled-state, or receiver outcome
labels. V8 was analyzed separately from all prior captures.

The registered protocol is
[`configs/native_clock_action_probe_turn_tcp_v8.json`](../configs/native_clock_action_probe_turn_tcp_v8.json)
(SHA256 `102aba4d5d22a3ef3b33d17216ee8fe89b8a5addf2d96f2fcb35c5dedd5139c0`).
The raw capture is retained at
`/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v8/`. Its capture
index SHA256 is
`21419782f45dc9c8ac096071ad299b86b04cd8f063199acbea6deee3503afc4c`; the
outcome-blind clock/transport gate SHA256 is
`98c47e187b485a0b65c3a3ad6c05ab10e6bf4f37adfc5ecad7b9e83aa30ea9c5`.

All 48 sessions passed file integrity, relay-only TURN/TCP transport, exact
two-way queue replay, and actual-run clock qualification. Every session
covered all four held-out markers; the maximum held-out mapped-time interval
width was 3.201 ms. All 48 sessions had two complete hold windows in each
scheduled state. Across 8,793 logged sender decisions, every assigned cap
matched the proposal and native readback. The BWE rule was replayed at all 144
assignment starts from the saved pre-action sender observation, with no
mismatch. The managed Chromium policy remained unchanged.

All session checksums passed before any outcome read. Queue drops were zero.
The possible and guaranteed relay byte estimates were close, so clock-boundary
ambiguity had little effect on these summaries.

## Policy contrasts

Contrasts are BWE-headroom 0.85 minus fixed 0.65, paired at the generated-scene
seed cluster after averaging the two repetitions. Intervals are unadjusted 95%
t intervals across 12 clusters (11 degrees of freedom). The primary endpoint
is the receiver on-time frame fraction across the six registered 800 ms
windows per session.

| Outcome | BWE 0.85 − fixed 0.65 | 95% interval |
|---|---:|---:|
| On-time receiver frame fraction, all states | −0.0030 | [−0.1025, +0.0966] |
| Mean sampled RGB PSNR on on-time frames | −0.687 dB | [−1.465, +0.090] |
| Guaranteed offered relay wire bytes, all windows | −37,575 bytes | [−52,769, −22,380] |
| Possible offered relay wire bytes, all windows | −37,508 bytes | [−52,897, −22,119] |
| Queue drop bytes | 0 | [0, 0] |

The BWE policy used fewer local relay bytes, but the overall on-time and PSNR
intervals include zero and do not establish an aggregate delivery or quality
gain over fixed 0.65.

| Scheduled state | On-time fraction difference | Offered wire byte difference | PSNR difference |
|---|---:|---:|---:|
| High | −0.1616 [−0.1946, −0.1287] | −20,935 [−38,598, −3,271] | −0.423 dB [−1.120, +0.273] |
| Collapse | +0.1866 [+0.0417, +0.3315] | −6,929 [−11,290, −2,568] | −0.210 dB [−0.361, −0.059] |
| Recovery | −0.0337 [−0.2193, +0.1520] | −9,711 [−11,717, −7,704] | −0.384 dB [−0.539, −0.228] |

The collapse-minus-high interaction in on-time fraction is +0.3482
[+0.1828, +0.5136]. Thus this fresh panel again shows treatment differences
across scheduled states. It also shows that the tested sender-only headroom
rule did not convert that heterogeneity into a full-panel delivery or PSNR
gain over fixed 0.65. Lower relay volume alone is not a QoE improvement.

These results do not support fitting or promoting another controller. They
remain bounded to one Chromium build, one loopback userspace relay, one scene
algorithm, and one capacity schedule. The RGB deadline and PSNR are proxies,
not human QoE or measured-Internet validation. V3–V7 and all archived or
synthetic evidence remain unchanged and unpooled.

The machine-readable report is
[`reports/native-clock-action-turntcp-v8-analysis.json`](../reports/native-clock-action-turntcp-v8-analysis.json)
(SHA256 `d324e806c5ebd38ce6497994e73710c3c0cfab3d0ea86e0de16bf1a728b8afd4`).

## Next validation

V9 should randomize 0.65 versus 1.05 at each three-second hold after observing
the pre-action sender state, using a fixed BWE split at 500 kbps. This directly
tests whether that sender-observable state identifies different causal action
values; it is not a fitted rule. Keep action propensity 0.5 within each state,
measure outcomes only in the registered post-ack windows, cluster uncertainty
by fresh generated-scene seed, and retain the same clock/transport gates. A
separate whole-session policy comparison against fixed 0.65 would still be
required before claiming policy gain.
