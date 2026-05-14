# KnowledgeOS Workbench

This folder contains the shared Workbench UI used by the Electron app and by the lightweight HTTP bridge.

The browser preview is read-only. The current product surface is intentionally monitoring-only: Launchpad opens focused inspection windows, Now Shelf shows compact state, and Mission Control summarizes the current OS gate.

## Run Locally

Live read-only bridge:

```bash
./bin/knowledgeos workbench-preview --project-root . --port 4173
```

The bridge exposes:

- `GET /workbench-state.json`: redacted project state.
- `GET /workbench-lifecycle.json`: the observable Doctor -> Route -> Dispatch -> Write Guard -> Run -> Eval -> Receipt chain.
- `GET /healthz`: bridge health check.

Static fixture mode:

```bash
python3 -m http.server 4173 --directory examples/workbench
```

Then open `http://127.0.0.1:4173`.

## Product Contract

- Launchpad is the home screen: six app icons open focused windows on demand.
- Now Shelf is the compact status strip: project, mission, receipt, and health.
- Mission Control shows the current gate, next move, compact evidence chain, and collapsed audit trail.
- Context shows project state surfaces without repeating run evidence.
- Evidence shows marker files and proof lanes without repeating the run timeline.
- Runs shows lifecycle checkpoints and run artifacts without repeating global capability summaries.
- Knowledge shows human-readable docs, decisions, handoffs, and skills.
- Settings shows product boundary and runtime inventory.
- Workspace switching is an Electron-only local registry. The registry is not written into project `.agent-os`.
- Paths remain redacted by default. Use `--show-paths` only for local debugging.
- Project mutation remains OS-routed work outside this UI.
