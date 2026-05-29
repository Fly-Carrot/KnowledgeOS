# KnowledgeOS Agent Guide

Use this checklist before substantial work in a KnowledgeOS-controlled project.

1. Read the project entry contract.
   - `AGENTS.md`

2. Load project control state.
   - `.agent-os/workspace.yaml`
   - `.agent-os/project.yaml`
   - `.agent-os/tasks.yaml`
   - `.agent-os/specs.yaml`
   - `.agent-os/phase-policy.yaml`
   - `.agent-os/decision-policy.yaml`
   - `.agent-os/effect-policy.yaml`
   - `.agent-os/decisions.yaml`
   - `.agent-os/evals.yaml`
   - `.agent-os/fabric-link.yaml`
   - `.agent-os/read-policy.yaml`
   - `.agent-os/write-policy.yaml`
   - `.agent-os/dispatch-policy.yaml`
   - `.agent-os/tool-registry.yaml`

3. Run checks before acting.
   - `knowledgeos doctor --project-root . --summary`
   - `knowledgeos check-write --project-root . --path <planned-path>`
   - `knowledgeos create-spec --project-root . --title "<title>"` when the user asks to create a spec.
   - `knowledgeos align-spec --project-root . --task-id <task-id>` when the user asks to align with a spec.
   - `knowledgeos thread-plan current --project-root .` when continuing a long-lived planning conversation.
   - `knowledgeos thread-plan start --project-root . --title "<natural language goal>"` when the user starts a durable plan/spec conversation.

4. Start work through a run envelope.
   - `knowledgeos route-task --project-root . --task-id <task-id>`
   - `knowledgeos dispatch-task --project-root . --task-id <task-id>`
   - `knowledgeos run-task --project-root . --task-id <task-id>`
   - `knowledgeos dispatch-task --project-root . --task-id <task-id> --run-id <run-id>`
   - `knowledgeos context-pack --project-root . --task-id <task-id> --run-id <run-id>`
   - `knowledgeos plan-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`
   - `knowledgeos archive-legacy-project --project-root . --write-plan` before cold-archiving old or superseded content.

5. Never bypass the write guard.
   - Immutable paths are denied.
   - Human-gated paths require explicit approval.
   - Unclassified paths should be triaged before mutation.
   - `archive/**` is cold storage and is not default context.

6. Keep receipts local and command-generated.
   - Use `knowledgeos trace-step --project-root . --task-id <task-id> --run-id <run-id> --step <step> --note "<public note>" --evidence "<command or file evidence>"` for user-visible operational progress.
   - Relay the returned `TRACE_OK` marker to the user.
   - Use `knowledgeos phase-task --project-root . --task-id <task-id> --run-id <run-id> --phase <phase> --status completed --note "<public note>" --evidence "<command or file evidence>"`.
   - Relay the returned `CHECKPOINT_OK` marker to the user.
   - Use `knowledgeos capability-event --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose "<purpose>"` for MCP, skill, subagent, orchestrator, or important script calls.
   - Relay the returned `CAPABILITY_OK` marker to the user.
   - Use `knowledgeos decision-event --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --title "<title>" --summary "<summary>" --reason "<reason>" --evidence "<evidence>"` when a plan branches, changes, rolls back, abandons a route, or records a major human decision.
   - Relay the returned `DECISION_OK` marker to the user.
   - Use `knowledgeos thread-plan append --project-root . --thread-id <thread-id> --kind <plan|phase|branch|decision|progress|change|summary> --text "<plain note>"` when the chat-level plan changes or advances.
   - Relay the returned `THREAD_PLAN_OK` marker when you update the long-lived plan.
   - Use `knowledgeos thread-plan link-run --project-root . --thread-id <thread-id> --task-id <task-id> --run-id <run-id>` to connect a run to the chat-level plan.
   - Use `knowledgeos artifact-assert --project-root . --task-id <task-id> --run-id <run-id> --kind <kind> --path <artifact>` to prove real artifact side effects.
   - Relay the returned `EFFECT_OK` marker to the user.
   - Use `knowledgeos eval-task --project-root . --task-id <task-id> --run-id <run-id>`; do not hand-write `Status: passed`.
   - Use `knowledgeos verify-context --project-root . --task-id <task-id> --run-id <run-id>`.
   - Use `knowledgeos verify-lifecycle --project-root . --task-id <task-id> --run-id <run-id>`.
   - Use `knowledgeos verify-effects --project-root . --task-id <task-id> --run-id <run-id>` and relay the returned `EFFECT_VERIFY_OK` marker before claiming effect verification success.
   - Use `knowledgeos verify-decisions --project-root . --task-id <task-id> --run-id <run-id>` and relay the returned `DECISION_VERIFY_OK` marker before claiming decision verification success.
   - Use `knowledgeos complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`.
   - For medium, high, or complex tasks, include the `FLOW_OK` Mermaid Mission Flow returned by `complete-task`; if needed, run `knowledgeos flow-summary --project-root . --run-id <run-id>` and relay `FLOW_OK`.
   - Keep the Mission Flow user-facing and readable: prefer labels like `Goal`, `Health Check`, `Task & Plan`, `Safe Writes`, `Work Done`, `Tools Used`, `Proof`, `Decisions`, and `Finish`.
   - Do not directly edit `.agent-os/specs.yaml`, `.agent-os/specs/**`, `.agent-os/threads/**`, `.agent-os/runs/RUN-*/context-pack.md`, `.agent-os/runs/RUN-*/spec-snapshot.md`, `.agent-os/runs/RUN-*/plan.md`, `.agent-os/runs/RUN-*/eval.md`, `.agent-os/runs/RUN-*/phases.ndjson`, `.agent-os/runs/RUN-*/step-events.ndjson`, `.agent-os/runs/RUN-*/capability-events.ndjson`, `.agent-os/runs/RUN-*/decision-events.ndjson`, `.agent-os/runs/RUN-*/effect-assertions.ndjson`, `.agent-os/runs/RUN-*/command-events.ndjson`, or `.agent-os/runs/RUN-*/receipt.md`.

7. Finish with the configured sync contract when a shared-fabric kernel module is active.
   - Report `SYNC_OK` only after the postflight command succeeds.
