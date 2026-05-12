# KnowledgeOS Workbench Preview

This is the local preview shell for the future KnowledgeOS Workbench.
It is intentionally read-only and has no terminal bridge, no paid API dependency, and no direct project mutation path.

## Run Locally

Live read-only preview:

```bash
./bin/knowledgeos workbench-preview --project-root . --port 4173
```

The live preview exposes:

- `GET /workbench-state.json`: redacted project state.
- `POST /api/ask-sandbox`: read-only mock Intent Console response.
- `GET /healthz`: preview health check.

Static fixture-only preview:

```bash
python3 -m http.server 4173 --directory examples/workbench
```

Then open `http://127.0.0.1:4173`.

## Design Contract

- Human Layer is visible by default: intent, current task, knowledge cards, next decision, capability health.
- System Black Box is collapsible: doctor summary, latest run, receipts, and raw state snapshot.
- The preview consumes `knowledgeos.workbench-state.v1` shape from `workbench-state.fixture.json`.
- The live preview serves the current project state from `/workbench-state.json`.
- The Intent Console calls `knowledgeos.ask-sandbox.v1` through the live preview bridge.
- Runtime adapter readiness is visible, but real CLI execution remains disabled by default.
- Paths remain redacted by default. Use `--show-paths` only for local debugging.
- The intent console must not mutate project files from this preview. Mutation remains OS-routed work.
