# Governance Core Template

This template represents the fixed KnowledgeOS governance kernel surface.

It contains a minimal runnable kernel scaffold:

- `rules/`: stable operating rules for agents;
- `hooks/`: before-task, phase logging, and after-task hooks;
- `registries/`: opt-in registry examples for MCP, skills, and workflows;
- `schemas/`: phase, memory, and postflight contracts;
- `memory/`: empty structured memory lane ledgers;
- `sync/`: empty receipt and phase-log ledgers.

It should not contain user-specific MCP implementations, large skill libraries, raw chat histories, project wiki pages, or secrets.

The kernel defines how agents operate. Project knowledge belongs in project folders, not in the kernel.
