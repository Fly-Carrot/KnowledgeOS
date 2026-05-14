# KnowledgeOS Workbench App

KnowledgeOS Workbench is a local monitoring surface for observable KnowledgeOS projects.

This app bundles the KnowledgeOS kernel for packaged desktop builds, but it still does not replace KnowledgeOS routing rules. It starts the read-only `knowledgeos workbench-preview` bridge on `127.0.0.1` with an ephemeral port, then adds a minimal frameless Electron shell for local workspace switching and focused inspection.

## Commands

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

## Build A macOS App

```bash
pnpm --dir apps/workbench install
pnpm --dir apps/workbench smoke
pnpm --dir apps/workbench diagnose
pnpm --dir apps/workbench dist:mac
```

The packaged output is written to `apps/workbench/dist/`. The source tree ignores that folder so local `.app`, `.dmg`, and `.zip` artifacts do not get committed accidentally.

The current build is ad-hoc signed for local Apple Silicon testing but not notarized with an Apple Developer ID. On macOS, open it from Finder with **Right click -> Open** the first time, or remove quarantine locally if you trust the build you just produced:

```bash
xattr -dr com.apple.quarantine "apps/workbench/dist/mac-arm64/KnowledgeOS Workbench.app"
```

Developer ID signing and notarization are intentionally left for a later release step.

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

## Workspace Switcher

The Workspace Switcher is local to the Electron app. It stores project roots under Electron's app data directory and inspects each selected root with KnowledgeOS doctor.

It does not write the registry into project `.agent-os/`. Broad container folders such as `Desktop`, `Downloads`, `Documents`, `Library`, and `HOME` are treated as unsafe initialization targets.

## Environment Overrides

- `KNOWLEDGEOS_PROJECT_ROOT`: project root shown by the Workbench. Defaults to the KnowledgeOS repo root.
- `KNOWLEDGEOS_BIN`: KnowledgeOS CLI path. Development defaults to the repo `bin/knowledgeos`; packaged builds default to the bundled `resources/knowledgeos/bin/knowledgeos`.

## Packaged Kernel

Packaged Workbench builds include:

- `bin/knowledgeos`
- `knowledgeos/`
- `examples/workbench/`
- `global-agent-fabric/`
- `capability-layer/`
- `templates/`

This makes the desktop app self-contained for the KnowledgeOS runtime. Project workspaces are still selected explicitly through the Workspace Switcher, and writes still require the OS route, write guard, eval, and receipt flow.

The bridge process is terminated when the desktop app exits.

## GitHub Release Boundary

The repository tracks Workbench source, packaging configuration, tests, and documentation. It does not track generated desktop binaries under `apps/workbench/dist/`.

For public releases, attach the generated `.dmg` or `.zip` as GitHub Release assets instead of committing them into the repository.

## Debugging

If the app opens but looks stale, run:

```bash
pnpm --dir apps/workbench diagnose
```

Common failure modes:

- `KnowledgeOS binary missing`: set `KNOWLEDGEOS_BIN` to the local `bin/knowledgeos`.
- `Bridge exited before URL`: run `./bin/knowledgeos doctor --project-root <root> --summary` and fix the reported OS state first.
- `lifecycle schema mismatch`: the app and CLI are out of sync; rerun tests before launching the app.
- macOS says the app is from an unidentified developer: this is expected for the ad-hoc local build; use **Right click -> Open** for local testing.
