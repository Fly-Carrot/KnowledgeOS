#!/usr/bin/env sh
set -eu

ROOT="${KNOWLEDGEOS_KERNEL_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
SUMMARY="${1:-${SUMMARY:-}}"
if [ -z "$SUMMARY" ]; then
  echo "usage: after-task.sh <summary>" >&2
  exit 2
fi

mkdir -p "$ROOT/sync" "$ROOT/memory"
python3 - "$ROOT" "$SUMMARY" "${USER_QUESTION_PROFILE_JSON:-}" <<'PY'
import json, sys
from datetime import datetime, timezone
root, summary, profile = sys.argv[1:4]
ts = datetime.now(timezone.utc).isoformat()
receipt = {"ts": ts, "summary": summary, "status": "synced"}
with open(f"{root}/sync/receipts.ndjson", "a", encoding="utf-8") as fh:
    fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")
with open(f"{root}/memory/handoffs.ndjson", "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"ts": ts, "summary": summary}, ensure_ascii=False) + "\n")
if profile:
    try:
        payload = json.loads(profile)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid USER_QUESTION_PROFILE_JSON: {exc}")
    with open(f"{root}/memory/user-question-profiles.ndjson", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": ts, "profile": payload}, ensure_ascii=False) + "\n")
PY

echo "[SYNC_OK] KnowledgeOS kernel postflight complete: $ROOT"
