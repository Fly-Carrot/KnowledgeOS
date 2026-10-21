# KnowledgeOS Simplification Step 2

Spec: SPEC-20261020-003, section 4.
Scope: retained eval/completion and task-scoped diagnostics. No new service,
orchestrator, mandatory ledger, project migration or GitHub publication.

## Reproduced Defects

1. An existing report containing incorrect content received `passed` from
   eval-task because only file existence was inspected.
2. A declared input changed from v1 to v2 without changing the eval fingerprint:
   the original fingerprint covered outputs and policies, not input data.
3. Full diagnostics treated a missing unrelated historical output as a project
   failure. There was no task-scoped diagnostic entry point.

The original three-test reproduction produced two assertion failures and one
unsupported-interface error before implementation. Separate CLI reproduction
confirmed that the old doctor did not accept task scope.

## Compatibility Boundary

Only new ordinary-v1 runs receive `validation_contract: result-v1`, bound in both
run metadata and the run-task event. Legacy and already-started Step 1 ordinary
runs retain their previous eval contract. This is not a retrospective claim that
old existence checks prove behavioral correctness.

Existing strict project gates, task/Spec bindings, raw-data restrictions,
postflight requirements and active chats are not migrated. The English global
entry remains unchanged; only the scoped installed guide gains validation usage.

## Three-Call Ordinary Path

1. run-task: scoped permissions, relevant declared inputs and existing context.
2. eval-task: explicit validators and their actual results.
3. complete-task: verify the recorded results and current revisions, without
   rerunning successful validators.

Use create-task --input to identify relevant data, source, tests and model/config
dependencies. Task creation is only needed for new scope, not each message.

Example for an already authorized project:

```sh
knowledgeos eval-task --project-root . --task-id T003 --run-id RUN-ID \
  --check '{"kind":"command","argv":["python3","-B","tests/check_result.py"],"inputs":["tests/check_result.py","src/model.py","data/input.csv"],"acceptance":[1]}' \
  --dry-run

knowledgeos eval-task --project-root . --task-id T003 --run-id RUN-ID \
  --check '{"kind":"command","argv":["python3","-B","tests/check_result.py"],"inputs":["tests/check_result.py","src/model.py","data/input.csv"],"acceptance":[1]}' \
  --execute-validators
```

`--check` may be repeated. Acceptance indices are 1-based and all criteria must
be covered. Supported checks: command, file_contains, json_key_equals, manual.
Recorded validators are bound to the run; failed checks cannot be dropped or
replaced to manufacture a pass. Missing checks can be added while retaining all
previous checks. Changed scope needs a reviewed new task/run.

Commands are explicit caller-supplied argv, not instructions discovered inside
documents, notes, repository manifests or logs. Review the command and its write,
network, credential and cost scope under existing host/project authorization
before execution. `--execute-validators` is not an OS sandbox or a permission
grant. Dry-run performs no command execution or evidence writes.

## Evidence And Limits

The existing eval produces validation.json with command/exit status or actual
content-check result, acceptance mapping, tested scope, timestamp and revision
fingerprints. Its hash and the eval.md hash are bound to command evidence.
Completion checks freshness and integrity rather than repeating work.

Relevant input/output changes invalidate verification. Generated caches and
source-control internals are excluded when encountered under an output
directory; explicitly declared input directories are fully fingerprinted,
including cache-named data. Unrelated observer
files outside the declared scope do not invalidate scientific outputs.

Commands have a configurable timeout and bounded stored output. A validator
that changes its own checked artifacts does not pass. Nonzero exits, missing
inputs, missing acceptance coverage and modified evidence block full completion.

Manual/scientific checks remain unverified. A content check can establish that
a citation or uncertainty statement is present; it cannot prove causality,
novelty, source reliability or scientific truth. No general remote-host
attestation or tamper-proof ledger is claimed.

## Scoped Diagnosis

Full doctor retains its original failure semantics. doctor --task-id can label
only a provably unrelated historical missing output as a warning, retaining the
original failed check separately from passed counts. Shared Spec, overlapping
or transitive dependencies, active legacy runs, missing dependency declarations,
custody uncertainty and unknown relevance do not qualify for relaxation.

Permission, provenance, tampering, current-input and binding failures remain
blocking. Optional HTML/observer files are not new mandatory checks. Required
legacy sync remains required; optional local exports do not mean GitHub push,
remote backup or complete multi-chat synchronization.

## Rollout

Build from the installed Step 1 release in an isolated source directory. Preserve
the dirty development checkout. After tests, create a separately versioned local
release, back up the launcher and global rule, atomically switch the launcher,
and repeat installed smoke tests. Rollback restores only the launcher/rule pair,
not work products or evidence created since the backup. No broad adoption.

## Verified Candidate Results

- Full regression: 289 tests passed.
- Guardrail scenarios: 30 passed, 0 failed.
- Clean-distribution smoke: 445 checks passed.
- Management calls remain 12 versus 3 in matched legacy/ordinary engineering
  and research fixtures. This is a command-count comparison, not a user-task
  speed claim. The final full suite took 154.992 seconds on this machine.
- Dry-run confirms byte-identical project contents and no validator execution.
- Independent review found additional boundaries, now covered by regression:
  manual checks cannot be hidden by an automatic pass; missing current inputs
  remain blocking; unbound Spec is not a shared Spec; explicit input data under
  cache-named directories remains relevant; missing criteria can be added
  without deleting prior validators.
- A separate red/green test rejects JSON boolean true as numeric result 1,
  including nested values.

Installed smoke and active-run preservation are recorded in the local deployment
receipt. No repository push or broad project adoption is included.
