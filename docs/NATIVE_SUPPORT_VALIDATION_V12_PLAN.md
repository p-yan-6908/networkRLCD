# V12: independent validation with prospective BWE support

## Question and authority

This registration follows `92a6ae3` and the support-only diagnosis in
`5451328`. V11D is negative, under-covered development evidence. Four of its
seven failed cells lacked enough high-BWE visits; three had randomized arm
imbalance. Its observed interaction is not a population estimate. V10 remains
closed. No prior outcomes or reused source groups enter this panel.

The question is whether a conditional proximal bitrate action effect has a
consistent direction across new content and three additional measured-network
campaigns after common pre-treatment conditioning. BWE is a measured state,
not a randomized intervention. A difference between state-specific randomized
action effects does not identify a causal effect of changing BWE itself.

This turn freezes the next panel without running its support census or
confirmatory sessions. New content has been inspected for rights and visual
suitability, and source rates have been inspected for prospective support.
There has been no native action, delivery, PSNR, or per-hold cost observation on
any of these new content/network combinations.

## Independent assets and source limits

The two content capture groups are **The Nature Box's 2013 King Penguins
production** and **Jacopo188's 2012 Shirlan Waterfall production**. Both have
pinned Commons own-work and CC BY-SA 3.0 declarations, verified catalogue
bytes/SHA-1, local SHA-256, and a six-frame selected-segment visual review.
Each uses its first 30 seconds without looping, the unchanged H.264 Main,
640×360, 30fps conversion, and no audio. Derivatives retain CC BY-SA 3.0 and
attribution. Neither creator/capture group appears in earlier registered
panels. The initial ants/ferry candidates were rejected for V11C overlap
before registration or native capture; their acquisition remains documented.

The three network families correspond to three distinct acquisition campaigns:

| Family | Source | Rights and representation |
| --- | --- | --- |
| Irish operator-A observed LTE | UCC 2017–2018, Zenodo `1219679` | CC BY 4.0; measured downlink kbps; duplicate-second median; at most two isolated missing seconds hold the immediately preceding measured value |
| NYU metropolitan LTE | NYU-METS, commit `886c73b1398457ba5f87faefe7a9ea3755e713f7`, `Dataset_1.rar` | ODbL 1.0 / DbCL 1.0; native 1Hz server-side iPerf rates with explicit original units |
| Murcia private campus TCP upload | UMU, Zenodo `15516876` | CC BY 4.0; measured upload kbps; contiguous rows at the documented nominal 1Hz polling cadence; no GPS timing or per-row SA/RAT claim |

Original archives match published Zenodo MD5 or Git blob SHA-1 and pinned
SHA-256. Derived source manifests are in `data/native-v12/`; attribution,
licenses, revision URLs and local cache paths are explicit. No source rate is
scaled or clamped. All these campaigns are new to V3–V11D. Files, windows,
operators and the two Murcia sampling days remain nested in their parent
campaigns. The six crossed cells are not six independent source replicates.

Source windows have 18 1Hz replay rates in `[0,10]` Mbps and no adjacent zero
samples. Their mean over indices `[3,13)` lies in `[0.28,0.42]` Mbps for a low
hint or `[0.8,4]` Mbps for a high hint. Selection is canonical member/offset
order, taking the earliest eligible window from two distinct source files per
family/state. These are hints, not assertions about browser BWE. The source
screen uses no native outcome. No location/cell/subscriber identifier is used
to select or retained in derived profiles.

Application throughput is replayed symmetrically through the qualified local
queue. This is a measured-rate validation with explicit representation
assumptions, not a live mobile-path or packet-trace validation. The small panel
does not support a claim about every measured or deployed network family.
Portrait padding remains in the frozen RGB PSNR definition; quality levels
are compared within sources, and pixel weighting is unchanged.

## Minimum panel and randomized protocol

Two content groups × three new campaigns × two BWE states × two distinct
source windows × two actions gives **48 fresh peer-connection sessions**.
There are 24 matched pairs. Each pair shares content, replay profile, target
state and conditioning. Session-order seed is `20261081`; action seed is
`20261082`, with a new `networkrlcd-native-v12` namespace.

Every session starts a fresh sender/receiver connection and keeps encoder
maxBitrate at **4,000,000 bps** before treatment. This is a common ceiling
under native GCC, not a forced payload rate or synthetic BWE value. It allows
the browser to observe available bandwidth before experimental caps limit
offered load. Jitter-buffer target remains zero. Codec, video sampling,
propagation, queue and rate scheduler retain the qualified V11D recipe.

