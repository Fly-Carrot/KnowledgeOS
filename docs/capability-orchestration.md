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

After `run-task` creates a run id, bind the dispatch decision to the run ledger:

```bash
./bin/knowledgeos dispatch-task --project-root /path/to/project --task-id T001 --run-id RUN-... --json
```

If an agent uses MCP, a skill, a subagent, an orchestrator, or an important script, it records the visible call:

```bash
./bin/knowledgeos capability-event \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --kind mcp \
  --id markitdown \
  --purpose "Convert reference document into reviewable text."
```

The command returns `CAPABILITY_OK` and writes public evidence into the run ledger. It does not execute the tool itself.

## Why Branch Builder Comes First

Branch Builder is the planning layer for medium or complex root tasks. It should be considered before invoking registered capabilities because it helps split the work into bounded branches and prevents premature tool calls.

## Why Orchestrators/Subagents Come Before MCP And Skills

For complex work, the first question is not always "which tool can do this?".

The better first question is:

```text
What roles or expert perspectives should inspect this task before action?
```

That is why Maestro or native role-specific subagents come before MCP and skills in the default dispatch order.

An orchestrator and a subagent are related but not identical:

- `orchestrator`: coordinates many agents, branches, worktrees, and review loops;
- `subagent`: performs one bounded role-specific task;
- `skill`: provides reusable method instructions;
- `MCP`: exposes an external tool or data interface;
- `script`: runs deterministic local work.

KnowledgeOS can register an external orchestrator adapter without copying its runtime into the project. Optional external adapters can remain visible in the registry, but they should not be treated as active subagent catalogs unless their individual agents are discoverable and registered.

The active local specialist-agent catalog is currently **Maestro Orchestrate** (`josstei/maestro-orchestrate`). It exposes 39 specialist agents and a Codex MCP server. Locally, Codex already has `mcp_servers.maestro` configured; KnowledgeOS registers that interface as `maestro-mcp` and registers each specialist as a `maestro-*` `subagent` entry.

Maestro's Codex runtime resolves agent methodology through MCP:

```text
maestro-mcp
-> get_runtime_context
-> get_agent(["architect", "coder", "security-engineer", ...])
-> spawn_agent(...) when delegation is useful
```

That means the MCP server retrieves the agent methodology and runtime context; the actual subagent execution still goes through Codex delegation (`spawn_agent`) or the host runtime's equivalent. KnowledgeOS records both surfaces:

- `maestro`: active orchestrator layer;
- `maestro-mcp`: MCP interface for runtime context, skill content, plan validation, and agent methodology;
- `maestro-*`: 39 visible specialist subagent entries, including `maestro-architect`, `maestro-coder`, `maestro-security-engineer`, `maestro-code-reviewer`, and `maestro-tester`.

ComposioHQ Agent Orchestrator remains an optional external worktree/PR orchestration adapter. It is not the active source of the 39 specialist agents.

## Public Operational Trace

Capability dispatch should not be the only visible trace. Agents should also record the main OS steps as public operational trace, without saving hidden chain-of-thought:

```bash
./bin/knowledgeos trace-step \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --step doctor_gate \
  --note "Doctor passed before mutation." \
  --evidence "doctor --summary"
```

The command returns `TRACE_OK` and writes `.agent-os/runs/<RUN_ID>/step-events.ndjson`. This is for user-visible progress such as `user_intent`, `load_rules`, `doctor_gate`, `task_intake`, `route_guard`, `dispatch_plan`, `write_guard`, `execution`, `eval`, `verify`, `complete`, and `sync`.

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
- required dispatch stages are either recorded through `capability-event` or explicitly skipped with a public reason;
- unknown task types require human triage.
