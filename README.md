<div align="center">

# KnowledgeOS

### An intent-driven operating layer for AI agents, knowledge work, and software development.

[![Status](https://img.shields.io/badge/status-working%20prototype-00f5ff?style=for-the-badge&labelColor=0b1020)](docs/LIVE-REPORT.md)
[![AgentOS](https://img.shields.io/badge/AgentOS-control%20plane-7c3aed?style=for-the-badge&labelColor=0b1020)](docs/agentos-architecture.md)
[![CLI](https://img.shields.io/badge/interface-natural%20language%20%2B%20CLI-f97316?style=for-the-badge&labelColor=0b1020)](docs/executable-control-plane.md)
[![Guardrails](https://img.shields.io/badge/guardrails-route%20%2B%20write%20%2B%20eval-22c55e?style=for-the-badge&labelColor=0b1020)](docs/route-bound-execution-guard.md)
[![Capabilities](https://img.shields.io/badge/capabilities-MCP%20%2B%20skills%20%2B%20subagents-38bdf8?style=for-the-badge&labelColor=0b1020)](docs/capability-orchestration.md)
[![Tests](https://img.shields.io/badge/tests-26%20unit%20%2B%2014%20scenarios-10b981?style=for-the-badge&labelColor=0b1020)](examples/scenarios)

![KnowledgeOS hero banner](docs/assets/knowledgeos-hero.svg)

**Natural language is the shell.**<br>
**`.agent-os/` is the control plane.**<br>
**The shared-fabric kernel records boot, phase, memory, and sync.**<br>
**The capability layer routes MCP, skills, workflows, and subagents.**

</div>

---

**Navigate:** [Architecture](docs/agentos-architecture.md) | [Quickstart](docs/quickstart.md) | [CLI](docs/executable-control-plane.md) | [Guardrails](docs/doctor-guardrails.md) | [Router](docs/workflow-router.md) | [Tool Registry](docs/tool-registry.md) | [Reset + Migration](docs/reset-and-migration.md) | [Archive Policy](docs/archive-policy.md)

---

## Download Workbench

KnowledgeOS Workbench is the packaged macOS desktop app for inspecting KnowledgeOS projects.

- **Apple Silicon DMG:** [KnowledgeOS-Workbench-0.1.0-arm64.dmg](https://github.com/Fly-Carrot/KnowledgeOS/releases/download/v0.1.0/KnowledgeOS-Workbench-0.1.0-arm64.dmg)
- **Apple Silicon ZIP:** [KnowledgeOS-Workbench-0.1.0-arm64.zip](https://github.com/Fly-Carrot/KnowledgeOS/releases/download/v0.1.0/KnowledgeOS-Workbench-0.1.0-arm64.zip)
- **Checksums:** [SHA256SUMS.txt](https://github.com/Fly-Carrot/KnowledgeOS/releases/download/v0.1.0/SHA256SUMS.txt)

The app bundles the KnowledgeOS kernel and opens a local read-only bridge on `127.0.0.1`. It is an observation layer for routes, receipts, runs, evidence, and knowledge cards; it does not expose a raw shell, model execution, or project mutation endpoint.

This first public build is ad-hoc signed and not notarized. On macOS, use **Right click -> Open** the first time if Gatekeeper warns about an unidentified developer.

---

## The Short Version

KnowledgeOS turns an ordinary project folder into an **observable agent workspace**.

Instead of letting an AI agent improvise from chat memory, KnowledgeOS gives every project a small operating layer:

- a project control plane under `.agent-os/`;
- a fixed lifecycle for tasks, routes, runs, evals, receipts, and handoffs;
- a write guard that protects raw materials and sensitive paths;
- a cold archive policy for historical files that should be stored but not read by default;
- a capability bus for MCP servers, skills, workflows, subagents, and orchestrators;
- a kernel module for boot discipline, phase logs, memory lanes, and postflight sync;
- a future-ready workbench model for visualizing the whole system.

The philosophy is simple:

> Classifications can stay extensible. The lifecycle must stay fixed.

---

## System Map

```mermaid
flowchart TB
    Human["Human / Final Judge"]:::human
    Intent["Intent\nwhat should happen?"]:::intent

    subgraph Project["Project Workspace"]
        AgentsMd["AGENTS.md\nentry contract"]:::control
        AgentOS[".agent-os/\ncontrol plane"]:::control
        Materials["materials/\nimmutable inputs"]:::data
        Knowledge["knowledge/\nsources, claims, evidence, wiki"]:::knowledge
        Code["src / tests / scripts\nexecution zone"]:::code
        Outputs["outputs / reports / docs\nhuman-facing artifacts"]:::artifact
    end

    subgraph Kernel["KnowledgeOS Kernel Module"]
        Boot["boot / doctor"]:::kernel
        Phase["phase logs"]:::kernel
        Memory["memory lanes"]:::kernel
        Sync["postflight sync"]:::kernel
    end

    subgraph Capability["Capability Layer"]
        MCP["MCP servers"]:::cap
        Skills["skills"]:::cap
        Workflows["workflows"]:::cap
        Subagents["subagents"]:::cap
        Orchestrator["orchestration"]:::cap
    end

    subgraph Runtime["Agent Runtime"]
        Codex["Codex"]:::agent
        Gemini["Gemini CLI"]:::agent
        Other["Other agents"]:::agent
    end

    subgraph Workbench["KnowledgeOS Workbench"]
        Desktop["visual state, evidence lanes, receipts, runs"]:::workbench
    end

    Human --> Intent --> AgentsMd --> AgentOS
    AgentOS --> Boot --> Runtime
    Runtime --> Phase
    Runtime --> Capability
    Capability --> Runtime
    Runtime --> Materials
    Runtime --> Knowledge
    Runtime --> Code
    Runtime --> Outputs
    Runtime --> Sync --> Memory
    Phase --> AgentOS
    Memory --> Runtime
    AgentOS --> Desktop
    Outputs --> Desktop

    classDef human fill:#fef3c7,stroke:#f59e0b,color:#111827
    classDef intent fill:#ffedd5,stroke:#f97316,color:#111827
    classDef control fill:#ede9fe,stroke:#7c3aed,color:#111827
    classDef data fill:#ecfeff,stroke:#06b6d4,color:#111827
    classDef knowledge fill:#dcfce7,stroke:#22c55e,color:#111827
    classDef code fill:#e0f2fe,stroke:#0284c7,color:#111827
    classDef artifact fill:#fce7f3,stroke:#db2777,color:#111827
    classDef kernel fill:#111827,stroke:#00f5ff,color:#ffffff
    classDef cap fill:#0f172a,stroke:#38bdf8,color:#ffffff
    classDef agent fill:#1e1b4b,stroke:#818cf8,color:#ffffff
    classDef workbench fill:#020617,stroke:#a3e635,color:#ffffff
```

---

## Why This Feels Like An OS

Most agent workflows are powerful but loose. They can read files, write code, call tools, summarize papers, and draft reports, but they often lack the basic operating discipline that normal computers rely on.

KnowledgeOS adds that missing discipline:

| OS idea | KnowledgeOS equivalent | What it gives agents |
|---|---|---|
| Shell | Natural language intent | A human-friendly command surface |
| System calls | `knowledgeos` CLI | Deterministic operations with evidence |
| Process state | `.agent-os/tasks.yaml` and runs | Task lifecycle and run receipts |
| File permissions | write policy and route guard | Dirty-write prevention |
| Drivers | capability layer | MCP, skills, workflows, subagents |
| Kernel logs | phase logs and receipts | Observable work history |
| Mount table | workspace and fabric links | Project-to-kernel connectivity |
| Desktop | KnowledgeOS Workbench | Visual inspection and trust-building |

This is not a replacement for macOS, VS Code, the terminal, Obsidian, Codex, Gemini CLI, or MCP. It is the control layer that lets them behave like one auditable agent system.

---

## Core Flow

```text
intent
  -> context loading
  -> doctor
  -> route
  -> dispatch
  -> write guard
  -> run envelope
  -> eval
  -> complete
  -> receipt
  -> postflight sync
```

Every meaningful task should leave evidence. No invisible success claims, no silent route changes, no untracked output sprawl.

---

## Quick Start

Run the low-token health check:

```bash
./bin/knowledgeos doctor --root . --project-root . --summary
```

Create a clean KnowledgeOS runtime in another location:

```bash
./bin/knowledgeos init-os --os-root /path/to/KnowledgeOSRuntime
```

Initialize an existing project folder:

```bash
./bin/knowledgeos init-project --project-root /path/to/project --name "My Project"
```

Route and execute a task with evidence:

```bash
./bin/knowledgeos route-task --project-root /path/to/project --task-id T001
./bin/knowledgeos dispatch-task --project-root /path/to/project --task-id T001
./bin/knowledgeos check-route-write --project-root /path/to/project --task-id T001 --path docs/plan.md
./bin/knowledgeos run-task --project-root /path/to/project --task-id T001
./bin/knowledgeos context-pack --project-root /path/to/project --task-id T001 --run-id RUN-...
./bin/knowledgeos plan-task --project-root /path/to/project --task-id T001 --run-id RUN-... --summary "Task plan."
./bin/knowledgeos eval-task --project-root /path/to/project --task-id T001 --run-id RUN-...
./bin/knowledgeos verify-context --project-root /path/to/project --task-id T001 --run-id RUN-...
./bin/knowledgeos verify-lifecycle --project-root /path/to/project --task-id T001 --run-id RUN-...
./bin/knowledgeos complete-task --project-root /path/to/project --task-id T001 --run-id RUN-... --summary "Task complete."
```

For old projects, generate a safe migration plan before moving files:

```bash
./bin/knowledgeos migrate-legacy-project --project-root /path/to/project --write-plan
```

For project reset and recovery:

```bash
./bin/knowledgeos reset-project --project-root /path/to/project --mode soft --dry-run
./bin/knowledgeos reopen-task --project-root /path/to/project --task-id T001 --reason "Rerun required."
```

---

## What Is In The Repository

```text
.agent-os/                  local KnowledgeOS control-plane example
bin/knowledgeos             CLI entrypoint
knowledgeos/                Python implementation
examples/scenarios/         distracted-agent guardrail tests
templates/governance-core/  minimal kernel module template
templates/capability-layer/ MCP, skills, workflows, subagents, agents, registries
templates/project-control-plane/ project bootstrap template
templates/project-control-plane/archive/ cold-storage convention for superseded project material
docs/                       architecture, guardrails, routing, reset, orchestration
```

The public repository intentionally excludes local runtime history, personal paths, private generated capability content, and machine-specific receipts.

---

## Verified Guardrails

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

Current checked baseline:

- `doctor --summary`: 389 checks passing in the local project.
- Clean public export: 371 checks passing outside the original working tree.
- Unit tests: 26 passing.
- Guardrail scenarios: 14 checkpoints passing.

The scenario suite verifies that distracted-agent mistakes are blocked by doctor, route, write, dispatch, and eval gates.

---

## Read Next

- [AgentOS Architecture](docs/agentos-architecture.md)
- [Quickstart](docs/quickstart.md)
- [Executable Control Plane](docs/executable-control-plane.md)
- [Doctor Guardrails](docs/doctor-guardrails.md)
- [Workflow Router](docs/workflow-router.md)
- [Tool Registry](docs/tool-registry.md)
- [Route-Bound Execution Guard](docs/route-bound-execution-guard.md)
- [Capability-Oriented Orchestration](docs/capability-orchestration.md)
- [Reset And Legacy Migration](docs/reset-and-migration.md)
- [Cold Archive Policy](docs/archive-policy.md)

---

## Project Status

KnowledgeOS is a working prototype and design manifesto for turning AI-agent workspaces into governed, inspectable systems. The current focus is the **knowledge + development AgentOS** form: a system for research writing, literature synthesis, grant drafting, codebase maintenance, reproducible analysis, project migration, and long-horizon agentic development.

KnowledgeOS Workbench is the current visual desktop for this OS layer: not the source of truth, but the place where humans inspect routes, receipts, artifacts, memory, graph state, and agent decisions. Download the packaged macOS app from the GitHub Release; generated desktop binaries live in Releases, not in the source tree.