The only treatment decision is in the sender's elapsed `[9000,9300]` ms
window. It requires eleven consecutive native BWE observations spanning at
least 900 ms, with every gap at most 250 ms. Every observation must be in the
registered low (`<500,000`) or high (`>=500,000`) bin and in
`[240,000,3,800,000]` bps. The additional range guarantees that both ratios
produce distinct unclipped native caps. It defines an eligible-state
estimand; it does not change the original 500 kbps threshold.

Only after this support check does the sampler decode the first uint32 of
`SHA256(networkrlcd-native-v12:{seed}:{pair_id})`. The low bit determines
which ratio (`0.65` or `1.05`) occurs in pair slot zero; slot one receives the
complement after an identical new conditioning period. Each session's
marginal treatment probability is 0.5. Given slot zero, slot one's conditional
probability is one; the pair is the randomized allocation unit. The ledger
records both scopes, the exact draw, pre-action BWE, proposed cap and native
readback. No analysis treats both slots as independent Bernoulli draws.

Each session contains one proximal hold; its assigned cap persists for at
least three seconds. The original endpoint window is **ack +1800 to +2600
ms**, wholly inside the middle six-second trace block. This preserves the
V9–V11D hold outcome definition. The delayed decision and common history
change the sampled causal context, so this panel is not pooled with those
earlier micro-randomized histories.

There are exactly two planned holds in each cell/state/action bucket. This is
the smallest panel preserving the registered two-hold minimum, multiple
content sources, three new source campaigns and two distinct trace files per
state. It is a strict replication screen, not a powered population study.

## Prospective qualification and failed sessions

After this registration is committed, run a separate **24-session support
census**, one fresh connection for each content/profile/state pair. It uses
the same source, schedule, conditioning, BWE eligibility and transport/clock
checks, applies no randomized treatment, and keeps its outcome files unopened.
All 24 must qualify before any of the 48 treatment sessions start. This tests
the actual recorded content × measured-rate combinations without selecting
on treatment outcomes. Its inventory must match every registered pair.

Every treatment session independently repeats the same pre-treatment support
check. Passing the earlier census never substitutes for support on the actual
action run. If a state is unavailable by 9300 ms, no treatment is assigned;
the sealed support failure remains indexed. There is no extended wait,
rescaling, state relabeling, alternate seed, replacement, source substitution
or additional capture to rescue coverage. A failed census blocks capture.
A failed action session blocks outcome analysis of the entire panel.

The prospective count rule is **all six cells**, each with **at least two
qualified holds in every state/action group**. This retains the previous
per-group minimum and raises completeness to 100%. It assures the necessary
counts conditional on qualification, rather than assuming trace-rate
crossings create BWE visits. No finite protocol can guarantee that an unknown
browser/network combination will attain a particular measured state; this
protocol makes such failure visible before inference and never lowers a gate.

## Clock, TURN and evidence gates

Retain Chromium `WebRtcIPHandling=disable_non_proxied_udp`; use relay-only
TURN/TCP with the unchanged loopback userspace queue. Every session needs
relay candidate gathering for both peers, nominated TCP-backed TURN pairs,
bidirectional transport, greater than ten encoded/decoded frames in each
measured block, finite encode time, and exact queue/event conservation.

Retain all twelve actual-run clock markers, train indices
`[0,1,3,4,6,7,9,11]`, holdouts `[2,5,8,10]`, affine slope bounds `[0.98,1.02]`,
100% held-out coverage, maximum width 50 ms and timestamp tolerance 1 ms.
Marker IDs, endpoint/phase order and all 18 exact trace ticks must match the
registration; tick tolerance stays 150 ms. Keep the qualified 120-marker
calibration as a reference. It never substitutes for actual-run alignment.

Keep the V11D terminal drain after the browser measurement cutoff, at
10 Mbps for at most 2 seconds, with an empty final queue, all served packets
forwarded, no send errors and byte conservation within `1e-6`. Drain service
is excluded from the measured rate history and all action windows.

