# M3: prefix-history intervention with a fixed later measured service

## Question, authority and scope

Anchor **`7cf6ae5`**. M2 supplies development evidence: replay is accurate,
while fixed initial BWE does not ensure repeatable later BWE under measured
history. V13, M1, M2 and all prior freezes remain unchanged. No V13 action,
QoE outcome or controller is opened by this experiment.

Question: does changing **only the order of early service rates** causally
change later native BWE distributions after both sessions enter the same
measured service sequence? Do those distributions converge over the existing
36.6-second capture, and is current BWE alone an adequate support-state
description if memory persists?

This is randomized **support-only development** using the two reused V13
clips and one reused LTE source profile. The prefixes are constructed rate
permutations; only the common suffix is replayed in its original measured
order. Neither source-derived permutation is an independent measured-network
panel. Content and repeats remain nested in one measurement program. Commit
the entire plan, protocol and implementation before the first new capture.

## Minimal intervention and fixed inputs

Use `att_lte_driving_2016-uplink-lower` from the unchanged V13 source manifest.
Take its **first ten** one-second rates as a multiset. Prefix A plays them
in ascending order; prefix B plays them in descending order. Both contain
the exact same values/counts, duration and service integral; no rate scaling,
clamping, interpolation, new source offset or zero replacement is introduced.
The first ten rates sum to **14.112 Mbps·s**.

From source bin **10 onward**, use the original measured array, unchanged.
Thus both arms share the last two seconds of block zero and every rate of
blocks one/two. Common registered service begins at second 10; the original
18-second decision history is at least seven seconds into common service.
All 36 rates and the exact multiset/suffix identity are frozen in the protocol.

Use the unchanged M2 recorder, with the same fixed initial target **1,200 kbps**
for every arm and content, successful native/SDP readback within **1 bps**, and
4 Mbps cap before connection and throughout measurement. This target is held
constant as an experimentally verified initialization, not proposed as a
repeatability cure. The intervention does not change initialization, content
within a pair, encoder/jitter settings, transport, source segment, bootstrap,
queue size/delay, cadence, durations or cleanup.

The existing two M2 instrument checks qualify the unchanged recorder. Verify
their pinned gate, protocol, all file seals and source hashes; no new technical
smoke sessions or instrument modifications are needed. Current runtime and
all source assets must match the qualified bindings before capture.

## Replicas, power planning and randomized order

Run **21 fresh ascending/descending pairs per content**, two contents:
**84 original sessions**. Each pair has one capture per prefix with the same
clip and later trace. A fresh browser, peer connection, TURN server and empty
queue are used for every session; exact cleanup separates adjacent pair slots.

Use fixed seed **20261108**. In each of 21 blocks shuffle the order of the two
content pairs, and randomize their ascending/descending slot order with an
independent fair bit. Freeze every trial ID, panel, exact order and allocation.
The allocation unit is the prefix pair; marginal propensity is 0.5 and slot
one is complementary. Never count both slots as independent randomized sources.
No replacements, added attempts, dropped pairs or adaptive replica count.

The largest qualified M2 four-repeat SD was 0.25944 octaves. Conservative
independent-arm planning gives paired-difference SD 0.36691, ignoring possible
benefit from pairing. With per-content two-sided alpha **0.025**, 20 pairs give
79% and 21 pairs give **81%** normal location-planning power for a 0.25-octave
shift. Twenty-one is the smallest integer reaching the frozen 80% planning
target. This approximation does not guarantee power for arbitrary distribution
alternatives, heavier tails or equivalence. All actual uncertainty is reported;
no lack of significance is called convergence.

## Original gates retained

Retain 45-second clips without looping, the fixed VP8 recipe, 4 Mbps cap,
zero jitter, 100 ms observations, 5 Mbps pre-trace bootstrap, 25 ms propagation,
30,000-byte queue and phases **`[12000,12000,12600]` ms**. The original admission
window stays **`[18000,18300]` ms**: eleven BWE observations spanning ≥900 ms,
positive gaps ≤250 ms, every BWE in **`[240000,3800000]` bps**. All native cap/
jitter and initialization readbacks must pass, with zero bitrate assignments.
The 500 kbps denominator is continuous-state centering, never a binary split.

