"""Versioned, model-neutral guidance; rendering never changes project policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shlex


CONTRACT_VERSION = 'kos-guidance-v1'
BEGIN = '<!-- KNOWLEDGEOS:GUIDANCE:BEGIN -->'
END = '<!-- KNOWLEDGEOS:GUIDANCE:END -->'
CONFIG_FILES = (
    'workspace.yaml', 'project.yaml', 'fabric-link.yaml', 'read-policy.yaml',
    'write-policy.yaml', 'dispatch-policy.yaml', 'phase-policy.yaml',
    'decision-policy.yaml', 'effect-policy.yaml', 'capabilities.yaml',
    'tool-registry.yaml',
)
SAFETY_RULES = (
    'Start every conversation with KOS_DECISION: project_state (managed, unmanaged, blocked), work_class (simple, substantial, blocked), required_flow (answer-only, task, spec, thread-plan, full lifecycle), and a concise public reason. Simple non-mutating replies may use answer-only.',
    'Use doctor first for managed projects; stop on failure. Report BOOT_OK only after successful command evidence and any required fabric boot hook. If .agent-os/ is absent, report KOS_UNMANAGED, do not claim managed safety, and ask before initialization.',
    'All models and both guidance modes use the same path, permission, artifact, lifecycle, validator, event, and sync gates. Project strictness (warn/enforce/off) is not changed by presentation, model names, or caches.',
    'Preserve user tone, confirmed scope, and custom restrictions. Load applicable policy from .agent-os/ and linked kernel/capability roots. Apply only defined configuration precedence; disclose conflicting sources and stop affected work rather than silently overriding restrictions.',
    'Before each mutation, check-route-write every planned path against current policy: immutable paths are denied, human-gated paths require valid approval, and unclassified paths require triage. Authorization is bounded by operation, target, scope, expiry, and project/host gates; never treat cached dispatch as permanent write permission.',
    'Keep route -> plan -> review -> dispatch -> execute -> report explicit. Use phase-task for real checkpoint evidence; review and execute require actual evidence, never automatic success from a plan or placeholder. Relay CHECKPOINT_OK only when returned; CLI output alone does not prove user visibility.',
    'Keep registered, adapter-resolvable, host-available, and execution-verified capabilities distinct. Resolve subagent-adapter when applicable, then use the real host schema; registry entries or bare Maestro do not prove a callable runtime. Log failures, warnings, pending states, and policy-backed skips with public reasons.',
    'A bounded spawned subagent executes only the parent-assigned scope: no new/reopened tasks or specs, completion/postflight, or recursive delegation unless explicitly assigned orchestration. Preserve every spawn id, wait once for several minutes, then on timeout request findings once and wait once more; close only after a terminal result. Record late recovery with recovered_from=timed_out.',
    'Use trace-step, capability-event, decision-event, and artifact-assert for public operational evidence, actual capabilities, material decisions, and real effects. Never manually fabricate spec snapshots, context packs, plans, ledgers, review, eval, execution, or sync. A written log is not tool success or a tamper-proof safety boundary.',
    'At consultation checkpoints state a recommendation and tradeoff; ask when applicable policy or risk requires human confirmation, not merely because a model name changed.',
    'Use eval-task for real acceptance, then complete-task as the final gate for spec/context/plan, lifecycle, effects, decisions, full capability dispatch, and required postflight. Missing or stale evidence is not success. Never claim successful completion on an earlier eval alone.',
    'Relay returned TRACE_OK, CAPABILITY_OK, DECISION_OK, EFFECT_OK, and AGENT_DISPATCH_PLAN only with command evidence. Final substantial reports include AGENT_DISPATCH_OK and the full capability dispatch report: agents invoked/skipped (explain agents=0), MCP, skills, plugins/apps, browser/Chrome/GitHub/security connectors, scripts, shell, file reads, evidence files, and gaps. Include returned FLOW_OK for medium/high/complex work; SYNC_OK only when complete-task returns sync_status: SYNC_OK.',
)


def configuration_fingerprint(project_root: Path | str) -> str:
    """Fingerprint applicable config bytes, not historical task/eval ledgers."""
    root = Path(project_root) / '.agent-os'
    values = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              if (root / name).is_file() else None for name in CONFIG_FILES}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def guidance_mode(project_root: Path | str) -> str:
    """Only project.guidance_mode is supported; never infer mode from model id."""
    path = Path(project_root) / '.agent-os/project.yaml'
    if not path.exists():
        return 'guided'
    found = []
    in_project = False
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if line.strip() and not line.lstrip().startswith('#') and not line.startswith((' ', '\t')):
            in_project = line.strip() == 'project:'
        if re.match(r'\s*guidance_mode\s*:', line):
            if not in_project or not line.startswith('  guidance_mode:'):
                raise ValueError(f'{path}:{number}: guidance_mode must be project.guidance_mode')
            value = line.split(':', 1)[1].split('#', 1)[0].strip().strip('\"\'')
            found.append((number, value))
    if len(found) > 1:
        raise ValueError(f'{path}: conflicting guidance_mode declarations: {found}')
    value = found[0][1] if found else 'guided'
    if value not in ('compact', 'guided'):
        raise ValueError(f'{path}: unsupported guidance_mode {value!r}; use compact or guided')
    return value


def render_guidance(project_root: Path | str, bin_path: Path | str, *,
                    surface: str = 'guide', mode: str | None = None) -> str:
    titles = {'guide': 'KnowledgeOS Agent Guide', 'startup': 'KnowledgeOS Startup Prompt',
              'entry': 'Agent Entry Contract'}
    selected = guidance_mode(project_root)
    if mode is not None:
        selected = mode
    if selected not in ('compact', 'guided'):
        raise ValueError(f'unsupported guidance_mode {selected!r}')
    command = f'{shlex.quote(str(bin_path))} {{}} --project-root {shlex.quote(str(project_root))}'
    task = ' --task-id <task-id>'
    run = task + ' --run-id <run-id>'
    lines = [BEGIN, f'# {titles[surface]}', '',
             '<!-- Generated by knowledgeos.guidance; do not edit this block. Custom rules belong outside it. -->',
             f'contract_version: {CONTRACT_VERSION}',
             f'configuration_fingerprint: {configuration_fingerprint(project_root)}',
             f'guidance_mode: {selected}', '', f'Project root: `{project_root}`', '',
             '## Safety', '', *[f'- {rule}' for rule in SAFETY_RULES], '',
             '## Normal Path', '',
             '1. Read AGENTS.md and applicable configuration; keep only current task, related Spec/Plan, valid permissions, enabled checks, and reference index in active context. Do not load historical ledgers wholesale; archive/** is cold storage.',
             '2. Run doctor; select one ready task. Route with route-task, preflight dispatch-task, and check-route-write before mutations. Use run-task to bind the preflight plan, checking the returned run-bound dispatch evidence and reused/recomputed reason, then context-pack and plan-task. Do not repeat dispatch on the normal path. Missing binding evidence requires the compatibility diagnostic below before execution; reuse never replaces current authorization or write checks.',
             '3. Execute scoped work with explicit phase-task checkpoints and real trace-step, capability-event, decision-event, and artifact-assert evidence. Do not substitute a planned review for an actual review.',
             '4. Run eval-task, then complete-task. Relay its actual final gate result, full capability summary, FLOW_OK when required, and evidenced sync status.', '']
    if selected == 'guided':
        lines += ['### Parameter Examples', '']
        for name, args in (
            ('doctor', ' --summary'), ('route-task', task), ('dispatch-task', task),
            ('check-route-write', task + ' --path <planned-path>'), ('run-task', task),
            ('context-pack', run),
            ('plan-task', run + ' --summary "<summary>"'),
            ('phase-task', run + ' --phase <route|plan|review|dispatch|execute|report> --status completed --note "<public summary>" --evidence "<actual evidence>"'),
            ('trace-step', run + ' --step <step> --note "<public summary>" --evidence "<evidence>"'),
            ('capability-event', run + ' --kind <kind> --id <capability-id> --purpose "<purpose>"'),
            ('decision-event', run + ' --kind <kind> --title "<title>" --summary "<summary>" --reason "<reason>" --evidence "<evidence>"'),
            ('artifact-assert', run + ' --kind <kind> --path <artifact>'),
            ('eval-task', run), ('complete-task', run + ' --summary "<summary>"'),
        ):
            lines.append(f'- `{command.format(name)}{args}`')
        lines.append('')
    lines += ['## Contextual Index', '',
              '- Configuration: .agent-os/workspace.yaml, project.yaml, fabric-link.yaml, read-policy.yaml, write-policy.yaml, dispatch-policy.yaml, phase-policy.yaml, decision-policy.yaml, effect-policy.yaml, capabilities.yaml, tool-registry.yaml. Use tool-registry to inspect configured candidates, not to assert host availability.',
              '- Current context: .agent-os/tasks.yaml, specs.yaml, relevant decisions.yaml/evals.yaml entries, and the current .agent-os/runs/ envelope. Do not choose an unrelated active Spec as the task contract.',
              '- Spec request: create-spec or align-spec before execution. Durable plan: thread-plan current/start; append plain-language changes and link-run; relay returned THREAD_PLAN_OK. New unmatched work: create-task. Same-task rejected result: reopen-task, not unrelated intake.',
              '- Diagnostics/manual audit/legacy clients (not repetitive mandatory pre-completion calls): verify-context, verify-lifecycle, verify-effects (EFFECT_VERIFY_OK), verify-decisions (DECISION_VERIFY_OK), dispatch-report (AGENT_DISPATCH_OK). These commands remain available; complete-task owns final enforcement and reporting.',
              '- Dispatch compatibility diagnostic: if run-task returns no run-bound dispatch evidence, use dispatch-task --run-id with the current project/task/run before execution. Legacy explicit calls remain supported; inspect reused/recomputed and its reason rather than assuming a cached plan grants permission.',
              '- Explicit catalog validation: verify-subagents; SUBAGENT_CATALOG_OK needs strict unique-role, challenge-bound evidence, not adapter resolution or duplicate events. No claim of independent host verification.',
              '- Reset: reset-project --mode <soft|hard> --dry-run first. Migration: migrate-legacy-project --write-plan first. Cold storage: archive-legacy-project --write-plan first. Show the plan and obtain required human approval before --apply or destructive actions.',
              '- Human-readable Mission Flow: flow-summary; relay actual FLOW_OK using simple labels such as Goal, Safe Writes, Work Done, Proof, and Finish.',
              '- Evidence references: capability-events.ndjson, command-events.ndjson, dispatch-report.md in the relevant run. Use command help for specialty parameters rather than loading all historical instructions.',
              '', END, '']
    return '\n'.join(lines)


def merge_generated(existing: str, generated: str) -> str:
    """Replace only our marked block; unknown legacy/custom text needs review."""
    if not existing:
        return generated
    if existing.count(BEGIN) != 1 or existing.count(END) != 1:
        raise ValueError('refusing to overwrite unmarked or ambiguous custom guidance; choose a new output path')
    start, end = existing.index(BEGIN), existing.index(END) + len(END)
    if start >= end - len(END):
        raise ValueError('invalid guidance block order')
    return existing[:start] + generated.rstrip('\n') + existing[end:]
