# Native clock/action V11A: independent content and measured-rate panel

## V11A amendment and excluded commissioning attempt

The original V11 protocol remains frozen at commit `dc425ba` and is not edited.
Its first capture attempt was stopped after a recorder-only `ReferenceError`
(`wait is not defined`) during post-run queue drain. Ten session directories were
retained and sealed: three process-complete, six failed with that ReferenceError,
and one operator-interrupted. No V11 outcomes were analyzed or used. All ten session manifests were checksum-verified; the integrity-only record is [`reports/native-clock-action-turntcp-v11-commissioning-failure.json`](native-clock-action-turntcp-v11-commissioning-failure.json), and the failed attempt index SHA-256 is `f4914053113241ec353947a1deb798d7c7743da2af8b1d1f4eb936cb20054765`. This V11A
run starts from a fresh cache root, uses new session and action randomization
seeds, and excludes all V11 commissioning captures. It preserves the same source
assets, crossed design, causal action assignment, and acceptance criteria.
The recorder amendment adds only the missing asynchronous delay helper; transport,
clock, measurement, randomization, and outcome logic are otherwise unchanged.

## Research question

V10 is closed. Its BWE-threshold rule underperformed fixed 0.65 on on-time
delivery by `-14.1 percentage points` (95% interval `[-22.6, -5.5]`) and will not
be retuned. V9's primary on-time delivery interaction was inconclusive;
its secondary timely-PSNR interaction was positive at `+0.508 dB` (95% interval
`[0.077, 0.938]`) across generated-scene clusters. V11A asks whether the direction
of that quality interaction persists with four independently licensed video
capture groups and four measured LTE/5G network families.

The V11A primary endpoint is

```text
(PSNR effect of 1.05 vs 0.65 at pre-action BWE >= 500 kbps)
- (PSNR effect of 1.05 vs 0.65 at pre-action BWE < 500 kbps)
```

PSNR is calculated from paired sampled RGB pixels for a source frame that is
read back within 150 ms. Sender BWE is classified before each randomized action.
The action ratios, 0.5 assignment propensity, six 3-second holds, 1.8–2.6 second
post-ack outcome window, clock marker pattern, and held-out affine clock checks
reuse the qualified V9 protocol. This estimates proximal action effects under
the sampled state distribution; it is not closed-loop policy value.

## Independent source panel

The content sources are the four pass-reviewed Commons entries named in
[`data/native-v11/content_sources.json`](../data/native-v11/content_sources.json).
Their capture groups are distinct from one another and from V3–V10. The selected
30-second clips are no-audio H.264 derivatives at 640x360 and 30 fps. Original
files and clips remain outside Git in `~/.cache/networkrlcd/independent-v11-sources/`.
The manifest records source revision, creator, licence, source and derivative
checksums, and attribution. Source/reference RGB arrays are transient in browser
memory; saved frame evidence retains scalar quality measurements only.

The network panel uses two acquisition campaigns and four technology/operator
families:

