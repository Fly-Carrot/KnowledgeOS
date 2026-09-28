# Lean Batch 3 Candidate Validation

Date: 2026-09-28
Scope: [Batch 3 Spec](../specs/lean-batch3.md)
Baseline: `b146608`, the previously published correctness/lean candidate
Publication target: existing `codex/correctness-lean-v1` draft PR against
`codex/thread-plan-ledger-hardening`, not `main`

## Reproduced Problems And Minimal Repairs

| Problem | Before repair | Repair and regression |
| --- | --- | --- |
| A clean source export depends on private maintainer history | `make smoke` fails ten completed-output checks for ignored local runtime/migration files | New `make release-smoke` creates a real disposable runtime/project and runs all release checks. Local smoke and doctor are unchanged; missing public source still fails. |
| Two doctor tests reuse the developer checkout as their healthy fixture | The first full clean-export run fails the summary and relative-path tests on the same absent private artifacts | Initialize independent real projects for both tests. Keep all summary assertions and verify that deleting a relative-linked kernel schema still causes failure. |
| Valid legacy interleaved checkpoints are rejected | A route checkpoint after run-bound dispatch but before context/plan yields `plan-task must precede phase-task`; repair proposes rewriting a valid legacy router | Legacy checkpoints may occur between run creation and evaluation. Tests cover implicit/explicit legacy contracts, routing, doctor and byte-identical audit/repair. Invalid envelope boundaries and short-contract ordering still fail. |

The clean-export failure was observed before implementation; both new
regressions failed before their corresponding fixes. A bounded read-only agent
identified the legacy case; the parent reproduced it and implemented the fix.
No native-role, cryptographic attestation or full repository security
certification is implied by that review.

## Verification

- Clean-export `make release-smoke`: **214 tests passed**, **30 guardrail
  scenarios passed**. Fresh runtime/project doctor: **401/401 passed**.
- Targeted release/legacy checks: **17 passed**. The two previously
  environment-dependent doctor tests also passed their isolated rerun.
- Candidate repository doctor: **1,602/1,602 passed** at verification time;
  independently installed repository doctor: **2,082/2,082 passed**, with no
  installed file changes.
- Python compilation, shell syntax, public path/credential-pattern scans,
  new documentation links and `git diff --check` passed. These are bounded
  checks and review, not a complete security-service audit or a guarantee
  against all undiscovered defects.
- Existing tests retain Spec isolation, stale artifact/eval refusal,
  unavailable tools, permissions, six phases, idempotent dispatch/sync,
  custom-rule preservation and rollback coverage. Legacy explicit phase hints
  and producer-bound short hints remain separate supported contracts.

## Installation And Publication Boundaries

- The independently dirty installed checkout and current global rule are not
  replaced. The Batch 2 migration hashes still match for both installed targets
  and all 192 other captured tracked files.
- New local tasks, Specs, thread history, private backups, runtime snapshots
  and run receipts are excluded from staging. Public templates remain generic.
  Pre-existing tracked repository build metadata is not rewritten to fake a
  clean doctor; release validation uses a fresh project instead.
- No live project is migrated, no running conversation is restarted and no
  older Workbench bundle is rebuilt. Source publication is not global rollout.
- Exact-model matrix: **untested / explicitly deferred by the user**. This
  includes GPT-5-family and GPT-6-family qualification under the parent Spec.
  Keep guided as default; neither instruction mode weakens safety gates.
- Publication proof is the actual PR head commit and remote ref, not SYNC_OK.
  No stable tag or main merge is part of this candidate update.

## Reproduce From The Candidate Source

```sh
make release-smoke
python3 -B -m unittest tests.test_lifecycle_contracts tests.test_release_portability -v
python3 -B -m py_compile knowledgeos/cli.py knowledgeos/guidance.py
git diff --check
```

`release-smoke` initializes only disposable state, not an existing project.
Use the normal project doctor and explicit versioned migration/rollback process
before switching any live project. Failures remain failures; passing fixtures
does not certify every host, model or active historical run.
