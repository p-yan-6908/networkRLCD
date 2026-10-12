# Agent instructions

## Mandatory storage policy (owner-approved 2026-10-11)

The physical `/Users/pyan/networkRLCD` project tree must remain below **10 GB
(10,000,000,000 bytes)**, including hidden caches and environments. Start cleanup at
8 GB. See `storage_policy.json` and [docs/STORAGE_POLICY.md](docs/STORAGE_POLICY.md).

- Before a large run/download, run `python tools/results_storage.py status --check`
  and account for its projected output with `--planned-bytes N`.
- Large captures, raw media, archive shards, and restore/download staging belong
  **outside this repository**, normally `~/.cache/networkrlcd/`. This external
  working cache is still local disk, NOT a verified backup; bound and prune it too.
- New multi-GB runs must use an external `--out`; do not refill `results/` with raw
  captures. Keep compact reports, summaries, protocols, manifests, provenance,
  checksums, archive receipts, and needed small models in Git.
- Raw evidence belongs in the existing **private** HF dataset
  `p-yan/networkrlcd-results-archive`. Preserve old snapshots and pin each new
  snapshot's immutable revision. Never overwrite prior evidence.
- Never delete active/unarchived bytes. Upload, verify every remote shard SHA-256
  and inventory, perform a fresh download check, then rehash each local candidate
  immediately before deletion. Keep drifted/new files and an audit receipt.
- Original licensed media and complete donor dependencies are not ordinary
  prune candidates. Review their licenses/dependencies; keep required working
  copies outside the project instead of deleting or uploading them blindly.
- Completed sessions may be relocated to the external working cache with
  path-preserving `results/` symlinks. Do not commit those machine-local links.
  A relocated session remains complete; an archived/pruned one does not. Restore
  before seal verification or raw replay; never rewrite a seal to conceal pruning.
- Do not download all archives automatically in Codex Cloud. Use committed
  summaries by default and restore only the pinned data needed for a task.
- Do not stop active captures, rerun the completed margin capture, or change its
  frozen recipes. Margin finished 192/192 sealed sessions; its final reports are
  under `results/native-margin-pilot-v1-report/`. Its raw archive is still pending:
  only the verified archive worker may prune matching raw evidence.

## Verification

Python 3.12 / uv. `uv sync --frozen --extra dev`; run relevant tests, then the
appropriate broader suite. Storage helper probes:
`uv run --frozen pytest -q tests/test_results_storage.py`.
Lint: `uv run --frozen ruff check tools/results_storage.py tests/test_results_storage.py`.
See README and the registered experiment protocols for research boundaries.
