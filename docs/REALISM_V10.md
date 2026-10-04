# V10: paced transport and conventional-gap learning

## Contract and evidence boundaries

Opt-in **`packet_v2`**, not a replacement of existing fluid-paper physics. `fluid_v1` remains the default. Old checkpoints/config digests normalize missing optional defaults; nondefault physics/training cannot masquerade as historical hashes. A frozen V9 fluid implementation is tested for exact telemetry, preview and step parity across all eleven families. Canonical V1–V9 directories and the 34-page nine-study PDF are not overwritten.

Commands:

```sh
uv run --frozen media-rl realism-study --config configs/realism_v10.json --out results/realism-v10 --no-plots
# Completed/partial directories cannot be reused; choose a fresh --out for reproduction.
```

## Where the original RLCD is behind

`results/jobs/rlcd-v10-gap-audit.json` reads hash-verified `results/delay-budget-v9/test/episodes.csv`; these are descriptive matched-panel contrasts, not new significance tests. Original RLCD is `calibrated`, distinct from retained V7.

Versus GCC-like on that common fluid panel:

| Family | RLCD QoE minus GCC-like | Unsafe difference (pp) |
|---|---:|---:|
| bufferbloat | -0.573 | +7.697 |
| collapse | -0.468 | +9.595 |
| step | -0.249 | +1.290 |
| ramp | -0.100 | +0.217 |
| capacity surge | -0.180 | 0.000 |

Steady/burst-loss quality is not uniformly worse; do not erase those strengths. Overall nominal RLCD QoE is 2.113 versus GCC-like 2.186; stress unsafe frequency is 10.648% versus 7.590%. GCC-like is a simplified AIMD/delay baseline, **not libwebrtc GCC**.

## Transport changes

`src/media_rl/packet_transport.py` implements:

- timestamped media frames at configurable FPS, variable-size/intra-frame bursts, encoding delay and packet pacing;
- payload packetization and headers; source, parity and header accounting are separate;
- shared finite FIFO/drop-tail service with independently seeded bursty competing UDP load;
- deterministic trace/time/frame/packet-indexed erasures for pure counterfactuals and reproducible replay;
- forward serialization/sojourn and ordered jittered arrival, not instantaneous application delivery;
- actual received source/parity byte accounting with bounded **synthetic** FEC repair and frame deadlines;
- reward/goodput credited from settled cohorts, not the current generated action's hypothetical quality;
- receiver reporting, reverse propagation and configured additional withholding; missing reports retain old telemetry.

Per-step mass checks: `queue_before + offered = total_service + queue_after + overflow`; media and cross service sum to total bottleneck service. Queues stay within the actual limit, including buffer shrink. The controller still sees only `Telemetry`, not capacity, loss cause, frame outcomes or scenario names. Optional NPZ profiles roundtrip and are read-only; unprofiled legacy traces retain their original serialized arrays.

This is higher-fidelity **synthetic transport**, not a real codec, network stack, TCP competition, measured-link fit or full packet-capture replay. FEC byte repair and logarithmic video quality are still proxies. Terminal pending frames are explicitly censored, not claimed successful or imputed from future capacity. RTP/media receivers are abstracted; no RTX, ECN, AQM, real codec dependency or multi-flow fairness claim is made.

