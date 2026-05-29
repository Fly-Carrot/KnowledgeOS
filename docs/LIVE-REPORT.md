# KnowledgeOS Live Construction Report

This file is the real-time construction log for the local KnowledgeOS build.

## 2026-05-09 - Milestone: Safe Skeleton

Status: in progress

What was created:

- public-facing `README.md` for the clean KnowledgeOS concept;
- `.agent-os/` control-plane seed for this KnowledgeOS workspace;
- `templates/` for reusable user-facing project scaffolds;
- `.knowledgeos-local/` for private local migration inventory;
- `.gitignore` boundaries to prevent local secrets and migration snapshots from entering a public release.

Design decision:

- Keep public KnowledgeOS clean and generic.
- Keep machine-specific workflow inventory separate under `.knowledgeos-local/`.
- Treat Agent Shared Fabric as a kernel module, not as content copied into every project.

Next steps:

- Fill architecture and write-guard documents.
- Inventory the current local shared-fabric kernel module and capability layer.
- Define the first migration task list.

## 2026-05-09 - Milestone Update: Public Template Boundary

Status: completed for initial skeleton

Changes:

- Marked `.agent-os/runs/`, `.agent-os/receipts/`, `.agent-os/handoffs/`, and `.agent-os/inbox/` as local-only through `.gitignore`.
- Added a user-facing `templates/project-control-plane/AGENTS.md`.
- Added portable `.agent-os` template files with `CHANGE_ME` placeholders instead of local personal paths.
- Confirmed that real local workflow migration notes remain under `.knowledgeos-local/`.

Why this matters:

- The KnowledgeOS repository can contain clean public templates.
- The repository can keep a sanitized minimal self-management control plane while local runtime evidence stays out of public release.
- Personal paths and private runtime state are less likely to leak into a public release.

## 2026-05-09 - Milestone Update: Local Registry Inventory

Status: completed

Observed local registry surface:

- 8 MCP server ids visible in the local shared-fabric MCP registry.
- 5 skill source ids visible in the local shared-fabric skill source registry.
- 4 workflow source ids visible in the local shared-fabric workflow registry.
- Branch Builder exists as a generated shared-fabric skill with scripts for state initialization, dispatch preparation, resolution, checkpointing, and validation.

Safety note:

- Only ids and structural roles were recorded.
- No secret values or private runtime databases were copied.

## 2026-05-09 - Milestone: Executable Control Plane

Status: initial implementation completed

Files added:

- `knowledgeos/__init__.py`
- `knowledgeos/__main__.py`
- `knowledgeos/cli.py`
- `bin/knowledgeos`
- `tests/test_knowledgeos_cli.py`
- `docs/executable-control-plane.md`

Commands implemented:

- `doctor`
- `init-project`
- `check-write`
- `run-task`
- `receipt`

Safety behavior:

- `init-project` preserves existing project files by default.
- `--force` is required to overwrite, and existing files are backed up first.
- `check-write` blocks immutable paths and human-gated paths through exit code `2`.
- `run-task` creates a structured run envelope instead of directly executing arbitrary work.

Verification:

- Python syntax compile passed.
- CLI public `doctor` passed.
- Unit tests passed: 5 tests, 0 failures.

Current limits:

- The CLI uses a minimal parser for KnowledgeOS templates, not full YAML semantics.
- `run-task` starts a run envelope; it does not yet dispatch an agent.
- Write guard is advisory/classification-based; it does not yet intercept filesystem writes automatically.

Executable control plane test correction:

- `doctor` caught local absolute paths in public CLI examples.
- Public docs were changed to use generic `./bin/knowledgeos` and `/path/to/KnowledgeOS` examples.
- This validates the public leakage scan as an active safety check, not just a checklist item.

Executable control plane developer ergonomics update:

- Added top-level `AGENTS.md` for KnowledgeOS development discipline.
- Added `Makefile` targets: `doctor`, `test`, and `smoke`.
- Updated README with the executable control-plane command surface.

Executable control plane cleanliness update:

- Added Python cache exclusions to `.gitignore`.
- Updated `bin/knowledgeos` to run Python with bytecode writing disabled.
- Updated `Makefile` test target to run with bytecode writing disabled.
- Cleared generated Python cache files.
- Final smoke test confirmed no `__pycache__` or `.pyc` files remained after the check.

## 2026-05-09 - Milestone: Doctor Guardrails

Status: initial implementation completed

