# KnowledgeOS Capability Effect Verification Summary

> HTML sidecar summary for the KOS-T066 change set. Markdown remains the canonical source; HTML is generated for human review.

## Executive Summary

This change upgrades KnowledgeOS from **capability visibility** to **capability effect verification**. The previous system could show that an agent claimed to use a tool, skill, shell command, or subagent. The new system asks the more important operational question: **did the claimed side effect actually land?**

The implementation adds a small verification layer built around `artifact-assert`, `verify-effects`, and `effect-policy.yaml`. These commands make real artifacts touchable, auditable, and enforceable before `complete-task` can report success.

## What Changed

| Area | Before | After |
| --- | --- | --- |
| Capability trace | `capability-event` recorded declared calls | `capability-event` now exposes stable `capability_event_id` values |
| Artifact proof | No first-class side-effect verifier | `artifact-assert` records `EFFECT_OK` only after checking a real artifact |
| Completion gate | `complete-task` checked eval, context, lifecycle, and sync | `complete-task` also runs `verify-effects` before postflight |
| Project strictness | No effect-verification policy | `.agent-os/effect-policy.yaml` supports `observe`, `warn`, `enforce`, and `off` |
| Forgery resistance | Ledger rows could be manually imitated | `verify-effects` requires matching command evidence for assertions |
| Templates | No effect policy in project template | New projects receive `effect-policy.yaml` by default |

## New Evidence Lane

The change introduces a fifth practical evidence lane that complements the existing mission-control model:

1. `step-events.ndjson` records public operational trace.
2. `phases.ndjson` records lifecycle checkpoints.
3. `capability-events.ndjson` records visible capability calls.
4. `effect-assertions.ndjson` records real artifact side-effect checks.
5. `postflight.md` records completion and `[SYNC_OK]`.

This preserves the KnowledgeOS philosophy: **small kernel, pluggable modules, optional apps, project-level strictness, and mandatory public checkpoints for substantial work.**

## Main Commands Added

### `artifact-assert`

Records artifact-level proof only after a real check passes.

Supported assertion kinds:

- `file_exists`
- `file_nonempty`
- `file_contains`
- `file_sha256`
- `file_changed`
- `json_key_equals`
- `html_self_contained`

Example:

```bash
knowledgeos artifact-assert \
  --project-root . \
  --task-id KOS-T066 \
  --run-id RUN-20260519-092120-KOS-T066 \
  --kind file_contains \
  --path knowledgeos/cli.py \
  --expect "def verify_effects"
```

### `verify-effects`

Checks whether declared task outputs have corresponding passed assertions and whether those assertions have command evidence.

Example:

```bash
knowledgeos verify-effects \
  --project-root . \
  --task-id KOS-T066 \
  --run-id RUN-20260519-092120-KOS-T066 \
  --json
```

### `effect-policy.yaml`

Controls project strictness.

```yaml
effect_policy:
  strictness: warn
  downgrade_reason:
  default_assertion: file_exists
  required_for:
    - declared_outputs
```

## Bugs Found And Fixed

### 1. Capability logs did not prove side effects

- **Root cause:** `capability-event` showed agent intent, not artifact reality.
- **Reproduction:** Before this change, a task could register a shell or MCP call and still not prove the expected file changed.
- **Fix:** Added `artifact-assert` and required effect verification before task completion.

### 2. Forged assertion rows could look valid

- **Root cause:** A plain NDJSON assertion row could be manually appended.
- **Reproduction:** Tests append forged effect rows without matching command evidence.
- **Fix:** `verify-effects` rejects assertions that do not have corresponding `artifact-assert` command events.

### 3. Strict effect policy could break old projects

- **Root cause:** Making `.agent-os/effect-policy.yaml` mandatory would cause existing projects to fail doctor immediately.
- **Reproduction:** Old project without `effect-policy.yaml` fails if the file is required.
- **Fix:** Existing projects default to `observe`; templates create the policy for new projects.

### 4. Completion could bypass effect verification

- **Root cause:** `complete-task` did not previously call `verify-effects`.
- **Reproduction:** A task with eval and lifecycle evidence could complete without artifact side-effect proof.
- **Fix:** `complete-task` now runs effect verification and records effect status in receipts.

### 5. Shell variable collision during assertion registration

- **Root cause:** A zsh loop used the variable name `path`, which maps to `PATH` in zsh.
- **Reproduction:** The shell reported `env: bash: No such file or directory` after `PATH` was clobbered.
- **Fix:** Renamed the loop variable to `relpath`.

## Verification Evidence

The KOS-T066 implementation passed the following checks:

- `python3 -B -m py_compile knowledgeos/cli.py`
- `python3 -B -m unittest discover -s tests -v`
- `./examples/scenarios/run_guardrail_scenarios.sh`
- `make smoke`
- `./bin/knowledgeos doctor --root . --project-root . --summary`
- `./bin/knowledgeos verify-context --project-root . --task-id KOS-T066 --run-id RUN-20260519-092120-KOS-T066 --json`
- `./bin/knowledgeos verify-lifecycle --project-root . --task-id KOS-T066 --run-id RUN-20260519-092120-KOS-T066 --json`
- `./bin/knowledgeos verify-effects --project-root . --task-id KOS-T066 --run-id RUN-20260519-092120-KOS-T066 --json`
- `./bin/knowledgeos complete-task --project-root . --task-id KOS-T066 --run-id RUN-20260519-092120-KOS-T066 --summary ... --json`

Final completion evidence:

- Task: `KOS-T066`
- Run: `RUN-20260519-092120-KOS-T066`
- Lifecycle status: `passed`
- Context status: `passed`
- Effect status: `passed`
- Sync status: `SYNC_OK`
- Status marker: `[SYNC_OK]`

## Design Meaning

The important product move is not just adding another command. It is creating a sharper contract between the agent and the project:

> A capability call is not success. A real verified effect is success.

This keeps KnowledgeOS lightweight while making long-running agent work more trustworthy. The kernel stays small; verification remains policy-driven; projects can choose strictness; apps can visualize evidence without becoming the rule engine.

## Follow-Up Note

During this summary task, a dry run found that the local KnowledgeOS project router lacks a `report_task` profile even though the project template includes one. To avoid a control-plane mutation inside a documentation-only task, this summary was routed to `docs/` instead of `reports/drafts/`. That router alignment should be handled as a separate small bugfix task.
