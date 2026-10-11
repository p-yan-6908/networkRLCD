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

## 13. An addendum to B1, added by the agent (2026-10-10)

Not asked for and not a decision of the owner's. After the registration was frozen and before
any B1 data exist, the agent described what happens inside an N1 hold from the raw logs
([NATIVE_PHASE_N1_DYNAMICS.md](NATIVE_PHASE_N1_DYNAMICS.md), mechanism only, no quality label
read) and then fixed an addendum to B1:
[NATIVE_PHASE_B1_ADDENDUM_POSITIONS.md](NATIVE_PHASE_B1_ADDENDUM_POSITIONS.md). It splits B1's
holds by their position in the schedule and repeats the within-hold tables on B1's capture.
It changes no registered quantity or outcome and none of the four frozen files, and it runs
only after the registered final report. The owner can strike it; nothing depends on it.

Later the same day, still before any B1 data, the agent added a third part to the addendum:
the tables of the [delivery pass](NATIVE_PHASE_N1_DELIVERY.md) (what became of the frames,
where the time went, the receiver's buffer per phase, and the first hold apart from the
later ones), to be run unchanged on B1's capture. They read timing labels and no PSNR.


## 14. An uncapped pilot, approved on a wrong premise and not run (2026-10-10)

After the within-hold pass the agent put two questions to the owner.

- *"Should I first check, on N1's twelve already-used sources, whether the uncapped browser
  simply beats the caps?"* The owner chose **"Uncapped pilot first"**: a development pilot,
  not confirmatory, of sessions with no effective cap against sessions held at 1.05, 0.85 and
  0.65 of the estimate on the four schedules; about 190 sessions, 2.6 hours of capture, 3 GB,
  no fresh sources and no download; new harness files only; B1 stays registered and waits.
- *"May I run short native smoke tests during development (a few sessions, a few minutes,
  already-used sources only) without asking each time?"* The owner chose **"Yes, short
  ones"**: up to about ten minutes of local browser sessions at a time, to check new harness
  code before a real capture. Any capture of record still needs the owner's go-ahead.

**The first answer rested on a statement of the agent's that was false.** The question said
that the browser without an application cap had never been measured in this harness. Earlier
development diagnostics ran it under a 4 Mbit/s ceiling, and it was the worst condition of
each: 10% to 51% of frames on time against 56% to 92% for the capped senders of the same
studies. The agent found this while reading the harness for the pilot, before any pilot code
was written. The figures and their limits are in the correction at the top of
[NATIVE_PHASE_N1_DYNAMICS.md](NATIVE_PHASE_N1_DYNAMICS.md).

**So the approval is not acted on.** No pilot code exists and nothing was captured. This is
the agent's reading, not the owner's instruction: a go-ahead given on a false premise is not
a go-ahead, and the pilot goes back to the owner with the corrected facts.

- The pilot's stated question is answered in direction by the earlier records. On this
  endpoint the uncapped browser does not beat a capped sender.
- Not known: where between N1's top ratio and the ceiling on-time delivery falls, by which
  path, and how a fixed cap chosen for the link compares with a ratio of the estimate on N1's
  schedules.
- The agent's recommendation is not to run the pilot as described, and to read the receiver
  side of N1's existing capture first, which needs no capture and no go-ahead.

The second answer does not depend on the false statement and stands. It has not been used.

## 15. A wide-range development pilot, approved with the corrected facts (2026-10-10)

After the [delivery pass](NATIVE_PHASE_N1_DELIVERY.md) the agent went back to the owner with
the corrected facts: the uncapped browser had been measured in earlier diagnostics and did
worst; in N1 frames miss the deadline mainly in the receiver's buffer; the schedule sets that;
and ratios 0.65 to 1.05 barely move it. Asked what should happen while B1 waits for the
reviewed CSV, the owner chose **"Wide-range pilot"**, as the agent described it:

> Development pilot, not confirmatory: whole sessions held at five levels, from a quarter of
> the estimate up to the browser under the 4 Mbit/s ceiling, on the four schedules and N1's
> twelve already-used sources. About 240 sessions, 4.4 hours of capture, 4.5 GB, no download.
> Asks whether any cap level moves on-time delivery here, which B1's narrow contrast cannot
> show. Design committed before capture; new harness files only; nothing frozen changes.
> Choosing this is the go-ahead for that capture.

The other options were to capture nothing until B1, and the original pilot of section 14.

What this does and does not allow:

- One capture of about that size, on N1's twelve used sources only. N1's nine reserve sources
  stay reserved to N1 and B1's candidates are not touched.
- New harness files. The four N1 files, the 31 controller files and the four B1 files stay as
  frozen.
- The design is committed before the capture, and the pilot is labelled development evidence
  wherever it appears. It promotes nothing and changes nothing in B1.
- The exact levels are the agent's to fix in the design. Short smoke tests (section 14) may be
  used to check the new harness and the rates the levels realise, not to look at outcomes.

**Outcome (2026-10-11).** The pilot ran as approved: the design and harness were committed
before any session of record (`bf73026`), all 240 sessions sealed, none failed, 4.1 GB,
three hours and twelve minutes. A smoke test of ten short sessions on used sources preceded
it. The record and its results are in [NATIVE_RANGE_PILOT_V1.md](NATIVE_RANGE_PILOT_V1.md).
In short: kept for a whole session, the lower levels deliver far more frames on time and score
higher on the endpoint than 1.05, and the browser under the ceiling is the worst level. It is
development evidence on used sources with one session per cell.

What the agent would put to the owner next, none of it decided:

- B1 stays as registered. Its contrast is within a hold, and the pilot suggests the larger
  effect belongs to a sustained level. A null in B1 would therefore not settle whether a lower
  cap helps.
- A confirmatory test of sustained levels needs whole sessions randomised to a level, on fresh
  sources. B1's 74 candidates are the only fresh sources in sight, and they are B1's. Whether
  such a test is registered beside B1, after it, or instead of some of it is the owner's call.
- The capture of this pilot is 4.1 GB on local disk and is not in the archive.

## 16. A first controller pilot, approved (2026-10-11)

After the [headroom pass](NATIVE_RANGE_PILOT_HEADROOM_V1.md) the agent wrote down two
rule-based candidates, built their harness as new files, smoke-tested it with five short
sessions on used sources and committed the design
([NATIVE_LADDER_PILOT_V1.md](NATIVE_LADDER_PILOT_V1.md), `56ad933`) before asking. The
question to the owner described a rule that moves among four ratios of the estimate by the age
of the presentation feedback, with a variant that cuts faster, to be run against the tuned
fixed levels 0.25 and 0.65 and against 1.05 on N1's twelve used sources: the first native test
of a controller against a tuned baseline here, development-grade, design already committed,
new harness files only, B1 untouched.

The owner chose **"Yes, two repetitions"**: 480 sessions, about 6.4 hours of capture, about
8 GB. The other options were one repetition, and to hold it.

What this allows: that one capture, on N1's twelve used sources only. The marks of the rules
stay as committed. Whatever it finds is development evidence; it cannot promote a controller,
and a confirmatory test on fresh sources would be a further decision of the owner's.
