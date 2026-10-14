# M2: randomized support-only mechanism experiment

## Authority and independence

Anchor `7427f48`. Preserve every file in that commit, V13/M1 protocols and
raw captures. V13 stays closed: no frozen action sessions, action outcomes
or controllers. All M2 sessions reuse the now-observed V13 clips/traces and
are **development evidence**. No independent action-value confirmation,
network-program generalization or population significance is claimed.

The outcome-free diagnosis is in `NATIVE_BWE_MECHANISMS_M2_DIAGNOSIS.md`.
Replay inputs were exact, small replay/exposure differences weakly tracked
BWE repeat deviations, and late BWE/queue histories showed larger
associations. Internal estimator/probe state was not directly recorded.
The present experiment distinguishes **early service history** and **initial
estimator target**, with randomized interleaving instead of a longer wait.
Commit this plan, implementation and both protocols before any M2 capture.

## Technical manipulation check (two support-only sessions)

Before the mechanism experiment, run the Kampar clip once with each native
codec start target, **300 and 1,200 kbps**, at the already-registered M1
synthetic constant 1.4523718338280722 Mbps. Both sessions use fresh browser,
TURN instance, peer connections and empty queues.

Set `x-google-start-bitrate` on the VP8 offer/answer, and retain the same
**4 Mbps encoder ceiling both before connection and during measurement**.
This common preconnection cap differs from V13/M1's temporary 300 kbps
preconnection cap; that change is held constant within every M2 comparison.
Therefore M2's 300-kbps target arm is an experimental initialization control,
not a literal rerun of all V13 startup details. Record SDP parameters,
native cap and the actual pre-measurement and first measured BWE.

Both SDP start parameters must equal the requested value; actual native
BWE at the pre-measurement check and first measurement must equal the
requested target within **1 bps**. Mere SDP acceptance does not establish
successful initialization. Every inherited session gate below must also
pass. If either original session fails, do not run the 32-session mechanism
panel. Preserve the failed technical manipulation as evidence; no hidden
retry or weakened readback tolerance is permitted. A subsequent instrument
revision needs a new prospective registration with the failed one retained.

## Fixed factorial mechanism panel (32 sessions)

Use the exact original **AT&T LTE driving 2016 uplink-lower** 36-second
profile, which failed repeatability for both clips. Cross:

- Reused Kampar boating and Volga lock content (two productions).
- **Original measured history** versus **flat first-block history**.
- Native codec start targets **300 versus 1,200 kbps**.
- **Four fresh repeats** per content/history/initial-target context.

The flat prefix consists of twelve identical service rates equal to the
**arithmetic mean of the original first twelve source rates**. Thus the
first block's exact service integral is matched; bins 12–35 are the original
measured array unchanged. This is explicitly a **hybrid synthetic-prefix
diagnostic**, not a newly measured trace or independent native confirmation.
The original-history arm preserves all 36 measured rates, without scaling,
clamping, wrapping, interpolation or a new source window.

Run four blocks, one session for each of eight content/history/target
contexts per block, with their order shuffled by `random.Random(20261105)`.
Freeze the exact order and every panel/hash before capture. No extra
attempts, replacements, discarded blocks or partial-context qualification.
The randomized intervention is the baseline history/initialization recipe,
not a bitrate treatment or a fitted policy. Every panel has
`support_only=true` and assigns zero bitrate actions.

## Unchanged support and technical gates

Retain the V13 sampler and **36.6-second** duration, phases
`[12000,12000,12600]` ms, source clip/45-second segment without looping,
VP8 fixed degradation preference, 4 Mbps measurement cap, zero jitter target,
100 ms sender observation cadence, 5 Mbps pre-trace bootstrap service,
25 ms propagation and 30,000-byte queue limit. Do not extend conditioning.

The only support decision window remains **[18000,18300] ms**. Require eleven
native BWE samples spanning ≥900 ms, positive gaps ≤250 ms and every value
in **[240000,3800000] bps**. Mean `log2(BWE/500000)` is the continuous state;
500 kbps is a unit, not a binary threshold. Read back 4 Mbps and zero jitter
at every observation; require zero assignments and successful initialization
as in the manipulation check for every mechanism run.

Preserve managed `WebRtcIPHandling=disable_non_proxied_udp`, authenticated
relay-only TURN/TCP, both nominated TCP-backed candidate pairs and
bidirectional native media progress. Retain the twelve clock markers,
training `[0,1,3,4,6,7,9,11]`, held-out `[2,5,8,10]`, slope `[0.98,1.02]`,
100% coverage, width ≤50 ms and timestamp tolerance 1 ms. Require exactly
36 registered ticks in order with ≤150 ms error. Terminal drain remains
10 Mbps for ≤2 seconds, empty queues, exact served/forwarded packet counts,
zero send errors and byte conservation within `1e-6`.

