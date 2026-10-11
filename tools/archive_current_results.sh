#!/usr/bin/env bash
# Owner-approved raw-results consolidation; never prune active/unverified evidence.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CAPTURE_PID="${1:?Pass the current margin collector PID (used only to wait, never signal)}"
HF_PYTHON="${HF_PYTHON:-$HOME/.hf-cli/venv/bin/python}"
export PYTHONDONTWRITEBYTECODE=1
export HF_XET_CHUNK_CACHE_SIZE_BYTES=0
export HF_XET_SHARD_CACHE_SIZE_LIMIT=134217728
cd "$ROOT"
[ -x "$HF_PYTHON" ] || { echo 'Set HF_PYTHON to a Python with huggingface_hub installed.' >&2; exit 2; }
for run in native-range-pilot-v1 native-ladder-pilot-v1; do
  prefix="${run}-$(date -u +%Y%m%d-%H%M%S)"
  "$HF_PYTHON" tools/results_storage.py archive "results/$run" --prefix "$prefix" --prune
done
prefix="native-margin-pilot-v1-$(date -u +%Y%m%d-%H%M%S)"
"$HF_PYTHON" tools/results_storage.py archive results/native-margin-pilot-v1 \
  --prefix "$prefix" --prune --wait-for-pid "$CAPTURE_PID" --wait-seconds 7200
"$HF_PYTHON" tools/results_storage.py status --check
printf 'ARCHIVE_consolidation_finished\n'
