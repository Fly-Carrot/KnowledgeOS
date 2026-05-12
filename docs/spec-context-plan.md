# Spec, Context Pack, And Plan Gate

KnowledgeOS keeps classification open, but the work lifecycle fixed. The spec/context/plan gate is the memory-stability layer for that lifecycle.

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

## Write Safety

Direct edits to `.agent-os/specs.yaml`, `.agent-os/specs/**`, `context-pack.md`, `spec-snapshot.md`, and `plan.md` are human-gated by default. The normal path is to use `create-spec`, `align-spec`, `context-pack`, and `plan-task`.