| Family | Acquisition campaign | Source and licence |
| --- | --- | --- |
| UCC LTE, operator A | UCC/MISL LTE | [UCC 4G LTE dataset](https://zenodo.org/records/1219679), CC BY 4.0 |
| UCC 5G, operator B | UCC/MISL 5G | [UCC 5G dataset](https://github.com/uccmisl/5Gdataset/tree/306d92eba81cb4f1195d8b8eba625666a02a10ec), GPL-3.0 at the pinned repository revision |
| Vienna LTE, operator C | Vienna full 4G/5G | [Vienna measurement dataset](https://zenodo.org/records/18322066), CC BY 4.0; pinned GitLab file revision `e4e2368d9a1c78dc673805f06f62486a41839d27` |
| Vienna 5G, operator A | Vienna full 4G/5G | Same Vienna campaign and licence; pinned file revision above |

The two UCC families share one acquisition campaign, as do the two Vienna
families. V11 therefore reports four radio/operator strata nested in two
campaigns. It will not describe them as four independent network campaigns.
Profiles from a family are repeated source windows, not independent campaigns.

The measured source files are pinned by SHA-256 in
[`data/native-v11/network_profiles.json`](../data/native-v11/network_profiles.json).
The private archive, environment, and alternative-source screening is recorded
in [`acquisition/native-independent-v11/source_screening.json`](../acquisition/native-independent-v11/source_screening.json).
The derivation tool reads only downlink throughput, source time for one-second
binning, and the dataset's operator/radio-mode labels. It excludes coordinates,
cell IDs, measurement IDs, and other radio identifiers. Four non-overlapping
18-second windows are selected per family using source values alone: each
window has at least four seconds at or below 0.5 Mbps, four above 0.5 Mbps, and
no sample above the local queue's 10 Mbps limit. No V11 treatment outcome enters
content or trace selection.

Each window is replayed as eighteen one-second local bottleneck service rates,
in three six-second blocks. The final rate is held for the existing 0.6-second
measurement tail. Both relay directions use the downlink-derived rate schedule
to preserve the existing symmetric queue mechanism. This is a deterministic
service-rate replay, not a replay of original packets or a live Internet/mobile
network measurement.

## Panel and assignment

The design crosses four content capture groups with four network families and
four distinct measured windows per family: 16 content-by-family cells and 64
sessions total. Every content source is tested on each network family. The four
network windows are crossed over all content sources and remain nested under
their family. Session order is shuffled with seed `20261040`; six action draws
per session use seed `20261041` and the exact V9 SHA-256 draw rule.

At each eligible sender sample, the instrument observes the current sender BWE
and assigns ratio 0.65 or 1.05 with probability 0.5. The encoder cap is rounded
from that BWE, clamped to the inherited `[150000, 4000000]` bps bounds, applied,
and checked against the native readback. The state threshold remains 500000 bps.
There is no BWE-threshold policy arm and no controller is fit or promoted.

## Gates and analysis

All 64 sessions must be sealed before the gate runs. The gate independently
checks each capture's file checksums, TURN/TCP-only ICE candidates, nominated
TURN pairs, bidirectional media, relay conservation and event replay, all twelve
actual-run clock markers, held-out affine clock coverage/width, and all eighteen
measured-rate changes against their frozen values and one-second offsets. The
V9 clock acceptance bounds remain unchanged: affine slope `[0.98, 1.02]`, all
held-out marker intervals covered, maximum held-out width 50 ms, and timestamp
ordering tolerance 1 ms. No per-hold relay join is estimated before the actual
session clock gate passes.

Action outcomes remain closed until all 64 sessions pass capture integrity,
transport, clock, randomization/readback, and trace-schedule gates. Failed
sessions remain sealed in the capture index and are never treated as action
outcomes or replaced. If any session fails a gate, V11 records the failed panel
and does not open its outcome telemetry.

A content-by-network cell is complete only if it has at least two hold windows
in all four BWE-state/action cells. At least 13 of 16 cells are required for the
registered directional replication check. The registered direction check
requires a positive equal-weight crossed mean, a positive mean in both measured
acquisition campaigns, and positive means in at least three of four content
groups and three of four network families. The report also shows every cell,
content, network family, and campaign estimate. It makes no population-level
confidence claim: the four cells share content/network sources, and only two
network acquisition campaigns are represented. The 16 crossed cells are not
treated as independent replicates.

Secondary outcomes are on-time fraction, PSNR by BWE state, guaranteed relay
wire bytes per hold, and queue drops. Relay effects are joined using validated
clock bounds. Failed ICE or clock sessions never contribute treatment outcomes.
V3–V10, archived sessions, and simulator/synthetic-controller results are not
pooled with V11.

## Freeze and storage

The prepared V11A protocol and 64 panel snapshots are written to the external
capture root, and the registered protocol is copied to
[`configs/native_clock_action_probe_turn_tcp_v11a.json`](../configs/native_clock_action_probe_turn_tcp_v11a.json).
Commit that protocol and the V11A source files before invoking `capture`. Raw
session files remain under `~/.cache/networkrlcd/native-clock-action-turntcp-v11a/`;
the report and source/trace provenance summaries are committed under `reports/`
and `data/native-v11/`. V9 and V10 source hashes and captured results are checked
before preparation and remain unchanged.

```bash
python tools/native_turn_clock_action_probe_v11a.py prepare --root /home/agent/.cache/networkrlcd/native-clock-action-turntcp-v11a
python tools/native_turn_clock_action_probe_v11a.py capture
python tools/native_turn_clock_action_probe_v11a.py integrity
python tools/native_turn_clock_action_probe_v11a.py clock-gate
python tools/native_turn_clock_action_probe_v11a.py analyze
```


## Versioned amendment record

V11A is a fresh 64-session execution of the frozen validation design. The only
implementation correction is to define the timer-backed `wait(ms)` used by the
existing TURN queue-drain loop. The panel uses session-order seed `20261042` and
action seed `20261043`. It has its own protocol/configuration hash, cache root,
report path, and capture IDs. The failed V11 attempt is retained as
commissioning evidence and is not pooled, replaced, or included in any estimate.

The same pre-outcome gate applies: all 64 V11A sessions must be integrity sealed,
TURN/TCP and bidirectional-media qualified, pass twelve-marker actual-run clock
validation, pass exact 18-tick measured-rate replay checks, and pass action
randomization/readback checks. If any V11A session fails, no V11A action outcome
telemetry is opened. The registered endpoints, crossed summaries, directional
replication rule, and prohibition on controller fitting remain unchanged.
