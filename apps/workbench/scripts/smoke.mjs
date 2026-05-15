import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const scriptDir = path.dirname(__filename);
const appRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(appRoot, "..", "..");
const projectRoot = path.resolve(process.env.KNOWLEDGEOS_PROJECT_ROOT || repoRoot);
const knowledgeosBin = path.resolve(process.env.KNOWLEDGEOS_BIN || path.join(repoRoot, "bin", "knowledgeos"));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function cssBlock(source, selector) {
  const start = source.indexOf(selector);
  assert(start >= 0, `CSS selector not found: ${selector}`);
  const open = source.indexOf("{", start);
  const close = source.indexOf("}", open);
  assert(open >= 0 && close > open, `CSS block not found: ${selector}`);
  return source.slice(open + 1, close);
}

function read(relativePath) {
  return fs.readFileSync(path.join(appRoot, relativePath), "utf8");
}

async function waitForPreviewUrl(child) {
  let transcript = "";
  return await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timed out waiting for preview URL. Output:\n${transcript}`)), 8000);
    const onData = (chunk) => {
      transcript += chunk.toString();
      const match = transcript.match(/KnowledgeOS Workbench preview:\s*(http:\/\/127\.0\.0\.1:\d+)/);
      if (match) {
        clearTimeout(timer);
        resolve({ url: match[1], transcript });
      }
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", onData);
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("exit", (code, signal) => {
      clearTimeout(timer);
      reject(new Error(`Bridge exited before URL. code=${code} signal=${signal}\n${transcript}`));
    });
  });
}

function assertNoConsoleSurface(source, label) {
  const banned = [
    "Command Dock",
    "Ask Sandbox",
    "Sandbox Console",
    "Raw Shell",
    "Prompt Preview",
    "Adapter Run Gate",
    "setupSandboxConsole",
    "setCommandPanelOpen",
    "renderPromptPreview",
    "loadShellAdapters",
    "runtimeAdaptersFromState",
    "mergeAdapterInventories",
    "renderGuidedAdapterStatus",
    "resolveGuidedKnowledgeScope",
    "renderKnowledgeSnapshot",
    "renderSnapshotViewer",
    "buildGuidedPrompt",
    "copyGuidedPrompt",
    "reviewAdapterRunGate",
    "adapterCommandPreview",
    "sandboxPreviewPath",
    "workbench:sandbox-create",
    "workbench:sandbox-destroy",
    "workbench:knowledge-scope-resolve",
    "knowledgeos.guided-context-snapshot.v1",
    "modelCliLaunchEnabled",
    "command -v",
    "sandbox-exec",
    "KNOWLEDGEOS_PROJECT_MUTATION"
  ];
  for (const item of banned) {
    assert(!source.includes(item), `${label} still contains console surface: ${item}`);
  }
}

async function main() {
  const pkg = JSON.parse(read("package.json"));
  assert(pkg.description === "KnowledgeOS desktop Workbench for observable local agent workspaces.", "package description should use product language");
  assert(pkg.scripts.dev === "electron .", "dev script must launch Electron");
  assert(pkg.scripts.package === "electron-builder --dir", "package script should build a bundled desktop app directory");
  assert(pkg.scripts["dist:mac"] === "electron-builder --mac dmg zip --arm64 --publish=never", "dist:mac script should build local ad-hoc macOS artifacts without publishing");
  assert(pkg.scripts.smoke === "node scripts/smoke.mjs", "smoke script must stay deterministic");
  assert(pkg.scripts.diagnose === "node scripts/diagnose.mjs", "diagnose script is missing");
  assert(pkg.build?.productName === "KnowledgeOS Workbench", "Electron package product name is missing");
  assert(pkg.build?.artifactName === "${productName}-${version}-${arch}.${ext}", "Distribution artifact names should include product version and arch");
  assert(pkg.build?.directories?.output === "dist", "Electron distribution output should stay under apps/workbench/dist");
  assert(pkg.build?.mac?.category === "public.app-category.developer-tools", "macOS app category should identify developer tooling");
  assert(pkg.build?.mac?.identity === "-", "Local macOS build should use ad-hoc signing by default");
  assert(pkg.build?.mac?.hardenedRuntime === false, "Ad-hoc local macOS build should not imply Developer ID hardened runtime signing");
  assert(JSON.stringify(pkg.build?.mac?.target || []).includes('"dmg"'), "macOS dmg target is missing");
  assert(JSON.stringify(pkg.build?.mac?.target || []).includes('"zip"'), "macOS zip target is missing");
  assert(JSON.stringify(pkg.build?.mac?.target || []).includes('"arm64"'), "macOS arm64 target is missing");
  assert(pkg.build?.dmg?.title === "KnowledgeOS Workbench ${version}", "DMG title is missing");
  assert(pkg.build?.files?.includes("index.html"), "Packaged app must include the local startup fallback page");
  assert(Array.isArray(pkg.build?.extraResources), "Bundled KnowledgeOS resources are not configured");
  for (const target of ["knowledgeos/bin", "knowledgeos/knowledgeos", "knowledgeos/examples/workbench", "knowledgeos/global-agent-fabric", "knowledgeos/capability-layer", "knowledgeos/templates"]) {
    assert(pkg.build.extraResources.some((entry) => entry.to === target), `Bundled resource missing: ${target}`);
  }
  const globalFabricResource = pkg.build.extraResources.find((entry) => entry.to === "knowledgeos/global-agent-fabric");
  assert(globalFabricResource?.filter?.includes("!global-agent-fabric_venv/**"), "Bundled global fabric must exclude local virtualenv symlinks");
  for (const target of ["knowledgeos/knowledgeos", "knowledgeos/examples/workbench", "knowledgeos/capability-layer", "knowledgeos/templates"]) {
    const resource = pkg.build.extraResources.find((entry) => entry.to === target);
    assert(resource?.filter?.includes("!**/__pycache__/**"), `Bundled resource must exclude Python cache files: ${target}`);
  }
  assert(pkg.devDependencies["electron-builder"], "electron-builder dependency is missing");
  assert(pkg.devDependencies.electron, "Electron dependency is missing");
  assert(pkg.devDependencies.vite, "Vite dependency is missing");
  const appGitignore = fs.readFileSync(path.join(appRoot, ".gitignore"), "utf8");
  assert(appGitignore.includes("dist/"), "Workbench dist output should be ignored locally");
  assert(appGitignore.includes("node_modules/"), "Workbench node_modules should be ignored locally");

  const mainSource = read("electron/main.mjs");
  const preloadSource = read("electron/preload.cjs");
  const viteSource = read("vite.config.mjs");
  const previewIndex = fs.readFileSync(path.join(repoRoot, "examples", "workbench", "index.html"), "utf8");
  const styles = fs.readFileSync(path.join(repoRoot, "examples", "workbench", "styles.css"), "utf8");
  const previewJs = fs.readFileSync(path.join(repoRoot, "examples", "workbench", "app.js"), "utf8");
  const rootReadme = fs.readFileSync(path.join(repoRoot, "README.md"), "utf8");
  const appReadme = fs.readFileSync(path.join(appRoot, "README.md"), "utf8");
  const packagingDoc = fs.readFileSync(path.join(repoRoot, "docs", "workbench-packaging.md"), "utf8");

  assert(mainSource.includes("workbench-preview"), "Electron shell must launch workbench-preview");
  assert(mainSource.includes('"--port"') && mainSource.includes('"0"'), "Bridge must use port 0");
  assert(mainSource.includes("PYTHONUNBUFFERED"), "Bridge stdout must be unbuffered for URL parsing");
  assert(mainSource.includes("process.resourcesPath") && mainSource.includes("bundledKernelRoot"), "Packaged app must resolve the bundled KnowledgeOS kernel");
  assert(mainSource.includes("defaultProjectRoot") && mainSource.includes("app.isPackaged ? os.homedir() : repoRoot"), "Packaged app must not default the observed workspace to the app bundle Contents directory");
  assert(mainSource.includes("explicitProjectRoot") && mainSource.includes("if (explicitProjectRoot) return"), "KNOWLEDGEOS_PROJECT_ROOT must take precedence over local workspace registry state");
  assert(mainSource.includes("applySelectedWorkspaceFromRegistry"), "Packaged app must apply the selected workspace registry before launching the bridge");
  assert(mainSource.includes("KNOWLEDGEOS_PROJECT_ROOT"), "Project root override is missing");
  assert(mainSource.includes("KNOWLEDGEOS_BIN"), "KnowledgeOS binary override is missing");
  assert(mainSource.includes("cleanupBridge"), "Bridge cleanup hook is missing");
  assert(mainSource.includes("preload.cjs"), "Electron shell must expose a constrained preload bridge");
  assert(mainSource.includes("workspaces.json"), "Local workspace registry is missing");
  assert(mainSource.includes("isDangerousWorkspaceRoot"), "Dangerous workspace root guard is missing");
  assert(mainSource.includes("contextIsolation: true"), "Renderer context isolation is required");
  assert(mainSource.includes("sandbox: true"), "Renderer sandbox is required");
  assert(!mainSource.includes("nodeIntegration: true"), "Renderer must not enable nodeIntegration");
  assert(mainSource.includes("width: 1280"), "Electron default width should stay restrained");
  assert(mainSource.includes("height: 820"), "Electron default height should stay restrained");
  assert(mainSource.includes("minWidth: 1180"), "Electron minimum width should prevent cramped Launchpad layouts");
  assert(mainSource.includes("minHeight: 760"), "Electron minimum height should prevent compact edge artifacts");
  assert(mainSource.includes('titleBarStyle: "hiddenInset"'), "Electron shell should use a hidden inset titlebar");
  assert(mainSource.includes("trafficLightPosition"), "Electron shell should preserve native macOS traffic lights");
  assert(viteSource.includes("workbenchStaticRoot") && viteSource.includes("examples") && viteSource.includes("workbench"), "Vite preview should serve the shared Workbench UI");

  assert(preloadSource.includes("contextBridge.exposeInMainWorld"), "Preload must expose an explicit API");
  assert(preloadSource.includes("getWorkspaces"), "Preload workspace registry reader is missing");
  assert(preloadSource.includes("addWorkspace"), "Preload workspace add action is missing");
  assert(preloadSource.includes("runDoctor"), "Preload workspace doctor action is missing");
  assert(!preloadSource.includes("require('fs')") && !preloadSource.includes('require("fs")'), "Preload must not expose filesystem primitives");

  assertNoConsoleSurface(mainSource, "electron main");
  assertNoConsoleSurface(preloadSource, "electron preload");
  assertNoConsoleSurface(previewIndex, "preview HTML");
  assertNoConsoleSurface(previewJs, "preview JS");
  assertNoConsoleSurface(styles, "preview CSS");

  assert(previewIndex.includes("<title>KnowledgeOS Workbench</title>"), "Workbench title should use product language");
  assert(!previewIndex.includes("KnowledgeOS Workbench Preview"), "Workbench UI should not present itself as a preview");
  assert(previewIndex.includes('class="launchpad"'), "Launchpad app grid is missing");
  assert(previewIndex.includes("Mission Control"), "Mission Control entry label is missing");
  assert(!previewIndex.includes("Open timeline"), "Mission Control entry pill should not survive");
  assert(previewIndex.includes('aria-label="Open Agent Mission Control"'), "Mission Control entry aria label is missing");
  assert(previewIndex.includes('class="now-shelf"'), "Now Shelf is missing");
  assert(previewIndex.includes('id="workspace-toggle"'), "Workspace switcher button is missing");
  assert(previewIndex.includes('id="workspace-panel"'), "Workspace switcher panel is missing");
  assert(previewIndex.includes("Registry is local to this App"), "Workspace registry boundary copy is missing");
  assert(previewIndex.includes('id="about-open"'), "About control is missing");
  assert(previewIndex.includes('id="onboarding-open"'), "Onboarding reopen control is missing");
  assert(previewIndex.includes('id="app-window" hidden'), "On-demand app window must exist and start hidden");
  assert(previewIndex.includes('id="window-close"'), "App window close control is missing");
  assert(previewIndex.includes('id="window-body"'), "App window body is missing");
  assert(previewIndex.includes('id="onboarding-screen"'), "First-run onboarding screen is missing");
  assert(previewIndex.includes("Getting Started"), "Onboarding title is missing");
  assert(previewIndex.includes("Open Mission Control"), "Onboarding primary action is missing");
  assert(previewIndex.includes("Choose an app") && previewIndex.includes("Glance at state"), "Onboarding steps are incomplete");
  assert(previewIndex.includes("Click any icon to open a focused app window."), "Onboarding should teach single-click opening");
  assert(previewIndex.includes('data-theme="dark"'), "Default theme should be dark, not system");
  assert(!previewIndex.includes('data-theme="system"'), "System theme option should not appear in the app UI");
  assert(previewIndex.includes(">Dark</button>"), "Theme button should start as Dark");
  assert(!previewIndex.includes(">Theme</button>"), "Theme button should not use a generic Theme label");
  assert(!previewIndex.includes('class="brand-mark"'), "Brand mark should not appear in the simplified top-left brand");
  assert(!previewIndex.includes('id="workspace-name"'), "Workspace subtitle should not appear in the simplified top-left brand");
  assert(!previewIndex.includes("Open only what matters."), "Marketing slogan should not appear in the app UI");
  assert(!previewIndex.includes("KnowledgeOS turns project state"), "Marketing paragraph should not appear in the app UI");
  assert(!previewIndex.includes('class="hero-card"'), "Hero card should not exist on Launchpad home");
  assert(!previewIndex.includes('class="app-sheet"'), "Default expanded app sheet should not exist on Launchpad home");

  assert(styles.includes("#6f8790") && styles.includes("#819aa2"), "Muted graphite/blue-gray accents are missing");
  assert(styles.includes("width: min(1180px, calc(100vw - 56px))"), "Desktop max-width guard is missing");
  assert(styles.includes("margin: 0 auto"), "Desktop centering rule is missing");
  assert(styles.includes("grid-template-columns: repeat(3, minmax(180px, 1fr))"), "Launchpad should use a 3-column / 2-row layout");
  assert(styles.includes("width: clamp(82px, 13vh, 104px)") && styles.includes("height: clamp(82px, 13vh, 104px)"), "Launchpad icons should be viewport-scaled");
  assert(styles.includes("grid-auto-rows: minmax(96px, 1fr)"), "Now Shelf should use stable rows");
  assert(styles.includes("max-height: clamp(152px, 18vh, 174px)"), "Now Shelf should keep a stable outer height");
  assert(styles.includes("-webkit-line-clamp: 2"), "Now Shelf descriptions should clamp instead of resizing the panel");
  for (const selector of [
    "\n.app-icon {",
    ".app-icon:hover, .app-icon.is-active",
    "\n.app-glyph {",
    ".app-icon:hover .app-glyph,",
    "\n.shelf-card {",
    "\n.shelf-card:hover {"
  ]) {
    assert(!cssBlock(styles, selector).includes("transform"), `${selector} must not move or scale layout-critical elements`);
  }
  assert(!styles.includes(".app-icon:active"), "Launchpad app active state must not move or scale icons");
  assert(!styles.includes(".entry-pill"), "Unused entry pill styles should not survive");
  assert(!styles.includes("grid-template-columns: repeat(6"), "Single-row six-icon Launchpad layout should not survive");
  assert(styles.includes(".workspace-panel") && styles.includes(".workspace-button"), "Workspace switcher styles are missing");
  assert(styles.includes(".workspace-list") && styles.includes(".workspace-row"), "Workspace list styles are missing");
  assert(styles.includes(".app-window") && styles.includes(".window-card"), "On-demand app window styles are missing");
  assert(styles.includes(".onboarding-screen") && styles.includes(".onboarding-card"), "Onboarding screen styles are missing");
  assert(styles.includes("#onboarding-open") && styles.includes("font-weight: 900"), "Help icon should be bold");
  assert(!styles.includes("prefers-color-scheme: dark"), "System theme media query should not survive");
  assert(!styles.includes("grid-template-columns: 220px minmax(0, 1fr) 300px"), "Old three-column dashboard shell still controls layout");

  assert(previewJs.includes("productInfo") && previewJs.includes('"0.1.1"'), "About/version product metadata is missing");
  assert(previewJs.includes("Monitoring and viewing only"), "Monitoring-only boundary is missing");
  assert(previewJs.includes("workbenchApi"), "Electron API bridge detection is missing");
  assert(previewJs.includes("setupWorkspaceSwitcher"), "Workspace switcher setup is missing");
  assert(previewJs.includes("missionAppContent"), "Mission app content renderer is missing");
  assert(previewJs.includes("contextAppContent"), "Context app content renderer is missing");
  assert(previewJs.includes("evidenceAppContent"), "Evidence app content renderer is missing");
  assert(previewJs.includes("runsAppContent"), "Runs app content renderer is missing");
  assert(previewJs.includes("knowledgeAppContent"), "Knowledge app content renderer is missing");
  assert(previewJs.includes("settingsAppContent"), "Settings app content renderer is missing");
  assert(previewJs.includes("Mission Control shows the next gate"), "Mission intro should be monitoring-oriented");
  assert(previewJs.includes("Agent Mission Control"), "Mission app should expose Mission Control framing");
  assert(previewJs.includes("Evidence Chain"), "Mission app should expose one compact evidence chain");
  assert(previewJs.includes("Audit Trail"), "Mission app should hide detailed evidence behind Audit Trail");
  assert(previewJs.includes("Public Operational Trace") && previewJs.includes("Completion And Sync"), "Mission app should expose evidence lanes");
  assert(previewJs.includes("TRACE_OK") && previewJs.includes("CHECKPOINT_OK") && previewJs.includes("CAPABILITY_OK") && previewJs.includes("SYNC_OK"), "Mission Control markers are missing");
  assert(previewJs.includes("Project State Map") && previewJs.includes("State Surfaces"), "Context app should expose project state map sections");
  assert(previewJs.includes("Evidence Lanes") && previewJs.includes("Proof Status"), "Evidence app should expose proof lanes");
  assert(previewJs.includes("Run Timeline") && previewJs.includes("Checkpoint Chain"), "Runs app should expose run timeline and checkpoint chain");
  assert(previewJs.includes("Knowledge Index") && previewJs.includes("Knowledge Entrypoints"), "Knowledge app should expose readable knowledge entrypoints");
  assert(previewJs.includes("Safety Boundary") && previewJs.includes("Runtime Adapters"), "Settings app should expose safety and runtime adapters");
  assert(previewJs.includes('kernel: "bundled"') && previewJs.includes('bridge: "local 127.0.0.1"'), "Settings should disclose bundled kernel and local bridge state");
  assert(styles.includes("height: 100dvh") && styles.includes("overflow: hidden"), "Launchpad home should be viewport-bound without body scrolling");
  assert(styles.includes("-webkit-app-region: drag"), "Borderless shell drag region is missing");
  assert(styles.includes("@media (max-height: 720px)") && styles.includes("@media (prefers-reduced-motion: reduce)"), "Compact viewport and reduced-motion guards are missing");
  assert(styles.includes("--ease-out") && styles.includes("--ring"), "Restrained interaction motion tokens are missing");
  assert(!previewJs.includes("Readable Knowledge Layer") && !previewJs.includes("Use this window for human-readable project memory."), "Old Knowledge explanatory intro should not survive");
  assert(!previewJs.includes("Workbench Safety") && !previewJs.includes("Workbench can explain state and draft OS-routed commands"), "Old Settings explanatory intro should not survive");
  assert(previewJs.includes("openAppWindow"), "Launchpad must expose on-demand app opening");
  assert(previewJs.includes("closeAppWindow"), "Launchpad must expose app closing");
  assert(previewJs.includes("setupOnboarding"), "First-run onboarding setup is missing");
  assert(previewJs.includes("knowledgeos-onboarding-complete"), "Onboarding completion state is missing");
  assert(previewJs.includes("closeOnboarding(true)"), "Onboarding primary action should open Mission");
  assert(previewJs.includes('button.addEventListener("click", () => openAppWindow(button.dataset.app))'), "Single-click app opening is missing");
  assert(previewJs.includes('button.addEventListener("mouseenter", () => renderApp(button.dataset.app))'), "Hover preview is missing");
  assert(previewJs.includes('event.key === "Enter"'), "Keyboard Enter app opening is missing");
  assert(previewJs.includes('event.key !== "Escape"'), "Escape-to-close behavior is missing");
  assert(rootReadme.includes('subgraph Workbench["KnowledgeOS Workbench"]'), "Root README should describe Workbench as current, not future");
  assert(rootReadme.includes("KnowledgeOS Workbench is the current visual desktop"), "Root README project status should mention the current Workbench app");
  assert(rootReadme.includes("Download Workbench"), "Root README should make the packaged app download visible");
  assert(rootReadme.includes("KnowledgeOS-Workbench-0.1.1-arm64.dmg"), "Root README should link the v0.1.1 DMG release asset");
  assert(rootReadme.includes("66 passing") && rootReadme.includes("30 checkpoints passing"), "Root README should reflect the current release validation scale");
  assert(!rootReadme.includes("26 passing") && !rootReadme.includes("14 checkpoints passing"), "Root README still contains stale validation counts");
  assert(!rootReadme.includes("Future workbench apps are expected"), "Root README still contains old future Workbench wording");
  assert(appReadme.includes("Use the packaged macOS app from the GitHub Release"), "App README should prioritize release download over local builds");
  assert(appReadme.includes("Maintainer Commands"), "App README should keep build commands in a maintainer-only section");
  assert(appReadme.includes("pnpm --dir apps/workbench dist:mac"), "App README should document the macOS distribution command for maintainers");
  assert(appReadme.includes("Right click -> Open"), "App README should document ad-hoc local macOS opening");
  assert(appReadme.includes("does not track generated desktop binaries"), "App README should document the Release asset boundary");
  assert(packagingDoc.includes("Workbench Release Packaging"), "Packaging doc is missing its release-focused title");
  assert(packagingDoc.includes("Public Release Assets"), "Packaging doc should describe published release assets");
  assert(packagingDoc.includes("resources/knowledgeos"), "Packaging doc should document bundled kernel resource resolution");
  assert(packagingDoc.includes("bridge binds only to `127.0.0.1`"), "Packaging doc should document local bridge binding");
  assert(packagingDoc.includes("Do not commit generated binaries"), "Packaging doc should document release artifact boundaries");
  assert(packagingDoc.includes("SHA256SUMS.txt"), "Packaging doc should document checksum release assets");

  assert(fs.existsSync(knowledgeosBin), `KnowledgeOS binary missing: ${knowledgeosBin}`);
  const remotePreview = spawnSync(
    knowledgeosBin,
    ["workbench-preview", "--project-root", projectRoot, "--host", "0.0.0.0", "--port", "0"],
    {
      cwd: projectRoot,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      encoding: "utf8"
    }
  );
  assert(remotePreview.status === 2, "workbench-preview must reject non-loopback hosts");
  assert(remotePreview.stderr.includes("only supports loopback hosts"), "workbench-preview host rejection message is missing");

  const child = spawn(knowledgeosBin, ["workbench-preview", "--project-root", projectRoot, "--host", "127.0.0.1", "--port", "0"], {
    cwd: projectRoot,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"]
  });

  try {
    const { url } = await waitForPreviewUrl(child);
    const html = await fetch(url).then((response) => {
      assert(response.ok, `Preview HTML failed: ${response.status}`);
      return response.text();
    });
    assert(html.includes("KnowledgeOS"), "Preview HTML does not look like Workbench UI");
    assertNoConsoleSurface(html, "served HTML");

    const state = await fetch(`${url}/workbench-state.json`).then((response) => {
      assert(response.ok, `Workbench state failed: ${response.status}`);
      return response.json();
    });
    assert(state.schema_version === "knowledgeos.workbench-state.v1", "Workbench state schema mismatch");
    assert(state.runtime_adapters, "Runtime adapter readiness is missing from state");

    const lifecycle = await fetch(`${url}/workbench-lifecycle.json?task-id=${encodeURIComponent(state.tasks?.current?.id || "")}`).then((response) => {
      assert(response.ok, `Workbench lifecycle failed: ${response.status}`);
      return response.json();
    });
    assert(lifecycle.schema_version === "knowledgeos.workbench-lifecycle.v1", "Workbench lifecycle schema mismatch");
    assert(Array.isArray(lifecycle.stages) && lifecycle.stages.length === 7, "Lifecycle must expose seven stages");
    assert(lifecycle.stages.some((stage) => stage.key === "write_guard"), "Write Guard stage is missing");
  } finally {
    child.kill("SIGTERM");
  }

  console.log("workbench smoke: ok");
}

main().catch((error) => {
  console.error(`workbench smoke: fail\n${error.stack || error.message}`);
  process.exit(1);
});