Files changed or added:

- `knowledgeos/cli.py`
- `tests/test_knowledgeos_cli.py`
- `docs/doctor-guardrails.md`
- `templates/project-control-plane/AGENTS.md`
- `Makefile`
- `README.md`
- `docs/quickstart.md`

Commands added:

- `doctor --project-root` project validation
- `agent-guide`

Project validation now checks:

- required project control-plane files;
- unresolved `CHANGE_ME` placeholders;
- workspace identity and project root;
- project metadata;
- Shared Fabric kernel and capability-layer links;
- runtime contract booleans;
- exact phase keys;
- write-policy coverage;
- task ids, statuses, and required fields;
- decision ids;
- eval profiles;
- artifact ids;
- capability guardrails such as `execution_mode: ask`.

Important risk found and fixed:

- Generic `CHANGE_ME` replacement could accidentally corrupt more specific placeholders.
- Templates now use explicit placeholders such as `CHANGE_ME_PROJECT_NAME`, `CHANGE_ME_PROJECT_ROOT`, and `CHANGE_ME_GLOBAL_AGENT_FABRIC_ROOT`.
- Tests now verify that unresolved placeholders are caught by `doctor --project-root`.

Verification:

- Unit tests expanded from 5 to 8 tests.
- `make smoke` now runs unified `doctor`, route validation, and the full test suite.
- Current smoke passes.

Doctor guardrails final cleanup:

- Public required-file checks now include the Executable control plane and Doctor guardrails documents.
- The public leakage scanner no longer hardcodes a personal home path in source; it builds the active home-path marker at runtime.
- Final scan found no `home-directory`, API-key, secret, token, or secrets-config markers in public/source surfaces checked.
- Final cache check found no `__pycache__` or `.pyc` files after smoke.

## 2026-05-10 - Milestone: Unified Doctor And Workflow Router

Status: implementation in progress

Files changed or added:

- `knowledgeos/cli.py`
- `tests/test_knowledgeos_cli.py`
- `docs/doctor-guardrails.md`
- `docs/workflow-router.md`
- `.agent-os/workflows/router.yaml`
- `templates/project-control-plane/.agent-os/workflows/router.yaml`
- `templates/project-control-plane/AGENTS.md`
- `Makefile`
- `README.md`
- `docs/quickstart.md`

Changes:

- Unified user-facing validation under `doctor --project-root`.
- Removed the legacy compatibility alias and kept `doctor --project-root` as the only validation entrypoint.
- Added `route-task` so agents can resolve a task id/type into an observable workflow path before dispatch.
- Added route profiles for current local task types and a minimal template route for new projects.
- Updated smoke to run `doctor`, `route-task`, and tests.

Design note:

- Hooks enforce boot, phase, and postflight boundaries.
- Doctor validates the control plane before work.
- Route-task chooses the visible workflow path.
- Skills and subagents remain dispatch-time capabilities, not the structure validator.

## 2026-05-10 - Milestone: Tool Registry And Orchestration Visibility

Status: implementation in progress

Files changed or added:

- `knowledgeos/cli.py`
- `tests/test_knowledgeos_cli.py`
- `docs/tool-registry.md`
- `.agent-os/tool-registry.yaml`
- `templates/project-control-plane/.agent-os/tool-registry.yaml`
- `.agent-os/workflows/router.yaml`
- `.agent-os/evals.yaml`
- `templates/project-control-plane/AGENTS.md`
- `Makefile`
- `README.md`
- `docs/quickstart.md`
- `docs/architecture.md`
- `docs/orchestration.md`

Changes:

- Removed the duplicate legacy project-validation command after equivalence tests.
- Added `tool-registry` for observable MCP / skill / workflow / orchestration / subagent configuration.
- Added secret-marker checks for tool registry entries.
- Added human-gate checks for risky tools.
- Added `execution_mode: ask` checks for orchestration and subagent entries.
- Added optional path-existence checks with `--check-paths`.
- Updated smoke to run `doctor`, `route-task`, `tool-registry`, and tests.

Current local tool summary:

- MCP: chrome-devtools, context7, markitdown, notebooklm, zotero, qgis-disabled.
- Orchestration: maestro.
- Memory: mempalace.
- Skills: generated shared-fabric skills, curated current workflow skills, curated top50 skills, nature skills, awesome-skills index.
- Subagent/planning: branch-builder.

Design note:

