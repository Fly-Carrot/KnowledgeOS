# Agent Entry Contract

This project uses KnowledgeOS.

Before substantial work:

1. Read `.agent-os/workspace.yaml`.
2. Read `.agent-os/project.yaml`.
3. Read `.agent-os/tasks.yaml`, `.agent-os/decisions.yaml`, and `.agent-os/evals.yaml`.
4. Run `CHANGE_ME_KNOWLEDGEOS_BIN doctor --project-root . --summary`.
5. Run the configured shared-fabric boot hook from `.agent-os/fabric-link.yaml`.
6. Report `[BOOT_OK]` only after the hook succeeds.

During substantial work:

- Follow the phase lifecycle: `route -> plan -> review -> dispatch -> execute -> report`.
- Check `.agent-os/write-policy.yaml` before writing.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN route-task --project-root . --task-id <task-id>` before dispatching work.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN check-route-write --project-root . --task-id <task-id> --path <planned-path>` before planned mutations.
- Use `.agent-os/capabilities.yaml` before invoking MCP tools, skills, workflows, or subagents.
- Use `.agent-os/tool-registry.yaml` to confirm the configured MCP, skills, workflows, orchestrators, and subagents.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN tool-registry --project-root .` before relying on registered capabilities.
- Use `.agent-os/dispatch-policy.yaml` to choose capabilities in a visible order.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-task --project-root . --task-id <task-id>` before invoking subagents, MCP tools, or skills.
- At consultation checkpoints, pause, state your recommendation, explain the tradeoff, and ask the human whether to proceed.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN run-task --project-root . --task-id <task-id>` to create run evidence.
- Record run evidence under `.agent-os/runs/`.

After substantial work:

- Run `CHANGE_ME_KNOWLEDGEOS_BIN eval-task --project-root . --task-id <task-id> --run-id <run-id>`; do not manually append eval status.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"` to close task state.
- Run the configured postflight hook.
- Report `[SYNC_OK]` only after postflight succeeds.

Reset and migration:

- If the user asks to rerun an unsatisfactory task, use `CHANGE_ME_KNOWLEDGEOS_BIN reopen-task --project-root . --task-id <task-id> --reason "<reason>"` before rerunning.
- If the user asks to reset the project OS state, run `CHANGE_ME_KNOWLEDGEOS_BIN reset-project --project-root . --mode <soft|hard> --dry-run` first and show the planned actions.
- If the user asks to reorganize an old project, run `CHANGE_ME_KNOWLEDGEOS_BIN migrate-legacy-project --project-root . --write-plan` first; use `--apply` only after human approval.

Never:

- write to immutable paths;
- bypass human-gated paths;
- invoke generic unscoped subagents;
- claim boot, eval, or sync success without command evidence.
