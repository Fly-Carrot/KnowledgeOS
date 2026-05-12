# Workflow Router

The workflow router adds a small, observable routing layer.

KnowledgeOS does not try to guess a perfect universal taxonomy. Instead, it keeps the lifecycle fixed and makes task-type routing explicit.

## Why This Exists

Different task types should move through the OS differently:

- a migration task should inventory first and avoid copying secrets;
- a template task should validate placeholders intentionally;
- an engineering task should route through tests and write guards;
- a knowledge task should protect raw materials and preserve source traceability.

The router makes that decision visible before an agent mutates files.

## Router File

Each project owns:

```text
.agent-os/workflows/router.yaml
```

A route profile maps a task `type` to:

- ordered command hints;
- eval profile;
- human gate;
- allowed output zones;
- notes for the agent.

Example:

```yaml
workflows:
  initialization:
    route_order:
      - doctor --project-root .
      - route-task --project-root . --task-id <task-id>
      - check-route-write --project-root . --task-id <task-id> --path <planned-path>
      - run-task --project-root . --task-id <task-id>
      - context-pack --project-root . --task-id <task-id> --run-id <run-id>
      - plan-task --project-root . --task-id <task-id> --run-id <run-id> --summary <summary>
      - eval-task --project-root . --task-id <task-id> --run-id <run-id>
      - verify-context --project-root . --task-id <task-id> --run-id <run-id>
      - verify-lifecycle --project-root . --task-id <task-id> --run-id <run-id>
      - complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary <summary>
    eval_profile: workspace_initialization
    human_gate: review_generated_control_plane
    allowed_outputs:
      - .agent-os/
      - AGENTS.md
```

## Command

Resolve a concrete task:

```bash
./bin/knowledgeos route-task --project-root /path/to/project --task-id T001
```

Resolve only a task type:

```bash
./bin/knowledgeos route-task --project-root /path/to/project --task-type initialization
```

If a task type has no route profile, the command exits non-zero and returns `human_triage_required`. That is deliberate. Unknown categories are allowed, but they need triage before mutation.

## Relationship To Hooks And Skills

The router does not replace hooks, skills, or subagents.

```text
hook      = enforces boot / phase / postflight boundary
router    = selects the intended workflow path
skill     = performs a specialized capability inside dispatch
subagent  = performs bounded delegated work when allowed
```

This keeps the system simple: routing is observable planning metadata, not hidden automation.

## Current Limits

- The router reads a small KnowledgeOS-owned YAML-like format, not arbitrary YAML.
- It does not execute the route order; the agent or host runtime still performs the commands.
- Later phases can add richer workflow profiles, eval binding, and workbench visualization.