[RFC 8868](https://www.rfc-editor.org/rfc/rfc8868.html), especially §§1, 4.1–4.5 and 5, motivates varying delay/queue/loss and competing traffic, measuring post-repair loss/discards, and separately validating real codecs. It does **not** validate these thresholds/proxies or establish RFC test-suite compliance. RFC 8593 is linked by that standard, but direct readable retrieval failed; no claim of implementing its full statistical model is made.

## Learning/data changes

- **History-v2 (16 inputs)** adds feedback-only RTT excess above an observed minimum, ACK/loss/trend EWMAs, ACK deviation and bitrate changes. Freshness inferred from decision time/feedback age prevents repeated stale reports becoming new samples. Encoder state resets per episode.
- **GCC-only demonstrations** have a separate `demonstration` seed namespace. Labels are conventional actions from telemetry only, never preview/reward/oracle labels. Behavior-cloning warm start and continuing large-margin expert regularization complement Double DQN; this is not a faithful DQfD reproduction.
- A predeclared weighted schedule adds collapse/bufferbloat/handover/erasure/outage/feedback-gap/surge training. Risk fitting and calibration receive their own separately seeded declared schedules. Historical `domain=ood` means **stress taxonomy**, not unseen distributions after this training.
- Packet-v2 can fit **new capture-cohort safety** under a fixed candidate continuation through actual deadlines. Three control intervals cover this study's capture/deadline window. Earlier-action frames are excluded from that target, though their backlog can affect the new cohort. Terminal labels are censored and excluded from fitting/reliability. Online execution can change actions; confidence is not a certificate for that alternative continuation.
- Actual per-interval unsafe frequency still measures settled-cohort outcomes. It is not interchangeable with the new confidence target; prevention/harm attribution across those different windows is suppressed.

## Development versus final study

Development panels use model seed 40 / trace ID 17101 (`results/transport-v10-pilot`, `results/transport-v10-cohort-pilot`). These motivated dropping the poor heuristic teacher and correcting stale history/cohort targets. They are development diagnostics, not final evidence, and cannot be counted as independent tests.

`configs/realism_v10.json` freezes three new model seeds (41/52/63), two validation trace IDs (18101/18102) and three fresh test IDs (19101–19103). Both recipes use the **same packet physics, conventional implementations, trace realizations, action space, gate settings and 120-episode online RL budgets**. Candidate has additional 30 demonstration episodes / 20 cloning epochs, changed exploration, history and broader safety data; compute/data volume and mechanisms are **not separately matched/identified**.

Selection considers only RLCD (`calibrated`) validation outcomes: ID QoE drop ≤0.03; ID/stress unsafe increases ≤0.2/0.5 pp; stress QoE gain ≥0.03; score gain >0.01. Implementation/model/validation hashes and UTC lock are saved before any fresh test. Both recipes and all six methods are tested regardless of rejection. Paired intervals use **model-seed means**, never time steps as independent trials. Means/contrasts include ungated policy, both conventional controls and the screening diagnostic; there is no post-test method promotion.

Completed panels: **792 validation episodes**, **1,188 fresh-test episodes**, **285,120 test control intervals**. Existing V7/fluid-paper selection stays untouched even if the new packet recipe is eligible. Three training seeds and known synthetic families cannot establish general superiority, real-network reliability or safety.

## Status

The frozen study completed in **499 seconds** and passes independent verification. **137 tests** and Ruff lint/format pass.

### Validation decision remains rejected

Candidate nominal QoE rises 0.7742 → 0.8774; nominal/stress unsafe frequency falls 19.306% → 10.174% and 30.853% → 24.385%. But stress QoE improves only **0.00536**, below the required **0.03**. The score gain 0.2103 and risk improvements cannot override that bound. `selection.json` locks **`baseline`** before test; the candidate is not promoted after seeing final results. This is a recipe decision for the new simulator, not evidence that V7/fluid-paper performance changed.

### Fresh test: improvements versus the matched retrained baseline

| RLCD metric | Baseline recipe | History/demo/cohort candidate | Candidate-minus-baseline [model-seed interval] |
|---|---:|---:|---:|
| Nominal QoE | 0.6265 | 0.7659 | +0.1395 [0.0378, 0.3334] |
| Nominal unsafe (%) | 19.572 | 10.949 | -8.623 pp [-17.812, -3.889] |
| Stress QoE | 0.0487 | 0.0869 | +0.0382 [-0.0102, 0.1038] |
| Stress unsafe (%) | 31.396 | 24.365 | -7.030 pp [-11.845, -4.226] |

Stress quality remains unresolved at this small three-seed scale. The ungated candidate also improves nominal QoE by **0.7155** and lowers nominal/stress unsafe frequency by **32.535/21.164 pp** versus the matched ungated baseline, so the iteration is not merely replacing every learned action with a different fallback. These effects bundle training/feature/target changes and additional demonstration compute; they do not isolate any single mechanism.

### Where conventional control still wins

GCC-like retains higher nominal/stress QoE: **1.0146/0.3948** versus candidate RLCD **0.7659/0.0869**. Candidate-minus-GCC quality is **-0.2487 [-0.4420,-0.1320]** nominal and **-0.3079 [-0.4913,-0.1961]** stress. Candidate is more conservative: unsafe frequency falls **12.801/8.214 pp** relative to GCC-like. These are quality/risk tradeoffs, not conventional dominance.

The largest remaining quality gaps are capacity surge **-0.897**, burst loss **-0.500**, ramp **-0.382**, steady **-0.290** and feedback gap **-0.251**. Fallback occupancy is roughly **56–76%** in these families; switching is lower than GCC-like, not a demonstrated excess-switch explanation. Descriptive details: `results/jobs/realism-v10-scenario-gaps.json`. A defensible next experiment would target underutilization, probabilistic action selection and feedback-gap recovery on **new training/validation IDs**, without tuning on this test panel or weakening safety bounds post hoc.

### Independent acceptance receipt

`results/jobs/realism-v10-evidence-check.json` verifies **2,058 study artifacts**, **408/420** artifacts in each validation/test recipe run, six checkpoint bundles, 27 executable implementation files, all **475,200 validation+test rows**, and **20 paired estimates**. It checks queue mass/capacity/delivery accounting, identical conventional outcomes and trace bytes, split separation, before-test locking, and **960 exact gated runtime replay steps**. Candidate has 792/1,188 censored validation/test proposal labels (two per episode); these are excluded from fitting/reliability, and terminal frame censoring is reported.

Canonical V8/V9 selections/manifests/raw logs and the existing **34-page / 17-reference nine-study PDF** are unchanged. V10 remains separately documented prototype evidence, not an appended confirmatory paper study. No cloud/GPU job, upload, deployment or submission occurred. Exact means/contrasts: `results/realism-v10/results.json`; protocol/model/source hashes and lock: `results/realism-v10/protocol.json`, `study_manifest.json`, `selection.json`.