Preserve managed `WebRtcIPHandling=disable_non_proxied_udp`, authenticated
relay-only TURN/TCP, both nominated TCP-backed pairs and bidirectional media.
Retain twelve clock markers, training `[0,1,3,4,6,7,9,11]`, held-out `[2,5,8,10]`,
slope `[0.98,1.02]`, 100% coverage, ≤50 ms interval width and 1 ms timestamp
tolerance. Require all 36 exact rate ticks and ≤150 ms tick error. Terminal
drain remains 10 Mbps for ≤2 seconds, empty queues, exact served/forwarded
counts, zero send errors and conservation within `1e-6` bytes.

Verify every sealed file before decoding support telemetry. Complete all 84
original attempts even if a session fails; preserve failed seals and errors.
Every content-specific primary comparison requires **all its original 42
sessions** and 21 complete pairs to qualify. A failed session cannot be
replaced, interpreted as a treatment outcome or silently omitted. The overall
program is qualified only if all 84 pass; content-specific gated results remain
visible rather than a pooled partial-panel mean.

The original **≤0.25-octave repeatability** standard is retained and applied
to the full 21-repeat spread per content/prefix at each registered window.
Failing repeatability is a support result, not a prohibition on outcome-free
mechanism analysis after technical/admission gates pass. Original four-cell
range ≥1 octave, SD ≥0.35 and common overlap ≥0.5 remain mandatory before any
future full measured conditional-action panel. This single-suffix experiment
does not substitute for those full-panel gates.

## Replay fidelity after convergence of the input

Use actual training-marker affine bounds to map every realized rate tick.
Both arm arrays must match the frozen suffix; record actual phase/poll timing
and all clock uncertainty. Add a prospective pair fidelity check: for each
registered endpoint T, cumulative **service capacity exposure** over the fixed
sender interval **[11000,T] ms** must agree within **0.01 octaves**, including
the extrema over each run's feasible affine vertices. This is an input/timing
check, not achieved delivery or offered-byte cost. Every pair must pass for
that content/window's contrast to be estimable.

One second after the nominal common-input boundary excludes the differing
prefix boundary itself. Timing remains bounded, not identical at every
microsecond. Report residual tick/phase jitter, exposure differences and queue
history; do not assign all remaining variability to a particular estimator
component. No trace substitution or relaxed fidelity bound follows results.
Record both directions' queued bytes at the realized common-input tick,
first subsequent empty-queue time, and time-averaged queues/pump gaps over
0–10, 10–18, 18–24, 24–30 and 30–36 seconds. These diagnose joint queue/
estimator memory; empty queues at one instant do not identify the estimator
as the unique mediator.

## Registered BWE windows and distribution tests

The primary BWE scalar is the original mean `log2(BWE/500000)` over the first
eligible history in `[18000,18300]` ms. Also preregister diagnostic windows
**[24000,24300], [30000,30300], [36000,36300] ms**, with the identical eleven-
sample/span/gap/eligibility requirements. These observe convergence during
the unchanged capture; none replaces or delays the original admission gate.
Each later content/window is estimable only with all 42 original histories,
original technical/admission gates and all 21 suffix-fidelity pair checks.

Keep each content separate. At every window report all pair/arm states,
paired mean and median differences, arm SD/full spread, all order statistics,
**W1** (mean absolute difference of sorted arm samples) and **W∞** (maximum
absolute sorted-sample difference), in BWE octaves.

Primary causal screen: exact paired randomization of W1 at 18 seconds,
enumerating **2^21** slot swaps per content (complementary allocations have
the same W1 and can be counted twice). Test each content at **0.025**; this
controls the two-primary family at 0.05. Report exact p, complete randomization
reference, all pairs and effect distances. A rejected primary confirms a
finite-content effect of the randomized prefix on later BWE; both rejections
are needed to call it replicated across the two contents. It does not identify
queue versus estimator/workload mediation or imply a bitrate action effect.

Later W1 tests are secondary. Formal persistence tests are gated on that
content's primary rejection, using Holm correction across its three later
windows with local alpha 0.025. Ungated late contrasts/p-values remain
descriptive, and cannot supply a selected favorable primary result.

