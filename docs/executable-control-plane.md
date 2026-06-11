# Executable Control Plane

This layer turns KnowledgeOS from a static architecture into a minimal executable control plane.

## CLI Entry Point

```bash
./bin/knowledgeos --help
```

The current implementation is intentionally dependency-light and uses only the Python standard library.

## Commands

### `init-os`

Create a minimal KnowledgeOS runtime root with a governance kernel and capability layer.

```bash
./bin/knowledgeos init-os --os-root /path/to/KnowledgeOSRuntime
```

This writes:

```text
/path/to/KnowledgeOSRuntime/
  global-agent-fabric/
  capability-layer/
```

The generated kernel is intentionally small: rules, hooks, registry examples, schemas, and empty ledgers. It does not include project wiki content, private chat logs, large skill libraries, or secrets.

### `doctor`

Validate the KnowledgeOS distribution and, optionally, a project control plane.

```bash
./bin/knowledgeos doctor --root /path/to/KnowledgeOS
```

For a project:

```bash
./bin/knowledgeos doctor --project-root /path/to/project
```

For distribution plus project in one check:

```bash
./bin/knowledgeos doctor \
  --root /path/to/KnowledgeOS \
  --project-root /path/to/project
```

Checks include:

- required public docs and templates;
- public leakage markers;
- required project `.agent-os` files;
- unresolved placeholders;
- kernel/body links;
- phase keys;
- phase policy;
- write-policy coverage;
- capability guardrails;
- workflow route coverage;
- lifecycle consistency for `run-task -> context-pack -> plan-task -> phase-task -> eval-task -> verify-context -> verify-lifecycle -> verify-effects -> complete-task`;
- decision policy validation when `.agent-os/decision-policy.yaml` is present.

### `init-project`

Copy the project control-plane template into a workspace.

```bash
./bin/knowledgeos init-project \
  --project-root /path/to/project \
  --name "My Project" \
  --global-root /path/to/global-agent-fabric \
  --capability-root /path/to/capability-layer
```

Default behavior is safe:

- existing files are skipped;
- existing `AGENTS.md` is not overwritten;
- `--force` is required to overwrite;
- `--force` creates backups first.

### `route-task`

Resolve a task id or task type into an observable workflow route.

```bash
./bin/knowledgeos route-task \
  --project-root /path/to/project \
  --task-id T001
```

Unrouted task types fail with `human_triage_required` so agents do not invent silent process flows.

### `create-task`

Append a new task when the user asks for new work and no existing ready task fits.

```bash
./bin/knowledgeos create-task \
  --project-root /path/to/project \
  --title "Fix migrated dashboard model alignment" \
  --type route_bound_execution_guard \
  --output knowledgeos/cli.py \
  --acceptance "doctor and tests pass"
```

`create-task` assigns the next id automatically (`T001 -> T002`, `KOS-T022 -> KOS-T023`). Unknown task types are allowed at intake time, but `route-task` will still return `human_triage_required` until a router profile exists.

### `create-spec`

Create a durable spec contract when the user says "create spec", "对齐 spec", or asks the agent to preserve a long-running intent.

```bash
./bin/knowledgeos create-spec \
  --project-root /path/to/project \
  --title "Grant proposal writing spec" \
  --intent "Keep the proposal logic, non-goals, and acceptance criteria visible." \
  --acceptance "run context includes the active spec snapshot"
```

This writes:

```text
.agent-os/specs.yaml
.agent-os/specs/SPEC-YYYYMMDD-001/
  spec.md
  acceptance.md
  non-goals.md
  alignment.md
  change-log.ndjson
```

### `align-spec`

Align the active or selected spec with the current task before execution.

```bash
./bin/knowledgeos align-spec \
  --project-root /path/to/project \
  --task-id T001
```

The command writes `alignment.md` and returns `aligned` or `needs_review`. Agents should stop for human triage when alignment needs review.

### `thread-plan`

Manage a chat-level, append-only natural-language plan. Use this when a conversation starts a durable plan/spec or when later rounds should build on an earlier planning path.

```bash
./bin/knowledgeos thread-plan start \
  --project-root /path/to/project \
  --title "长期维护鸟类声景基金申请计划" \
  --spec-id SPEC-...
```

Append progress, branch, phase, decision, change, or summary notes:

```bash
./bin/knowledgeos thread-plan append \
  --project-root /path/to/project \
  --thread-id THREAD-... \
  --kind phase \
  --text "Phase A：把聊天级计划记录清楚；Phase B：再把多个任务串起来。"
```

