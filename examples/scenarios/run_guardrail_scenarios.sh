#!/usr/bin/env bash
set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="$ROOT/bin/knowledgeos"
TMPDIR_ROOT="$(mktemp -d)"
PASS_COUNT=0
FAIL_COUNT=0

cleanup() {
  rm -rf "$TMPDIR_ROOT"
}
trap cleanup EXIT

print_header() {
  printf '\n===== CHECKPOINT: %s =====\n' "$1"
}

run_checkpoint() {
  local name="$1"
  local expected_exit="$2"
  shift 2
  local cmd=("$@")
  print_header "$name"
  printf 'command: %q' "${cmd[0]}"
  for arg in "${cmd[@]:1}"; do
    printf ' %q' "$arg"
  done
  printf '\n'
  set +e
  local output
  output="$("${cmd[@]}" 2>&1)"
  local status=$?
  set -e
  printf 'exit: %s\n' "$status"
  printf '%s\n' "$output"
  if [[ "$status" == "$expected_exit" ]]; then
    printf 'checkpoint_status: PASS\n'
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    printf 'checkpoint_status: FAIL expected_exit=%s actual_exit=%s\n' "$expected_exit" "$status"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

RUNTIME="$TMPDIR_ROOT/KnowledgeOSRuntime"
PROJECT="$TMPDIR_ROOT/DistractedAgentProject"
mkdir -p "$PROJECT"

print_header "setup-isolated-runtime"
printf 'command: %q init-os --root %q --os-root %q --json\n' "$BIN" "$ROOT" "$RUNTIME"
INIT_OS_OUTPUT="$($BIN init-os --root "$ROOT" --os-root "$RUNTIME" --json 2>&1)"
INIT_OS_STATUS=$?
printf 'exit: %s\n%s\n' "$INIT_OS_STATUS" "$INIT_OS_OUTPUT"
if [[ "$INIT_OS_STATUS" == "0" ]]; then
  printf 'checkpoint_status: PASS\n'
  PASS_COUNT=$((PASS_COUNT + 1))
else
  printf 'checkpoint_status: FAIL expected_exit=0 actual_exit=%s\n' "$INIT_OS_STATUS"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

print_header "setup-isolated-project"
printf 'command: %q init-project --root %q --project-root %q --name %q --global-root %q --capability-root %q --json\n' "$BIN" "$ROOT" "$PROJECT" "Distracted Agent Project" "$RUNTIME/global-agent-fabric" "$RUNTIME/capability-layer"
INIT_PROJECT_OUTPUT="$($BIN init-project --root "$ROOT" --project-root "$PROJECT" --name "Distracted Agent Project" --global-root "$RUNTIME/global-agent-fabric" --capability-root "$RUNTIME/capability-layer" --json 2>&1)"
INIT_PROJECT_STATUS=$?
printf 'exit: %s\n%s\n' "$INIT_PROJECT_STATUS" "$INIT_PROJECT_OUTPUT"
if [[ "$INIT_PROJECT_STATUS" == "0" ]]; then
  printf 'checkpoint_status: PASS\n'
  PASS_COUNT=$((PASS_COUNT + 1))
else
  printf 'checkpoint_status: FAIL expected_exit=0 actual_exit=%s\n' "$INIT_PROJECT_STATUS"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

run_checkpoint "doctor-summary-clean-project" 0 "$BIN" doctor --project-root "$PROJECT" --project-only --summary
run_checkpoint "create-spec-contract" 0 "$BIN" create-spec --project-root "$PROJECT" --title "Distracted agent guardrail spec" --intent "Keep spec, context, plan, checkpoint, eval, and sync evidence visible." --acceptance "run context includes the spec snapshot" --json
run_checkpoint "route-initialization-task" 0 "$BIN" route-task --project-root "$PROJECT" --task-id T001 --json
run_checkpoint "dispatch-initialization-task" 0 "$BIN" dispatch-task --project-root "$PROJECT" --task-id T001 --json
run_checkpoint "align-spec-before-run" 0 "$BIN" align-spec --project-root "$PROJECT" --task-id T001 --json
run_checkpoint "raw-material-mutation-blocked" 2 "$BIN" check-route-write --project-root "$PROJECT" --task-id T001 --path materials/raw/source.pdf --json
run_checkpoint "route-output-denied" 2 "$BIN" check-route-write --project-root "$PROJECT" --task-id T001 --path src/main.py --json
run_checkpoint "unrouted-task-human-triage" 2 "$BIN" route-task --project-root "$PROJECT" --task-type invented_unregistered_work --json
run_checkpoint "create-task-new-work-entry" 0 "$BIN" create-task --project-root "$PROJECT" --title "New unregistered work" --type invented_unregistered_work --output docs/new-work.md --acceptance "new task is visible for triage" --json
run_checkpoint "created-task-human-triage" 2 "$BIN" route-task --project-root "$PROJECT" --task-id T003 --json
run_checkpoint "reset-project-dry-run-visible" 0 "$BIN" reset-project --project-root "$PROJECT" --mode soft --dry-run --json

mkdir -p "$PROJECT/code" "$PROJECT/前期材料"
run_checkpoint "legacy-migration-plan-visible" 0 "$BIN" migrate-legacy-project --project-root "$PROJECT" --write-plan --json

print_header "run-envelope-created"
printf 'command: %q run-task --project-root %q --task-id T001 --summary %q --json\n' "$BIN" "$PROJECT" "Scenario guarded run."
RUN_OUTPUT="$($BIN run-task --project-root "$PROJECT" --task-id T001 --summary "Scenario guarded run." --json 2>&1)"
RUN_STATUS=$?
printf 'exit: %s\n%s\n' "$RUN_STATUS" "$RUN_OUTPUT"
if [[ "$RUN_STATUS" == "0" ]]; then
  RUN_ID="$(printf '%s' "$RUN_OUTPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
  printf 'run_id: %s\ncheckpoint_status: PASS\n' "$RUN_ID"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  RUN_ID=""
  printf 'checkpoint_status: FAIL expected_exit=0 actual_exit=%s\n' "$RUN_STATUS"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

if [[ -n "$RUN_ID" ]]; then
  run_checkpoint "dispatch-evidence-recorded" 0 "$BIN" dispatch-task --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --json
  run_checkpoint "capability-event-recorded" 0 "$BIN" capability-event --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --kind orchestrator --id maestro --purpose "Scenario records required orchestration visibility without invoking external work." --evidence "guardrail scenario"
  run_checkpoint "verify-context-without-plan-blocked" 2 "$BIN" verify-context --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --json
  run_checkpoint "plan-task-writes-checkpoint-plan" 0 "$BIN" plan-task --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --summary "Scenario plan loads spec snapshot and context before work." --json
  run_checkpoint "verify-context-passed" 0 "$BIN" verify-context --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --json
  run_checkpoint "completion-without-eval-blocked" 1 "$BIN" complete-task --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --summary "Should not complete yet."
  run_checkpoint "eval-task-generates-evidence" 0 "$BIN" eval-task --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --json
  for phase in route plan review dispatch execute report; do
    run_checkpoint "phase-$phase-recorded" 0 "$BIN" phase-task --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --phase "$phase" --status completed --note "Scenario recorded $phase public trace." --evidence "guardrail scenario"
  done
  run_checkpoint "verify-lifecycle-passed" 0 "$BIN" verify-lifecycle --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --json
  run_checkpoint "completion-after-lifecycle-and-eval-passed" 0 "$BIN" complete-task --project-root "$PROJECT" --task-id T001 --run-id "$RUN_ID" --summary "Scenario completed after eval and lifecycle evidence."
else
  print_header "completion-checks-skipped"
  printf 'exit: 1\nmissing run id; completion checkpoints skipped\ncheckpoint_status: FAIL\n'
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

printf '\n===== CHECKPOINT COMPLETE =====\n'
printf 'passed: %s\n' "$PASS_COUNT"
printf 'failed: %s\n' "$FAIL_COUNT"

if [[ "$FAIL_COUNT" == "0" ]]; then
  exit 0
fi
exit 1
