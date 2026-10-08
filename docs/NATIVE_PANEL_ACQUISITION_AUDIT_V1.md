# Powered-panel acquisition audit v1 — metadata only

**A rights-clean, independently verified 96-unit native panel is not yet established.** No media was downloaded, no generator or native panel was run, no treatment outcome was observed, and no controller was trained/promoted. All **31 frozen file hashes** remain unchanged.

## Protocol and artifacts

Protocol: `configs/native_panel_acquisition_audit_v1.json`. This is a repository collection protocol before media acquisition, not a claim of external registry preregistration. Source discovery refined the metadata allowlist without changing N, independence, source duration, controller hashes or outcome analysis. N remains **96**, based on assumed nuisance variance; blinded sample-size re-estimation remains disabled.

Final package: `results/native-panel-acquisition-audit-v1-final/`:

- `inventory.json`: **156 candidate rows**, including alternative representations, exact known/unknown metadata and rights evidence references.
- `inventory.csv`: one row per candidate with requested identity/license/hash/origin/split fields and eligibility blockers.
- `evidence.json` + `evidence/`: preserved original HTTP bodies/small rights PDFs, retrieval times, source/final URLs, sizes and SHA256. PDF readable views are regenerated from verified originals during replay.
- `protocol.json` + `report.json`: contract and auditor/protocol/freeze hashes, source contributions, storage bounds and deficits.

Evidence date: **2026-10-05 UTC**. Collection/retries made 104 logical metadata GET attempts; 93 distinct receipts were preserved and one distinct URL remains unresolved. Metadata response bodies read total **3,109,884 bytes**. Seed receipts were reused; final replay added zero HTTP requests. HTTP headers/redirect overhead are not a measured bandwidth total.

Original/normalized media SHA256, capture identity, measured complexity and network-panel split are **null**, not fabricated or substituted with page hashes. These are audit candidates, not ready ingest requests.

Safety boundaries: no media-download implementation; media extensions, unapproved hosts/schemes/ports, embedded credentials, unsafe redirects, non-text responses and oversized metadata are rejected. Explicit small rights PDFs are the only allowed binary evidence. Caps: 2 MiB/response, 16 MiB cumulative response bodies, 256 logical metadata requests. `--offline` refuses unseeded URLs.

## Source contributions

| Source | Enumerated | Rights-cleared title candidates | Fresh title upper bound | Verified native units |
|---|---:|---:|---:|---:|
| UVG-VCM | 20 sequences / 22 raw views | 20 | 20 | 0 |
| Netflix Open Content | 7 titles | 7 | 7 | 0 |
| Xiph Derf | 113 catalog rows with Y4M downloads | 1 (Sintel) | 0 | 0 |
| Original UVG, separate restricted class | 16 sequences | 0 | 0 | 0 |

There are **28 rights-cleared title candidates overall, 27 fresh**, not 27 verified independent captures. Sintel was previously used; Big Buck Bunny and Tears of Steel are also conservatively excluded as exposed titles. All fresh candidates require cross-source capture/generation/parent-lineage review and actual media validation.

Netflix titles: **Sol Levante, Nocturne, Sparks, Meridian, Cosmos Laundromat, Chimera, El Fuente**. Nineteen Xiph rows identify Chimera/El Fuente and merge with those existing title identities. Five SVT shots are explicitly from one **Fairytale** title. Thus the 113 Xiph rows have only **92 provisional title identities** before unresolved capture relationships. Crops, encodes, stereo views, frame-rate variants and mirrors never manufacture independent units.

`rights_unit_id` identifies a grant/scope/evidence document. Statistical identity is separate: a shared title OR capture OR parent lineage merges units even if rights documents differ. Audit `source_cluster_id` values are deliberately `candidate-*`, not ingestible sealed native `source-*` IDs. `capture_cluster_id` remains unknown. Sharing a license document alone does not merge independent captures.

## Tiers, origin and complexity coverage

