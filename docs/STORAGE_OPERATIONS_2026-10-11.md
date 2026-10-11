# Storage operations handoff — 2026-10-11

This is a progress record, not a claim that every archive has completed.
Read AGENTS.md and STORAGE_POLICY.md before acting on these paths.

## Applied

- Physical project budget: under 10,000,000,000 bytes; last checked around 4.8 GB.
- Large untracked acquisition/donor inputs and older raw captures moved by
  same-filesystem rename to `~/.cache/networkrlcd/working/results/`, with original
  ignored `results/` paths preserved by symlinks. No data bytes were changed.
- Completed, full-checksum-sealed margin peer directories relocate similarly.
  The live peer remains untouched. The collector was not stopped or rerun.
- Existing N1 stage-one snapshot at private HF revision
  `aa1b8d80fd66a3f52e88b59d589825f50d5e5dd2` was reverified (all shards, inventory
  bytes, and fresh download probe). 1,440 identical raw traces were pruned,
  totaling 8,116,250,827 logical bytes. Reports, ledgers, manifests, cohorts,
  derived JSON, models and frozen source snapshots remain. Its full seal needs
  raw restoration; see docs/storage-receipts/n1-stage-one-pruning-2026-10-11.json.

## In flight — inspect, do not duplicate

- Durable archive task: `6d40edf4-bbd9-4aba-855b-9767561416f4`.
  Worker: `bash tools/archive_current_results.sh 18770`.
  Log: `~/.cache/networkrlcd/logs/consolidation-2026-10-11.log`.
  Order: native-range-pilot-v1, native-ladder-pilot-v1, then native-margin-pilot-v1.
  Initial range prefix: `native-range-pilot-v1-20261011-233324`.
  Each snapshot receives its own pinned verified receipt before original pruning.
  A failure stops the queue safely; do not rerun against an existing prefix.
- Sealed-peer watcher task: `ae19ca4a-5b7d-4375-8d24-4d8968ed1513`.
  Collector PID: `18770`; PID is a point-in-time identifier, not permanent.
  The watcher scans sealed peers only and ends after the collector exits (four-hour
  maximum from watcher startup). It does not delete raw capture data.
- The margin archive waits up to two hours after reaching that queue step for the
  collector to exit and report.json + sessions.json to exist under
  results/native-margin-pilot-v1-report/. It computes no interim outcomes.

Do not interfere with the current capture/analysis or overwrite recipes/seals.
If a job fails, inspect its error and external staging/receipts first. Originals
for an incompletely verified snapshot remain. Review any restart with a new
prefix; do not treat uploaded partial shards as a complete recoverable archive.

## Follow-up

Confirm worker completion and all three compact receipts. Review/stage new
receipts and compact reports for GitHub; the worker NEVER commits or pushes Git.
Private raw archives are on demand, not an automatic full download in Codex.
Original source media and the complete donor remain external local dependencies;
these were not uploaded or pruned blindly. External relocation is not a backup
and does not itself reclaim machine-wide disk space.
