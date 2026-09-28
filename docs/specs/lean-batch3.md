# Lean Batch 3: Qualified Candidate Publication

Date: 2026-09-28
Parent: [Correctness + Lean Orchestration](correctness-lean-v1.md)
Status: candidate release; exact-model qualification explicitly deferred

## Authorized Scope

The user selected engineering-qualified candidate publication first. Execute
broader deterministic validation and publish the reviewed Batch 1/2 changes
plus release fixes to the existing candidate PR. Do not merge main, create a
stable tag, replace the independently dirty installed kernel, or migrate every
project. This is the release track, not completion of the parent model matrix.

## Acceptance

1. Freeze the public source tree and test an export without private local
   runtime folders. Use real templates to initialize disposable runtime and
   project state; run full doctor, routes, capability-path checks and write
   guards against that state. Missing public source and forbidden writes must
   still fail. The maintainer's historical tasks are not release fixtures.
2. Keep `make smoke` for local repository history and add `make release-smoke`
   for downloadable source. Both retain guardrail scenarios and the full test
   suite. Never fabricate missing historical artifacts or skip doctor errors.
3. Retain Batch 1/2 negative gates, legacy/short-route and guided/compact
   pilots, active-run/custom-rule preservation and rollback checks.
4. Inspect the public diff and publication tree for credentials, private home
   paths and newly included local ledgers. Stage exact reviewed files only.
   Preserve all unrelated installed and candidate work.
5. Update the existing candidate PR, retaining its development base and draft
   status. Record the exact commit, public tree, validation counts and limits.
   A local SYNC_OK is not proof of a GitHub push.

## Qualification Boundary

All exact model IDs remain **untested** under the parent Spec's full matrix.
No GPT-5/GPT-6 compatibility or performance qualification is inferred from a
single subagent review or a deterministic fixture. Unverified models retain
guided instructions and the same safety gates. The full matrix, broad live
rollout, stable release and main merge need their own observed evidence and
authorization; this candidate publication does not certify them.

## Recovery

Publication does not switch the installed launcher or global entry. Existing
Batch 2 hash-guarded backups stay local. A clean checkout at the candidate
commit can be evaluated independently; existing runs must not be silently
restarted or handed back to a client that cannot interpret their records.
Do not force-push, rewrite release history, or discard unrelated dirty work.
