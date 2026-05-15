const fallbackState = {
  schema_version: "knowledgeos.workbench-state.v1",
  project_root: "<PROJECT_ROOT>",
  project_name: "KnowledgeOS",
  managed: true,
  status: "managed_ok",
  boot: { claim: "BOOT_OK", doctor: "ok" },
  workspace: { name: "KnowledgeOS Local Build", root: "<PROJECT_ROOT>", phase: "workbench-product-shell" },
  project: { id: "KOS001", name: "KnowledgeOS", current_phase: "product-shell" },
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
      { id: "mock", label: "Mock Runtime", status: "available", execution_mode: "disabled_by_default" },
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
    detail: "Workbench shows the command chain first; no mutation is executed from this app."
  },
  stages: [
    { key: "doctor", label: "Doctor", status: "ok", detail: "Workspace health is readable." },
    { key: "route", label: "Route", status: "ok", detail: "Task has a workflow route." },
    { key: "dispatch", label: "Dispatch", status: "ok", detail: "Capability order is known." },
    { key: "write_guard", label: "Write Guard", status: "active", detail: "Planned outputs must stay inside allowed paths." },
    { key: "run", label: "Run", status: "pending", detail: "No real execution from Workbench." },
    { key: "eval", label: "Eval", status: "pending", detail: "Verification evidence has not been written." },
    { key: "receipt", label: "Receipt", status: "pending", detail: "Completion receipt is pending." }
  ]
};

let currentState = fallbackState;
let currentLifecycle = fallbackLifecycle;
let activeApp = "mission";
let workspaceRegistry = { selected: "fixture", workspaces: [] };
const onboardingStorageKey = "knowledgeos-onboarding-complete";
const productInfo = {
  name: "KnowledgeOS Workbench",
  version: "0.1.1",
  boundary: "Monitoring and viewing only",
  kernel: "bundled",
  bridge: "local 127.0.0.1"
};
const workbenchApi = window.knowledgeosWorkbench || null;

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
      // Static fixture mode falls back from live endpoints to local JSON.
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

function fallbackWorkspaceRegistry(state = currentState) {
  const name = state.project?.name || state.project_name || "KnowledgeOS";
  return {
    selected: "fixture",
    workspaces: [
      {
        id: "fixture",
        name,
        root: state.workspace?.root || state.project_root || "<PROJECT_ROOT>",
        status: state.managed ? "managed_ok" : "unmanaged",
        boot: state.boot?.claim || "BOOT_OK",
        checks: state.system_black_box?.doctor?.checks || 0,
        failed: state.system_black_box?.doctor?.failed || 0,
        detail: workbenchApi ? "Live workspace registry." : "Static preview uses a fixture workspace.",
        selected: true
      }
    ]
  };
}

