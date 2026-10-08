# Native Phase N1: acquisition log

No outcome data exists. Nothing here ingests, screens, plans or runs the native experiment.
The registration stays frozen at `318c473` (`native-n1-preregistered`).

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
