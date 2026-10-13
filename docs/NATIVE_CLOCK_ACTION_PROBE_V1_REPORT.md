# Native clock/action probe V1 report

## Clock alignment

The marker-only calibration passed under the frozen protocol. It recorded 120
sequential no-op exchanges over about 60 seconds. Even-indexed exchanges fit the
affine feasible region; all 60 odd-indexed holdouts were covered pointwise by
every feasible mapping under the 1 ms validation tolerance.

- Feasible sender-to-Node slope: **0.9999546004 to 1.0000401842**.
- Maximum mapped-time interval across held-out exchanges: **2.6424 ms**.
- Feasible polygon vertices: **13**.
- Clock-width acceptance limit: **50 ms**.

This validates the short-run browser/Node clock mapping for this runtime. The
calibration contains no media, action, or QoE evidence. Its raw files were
checksum-verified before analysis.

## Native action capture attempt

The frozen action protocol planned 32 sessions: eight generated-scene seed
clusters, two repetitions, and randomized whole-session cap ratios 0.65 and
1.05 under the same high/collapse/recovery schedule. The 1.05 arm was the
strong baseline. The capture runner attempted each planned session once and
retained all 32 failures. **Zero qualified sessions completed.**

Every attempt stopped during ICE setup with `no local IPv4 ICE candidates; do
not bypass relay`. Chromium 154.0.8037.57 reported ICE gathering complete for
both peers but emitted zero candidate events and no ICE candidate error. The
managed browser policy at `/etc/chromium/policies/managed/misc.json` sets
`WebRtcIPHandling` to `disable_non_proxied_udp`. An explicit public-and-private
candidate flag did not produce candidates. The policy was left unchanged. No
`RLCD_TURN_BINARY`, `TURN_SERVER`, or `RLCD_TURN_SECRET` is configured, and no
TURN server is installed.

The complete 32-session inventory and each failed session's 26-file manifest
passed checksum verification before the error logs were inspected. No measured
study-arm actions, relay-cost outcomes, frame-readback outcomes, or QoE values
were produced. Consequently there is no state-dependent delivery effect to
estimate, and no per-hold relay join is claimed. No controller was fit or
promoted.

## Integrity and separation

The authoritative capture is in
`~/.cache/networkrlcd/native-clock-action-probe-v1-final3/`. Its frozen
protocol SHA256 is
`9c09468dda2d6126dcb551fe14762c7d64de722c2b03d04430e657ad8b0a3f1f`; the clock
report SHA256 is
`27946a8b2a312ab30ddbf6dbfefadc419f1e010cd32fe66f7f491fec09711dbf`; and the
failed-session index SHA256 is
`f844c2500df1de885466fcef8bef69c300ce99ef9b36b7eac09cf6c397778f1b`. Earlier
marker-only preflight attempts remain in sibling cache directories and contain
no action outcomes; this report uses only the final protocol-conforming
calibration.

The targeted 20-session restore/replay/report, V3 result, and prior freezes are
unchanged. This generated-canvas native probe is not pooled with archived
native sessions, recorded-video evidence, or simulator/synthetic results.

The next informative action study needs a policy-approved WebRTC path, such as
an already configured TURN/TCP service, or a runtime whose managed browser
policy permits the native relay capture. The existing task runtime does not
provide that path.
