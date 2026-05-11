# Global Kernel Rule

This is the minimal KnowledgeOS kernel rule.

Agents must:

- load project context before acting;
- run the before-task hook before substantial work;
- follow the fixed lifecycle: route -> plan -> review -> dispatch -> execute -> report;
- check write policy and route policy before mutation;
- write receipts and handoffs after substantial work;
- never store secrets in the kernel.

The kernel defines operating discipline. It does not store project knowledge, raw materials, or private chat histories.