- **A:** clean publisher grants for real content and established creative/animated titles. UVG-VCM has **17 real sequences**; Netflix has five live-action and two animated titles.
- **B:** reviewed per-sequence Xiph evidence only. The host's belief that files are freely redistributable is not a grant.
- **C:** UVG-VCM's **Synthetic Aerial, Synthetic Drone, Synthetic City**, explicitly tagged synthetic. These are publisher-provided, not newly generated independent scene draws; shared generation lineage remains unreviewed. No generated/captured tranche was created.

Observed-real-only rights-title upper bound: **22**. Fresh title upper bound excluding the three explicitly procedural synthetic assets: **24**, including two Netflix animated titles. Animation is tagged `animated`, not silently classified as camera-captured or a newly generated Tier C tranche. Verified units with and without explicit synthetic assets are both zero.

**Quantitative low/medium/high stratum coverage is unmeasured (0/0/0 qualified).** Descriptions span traffic, sports, walking, robots, animation and codec-challenging scenes, but descriptions/filenames are not measured spatial/temporal complexity. Do not reuse correlated excerpt strata or assign splits prematurely. Generated/captured fills must follow owned preassignment measurements and source-level lineage review, not a convenient missing-file count.

## Rights review and legacy conflict

Official UVG-VCM membership/grant and Netflix's listed-project grant support **CC BY 4.0**. Original UVG explicitly links **CC BY-NC 3.0**; its sixteen sequences remain separate and excluded.

| Xiph exact class / preserved terms | Rows | Main-pool decision |
|---|---:|---|
| Unknown / no explicit permitted sequence grant | 62 | Reject/pending review |
| CC BY-NC-ND 4.0, legacy Netflix notices | 18 | Reject: NC + ND |
| Public-domain assertion | 6 | Separate class; not silently CC0 |
| No-copyright assertion | 11 | Separate class; not a CC0 grant |
| NTIA research-only terms | 8 | Outside unchanged main whitelist |
| SVT technology-standards-only 2006 terms | 5 | Outside unchanged main whitelist |
| Other research-only terms | 2 | Outside unchanged main whitelist |
| CC BY 3.0, official Sintel grant | 1 | Rights clear; exposed title and short trailer excluded |

Current Netflix masters say CC BY 4.0, but **archived Xiph representations retain older NC-ND notices**. Do not borrow a new license for a different archived file. Netflix_Aerial's copyright URL returns 404 and stays unresolved. Conflicting grants require review; later permissive evidence cannot override an earlier restriction.

`LicenseRef-*` names preserved custom terms, not invented SPDX/CC licenses. Custom/no-copyright/public-domain material is not asserted universally unusable: it falls outside the existing CC BY 3/4 + CC0 whitelist or needs scope/jurisdiction review. Any rights-class expansion requires separate approval. Sintel requires the full credit scroll when distributing/screening the movie; its trademark/logo exceptions are preserved.

## Native source-length blocker

The unchanged native design requires **>=80 seconds**: a real 20-second window after 60 seconds of excluded opening footage, with browser H.264 normalization. All twenty UVG-VCM sequences are **1.17–19 seconds** from published frame counts/FPS. Padding, looping, concatenating fake independence or renaming cannot qualify them.

Selected Nocturne video: **664.5 seconds, 60 fps**, bound to its concrete IMF track via CPL UUID/asset-map metadata. This is publisher metadata, not FFprobe validation. The other six Netflix source durations remain unknown; Sparks' selected finished-video representation is unresolved within the bounded traversal. Geometry/FPS not explicitly resolved remain null rather than guessed from generic 4K labels. All alternatives and known/unknown fields are in JSON/CSV.

- Ignoring length and assuming every fresh title independent: **69** more rights-title candidates needed (96−27).
- Enforcing known lengths: **at most seven** fresh rights-and-length-compatible title candidates, most with unknown length. Optimistic additional deficit: **89**.
- Fully verified native units: **0**; operational reservation deficit: **96**.

This is missing provenance/measurement plus known source incompatibility, **not evidence of no actuator effect**. A future media-only adapter for short test material needs explicit protocol review; this audit changes neither it nor frozen controller/sampler/credit semantics.

## Storage — estimates, not download authorization

