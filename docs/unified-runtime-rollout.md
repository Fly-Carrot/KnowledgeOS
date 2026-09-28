# Unified Runtime Rollout

## Scope

One shared launcher selects a tested runtime. Existing tasks, run histories,
Spec bindings, project strictness and custom global prose are not reset.
Disk updates are not retroactive edits to an open chat's cached context.
At its next substantial operation, an agent reloads the current agent guide.

## Preserved History Safety

Subagents inherit no conversation by default. Adapters explicitly encode
`fork_turns=none` or `fork_context=false` using the actual host schema.
Bounded windows accept only canonical strings `1` through `8`. A boolean-only
host cannot represent that window and must refuse rather than widen access.
Hosts without an explicit supported isolation control are not callable.

Full history requires `--fork-turns all --allow-full-history`, a justification,
and an executed task/run-bound human decision whose summary names both
`fork_turns=all` and the subagent, with `chosen=approve_full_history:<exact-id>`.
Matching command evidence is required; a refusal or a similar ID cannot authorize it.
This is a parent-attested audit record, not cryptographic proof of consent.
The agent must still obtain actual user approval; ordinary delegation does not
authorize sharing all history. A registry cannot persist an `all` default.

## Missing Routes

Prefer an existing task type and route. For an unmatched new task:

```sh
knowledgeos ensure-route --project-root . --task-id T003 --dry-run --json
knowledgeos ensure-route --project-root . --task-id T003 --profile report_task --json
knowledgeos doctor --project-root . --summary
```

`ensure-route` does not invent or edit workflow profiles. It records a task-local
mapping in `.agent-os/workflows/task-routes.json`, validates the existing
lifecycle/eval profile and restricts writes to declared outputs. It preserves
the profile's human gate. Protected, external, wildcard and control-plane
outputs are ineligible. Multiple eligible profiles require an explicit agent
selection, not a new user approval. New permissions still require review.
Existing runs and historical tasks cannot be remapped. Source-profile or task
output changes invalidate a mapping rather than silently changing its scope.

Only missing-route doctor failures permit this narrow recovery before a second
doctor run. It is not a general bypass for unhealthy projects.

## Safe Local Activation

1. Back up the shared launcher, global rule and installed dirty source hashes.
2. Build a versioned source distribution outside active run histories.
3. Test the distribution, then stage the exact launcher and English rule block.
4. Rehearse forward application and rollback in a disposable mirror.
5. Compare old hashes immediately before atomically replacing each file.
6. Verify the real shared entry and sampled projects; preserve rollback files.

Do not replace an entire dirty checkout or bulk rewrite project policies.
Launcher selection supports both PATH invocation and legacy absolute entry
paths. Direct invocation of another checkout's Python module remains a distinct
runtime; global guidance must use the shared entry, not a cached source path.
Exact-model qualification is still separate from deterministic engineering tests.
