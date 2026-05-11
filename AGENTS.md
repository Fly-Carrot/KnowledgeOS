# KnowledgeOS Agent Contract

This repository is building KnowledgeOS, an intent-driven control plane for knowledge and development agents.

Before substantial work:

1. Inspect the current repository structure.
2. If a local `.agent-os/` control plane exists, read its workspace, project, tasks, decisions, evals, capabilities, dispatch policy, read policy, and write policy.
3. Use `./bin/knowledgeos doctor --project-root . --summary` before claiming the local control plane is clean.
4. Use `./bin/knowledgeos route-task --project-root . --task-id <task-id>` and `./bin/knowledgeos dispatch-task --project-root . --task-id <task-id>` before capability-heavy work.
5. Use `./bin/knowledgeos eval-task --project-root . --task-id <task-id> --run-id <run-id>` before `complete-task`; do not manually append eval status.
6. For reset requests, run `reset-project --dry-run` first. For legacy reorganization, run `migrate-legacy-project --write-plan` first. For cold storage of old or superseded project content, run `archive-legacy-project --write-plan` first.
7. Run `python3 -m unittest discover -s tests -v` after CLI or template changes.

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