- The tool registry is visibility and validation, not hidden execution.
- Actual runtime invocation still follows task intent, capability match, route profile, human gate, and postflight evidence.

## 2026-05-10 - Milestone: Route-Bound Execution Guard

Status: verified locally

Files changed or added:

- `knowledgeos/cli.py`
- `tests/test_knowledgeos_cli.py`
- `docs/route-bound-execution-guard.md`
- `docs/architecture.md`
- `.agent-os/tasks.yaml`
- `.agent-os/evals.yaml`
- `.agent-os/workflows/router.yaml`
- `.agent-os/write-policy.yaml`
- `templates/project-control-plane/.agent-os/evals.yaml`
- `templates/project-control-plane/.agent-os/workflows/router.yaml`
- `templates/project-control-plane/.agent-os/write-policy.yaml`
- `templates/project-control-plane/AGENTS.md`
- `README.md`
- `docs/quickstart.md`
- `Makefile`

Changes:

- Added `check-route-write` to enforce both project write policy and task route `allowed_outputs`.
- Hardened `run-task` so official run envelopes require a routed task with status `ready` or `in_progress`.
- Added `complete-task` so task completion requires a passed eval by default.
- Added run-id traversal protection for `complete-task`.
- Extended `doctor` to validate route `eval_profile` references and non-empty `allowed_outputs`.
- Added `KOS-T008` and the `route_bound_guard_task` eval profile.
- Updated template initialization route to use route-bound write checking and eval-bound completion.
- Updated quickstart, README, architecture notes, and smoke targets.

Extreme checks performed:

- Allowed route write returns `allow`.
- Out-of-route but otherwise writable path returns `route_output_denied`.
- Immutable raw-material path returns `deny`.
- Completion without `eval-task` generated `Status: passed` is blocked.
- `../` style run-id traversal is blocked.
- Completion after `eval-task` passes succeeds and updates task/run/receipt/handoff state.

Verification:

- `python3 -B -m py_compile knowledgeos/cli.py` passed.
- Unit tests expanded from 13 to 16 tests.
- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v` passed.
- `doctor --root .` passed.
- `doctor --root . --project-root .` passed.
- `make smoke` passed.

Design note:

- KnowledgeOS is still not an OS-level sandbox. It is now a stronger route-bound harness: agents can see the route, the allowed outputs, the eval gate, and the receipt trail before and after mutation.

## 2026-05-10 - Milestone: Capability-Oriented Orchestration

Status: verified locally

Files changed or added:

- `knowledgeos/cli.py`
- `tests/test_knowledgeos_cli.py`
- `docs/capability-orchestration.md`
- `docs/orchestration.md`
- `docs/architecture.md`
- `.agent-os/dispatch-policy.yaml`
- `.agent-os/tool-registry.yaml`
- `.agent-os/tasks.yaml`
- `.agent-os/evals.yaml`
- `.agent-os/workflows/router.yaml`
- `templates/project-control-plane/.agent-os/dispatch-policy.yaml`
- `templates/project-control-plane/.agent-os/tool-registry.yaml`
- `templates/project-control-plane/.agent-os/evals.yaml`
- `templates/project-control-plane/AGENTS.md`
- `AGENTS.md`
- `README.md`
- `docs/quickstart.md`
- `Makefile`

Changes:

- Added `.agent-os/dispatch-policy.yaml` as the observable capability-selection policy.
- Added `dispatch-task` to build a dispatch plan from task, route, dispatch policy, and tool registry.
- Added tool registry `task_fit` and `capability_fit` metadata.
- Added `KOS-T009` for capability-oriented orchestration.
- Added `capability_orchestration_task` eval profile.
- Added `capability_orchestration` route profile.
- Updated templates so new projects have dispatch policy and consultation behavior.
- Updated product language so agents pause at consultation checkpoints, state their recommendation, name the tradeoff, and ask whether to proceed.

Verified dispatch order for complex orchestration work:

```text
branch_builder -> orchestrator -> subagent -> mcp -> skill -> script
```

Consultation checkpoints:

```text
execute, complete
```

Verification:

- `python3 -B -m py_compile knowledgeos/cli.py` passed.
- Unit tests expanded from 16 to 18 tests.
- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v` passed.
- `doctor --root . --project-root .` passed with 230 checks.
- `make smoke` passed.

Design note:

