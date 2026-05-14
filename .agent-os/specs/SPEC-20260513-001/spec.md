# KnowledgeOS Core Product Philosophy

Spec ID: SPEC-20260513-001
Status: active
Created At: 2026-05-13T05:59:52.646718+00:00

## Intent

KnowledgeOS must stay a small-kernel agent operating system: modules inject only when enabled or invoked, apps observe rather than govern, projects choose strictness, and every meaningful run reports public operational trace plus command-evidenced checkpoints and capability calls.

## Raw Shell Product Direction

The Workbench Raw Shell must be productized as a disposable sandbox surface, not as a hidden chat box and not as a second unmanaged project terminal.

### Interaction Modes

- `Simple Model Ask` is the default mode. It lets users ask a selected local model CLI through a visible adapter, bounded knowledge scope, and disposable sandbox.
- `Advanced Raw Terminal` is the expert mode. It exposes a real terminal only after the user opts into it and sees the adapter, sandbox cwd, context mode, and mutation boundary.

Simple mode must not silently choose a model. The UI must show the selected adapter, command readiness, sandbox path, and context scope before any model CLI is started.

### Model Adapter Detection

Workbench detects local CLI availability in the Electron main process and exposes only read-only readiness to the renderer.

Adapter readiness is staged:

1. `missing`: no executable found.
2. `installed`: executable path found.
3. `runnable`: lightweight version command succeeds.
4. `sandbox_ready`: the adapter can start with sandbox `HOME`, `TMPDIR`, and cwd.
5. `auth_managed_by_cli`: Workbench does not manage provider keys or login state.

Workbench may inspect executable paths and version commands. It must not automatically read provider tokens, API keys, or private CLI configuration directories.

### Knowledge Scope

Model sessions must read fixed context snapshots, not arbitrary project or machine directories.

Allowed scopes:

- `OS Knowledge Pack`: KnowledgeOS-generated context for the current project, task, handoff, decisions, and selected docs.
- `Current Run Evidence`: current run context pack, lifecycle, eval, and receipts.
- `Selected Files`: user-selected files converted into a temporary source pack.
- `Selected Folder`: user-selected folder inventory plus explicitly converted files.

The model reads sandbox files such as `workbench-state.json`, `workbench-lifecycle.json`, `context-pack.md`, `source-pack.md`, `agent-guide.md`, and `user-question.md`.

Promoting temporary files or model output back into durable project knowledge is a later OS-routed action. It must create or select a KnowledgeOS task and pass route guard, write guard, eval, and complete-task before mutating project files.

### Phased Plan

1. `8A`: Rename and reframe Raw Shell as `Sandbox Console` with `Guided` and `Terminal` modes.
2. `8B`: Harden CLI detection and settings for Gemini, Codex, and custom commands.
3. `8C`: Implement `Simple Model Ask` inside the disposable sandbox.
4. `8D`: Add context scope picker and temporary source packs.
5. `8E`: Add optional `Promote to OS Knowledge` handoff through KnowledgeOS route-bound execution.
6. `8F`: Review security boundaries, session cleanup, provider-log caveats, and absence of mutation endpoints.

Non-goals: hidden model selection, direct project-root terminal by default, automatic API-key management, provider log deletion claims, or project mutation from either Simple Model Ask or Advanced Raw Terminal.
