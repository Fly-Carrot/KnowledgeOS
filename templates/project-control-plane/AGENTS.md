# Agent Entry Contract

This project uses KnowledgeOS.

At the start of every conversation:

- Make a visible KnowledgeOS judgment before acting: project state (`managed` or `unmanaged`), work class (`simple`, `substantial`, or `blocked`), required flow (`answer-only`, `task`, `spec`, `thread-plan`, or `full lifecycle`), and reason.
- Relay this as `KOS_DECISION` in user-visible text. This is a public routing decision, not hidden reasoning.
- If the project is managed and the work is substantial, continue with the command-evidenced lifecycle below.

Before substantial work:

1. Read `.agent-os/workspace.yaml`.
2. Read `.agent-os/project.yaml`.
3. Read `.agent-os/tasks.yaml`, `.agent-os/specs.yaml`, `.agent-os/phase-policy.yaml`, `.agent-os/decision-policy.yaml`, `.agent-os/decisions.yaml`, and `.agent-os/evals.yaml`.
4. Run `CHANGE_ME_KNOWLEDGEOS_BIN doctor --project-root . --summary`.
5. Run the configured shared-fabric boot hook from `.agent-os/fabric-link.yaml`.
6. Report `[BOOT_OK]` only after the hook succeeds.

During substantial work:

