# Spec: Decision Graph Module

## Intent

Add an optional Decision Graph module that records public, auditable natural-language decision summaries during KnowledgeOS runs. The module captures plan branches, route selections, inserted steps, abandoned branches, rollbacks, superseded paths, deferred work, human decisions, risk tradeoffs, and final decisions.

The module must preserve KnowledgeOS product philosophy:

```text
small kernel + pluggable modules + optional apps + project-level strictness + mandatory visible checkpoints
```

Decision Graph is not kernel. It is a module that can be observed by default and enforced only by project policy.

## Public Contract

- `decision-event` writes `.agent-os/runs/<RUN_ID>/decision-events.ndjson` and emits `DECISION_OK`.
- `decision-query` filters decision events by run, task, kind, status, or parent id.
- `verify-decisions` checks command evidence, orphan parents, duplicate ids, invalid kinds/statuses, and unexplained abandoned/rollback/superseded branches.
- `render-html --kind decision-map` renders a static HTML sidecar from `decision-events.ndjson`.
- `.agent-os/decision-policy.yaml` defaults to `strictness: warn`.
- `complete-task` blocks only when decision verification status is failed, including `strictness: enforce` without valid decision evidence.

## Source Of Truth

The source of truth is NDJSON under `.agent-os/runs/<RUN_ID>/decision-events.ndjson`. HTML is presentation only.