- Route-bound guard made execution safer.
- Capability orchestration makes capability selection more intelligent and legible.
- The next natural step is a richer scheduler/evaluator that can compare multiple dispatch alternatives and record why one was selected.

## 2026-05-11 - Milestone Update: Public GitHub Archive Boundary

Status: completed

Changes:

- Added `docs/agentos-architecture.md` as a GitHub-ready architecture and manifesto document.
- Replaced app-specific wording with a generic future Workbench/Desktop App model.
- Sanitized tracked `.agent-os/` control files so public paths are relative to the repository.
- Updated `.gitignore` so local generated kernel roots, capability roots, run receipts, handoffs, inbox items, and private inventories do not enter the public archive.

Why this matters:

- The public repository can communicate the AgentOS idea without binding the project to one local machine or one specific desktop app.
- The repository can remain useful as source, documentation, and scaffolding while runtime evidence stays local.

## 2026-05-12 - Milestone Update: Task Intake And Lifecycle Gates

Status: implemented in isolated worktree; verified with targeted regression tests before full regression.

Changes:

- Added `create-task` as the official intake path for new work when no ready task fits.
- Kept `reopen-task` scoped to same-task reruns after rejected outputs.
- Added `.agent-os/phase-policy.yaml` and the matching project template file.
- Added `phase-task` to write public lifecycle evidence to `.agent-os/runs/<RUN_ID>/phases.ndjson`.
- Added `verify-lifecycle` to enforce `route -> plan -> review -> dispatch -> execute -> report` before completion.
- Hardened `complete-task` so it now requires eval, declared outputs, lifecycle verification, and required postflight.
- Added explicit pending-postflight escape hatch through `--allow-pending-postflight "<reason>"`; the reason is written into receipt evidence.
- Updated guardrail scenarios so distracted agents must create new tasks and record phase evidence before completion.

Design note:

- Phase notes are public decision traces, not hidden chain-of-thought. The OS records what was decided, what evidence was used, and why a phase was skipped when applicable.

## 2026-05-12 - Hardening Note: Checkpoint Spoofing Audit

Status: reproduced and patched in the task lifecycle gate branch.

Findings reproduced before the patch:

- A forged `eval.md` with `Generated By: knowledgeos eval-task` plus hand-written `phases.ndjson` could complete.
- A weakened `.agent-os/phase-policy.yaml` with no required phases could complete.
- A direct edit from `postflight_required: true` to `false` could complete without `[SYNC_OK]`.

Hardening added:

- `run-task`, `eval-task`, and `phase-task` now write command evidence into `.agent-os/runs/<RUN_ID>/command-events.ndjson`.
- `complete-task` requires matching `eval-task` command evidence, not just text inside `eval.md`.
- `verify-lifecycle` requires matching `phase-task` command evidence for every required phase.
- `verify-lifecycle` rejects weakened phase policies; required phases must stay `route -> plan -> review -> dispatch -> execute -> report` and skipped phases must require a reason.
- `complete-task` rejects disabled postflight contracts; `postflight_required` must remain `true` for managed projects with fabric links.
- Default write policy human-gates direct edits to run evidence files and critical control-plane files, including `tasks.yaml`, `evals.yaml`, `read-policy.yaml`, `write-policy.yaml`, `dispatch-policy.yaml`, `tool-registry.yaml`, `workflows/router.yaml`, `phase-policy.yaml`, and `fabric-link.yaml`.

Residual boundary:

- This is still a harness-level guard, not a kernel permission boundary. A fully malicious process with arbitrary filesystem write access can forge local files. Strong tamper-proofing would require a protected external ledger, signing key, or OS-level sandbox.

## 2026-05-12 - Milestone Update: Spec Context Plan Gate

Status: implemented in isolated worktree; validation in progress.

Changes:

- Added `create-spec` and `align-spec` so durable user intent can live under `.agent-os/specs/` instead of only in a pasted prompt.
- Added `.agent-os/specs.yaml` to the project control plane and project template.
- `run-task` now writes `spec-snapshot.md` and `context-pack.md` for each run.
- Added `context-pack`, `plan-task`, and `verify-context` commands.
- Hardened `complete-task` so completion now requires command-generated spec/context/plan evidence before postflight.
- Added spec drift detection: if the active spec changes after a run snapshot, completion fails until the context is realigned.
- Human-gated direct writes to spec registry, spec bodies, context packs, spec snapshots, and plans.
- Updated guardrail scenarios to include checkpoint-visible spec creation, spec alignment, context verification, and plan generation.

