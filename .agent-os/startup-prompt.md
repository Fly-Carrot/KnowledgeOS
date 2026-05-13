# KnowledgeOS Startup Prompt

Use this workspace's KnowledgeOS control plane.

Project root: `.`

This prompt is only the session trigger. Durable rules live in `AGENTS.md`, `.agent-os/`, and the linked KnowledgeOS kernel/capability roots.

Before substantial work:

1. Read `AGENTS.md`.
2. Read `.agent-os/workspace.yaml`, `.agent-os/project.yaml`, `.agent-os/tasks.yaml`, `.agent-os/specs.yaml`, `.agent-os/phase-policy.yaml`, `.agent-os/decisions.yaml`, `.agent-os/evals.yaml`, `.agent-os/fabric-link.yaml`, `.agent-os/read-policy.yaml`, `.agent-os/write-policy.yaml`, `.agent-os/dispatch-policy.yaml`, and `.agent-os/tool-registry.yaml`.
3. Run `./bin/knowledgeos doctor --project-root . --summary` and do not proceed if it fails.
4. If the user says `create spec`, `align spec`, `创建spec`, `对齐spec`, or equivalent, run `./bin/knowledgeos create-spec --project-root . --title "<title>"` or `./bin/knowledgeos align-spec --project-root . --task-id <task-id>` before execution.
5. Select or confirm one task id from `.agent-os/tasks.yaml`.
6. Run `./bin/knowledgeos route-task --project-root . --task-id <task-id>`.
7. Run `./bin/knowledgeos dispatch-task --project-root . --task-id <task-id>` before invoking subagents, MCP tools, skills, workflows, or scripts.
8. Before planned mutation, run `./bin/knowledgeos check-route-write --project-root . --task-id <task-id> --path <planned-path>`.
9. Create run evidence with `./bin/knowledgeos run-task --project-root . --task-id <task-id>`.
10. Write/update the execution context with `./bin/knowledgeos context-pack --project-root . --task-id <task-id> --run-id <run-id>` and `./bin/knowledgeos plan-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`.
11. Pause at consultation checkpoints, state your recommended next move, name the tradeoff, and ask the human whether to proceed.
12. Record run-bound dispatch evidence with `./bin/knowledgeos dispatch-task --project-root . --task-id <task-id> --run-id <run-id>`.
13. Record public operational progress with `./bin/knowledgeos trace-step --project-root . --task-id <task-id> --run-id <run-id> --step <step> --note "<public trace>" --evidence "<command/file/user confirmation>"`, and relay the returned `TRACE_OK` marker.
14. Record public phase evidence with `./bin/knowledgeos phase-task --project-root . --task-id <task-id> --run-id <run-id> --phase <route|plan|review|dispatch|execute|report> --status completed --note "<public trace>" --evidence "<command/file/user confirmation>"`, and relay the returned `CHECKPOINT_OK` marker.
15. Record MCP, skill, subagent, orchestrator, or important script use with `./bin/knowledgeos capability-event --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose "<purpose>"`, and relay the returned `CAPABILITY_OK` marker.
16. Run `./bin/knowledgeos eval-task --project-root . --task-id <task-id> --run-id <run-id>`; do not manually append eval status.
17. Run `./bin/knowledgeos verify-context --project-root . --task-id <task-id> --run-id <run-id>` and `./bin/knowledgeos verify-lifecycle --project-root . --task-id <task-id> --run-id <run-id>`.
18. Use `./bin/knowledgeos complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`; it enforces spec/context/plan, lifecycle, capability visibility, and required postflight.
19. If a shared-fabric postflight hook is configured, report `[SYNC_OK]` only after `complete-task` returns `sync_status: SYNC_OK`.
20. For reset requests, run `./bin/knowledgeos reset-project --project-root . --mode <soft|hard> --dry-run` before destructive action.
21. For old-project reorganization requests, run `./bin/knowledgeos migrate-legacy-project --project-root . --write-plan` before moving files.
22. For historical or superseded files that should be stored but not read by default, run `./bin/knowledgeos archive-legacy-project --project-root . --write-plan` before moving files into `archive/`.

Never claim boot, route, dispatch, write safety, spec alignment, context pack, plan, trace, checkpoint, eval, completion, or sync success without command evidence.
