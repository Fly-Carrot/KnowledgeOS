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

4. Start work through a run envelope.
   - `knowledgeos route-task --project-root . --task-id <task-id>`
   - `knowledgeos dispatch-task --project-root . --task-id <task-id>`
   - `knowledgeos run-task --project-root . --task-id <task-id>`
   - `knowledgeos context-pack --project-root . --task-id <task-id> --run-id <run-id>`
   - `knowledgeos plan-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`
   - `knowledgeos archive-legacy-project --project-root . --write-plan` before cold-archiving old or superseded content.

5. Never bypass the write guard.
   - Immutable paths are denied.
   - Human-gated paths require explicit approval.
   - Unclassified paths should be triaged before mutation.
   - `archive/**` is cold storage and is not default context.

6. Keep receipts local and command-generated.
   - Use `knowledgeos phase-task --project-root . --task-id <task-id> --run-id <run-id> --phase <phase> --status completed --note "<public note>" --evidence "<command or file evidence>"`.
   - Use `knowledgeos eval-task --project-root . --task-id <task-id> --run-id <run-id>`; do not hand-write `Status: passed`.
   - Use `knowledgeos verify-context --project-root . --task-id <task-id> --run-id <run-id>`.
   - Use `knowledgeos verify-lifecycle --project-root . --task-id <task-id> --run-id <run-id>`.
   - Use `knowledgeos complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary "<summary>"`.
   - Do not directly edit `.agent-os/specs.yaml`, `.agent-os/specs/**`, `.agent-os/runs/RUN-*/context-pack.md`, `.agent-os/runs/RUN-*/spec-snapshot.md`, `.agent-os/runs/RUN-*/plan.md`, `.agent-os/runs/RUN-*/eval.md`, `.agent-os/runs/RUN-*/phases.ndjson`, `.agent-os/runs/RUN-*/command-events.ndjson`, or `.agent-os/runs/RUN-*/receipt.md`.

7. Finish with the configured sync contract when a shared-fabric kernel module is active.
   - Report `SYNC_OK` only after the postflight command succeeds.
