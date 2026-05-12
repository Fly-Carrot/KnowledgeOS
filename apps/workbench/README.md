# KnowledgeOS Workbench App

This is the minimal Electron desktop shell for KnowledgeOS Workbench.

It does not run Gemini, Codex, or any real agent adapter. The shell launches the existing read-only `knowledgeos workbench-preview` bridge on `127.0.0.1` with an ephemeral port and then loads that local URL.

## Commands

```bash
pnpm --dir apps/workbench dev
pnpm --dir apps/workbench smoke
pnpm --dir apps/workbench diagnose
```

- `dev` opens the desktop shell and starts a local read-only bridge.
- `smoke` runs fast structural checks and probes the bridge contracts without a GUI.
- `diagnose` starts the bridge, reads state, lifecycle, and sandbox endpoints, then prints a concise health summary.

The UI intentionally exposes the operating chain as a read-only lifecycle:

`Doctor -> Route -> Dispatch -> Write Guard -> Run -> Eval -> Receipt`

`Preview OS Route` is not a mutation button. It exists to make the next command chain visible before any future execution feature is introduced.

## Environment Overrides

- `KNOWLEDGEOS_PROJECT_ROOT`: project root shown by the Workbench. Defaults to the KnowledgeOS repo root.
- `KNOWLEDGEOS_BIN`: KnowledgeOS CLI path. Defaults to `../../bin/knowledgeos` from this app.

The bridge process is terminated when the desktop shell exits.

## Debugging

If the app opens but looks stale, run:

```bash
pnpm --dir apps/workbench diagnose
```

Common failure modes:

- `KnowledgeOS binary missing`: set `KNOWLEDGEOS_BIN` to the local `bin/knowledgeos`.
- `Bridge exited before URL`: run `./bin/knowledgeos doctor --project-root <root> --summary` and fix the reported OS state first.
- `lifecycle schema mismatch`: the app and CLI are out of sync; rerun tests before launching the shell.
- `sandbox must not execute commands`: this is a safety regression. The Workbench must stay read-only until a separate adapter execution phase.
