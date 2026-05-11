# KnowledgeOS Startup Prompt

Use this workspace's KnowledgeOS control plane.

Project root: `.`

This prompt is only the session trigger. Durable rules live in `AGENTS.md`, `.agent-os/`, and the linked KnowledgeOS kernel/capability roots.

Before substantial work:

1. Read `AGENTS.md`.
2. Read `.agent-os/workspace.yaml`, `.agent-os/project.yaml`, `.agent-os/tasks.yaml`, `.agent-os/decisions.yaml`, `.agent-os/evals.yaml`, `.agent-os/fabric-link.yaml`, `.agent-os/write-policy.yaml`, `.agent-os/dispatch-policy.yaml`, and `.agent-os/tool-registry.yaml`.
3. Run `./bin/knowledgeos doctor --project-root . --summary` and do not proceed if it fails.
4. Select or confirm one task id from `.agent-os/tasks.yaml`.
5. Run `./bin/knowledgeos route-task --project-root . --task-id <task-id>`.
6. Run `./bin/knowledgeos dispatch-task --project-root . --task-id <task-id>` before invoking subagents, MCP tools, skills, workflows, or scripts.
7. Before planned mutation, run `./bin/knowledgeos check-route-write --project-root . --task-id <task-id> --path <planned-path>`.
8. Create run evidence with `./bin/knowledgeos run-task --project-root . --task-id <task-id>`.
9. Pause at consultation checkpoints, state your recommended next move, name the tradeoff, and ask the human whether to proceed.
10. Run `./bin/knowledgeos eval-task --project-root . --task-id <task-id> --run-id <run-id>`; do not manually append eval status.
11. Use `./bin/knowledgeos complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`.
12. If a shared-fabric postflight hook is configured, report `[SYNC_OK]` only after it succeeds.
13. For reset requests, run `./bin/knowledgeos reset-project --project-root . --mode <soft|hard> --dry-run` before destructive action.
14. For old-project reorganization requests, run `./bin/knowledgeos migrate-legacy-project --project-root . --write-plan` before moving files.

Never claim boot, route, dispatch, write safety, eval, or sync success without command evidence.
