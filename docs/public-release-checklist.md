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
- `create-task` works and new work does not require abusing `reopen-task`;
- `phase-task` and `verify-lifecycle` work;
- `complete-task` refuses missing phases;
- `complete-task` runs required postflight or records an explicit pending reason.
