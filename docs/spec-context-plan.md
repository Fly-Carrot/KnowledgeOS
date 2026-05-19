# Spec, Context Pack, And Plan Gate

KnowledgeOS keeps classification open, but the work lifecycle fixed. The spec/context/plan gate is the memory-stability layer for that lifecycle.

## Product Spec Philosophy

KnowledgeOS should be governed by this product spec:

```text
Kernel stays small.
Modules inject only when enabled or invoked.
Apps observe, not govern.
Projects choose strictness.
Every major operational step emits public trace.
Every lifecycle phase emits CHECKPOINT_OK.
Every capability call emits CAPABILITY_OK.
No command evidence, no success claim.
```

The spec is intentionally anti-bloat. Route profiles create order by setting policy, not by trying to pre-model every mixed task. Capability dispatch remains pluggable. Workbench and future desktop surfaces read OS state; they do not become required kernel.

## Why It Exists

Agents can lose focus across long sessions. A user may say "对齐 spec", "创建 spec", or "按这个 spec 做" because they want durable intent, not a one-turn plan. KnowledgeOS turns that intent into command-generated project state.

## Files

```text
.agent-os/specs.yaml
.agent-os/specs/SPEC-YYYYMMDD-001/
  spec.md
  acceptance.md
  non-goals.md
  alignment.md
  change-log.ndjson

.agent-os/runs/RUN-*/
  spec-snapshot.md
  context-pack.md
  plan.md
  step-events.ndjson
```

## Command Path

```text
create-spec or align-spec
-> run-task
-> context-pack
-> plan-task
-> phase-task checkpoints
-> eval-task
-> verify-context
-> verify-lifecycle
-> verify-effects
-> complete-task
```

`run-task` writes the first `spec-snapshot.md` and `context-pack.md`. Agents should rerun `context-pack` after spec alignment or when the visible context changes. `plan-task` writes `plan.md` and creates command evidence.

## Completion Gate

`complete-task` refuses to close a run if:

- `context-pack.md`, `spec-snapshot.md`, or `plan.md` is missing;
- the files lack KnowledgeOS generator markers;
- `command-events.ndjson` lacks `context-pack` or `plan-task` evidence;
- the active spec changed after the run snapshot.

The saved content is a public decision trace and execution contract. It is not hidden chain-of-thought.

`trace-step` complements the six lifecycle checkpoints by recording user-visible operational progress such as `user_intent`, `load_rules`, `doctor_gate`, `task_intake`, `route_guard`, `dispatch_plan`, `write_guard`, `execution`, `eval`, `verify`, `complete`, and `sync`.

## Write Safety

Direct edits to `.agent-os/specs.yaml`, `.agent-os/specs/**`, `context-pack.md`, `spec-snapshot.md`, and `plan.md` are human-gated by default. The normal path is to use `create-spec`, `align-spec`, `context-pack`, and `plan-task`.
