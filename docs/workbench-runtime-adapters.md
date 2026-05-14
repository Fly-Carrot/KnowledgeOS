# Workbench Runtime Adapters

Workbench is currently a monitoring and viewing app.

Runtime adapters may appear as local readiness signals, but this version does not expose a model prompt, raw terminal, or adapter launch button. KnowledgeOS remains the execution boundary: real project work still goes through route, write guard, run evidence, eval, and receipt.

## Current Contract

- The app can display whether local runtime adapters are present.
- The app can show the KnowledgeOS lifecycle and evidence lanes.
- The app must not start Gemini, Codex, or any other model CLI.
- The app must not open a terminal.
- The app must not create a project mutation endpoint.
- The app must not silently choose a model or context scope.

## Visible State Only

Adapter data is treated as inventory:

| Field | Meaning |
| --- | --- |
| `id` | Stable adapter identifier. |
| `label` | Human-readable adapter name. |
| `status` | Local readiness signal, such as `available` or `missing`. |
| `execution_mode` | Boundary note; execution remains disabled in the Workbench UI. |

## Deferred Ideas

Earlier design notes explored a disposable model console and a raw terminal. Those ideas are intentionally deferred. If they return, they should be implemented as a separate, explicit product phase with its own threat model, tests, and route-bound lifecycle.

Until then, Workbench should feel like mission control, not a second unmanaged shell.