async function loadWorkspaces() {
  if (!workbenchApi) {
    workspaceRegistry = fallbackWorkspaceRegistry(currentState);
    renderWorkspaces();
    return workspaceRegistry;
  }
  try {
    workspaceRegistry = await workbenchApi.getWorkspaces();
  } catch (error) {
    workspaceRegistry = fallbackWorkspaceRegistry(currentState);
  }
  renderWorkspaces();
  return workspaceRegistry;
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
      ["Mission Control", shortTitle(task.title || "No task selected"), task.id ? `${task.id} · ${task.status || "unknown"}` : "Task pending"],
      ["Receipt", run.run_id || state.boot?.claim || "No receipt", run.task_id || "Run evidence stays in OS."],
      ["Health", doctor.status === "ok" ? "Healthy" : "Needs review", `${doctor.passed || 0}/${doctor.checks || 0} project checks · ${doctor.failed || 0} failed`]
    ],
    context: [
      ["Workspace", state.workspace?.name || "Local workspace", state.workspace?.phase || "workbench-product-shell"],
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
      ["Now", activeStage, lifecycle.next_action?.detail || "Read-only shell"],
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
      ["Product", productInfo.name, productInfo.boundary],
      ["Kernel", "Bundled", `v${productInfo.version}`],
      ["Runtime", `${runtime.status || "unknown"} · ${runtime.available_count || 0}/${runtime.total || 0}`, runtime.policy?.real_cli_execution || "disabled"],
      ["Bridge", productInfo.bridge, state.capabilities?.ok ? "Read-only" : "Review"]
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

function selectedWorkspace() {
  return (workspaceRegistry.workspaces || []).find((workspace) => workspace.selected || workspace.id === workspaceRegistry.selected)
    || fallbackWorkspaceRegistry(currentState).workspaces[0];
}

function workspaceStatusLabel(workspace) {
  if (workspace.boot === "BOOT_OK") return "BOOT_OK";
  if (workspace.boot === "KOS_UNMANAGED") return "KOS_UNMANAGED";
  if (workspace.boot === "KOS_UNSAFE") return "blocked";
  return workspace.boot || workspace.status || "unknown";
}

function renderWorkspaces() {
  const selected = selectedWorkspace();
  setText("#workspace-current", selected.name || "Workspace");
  const list = $("#workspace-list");
  if (!list) return;
  const workspaces = workspaceRegistry.workspaces?.length ? workspaceRegistry.workspaces : fallbackWorkspaceRegistry(currentState).workspaces;
  list.innerHTML = workspaces.map((workspace) => {
    const isSelected = workspace.selected || workspace.id === workspaceRegistry.selected;
    return `
      <article class="workspace-row ${isSelected ? "is-selected" : ""} ${escapeHtml(workspace.status || "")}">
        <div>
          <strong>${escapeHtml(workspace.name || "Workspace")}</strong>
          <small>${escapeHtml(workspace.root || "<PROJECT_ROOT>")}</small>
          <em>${escapeHtml(workspace.detail || "Local workspace")}</em>
        </div>
        <span>${escapeHtml(workspaceStatusLabel(workspace))}</span>
        <div class="workspace-row-actions">
          <button type="button" data-workspace-action="open" data-workspace-id="${escapeHtml(workspace.id)}" ${isSelected ? "disabled" : ""}>Open</button>
          <button type="button" data-workspace-action="doctor" data-workspace-id="${escapeHtml(workspace.id)}">Doctor</button>
          <button type="button" data-workspace-action="remove" data-workspace-id="${escapeHtml(workspace.id)}" ${workspaces.length <= 1 ? "disabled" : ""}>Remove</button>
        </div>
      </article>
    `;
  }).join("");
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
  return $(`.app-icon[data-app="${appKey}"] strong`)?.textContent || "Mission Control";
}

function appWindowIntro(appKey) {
  const intros = {
    mission: "Mission Control shows the next gate, evidence chain, and receipt status.",
    context: "Project state is readable here without exposing noisy control-plane files on the desktop.",
    evidence: "Receipts, evals, and doctor results remain visible as proof, not decoration.",
    runs: "Lifecycle stages show where the task is now and what still needs evidence.",
    knowledge: "Readable cards summarize the knowledge layer while raw logs stay inside KnowledgeOS.",
    settings: "About this Workbench: local version, runtime readiness, and read-only safety defaults."
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

function artifactRows(rows) {
  return `
    <div class="artifact-list">
      ${rows.map((row) => `
        <article class="artifact-row ${escapeHtml(row.status || "")}">
          <span>${escapeHtml(row.marker || row.label || "")}</span>
          <strong>${escapeHtml(row.title || row.value || "")}</strong>
          <code>${escapeHtml(row.file || row.detail || "")}</code>
        </article>
      `).join("")}
    </div>
  `;
}

function detailsSection(title, body, label, intro = "") {
  return `
    <details class="details-panel">
      <summary>
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(label || "Open supporting files")}</span>
      </summary>
      <div class="details-body">
        ${intro ? `<p class="details-intro">${escapeHtml(intro)}</p>` : ""}
        ${body}
      </div>
    </details>
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

function phaseRail(lifecycle) {
  const stages = lifecycle.stages || [];
  if (!stages.length) return "";
  return `
    <ol class="phase-rail" aria-label="Command chain">
      ${stages.map((stage) => `
        <li>
          <span class="stage-dot ${escapeHtml(stage.status || "pending")}"></span>
          <strong>${escapeHtml(stage.label || stage.key)}</strong>
          <small>${escapeHtml(stage.status || "pending")}</small>
        </li>
      `).join("")}
    </ol>
  `;
}

function lifecycleStageMap(lifecycle) {
  return Object.fromEntries((lifecycle.stages || []).map((stage) => [stage.key, stage]));
}

function statusForStage(stage, fallback = "pending") {
  if (!stage) return fallback;
  if (["ok", "passed", "completed", "ready"].includes(stage.status)) return "passed";
  if (["active", "in_progress", "attention"].includes(stage.status)) return "running";
  if (["blocked", "fail", "failed"].includes(stage.status)) return "blocked";
  return stage.status || fallback;
}

function missionControlTimeline(state, lifecycle) {
  const stages = lifecycleStageMap(lifecycle);
  const task = lifecycle.selected_task || state.tasks?.current || {};
  const receiptStatus = statusForStage(stages.receipt);
  const runStatus = statusForStage(stages.run);
  const evalStatus = statusForStage(stages.eval);
  const managedStatus = state.managed ? "passed" : "blocked";
  const taskStatus = task.id ? "passed" : "pending";
  const syncStatus = receiptStatus === "passed" ? "passed" : "pending";
  const nodes = [
    ["User Intent", managedStatus, "TRACE_OK", "step-events.ndjson"],
    ["Load Rules", managedStatus, "TRACE_OK", "AGENTS.md + .agent-os"],
    ["Doctor Gate", statusForStage(stages.doctor), "TRACE_OK", "doctor --summary"],
    ["Task Intake", taskStatus, "TRACE_OK", task.id || "waiting"],
    ["Spec Alignment", taskStatus, "TRACE_OK", "spec-snapshot.md"],
    ["Route Guard", statusForStage(stages.route), "TRACE_OK", "route-task"],
    ["Dispatch Plan", statusForStage(stages.dispatch), "TRACE_OK", "dispatch-task"],
    ["Write Guard", statusForStage(stages.write_guard), "TRACE_OK", "check-route-write"],
    ["Run Envelope", runStatus, "TRACE_OK", "run-task"],
    ["Context Pack", runStatus, "TRACE_OK", "context-pack.md"],
    ["Plan Task", runStatus, "TRACE_OK", "plan.md"],
    ["Execution", runStatus, "TRACE_OK", "project changes"],
    ["Capability Visibility", state.capabilities?.ok ? "passed" : "pending", "CAPABILITY_OK", "capability-events.ndjson"],
    ["Phase Checkpoints", receiptStatus === "passed" ? "passed" : statusForStage(stages.dispatch), "CHECKPOINT_OK", "phases.ndjson"],
    ["Eval", evalStatus, "TRACE_OK", "eval-task"],
    ["Verify", evalStatus === "passed" ? "passed" : "pending", "TRACE_OK", "verify-context + verify-lifecycle"],
    ["Sync", syncStatus, syncStatus === "passed" ? "SYNC_OK" : "[SYNC_OK]", "postflight.md"]
  ];
  return `
    <ol class="mission-timeline" aria-label="Agent Mission Control timeline">
      ${nodes.map(([label, status, marker, evidence], index) => `
        <li class="${escapeHtml(status)}">
          <span class="timeline-index">${index + 1}</span>
          <strong>${escapeHtml(label)}</strong>
          <small>${escapeHtml(marker)}</small>
          <em>${escapeHtml(evidence)}</em>
        </li>
      `).join("")}
    </ol>
  `;
}

function evidenceLanes(state, lifecycle) {
  const laneData = evidenceLaneData(state, lifecycle);
  return `
    <div class="evidence-lanes" aria-label="Evidence lanes">
      ${laneData.map(({ title, marker, file, detail, status }) => `
        <article class="${escapeHtml(status)}">
          <span>${escapeHtml(marker)}</span>
          <strong>${escapeHtml(title)}</strong>
          <code>${escapeHtml(file)}</code>
          <small>${escapeHtml(detail)}</small>
        </article>
      `).join("")}
    </div>
  `;
}

function evidenceLaneData(state, lifecycle) {
  const stages = lifecycleStageMap(lifecycle);
  const latest = latestRun(state);
  const receiptPassed = statusForStage(stages.receipt) === "passed";
  return [
    { key: "trace", label: "Trace", title: "Public Operational Trace", marker: "TRACE_OK", file: "step-events.ndjson", detail: "User-visible steps from intent to sync.", status: "passed" },
    { key: "checkpoint", label: "Checkpoints", title: "Lifecycle Checkpoints", marker: "CHECKPOINT_OK", file: "phases.ndjson", detail: "Six phase gates: route, plan, review, dispatch, execute, report.", status: statusForStage(stages.dispatch) },
    { key: "capability", label: "Capabilities", title: "Capability Visibility", marker: "CAPABILITY_OK", file: "capability-events.ndjson", detail: "MCP, skill, subagent, script, shell, and file-read visibility.", status: state.capabilities?.ok ? "passed" : "pending" },
    { key: "sync", label: "Sync", title: "Completion And Sync", marker: "[SYNC_OK]", file: "postflight.md", detail: latest.run_id || receiptPassed ? "Completion evidence remains in the OS run folder." : "Waiting for complete-task.", status: receiptPassed ? "passed" : "pending" }
  ];
}

function missionEvidenceChain(state, lifecycle) {
  return `
    <ol class="evidence-chain" aria-label="Mission evidence chain">
      ${evidenceLaneData(state, lifecycle).map(({ label, marker, file, status }, index) => `
        <li class="${escapeHtml(status)}">
          <span>${index + 1}</span>
          <strong>${escapeHtml(label)}</strong>
          <small>${escapeHtml(marker)}</small>
          <code>${escapeHtml(file)}</code>
        </li>
      `).join("")}
    </ol>
  `;
}

function missionOverview(state, lifecycle) {
  const stages = lifecycle.stages || [];
  const task = lifecycle.selected_task || state.tasks?.current || {};
  const blocked = stages.find((stage) => statusForStage(stage) === "blocked");
  const active = stages.find((stage) => ["active", "in_progress", "attention"].includes(stage.status));
  const pending = stages.find((stage) => statusForStage(stage) === "pending");
  const gate = blocked || active || pending || stages.at(-1);
  if (blocked) {
    return {
      label: "Blocked",
      tone: "blocked",
      gate: blocked.label || blocked.key || "Unknown gate"
    };
  }
  if (active || pending) {
    return {
      label: "Needs Review",
      tone: "attention",
      gate: gate?.label || gate?.key || "Review route"
    };
  }
  return {
    label: "On Track",
    tone: "passed",
    gate: gate?.label || "Sync"
  };
}

function keyValueRows(rows) {
  return rows.map(([label, value]) => `
    <div class="kv-row">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `).join("");
}

function missionAppContent(state, lifecycle) {
  const task = lifecycle.selected_task || state.tasks?.current || {};
  const next = lifecycle.next_action || {};
  const overview = missionOverview(state, lifecycle);
  return `
    <div class="app-workspace mission-workspace mission-control-workspace">
      <section class="focus-panel mission-top-panel current-gate-panel">
        <p class="eyebrow">Current Gate</p>
        <span class="status-pill ${escapeHtml(overview.tone)}">${escapeHtml(overview.label)}</span>
        ${keyValueRows([
          ["Gate", overview.gate],
          ["Task", task.id || "None"],
          ["Status", task.status || "unknown"],
          ["Risk", task.risk || "low"]
        ])}
      </section>
      <section class="focus-panel mission-top-panel next-move-panel">
        <p class="eyebrow">Next Move</p>
        <h3>${escapeHtml(next.label || "Review route")}</h3>
        <p>${escapeHtml(next.detail || "Select a task, inspect route, then decide whether to proceed.")}</p>
        <div class="panel-actions">
          <button type="button" data-open-app="context">Open context</button>
          <button type="button" data-open-app="evidence">Inspect evidence</button>
          <button type="button" data-open-app="runs">Open runs</button>
        </div>
      </section>
      <section class="focus-panel wide-panel mission-evidence-panel">
        <p class="eyebrow">Evidence Chain</p>
        ${missionEvidenceChain(state, lifecycle)}
      </section>
      <details class="focus-panel wide-panel flight-recorder">
        <summary>
          <strong>Audit Trail</strong>
          <span>Timeline nodes and evidence lanes behind the current gate.</span>
        </summary>
        <div class="flight-recorder-body">
          <p class="details-intro">Use this only when you want to see exactly which OS checkpoints and evidence files support the current Mission Control status.</p>
          <section>
            <p class="eyebrow">Timeline Detail</p>
            ${missionControlTimeline(state, lifecycle)}
          </section>
          <section>
            <p class="eyebrow">Evidence Lane Detail</p>
            ${evidenceLanes(state, lifecycle)}
          </section>
        </div>
      </details>
    </div>
  `;
}

function contextAppContent(state, lifecycle) {
  const runtime = state.runtime_adapters || {};
  const caps = state.capabilities?.counts || {};
  const routes = state.routes?.task_types || [];
  return `
    <div class="app-workspace secondary-app-workspace context-workspace">
      <section class="focus-panel lead-panel primary-panel">
        <p class="eyebrow">Project State Map</p>
        <h3>${escapeHtml(state.project?.name || state.project_name || "KnowledgeOS")}</h3>
        ${keyValueRows([
          ["Workspace", state.workspace?.name || "Local workspace"],
          ["Root", state.workspace?.root || state.project_root || "<PROJECT_ROOT>"],
          ["Phase", state.workspace?.phase || state.project?.current_phase || "product-shell"],
          ["Boot", state.boot?.claim || state.status || "unknown"]
        ])}
      </section>
      <section class="focus-panel">
        <p class="eyebrow">State Surfaces</p>
        <div class="support-grid">
          ${windowCard("Current Task", lifecycle.selected_task?.id || state.tasks?.current?.id || "None", lifecycle.selected_task?.title || state.tasks?.current?.title || "No task selected")}
          ${windowCard("Route Profiles", `${state.routes?.count || routes.length || 0}`, routes.slice(0, 4).join(" · ") || "No route profiles loaded")}
          ${windowCard("Runtime Policy", runtime.policy?.real_cli_execution || "disabled", `${runtime.available_count || 0}/${runtime.total || 0} adapters ready`)}
          ${windowCard("Capability Index", `${capabilityCount(state)} entries`, Object.entries(caps).map(([key, value]) => `${key}:${value}`).join(" · ") || "No capability entries")}
        </div>
      </section>
      ${detailsSection("Control Files", artifactRows([
        { marker: "workspace", title: "workspace.yaml", file: ".agent-os/workspace.yaml", status: "passed" },
        { marker: "project", title: "project.yaml", file: ".agent-os/project.yaml", status: "passed" },
        { marker: "routes", title: "router.yaml", file: ".agent-os/workflows/router.yaml", status: "passed" },
        { marker: "tools", title: "tool-registry.yaml", file: ".agent-os/tool-registry.yaml", status: state.capabilities?.ok ? "passed" : "pending" }
      ]), "The files that define this project map.", "These are the control-plane sources behind the cards above: workspace identity, project metadata, route profiles, and capability registry.")}
    </div>
  `;
}

function evidenceAppContent(state, lifecycle) {
  const doctor = state.system_black_box?.doctor || {};
  const run = latestRun(state);
  const lanes = evidenceLaneData(state, lifecycle);
  return `
    <div class="app-workspace secondary-app-workspace evidence-workspace">
      <section class="focus-panel lead-panel primary-panel">
        <p class="eyebrow">Evidence Lanes</p>
        ${artifactRows(lanes.map((lane) => ({
          marker: lane.marker,
          title: lane.title,
          file: lane.file,
          status: lane.status
        })))}
      </section>
      <section class="focus-panel">
        <p class="eyebrow">Proof Status</p>
        <div class="support-grid">
          ${windowCard("Doctor", doctor.status || "not_run", `${doctor.failed || 0} failed checks`)}
          ${windowCard("Eval", run.eval_passed ? "Passed" : "Pending", run.eval_profile || "Generated eval required")}
          ${windowCard("Sync", run.receipt_exists === false ? "Missing" : "Tracked", "complete-task must produce postflight.md")}
        </div>
      </section>
      ${detailsSection("Evidence Files", evidenceLanes(state, lifecycle), "The four proof lanes written by the OS.", "This section points to the concrete marker files used to prove traceability: public trace, lifecycle checkpoints, capability visibility, and final sync.")}
    </div>
  `;
}

function runsAppContent(state, lifecycle) {
  const task = lifecycle.selected_task || state.tasks?.current || {};
  const run = latestRun(state);
  const summary = stageSummary(lifecycle);
  return `
    <div class="app-workspace secondary-app-workspace runs-workspace">
      <section class="focus-panel lead-panel primary-panel runs-summary-panel">
        <p class="eyebrow">Run Timeline</p>
        <h3>${escapeHtml(run.run_id || "No run selected")}</h3>
        ${keyValueRows([
          ["Task", run.task_id || task.id || "None"],
          ["Status", run.status || task.status || "unknown"],
          ["Stages", `${summary.complete}/${summary.total}`],
          ["Now", summary.active?.label || lifecycle.next_action?.label || "Ready"]
        ])}
      </section>
      <section class="focus-panel runs-chain-panel wide-panel">
        <p class="eyebrow">Checkpoint Chain</p>
        ${phaseRail(lifecycle)}
      </section>
      ${detailsSection("Run Artifacts", `
        ${lifecycleRows(lifecycle)}
        ${artifactRows([
          { marker: "run", title: "run.yaml", file: ".agent-os/runs/<RUN_ID>/run.yaml", status: run.run_id ? "passed" : "pending" },
          { marker: "eval", title: "eval.md", file: ".agent-os/runs/<RUN_ID>/eval.md", status: run.eval_passed ? "passed" : "pending" },
          { marker: "receipt", title: "receipt.md", file: ".agent-os/runs/<RUN_ID>/receipt.md", status: run.receipt_exists === false ? "pending" : "passed" },
          { marker: "sync", title: "postflight.md", file: ".agent-os/runs/<RUN_ID>/postflight.md", status: statusForStage(lifecycleStageMap(lifecycle).receipt) }
        ])}
      `, "Command chain, eval, receipt, and postflight.", "These are the per-run files generated inside .agent-os/runs/<RUN_ID>/ so you can audit how the current execution moved from envelope to completion.")}
    </div>
  `;
}

function knowledgeAppContent(state, lifecycle) {
  const task = lifecycle.selected_task || state.tasks?.current || {};
  return `
    <div class="app-workspace secondary-app-workspace knowledge-workspace">
      <section class="focus-panel lead-panel primary-panel">
        <p class="eyebrow">Knowledge Index</p>
        ${keyValueRows([
          ["Docs", "docs/"],
          ["Decisions", ".agent-os/decisions.yaml"],
          ["Handoffs", ".agent-os/handoffs/current.md"],
          ["Skills", "capability-layer/skills/"]
        ])}
      </section>
      <section class="focus-panel">
        <p class="eyebrow">Knowledge Entrypoints</p>
        <div class="support-grid">
          ${windowCard("Docs", "docs/", "Project-facing documents")}
          ${windowCard("Decisions", "decisions.yaml", "Recorded choices")}
          ${windowCard("Handoffs", "current.md", "Next-agent context")}
          ${windowCard("Skills", "skills/", "Reusable methods")}
        </div>
      </section>
      ${detailsSection("Knowledge Sources", artifactRows([
        { marker: "task", title: task.id || "Current task", file: task.title || "No active task", status: task.id ? "passed" : "pending" },
        { marker: "docs", title: "Workbench docs", file: "examples/workbench/README.md", status: "passed" },
        { marker: "memory", title: "Decision lane", file: ".agent-os/decisions.yaml", status: "passed" },
        { marker: "handoff", title: "Handoff lane", file: ".agent-os/handoffs/current.md", status: "passed" }
      ]), "Open source files for docs, decisions, handoffs, and reusable methods.", "These are the human-readable files that explain project memory and handoff context without repeating Evidence or Runs.")}
    </div>
  `;
}

function settingsAppContent(state, lifecycle) {
  const runtime = state.runtime_adapters || {};
  const adapters = runtime.adapters || [];
  return `
    <div class="app-workspace secondary-app-workspace settings-workspace">
      <section class="focus-panel lead-panel primary-panel">
        <p class="eyebrow">Safety Boundary</p>
        ${keyValueRows([
          ["Project mutation", runtime.policy?.project_mutation_allowed ? "enabled" : "disabled"],
          ["Model access", "not exposed"],
          ["Context", "state view only"],
          ["Kernel", productInfo.kernel],
          ["Bridge", productInfo.bridge]
        ])}
      </section>
      <section class="focus-panel">
        <p class="eyebrow">Runtime Adapters</p>
        <div class="support-grid">
          ${windowCard("Kernel", productInfo.kernel, "Ships with the app")}
          ${windowCard("Default", runtime.policy?.default_runtime || "mock", productInfo.name)}
          ${windowCard("Available", `${runtime.available_count || 0}/${runtime.total || 0}`, runtime.status || "unknown")}
          ${windowCard("Execution", runtime.policy?.real_cli_execution || "disabled", "Adapter gated")}
          ${windowCard("Mutation", runtime.policy?.project_mutation_allowed ? "allowed" : "disabled", "Route-bound")}
        </div>
      </section>
      ${detailsSection("Adapter Inventory", artifactRows(adapters.map((adapter) => ({
        marker: adapter.id || "adapter",
        title: adapter.label || adapter.id || "Runtime adapter",
        file: `${adapter.status || "unknown"} · ${adapter.execution_mode || "not configured"}`,
        status: adapter.status === "available" ? "passed" : "pending"
      }))), "Detected local adapters and their execution mode.", "This is a local runtime inventory only. It does not grant project mutation or replace KnowledgeOS route, write guard, eval, and receipt.")}
    </div>
  `;
}

function appWindowContent(appKey, state, lifecycle) {
  if (appKey === "mission") return missionAppContent(state, lifecycle);
  if (appKey === "context") return contextAppContent(state, lifecycle);
  if (appKey === "evidence") return evidenceAppContent(state, lifecycle);
  if (appKey === "runs") return runsAppContent(state, lifecycle);
  if (appKey === "knowledge") return knowledgeAppContent(state, lifecycle);
  if (appKey === "settings") return settingsAppContent(state, lifecycle);
  const task = lifecycle.selected_task || state.tasks?.current || {};
  const nextAction = lifecycle.next_action?.label || "Review route";
  const nextHint = appKey === "mission"
    ? "Open Mission Control to inspect the current gate, evidence chain, and receipt status."
    : `Recommended next check: ${nextAction}.`;
  return `
    <div class="window-note">
      <strong>${escapeHtml(task.id || "No active task")}</strong>
      <span>${escapeHtml(nextHint)}</span>
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
  renderWorkspaces();
}

function setWorkspacePanelOpen(open) {
  const panel = $("#workspace-panel");
  const toggle = $("#workspace-toggle");
  if (!panel || !toggle) return;
  panel.hidden = !open;
  toggle.setAttribute("aria-expanded", String(open));
}

async function refreshAfterWorkspaceSwitch() {
  const state = await loadState();
  const taskId = state.system_black_box?.latest_run?.task_id || state.tasks?.current?.id;
  const lifecycle = await loadLifecycle(taskId, state);
  render(state, lifecycle);
  await loadWorkspaces();
}

async function handleWorkspaceAction(target) {
  const action = target.dataset.workspaceAction;
  const id = target.dataset.workspaceId;
  if (!workbenchApi || !action || !id) return;
  target.disabled = true;
  try {
    if (action === "open") {
      await workbenchApi.selectWorkspace(id);
      setWorkspacePanelOpen(false);
      await refreshAfterWorkspaceSwitch();
      return;
    }
    if (action === "doctor") {
      await workbenchApi.runDoctor(id);
      await loadWorkspaces();
      return;
    }
    if (action === "remove") {
      await workbenchApi.removeWorkspace(id);
      await loadWorkspaces();
    }
  } catch (error) {
    renderWorkspaceError(error);
  } finally {
    target.disabled = false;
  }
}

function renderWorkspaceError(error) {
  const list = $("#workspace-list");
  if (!list) return;
  list.insertAdjacentHTML("afterbegin", `
    <article class="workspace-row blocked_root">
      <div>
        <strong>Workspace action failed</strong>
        <small>${escapeHtml(error?.message || error || "Unknown workspace error")}</small>
        <em>No project files were modified.</em>
      </div>
      <span>blocked</span>
    </article>
  `);
}

async function setupWorkspaceSwitcher() {
  $("#workspace-toggle")?.addEventListener("click", async () => {
    await loadWorkspaces();
    setWorkspacePanelOpen($("#workspace-panel")?.hidden ?? true);
  });
  $("#workspace-close")?.addEventListener("click", () => setWorkspacePanelOpen(false));
  $("#workspace-add")?.addEventListener("click", async () => {
    if (!workbenchApi) {
      renderWorkspaceError("Folder picker is available only in the Electron app.");
      return;
    }
    await workbenchApi.addWorkspace();
    await loadWorkspaces();
  });
  $("#workspace-list")?.addEventListener("click", (event) => {
    const target = event.target.closest?.("[data-workspace-action]");
    if (target) void handleWorkspaceAction(target);
  });
  await loadWorkspaces();
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
    const appTarget = event.target.closest?.("[data-open-app]");
    if (appTarget) {
      openAppWindow(appTarget.dataset.openApp);
    }
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
    const workspacePanel = $("#workspace-panel");
    if (workspacePanel && !workspacePanel.hidden) {
      setWorkspacePanelOpen(false);
      return;
    }
  });
}

function setupOnboarding() {
  const panel = $("#onboarding-screen");
  const shouldShow = localStorage.getItem(onboardingStorageKey) !== "true";
  if (panel) panel.hidden = !shouldShow;
  $("#about-open")?.addEventListener("click", () => openAppWindow("settings"));
  $("#onboarding-open")?.addEventListener("click", openOnboarding);
  $("#onboarding-start")?.addEventListener("click", () => closeOnboarding(true));
  $("#onboarding-skip")?.addEventListener("click", () => closeOnboarding(false));
}

async function boot() {
  setupTheme();
  setupLaunchpad();
  setupAppWindow();
  setupOnboarding();
  const state = await loadState();
  const taskId = state.system_black_box?.latest_run?.task_id || state.tasks?.current?.id;
  const lifecycle = await loadLifecycle(taskId, state);
  render(state, lifecycle);
  await setupWorkspaceSwitcher();
}

boot();
