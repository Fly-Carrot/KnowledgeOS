import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { spawn, spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const appRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(appRoot, "..", "..");
const bundledKernelRoot = app.isPackaged ? path.join(process.resourcesPath, "knowledgeos") : repoRoot;
const explicitProjectRoot = Boolean(process.env.KNOWLEDGEOS_PROJECT_ROOT);
const defaultProjectRoot = path.resolve(process.env.KNOWLEDGEOS_PROJECT_ROOT || (app.isPackaged ? os.homedir() : repoRoot));

let projectRoot = defaultProjectRoot;
const knowledgeosBin = path.resolve(process.env.KNOWLEDGEOS_BIN || path.join(bundledKernelRoot, "bin", "knowledgeos"));

let mainWindow = null;
let bridgeProcess = null;
let bridgeReady = false;
let isQuitting = false;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function failurePage(message, details = "") {
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>KnowledgeOS Workbench</title>
<style>
:root{color-scheme:light dark;font-family:"Avenir Next","Helvetica Neue",sans-serif;background:#f4f3ef;color:#202321}
@media (prefers-color-scheme:dark){:root{background:#141514;color:#f0eee9}}
body{min-height:100vh;margin:0;display:grid;place-items:center;background:radial-gradient(circle at 50% 28%,rgba(95,127,140,.13),transparent 30rem),var(--bg,#f4f3ef)}
main{width:min(680px,calc(100vw - 48px));padding:34px;border:1px solid rgba(95,127,140,.18);border-radius:30px;background:rgba(250,249,245,.86);box-shadow:0 30px 110px rgba(20,35,42,.14)}
@media (prefers-color-scheme:dark){main{background:rgba(27,28,27,.88);box-shadow:0 30px 110px rgba(0,0,0,.28)}}
h1{margin:0 0 12px;font-size:40px;letter-spacing:-.05em}p,pre{color:#737a75;line-height:1.55}pre{white-space:pre-wrap;border-top:1px solid rgba(95,127,140,.16);padding-top:18px}
</style></head><body><main><h1>Bridge did not start.</h1><p>${escapeHtml(message)}</p><pre>${escapeHtml(details)}</pre></main></body></html>`;
}

function appDataPath(...parts) {
  return path.join(app.getPath("userData"), ...parts);
}

function workspaceRegistryPath() {
  return appDataPath("workspaces.json");
}

function workspaceId(root) {
  return crypto.createHash("sha1").update(path.resolve(root)).digest("hex").slice(0, 12);
}

function isDangerousWorkspaceRoot(root) {
  const resolved = path.resolve(root);
  const home = os.homedir();
  const blocked = new Set([
    home,
    path.join(home, "Desktop"),
    path.join(home, "Downloads"),
    path.join(home, "Documents"),
    path.join(home, "Library")
  ]);
  return blocked.has(resolved);
}

function readJsonFile(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return fallback;
  }
}

function writeJsonFile(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);
}

function normalizeWorkspace(root, label = "") {
  const resolved = path.resolve(root);
  return {
    id: workspaceId(resolved),
    name: label || path.basename(resolved) || "Workspace",
    root: resolved
  };
}

function loadWorkspaceRegistry() {
  const fallback = {
    selected: workspaceId(projectRoot),
    workspaces: [normalizeWorkspace(projectRoot, projectRoot === repoRoot ? "KnowledgeOS" : "Choose Workspace")]
  };
  const registry = readJsonFile(workspaceRegistryPath(), fallback);
  const workspaces = Array.isArray(registry.workspaces) ? registry.workspaces : [];
  const merged = [...workspaces, normalizeWorkspace(projectRoot, projectRoot === repoRoot ? "KnowledgeOS" : "")];
  const deduped = new Map();
  for (const item of merged) {
    if (!item?.root) continue;
    const normalized = normalizeWorkspace(item.root, item.name);
    deduped.set(normalized.id, normalized);
  }
  const selected = registry.selected && deduped.has(registry.selected) ? registry.selected : workspaceId(projectRoot);
  return { selected, workspaces: [...deduped.values()] };
}

function saveWorkspaceRegistry(registry) {
  writeJsonFile(workspaceRegistryPath(), registry);
}

function applySelectedWorkspaceFromRegistry() {
  if (explicitProjectRoot) return;
  const registry = loadWorkspaceRegistry();
  const selected = registry.workspaces.find((workspace) => workspace.id === registry.selected);
  if (selected?.root) projectRoot = path.resolve(selected.root);
}

function runKnowledgeOS(args, cwd = projectRoot, timeoutMs = 8000) {
  const child = spawnSync(knowledgeosBin, args, {
    cwd,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    encoding: "utf8",
    timeout: timeoutMs
  });
  return {
    status: child.status,
    signal: child.signal,
    stdout: child.stdout || "",
    stderr: child.stderr || "",
    error: child.error?.message || ""
  };
}

function inspectWorkspace(workspace) {
  const root = path.resolve(workspace.root);
  const hasControlPlane = fs.existsSync(path.join(root, ".agent-os"));
  const dangerous = isDangerousWorkspaceRoot(root);
  if (dangerous && !hasControlPlane) {
    return { ...workspace, root, status: "blocked_root", boot: "KOS_UNSAFE", detail: "Broad container folder cannot be initialized from Workbench." };
  }
  if (!hasControlPlane) {
    return { ...workspace, root, status: "unmanaged", boot: "KOS_UNMANAGED", detail: ".agent-os control plane not found." };
  }
  const result = runKnowledgeOS(["doctor", "--project-root", root, "--summary"], root, 10000);
  const ok = result.status === 0 && /status:\s*ok/.test(result.stdout);
  const failedMatch = result.stdout.match(/failed:\s*(\d+)/);
  const checksMatch = result.stdout.match(/checks:\s*(\d+)/);
  return {
    ...workspace,
    root,
    status: ok ? "managed_ok" : "doctor_failed",
    boot: ok ? "BOOT_OK" : "DOCTOR_FAILED",
    checks: checksMatch ? Number(checksMatch[1]) : 0,
    failed: failedMatch ? Number(failedMatch[1]) : 0,
    detail: ok ? "Doctor passed for this workspace." : (result.stderr || result.stdout || result.error || "Doctor failed.")
  };
}

function createWindow() {
  applySelectedWorkspaceFromRegistry();
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1180,
    minHeight: 760,
    title: "KnowledgeOS Workbench",
    backgroundColor: "#f4f3ef",
    autoHideMenuBar: true,
    titleBarStyle: "hiddenInset",
    trafficLightPosition: { x: 14, y: 14 },
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow.setMenuBarVisibility(false);
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  void mainWindow.loadFile(path.join(appRoot, "index.html"));
  startBridge(mainWindow);
}

function startBridge(win) {
  cleanupBridge();
  bridgeReady = false;
  const args = [
    "workbench-preview",
    "--project-root",
    projectRoot,
    "--host",
    "127.0.0.1",
    "--port",
    "0"
  ];

  bridgeProcess = spawn(knowledgeosBin, args, {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1"
    },
    stdio: ["ignore", "pipe", "pipe"]
  });

  let transcript = `$ ${knowledgeosBin} ${args.map((item) => JSON.stringify(item)).join(" ")}\n`;
  const readyTimer = setTimeout(() => {
    if (!bridgeReady && !win.isDestroyed()) {
      win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(failurePage("KnowledgeOS bridge startup timed out.", transcript))}`);
      cleanupBridge();
    }
  }, 15000);

  function handleChunk(chunk) {
    const text = chunk.toString();
    transcript += text;
    const match = transcript.match(/KnowledgeOS Workbench preview:\s*(http:\/\/127\.0\.0\.1:\d+)/);
    if (!match || bridgeReady || win.isDestroyed()) return;
    bridgeReady = true;
    clearTimeout(readyTimer);
    void win.loadURL(match[1]);
  }

  bridgeProcess.stdout.on("data", handleChunk);
  bridgeProcess.stderr.on("data", handleChunk);
  bridgeProcess.on("error", (error) => {
    clearTimeout(readyTimer);
    if (!win.isDestroyed()) {
      win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(failurePage("Unable to launch KnowledgeOS bridge.", `${transcript}\n${error.message}`))}`);
    }
  });
  bridgeProcess.on("exit", (code, signal) => {
    clearTimeout(readyTimer);
    const expectedExit = isQuitting || signal === "SIGTERM" || signal === "SIGKILL";
    if (!bridgeReady && !expectedExit && !win.isDestroyed()) {
      win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(failurePage(`KnowledgeOS bridge exited before it was ready. code=${code ?? "null"} signal=${signal ?? "null"}`, transcript))}`);
    }
  });
}

function cleanupBridge() {
  if (!bridgeProcess || bridgeProcess.killed) return;
  const child = bridgeProcess;
  bridgeProcess = null;
  child.kill("SIGTERM");
  setTimeout(() => {
    if (!child.killed) child.kill("SIGKILL");
  }, 1500).unref?.();
}

function setupIpc() {
  ipcMain.handle("workbench:workspaces", () => {
    const registry = loadWorkspaceRegistry();
    return {
      selected: registry.selected,
      workspaces: registry.workspaces.map((workspace) => ({
        ...inspectWorkspace(workspace),
        selected: workspace.id === registry.selected
      }))
    };
  });

  ipcMain.handle("workbench:add-workspace", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: "Add KnowledgeOS workspace",
      properties: ["openDirectory"]
    });
    if (result.canceled || !result.filePaths[0]) return { canceled: true };
    const registry = loadWorkspaceRegistry();
    const workspace = normalizeWorkspace(result.filePaths[0]);
    if (!registry.workspaces.some((item) => item.id === workspace.id)) registry.workspaces.push(workspace);
    saveWorkspaceRegistry(registry);
    return { canceled: false, workspace: inspectWorkspace(workspace) };
  });

  ipcMain.handle("workbench:remove-workspace", (_event, id) => {
    const registry = loadWorkspaceRegistry();
    const filtered = registry.workspaces.filter((workspace) => workspace.id !== id);
    const selected = registry.selected === id ? (filtered[0]?.id || workspaceId(projectRoot)) : registry.selected;
    saveWorkspaceRegistry({ selected, workspaces: filtered });
    return { removed: filtered.length !== registry.workspaces.length, selected };
  });

  ipcMain.handle("workbench:select-workspace", (_event, id) => {
    const registry = loadWorkspaceRegistry();
    const workspace = registry.workspaces.find((item) => item.id === id);
    if (!workspace) throw new Error("workspace_not_found");
    projectRoot = path.resolve(workspace.root);
    saveWorkspaceRegistry({ ...registry, selected: id });
    if (mainWindow) startBridge(mainWindow);
    return inspectWorkspace(workspace);
  });

  ipcMain.handle("workbench:run-doctor", (_event, id) => {
    const registry = loadWorkspaceRegistry();
    const workspace = registry.workspaces.find((item) => item.id === id);
    if (!workspace) throw new Error("workspace_not_found");
    return inspectWorkspace(workspace);
  });
}

app.on("before-quit", () => {
  isQuitting = true;
  cleanupBridge();
});

app.on("window-all-closed", () => {
  app.quit();
});

app.whenReady().then(() => {
  setupIpc();
  createWindow();
});
