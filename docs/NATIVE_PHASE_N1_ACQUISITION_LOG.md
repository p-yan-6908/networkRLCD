# Native Phase N1: acquisition log

Entries are dated. Those of 2026-10-08 were written before any capture; the stage-one capture
is opened by the entry of 2026-10-09 and logged in the
[capture log](NATIVE_PHASE_N1_CAPTURE_LOG.md). The registration stays frozen at `318c473`
(`native-n1-preregistered`).

## 2026-10-08: review received, queue fetched

### The rights review as submitted

`acquisition/native-n1/rights-review/rights-review-manifest-reviewed.csv`, recorded unchanged.

| Decision | Candidates |
|---|---:|
| `pass` | 16 |
| `needs_media_inspection` | 20 |
| `fail` | 0 |

The reviewer of record for all 36 rows is "ChatGPT (OpenAI) — copyright/licence evidence
review", with one timestamp. The review changed no discovered field other than setting
`rights_cleared` on its 16 passes.

**No source is rights-cleared for ingest yet**, for two reasons.

1. **The binding quotes are not in the evidence.** The unchanged ingest accepts a binding
   quote only if it occurs verbatim in the archived evidence file. A mechanical check
   (`media-n1-acquisition evidence`) finds 0 of the 16 passes' quotes there. Each is the
   generic sentence "This file is licensed under the Creative Commons Attribution ...
   license", which is how a Commons page renders, not text from the archived revision. As
   written, ingest would refuse all 16. The source title does occur in the evidence for all
   36, and `acquisition/native-n1/rights-review/evidence-extracts.json` lists, per candidate,
   the strings that do occur verbatim: the licence template of the reviewed revision, the
   licence-review template where one exists, and the source, author and permission fields.
2. **The importer's assertion is not recorded.** Ingest requires `rights_asserted_by_importer`
   and `reviewed_by_importer`. The reviewer of record is an AI assistant, so those two flags
   are the repository owner's to give.

The 20 `needs_media_inspection` rows await a decision after someone looks at the media.

### Fetch

Under the rule that only reviewed `pass` or `needs_media_inspection` candidates are
downloaded, all 36 were fetched (`media-n1-acquisition fetch`).

| | Used | Budget |
|---|---:|---:|
| Network download | 6.48 GB | 10 GB |
| Temporary local storage | 9.59 GB | 30 GB |

- Every download matches the SHA-1 that Commons recorded for the reviewed revision.
- One derived file per source: video-only H.264 Main, yuv420p, at most 1280x720, frame rate
  and aspect ratio unchanged. No other variant is kept. The unchanged collector draws frames
  at 640x360, and the earlier native-ready films are 1280x720 and 1280x544.
- Lineage is in `acquisition/native-n1/lineage.json`: original SHA-256 and SHA-1, the ffmpeg
  version and arguments, and the derived SHA-256 with the original's SHA-256 as its parent.
- 35 of 36 are native-ready by format (H.264, at least 80 seconds of video). `commons-29168975`
  cannot be decoded (Ogg CRC errors in the file as hosted) and is recorded as such. It shares
  a capture group with `commons-29267197`, so no independent source is lost.
- Originals were VP9 (14), VP8 (13), Theora (7) and AV1 (1). All 35 decodable originals carry
  audio; no derived file does.
- 26 derived files are 1280x720. Nine are smaller or not 16:9, including one vertical
  (406x720); the collector will scale those to 640x360 as it did the 1280x544 film.
- Frame rates are 25 (17 files), 30 (11), 29.97 (3), 60 (1), 23.98 (1), about 30 variable (1)
  and 14.75 (1).
- `commons-42522829` has 143 seconds of video under a 215-second audio track; its derived
  file keeps every video frame.

Media and inspection sheets are local and untracked under `results/native-n1-acquisition/`:
`original/`, `native/`, and `inspection/<candidate>.jpg`, a 30-frame contact sheet per
decodable candidate.

### Where the pool stands

| | Independent capture groups |
|---|---:|
| Reviewed as `pass`, decodable | 15 |
| Awaiting media inspection, decodable | 20 |
| Verified eligible | 0 |

Twelve eligible sources, four per complexity tercile, need at least twelve of these to clear
rights and pass ingest. Twenty-four need at least nine of the inspection candidates as well.
Terciles are fixed by one screening of the whole verified pool, so screening and the sealed
plan wait until the review is complete.

### Outstanding before ingest

1. Binding quotes that occur in the archived evidence, for every pass.
2. The importer's assertion for every pass.
3. A decision on each of the 20 inspection candidates.

## 2026-10-08: final review, ingest, screening and sealed plan

Still no outcome data. No native capture has been run.

### The final review as submitted

`rights-review-manifest-final.csv` and `contact-sheet-review-final.json`, recorded unchanged.

