# Cold Archive Policy

KnowledgeOS separates **raw evidence**, **active knowledge**, and **cold historical storage**.

`archive/**` is for files that should be kept for recovery or audit but should not be read as default agent context.

## Folder Semantics

```text
materials/raw/      original evidence; readable when relevant, immutable by default
knowledge/          extracted active knowledge; source-linked and maintained
src/ tests/ docs/   active working surface
outputs/ reports/   active generated products
archive/            cold storage; not default context
```

Recommended archive layout:

```text
archive/
  legacy/            old code, old project layouts, previous structures
  generated/         obsolete generated outputs, old figures, old tables
  superseded/        old drafts, replaced docs, previous reports
  trash-candidates/  candidates for deletion, kept temporarily for safety
```

## Read Rule

Agents should not scan or summarize `archive/**` during normal context loading.

They may inspect it only when:

- the user explicitly asks for archive review or recovery;
- a routed task has type `archive_management` or an equivalent explicit route;
- a cold archive plan names the files that will be inspected or moved.

This rule lives in `.agent-os/read-policy.yaml`:

```yaml
read_policy:
  cold_storage:
    - archive/**
  require_explicit_human_request:
    - archive/**
  deny_indexing:
    - archive/**
```

## Migration Workflow

Use `archive-legacy-project` for historical leftovers that should be retained but removed from active context.

Plan first:

```bash
./bin/knowledgeos archive-legacy-project \
  --project-root /path/to/project \
  --write-plan
```

The plan is written to:

```text
.agent-os/inbox/cold-archive-plan.md
```

Apply only after review:

```bash
./bin/knowledgeos archive-legacy-project \
  --project-root /path/to/project \
  --apply
```

Explicit one-off archive decisions are supported:

```bash
./bin/knowledgeos archive-legacy-project \
  --project-root /path/to/project \
  --include docs/old-draft.md \
  --write-plan
```

## Safety Guarantees

- The command is plan-first; `--apply` is separate.
- It does not delete files.
- It skips `.agent-os/` control-plane paths.
- It skips files already under `archive/`.
- It preserves the original relative path under an archive category.
- It treats archive as a write-controlled zone and a read-cold zone.