UVG single-view raw payload estimate: **464,320,512,000 bytes = 464.32 GB decimal (~432.43 GiB)**, derived from published geometry/chroma/sample storage/frame counts. Retaining two stereo-right views adds **2.49 GB**. Publisher rounded size labels are retained; no downloads were verified.

Six provisional Netflix video representations total **110,013,675,661 bytes (~110.01 GB)** by S3 ListObjects sizes; Sparks is unresolved. Audio-only MXF, animatics and original-camera takes are not silently selected as finished masters. Smallest listed MP4 is preferred where available, otherwise a video master; this is not approval of fidelity, codec or source duration. Nocturne alone is ~81.8 GB.

Known A/C subset subtotal: **~574.33 GB plus Sparks**, before normalization, encoded cohorts, logs, decoded samples and replay artifacts. The partial Netflix listing already contains **2,680,540,223,958 bytes (~2.68 TB)** across variants, image sequences and other assets: a lower bound, not a complete bucket estimate. With UVG originals, all-variant archival exceeds **3.14 TB** before working outputs. **2 TB cannot retain everything.**

Xiph selected catalog labels add **~82.38 GB plus 29 unknown sizes**; these are rejected/restricted/exposed/unverified candidates, **not an approved download queue**. Mirrors are not new observations.

1 TB minimum / 2 TB preferred scratch is a planning recommendation, not allocated storage or permission to download. It may fit a reviewed subset, not full-master retention. Normalization/encoded/log/replay volume remains unknown. Spending ~464 GB on short UVG raw sequences does not solve the frozen source-length requirement.

## Reproduction and next decision

Rights-PDF extraction/replay requires the existing `pdftotext` (Poppler) executable. This audit installs nothing. A missing extractor leaves live PDF evidence unresolved or blocks PDF replay; cached derived text is never accepted in place of the preserved original.

```bash
uv run --frozen media-acquisition-audit snapshot \
  --config configs/native_panel_acquisition_audit_v1.json \
  --out results/acquisition-snapshots-fresh
uv run --frozen media-acquisition-audit audit \
  --config configs/native_panel_acquisition_audit_v1.json \
  --snapshots results/acquisition-snapshots-fresh \
  --out results/acquisition-audit-fresh

# Zero new URL fetches; output directory must be fresh.
uv run --frozen media-acquisition-audit audit \
  --config configs/native_panel_acquisition_audit_v1.json \
  --snapshots results/native-panel-acquisition-audit-v1-final \
  --offline --out results/acquisition-audit-offline-replay
uv run --frozen media-panel-assets verify-freeze
```

`--retry-unresolved` explicitly retries research failures in a new live pass. Audit artifacts are not ingest requests: reviewed source/capture lineage, original/normalized bytes, attribution receipt, native probe and owned quantitative strata remain required.

Verified: **40 audit tests**, **48 existing asset/panel/native-identification regressions**, actual 156-row JSON/CSV and every preserved original/rights digest, network-disabled replay, public CLI/config registration and the 31-file freeze. No full native panel was run for this metadata phase.

Next: review **>=80-second** rights-clean real captures/titles and cross-source lineage, resolve missing metadata/rights scopes, authorize a bounded tranche/storage budget, then measure source-level complexity before designing generated fills. Preserve N and frozen code. If no defensible path remains, report rights/length/provenance deficit and request explicit scope/protocol input; do not manufacture units or iterate controllers.

Primary evidence:

- https://ultravideo.fi/UVG-VCM/index.html
- https://opencontent.netflix.com/home
- https://media.xiph.org/video/derf/
- https://ultravideo.fi/dataset.html
- https://durian.blender.org/sharing/
- https://media.xiph.org/video/derf/Chimera/Netflix_DinnerScene_Copyright.txt
- https://media.xiph.org/video/derf/vqeg.its.bldrdoc.gov/HDTV/SVT_MultiFormat/SVT_MultiFormat_v10.pdf
- https://media.xiph.org/video/derf/vqeg.its.bldrdoc.gov/HDTV/NTIA_source/HDTV_Readme.txt
