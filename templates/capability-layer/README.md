# Capability Layer Template

This template represents the OS capability layer.

It can contain:

- `mcp/` for MCP server adapters;
- `skills/` for local, curated, generated, or domain skills;
- `workflows/` for reusable workflow prompts;
- `subagents/` for custom subagent definitions or orchestration packets;
- `agents/` for runtime-specific agent adapters;
- `registries/` for local capability indexes.

The capability layer is part of the KnowledgeOS operating surface. It stays separate from the kernel module so users can customize tools without dirtying the fixed operating discipline.
