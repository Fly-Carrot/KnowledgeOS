import { app, BrowserWindow } from "electron";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const appRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(appRoot, "..", "..");

const projectRoot = path.resolve(process.env.KNOWLEDGEOS_PROJECT_ROOT || repoRoot);
const knowledgeosBin = path.resolve(process.env.KNOWLEDGEOS_BIN || path.join(repoRoot, "bin", "knowledgeos"));

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

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 1060,
    minHeight: 680,
    title: "KnowledgeOS Workbench",
    backgroundColor: "#f4f3ef",
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  win.setMenuBarVisibility(false);
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  void win.loadFile(path.join(appRoot, "index.html"));
  startBridge(win);
}

function startBridge(win) {
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
  child.kill("SIGTERM");
  setTimeout(() => {
    if (!child.killed) child.kill("SIGKILL");
  }, 1500).unref?.();
}

app.on("before-quit", () => {
  isQuitting = true;
  cleanupBridge();
});

app.on("window-all-closed", () => {
  app.quit();
});

app.whenReady().then(createWindow);
