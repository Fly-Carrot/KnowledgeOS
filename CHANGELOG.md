# Changelog

All notable KnowledgeOS changes are recorded here in a public, repository-friendly form.

KnowledgeOS is still a working prototype, so versions below describe capability milestones rather than packaged releases. The project follows this principle: classifications can remain extensible, but the lifecycle must remain fixed and observable.

## Unreleased

### Added

- Root `CHANGELOG.md` as the public release and repair history for the project.
- Root changelog support in the local write policy and route-bound execution profile so future release notes are governed artifacts instead of unclassified writes.
- `phase-task` now emits a visible `CHECKPOINT_OK` marker in plain output and JSON.
- `capability-event` records observable MCP, skill, subagent, orchestrator, script, shell, and file-read use into the run ledger.
- `dispatch-task --run-id` binds capability dispatch decisions to a specific run.

### Fixed

- Local Codex operator configuration can use the current `hooks` feature flag instead of the deprecated `codex_hooks` feature path.
- `verify-lifecycle` now blocks completion when dispatch evidence or required capability-stage evidence is missing.

## 0.5.0 - System Hardening And Kernel Repair

### Added

- `harness-audit` for scanning managed projects for mount drift, missing hooks, missing control-plane files, lifecycle router drift, and missing archive write guards.
- Safe harness repair mode with backups before rewriting project control-plane files.
- Doctor validation for executable postflight hooks.
- Doctor validation for boot kernel skeleton directories and the phase contract required by the shared-fabric boot hook.
- Minimal live kernel skeleton directories for registry and schema contracts.

### Fixed

- Projects that still mounted a retired pre-OS shared-fabric root could pass local eval but fail required postflight sync.
- `doctor` could previously pass while `before-task.sh` failed because the live kernel root was missing `registries/` or `schemas/`.
- Shared-fabric boot now reports `[BOOT_OK]` when the live kernel skeleton is present and blocks clearly when it is not.

### Removed

- Retired the legacy pre-OS skills root from the active runtime path after dependency scanning.
- Removed stale generated runtime context that could reintroduce the retired root into new agent sessions.

### Verified

- KnowledgeOS doctor passes after kernel repair.
- Shared-fabric `before-task.sh` returns `[BOOT_OK]` after skeleton restoration.
- Full unit test suite passes after hardening coverage was added.

## 0.4.0 - Spec, Context, And Lifecycle Gates

### Added

- `create-task` for official task intake when no ready task fits a new user request.
- `phase-task` for public lifecycle evidence across `route`, `plan`, `review`, `dispatch`, `execute`, and `report`.
- `verify-lifecycle` to reject missing phases, invalid phase records, and skipped phases without reasons.
- `create-spec` and `align-spec` for durable user intent.
- `context-pack`, `plan-task`, and `verify-context` so every run can bind itself to the current spec and execution plan.
- Command-event evidence for eval and phase logging, making hand-written ledgers insufficient for completion.

### Changed

- `complete-task` now enforces eval evidence, declared outputs, lifecycle evidence, context evidence, and required postflight before marking a task completed.
- `reopen-task` is documented as same-task rerun only; new work should use `create-task`.
- Medium or risky work now records checkpoint-visible public decision traces rather than hidden chain-of-thought.

### Fixed

- Agents could previously finish a task without recording required phases.
- Agents could manually append eval markers without command evidence.
- Agents could drift away from the user's original spec after run start.
- Agents could misuse `reopen-task` as a substitute for creating a new task.

## 0.3.0 - Route-Bound Execution Guard

### Added

- Route-bound execution guard through `route-task`, `dispatch-task`, and `check-route-write`.
- Workflow router profiles for fixed lifecycle routing by task type.
- Write policy sections for immutable inputs, controlled outputs, human-gated paths, and receipt-required paths.
- Tool and capability visibility through `tool-registry` and dispatch policy.
- Human consultation checkpoints for medium-risk, release, external-write, destructive, and browser-facing work.

### Changed

- Task classification remains open, but task lifecycle routing must be explicit.
- `.agent-os/` became the local project control plane rather than a content dump.
- Capability orchestration is represented as MCP, skills, workflows, subagents, agents, and registries under the capability layer.

### Fixed

- Unclassified writes are blocked rather than silently accepted.
- Critical control-plane edits require a human gate.
- Raw materials and archive storage are protected from default context loading.

## 0.2.0 - Project Utilities And Migration Tools

### Added

- `reset-project` for reversible soft or hard reset previews before removing OS state.
- `migrate-legacy-project` for planning old-project reorganization before moving files.
- `archive-legacy-project` for cold storage of historical files that should not be read by default.
- Archive read and write policies to keep legacy outputs available but out of normal agent context.
- Guardrail scenarios that simulate distracted-agent behavior.
- `doctor --summary` for low-token health reporting.

### Changed

- Old project migration became plan-first rather than patch-by-patch cleanup.
- Cold archive became a first-class storage strategy for legacy code, stale generated content, and superseded outputs.

### Fixed

- Legacy projects could previously mix raw materials, derived knowledge, outputs, reports, and agent state without a clear lifecycle boundary.
- Agents could over-read old archives as if they were current project context.

## 0.1.0 - Minimal Runnable KnowledgeOS

### Added

- Initial project control-plane template under `.agent-os/`.
- Minimal governance-core template with rules, hooks, registries, schemas, memory lanes, and sync ledgers.
- Capability-layer template for MCP, skills, workflows, subagents, agents, and registries.
- Project folder model separating materials, knowledge, source code, tests, data, outputs, reports, docs, and OS control state.
- `doctor` for validating public files, project files, schemas, policies, tasks, decisions, evals, artifacts, tool registry, and workflow router state.
- `init-os` and `init-project` for generating clean runtime and project scaffolds.
- Public architecture documentation, quickstart, guardrail docs, workflow router docs, tool registry docs, and reset/migration docs.

### Design Notes

- KnowledgeOS is an intent-driven operating layer, not a replacement for the host operating system.
- Natural language is the shell; the `knowledgeos` CLI is the system-call layer; `.agent-os/` is the project control plane.
- The shared-fabric kernel model handles boot, phase, memory, receipts, and sync.
- The capability layer makes external tools visible and governable rather than hidden in ad hoc prompts.
