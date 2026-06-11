# KnowledgeOS Startup Prompt

Use this workspace's KnowledgeOS control plane.

Project root: `.`

This prompt is only the session trigger. Durable rules live in `AGENTS.md`, `.agent-os/`, and the linked KnowledgeOS kernel/capability roots.

Before substantial work:

0. At the start of every conversation, make a visible KnowledgeOS judgment and relay `KOS_DECISION` with project state (`managed` or `unmanaged`), work class (`simple`, `substantial`, or `blocked`), required flow (`answer-only`, `task`, `spec`, `thread-plan`, or `full lifecycle`), and reason. This is a public routing decision, not hidden reasoning.
1. Read `AGENTS.md`.
2. Read `.agent-os/workspace.yaml`, `.agent-os/project.yaml`, `.agent-os/tasks.yaml`, `.agent-os/specs.yaml`, `.agent-os/phase-policy.yaml`, `.agent-os/decision-policy.yaml`, `.agent-os/effect-policy.yaml`, `.agent-os/decisions.yaml`, `.agent-os/evals.yaml`, `.agent-os/fabric-link.yaml`, `.agent-os/read-policy.yaml`, `.agent-os/write-policy.yaml`, `.agent-os/dispatch-policy.yaml`, and `.agent-os/tool-registry.yaml`.
3. Run `./bin/knowledgeos doctor --project-root . --summary` and do not proceed if it fails.
4. If the user says `create spec`, `align spec`, `创建spec`, `对齐spec`, or equivalent, run `./bin/knowledgeos create-spec --project-root . --title "<title>"` or `./bin/knowledgeos align-spec --project-root . --task-id <task-id>` before execution.
5. If the user starts or continues a durable plan/spec conversation, run `./bin/knowledgeos thread-plan current --project-root .` or `./bin/knowledgeos thread-plan start --project-root . --title "<natural language goal>"`; append plain-language progress with `./bin/knowledgeos thread-plan append --project-root . --thread-id <thread-id> --kind <kind> --text "<plain note>"` and relay `THREAD_PLAN_OK`.
6. Select or confirm one task id from `.agent-os/tasks.yaml`.
7. Run `./bin/knowledgeos route-task --project-root . --task-id <task-id>`.
8. Run `./bin/knowledgeos dispatch-task --project-root . --task-id <task-id>` before invoking subagents, MCP tools, skills, workflows, or scripts, and relay the returned `AGENT_DISPATCH_PLAN` marker.
9. Before planned mutation, run `./bin/knowledgeos check-route-write --project-root . --task-id <task-id> --path <planned-path>`.
10. Create run evidence with `./bin/knowledgeos run-task --project-root . --task-id <task-id>`.
11. Write/update the execution context with `./bin/knowledgeos context-pack --project-root . --task-id <task-id> --run-id <run-id>` and `./bin/knowledgeos plan-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`.
12. Pause at consultation checkpoints, state your recommended next move, name the tradeoff, and ask the human whether to proceed.
13. Record run-bound dispatch evidence with `./bin/knowledgeos dispatch-task --project-root . --task-id <task-id> --run-id <run-id>`.
14. Record public operational progress with `./bin/knowledgeos trace-step --project-root . --task-id <task-id> --run-id <run-id> --step <step> --note "<public trace>" --evidence "<command/file/user confirmation>"`, and relay the returned `TRACE_OK` marker.
15. Record public phase evidence with `./bin/knowledgeos phase-task --project-root . --task-id <task-id> --run-id <run-id> --phase <route|plan|review|dispatch|execute|report> --status completed --note "<public trace>" --evidence "<command/file/user confirmation>"`, and relay the returned `CHECKPOINT_OK` marker.
16. Record MCP, skill, plugin/app, browser/Chrome/GitHub/security connector, subagent, orchestrator, shell, file_read, or important script use with `./bin/knowledgeos capability-event --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose "<purpose>"`, and relay the returned `CAPABILITY_OK` marker.
17. Summarize actual capability dispatch with `./bin/knowledgeos dispatch-report --project-root . --task-id <task-id> --run-id <run-id>` and relay the returned `AGENT_DISPATCH_OK` marker. Treat it as a full capability report: agents invoked/skipped, MCP, skills, plugins/apps, browser/Chrome/GitHub/security connectors, scripts, shell, file reads, evidence files, and gaps. If no subagent was used, still report `agents=0` and explain why.
18. Record public decision changes with `./bin/knowledgeos decision-event --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --title "<title>" --summary "<summary>" --reason "<reason>" --evidence "<evidence>"`, and relay the returned `DECISION_OK` marker when plans branch, change, roll back, or abandon a route.
19. Verify real side effects with `./bin/knowledgeos artifact-assert --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --path <artifact>` and relay the returned `EFFECT_OK` marker.
20. Run `./bin/knowledgeos eval-task --project-root . --task-id <task-id> --run-id <run-id>`; do not manually append eval status.
21. Run `./bin/knowledgeos verify-context --project-root . --task-id <task-id> --run-id <run-id>`, `./bin/knowledgeos verify-lifecycle --project-root . --task-id <task-id> --run-id <run-id>`, `./bin/knowledgeos verify-effects --project-root . --task-id <task-id> --run-id <run-id>`, and `./bin/knowledgeos verify-decisions --project-root . --task-id <task-id> --run-id <run-id>`; relay `EFFECT_VERIFY_OK` and `DECISION_VERIFY_OK` before claiming verification success.
22. Use `./bin/knowledgeos complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`; it enforces spec/context/plan, lifecycle, capability visibility, visible dispatch reporting, effect verification, decision verification, and required postflight.
23. Include the `AGENT_DISPATCH_OK` marker and full capability summary returned by `dispatch-report` or `complete-task` in the final answer for substantial work.
24. For medium, high, or complex tasks, include the returned `FLOW_OK` Mermaid Mission Flow in the final answer; if needed, run `./bin/knowledgeos flow-summary --project-root . --run-id <run-id>`.
25. If a shared-fabric postflight hook is configured, report `[SYNC_OK]` only after `complete-task` returns `sync_status: SYNC_OK`.
26. For reset requests, run `./bin/knowledgeos reset-project --project-root . --mode <soft|hard> --dry-run` before destructive action.
27. For old-project reorganization requests, run `./bin/knowledgeos migrate-legacy-project --project-root . --write-plan` before moving files.
28. For historical or superseded files that should be stored but not read by default, run `./bin/knowledgeos archive-legacy-project --project-root . --write-plan` before moving files into `archive/`.

Never skip the initial `KOS_DECISION`. Never claim boot, route, dispatch, write safety, spec alignment, thread plan, context pack, plan, trace, checkpoint, capability, agent dispatch, decision, effect, eval, completion, flow, or sync success without command evidence.
