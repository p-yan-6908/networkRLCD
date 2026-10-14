# V13: preregistered continuous BWE-by-action validation

## Authority, question and scope

Anchor `a7ea1b0`. V12 is closed as a support-design failure with zero complete
cells and no action effects. V11D/V12 supply outcome-free development
diagnostics only. V10 remains closed. No earlier panel, synthetic development
session or reused production is pooled into this confirmation.

Question: under common pre-treatment conditioning, does the randomized
`1.05 minus 0.65` timely-quality contrast have a stable **continuous log2-BWE
gradient** across two new content productions and two new measured radio
families? This changes the state formulation and sampled context; it does
not claim to repeat the V9 binary estimand. BWE is not randomized. The causal
intervention is the bitrate action, not changing BWE itself.

The panel is a small finite-panel replication screen. It is not a population
estimate, a powered generalization study, or authorization to fit a controller.
The registration and its support/action panels must be committed before
the first new native support capture. This turn qualifies development only
and leaves both new panels untouched.

## New sources and explicit dependence

Two independent productions: Lelly Marliana/Joaquim Baeta's **Kampar River
boating** (Commons 122934090, CC BY 4.0) and Vitaliy Voland's **Volga lock
time-lapse** (Commons 48770370, CC BY 3.0). Both have pinned catalogue rights,
revision, size/SHA-1 and local SHA-256. The first 45 seconds are transcoded
without looping/audio to H.264 Main, 640×360, 30fps, yuv420p, CRF18. The six
reviewed frames at 0/8/16/24/32/40 seconds contain moving natural scenes,
no unrelated slate or pre-existing native outcomes. Attribution and derivative
licenses remain in `data/native-v13/sources.json`. Originals stay external.

Two new trace collection bundles, published directly in Mahimahi at revision
`f1346c38c415abfc98626dd82450f49a57033603`:

| Family | Collection provenance | Source streams |
| --- | --- | --- |
| Verizon EVDO driving | Original Sprout evaluation bundle, imported at `1a775777d2f8e667c59447bf0ff268178b6ff4ad` | Original driving downlink/uplink service-opportunity traces |
| AT&T LTE driving 2016 | Separately added 2016-named bundle at `524fe6bda7ebe94de98d00fdbe5bf61df7a3b2d4` | Original driving downlink/uplink service-opportunity traces |

These are separate raw bundles and radio families, new to V3–V12. They
share **one Mahimahi measurement program**, not two independent collection
institutions. Exact measurement days, subscribers and source independence
beyond the distinct published bundles are not established. The limited
confirmation cannot claim independent-program or deployed-network validity.

The publisher's GPLv3 distribution includes these original evaluation traces;
preserve `LICENSE-network-GPL-3.0.txt`, source URLs, Git blob SHA-1, SHA-256
and upstream commits. This is not a mirror-code-license claim about separately
owned FCC/Norway/Puffer datasets. Those alternatives remain excluded.

Each timestamp is a 1500-byte service opportunity in milliseconds, as the
pinned `mm-link` manual/code specify. Count original opportunities in complete
one-second bins and multiply by 12000/1e6. Discard only the incomplete terminal
second. Select uninterrupted 36-second windows whose **every rate** lies in
0.3–10 Mbps. For each of the four streams, take the minimum and maximum
geometric mean of the first nineteen source bins (indices 0–18), breaking
ties by earliest offset. The last input bin straddles the nominal native
decision boundary; this prospective source hint is not a causal BWE state
measurement and cannot establish support. Only the actual native history
and the separate census determine the continuous modifier.
All selected arrays/offsets are fixed in the manifest. There is no scaling,
clamping, interpolation, zero replacement or trace wraparound. Two LTE
windows from the same stream overlap; all overlap seconds are explicit.
The eight profiles are not eight independent measurement campaigns.

Replay one-second service rates symmetrically through the qualified userspace
queue. This discards original subsecond burst timing and direction asymmetry;
it is a measured-rate abstraction, not a live EVDO/LTE path or an exact
packet-opportunity replay. Windows/directions/repeats remain nested within
the two bundles. The four content × family cells are crossed repeated
sources, not four independent population observations.

Fjord5G traffic counters, sparse DEDICAT/EdgeInfrastructure tests, unsupported
mirror rights, high-rate 6GSMART records and previously used UCC sources were
examined and excluded without native outcomes. Reasons and verified-byte
provenance are retained in the acquisition manifest.

## Fixed conditioning, continuous state and support census

