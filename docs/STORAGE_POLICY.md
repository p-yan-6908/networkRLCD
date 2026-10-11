# Storage policy: 10 GB project budget

Owner-approved on 2026-10-11. The entire physical project tree, including hidden
state, must stay below **10,000,000,000 bytes** (10 decimal GB); begin cleanup at
8 GB. This is an agent/workflow guard, not an OS filesystem quota.

## Storage split

- **GitHub / local project:** code, reports, summaries, protocols/reservation
  ledgers, manifests, attribution, checksums, compact archive receipts and needed
  small models. Raw links are ignored. Put new compact reports under tracked
  `reports/` or explicitly review/stage the selected small files under `results/`.
- **Private Hugging Face:** raw immutable evidence in
  https://huggingface.co/datasets/p-yan/networkrlcd-results-archive.
  Each snapshot gets a fresh prefix and a pinned immutable revision, a file-level
  SHA-256 inventory, shard checksums and restoration instructions.
- **External local working area:** `~/.cache/networkrlcd/working/` for live capture
  data and required source/donor inputs. Upload/restore staging and receipts also
  live outside the repository. Relocation does NOT back up or free machine-wide
  disk space; actual space is reclaimed only after verified raw-file pruning.

## Budget check and future runs

```sh
python tools/results_storage.py status --check
python tools/results_storage.py status --check --planned-bytes 1000000000
# Large runs: choose a NEW output path outside the repository.
# --out "$HOME/.cache/networkrlcd/working/new-run"
```

The checker includes hidden files and deduplicates hardlinks; it does not follow
external symlinks. The 10 GB limit is the physical project footprint, not the
size of external data accessible through a link. Check free device space too.

## Current migration

The folder was about 44 GB when this policy was adopted. Completed raw captures
and required acquisition/donor working inputs are being moved outside the tree
with path-preserving symlinks. The running margin capture remains running: only
fully checksum-sealed completed peer directories are eligible for relocation;
its live peer is untouched. A bounded watcher relocates newly sealed peers.
No bytes, frozen recipes, source paths, reservation ledgers or seals are changed.

Original licensed source videos are NOT included in the raw-result uploads.
Required sources and complete donor evidence remain available through their
original paths in external working storage. Deleting them needs a separate
license/dependency review. See ARCHIVED_RESULTS.md for earlier snapshots.

## Archive and prune safety

The helper `tools/results_storage.py` uploads through the installed `hf` CLI;
its archival commands use the HF SDK for pinned inventory/checksum verification.
Use a Python environment with `huggingface_hub` for these commands (the installed
HF CLI's environment is sufficient). Authentication stays outside Git.

```sh
python tools/results_storage.py externalize results/COMPLETED_RUN        # dry run
python tools/results_storage.py externalize results/COMPLETED_RUN --apply
python tools/results_storage.py archive results/COMPLETED_RUN \
  --prefix UNIQUE_NEW_SNAPSHOT_PREFIX                                  # backup + prune plan
# After reviewing the scope, --prune applies checksum-only raw-file removal.
```

- Existing verified N1 snapshot may be reused only after rechecking its pinned
  remote inventory, checksums, inventory bytes and a fresh download probe.
- New snapshots never overwrite a prefix. Staging is streamed in 1 GiB shards,
  uploaded and checked individually, so no second full capture is staged locally.
- The entire snapshot must pass remote checks before ORIGINAL files are pruned.
  Deleting an already verified temporary upload shard is not deleting evidence.
- `frame_events.json` and `sender_observations.json` are large RAW traces, not
  summaries, despite their JSON suffix. They and compressed event logs are
  eligible only after complete remote verification; derived/cohort/manifest JSON,
  frozen source snapshots and models remain.
- Local removal requires identical SHA-256, size and stable file state immediately
  before unlink. Changed/new/unsafe paths are retained. Protected metadata,
  models, source inputs and donor dependencies remain.
- Keep full file inventories and prune logs in the external receipt cache, plus
  compact pinned receipts in `docs/storage-receipts/` for GitHub/Codex.
- The approved consolidation worker is `bash tools/archive_current_results.sh CAPTURE_PID`.
  It archives range and ladder captures first, then waits (at most two hours) for
  the margin collector to exit and its final reports to exist. It never reruns
  a capture or computes interim outcomes. Failed verification stops the worker
  without deleting that snapshot's originals. Check its log and receipts.
- Successfully pruned run roots get `ARCHIVED_RAW.json` identifying their pinned
  remote copy and removed-file count; this does not replace or rewrite a seal.
- Pruned historical folders are partial evidence even when manifest.json remains.
  Restore first for raw replay or a full seal audit; NEVER change old seals.
- Do not prune the current margin capture until it has finished and the final
  `report.json` and `sessions.json` have been generated from complete evidence.

## Restoration and Codex Cloud

Download only the requested snapshot at its receipt's **pinned revision**, into
external staging. Verify SHA256SUMS, concatenate tar parts in lexical order and
extract into a NEW EMPTY external directory. Verify each restored file against
file-index.json (or the older file-sha256.txt). Review merges; never overwrite
changed local evidence. Existing older restore.sh scripts remain valid.

Codex can read committed reports without raw data. A raw replay needs access to
this private HF dataset and a read-only credential configured securely in the
cloud environment, not committed to Git. Avoid automatic full-archive downloads.
