# KnowledgeOS Workbench App

KnowledgeOS Workbench is a local monitoring surface for observable KnowledgeOS projects.

## Download

Use the packaged macOS app from the GitHub Release:

- [KnowledgeOS-Workbench-0.1.1-arm64.dmg](https://github.com/Fly-Carrot/KnowledgeOS/releases/download/v0.1.1/KnowledgeOS-Workbench-0.1.1-arm64.dmg)
- [KnowledgeOS-Workbench-0.1.1-arm64.zip](https://github.com/Fly-Carrot/KnowledgeOS/releases/download/v0.1.1/KnowledgeOS-Workbench-0.1.1-arm64.zip)
- [SHA256SUMS.txt](https://github.com/Fly-Carrot/KnowledgeOS/releases/download/v0.1.1/SHA256SUMS.txt)

This first build is ad-hoc signed for Apple Silicon and not notarized. On macOS, open it from Finder with **Right click -> Open** the first time if Gatekeeper warns about an unidentified developer.

Generated desktop binaries are published as GitHub Release assets. The repository does not track generated desktop binaries under `apps/workbench/dist/`.

## Product Boundary

This version is monitoring and viewing only.

- No Command Dock.
- No Ask Sandbox.
- No raw terminal.
- No model prompt builder.
- No project mutation endpoint.

The UI exposes the operating chain as read-only state:

`Doctor -> Route -> Dispatch -> Write Guard -> Run -> Eval -> Receipt`

Project writes still happen outside the app through KnowledgeOS route, write guard, eval, and receipt commands.

## Packaged Kernel

Packaged Workbench builds include the KnowledgeOS runtime:

- `bin/knowledgeos`
- `knowledgeos/`
- `examples/workbench/`
- `global-agent-fabric/`
- `capability-layer/`
- `templates/`

The app starts the read-only `knowledgeos workbench-preview` bridge on `127.0.0.1` with an ephemeral local port. The bridge process is terminated when the desktop app exits.

## Workspace Switcher

The Workspace Switcher is local to the Electron app. It stores project roots under Electron's app data directory and inspects each selected root with KnowledgeOS doctor.

It does not write the registry into project `.agent-os/`. Broad container folders such as `Desktop`, `Downloads`, `Documents`, `Library`, and `HOME` are treated as unsafe initialization targets.

## Maintainer Commands

These commands are for maintainers who need to rebuild the app locally. Normal users should download the Release asset instead.

```bash
pnpm --dir apps/workbench dev
pnpm --dir apps/workbench package
pnpm --dir apps/workbench dist:mac
pnpm --dir apps/workbench smoke
pnpm --dir apps/workbench diagnose
```

- `dev` opens the desktop app and starts a local read-only bridge.
- `package` creates a packaged app directory with bundled KnowledgeOS resources.
- `dist:mac` creates a local ad-hoc signed macOS `arm64` `.app`, `.dmg`, and `.zip`.
- `smoke` runs fast structural checks and verifies the monitoring-only boundary.
- `diagnose` starts the bridge, reads state and lifecycle JSON, then prints a concise health summary.

## Environment Overrides

- `KNOWLEDGEOS_PROJECT_ROOT`: project root shown by the Workbench. Defaults to the KnowledgeOS repo root in development.
- `KNOWLEDGEOS_BIN`: KnowledgeOS CLI path. Development defaults to the repo `bin/knowledgeos`; packaged builds default to the bundled `resources/knowledgeos/bin/knowledgeos`.

## Debugging

If the app opens but looks stale, maintainers can run:

```bash
pnpm --dir apps/workbench diagnose
```

Common failure modes:

- `KnowledgeOS binary missing`: set `KNOWLEDGEOS_BIN` to the local `bin/knowledgeos`.
- `Bridge exited before URL`: run `./bin/knowledgeos doctor --project-root <root> --summary` and fix the reported OS state first.
- `lifecycle schema mismatch`: the app and CLI are out of sync; rerun tests before launching the app.
- macOS says the app is from an unidentified developer: this is expected for the ad-hoc v0.1.1 build; use **Right click -> Open**.
