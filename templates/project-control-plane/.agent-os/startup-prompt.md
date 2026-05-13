# KnowledgeOS Startup Prompt

Use this workspace's KnowledgeOS control plane.

Project root: `CHANGE_ME_PROJECT_ROOT`

This startup prompt is only the session trigger. Durable rules live in `AGENTS.md`, `.agent-os/`, and the linked KnowledgeOS kernel/capability roots.

Before substantial work:

1. Read `AGENTS.md`.
2. Read `.agent-os/workspace.yaml`, `.agent-os/project.yaml`, `.agent-os/tasks.yaml`, `.agent-os/phase-policy.yaml`, `.agent-os/decisions.yaml`, `.agent-os/evals.yaml`, `.agent-os/fabric-link.yaml`, `.agent-os/read-policy.yaml`, `.agent-os/write-policy.yaml`, `.agent-os/dispatch-policy.yaml`, and `.agent-os/tool-registry.yaml`.
3. Run `CHANGE_ME_KNOWLEDGEOS_BIN doctor --project-root CHANGE_ME_PROJECT_ROOT --summary` and do not proceed if it fails.
4. Select or confirm one task id from `.agent-os/tasks.yaml`; if no ready task fits the user's new request, run `CHANGE_ME_KNOWLEDGEOS_BIN create-task --project-root CHANGE_ME_PROJECT_ROOT --title "<title>" --type <type> --output <path> --acceptance "<check>"`.
5. Run `CHANGE_ME_KNOWLEDGEOS_BIN route-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id>`.
6. Run `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id>` before invoking subagents, MCP tools, skills, workflows, or scripts.
7. Before planned mutation, run `CHANGE_ME_KNOWLEDGEOS_BIN check-route-write --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --path <planned-path>`.
8. Create run evidence with `CHANGE_ME_KNOWLEDGEOS_BIN run-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id>`.
9. Pause at consultation checkpoints, state your recommended next move, name the tradeoff, and ask the human whether to proceed.
10. Record run-bound dispatch evidence with `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>`.
11. Record lifecycle evidence with `CHANGE_ME_KNOWLEDGEOS_BIN phase-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id> --phase <route|plan|review|dispatch|execute|report> --status completed --note "<public trace>" --evidence "<command/file/user confirmation>"`, and relay the returned `CHECKPOINT_OK` marker.
12. Record MCP, skill, subagent, orchestrator, or important script use with `CHANGE_ME_KNOWLEDGEOS_BIN capability-event --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose "<purpose>"`, and relay the returned `CAPABILITY_OK` marker.
13. Run `CHANGE_ME_KNOWLEDGEOS_BIN eval-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>`; do not manually append eval status.
14. Run `CHANGE_ME_KNOWLEDGEOS_BIN verify-lifecycle --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>`.
15. Use `CHANGE_ME_KNOWLEDGEOS_BIN complete-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id> --summary "<summary>"`; it enforces lifecycle, capability visibility, and required postflight.
16. If a shared-fabric postflight hook is configured, report `[SYNC_OK]` only after `complete-task` returns `sync_status: SYNC_OK`.
17. For reset requests, run `CHANGE_ME_KNOWLEDGEOS_BIN reset-project --project-root CHANGE_ME_PROJECT_ROOT --mode <soft|hard> --dry-run` before any destructive action.
18. For old-project reorganization requests, run `CHANGE_ME_KNOWLEDGEOS_BIN migrate-legacy-project --project-root CHANGE_ME_PROJECT_ROOT --write-plan` before moving files.
19. For historical or superseded files that should be stored but not read by default, run `CHANGE_ME_KNOWLEDGEOS_BIN archive-legacy-project --project-root CHANGE_ME_PROJECT_ROOT --write-plan` before moving files into `archive/`.

Never claim boot, route, dispatch, write safety, phase, lifecycle, eval, completion, or sync success without command evidence.
