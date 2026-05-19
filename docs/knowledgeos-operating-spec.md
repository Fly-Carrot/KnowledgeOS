# KnowledgeOS Operating Architecture

This document is the detailed companion to the root `SPEC.md`.

## Product Doctrine

```text
KnowledgeOS = small kernel + pluggable modules + optional apps + project-level strictness + mandatory checkpoint reporting
```

The architecture is designed to keep the kernel small while making long-running agent work observable and auditable.

## Kernel Boundary

The kernel is the always-on control path:

```text
doctor
-> task intake
-> route-task
-> check-route-write
-> run-task
-> eval-task
-> verify-context
-> verify-lifecycle
-> verify-effects
-> complete-task
```

The kernel owns:

- `.agent-os/` control-plane files;
- run envelopes under `.agent-os/runs/`;
- receipts and handoffs;
- write policy and route policy;
- completion and postflight gates.

The kernel does not own app layout, model UX, or optional specialist workflows.

## Module Boundary

Modules are invoked by task intent, route policy, or project profile.

Current and planned modules include:

- `spec`: durable user intent, context pack, plan, and drift checks;
- `capability`: dispatch policy, tool registry, and capability events;
- `archive`: cold storage for old or superseded project content;
- `migration`: old-project reorganization plans;
- `harness`: cross-project audit and repair;
- `adapters`: optional external runtime bridges.

Modules must write public command evidence when their output affects a task. They should not expand the kernel unless they are required for safety.

## App Boundary

Apps are optional work surfaces.

The Workbench should read:

- `.agent-os/tasks.yaml`;
- `.agent-os/runs/`;
- `.agent-os/specs/`;
- receipts and handoffs;
- evidence lanes.

The Workbench should not directly replace:

- route guards;
- write guards;
- eval gates;
- lifecycle verification;
- postflight sync.

If a future app button performs a mutation, it must show the exact KnowledgeOS command, ask for confirmation, and write command evidence through the CLI.

## Project Strictness

Projects should choose strictness through a future profile or feature file.

Recommended profiles:

- `minimal`: kernel gates only;
- `standard`: kernel plus context, plan, checkpoint, and capability visibility;
- `strict`: standard plus stronger spec and release checks;
- `research`: strict spec/context tracking and artifact discipline;
- `release`: strict verification, security review, and postflight requirements.

Checkpoint reporting should remain mandatory for substantial managed work even when optional modules are disabled.

## Evidence Lanes

KnowledgeOS separates evidence into four lanes.

### Public Operational Trace

```text
File: .agent-os/runs/<RUN_ID>/step-events.ndjson
Command: trace-step
Marker: TRACE_OK
```

This lane records visible operating progress: user intent, loading rules, doctor gate, task intake, route guard, dispatch plan, write guard, execution, eval, verify, complete, and sync.

### Lifecycle Checkpoints

```text
File: .agent-os/runs/<RUN_ID>/phases.ndjson
Command: phase-task
Marker: CHECKPOINT_OK
```

This lane records the fixed six-phase lifecycle:

```text
route -> plan -> review -> dispatch -> execute -> report
```

### Capability Visibility

```text
File: .agent-os/runs/<RUN_ID>/capability-events.ndjson
Command: capability-event
Marker: CAPABILITY_OK
```

This lane records visible use of:

- MCP;
- skills;
- subagents;
- orchestrators;
- scripts;
- shell commands;
- file reads.

Required dispatch stages must be recorded or explicitly skipped with a public reason.

### Completion And Sync

```text
File: .agent-os/runs/<RUN_ID>/postflight.md
Command: complete-task
Marker: SYNC_OK
```

This lane proves the task closed through the completion gate and postflight contract.

## Full Task Chain

A substantial managed task should follow this chain:

```text
User Intent
-> Load Rules
-> Doctor Gate
-> Task Intake
-> Spec Alignment
-> Route Guard
-> Dispatch Plan
-> Write Guard
-> Run Envelope
-> Context Pack
-> Plan Task
-> Execution
-> Capability Visibility
-> Phase Checkpoints
-> Eval
-> Verify
-> Complete
-> Sync
```

`trace-step` explains the operational path. `phase-task` proves the lifecycle checkpoints. `capability-event` proves tool and agent visibility. `complete-task` proves closure and sync.

## Doctor And Repair Tools

`doctor` is diagnostic only. It answers whether a control plane is healthy.

Repair actions must use explicit tools:

- `harness-audit --repair`;
- `init-os`;
- `init-project`;
- `migrate-legacy-project`;
- `archive-legacy-project`;
- `reset-project`.

This keeps health checks safe and predictable.

## Public Sharing Rule

Public documentation should describe portable concepts and generic paths. Local machine details, private roots, secrets, browser profiles, private chat histories, and provider credentials must not be copied into public docs or templates.

## Design Rule

When adding a feature, decide where it belongs:

- kernel if it is required for safety or completion;
- module if it extends a task class or project profile;
- app if it visualizes or operates existing OS state;
- project config if it chooses strictness.

This rule prevents KnowledgeOS from becoming a monolithic hook.
