const fallbackState = {
  schema_version: "knowledgeos.workbench-state.v1",
  project_root: "<PROJECT_ROOT>",
  project_name: "KnowledgeOS",
  managed: true,
  status: "managed_ok",
  boot: { claim: "BOOT_OK", doctor: "ok" },
  workspace: { name: "KnowledgeOS Local Build", root: "<PROJECT_ROOT>", phase: "workbench-preview" },
  project: { id: "KOS001", name: "KnowledgeOS", current_phase: "launchpad-preview" },
  tasks: {
    total: 22,
    counts: { in_progress: 1, ready: 2, completed: 19 },
    current: { id: "KOS-T022", title: "Refine Launchpad desktop", type: "route_bound_execution_guard", status: "in_progress", risk: "workbench_observability_boundary" },
    active: []
  },
  routes: { count: 10, task_types: ["route_bound_execution_guard", "executable_control_plane"] },
  capabilities: { ok: true, counts: { mcp: 6, orchestrator: 1, memory: 1, skill: 4, workflow: 1, subagent: 1 }, entries: [] },
  runtime_adapters: {
    schema_version: "knowledgeos.runtime-adapters.v1",
    status: "ready",
    available_count: 1,
    total: 3,
    policy: { default_runtime: "mock", real_cli_execution: "disabled_until_adapter_phase" },
    adapters: [
      { id: "mock", label: "Mock Sandbox", status: "available", execution_mode: "disabled_by_default" },
      { id: "gemini-cli", label: "Gemini CLI", status: "missing", execution_mode: "disabled_by_default" },
      { id: "codex-cli", label: "Codex CLI", status: "missing", execution_mode: "disabled_by_default" }
    ]
  },
  system_black_box: { doctor: { status: "ok", checks: 520, passed: 520, failed: 0 }, latest_run: null }
};

const fallbackLifecycle = {
  schema_version: "knowledgeos.workbench-lifecycle.v1",
  managed: true,
  status: "ready",
  selected_task: fallbackState.tasks.current,
  next_action: {
    key: "write_guard",
    label: "Review planned writes",
    detail: "Workbench shows the command chain first; no mutation is executed from this preview."
  },
  stages: [
    { key: "doctor", label: "Doctor", status: "ok", detail: "Workspace health is readable." },
    { key: "route", label: "Route", status: "ok", detail: "Task has a workflow route." },
    { key: "dispatch", label: "Dispatch", status: "ok", detail: "Capability order is known." },
    { key: "write_guard", label: "Write Guard", status: "active", detail: "Planned outputs must stay inside allowed paths." },
    { key: "run", label: "Run", status: "pending", detail: "No real execution from Workbench preview." },
    { key: "eval", label: "Eval", status: "pending", detail: "Verification evidence has not been written." },
    { key: "receipt", label: "Receipt", status: "pending", detail: "Completion receipt is pending." }
  ]
};

let currentState = fallbackState;
let currentLifecycle = fallbackLifecycle;
let activeApp = "mission";
let commandMode = "mission";
const onboardingStorageKey = "knowledgeos-onboarding-complete";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function loadJson(sources, fallback) {
  for (const source of sources) {
    try {
      const response = await fetch(source, { cache: "no-store" });
      if (!response.ok) throw new Error(`${source} status ${response.status}`);
      return await response.json();
    } catch (error) {
      // Static file previews fall back from live endpoints to fixtures.
    }
  }
  return fallback;
}

async function loadState() {
  return await loadJson(["workbench-state.json", "workbench-state.fixture.json"], fallbackState);
}

function buildFallbackLifecycle(state) {
  return {
    ...fallbackLifecycle,
    selected_task: state.tasks?.current || fallbackLifecycle.selected_task,
    status: state.managed ? "ready" : "unmanaged"
  };
}

async function loadLifecycle(taskId, state) {
  const query = taskId ? `?task-id=${encodeURIComponent(taskId)}` : "";
  return await loadJson([`workbench-lifecycle.json${query}`], buildFallbackLifecycle(state));
}

function setText(selector, value) {
  const node = $(selector);
  if (node) node.textContent = value || "-";
}

