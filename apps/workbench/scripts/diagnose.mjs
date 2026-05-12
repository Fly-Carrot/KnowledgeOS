import { spawn } from "node:child_process";
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

async function main() {
  const child = spawn(knowledgeosBin, ["workbench-preview", "--project-root", projectRoot, "--host", "127.0.0.1", "--port", "0"], {
    cwd: projectRoot,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"]
  });

  try {
    const { url } = await waitForPreviewUrl(child);
    const health = await fetch(`${url}/healthz`).then((response) => response.text());
    assert(health === "ok\n", "health endpoint did not return ok");

    const state = await readJson(`${url}/workbench-state.json`, "state endpoint");
    assert(state.schema_version === "knowledgeos.workbench-state.v1", "state schema mismatch");
    const taskId = state.system_black_box?.latest_run?.task_id || state.tasks?.current?.id || "";

    const lifecycle = await readJson(`${url}/workbench-lifecycle.json?task-id=${encodeURIComponent(taskId)}`, "lifecycle endpoint");
    assert(lifecycle.schema_version === "knowledgeos.workbench-lifecycle.v1", "lifecycle schema mismatch");
    assert(Array.isArray(lifecycle.stages) && lifecycle.stages.length === 7, "lifecycle must expose seven stages");

    const sandbox = await fetch(`${url}/api/ask-sandbox`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: "Please create a short project report." })
    }).then((response) => {
      assert(response.ok, `sandbox endpoint failed: ${response.status}`);
      return response.json();
    });
    assert(sandbox.schema_version === "knowledgeos.ask-sandbox.v1", "sandbox schema mismatch");
    assert(sandbox.executed === false, "sandbox must not execute commands");
    assert(sandbox.project_mutation === false, "sandbox must not mutate project files");
    assert(sandbox.recommended_next_step === "route_through_os", "mutation-like prompt should be routed through OS");
    assert(Array.isArray(sandbox.recommended_os_commands) && sandbox.recommended_os_commands.length >= 5, "sandbox command chain is missing");

    console.log("KnowledgeOS Workbench Diagnose");
    console.log(`bridge: ok ${url}`);
    console.log(`state: ${state.status} task=${taskId || "none"} doctor=${state.system_black_box?.doctor?.status || "unknown"}`);
    console.log(`lifecycle: ${lifecycle.selected_task?.id || "none"} ${summarizeStages(lifecycle.stages)}`);
    console.log(`sandbox: ${sandbox.recommended_next_step} executed=${sandbox.executed} mutation=${sandbox.project_mutation}`);
    console.log(`runtime: ${state.runtime_adapters?.status || "unknown"} ${state.runtime_adapters?.available_count || 0}/${state.runtime_adapters?.total || 0}`);
    console.log("diagnose: ok");
  } finally {
    child.kill("SIGTERM");
  }
}

main().catch((error) => {
  console.error(`workbench diagnose: fail\n${error.stack || error.message}`);
  process.exit(1);
});