Design note:

- Spec and plan records are public execution contracts. They preserve attention and intent without storing hidden chain-of-thought.

## 2026-05-13 - Hardening Note: Harness Mount Drift Audit

Status: implemented and applied locally across managed KnowledgeOS projects.

Bug reproduced:

- Project4 task `T005` had passed eval, lifecycle, and context checks, but could not claim `[SYNC_OK]` because `.agent-os/fabric-link.yaml` still pointed at the legacy pre-OS shared-fabric root.
- Several other managed projects had newer KnowledgeOS paths but no executable `global-agent-fabric/hooks/after-task.sh`, so required postflight would have failed later.
- Older project routers still lacked the newer `context-pack`, `plan-task`, `phase-task`, `verify-context`, and `verify-lifecycle` route steps.

Changes:

- Added `harness-audit` to scan managed projects for mount drift, missing kernel hooks, missing control-plane files, old lifecycle routers, and missing archive write guards.
- `harness-audit` defaults to dry-run and requires `--apply` before mutation.
- Added safe repair behavior that backs up existing project files under `.agent-os/backups/harness-audit-<timestamp>/` before rewriting mount/router/write-policy files.
- Exposed executable hooks under `global-agent-fabric/hooks/` so projects mounted to the canonical governance root can complete required postflight.
- Added doctor validation for required executable postflight hooks.

Applied local repair:

- Repaired Project4 and David Gallery legacy pre-OS governance roots.
- Repaired Fundings, Nanling Consulting, Project5.5, David Gallery, Project4, and KnowledgeOS mount/hook audit state.
- Upgraded old workflow routers for David Gallery, Fundings, Nanling Consulting, and Project5.5.
- Re-ran Project4 `T005` completion after repair; it now returns `sync_status: SYNC_OK`.

Validation:

- `harness-audit --json` reports `status: ok` and `issue_count: 0` for managed projects.
- Doctor passes for David Gallery, Fundings, Nanling Consulting, Project4, Project5.5, and KnowledgeOS.
- Targeted regression test `test_harness_audit_repairs_legacy_mount_and_missing_control_files` passes.

## 2026-05-13 - Cleanup Note: Retire Legacy Pre-OS Skills Root

Status: implemented locally after dependency scan.

Bug reproduced:

- The old local skills/root folder still existed even though KnowledgeOS now owns kernel, capability, workflow, and postflight behavior.
- Several legacy `.agents/sync/codex-context.md` files could still inject the old boot contract into future agents.
- Codex prompt history and Gemini project registry still had entries that could resurrect the old startup path.

Changes:

- Deleted the old local skills/root folder after confirming managed KnowledgeOS projects no longer mount it.
- Deleted stale generated `.agents/sync/codex-context.md` files that referenced the retired root.
- Removed the retired root from Gemini's project registry.
- Removed stale startup snippets from Codex prompt history.
- Updated the GitHub AI Radar runtime snapshot to point at the KnowledgeOS kernel.
- Removed `.knowledgeos-local/`, which was a migration-era local inventory cache, not an active OS component.

Validation:

- The retired root no longer exists on disk.
- `harness-audit --json` reports `status: ok` and `issue_count: 0`.
- Doctor passes for all managed KnowledgeOS projects.

## 2026-05-13 - Boot Repair: Restore Kernel Skeleton Directories

Status: implemented locally after reproducing the boot hook failure.

Bug reproduced:

- `knowledgeos doctor --project-root KnowledgeOS --summary` passed.
- `global-agent-fabric/hooks/before-task.sh` failed before `[BOOT_OK]` because the live kernel root lacked `global-agent-fabric/registries`.
- The same hook would also require `global-agent-fabric/schemas`, including `schemas/phase-contract.md`.

Root cause:

- The canonical governance-core template already defined `registries/` and `schemas/`, but the live migrated `global-agent-fabric/` root did not include those minimal kernel skeleton directories.
- This was a migration consistency bug, not a project `.agent-os` doctor failure.

Fix:

- Restored minimal kernel registry examples under `global-agent-fabric/registries/`.
- Restored minimal public kernel schema docs under `global-agent-fabric/schemas/`.
- Added doctor validation for required boot kernel skeleton directories and `schemas/phase-contract.md`.
- Extended harness audit repair so missing shared-fabric hooks also restore the minimal kernel skeleton.
- Kept the boot hook strict; no boot check was weakened.

