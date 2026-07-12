# Changelog

All notable KnowledgeOS changes are recorded here in a public, repository-friendly form.

KnowledgeOS is still a working prototype, so versions below describe capability milestones rather than packaged releases. The project follows this principle: classifications can remain extensible, but the lifecycle must remain fixed and observable.

## Unreleased

### Added

- `verify-subagents` now validates challenge-bound parent attestations against an immutable run catalog snapshot and emits `SUBAGENT_CATALOG_OK` only when marker, cleanup, role-contract, catalog-integrity, and native stability checks pass.
- A public Markdown and HTML subagent validation report records the 42-role runtime matrix without exposing local paths or runtime agent ids.
- Full Capability Dispatch Report: `dispatch-report` now treats `AGENT_DISPATCH_OK` as a complete mounted-capability report, not only a subagent summary.
- `capability-event` can record plugin/app, browser, Chrome, GitHub, security connector, MCP, skill, subagent, orchestrator, script, shell, and file-read capability use.
- `KOS_DECISION` prompt contract: every conversation should begin with a visible KnowledgeOS routing judgment covering project state, work class, required flow, and reason.
- `dispatch-report.md` now includes used/skipped counts by capability kind, skipped/not-needed reasons, dispatch plan evidence, evidence file paths, and gaps.
- Codex native runtime subagents: `codex-default`, `codex-explorer`, and `codex-worker` are registered globally and in new project templates.
- Maestro adapter-backed subagents: `maestro-*` role specs now live under `capability-layer/subagents/maestro/` and resolve to Codex `multi_agent_v1.spawn_agent` call packages.
- `subagent-adapter` emits `SUBAGENT_ADAPTER_OK` with runtime tool, runtime agent type, role prompt, and suggested capability-event evidence.
- `runtime-adapters` now reports registered Codex runtime subagents separately from CLI/builtin adapters.
- `dispatch-report` now treats `timed_out`, `blocked`, and `close_failed` subagent records as runtime gaps instead of successful agent invocations.
- HTML sidecar presentation modes: `default`, `minimal`, `bare`, and `fragment`, keeping evidence metadata mandatory while making visual layout project-selectable.
- Decision Graph module for public, auditable decision summaries without expanding the kernel.
- `decision-event` records plan branches, route selections, inserted steps, abandoned branches, rollbacks, deferred work, human decisions, risk tradeoffs, and final decisions into `decision-events.ndjson`, returning `DECISION_OK`.
- `decision-query` and `verify-decisions` make decision trees queryable and command-evidence checked.
- `render-html --kind decision-map` generates a presentation sidecar from the decision ledger while keeping NDJSON as the source of truth.
- `.agent-os/decision-policy.yaml` lets projects choose decision-graph strictness: `warn`, `enforce`, or `off` with a downgrade reason.
- `flow-summary` emits a readable, layered Mermaid Mission Flow with `FLOW_OK` for medium-or-larger task completion reports.
- `render-html --kind mission-flow` generates a self-contained Mission Flow HTML sidecar.
- `complete-task` now prepares `mission-flow.md` and returns `flow_mermaid` for medium, high, or complex tasks so agents can include a clear end-of-task flow diagram.
- Thread Plan Ledger module for chat-window-level, append-only natural-language planning across multiple tasks and runs.
- `thread-plan start/current/append/link-run/render` creates readable `Plan A / Plan B` and `Phase A / Phase B` planning maps, returning `THREAD_PLAN_OK`.
- `render-html` for HTML presentation sidecars without replacing Markdown, YAML, or NDJSON as canonical evidence.
- Composable HTML report manifests and fragments for receipt, handoff, rich-report, and stitched report outputs.
- `.agent-os/effect-policy.yaml` for project-level capability effect verification strictness.
- `artifact-assert` for verifying real artifact side effects after capability calls and emitting `EFFECT_OK`.
- `verify-effects` for checking capability-to-artifact effect evidence and emitting `EFFECT_VERIFY_OK`.
- Completion receipts and JSON now surface effect verification status alongside lifecycle, eval, context, and sync evidence.
- Root `CHANGELOG.md` as the public release and repair history for the project.
- Root changelog support in the local write policy and route-bound execution profile so future release notes are governed artifacts instead of unclassified writes.
- `phase-task` now emits a visible `CHECKPOINT_OK` marker in plain output and JSON.
- `capability-event` records observable MCP, skill, subagent, orchestrator, script, shell, and file-read use into the run ledger.
- `dispatch-task --run-id` binds capability dispatch decisions to a specific run.
- `trace-step` records public operational trace events such as `user_intent`, `doctor_gate`, `dispatch_plan`, `execution`, `eval`, `verify`, `complete`, and `sync`, returning a visible `TRACE_OK` marker.
- ComposioHQ Agent Orchestrator is registered as an external `orchestrator` adapter for future parallel subagent/worktree orchestration, without copying external runtime code into the kernel.
- The active product spec now captures the KnowledgeOS philosophy: small kernel, pluggable modules, optional apps, project-chosen strictness, and command-evidenced public checkpoints.

