#!/usr/bin/env sh
set -eu

ROOT="${KNOWLEDGEOS_KERNEL_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
PHASE="${1:-}"
NOTE="${2:-}"

case "$PHASE" in
  route|plan|review|dispatch|execute|report) ;;
  *) echo "usage: log-phase.sh <route|plan|review|dispatch|execute|report> [note]" >&2; exit 2 ;;
esac

mkdir -p "$ROOT/sync"
python3 - "$ROOT/sync/task-phases.ndjson" "$PHASE" "$NOTE" <<'PY'
import json, sys
from datetime import datetime, timezone
path, phase, note = sys.argv[1:4]
record = {
    "ts": datetime.now(timezone.utc).isoformat(),
    "phase": phase,
    "note": note,
}
with open(path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
PY

echo "[PHASE_OK] $PHASE"
