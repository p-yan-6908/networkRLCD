# Native Phase N1: decisions and custodian record

The N1 registration is frozen at commit `318c473`, tagged `native-n1-preregistered` and pushed
on 2026-10-07. This file records decisions taken after registration and before any media
acquisition or outcome. It does not amend the registration: the four hash-frozen N1 files are
unchanged and `media-actuator-qualification verify-freeze` passes.

No outcome data exists. No controller, model or Phase N2 file is changed.

## 1. Level of the "not separable" outcome

Kept as registered. Each upper bound is taken at one-sided 0.0125, because that outcome needs
only one of the two contrasts. Qualification is unchanged: both lower bounds above 0.03, each
at one-sided 0.025, with no Bonferroni correction.

## 2. Complexity-heterogeneity diagnostic, reviewed

Kept as registered. The rule is a Bonferroni test over a defined family of two: the two
registered adjacent contrasts. For each contrast, a one-way test asks whether its mean is equal
across the three complexity terciles; the designation is attached to a qualified outcome when
the smaller of the two p-values, doubled, is below 0.05. The family-wise chance of attaching
it when neither contrast differs by tercile is at most 0.05.

The alternative considered was one omnibus test that the pair of contrasts is equal across
terciles (Wilks' lambda). Simulated at the design effect with smoke-level noise, 4,000 studies
per cell:

| Sources | Truth | Registered rule | One omnibus test |
|---:|---|---:|---:|
| 12 | terciles do not differ | 0.042 | 0.050 |
| 12 | upper contrast halved in one tercile | 0.149 | 0.213 |
| 12 | upper contrast zero in one tercile | 0.608 | 0.652 |
| 24 | terciles do not differ | 0.048 | 0.054 |
| 24 | upper contrast halved in one tercile | 0.357 | 0.541 |
| 24 | upper contrast zero in one tercile | 0.983 | 0.988 |

The omnibus test is somewhat more sensitive to moderate differences. The registered rule is
kept because it corresponds to a clearly defined two-contrast family, it holds its level, the
diagnostic never changes the outcome, and keeping it leaves the registration untouched.
Switching would need a new N1 freeze record committed before acquisition.

## 3. Interim custodian

The interim custodian is **the repository owner (pyan)**, because no independent human
custodian is available.

**This is procedural blinding, not independent blinding.** The custodian is also the study
owner, can run the analysis and has file access to the raw captures. Nothing but procedure and
tooling separates the custodian from the data.

What the procedure is:

- Capture computes no outcome statistic.
- `media-actuator-qualification interim` is the only look before the final analysis. It prints
  the public record only: the prescribed total source count (12, 15, 18, 21 or 24),
  non-outcome capture-support metrics, and hashes. It does not print the contrast variances,
  the uncapped requirement or the precision-futility flag.
- The sealed record is written to a path outside the results tree and is not opened before
  the final analysis, which checks it against the hash in the public record.
- No other analysis of N1 captures is run before the final analysis.

The planner binds the custodian into the sealed plan and into both interim records. Use this
exact value:

```text
--custodian "pyan (repository owner; procedural interim custodian, not independent)"
```

## 4. Publication of the registration

The three commits up to `318c473` were pushed to `origin/main` before any media acquisition,
and the annotated tag `native-n1-preregistered` marks the registered state. The N1 freeze is
not to be amended once outcome data exists.

## 5. Acquisition budget

Recorded in `configs/native_actuator_qualification_n1_acquisition.json`, for the seeded
36-candidate queue only:

- at most 10 GB of network download;
- at most 30 GB of temporary local storage;
- no unnecessary transcode variants retained.

If the queue cannot supply the balanced verified pool, acquisition stops. Discovery is not
expanded automatically.

## 6. Rights-review manifest

Exported before any download:

- `acquisition/native-n1/queue.json`: the seeded queue.
- `acquisition/native-n1/rights-review/rights-review-manifest.csv` and `.json`: one row per
  queued candidate with candidate ID, source URL, media URL, title, creator, proposed source,
  title and capture cluster, duration, catalogue size, declared license, license URL and
  rights-evidence URLs, plus what discovery recorded about provenance.

The 36 candidates total 6.48 GB by catalogue size, so fetching all of them would stay inside
the download budget. Fifteen declare CC BY 3.0, thirteen CC BY 4.0 and eight CC0 1.0.
Twenty-eight are WebM and eight Ogg, so every one needs conversion to become native-ready.
Eight name an external origin.

**No candidate is rights-cleared.** Every row has `rights_cleared = False` and empty review
fields. The column `discovery_metadata_screen_passed` is the crawl's metadata screen and is
context for the reviewer, not a clearance. A source is cleared only by an explicit reviewer
entry of `pass` with reviewer, time, attribution, binding quote from the evidence, capture
group and independence basis. Those last four are what the unchanged ingest request requires
from the importer. `media-n1-acquisition review-status` reads a filled-in copy back and
refuses an incomplete pass, an unknown decision, or an edit to a discovered field.

## 7. After the rights review

Not started. Only candidates reviewed as `pass` or `needs_media_inspection` are downloaded.
Conversion to H.264 is a derived verification artifact: the original file's SHA-256 is
recorded and carried as the parent of the native-ready file's SHA-256, so the unchanged
cluster rules treat both as one source.

## 8. Acquisition target

The target is not 108 to 120 sources. It is 4 eligible sources per complexity tercile for the
initial 12, and preferably 8 per tercile so that the blinded extension to 24 stays available.
Terciles are fixed by one screening of the whole verified pool.

## Gate before the native experiment

The browser/native outcome experiment does not run until all four are complete:

| Item | State |
|---|---|
| Custodian record | this file |
| Acquisition provenance | complete: manifest, both reviews as submitted, evidence extracts, lineage, pool and plan record |
| Source pool | 21 verified eligible sources, 7 per complexity tercile |
| Sealed plan | sealed 2026-10-08 with 21 sources; the blinded rule's maximum is 21 |

Details are in the [acquisition log](NATIVE_PHASE_N1_ACQUISITION_LOG.md). Completing the gate
does not start the experiment.

## 9. Importer's assertion and go-ahead (2026-10-09)

The repository owner adopted the final rights review as their own importer assertion for the
21 ingested sources, and instructed that stage one be captured as registered. Both answers
are quoted in the acquisition log. The custodian record of section 3 applies to the interim
unchanged.

## 10. After the N1 result (2026-10-10)

Asked which native phase should come next, the owner chose "Targeted backoff test": a draft
registration for the owner's review, and a rights-review manifest for the 74 Discovery V2
candidates that the N1 queue did not draw, with nothing downloaded or captured until the owner
approves. The draft, since registered (section 11), is
[NATIVE_PHASE_B1_BACKOFF_BENEFIT.md](NATIVE_PHASE_B1_BACKOFF_BENEFIT.md). Phase N2
stays registered and untouched. Asked whether to push the local commits, the owner chose "Not
yet".

## 11. B1 design choices and registration (2026-10-10)

Asked four questions about the draft, the owner chose the recommended option in each:

| Question | Chosen |
|---|---|
| Which pre-hold rule flags a hold as congested | Stalled estimate: the estimate grew by less than 5% since the previous hold, or fell |
| The single primary contrast among flagged holds | Both lower ratios (0.65 and 0.85) against 1.05 |
| Whether B1 may conclude that any benefit is too small to matter | Yes, with the gate at 1.0 |
| Smallest number of eligible sources for a confirmatory run | 30 |

The draft then became the registration,
[NATIVE_PHASE_B1_BACKOFF_BENEFIT.md](NATIVE_PHASE_B1_BACKOFF_BENEFIT.md), implemented and
hash-frozen before any B1 data existed. One secondary analysis was added by the agent before
the freeze without being asked: a split of the flagged holds by the previous hold's ratio,
because in N1 a hold is flagged about twice as often after a request of 0.65 as after the
other two. It changes no outcome.

Still the owner's, and not started: the rights review of the 74 candidates and its explicit
adoption, a download budget, the storage decision, and the instruction to fetch, screen, plan
and capture.

Prepared for the reviewer, from files already on disk and with nothing downloaded:
`acquisition/native-b1/rights-review/evidence-extracts.json`, written by the unchanged
`media-n1-acquisition evidence` on the unreviewed manifest. Per candidate it lists the
strings that occur verbatim in the archived evidence (`verbatim_quote_candidates`). The
unchanged ingest accepts a binding quote only if it is one of those, which none of N1's
first sixteen were. It reviews and clears nothing: all 74 rows are `not_reviewed`. For one
candidate the title does not occur in the archived evidence, so ingest would refuse it as
it stands.

## 12. B1 acquisition gate (2026-10-10)

Asked three questions, the owner answered:

| Question | Answer |
|---|---|
| How the rights review of the 74 candidates is done | "I return a reviewed CSV": the owner or their reviewer fills in the manifest and returns it, and the agent checks it mechanically |
| Download budget once the review is back | "10 GB, files under 1 GB" |
| Where the space for the capture comes from | in the owner's words, "you can store old data here: /Users/pyan/networkRLCD/ARCHIVED_RESULTS.md" |

The budget is recorded in `configs/native_backoff_benefit_b1_acquisition.json`: at most 10 GB
of download, at most 1 GB per file, the same conversion as N1, and no automatic expansion of
discovery. Seventy candidates are under 1 GB and total 9.65 GB by catalogue. The four larger
ones are passed over and listed, never fetched.

The third answer is read as follows, and the reading is the agent's.
[ARCHIVED_RESULTS.md](../ARCHIVED_RESULTS.md) documents the private offsite archive of
results and the byte-verified procedure by which archived files were removed locally, and it
asks that any further cleanup make a new backup and receipt and review active dependencies
again. So old results may be moved to that archive to make room for the capture.

What follows from the three answers:

- Nothing is downloaded until the reviewed CSV is returned. Then only candidates marked
  `pass` or `needs_media_inspection`, under the cap and within the budget, are fetched.
- Of the 32 GB free, about 14 GB go to B1's media. The capture needs 20 to 33 GB, depending on
  how many sources screen as eligible. N1's raw stage-one capture (8.3 GB of event logs and
  per-peer harness snapshots, no source media) is the old data that can move to the archive.
- It is backed up and verified first. Local copies are removed only when the capture needs the
  room and after the owner has seen the list. N1's result records and the audited cohort rows
  stay tracked in the repository either way.
- Source media are not results and are not put in the archive.

### Mechanical check of B1's analysis on real rows (2026-10-10)

B1's frozen row handling had read only mock rows. Before any B1 data exist, N1's 2,880 real
audited rows and N1's sealed plan were passed through it to exercise the code paths. This is
not a B1 result and not a new look at N1: the only statistic read was the one already recorded
for sizing, and every other quantity was checked for shape and finiteness without being shown.

- Every field B1 reads is present in a real audited row, and all 2,880 rows were accepted.
- The registered estimator reproduces the sizing record exactly on those rows: mean 1.2719,
  per-source SD 2.2674, flagged share 0.3392, smallest flagged cell 13.
- Every secondary path ran and returned finite values.
- One thing to expect: under the unconstrained schedule only 3 of the 12 N1 sources had three
  flagged holds in every arm, so B1's by-schedule secondary for that schedule will rest on
  few sources.

No frozen file needed a change.