Every session starts a fresh browser profile, peer connection, TURN server
and empty queue. Keep the native encoder ceiling at **4 Mbps**, jitter target
zero, original VP8 recipe and 100 ms observation cadence before treatment.
The initial 300 kbps BWE is never accepted as settled support. Three exact
12-second rate blocks run for 36.6 seconds, with the final 0.6 seconds holding
the last measured rate. The movie's 45-second segment does not wrap.

The only decision window is **[18000,18300] ms** from sender measurement
start. Require eleven successive native BWE observations spanning at least
900 ms, gaps at most 250 ms, and every BWE in **[240000,3800000] bps**.
Keep those original unclipped-action bounds. There is no binary-bin
membership or 500 kbps boundary dwell requirement. A continuous state is
the mean of `log2(BWE/500000)` over that history, equivalently log2 of its
geometric mean. The 500 kbps value supplies units/centering only.

First run **32 support-only sessions**: two fresh repeats for every one of
the 2 content × 8 profile combinations. Every one keeps the common ceiling,
assigns zero treatments, and qualifies clock/transport/media/readback/trace/
cleanup/support. The registered all-panel support conditions are:

1. All 32 original sessions qualify, without replacements or extra attempts.
2. Both continuous census states exist for every content/profile and differ
   by at most **0.25 octaves** (about 19%). Freeze their mean as `x_cp`.
3. Every one of four content × family cells has all four profile states,
   a **range of at least 1.0 octave**, and sample SD at least **0.35 octaves**
   across those four frozen means.

These are prospectively specified design/range checks, not guaranteed by
capacity hints. If any fails, close V13 as a support-design failure, keep all
failures and do not begin the action panel or inspect outcome files.

A deterministic intersection of the four observed census ranges is reported
before randomization. Common overlap of at least **0.5 octaves** is separately
required for a claim of cross-campaign conditional-value stability. Local
gradient estimation may qualify with smaller/disjoint ranges; such a result
cannot establish transportability or open controller development.

## Randomized action panel and actual-run gates

Only after support qualifies, run **64 fresh sessions**: each content/profile
has two randomized pairs, with one `0.65` and one `1.05` hold per pair.
This yields **two holds per profile/action**, four profiles and eight pairs
per cell. A smaller single-pair panel would not preserve the prospectively
required two-hold minimum for each continuous context and would leave very
little sensitivity support.

Order is the fixed manifest order, with pair slots adjacent and all completed
cleanup between sessions; `20261101` is the inventory namespace, not a claim
of shuffled sessions. Action seed is **20261102**, namespace
`networkrlcd-native-v13`. Decode the first big-endian uint32 of
`SHA256(networkrlcd-native-v13:{seed}:{pair_id})` only after actual session
support. Its low bit chooses slot zero; slot one gets the complement.
Marginal propensity is 0.5; given slot zero, slot one's conditional propensity
is one. The randomized allocation unit is the pair. Repetitions and slots
are not independent sources or independent Bernoulli allocations.

Both actions multiply the **instantaneous actual pre-action BWE**; round to
nearest bps and reject clipping outside 150 kbps–4 Mbps. Each actual run
repeats the entire fixed-window history check and must be within **0.25
octaves** of its frozen census `x_cp`. Agreement is checked on the sealed
pre-action records before outcome access; a mismatching session invalidates
the entire panel even if its range-qualified cap was assigned. This links the previously measured
continuous conditioning context to the actual sender state; the census never
substitutes for missing action-run support. Exact draw, support history,
ratio, base BWE, cap, first ack and native readback are retained. Ack delay
must be ≤100 ms, and the cap persists at least 3000 ms.

All 64 seals, all actual gates, all state agreements and exactly two qualified
holds per profile/action are required before outcome decoding. A failed
session is a technical/support failure, never a treatment outcome. There is
no extended wait, threshold/count change, state relabel, source substitution,
added capture, replacement session, seed change or partial-cell mean. An
interruption does not authorize silently reusing a nonempty capture directory.

## Qualified instrumentation retained

Preserve managed `WebRtcIPHandling=disable_non_proxied_udp` and relay-only
authenticated **TURN/TCP**. Both peers must gather relay candidates and
nominate TCP-backed pairs with bidirectional media. Every block must have
more than ten newly encoded/decoded frames and finite encode time.

