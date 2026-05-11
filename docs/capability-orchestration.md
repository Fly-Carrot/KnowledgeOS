# Capability-Oriented Orchestration

The capability orchestration layer starts turning KnowledgeOS from a safe execution harness into an intelligent AgentOS scheduler.

The goal is not to let agents improvise tools freely. The goal is to make capability selection visible, policy-driven, and reviewable.

## Product Position

KnowledgeOS should help agents become more proactive, not more reckless.

For medium or complex work, an agent should pause at defined checkpoints, state its view of the next best move, explain the tradeoff, and ask the human whether to proceed.

This creates a rhythm:

```text
agent proposes
-> human judges
-> agent executes within guardrails
-> evidence is recorded
```

## New Control File

### `.agent-os/dispatch-policy.yaml`

The dispatch policy defines the preferred capability order:

```text
branch_builder
-> orchestrator
-> subagent
-> mcp
-> skill
-> script
-> human_gate
```

It also defines consultation checkpoints and risks that require human attention.

## New Command

### `dispatch-task`

`dispatch-task` reads:

- `.agent-os/tasks.yaml`
- `.agent-os/workflows/router.yaml`
- `.agent-os/dispatch-policy.yaml`
- `.agent-os/tool-registry.yaml`

Then it returns an observable dispatch plan.

Example:

```bash
./bin/knowledgeos dispatch-task --project-root /path/to/project --task-id T001 --json
```

The output includes:

- task metadata;
- route metadata;
- recommended capability stages;
- matching registered tools;
- consultation checkpoints;
- an explicit agent-opinion prompt.

## Why Branch Builder Comes First

Branch Builder is the planning layer for medium or complex root tasks. It should be considered before invoking registered capabilities because it helps split the work into bounded branches and prevents premature tool calls.

## Why Orchestrators/Subagents Come Before MCP And Skills

For complex work, the first question is not always "which tool can do this?".

The better first question is:

```text
What roles or expert perspectives should inspect this task before action?
```

That is why Maestro or native role-specific subagents come before MCP and skills in the default dispatch order.

## Consultation Policy

Agents must pause before:

- execution;
- completion.

For risky work, agents must also ask before actions involving:

- external writes;
- release actions;
- destructive changes;
- private account access;
- browser automation.

The expected agent behavior is:

```text
My recommendation is ...
The tradeoff is ...
I suggest doing ... next.
Do you want me to proceed?
```

This is intentionally a product feature: KnowledgeOS should make agents more thoughtful and more collaborative, not just faster.

## Verification

Capability orchestration tests verify that:

- `dispatch-task` returns a dispatch-ready plan for `KOS-T009`;
- Branch Builder is prioritized before orchestration;
- orchestration appears before lower-level capability use;
- consultation checkpoints include execution and completion;
- unknown task types require human triage.
