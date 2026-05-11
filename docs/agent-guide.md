# KnowledgeOS Agent Guide

Use this checklist before substantial work in a KnowledgeOS-controlled project.

1. Read the project entry contract.
   - `AGENTS.md`

2. Load project control state.
   - `.agent-os/workspace.yaml`
   - `.agent-os/project.yaml`
   - `.agent-os/tasks.yaml`
   - `.agent-os/decisions.yaml`
   - `.agent-os/evals.yaml`
   - `.agent-os/capabilities.yaml`
   - `.agent-os/write-policy.yaml`

3. Run checks before acting.
   - `knowledgeos doctor --project-root . --summary`
   - `knowledgeos check-write --project-root . --path <planned-path>`

4. Start work through a run envelope.
   - `knowledgeos route-task --project-root . --task-id <task-id>`
   - `knowledgeos dispatch-task --project-root . --task-id <task-id>`
   - `knowledgeos run-task --project-root . --task-id <task-id>`

5. Never bypass the write guard.
   - Immutable paths are denied.
   - Human-gated paths require explicit approval.
   - Unclassified paths should be triaged before mutation.

6. Keep receipts local and concise.
   - Update `.agent-os/runs/RUN-*/receipt.md`.
   - Update `.agent-os/runs/RUN-*/eval.md`.
   - Update `.agent-os/handoffs/current.md`.

7. Finish with the configured sync contract when a shared-fabric kernel module is active.
   - Report `SYNC_OK` only after the postflight command succeeds.
