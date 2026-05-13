# KnowledgeOS Agent Contract

This repository is building KnowledgeOS, an intent-driven control plane for knowledge and development agents.

Before substantial work:

1. Inspect the current repository structure.
2. If a local `.agent-os/` control plane exists, read its workspace, project, tasks, phase policy, decisions, evals, capabilities, dispatch policy, read policy, and write policy.
3. Use `./bin/knowledgeos doctor --project-root . --summary` before claiming the local control plane is clean.
4. If no ready task fits the user's new request, use `./bin/knowledgeos create-task --project-root . --title "<title>" --type <type> --output <path> --acceptance "<check>"` instead of reopening unrelated old work.
5. Use `./bin/knowledgeos route-task --project-root . --task-id <task-id>` and `./bin/knowledgeos dispatch-task --project-root . --task-id <task-id>` before capability-heavy work.
6. After `run-task` creates a run id, use `./bin/knowledgeos dispatch-task --project-root . --task-id <task-id> --run-id <run-id>` to record dispatch evidence for that run.
7. Use `./bin/knowledgeos phase-task --project-root . --task-id <task-id> --run-id <run-id> --phase <route|plan|review|dispatch|execute|report> --status completed --note "<public trace>" --evidence "<evidence>"` to record public lifecycle evidence, and relay the returned `CHECKPOINT_OK` marker.
8. Before or after MCP, skill, subagent, orchestrator, or important script use, record it with `./bin/knowledgeos capability-event --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose "<purpose>"`, and relay the returned `CAPABILITY_OK` marker.
9. Use `./bin/knowledgeos eval-task --project-root . --task-id <task-id> --run-id <run-id>` before `complete-task`; do not manually append eval status.
10. Use `./bin/knowledgeos verify-lifecycle --project-root . --task-id <task-id> --run-id <run-id>` before completion.
11. Use `./bin/knowledgeos complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`; it enforces lifecycle, capability visibility, and required postflight.
12. For reset requests, run `reset-project --dry-run` first. For legacy reorganization, run `migrate-legacy-project --write-plan` first. For cold storage of old or superseded project content, run `archive-legacy-project --write-plan` first.
13. Run `python3 -m unittest discover -s tests -v` after CLI or template changes.

Consultation discipline:

- Before execution and before completion, pause and state your recommended next move.
- Name the tradeoff in plain language.
- Ask the human whether to proceed when the dispatch policy or risk profile calls for it.

Write discipline:

- Do not copy local secrets, private runtime state, browser profiles, or raw chat histories into public docs or templates.
- Keep public templates generic and placeholder-based.
- Keep local migration notes under `.knowledgeos-local/`.
- Treat `archive/**` as cold storage: do not read it as default context unless the user explicitly asks for archive review or recovery.
- Treat Agent Shared Fabric as an external kernel module, not as content copied into every project.
- Use `reopen-task` only for same-task reruns after rejected results. New work gets a new `create-task` record.