| Decision | Candidates |
|---|---:|
| `pass` | 22 |
| `fail` | 14 |

The 16 earlier passes stay passes. Of the 20 inspection candidates, 6 pass and 14 fail. The
reviewer of record for all 36 rows is "ChatGPT (OpenAI) — archived-evidence and contact-sheet
copyright/licence review". The contact-sheet record states its basis: archived evidence plus
the 30-frame contact sheets, with native-ready derivatives being video-only, and a fail
meaning insufficient component-rights evidence under a strict screen, not infringement.

Mechanical checks on the final review:

- All 22 binding quotes now occur verbatim in the archived evidence, and all 22 titles do.
  They are licence templates of the reviewed revision such as `{{self|cc-by-4.0}}`, or the
  licence-review template for files that came from an external site.
- `commons-29168975` is a pass with no decodable file, so it is not ingested. Its capture
  group is represented by `commons-29267197`.

**Importer flags.** Ingest records `rights_asserted_by_importer` and `reviewed_by_importer`
in the importer's name. They are set for the 21 ingested assets on this basis: the
repository owner submitted the final review for ingest after being told ingest needs them.
The owner did not write a separate assertion, and the evidence review itself is by the
reviewer of record. Each catalog carries both facts in `rights_review_provenance`. If the
owner does not adopt the review, the ingest, screening and plan are discarded; nothing
depends on them yet.

### Ingest and screening, with the unchanged tools

- `media-panel-assets ingest`: **21 independent source clusters, all native-ready** (H.264,
  at least 80 seconds; the shortest is 84.9 s). Nine are CC BY 3.0, eight CC BY 4.0 and four
  CC0 1.0.
- `media-actuator-panel screen`, run once on the whole pool: 120 windows, no outcome data,
  terciles at 0.0339 and 0.0453. **Seven sources per complexity tercile.**

### Sealed plan

`media-actuator-qualification plan`, sealed at
`results/native-actuator-qualification-n1-plan/` with the recorded custodian value. This was
the planner's first run on real catalogs. The sealed plan re-derives exactly from the
registration, the screening file and the reservations.

| | |
|---|---:|
| Sources (7 / 7 / 7) | 21 |
| Stage one (4 / 4 / 4) | 12 |
| Reserve blocks | 3 |
| Maximum for the blinded rule | **21**, not 24 |
| Planned peers | 840 |
| Planned cohorts | 5,040 |
| Planned arm counts (0.65 / 0.85 / 1.05) | 1,686 / 1,653 / 1,701 (p = 0.70 against equal shares) |
| Smallest planned source x regime x arm cell | 11 |

The queue supplied 21 eligible sources, short of the preferred 24, so the rule's maximum is
21. Discovery was not expanded. The rule then reads 12, 15, 18 or 21 sources, with precision
futility above a first-stage SD of 0.146. Simulated at the design effect, 10,000 studies:

| Scenario | Qualified with maximum 21 | With maximum 24 |
|---|---:|---:|
| Smoke-level noise | 0.986 | 0.984 |
| Heterogeneous sources (SD 0.08) | 0.893 | 0.921 |
| Very heterogeneous (SD 0.12) | 0.556 | 0.632 |
| Lower contrast exactly at the margin (false qualification) | 0.027 | 0.025 |

The sources, their order, terciles, licences and hashes are in
`acquisition/native-n1/pool-and-plan.json`, with the hashes of the review files, the ingest
request and manifest, the screening file and the sealed plan. The plan's sources are reserved
by the existing reservation scan, so a later plan, including Phase N2's, cannot draw them.

### State of the gate

Source pool, sealed plan, custodian record and acquisition provenance are complete. The
native outcome experiment has not been started and is not started by this log. The capture
path has still only run on test doubles; its first native run is also its first test against
a browser.

## 2026-10-09: the owner adopts the review and opens the capture

No outcome data existed when this entry was written.

**Importer's assertion.** Asked directly whether they adopt the final review as their own
assertion, the repository owner answered "Yes, I adopt it". The final rights review
(`rights-review-manifest-final.csv`, `contact-sheet-review-final.json`) is therefore the
owner's importer assertion for the 21 ingested sources. This replaces the basis recorded on
2026-10-08, which inferred the two importer flags from the owner having submitted the review.
The evidence review itself is still by the reviewer of record. The ingest, the screening and
the sealed plan stand unchanged, and no file was regenerated.

**Go-ahead.** Asked whether to start the capture, the owner chose "Start stage one": the
registered capture of planned positions 0 to 12 of the sealed plan (12 sources, 480 fresh
peers, 2,880 assigned cohorts), then the outcome-free `status`, then the sealed interim with
the recorded custodian value. The run is logged in the
[capture log](NATIVE_PHASE_N1_CAPTURE_LOG.md).
