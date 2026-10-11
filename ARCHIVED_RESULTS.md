# Archived experiment results

## Current owner-approved storage policy (2026-10-11)

Keep the physical project tree below **10 GB (10,000,000,000 bytes)**; start cleanup
at 8 GB. Keep compact reports, summaries, protocols, manifests, checksums and archive
receipts locally/in GitHub. Store large raw evidence in the private HF dataset below,
then prune local raw files only after pinned remote checksum and recovery verification.
See [AGENTS.md](AGENTS.md), [docs/STORAGE_POLICY.md](docs/STORAGE_POLICY.md), and
`storage_policy.json`. Compact new receipts are recorded in `docs/storage-receipts/`.

### Current cleanup record

The project-budget check fell from about **45.0 GB to 4.8 GB** after relocating
untracked raw working trees outside the repository. Relocation alone reclaimed no
device space. The separately verified N1 cleanup removed 1,440 raw trace files
(8,116,250,827 logical bytes); compact proof is in
[docs/storage-receipts/n1-stage-one-pruning-2026-10-11.json](docs/storage-receipts/n1-stage-one-pruning-2026-10-11.json).
Device free space rose from roughly 14 GiB to 21 GiB before new upload staging.

Range and ladder snapshots are being uploaded/verified before any pruning. The
margin snapshot is queued only after its collector exits and final reports exist.
These new backups are **not yet claimed complete**; their verified pinned receipts
will appear under `docs/storage-receipts/`. Live handoff details are in
[docs/STORAGE_OPERATIONS_2026-10-11.md](docs/STORAGE_OPERATIONS_2026-10-11.md).

Large active/required working data may live in `~/.cache/networkrlcd/working/` through
path-preserving ignored symlinks in `results/`. This is **still local disk**, not an
archive; the new policy does not falsely count relocation as recovered disk space.
Never prune the running margin capture before its final report, or delete licensed
source media / active donor dependencies blindly. Historical receipts below remain
valid for their exact immutable snapshots; old footprint numbers are historical.

Historical results from `/Users/pyan/networkRLCD/results/` are backed up on Hugging Face:

**Private dataset:** https://huggingface.co/datasets/p-yan/networkrlcd-results-archive  
**Verified immutable revision:** `b8c76444251d84bdab612cca0884c6e90aa96b04`  
**Snapshot created:** `2026-10-04T20:01:40Z`  
**Contents:** 52,154 files in one tar stream split into 20 parts (about 21.3 GB).

Access requires a Hugging Face account with permission for this private dataset. This is a research-evidence archive, not a promoted model or a redistributable media dataset. Source/configuration changes made after the snapshot are not included.

## Local pruning

Cleanup unlinked **46,594 byte-verified archived files**, reclaiming approximately **18.1 GiB (19.4 GB)** from the original results tree. `results/` went from **19.9 GiB to 1.8 GiB**; the full project is now approximately **4.8 GiB**. The temporary archive download was also removed and is not included in the stated original-result savings.

Totals are recorded in `.tools/results-archive-receipts-v1/prune-deletions-v1.jsonl` (last line); exact allocated-size measurements are in `prune-disk-before-v1.txt` and `prune-disk-after-v1.txt`. The deletion log's logical bytes include hardlink aliases, so they are **not** actual disk space freed.

Only files byte-identical to the archived copy were eligible for deletion. Source, configs, docs, licensed source videos, build dependencies, changed/unarchived results and concurrent actuator work were not targeted.

Retained locally:

- `results/native-action-excitation-train-sintel-v1/` in full: the current actuator studies require its complete donor seal.
- Current supervised baseline `results/jevbwe-feedback-pilot-v1-verified/` and experimental controller `results/jevbwe-rlcd-pilot-v1/`.
- Lightweight model runs, checkpoint JSON files and training provenance.
- `protocol.json` reservation ledgers, including historical ones needed to keep discovery/replication/holdout content disjoint; provenance `manifest.json` files.
- Runs containing any new/unarchived files; newly created results were never deletion candidates.

**Some old run directories now contain only retained metadata/checkpoints. Their manifests still describe the original complete runs. Do not treat them as complete or rewrite their seals. Restore the archived artifacts before historical replay, reporting or a full manifest/seal audit.**

## Procedure used

1. Rechecked the private remote dataset and the verified immutable commit, plus the successful original remote part-checksum receipt.
2. Downloaded that exact revision into temporary `.tools/results-prune-stage-v1/`; checked every part against the original `SHA256SUMS`.
3. Streamed the parts without extracting another full results tree. Built an individual-file SHA256 index, resolving tar hardlinks; checked the path set against `original-file-list.txt`.
4. Generated a dry-run plan with `.tools/prune-backed-up-results-v1.py`, protecting the dependencies listed above. Hashed local files and required equality with the archived file, not just its name/size/date.
5. Ran `.tools/probe-backed-up-prune-v1.py` on disposable fixtures: matching-byte deletion, hardlinks, changed/new data, protected donor/ledger/model retention, path containment and drift retention.
6. Recorded protected-file hashes and all-role reservations, verified the donor's complete seal, then applied the reviewed plan. Each candidate was rehashed immediately before unlink; drifted files were retained. Only empty directories were removed.
7. Rechecked protected bytes, frozen reservation inputs, donor seal, unarchived paths and deletion receipts using `.tools/verify-prune-preservation-v1.py`. Removed only the temporary downloaded archive staging afterward.

Verification passed: the complete donor seal, 72 frozen reservation inputs (221 content reservations), retained experiment/checkpoint bytes and all 219 unarchived paths survived. **51 controller regression tests passed**, maintenance-helper lint passed, and all three public CLIs still show help. The recovery helper was directly checked to reject a populated destination. Finder changed the retained root `.DS_Store` and regenerated three deleted `.DS_Store` files; those incidental metadata exceptions are explicitly recorded, not treated as experiment-data failures.

