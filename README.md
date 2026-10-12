# Calibrated RL for Safe Real-Time Media Adaptation

A reproducible **simulation research framework**, not a certified safety system or a WebRTC/GCC implementation. An actual NumPy Double DQN chooses bitrate, FEC and media mode. A separate episode-bootstrap safety ensemble estimates the probability that its proposed action meets next-interval latency/loss constraints. Held-out Platt/temperature calibration, a telemetry-support guard and hysteresis determine when to use a deterministic conservative controller.

## Storage policy: keep the project below 10 GB

**Owner-approved:** keep this entire project tree below **10 GB (10,000,000,000 bytes)**;
start cleanup at 8 GB. Large raw captures, source working copies, downloads and archive
staging belong outside the repository (`~/.cache/networkrlcd/`), while compact reports,
summaries, protocols, manifests, checksums and archive receipts stay in Git. Raw evidence
is archived in the existing **private** Hugging Face dataset before checksum-verified
local pruning. Moving data outside the tree alone is not a backup or disk-space saving.

Read [AGENTS.md](AGENTS.md), [the storage policy](docs/STORAGE_POLICY.md), and
[archive/recovery records](ARCHIVED_RESULTS.md) before a large job. Budget check:
`python tools/results_storage.py status --check`. Never prune active captures or rewrite
historical seals. New multi-GB jobs must use an external output directory.

## Run

