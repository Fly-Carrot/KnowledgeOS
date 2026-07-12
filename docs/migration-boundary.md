# Migration Boundary

KnowledgeOS has two tracks.

## Public Track

The public track contains reusable concepts, templates, and user-facing documentation.

It must not contain:

- personal filesystem paths;
- API keys or secrets;
- private project names unless explicitly sanitized;
- raw chat histories;
- generated private runtime state.

## Local Track

The local track lives under `.knowledgeos-local/` and can reference the current machine's real paths.

This track is for migration planning only. It should not be published as part of the clean KnowledgeOS release.

For runtime migrations that must touch exact machine-local targets outside the repo, keep the allowlist in `.knowledgeos-local/write-policy.local.yaml`.

That file is a local overlay, not part of the public control plane. It may contain sections such as:

- `external_controlled`
- `external_forbidden_without_human_gate`
- `external_require_receipt_for`

External writes remain denied by default. They become legal only when all three conditions are true:

1. the path is listed in the local overlay;
2. the active task route explicitly sets `allow_external_controlled: true`;
3. normal KnowledgeOS route, run, eval, and lifecycle evidence still complete.

## Reorganization Boundary

`migrate-legacy-project` is the safe entry point for old project folders. It creates a reviewable plan first and only moves confidently classified top-level entries with `--apply`.

Unknown files or folders should remain in `inbox/` for human or orchestrator triage. The OS should not pretend every possible legacy project can be perfectly classified ahead of time.

## Cold Archive Boundary

`archive-legacy-project` is the safe entry point for historical or superseded project material that should be kept but removed from default agent context.

It writes `.agent-os/inbox/cold-archive-plan.md` first. `--apply` moves strong candidates into `archive/` and preserves their relative paths under `archive/legacy/`, `archive/generated/`, `archive/superseded/`, or `archive/trash-candidates/`.

`archive/**` is storage, not active knowledge. Agents must not index or summarize it during normal startup unless the user explicitly asks for archive review or recovery.

## Reset Boundary

`reset-project` controls OS state, not the user's domain materials. Soft reset archives volatile run state while keeping `.agent-os` configuration. Hard reset archives or removes `.agent-os` and `.agents` so the project becomes unmanaged again.

Use `--purge` only when the user explicitly asks for deletion instead of backup.
