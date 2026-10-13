# Native clock/action V11D: independent content and measured-network validation

## Purpose and separation

V10 is closed. Its BWE-threshold policy significantly underperformed fixed
0.65 and will not be retuned. V9's primary on-time-delivery interaction was
inconclusive; its secondary timely-PSNR interaction was positive at `+0.508 dB`
(95% interval `[0.077, 0.938]`). V11D asks whether that state-dependent quality
signal repeats across new licensed content and genuinely distinct measured
network families.

V11D is a fresh panel independent of V3–V10 and V11C. It does not read or pool
prior V3–V10 outcomes, V11C's failed-gate attempts, simulator results, or
synthetic-controller evidence. V11C's all-session gate failed with its outcome
telemetry unopened. That failure remains frozen and is listed in the V11D
source inventory only as excluded history. No V10 policy arm or controller is
included.

## Acquisition and source screen

The authenticated private archive was inspected at revision
`b1497fa425f59c3b796d9ce5354ee58a0afe9667`. Its 80-entry tree contains prior
experiment archives, receipts/manifests, and result shards; it supplies no
unused independently sourced video or measured mobile-network inputs. No
archived results were restored or opened for outcomes. The source and
environment screen, including excluded alternatives, is in
[`acquisition/native-independent-v11d/source_screening.json`](../acquisition/native-independent-v11d/source_screening.json).

The four content groups below were marked as reserves in the N1 source pool,
were not N1 stage-one captures, and do not overlap V11C's content IDs. Their
Commons originals match the archived catalogue byte counts and SHA-1 values;
each has a recorded rights/contact-sheet pass. The final selected segments were
also visually checked for personal details. Only 30-second no-audio derivatives
are served. Originals and derivatives stay in the external cache; browser pixel
references are transient and saved evidence retains scalar quality and source
IDs only.

