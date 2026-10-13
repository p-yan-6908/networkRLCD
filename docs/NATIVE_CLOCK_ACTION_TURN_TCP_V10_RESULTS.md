# Native clock/action TURN/TCP V10 results

## Capture and qualification

V10 compared the frozen sender-only BWE-threshold rule with a fixed
0.65 BWE-relative action in 48 whole-session trials: twelve fresh scene seeds,
two repetitions per policy per seed. The threshold rule used ratio 1.05 when
pre-action sender BWE was at least 500 kbps, and 0.65 below that boundary.
Both policies selected from the current pre-action sender BWE at each
three-second hold boundary.

The preregistered protocol is
[`configs/native_clock_action_probe_turn_tcp_v10.json`](../configs/native_clock_action_probe_turn_tcp_v10.json)
(SHA256 `30f51e5240cd142533bc198c5b7e50d584327e022300d00ce7f06ef850b178fd`).
The raw capture remains outside Git at
`/home/agent/.cache/networkrlcd/native-clock-action-turntcp-v10/`. Its capture
index SHA256 is
`ed73cb4c8792ec3e4f58cbbae781a3ef5819683357a35adbc154bc9854b61762`; the
outcome-blind clock/transport gate SHA256 is
`448fb02eb49250ae1d99341d77e4625324693fc43ff83570db2f93f0d5244024`.

All 48 sessions sealed with no capture failures. Checksums, TURN/TCP transport,
bidirectional media, exact queue replay, and the unchanged browser policy
passed for all sessions. All 48 actual-run sender-to-relay clock maps passed;
the widest held-out mapped-time interval was 3.212 ms, below the registered
50 ms limit. The 288 policy-boundary assignments replayed, and every requested
cap matched the proposal and native readback.

The threshold policy selected ratio 1.05 for 46 of its 144 holds and 0.65 for
98; the fixed policy selected 0.65 in all 144 holds. The threshold policy's
1.05 holds were distributed across the registered high and collapse phases;
it selected 0.65 for all recovery-phase holds. These counts describe the
executed rule and are not independent outcome observations.

## Whole-session policy contrast

Contrasts are threshold rule minus fixed 0.65. Each policy's two session
repetitions were averaged within each scene seed, then paired across twelve
seed clusters. Intervals are unadjusted 95% t intervals (11 degrees of
freedom). The primary is the on-time receiver frame fraction across the six
registered post-acknowledgment windows.

| Outcome | Threshold rule − fixed 0.65 | 95% interval |
|---|---:|---:|
| On-time receiver frame fraction | −14.1 percentage points | [−22.6, −5.5] |
| Sampled RGB PSNR among on-time frames | +0.257 dB | [−0.132, +0.646] |
| Guaranteed offered relay bytes | −2,438 bytes | [−12,120, +7,244] |
| Possible offered relay bytes | −2,647 bytes | [−12,402, +7,107] |
| Queue drop bytes | 0 | [0, 0] |

The threshold rule's primary delivery interval is negative. Its overall PSNR
and relay-byte intervals include zero; lower relay volume does not offset the
measured delivery loss. By scheduled phase, the rule's on-time contrast was
−0.3 pp [−3.3, +2.8] in high, −31.3 pp [−47.0, −15.6] in collapse, and
−10.4 pp [−25.9, +5.0] in recovery. The corresponding PSNR contrasts were
+1.245 dB [+0.736, +1.755], −0.633 dB [−0.684, −0.582], and −0.583 dB
[−0.777, −0.389]. The high-phase PSNR increase did not produce a whole-session
delivery gain.

This directly tested V9's fixed BWE split against the strong baseline and did
not establish policy value. No controller was fitted or promoted. The result
does not support searching another threshold on these same scene and queue
families; the next meaningful validation requires independently sourced
content and a measured network family.

## Analysis correction record

The first post-gate analysis attempt stopped before writing an estimate. Its
validator compared each later sender BWE sample within a hold against the
saved BWE from that hold's action boundary. The action cap remains fixed during
the hold, while BWE can move. The corrected replay checks the saved BWE against
the actual sender observation at each of the six epoch starts, then checks the
policy assignment, proposal, cap formula, and native readback for every
decision. All 288 epoch starts and every subsequent decision passed. The
capture, protocol, checksums, and acceptance thresholds were not changed.

The correction is isolated in
[`tools/native_turn_clock_action_probe_v10_reanalysis.py`](../tools/native_turn_clock_action_probe_v10_reanalysis.py)
(SHA256 `130a50b579508fb60717dbbb0dd0817dbd1f02c0ed167074d16954c5866e049b`).
The machine-readable report is
[`reports/native-clock-action-turntcp-v10-analysis.json`](../reports/native-clock-action-turntcp-v10-analysis.json)
(SHA256 `9ca5df3fc70cb8f81ac5dd94b4e4057d78e91976b41bcb21ae73bbce19c1d162`).
The correction and report preserve the original registered analyzer and raw
session evidence.

V3–V9, archived sessions, recorded-video evidence, and synthetic studies
remain unchanged and unpooled. V10 remains bounded to one local Chromium
build, one generated-scene algorithm, and one local queue/capacity schedule.
The 150 ms pixel-readback and sampled RGB PSNR are proxies, not human QoE or
measured-Internet validation.
