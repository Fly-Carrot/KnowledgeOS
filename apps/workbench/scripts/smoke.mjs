import { spawn } from "node:child_process";
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

async function main() {
  const pkg = JSON.parse(read("package.json"));
  assert(pkg.scripts.dev === "electron .", "dev script must launch Electron");
  assert(pkg.scripts.smoke === "node scripts/smoke.mjs", "smoke script must stay deterministic");
  assert(pkg.scripts.diagnose === "node scripts/diagnose.mjs", "diagnose script is missing");
  assert(pkg.devDependencies.electron, "Electron dependency is missing");
  assert(pkg.devDependencies.vite, "Vite dependency is missing");

  const mainSource = read("electron/main.mjs");
  assert(mainSource.includes("workbench-preview"), "Electron shell must launch workbench-preview");
  assert(mainSource.includes('"--port"') && mainSource.includes('"0"'), "Bridge must use port 0");
  assert(mainSource.includes("PYTHONUNBUFFERED"), "Bridge stdout must be unbuffered for URL parsing");
  assert(mainSource.includes("KNOWLEDGEOS_PROJECT_ROOT"), "Project root override is missing");
  assert(mainSource.includes("KNOWLEDGEOS_BIN"), "KnowledgeOS binary override is missing");
  assert(mainSource.includes("cleanupBridge"), "Bridge cleanup hook is missing");
  assert(mainSource.includes("width: 1280"), "Electron default width should stay restrained");
  assert(mainSource.includes("height: 840"), "Electron default height should stay restrained");
  assert(!mainSource.includes("hiddenInset"), "Electron titlebar should not hide macOS chrome in this phase");
  assert(!mainSource.includes("trafficLightPosition"), "Electron shell should not collide with macOS window controls");

  const previewIndex = fs.readFileSync(path.join(repoRoot, "examples", "workbench", "index.html"), "utf8");
  const styles = fs.readFileSync(path.join(repoRoot, "examples", "workbench", "styles.css"), "utf8");
  const oldGreenLight = ["#", "0f", "5f", "66"].join("");
  const oldGreenDark = ["#", "9d", "d9", "d2"].join("");
  const oldBrightLight = ["#", "0a", "84", "ff"].join("");
  const oldBrightDark = ["#", "64", "d2", "ff"].join("");
  assert(!styles.includes(oldGreenLight), "Old green light accent still exists");
  assert(!styles.includes(oldGreenDark), "Old green dark accent still exists");
  assert(!styles.includes(oldBrightLight), "High-saturation blue light accent still exists");
  assert(!styles.includes(oldBrightDark), "High-saturation blue dark accent still exists");
  assert(previewIndex.includes('class="launchpad"'), "Launchpad app grid is missing");
  assert(previewIndex.includes('class="now-shelf"'), "Now Shelf is missing");
  assert(previewIndex.includes('id="command-panel"'), "Command panel is missing");
  assert(previewIndex.includes('id="onboarding-open"'), "Onboarding reopen control is missing");
  assert(previewIndex.includes('id="app-window" hidden'), "On-demand app window must exist and start hidden");
  assert(previewIndex.includes('id="window-close"'), "App window close control is missing");
  assert(previewIndex.includes('id="window-body"'), "App window body is missing");
  assert(previewIndex.includes('id="onboarding-screen"'), "First-run onboarding screen is missing");
  assert(previewIndex.includes("Getting Started"), "Onboarding title is missing");
  assert(previewIndex.includes("Start with Mission"), "Onboarding primary action is missing");
  assert(previewIndex.includes("Choose an app") && previewIndex.includes("Preview state"), "Onboarding steps are incomplete");
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
  assert(!previewIndex.includes("Current Task</p>"), "Old dashboard Current Task block still exists on home");
  assert(!previewIndex.includes("Capability Health</p>"), "Old dashboard Capability Health block still exists on home");
  assert(styles.includes("#6f8790") && styles.includes("#819aa2"), "Muted graphite/blue-gray accents are missing");
  assert(styles.includes("width: min(1180px, calc(100vw - 64px))"), "Desktop max-width guard is missing");
  assert(styles.includes("margin: 0 auto"), "Desktop centering rule is missing");
  assert(styles.includes("grid-template-rows: minmax(max-content, clamp(430px, 45vh, 470px)) auto"), "Desktop should use anchored Launchpad and Shelf rows");
  assert(styles.includes("align-content: start") && styles.includes("align-items: start"), "Desktop should not recenter when shelf height changes");
  assert(styles.includes("align-self: end") && styles.includes("justify-self: center"), "Launchpad row should be anchored");
  assert(styles.includes("align-self: start") && styles.includes("justify-self: stretch"), "Now Shelf top edge should be anchored");
  assert(styles.includes("width: 100%"), "Now Shelf should keep left/right anchors");
  assert(styles.includes("grid-template-columns: repeat(3, minmax(180px, 1fr))"), "Launchpad should use a 3-column / 2-row layout");
  assert(styles.includes("width: 96px") && styles.includes("height: 96px"), "Launchpad icons should be enlarged");
  assert(!styles.includes("grid-template-columns: repeat(6"), "Single-row six-icon Launchpad layout should not survive");
  assert(!styles.includes("width: 72px") && !styles.includes("height: 72px"), "Old smaller icon sizing should not survive");
  assert(styles.includes(".app-window") && styles.includes(".window-card"), "On-demand app window styles are missing");
  assert(styles.includes(".window-grid") && styles.includes(".window-list"), "App window detail layout is missing");
  assert(styles.includes(".onboarding-screen") && styles.includes(".onboarding-card"), "Onboarding screen styles are missing");
  assert(styles.includes(".onboarding-steps") && styles.includes(".onboarding-actions"), "Onboarding layout styles are missing");
  assert(styles.includes("#onboarding-open") && styles.includes("font-weight: 900"), "Help icon should be bold");
  assert(!styles.includes("prefers-color-scheme: dark"), "System theme media query should not survive");
  assert(!styles.includes("grid-template-columns: 220px minmax(0, 1fr) 300px"), "Old three-column dashboard shell still controls layout");
  assert(!styles.includes(".hero-card"), "Hero card CSS should not survive this simplified home");
  assert(!styles.includes(".app-sheet"), "App sheet CSS should not survive this simplified home");

  const previewJs = fs.readFileSync(path.join(repoRoot, "examples", "workbench", "app.js"), "utf8");
  assert(previewJs.includes("openAppWindow"), "Launchpad must expose on-demand app opening");
  assert(previewJs.includes("closeAppWindow"), "Launchpad must expose app closing");
  assert(previewJs.includes("setupOnboarding"), "First-run onboarding setup is missing");
  assert(previewJs.includes("knowledgeos-onboarding-complete"), "Onboarding completion state is missing");
  assert(previewJs.includes("closeOnboarding(true)"), "Onboarding primary action should open Mission");
  assert(previewJs.includes('button.addEventListener("click", () => openAppWindow(button.dataset.app))'), "Single-click app opening is missing");
  assert(previewJs.includes('button.addEventListener("mouseenter", () => renderApp(button.dataset.app))'), "Hover preview is missing");
  assert(previewJs.includes('button.addEventListener("focus", () => renderApp(button.dataset.app))'), "Keyboard focus preview is missing");
  assert(previewJs.includes("dblclick"), "Double-click app opening is missing");
  assert(previewJs.includes('event.key === "Enter"'), "Keyboard Enter app opening is missing");
  assert(previewJs.includes('event.key !== "Escape"'), "Escape-to-close behavior is missing");

  assert(fs.existsSync(knowledgeosBin), `KnowledgeOS binary missing: ${knowledgeosBin}`);
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
