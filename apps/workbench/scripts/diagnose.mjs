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

async function waitForPreviewUrl(child) {
  let transcript = "";
  return await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timed out waiting for preview URL. Output:\n${transcript}`)), 10000);
    const onData = (chunk) => {
      transcript += chunk.toString();
      const match = transcript.match(/KnowledgeOS Workbench preview:\s*(http:\/\/127\.0\.0\.1:\d+)/);
      if (!match) return;
      clearTimeout(timer);
      resolve({ url: match[1], transcript });
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

async function readJson(url, label) {
  const response = await fetch(url);
  assert(response.ok, `${label} failed: ${response.status}`);
  return await response.json();
}

function summarizeStages(stages = []) {
  return stages.map((stage) => `${stage.key}:${stage.status}`).join(" -> ");
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
    "workbench:sandbox-create",
    "workbench:sandbox-destroy",
    "workbench:knowledge-scope-resolve",
    "knowledgeos.guided-context-snapshot.v1",
    "sandbox-exec",
    "modelCliLaunchEnabled"
  ];
  for (const item of banned) {
    assert(!source.includes(item), `${label} still contains console surface: ${item}`);
  }
}

function assertElectronBoundary() {
  const mainSource = fs.readFileSync(path.join(appRoot, "electron", "main.mjs"), "utf8");
  const preloadSource = fs.readFileSync(path.join(appRoot, "electron", "preload.cjs"), "utf8");
  const previewIndex = fs.readFileSync(path.join(repoRoot, "examples", "workbench", "index.html"), "utf8");
  const previewJs = fs.readFileSync(path.join(repoRoot, "examples", "workbench", "app.js"), "utf8");
  const styles = fs.readFileSync(path.join(repoRoot, "examples", "workbench", "styles.css"), "utf8");

  assert(mainSource.includes("workspaces.json"), "workspace registry support is missing");
  assert(mainSource.includes("process.resourcesPath") && mainSource.includes("bundledKernelRoot"), "bundled KnowledgeOS kernel resolution is missing");
  assert(mainSource.includes('titleBarStyle: "hiddenInset"'), "hidden inset titlebar is missing");
  assert(mainSource.includes("trafficLightPosition"), "native macOS traffic light placement is missing");
  assert(mainSource.includes("contextIsolation: true"), "contextIsolation is not enabled");
  assert(mainSource.includes("sandbox: true"), "renderer sandbox is not enabled");
  assert(!mainSource.includes("nodeIntegration: true"), "nodeIntegration must stay disabled");
  assert(preloadSource.includes("contextBridge.exposeInMainWorld"), "preload API is missing");
  assert(preloadSource.includes("getWorkspaces") && preloadSource.includes("runDoctor"), "workspace preload API is incomplete");
  assert(!preloadSource.includes('require("fs")') && !preloadSource.includes("require('fs')"), "preload must not expose fs");
  assert(previewIndex.includes('id="workspace-panel"'), "workspace switcher panel is missing");
  assert(previewIndex.includes('id="app-window" hidden'), "app window is missing");
  assert(previewJs.includes("Monitoring and viewing only"), "monitoring-only product boundary is missing");
  assert(previewJs.includes("missionAppContent"), "Mission Control renderer is missing");
  assert(previewJs.includes("contextAppContent"), "Context renderer is missing");
  assert(previewJs.includes("evidenceAppContent"), "Evidence renderer is missing");
  assert(previewJs.includes("runsAppContent"), "Runs renderer is missing");
  assert(previewJs.includes("knowledgeAppContent"), "Knowledge renderer is missing");
  assert(previewJs.includes("settingsAppContent"), "Settings renderer is missing");
  assert(previewJs.includes('kernel: "bundled"'), "bundled kernel disclosure is missing");
  assert(previewJs.includes('bridge: "local 127.0.0.1"'), "local bridge disclosure is missing");
  assert(styles.includes(".launchpad") && styles.includes(".now-shelf"), "Launchpad monitor shell styles are missing");
  assert(styles.includes("height: 100dvh") && styles.includes("overflow: hidden"), "viewport-bound home layout is missing");
  assert(styles.includes("-webkit-app-region: drag"), "borderless drag region is missing");

  assertNoConsoleSurface(mainSource, "electron main");
  assertNoConsoleSurface(preloadSource, "electron preload");
  assertNoConsoleSurface(previewIndex, "preview HTML");
  assertNoConsoleSurface(previewJs, "preview JS");
  assertNoConsoleSurface(styles, "preview CSS");
}

async function main() {
  assertElectronBoundary();
  const child = spawn(knowledgeosBin, ["workbench-preview", "--project-root", projectRoot, "--host", "127.0.0.1", "--port", "0"], {
    cwd: projectRoot,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"]
  });

  try {
    const { url } = await waitForPreviewUrl(child);
    const health = await fetch(`${url}/healthz`).then((response) => response.text());
    assert(health === "ok\n", "health endpoint did not return ok");

    const html = await fetch(url).then((response) => response.text());
    assertNoConsoleSurface(html, "served HTML");

    const state = await readJson(`${url}/workbench-state.json`, "state endpoint");
    assert(state.schema_version === "knowledgeos.workbench-state.v1", "state schema mismatch");
    const taskId = state.system_black_box?.latest_run?.task_id || state.tasks?.current?.id || "";

    const lifecycle = await readJson(`${url}/workbench-lifecycle.json?task-id=${encodeURIComponent(taskId)}`, "lifecycle endpoint");
    assert(lifecycle.schema_version === "knowledgeos.workbench-lifecycle.v1", "lifecycle schema mismatch");
    assert(Array.isArray(lifecycle.stages) && lifecycle.stages.length === 7, "lifecycle must expose seven stages");

    console.log("KnowledgeOS Workbench Diagnose");
    console.log(`bridge: ok ${url}`);
    console.log(`state: ${state.status} task=${taskId || "none"} doctor=${state.system_black_box?.doctor?.status || "unknown"}`);
    console.log(`lifecycle: ${lifecycle.selected_task?.id || "none"} ${summarizeStages(lifecycle.stages)}`);
    console.log(`runtime inventory: ${state.runtime_adapters?.status || "unknown"} ${state.runtime_adapters?.available_count || 0}/${state.runtime_adapters?.total || 0}`);
    console.log("surface: monitoring-only; no Command Dock, Ask Sandbox, raw terminal, prompt builder, or model launch UI");
    console.log("electron: workspace registry + read-only bridge boundary ok");
    console.log("diagnose: ok");
  } finally {
    child.kill("SIGTERM");
  }
}

main().catch((error) => {
  console.error(`workbench diagnose: fail\n${error.stack || error.message}`);
  process.exit(1);
});
