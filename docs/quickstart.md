# Quickstart

This is the first user-facing path for KnowledgeOS.

## 1. Create Or Link The OS Kernel And Capability Layer

KnowledgeOS keeps the project control plane inside `.agent-os/`, while shared kernel and capability registries can live in stable OS-level roots.

```text
KnowledgeOS/
  global-agent-fabric/          # kernel module: boot, phase logs, postflight, memory lanes
  capability-layer/             # MCP, skills, workflows, subagents, adapters
  projects/
    YourProject/
      .agent-os/                # project-local OS control plane
```

The kernel provides boot, phase logging, memory lanes, registries, receipts, and postflight sync.

The capability layer provides MCP adapters, skills, workflows, and custom subagents. It is part of the OS capability surface, not a second source of truth.

Create a minimal runtime root:

```bash
./bin/knowledgeos init-os --os-root /path/to/KnowledgeOSRuntime
```

This creates:

```text
/path/to/KnowledgeOSRuntime/
  global-agent-fabric/
  capability-layer/
```

## 2. Add A Project Control Plane

Copy the project control-plane template into your project:

```text
YourProject/
  AGENTS.md
  .agent-os/
```

Then fill the `CHANGE_ME` placeholders in:

```text
.agent-os/workspace.yaml
.agent-os/project.yaml
.agent-os/fabric-link.yaml
.agent-os/capabilities.yaml
.agent-os/read-policy.yaml
.agent-os/write-policy.yaml
.agent-os/tool-registry.yaml
```

## 3. Define The First Task

Edit `.agent-os/tasks.yaml` and mark one task as `ready`.

A good first task is usually one of:

```text
initialization
migration_inventory
knowledge_structuring
engineering_eval
report_task
archive_management
```

If you invent a new task type, add a route profile for it in `.agent-os/workflows/router.yaml` before asking an agent to mutate files.

## 4. Run The Agent Lifecycle

The agent should follow:

```text
boot
-> route
-> plan
-> review
-> dispatch
-> execute
-> eval
-> receipt
-> postflight
```

## 5. Keep Raw Materials Safe

Put raw inputs in:

```text
materials/raw/
data/raw/
```

Then protect them through `.agent-os/write-policy.yaml`.

For old drafts, obsolete generated outputs, or previous code that should be kept but not used as default context, use cold archive:

```bash
./bin/knowledgeos archive-legacy-project --project-root /path/to/project --write-plan
```

`archive/**` is governed by `.agent-os/read-policy.yaml`: it is storage, not default context.

## 6. Observe The System

A future workbench app should consume:

```text
.agent-os/runs/
.agent-os/receipts/
.agent-os/handoffs/
knowledge/wiki/
knowledge/graph/
```

It should not become the source of truth for governance.

## 7. Use The Executable Control Plane

Core commands:

```bash
./bin/knowledgeos doctor --root /path/to/KnowledgeOS
./bin/knowledgeos init-os --os-root /path/to/KnowledgeOSRuntime
./bin/knowledgeos doctor --project-root /path/to/project
./bin/knowledgeos route-task --project-root /path/to/project --task-id T001
./bin/knowledgeos dispatch-task --project-root /path/to/project --task-id T001
./bin/knowledgeos tool-registry --project-root /path/to/project
./bin/knowledgeos check-write --project-root /path/to/project --path src/main.py
./bin/knowledgeos check-route-write --project-root /path/to/project --task-id T001 --path .agent-os/workspace.yaml
./bin/knowledgeos run-task --project-root /path/to/project --task-id T001
./bin/knowledgeos eval-task --project-root /path/to/project --task-id T001 --run-id RUN-...
./bin/knowledgeos complete-task --project-root /path/to/project --task-id T001 --run-id RUN-... --summary "Task complete."
./bin/knowledgeos reopen-task --project-root /path/to/project --task-id T001 --reason "Rerun required."
./bin/knowledgeos reset-project --project-root /path/to/project --mode soft
./bin/knowledgeos migrate-legacy-project --project-root /path/to/project --write-plan
./bin/knowledgeos archive-legacy-project --project-root /path/to/project --write-plan
```

Command meanings:

```text
doctor       validate the distribution and project control plane
init-project copy the project-control-plane template safely
route-task   map a task id/type to an observable workflow route
dispatch-task build an observable capability plan from dispatch-policy.yaml and tool-registry.yaml
tool-registry inspect MCP, skills, workflows, orchestration, and subagents
check-write  classify a planned write against write-policy.yaml
check-route-write classify a planned write against both write-policy.yaml and the task route allowed_outputs
run-task     create a run envelope for a routed ready/in-progress task
eval-task     write deterministic run eval evidence and output-existence checks
complete-task close a task only after eval-task passes and declared outputs exist
reopen-task  reopen a task for rerun and optionally archive its declared outputs
reset-project reset volatile OS state or archive/remove the project control plane
migrate-legacy-project plan or apply conservative old-folder reorganization
archive-legacy-project plan or apply cold archival for old/superseded content
receipt      write a lightweight local receipt
```

See [Executable Control Plane](executable-control-plane.md).

## 8. Run Doctor Before Agent Work

Before a new agent starts substantial work, run:

```bash
./bin/knowledgeos doctor --project-root /path/to/project
./bin/knowledgeos route-task --project-root /path/to/project --task-id T001
./bin/knowledgeos dispatch-task --project-root /path/to/project --task-id T001
./bin/knowledgeos tool-registry --project-root /path/to/project
./bin/knowledgeos check-route-write --project-root /path/to/project --task-id T001 --path <planned-path>
./bin/knowledgeos agent-guide --project-root /path/to/project
```

This catches unresolved placeholders, missing kernel links, invalid phase keys, incomplete write policy, unsafe capability settings, missing task-type routes, and out-of-route write attempts before the agent mutates files.
