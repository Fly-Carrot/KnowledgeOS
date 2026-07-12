# KnowledgeOS Startup Prompt

Use this workspace's KnowledgeOS control plane.

Project root: `CHANGE_ME_PROJECT_ROOT`

This startup prompt is only the session trigger. Durable rules live in `AGENTS.md`, `.agent-os/`, and the linked KnowledgeOS kernel/capability roots.

Before substantial work:

1. Read `AGENTS.md`.
2. Read `.agent-os/workspace.yaml`, `.agent-os/project.yaml`, `.agent-os/tasks.yaml`, `.agent-os/specs.yaml`, `.agent-os/phase-policy.yaml`, `.agent-os/decision-policy.yaml`, `.agent-os/effect-policy.yaml`, `.agent-os/decisions.yaml`, `.agent-os/evals.yaml`, `.agent-os/fabric-link.yaml`, `.agent-os/read-policy.yaml`, `.agent-os/write-policy.yaml`, `.agent-os/dispatch-policy.yaml`, and `.agent-os/tool-registry.yaml`.
3. Run `CHANGE_ME_KNOWLEDGEOS_BIN doctor --project-root CHANGE_ME_PROJECT_ROOT --summary` and do not proceed if it fails.
4. If the user starts or continues a durable plan/spec conversation, run `CHANGE_ME_KNOWLEDGEOS_BIN thread-plan current --project-root CHANGE_ME_PROJECT_ROOT` or `CHANGE_ME_KNOWLEDGEOS_BIN thread-plan start --project-root CHANGE_ME_PROJECT_ROOT --title "<natural language goal>"`; append plain-language progress with `CHANGE_ME_KNOWLEDGEOS_BIN thread-plan append --project-root CHANGE_ME_PROJECT_ROOT --thread-id <thread-id> --kind <kind> --text "<plain note>"` and relay `THREAD_PLAN_OK`.
5. Select or confirm one task id from `.agent-os/tasks.yaml`; if no ready task fits the user's new request, run `CHANGE_ME_KNOWLEDGEOS_BIN create-task --project-root CHANGE_ME_PROJECT_ROOT --title "<title>" --type <type> --output <path> --acceptance "<check>"`.
6. Run `CHANGE_ME_KNOWLEDGEOS_BIN route-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id>`.
7. Run `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id>` before invoking subagents, MCP tools, skills, workflows, or scripts, and relay `AGENT_DISPATCH_PLAN`.
7a. If `dispatch-task` selects `codex-*` or `maestro-*` subagents, run `CHANGE_ME_KNOWLEDGEOS_BIN subagent-adapter --project-root CHANGE_ME_PROJECT_ROOT --id <subagent-id>` to resolve the Codex runtime call package. Actual delegation must use the Codex runtime subagent tool, then be recorded with `capability-event --kind subagent`.
7b. Preserve every spawned agent id. For substantive work, use one multi-minute `wait_agent` window rather than repeated short polls. If it expires, send one interrupt requesting current findings, wait once more, and close only after a terminal result. Reconcile a late result with a completed capability event containing `recovered_from=timed_out`.
7c. A bounded spawned subagent executes the parent-assigned scope directly and returns findings. It must not create/reopen tasks or specs, run completion/postflight, or recursively dispatch subagents unless the parent explicitly delegated orchestration.
8. Before planned mutation, run `CHANGE_ME_KNOWLEDGEOS_BIN check-route-write --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --path <planned-path>`.
9. Create run evidence with `CHANGE_ME_KNOWLEDGEOS_BIN run-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id>`.
10. Pause at consultation checkpoints, state your recommended next move, name the tradeoff, and ask the human whether to proceed.
11. Record run-bound dispatch evidence with `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>`.
12. Record public operational progress with `CHANGE_ME_KNOWLEDGEOS_BIN trace-step --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id> --step <step> --note "<public trace>" --evidence "<command/file/user confirmation>"`, and relay the returned `TRACE_OK` marker.
13. Record lifecycle evidence with `CHANGE_ME_KNOWLEDGEOS_BIN phase-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id> --phase <route|plan|review|dispatch|execute|report> --status completed --note "<public trace>" --evidence "<command/file/user confirmation>"`, and relay the returned `CHECKPOINT_OK` marker.
14. Record MCP, skill, plugin/app, browser/Chrome/GitHub/security connector, subagent, orchestrator, shell, file_read, or important script use with `CHANGE_ME_KNOWLEDGEOS_BIN capability-event --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose "<purpose>"`, and relay the returned `CAPABILITY_OK` marker.
14a. If a planned `codex-*` or `maestro-*` subagent is not used or the runtime times out, record `capability-event --kind subagent --status skipped|timed_out|blocked|close_failed` with the reason before `dispatch-report`.
14aa. For an explicit catalog validation task, run `CHANGE_ME_KNOWLEDGEOS_BIN verify-subagents --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>` and relay `SUBAGENT_CATALOG_OK` only after challenge-bound parent attestations cover the immutable run catalog; do not claim independent host verification.
14b. Summarize actual capability dispatch with `CHANGE_ME_KNOWLEDGEOS_BIN dispatch-report --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>` and relay `AGENT_DISPATCH_OK`.
15. Record public decision changes with `CHANGE_ME_KNOWLEDGEOS_BIN decision-event --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id> --kind <kind> --title "<title>" --summary "<summary>" --reason "<reason>" --evidence "<evidence>"`, and relay the returned `DECISION_OK` marker when plans branch, change, roll back, or abandon a route.
16. Verify real side effects with `CHANGE_ME_KNOWLEDGEOS_BIN artifact-assert --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id> --kind <kind> --path <artifact>` and relay the returned `EFFECT_OK` marker.
17. Run `CHANGE_ME_KNOWLEDGEOS_BIN eval-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>`; do not manually append eval status.
18. Run `CHANGE_ME_KNOWLEDGEOS_BIN verify-context --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>`, `CHANGE_ME_KNOWLEDGEOS_BIN verify-lifecycle --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>`, `CHANGE_ME_KNOWLEDGEOS_BIN verify-effects --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>`, and `CHANGE_ME_KNOWLEDGEOS_BIN verify-decisions --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id>`; relay `EFFECT_VERIFY_OK` and `DECISION_VERIFY_OK` before claiming verification success.
19. Use `CHANGE_ME_KNOWLEDGEOS_BIN complete-task --project-root CHANGE_ME_PROJECT_ROOT --task-id <task-id> --run-id <run-id> --summary "<summary>"`; it enforces lifecycle, capability visibility, effect verification, decision verification, and required postflight.
20. For medium, high, or complex tasks, include the returned `FLOW_OK` Mermaid Mission Flow in the final answer; if needed, run `CHANGE_ME_KNOWLEDGEOS_BIN flow-summary --project-root CHANGE_ME_PROJECT_ROOT --run-id <run-id>`.
21. If a shared-fabric postflight hook is configured, report `[SYNC_OK]` only after `complete-task` returns `sync_status: SYNC_OK`.
22. For reset requests, run `CHANGE_ME_KNOWLEDGEOS_BIN reset-project --project-root CHANGE_ME_PROJECT_ROOT --mode <soft|hard> --dry-run` before any destructive action.
23. For old-project reorganization requests, run `CHANGE_ME_KNOWLEDGEOS_BIN migrate-legacy-project --project-root CHANGE_ME_PROJECT_ROOT --write-plan` before moving files.
24. For historical or superseded files that should be stored but not read by default, run `CHANGE_ME_KNOWLEDGEOS_BIN archive-legacy-project --project-root CHANGE_ME_PROJECT_ROOT --write-plan` before moving files into `archive/`.

Never claim boot, route, dispatch, write safety, thread plan, trace, phase, lifecycle, capability, decision, effect, eval, completion, flow, or sync success without command evidence.
