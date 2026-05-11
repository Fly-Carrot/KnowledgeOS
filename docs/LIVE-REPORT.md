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
