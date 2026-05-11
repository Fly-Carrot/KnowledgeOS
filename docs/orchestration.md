# Capability Orchestration

KnowledgeOS routes tools through explicit capability layers.

## Three Levels

1. Global registry: what exists outside the project.
2. Project dispatch policy: which capability order this workspace prefers.
3. Project tool registry: what this workspace can see.
4. Project capability policy: what this project allows.
5. Workflow profile: what this task type should use.

## Golden Route

```text
task.type
-> workflow profile
-> dispatch policy
-> tool registry
-> capability policy
-> branch packet
-> MCP / skill / subagent
-> eval
-> receipt
-> postflight
```

## Recommended Dispatch Priority

```text
Branch Builder planning packets
-> Maestro or native role-specific subagents
-> MCP capability match
-> curated/generated skills
-> registered workflows
-> bounded scripts
-> human gate
```

Subagents should not be generic fallbacks. They should be selected by role, scope, expected output, and human gate.

## Consultation Checkpoints

Agents should pause before execution and before completion. At each pause they should state:

```text
my recommendation
the tradeoff
what I suggest doing next
the question for the human
```

This is part of the product behavior: KnowledgeOS should make agents more proactive and more legible, not merely faster.
