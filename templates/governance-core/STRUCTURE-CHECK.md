# Governance Core Structure Check

A valid governance core should provide:

- rules/
- hooks/
- registries/
- schemas/
- memory/
- sync/
- hooks/before-task.sh
- hooks/log-phase.sh
- hooks/after-task.sh
- schemas/phase-contract.md
- schemas/memory-lanes.md
- schemas/postflight-contract.md
- sync/task-phases.ndjson
- sync/receipts.ndjson

The governance core is the brain. It should stay small, inspectable, and portable.
