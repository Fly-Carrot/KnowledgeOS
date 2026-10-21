# Lean project workflow (v0.3.0)

KnowledgeOS is a constraints, research evidence and handoff layer, not a second
execution harness. Codex executes work. Optional observers visualize tool logs.

## Start work, not an onboarding ceremony

An unmanaged directory needs no initialization prompt, managed task, or full
doctor check. Read its applicable instructions, do authorized work and verify the
result. Never create `.agent-os/` without explicit or standing authorization.
Reading `agent-guide` does not initialize anything.

An explicitly adopted ordinary-v1 project uses:

```text
select/create a bounded task -> run-task -> work and tests -> eval-task -> complete-task
```

`run-task --dry-run` previews the actual contract and write checks. Recheck newly
planned paths. Result-v1 evaluation binds acceptance criteria to reviewed checks
and relevant input/output revisions; command validators require an explicit
execution flag. Failed, missing or stale evidence cannot authorize completion.

Simple questions require no managed task. Durable research reuses its Spec/Plan
and records sources, material decisions, uncertainty and continuation notes.
Do not duplicate every tool call in a second ledger.

## One visible receipt

Substantive managed work ends with a concise, evidence-backed line, for example:

> KnowledgeOS: completed | verification passed | task record

Use actual status and a link to the relevant record. Disclose failed/unverified
checks and required sync still pending. A log, marker or doctor pass does not
prove a research claim. Unmanaged work must not claim KnowledgeOS verification.
Existing strict contracts retain their required reporting. No new receipt format,
command, service or per-message logging gate is introduced.

## Upgrade without changing work in progress

- Missing managed configuration is legacy, not implicit permission to downgrade.
- Existing runs keep their bound contracts, approvals, acceptance and history.
- Only eligible new runs use adopted ordinary defaults. Explicit enforce/high-risk
  policies and required postflight remain enforced.
- Authorized local future-default receipts bind project identity and unchanged
  policy hashes. They do not provide cryptographic authorization.
- Update only known generated entry blocks. Back up targets and refuse changed,
  redirected or ambiguous entries. Busy/conflicting projects are deferred, not reset.
- Keep the previous runtime while a live task or pinned launcher needs it.
- Existing chats load refreshed entries at their next relevant operation. Updating
  a file cannot replace context already loaded by a running model.

Global entry, project entry and agent-guide share `knowledgeos.guidance`. Preserve
custom communication, delegation and observer rules outside generated blocks.
The global entry remains below 200 English words (excluding custom sections).

## Cleanup and recovery

Only delete reproducible, unreferenced temporary products after a reviewed
inventory. Preserve raw research data, provenance, accepted decisions, completed
evidence and required rollback versions. Declared outputs must be relocated or
retired through the existing output registry with custody evidence; deleting them
directly would invalidate diagnostics. Archiving on the same disk is not reclaimed
space. Report measured space savings, not the sum of potential candidates.

Use `make release-smoke` in a clean distribution. `make smoke` remains a diagnostic
for a configured maintainer workspace, not proof that private history was shipped.
No exact-model qualification is claimed by this deterministic regression suite.
