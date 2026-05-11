# Reset And Legacy Migration

KnowledgeOS should make projects observable without making them feel impossible to clean up. Reset and migration are therefore explicit, reversible operations.

## Reset Model

There are three reset levels.

### Reopen One Task

Use this when the project is valid but a specific task output is not accepted.

```bash
./bin/knowledgeos reopen-task \
  --project-root /path/to/project \
  --task-id T002 \
  --reason "draft rejected; rerun required"
```

Optional output cleanup:

```bash
./bin/knowledgeos reopen-task \
  --project-root /path/to/project \
  --task-id T002 \
  --reason "draft rejected; rerun required" \
  --archive-outputs
```

By default, cleanup archives outputs instead of deleting them. Control-plane outputs under `.agent-os/` are protected.

### Soft Reset

Use this when the project should keep its OS configuration but lose volatile run state.

```bash
./bin/knowledgeos reset-project \
  --project-root /path/to/project \
  --mode soft
```

Soft reset archives:

- `.agent-os/runs/`
- `.agent-os/receipts/`
- `.agent-os/handoffs/`

It also resets completed, in-progress, and blocked tasks to `ready` unless `--keep-task-status` is used.

### Hard Reset

Use this when the project should become unmanaged again.

```bash
./bin/knowledgeos reset-project \
  --project-root /path/to/project \
  --mode hard
```

Hard reset archives:

- `.agent-os/`
- `.agents/`

Use `--include-agents-md` when the project entry contract was generated and should be removed too.

### Purge Mode

`--purge` deletes instead of archiving. It is intentionally explicit and should only be used after human confirmation.

```bash
./bin/knowledgeos reset-project \
  --project-root /path/to/project \
  --mode hard \
  --purge
```

## Legacy Project Migration

Use this when a user installs KnowledgeOS into an old project whose folders do not yet match the standard structure.

```bash
./bin/knowledgeos migrate-legacy-project \
  --project-root /path/to/project \
  --write-plan
```

The command writes a review-first plan to:

```text
.agent-os/inbox/legacy-reorganization-plan.md
```

The plan maps obvious legacy folders such as `前期材料`, `code`, `results`, and `reports` into the canonical layout. Unknown items stay in `inbox/` for human triage.

Apply is conservative:

```bash
./bin/knowledgeos migrate-legacy-project \
  --project-root /path/to/project \
  --apply
```

It moves only confidently classified top-level entries and skips any target conflict. Raw materials remain protected by the write policy after migration.

## Cold Archive For Historical Leftovers

Use this when an old project contains previous drafts, old code, obsolete generated outputs, or other material that should be retained but removed from default agent context.

```bash
./bin/knowledgeos archive-legacy-project \
  --project-root /path/to/project \
  --write-plan
```

The command writes a review-first plan to:

```text
.agent-os/inbox/cold-archive-plan.md
```

Apply is separate and reversible by normal filesystem move semantics:

```bash
./bin/knowledgeos archive-legacy-project \
  --project-root /path/to/project \
  --apply
```

The archive command moves strong legacy/archive candidates into:

```text
archive/legacy/
archive/generated/
archive/superseded/
archive/trash-candidates/
```

`archive/**` is cold storage. Agents should not read it during default context loading; they should inspect it only after explicit human request or through an `archive_management` route.

## Natural-Language Use

A user can say:

```text
Please reset this KnowledgeOS project and make it unmanaged again.
```

The agent should run `reset-project --mode hard --dry-run` first, show the actions, then ask before running without `--dry-run`.

A user can say:

```text
Please reorganize this old project into KnowledgeOS structure.
```

The agent should run `migrate-legacy-project --write-plan`, present the plan, and only use `--apply` after approval.

A user can say:

```text
Please move old leftovers into cold archive so agents stop treating them as active context.
```

The agent should run `archive-legacy-project --write-plan`, present the plan, and only use `--apply` after approval.