Evidence stays under `.tools/results-archive-receipts-v1/`: archive/remote receipts, the original inventory/checksums, `archived-file-sha256.json`, `prune-plan-v1.json`, deletion log and preservation checks. The helpers are local maintenance utilities, not an automatic pruning policy. For another cleanup, make a new backup/receipt and review active dependencies again; do not blindly reuse this snapshot or plan.

## Restore the old files

Download the **pinned revision**, not a moving `main`:

```sh
hf auth login
archive=$(mktemp -d /tmp/networkrlcd-archive.XXXXXX)
hf download p-yan/networkrlcd-results-archive \
  --type dataset \
  --revision b8c76444251d84bdab612cca0884c6e90aa96b04 \
  --local-dir "$archive"

# Use a new/empty directory on a drive with enough space.
# This recreates EMPTY_RECOVERY_DIRECTORY/results/.
bash "$archive/restore.sh" /path/to/EMPTY_RECOVERY_DIRECTORY
```

`restore.sh` verifies all 20 part SHA256s before extraction and refuses a populated destination. The complete stream preserves cross-run hardlinks. Allow roughly 21.3 GB for downloaded parts plus additional space for the restored tree; use an external drive if needed. Deleting the temporary download later does not delete the restored results or remote backup.

Work with the recovered copy first. To refill one partial local run, **stop experiment writers**, review a dry-run, and merge only missing files (never overwrite current results):

```sh
rsync -aH --ignore-existing --dry-run --itemize-changes \
  /path/to/EMPTY_RECOVERY_DIRECTORY/results/RUN_NAME/ \
  /Users/pyan/networkRLCD/results/RUN_NAME/
# After reviewing, rerun without --dry-run; then run the normal manifest/seal audit.
```

Existing changed files are deliberately not overwritten; a run with such changes may need separate recovery/audit. Absolute workspace paths inside historical metadata are preserved, not rewritten. Hardlinks across different runs may not be preserved by a one-run merge, so restoring the complete snapshot to a separate location is preferred.

## Second snapshot: Native Phase N1 stage-one capture (2026-10-10 backup; 2026-10-11 raw cleanup)

Added after the repository owner pointed to this archive as the place for old data, to make
room for the Native Phase B1 capture. It is a separate snapshot in the same private dataset.
The first snapshot and its pinned revision above are unchanged.

**Folder:** `n1-stage-one-2026-10-10/` in `p-yan/networkrlcd-results-archive`  
**Verified immutable revision:** `aa1b8d80fd66a3f52e88b59d589825f50d5e5dd2`  
**Snapshot created:** `2026-10-10T18:56:41Z`  
**Contents:** 20,194 files in one tar stream split into 9 parts (8.85 GB).

What it holds:

- `results/native-actuator-qualification-n1-stage-one/` in full (20,175 files): per-peer event
  logs, audit records and harness snapshots, the capture manifest and the audited cohort rows.
  It contains no source media.
- `results/native-actuator-qualification-n1-plan/`, the sealed plan.
- The N1 status, interim, final and exploratory records and logs directly under `results/`.

Verification, all passed:

- every part's SHA-256 as the Hub records it at that revision equals the local `SHA256SUMS`;
- no file is missing from the folder and none is extra;
- the six inventory and recovery files are byte-identical to the local ones;
- one part was downloaded afresh and its SHA-256 matched.

Receipt: `.tools/results-archive-receipts-n1-v1/archive-receipt.json`. The SHA-256 of every
archived file is in `file-sha256.txt` beside it and in the archive folder. The scripts are
`.tools/offload-n1-stage-one-v1.sh` and `.tools/verify-n1-stage-one-archive-v1.py`. The
temporary staged parts were removed after verification.

**At backup verification on 2026-10-10, no result file had been deleted.** On
2026-10-11 the owner-approved storage cleanup reverified that exact private revision
and removed **1,440 byte-matched raw trace files (8,116,250,827 logical bytes)**.
See [the new pruning receipt](docs/storage-receipts/n1-stage-one-pruning-2026-10-11.json).
Derived/cohort/manifest JSON, models, frozen source snapshots, plans and tracked records
remain. The raw capture is now **partial locally**, marked `ARCHIVED_RAW.json`, and
requires restoration before a full seal audit or raw replay. The original backup and
its immutable receipt were not changed. The reviewed removal rules were:

- only after the owner has seen the list;
- only files whose bytes still equal the hash in `file-sha256.txt`, rehashed just before removal;
- never `manifest.json`, `cohorts.json` or anything under the plan directory: they are small,
  and the sealed plan is a reservation ledger that later planners read;
- never the tracked N1 records in the repository.

After such a removal, replaying N1's `status`, `interim` or `final` needs a restore first.

### Restore this snapshot

```sh
hf auth login
archive=$(mktemp -d /tmp/networkrlcd-n1-archive.XXXXXX)
hf download p-yan/networkrlcd-results-archive \
  --type dataset \
  --revision aa1b8d80fd66a3f52e88b59d589825f50d5e5dd2 \
  --include 'n1-stage-one-2026-10-10/*' \
  --local-dir "$archive"

# Use a new, empty directory. This recreates EMPTY_RECOVERY_DIRECTORY/results/.
bash "$archive/n1-stage-one-2026-10-10/restore.sh" /path/to/EMPTY_RECOVERY_DIRECTORY
```

`restore.sh` checks all nine part SHA-256s before extraction and refuses a populated
destination. Allow about 9 GB for the download and as much again for the restored tree. To
refill the local run, merge missing files only, as described above for the first snapshot.

