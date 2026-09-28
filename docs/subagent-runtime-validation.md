# Subagent Runtime Validation

Date: 2026-07-11
Task: KOS-T087
Spec: SPEC-20260711-001

## Outcome

KnowledgeOS now has command-evidenced validation for the complete runtime-callable subagent catalog:

- `SUBAGENT_CATALOG_OK roles=42/42 native_min=3 invalid=0`
- 3 native Codex roles completed three serial smoke rounds each.
- 39 Maestro adapter roles each completed one live role-contract smoke.
- 48 catalog invocations completed with a unique nonce, matching role id, `cleanup=completed`, and `role_contract=passed`.
- Three additional diagnostic invocations isolated the substantive-task timeout behavior.
- No active runtime gap remained after late-result reconciliation.

This validates invocation, role-prompt loading, result delivery, and cleanup through parent-recorded runtime attestations. It is not a deep benchmark of every specialist domain or an independent host-runtime audit.

## Root Cause

The earlier `codex-explorer` symptom was reproducible only for substantive work, not for minimal runtime smokes:

1. `codex-default`, `codex-explorer`, and `codex-worker` each completed three minimal serial smokes.
2. A real read-only code-review task exceeded a fixed 120-second wait on both `codex-explorer` and `codex-default`.
3. The explorer returned a valid late result without intervention.
4. The default agent returned valid current findings after one interrupt request.
5. Both agents closed successfully.
6. A later Maestro code-review run inherited parent-level lifecycle behavior and attempted nested delegation instead of directly reviewing the diff.

The defect was therefore not an explorer adapter mapping failure. The operational failure combined a fixed short wait, lost recovery context, and missing boundaries between parent orchestration and bounded subagent execution.

## Repair

### Strict catalog verifier

`verify-subagents` reads the registered runtime-callable catalog and the run capability ledger. A role counts only when its evidence contains:

```text
SUBAGENT_SMOKE_OK id=<registered-id> nonce=<unique-nonce>
cleanup=completed
role_contract=passed
adapter_challenge=<challenge from subagent-adapter>
```

The verifier:

- counts unique role ids rather than raw events;
- locks the target catalog in a run-level snapshot before validation;
- validates snapshot schema, task/run binding, UTC timestamp, evidence model, catalog hash, and full snapshot integrity;
- counts unique nonces for native stability;
- rejects unknown roles and malformed strict evidence;
- rejects catalog drift and challenge-free attestations;
- consumes each adapter challenge once, so one adapter issuance cannot prove multiple executions;
- enforces a native minimum floor of three rather than allowing callers to weaken it;
- does not count `timed_out`, `blocked`, `skipped`, or cleanup failures;
- emits `SUBAGENT_CATALOG_OK` only after full coverage.

### Runtime-gap reconciliation

`dispatch-report` now:

- keeps safety-policy `blocked` events visible without calling them runtime failures;
- treats timeout, interruption, orphaning, errors, and close failures as runtime gaps;
- treats explicit `failed` or cancelled subagent events as runtime gaps rather than successful invocations;
- recognizes a later completed event with `recovered_from=timed_out` as a resolved gap;
- binds each recovery to one exact timeout with `--recovers-event-id`, preventing one completion from clearing multiple failures;
- reports unique agent ids separately from raw capability-event counts.

### Host runtime usage contract

Startup prompts and agent guidance now require:

- preserving every spawned agent id;
- one multi-minute wait for substantive work instead of repeated short polls;
- one interrupt requesting current findings after a timeout;
- one recovery wait;
- closing only after a terminal result;
- recording late completion as recovered evidence.

### Bounded subagent runtime boundary

Every adapter role prompt now states that a spawned specialist:

- works directly on the parent-assigned scope;
- returns findings to the parent;
- does not create or reopen KnowledgeOS tasks/specs;
- does not run completion or postflight;
- does not recursively dispatch another subagent unless orchestration was explicitly delegated.

This keeps the parent Agent responsible for lifecycle and capability evidence and prevents accidental recursive delegation.

KnowledgeOS still does not spawn agents from the shell. The Codex host performs delegation; KnowledgeOS resolves roles and verifies public evidence.

The evidence model is explicitly `parent_attested_runtime`. `host_runtime_verified=false` means the CLI cannot independently inspect Codex's private tool-call log. The adapter challenge, immutable run catalog snapshot, result marker, cleanup record, and role-contract record make the parent attestation auditable and resistant to accidental or stale evidence, but they are not a cryptographic host signature.

## Verified Catalog

### Default-backed (1)

- `codex-default`

### Explorer-backed (17)

- `codex-explorer`
- `maestro-accessibility-specialist`
- `maestro-api-designer`
- `maestro-architect`
- `maestro-cloud-architect`
- `maestro-code-reviewer`
- `maestro-compliance-reviewer`
- `maestro-content-strategist`
- `maestro-database-administrator`
- `maestro-db2-dba`
- `maestro-debugger`
- `maestro-performance-engineer`
- `maestro-security-engineer`
- `maestro-seo-specialist`
- `maestro-site-reliability-engineer`
- `maestro-solutions-architect`
- `maestro-zos-sysprog`

### Worker-backed (24)

- `codex-worker`
- `maestro-analytics-engineer`
- `maestro-cobol-engineer`
- `maestro-coder`
- `maestro-copywriter`
- `maestro-data-engineer`
- `maestro-design-system-engineer`
- `maestro-devops-engineer`
- `maestro-hlasm-assembler-specialist`
- `maestro-i18n-specialist`
- `maestro-ibm-i-specialist`
- `maestro-integration-engineer`
- `maestro-ml-engineer`
- `maestro-mlops-engineer`
- `maestro-mobile-engineer`
- `maestro-observability-engineer`
- `maestro-platform-engineer`
- `maestro-product-manager`
- `maestro-prompt-engineer`
- `maestro-refactor`
- `maestro-release-manager`
- `maestro-technical-writer`
- `maestro-tester`
- `maestro-ux-designer`

## Verification Commands

```bash
./bin/knowledgeos verify-subagents \
  --project-root . \
  --task-id KOS-T087 \
  --run-id RUN-20260711-202846-KOS-T087 \
  --native-min-successes 3

python3 -B -m py_compile knowledgeos/cli.py
python3 -B -m unittest discover -s tests -v
./examples/scenarios/run_guardrail_scenarios.sh
./bin/knowledgeos doctor --project-root . --summary
git diff --check
```

## Evidence Boundary

Canonical evidence remains in Markdown, YAML, and NDJSON. The HTML report is a presentation sidecar and is not the source of truth. Public artifacts intentionally omit local absolute paths, runtime agent ids, and credentials.
