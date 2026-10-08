# NATIVE_PANEL_ACQUISITION_DISCOVERY_V2

## Status and unchanged contract

Metadata-only collection/audit, sealed 2026-10-05. **No bulk media downloaded,
no captures made, no models trained, no controller promoted.** All **31** frozen
controller/model/physical-actuator files match
`configs/native_controller_freeze_v1.json`, freeze SHA256
`68f770b4dc561497bf7fa2e1ff17917bbc7c77df5c32a4ebe680d94a58db7fed`.

The target is still **96 independent source/title/capture units**, each with an
unlooped, unpadded source representation **at least 80 seconds** long. No excerpts
become new independent units. The unchanged rights whitelist is CC BY 4.0,
CC BY 3.0 and CC0 1.0; NC, SA, ND, unversioned PD and other versions are not
silently accepted. No sample-size reduction or treatment-effect analysis occurs.

V2 is a separate module, CLI and collection configuration:

- `src/media_rl/native_acquisition_discovery.py`
- `configs/native_panel_acquisition_discovery_v2.json`
- `media-acquisition-discovery` (registered in `pyproject.toml`)

## Sealed counts: files, metadata rights, then actual eligibility

Artifacts: `results/native-panel-acquisition-discovery-v2-sealed/`.

| Source | Discovered candidate records | Rights/provenance-screened records | Fresh rights + >=80s candidate clusters | Fully verified eligible units |
| --- | ---: | ---: | ---: | ---: |
| Wikimedia Commons | 234 | 136 | 110 | 0 |
| Blender production catalog | 22 | 4 | 1 | 0 |
| Combined records | 256 | 140 | **110 after cross-source deduplication** | **0** |

The Commons searches enumerated **600 unique file pages**; the table's 234
Commons records satisfy the catalog's >=80-second duration check and include
production-specific auxiliary searches. The audit catalog has 22 productions,
including two in development. A catalog entry is a discovered production record,
not an assertion that a released >=80-second master exists.

The Blender fresh cluster is **Spring**, already represented on Commons; it
adds no extra independent cluster to the combined 110. Big Buck Bunny, Sintel
and Tears of Steel have cleared grants but were previously exposed and are
excluded from fresh planning. Rights record totals are not independent-unit
counts, and source subtotals must not be added to obtain clusters.

**Verified deficit: 96. Conditional count deficit: 0**, only if enough of the
110 metadata candidates later pass all frozen ingestion, source independence,
actual media hash/probe, duration and complexity requirements. The margin over
96 is only 14 provisional clusters. This is not a powered panel or evidence of
negative/positive actuator effects. Neither independence nor stratum coverage
has been certified.

## A. Commons collection and rights evidence