Link a run back to the long-lived conversation:

```bash
./bin/knowledgeos thread-plan link-run \
  --project-root /path/to/project \
  --thread-id THREAD-... \
  --task-id T001 \
  --run-id RUN-...
```

Render the plan as Markdown, Mermaid, or HTML:

```bash
./bin/knowledgeos thread-plan render \
  --project-root /path/to/project \
  --thread-id THREAD-... \
  --format html
```

Successful output begins with `THREAD_PLAN_OK`. This module does not gate completion. It is a readable planning map across a chat window, while `plan-task` remains the run-level execution plan.

### `check-write`

Classify a planned write against `.agent-os/write-policy.yaml`.

```bash
./bin/knowledgeos check-write \
  --project-root /path/to/project \
  --path src/main.py
```

Possible decisions:

- `allow`
- `deny`
- `human_gate_required`
- `unclassified`

Use `--strict` to treat unclassified paths as failures.

### `run-task`

Create a run envelope for a task in `.agent-os/tasks.yaml`.

```bash
./bin/knowledgeos run-task \
  --project-root /path/to/project \
  --task-id T001 \
  --summary "Start task."
```

Generated files:

```text
.agent-os/runs/RUN-*/
  run.yaml
  command-events.ndjson
  prompt.md
  receipt.md
  diff_summary.md
  eval.md
  handoff.md
  spec-snapshot.md
  context-pack.md
```

It also updates:

```text
.agent-os/receipts/latest.md
.agent-os/handoffs/current.md
```

### `context-pack`

Write or refresh the run context pack and active spec snapshot.

```bash
./bin/knowledgeos context-pack \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-...
```

`run-task` creates the first context pack automatically, but agents should rerun `context-pack` after spec alignment or before execution if the context changed.

### `plan-task`

Write the public execution plan after the context pack exists.

```bash
./bin/knowledgeos plan-task \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --summary "Execute through the routed lifecycle."
```

`complete-task` refuses to close a run without `plan.md` and matching `plan-task` command evidence.

### `eval-task`

Write deterministic evaluation evidence for a run.

```bash
./bin/knowledgeos eval-task \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-...
```

The generated `eval.md` includes `Generated By: knowledgeos eval-task`, `Status: passed` or `Status: failed`, and checks that declared task outputs exist.

`eval-task` also appends command evidence to `command-events.ndjson`. `complete-task` requires that event, so a hand-written `eval.md` marker is not sufficient.

### `verify-context`

Verify that the run has command-generated context, spec snapshot, and plan evidence.

```bash
./bin/knowledgeos verify-context \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-...
```

It fails when:

- `context-pack.md`, `spec-snapshot.md`, or `plan.md` is missing;
- the context or plan lacks the KnowledgeOS generator marker;
- `command-events.ndjson` lacks matching `context-pack` or `plan-task` events;
- the active spec changed after the run snapshot was created.

### `phase-task`

Append public lifecycle evidence to `.agent-os/runs/<RUN_ID>/phases.ndjson`.

```bash
./bin/knowledgeos phase-task \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --phase review \
  --status completed \
  --note "Reproduced the bug with a failing test." \
  --evidence "python3 -B -m unittest ..."
```

This is a public decision trace, not hidden chain-of-thought. If a phase is skipped, `--skip-reason` is required.

Successful plain-text output begins with:

```text
CHECKPOINT_OK phase=<phase> status=<status> evidence=<short evidence>
```

JSON output includes `checkpoint_marker: CHECKPOINT_OK`.

### `trace-step`

Record a public operational trace step without storing hidden chain-of-thought.

```bash
./bin/knowledgeos trace-step \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --step doctor_gate \
  --note "Doctor passed before mutation." \
  --evidence "doctor --summary"
```

The command writes `.agent-os/runs/<RUN_ID>/step-events.ndjson` and matching command evidence. Successful plain-text output begins with:

```text
TRACE_OK step=<step> status=<status> evidence=<short evidence>
```

Use this for user-visible mainline steps such as `user_intent`, `load_rules`, `doctor_gate`, `task_intake`, `route_guard`, `dispatch_plan`, `write_guard`, `execution`, `eval`, `verify`, `complete`, and `sync`.

### `capability-event`

Record an observable capability call without executing it.

```bash
./bin/knowledgeos capability-event \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --kind orchestrator \
  --id maestro \
  --purpose "Coordinate specialist review before execution."
```

