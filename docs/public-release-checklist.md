# Public Release Checklist

Before publishing KnowledgeOS, verify:

- no personal absolute paths in public docs or templates;
- no API keys or secret values;
- local migration content stays under `.knowledgeos-local/` and is not shipped;
- top-level `.agent-os/` is treated as local build state;
- templates use placeholders such as `CHANGE_ME`;
- governance core and capability layer are documented as separate layers;
- Agent Shared Fabric is described as a kernel module, not copied project content;
- Any future app is described as a workbench that consumes receipts/wiki/graph outputs.
