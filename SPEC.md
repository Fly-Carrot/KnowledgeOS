# KnowledgeOS Operating Spec

KnowledgeOS is a project constraints, research evidence and handoff layer.
Codex or another host executes the work.

## Current Workflow Contract (v0.3.0)

Unmanaged directories work normally without initialization prompts or automatic
control-plane creation. Simple questions require no managed task. Explicitly
adopted, eligible new ordinary runs use `run-task`, actual work and verification,
`eval-task`, then `complete-task`. They end with one truthful receipt: status,
verification and record link, including unresolved checks or required sync.

Existing runs keep their bound contracts. Strict projects retain the full
lifecycle below. Permissions, protected data, explicit approvals, research
provenance, material decisions and required postflight are not weakened. Detailed
evidence lanes and phase markers are not mandatory for ordinary runs. See
[Lean project workflow](docs/lean-workflow.md) and the installed `agent-guide`
for the applicable contract; older full-lifecycle descriptions are not universal
startup requirements.

Its product doctrine is:

```text
small kernel + pluggable modules + optional apps + project-level strictness + evidence-backed reporting
```

## 1. Small Kernel

The kernel owns the minimum lifecycle required for safe agent work:

- boot and health checks;
- task intake;
- route selection;
- write guarding;
- run envelopes;
- evaluation evidence;
- completion gates;
- receipt, handoff, and sync evidence.

The kernel should stay small. New product abilities should become modules unless they are required to prevent unsafe or unverifiable work.

## 2. Pluggable Modules

Modules extend the kernel only when a project enables them or a task invokes them.

Examples:

- spec alignment;
- capability orchestration;
- legacy migration;
- archive management;
- harness audit and repair;
- external adapters.

Modules must record command evidence when they affect a run. They must not silently replace kernel gates.

## 3. Optional Apps

Apps are observation and operation surfaces. They are not the kernel.

The Workbench may read KnowledgeOS state, explain the current run, and suggest commands. By default it must not bypass route guards, write guards, eval gates, or completion gates.

## 4. Project-Level Strictness

Different projects need different levels of governance.

KnowledgeOS should support stricter profiles for release, research, and long-running work without forcing every small project to load every module.

The default path should be safe and observable, not heavy.

## 5. Strict-Profile Evidence Lanes

Legacy/strict runs retain these evidence lanes when required by their contract:

| Lane | File | Marker | Meaning |
| --- | --- | --- | --- |
| Public Operational Trace | `.agent-os/runs/<RUN_ID>/step-events.ndjson` | `TRACE_OK` | User-visible operating trace. |
| Lifecycle Checkpoints | `.agent-os/runs/<RUN_ID>/phases.ndjson` | `CHECKPOINT_OK` | Six-phase lifecycle evidence. |
| Capability Visibility | `.agent-os/runs/<RUN_ID>/capability-events.ndjson` | `CAPABILITY_OK` | Visible MCP, skill, subagent, orchestrator, script, shell, or file-read use. |
| Completion And Sync | `.agent-os/runs/<RUN_ID>/postflight.md` | `SYNC_OK` | Completion and postflight sync evidence. |

No command evidence, no success claim.

## 6. Full Task Lifecycle

A legacy/strict task follows this operating chain; ordinary runs use the reduced
contract above:

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

The exact module set can vary by project profile, but completion must remain evidence-bound.

## 7. Doctor Versus Repair

`doctor` is diagnostic. It reports whether the control plane is healthy.

Repair tools are separate:

- `harness-audit --repair`;
- `init-os`;
- `init-project`;
- `migrate-legacy-project`;
- `archive-legacy-project`;
- `reset-project`.

This separation keeps health checks predictable and prevents hidden repair work.

## 8. Non-Goals

KnowledgeOS is not:

- a replacement for the host operating system;
- a generic chat UI;
- a hidden auto-mutation engine;
- a tool launcher that bypasses project rules;
- a single giant hook that loads every module for every project.

KnowledgeOS is the operating contract that lets agents work visibly, safely, and repeatably.