Allowed kinds are `app`, `browser`, `chrome`, `file_read`, `github`, `mcp`, `plugin`, `script`, `security`, `shell`, `skill`, `subagent`, and `orchestrator`.

The command writes `.agent-os/runs/<RUN_ID>/capability-events.ndjson` and matching command evidence. Successful plain-text output begins with:

```text
CAPABILITY_OK kind=<kind> id=<capability-id> purpose=<short purpose>
```

JSON output also includes a stable `capability_event_id`. Use that id when an effect assertion proves the real side effect produced by the capability. If `artifact-assert` is called with `--capability-event-id`, the id must already exist in the run's `capability-events.ndjson`; bogus links are rejected.

### `decision-event`

Record a public Decision Graph event when a plan branches, a route is selected, a step is inserted, or a branch is abandoned, rolled back, superseded, deferred, or finalized.

```bash
./bin/knowledgeos decision-event \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --kind branch_selected \
  --status selected \
  --title "Use targeted rerun" \
  --summary "Select the smaller validation path." \
  --reason "It proves the changed artifact without repeating expensive work." \
  --evidence "plan review"
```

The command writes `.agent-os/runs/<RUN_ID>/decision-events.ndjson` and matching command evidence. Plain-text output begins with:

```text
DECISION_OK kind=<kind> status=<status> title=<short title>
```

Use `decision-event` for public decision summaries, not hidden chain-of-thought. Ordinary linear progress should stay in `trace-step`.

### `decision-query`

Query Decision Graph events by run, task, kind, status, or parent id.

```bash
./bin/knowledgeos decision-query \
  --project-root /path/to/project \
  --run-id RUN-... \
  --parent-id DEC-...
```

### `artifact-assert`

Verify a real artifact side effect before recording `EFFECT_OK`.

```bash
./bin/knowledgeos artifact-assert \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --kind file_contains \
  --path docs/report.md \
  --expect "verified result"
```

Supported assertion kinds are `file_exists`, `file_nonempty`, `file_contains`, `file_sha256`, `file_changed`, `json_key_equals`, and `html_self_contained`.

Successful assertions write `.agent-os/runs/<RUN_ID>/effect-assertions.ndjson` and matching command evidence. Plain-text output begins with:

```text
EFFECT_OK kind=<kind> target=<path> evidence=<short evidence>
```

Failed assertions return non-zero and do not write a passing effect record. Assertions that claim a missing capability event id also fail.

### Dispatch Evidence

`dispatch-task` can be run before a run exists to inspect the capability plan. After `run-task`, run it again with `--run-id` to bind that dispatch decision to the run ledger:

```bash
./bin/knowledgeos dispatch-task \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-...
```

### `verify-lifecycle`

Verify that a run has all phases required by `.agent-os/phase-policy.yaml`.

```bash
./bin/knowledgeos verify-lifecycle \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-...
```

Missing phases, invalid phases, and skipped phases without reasons fail with exit code `2`.

`verify-lifecycle` also requires matching `phase-task` command events for each phase. A hand-written `phases.ndjson` is not sufficient.

It also requires run-bound `dispatch-task --run-id` evidence. If the dispatch plan marks a capability stage as required, the run must either record a matching `capability-event` or explain the skipped stage in the dispatch phase public note/evidence.

### `verify-effects`

Verify that declared outputs or other policy-selected artifacts have real effect assertions.

```bash
./bin/knowledgeos verify-effects \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-...
```

The project policy lives in `.agent-os/effect-policy.yaml`. `strictness: warn` records warnings without blocking completion. `strictness: enforce` blocks completion when required effect evidence is missing, forged, or linked to a nonexistent capability event. `strictness: off` requires a `downgrade_reason`.

Plain output includes a visible marker:

```text
EFFECT_VERIFY_OK status=<passed|warning|failed|disabled> strictness=<level> assertions=<n> warnings=<n> errors=<n>
```

JSON output includes `effect_verify_marker: EFFECT_VERIFY_OK` and the full `marker` string. Agents must relay this marker before claiming effect verification success.

### `verify-decisions`

Verify that Decision Graph evidence is command-generated and structurally valid.

```bash
./bin/knowledgeos verify-decisions \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-...
```

The project policy lives in `.agent-os/decision-policy.yaml`. `strictness: warn` is the default and does not block linear work with no decision events. `strictness: enforce` blocks completion when decision evidence is missing, forged, orphaned, or invalid. `strictness: off` requires a `downgrade_reason`.

