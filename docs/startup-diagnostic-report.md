# Startup Diagnostic Report

## Scope

This audit covers startup, project initialization, harness discovery, lifecycle
and completion regressions. It is not a claim that all possible workflows or
model configurations are bug-free. Existing user changes and historical evidence
must remain intact. Machine-specific audit details stay in local diagnostics.

## Reproduced Failures

### Evidence incorrectly treated as configuration

An otherwise healthy project failed doctor because a completed phase's evidence
said `rg CHANGE_ME returned no matches`. The scanner recursively searched every
file under the control plane, including immutable historical records.

Regression: `test_historical_evidence_does_not_poison_placeholder_scan` failed
before the fix. Restrict scanning to YAML/JSON configuration outside evidence
directories. Existing run/context/effect integrity validators remain unchanged.
The negative control verifies that unresolved workspace, mount, workflow and
custom configuration placeholders still fail scanning. Do not rewrite receipts
or use `--allow-placeholders` as a recovery shortcut.

### Initialized command examples were not shell-safe

The guidance renderer correctly quoted paths, but initialization only performed
raw substitutions into a pre-rendered template. Spaces split a root argument;
apostrophes could cause an unmatched quote. The template fingerprint was also
copied rather than computed for the actual project.

Regression: initializing a temporary project with spaces and an apostrophe
produced commands that failed `shlex.split`. Newly written guidance now uses the
existing renderer after configuration materialization. Existing custom AGENTS
files are preserved; dry-run does not create the project. The path assertion
normalizes the macOS `/var` symlink to `/private/var` rather than treating these
identical directories as different targets.

### Harness discovery included cold snapshots

Automatic recursive discovery found control planes under archives, generated
outputs and initialization backups, then proposed changing their mounts as if
they were active projects. Applying that proposal could alter rollback material.

Regression: discovery returned five cold copies in addition to the live parent
and nested child. Discovery now prunes cold-copy directories. Explicitly selected
roots remain supported, including deliberate recovery/audit of an archived copy.
No automatic bulk repair of historical snapshots was performed.

## Validation

- Run `python3 -B -m unittest discover -s tests -p test_startup_regressions.py -v`.
- Run all unit tests and `examples/scenarios/run_guardrail_scenarios.sh`.
- Run `make release-project` and `git diff --check`.
- Recheck the affected live project with ordinary doctor, without relaxed flags.
- Hash historical evidence before and after runtime activation.

Verified in this audit: 247 unit tests passed, 30 guardrail scenarios passed,
and the clean-distribution `release-project` smoke passed. The affected project
passed all 453 doctor checks using the corrected source, without relaxed flags.

Read-only discovery followed by project-only doctor covered 31 live managed
projects: 19 passed and 12 retained project-specific failures. These included
missing outputs of completed tasks, missing historical task-type routes, legacy
route validation steps and one missing completed-run evaluation. Those failures
were not suppressed or relabeled as success. Optional subagent registry warnings
were distinguished from doctor failures. Restoring deleted artifacts or deciding
their retirement requires a separate evidence-preserving project migration.

## Deployment Boundary

The local hotfix must match the audited runtime baseline before replacement.
Back up the original module, record before/after hashes, atomically replace only
the tested module, and retain the existing launcher paths. This reaches both
the shared launcher and existing version-pinned entries without rewriting run
history or changing global permissions. Rollback restores the saved module.

Missing optional runtime registrations are not proof of unavailable model tools
or a reason to invent capability success. Unmanaged folders and stale completed
outputs need separate project-specific decisions; do not manufacture artifacts
to make doctor pass.
