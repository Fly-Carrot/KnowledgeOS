# KnowledgeOS Thread Plan Ledger

Thread Plan Ledger is a chat-level planning module. It keeps a natural-language, append-only map of a long conversation: the original plan, later branches, route changes, inserted phases, linked runs, and current working line.

It is not a checkpoint gate. It does not replace `plan-task`, `decision-event`, lifecycle evidence, or completion receipts.

## Why It Exists

Some research and product conversations last across many tasks. A run-level Mission Flow shows one completed task, but it does not show how the whole conversation evolved. Thread Plan Ledger gives that longer story a durable, readable home.

Use it when the user says they want to create, align, or follow a durable plan/spec, or when a conversation starts to branch over multiple rounds.

## Evidence Files

```text
.agent-os/threads/<THREAD_ID>/thread-plan.ndjson
.agent-os/threads/<THREAD_ID>/thread-plan.md
.agent-os/threads/<THREAD_ID>/thread-map.html
.agent-os/threads/current.json
```

The NDJSON ledger is the source of truth. Markdown and HTML are sidecars for human review.

## Commands

Start a chat-level plan:

```bash
knowledgeos thread-plan start \
  --project-root . \
  --title "长期维护鸟类声景基金申请计划" \
  --spec-id SPEC-...
```

Append a natural-language note:

```bash
knowledgeos thread-plan append \
  --project-root . \
  --thread-id THREAD-... \
  --kind phase \
  --text "Phase A：先稳定计划记录；Phase B：再串联多个任务。"
```

Link a run to the conversation:

```bash
knowledgeos thread-plan link-run \
  --project-root . \
  --thread-id THREAD-... \
  --task-id T001 \
  --run-id RUN-...
```

Render the plan:

```bash
knowledgeos thread-plan render --project-root . --thread-id THREAD-... --format markdown
knowledgeos thread-plan render --project-root . --thread-id THREAD-... --format mermaid
knowledgeos thread-plan render --project-root . --thread-id THREAD-... --format html
```

All successful commands return `THREAD_PLAN_OK`.

## Writing Style

Keep entries readable. Prefer:

- `Plan A / Plan B`;
- `Phase A / Phase B`;
- `当前选择`;
- `为什么改路`;
- `已经完成到哪里`;
- `下一步是什么`.

Do not paste hidden chain-of-thought. Record concise public planning notes that another human can read later.

## Module Boundary

Thread Plan Ledger is a module, not kernel. It should not block `complete-task`, `verify-lifecycle`, or `SYNC_OK`. It can be rendered in a Workbench or HTML page as a versioned planning map, similar to a lightweight visual worktree for the conversation.