Plain output includes:

```text
DECISION_VERIFY_OK status=<passed|warning|failed|disabled> strictness=<level> decisions=<n> warnings=<n> errors=<n>
```

### `render-html --kind decision-map`

Render `.agent-os/runs/<RUN_ID>/decision-events.ndjson` into a human-readable static decision map.

```bash
./bin/knowledgeos render-html \
  --project-root /path/to/project \
  --run-id RUN-... \
  --kind decision-map
```

The HTML includes source path, source SHA-256, run id, generated time, and the notice `HTML is presentation, not source of truth.`

### `flow-summary`

Print a friendly, layered Mermaid mission flow for a run. This is designed for human end-of-task reporting, not machine enforcement.

```bash
./bin/knowledgeos flow-summary \
  --project-root /path/to/project \
  --run-id RUN-...
```

Plain output begins with:

```text
FLOW_OK run=<run-id> stages=<n> synced=<yes|no>
```

The diagram uses simple labels: `Goal`, `Health Check`, `Task & Plan`, `Safe Writes`, `Work Done`, `Tools Used`, `Proof`, `Decisions`, and `Finish`. It intentionally avoids exposing internal jargon as the main user-facing surface.

For medium, high, or complex tasks, `complete-task` also writes `.agent-os/runs/<RUN_ID>/mission-flow.md` and returns `flow_marker`, `flow_summary_marker`, and `flow_mermaid` so the agent can include the readable flow in its final answer.

### `render-html --kind mission-flow`

Render `.agent-os/runs/<RUN_ID>/mission-flow.md` into a self-contained HTML sidecar with colored cards and source metadata.

```bash
./bin/knowledgeos render-html \
  --project-root /path/to/project \
  --run-id RUN-... \
  --kind mission-flow
```

The HTML is presentation only. Markdown, YAML, and NDJSON remain the source of truth.

### `complete-task`

Close a task only after `eval-task` passed, declared outputs exist, context verification passes, lifecycle verification passes, effect verification passes or explicitly downgrades, decision verification passes or warns according to policy, and required postflight succeeds or records an explicit pending reason.

```bash
./bin/knowledgeos complete-task \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --summary "Task complete."
```

Manual `Status: passed` text is not enough unless an explicit override is used.

Before postflight, `complete-task` runs `verify-effects` and `verify-decisions`. It blocks on failed verification and records status, visible markers, warnings, or explicit strictness downgrades in the receipt.

For medium, high, or complex tasks, `complete-task` also prepares a readable Mission Flow summary and returns `FLOW_OK` fields. Agents should include that Mermaid flow in the final user-facing answer unless the user explicitly asks for a terse response.

`complete-task` also writes a dispatch report from the recorded `capability-event` ledger and returns `AGENT_DISPATCH_OK` fields. This makes all mounted capabilities visible in the final response without trusting hidden runtime claims, including agents invoked or skipped, MCP, skills, plugins/apps, browser/Chrome/GitHub/security connectors, scripts, shell, and file reads.

If `.agent-os/fabric-link.yaml` sets `postflight_required: true`, `complete-task` runs the configured shared-fabric `after-task.sh` and only reports `sync_status: SYNC_OK` when the hook emits `[SYNC_OK]`. Use `--allow-pending-postflight "<reason>"` only as an explicit, receipt-recorded escape hatch.

### `dispatch-report`

Summarize actual capability events recorded for a run:

```bash
./bin/knowledgeos dispatch-report \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-...
```

The command writes:

```text
.agent-os/runs/<RUN_ID>/dispatch-report.md
```

It emits `AGENT_DISPATCH_OK agents=<n> capabilities=<n> run=<RUN_ID>`.

The generated report is a **Full Capability Dispatch Report**. It includes:

- used and skipped counts by capability kind;
- agents invoked and agents skipped;
- MCP, skills, plugins/apps, browser/Chrome/GitHub/security connectors, scripts, shell, and file reads;
- skipped/not-needed reasons;
- dispatch plan evidence;
- capability and command ledger paths;
- gaps, such as required stages without a capability event or skip reason.

Use `dispatch-task` for the planned route (`AGENT_DISPATCH_PLAN`) and `dispatch-report` for what was actually registered through `capability-event`.

### `render-html`

Render canonical Markdown evidence into static, composable HTML sidecars for human review.