Validation:

- `global-agent-fabric/hooks/before-task.sh` now returns `[BOOT_OK]`.
- KnowledgeOS doctor remains clean.

## 2026-05-13 - Release Note: Public Changelog And Codex Hooks Flag

Status: implemented locally.

Bug reproduced:

- Root `CHANGELOG.md` was not yet a governed KnowledgeOS artifact, so `check-route-write` classified it as an unclassified write.
- Local Codex configuration did not enable the current `hooks` feature flag, while Codex warned that the old `codex_hooks` flag is deprecated.

Fix:

- Added a public root `CHANGELOG.md` summarizing KnowledgeOS capability milestones and hardening repairs.
- Added `CHANGELOG.md` to the local route-bound write policy and route-bound execution profile.
- Updated the local Codex config to use `[features].hooks = true` while preserving the existing memories feature.
- Backed up the previous local Codex config before editing.

Validation:

- `check-route-write` now allows `CHANGELOG.md` as a governed artifact.
- Local Codex config parses as TOML and includes `features.hooks = true`.
- No active `codex_hooks` key remains in the targeted Codex configuration scan.

## 2026-05-13 - Hardening Note: Explicit Checkpoints And Capability Events

Status: implemented locally after reproducing low-visibility lifecycle reporting.

Bug reproduced:

- `phase-task` wrote `phases.ndjson` but plain output did not force a user-visible `CHECKPOINT_OK` marker.
- A run with all six phases and eval evidence could complete without any run-bound dispatch evidence or capability-call trace.
- MCP, skill, subagent, orchestrator, and important script use were visible in the dispatch plan but not recorded as first-class run events.

Fix:

- `phase-task` now returns `CHECKPOINT_OK phase=<phase> status=<status> evidence=<short evidence>` in plain output and `checkpoint_marker: CHECKPOINT_OK` in JSON.
- Added `capability-event` for observable MCP, skill, subagent, orchestrator, script, shell, and file-read calls.
- `capability-event` writes `.agent-os/runs/<RUN_ID>/capability-events.ndjson` plus matching `command-events.ndjson` evidence and returns `CAPABILITY_OK`.
- `dispatch-task --run-id` now records dispatch command evidence for the active run.
- `verify-lifecycle` now rejects runs missing dispatch command evidence or missing required capability-stage evidence unless the dispatch phase explicitly explains the skipped required stage.
- Write policy now human-gates direct edits to `capability-events.ndjson` so capability traces must be command-generated.

Validation:

- Added targeted tests for checkpoint markers, capability-event ledgers, and missing required capability traces.
- Updated the distracted-agent guardrail scenario to require dispatch evidence and capability visibility.

## 2026-05-15 - HTML Sidecar Reports

Status: implemented locally as a presentation sidecar, not an OS source format.

Why:

- Markdown, YAML, and NDJSON should remain canonical evidence for doctor, lifecycle, eval, receipt, handoff, and sync.
- Human-facing reports benefit from richer layout, stable anchors, metadata cards, and composable sections.

Fix:

- Added `render-html` with `receipt`, `handoff`, `rich-report`, and `--compose` modes.
- Generated HTML includes source path, source SHA-256, run id when available, generated time, and the notice `HTML is presentation, not source of truth.`
- Each report writes a full page, a reusable `.fragment.html`, and a `.manifest.json` for stitching.
- Composition merges fragments into one self-contained static page without iframes, remote scripts, remote fonts, or CDN assets.

Validation:

- Added targeted tests for receipt/handoff sidecars, rich-report escaping, self-contained output, composition, stale source hash detection, and doctor ignoring HTML sidecars as source evidence.

## 2026-05-19 - Hardening Note: Capability Effect Verification

Status: implemented locally after reproducing missing side-effect verification.

Bug reproduced:

- `artifact-assert` and `verify-effects` did not exist, so capability visibility could prove that a tool call was declared but not that a real artifact changed.
- `complete-task` could not distinguish between a real output and a claimed side effect beyond declared output existence.
- Initial effect assertion ids used second-level timestamps, which could collide during rapid same-kind assertions.

Fix:

