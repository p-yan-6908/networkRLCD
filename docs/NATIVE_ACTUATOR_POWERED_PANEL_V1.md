# Source-clustered causal actuator panel V2

**Controller/model code frozen. Acquisition and panel execution are the critical
path.** The file/command paths retain their V1 names, but the panel protocol is
`native_actuator_source_panel_v2`; earlier clip-clustered V1 plans/screens are
intentionally incompatible, not silently reinterpreted. The original
`media-actuator` smoke and its raw evidence are unchanged.

`configs/native_controller_freeze_v1.json` hashes 31 controller/model/physical
actuator source files. `media-panel-assets verify-freeze` checks this inventory
and its bytes. Acquisition, screening, prospective planning and panel validation
refuse drift. The freeze hash is bound into sealed panel/screen provenance.
No model, actuator-validity predictor or state-action preference model is fitted.
Safety weights, original six controller actions, causal history/telemetry,
1.8-second increase dwell, settled-credit attribution and promotion gates remain
unchanged. Never rewrite the freeze to accommodate another model iteration.

## Correction: files are not independent panel units

The previous statement "13 clips toward 96; acquire 83 more" was incorrect as an
independence claim. Those 13 unused 20-second intervals are from **one previously
used Big Buck Bunny title**. Current inventory reports 13 candidate windows,
**one provisional source group and zero eligible fresh source clusters**. Legacy
catalogs also lack the new explicit per-asset license/title/capture receipts.
The old 5/4/4 excerpt strata do not define three independent source populations.
No powered panel was collected and no negative actuator effect is established.

A cluster is a connected source/title/capture/lineage component:

- Same canonical title, even at a different provider, is one source cluster.
- Shared capture group merges titles from the same session.
- Shared original/media/parent SHA256 merges encodes, remuxes and mirrors.
- Connections are transitive. Different resolutions, files, crops, excerpts,
  render variants and repeated peers do not create new independent units.
- Discovery/replication split whole components, never individual files. Known
  prior-study media or parent hashes exclude the whole source cluster, not only
  overlapping time ranges. Missing/uncertain rights or lineage is quarantined.
- Importer must review original title/capture/generation lineage. The software
  checks evidence consistency; it cannot prove legal authenticity or stochastic
  independence. Unknown shared origin must be grouped conservatively or excluded.

The fixed preset selects **16 independent source units per primary complexity
stratum per role**, three strata, two roles: **96 units**. One representative
20-second window per source unit is selected prospectively, nearest that unit's
median screening complexity. Four regimes and five fresh peers give 1,920 peers
and 11,520 expected factual cohorts, but only 96 inferential source clusters.
More excerpts cannot satisfy a missing source-unit quota.

All support checks, per-arm counts, CR1 sandwich covariance, t/F denominator
degrees of freedom, interaction tests and power inputs use source cluster count.
Within-source excerpt fixed effects are nuisance adjustments, not additional
independent observations. Direct analysis rejects distinct cluster IDs sharing a
title/capture/asset lineage and rejects source-role leakage. This remains valid
if a later prespecified design collects several excerpts per source: extra files
cannot inflate independent N. It is a conservative source-cluster analysis,
not a fitted hierarchical random-effects model.

## Acquisition manifest and rights

`media-panel-assets ingest` accepts explicit local media requests; it does not
perform bulk downloads, infer rights, transcode, loop, pad or stretch content.
`configs/native_panel_asset_request.example.json` is an intentionally invalid
placeholder: rights assertions/review are false until an importer supplies them.
An import emits `asset-0000.json`, etc., the data manifest `assets.json`, and the
separate immutable integrity seal `manifest.json`. Each media/evidence file is
hash-checked and FFprobe measures actual resolution, fps, duration and codec.

The source/screening/plan pipeline records:

```text
clip_id, source, source_title, capture_group, cluster_id, parent_sha256
license, license_url, attribution, license_evidence(path/hash/url/scope/quote/review)
resolution, fps, duration_ms, segment, sha256, source_sha256, sha256_scope
spatial_complexity, temporal_complexity, motion_score, motion_score_method
source_complexity_score, content_stratum, panel_split
```

