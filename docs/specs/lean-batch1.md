# KnowledgeOS Lean Batch 1: Compatible Execution

Status: implemented candidate; validation results live in `docs/LIVE-REPORT.md`.
Date: 2026-09-28
Parent: [Correctness + Lean Orchestration Spec](correctness-lean-v1.md)

## Scope

Batch 1 makes the existing shorter execution path compatible with doctor,
harness repair, and unfinished runs. It does not introduce another scheduler.
The working baseline is candidate commit `b146608`, on top of the previously
published development baseline `4867612`. Preserve both baselines and unrelated
uncommitted work. Implement on an isolated branch, not the installed checkout.

The user-approved sequence remains:

1. Batch 1: compatible execution, reproduction, tests, and recovery boundaries.
2. Batch 2: shorter global/project instructions and a limited project pilot.
3. Batch 3: broader qualification, rollout, and release.

Only Batch 1 is authorized here. No installed CLI replacement, global-rule
replacement, automatic project migration, main-branch merge, or GitHub release.

## Invariants

- Keep task-bound Spec context, per-path write guards, real artifact checks,
  six lifecycle phases, evaluation freshness, and evidence-backed sync.
- Do not remove diagnostics or rewrite historical evidence to simplify a run.
- A cache is not an authorization permit. Recheck scope and current policy.
- Public checkpoint output is not proof that the host displayed it. Agents
  still relay meaningful outcomes under their current instructions.
- A successful command record is not proof of a real tool side effect.
- No new kernel/module/app hierarchy or model-specific bypass is needed.

## Versioned Route Contract

The existing workflow profile in `.agent-os/workflows/router.yaml` gains an
optional `lifecycle_contract` scalar. No additional policy file is introduced.

| Contract | Static route hints | Runtime behavior |
| --- | --- | --- |
| Absent, or `legacy-v1` | Existing explicit dispatch and verification calls | Continue accepting historical manual phases and commands |
| `producer-bound-v1` | Permit omission of repeated dispatch and standalone verification calls | Successful producers record route/dispatch/plan; completion performs final checks |
| Unknown or invalid explicit version | Diagnostic and human review | Do not silently convert it to the legacy contract |

The shorter path is:

```text
doctor -> task/spec binding -> route -> per-path write guards
-> run-task (bind dispatch and route/dispatch checkpoints)
-> context-pack -> plan-task (plan checkpoint)
-> review -> execute -> report (actual evidence and manual checkpoints)
-> eval-task -> complete-task (final verification and postflight)
```

For the short contract, route hints must retain `run-task`, `context-pack`,
`plan-task`, `phase-task`, `eval-task`, and `complete-task` in that order.
Optional explicit dispatch must remain after run creation and before context,
with a run id. Legacy preflight-only dispatch before run creation remains
accepted, but cannot replace run-bound dispatch evidence. Optional standalone
verifiers must precede completion.
These are command hints, not executable shell scripts; mentioning a command
inside prose or `echo` does not satisfy its presence check.

Doctor and harness repair MUST share this contract validator. A valid short
route MUST remain byte-identical after audit or repair. A broken legacy route
may use the existing backed-up repair. Unknown/invalid explicit short contracts
MUST remain unchanged and report review required, rather than guessing an
upgrade or silently lowering checks. Other requested harness repairs retain
their existing behavior.

New run metadata records the route contract used at start. This does not freeze
policy permissions or grant permission to reuse stale evaluations.

## Active Run Compatibility

- Repeated unchanged dispatch reuses its successful command evidence.
- If a crash happened after command recording but before its checkpoint,
  repeating dispatch restores the missing checkpoint, not a fake new call.
- Failed/incomplete command records cannot be reused as successful dispatch.
- Preserve a command-backed legacy manual dispatch decision when its captured
  requirements and tool selection still match. Do not overwrite a public skip
  merely because the newer producer emits an automatic checkpoint.
- A changed plan invalidates that reuse and requires current decisions. Legacy
  evidence without fingerprints cannot prove every historical policy value;
  compatibility is limited to matching captured requirements and tool selection.
- Missing legacy eval fingerprints still require fresh evaluation. Do not
  synthesize fingerprints for past results.
- Matching journaled sync successes are reused. Old `postflight.md` or a
  completed run without an attempt journal must not automatically replay a
  possibly completed external action. Inspect the real side effect first.
  An explicit pending reason remains `PENDING`, never `SYNC_OK`, and preserves
  the old postflight evidence. This batch does not add an automatic migration
  that certifies unverifiable historical sync records.

## Acceptance

Use disposable projects, not real project outputs, for destructive fixtures.

1. New and legacy routes pass appropriate doctor checks; broken routes fail.
2. Audit preview does not write files; short-route repair does not expand it.
3. Unknown contracts require review without router rewrites.
4. A short run completes with real output, review, execution, report, and eval.
5. Missing phases/eval and changed artifacts still block completion.
6. Dispatch retry, legacy skip preservation, and changed-plan invalidation pass.
7. Journaled completion twice invokes a real test hook exactly once; ambiguous
   legacy attempts invoke it zero times until reconciliation.
8. Existing unit tests, guardrail scenarios, repository doctor, and smoke pass.

Tests are in `tests/test_lifecycle_contracts.py`, with existing producer,
completion, runtime, Spec, and end-to-end suites retained. Passing these tests
does not certify every existing conversation, host version, or GPT-5 model.
Cross-model and live-project rollout remain later-batch work.

Cross-directory testing also found a pre-existing launcher import-precedence
defect outside this task's allowed paths. It is documented in LIVE-REPORT and
must be fixed under an appropriately scoped task before global rollout; no
write guard is bypassed to expand this batch.