All original captures must be sealed and every file checksum verified
before support telemetry is decoded. Missing qualification, startup readback,
transport, clock, trace or cleanup makes the affected context unqualified.
Finish and preserve the original 32 attempts even if a context fails;
do not use a passing subset to declare a mechanism/reliability result.
No outcome, frame quality/deadline, receiver feedback, encoded-frame meter
or per-hold cost/QoE is decoded in any M2 stage.

## Prespecified support analysis and decision

For each of eight factorial contexts, report all four states, BWE geometric
means, sample SD, full max-minus-min spread and all six pairwise differences.
The full four-repeat spread must be **≤0.25 octaves**, with all four session
gates passing. This is at least as strict as the original two-repeat rule;
no averaging hides an individual gate failure or excessive spread.

Within each content report mean-state contrasts, repeat variance ratios and
spread differences for the two randomized factors and their interaction.
Keep each content visible. In each randomized block, compute the history
and initialization mean contrasts and difference of differences; retain all
four blocks. For each main-factor sharp null, enumerate swaps within the
two levels of the other factor (four allocations per block, 256 across four
blocks). For the interaction contrast report its reference distribution
under the **joint no-recipe-effect sharp null**, using all 24 factorial
allocations per block (six equally repeated two-versus-two partitions give
the same contrast distribution). This joint-null calculation is not an
isolated interaction-null test in the presence of unknown main effects. Four
blocks and reused content do not supply a population CI or precise variance
component estimate. SD/spread comparisons are descriptive screens, not
proof that a noise mechanism has been eliminated.

Report pre-decision sender RTT, sending demand/encode timing, replay timing,
queue/service and timer histories by registered windows. They show how the
controlled factors change baseline dynamics; do not assign additive causal
shares to their correlated mediators. The initial native scalar is now
directly verified, but internal GCC probe state remains latent.

Candidate initialization for a **prospective full measured-support check**:

1. Only original measured-history contexts count; hybrid histories never
   qualify the measured panel.
2. If the 300-kbps arm passes the full four-repeat rule for **both clips**,
   select 300 kbps. Otherwise select 1,200 kbps only if it passes for both.
3. If neither qualifies, stop this development program after diagnosing the
   complete original mechanism panel. Do not run a full panel or actions.

A selected startup recipe is a development candidate, not proof of general
reliability or a controller. The selection rule is frozen before results;
there is no threshold, time, source or rate retuning.

## Conditional prospective replication (32 more support-only sessions)

Only if the candidate rule above succeeds, prepare and commit a new
development support protocol before these captures. Reuse the original
V13 two clips × eight measured profiles × two fresh repeats, all **32**
checks, with the selected initial target and common M2 preconnection cap.
Use the full original measured arrays and pinned licensed inputs. No hybrid
profile or synthetic session supplies this check. This prospective repetition
is still reused-source development, not independent content confirmation.

Enforce all original V13 per-session gates, **all 16 repeat differences
≤0.25 octaves**, **all four cell ranges ≥1.0 octave and SD ≥0.35**, and
**common four-cell overlap ≥0.5 octaves**. Both repeatability and common
support are necessary to say this selected panel's native conditioning is
prospectively reproducible enough to develop a causal action study. Do not
relax any gate, choose alternate traces, add attempts or discard a cell.
If it fails, close that replication with no action effects and no controller.
Even passing does not open V13 or establish conditional action value: a
separately registered untouched independent validation remains necessary.

## Storage and execution

External roots: `~/.cache/networkrlcd/native-bwe-mechanisms-m2-instrument-check`,
`native-bwe-mechanisms-m2`, and conditionally `native-bwe-mechanisms-m2-replication`.
Bound the project below 10 GB and budget ≤800 MB new external captures.
Keep protocols, summaries, provenance and receipts in Git. Preserve every
failure and all original media rights; licensed originals stay external.
Archive each completed stage under a fresh private HF namespace, pin its
revision, freshly download/verify every archive object and every file,
and delete no active/unarchived bytes.

```bash
python tools/measure_bwe_mechanisms_m2.py prepare
# Commit the plan, source and config before any capture.
python tools/measure_bwe_mechanisms_m2.py instrument-check
python tools/measure_bwe_mechanisms_m2.py capture
python tools/measure_bwe_mechanisms_m2.py summarize
# Only under the registered selection rule:
python tools/measure_bwe_mechanisms_m2.py prepare-replication
# Commit the conditional replication protocol before capture.
python tools/measure_bwe_mechanisms_m2.py replication
```