A virtual window's `sha256` is the referenced **source media file** hash, not a
claim that an unmaterialized excerpt file has separate bytes. `clip_id` binds that
hash and exact interval; raw frame/encoder attribution is replayed later.

Primary-panel permissions allow explicit **CC BY 4.0, CC BY 3.0 or CC0 1.0**.
NC, ND, unknown rights and collection-wide assumptions are rejected. Evidence
must be an accompanying readme or rights-page snapshot whose hash, exact binding
quote, asset title and license marker are verified; the importer explicitly
reviews applicability to this asset. Record required owner attribution. Synthetic
assets require explicit component ownership/permission and generation provenance;
self-generation alone does not establish a license for imported meshes/textures.

### Official sources checked (2026-10-05 UTC)

`configs/native_panel_acquisition_sources_v1.json` is an acquisition queue, **not
an acquired corpus**. It reports zero newly acquired units and no download budget.

- [UVG-VCM](https://ultravideo.fi/UVG-VCM/index.html): official page lists 20 sequences
  under CC BY 4.0, mostly 4K/60. Verify asset membership and capture-session
  relationships; "20 sequences" is not automatically 20 independent captures.
- [Netflix Open Content](https://opencontent.netflix.com/home): official page
  states CC BY 4.0. Candidate titles include Nocturne, Sparks, Meridian, Chimera
  and El Fuente. All encodes/excerpts of a title remain one cluster; review shared
  sessions between titles. Save applicable per-asset rights evidence.
- [Xiph Derf](https://media.xiph.org/video/derf/): inspect each accompanying readme
  and license. Never infer blanket permissions or count mirrors as new sources.
- [Original UVG](https://ultravideo.fi/dataset.html): official page specifies
  noncommercial BY-NC; excluded from the commercially usable primary corpus.
- Procedural Blender scenes are a useful **component**, not the whole panel.
  Independently generate scene layout, texture, camera/object motion and preserve
  scene/component/seed/render provenance. Variants of one scene/capture are one
  unit. A renderer and representative synthetic corpus are not implemented here;
  no fabricated generation, ownership or acquisition is claimed.

**Native format/duration limitation:** frozen recorded-source/catalog machinery
requires browser H.264 and the current design takes a real 20-second window after
60 seconds of excluded opening footage. Thus this preset needs >=80 seconds of
source media. Short/uncompressed codec-test sequences can be inventoried by the
importer but are marked not native-ready. Do not repeat/pad short sequences to
manufacture eligibility or independence. A future explicitly reviewed media-only
adapter may be needed; it must not change controller/sampler/credit semantics.

## Screening, ordered inference and execution

Owned, preassignment FFmpeg center-crop samples at 5 fps, gray 40x20, provide a
normalized spatial-neighbor gradient and temporal absolute-change proxy. The
score averages these. `motion_score` explicitly labels the temporal-change proxy,
not optical flow or ITU SI/TI. Source medians contribute **one vote per cluster**
to frozen low/medium/high terciles. Long titles do not dominate cutpoints via file
count. Screening is source-balanced; all windows of a source receive its primary
stratum. No QP/actual bitrate/QoE outcome defines the strata.

Keep IID instruments **{0.65, 0.85, 1.05} x frozen BWE**, known 1/3 propensities,
six 3-second holds per fresh native peer and the original encoded-payload/RTP byte
meters. IID labels do not promise exactly balanced action counts. Zero-output,
aliased and non-plateau windows remain factual; clock/outcome missingness is
explicit. A 3-second hold does not prove physical steady state.

1. **Z→A:** action-separated actual encoded/send distributions, pairwise effects
   and Delta A / Delta Z with multiplicity-adjusted CIs, source-cluster F and
   partial R². Both independent roles must clear existing rate/separation/safety
   gates; at least eight source clusters per cell/role and per arm. Failure is
   inconclusive unless simultaneous contrasts establish effects inside the
   predeclared ±0.03 BWE equivalence margin.
2. **A→QoE:** only after a cell's encoded AND send first stages replicate, report
   factual randomized-action ITT contrasts with corrected CIs and the 1 dB
   practical-effect gate. Scalar-rate 2SLS/weak-IV-robust Anderson–Rubin sets also
   report sensitivity for a 20% actual-rate change. Exclusion, monotonicity,
   carryover/interference and linear/common effect assumptions are unverified;
   default configuration does not assert actual-rate causal identification.
   QoE is on-time sampled RGB-PSNR contribution, not perceptual QoE.
3. **s×a→QoE:** deferred to a separately prespecified analysis after the first
   two gates. Current content/regime interaction tests concern Z→actual bitrate,
   not state-conditioned QoE preference. No state-action preference or policy is
   fitted. Returning to RLCD requires that later evidence; nothing is promoted.

Regime high/collapse/recovery capacities (Mbps) remain 4/4/4, 0.85/0.85/0.85,
1.2/0.6/0.6 and 1.2/0.35/1.2 for underutilized, near-capacity, queue-building and
collapse-recovery respectively; durations are 6/6/6.6 seconds. These labels are
configured, not guaranteed realized. Original FIFO replay and capacity/queue/drop
summaries are **peer-scoped**; no relay/browser clock transform is invented.
Full factorial collection is required to qualify. Prefix flags are explicitly
false; failures preserve evidence and require fresh output paths. `audit` replays
original assignments, raw frames, actual encoded bytes, wire events and reports.
No unobserved action is labelled or imputed.

## Power and blinded re-estimation

96 is based on **assumed nuisance variance**, not measured representative source
variance. The source-unit power simulation uses adjacent normalized effect .15,
source random-slope SD .10, peer/cohort noise SD .08/.08 and the original criteria.
It reports Wilson Monte Carlo uncertainty and independent-role detection, with
156 reserved rate comparisons. The 16-source projection passed under those
assumptions; this is single-cell encoded first-stage power, not empirical evidence,
send/outcome power or guaranteed joint all-cell power. Reinterpreting the assumed
SD as source-level variance does not make it measured or representative.

A blinded nuisance-variance sample-size review is a defensible future option, but
**not enabled**. Before any tranche outcomes, preregister source-level tranche,
estimator, blinding/access firewall, min/max N, one adaptation rule and sequential
error-control review. Suppressing action columns alone is not a validated blinded
estimator (pooled variance may include treatment effects). Do not conveniently
reduce N because acquisition is difficult or use observed contrasts to resize it.
The registry preserves 96 pending such a justified, independently reviewed plan.

## Commands and verification

```sh
uv run --frozen media-panel-assets verify-freeze
uv run --frozen media-panel-assets ingest --request /path/reviewed-request.json --out results/my-assets
uv run --frozen media-actuator-panel inventory --catalog results/my-assets/asset-0000.json --out results/my-inventory.json
uv run --frozen media-actuator-panel screen --catalog results/my-assets/asset-0000.json --limit 120 --out results/my-screen
uv run --frozen media-actuator-panel power --config configs/native_actuator_powered_panel_v1.json --out results/my-power.json
uv run --frozen media-actuator-panel plan --config configs/native_actuator_powered_panel_v1.json --screen results/my-screen/screen.json --out results/my-plan
uv run --frozen media-actuator-panel run --protocol results/my-plan/protocol.json --out results/my-panel
uv run --frozen media-actuator-panel audit --root results/my-panel
```

Repeat `--catalog` for the complete reviewed pool. Six independent source clusters
are needed even to screen terciles; ties/stratum shortages block planning. The
current corpus has zero eligible fresh units, so no new screen/plan/panel can
qualify. Provide fresh source/capture provenance, real rights snapshots and an
explicit download/storage budget before large-media acquisition.

Verification: **99 focused tests** (asset/panel/original actuator/JevBWE/RLCD),
lint/format and 31-file controller freeze passed. Tests explicitly reject 96
same-title excerpts as 96 units, shared-session/lineage aliases, source-role
leakage and NC/ND/unknown rights. Runner/audit fixtures use real original scheduling
but capture/auditor test doubles; they are not powered native evidence. Original
four-peer/24-cohort smoke remains inconclusive and retains all windows (13 were
non-plateau). Final inventory is `results/native-source-panel-inventory-v2.json`;
source-unit power sensitivity is `results/native-source-panel-power-v2.json`.
Generated evidence is local/untracked. Learned promotion still requires replay/
control QoE to significantly beat fallback-only with every safety constraint met.
