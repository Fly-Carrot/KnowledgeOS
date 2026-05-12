# Workbench Runtime Adapters

Phase 5 defined the boundary between the visual Workbench and local CLI runtimes.
Phase 6B adds the observable lifecycle layer so users can see how KnowledgeOS would route work before any real agent execution is allowed.

The Workbench may display runtime readiness, but it must not execute real agents by default. This keeps the Intent Console from accidentally becoming a second unmanaged operating system inside a KnowledgeOS project.

## Observable Lifecycle

`knowledgeos workbench-lifecycle --project-root <PROJECT_ROOT> --task-id <TASK_ID> --json` emits `knowledgeos.workbench-lifecycle.v1`.

The same read-only contract is available from the preview bridge:

```text
/workbench-lifecycle.json?task-id=<TASK_ID>
```

The lifecycle is deliberately small and inspectable:

| Stage | Meaning |
| --- | --- |
| `Doctor` | The project health gate has been checked. |
| `Route` | The task type has a known route profile. |
| `Dispatch` | The capability order is known. |
| `Write Guard` | Planned outputs are checked against route bounds. |
| `Run` | A run receipt exists or is still pending. |
| `Eval` | Verification evidence exists or is still pending. |
| `Receipt` | Completion and handoff evidence exists or is still pending. |

This layer gives the Workbench operational visibility without adding any mutation endpoint.

## Adapter States

`knowledgeos runtime-adapters --project-root <PROJECT_ROOT> --json` emits `knowledgeos.runtime-adapters.v1`.

The current adapters are:

| Adapter | Kind | Default Status | Purpose |
| --- | --- | --- | --- |
| `mock` | builtin | required | Safe read-only Intent Console behavior checks |
| `gemini-cli` | cli | optional | Future Gemini CLI adapter candidate |
| `codex-cli` | cli | optional | Future Codex CLI adapter candidate |

Optional adapters may be missing without blocking the Workbench. Their presence only means the executable is discoverable; it does not mean the Workbench is allowed to run it.

## Safety Contract

Runtime readiness is not runtime execution.

Every adapter reports:

- `execution: not_started`
- `execution_mode: disabled_by_default`
- `default_cwd: <SANDBOX>`
- `project_mutation: false`
- `requires_os_route_for_mutation: true`

The Workbench can use these fields to explain what is available locally while keeping the real project mutation path under KnowledgeOS route-bound execution.

## Why The Console Is Not The OS

The embedded console will eventually let users ask questions and interact with local CLI tools. However, the default console should remain a sandbox because a CLI session may itself load KnowledgeOS rules.

If the Workbench launches a CLI directly inside the project root, two control layers can compete:

1. The Workbench tries to supervise the runtime.
2. The CLI runtime loads project `AGENTS.md` and `.agent-os/` rules.

That overlap is useful for experts, but confusing and risky as a default. Phase 5 therefore makes readiness observable first, before real CLI execution is introduced.

## When Actual App Construction Can Begin

App construction began as a thin Electron shell after these conditions became true:

1. `workbench-state` exposes enough read-only OS state for the first UI screens.
2. `workbench-preview` serves live local state and a read-only Intent Console endpoint.
3. `runtime-adapters` exposes CLI readiness without running agents.
4. Tests verify that no preview endpoint mutates project files.
5. The first app shell can consume these same local HTTP/JSON contracts without inventing a second source of truth.

The shell remains thin: it wraps the existing preview endpoints instead of rewriting KnowledgeOS.

## Recommended Next Phase

The next phase should keep building from the same safety model:

- Keep `.agent-os/` and `knowledgeos` CLI as the source of truth.
- Reuse the current `workbench-state`, `runtime-adapters`, and `ask-sandbox` contracts.
- Reuse `workbench-lifecycle` for the visible run chain.
- Keep real `gemini` and `codex` execution disabled until a separate adapter execution phase.

This makes the first app feel real without surrendering the safety model.
