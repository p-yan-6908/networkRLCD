# Native clock alignment and state-conditioned action probe V1

## Status and scope

This is a new development probe. It does not change the frozen V3 result, the
targeted 20-session restore or replay, the earlier native range pilot, or the
instrumentation-only clock-marker plan. No old evidence is reinterpreted. The
probe uses deterministic generated canvas scenes with the local native browser
WebRTC stack and owned userspace UDP relay. It is not a representative video
corpus, physical network, human QoE, or deployment evaluation. Its evidence is
kept separate from recorded-video, simulator, and synthetic policy evidence.

The runtime is local Chromium plus a Node relay on loopback. Every capture uses
the same separately versioned recorder. Its panel, recorder, module snapshots,
browser build, raw files, and checksums are retained per session.

## Clock calibration, before outcome capture

`clock_marker_calibrate_v1.mjs` sends 120 sequential no-op HTTP exchanges at
500 ms intervals over about one minute. It records browser `performance.now()`
immediately before request and after response, and Node `performance.now()`
after the complete request body and immediately before response. IDs and the
browser send time are echoed and recorded at both endpoints. This calibration
collects no media, frame, action, or QoE data.

For each exchange, require the positive affine mapping
`Node_ms = alpha * Browser_ms + beta` to satisfy:

```text
alpha * browser_send_ms + beta <= node_receive_ms
node_send_ms <= alpha * browser_receive_ms + beta
```

The feasible set is the full polygon under `0.98 <= alpha <= 1.02`; it is not
reduced to a fitted point. Fit exchanges with even indices and validate the odd
indices without adding them to the fit. Allow 1 ms for timestamp quantization,
request scheduling, and short-run affine approximation. This tolerance is
separately reported and remains far below the 50 ms mapping-width limit.
Calibration passes only if all 60
held-out exchanges are causally covered by every feasible mapping, the feasible
set is nonempty, and the maximum held-out mapped-time interval is at most
50 ms. Failure ends the action study before any outcome capture.

The native recorder repeats marker exchanges at measurement start, each of the
three phase transitions, and measurement end. For each session, fit even-indexed
markers, validate odd-indexed markers, then use the complete feasible set for
relay-event assignment only after that session passes the same coverage and
50 ms width checks. All mapped event bounds are retained. Relay offers count as
belonging to an action window only if every feasible mapping puts them in that
window; possible and boundary-ambiguous packets/bytes remain separately
reported. Pre-schedule and post-schedule offers are retained in reconciliation.

## Action study frozen before capture

- **Question:** In the native local WebRTC/UDP-relay setup, do the 0.65 and 1.05
  sender-estimate cap ratios have different delivery cost or pixel-readback
  outcomes in high, collapse, and recovery states?
- **Strong baseline:** 1.05 times the sender’s estimate, matching the existing
  native range reference. The comparator is 0.65 times that estimate. The
  existing `LevelSampler` freezes the estimate at assignment, applies the
  requested cap through native `RTCRtpSender.setParameters`, reads the applied
  cap back, and holds the assignment for at least 3 seconds. The two arms are
  separate sessions; no within-session treatment switching is used.
- **Schedule:** the existing collapse-recovery schedule: 1.2 Mbit/s high for
  6,000 ms, 0.35 Mbit/s collapse for 6,000 ms, then 1.2 Mbit/s recovery for
  6,600 ms. Each planned sender hold uses the existing 1,800–2,600 ms endpoint
  window after its browser-clock action acknowledgement.
- **Content and blocks:** eight fixed generated-scene seeds, two repetitions per
  seed, and both action levels in every seed/repetition block (32 sessions).
  There are eight seed clusters, not 32 independent content sources. Within
  each block the two level orders are randomized; order is balanced across the
  16 blocks using seed `20261013`. The single fixed network schedule and scene
  generator limit generalization.
- **Primary measures:** on-time source-frame readback share at the existing
  150 ms application deadline, mean paired sampled RGB PSNR for on-time frames,
  and A-to-B relay wire bytes and drops in the validated per-hold endpoint
  windows. PSNR is a synthetic pixel proxy, not human QoE. Relay cost is shown
  with guaranteed and possible event bounds.
- **Analysis unit:** seed. Average the two repetitions within seed and action,
  then report paired 0.65-minus-1.05 differences across eight seeds with a
  two-sided 95% t interval (`df=7`). Report each state and action-by-state
  contrasts. Do not pool these captures with V3, the archived native sessions,
  recorded-video sources, or simulator/synthetic controller results.
- **Integrity and missingness:** freeze the protocol, source hashes, randomized
  order, and analysis code before capture. Keep each failed or incomplete run;
  do not retry it or replace its cell. Seal every session file inventory before
  analysis, then verify all hashes before parsing telemetry or QoE.
- **Stopping:** no controller is fit or promoted by this probe. Controller
  work remains frozen unless replicated factual evidence establishes a
  state-dependent benefit over the 1.05 baseline with a paired interval that
  excludes zero, an action-by-state interaction that excludes zero, no
  material on-time loss in the other measured state, and a result robust to
  ambiguous relay-event bounds. This small development probe alone cannot
  establish that condition.

## Implementation and capture

The separately versioned `benchmarks/native_rtc/clock_action_episode_v1.mjs`
is derived from the native range episode but removes archived model/video
requirements, keeps the generated canvas and native relay, and records paired
clock markers. It writes only to a fresh capture directory. The clock-only
calibration and all sessions are stored under
`~/.cache/networkrlcd/native-clock-action-probe-v1/`, outside the repository.
The sealed report is written after the complete raw inventory is verified.