Requires Python 3.11+ (locked reference: Python 3.12) and [uv](https://docs.astral.sh/uv/).

Generated run artifacts under `results/` and large local recorded-video binaries are intentionally not included in this repository. The small source descriptors and attribution pages under `data/native_video/` retain provenance and checksums; native recorded-video workflows require the corresponding local media assets. Tests that depend on omitted research artifacts are skipped in a clean source-only checkout and run when the local evidence bundle is present.

```sh
uv sync --frozen --extra dev
uv run pytest -q
uv run media-rl run --config configs/smoke.json --out results/my-smoke
uv run media-rl audit --run results/my-smoke
# Three-seed exploratory pilot; not confirmatory evidence
uv run media-rl run --config configs/demo.json --out results/my-pilot
# Larger predeclared protocol (not run by default)
uv run media-rl run --config configs/paper.json --out results/my-paper
```

Output directories must be empty/nonexistent; existing evidence is never silently overwritten. CPU training is sufficient for these small networks. The user permits Modal CLI GPU training if needed; see [`GOAL.md`](GOAL.md). No GPU jobs are required or launched by this package.

## Synthetic Typed-Control (JevBWE typed decisions)

A small Jev-like head answers one typed question per second (which of six BWE-relative bitrate ratios is best over the next few seconds) and reports a probability for every option. It is trained on strictly proper scoring rules, using the RLCD recipe of REINFORCE over noisy reported logits, with labels from counterfactual rollouts in a forked simulator. The controller multiplies the probabilities by a fixed payoff table. **Synthetic only; nothing is promoted.** This is a separate track from the native actuator study: it does not touch the native controller freeze and does not answer the native identifiability problem, because a real network cannot supply rollout labels.

- **[V2](docs/JEVBWE_TYPED_V2.md), trained on four families.** In distribution the head beats the fixed ratio selected on training families by **+0.213 utility**, positive in 4 of 4 families (family-level interval [+0.066, +0.361]). On seven held-out families the mean gain is +0.047 but its family-level interval [-0.027, +0.122] includes zero, and calibration degrades (ECE 0.152; pooled ID ECE 0.012 hides up to 0.181 per family).
- **[V3](docs/JEVBWE_TYPED_V3_BROAD.md), trained on thirteen broader families, tested once on twelve untouched families** against criteria written down beforehand. Gain +0.054, positive in 7 of 12 families, family-level t interval [-0.005, +0.112]: not established. Pooled ECE 0.070: above the 0.05 threshold. Unsafe intervals down 0.72 points: met.
- **[Baseline audit](docs/JEVBWE_TYPED_BASELINE_AUDIT.md): the comparator was not weak.** The fixed ratio 1.05 is an interior optimum of an extended grid, and the best of 204 tuned reactive rules over the same options adds at most +0.008 on any panel.
- **[V3 replication on a sampled family population](docs/JEVBWE_TYPED_V3_REPLICATION.md), registered before it ran.** The frozen V3 models, evaluated once on 48 families drawn from a stated population, meet three of four criteria: gain over the train-selected fixed ratio +0.019 (family-level t interval [+0.005, +0.034], 32 of 48 families) and +0.020 over the tuned rule; unsafe intervals down 0.26 points; pooled ECE 0.138, so calibration fails. The gain is 18% of the hindsight oracle's, absent in 19 families, and not established against the best fixed ratio in hindsight (+0.012, interval includes zero).
- **[Factual supervision](docs/JEVBWE_TYPED_FACTUAL_V1.md): possible, and about sixty times as costly.** A learner that sees one randomised option per 5 s block, as a real network would allow, has an established in-distribution gain from 36 hours of link time and reaches +0.105 at 571 hours. A control trained on rollout labels reaches +0.109 at 9 hours. Development study; a floor for a real network, not an estimate.
- **[Factual supervision on unseen families](docs/JEVBWE_TYPED_FACTUAL_V2.md): mixed, and harmful when data are thin.** Trained on 64 population families and scored on the two read population panels, the factual learner at 571 hours gains +0.036 [+0.016, +0.057] on one and +0.009 [-0.003, +0.020] on the other; at 36 hours it loses utility on every panel (-0.033 [-0.062, -0.005] on the harder one) and its doubly-robust selection step approved the policy in all three seeds. Development evidence.
- **[Native actuator qualification](docs/NATIVE_PHASE_N1_RESULT.md) bears on all of the above.** On a real browser the requested ratio does move the encoded rate, but the encoder realises 72% of the step from 0.65 to 0.85 and 47% of the step from 0.85 to 1.05, and a cap on the encoder cannot push it above the browser's own estimate. The simulator's sender follows ratios above one, including the train-selected base ratio 1.05, so the synthetic gains do not transfer to that actuator as they stand.
- **[Headroom when the option set stops at the estimate](docs/JEVBWE_TYPED_HEADROOM_V1.md): most of it survives.** A model-free check prompted by the native result. With the top option at 1.00 a fixed policy loses nothing and 78% and 83% of the hindsight headroom remain on the two population panels, so what the simulator offers a controller is mostly the chance to back off, which a cap can do. Cut off at 0.90 the share falls to 37% and 51%. Development evidence; the native pilot found no schedule under which a lower ratio scored better, and the two are not reconciled.
- **[Per-link crossover](docs/JEVBWE_TYPED_CROSSOVER_V1.md): a negative result.** Alternating two ratios in blocks within a session does not identify which is better on a link. Blocks of 3 to 9 s measure a different quantity (carryover through the estimator and encoder); half-session blocks need more sessions than randomising whole sessions, which needs about 190 to 440 per ratio for adjacent ratios.
- **[V4](docs/JEVBWE_TYPED_V4_POPULATION.md), the V3 method trained on draws from the population, tested once on a sealed panel.** All four criteria fixed in advance are met: gain over the train-selected fixed ratio +0.032 (family-level t interval [+0.008, +0.056], 35 of 48 families), +0.032 over the tuned rule, pooled ECE 0.020, unsafe intervals down 0.87 points. Read with its registered secondaries: no established utility advantage over the V3 head on the same traces (+0.004 [-0.018, +0.026]); family-level ECE above 0.05 in 38 of 48 families; an untyped regression beats the typed head by 0.023; and the development panel, read first, gave +0.012 with an interval that includes zero.
- **The RLCD recipe is not what helps.** An exact-gradient control matches the head on every panel, and an untyped regression matches it under V2 and V3 and outperforms it under V4. What they share is rollout supervision.
- **No hindsight at run time.** Replaying every learned test episode with rollouts switched off reproduces the frozen outcomes exactly.

The V2 study also explains the earlier null results. The legacy GCC-like estimator grows without bound when the sender is below capacity, so the old `0.85 x BWE` fallback was an untuned baseline. Over that estimator a fixed 0.60 ratio is a constant cap that scores higher utility than the typed head over the bounded estimator (0.636 against 0.527) with more unsafe intervals (7.20% against 4.55%); neither dominates.

```sh
uv run --frozen jevbwe-typed run --config configs/jevbwe_typed_smoke_v2.json --out results/my-typed-smoke
make jevbwe-typed            # V2: diagnosis, main study, ablation and replication; about two hours on 8 cores
make jevbwe-typed-audit      # V2: replay checks and the family-level audit of the frozen panel
make jevbwe-typed-broad      # V3: train, validation and development panels; about 90 minutes
make jevbwe-typed-broad-test # V3: the untouched test panel, once
make jevbwe-typed-baselines  # tuned reactive rules against the frozen V3 panels; about three minutes
make jevbwe-typed-replication # frozen V3 models on the registered population panel, once; about 75 minutes
make jevbwe-typed-factual    # factual supervision against a rollout-labelled control; about an hour
make jevbwe-typed-population # V4: train on the population pool, development panel; about two hours
make jevbwe-typed-population-test # V4: the sealed panel, once, after the freeze commit; about 100 minutes
make jevbwe-typed-crossover  # per-link crossover identification; about five minutes
make jevbwe-typed-factual-unseen # factual supervision trained on the pool, scored on both read panels; about an hour
make jevbwe-typed-evidence   # paper macros, tables and figures
make jevbwe-typed-followup-evidence # the same for the audit, replication and factual study
```

`results/` is ignored except for the small summaries the paper reads (config, report, audit and isolation JSON). On a clone those already occupy `results/jevbwe-typed-*`, so pass `TYPED=results/regen` to regenerate into fresh directories; see [what is tracked](docs/JEVBWE_TYPED_V2.md#what-is-tracked-and-regenerating-the-rest).

## JevBWE V1: supervised bitrate residual (superseded)

Superseded by the typed-decision study above, which shows its `0.85 x BWE` fallback was an untuned baseline. Code and artifacts are unchanged.

The [residual research path](docs/JEVBWE_RESIDUAL_V1.md) ranks **six BWE-relative bitrate ratios**, not the legacy 42 joint actions. It uses three seconds of ordered causal history, separate requested/actual/encoder-target telemetry, a **1.8-second increase dwell with immediate decreases**, and encoder-settled/network-delayed delivered-QoE credit. Matched state-only checks of utility **and delivered-only QoE** must pass before screened learned control is enabled. The first workflow is **synthetic only**; old native data/weights are not relabeled, and no native superiority or safety is claimed. The completed pilot passes predictive action skill, but a separate fallback-only diagnosis shows **no demonstrated neural control gain**, so it is not promoted.

```sh
uv run media-rl jevbwe-run --config configs/jevbwe_smoke_v1.json --out results/my-jevbwe-smoke
uv run media-rl jevbwe-audit --run results/my-jevbwe-smoke
```

## JevBWE-RLCD V1: factual-bandit pilot (superseded)

Superseded by the typed-decision study above. This pilot scored an event that barely depends on the action, on 432 factual cohorts; its failure says little about whether the approach can work. Code and artifacts are unchanged.

The [experimental numeric RLCD path](docs/JEVBWE_RLCD_V1.md) preserves the supervised JevBWE baseline and frozen risk model. A **1,846-parameter six-action policy** uses Gaussian REINFORCE and factual-only, inverse-propensity-weighted proper log/spherical rewards. New IID exploration logs known conditional propensities; unobserved actions are never fabricated as failures or winners. The optional local **Laya** typed-decision benchmark is separate and is **not** the default controller.

The synthetic pilot has valid randomized identification data but **does not qualify causal action discrimination or demonstrate learned control gain**. Both paths remain unpromoted; genuine Laya inference was not run. The dedicated document covers probability semantics, statistical/safety gates and optional setup.

```sh
uv run --frozen jevbwe-rlcd run --config configs/jevbwe_rlcd_smoke_v1.json \
  --baseline-model results/my-jevbwe-smoke/training/model.json --out results/my-rlcd-smoke
uv run --frozen benchmarks/jevbwe/verify_rlcd.py --run results/my-rlcd-smoke
```

## Causal actuator identification: next milestone, no new model

The [separate native diagnostic](docs/NATIVE_ACTUATOR_IDENTIFICATION_V1.md) freezes
all controller architectures. It randomizes **{0.65, 0.85, 1.05} × observed BWE**,
holds each assignment for **3 s after acknowledgment**, and logs actual encoded
payload output separately from encoder target and RTP send rate. Fresh discovery
and replication clips, factual-only outcomes and staged actuator/QoE gates come
before any state×action ML. Laya remains deferred; policy probabilities are not
probabilities that a bitrate is "correct".

**Native smoke:** four peers, 2,009 encoded-frame events and 24 complete cohorts
replay exactly. Thirteen windows were non-plateau and retained. Only two physical
blocks per role: **insufficient causal qualification**, not an established negative
action effect. No policy was trained or promoted. Licensed content reservations
are nearly exhausted; do not recycle old validation clips for a powered panel.

```sh
uv run --frozen media-actuator plan --config configs/native_actuator_identification_smoke_v1.json --out results/my-actuator-plan
uv run --frozen media-actuator run --protocol results/my-actuator-plan/protocol.json --out results/my-actuator
uv run --frozen media-actuator audit --root results/my-actuator
```

## Native Phase N1: actuator qualification (registered, run once: qualified)

The [N1 preregistration](docs/NATIVE_PHASE_N1_ACTUATOR_QUALIFICATION.md) isolates one question from the powered panel below: does the requested ratio separate the actual encoded output rate? It reuses the frozen controller, the three-arm randomized hold protocol and the unchanged collector, makes no QoE claim, and leaves the 96-unit panel untouched as Phase N2. It needs **12 independent source clusters** at minimum (4 per complexity tercile), extended in balanced blocks to at most 24 by a blinded rule that exposes only the prescribed source count.

**Result (2026-10-09): qualified.** The capture ran once on the sealed plan: 12 Wikimedia Commons sources, 480 fresh native peers, 2,880 assigned cohorts, capture support passed, and the blinded interim prescribed no extension. Encoded rate over frozen BWE rises by +0.144 from ratio 0.65 to 0.85 (one-sided 97.5% lower bound +0.128) and by +0.094 from 0.85 to 1.05 (lower bound +0.067), against a margin of 0.03. The encoder realises 72% and 47% of the requested steps, and within the two persistently constrained regimes the upper step is not established after correction. This qualifies the actuator on one browser build over a local userspace relay. No controller acted, no quality was measured, and nothing is promoted. See the [result](docs/NATIVE_PHASE_N1_RESULT.md), the [capture log](docs/NATIVE_PHASE_N1_CAPTURE_LOG.md) and the [acquisition log](docs/NATIVE_PHASE_N1_ACQUISITION_LOG.md).

An [exploratory description](docs/NATIVE_PHASE_N1_EXPLORATORY.md) of the same rows, fixed before it was computed and not confirmatory, adds two things. A cap below the estimate holds back the estimate itself when the link has room (it grows 18%, 24% and 100% per 3 s hold at ratios 0.65, 0.85 and 1.05 under the unconstrained schedule), so a ratio of the estimate is not a fixed reference. And in a pilot look at the on-time PSNR proxy, no schedule shows a lower ratio to be better: the top ratio is ahead by +1.26 [+0.33, +2.18] overall, mostly in the first two holds of a session. A second pass by what the sender had seen before each hold names no candidate signal under its pre-declared rule; in the third of holds flagged by high jitter, high RTT or a stalled estimate the point estimates favour backing off by 0.5 to 1.5 and are not established (smallest Holm-adjusted p 0.27). A confirmatory study of that would need roughly 40 to 60 fresh sources to detect a difference of 1.

The owner chose that study as the next native step and confirmed its design. [Native Phase B1](docs/NATIVE_PHASE_B1_BACKOFF_BENEFIT.md) is registered and hash-frozen (`configs/native_backoff_benefit_b1_freeze.json`) before any of its data exist. It asks one question on fresh sources: in holds flagged beforehand by a stalled estimate, is the on-time PSNR proxy higher at the two lower ratios than at the top one? The sample is fixed (every eligible source, at least 30), with one endpoint and no interim. Its planner, capture loop and analysis have run only on mock rows and test doubles (`uv run --frozen media-backoff-benefit dry-run --out results/my-b1-dry-run`). Nothing is downloaded or captured. The owner has set the acquisition terms: they return a reviewed copy of the rights manifest for the 74 undrawn Discovery V2 candidates (`acquisition/native-b1/rights-review/`, with the verbatim evidence strings a binding quote may cite), the download budget is 10 GB with files under 1 GB (`configs/native_backoff_benefit_b1_acquisition.json`), and room for the capture comes from moving old results to the private archive described in `ARCHIVED_RESULTS.md`. The capture itself still needs the owner's go-ahead.

Before B1 has any data, the simulator's answer to it was written down ([forecast](docs/JEVBWE_TYPED_B1_FORECAST_V1.md), synthetic, design committed before the run, `make jevbwe-typed-b1-forecast`). Run under B1's protocol on mirrors of the four native schedules and scored with B1's registered estimator, the simulator forecasts that backing off *lowers* its on-time quality term in flagged holds, by about 12% of the top ratio's level, under both descriptions of the actuator (-0.114 [-0.134, -0.094] as built, -0.107 [-0.116, -0.098] at the levels N1's encoder realised), and that the flag separates nothing. Set beside N1's known figures, the simulator produces the flag differently: a hold is flagged 96% of the time after a request of 0.65 and 4% to 10% after the others, against 51%, 23% and 28% natively. B1 will show whether the simulator or the pilot's lean is right; the reading rule is fixed. This is not native evidence.

A third exploratory pass reads N1's raw logs for mechanism only, with no quality label ([what happens inside a hold](docs/NATIVE_PHASE_N1_DYNAMICS.md), design committed before the run). When capacity drops, every ratio overshoots, because the request is a ratio of an estimate frozen before the drop, and the browser's own estimate is below the new capacity within 0.4 to 0.9 s whatever the cap. Under steady constraint nothing is dropped at any ratio. With room, a cap above the estimate makes the estimate nearly double within 0.6 s, and a cap below it holds it nearly still (about 5% and 14% per hold after the first; the earlier 18%, 24% and 100% pooled the first hold). The encoder needs most of a hold to reach a new cap. Of the holds B1's flag marks, about a seventh are the hold of a drop, the one place where a lower cap left less queue and loss, and the flag does not see the drop coming. The pass reads the sender and the relay only. Its record first called the relay the only path by which a cap can help and said the uncapped browser had never been measured here; both were wrong and are corrected in it. Earlier development diagnostics ran the browser under a 4 Mbit/s ceiling, where it delivered far fewer frames on time than any capped sender (10% to 51% against 56% to 92%), and they put the cost at the receiver, which this pass does not read. So the three ratios of N1 and B1 are caps compared with each other, and the baseline to beat is a tuned cap, not the uncapped browser. A [B1 addendum](docs/NATIVE_PHASE_B1_ADDENDUM_POSITIONS.md), fixed before B1 has data and outside its frozen registration, splits B1's holds by position to show where any benefit sits.

A fourth exploratory pass reads the rest of the path from the same capture ([where a hold's frames and time go](docs/NATIVE_PHASE_N1_DELIVERY.md), design committed before anything was computed by ratio; it reads the auditor's timing labels and no PSNR). From the second hold on, 76%, 75% and 74% of the capture requests of the registered window are on time at the three ratios (top minus lower: -1.5 points [-4.1, +1.0]). The schedule moves that from 93% with room to 52% under collapse-recovery. A request that misses the deadline was mostly shown, late, and the time is lost after the relay: the receiver's jitter buffer holds 27 ms per frame with room and 124 ms under collapse-recovery, at all three ratios alike. One of four statements fixed in advance holds: a higher cap fills the receiver's buffer, by +10.5 ms [+4.6, +16.3] from the lowest to the top ratio, and by +36 ms under the schedule with the deepest drop. Added after the tables were read: the earlier figure that the top ratio is no worse on timing pooled the first hold, in which a cap of 195 kbit/s makes the encoder skip 29% of the frames (top minus lowest: +21.0 points [+8.8, +33.1]); from the second hold on the contrast is -2.2 points [-5.0, +0.5]. So among these three ratios the cap hardly reaches what makes frames late, and the simulator, which counts a fixed delay at the receiver, leaves that place out. None of this says whether backing off helps; B1 measures that.

A development pilot then kept one cap level for a whole session ([wide-range pilot](docs/NATIVE_RANGE_PILOT_V1.md); approved by the owner, design committed before any session of record; 240 sessions on N1's twelve used sources, all sealed; **not confirmatory**). The levels are 0.25, 0.65, 0.85 and 1.05 of the estimate, and the browser under the 4 Mbit/s ceiling. From the second hold on, the endpoint is 26.60, 26.36, 23.85, 21.44 and 13.07, and the share of requests on time 88%, 82%, 70%, 62% and 36%. Against 1.05, the level 0.65 gains +4.92 [+2.17, +7.67] and 0.25 gains +5.16 [+2.25, +8.06]; the ceiling loses 8.37 [5.60, 11.15] and is below 1.05 in all twelve sources. The receiver's jitter buffer grows from 30 ms to 190 ms as the encoder goes from 19% to 65% of capacity. After a drop of capacity the lowest level does best (87% on time against 34% at 1.05 under collapse-recovery); with room 0.85 does best and both ends lose; under near-capacity nothing is established. N1's per-hold contrast saw little of this because a level that is kept also sets the estimate it is a ratio of. What follows is stated as development evidence. On this endpoint the strong fixed baseline is a lower fixed ratio, not 1.05 and not the uncapped browser. B1 is unchanged, but finding no benefit of backing off within a hold would not show that a sustained lower cap does not help. And the simulator, whose train-selected fixed ratio is 1.05, orders the ratios the other way round: run on the same five sustained levels ([direct check](docs/JEVBWE_TYPED_SUSTAINED_LEVELS_V1.md), synthetic, done after the pilot was read), it ranks the four ratios in the reverse order over all schedules, shares its best level with the pilot under no schedule, and with room rates the ceiling best where natively it is worst. One session per cell, used sources, one machine carrying sender, relay and receiver; nothing is promoted.

A second development pilot then ran the first native test of a controller against a tuned baseline ([controller pilot](docs/NATIVE_LADDER_PILOT_V1.md); approved by the owner, design committed before any session of record; 480 sessions, two per cell, on the same twelve used sources, all sealed; **not confirmatory**). **The result is negative.** Two rules move among the ratios 0.25, 0.65, 0.85 and 1.05 by the age of the presentation acknowledgements the sender receives; the second also cuts to the bottom inside a hold. Over the whole session the endpoint is 22.79 under the ladder and 23.94 under the fast ladder, against 25.34 and 26.06 at the tuned fixed levels 0.25 and 0.65 and 21.87 at 1.05. The ladder loses to both tuned levels (−2.55 [−3.80, −1.30] and −3.27 [−4.84, −1.69]). The fast ladder loses to 0.65 (−2.12 [−3.99, −0.24]), is not separated from 0.25 (−1.40 [−3.12, +0.32]) and beats 1.05 (+2.07 [+0.43, +3.71]). Neither rule stepped up once. The fixed levels repeat the range pilot's comparison on the same sources: 0.25 and 0.65 gain +3.47 [+1.50, +5.44] and +4.19 [+1.94, +6.43] on 1.05. A description added after the report was read shows where the rules lose: after a drop of capacity the fast ladder is at the bottom within a stretch and offers 14% of capacity in the phase after the drop, yet the receiver's jitter buffer still holds 157 ms per frame there, against 50 ms at the fixed 0.25. A cut that waits for lateness comes after the receiver's buffer has grown, and the buffer shrinks more slowly than an 18.6 s session lasts; a fixed low level never lets it grow. The schedules have at most one change of capacity, at 6 s, so they cannot show what history could give a controller. On this harness the tuned fixed ratio stands unbeaten; nothing is promoted.

A synthetic step followed, approved by the owner: a receiver layer on top of the simulator, fitted on the range pilot only and tested once on the controller pilot ([receiver layer](docs/JEVBWE_TYPED_RECEIVER_V1.md); layer, fitting procedure, test and verdict rule committed before anything was fitted; one revision of the fitting from the range pilot's residuals, recorded before the test). The layer makes the cap a cap, adds a receiver buffer that rises at once and falls slowly (fitted time constant 35 s), and values frames as the native endpoint does; the endpoint is never a fitting target. **By its own rule the verdict is negative: the layer does not predict the controller pilot.** Of the eight differences between arms established natively, seven agree in the simulator and one is flat: the simulator does not reproduce that cutting fast helps (+0.03 against +1.37 natively). What it does reproduce: both rules below both tuned fixed levels and above 1.05, all five simulated endpoints inside the native 95% intervals (22.6, 22.7, 27.9, 27.0, 18.4 against 21.8, 23.2, 26.6, 26.8, 20.7), 19 of 22 differences established under single schedules, and rules that never step up. On the range pilot the layer has the five levels in the native order, with 7 agreements, no disagreement and 13 unclear where the simulator as built had 4, 6 and 10. With the buffer held still the order is wrong. The miss comes from the simulator's estimator, which the layer leaves as built. The synthetic track stays set aside for native claims; both pilots are now used, so a further test needs native sessions the layer has not seen.

**The long-session pilot is complete and negative** ([results](docs/NATIVE_MARGIN_PILOT_V1.md#results-2026-10-11)): 192/192 one-minute native sessions, four schedules including recurring drops, on twelve used sources. The rule with memory loses to tuned fixed 0.65 by **−1.13 endpoint units [−1.99, −0.27]** and 3.87 on-time percentage points; it is not separated from 0.25 and beats 1.05. A post-report six-comparison Holm check retains the loss (adjusted p = 0.043); no controller is promoted. **The unchanged simulator forecast fails the registered blind test**: 3 of 4 established overall contrasts agree, but it forecasts the rule against 0.65 as flat. All four forecast arm averages lie within their native intervals, which is insufficient validation. The compact factual reports reproduce within rounding tolerance; this verification does not restore or replay raw captures. Reports, pinned inputs and code hashes are in `reports/native-margin-validation-v1/`. Native estimator recovery differs from the forecast; the [active research status](docs/RESEARCH_STATUS.md) records the next uncertainty and the separate synthetic/native validation boundaries.

**The [factual BWE dynamics diagnostic](docs/BWE_DYNAMICS_DIAGNOSTIC_V1.md) does not qualify a simple repair.** Fixed-penalty regressions fitted on short range sessions improve short-session prediction, but lose to persistence on the one-minute panel (absolute log error 0.181 vs 0.161). Adding the current cap gives no consistent improvement. Nominal 0.25 is clipped in 67–76% of recorded epochs, and the range data never change nominal ratio within a session, so a predictive fit is not state-conditioned causal action value. All panels were previously read development data; no encoder model, calibrated safety probability or controller is evaluated. Models, numerical prediction replay and provenance are under `reports/bwe-dynamics-diagnostic-v1/`. Raw encoder/sender histories are needed for the next modelling step.

The planner, a capture path that computes no outcome statistic, the sealed interim and the final analysis are hash-frozen (`configs/native_actuator_qualification_n1_freeze.json`) and were not changed for the run.

```sh
uv run --frozen media-actuator-qualification show
uv run --frozen media-actuator-qualification verify-freeze
uv run --frozen media-actuator-qualification dry-run --out results/my-n1-dry-run   # mock rows only
make native-n1-evidence   # paper macros and tables from the registered final report
```

## Powered causal actuator panel (diagnostic only)

`media-actuator-panel` adds frozen preintervention low/medium/high content strata,
four controlled network schedules and fresh repeated peers, keeping the original
three residuals and all controller architectures unchanged. First-stage strength,
content/regime interactions and factual QoE sensitivity use source/title/capture-clustered,
independent-role replication gates. An optional actuator-validity predictor is
**not fitted**; no safety gate or policy is promoted.

The 13 unused windows are **one previously used title**, not 13 independent units.
The corrected inventory has **zero eligible fresh source clusters**; the prospective
target is **96 independent licensed source/capture units**. Collection is blocked,
not a negative actuator result. `media-panel-assets` validates per-asset rights and
lineage; 31 controller/model/physical-actuator source files are hash-frozen.
See [powered-panel methods, assumptions and commands](docs/NATIVE_ACTUATOR_POWERED_PANEL_V1.md).
The [text-only acquisition audit](docs/NATIVE_PANEL_ACQUISITION_AUDIT_V1.md)
records actual candidates, license snapshots, provisional clusters and storage
bounds without media downloads or changes to the frozen controllers.
The [Commons/Blender Discovery V2](docs/NATIVE_PANEL_ACQUISITION_DISCOVERY_V2.md)
adds per-file rights/provenance snapshots, conservative independent-cluster
counts and a sealed original-capture reserve matrix. Its 110 fresh metadata
candidate clusters are **not** 110 verified eligible units; eligibility remains zero.

## What is included

- 42 joint actions: seven bitrates × three FEC levels × normal/low-latency media mode.
- Seeded causal `fluid_v1` (legacy default) plus opt-in `packet_v2`: paced/VBR media packets, headers, competing UDP traffic, shared FIFO/drop-tail service, actual frame delivery/deadlines/FEC accounting and propagation-delayed reports.
- Heuristic, GCC-**like**, conservative safe, identical ungated RL, calibrated RL, four inference-time ablations, and a separate top-five calibrated action-screen candidate; no-FEC and temperature-scaling retraining sweeps.
- Disjoint training, safety-fit, calibration and test seed namespaces; identical test traces across all methods/model seeds.
- QoE, virtual latency tails, loss, deadlines, stability, calibration (ECE/Brier/NLL), selective risk, OOD support AUROC, fallback reasons/duration/harm/prevention, recovery and censoring.
- Raw compressed step logs; checkpoints; resolved configs; source snapshots and artifact hashes; inference-time diagnostics; paired seed-cluster bootstrap contrasts; CSV/LaTeX tables; PDF/PNG figures.
- Unit/integration/regression tests, reproducibility replay, CI, research notes and an academic paper scaffold.

## Commands

```sh
uv run media-rl train --config configs/demo.json --out results/models
uv run media-rl evaluate --config configs/demo.json --models results/models --out results/evaluation
uv run media-rl report --run results/evaluation
uv run media-rl sweep --kind thresholds --config configs/demo.json --models results/models --out results/thresholds --no-plots
uv run media-rl sweep --kind ablations --config configs/demo.json --out results/ablations --no-plots
uv run media-rl trace --scenario collapse --seed 42 --steps 600 --out results/collapse.npz
uv run media-rl --help
```

`--no-plots` retains tables and diagnostics. Physical/action-space changes require retraining. Checkpoints are inference artifacts, not training-resume snapshots. Trace export supports deterministic inspection; `load_trace` is the Python API for replaying NPZ traces, including validated custom `Trace` instances.

## Start reading

| Path | Purpose |
|---|---|
| `GOAL.md` | Objective, boundaries, verification and optional Modal permission |
| `docs/methodology.md` | Equations, confidence semantics, simulator/controller assumptions |
| `docs/experiments.md` | Protocol, scenarios, ablations, metrics and artifact map |
| `docs/acceptance.md` | Acceptance checks and verification evidence |
| `research/RELATED_WORK.md` | Sources actually consulted and design implications |
| `research/references.bib` | Primary-source bibliography |
| `paper/main.tex` | Nine audited synthetic studies, including V8/V9 rejection and matched confidence ablations |
| `src/media_rl/` | Simulator, learning, calibration, controllers, metrics, CLI |
| `tests/` | Behavioral, scientific-correctness and integration tests |

## Fresh native deployment candidate — negative development result

A separate audited **6 training + 2 calibration** Chrome/VP8 exploration panel covers all seven supported zero-target caps. Fresh native conservative RLCD fits **543/180 transitions** from **1,703/567 factual source requests**, without legacy weights or receiver/proxy oracle inputs. Portable JS/Python inference agrees within **3.6e-15**; offline calibration is not policy performance. The frozen candidate subsequently ran in **6 learned + 12 matched conventional** development episodes. It loses **2.51 timing-weighted PSNR units / 11.97 on-time percentage points** versus the BWE control despite first-phase quality gains; **not promoted**. See [`docs/NATIVE_DEVELOPMENT_V1.md`](docs/NATIVE_DEVELOPMENT_V1.md) and the [training provenance](docs/NATIVE_TRAINING_V1.md). The subsequent [screened cadence live study](docs/NATIVE_CADENCE_V2.md) executes 18 fresh runs and 29 actual holds, but harms both steady-link cases and remains 1.68 utility / 7.66 on-time pp behind BWE—**not adopted**. V7 remains selected.

## Fresh mixed-native data — steady gain, transient loss

The [mixed-dwell/BWE data revision](docs/NATIVE_MIXED_V3.md) completes **12 fresh train + four calibration** 30-second native episodes and **18 separate old/new/BWE development runs**. Fresh same-recipe weights retain all risk screens. Known-cap ages ≥1 second grow from **6.59% to 44.31%**. The candidate gains **9.19 utility versus old RLCD** and **10.99 versus BWE** on both steady cases, but loses **1.72 aggregate utility versus old RLCD** and **7.94 on-time pp versus BWE**, with severe collapse/variable losses—**not adopted**. Independent dual-model/raw/source replay verifies 486 live artifact hashes and 517 unchanged before/after hashes. The **38-page** paper preserves all gains/losses; V7 remains selected and SOTA unachieved.

## Temporal native credit V4 — aggregate gain, nominal loss

The [single n=3→20 actor ablation](docs/NATIVE_TEMPORAL_V4.md) reuses exactly the verified V3 fitting data, with **bit-identical risk weights/Platt/cutoffs**, and completes **18 new n=3/n=20/BWE native peers**. Aggregate utility gains **4.09 versus V3 / 2.60 versus BWE**; variable-link utility gains **13.15 versus V3**. But both steady cases regress (**−5.36 utility**) and one collapse case loses **13.37 utility versus BWE**—**not adopted**. Full read-only replay checks 486 child/518 before-after hashes. The updated **38-page** PDF preserves all trade-offs; **127 generated hashes** pass. V7 remains selected, SOTA unachieved.

## Causal context V5 — failed control and repeatability warning

[One frozen sender-only switch](docs/NATIVE_CONTEXT_V5.md) between unchanged n=3/n=20 actors completes **32 actual peers**, adding one-second collapses without phase inputs. It loses **1.896 utility versus short / 1.818 versus long / 1.795 versus BWE**—**not adopted**. Steady mean improves versus long, but one nominal group selects long; two groups never switch and still show substantial separate-run differences, so gains are not causal switching evidence. Full replay verifies **928 child / 977 immutable hashes**. Current paper: **40 pages / 17 references**, every case and timing/ambiguity limit retained, **132 generated hashes** checked. Follow-up: [prospective repeated controls and selected native calibration](docs/NATIVE_RELIABILITY_V1.md); V7 selected, SOTA unachieved.

## Native reliability/calibration — audited workflow, no promotion

The [portable native pipeline](docs/NATIVE_RELIABILITY_V1.md) adds frozen role/source/model/workload plans, complete raw wire/frame/policy replay, group-cluster comparisons, common shadow inference, selected-action calibration, and strict cleanup-only resume without replacing outcomes. **68 new Chrome/VP8 runs** complete: **12 repeated controls + eight separate calibration + 48 untouched validation**. The refit changes only Platt parameters. It gains **0.984 utility versus unchanged V3** but its interval crosses zero, and trails BWE by **1.943 utility / 14.704 on-time pp**, especially on variable links. The frozen gate **rejects** it; canonical models/V7 selection remain unchanged. Native safety/SOTA remain unachieved.

## Recorded-media source — repeatability gate still fails

The [recorded-video extension](docs/NATIVE_RECORDED_V1.md) adds hashed licensed local films, disjoint clip reservations, pre-capture RGB references and immutable native replay without changing sender inputs or risk gates. **24 actual Tears of Steel/Chrome/VP8 runs** complete. RLCD averages **48–54% on-time versus BWE's 87.26%**; identical-policy brief-collapse runs span **16.46 utility / 60.97 on-time pp**, and two inference tails exceed 10 ms. The gate fails; no model is promoted or labels reused for fitting. One live-action/VFX film is not a representative corpus.

## Native controller repair — efficacy still unverified

The [versioned repair path](docs/NATIVE_REPAIR_V2.md) adds seconds-long causal history, transported presentation ACKs, BWE-bounded/dwell control, a stricter supported risk screen, three-seed delayed-credit training, fresh selected-controller calibration, streamed sources and isolated warmup. Eight smoke captures and 96 additional role-disjoint Chrome/VP8 exploration captures complete; a three-seed repair model is now fitted and its actual weights pass 120-step Python/JS parity. **The calibrated V2 controller is rejected before validation:** its 24 fresh controls pass repeatability but deliver 55.8% on-time versus BWE's 81.3%, with zero eligible learned actions in 1,348 actual decisions. The [separate V3 recipe](docs/NATIVE_REPAIR_V3.md) fixes fallback identity and adds causal sender-content features and per-action risk heads; eight untouched native smoke peers now pass full immutable replay (metadata-only recovery after an outer timeout, no recollection); the fitted V3 model is also rejected after selected calibration (zero useful departures in 682 decisions). The [separate V4 GCC-deferring path](docs/NATIVE_REPAIR_V4.md) preserves neural risk/BWE/use gates, keeps the old BWE comparison and adds native-GCC superiority checks; its ten-peer raw audit passes but unlimited GCC fallback is rejected (9.6% on-time versus BWE's 80.9% on that matched diagnostic). The [independent V5 repair](docs/NATIVE_REPAIR_V5.md) restores conservative fallback, requires fixed-framerate preference readback, expires the RTT baseline and implements normalized factual IQL with fresh two-movie fitting roles. All twelve new diagnostic peers pass full immutable replay and actual encoder readback; fixed-600 reaches 91.5% on-time versus matched BWE 85.7% on one group. Both fresh 96-peer two-film/four-family training and calibration panels pass full raw replay with all seven factual actions; the real three-seed checkpoint passes 160-step actual-weight Python/JS and isolated-package parity. Fresh selected calibration rejects the checkpoint: only 2/680 genuine executed decisions (0.29%), then all actions are risk-vetoed. A separate [scalar-control mechanism probe](docs/NATIVE_DENSE_PROBE.md) now tests the quantization/BWE dead zone against continuous 85%-BWE; it is not a learned model. Eight diagnostic peers now complete and raw-replay. A separate [bounded action-outcome candidate](docs/NATIVE_ACTION_MODEL_V1.md) implements causal scalar histories and exact-cap/context calibration; its new neural fit and group-held-out skill checks use only legal train/calibration parents, not diagnostic or selected labels. A separate [legal exact-cap coverage pipeline](docs/NATIVE_ACTION_COVERAGE_V1.md) adds the missing 400/450/500-kb/s factual collection path while preserving source roles, physical-group counting and every original gate. All 96 exact-cap augmentation peers and the separate V2 refit now complete: missing finer-cap factual support is removed, but no native gain is established. V2's recorded-input probe yields **9.14% shadow departure intents**, not executed learned actions. An [isolated live action-outcome probe](docs/NATIVE_ACTION_LIVE_V1.md) adds frozen learned aliases, legacy/continuous-BWE controls and complete raw audit; its first 16-peer/two-group actual comparison now completes and fully raw-replays, with **78/1,358 genuine learned decisions (5.74%)** and zero learned-budget/tail failures. **Repeatability fails** (stable-alias span 14.50 utility / 63.22 on-time pp), and aggregate quality is worse versus legacy BWE despite positive descriptive contrasts with continuous BWE. Stable executes no learned departures; read-only diagnosis identifies a fallback/buffering/deadline-control hypothesis, not a proven neural gain. Native selected-policy calibration, qualification and SOTA remain open. No V5 checkpoint is promoted. Original checkpoints and failed outcomes remain unchanged.

A [separate fallback-growth-hold comparison](docs/NATIVE_ACTION_GUARD_V1.md) completes and raw-replays **24 fresh Sintel peers / 12,988 requests**, preserving all **1,002 saved files**. It executes 1,007 held-growth fallback steps with zero neural credit; genuine use and timing pass, but **both guarded/unchanged mappings fail collapse repeatability**, and the guard loses to unchanged V2 and both BWE references. All negative phases are retained. **The guard is not adopted; native deadline instability, selected calibration and SOTA remain unresolved.**

[Causal identified-readback transport](docs/NATIVE_PRESENTATION_V1.md) now supplies a separately logged sender sidecar without changing the trained ACK-age feature or policy. Eight new native peers actually transport 1,200 readback packets and pass public raw replay; 368 saved files remain unchanged. This fixes wire observability only, **not** a proven deadline/controller gain, selected calibration or SOTA.

A [train-only action-value qualification check](docs/NATIVE_ACTION_VALUE_SKILL_V1.md) finds a learning blocker hidden by the original action-average-prior proxy: on **24,335 factual training rows**, proposed action adds only **+0.7437% / -0.3649%** utility skill over an identically trained state-only control, failing the unchanged 1% requirement in both physical folds. **98.0851%** of factual actions equal the previous cap already in state. An independently recomputed, externally receipt-pinned **opt-in** actor interface rejects actual V2 before initialization; 32 new invariants, 57 adjacent checks and actual extracted-wheel rejection pass. Old weights, defaults and native outcomes remain unchanged. **The missing qualification check is removed, not the model/data/native-control or SOTA blockers.**

A [separate randomized-hold/credit intervention](docs/NATIVE_ACTION_EXCITATION_V1.md) now completes **48 train-only Chrome/VP8 peers** with **672 uncontaminated cohorts / 8,071 requests**, all three caps and **69.64% changed-action** cohorts. This addresses near-total prior-cap coupling, not a proven encoder/quality effect. The once-only new-data six-conditional/six-blind grouped comparison still fails fixed 1% utility skill (**+0.2274% / -4.4866%**); its original proxy also fails. Complete public raw replay, 1,800 preserved native artifact hashes, saved-weight numerical replay and actual extracted-wheel evidence pass. A separate filename-only read-only auditor repairs replay without changing frozen producer/data. **Learning, causal native control, selected calibration and SOTA remain blocked; no old/default model is changed or promoted.**

A [read-only response diagnosis and compact neural development recipe](docs/NATIVE_ACTION_COMPACT_HOLD_CV_V1.md) identifies 89.75×/133.02× fit-versus-held utility error gaps on those actual cohorts. A separately frozen **786-parameter** model mitigates that generalization defect, lowering held utility MSE **58.7932% / 54.9981%**, with held/fit ratios 1.32×/2.35×. **Action information still fails 1% (−3.3981% / +0.0615%)**, even though the original action-prior proxy becomes green. This is reused-training-fold development, not independent/native/SOTA validation; all twelve forecasts fail the actual native actor ABI. Seventeen response plus eighteen model tests, numeric/extracted-wheel replay and five resealed-forgery rejections pass. Old weights/defaults remain unchanged; actual encoder target/QP response still needs separate measurement.

A [separate native encoder sidecar](docs/NATIVE_ENCODER_RESPONSE_V1.md) removes the previous missing target/QP telemetry: **169/169 actual Chrome samples**, **167 valid same-cap intervals**, one conventional fixed450 train-reservation peer and zero refits. Actual target spans **232.5–450 kbps** under a 450-kbps cap. Full original native/extracted-wheel replay, 19 Python/four Node checks and six resealed-forgery rejections pass. The original actor observation/defaults/models remain unchanged; availability does **not** prove encoder response lag, causal quality gain or SOTA.

A [preregistered four-peer longer-hold test](docs/NATIVE_ENCODER_LONG_HOLD_V1.md) identifies an **asymmetric credit-timing blocker**: observed encoder-target increases take **1.16–1.60 s** (10/14, four censored), versus **101–112 ms** decreases (10/10). The old 200–600-ms window often precedes upward response. Both repeated sequences show later QP evolution; quality variance/confounding still prevents causal-value acceptance. **679 actual samples / 1,494 band requests**, 16 Python/two Node tests, full native/extracted-wheel replay and seven forged-case rejections pass. No model refit or old credit/threshold/default change within that timing probe; the separate prospective repair below now completes.

A [separate prospective 32-step/1800–2200-ms hold/credit repair](docs/NATIVE_ACTION_LATE_CREDIT_V2.md) now supplies **48 actual train-only peers / 160 late factual cohorts / 1,944 requests / eight original physical groups**, retaining all **42 target-unsettled cohorts**. The fixed twelve **786-parameter** neural comparison passes the unchanged **1% conditional-versus-matched-blind development criterion (+1.4258% / +6.8950%)** on the exact old physical folds. Complete native/raw/credit and actual extracted-wheel model/numeric replay, seven resealed-forgery rejections and twelve actual native-actor ABI rejections pass. This is **necessary training-development action information, not independent validation, universally settled targets, selected transient-risk calibration, safe native control or SOTA**. Earlier negative artifacts/models/defaults remain unchanged.

A [new frozen role-disjoint forecast validation](docs/NATIVE_ACTION_LATE_VALIDATION_V3.md) now checks six once-only all-training forecasts against **24 fresh conventional peers / 80 factual late cohorts / 971 requests / four original groups**. The complete 56-input role scanner finds **ToS exhausted**; a wholly new [official CC-BY Blender Big Buck Bunny source](https://peach.blender.org/about/) preserves original credits and remedies that bounded data-access blocker without reusing role footage. **Action information does not replicate: +0.5366% pooled / −2.2405% Sintel / +1.5466% unseen BBB; physical-group interval [−6.7420%, +2.5261%] crosses zero.** Risk is also worse than matched blind despite green prior-proxy skill. Complete original native/public/extracted-wheel replay, seven resealed-forgery rejections and six actual native-ABI rejections pass. **No validation fit/retuning, learned native steps, promotion, selected calibration or SOTA; out-of-training-context value generalization remains blocked.** Old development evidence/models/defaults remain unchanged.

A [training-only diagnosis and separate balanced-assignment pilot](docs/NATIVE_ACTION_BALANCED_HOLD_V1.md) now removes a concrete **local data-exposure gap**: the old two shared-alias repetitions give **0/40 matched group/epoch contexts with all three arms**. The new seed-only three-repetition arm/previous-current-balanced sampler completes **9 genuine native peers / 30 factual cohorts / 365 requests**, **5/5 all-arm contexts / all nine transitions**, retaining all nine target-partial cohorts. **18 Python/3 Node**, full original public/extracted-wheel raw replay, 360 exact Python/JS cases and seven resealed-forgery rejections pass. **No refit, validation-target use, learned native action, causal/generalization/safety/SOTA claim**; one physical-group pilot does not repair the frozen model's failed replication. Original models/defaults/development/validation bytes remain unchanged.

A [prospective multi-context balanced training study](docs/NATIVE_ACTION_BALANCED_MATRIX_V2.md) is **blocked at native peer 17/36**: 16 independently replayed complete peers / 50 partial cohorts / 603 requests, no complete source or model fits. A separately versioned metadata-only adapter repairs actual episode-ID truncation **U103→U109** without changing numeric inputs/folds/recipe; **19 Python checks** and isolated actual partial replay/public no-fit rejection pass. The failed native snapshot summary was not persisted, so its exact stats predicate is unknown. No retries, gate relaxation, partial fitting, new generalization or SOTA claim; old weights/evidence/defaults remain fixed.

[Native before-rejection evidence is now preserved](docs/NATIVE_FAILURE_EVIDENCE_V3.md) without weakening original validity gates. Atomic host-side ledger/count/gzip capture fixes a real four-event diagnostic observer effect; read-only role metadata repair keeps diagnostic cohorts out of training. **23 Python / 15 Node**, one actual corrected native diagnosis (**3 snapshots / 5 diagnostic cohorts / 60 requests / 39,596 events**), full original raw/quality/encoder installed-wheel replay, seven source-aware resealed forgeries and diagnostic-as-training rejection pass. Original failed panel/validation/models remain unchanged; this is observability, **not generalization/native improvement/SOTA**.

A [fresh atomic four-context balanced training study](docs/NATIVE_ACTION_ATOMIC_MATRIX_V4.md) now completes **36 conventional peers / 120 cohorts / 1,456 requests**, all-arm exposure in **20/20 strata** and all nine transitions per group, outside **65 earlier role inputs**. The once-only unchanged twelve-forecaster comparison uses **280 rows / 3,400 requests / 12 groups**. **Action information still fails: −1.07788% pooled; group interval [−5.61132%, +2.18487%]; both folds are negative.** **19 Python / four Node**, actual full native/numeric/extracted-wheel replay, fourteen executing-source hashes, sixteen resealed semantic rejections and twelve native-actor ABI rejections pass. No old model/default/validation change, tuning, native promotion or SOTA; completed balanced exposure is not sufficient evidence of generalization.

A [training-only diagnosis of the fixed negative models](docs/NATIVE_ACTION_ATOMIC_DIAGNOSIS_V2.md) now attributes the net error gap mainly to ToS, rules out dead hidden units, and verifies alias/encoder/gradient/sampling variability. A separate **opt-in ordered32-step projection** removes provable summary-order invariance while preserving old92 features/state/actions; **no model was fitted in that diagnosis phase or default changed**. Actual full/current/ordered inputs have the same26 duplicate pairs, so no real collision or performance improvement is claimed. **17 Python checks**, isolated actual12-model replay andeight semantic reseal rejections pass; action generalization/native/SOTA remain blocked.

A [single predeclared ordered-history training ablation](docs/NATIVE_ACTION_ORDERED_VALUE_CV_V1.md) is now complete: twelve new 118-input auxiliary models preserve original initialization/minibatch RNG, data/folds/recipe and matched blind controls. Pooled action skill changes **−1.08% → +1.31%**, but **the full gate still fails**: Sintel misses action/prior thresholds and the group interval **[−4.13%, +7.98%]** crosses zero; new-only conditional MSE also worsens. **15 targeted Python cases**, full deterministic twelve-model training replay, isolated-wheel replay and ten fully resealed semantic rejections pass. Original models/roles/defaults remain intact; no native deployment or SOTA claim. This experiment is closed; no further experiment is started.

## Published RTC peers — original checkpoints, offline replay only

The [pinned published-peer interface](docs/PUBLISHED_RTC_PEERS_V1.md) now runs the original **Schaferct MMSys 2024 winner** and organizer ONNX baseline locally. **4,148 public observation rows** match the original reference feed/channel exactly, pass read-only audit and remain invariant to poisoned capacity/quality labels. Native 64-input histories are rejected rather than padded. Optional `rtc-peers` installs the locked CPU runtime; `rtc-peer-list`, `rtc-peer-inspect`, `rtc-peer-replay` and `rtc-peer-audit` are public CLI commands. **This is not closed-loop QoE evidence or a SOTA claim**: compatible receiver features and transport/encoder actuation remain unverified.

## Verified local evidence

The current implementation passes **661 Python tests** and **117 native Node tests**. Completed evidence includes the **10-seed v1 scale-up (19,800 episodes / 11.88 million intervals)**, v2 safety refit, v3 threshold selection (5,500 validation and **7,700 fresh-test episodes**), v4 policy randomization (**7,700 validation plus 7,700 fresh-test episodes**), v5 action screening (**2,200 validation plus 8,800 fresh-test episodes**) and v6 selected-action recalibration (**40 ID calibration episodes per source seed, 2,200 validation and 8,800 fresh-test episodes**). V2–v4 candidates retained v1; v5 and v6 validation selected their screen variants. See [`docs/verification.md`](docs/verification.md), [`docs/IMPROVEMENT_V2.md`](docs/IMPROVEMENT_V2.md), [`docs/THRESHOLD_SELECTION_V3.md`](docs/THRESHOLD_SELECTION_V3.md), [`docs/POLICY_RANDOMIZATION_V4.md`](docs/POLICY_RANDOMIZATION_V4.md), [`docs/SAFETY_SHIELD_V5.md`](docs/SAFETY_SHIELD_V5.md), [`docs/ACTION_CALIBRATION_V6.md`](docs/ACTION_CALIBRATION_V6.md), and the stage reports.

**Measured outcome:** relative to matched calibrated v1, the v5 screen improved ID QoE by 0.0259 (95% model-seed interval [0.0135, 0.0387]) and reduced ID violation rate by 0.00144 on the fixed synthetic panel. OOD QoE and violation effects were inconclusive; GCC-like and heuristic baselines still offer better ID tradeoffs. V2–v4 candidate outcomes remain negative or unpromoted. The original v1 weights/gate remain the learned reference, while v5 adds a validation-selected action-screen variant. All findings are synthetic; the screen is not a safety guarantee. Do not use the final traces for further tuning.

**V6 measured outcome:** recalibrating on screen-selected ID actions while freezing policy/safety weights was promoted on validation. On its disjoint 8,800-episode synthetic test, the recalibrated screen improved ID QoE by 0.022 [0.009, 0.036] and reduced ID violations by 0.050 percentage points [0.007, 0.100] versus v1. Stress/OOD QoE improved, but its violation interval includes zero. OOD selected-action confidence remains 5.09 points optimistic [4.51, 5.71]; this is not an OOD safety guarantee.

- **V7 audited result:** validation promoted `shielded_uncertainty` by a narrow score gain of 0.005073. The 8,800-episode fresh panel found negligible ID effects and a small OOD violation change of -0.083 percentage points (10-seed interval [-0.209, -0.0005]); the cutoff activated on just 0.24% of stress steps. This conditional result does not close the GCC-like OOD gap or establish a safety guarantee. Audited outputs: `results/uncertainty-shield-v7/final-campaign/test` and `paper/generated-uncertainty-shield-v7/`.

**V8 audited outcome: not promoted.** The 1,100-validation / 8,800-test episode wire-budget study keeps all ten V6-derived bundles unchanged. Validation rejects its 0.0946 ID-QoE drop (limit 0.03). On the fresh panel, stress violations fall 2.862 percentage points [1.986, 3.724 reduction], but ID/stress QoE falls 0.104/0.133; confidence eligibility adds no resolved violation benefit over the matched budget-only ablation. V7 remains the locked choice. See [`docs/BUDGET_SHIELD_V8.md`](docs/BUDGET_SHIELD_V8.md), `results/budget-shield-v8/test` and `paper/generated-budget-shield-v8/`. All intervals condition on the fixed synthetic panel.

**V9 audited outcome: partial repair, not promoted.** The delay-evidence budget/fallback variant completes 1,650 validation and 9,900 fresh-test episodes with unchanged models. Compared with V8 on this new panel, burst-loss QoE recovers **1.160** with unchanged observed violations, but ID quality still fails validation (0.1109 drop; limit 0.03), so V7 remains selected. Confidence eligibility adds a small conditional stress-risk regression versus the matched ablation. Protocol, exact effects and limitations: [`docs/DELAY_BUDGET_V9.md`](docs/DELAY_BUDGET_V9.md).

## Realistic transport and model retraining (V10)

```sh
# Choose a fresh output directory; the completed canonical study is immutable.
uv run --frozen media-rl realism-study --config configs/realism_v10.json --out results/realism-v10-reproduction --no-plots
```

The completed **three-seed / 1,188 fresh-test episode** study adds a causal 16-feature history policy, GCC-only demonstrations, broader stress data and deadline-resolved capture-cohort safety labels. Compared with matched retrained RLCD on the same packet physics, nominal QoE gains **0.1395** and nominal/stress unsafe frequency drops **8.623/7.030 pp**. GCC-like still leads quality; validation **rejects** the candidate because stress-quality gain misses the frozen bound. Test data does not override that choice. `fluid_v1`, old model behavior, V7 selection and the nine-study PDF remain unchanged.

Details and remaining realism/conventional gaps: [docs/REALISM_V10.md](docs/REALISM_V10.md). Canonical numerical results: `results/realism-v10/results.json`; independent all-row/statistic/replay/provenance receipt: `results/jobs/realism-v10-evidence-check.json`. Extra demonstration compute, bundled changes, trained stress families and synthetic codec/FEC/quality proxies limit the claim.

## Continuing competitiveness work (V11)

Opt-in `training.n_step` supports delayed-return credit while **n=1 remains bit-exact and the default**. The completed five-seed study (`configs/n_step_v11.json`) covers **1,320 validation + 1,980 fresh-test episodes** with equal TD/demo budgets. Validation **rejects n=3**; gated fresh-test effects are inconclusive, and GCC-like still leads quality. All **792,000 rows**, ten models, twenty intervals and historical artifact preservation are independently audited.

Details: [docs/DELAYED_CREDIT_V11.md](docs/DELAYED_CREDIT_V11.md). Independent real-codec burst/quality and inference diagnostics are recorded separately—not substituted for genuine RTC/SOTA evidence. The active evidence checklist and next development intervention are in [docs/SOTA_TRACK.md](docs/SOTA_TRACK.md).

## Paper and model refinement

```sh
# Audited nine-study tables, figures and PDF
make paper
# Reproduce/reuse hash-audited completed studies under identical settings/code
uv run media-rl improve --config configs/improve_v2.json \
  --models results/paper-v1 --out results/improvement-v2
uv run media-rl tune-threshold --config configs/threshold_select_v3.json \
  --models results/paper-v1 --out results/threshold-selection-v3
# Frozen v4 domain-randomized policy training; validation locks promotion before fresh test
uv run media-rl policy-randomization --config configs/policy_randomization_v4.json \
  --models results/paper-v1 --out results/policy-randomization-v4
uv run media-rl audit --run results/policy-randomization-v4/test
# V5 action-level screen; validation lock precedes a disjoint fresh test
make safety-shield-v5
uv run media-rl audit --run results/action-shield-v5/test
# V6 one-pass selected-action recalibration (policy/safety weights frozen)
make action-calibration-v6
uv run media-rl audit --run results/action-calibration-v6/final-campaign/test
# V7 complete; the initial partial test is preserved separately
uv run media-rl audit --run results/uncertainty-shield-v7/final-campaign/test
# V8 is complete but rejected; audit preserved test evidence, not a retuned candidate.
uv run media-rl audit --run results/budget-shield-v8/test
# V9 repairs burst-loss quality but still fails the nominal-quality promotion bound.
uv run media-rl audit --run results/delay-budget-v9/test
```

The updated draft is **`paper/build/main.pdf`**, source `paper/main.tex`. Separate evidence directories (`paper/generated-scaleup`, `paper/generated-followup`, `paper/generated-threshold`, `paper/generated-randomization`, `paper/generated-shield`, `paper/generated-action-calibration-v6`, `paper/generated-uncertainty-shield-v7`, `paper/generated-budget-shield-v8`, `paper/generated-delay-budget-v9`) prevent mixing studies; each has a provenance record. The pilot manuscript is archived. See `paper/README.md` for reproduction and remaining submission blockers.

`evaluate` also supports `--split validation` and `--model-map FILE` for explicit per-method checkpoint references (relative paths resolve against the map file). Evaluated runs retain copied references and a portable model map. `improve`, `tune-threshold`, the v4 policy-randomization and v5 safety-shield campaigns hash inputs, lock validation selection before opening test traces, and refuse to reuse partial stages or changed code/settings. The v4/v5/v6 protocols are frozen in [`docs/POLICY_RANDOMIZATION_V4.md`](docs/POLICY_RANDOMIZATION_V4.md), [`docs/SAFETY_SHIELD_V5.md`](docs/SAFETY_SHIELD_V5.md), and [`docs/ACTION_CALIBRATION_V6.md`](docs/ACTION_CALIBRATION_V6.md); all results remain synthetic.

## Interpretation boundaries

A probability of 0.9 means an **estimated next-step constraint-satisfaction probability**, not 90% confidence in optimality or a guarantee of long-horizon safety. Calibration on ID data need not transfer to OOD conditions or the gate-induced state distribution. A conservative fallback cannot repair an outage or create bandwidth. Report all baselines and negative findings; do not assume calibrated RL beats GCC-like control. Synthetic QoE is not MOS/VMAF, latency is a fluid virtual-delay proxy, and FEC is not a codec implementation. Real WebRTC, packet-level emulation, real traces, multi-flow fairness and human perceptual validation are future work.