| Content group | Source | Licence |
| --- | --- | --- |
| Periodical cicada emergence | [Commons 106384795](https://commons.wikimedia.org/wiki/File:Periodical_Cicada_emerging_from_underground_2021-05-15_233901977.webm) | CC BY 4.0 |
| Vižanice outdoor scene | [Commons 29267197](https://commons.wikimedia.org/wiki/File:Na_sjeveru_Vi%C5%BEanice_20131027_103431.ogv) | CC BY 3.0 |
| Schmilka firefighting helicopter | [Commons 121308342](https://commons.wikimedia.org/wiki/File:Heli_Schmilka_Fire_Fighting_Elbe_30_7_2022.webm) | CC0 1.0 |
| D3 tree-layout tutorial | [Commons 32353576](https://commons.wikimedia.org/wiki/File:D3.js-tutorial-14-The-Tree-Layout-%281-of-2%29.webm) | CC BY 3.0 |

An earlier unregistered V11D draft included N1 stage-one sources and was
discarded before any V11D capture. Two later source candidates were excluded
after segment review: a GNU/Linux recording shows a desktop filename, and an
IBAI recording shows an identifiable speaker. Neither is in the final manifest.

The network panel uses two new CC BY 4.0 field-measurement datasets, distinct
from V11C's UCC/Vienna inputs:

| Measured family | Acquisition campaign | Source |
| --- | --- | --- |
| NordicDat operator 1, 5G-NSA, LTE_B20 | NordicDat cross-border drive-test | [Zenodo 10964584](https://zenodo.org/records/10964584) |
| NordicDat operator 1, LTE, LTE_B20 | Same NordicDat campaign | Same dataset |
| NordicDat operator 3, LTE, LTE_B3 | Same NordicDat campaign | Same dataset |
| Rome anonymized operator 2, actual LTE with 5G-enabled UE mode | Rome active Speedtest | [Zenodo 8224890](https://zenodo.org/records/8224890) |

Thus the four measured strata represent **two independent acquisition
campaigns**, not four campaigns. Repeated windows and Rome
`Speedtest_Campaign` IDs are nested. In Rome, each selected downlink speedtest
row is matched to an actual LTE radio observation within 1.5 seconds in the
same date and campaign; the UE-mode label alone is not treated as evidence of
5G. Source files are pinned by SHA-256 and MD5 in
[`data/native-v11d/network_profiles.json`](../data/native-v11d/network_profiles.json).
The derivation reads only time, downlink throughput, service status, anonymized
operator, radio technology/band, UE mode, and campaign. It does not retain
location, cell, mobility, or other radio identifiers.

Four 18-second measured-rate windows per family are selected using source
values only. Each has 1 Hz rates, both sides of the 500 kbps BWE state split in
each six-second block, no rate above 10 Mbps, and no consecutive zero rates.
NordicDat contributes three strata from one campaign; the Nordic operator-3
LTE band-3 stratum's eligible windows come from two source runs. Rome contributes
one LTE stratum from its separate active-measurement campaign. These are
measured rate histories replayed as local queue service rates, not packet
replays or live mobile/Internet paths.

## Design and registered estimand

The 4 content groups cross with 4 measured network families. Each of the 16
content-by-family cells has 4 distinct registered measured windows, for 64
sessions total. Session order and action draws use fresh seeds `20261067` and
`20261068`. Each session lasts 18 seconds with six 3-second action holds.

At each eligible sender observation, the instrument records pre-action BWE and
randomly assigns encoder ratio `0.65` or `1.05` with probability `0.5`, then
checks the proposed cap and native sender readback. This estimates proximal
randomized action effects at the sampled states. It is not a closed-loop policy
comparison or policy-value estimate.

The primary endpoint is the timely sampled RGB PSNR action interaction:

```text
(PSNR effect of 1.05 vs 0.65 at pre-action BWE >= 500 kbps)
- (PSNR effect of 1.05 vs 0.65 at pre-action BWE < 500 kbps)
```

PSNR is computed from paired sampled RGB pixels when the marked source frame is
read back within 150 ms. The action hold, endpoint window, 12-marker pattern,
affine clock procedure, and held-out clock criteria reuse the qualified V9
protocol. Secondary outcomes are on-time fraction, PSNR by BWE state, guaranteed
relay wire bytes, and queue drops per hold.

The replication rule requires at least 13 of 16 cells with two or more hold
windows in each state/action group, a positive equal-weight crossed mean, a
positive mean in each of the two acquisition campaigns, and positive means for
at least three of the four content groups and three of the four measured
families. Every cell, family, content group, and campaign estimate is reported.
The panel is a directional source-stratified replication check; the 16 crossed
cells, repeated profiles, and four nested families are not independent
replicates, and no population-level confidence claim is made.

No per-hold relay estimate is produced unless that session's actual sender to
relay clock map passes all twelve marker exchanges, including held-out marker
coverage and width. V9 affine bounds remain slope `[0.98, 1.02]`, 100% held-out
coverage, maximum held-out interval width 50 ms, and timestamp-order tolerance
1 ms.

## Capture, gates, and preservation

The managed Chromium `WebRtcIPHandling=disable_non_proxied_udp` policy remains
unchanged. The registered local TURN/TCP transport reuses the qualified
userspace relay and the existing preflight. Each session must independently
pass source and file integrity, relay-only TCP ICE candidate gathering,
nominated TURN pairs, bidirectional media, exact queue/event conservation,
all actual-run clock checks, all 18 exact measured-rate ticks, sender assignment
and cap readback, and terminal queue cleanup. Cleanup begins only after the
browser observation cutoff, uses the existing 10 Mbps rate for at most 2
seconds, and requires an empty final queue with conserved bytes.

Before the main capture, a technical smoke uses the registered profile with the
lowest sum of three terminal rates. It tests integrity, TURN, clocks, trace
replay, assignment/readback, and terminal cleanup only. It must exercise a
nonempty pre-cleanup queue and empty post-cleanup queue. Its action/QoE/relay
outcomes are never opened or pooled.

All 64 main sessions must be sealed and pass every integrity, transport, clock,
trace, action, and cleanup gate before any frame-quality, action-outcome, or
per-hold relay telemetry is read. Failed sessions stay indexed and are never
replaced or counted as treatment outcomes. If any gate fails, preserve the
failure evidence and do not analyze treatment outcomes. No controller is fit or
promoted from V11D alone.

Raw session data are outside Git at
`~/.cache/networkrlcd/native-clock-action-turntcp-v11d/`; smoke data have a
separate root. Source assets and outputs remain within the available external
cache budget. Commit the source screen, manifests, tools, recorder, registered
protocol, and this plan before running the smoke or capture.

```bash
python tools/native_turn_clock_action_probe_v11d.py prepare --root /home/agent/.cache/networkrlcd/native-clock-action-turntcp-v11d
python tools/native_turn_clock_action_probe_v11d.py smoke
python tools/native_turn_clock_action_probe_v11d.py capture
python tools/native_turn_clock_action_probe_v11d.py integrity
python tools/native_turn_clock_action_probe_v11d.py clock-gate
python tools/native_turn_clock_action_probe_v11d.py analyze
```

If interrupted, `tools/resume_native_turn_tcp_v11d.py` preserves all indexed
session files, seals any unindexed interrupted ID as failed, and resumes only
the original remaining randomized IDs.