- Follow the phase lifecycle: `route -> plan -> review -> dispatch -> execute -> report`.
- Check `.agent-os/read-policy.yaml` before using broad project context; `archive/**` is cold storage and is not default context.
- Check `.agent-os/write-policy.yaml` before writing.
- If the user asks to create, align, or follow a spec, use `CHANGE_ME_KNOWLEDGEOS_BIN create-spec --project-root . --title "<title>"` or `CHANGE_ME_KNOWLEDGEOS_BIN align-spec --project-root . --task-id <task-id>` before execution.
- If the user starts or continues a durable plan/spec conversation, use `CHANGE_ME_KNOWLEDGEOS_BIN thread-plan current --project-root .` or `CHANGE_ME_KNOWLEDGEOS_BIN thread-plan start --project-root . --title "<natural language goal>"`; update it with `CHANGE_ME_KNOWLEDGEOS_BIN thread-plan append --project-root . --thread-id <thread-id> --kind <kind> --text "<plain note>"` when the plan changes or advances, and relay `THREAD_PLAN_OK`.
- If no ready task fits the user's new request, use `CHANGE_ME_KNOWLEDGEOS_BIN create-task --project-root . --title "<title>" --type <type> --output <path> --acceptance "<check>"` instead of reopening unrelated prior work.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN route-task --project-root . --task-id <task-id>` before dispatching work.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN check-route-write --project-root . --task-id <task-id> --path <planned-path>` before planned mutations.
- Use `.agent-os/capabilities.yaml` before invoking MCP tools, skills, workflows, or subagents.
- Use `.agent-os/tool-registry.yaml` to confirm the configured MCP, skills, workflows, orchestrators, and subagents.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN tool-registry --project-root .` before relying on registered capabilities.
- Use `.agent-os/dispatch-policy.yaml` to choose capabilities in a visible order.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-task --project-root . --task-id <task-id>` before invoking subagents, MCP tools, or skills, and relay the returned `AGENT_DISPATCH_PLAN` marker.
- At consultation checkpoints, pause, state your recommendation, explain the tradeoff, and ask the human whether to proceed.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN run-task --project-root . --task-id <task-id>` to create run evidence.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN context-pack --project-root . --task-id <task-id> --run-id <run-id>` and `CHANGE_ME_KNOWLEDGEOS_BIN plan-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"` before execution.
- After `run-task` creates a run id, use `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-task --project-root . --task-id <task-id> --run-id <run-id>` to record dispatch evidence for that run.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN trace-step --project-root . --task-id <task-id> --run-id <run-id> --step <step> --note "<public trace>" --evidence "<command/file/user confirmation>"` to record visible operational progress, and relay the returned `TRACE_OK` marker.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN phase-task --project-root . --task-id <task-id> --run-id <run-id> --phase <route|plan|review|dispatch|execute|report> --status completed --note "<public trace>" --evidence "<command/file/user confirmation>"` to record observable phase evidence, and relay the returned `CHECKPOINT_OK` marker.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN capability-event --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose "<purpose>"` before or after MCP, skill, plugin/app, browser/Chrome/GitHub/security connector, subagent, orchestrator, shell, file_read, or important script use, and relay the returned `CAPABILITY_OK` marker.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-report --project-root . --task-id <task-id> --run-id <run-id>` when summarizing actual capability dispatch, and relay the returned `AGENT_DISPATCH_OK` marker.
- Treat `AGENT_DISPATCH_OK` as a full capability dispatch report: include agents invoked/skipped, MCP, skills, plugins/apps, browser/Chrome/GitHub/security connectors, scripts, shell, file reads, evidence files, and any gaps. If no subagent was used, still report `agents=0` and explain why.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN decision-event --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --title "<title>" --summary "<summary>" --reason "<reason>" --evidence "<evidence>"` when a plan branches, changes, rolls back, abandons a route, or records a major human decision, and relay the returned `DECISION_OK` marker.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN thread-plan link-run --project-root . --thread-id <thread-id> --task-id <task-id> --run-id <run-id>` to connect a task run to the chat-level plan.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN artifact-assert --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --path <artifact>` to verify real side effects, and relay the returned `EFFECT_OK` marker.
- Record run evidence under `.agent-os/runs/`.

After substantial work:

- Run `CHANGE_ME_KNOWLEDGEOS_BIN eval-task --project-root . --task-id <task-id> --run-id <run-id>`; do not manually append eval status.
- Run `CHANGE_ME_KNOWLEDGEOS_BIN verify-context --project-root . --task-id <task-id> --run-id <run-id>`.
- Run `CHANGE_ME_KNOWLEDGEOS_BIN verify-lifecycle --project-root . --task-id <task-id> --run-id <run-id>`.
- Run `CHANGE_ME_KNOWLEDGEOS_BIN verify-effects --project-root . --task-id <task-id> --run-id <run-id>` and relay the returned `EFFECT_VERIFY_OK` marker before claiming effect verification success.
- Run `CHANGE_ME_KNOWLEDGEOS_BIN verify-decisions --project-root . --task-id <task-id> --run-id <run-id>` and relay the returned `DECISION_VERIFY_OK` marker before claiming decision verification success.
- Use `CHANGE_ME_KNOWLEDGEOS_BIN complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"` to close task state. It enforces spec/context/plan, lifecycle evidence, visible dispatch reporting, effect evidence, decision evidence according to policy, and required postflight.
- Include the `AGENT_DISPATCH_OK` marker and full capability summary returned by `dispatch-report` or `complete-task` in the final answer for substantial work.
- For medium, high, or complex tasks, include the `FLOW_OK` Mermaid Mission Flow returned by `complete-task`; if needed, run `CHANGE_ME_KNOWLEDGEOS_BIN flow-summary --project-root . --run-id <run-id>` and relay `FLOW_OK`.
- Keep Mission Flow readable for humans: use simple labels like Goal, Health Check, Task & Plan, Safe Writes, Work Done, Tools Used, Proof, Decisions, and Finish.
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
- claim boot, phase, lifecycle, decision, eval, completion, or sync success without command evidence.
- claim agent, subagent, tool, or script dispatch success without `AGENT_DISPATCH_PLAN` and `AGENT_DISPATCH_OK` command evidence.
- skip the initial `KOS_DECISION` routing judgment for any conversation.
- manually write spec snapshots, context packs, plans, phase ledgers, or eval status instead of using KnowledgeOS commands.
- manually write operational trace ledgers instead of using `trace-step`.
- manually write decision event ledgers instead of using `decision-event`.
- manually write thread plan ledgers instead of using `thread-plan`.
