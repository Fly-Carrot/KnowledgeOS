# KnowledgeOS Architecture

KnowledgeOS has three primary layers.

## 1. Context Layer

The user's real project files live here.

```text
materials/   raw inputs and references
knowledge/   structured sources, claims, evidence, methods, concepts, wiki
src/          code
tests/        tests and reproducibility checks
outputs/      generated figures, tables, models, logs
reports/      human-facing drafts and final reports
docs/         project documentation
```

## 2. Control Layer

The project-local control plane lives in `.agent-os/`.

```text
.agent-os/
  workspace.yaml
  project.yaml
  tasks.yaml
  decisions.yaml
  evals.yaml
  artifacts.yaml
  fabric-link.yaml
  capabilities.yaml
  dispatch-policy.yaml
  tool-registry.yaml
  write-policy.yaml
  workflows/
  runs/
  receipts/
  handoffs/
  inbox/
```

This layer tells agents what the workspace is, what is allowed, which tools are visible, what is finished, what is risky, and how to report work.

The executable guard path is:

```text
doctor
  validate structure and route/eval consistency
route-task
  select the workflow profile for the current task
dispatch-task
  recommend Branch Builder / orchestrator / subagent / MCP / skill / script order
check-route-write
  allow writes only when both write-policy and route.allowed_outputs agree
run-task
  create run evidence only for routed ready/in-progress tasks
context-pack / plan-task
  freeze active spec, current context, and public execution plan before work
complete-task
  close task state only after context, lifecycle, eval, outputs, and postflight gates pass
```

This makes the project control plane a route-bound harness rather than a purely advisory checklist.

The consultation layer makes agents pause before execution and completion, state their recommended next move, name the tradeoff, and ask for human approval when the policy calls for it.

## 3. OS Kernel And Capability Layer

KnowledgeOS treats shared governance and reusable capabilities as OS-layer modules. They may be physically stored in stable shared roots, but they are mounted into the project through `.agent-os/fabric-link.yaml` and `.agent-os/tool-registry.yaml`.

```text
global-agent-fabric/         kernel module for boot, phase logs, postflight, memory lanes
capability-layer/            capability registries for MCP, skills, workflows, subagents
.agent-os/tool-registry.yaml project-local capability view
```

`init-os` can generate a clean minimal `global-agent-fabric/` and `capability-layer/` for a new user. Existing advanced users can still point `.agent-os/fabric-link.yaml` at an already-managed kernel.

The important boundary is not "inside vs outside the folder." The important boundary is source of truth:

- `.agent-os/` owns project state, routes, write guards, and receipts.
- `global-agent-fabric/` owns shared runtime discipline and memory lanes.
- `capability-layer/` owns reusable capability adapters.
- A future desktop workbench can consume these outputs; it does not own governance.
