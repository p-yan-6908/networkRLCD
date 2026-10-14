# M1: steady-service BWE reliability qualified in development

M1 was preregistered in commit `4a67424` before any M1 capture. All eight
original support-only sessions completed without failures or replacements:
four fresh repeats for each reused V13 content clip, interleaved in the
registered seeded order. The service rate was the frozen synthetic constant
**1.4523718338280722 Mbps**; no measured trace was relabeled as synthetic
confirmation and no source was treated as new independent evidence.

All **8/8** passed unchanged native history/eligibility, 4 Mbps conditioning,
zero-jitter readback, TURN/TCP, bidirectional media, exact 36-tick replay,
actual-run clock and terminal-cleanup gates. All four held-out markers were
covered in every session; maximum interval width was **3.586 ms**, below
the unchanged 50 ms limit. All native decisions retained the common cap
and jitter target; **zero bitrate treatments** were assigned.

## Registered finite-repeat reliability screen

The first qualifying eleven-sample BWE history in `[18000,18300]` ms was
used in every session, with no changed window, threshold, history length
or eligibility bounds. The four-repeat spread per clip was compared with
the prospectively retained **0.25-octave** benchmark. Both clips passed.

| Reused development content | Four native census geometric means (kbps, repeat order) | Full spread (octaves) | Sample SD (octaves) | Screen |
| --- | --- | ---: | ---: | --- |
| Kampar boating | 1536, 1504, 1493, 1498 | 0.04086 | 0.01839 | Pass |
| Volga lock | 1480, 1464, 1510, 1506 | 0.04462 | 0.02127 | Pass |

Every repeat, qualifying history drift/range and all six pairwise differences
per clip are preserved in `reports/native-bwe-reliability-m1-summary.json`.
Those six differences share four sessions and are not six independent
observations. No population confidence interval, significance test, quality
estimate or action-effect regression was performed.

## What this resolves and what follows

Fresh native sessions can produce repeatable 18-second BWE measurements
under this particular steady-service recipe. Thus V13's failure is compatible
with a problem specific to its dynamic measured-profile contexts rather
than an unavoidable large spread in every fresh session. M1 does not prove
that dynamic traces caused the failure: it changes rate history, was run
in a separate batch and has only four repeats per clip at one rate. It does
not isolate probing, estimator lag, offered demand or queue history.

The scientifically justified continuation was completed as this separately
frozen development diagnostic, using only support variables. V13 remains
closed as a support-design failure: its repeatability requirements still
failed, its four-family/content ranges remain disjoint and its 64 action
sessions remain unrun. M1 cannot rescue or be pooled into that panel. No
conditional action value, delivery/QoE improvement, controller advantage
or broad network generalization has been established.

Before another confirmation, the measurement design needs development on
reused sources. The next informative design is a prospectively randomized
steady-versus-dynamic service-history comparison with interleaved fresh
sessions, or qualification of an **actual pre-action continuous BWE** modifier
that does not substitute a between-session census for sender state. Such
a formulation must be specified and qualified before a new untouched
content/network panel; retain unclipped actions, outcome definitions and
clock/TURN/readback/cleanup gates. Neither changing V13's census state nor
relaxing its repeatability rule is authorized by M1. Controller development
and V10 retuning remain closed.

## Evidence preservation

All **328 sealed session files** were SHA-256 verified before support
telemetry was projected. Only sender timing/BWE/validity, qualification,
assignment/readback and the inherited technical gate were decoded. Frame
quality, timely-delivery, sender encoded meter, receiver feedback and
per-hold relay outcomes remain unopened.

- Protocol SHA-256:
  `143501401fb23154d0c9fe96b57ec25ca8ac6698a1f82b2b533c702e1a1e9028`.
- Capture index SHA-256:
  `0faac30f3042ab68a838de02e39eeb0386b90975369824469ce51d797971370d`.
- Compact technical gate and execution summary:
  `reports/native-bwe-reliability-m1-gate.json` and
  `reports/native-bwe-reliability-m1-execution-result.json`.
- Private archive namespace: `native-bwe-reliability-m1-20261014-01`, pinned
  revision `f90bcd3fb6682b0c6e89cb18f8ab65d6e9cde677` in
  `p-yan/networkrlcd-results-archive`.
- Receipt:
  `docs/storage-receipts/native-bwe-reliability-m1-20261014-01.json`.
  Every remote object and all **350 archived files** passed fresh-download
  verification, including the support-only diagnostic summary. Local raw
  evidence and licensed originals were retained; zero files were deleted.
- V13 support figure and its source/checksum receipt:
  `reports/native-v13-support-repeatability.png` and
  `reports/native-v13-support-repeatability.json`. It plots the previously
  preserved census summaries only, with no new outcome access.
