# Tool Registry

The tool registry adds a visible configuration layer for MCP servers, skills, workflows, orchestration, subagents, and memory tools.

This layer does not make KnowledgeOS execute registered capabilities automatically. It gives agents a single place to inspect what exists, how it should be invoked, and which capabilities need a human gate.

## Why This Exists

Agents are dangerous when they discover tools implicitly and improvise dispatch rules.

KnowledgeOS keeps the rule simple:

```text
route-task chooses the workflow path
-> tool-registry shows available capabilities
-> check-write protects mutation
-> runtime invokes the selected tool only by task intent and policy
```

## Registry File

Each project owns:

```text
.agent-os/tool-registry.yaml
```

Entries are intentionally flat:

```yaml
tools:
  - id: maestro
    kind: orchestrator
    status: recommended
    scope: subagent-orchestration
    invocation: medium_complex_tasks
    human_gate: true
    execution_mode: ask
```

Supported `kind` values:

- `mcp`
- `skill`
- `workflow`
- `orchestrator`
- `subagent`
- `memory`

## Command

Inspect and validate the registry:

```bash
./bin/knowledgeos tool-registry --project-root /path/to/project
```

Also verify absolute `path` or `source_path` entries exist:

```bash
./bin/knowledgeos tool-registry --project-root /path/to/project --check-paths
```

## Current Local Invocation Logic

For this local KnowledgeOS workspace, the intended order is:

```text
MCP
-> capability match, not raw complexity

Skills
-> generated/shared-fabric skills
-> curated local skills
-> broad awesome-skills index only

Orchestration / Subagents
-> Maestro or native runtime for medium/complex tasks
-> execution_mode must remain ask
-> generic unscoped agents are forbidden

Memory
-> MemPalace is recommended for process memory
-> canonical postflight remains the write-back boundary
```

## Safety Checks

`doctor` and `tool-registry` now check:

- tool entries exist;
- ids are unique;
- every entry has `id`, `kind`, `status`, and `invocation`;
- risky MCP/orchestration entries have `human_gate: true`;
- orchestration/subagent entries use `execution_mode: ask`;
- inline secret markers such as API-key assignments are rejected;
- optional `--check-paths` validates local source paths.

## Current Limits

- This is configuration validation, not a live MCP handshake test.
- Runtime-specific MCP health checks still belong to the runtime that owns the tool session.
- Public templates remain opt-in and do not ship enabled network tools.