### Fixed

- Substantive subagent work is no longer treated as failed solely because a short marker-smoke wait elapsed; startup guidance now preserves agent ids, uses a multi-minute wait, performs one interrupt/recovery cycle, and reconciles late results.
- Adapter role prompts now enforce a bounded-subagent runtime boundary so specialist agents do not restart the full KnowledgeOS lifecycle or recursively delegate unless explicitly appointed as orchestrators.
- `dispatch-report` no longer labels safety-policy `blocked` events as runtime failures, separates resolved late-result gaps from active gaps, and reports unique agent ids separately from raw capability-event counts.
- Catalog verification no longer allows duplicate events for one role to compensate for another missing role.
- Catalog verification now rejects catalog drift, malformed marker evidence, missing adapter challenges, and attempts to lower the native stability floor below three; output explicitly states the parent-attested trust boundary.
- Runtime-gap reconciliation now requires a later `completed` event of the same capability kind, id, and purpose, so failed or unrelated events cannot erase a timeout.
- Adapter challenges are now single-use, standard runtime roles remain mandatory even if disabled before the first snapshot, snapshot metadata fails closed, and timeout recovery is one-to-one through `--recovers-event-id`.
- Snapshot metadata now has a complete integrity hash and validated timestamp/evidence model; failed or cancelled subagents are runtime gaps, never successful invocations.
- Prompt templates and generated startup prompts now require `AGENT_DISPATCH_PLAN`, `AGENT_DISPATCH_OK`, and full capability summaries for substantial work.
- `dispatch-task` limits subagent candidates to a small runtime-callable set instead of flooding plans with every Maestro role.
- `harness-audit --apply` can repair old project registries that are missing the three Codex native runtime subagents.
- Runtime subagent smoke failures can now be closed honestly through `capability-event --kind subagent --status timed_out` plus `AGENT_DISPATCH_OK` gap reporting.
- `dispatch-report` now reports `agents=0` with explicit skipped-agent reasons instead of making no-subagent runs look empty.
- `thread-plan render --format html` no longer duplicates the Thread Plan heading inside the report body; the HTML shell keeps the page title and the Markdown fragment keeps the plan title.
- `complete-task` now runs decision verification and blocks forged or structurally invalid decision evidence when project policy is enforced.
- `artifact-assert` now rejects nonexistent `capability_event_id` links instead of allowing forged capability-to-effect evidence.
- `verify-effects` now rejects existing effect assertions that reference missing capability events.
- `run-task` now allocates suffixed run ids when the same task is run more than once within the same second.
- Local Codex operator configuration can use the current `hooks` feature flag instead of the deprecated `codex_hooks` feature path.
- `verify-lifecycle` now blocks completion when dispatch evidence or required capability-stage evidence is missing.
- Root and template startup prompts now mention `TRACE_OK`, `CHECKPOINT_OK`, and `CAPABILITY_OK` as separate public evidence channels.

### Verified

- All 42 registered runtime-callable roles completed strict live role-contract validation; the three native Codex roles each completed three serial smoke rounds.
- The prior explorer timeout was reproduced as a workload-duration issue: explorer and default both exceeded the same fixed wait on substantive review, then returned valid recoverable results.

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
