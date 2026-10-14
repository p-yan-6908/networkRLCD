# M1: prospective support-only native BWE reliability diagnostic

## Authority and separation

V13 is closed as a support-design failure at unchanged registration `6b8471a`.
All 32 sessions qualified individually, but six of sixteen contexts failed
the 0.25-octave census-repeatability rule and the measured-family ranges
lacked common support. Its action panel remains unrun and its outcomes
unopened. This diagnostic is development work prompted only by that
outcome-free support failure. Commit this plan, tool and protocol before the
first M1 session. Preserve every V13/prior file and result.

M1 reuses V13 content and uses synthetic service. It is not a new independent
content or measured-network panel, a V13 replacement or an action experiment.
Do not pool its sessions with prior evidence or estimate delivery/QoE,
quality, relay cost, action effects or controller value.

## Minimal question and fixed inputs

Is the registered 18-second native census state repeatable across fresh
sessions when the service rate is constant? Run **eight sessions**: the two
V13 45-second clips × four fresh repeats, interleaved in four blocks, with
the within-block content order shuffled by fixed seed **20261104**. Four
repeats per clip give six descriptive pairwise differences without treating
those six as independent observations. No added attempts or replacements.

Use one synthetic rate, exactly **1.4523718338280722 Mbps**, for every one of
the 36 one-second ticks, symmetrically on the qualified userspace queue.
This is the already-frozen source-conditioning geometric-mean hint of
`att_lte_driving_2016-uplink-lower` in `data/native-v13/sources.json`; that
profile failed V13 repeatability for both clips. It is selected for a
development diagnostic, not as a new measured trace, observed BWE target
or matched counterfactual. No rate search or tuning follows M1 results.

Reuse the exact V13 recorder/sampler and unchanged 36.6-second duration,
three phase lengths `[12000,12000,12600]` ms, 45-second source without looping,
VP8, 4 Mbps encoder ceiling, zero jitter target, 100 ms sender cadence,
bootstrap service, queue size/delay and terminal drain. Start fresh browser,
peer connections, TURN instance and empty queues for each repeat. Preserve
managed `WebRtcIPHandling=disable_non_proxied_udp` and relay-only TURN/TCP.
All panels set `support_only=true`: no bitrate treatment is assigned.

## Frozen measurement and gates

Retain the first eligible observation in `[18000,18300]` ms, with eleven native
BWE values spanning ≥900 ms, positive gaps ≤250 ms and every BWE in
`[240000,3800000]` bps. The scalar is mean `log2(BWE/500000)` over that history.
The 500 kbps factor is a unit/centering constant, never a binary threshold.
Do not change times, eligibility or history requirements.

Every original session must pass the inherited checksum, native readback,
TURN/TCP, bidirectional media, 36 exact tick/150 ms tolerance, actual-run
clock and cleanup gates. Retain twelve markers, train `[0,1,3,4,6,7,9,11]`,
hold out `[2,5,8,10]`, slope `[0.98,1.02]`, 100% held-out coverage, ≤50 ms width
and 1 ms timestamp tolerance. Retain 10 Mbps terminal drain ≤2 seconds,
empty final queues, served=forwarded, zero send errors and conservation
within `1e-6` bytes. Require 4 Mbps cap and zero jitter at every decision,
and zero assignments. Failed sessions remain failed and make the complete
diagnostic unqualified; do not substitute them or select a passing subset.

Verify every sealed file before reading permitted support telemetry. Decode
only the inherited technical gate, sender timestamps, native BWE/validity,
qualification and assignment/readback. The collector may retain outcome
files for preservation; do not decode frame events, quality, sender encoded
meter, receiver feedback or per-hold relay outcomes.

## Prespecified descriptive analysis and decision

For each clip, report all four census states/BWE geometric means, sample SD,
max-minus-min spread, all six pairwise absolute differences and qualifying
history drift/range. Compare the **entire four-repeat spread** to the existing
**0.25-octave** reliability benchmark. Require all eight original sessions
and both full-content spreads to pass for the descriptive reliability screen.
This extends repeated support measurement under constant synthetic service;
it does not redefine or satisfy V13's closed confirmatory gate. No hypothesis
test, population CI, action-effect regression or pooled family mean is used.

- If both clips pass, steady service is compatible with reliable measurement
  under this recipe. The next development step is a separate repeated
  measured-profile or prospective within-session-state reliability design.
  Passing M1 alone cannot prove dynamic rate history caused V13's failure or
  certify a measured-family census; constant service changes the history.
- If either clip fails, a fixed context census scalar is unreliable even
  under this steady-service recipe. Do not build another confirmatory
  action panel around a between-session census. Investigate support history
  and a prospectively measured within-session continuous modifier on reused
  development sources before seeking new confirmation.
- If a technical/eligibility gate fails, preserve it as a diagnostic
  qualification failure and identify that failure without opening outcomes.

In all branches, V13 stays closed, common measured-network support remains
unestablished, new independent confirmation remains necessary and controller
development remains closed. No broad network inference is authorized.

## Execution and preservation

```bash
python tools/measure_bwe_reliability_m1.py prepare
# Commit this plan, tool and configs/native_bwe_reliability_m1.json first.
python tools/results_storage.py status --check --planned-bytes 200000000
python tools/measure_bwe_reliability_m1.py verify
python tools/measure_bwe_reliability_m1.py capture
python tools/measure_bwe_reliability_m1.py summarize
```

Raw root: `~/.cache/networkrlcd/native-bwe-reliability-m1`. Compact protocols,
reports and receipts stay in Git; large raw capture stays external. Bound
the archive snapshot to the committed M1 registration. Upload to a new
private HF namespace, verify all remote archive objects via a fresh download
and every file checksum, preserve licensed original rights and delete no
active/unarchived bytes. An interrupted/nonempty capture is preserved;
continuing requires an explicit documented decision, not silent retries.
