# KnowledgeOS

KnowledgeOS is an intent-driven operating layer for knowledge work and software development with AI agents.

It is not a replacement for your editor, terminal, Obsidian vault, or agent runtime. It is the control plane that makes them behave like one observable system.

## What It Does

KnowledgeOS gives agents a shared way to:

- load project context before acting;
- classify the task and choose a workflow;
- select capabilities through an observable dispatch policy;
- pause at opinion checkpoints before risky or important next steps;
- protect raw materials and sensitive files from dirty writes;
- route work through MCP tools, skills, workflows, and subagents;
- record decisions, runs, artifacts, receipts, and handoffs;
- write memory back through the OS kernel module;
- let a workbench app visualize the project state.

The core principle is:

> Classifications can stay extensible, but the task lifecycle must stay fixed.

## Core Flow

```text
intent
-> context loading
-> route
-> plan
-> review
-> dispatch
-> execute
-> eval
-> receipt
-> postflight
```

## Layers

```text
Project folder
  .agent-os/                  # workspace control plane
  materials/                  # immutable or lightly curated inputs
  knowledge/                  # extracted sources, claims, evidence, wiki
  src/ tests/ scripts/        # engineering execution zone
  outputs/ reports/ docs/     # generated and human-facing outputs

KnowledgeOS OS layer
  global-agent-fabric/        # kernel module: boot, phase logs, postflight, memory lanes
  capability-layer/           # capability registries: MCP, skills, workflows, subagents
  .agent-os/                  # project-local control plane and runtime state

Future Workbench App
  consumes receipts, wiki, graph, source artifacts, runtime logs
```

## Current Status

This repository is being built gradually. See [docs/LIVE-REPORT.md](docs/LIVE-REPORT.md) for the live construction report.

For a GitHub-ready architecture narrative, see [KnowledgeOS: Turning Agents Into An Operating System For Knowledge Work](docs/agentos-architecture.md). It explains the AgentOS idea, color-layer architecture, folder semantics, natural-language-to-CLI calling logic, reset/migration recovery model, and how this work relates to agent-readable knowledge-base patterns such as LLM Wiki.

## Executable Control Plane

KnowledgeOS includes a small standard-library CLI:

```bash
./bin/knowledgeos doctor --root .
./bin/knowledgeos doctor --root . --project-root . --summary
./bin/knowledgeos init-os --os-root /path/to/KnowledgeOSRuntime
./bin/knowledgeos init-project --project-root /path/to/project --name "My Project"
./bin/knowledgeos doctor --project-root /path/to/project
./bin/knowledgeos route-task --project-root /path/to/project --task-id T001
./bin/knowledgeos dispatch-task --project-root /path/to/project --task-id T001
./bin/knowledgeos tool-registry --project-root /path/to/project
./bin/knowledgeos check-write --project-root /path/to/project --path src/main.py
./bin/knowledgeos check-route-write --project-root /path/to/project --task-id T001 --path .agent-os/workspace.yaml
./bin/knowledgeos agent-guide --project-root /path/to/project
./bin/knowledgeos run-task --project-root /path/to/project --task-id T001
./bin/knowledgeos eval-task --project-root /path/to/project --task-id T001 --run-id RUN-...
./bin/knowledgeos complete-task --project-root /path/to/project --task-id T001 --run-id RUN-... --summary "Task complete."
./bin/knowledgeos reopen-task --project-root /path/to/project --task-id T001 --reason "Rerun required."
./bin/knowledgeos reset-project --project-root /path/to/project --mode soft
./bin/knowledgeos migrate-legacy-project --project-root /path/to/project --write-plan
./bin/knowledgeos receipt --project-root /path/to/project --summary "Checkpoint."
```

Development checks:

```bash
make doctor
make doctor-summary
make route
make tools
make dispatch
make guard
make scenarios
make test
make smoke
```

`doctor --summary` is the low-token health check for routine agent loops. It prints aggregate pass/fail counts and only expands failed checks. The full `doctor` output remains available when you need detailed evidence.

Executable guardrail scenarios live under [examples/scenarios](examples/scenarios). They create temporary projects and verify that distracted-agent mistakes are blocked by doctor, route, write, dispatch, and eval gates.

Functional references: [AgentOS Architecture](docs/agentos-architecture.md), [Executable Control Plane](docs/executable-control-plane.md), [Doctor Guardrails](docs/doctor-guardrails.md), [Workflow Router](docs/workflow-router.md), [Tool Registry](docs/tool-registry.md), [Route-Bound Execution Guard](docs/route-bound-execution-guard.md), [Capability-Oriented Orchestration](docs/capability-orchestration.md), and [Reset And Legacy Migration](docs/reset-and-migration.md).