```bash
./bin/knowledgeos render-html \
  --project-root /path/to/project \
  --run-id RUN-... \
  --kind receipt

./bin/knowledgeos render-html \
  --project-root /path/to/project \
  --run-id RUN-... \
  --kind handoff

./bin/knowledgeos render-html \
  --project-root /path/to/project \
  --input reports/drafts/x.md \
  --kind rich-report \
  --output reports/drafts/x.html \
  --presentation minimal

./bin/knowledgeos render-html \
  --project-root /path/to/project \
  --run-id RUN-... \
  --kind decision-map

./bin/knowledgeos render-html \
  --project-root /path/to/project \
  --run-id RUN-... \
  --kind mission-flow
```

HTML is presentation only. Markdown, YAML, and NDJSON remain the source of truth. Generated pages include source path, source SHA-256, generated time, run id when available, and the notice `HTML is presentation, not source of truth.`

The OS only enforces the evidence metadata contract. It does not require a single visual layout. Presentation modes:

- `default`: the original KnowledgeOS card layout with hero, panel, and colored report shell;
- `minimal`: readable document body with evidence metadata footer, without hero/sidebar layout;
- `bare`: very small HTML shell and metadata footer for project-owned styling;
- `fragment`: reusable fragment plus manifest only, without writing a full document shell.

Projects may set an optional default:

```yaml
reporting:
  html_sidecars: true
  html_source_of_truth: false
  html_presentation_default: minimal
  html_required_metadata: true
```

Each render writes:

```text
<output>.html
<output>.fragment.html
<output>.manifest.json
```

When `--presentation fragment` is used, only `<output>.fragment.html` and `<output>.manifest.json` are written. The manifest records an empty `output` field because no full HTML document was generated.

Use the fragment and manifest for composition:

```bash
./bin/knowledgeos render-html \
  --project-root /path/to/project \
  --compose reports/drafts/report-manifest.json \
  --output reports/final/combined.html
```

Composition embeds static fragments into one self-contained page. It does not use iframes, remote scripts, remote fonts, or CDN assets, and it does not bypass lifecycle, eval, receipt, or sync gates.

### `reopen-task`

Reopen the same task when a result is rejected and should be rerun. Do not use this as intake for unrelated new work; use `create-task` instead.

```bash
./bin/knowledgeos reopen-task \
  --project-root /path/to/project \
  --task-id T001 \
  --reason "draft rejected; rerun required"
```

Use `--archive-outputs` to move declared outputs into `.agent-os/backups/` before rerunning. Control-plane outputs under `.agent-os/` are protected.

### `reset-project`

Reset project OS state without guessing user intent.

```bash
./bin/knowledgeos reset-project --project-root /path/to/project --mode soft
./bin/knowledgeos reset-project --project-root /path/to/project --mode hard
```

Soft reset archives volatile run state and keeps `.agent-os` configuration. Hard reset archives `.agent-os/` and `.agents/`, making the project unmanaged again. `--purge` deletes instead of archiving and should require human confirmation.

### `migrate-legacy-project`

Plan or apply a conservative reorganization for old project folders.

```bash
./bin/knowledgeos migrate-legacy-project \
  --project-root /path/to/project \
  --write-plan
```

The plan is written to `.agent-os/inbox/legacy-reorganization-plan.md`. `--apply` moves only confidently classified top-level entries and skips conflicts.

### `archive-legacy-project`

Plan or apply cold archival for old, superseded, or generated leftovers that should be kept but not read by default.

```bash
./bin/knowledgeos archive-legacy-project \
  --project-root /path/to/project \
  --write-plan
```

The plan is written to `.agent-os/inbox/cold-archive-plan.md`. `--apply` moves strong candidates into `archive/` without deleting them. Use `--include <path>` for explicit one-off archive decisions.

### `receipt`

Write a lightweight project-local receipt.

```bash
./bin/knowledgeos receipt \
  --project-root /path/to/project \
  --summary "Manual checkpoint."
```

## Current Limits

- The CLI reads KnowledgeOS' own simple YAML-like templates, not arbitrary YAML.
- `route-task` selects a route; it does not execute the route.
- `run-task` creates the envelope; it does not yet execute the task or call agents.
- `check-write` classifies planned paths; it does not yet intercept file-system writes automatically.
- `migrate-legacy-project --apply` is intentionally conservative and leaves unknown items for human triage.
- `archive-legacy-project --apply` is intentionally conservative and moves only strong marker matches or explicit includes into cold storage.