- Added `.agent-os/effect-policy.yaml` with project-level strictness: `observe`, `warn`, `enforce`, and `off` with downgrade reason.
- Added `artifact-assert`, which verifies real artifacts and emits `EFFECT_OK` only after checks such as `file_exists`, `file_contains`, `file_sha256`, `file_changed`, `json_key_equals`, or `html_self_contained` pass.
- Added stable `capability_event_id` values to `capability-event` so effect assertions can link a tool/subagent/script call to its verified artifact side effect.
- Added `verify-effects`, which rejects missing or forged effect evidence under `strictness: enforce` and records warnings under `strictness: warn`.
- Integrated `verify-effects` into router lifecycle checks and `complete-task` before postflight.
- Human-gated direct writes to `effect-assertions.ndjson` and documented `EFFECT_OK` in startup prompts, templates, agent guide, and release checklist.

Validation:

- Targeted tests verify successful and failed `artifact-assert` behavior, capability-to-effect linkage, warn/enforce/off strictness behavior, forged ledger rejection, and `complete-task` effect gating.
- Dry-run temporary projects confirm completion is blocked without required effect proof and succeeds after a real `artifact-assert`.

## 2026-05-19 - Hardening Note: Explicit Effect Verification Reporting

Status: implemented locally after reproducing hidden verifier reporting.

Bug reproduced:

- `verify-effects` returned structured status but did not emit a dedicated visible marker like `CHECKPOINT_OK`, `CAPABILITY_OK`, or `EFFECT_OK`.
- This meant effect verification was enforced at completion time, but a human watching the session did not get a crisp one-line confirmation unless the agent summarized the JSON manually.

Fix:

- Added `EFFECT_VERIFY_OK status=<status> strictness=<level> assertions=<n> warnings=<n> errors=<n>`.
- Added `effect_verify_marker: EFFECT_VERIFY_OK` and `marker` to `verify-effects --json`.
- Updated `complete-task` receipts and JSON to include the effect verification marker.
- Updated startup prompts, template `AGENTS.md`, agent guide, executable control-plane docs, route-bound guard docs, and release checklist to require relaying `EFFECT_VERIFY_OK` before claiming effect verification success.

Validation:

- Reproduced the missing marker with an existing completed run.
- Added targeted tests for plain and JSON `verify-effects` marker output.
- Verified the marker appears after the patch and remains command-evidenced.

## 2026-05-19 - Audit Note: Capability Link And Run Id Robustness

Status: implemented locally during staged-diff and robustness audit.

Bug reproduced:

- `artifact-assert --capability-event-id CAP-DOES-NOT-EXIST` succeeded even though the referenced capability event did not exist.
- Rapidly reopening and rerunning the same task could allocate the same second-level `RUN-YYYYMMDD-HHMMSS-<TASK>` id and fail with `File exists`.

Fix:

- `artifact-assert` now rejects nonexistent capability event ids before writing a passing `EFFECT_OK` record.
- `verify-effects` now rejects existing effect assertions that claim a missing capability event id.
- `run-task` now allocates a suffixed run id such as `RUN-20260519-120000-T001-01` when a same-second run id already exists.

Validation:

- Reproduced the bogus capability link acceptance in a temporary project, then verified the same command fails with `capability event not found`.
- Added targeted regression coverage for bogus capability links, forged effect ledgers, and same-second run id collisions.
- Re-ran harness audit, guardrail scenarios, unit tests, smoke, and diff checks after the fix.

## 2026-05-29 - Module Note: Decision Graph

Status: implemented locally as an optional module, not a kernel expansion.

Bug / product gap reproduced:

- Long research and agent sessions could record what happened through trace steps and lifecycle checkpoints, but they had no first-class public record of why a plan branched, why a route was abandoned, or why a rollback happened.
- Without a decision ledger, the human-readable plan could drift from the executed path, especially when a task inserted new checks or changed route midway.
- Completion could not distinguish between ordinary linear progress and important decision changes that should be auditable.

Fix:

- Added `decision-event` to write `.agent-os/runs/<RUN_ID>/decision-events.ndjson` and return `DECISION_OK`.
- Added `decision-query` for filtering decision events by run, task, kind, status, or parent id.
- Added `verify-decisions` to detect forged events, orphan nodes, invalid kinds/statuses, and unexplained abandoned, rollback, or superseded branches.
- Added `.agent-os/decision-policy.yaml` with default `strictness: warn`; `strictness: enforce` makes `complete-task` block on decision verification failure.
- Added `render-html --kind decision-map` to generate a readable HTML sidecar from the decision ledger while keeping NDJSON as source of truth.
- Updated agent guide, startup prompts, operating spec, executable control-plane docs, release checklist, project template, and tests.

