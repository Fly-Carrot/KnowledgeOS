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
- lifecycle consistency for `run-task -> context-pack -> plan-task -> phase-task -> eval-task -> verify-context -> verify-lifecycle -> verify-effects -> complete-task`.

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

Allowed kinds are `mcp`, `skill`, `subagent`, `orchestrator`, `script`, `shell`, and `file_read`.

The command writes `.agent-os/runs/<RUN_ID>/capability-events.ndjson` and matching command evidence. Successful plain-text output begins with:

```text
CAPABILITY_OK kind=<kind> id=<capability-id> purpose=<short purpose>
```

JSON output also includes a stable `capability_event_id`. Use that id when an effect assertion proves the real side effect produced by the capability. If `artifact-assert` is called with `--capability-event-id`, the id must already exist in the run's `capability-events.ndjson`; bogus links are rejected.

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

### `complete-task`

Close a task only after `eval-task` passed, declared outputs exist, context verification passes, lifecycle verification passes, effect verification passes or explicitly downgrades, and required postflight succeeds or records an explicit pending reason.

```bash
./bin/knowledgeos complete-task \
  --project-root /path/to/project \
  --task-id T001 \
  --run-id RUN-... \
  --summary "Task complete."
```

Manual `Status: passed` text is not enough unless an explicit override is used.

Before postflight, `complete-task` runs `verify-effects`. It blocks on failed effect verification and records effect status, the `EFFECT_VERIFY_OK` marker, warnings, or explicit strictness downgrades in the receipt.

If `.agent-os/fabric-link.yaml` sets `postflight_required: true`, `complete-task` runs the configured shared-fabric `after-task.sh` and only reports `sync_status: SYNC_OK` when the hook emits `[SYNC_OK]`. Use `--allow-pending-postflight "<reason>"` only as an explicit, receipt-recorded escape hatch.

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
  --output reports/drafts/x.html
```

HTML is presentation only. Markdown, YAML, and NDJSON remain the source of truth. Generated pages include source path, source SHA-256, generated time, run id when available, and the notice `HTML is presentation, not source of truth.`

Each render writes:

```text
<output>.html
<output>.fragment.html
<output>.manifest.json
```

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