function shortTitle(value, limit = 36) {
  const text = String(value || "");
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

function stageSummary(lifecycle) {
  const stages = lifecycle.stages || [];
  const complete = stages.filter((stage) => ["ok", "passed", "completed", "ready"].includes(stage.status)).length;
  const active = stages.find((stage) => ["active", "in_progress", "attention"].includes(stage.status));
  return { complete, total: stages.length, active };
}

function capabilityCount(state) {
  const counts = state.capabilities?.counts || {};
  return Object.values(counts).reduce((sum, value) => sum + Number(value || 0), 0);
}

function latestRun(state) {
  return state.system_black_box?.latest_run || {};
}

function shelfCardsFor(appKey, state, lifecycle) {
  const task = lifecycle.selected_task || state.tasks?.current || {};
  const doctor = state.system_black_box?.doctor || {};
  const run = latestRun(state);
  const stages = stageSummary(lifecycle);
  const runtime = state.runtime_adapters || {};
  const caps = state.capabilities?.counts || {};
  const activeStage = stages.active?.label || lifecycle.next_action?.label || "Ready";

  const cards = {
    mission: [
      ["Project", state.project?.name || state.project_name || "KnowledgeOS", state.workspace?.root || state.project_root || "<PROJECT_ROOT>"],
      ["Mission", shortTitle(task.title || "No task selected"), task.id ? `${task.id} · ${task.status || "unknown"}` : "Task pending"],
      ["Receipt", run.run_id || state.boot?.claim || "No receipt", run.task_id || "Run evidence stays in OS."],
      ["Health", doctor.status === "ok" ? "Healthy" : "Needs review", `${doctor.passed || 0}/${doctor.checks || 0} project checks · ${doctor.failed || 0} failed`]
    ],
    context: [
      ["Workspace", state.workspace?.name || "Local workspace", state.workspace?.phase || "workbench-preview"],
      ["Task", task.id || "None", task.type || "manual"],
      ["Route", `${state.routes?.count || 0} profiles`, lifecycle.next_action?.label || "No active route"],
      ["Root", state.workspace?.root || state.project_root || "<PROJECT_ROOT>", "Paths stay redacted by default"]
    ],
    evidence: [
      ["Doctor", doctor.status || "not_run", `${doctor.failed || 0} failed project checks`],
      ["Run", run.run_id || "No run", run.status || "No latest run loaded"],
      ["Eval", run.eval_passed ? "Passed" : "Pending", run.eval_profile || "Generated eval required"],
      ["Receipt", run.receipt_exists === false ? "Missing" : "Ready", run.path || "<PROJECT_ROOT>/.agent-os/runs"]
    ],
    runs: [
      ["Lifecycle", `${stages.complete}/${stages.total} stages`, "Doctor · Route · Dispatch · Guard · Run · Eval · Receipt"],
      ["Now", activeStage, lifecycle.next_action?.detail || "Read-only preview"],
      ["Run", run.run_id || "No run", run.task_id || task.id || "Task not selected"],
      ["Guard", task.risk || "low", "Writes remain route-bound"]
    ],
    knowledge: [
      ["Cards", "Readable state", "No raw logs on the home screen"],
      ["Routes", `${state.routes?.count || 0} profiles`, "Workflow choices are explicit"],
      ["Capabilities", `${capabilityCount(state)} indexed`, Object.entries(caps).map(([key, value]) => `${key}:${value}`).join(" · ") || "No entries"],
      ["Memory", caps.memory ? `${caps.memory} lane` : "Not indexed", "Receipts and handoffs remain in OS"]
    ],
    settings: [
      ["Runtime", `${runtime.status || "unknown"} · ${runtime.available_count || 0}/${runtime.total || 0}`, runtime.policy?.real_cli_execution || "disabled"],
      ["Command", "Sandbox first", "Terminal Pro suggests dry-runs only"],
      ["Theme", document.documentElement.dataset.theme || "dark", "Toggle between dark and light"],
      ["Safety", state.capabilities?.ok ? "Healthy" : "Review", "No real Gemini/Codex execution here"]
    ]
  };
  return cards[appKey] || cards.mission;
}

function renderShelf(appKey = activeApp) {
  const cards = shelfCardsFor(appKey, currentState, currentLifecycle);
  cards.forEach(([label, value, detail], index) => {
    const offset = index + 1;
    setText(`#shelf-label-${offset}`, label);
    setText(`#shelf-value-${offset}`, value);
    setText(`#shelf-detail-${offset}`, detail);
  });
}

function renderApp(appKey = activeApp) {
  activeApp = shelfCardsFor(appKey, currentState, currentLifecycle) ? appKey : "mission";
  $$(".app-icon").forEach((button) => {
    const isActive = button.dataset.app === activeApp;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  renderShelf(activeApp);
}

function appLabel(appKey) {
  return $(`.app-icon[data-app="${appKey}"] strong`)?.textContent || "Mission";
}

function appWindowIntro(appKey) {
  const intros = {
    mission: "Intent stays first: draft the next move, then route any mutation through OS commands.",
    context: "Project state is readable here without exposing noisy control-plane files on the desktop.",
    evidence: "Receipts, evals, and doctor results remain visible as proof, not decoration.",
    runs: "Lifecycle stages show where the task is now and what still needs evidence.",
    knowledge: "Readable cards summarize the knowledge layer while raw logs stay inside KnowledgeOS.",
    settings: "Runtime adapters and safety defaults are visible, but real agent execution stays disabled here."
  };
  return intros[appKey] || intros.mission;
}

function windowCard(label, value, detail) {
  return `
    <article class="window-micro-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(detail)}</small>
    </article>
  `;
}

function lifecycleRows(lifecycle) {
  const stages = lifecycle.stages || [];
  if (!stages.length) return "";
  return `
    <ol class="window-list" aria-label="Lifecycle stages">
      ${stages.map((stage) => `
        <li>
          <span class="stage-dot ${escapeHtml(stage.status || "pending")}"></span>
          <strong>${escapeHtml(stage.label || stage.key)}</strong>
          <small>${escapeHtml(stage.detail || stage.status || "")}</small>
        </li>
      `).join("")}
    </ol>
  `;
}

function appWindowContent(appKey, state, lifecycle) {
  const task = lifecycle.selected_task || state.tasks?.current || {};
  const cards = shelfCardsFor(appKey, state, lifecycle);
  const nextAction = lifecycle.next_action?.label || "Review route";
  const commandHint = appKey === "mission"
    ? "Open Command Panel to draft safely; mutation still requires route, guard, run, eval, and receipt."
    : `Recommended next check: ${nextAction}.`;
  const stagePanel = appKey === "runs" ? lifecycleRows(lifecycle) : "";
  return `
    <p class="window-intro">${escapeHtml(appWindowIntro(appKey))}</p>
    <div class="window-grid">
      ${cards.map(([label, value, detail]) => windowCard(label, value, detail)).join("")}
    </div>
    ${stagePanel}
    <div class="window-note">
      <strong>${escapeHtml(task.id || "No active task")}</strong>
      <span>${escapeHtml(commandHint)}</span>
    </div>
  `;
}

function openAppWindow(appKey = activeApp) {
  renderApp(appKey);
  const panel = $("#app-window");
  const title = $("#window-title");
  const eyebrow = $("#window-eyebrow");
  const body = $("#window-body");
  if (!panel || !title || !eyebrow || !body) return;
  const label = appLabel(activeApp);
  title.textContent = label;
  eyebrow.textContent = `${label} App`;
  body.innerHTML = appWindowContent(activeApp, currentState, currentLifecycle);
  panel.dataset.app = activeApp;
  panel.hidden = false;
  $("#window-close")?.focus();
}

function closeAppWindow() {
  const panel = $("#app-window");
  if (!panel || panel.hidden) return;
  panel.hidden = true;
  $(`.app-icon[data-app="${activeApp}"]`)?.focus();
}

function closeOnboarding(openMission = false) {
  const panel = $("#onboarding-screen");
  if (!panel) return;
  localStorage.setItem(onboardingStorageKey, "true");
  panel.hidden = true;
  if (openMission) openAppWindow("mission");
}

function openOnboarding() {
  const panel = $("#onboarding-screen");
  if (!panel) return;
  panel.hidden = false;
  $("#onboarding-start")?.focus();
}

function render(state, lifecycle) {
  currentState = state;
  currentLifecycle = lifecycle || buildFallbackLifecycle(state);
  renderApp(activeApp);
}

function commandList(commands = []) {
  if (!commands.length) return "";
  return `<ol class="command-list">${commands.map((command) => `<li><code>${escapeHtml(command)}</code></li>`).join("")}</ol>`;
}

function renderSandboxResult(payload) {
  const result = $("#sandbox-result");
  if (!result) return;
  const title = payload.recommended_next_step
    ? `Sandbox: ${payload.recommended_next_step}`
    : "Sandbox unavailable";
  const detail = payload.response || payload.reason || "No sandbox response.";
  result.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    <span>${escapeHtml(detail)}</span>
    ${commandList(payload.recommended_os_commands || [])}
  `;
}

async function askSandbox() {
  const input = $("#intent-input");
  const button = $("#ask-sandbox");
  const prompt = input?.value?.trim() || "";
  if (!prompt) {
    renderSandboxResult({ reason: "Write an intent first. The sandbox will not infer hidden context." });
    return;
  }
  if (button) {
    button.disabled = true;
    button.textContent = "Asking...";
  }
  try {
    const response = await fetch("api/ask-sandbox", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, mode: commandMode })
    });
    if (!response.ok) throw new Error(`sandbox status ${response.status}`);
    renderSandboxResult(await response.json());
  } catch (error) {
    renderSandboxResult({
      reason: "Live sandbox is available through `knowledgeos workbench-preview`; static fixture mode stays read-only."
    });
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Ask Sandbox";
    }
  }
}

function setupTheme() {
  const html = document.documentElement;
  const button = $("#theme-toggle");
  const modes = ["dark", "light"];
  const saved = localStorage.getItem("knowledgeos-theme");
  html.dataset.theme = modes.includes(saved) ? saved : "dark";
  if (!button) return;
  button.textContent = html.dataset.theme === "dark" ? "Dark" : "Light";
  button.addEventListener("click", () => {
    const next = modes[(modes.indexOf(html.dataset.theme) + 1) % modes.length];
    html.dataset.theme = next;
    localStorage.setItem("knowledgeos-theme", next);
    button.textContent = next === "dark" ? "Dark" : "Light";
    if (activeApp === "settings") renderShelf("settings");
  });
}

function setupLaunchpad() {
  $$(".app-icon").forEach((button) => {
    button.addEventListener("mouseenter", () => renderApp(button.dataset.app));
    button.addEventListener("focus", () => renderApp(button.dataset.app));
    button.addEventListener("click", () => openAppWindow(button.dataset.app));
    button.addEventListener("dblclick", () => openAppWindow(button.dataset.app));
    button.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        openAppWindow(button.dataset.app);
      }
    });
  });
}

function setupAppWindow() {
  const panel = $("#app-window");
  $("#window-close")?.addEventListener("click", closeAppWindow);
  panel?.addEventListener("click", (event) => {
    if (event.target === panel) closeAppWindow();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const onboarding = $("#onboarding-screen");
    if (onboarding && !onboarding.hidden) {
      closeOnboarding(false);
      return;
    }
    if (panel && !panel.hidden) {
      closeAppWindow();
      return;
    }
    const commandPanel = $("#command-panel");
    const commandToggle = $("#command-toggle");
    if (commandPanel && !commandPanel.hidden) {
      commandPanel.hidden = true;
      commandToggle?.setAttribute("aria-expanded", "false");
    }
  });
}

function setupOnboarding() {
  const panel = $("#onboarding-screen");
  const shouldShow = localStorage.getItem(onboardingStorageKey) !== "true";
  if (panel) panel.hidden = !shouldShow;
  $("#onboarding-open")?.addEventListener("click", openOnboarding);
  $("#onboarding-start")?.addEventListener("click", () => closeOnboarding(true));
  $("#onboarding-skip")?.addEventListener("click", () => closeOnboarding(false));
}

function setupCommandPanel() {
  const panel = $("#command-panel");
  const toggle = $("#command-toggle");
  const close = $("#command-close");
  const note = $("#command-mode-note");
  const setOpen = (open) => {
    if (!panel || !toggle) return;
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
  };
  toggle?.addEventListener("click", () => setOpen(panel?.hidden ?? true));
  close?.addEventListener("click", () => setOpen(false));
  $$(".mode-switch button").forEach((button) => {
    button.addEventListener("click", () => {
      commandMode = button.dataset.mode || "mission";
      $$(".mode-switch button").forEach((item) => item.classList.toggle("is-active", item === button));
      if (note) {
        note.textContent = commandMode === "terminal"
          ? "Terminal Pro is conservative in this phase: it suggests KnowledgeOS commands and dry-runs only."
          : "Natural language is routed through a read-only mock sandbox. Nothing is executed.";
      }
    });
  });
}

async function boot() {
  setupTheme();
  setupLaunchpad();
  setupAppWindow();
  setupOnboarding();
  setupCommandPanel();
  $("#ask-sandbox")?.addEventListener("click", askSandbox);
  const state = await loadState();
  const taskId = state.system_black_box?.latest_run?.task_id || state.tasks?.current?.id;
  const lifecycle = await loadLifecycle(taskId, state);
  render(state, lifecycle);
}

boot();