Retain twelve marker IDs and endpoint/phase order; train `[0,1,3,4,6,7,9,11]`,
hold out `[2,5,8,10]`. Affine slope is bounded to `[0.98,1.02]`; held-out
coverage is 100%, width ≤50 ms, timestamp tolerance 1 ms. The old qualified
120-marker reference remains a reference, not a replacement for actual-run
alignment. Exactly **36 registered ticks** must match all source rates/order,
with the unchanged **150 ms** tick tolerance. Source/runtime/managed-policy
hashes remain pinned.

Terminal drain starts after browser measurement cutoff, at 10 Mbps for at
most 2 seconds. Require empty final queues, exact served/forwarded counts,
zero send errors and conservation within `1e-6` bytes. Its rates/bytes stay
outside measurement and treatment windows. Verify every session file's seal
before permitted telemetry access. Per-hold relay joins are possible only
after validated actual-run affine alignment.

The new duration/sampler/36-tick checks undergo six development sessions
using V11D cicada content and explicitly **synthetic** constant 0.35/1.2 Mbps
links: one census and both complementary actions per link. All development
outcome files stay unopened. This only qualifies instrumentation, not a
measured-network interaction or the new census's state variation.

## Outcomes, estimand, heterogeneity and decision

Preserve the existing **ack +1800 to +2600 ms** endpoint inside the middle
trace block, paired source/receiver RGB sampling, and **150 ms** readback
deadline. Each hold's timely PSNR is the sum of observed timely finite RGB
PSNR divided by its timely PSNR-frame count. Missing quality is not imputed;
a hold without timely quality makes the primary panel unestimable.

For pair `p` at content/profile context `cp`, compute the hold-quality
difference `D_p = Y_(1.05) − Y_(0.65)`. Within each crossed cell fit the
prespecified finite-panel linear projection `D_p = intercept + beta*x_cp`,
using all eight pairs equally. Primary: **beta, dB per BWE doubling**. The
modifier was frozen before every treatment; no later BWE or treatment-dependent
covariate is used. This is a new continuous-context estimand, not the old
frame-weighted dichotomized interaction or a causal effect of varying BWE.
The intercept is not interpreted when 500 kbps is outside observed support.

Secondary: the same paired continuous slopes for on-time source-frame
fraction, guaranteed offered relay wire bytes per hold and guaranteed dropped
wire bytes per hold. Preserve possible clock-boundary bytes. Report every
pair/profile/arm, timely/missing frame counts, cell slope, content mean,
campaign mean and actual state range. Equal-cell crossed means are descriptive
only. A stratum mean is undefined if any constituent cell is unestimable.
Do not pool prior sources or convert repeated windows into a population CI.

The two-sided local-gradient directional stability screen requires:

1. Every primary cell and all eight constituent paired contrasts are estimable.
2. All four cell slopes have the same nonzero sign.
3. Both content means and both campaign means have that sign and magnitude
   at least **0.25 dB per octave**, a prospective screening margin.
4. Every prespecified leave-one-profile sensitivity in each cell is estimable
   and retains the sign. Retain all four sensitivities, including overlapping
   source windows; do not select a favorable sensitivity.

Cross-campaign common-support stability additionally requires ≥0.5 octaves
of common census overlap. Its absence cannot be hidden behind a pooled mean.
No population significance claim is made from this small selected panel or
from two bundles sharing one measurement program.

Even a qualified quality gradient is not policy value: PSNR conditions on
successful timely delivery, and relay volume is only a local cost proxy.
Controller fitting/promotion, V10 retuning and any learned-policy claim stay
closed. If gradient/common-support confirmation succeeds, the next informative
step is a separately preregistered native delivery/QoE-and-cost comparison
against fixed **0.65**, with genuinely new measurement-program/content
validation and explicit utility/coverage gates. Mixed effects freeze a
negative conditional-gradient result; unsupported or unestimable panels freeze
their qualification/estimability failure with no rescue.

## Frozen workflow and storage

```bash
python tools/design_native_v13.py verify
# Future turn, after this registration is committed:
python tools/results_storage.py status --check --planned-bytes 800000000
python tools/design_native_v13.py support-census
python tools/design_native_v13.py capture
python tools/design_native_v13.py gate
python tools/analyze_native_v13.py
```

The collector's legacy `stage=discovery` compatibility tag does not change
the scientific protocol's `confirmatory=true`. Large raw output, originals
and staging remain in `~/.cache/networkrlcd/`, outside the <10 GB repository.
Private immutable HF snapshots and fresh archive/file checksum verification
are required before any pruning. No licensed original or unarchived bytes
are deleted. All files present at `a7ea1b0` are hash-bound and preserved.
