# Public Release Checklist

Before publishing KnowledgeOS, verify:

- no personal absolute paths in public docs or templates;
- no API keys or secret values;
- local migration content stays under `.knowledgeos-local/` and is not shipped;
- top-level `.agent-os/` is treated as local build state;
- templates use placeholders such as `CHANGE_ME`;
- governance core and capability layer are documented as separate layers;
- Agent Shared Fabric is described as a kernel module, not copied project content;
- Any future app is described as a workbench that consumes receipts/wiki/graph outputs;
- `archive/**` is documented as cold storage, not default context.
- `create-spec` and `align-spec` work for durable user intent;
- `thread-plan start/current/append/link-run/render` work for chat-level natural-language planning;
- `thread-plan render --format html` creates a self-contained sidecar without becoming a completion gate;
- `context-pack`, `plan-task`, and `verify-context` work;
- `complete-task` refuses missing plan/context evidence and spec drift;
- `create-task` works and new work does not require abusing `reopen-task`;
- `phase-task` and `verify-lifecycle` work;
- `phase-task` returns a visible `CHECKPOINT_OK` marker;
- `capability-event` records capability visibility and returns `CAPABILITY_OK`;
- `decision-event` records public decision graph events and returns `DECISION_OK`;
- `decision-query` can filter run decisions by parent, kind, and status;
- `verify-decisions` returns a visible `DECISION_VERIFY_OK` marker and rejects forged or orphaned decisions;
- `flow-summary` returns a visible `FLOW_OK` marker and a readable Mermaid Mission Flow;
- `render-html --kind mission-flow` creates a self-contained HTML sidecar from `mission-flow.md`;
- `artifact-assert` verifies real side effects and returns `EFFECT_OK`;
- `artifact-assert` rejects bogus `--capability-event-id` links;
- `verify-effects` returns a visible `EFFECT_VERIFY_OK` marker with status, strictness, assertion count, warning count, and error count;
- `verify-effects` refuses missing or forged effect evidence when policy is `enforce`;
- `verify-lifecycle` refuses missing dispatch or required capability evidence;
- `complete-task` refuses missing phases;
- `complete-task` runs effect and decision verification and records warnings or downgrade reasons;
- `complete-task` returns Mission Flow fields for medium, high, or complex tasks;
- `complete-task` runs required postflight or records an explicit pending reason.
