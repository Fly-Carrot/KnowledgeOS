# Lean Batch 2: Short Entries, Unchanged Safety

Date: 2026-09-28
Status: implementation candidate; results in `docs/LIVE-REPORT.md`
Parent: [Correctness + Lean Orchestration](correctness-lean-v1.md), sections B1-B5
Prerequisite: [launcher import isolation](../launcher-isolation.md)

## Product Boundary

Keep the kernel small. Do not add a scheduler, new phase ledger, model-specific
mode, or automatic bulk migration. This batch removes repeated instructions
from always-loaded entry files; it does not remove safety checks.

```text
Short global/project entry
  -> classify the request and check project health
  -> read the selected CLI's agent-guide for substantive work or any side effect
  -> use the current task, bound Spec/Plan, permissions and enabled modules
  -> perform the supported lifecycle and verify actual artifacts
  -> relay concise, evidenced checkpoints and the final capability/sync result
```

Simple non-mutating questions need no new task. Loading the guide is mandatory
before even a small write or external side effect. Missing, failed, empty,
truncated, incompatible or conflicting guidance stops affected mutation; it
must not silently become permission to work without rules.

## One Rule Source

- `knowledgeos/guidance.py` produces the global template, project entry,
  startup prompt and detailed guide under `kos-guidance-v2`.
- Entries use one short loader. They do not copy every command example or
  pretend that a newer candidate's contract applies to an older installed CLI.
- Existing `agent-guide` and `startup-prompt` commands retain their interfaces.
  The public global template is `templates/global-agent-rules.md`; it is not
  an automatic installer for user configuration.
- `project.guidance_mode` remains `guided` by default, with `compact` available
  explicitly. Both views share the same safety rules. Model names never choose
  a weaker gate, and this batch does not qualify additional model versions.
- Route configuration participates in the guidance fingerprint. Task history
  is not copied into the entry or used as its configuration fingerprint.

## Visible Reporting

Keep `KOS_DECISION`, command-evidenced checkpoints, actual capabilities and
effects, public plan decisions, and final full capability/sync reporting.
Adjacent returned markers may share one short, readable update. Failures,
skipped reasons, pending states, gaps and required human decisions remain
visible. Do not repeat the entire capability inventory in every update.

Successful producer checkpoints need not be manually recorded again. Review,
execute and report still require actual evidence. Legacy clients follow their
own guide's explicit calls; supported lean clients retain completion as the
final verification gate. `SYNC_OK` is not GitHub publication.

## Compatibility And Rollback

1. Keep existing task/run/Spec identity and historical ledgers. Entry updates
   do not restart an in-flight run or switch its policies.
2. Generated blocks may be refreshed while preserving outside text verbatim.
   Unmarked, duplicate or reversed blocks are rejected for automatic merging.
3. Initial migration of the reviewed unmarked global rule is a separately
   scoped operation: exact before-hash, byte-identical backup, preserved
   communication style and delegation authorization, reviewed replacement,
   atomic write and post-write verification. Unknown changed input aborts.
4. The global loader continues using the installed CLI; do not repoint every
   conversation to an unqualified candidate. Install only the separately
   validated launcher fix, not unrelated candidate code or dirty work.
5. Roll back only files changed by this migration after verifying their current
   hashes. Keep new ledgers and unrelated work. Do not blindly overwrite changes
   made after deployment or terminate/restart other conversations.

## Bounded Pilot

The deterministic pilot matrix covers `report_task` and `engineering_change`,
each in guided and compact modes. Each creates an actual artifact, performs
acceptance, completes via real lifecycle gates, and checks a real shell-hook
counter. Repeated completion must sync only once. No redundant explicit
dispatch/verify command is needed in the lean test path.

Also test an active legacy-style run across entry refresh and rollback with
byte-identical history; custom-block preservation; missing guide input refusal;
and the old installed CLI's guide loading from the shortened global entry.
These are disposable project pilots and one bounded local entry migration,
not broad live-project migration or a model-performance benchmark. GPT-5 and
other exact-model qualification remains untested until its required matrix runs.

## Acceptance

- Launcher shadowing reproduces before repair and passes after repair, with
  caller directory, arguments, space paths and exit status preserved.
- Entry text is materially shorter; full guide remains available and tested.
- Both guidance modes retain the same negative-case safety regressions.
- Pilot tasks finish without duplicate dispatch, runs or sync side effects.
- Original installed source changes are preserved; only approved target files
  are deployed with reversible local evidence.
- Full unittest, guardrail scenarios, doctor, syntax and diff checks pass.
- Update changelog and repair report without exposing private paths/ledgers.
  GitHub release, bulk rollout and stable version certification stay in Batch 3.
