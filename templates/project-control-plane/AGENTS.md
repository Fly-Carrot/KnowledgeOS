# Agent Entry Contract

This project uses KnowledgeOS.

Before substantial work:

1. Read `.agent-os/workspace.yaml`.
2. Read `.agent-os/project.yaml`.
3. Read `.agent-os/tasks.yaml`, `.agent-os/specs.yaml`, `.agent-os/phase-policy.yaml`, `.agent-os/decisions.yaml`, and `.agent-os/evals.yaml`.
4. Run `CHANGE_ME_KNOWLEDGEOS_BIN doctor --project-root . --summary`.
5. Run the configured shared-fabric boot hook from `.agent-os/fabric-link.yaml`.
6. Report `[BOOT_OK]` only after the hook succeeds.

During substantial work:

- Follow the phase lifecycle: `route -> plan -> review -> dispatch -> execute -> report`.
- Check `.agent-os/read-policy.yaml` before using broad project context; `archive/**` is cold storage and is not default context.
- Check `.agent-os/write-policy.yaml` before writing.
- If the user asks to create, align, or follow a spec, use `CHANGE_ME_KNOWLEDGEOS_BIN create-spec --project-root . --title "<title>"` or `CHANGE_ME_KNOWLEDGEOS_BIN align-spec --project-root . --task-id <task-id>` before execution.
- If no ready task fits the user's new request, use `CHANGE_ME_KNOWLEDGEOS_BIN create-task --project-root . --title "<title>" --type <type> --output <path> --acceptance "<check>"` instead of reopening unrelated prior work.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN route-task --project-root . --task-id <task-id>` before dispatching work.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN check-route-write --project-root . --task-id <task-id> --path <planned-path>` before planned mutations.
- Use `.agent-os/capabilities.yaml` before invoking MCP tools, skills, workflows, or subagents.
- Use `.agent-os/tool-registry.yaml` to confirm the configured MCP, skills, workflows, orchestrators, and subagents.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN tool-registry --project-root .` before relying on registered capabilities.
- Use `.agent-os/dispatch-policy.yaml` to choose capabilities in a visible order.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-task --project-root . --task-id <task-id>` before invoking subagents, MCP tools, or skills.
- At consultation checkpoints, pause, state your recommendation, explain the tradeoff, and ask the human whether to proceed.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN run-task --project-root . --task-id <task-id>` to create run evidence.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN context-pack --project-root . --task-id <task-id> --run-id <run-id>` and `CHANGE_ME_KNOWLEDGEOS_BIN plan-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"` before execution.
- After `run-task` creates a run id, use `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-task --project-root . --task-id <task-id> --run-id <run-id>` to record dispatch evidence for that run.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN phase-task --project-root . --task-id <task-id> --run-id <run-id> --phase <route|plan|review|dispatch|execute|report> --status completed --note "<public trace>" --evidence "<command/file/user confirmation>"` to record observable phase evidence, and relay the returned `CHECKPOINT_OK` marker.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN capability-event --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose "<purpose>"` before or after MCP, skill, subagent, orchestrator, or important script use, and relay the returned `CAPABILITY_OK` marker.
- Record run evidence under `.agent-os/runs/`.

After substantial work:

- Run `CHANGE_ME_KNOWLEDGEOS_BIN eval-task --project-root . --task-id <task-id> --run-id <run-id>`; do not manually append eval status.
- Run `CHANGE_ME_KNOWLEDGEOS_BIN verify-context --project-root . --task-id <task-id> --run-id <run-id>`.
- Run `CHANGE_ME_KNOWLEDGEOS_BIN verify-lifecycle --project-root . --task-id <task-id> --run-id <run-id>`.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"` to close task state. It enforces spec/context/plan, lifecycle evidence, and required postflight.
- Report `[SYNC_OK]` only after `complete-task` returns `sync_status: SYNC_OK`.

Reset and migration:

- If the user asks to rerun an unsatisfactory result for the same task, use `CHANGE_ME_KNOWLEDGEOS_BIN reopen-task --project-root . --task-id <task-id> --reason "<reason>"` before rerunning.
- If the user asks for new work, create a new task with `create-task`; do not use `reopen-task` as task intake.
- If the user asks to reset the project OS state, run `CHANGE_ME_KNOWLEDGEOS_BIN reset-project --project-root . --mode <soft|hard> --dry-run` first and show the planned actions.
- If the user asks to reorganize an old project, run `CHANGE_ME_KNOWLEDGEOS_BIN migrate-legacy-project --project-root . --write-plan` first; use `--apply` only after human approval.
- If the user asks to store old or superseded project content without reading it by default, run `CHANGE_ME_KNOWLEDGEOS_BIN archive-legacy-project --project-root . --write-plan` first; use `--apply` only after human approval.

Never:

- write to immutable paths;
- bypass human-gated paths;
- invoke generic unscoped subagents;
- claim boot, phase, lifecycle, eval, completion, or sync success without command evidence.
- manually write spec snapshots, context packs, plans, phase ledgers, or eval status instead of using KnowledgeOS commands.
