# Acceptance

- `decision-event` records command-generated decision events and returns `DECISION_OK`.
- `decision-query` returns filtered parent/child decision events.
- `verify-decisions` rejects forged or orphaned decision events and emits `DECISION_VERIFY_OK`.
- `decision-policy strictness: warn` does not block linear work without decision events.
- `decision-policy strictness: enforce` blocks completion without valid decision evidence.
- `decision-policy strictness: off` requires `downgrade_reason`.
- `render-html --kind decision-map` creates a self-contained HTML sidecar with source hash metadata.
- Documentation explains Decision Graph as a module, not kernel.