Validation:

- Reproduced missing CLI behavior before implementation: `decision-event` was an invalid command and completion did not enforce decision verification.
- Added targeted tests for event creation, query, orphan detection, strict policy completion blocking, default warn policy, startup prompt contract, doctor policy validation, and decision-map HTML output.
- Verified `python3 -B -m py_compile knowledgeos/cli.py`.
- Verified `python3 -B -m unittest discover -s tests -v`: 87 tests passed.
- Verified `./examples/scenarios/run_guardrail_scenarios.sh`: 30 checkpoints passed.
- Verified `./bin/knowledgeos doctor --root . --project-root . --summary`: 1789 checks passed.
- Verified `git diff --check`.

## 2026-05-29 - Reporting Note: Mission Flow

Status: implemented locally as a presentation/reporting layer, not kernel evidence.

Product gap reproduced:

- Medium and complex tasks could finish with strong command evidence but still require the user to mentally assemble what happened from raw markers such as `CHECKPOINT_OK`, `CAPABILITY_OK`, `EFFECT_OK`, `DECISION_OK`, and `[SYNC_OK]`.
- The user-facing closeout needed a readable flow diagram with plain labels, not a dense dump of internal lifecycle terms.

Fix:

- Added `flow-summary`, which writes `.agent-os/runs/<RUN_ID>/mission-flow.md` and emits `FLOW_OK`.
- Added `render-html --kind mission-flow`, which creates a self-contained HTML sidecar with colored cards and source metadata.
- Updated `complete-task` so medium, high, and complex tasks return `flow_marker`, `flow_summary_marker`, `flow_mermaid`, and `flow_source`.
- Kept Mission Flow out of kernel enforcement. It summarizes existing evidence lanes for humans and does not replace Markdown, YAML, or NDJSON evidence.
- Updated executable docs, operating spec, agent guide, startup prompts, templates, changelog, and tests.

Validation:

- Added targeted tests for `flow-summary`, mission-flow HTML sidecars, and `complete-task` flow output.
- Verified the diagram uses readable labels such as `Goal`, `Health Check`, `Task & Plan`, `Safe Writes`, `Work Done`, `Tools Used`, `Proof`, `Decisions`, and `Finish`.

## 2026-05-29 - Module Note: Thread Plan Ledger

Status: implemented locally as a chat-level planning module, not a lifecycle checkpoint.

Product gap reproduced:

- Run-level Mission Flow summarizes one completed task but does not preserve the whole chat-window plan as the conversation grows.
- Long research/product conversations need a natural-language version map: Plan A / Plan B, Phase A / Phase B, current route, inserted steps, linked runs, and deferred branches.
- The desired view should be readable by humans and should not add another completion gate.

Fix:

- Added `thread-plan start`, `thread-plan current`, `thread-plan append`, `thread-plan link-run`, and `thread-plan render`.
- Added `.agent-os/threads/<THREAD_ID>/thread-plan.ndjson` as the append-only source of truth, with Markdown and HTML sidecars for review.
- Added `THREAD_PLAN_OK` command output for successful thread-plan operations.
- Kept Thread Plan Ledger out of `complete-task`, `verify-lifecycle`, and checkpoint enforcement.
- Updated executable docs, operating spec, agent guide, startup prompts, templates, release checklist, changelog, and tests.

Validation:

- Added targeted tests for start/current/append/link-run/render and append-only ledger behavior.
- Verified Markdown includes `Plan A / Plan B`, `Phase A / Phase B`, current working line, and linked run evidence.
- Verified HTML sidecar is self-contained and marks HTML as presentation, not source of truth.

## 2026-05-30 - Bugfix Note: Thread Plan HTML Heading

Status: fixed and regression-tested.

Bug reproduced:

- `thread-plan render --format html` produced three `<h1>` headings for one thread-plan page.
- Root cause: the HTML document shell already renders a page title, the Thread Plan renderer manually prepended another `<h1>`, and the Markdown fragment converted its own top-level title into a third `<h1>`.

Fix:

- Removed the extra hand-written Thread Plan body heading from `render_thread_plan_html`.
- Kept the canonical Markdown title and the outer HTML shell title intact.

Validation:

- Reproduced the issue in a temporary project before the fix: `h1_count=3`.
- Re-ran the same reproduction after the fix: `h1_count=2`.
- Added a regression assertion to the Thread Plan Ledger test.