[Commons Action API](https://commons.wikimedia.org/w/api.php) generator search,
namespace 6, `filetype:video`, bounded continuation with 10 files per batch,
15 batches per query and a 600-file main-search ceiling. The fixed priority
queries are in the configuration; the search is **bounded, not exhaustive**.
Broad queries can be left unexecuted when the budget is reached. All query
URLs, returned-file counts and API errors are recorded in `report.json`.

Requests use `videoinfo` and current file revisions, preserving the response
bytes and SHA256. Per-file records carry file/title/page/revision identifiers,
creator separate from uploader, creation/capture metadata when supplied,
original source credit/URLs, dimensions, reported duration/size, available
catalog FPS, exact license identifier/URL and a reconstruction-tested scope
hash binding that file's metadata and revision. A reported Commons media SHA1
is stored as such; it is **not** substituted for an actual original SHA256.
Missing native/normalized SHA256s, measurements and capture provenance remain
null or unverified.

Metadata rights screening requires an exact permitted version and canonical
license-host URL, a named creator and preserved revision, and either explicit
own-work credit with the corresponding own-source template, or a completed
named/dated source-license review with an original-source URL. Empty, malformed,
pending or failed review tags do not clear rights. Explicit restrictions and
unreviewed soundtrack/gameplay/component grants are quarantined. A historical
source-review receipt is **not** a frozen native-importer rights review, and does
not eliminate the need to inspect the actual media and all component rights.

`commons_retained.json` contains only rights/provenance-screened >=80-second
files; `inventory.json`/`inventory.csv` also retain unresolved cases for audit.

## B. Blender production audit and master caveats

The [Blender Studio film catalog](https://studio.blender.org/films/) supplies
production membership. Actual linked production About/licensing pages and
[download directory metadata](https://download.blender.org/demo/movies/), plus
Commons representation metadata, are preserved. Generic website/software
licenses and merely calling a title an Open Movie do **not** clear a film.

Confirmed production-specific grants:

- [Spring](https://studio.blender.org/projects/spring/pages/about/): CC BY 4.0;
  a 464.141-second downloadable Commons representation is cataloged. The
  primary page says "released un" rather than "released under"; the preserved
  film-specific declaration and linked 4.0 license bind the version explicitly.
- [Big Buck Bunny](https://peach.blender.org/about/),
  [Sintel](https://durian.blender.org/sharing/) and
  [Tears of Steel](https://mango.blender.org/sharing/): CC BY 3.0, all previously
  exposed; no fresh-cluster contribution.
- [Sprite Fright](https://studio.blender.org/projects/sprite-fright/pages/about/)
  explicitly says **Attribution 1.0**, outside the frozen whitelist. It is not
  upgraded to 4.0 because a mirror has a reviewed 4.0 label.
- [Agent 327](https://studio.blender.org/projects/agent-327/pages/about/)
  explicitly binds **CC BY-ND 2.0**, also outside the whitelist. Its 44-minute
  "A feature film in progress" documentary is not recorded as the short film's
  full master.

There are **18 uncleared Blender production records**, including the disallowed
cases and unfinished productions. Other titles remain unresolved where the
captured first-party pages do not explicitly bind a permitted grant. The film
catalog is not a blanket-license receipt. Exact unsupported declarations and
conflicting mirror evidence are kept in the inventory.

Representations distinguish publisher directory links with unknown duration
from downloadable >=80-second cataloged mirrors. Trailers, teasers, making-of,
interviews, commentaries and work-in-progress films are not silently relabeled
full-movie masters. Cataloged mirrors have `publisher_master_verified=false`;
no native original-master authenticity or probe is claimed. Raw discoveries of
these other files remain in the Commons audit and share conservative lineage.

## Independence, unresolved cases and strata

`rights_unit_id` is separate from `source_cluster_id`/`capture_cluster_id`.
Identical title/media SHA1, original source URL (tracking/fragment aliases
removed), event/capture identifiers and conservative creator families form
transitive union-find components. Non-Latin title identity is retained. Known
Blender productions and their Commons mirrors canonicalize together; known
Caminandes franchise/asset lineage merges across episodes. Different titles do
not merge solely because they share a rights document or studio creator.

`cluster_collisions.json` records **70 actual component-union edges**, not all
pairwise similarities. Creator-only Commons merges are conservative without
reviewed capture sessions; they are not proof that those files are dependent or
that different creators are independent. Cross-query revision/media drift is
quarantined, and first-party incompatible grants override reviewed-mirror
assumptions.

**116 unresolved/uncleared rights records**: 98 Commons and 18 Blender. Commons
cases include 80 external/incomplete-provenance records, six component-grant
cases, eight own-work/review records with unsupported license or restrictions,
and four primary/mirror scope/version conflicts. See per-record flags and
archived source/revision evidence; no blanket license is applied.

All **110** fresh candidate clusters have unmeasured quantitative complexity.
**Measured spatial strata: 0; temporal strata: 0; joint cells: 0.** Descriptions,
genre and planned recipes are not measured low/medium/high labels. Actual
complexity measurement and source-disjoint split assignment are deferred to the
unchanged ingestion/panel procedures, before controller/panel outcome access.

## C. Immutable original-capture reserve plan and receipts

`capture_plan.json` reserves **96 immutable UUID-derived capture IDs** in the
configured V2 namespace, plus immutable receipt/source/session identifiers.
The currently conditional count-driven activation is zero; the verified deficit
is still 96. Reserve slots can later fill failed native/independence checks or
sparse *measured* strata, without pretending an unmade capture is a unit.

Rows are spatial targets; columns are temporal targets:

| Planned target | Low temporal | Medium temporal | High temporal | Total |
| --- | ---: | ---: | ---: | ---: |
| Low spatial | 11 | 11 | 10 | 32 |
| Medium spatial | 10 | 11 | 11 | 32 |
| High spatial | 11 | 10 | 11 | 32 |
| Total | 32 | 32 | 32 | 96 |

Each slot requests a genuinely separate scene/source/event/session, 120 seconds
at 1920x1080/30 fps, with tripod/slow, ordinary movement and fast
object/camera-action recipes over plain, mixed-detail and dense-texture scenes.
Repeated shots, excerpts or multiple files from one event/session merge; planned
IDs do not assert independence. Quantitative strata must be measured and frozen
before assignment, rather than forced to match recipe names.

`capture_rights_receipt.schema.json` is a JSON Schema for actual signed receipts.
`capture_rights_receipts.json` contains 96 **unsigned, ungranted templates**:
owner/creator identities, signatures, actual timestamps, media hashes, native
probe and complexity evidence are unset. No owner or license grant is invented.
Actual receipts require the named creator and copyright owner, an explicit
CC BY 4.0 grant bound to capture ID/media hashes, contributor/property/person
release references where necessary, actual >=80-second unpadded capture,
independence review, native probe and owned complexity-measurement receipts.
No third-party footage/music should be used; silent capture is preferred.

## Storage estimates (decimal GB; metadata is not media)

- One known size-minimal catalog representative for each of 110 provisional
  fresh clusters: **20,820,664,226 bytes (~20.82 GB)**.
- All distinct selected fresh-candidate file URLs: **28,521,695,572 bytes
  (~28.52 GB)**. Do not add these two alternatives.
- Missing sizes among these selections: **0**. Sizes remain catalog estimates,
  not downloaded-byte checksums or a claim of lossless original masters.
- Normalization, encoded panel outputs, logs and replay storage: **unresolved**;
  provision additional scratch/retention after actual representation selection.
- All 96 capture reserves, if activated: source 8–20 Mbps plus normalized
  2–8 Mbps over 120 seconds gives **14.4–40.32 GB** before logs/replays/backups.
  This is a bitrate scenario, not an actual encoder measurement. Current
  count-driven activation is zero, so this is a reserve rather than a purchase
  or collection commitment.

The sealed evidence contains **126 preserved metadata responses / 9,329,882
bytes (~9.33 MB)**. Request counters include inherited snapshots, not new
requests issued by offline replay. Media download bytes are exactly **0**.

## Reproduction and verification

```sh
# Fresh bounded live collection (text/JSON metadata only; output must be new):
uv run --frozen media-acquisition-discovery discover \
  --config configs/native_panel_acquisition_discovery_v2.json \
  --out results/my-discovery-v2

# Reproduce the sealed metadata workflow, no network:
uv run --frozen media-acquisition-discovery discover \
  --config configs/native_panel_acquisition_discovery_v2.json \
  --snapshots results/native-panel-acquisition-discovery-v2-sealed \
  --offline --out results/my-discovery-v2-offline

uv run --frozen media-panel-assets verify-freeze
uv run --frozen pytest -q tests/test_native_acquisition_discovery.py \
  tests/test_native_acquisition_audit.py tests/test_native_panel_assets.py \
  tests/test_native_actuator_panel.py
```

Verified **118 focused tests**. A direct behavioral replay additionally:

1. Re-hashed all 126 preserved responses and reconstructed all 234 per-file
   Commons scope hashes from archived API metadata/revisions.
2. Replaced the network opener with a failing stub; **zero network calls**.
3. Compared inventory, capture plan, receipts and report (except generation
   timestamp) against sealed outputs: identical.
4. Confirmed all 31 frozen controller/model/actuator hashes still match.

Replay evidence: `results/native-panel-acquisition-discovery-v2-offline-replay/`.
Frozen-method context: [powered-panel V1](NATIVE_ACTUATOR_POWERED_PANEL_V1.md);
previous source/storage audit: [acquisition V1](NATIVE_PANEL_ACQUISITION_AUDIT_V1.md).
No native media was imported or normalized by this workflow. That separately
reviewed acquisition/ingestion step, actual independence/stratum verification
and panel execution remain the critical path.
