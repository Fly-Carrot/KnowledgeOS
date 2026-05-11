#!/usr/bin/env sh
set -eu

ROOT="${KNOWLEDGEOS_KERNEL_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"

for path in rules hooks registries memory sync schemas; do
  if [ ! -d "$ROOT/$path" ]; then
    echo "[BOOT_FAIL] missing kernel path: $ROOT/$path" >&2
    exit 1
  fi
done

if [ ! -f "$ROOT/schemas/phase-contract.md" ]; then
  echo "[BOOT_FAIL] missing phase contract" >&2
  exit 1
fi

echo "[BOOT_OK] KnowledgeOS kernel ready: $ROOT"