For uncertainty, paired-resample the **21 capture pairs**, 10,000 draws with
root seed **20261109** plus ten times the lexical content index plus the
endpoint's order index, retaining both arms in each draw. Report percentile 95%
intervals for the paired mean difference and W1, and the W1 97.5% upper
percentile. These describe uncertainty among repeated captures of the fixed
recipe, not independent-source or broad network population intervals.

## Prospectively defined convergence screen

At any registered content/window, finite-panel convergence requires:

1. Every original technical/admission/window/fidelity gate qualifies.
2. Each arm's full 21-repeat spread is **≤0.25 octaves**.
3. Empirical W∞ is **≤0.25 octaves**.
4. The paired-mean bootstrap 95% interval lies wholly within **[−0.25,0.25]**,
   and W1's bootstrap 97.5% upper percentile is **≤0.25**.

Call convergence sustained only if **both 30- and 36-second windows** pass
for **both contents**. Publish every failed component. A nonsignificant
randomization test, unchanged mean or positive one-content result cannot
replace this screen. Even sustained late convergence does not reopen V13,
move the 18-second support gate or establish full native common support.

## Conditional evaluation of a richer support state

Only if at least one qualified primary W1 test rejects, evaluate the fixed
state diagnostic below. A prefix effect on BWE alone does **not** prove raw
BWE is an insufficient state; current BWE may already carry the memory.
The evaluation asks whether additional observable sender history improves
prediction of the next BWE under the common measured service.

For each content and each transition **18→24, 24→30, 30→36 seconds**, require
all original current/future histories and gates. Fit separate fixed kernel
ridge support-state predictors, leave **one complete capture pair** out per
fold. No pair member enters its own training set, and no content or prior
study is pooled. Targets are future BWE only; no delivery/QoE/reward is used.

- Raw-state baseline: RBF kernel of current continuous BWE, bandwidth
  **0.25 octaves**, ridge **0.1**, training-mean-centered target.
- Augmented state: the same raw-BWE kernel plus an RBF history kernel,
  with bandwidth √D after training-only feature standardization. Extra
  features are two preceding one-second mean log-BWE histories (T−3 to T−2
  and T−2 to T−1 seconds), current one-second RTCP RTT/observed age, payload
  send rate, packet-send delay, encoder fps/encode time, and each applicable
  native-validity fraction. Missing entries are zero with validity indicators.
  Use the same ridge 0.1; no hyperparameter, feature or endpoint tuning.

Prefix label, content ID, elapsed stage, source/relay capacity/queue, receiver
pixels/feedback and future trace values are **excluded model inputs**. Models
are separate per fixed transition, so future service is held common rather
than supplied as an oracle. Queue and replay telemetry are mechanism checks,
not proposed deployed-state features.

Report every held-out prediction, residual prefix mean contrast, per-content/
transition RMSE and equal-transition squared loss. Bootstrap the original
capture pairs jointly over transitions, 10,000 draws with seed 20261110 plus
the lexical content index.
An augmented state is a promising **development candidate** only if each
content's equal-transition RMSE improves ≥20%, no transition worsens by >10%,
and both contents' 95% paired-loss-difference upper percentiles are <0.
Failure/unestimability remains visible. This predictive check does not prove
causal/Markov sufficiency; a separately frozen independent support/state
validation is required before another conditional-action study. No support
predictor is fitted or promoted as a controller.

## Workflow and preservation

```bash
python tools/measure_prefix_memory_m3.py prepare
# Commit plan, source and configs/native_prefix_memory_m3.json before capture.
python tools/results_storage.py status --check --planned-bytes 1000000000
python tools/measure_prefix_memory_m3.py verify
python tools/measure_prefix_memory_m3.py capture
python tools/measure_prefix_memory_m3.py analyze
```

Raw root: `~/.cache/networkrlcd/native-prefix-memory-m3`, outside the <10 GB
project. Bound new external captures/staging to the planned budget; preserve
licensed originals. Archive the complete original inventory, every failure,
protocol, gate and permitted support projection in a fresh private HF namespace.
Pin the revision and freshly verify every archive object and file checksum.
Delete no active/unarchived bytes. Keep compact protocols, reports, plots and
receipts in Git; preserve every file at `7cf6ae5` byte-for-byte.
