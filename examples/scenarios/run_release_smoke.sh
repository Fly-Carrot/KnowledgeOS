#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="$ROOT/bin/knowledgeos"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
RUNTIME="$WORK/runtime"
PROJECT="$WORK/project"
mkdir -p "$PROJECT"

"$BIN" init-os --root "$ROOT" --os-root "$RUNTIME" --json > "$WORK/init-os.json"
"$BIN" init-project --root "$ROOT" --project-root "$PROJECT" --name 'Release smoke' \
  --global-root "$RUNTIME/global-agent-fabric" \
  --capability-root "$RUNTIME/capability-layer" --json > "$WORK/init-project.json"
"$BIN" doctor --root "$ROOT" --project-root "$PROJECT" --summary
"$BIN" agent-guide --project-root "$PROJECT" > "$WORK/guide.md"
"$BIN" route-task --project-root "$PROJECT" --task-id T001 --json > "$WORK/route.json"
"$BIN" dispatch-task --project-root "$PROJECT" --task-id T001 --json > "$WORK/dispatch.json"
"$BIN" tool-registry --project-root "$PROJECT" --check-paths > "$WORK/tools.txt"

# A portable release must still reject writes to raw material.
set +e
"$BIN" check-route-write --project-root "$PROJECT" --task-id T001 \
  --path materials/raw/source.pdf --json > "$WORK/guard.json"
rc=$?
set -e
if [[ "$rc" -ne 2 ]]; then
  cat "$WORK/guard.json"
  printf 'Expected raw-material refusal (exit 2), got %s\n' "$rc" >&2
  exit 1
fi
printf 'RELEASE_PROJECT_OK distribution, fresh runtime/project, guide, route, dispatch, tools and raw write guard\n'
