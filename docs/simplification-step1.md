# KnowledgeOS Simplification Step 1

Spec: SPEC-20261020-003
Task: T096
Scope: ordinary workflow and generated English entry only. Step 2 is not implemented.

## Behavior

The installed baseline still required the full lifecycle even with compact
guidance. The entry duplicated runtime reporting instructions. Red tests
reproduced the missing ordinary path, long global entry and the need to preserve
explicit write checks when reducing management calls.

The candidate extends existing run-task, eval-task, complete-task and agent-guide.
It does not introduce a service, orchestrator, replacement ledger or scheduler.

Explicitly adopted new work uses:

```sh
knowledgeos run-task --project-root . --task-id TASK --summary "Scoped work"
# Perform the actual work and relevant tests.
knowledgeos eval-task --project-root . --task-id TASK --run-id RUN --notes "Actual validation and limits"
knowledgeos complete-task --project-root . --task-id TASK --run-id RUN --summary "Result and remaining uncertainty"
```

Create a task only for new substantial work; reuse existing relevant work and
Spec/Plan. Newly planned paths still require check-route-write. Read-only questions
do not need a management task. Existing stricter instructions still win.

## Explicit Adoption

This release does not silently migrate existing projects. In a reviewed project
configuration, `project.execution_contract: ordinary-v1` selects the new default.
The existing `runtime_contract.phase_logging_required` must explicitly be false;
true or absent keeps the full lifecycle. Optional postflight can be selected with
the existing `postflight_required: false`; true remains a required hook.
These are existing project policy files, not a new toggle framework.

Do not change these settings for an active run. New runs bind their contract,
task scope and postflight requirement to command evidence. Old runs and missing
fields retain legacy behavior. Unknown/conflicting settings fail closed.
Use `agent-guide --legacy` when a returned run contract is legacy.

Enforced decision/effect policies, high-risk or unclassified-risk tasks, unsupported
task types and required capability stages retain full handling. Ordinary start
checks bounded declared paths; completion checks them again. Raw/secret paths,
path escapes, task scope changes and stale eval cannot use the shortcut.

## What Remains Unchanged

- Host permissions, explicit approvals, protected raw data and current write policy.
- Spec binding, required postflight, completion lock and freshness checks.
- Research provenance, important decisions and continuation notes.
- Existing CLI calls and historical records.
- Existing project AGENTS.md files and active task/run bindings.
- Communication Style, Context Continuity and Trajectory global-rule sections.

The global English entry is generated from one source. Only the unconditional
subagent-spawn sentence outside that block is replaced; delegation limits and
sensitive/external/cost boundaries remain.

## Verification Boundary

Step 1 intentionally keeps eval-task's current presence/freshness semantics.
Actual behavior must still be tested separately and reported honestly. This
release does not claim scientific or behavioral correctness merely because an
output exists. Step 2 will improve those validators after separate review.

No fake review/execute checkpoints are generated. Missing capability inventory
is reported as unknown coverage, not zero actual calls. Optional sync is
NOT_REQUIRED, never SYNC_OK.

## Regression Notes

- Initial six-test run: six failing assertions, including absent ordinary
  contract and long global entry; legacy behavior tests already passed.
- Matched temporary engineering and research fixtures execute real validation:
  management commands fall from 12 to 3 (75%); task creation and actual work are
  excluded identically from both counts. This is not a measured latency claim.
- Dry-run compares all project file bytes before and after.
- Negative tests cover raw data, escape paths, forged contracts, strict policy,
  stale/missing eval, required sync and active-run continuity.
- Some baseline tests depended on private maintainer tasks KOS-T009/KOS-T014.
  Their failures reproduce on the old installed release. They now use an
  initialized temporary runtime/project and explicit legacy capability fixtures,
  without deleting the original assertions or weakening product checks.

## Deployment And Rollback

Build a separate candidate release from the installed baseline, not the dirty
development checkout. Back up the global rule and launcher before switching.
Promote the runtime and matching generated rule only after regression checks.
Keep the previous release untouched.

Rollback restores only the launcher and rule backup; never roll back user work,
task evidence or chat history. No repository push, broad migration, or Step 2
implementation is included in this task.
