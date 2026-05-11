# Doctor Guardrails

Doctor guardrails make KnowledgeOS harder to misuse by turning `doctor` into the single validation entrypoint.

The goal is not just to check whether files exist. The goal is to detect cases where an agent could start work with the wrong project state, unresolved placeholders, unsafe tool policy, missing kernel links, ambiguous write permissions, or missing workflow routes.

## Command

Run project validation:

```bash
./bin/knowledgeos doctor --project-root /path/to/project
```

Template validation is explicit:

```bash
./bin/knowledgeos doctor --project-root templates/project-control-plane --template
```

Useful options:

```bash
./bin/knowledgeos doctor --project-root /path/to/project --json
./bin/knowledgeos doctor --project-root /path/to/project --allow-placeholders
./bin/knowledgeos doctor --project-root /path/to/project --skip-linked-checks
```

`doctor --project-root` is the only project validation entrypoint.

## What Doctor Checks

- required `.agent-os` files;
- unresolved `CHANGE_ME` placeholders;
- workspace identity and project root;
- project metadata;
- Shared Fabric kernel link;
- runtime contract flags;
- exact phase keys;
- write-policy sections;
- forbidden write coverage for `.env`, secrets, and final reports;
- task ids, task statuses, and required task fields;
- decision ids;
- eval profiles;
- artifact ids;
- capability guardrails such as `execution_mode: ask`;
- workflow route coverage for every declared task type.

## Agent Guide

Generate an operational checklist for agents:

```bash
./bin/knowledgeos agent-guide --project-root /path/to/project
```

Write it to a file:

```bash
./bin/knowledgeos agent-guide \
  --project-root /path/to/project \
  --output /path/to/project/.agent-os/handoffs/agent-guide.md
```

## Error-Call Risks Now Covered

### Unresolved Templates

Risk:

```text
An agent starts work while workspace.yaml still contains CHANGE_ME placeholders.
```

Mitigation:

```text
doctor fails unless --allow-placeholders or --template is explicitly used.
```

### Wrong Kernel Link

Risk:

```text
An agent thinks Shared Fabric is mounted, but the path does not exist.
```

Mitigation:

```text
doctor checks governance_root and capability_root unless --skip-linked-checks or --template is used.
```

### Wrong Phase Discipline

Risk:

```text
An agent invents phase names or skips the lifecycle contract.
```

Mitigation:

```text
doctor checks the exact phase keys: route, plan, review, dispatch, execute, report.
```

### Unsafe Writes

Risk:

```text
An agent writes to raw data, final reports, secrets, or unclassified paths.
```

Mitigation:

```text
check-write classifies planned paths; doctor checks write-policy coverage.
```

### Over-Autonomous Subagents

Risk:

```text
An orchestrator dispatches subagents without a human gate.
```

Mitigation:

```text
doctor checks execution_mode: ask when declared.
```

## Smoke Test

Current smoke runs:

```text
doctor
-> route-task
-> unittest suite
```

## Current Limits

- `doctor` is schema-aware rather than a full YAML validator.
- It detects unsafe configuration before work starts; it does not yet intercept runtime writes.
- Capability routing is checked as policy; actual MCP / skill / subagent dispatch remains runtime-specific.
