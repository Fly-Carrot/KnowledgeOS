# KnowledgeOS Decision Graph Module

Decision Graph is an optional KnowledgeOS module for public, auditable decision summaries. It records how a task plan branches, changes, rolls back, abandons a route, or reaches a final decision.

It is not a hidden chain-of-thought store. It saves concise natural-language decisions that a human can read later.

## Why It Exists

Research and long-running agent work are rarely pure automation. A task may start with one plan, insert a new check, abandon a later branch, or roll back after evidence changes. Linear traces say what happened; Decision Graph records why the path changed.

## Evidence Lane

```text
File: .agent-os/runs/<RUN_ID>/decision-events.ndjson
Command: decision-event
Marker: DECISION_OK
Verifier: verify-decisions
Verify Marker: DECISION_VERIFY_OK
HTML: render-html --kind decision-map
```

Decision Graph complements the existing lanes:

```text
trace-step        what happened
phase-task        which lifecycle checkpoint passed
capability-event  which tool or agent capability was used
artifact-assert   which real side effect landed
decision-event    why the route changed or was selected
```

## Commands

Record a public decision:

```bash
knowledgeos decision-event \
  --project-root . \
  --task-id T001 \
  --run-id RUN-... \
  --kind branch_selected \
  --status selected \
  --title "Use targeted rerun" \
  --summary "Select the smaller validation path." \
  --reason "It proves the changed artifact without repeating expensive work." \
  --evidence "plan review"
```

Query the graph:

```bash
knowledgeos decision-query --project-root . --run-id RUN-... --parent-id DEC-...
```

Verify command-generated decision evidence:

```bash
knowledgeos verify-decisions --project-root . --task-id T001 --run-id RUN-...
```

Render a human-readable sidecar:

```bash
knowledgeos render-html --project-root . --run-id RUN-... --kind decision-map
```

## Policy

Project policy lives at `.agent-os/decision-policy.yaml`:

```yaml
decision_policy:
  strictness: warn
  downgrade_reason: ""
```

Supported strictness values:

- `warn`: default; missing decision events warn but do not block completion.
- `enforce`: completion fails when decision evidence is missing or invalid.
- `off`: allowed only with a `downgrade_reason`.

## When To Use

Use `decision-event` when one of these happens:

- a plan branches;
- a route is selected among alternatives;
- a new step is inserted mid-task;
- a branch is abandoned, deferred, superseded, or rolled back;
- the human makes a meaningful decision;
- a risk tradeoff changes execution.

Do not use it for ordinary linear progress. Use `trace-step` for that.

## Module Boundary

Decision Graph is a module, not kernel. The kernel remains small: route, write guard, lifecycle, eval, effect verification, and completion. Decision Graph can be enforced by project policy when a research, strict, or release project needs stronger auditability.
