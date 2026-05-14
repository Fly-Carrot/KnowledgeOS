# Workbench macOS Packaging

KnowledgeOS Workbench can be packaged as a local macOS desktop app. The packaged app bundles the KnowledgeOS kernel and opens the same read-only Workbench bridge that development mode uses.

## Build Commands

```bash
pnpm --dir apps/workbench install
pnpm --dir apps/workbench smoke
pnpm --dir apps/workbench diagnose
pnpm --dir apps/workbench dist:mac
```

`dist:mac` creates Apple Silicon (`arm64`) artifacts in `apps/workbench/dist/`:

- `mac-arm64/KnowledgeOS Workbench.app`
- `KnowledgeOS Workbench-<version>-arm64.dmg`
- `KnowledgeOS Workbench-<version>-arm64.zip`

The `dist/` folder is ignored by `apps/workbench/.gitignore`. Keep generated desktop binaries out of normal source commits.

## Bundled Runtime

Packaged builds include the minimum runtime surface needed by the Workbench:

- `bin/knowledgeos`
- `knowledgeos/`
- `examples/workbench/`
- `global-agent-fabric/`
- `capability-layer/`
- `templates/`

Development mode resolves the kernel from the repository. Packaged mode resolves it from Electron `resources/knowledgeos/`.

`KNOWLEDGEOS_BIN` and `KNOWLEDGEOS_PROJECT_ROOT` remain available for local debugging, but normal packaged builds should use the bundled binary by default.

## Security Boundary

Workbench is a monitoring app. It does not replace the KnowledgeOS kernel.

- The bridge binds only to `127.0.0.1`.
- The bridge is started with an ephemeral local port.
- The desktop shell keeps `contextIsolation: true`, `nodeIntegration: false`, and `sandbox: true`.
- The UI does not expose Raw Shell, model execution, prompt launch, or project mutation endpoints.
- Project writes still require the KnowledgeOS route, write guard, eval, verify, complete, and sync lifecycle outside the Workbench UI.

## Ad-Hoc Local Builds

The current package is ad-hoc signed for local Apple Silicon testing and not notarized. For local testing, open the app from Finder with **Right click -> Open** the first time.

If macOS quarantine blocks a build that you created locally and trust, remove quarantine from the generated `.app`:

```bash
xattr -dr com.apple.quarantine "apps/workbench/dist/mac-arm64/KnowledgeOS Workbench.app"
```

Developer ID signing, notarization, auto-update, and GitHub Release asset upload are release engineering tasks for a later phase.

## GitHub Publishing

Commit source, tests, packaging config, and documentation to the `KnowledgeOS` repository. Do not commit generated binaries.

For a public release:

1. Run the test ladder.
2. Build with `pnpm --dir apps/workbench dist:mac`.
3. Create a GitHub Release.
4. Upload the generated `.dmg` and `.zip` as release assets.
5. Document that the build is ad-hoc signed unless a notarized build is produced.
