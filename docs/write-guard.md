# Write Guard

KnowledgeOS must prevent dirty writes.

A dirty write is any agent mutation that lacks scope, evidence, rollback, or permission.

## Rule

Agents should not write directly just because they can. They should first declare intent, check policy, write in a controlled path, and leave receipts.

## Lifecycle

```text
task selected
-> write intent declared
-> path policy checked
-> diff or generated artifact created
-> eval run
-> receipt written
-> postflight sync
```

## Zones

- Immutable: raw materials, raw data, kernel schemas, secrets.
- Controlled: project state, knowledge, source code, tests, outputs, draft reports.
- Cold archive: historical files under `archive/**`; write-controlled and not read as default context.
- Human-gated: final reports, credentials, deployment, global kernel changes.
- Generated: run receipts, evals, logs, graph, wiki indexes.