Hash every session file before accessing telemetry. Outcome analysis requires
all 48 seals, every actual-run source/support/assignment/readback/clock/
transport/media/trace/cleanup gate, and the six-cell count gate. Per-hold relay
joins use the validated feasible clock map only after this all-session gate.
Failed ICE/clock/support sessions are technical failures, never treatment
outcomes. Raw evidence stays outside Git in `~/.cache/networkrlcd/`; all
failures, old freezes and negative results remain preserved.

The six-session development qualification in commit `f83ad5c` reused V11D
cicada content and **synthetic constant commissioning links** at 0.35/1.2 Mbps.
It tested the support census and both randomized actions, readback, exact rate
replay, TURN, clocks and cleanup, without reading outcomes. All six passed;
maximum held-out clock width was **2.481 ms**. This is instrument development,
not measured-network replication evidence. The later registration wrapper
adds input binding and stricter metadata/media validation; the exercised
sampler and all operational recorder statements remain byte-identical. The
recorder source/limitation notices now describe upload/downlink provenance
and the pinned content licenses;
the uncommitted earlier draft is retained without any census or action data
in `reports/native-v12-draft-supersession.json`.

## Frozen outcomes, summaries and decisions

Primary: the timely sampled RGB PSNR `1.05 minus 0.65` action effect in high
BWE minus the same effect in low BWE. Preserve paired source/receiver RGB
sampling and the **150 ms** readback deadline. The state/action bucket PSNR
mean is the sum of observed timely frame PSNR divided by the timely sampled
frame count, as in V11D. There is no missing-quality imputation.

Secondary: on-time source-frame fraction; guaranteed offered relay wire bytes
and guaranteed dropped wire bytes per hold. Possible clock-boundary bytes
remain auditable. These are local delivery/volume proxies, not complete human
QoE or real mobile-network charges. PSNR conditions on successful timely
delivery, so survival selection prevents a PSNR-only claim of utility.

Report every cell's action effect in each BWE state, its interaction, and
content/family/campaign summaries. The crossed mean weights the six cells
equally; each family has one campaign and two content cells. A stratum mean
is undefined if any registered constituent cell is unestimable. Do not
average only favorable or available cells into a confirmatory mean. Repeats
and source windows are nested; no population interval is produced from six
crossed cells.

The preregistered **two-sided directional stability screen** requires:

1. All six primary cells are estimable, in addition to the technical and
   two-hold gates.
2. All six cell interactions have the same nonzero sign.
3. Both content means and each of the three campaign means have that sign
   and magnitude at least **0.25 dB**. This is a prospective screening margin,
   not a data-derived power claim or a population significance threshold.
4. Every prespecified sensitivity that retains one of the two low profiles
   and one of the two high profiles (four combinations per cell) is estimable
   and retains that sign. No sensitivity combination is selected for success.

The frozen implementation is `tools/analyze_native_v12.py`. It uses the same
outcome definitions, reports missingness and every stratum, and has no
controller fit. This rule tests consistency in this selected panel; it does
not establish a universal interaction or superiority over fixed 0.65.

If the support/technical or primary estimability gate fails, preserve the
under-covered validation and do not change thresholds or rescue the panel.
If qualified effects are mixed, freeze the negative result. If the stability
screen passes, the next informative native step is an independently
preregistered delivery/QoE-and-cost validation against fixed 0.65, retaining
source-level strata and testing whether the quality signal survives the
delivery tradeoff. Controller fitting, V10 retuning and promotion remain
closed until factual evidence establishes stable conditional utility over
that strong baseline. No controller is fitted or selected from V12 alone.

## Registered workflow

The new protocol, manifests, recorder, sampler, analyzer, rights notices,
source screen and this plan are committed before the new support census.
The collector retains its legacy `stage=discovery` compatibility tag; the
separate V12 scientific protocol sets `confirmatory=true` and prohibits fitting.
Session and support panels have individual hashes; the main registration
binds all inputs and the tested development report.

```bash
python tools/native_support_validation_v12.py verify
python tools/results_storage.py status --check --planned-bytes 1000000
# Raw 24+48-session output budget: 500 MB in the external cache.
python tools/native_support_validation_v12.py support-census
python tools/native_support_validation_v12.py capture
python tools/native_support_validation_v12.py gate
python tools/analyze_native_v12.py
```

Only `verify` is run on the new registration during this turn. The census and
confirmatory panel remain pristine. Reusing a nonempty capture directory or
overwriting a frozen report is rejected. A future interruption must preserve
the original IDs, failed sessions and seals; this registration offers no
automatic replacement or new-source enrollment.
