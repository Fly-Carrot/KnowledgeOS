# Workbench Release Packaging

KnowledgeOS Workbench is distributed as a macOS Release asset, not as a binary committed to the source tree.

## Public Release Assets

The v0.1.1 Release publishes:

- `KnowledgeOS-Workbench-0.1.1-arm64.dmg`
- `KnowledgeOS-Workbench-0.1.1-arm64.zip`
- `SHA256SUMS.txt`

Normal users should download the `.dmg` from the GitHub Release. Maintainers can use the `.zip` for quick app extraction or checksum verification.

## Maintainer Build Commands

Local packaging remains a maintainer operation:

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

The `dist/` folder is ignored by `apps/workbench/.gitignore`. Do not commit generated binaries.

## Bundled Runtime

Packaged builds include the minimum runtime surface needed by the Workbench:

- `bin/knowledgeos`
- `knowledgeos/`
- `examples/workbench/`
- `global-agent-fabric/`
- `capability-layer/`
- `templates/`

Development mode resolves the kernel from the repository. Packaged mode resolves it from Electron `resources/knowledgeos/`.

`KNOWLEDGEOS_BIN` and `KNOWLEDGEOS_PROJECT_ROOT` remain available for local debugging, but normal packaged builds use the bundled binary by default.

## Security Boundary

Workbench is a monitoring app. It does not replace the KnowledgeOS kernel.

- The bridge binds only to `127.0.0.1`.
- The bridge is started with an ephemeral local port.
- The desktop shell keeps `contextIsolation: true`, `nodeIntegration: false`, and `sandbox: true`.
- The UI does not expose Raw Shell, model execution, prompt launch, or project mutation endpoints.
- Project writes still require the KnowledgeOS route, write guard, eval, verify, complete, and sync lifecycle outside the Workbench UI.

## Ad-Hoc Signed v0.1.1

The current public build is ad-hoc signed for local Apple Silicon use and not notarized with an Apple Developer ID. On macOS, open the app from Finder with **Right click -> Open** the first time.

If macOS quarantine blocks a build that you created locally and trust, remove quarantine from the generated `.app`:

```bash
xattr -dr com.apple.quarantine "apps/workbench/dist/mac-arm64/KnowledgeOS Workbench.app"
```

Developer ID signing, notarization, and auto-update are future release engineering tasks.

## Release Boundary

The repository tracks Workbench source, packaging configuration, tests, and documentation. Release binaries belong in GitHub Releases.

For a public release:

1. Run the test ladder.
2. Build with `pnpm --dir apps/workbench dist:mac`.
3. Copy artifacts to release-safe names without spaces.
4. Generate `SHA256SUMS.txt`.
5. Create or update the GitHub Release.
6. Upload the `.dmg`, `.zip`, and checksum file as Release assets.
