#!/usr/bin/env python3
"""KnowledgeOS executable control plane.

The bootstrap path intentionally uses only the Python standard library. The
parser supports KnowledgeOS' own small YAML-like templates; richer schema
validation can come later without making the bootstrap path fragile.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import html as html_lib
import ipaddress
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

REQUIRED_PUBLIC_FILES = [
    "README.md",
    "CHANGELOG.md",
    "docs/LIVE-REPORT.md",
    "docs/architecture.md",
    "docs/write-guard.md",
    "docs/orchestration.md",
    "docs/quickstart.md",
    "docs/migration-boundary.md",
    "docs/executable-control-plane.md",
    "docs/doctor-guardrails.md",
    "docs/workflow-router.md",
    "docs/tool-registry.md",
    "docs/route-bound-execution-guard.md",
    "docs/capability-orchestration.md",
    "docs/spec-context-plan.md",
    "docs/reset-and-migration.md",
    "docs/archive-policy.md",
    "docs/decision-graph-module.md",
    "docs/thread-plan-ledger.md",
    "templates/governance-core/README.md",
    "templates/governance-core/STRUCTURE-CHECK.md",
    "templates/governance-core/rules/global.md",
    "templates/governance-core/rules/runtime.md",
    "templates/governance-core/hooks/before-task.sh",
    "templates/governance-core/hooks/log-phase.sh",
    "templates/governance-core/hooks/after-task.sh",
    "templates/governance-core/registries/mcp.example.yaml",
    "templates/governance-core/registries/skills.example.yaml",
    "templates/governance-core/registries/workflows.example.yaml",
    "templates/governance-core/schemas/phase-contract.md",
    "templates/governance-core/schemas/memory-lanes.md",
    "templates/governance-core/schemas/postflight-contract.md",
    "templates/governance-core/memory/decision-log.ndjson",
    "templates/governance-core/memory/handoffs.ndjson",
    "templates/governance-core/memory/open-loops.ndjson",
    "templates/governance-core/memory/promoted-learnings.ndjson",
    "templates/governance-core/memory/user-question-profiles.ndjson",
    "templates/governance-core/sync/receipts.ndjson",
    "templates/governance-core/sync/task-phases.ndjson",
    "templates/governance-core/sync/import-state.json",
    "templates/capability-layer/README.md",
    "templates/capability-layer/STRUCTURE-CHECK.md",
    "templates/capability-layer/subagents/maestro/manifest.yaml",
    "templates/project-control-plane/AGENTS.md",
    "examples/scenarios/README.md",
    "examples/scenarios/distracted-agent-guardrails.md",
    "examples/scenarios/run_guardrail_scenarios.sh",
    "templates/project-control-plane/.agent-os/workspace.yaml",
    "templates/project-control-plane/.agent-os/project.yaml",
    "templates/project-control-plane/.agent-os/startup-prompt.md",
    "templates/project-control-plane/.agent-os/tasks.yaml",
    "templates/project-control-plane/.agent-os/specs.yaml",
    "templates/project-control-plane/.agent-os/phase-policy.yaml",
    "templates/project-control-plane/.agent-os/decision-policy.yaml",
    "templates/project-control-plane/.agent-os/effect-policy.yaml",
    "templates/project-control-plane/.agent-os/read-policy.yaml",
    "templates/project-control-plane/.agent-os/write-policy.yaml",
    "templates/project-control-plane/archive/README.md",
    "templates/project-control-plane/.agent-os/capabilities.yaml",
    "templates/project-control-plane/.agent-os/dispatch-policy.yaml",
    "templates/project-control-plane/.agent-os/workflows/router.yaml",
    "templates/project-control-plane/.agent-os/tool-registry.yaml",
]

REQUIRED_PROJECT_FILES = [
    "AGENTS.md",
    ".agent-os/workspace.yaml",
    ".agent-os/project.yaml",
    ".agent-os/startup-prompt.md",
    ".agent-os/tasks.yaml",
    ".agent-os/specs.yaml",
    ".agent-os/phase-policy.yaml",
    ".agent-os/decisions.yaml",
    ".agent-os/evals.yaml",
    ".agent-os/artifacts.yaml",
    ".agent-os/fabric-link.yaml",
    ".agent-os/capabilities.yaml",
    ".agent-os/dispatch-policy.yaml",
    ".agent-os/read-policy.yaml",
    ".agent-os/write-policy.yaml",
    ".agent-os/workflows/router.yaml",
    ".agent-os/tool-registry.yaml",
]

REQUIRED_KERNEL_DIRS = ["rules", "hooks", "registries", "memory", "sync", "schemas"]
REQUIRED_KERNEL_FILES = [
    "hooks/before-task.sh",
    "schemas/phase-contract.md",
]
KERNEL_SKELETON_TEMPLATE_FILES = [
    "registries/mcp.example.yaml",
    "registries/skills.example.yaml",
    "registries/workflows.example.yaml",
    "schemas/phase-contract.md",
    "schemas/memory-lanes.md",
    "schemas/postflight-contract.md",
]

PUBLIC_FORBIDDEN_NEEDLES = [
    str(Path.home()) + "/",
    "API" + "_KEY=",
    "SECRET" + "=",
    "TOKEN" + "=",
    "secrets" + ".yaml",
]

WRITE_POLICY_SECTIONS = {
    "immutable",
    "controlled",
    "forbidden_without_human_gate",
    "require_receipt_for",
}
LOCAL_EXTERNAL_WRITE_POLICY_SECTIONS = {
    "external_controlled",
    "external_forbidden_without_human_gate",
    "external_require_receipt_for",
}
READ_POLICY_SECTIONS = {
    "default_context",
    "cold_storage",
    "require_explicit_human_request",
    "deny_indexing",
}

EXPECTED_PHASE_KEYS = ["route", "plan", "review", "dispatch", "execute", "report"]
PHASE_STATUSES = {"completed", "skipped"}
CAPABILITY_EVENT_KINDS = {
    "app",
    "browser",
    "chrome",
    "file_read",
    "github",
    "mcp",
    "plugin",
    "script",
    "security",
    "shell",
    "skill",
    "subagent",
    "orchestrator",
}
AGENT_CAPABILITY_KINDS = {"orchestrator", "subagent"}
SKIPPED_CAPABILITY_STATUSES = {"skipped", "skip", "not_needed", "not-needed", "timed_out", "timed-out", "timeout", "blocked", "close_failed", "close-failed"}
RUNTIME_GAP_CAPABILITY_STATUSES = {"timed_out", "timed-out", "timeout", "blocked", "close_failed", "close-failed"}
EFFECT_STRICTNESS_LEVELS = {"observe", "warn", "enforce", "off"}
DECISION_STRICTNESS_LEVELS = {"warn", "enforce", "off"}
DECISION_EVENT_KINDS = {
    "plan_node",
    "branch_opened",
    "branch_selected",
    "step_inserted",
    "branch_abandoned",
    "rollback",
    "superseded",
    "deferred",
    "human_decision",
    "risk_tradeoff",
    "final_decision",
}
DECISION_EVENT_STATUSES = {
    "planned",
    "active",
    "selected",
    "executed",
    "skipped",
    "abandoned",
    "rolled_back",
    "superseded",
    "deferred",
    "blocked",
}
DECISION_EXPLANATION_REQUIRED_KINDS = {"branch_abandoned", "rollback", "superseded"}
THREAD_PLAN_EVENT_KINDS = {"plan", "phase", "branch", "decision", "progress", "change", "summary"}
THREAD_PLAN_MARKER = "THREAD_PLAN_OK"
EFFECT_ASSERTION_KINDS = {
    "file_exists",
    "file_nonempty",
    "file_contains",
    "file_sha256",
    "file_changed",
    "json_key_equals",
    "html_self_contained",
}
OPERATIONAL_TRACE_STEPS = [
    "user_intent",
    "load_rules",
    "doctor_gate",
    "task_intake",
    "spec_alignment",
    "route_guard",
    "dispatch_plan",
    "write_guard",
    "run_envelope",
    "run_dispatch",
    "context_pack",
    "plan_task",
    "execution",
    "capability_visibility",
    "phase_checkpoints",
    "eval",
    "verify",
    "complete",
    "sync",
    "handoff",
]
LIFECYCLE_ROUTE_COMMANDS = [
    "dispatch-task --project-root . --task-id <task-id> --run-id <run-id>",
    "context-pack --project-root . --task-id <task-id> --run-id <run-id>",
    "plan-task --project-root . --task-id <task-id> --run-id <run-id> --summary <summary>",
    "phase-task --project-root . --task-id <task-id> --run-id <run-id> --phase <phase> --status completed --note <public-trace> --evidence <evidence>",
    "eval-task --project-root . --task-id <task-id> --run-id <run-id>",
    "verify-context --project-root . --task-id <task-id> --run-id <run-id>",
    "verify-lifecycle --project-root . --task-id <task-id> --run-id <run-id>",
    "verify-effects --project-root . --task-id <task-id> --run-id <run-id>",
    "complete-task --project-root . --task-id <task-id> --run-id <run-id> --summary <summary>",
]
LIFECYCLE_COMMAND_MARKERS = [
    "context-pack",
    "plan-task",
    "dispatch-task",
    "phase-task",
    "eval-task",
    "verify-context",
    "verify-lifecycle",
    "verify-effects",
    "complete-task",
]
TASK_STATUSES = {"backlog", "ready", "in_progress", "blocked", "completed", "cancelled"}
RUNNABLE_TASK_STATUSES = {"ready", "in_progress"}
TOOL_KINDS = {"mcp", "skill", "workflow", "orchestrator", "subagent", "memory"}
TOOL_STATUSES = {"enabled", "disabled", "optional", "recommended", "configured", "indexed"}
ACTIVE_TOOL_STATUSES = {"enabled", "recommended", "configured", "indexed"}
CODEX_RUNTIME_TOOL = "multi_agent_v1.spawn_agent"
CODEX_RUNTIME_AGENT_TYPES = {"default", "explorer", "worker"}
SUBAGENT_CANDIDATE_LIMIT = 3
CODEX_NATIVE_SUBAGENTS = [
    {
        "id": "codex-default",
        "runtime_agent_type": "default",
        "task_fit": "capability_orchestration,knowledge_structuring,report_task,documentation_task",
        "capability_fit": "codex_native,default_agent,general_execution",
        "scope": "codex-native-subagent",
    },
    {
        "id": "codex-explorer",
        "runtime_agent_type": "explorer",
        "task_fit": "research_task,documentation_task,analysis_task,security_audit,architecture_design",
        "capability_fit": "codex_native,exploration,read_only,research",
        "scope": "codex-native-subagent",
    },
    {
        "id": "codex-worker",
        "runtime_agent_type": "worker",
        "task_fit": "engineering_change,route_bound_execution_guard,executable_control_plane,workflow_routing,tool_registry",
        "capability_fit": "codex_native,implementation,read_write,tests",
        "scope": "codex-native-subagent",
    },
]
SUBAGENT_PREFERENCES_BY_TASK = {
    "analysis_task": ["codex-explorer", "maestro-analytics-engineer", "codex-default"],
    "architecture_design": ["maestro-architect", "codex-explorer", "maestro-api-designer"],
    "capability_orchestration": ["codex-default", "maestro-architect", "maestro-coder"],
    "documentation_task": ["codex-explorer", "maestro-technical-writer", "codex-default"],
    "engineering_change": ["codex-worker", "maestro-coder", "maestro-code-reviewer"],
    "executable_control_plane": ["codex-worker", "maestro-architect", "maestro-coder"],
    "report_task": ["codex-default", "codex-explorer", "maestro-technical-writer"],
    "route_bound_execution_guard": ["codex-worker", "maestro-coder", "maestro-code-reviewer"],
    "security_audit": ["maestro-security-engineer", "maestro-code-reviewer", "codex-explorer"],
    "tool_registry": ["codex-worker", "maestro-architect", "codex-default"],
    "workflow_routing": ["codex-worker", "maestro-architect", "maestro-coder"],
}
DISPATCH_POLICY_SECTIONS = {
    "default_order",
    "always_consult_before",
    "consult_for_risks",
    "branch_builder_task_types",
    "subagent_task_types",
    "mcp_task_types",
    "skill_task_types",
    "script_task_types",
    "human_gate_for",
}
REQUIRED_AGENT_GUIDE_FILES = [
    "AGENTS.md",
    ".agent-os/workspace.yaml",
    ".agent-os/project.yaml",
    ".agent-os/startup-prompt.md",
    ".agent-os/tasks.yaml",
    ".agent-os/specs.yaml",
    ".agent-os/phase-policy.yaml",
    ".agent-os/decisions.yaml",
    ".agent-os/evals.yaml",
    ".agent-os/capabilities.yaml",
    ".agent-os/dispatch-policy.yaml",
    ".agent-os/read-policy.yaml",
    ".agent-os/write-policy.yaml",
    ".agent-os/tool-registry.yaml",
]
BROAD_PROJECT_NAMES = {
    "",
    "Users",
    "Desktop",
    "Downloads",
    "Documents",
    "Library",
    "Applications",
    "System",
    "Volumes",
    "tmp",
    "var",
}
RESETTABLE_STATUS_DEFAULTS = {"completed", "in_progress", "blocked"}
CANONICAL_PROJECT_DIRS = {
    ".agent-os",
    ".agents",
    ".git",
    ".knowledgeos-local",
    ".knowledgeos-reset-backups",
    "archive",
    "bin",
    "capability-layer",
    "materials",
    "knowledge",
    "knowledgeos",
    "global-agent-fabric",
    "src",
    "tests",
    "notebooks",
    "scripts",
    "data",
    "outputs",
    "reports",
    "docs",
    "examples",
    "templates",
}


@dataclass
class CheckResult:
    ok: bool
    label: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "label": self.label, "detail": self.detail}


def knowledgeos_root_from_file() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_root(value: str | None) -> Path:
    return Path(value).expanduser().resolve() if value else knowledgeos_root_from_file()


def resolve_project_config_path(project_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def date_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-.") or "item"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def content_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_files(root: Path, relative_paths: Iterable[str]) -> Iterable[Path]:
    for rel in relative_paths:
        yield root / rel


def scan_public_content(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    scan_roots = [root / "README.md", root / "CHANGELOG.md", root / "docs", root / "templates"]
    for base in scan_roots:
        if not base.exists():
            continue
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
        for path in files:
            try:
                text = read_text(path)
            except UnicodeDecodeError:
                continue
            rel = path.relative_to(root)
            for needle in PUBLIC_FORBIDDEN_NEEDLES:
                if needle in text:
                    results.append(CheckResult(False, "public_scan", f"{rel} contains forbidden marker {needle!r}"))
    if not results:
        results.append(CheckResult(True, "public_scan", "no forbidden public markers found"))
    return results


def check_required_files(root: Path, files: list[str], label: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    for path in iter_files(root, files):
        rel = path.relative_to(root)
        results.append(CheckResult(path.exists(), label, f"{rel}"))
    return results


def parse_simple_list_sections(path: Path, allowed_sections: set[str]) -> dict[str, list[str]]:
    """Parse simple top-level/nested sections with '- value' list items.

    This intentionally handles the small KnowledgeOS policy files without trying
    to be a full YAML parser. It strips quotes and comments for list values.
    """
    sections: dict[str, list[str]] = {section: [] for section in allowed_sections}
    current: str | None = None
    for raw in read_text(path).splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith(":") and not stripped.startswith("-"):
            key = stripped[:-1].strip()
            current = key if key in allowed_sections else None
            continue
        if current and stripped.startswith("-"):
            value = stripped[1:].strip()
            if " #" in value:
                value = value.split(" #", 1)[0].strip()
            value = value.strip('"').strip("'")
            if value:
                sections[current].append(value)
    return sections


def parse_scalar_values(path: Path, keys: set[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in read_text(path).splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in keys and value:
                values[key] = value
    return values


def parse_task_list_field(path: Path, field_name: str) -> dict[str, list[str]]:
    """Parse a simple list field from each task block in tasks.yaml."""
    values: dict[str, list[str]] = {}
    current_id: str | None = None
    in_field = False
    for raw in read_text(path).splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- id:"):
            current_id = stripped.split(":", 1)[1].strip().strip('"\'')
            values.setdefault(current_id, [])
            in_field = False
            continue
        if current_id is None:
            continue
        if ":" in stripped and not stripped.startswith("-"):
            key = stripped.split(":", 1)[0].strip()
            in_field = key == field_name
            continue
        if in_field and stripped.startswith("-"):
            value = stripped[1:].strip()
            if " #" in value:
                value = value.split(" #", 1)[0].strip()
            value = value.strip('"').strip("'")
            if value:
                values.setdefault(current_id, []).append(value)
    return values


def parse_phase_policy(project_root: Path) -> dict[str, Any]:
    policy_path = project_root / ".agent-os" / "phase-policy.yaml"
    if not policy_path.exists():
        raise FileNotFoundError(f"missing phase policy: {policy_path}")
    required_phases: list[str] = []
    require_skip_reason = True
    in_required = False
    in_default = False
    in_skip = False
    for raw in read_text(policy_path).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            in_required = stripped == "required_phases:"
            in_skip = stripped == "skip_policy:"
            in_default = False
            continue
        if in_required and indent == 2 and stripped == "default:":
            in_default = True
            continue
        if in_required and in_default and stripped.startswith("-"):
            value = stripped[1:].strip().strip('"').strip("'")
            if value:
                required_phases.append(value)
            continue
        if in_skip and ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            if key.strip() == "require_skip_reason":
                require_skip_reason = value.strip().strip('"').strip("'").lower() == "true"
    return {
        "required_phases": {"default": required_phases},
        "skip_policy": {"require_skip_reason": require_skip_reason},
    }


def validate_phase_policy(project_root: Path) -> list[CheckResult]:
    try:
        policy = parse_phase_policy(project_root)
    except FileNotFoundError as exc:
        return [CheckResult(False, "phase_policy", str(exc))]
    required = policy["required_phases"]["default"]
    require_skip_reason = policy["skip_policy"]["require_skip_reason"]
    return [
        CheckResult(required == EXPECTED_PHASE_KEYS, "phase_policy", f"default required phases={required}"),
        CheckResult(require_skip_reason, "phase_policy", "skipped phases require a skip reason"),
    ]


def parse_effect_policy(project_root: Path) -> dict[str, Any]:
    policy_path = project_root / ".agent-os" / "effect-policy.yaml"
    if not policy_path.exists():
        return {
            "exists": False,
            "strictness": "observe",
            "downgrade_reason": "",
            "required_for": [],
            "default_assertion": "file_exists",
        }
    scalars = parse_scalar_values(policy_path, {"strictness", "downgrade_reason", "default_assertion"})
    required_for = parse_simple_list_sections(policy_path, {"required_for"}).get("required_for", [])
    return {
        "exists": True,
        "strictness": (scalars.get("strictness") or "observe").lower(),
        "downgrade_reason": scalars.get("downgrade_reason", ""),
        "required_for": required_for,
        "default_assertion": scalars.get("default_assertion") or "file_exists",
    }


def validate_effect_policy(project_root: Path) -> list[CheckResult]:
    policy = parse_effect_policy(project_root)
    strictness = str(policy.get("strictness", "observe"))
    results = [
        CheckResult(
            strictness in EFFECT_STRICTNESS_LEVELS,
            "effect_policy",
            f"strictness={strictness}" if strictness in EFFECT_STRICTNESS_LEVELS else f"invalid strictness={strictness}",
        )
    ]
    if not policy.get("exists"):
        results.append(CheckResult(True, "effect_policy", "missing effect-policy defaults to strictness=observe"))
        return results
    if strictness == "off":
        reason = str(policy.get("downgrade_reason", "")).strip()
        results.append(CheckResult(bool(reason), "effect_policy", "strictness=off requires downgrade_reason"))
    return results


def parse_decision_policy(project_root: Path) -> dict[str, Any]:
    policy_path = project_root / ".agent-os" / "decision-policy.yaml"
    if not policy_path.exists():
        return {
            "exists": False,
            "strictness": "warn",
            "downgrade_reason": "",
        }
    scalars = parse_scalar_values(policy_path, {"strictness", "downgrade_reason"})
    return {
        "exists": True,
        "strictness": (scalars.get("strictness") or "warn").lower(),
        "downgrade_reason": scalars.get("downgrade_reason", ""),
    }


def validate_decision_policy(project_root: Path) -> list[CheckResult]:
    policy = parse_decision_policy(project_root)
    strictness = str(policy.get("strictness", "warn"))
    results = [
        CheckResult(
            strictness in DECISION_STRICTNESS_LEVELS,
            "decision_policy",
            f"strictness={strictness}" if strictness in DECISION_STRICTNESS_LEVELS else f"invalid strictness={strictness}",
        )
    ]
    if not policy.get("exists"):
        results.append(CheckResult(True, "decision_policy", "missing decision-policy defaults to strictness=warn"))
        return results
    if strictness == "off":
        reason = str(policy.get("downgrade_reason", "")).strip()
        results.append(CheckResult(bool(reason), "decision_policy", "strictness=off requires downgrade_reason"))
    return results


def parse_named_blocks(path: Path) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in read_text(path).splitlines():
        stripped = raw.strip()
        if stripped.startswith("- id:"):
            if current:
                blocks.append(current)
            current = {"id": stripped.split(":", 1)[1].strip().strip('"\'')}
            continue
        if current and ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            value = value.strip().strip('"\'')
            if value:
                current[key.strip()] = value
    if current:
        blocks.append(current)
    return blocks


def parse_task_acceptance(path: Path) -> dict[str, list[str]]:
    return parse_task_list_field(path, "acceptance")


def parse_indented_profile_keys(path: Path, root_key: str) -> list[str]:
    profiles: list[str] = []
    in_root = False
    for raw in read_text(path).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        if raw.startswith(root_key + ":"):
            in_root = True
            continue
        if in_root:
            if raw.startswith("  ") and not raw.startswith("    ") and stripped.endswith(":") and not stripped.startswith("-"):
                profiles.append(stripped[:-1])
            elif not raw.startswith(" "):
                in_root = False
    return profiles


def parse_workflow_profiles(path: Path) -> dict[str, dict[str, Any]]:
    """Parse KnowledgeOS' small workflow router profile file.

    The router intentionally stays tiny and inspectable: each task type maps to
    ordered command hints and guardrail metadata. It is not a general YAML
    implementation, but it supports the structure generated by the templates.
    """
    profiles: dict[str, dict[str, Any]] = {}
    in_workflows = False
    current_name: str | None = None
    current_key: str | None = None

    for raw in read_text(path).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))

        if indent == 0:
            in_workflows = stripped == "workflows:"
            current_name = None
            current_key = None
            continue

        if not in_workflows:
            continue

        if indent == 2 and stripped.endswith(":") and not stripped.startswith("-"):
            current_name = stripped[:-1].strip()
            profiles[current_name] = {}
            current_key = None
            continue

        if not current_name:
            continue

        if indent == 4 and ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            current_key = key
            profiles[current_name].setdefault(key, [] if not value else value)
            continue

        if indent >= 6 and stripped.startswith("-") and current_key:
            value = stripped[1:].strip().strip('"').strip("'")
            if value:
                existing = profiles[current_name].setdefault(current_key, [])
                if not isinstance(existing, list):
                    existing = [str(existing)]
                    profiles[current_name][current_key] = existing
                existing.append(value)

    return profiles


def find_placeholder_markers(path: Path) -> list[str]:
    markers: list[str] = []
    if path.is_file():
        paths = [path]
    else:
        paths = [p for p in path.rglob("*") if p.is_file()]
    for item in paths:
        try:
            text = read_text(item)
        except UnicodeDecodeError:
            continue
        if "CHANGE_ME" in text:
            markers.append(str(item))
    return markers


def unique_id_results(items: list[dict[str, str]], label: str) -> list[CheckResult]:
    seen: set[str] = set()
    results: list[CheckResult] = []
    for item in items:
        item_id = item.get("id", "")
        if not item_id:
            results.append(CheckResult(False, label, "item is missing id"))
            continue
        if item_id in seen:
            results.append(CheckResult(False, label, f"duplicate id {item_id}"))
        seen.add(item_id)
    if not results:
        results.append(CheckResult(True, label, f"{len(items)} ids are unique"))
    return results


def load_write_policy(project_root: Path) -> dict[str, list[str]]:
    policy_path = project_root / ".agent-os" / "write-policy.yaml"
    if not policy_path.exists():
        raise FileNotFoundError(f"missing write policy: {policy_path}")
    return parse_simple_list_sections(policy_path, WRITE_POLICY_SECTIONS)


def load_local_external_write_policy(project_root: Path) -> dict[str, list[str]]:
    policy_path = project_root / ".knowledgeos-local" / "write-policy.local.yaml"
    if not policy_path.exists():
        return {section: [] for section in LOCAL_EXTERNAL_WRITE_POLICY_SECTIONS}
    return parse_simple_list_sections(policy_path, LOCAL_EXTERNAL_WRITE_POLICY_SECTIONS)


def load_read_policy(project_root: Path) -> dict[str, list[str]]:
    policy_path = project_root / ".agent-os" / "read-policy.yaml"
    if not policy_path.exists():
        raise FileNotFoundError(f"missing read policy: {policy_path}")
    return parse_simple_list_sections(policy_path, READ_POLICY_SECTIONS)


def validate_read_policy(project_root: Path) -> list[CheckResult]:
    try:
        policy = load_read_policy(project_root)
    except FileNotFoundError as exc:
        return [CheckResult(False, "read_policy", str(exc))]

    results: list[CheckResult] = []
    for section in sorted(READ_POLICY_SECTIONS):
        results.append(CheckResult(bool(policy.get(section)), "read_policy", f"{section} has entries"))

    cold_storage = " ".join(policy.get("cold_storage", []))
    explicit = " ".join(policy.get("require_explicit_human_request", []))
    deny_indexing = " ".join(policy.get("deny_indexing", []))
    for label, text in [
        ("cold storage", cold_storage),
        ("explicit human request", explicit),
        ("deny indexing", deny_indexing),
    ]:
        results.append(CheckResult("archive/**" in text, "archive_read_guard", f"archive/** covered by {label}"))
    return results


def load_tool_registry(project_root: Path) -> list[dict[str, str]]:
    registry_path = project_root / ".agent-os" / "tool-registry.yaml"
    if not registry_path.exists():
        raise FileNotFoundError(f"missing tool registry: {registry_path}")
    return parse_named_blocks(registry_path)


def load_dispatch_policy(project_root: Path) -> dict[str, list[str]]:
    policy_path = project_root / ".agent-os" / "dispatch-policy.yaml"
    if not policy_path.exists():
        raise FileNotFoundError(f"missing dispatch policy: {policy_path}")
    return parse_simple_list_sections(policy_path, DISPATCH_POLICY_SECTIONS)


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def validate_tool_registry(project_root: Path, *, allow_placeholders: bool = False, check_paths: bool = False) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        entries = load_tool_registry(project_root)
    except FileNotFoundError as exc:
        return [CheckResult(False, "tool_registry", str(exc))]

    results.append(CheckResult(bool(entries), "tool_registry", f"{len(entries)} tool entrie(s) found"))
    results.extend(unique_id_results(entries, "tool_registry_ids"))

    for entry in entries:
        entry_id = entry.get("id", "<missing>")
        kind = entry.get("kind", "")
        status = entry.get("status", "")
        invocation = entry.get("invocation", "")
        results.append(CheckResult(kind in TOOL_KINDS, "tool_registry_kind", f"{entry_id} kind={kind}"))
        results.append(CheckResult(status in TOOL_STATUSES, "tool_registry_status", f"{entry_id} status={status}"))
        results.append(CheckResult(bool(invocation), "tool_registry_invocation", f"{entry_id} invocation present"))

        serialized_values = " ".join(str(value) for value in entry.values())
        has_secret_marker = any(marker in serialized_values for marker in ["API_KEY=", "SECRET=", "TOKEN=", "password=", "secret:"])
        results.append(CheckResult(not has_secret_marker, "tool_registry_secret", f"{entry_id} has no inline secret markers"))

        if "CHANGE_ME" in serialized_values:
            results.append(CheckResult(allow_placeholders, "tool_registry_placeholder", f"{entry_id} placeholder allowed" if allow_placeholders else f"{entry_id} has unresolved placeholder"))

        if kind in {"mcp", "orchestrator", "subagent"} and status in {"enabled", "configured", "recommended"}:
            risk_text = " ".join([entry.get("scope", ""), entry.get("risk", "")]).lower()
            if any(token in risk_text for token in ["browser", "private", "external", "write"]):
                results.append(CheckResult(entry.get("human_gate") == "true", "tool_registry_gate", f"{entry_id} human_gate=true"))

        if kind in {"orchestrator", "subagent"} and status in {"enabled", "configured", "recommended"}:
            results.append(CheckResult(entry.get("execution_mode") == "ask", "tool_registry_orchestration", f"{entry_id} execution_mode=ask"))

        if check_paths:
            for key in ["path", "source_path"]:
                value = entry.get(key, "")
                if not value or "CHANGE_ME" in value:
                    continue
                path = Path(value).expanduser()
                if path.is_absolute():
                    results.append(CheckResult(path.exists(), "tool_registry_path", f"{entry_id}.{key} -> {value}"))

    return results


def summarize_tool_registry(project_root: Path, *, check_paths: bool = False) -> dict[str, Any]:
    entries = load_tool_registry(project_root)
    counts: dict[str, int] = {}
    for entry in entries:
        kind = entry.get("kind", "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    checks = validate_tool_registry(project_root, check_paths=check_paths)
    return {
        "entries": entries,
        "counts": counts,
        "checks": [item.as_dict() for item in checks],
        "ok": all(item.ok for item in checks),
    }


def validate_dispatch_policy(project_root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        policy = load_dispatch_policy(project_root)
    except FileNotFoundError as exc:
        return [CheckResult(False, "dispatch_policy", str(exc))]

    order = policy.get("default_order", [])
    required = ["branch_builder", "orchestrator", "subagent", "mcp", "skill", "script", "human_gate"]
    results.append(CheckResult(bool(order), "dispatch_policy", "default_order present"))
    for item in required:
        results.append(CheckResult(item in order, "dispatch_policy_order", f"default_order includes {item}"))

    checkpoints = policy.get("always_consult_before", [])
    for checkpoint in ["execute", "complete"]:
        results.append(CheckResult(checkpoint in checkpoints, "consultation_policy", f"consult before {checkpoint}"))

    risky = policy.get("consult_for_risks", []) + policy.get("human_gate_for", [])
    for risk in ["external_write", "release", "destructive_change"]:
        results.append(CheckResult(risk in risky, "consultation_risk", f"consult/human gate covers {risk}"))

    return results


def choose_tools(entries: list[dict[str, str]], kind: str, task_type: str, capability: str | None = None) -> list[dict[str, str]]:
    chosen: list[dict[str, str]] = []
    for entry in entries:
        if entry.get("kind") != kind:
            continue
        if entry.get("status") not in ACTIVE_TOOL_STATUSES:
            continue
        task_fit = split_csv(entry.get("task_fit", ""))
        capability_fit = split_csv(entry.get("capability_fit", ""))
        if task_fit and task_type not in task_fit and "*" not in task_fit:
            continue
        if capability and capability_fit and capability not in capability_fit and "*" not in capability_fit:
            continue
        chosen.append(entry)
    return chosen


def runtime_agent_type_for_entry(entry: dict[str, str]) -> str:
    explicit = entry.get("runtime_agent_type", "").strip()
    if explicit in CODEX_RUNTIME_AGENT_TYPES:
        return explicit
    capability_fit = set(split_csv(entry.get("capability_fit", "")))
    entry_id = entry.get("id", "")
    if entry_id == "codex-default":
        return "default"
    if entry_id == "codex-explorer":
        return "explorer"
    if entry_id == "codex-worker":
        return "worker"
    if entry_id.startswith("maestro-"):
        if "full" in capability_fit or "read_write" in capability_fit:
            return "worker"
        if "read_only" in capability_fit or "read_shell" in capability_fit:
            return "explorer"
        return "default"
    return ""


def is_runtime_callable_subagent(entry: dict[str, str]) -> bool:
    if entry.get("kind") != "subagent":
        return False
    runtime_tool = entry.get("runtime_tool", "")
    runtime_type = runtime_agent_type_for_entry(entry)
    return runtime_tool == CODEX_RUNTIME_TOOL and runtime_type in CODEX_RUNTIME_AGENT_TYPES


def select_subagent_candidates(entries: list[dict[str, str]], task_type: str, limit: int = SUBAGENT_CANDIDATE_LIMIT) -> list[dict[str, str]]:
    active = [entry for entry in entries if entry.get("kind") == "subagent" and entry.get("status") in ACTIVE_TOOL_STATUSES]
    by_id = {entry.get("id", ""): entry for entry in active}
    selected: list[dict[str, str]] = []

    def add(entry: dict[str, str] | None) -> None:
        if not entry:
            return
        if entry in selected:
            return
        selected.append(entry)

    for preferred_id in SUBAGENT_PREFERENCES_BY_TASK.get(task_type, []):
        add(by_id.get(preferred_id))
        if len(selected) >= limit:
            return selected[:limit]

    fitted = choose_tools(entries, "subagent", task_type)
    fitted.sort(
        key=lambda item: (
            0 if is_runtime_callable_subagent(item) else 1,
            0 if item.get("id", "").startswith("codex-") else 1,
            item.get("id", ""),
        )
    )
    for entry in fitted:
        add(entry)
        if len(selected) >= limit:
            return selected[:limit]

    for fallback_id in ["codex-default", "maestro-architect", "codex-explorer", "codex-worker"]:
        add(by_id.get(fallback_id))
        if len(selected) >= limit:
            return selected[:limit]
    return selected[:limit]


def tool_summary(entry: dict[str, str]) -> dict[str, Any]:
    summary = {
        "id": entry.get("id", ""),
        "kind": entry.get("kind", ""),
        "status": entry.get("status", ""),
        "scope": entry.get("scope", ""),
        "invocation": entry.get("invocation", ""),
        "human_gate": entry.get("human_gate", ""),
        "execution_mode": entry.get("execution_mode", ""),
    }
    for key in ["runtime", "runtime_tool", "runtime_agent_type", "adapter", "adapter_role", "source_path"]:
        value = entry.get(key, "")
        if value:
            summary[key] = value
    if summary.get("kind") == "subagent" and not summary.get("runtime_agent_type"):
        inferred = runtime_agent_type_for_entry(entry)
        if inferred:
            summary["runtime_agent_type"] = inferred
    if summary.get("kind") == "subagent":
        summary["runtime_callable"] = is_runtime_callable_subagent(entry)
    return summary


def dispatch_tool_runtime_callable(item: dict[str, Any]) -> bool:
    return (
        str(item.get("kind", "")) == "subagent"
        and str(item.get("runtime_tool", "")) == CODEX_RUNTIME_TOOL
        and str(item.get("runtime_agent_type", "")) in CODEX_RUNTIME_AGENT_TYPES
    )


def summarize_dispatch_plan(dispatch: dict[str, Any]) -> dict[str, Any]:
    steps = dispatch.get("steps", [])
    planned_tools: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        stage = str(step.get("stage", ""))
        for tool in step.get("tools", []) or []:
            if not isinstance(tool, dict):
                continue
            planned_tools.append({**tool, "stage": stage, "required": bool(step.get("required"))})
    planned_agents = [
        item
        for item in planned_tools
        if str(item.get("kind", "")) in AGENT_CAPABILITY_KINDS or str(item.get("stage", "")) in {"branch_builder", "orchestrator", "subagent"}
    ]
    runtime_callable_agents = [item for item in planned_agents if dispatch_tool_runtime_callable(item)]
    required_stages = [str(step.get("stage", "")) for step in steps if isinstance(step, dict) and step.get("required")]
    marker = (
        f"AGENT_DISPATCH_PLAN agents={len(planned_agents)} "
        f"runtime_callable={len(runtime_callable_agents)} capabilities={len(planned_tools)} required={len(required_stages)}"
    )
    return {
        "dispatch_marker": "AGENT_DISPATCH_PLAN",
        "marker": marker,
        "dispatch_summary": {
            "planned_agents": len(planned_agents),
            "runtime_callable_agents": len(runtime_callable_agents),
            "planned_capabilities": len(planned_tools),
            "required_stages": required_stages,
            "declared_agents": [str(item.get("id", "")) for item in planned_agents if item.get("id")],
            "planned_agent_ids": [str(item.get("id", "")) for item in planned_agents if item.get("id")],
            "runtime_callable_agent_ids": [str(item.get("id", "")) for item in runtime_callable_agents if item.get("id")],
        },
    }


def build_dispatch_plan(project_root: Path, task_id: str) -> dict[str, Any]:
    task = find_task(project_root, task_id)
    route = build_task_route(project_root, task_id, None)
    if route.get("status") != "routed":
        return {
            "status": "human_triage_required",
            "reason": route.get("reason", "task has no route profile"),
            "task": task,
            "route": route,
        }

    policy = load_dispatch_policy(project_root)
    entries = load_tool_registry(project_root)
    task_type = task.get("type", "")
    complexity = task.get("complexity", "medium")
    risk = task.get("risk", "")
    default_order = policy.get("default_order", [])

    steps: list[dict[str, Any]] = []

    def add_step(stage: str, reason: str, tools: list[dict[str, str]] | None = None, required: bool = False) -> None:
        steps.append(
            {
                "stage": stage,
                "reason": reason,
                "required": required,
                "tools": [tool_summary(item) for item in (tools or [])],
            }
        )

    if "branch_builder" in default_order and (task_type in policy.get("branch_builder_task_types", []) or complexity in {"medium", "complex", "high"}):
        branch_tools = [entry for entry in entries if entry.get("id") == "branch-builder" and entry.get("status") in ACTIVE_TOOL_STATUSES]
        add_step("branch_builder", "create virtual planning branches before specialist dispatch", branch_tools, required=bool(branch_tools))

    if "orchestrator" in default_order:
        orchestrators = choose_tools(entries, "orchestrator", task_type) or [entry for entry in entries if entry.get("kind") == "orchestrator" and entry.get("status") in ACTIVE_TOOL_STATUSES]
        if orchestrators and (task_type in policy.get("subagent_task_types", []) or complexity in {"medium", "complex", "high"}):
            add_step("orchestrator", "coordinate role-specific subagents with execution_mode=ask", orchestrators, required=True)

    if "subagent" in default_order:
        subagents = select_subagent_candidates(entries, task_type)
        if subagents:
            add_step("subagent", "use up to three role-specific runtime subagent candidates when useful", subagents)

    if "mcp" in default_order:
        mcp_tools = choose_tools(entries, "mcp", task_type)
        if mcp_tools or task_type in policy.get("mcp_task_types", []):
            add_step("mcp", "use MCP by capability match for account-backed or outside-context capabilities", mcp_tools)

    if "skill" in default_order:
        skill_tools = choose_tools(entries, "skill", task_type) or [entry for entry in entries if entry.get("kind") == "skill" and entry.get("status") in ACTIVE_TOOL_STATUSES]
        if skill_tools:
            add_step("skill", "use registered skills for reusable task methods", skill_tools)

    if "script" in default_order:
        add_step("script", "prefer deterministic local commands for doctor, tests, build, package, and eval evidence")

    consult = list(policy.get("always_consult_before", []))
    risk_items = [item for item in [risk, route.get("human_gate", "")] if item]
    for item in risk_items:
        if item in policy.get("consult_for_risks", []) or item in policy.get("human_gate_for", []):
            consult.append(item)
    consult = sorted(set(consult))

    result = {
        "status": "dispatch_ready",
        "task": task,
        "route": route,
        "dispatch_policy": {
            "default_order": default_order,
            "consultation_checkpoints": consult,
        },
        "steps": steps,
        "agent_opinion_required": True,
        "agent_opinion_prompt": "Pause before execution, state your recommended next move, name the tradeoff, and ask the human whether to proceed.",
    }
    result.update(summarize_dispatch_plan(result))
    return result


def path_for_policy(project_root: Path, target: str) -> tuple[Path, str, bool]:
    candidate = Path(target).expanduser()
    absolute = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        relative = absolute.relative_to(project_root.resolve()).as_posix()
        inside = True
    except ValueError:
        relative = absolute.as_posix()
        inside = False
    return absolute, relative, inside


def matches_any(value: str, patterns: list[str]) -> str | None:
    normalized_value = value.replace(os.sep, "/").rstrip("/")
    for pattern in patterns:
        normalized = pattern.replace(os.sep, "/")
        if normalized.endswith("/**"):
            prefix = normalized[:-3].rstrip("/")
            if normalized_value == prefix or normalized_value.startswith(prefix + "/"):
                return pattern
        if fnmatch.fnmatch(value, normalized) or fnmatch.fnmatch("/" + value, normalized):
            return pattern
    return None


def route_output_match(relative: str, allowed_outputs: list[str]) -> str | None:
    normalized_relative = relative.strip("/")
    for raw_pattern in allowed_outputs:
        pattern = raw_pattern.strip().strip('"').strip("'")
        if not pattern:
            continue
        normalized = pattern.replace(os.sep, "/").strip("/")
        if pattern.endswith("/") or normalized.endswith("/"):
            prefix = normalized.rstrip("/")
            if normalized_relative == prefix or normalized_relative.startswith(prefix + "/"):
                return raw_pattern
            continue
        if pattern.endswith("/**") or normalized.endswith("/**"):
            prefix = normalized[:-3].rstrip("/")
            if normalized_relative == prefix or normalized_relative.startswith(prefix + "/"):
                return raw_pattern
            continue
        if fnmatch.fnmatch(normalized_relative, normalized) or normalized_relative == normalized:
            return raw_pattern
    return None


def classify_write(project_root: Path, target: str) -> dict[str, Any]:
    policy = load_write_policy(project_root)
    local_external_policy = load_local_external_write_policy(project_root)
    absolute, relative, inside = path_for_policy(project_root, target)
    absolute_value = absolute.as_posix()

    forbidden_match = matches_any(relative, policy["forbidden_without_human_gate"]) or matches_any(
        absolute_value, policy["forbidden_without_human_gate"]
    )
    if forbidden_match:
        return {
            "decision": "human_gate_required",
            "reason": f"matches forbidden_without_human_gate pattern {forbidden_match}",
            "path": relative,
            "inside_project": inside,
        }

    immutable_match = matches_any(relative, policy["immutable"])
    if immutable_match:
        return {
            "decision": "deny",
            "reason": f"matches immutable pattern {immutable_match}",
            "path": relative,
            "inside_project": inside,
        }

    if not inside:
        external_forbidden_match = matches_any(
            absolute_value,
            local_external_policy["external_forbidden_without_human_gate"],
        )
        if external_forbidden_match:
            return {
                "decision": "human_gate_required",
                "reason": f"matches external_forbidden_without_human_gate pattern {external_forbidden_match}",
                "path": absolute_value,
                "inside_project": False,
            }

        external_controlled_match = matches_any(
            absolute_value,
            local_external_policy["external_controlled"],
        )
        if external_controlled_match:
            receipt_match = matches_any(
                absolute_value,
                local_external_policy["external_require_receipt_for"],
            )
            return {
                "decision": "allow",
                "reason": f"matches external_controlled pattern {external_controlled_match}",
                "path": absolute_value,
                "inside_project": False,
                "receipt_required": bool(receipt_match),
                "receipt_pattern": receipt_match,
            }
        return {
            "decision": "deny",
            "reason": "path is outside the project root and no explicit allow policy matched",
            "path": absolute_value,
            "inside_project": False,
        }

    controlled_match = matches_any(relative, policy["controlled"])
    if controlled_match:
        receipt_match = matches_any(relative, policy["require_receipt_for"])
        return {
            "decision": "allow",
            "reason": f"matches controlled pattern {controlled_match}",
            "path": relative,
            "inside_project": True,
            "receipt_required": bool(receipt_match),
            "receipt_pattern": receipt_match,
        }

    return {
        "decision": "unclassified",
        "reason": "path is inside the project but not covered by controlled or immutable policies",
        "path": relative,
        "inside_project": True,
    }


def classify_route_write(project_root: Path, task_id: str, target: str) -> dict[str, Any]:
    route = build_task_route(project_root, task_id, None)
    if route.get("status") != "routed":
        return {
            "decision": "human_triage_required",
            "reason": route.get("reason", "task has no route profile"),
            "task_id": task_id,
            "route": route,
        }

    write_decision = classify_write(project_root, target)
    if write_decision.get("decision") != "allow":
        return {
            **write_decision,
            "task_id": task_id,
            "route_status": "blocked_by_write_policy",
            "route": route,
        }

    if not write_decision.get("inside_project", True):
        if str(route.get("allow_external_controlled", "")).lower() == "true":
            return {
                **write_decision,
                "task_id": task_id,
                "route_status": "allowed_by_external_route",
                "route_output_match": "external_controlled",
                "route": route,
            }
        return {
            "decision": "route_output_denied",
            "reason": f"path is allowed by local external write policy but task {task_id} route does not allow external controlled writes",
            "path": write_decision["path"],
            "inside_project": False,
            "task_id": task_id,
            "allowed_outputs": route.get("allowed_outputs", []),
            "route": route,
        }

    allowed_outputs = route.get("allowed_outputs", [])
    if not allowed_outputs:
        return {
            "decision": "route_output_denied",
            "reason": f"route for task {task_id} has no allowed_outputs",
            "path": write_decision["path"],
            "inside_project": write_decision["inside_project"],
            "task_id": task_id,
            "allowed_outputs": [],
            "route": route,
        }

    match = route_output_match(write_decision["path"], allowed_outputs)
    if not match:
        return {
            "decision": "route_output_denied",
            "reason": f"path is allowed by write-policy but outside route.allowed_outputs for task {task_id}",
            "path": write_decision["path"],
            "inside_project": write_decision["inside_project"],
            "task_id": task_id,
            "allowed_outputs": allowed_outputs,
            "route": route,
        }

    return {
        **write_decision,
        "task_id": task_id,
        "route_status": "allowed_by_route",
        "route_output_match": match,
        "route": route,
    }


IGNORED_TEMPLATE_FILENAMES = {".DS_Store"}


def should_skip_template_file(path: Path) -> bool:
    return path.name in IGNORED_TEMPLATE_FILENAMES or path.name.startswith("._")


def copy_template_tree(src: Path, dest: Path, replacements: dict[str, str], *, dry_run: bool, force: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for source_path in sorted(p for p in src.rglob("*") if p.is_file() and not should_skip_template_file(p)):
        relative = source_path.relative_to(src)
        target_path = dest / relative
        if target_path.exists() and not force:
            actions.append({"action": "skip", "path": str(target_path), "reason": "exists"})
            continue
        if target_path.exists() and force:
            backup_root = dest / ".agent-os" / "backups" / f"knowledgeos-init-{now_stamp()}"
            backup_path = backup_root / relative
            actions.append({"action": "backup", "path": str(target_path), "target": str(backup_path)})
            if not dry_run:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target_path, backup_path)
        text = read_text(source_path)
        for old, new in replacements.items():
            text = text.replace(old, new)
        actions.append({"action": "write", "path": str(target_path), "source": str(source_path)})
        if not dry_run:
            write_text(target_path, text)
    return actions


def make_kernel_hooks_executable(kernel_root: Path) -> None:
    hooks_dir = kernel_root / "hooks"
    if not hooks_dir.exists():
        return
    for hook in hooks_dir.glob("*.sh"):
        hook.chmod(hook.stat().st_mode | 0o111)


def parse_tasks(path: Path) -> list[dict[str, str]]:
    tasks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in read_text(path).splitlines():
        stripped = raw.strip()
        if stripped.startswith("- id:"):
            if current:
                tasks.append(current)
            current = {"id": stripped.split(":", 1)[1].strip().strip('"\'')}
        elif current and ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            if key in {"title", "type", "status", "project", "complexity", "risk"}:
                current[key] = value
    if current:
        tasks.append(current)
    return tasks


def find_task(project_root: Path, task_id: str) -> dict[str, str]:
    tasks_path = project_root / ".agent-os" / "tasks.yaml"
    if not tasks_path.exists():
        raise FileNotFoundError(f"missing tasks file: {tasks_path}")
    for task in parse_tasks(tasks_path):
        if task.get("id") == task_id:
            return task
    raise KeyError(f"task not found: {task_id}")


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def next_task_id(tasks: list[dict[str, str]]) -> str:
    kos_numbers: list[int] = []
    template_numbers: list[int] = []
    for task in tasks:
        task_id = task.get("id", "")
        kos_match = re.fullmatch(r"KOS-T(\d+)", task_id)
        if kos_match:
            kos_numbers.append(int(kos_match.group(1)))
            continue
        template_match = re.fullmatch(r"T(\d+)", task_id)
        if template_match:
            template_numbers.append(int(template_match.group(1)))
    if kos_numbers:
        return f"KOS-T{max(kos_numbers) + 1:03d}"
    if template_numbers:
        return f"T{max(template_numbers) + 1:03d}"
    return "T001"


def create_task(
    project_root: Path,
    *,
    title: str,
    task_type: str,
    status: str,
    complexity: str,
    risk: str,
    outputs: list[str],
    acceptance: list[str],
    dry_run: bool = False,
) -> dict[str, Any]:
    ensure_safe_project_root(project_root)
    if status not in TASK_STATUSES:
        raise ValueError(f"invalid task status: {status}")
    if not title.strip():
        raise ValueError("--title is required")
    if not task_type.strip():
        raise ValueError("--type is required")
    if not outputs:
        raise ValueError("at least one --output is required")
    if not acceptance:
        raise ValueError("at least one --acceptance is required")

    tasks_path = project_root / ".agent-os" / "tasks.yaml"
    if not tasks_path.exists():
        raise FileNotFoundError(f"missing tasks file: {tasks_path}")
    tasks = parse_tasks(tasks_path)
    task_id = next_task_id(tasks)
    block_lines = [
        f"  - id: {task_id}",
        f"    title: {yaml_scalar(title.strip())}",
        f"    type: {yaml_scalar(task_type.strip())}",
        f"    status: {status}",
        f"    complexity: {yaml_scalar(complexity.strip() or 'medium')}",
        f"    risk: {yaml_scalar(risk.strip() or 'normal')}",
        "    outputs:",
        *[f"      - {yaml_scalar(item.strip())}" for item in outputs if item.strip()],
        "    acceptance:",
        *[f"      - {yaml_scalar(item.strip())}" for item in acceptance if item.strip()],
    ]
    if not dry_run:
        current = read_text(tasks_path).rstrip()
        if not current:
            current = "tasks:"
        write_text(tasks_path, current + "\n" + "\n".join(block_lines) + "\n")
    return {
        "task_id": task_id,
        "title": title.strip(),
        "type": task_type.strip(),
        "status": status,
        "complexity": complexity.strip() or "medium",
        "risk": risk.strip() or "normal",
        "outputs": outputs,
        "acceptance": acceptance,
        "dry_run": dry_run,
        "path": str(tasks_path),
    }


def specs_registry_path(project_root: Path) -> Path:
    return project_root / ".agent-os" / "specs.yaml"


def specs_root(project_root: Path) -> Path:
    return project_root / ".agent-os" / "specs"


def load_specs_registry(project_root: Path) -> dict[str, Any]:
    path = specs_registry_path(project_root)
    if not path.exists():
        raise FileNotFoundError(f"missing specs registry: {path}")
    active = parse_scalar_values(path, {"active_spec"}).get("active_spec", "")
    if active.lower() in {"null", "none"}:
        active = ""
    return {"active_spec": active, "specs": parse_named_blocks(path)}


def next_spec_id(project_root: Path) -> str:
    existing = load_specs_registry(project_root).get("specs", [])
    prefix = f"SPEC-{date_stamp()}-"
    numbers: list[int] = []
    for item in existing:
        spec_id = item.get("id", "")
        if spec_id.startswith(prefix):
            match = re.fullmatch(rf"{re.escape(prefix)}(\d+)", spec_id)
            if match:
                numbers.append(int(match.group(1)))
    return f"{prefix}{(max(numbers) + 1) if numbers else 1:03d}"


def spec_dir(project_root: Path, spec_id: str) -> Path:
    if Path(spec_id).name != spec_id:
        raise ValueError("spec_id must not contain path separators")
    return specs_root(project_root) / spec_id


def spec_markdown(project_root: Path, spec_id: str) -> str:
    directory = spec_dir(project_root, spec_id)
    parts: list[str] = []
    for name in ["spec.md", "acceptance.md", "non-goals.md"]:
        path = directory / name
        if path.exists():
            parts.append(read_text(path).strip())
    return "\n\n".join(part for part in parts if part)


def spec_fingerprint(project_root: Path, spec_id: str) -> str:
    if not spec_id:
        return "none"
    return content_fingerprint(spec_markdown(project_root, spec_id))


def find_spec(project_root: Path, spec_id: str | None = None) -> dict[str, str]:
    registry = load_specs_registry(project_root)
    selected = spec_id or registry.get("active_spec", "")
    if not selected:
        raise ValueError("no active spec; run create-spec or pass --spec-id")
    for item in registry.get("specs", []):
        if item.get("id") == selected:
            return item
    raise KeyError(f"spec not found: {selected}")


def set_active_spec(project_root: Path, spec_id: str) -> None:
    path = specs_registry_path(project_root)
    lines = read_text(path).splitlines()
    output: list[str] = []
    updated = False
    for line in lines:
        if line.strip().startswith("active_spec:"):
            indent = line[: len(line) - len(line.lstrip())]
            output.append(f"{indent}active_spec: {spec_id}")
            updated = True
        else:
            output.append(line)
    if not updated:
        output.insert(0, f"active_spec: {spec_id}")
    write_text(path, "\n".join(output).rstrip() + "\n")


def append_spec_change(project_root: Path, spec_id: str, event: dict[str, Any]) -> None:
    event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    change_log = spec_dir(project_root, spec_id) / "change-log.ndjson"
    change_log.parent.mkdir(parents=True, exist_ok=True)
    with change_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def create_spec(
    project_root: Path,
    *,
    title: str,
    intent: str = "",
    acceptance: list[str] | None = None,
    non_goal: list[str] | None = None,
    set_active: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    ensure_safe_project_root(project_root)
    if not title.strip():
        raise ValueError("--title is required")
    registry_path = specs_registry_path(project_root)
    if not registry_path.exists():
        raise FileNotFoundError(f"missing specs registry: {registry_path}")
    spec_id = next_spec_id(project_root)
    directory = spec_dir(project_root, spec_id)
    acceptance = [item.strip() for item in (acceptance or []) if item.strip()]
    non_goal = [item.strip() for item in (non_goal or []) if item.strip()]
    created_at = datetime.now(timezone.utc).isoformat()
    spec_status = "active" if set_active else "draft"
    spec_text = "\n".join(
        [
            f"# {title.strip()}",
            "",
            f"Spec ID: {spec_id}",
            f"Status: {spec_status}",
            f"Created At: {created_at}",
            "",
            "## Intent",
            "",
            intent.strip() or "Describe the durable user intent, constraints, and success shape for this project or task family.",
            "",
        ]
    )
    acceptance_text = "\n".join(["# Acceptance Criteria", "", *[f"- {item}" for item in acceptance], ""])
    non_goal_text = "\n".join(["# Non-Goals", "", *[f"- {item}" for item in non_goal], ""])
    alignment_text = "# Alignment\n\nNo alignment has been run yet.\n"
    if not dry_run:
        write_text(directory / "spec.md", spec_text)
        write_text(directory / "acceptance.md", acceptance_text)
        write_text(directory / "non-goals.md", non_goal_text)
        write_text(directory / "alignment.md", alignment_text)
        append_spec_change(project_root, spec_id, {"event_type": "create-spec", "title": title.strip(), "set_active": set_active})
        current = read_text(registry_path).rstrip()
        if not current:
            current = "active_spec: null\nspecs:"
        current = re.sub(r"(?m)^(\s*)specs:\s*\[\]\s*$", r"\1specs:", current)
        block = "\n".join(
            [
                f"  - id: {spec_id}",
                f"    title: {yaml_scalar(title.strip())}",
                f"    status: {spec_status}",
                f"    created_at: {created_at}",
                f"    path: .agent-os/specs/{spec_id}",
            ]
        )
        write_text(registry_path, current + "\n" + block + "\n")
        if set_active:
            set_active_spec(project_root, spec_id)
    return {
        "spec_id": spec_id,
        "title": title.strip(),
        "active": set_active,
        "path": str(directory),
        "dry_run": dry_run,
    }


def align_spec(project_root: Path, *, task_id: str | None = None, spec_id: str | None = None, note: str = "") -> dict[str, Any]:
    ensure_safe_project_root(project_root)
    spec = find_spec(project_root, spec_id)
    selected = spec["id"]
    task: dict[str, str] | None = find_task(project_root, task_id) if task_id else None
    task_acceptance = parse_task_acceptance(project_root / ".agent-os" / "tasks.yaml").get(task_id or "", [])
    task_outputs = parse_task_list_field(project_root / ".agent-os" / "tasks.yaml", "outputs").get(task_id or "", [])
    missing: list[str] = []
    if task and not task_acceptance:
        missing.append("task has no acceptance criteria")
    if task and not task_outputs:
        missing.append("task has no declared outputs")
    if not spec_markdown(project_root, selected).strip():
        missing.append("spec body is empty")
    status = "aligned" if not missing else "needs_review"
    lines = [
        "# Alignment",
        "",
        f"Spec: {selected}",
        f"Task: {task_id or 'none'}",
        f"Status: {status}",
        f"Generated At: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Public Alignment Note",
        "",
        note.strip() or "Spec alignment checked through KnowledgeOS.",
        "",
        "## Task Summary",
        "",
        f"- Title: {task.get('title', '') if task else 'none'}",
        f"- Type: {task.get('type', '') if task else 'none'}",
        f"- Outputs: {', '.join(task_outputs) if task_outputs else 'none'}",
        "",
        "## Findings",
        "",
    ]
    lines.extend([f"- {item}" for item in missing] or ["- No blocking spec/task alignment gaps detected."])
    alignment_path = spec_dir(project_root, selected) / "alignment.md"
    write_text(alignment_path, "\n".join(lines).rstrip() + "\n")
    append_spec_change(project_root, selected, {"event_type": "align-spec", "task_id": task_id or "", "status": status})
    return {"status": status, "spec_id": selected, "task_id": task_id or "", "alignment": str(alignment_path), "findings": missing}


def active_spec_snapshot(project_root: Path) -> dict[str, str]:
    registry = load_specs_registry(project_root)
    active = registry.get("active_spec", "")
    if not active:
        return {"spec_id": "", "title": "", "fingerprint": "none", "body": "No active spec is registered for this project."}
    spec = find_spec(project_root, active)
    body = spec_markdown(project_root, active) or "Active spec exists but has no body."
    return {
        "spec_id": active,
        "title": spec.get("title", ""),
        "fingerprint": content_fingerprint(body),
        "body": body,
    }


def write_context_pack(project_root: Path, task_id: str, run_id: str, *, summary: str = "") -> dict[str, Any]:
    task = find_task(project_root, task_id)
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    route = build_task_route(project_root, task_id, None)
    dispatch = build_dispatch_plan(project_root, task_id)
    snapshot = active_spec_snapshot(project_root)
    decisions = parse_named_blocks(project_root / ".agent-os" / "decisions.yaml")
    eval_profiles = parse_indented_profile_keys(project_root / ".agent-os" / "evals.yaml", "evals")
    spec_snapshot = [
        "# Spec Snapshot",
        "",
        f"Spec ID: {snapshot['spec_id'] or 'none'}",
        f"Spec Title: {snapshot['title'] or 'none'}",
        f"Spec Fingerprint: {snapshot['fingerprint']}",
        "",
        "## Body",
        "",
        snapshot["body"],
        "",
    ]
    context_lines = [
        "# Context Pack",
        "",
        "Generated By: knowledgeos context-pack",
        f"Generated At: {datetime.now(timezone.utc).isoformat()}",
        f"Run: {run_id}",
        f"Task: {task_id}",
        f"Task Title: {task.get('title', '')}",
        f"Task Type: {task.get('type', '')}",
        f"Spec ID: {snapshot['spec_id'] or 'none'}",
        f"Spec Fingerprint: {snapshot['fingerprint']}",
        "",
        "## User/Run Summary",
        "",
        summary.strip() or "No additional run summary supplied.",
        "",
        "## Route",
        "",
        f"- Status: {route.get('status', '')}",
        f"- Eval Profile: {route.get('eval_profile', '')}",
        f"- Human Gate: {route.get('human_gate', '')}",
        "",
        "## Dispatch",
        "",
        *[f"- {step.get('stage')}: {step.get('reason')}" for step in dispatch.get("steps", [])],
        "",
        "## Decisions",
        "",
        *[f"- {item.get('id', '')}: {item.get('decision', '')}" for item in decisions],
        "",
        "## Eval Profiles",
        "",
        *[f"- {item}" for item in eval_profiles],
        "",
        "## Attention Contract",
        "",
        "- Load this context pack before execution.",
        "- Use plan.md as the current execution contract.",
        "- If user intent conflicts with the spec snapshot, stop and run align-spec.",
        "",
    ]
    write_text(run_dir / "spec-snapshot.md", "\n".join(spec_snapshot).rstrip() + "\n")
    write_text(run_dir / "context-pack.md", "\n".join(context_lines).rstrip() + "\n")
    append_command_event(run_dir, "context-pack", task_id, run_id, spec_id=snapshot["spec_id"] or "none", spec_fingerprint=snapshot["fingerprint"])
    return {
        "status": "written",
        "task_id": task_id,
        "run_id": run_id,
        "spec_id": snapshot["spec_id"] or "none",
        "spec_fingerprint": snapshot["fingerprint"],
        "context_pack": str(run_dir / "context-pack.md"),
        "spec_snapshot": str(run_dir / "spec-snapshot.md"),
    }


def write_task_plan(project_root: Path, task_id: str, run_id: str, *, summary: str = "") -> dict[str, Any]:
    task = find_task(project_root, task_id)
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    context = run_dir / "context-pack.md"
    snapshot = run_dir / "spec-snapshot.md"
    if not context.exists() or not snapshot.exists():
        raise ValueError("context-pack.md and spec-snapshot.md are required before plan-task")
    route = build_task_route(project_root, task_id, None)
    outputs = task_declared_outputs(project_root, task_id)
    acceptance = parse_task_acceptance(project_root / ".agent-os" / "tasks.yaml").get(task_id, [])
    lines = [
        "# Plan",
        "",
        "Generated By: knowledgeos plan-task",
        f"Generated At: {datetime.now(timezone.utc).isoformat()}",
        f"Run: {run_id}",
        f"Task: {task_id}",
        f"Task Title: {task.get('title', '')}",
        "",
        "## Recommended Next Move",
        "",
        summary.strip() or "Execute the task through the routed lifecycle while preserving the spec snapshot and context pack.",
        "",
        "## Route-Bound Scope",
        "",
        f"- Route Status: {route.get('status', '')}",
        f"- Eval Profile: {route.get('eval_profile', '')}",
        f"- Human Gate: {route.get('human_gate', '')}",
        "",
        "## Declared Outputs",
        "",
        *[f"- {item}" for item in outputs],
        "",
        "## Acceptance Checks",
        "",
        *[f"- {item}" for item in acceptance],
        "",
        "## Checkpoint Requirement",
        "",
        "- Record run-bound dispatch evidence with dispatch-task --run-id.",
        "- Record public lifecycle checkpoints with phase-task.",
        "- Record MCP, skill, subagent, orchestrator, or important script use with capability-event.",
        "- Complete only after eval-task, verify-lifecycle, and postflight pass.",
        "- For medium, high, or complex tasks, include a readable FLOW_OK Mission Flow in the final answer.",
        "",
    ]
    write_text(run_dir / "plan.md", "\n".join(lines).rstrip() + "\n")
    append_command_event(run_dir, "plan-task", task_id, run_id, status="written")
    return {"status": "written", "task_id": task_id, "run_id": run_id, "plan": str(run_dir / "plan.md")}


def snapshot_metadata(path: Path) -> dict[str, str]:
    return parse_scalar_values(path, {"Spec ID", "Spec Title", "Spec Fingerprint"})


def verify_context_contract(project_root: Path, task_id: str, run_id: str, *, allow_spec_drift: bool = False) -> dict[str, Any]:
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    errors: list[dict[str, Any]] = []
    context = run_dir / "context-pack.md"
    snapshot = run_dir / "spec-snapshot.md"
    plan = run_dir / "plan.md"
    for label, path in [("context_pack", context), ("spec_snapshot", snapshot), ("plan", plan)]:
        if not path.exists():
            errors.append({"label": f"missing_{label}", "detail": str(path)})
    if context.exists() and "Generated By: knowledgeos context-pack" not in read_text(context):
        errors.append({"label": "invalid_context_pack", "detail": "context-pack.md missing generator marker"})
    if plan.exists() and "Generated By: knowledgeos plan-task" not in read_text(plan):
        errors.append({"label": "invalid_plan", "detail": "plan.md missing generator marker"})
    if not has_command_event(run_dir, "context-pack", task_id, run_id):
        errors.append({"label": "missing_context_pack_command_event", "detail": "context-pack command evidence is missing"})
    if not has_command_event(run_dir, "plan-task", task_id, run_id, status="written"):
        errors.append({"label": "missing_plan_command_event", "detail": "plan-task command evidence is missing"})
    if snapshot.exists():
        metadata = snapshot_metadata(snapshot)
        snap_spec = metadata.get("Spec ID", "")
        snap_fingerprint = metadata.get("Spec Fingerprint", "")
        registry = load_specs_registry(project_root)
        active = registry.get("active_spec", "") or "none"
        if snap_spec != active and not allow_spec_drift:
            errors.append({"label": "spec_drift", "detail": f"snapshot spec {snap_spec or 'none'} != active spec {active}"})
        if not allow_spec_drift:
            expected = "none" if snap_spec in {"", "none"} else spec_fingerprint(project_root, snap_spec)
            if snap_fingerprint != expected:
                errors.append({"label": "spec_drift", "detail": f"snapshot fingerprint {snap_fingerprint} != current {expected}"})
    return {
        "status": "passed" if not errors else "failed",
        "task_id": task_id,
        "run_id": run_id,
        "errors": errors,
        "context_pack": str(context),
        "spec_snapshot": str(snapshot),
        "plan": str(plan),
    }


def resolve_run_dir(project_root: Path, run_id: str) -> Path:
    if Path(run_id).name != run_id:
        raise ValueError("run_id must not contain path separators")
    runs_root = (project_root / ".agent-os" / "runs").resolve()
    run_dir = (runs_root / run_id).resolve()
    try:
        run_dir.relative_to(runs_root)
    except ValueError as exc:
        raise ValueError("run_id escapes .agent-os/runs") from exc
    return run_dir


def set_task_status(project_root: Path, task_id: str, status: str) -> None:
    if status not in TASK_STATUSES:
        raise ValueError(f"invalid task status: {status}")
    tasks_path = project_root / ".agent-os" / "tasks.yaml"
    lines = read_text(tasks_path).splitlines()
    output: list[str] = []
    in_target = False
    found = False
    updated = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- id:"):
            if in_target and not updated:
                output.append(f"    status: {status}")
                updated = True
            current_id = stripped.split(":", 1)[1].strip().strip('"\'')
            in_target = current_id == task_id
            found = found or in_target
            output.append(line)
            continue
        if in_target and stripped.startswith("status:"):
            indent = line[: len(line) - len(line.lstrip())]
            output.append(f"{indent}status: {status}")
            updated = True
            continue
        output.append(line)

    if in_target and not updated:
        output.append(f"    status: {status}")
        updated = True
    if not found:
        raise KeyError(f"task not found: {task_id}")
    write_text(tasks_path, "\n".join(output).rstrip() + "\n")


def update_run_status(run_yaml: Path, status: str) -> None:
    lines = read_text(run_yaml).splitlines()
    output: list[str] = []
    updated = False
    for line in lines:
        if line.strip().startswith("status:"):
            indent = line[: len(line) - len(line.lstrip())]
            output.append(f"{indent}status: {status}")
            updated = True
        else:
            output.append(line)
    if not updated:
        output.append(f"status: {status}")
    write_text(run_yaml, "\n".join(output).rstrip() + "\n")


def eval_has_passed(eval_path: Path) -> bool:
    if not eval_path.exists():
        return False
    text = read_text(eval_path)
    return bool(re.search(r"(?im)^\s*status\s*:\s*passed\b", text))


def eval_is_knowledgeos_generated(eval_path: Path) -> bool:
    if not eval_path.exists():
        return False
    text = read_text(eval_path)
    return "Generated By: knowledgeos eval-task" in text


def run_has_checkpoint_contract_evidence(run_dir: Path) -> bool:
    """New lifecycle gates are mandatory for new runs, but old receipts remain readable."""
    return any(
        (run_dir / name).exists()
        for name in [
            "command-events.ndjson",
            "phases.ndjson",
            "context-pack.md",
            "spec-snapshot.md",
            "plan.md",
        ]
    )


def command_events_path(run_dir: Path) -> Path:
    return run_dir / "command-events.ndjson"


def capability_events_path(run_dir: Path) -> Path:
    return run_dir / "capability-events.ndjson"


def effect_assertions_path(run_dir: Path) -> Path:
    return run_dir / "effect-assertions.ndjson"


def decision_events_path(run_dir: Path) -> Path:
    return run_dir / "decision-events.ndjson"


def step_events_path(run_dir: Path) -> Path:
    return run_dir / "step-events.ndjson"


def append_command_event(run_dir: Path, event_type: str, task_id: str, run_id: str, **extra: Any) -> None:
    record = {
        "event_type": event_type,
        "task_id": task_id,
        "run_id": run_id,
        "generated_by": "knowledgeos",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    with command_events_path(run_dir).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_command_events(run_dir: Path) -> list[dict[str, Any]]:
    path = command_events_path(run_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, raw in enumerate(read_text(path).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            item = {"_invalid_json": raw, "_line": line_number}
        events.append(item)
    return events


def has_command_event(run_dir: Path, event_type: str, task_id: str, run_id: str, **matches: str) -> bool:
    for event in load_command_events(run_dir):
        if event.get("generated_by") != "knowledgeos":
            continue
        if event.get("event_type") != event_type:
            continue
        if event.get("task_id") != task_id or event.get("run_id") != run_id:
            continue
        if all(str(event.get(key, "")) == value for key, value in matches.items()):
            return True
    return False


def load_capability_events(run_dir: Path) -> list[dict[str, Any]]:
    path = capability_events_path(run_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, raw in enumerate(read_text(path).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            item = {"_invalid_json": raw, "_line": line_number}
        events.append(item)
    return events


def load_effect_assertions(run_dir: Path) -> list[dict[str, Any]]:
    path = effect_assertions_path(run_dir)
    if not path.exists():
        return []
    assertions: list[dict[str, Any]] = []
    for line_number, raw in enumerate(read_text(path).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            item = {"_invalid_json": raw, "_line": line_number}
        assertions.append(item)
    return assertions


def load_decision_events(run_dir: Path) -> list[dict[str, Any]]:
    path = decision_events_path(run_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, raw in enumerate(read_text(path).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            item = {"_invalid_json": raw, "_line": line_number}
        events.append(item)
    return events


def threads_root(project_root: Path) -> Path:
    return project_root / ".agent-os" / "threads"


def current_thread_path(project_root: Path) -> Path:
    return threads_root(project_root) / "current.json"


def thread_dir(project_root: Path, thread_id: str) -> Path:
    return threads_root(project_root) / thread_id


def thread_plan_path(project_root: Path, thread_id: str) -> Path:
    return thread_dir(project_root, thread_id) / "thread-plan.ndjson"


def thread_command_events_path(project_root: Path, thread_id: str) -> Path:
    return thread_dir(project_root, thread_id) / "command-events.ndjson"


def thread_meta_path(project_root: Path, thread_id: str) -> Path:
    return thread_dir(project_root, thread_id) / "thread.json"


def utc_event_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def make_thread_id(project_root: Path, title: str) -> str:
    base = f"THREAD-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{safe_slug(title)[:36]}"
    candidate = base.rstrip("-")
    suffix = 2
    while thread_dir(project_root, candidate).exists():
        candidate = f"{base}-{suffix}".rstrip("-")
        suffix += 1
    return candidate


def append_thread_command_event(project_root: Path, thread_id: str, event_type: str, **extra: Any) -> None:
    record = {
        "event_type": event_type,
        "thread_id": thread_id,
        "generated_by": "knowledgeos",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    path = thread_command_events_path(project_root, thread_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_thread_meta(project_root: Path, thread_id: str) -> dict[str, Any]:
    path = thread_meta_path(project_root, thread_id)
    if not path.exists():
        raise FileNotFoundError(f"missing thread metadata: {path}")
    return json.loads(read_text(path))


def load_current_thread(project_root: Path) -> dict[str, Any]:
    path = current_thread_path(project_root)
    if not path.exists():
        raise FileNotFoundError(f"missing current thread pointer: {path}")
    current = json.loads(read_text(path))
    thread_id = str(current.get("thread_id", ""))
    if not thread_id:
        raise ValueError("current thread pointer is missing thread_id")
    if not thread_dir(project_root, thread_id).exists():
        raise FileNotFoundError(f"current thread directory missing: {thread_id}")
    return current


def load_thread_events(project_root: Path, thread_id: str) -> list[dict[str, Any]]:
    path = thread_plan_path(project_root, thread_id)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, raw in enumerate(read_text(path).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            item = {"_invalid_json": raw, "_line": line_number}
        events.append(item)
    return events


def write_thread_current(project_root: Path, meta: dict[str, Any]) -> None:
    current = {
        "thread_id": meta.get("thread_id", ""),
        "title": meta.get("title", ""),
        "spec_id": meta.get("spec_id", ""),
        "created_at": meta.get("created_at", ""),
        "last_updated_at": meta.get("last_updated_at", ""),
    }
    write_text(current_thread_path(project_root), json.dumps(current, indent=2, ensure_ascii=False) + "\n")


def update_thread_meta(project_root: Path, thread_id: str, **updates: Any) -> dict[str, Any]:
    meta = load_thread_meta(project_root, thread_id)
    meta.update(updates)
    meta["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    write_text(thread_meta_path(project_root, thread_id), json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    write_thread_current(project_root, meta)
    return meta


def thread_event_label(text: str, limit: int = 52) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) > limit:
        cleaned = cleaned[: max(0, limit - 3)].rstrip() + "..."
    return cleaned.replace('"', "'").replace("[", "(").replace("]", ")")


def append_thread_plan_event(
    project_root: Path,
    *,
    thread_id: str,
    kind: str,
    text: str,
    linked_spec_id: str = "",
    linked_task_id: str = "",
    linked_run_id: str = "",
    parent_event_id: str = "",
    event_type: str = "thread-plan append",
) -> dict[str, Any]:
    if kind not in THREAD_PLAN_EVENT_KINDS:
        raise ValueError(f"invalid thread-plan kind: {kind}")
    if not text.strip():
        raise ValueError("thread-plan text is required")
    if not thread_dir(project_root, thread_id).exists():
        raise FileNotFoundError(f"thread not found: {thread_id}")
    event_id = f"TPE-{utc_event_stamp()}-{safe_slug(kind)}"
    record = {
        "event_id": event_id,
        "thread_id": thread_id,
        "kind": kind,
        "text": text.strip(),
        "linked_spec_id": linked_spec_id.strip(),
        "linked_task_id": linked_task_id.strip(),
        "linked_run_id": linked_run_id.strip(),
        "parent_event_id": parent_event_id.strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "append_only": True,
    }
    path = thread_plan_path(project_root, thread_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    update_thread_meta(project_root, thread_id)
    append_thread_command_event(
        project_root,
        thread_id,
        event_type,
        event_id=event_id,
        kind=kind,
        linked_task_id=linked_task_id.strip(),
        linked_run_id=linked_run_id.strip(),
        linked_spec_id=linked_spec_id.strip(),
    )
    render_thread_plan_markdown(project_root, thread_id)
    marker = f"{THREAD_PLAN_MARKER} action=append thread={thread_id} kind={kind}"
    return {
        "status": "recorded",
        "thread_plan_marker": THREAD_PLAN_MARKER,
        "marker": marker,
        "thread_id": thread_id,
        "event_id": event_id,
        "ledger": str(path),
        "record": record,
    }


def start_thread_plan(project_root: Path, *, title: str, spec_id: str = "") -> dict[str, Any]:
    if not title.strip():
        raise ValueError("thread-plan title is required")
    thread_id = make_thread_id(project_root, title)
    created_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "thread_id": thread_id,
        "title": title.strip(),
        "spec_id": spec_id.strip(),
        "created_at": created_at,
        "last_updated_at": created_at,
    }
    thread_dir(project_root, thread_id).mkdir(parents=True, exist_ok=True)
    write_text(thread_meta_path(project_root, thread_id), json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    write_thread_current(project_root, meta)
    result = append_thread_plan_event(
        project_root,
        thread_id=thread_id,
        kind="plan",
        text=f"总体计划：{title.strip()}",
        linked_spec_id=spec_id,
        event_type="thread-plan start",
    )
    result.update({"status": "started", "title": title.strip(), "spec_id": spec_id.strip()})
    result["marker"] = f"{THREAD_PLAN_MARKER} action=start thread={thread_id}"
    return result


def render_thread_plan_mermaid(project_root: Path, thread_id: str) -> str:
    meta = load_thread_meta(project_root, thread_id)
    events = [event for event in load_thread_events(project_root, thread_id) if "_invalid_json" not in event]
    lines = ["flowchart LR"]
    lines.append(f'  S["Start: {thread_event_label(str(meta.get("title", thread_id)))}"]')
    previous = "S"
    branch_anchor = "S"
    if not events:
        lines.append('  E["No plan notes yet"]')
        lines.append("  S --> E")
    for index, event in enumerate(events, start=1):
        node = f"N{index}"
        kind = str(event.get("kind", "summary"))
        label = thread_event_label(str(event.get("text", "")))
        lines.append(f'  {node}["{label}"]')
        if kind == "branch":
            lines.append(f"  {branch_anchor} -.-> {node}")
        else:
            lines.append(f"  {previous} --> {node}")
            previous = node
            branch_anchor = node
    lines.extend(
        [
            "",
            "  classDef start fill:#E8F3FF,stroke:#2B6CB0,color:#102A43;",
            "  classDef plan fill:#ECFEFF,stroke:#0891B2,color:#083344;",
            "  classDef phase fill:#E9FBEF,stroke:#2F855A,color:#123524;",
            "  classDef branch fill:#FFF7ED,stroke:#EA580C,color:#431407;",
            "  classDef decision fill:#F3E8FF,stroke:#6B46C1,color:#2D174D;",
            "  classDef progress fill:#DCFCE7,stroke:#15803D,color:#052E16;",
            "  class S start;",
        ]
    )
    classes: dict[str, list[str]] = {"plan": [], "phase": [], "branch": [], "decision": [], "progress": []}
    for index, event in enumerate(events, start=1):
        kind = str(event.get("kind", "summary"))
        css_kind = kind if kind in classes else ("decision" if kind in {"change", "summary"} else "plan")
        classes.setdefault(css_kind, []).append(f"N{index}")
    for kind, nodes in classes.items():
        if nodes:
            lines.append(f"  class {','.join(nodes)} {kind};")
    return "\n".join(lines)


def render_thread_plan_markdown(project_root: Path, thread_id: str) -> dict[str, Any]:
    meta = load_thread_meta(project_root, thread_id)
    events = [event for event in load_thread_events(project_root, thread_id) if "_invalid_json" not in event]
    by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in THREAD_PLAN_EVENT_KINDS}
    for event in events:
        by_kind.setdefault(str(event.get("kind", "")), []).append(event)
    current_line = next((event for event in reversed(events) if str(event.get("kind")) in {"progress", "phase", "decision", "change", "summary"}), None)
    lines = [
        f"# Thread Plan {thread_id}",
        "",
        f"目标：{meta.get('title', '')}",
        "",
        f"当前工作线：{current_line.get('text', '还没有记录进展。') if current_line else '还没有记录进展。'}",
        "",
        "## 总体计划",
        "",
    ]
    for event in by_kind.get("plan", []):
        lines.append(f"- {event.get('text', '')}")
    if not by_kind.get("plan"):
        lines.append("- 尚未记录总体计划。")
    lines.extend(["", "## Plan A / Plan B", ""])
    branch_events = by_kind.get("branch", [])
    if branch_events:
        for index, event in enumerate(branch_events, start=1):
            label = chr(ord("A") + min(index - 1, 25))
            lines.append(f"- Plan {label}: {event.get('text', '')}")
    else:
        lines.append("- 当前没有分支计划。")
    lines.extend(["", "## Phase A / Phase B", ""])
    phase_events = by_kind.get("phase", [])
    if phase_events:
        for index, event in enumerate(phase_events, start=1):
            label = chr(ord("A") + min(index - 1, 25))
            lines.append(f"- Phase {label}: {event.get('text', '')}")
    else:
        lines.append("- 当前没有阶段拆分。")
    lines.extend(["", "## 当前选择", ""])
    choice_events = by_kind.get("decision", []) + by_kind.get("change", [])
    if choice_events:
        for event in choice_events:
            lines.append(f"- {event.get('text', '')}")
    else:
        lines.append("- 尚未记录改路或选择。")
    lines.extend(["", "## 已完成", ""])
    progress_events = by_kind.get("progress", [])
    if progress_events:
        for event in progress_events:
            lines.append(f"- {event.get('text', '')}")
    else:
        lines.append("- 尚未记录完成项。")
    lines.extend(["", "## 下一步", ""])
    summary_events = by_kind.get("summary", [])
    if summary_events:
        lines.append(f"- {summary_events[-1].get('text', '')}")
    else:
        lines.append("- 等待下一轮计划推进。")
    lines.extend(["", "## 关联证据", ""])
    linked = [
        event
        for event in events
        if event.get("linked_spec_id") or event.get("linked_task_id") or event.get("linked_run_id")
    ]
    if linked:
        for event in linked:
            parts = [str(event.get(key, "")) for key in ["linked_spec_id", "linked_task_id", "linked_run_id"] if event.get(key)]
            lines.append(f"- {event.get('event_id', '')}: {' / '.join(parts)}")
    else:
        lines.append("- 尚未关联 spec/task/run。")
    lines.extend(["", "## Mermaid", "", "```mermaid", render_thread_plan_mermaid(project_root, thread_id), "```", ""])
    source_path = thread_dir(project_root, thread_id) / "thread-plan.md"
    markdown = "\n".join(lines).rstrip() + "\n"
    write_text(source_path, markdown)
    return {
        "status": "rendered",
        "thread_plan_marker": THREAD_PLAN_MARKER,
        "marker": f"{THREAD_PLAN_MARKER} action=render thread={thread_id} format=markdown",
        "thread_id": thread_id,
        "format": "markdown",
        "output": str(source_path),
        "markdown": markdown,
        "event_count": len(events),
    }


def render_thread_plan_html(project_root: Path, thread_id: str) -> dict[str, Any]:
    markdown_result = render_thread_plan_markdown(project_root, thread_id)
    source_path = thread_plan_path(project_root, thread_id)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    source_sha = sha256_file(source_path)
    mermaid = render_thread_plan_mermaid(project_root, thread_id)
    body_html, _title, sections = markdown_to_html_fragment(markdown_result["markdown"], anchor_prefix=safe_slug(thread_id.lower()))
    body_html = (
        "<details><summary>Visual plan map</summary>"
        f"<pre><code>{html_escape(mermaid)}</code></pre>"
        "</details>"
        + body_html
    )
    output_path = thread_dir(project_root, thread_id) / "thread-map.html"
    fragment_path = output_path.with_suffix(".fragment.html")
    manifest_path = output_path.with_suffix(".manifest.json")
    generated_at = datetime.now(timezone.utc).isoformat()
    source_rel = project_relative(project_root, source_path)
    fragment_html = build_html_fragment(
        kind="thread-plan",
        title=f"Thread Plan {thread_id}",
        source_rel=source_rel,
        source_sha=source_sha,
        run_id="not run-bound",
        body_html=body_html,
        sections=sections,
        generated_at=generated_at,
    )
    write_text(fragment_path, fragment_html)
    full_html = build_html_document(
        title=f"Thread Plan {thread_id}",
        kind="thread-plan",
        body=fragment_html,
        source_rel=source_rel,
        source_sha=source_sha,
        run_id="not run-bound",
        generated_at=generated_at,
        theme=HTML_DEFAULT_THEME,
    )
    write_text(output_path, full_html)
    manifest = {
        "schema_version": "knowledgeos.html-report.v1",
        "kind": "thread-plan",
        "title": f"Thread Plan {thread_id}",
        "thread_id": thread_id,
        "source": source_rel,
        "source_sha256": source_sha,
        "output": project_relative(project_root, output_path),
        "fragment": project_relative(project_root, fragment_path),
        "sections": sections,
        "generated_at": generated_at,
        "html_source_of_truth": False,
        "notice": HTML_SOURCE_TRUTH_NOTICE,
    }
    write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {
        "status": "rendered",
        "thread_plan_marker": THREAD_PLAN_MARKER,
        "marker": f"{THREAD_PLAN_MARKER} action=render thread={thread_id} format=html",
        "thread_id": thread_id,
        "format": "html",
        "output": str(output_path),
        "manifest": str(manifest_path),
        "source": str(source_path),
        "source_sha256": source_sha,
        "html_source_of_truth": False,
    }


def short_marker_value(value: str, limit: int = 96) -> str:
    cleaned = " ".join(value.strip().split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def task_declared_outputs(project_root: Path, task_id: str) -> list[str]:
    tasks_path = project_root / ".agent-os" / "tasks.yaml"
    if not tasks_path.exists():
        raise FileNotFoundError(f"missing tasks file: {tasks_path}")
    return parse_task_list_field(tasks_path, "outputs").get(task_id, [])


def output_status(project_root: Path, output: str) -> tuple[bool, str]:
    cleaned = output.strip().strip('"').strip("'")
    if not cleaned:
        return True, "empty output ignored"
    if cleaned.startswith("~"):
        return False, f"{cleaned} uses home-relative path"
    candidate = Path(cleaned)
    if candidate.is_absolute():
        absolute = candidate.resolve()
        detail = absolute.as_posix()
    else:
        absolute = (project_root / cleaned).resolve()
        detail = cleaned
    try:
        absolute.relative_to(project_root.resolve())
    except ValueError:
        return False, f"{detail} escapes project root"
    if any(char in cleaned for char in "*?[]"):
        matches = list(project_root.glob(cleaned))
        return bool(matches), f"{cleaned} matched {len(matches)} path(s)"
    return absolute.exists(), f"{detail} exists" if absolute.exists() else f"{detail} missing"


def output_path(project_root: Path, output: str) -> Path:
    cleaned = output.strip().strip('"').strip("'")
    candidate = Path(cleaned).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (project_root / cleaned).resolve()


def missing_declared_outputs(project_root: Path, task_id: str) -> list[str]:
    outputs = task_declared_outputs(project_root, task_id)
    missing: list[str] = []
    for output in outputs:
        ok, detail = output_status(project_root, output)
        if not ok:
            missing.append(detail)
    return missing


def ensure_safe_project_root(project_root: Path) -> None:
    resolved = project_root.expanduser().resolve()
    if resolved == Path.home() or resolved.parent == resolved or resolved.name in BROAD_PROJECT_NAMES:
        raise ValueError(f"refusing broad/container project root: {resolved}")
    if any(part in {"Library", ".Trash"} for part in resolved.parts):
        raise ValueError(f"refusing private/system-like project root: {resolved}")


def move_or_delete_path(path: Path, backup_root: Path | None, *, purge: bool, dry_run: bool) -> dict[str, str]:
    action = "delete" if purge else "archive"
    result = {"action": action, "path": str(path)}
    if not path.exists():
        result["action"] = "skip"
        result["reason"] = "missing"
        return result
    if purge:
        if not dry_run:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        return result
    if backup_root is None:
        raise ValueError("backup_root is required when purge is false")
    target = backup_root / path.name
    suffix = 1
    while target.exists():
        target = backup_root / f"{path.name}.{suffix}"
        suffix += 1
    result["target"] = str(target)
    if not dry_run:
        backup_root.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
    return result


def set_task_statuses(project_root: Path, from_statuses: set[str], to_status: str, *, dry_run: bool = False) -> list[dict[str, str]]:
    tasks = parse_tasks(project_root / ".agent-os" / "tasks.yaml")
    actions: list[dict[str, str]] = []
    for task in tasks:
        status = task.get("status", "")
        task_id = task.get("id", "")
        if task_id and status in from_statuses:
            actions.append({"action": "set-task-status", "task_id": task_id, "from": status, "to": to_status})
            if not dry_run:
                set_task_status(project_root, task_id, to_status)
    return actions


def reopen_task(
    project_root: Path,
    task_id: str,
    *,
    status: str,
    reason: str,
    archive_outputs: bool = False,
    purge_outputs: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    ensure_safe_project_root(project_root)
    task = find_task(project_root, task_id)
    if status not in TASK_STATUSES:
        raise ValueError(f"invalid task status: {status}")
    if status == "completed":
        raise ValueError("reopen-task target status cannot be completed")

    backup_root = project_root / ".agent-os" / "backups" / f"reopen-{safe_slug(task_id)}-{now_stamp()}"
    actions: list[dict[str, str]] = []
    if archive_outputs or purge_outputs:
        for output in task_declared_outputs(project_root, task_id):
            cleaned = output.strip().strip('"').strip("'")
            if not cleaned or cleaned.startswith(".agent-os"):
                actions.append({"action": "skip-output", "path": cleaned, "reason": "control-plane output is protected"})
                continue
            if any(char in cleaned for char in "*?[]"):
                actions.append({"action": "skip-output", "path": cleaned, "reason": "glob outputs require manual cleanup"})
                continue
            actions.append(move_or_delete_path(output_path(project_root, cleaned), backup_root, purge=purge_outputs, dry_run=dry_run))
    actions.append({"action": "set-task-status", "task_id": task_id, "from": task.get("status", ""), "to": status})
    if not dry_run:
        set_task_status(project_root, task_id, status)
        receipt_text = "\n".join(
            [
                "# Receipt",
                "",
                f"Receipt: reopen-{safe_slug(task_id)}-{now_stamp()}",
                "",
                f"Task: {task_id}",
                "",
                f"Status: {status}",
                "",
                f"Reason: {reason}",
                "",
            ]
        )
        write_text(project_root / ".agent-os" / "receipts" / "latest.md", receipt_text)
        write_text(project_root / ".agent-os" / "handoffs" / "current.md", f"# Current Handoff\n\nTask {task_id} reopened as `{status}`.\n\nReason: {reason}\n")
    return {"task_id": task_id, "status": status, "dry_run": dry_run, "actions": actions}


def reset_project(
    project_root: Path,
    *,
    mode: str,
    purge: bool = False,
    reset_tasks: bool = True,
    include_agents_md: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    ensure_safe_project_root(project_root)
    if mode not in {"soft", "hard"}:
        raise ValueError("mode must be one of: soft, hard")
    backup_root = project_root / ".knowledgeos-reset-backups" / f"{mode}-{now_stamp()}"
    actions: list[dict[str, str]] = []

    if mode == "soft":
        if not (project_root / ".agent-os").is_dir():
            raise FileNotFoundError(f"missing KnowledgeOS control plane: {project_root / '.agent-os'}")
        volatile = [
            project_root / ".agent-os" / "runs",
            project_root / ".agent-os" / "receipts",
            project_root / ".agent-os" / "handoffs",
        ]
        for path in volatile:
            actions.append(move_or_delete_path(path, backup_root / ".agent-os", purge=purge, dry_run=dry_run))
        if reset_tasks and (project_root / ".agent-os" / "tasks.yaml").exists():
            actions.extend(set_task_statuses(project_root, RESETTABLE_STATUS_DEFAULTS, "ready", dry_run=dry_run))
        if not dry_run and (project_root / ".agent-os").exists():
            write_text(project_root / ".agent-os" / "receipts" / "latest.md", "# Receipt\n\nStatus: reset\n\nSummary: Project OS volatile state reset.\n")
            write_text(project_root / ".agent-os" / "handoffs" / "current.md", "# Current Handoff\n\nProject OS volatile state was reset.\n")
    else:
        for path in [project_root / ".agent-os", project_root / ".agents"]:
            actions.append(move_or_delete_path(path, backup_root, purge=purge, dry_run=dry_run))
        if include_agents_md:
            actions.append(move_or_delete_path(project_root / "AGENTS.md", backup_root, purge=purge, dry_run=dry_run))

    return {
        "mode": mode,
        "project_root": str(project_root),
        "purge": purge,
        "dry_run": dry_run,
        "backup_root": None if purge else str(backup_root),
        "actions": actions,
    }


def classify_legacy_entry(path: Path) -> tuple[str, str]:
    name = path.name
    lower = name.lower()
    if path.is_dir():
        dir_map = {
            "前期材料": "materials/raw/",
            "materials": "materials/raw/",
            "raw_materials": "materials/raw/",
            "material": "materials/raw/",
            "code": "src/",
            "source": "src/",
            "source_code": "src/",
            "results": "outputs/",
            "result": "outputs/",
            "output": "outputs/",
            "outputs": "outputs/",
            "报告": "reports/drafts/",
            "report": "reports/drafts/",
            "reports": "reports/drafts/",
            "paper": "materials/references/",
            "papers": "materials/references/",
            "reference": "materials/references/",
            "references": "materials/references/",
            "notebook": "notebooks/",
            "notebooks": "notebooks/",
            "script": "scripts/",
            "scripts": "scripts/",
        }
        target = dir_map.get(lower, "inbox/")
        return target, "known legacy directory" if target != "inbox/" else "unknown directory"
    suffix = path.suffix.lower()
    if suffix in {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".tsv"}:
        return "materials/raw/", "source-like document"
    if suffix in {".py", ".r", ".sh", ".jl"}:
        return "scripts/", "executable/script file"
    if suffix == ".ipynb":
        return "notebooks/", "notebook"
    if suffix in {".md", ".txt"}:
        return "docs/", "document/note"
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".pdf"}:
        return "outputs/figures/", "visual artifact"
    return "inbox/", "unclassified"


def build_legacy_migration_plan(project_root: Path) -> list[dict[str, str]]:
    ensure_safe_project_root(project_root)
    plan: list[dict[str, str]] = []
    for entry in sorted(project_root.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith(".") or entry.name in CANONICAL_PROJECT_DIRS or entry.name in {"AGENTS.md", "README.md", "Makefile"}:
            continue
        target_dir, reason = classify_legacy_entry(entry)
        plan.append(
            {
                "source": entry.name,
                "target": f"{target_dir}{entry.name}",
                "kind": "directory" if entry.is_dir() else "file",
                "reason": reason,
                "action": "move" if target_dir != "inbox/" else "triage",
            }
        )
    return plan


def render_migration_plan(project_root: Path, plan: list[dict[str, str]]) -> str:
    lines = [
        "# Legacy Project Reorganization Plan",
        "",
        f"Project root: `{project_root}`",
        "",
        "This is a review-first plan. It does not move files unless `--apply` is used.",
        "",
        "| Source | Target | Action | Reason |",
        "| --- | --- | --- | --- |",
    ]
    if not plan:
        lines.append("| _none_ | _none_ | no-op | Project already looks canonical |")
    for item in plan:
        lines.append(f"| `{item['source']}` | `{item['target']}` | `{item['action']}` | {item['reason']} |")
    lines.append("")
    lines.append("Apply only after human review. Unknown items should stay in inbox/ for triage.")
    return "\n".join(lines) + "\n"


def migrate_legacy_project(project_root: Path, *, write_plan: bool = False, apply: bool = False, dry_run: bool = False) -> dict[str, Any]:
    if (write_plan or apply) and not (project_root / ".agent-os").is_dir():
        raise FileNotFoundError(f"missing KnowledgeOS control plane: {project_root / '.agent-os'}")
    plan = build_legacy_migration_plan(project_root)
    actions: list[dict[str, str]] = []
    if write_plan:
        plan_path = project_root / ".agent-os" / "inbox" / "legacy-reorganization-plan.md"
        actions.append({"action": "write-plan", "path": str(plan_path)})
        if not dry_run:
            write_text(plan_path, render_migration_plan(project_root, plan))
    if apply:
        for item in plan:
            if item["action"] != "move":
                actions.append({"action": "skip", "path": item["source"], "reason": "requires triage"})
                continue
            source = project_root / item["source"]
            target = project_root / item["target"]
            if target.exists():
                actions.append({"action": "skip", "path": item["source"], "target": item["target"], "reason": "target exists"})
                continue
            actions.append({"action": "move", "path": item["source"], "target": item["target"]})
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
    return {"project_root": str(project_root), "dry_run": dry_run, "plan": plan, "actions": actions}


ARCHIVE_NAME_MARKERS = {
    "old",
    "legacy",
    "archive",
    "archived",
    "backup",
    "backups",
    "bak",
    "deprecated",
    "obsolete",
    "unused",
    "superseded",
    "previous",
    "trash",
    "tmp",
    "temp",
    "copy",
    "draft-old",
    "旧",
    "备份",
    "历史",
    "废弃",
    "过时",
    "副本",
}
ARCHIVE_SCAN_DIRS = {"docs", "reports", "outputs", "src", "scripts", "notebooks", "tests"}


def archive_marker_reason(path: Path) -> str | None:
    name = path.name.lower()
    stem = path.stem.lower()
    parts = set(re.split(r"[^a-z0-9\u4e00-\u9fff]+", name))
    if parts & ARCHIVE_NAME_MARKERS:
        return "name contains legacy/archive marker"
    if any(marker in name for marker in ["旧", "备份", "历史", "废弃", "过时", "副本"]):
        return "name contains Chinese legacy/archive marker"
    if stem.endswith(("_old", "-old", ".old", "_bak", "-bak", ".bak")):
        return "name suffix indicates old or backup content"
    return None


def archive_category_for(path: Path, relative: Path) -> str:
    lower_parts = [part.lower() for part in relative.parts]
    name = path.name.lower()
    suffix = path.suffix.lower()
    if any(token in name for token in ["trash", "tmp", "temp", "delete", "删除", "废弃"]):
        return "trash-candidates"
    if lower_parts and lower_parts[0] in {"outputs", "results"}:
        return "generated"
    if any(token in name for token in ["result", "output", "generated", "figure", "plot"]):
        return "generated"
    if lower_parts and lower_parts[0] in {"docs", "reports"}:
        return "superseded"
    if suffix in {".md", ".txt", ".doc", ".docx", ".pdf", ".ppt", ".pptx"}:
        return "superseded"
    return "legacy"


def plan_archive_item(project_root: Path, path: Path, reason: str) -> dict[str, str]:
    relative = path.resolve().relative_to(project_root.resolve())
    category = archive_category_for(path, relative)
    return {
        "source": relative.as_posix(),
        "target": (Path("archive") / category / relative).as_posix(),
        "kind": "directory" if path.is_dir() else "file",
        "reason": reason,
        "action": "archive",
        "read_policy": "cold_storage",
    }


def iter_archive_candidates(project_root: Path) -> Iterable[tuple[Path, str]]:
    for entry in sorted(project_root.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith(".") or entry.name in CANONICAL_PROJECT_DIRS or entry.name in {"AGENTS.md", "README.md", "Makefile"}:
            continue
        reason = archive_marker_reason(entry)
        if reason:
            yield entry, reason

    for root_name in sorted(ARCHIVE_SCAN_DIRS):
        root = project_root / root_name
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            reason = archive_marker_reason(entry)
            if reason:
                yield entry, reason


def build_archive_plan(project_root: Path, includes: list[str] | None = None) -> list[dict[str, str]]:
    ensure_safe_project_root(project_root)
    seen: set[str] = set()
    plan: list[dict[str, str]] = []

    if includes:
        for raw in includes:
            absolute, relative, inside = path_for_policy(project_root, raw)
            if not inside:
                plan.append(
                    {
                        "source": raw,
                        "target": "",
                        "kind": "unknown",
                        "reason": "outside project root",
                        "action": "skip",
                        "read_policy": "not_applicable",
                    }
                )
                continue
            if relative.startswith(".agent-os/") or relative == ".agent-os":
                plan.append(
                    {
                        "source": relative,
                        "target": "",
                        "kind": "control-plane",
                        "reason": "control-plane paths are not cold-archived",
                        "action": "skip",
                        "read_policy": "not_applicable",
                    }
                )
                continue
            if relative.startswith("archive/") or relative == "archive":
                plan.append(
                    {
                        "source": relative,
                        "target": "",
                        "kind": "archive",
                        "reason": "already in cold archive",
                        "action": "skip",
                        "read_policy": "cold_storage",
                    }
                )
                continue
            if relative in {"", "."}:
                plan.append(
                    {
                        "source": relative or ".",
                        "target": "",
                        "kind": "project-root",
                        "reason": "project root cannot be cold-archived",
                        "action": "skip",
                        "read_policy": "not_applicable",
                    }
                )
                continue
            if not absolute.exists():
                plan.append(
                    {
                        "source": relative,
                        "target": "",
                        "kind": "missing",
                        "reason": "source missing",
                        "action": "skip",
                        "read_policy": "not_applicable",
                    }
                )
                continue
            if relative in seen:
                continue
            seen.add(relative)
            plan.append(plan_archive_item(project_root, absolute, "explicit include"))
        return plan

    for candidate, reason in iter_archive_candidates(project_root):
        relative = candidate.resolve().relative_to(project_root.resolve()).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        plan.append(plan_archive_item(project_root, candidate, reason))
    return plan


def render_archive_plan(project_root: Path, plan: list[dict[str, str]]) -> str:
    lines = [
        "# Cold Archive Plan",
        "",
        f"Project root: `{project_root}`",
        "",
        "This is a review-first plan for moving historical or superseded files into `archive/`.",
        "`archive/**` is cold storage: agents should not read it as default context and should only inspect it after explicit human request.",
        "",
        "| Source | Target | Action | Read Policy | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not plan:
        lines.append("| _none_ | _none_ | no-op | cold_storage | No strong legacy/archive markers found |")
    for item in plan:
        lines.append(
            f"| `{item['source']}` | `{item.get('target', '')}` | `{item['action']}` | `{item.get('read_policy', '')}` | {item['reason']} |"
        )
    lines.extend(
        [
            "",
            "Apply only after human review. Use `--include <path>` for explicit one-off archival decisions.",
            "Do not use this as deletion; cold archive is reversible storage.",
        ]
    )
    return "\n".join(lines) + "\n"


def archive_legacy_project(
    project_root: Path,
    *,
    write_plan: bool = False,
    apply: bool = False,
    dry_run: bool = False,
    includes: list[str] | None = None,
) -> dict[str, Any]:
    if (write_plan or apply) and not (project_root / ".agent-os").is_dir():
        raise FileNotFoundError(f"missing KnowledgeOS control plane: {project_root / '.agent-os'}")
    plan = build_archive_plan(project_root, includes)
    actions: list[dict[str, str]] = []
    if write_plan:
        plan_path = project_root / ".agent-os" / "inbox" / "cold-archive-plan.md"
        actions.append({"action": "write-plan", "path": str(plan_path)})
        if not dry_run:
            write_text(plan_path, render_archive_plan(project_root, plan))
    if apply:
        for item in plan:
            if item["action"] != "archive":
                actions.append({"action": "skip", "path": item["source"], "reason": item["reason"]})
                continue
            source = project_root / item["source"]
            target = project_root / item["target"]
            if not source.exists():
                actions.append({"action": "skip", "path": item["source"], "target": item["target"], "reason": "source missing"})
                continue
            if target.exists():
                actions.append({"action": "skip", "path": item["source"], "target": item["target"], "reason": "target exists"})
                continue
            actions.append({"action": "archive", "path": item["source"], "target": item["target"]})
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(target))
    return {"project_root": str(project_root), "dry_run": dry_run, "plan": plan, "actions": actions}


def write_task_eval(project_root: Path, task_id: str, run_id: str, notes: str = "") -> dict[str, Any]:
    task = find_task(project_root, task_id)
    run_dir = resolve_run_dir(project_root, run_id)
    if not run_dir.exists():
        raise FileNotFoundError(f"missing run directory: {run_dir}")
    run_yaml = run_dir / "run.yaml"
    if not run_yaml.exists():
        raise FileNotFoundError(f"missing run metadata: {run_yaml}")
    metadata = parse_scalar_values(run_yaml, {"run_id", "task_id", "status"})
    if metadata.get("task_id") != task_id:
        raise ValueError(f"run {run_id} belongs to task {metadata.get('task_id')!r}, not {task_id!r}")

    outputs = task_declared_outputs(project_root, task_id)
    checks: list[tuple[bool, str]] = []
    if outputs:
        for output in outputs:
            ok, detail = output_status(project_root, output)
            checks.append((ok, detail))
    else:
        checks.append((False, "task has no declared outputs"))

    passed = all(ok for ok, _ in checks)
    lines = [
        "# Eval",
        "",
        "Generated By: knowledgeos eval-task",
        f"Generated At: {datetime.now(timezone.utc).isoformat()}",
        f"Run: {run_id}",
        f"Task: {task_id}",
        f"Task Title: {task.get('title', '')}",
        f"Status: {'passed' if passed else 'failed'}",
        "",
        "## Checks",
        "",
    ]
    for ok, detail in checks:
        lines.append(f"- [{'x' if ok else ' '}] {detail}")
    if notes:
        lines.extend(["", "## Notes", "", notes])
    write_text(run_dir / "eval.md", "\n".join(lines).rstrip() + "\n")
    append_command_event(run_dir, "eval-task", task_id, run_id, status="passed" if passed else "failed")
    return {
        "task_id": task_id,
        "run_id": run_id,
        "status": "passed" if passed else "failed",
        "checks": [{"ok": ok, "detail": detail} for ok, detail in checks],
        "eval": str(run_dir / "eval.md"),
    }


def deep_validate_project(project_root: Path, *, allow_placeholders: bool = False, skip_external: bool = False) -> list[CheckResult]:
    agent_os = project_root / ".agent-os"
    results: list[CheckResult] = []

    results.extend(check_required_files(project_root, REQUIRED_PROJECT_FILES, "project_file"))
    if any(not item.ok for item in results):
        return results

    placeholders = find_placeholder_markers(agent_os)
    if placeholders and not allow_placeholders:
        details = ", ".join(str(Path(p).relative_to(project_root)) for p in placeholders[:5])
        suffix = "" if len(placeholders) <= 5 else f", +{len(placeholders) - 5} more"
        results.append(CheckResult(False, "placeholders", f"unresolved CHANGE_ME markers in {details}{suffix}"))
    else:
        results.append(CheckResult(True, "placeholders", "no unresolved placeholders" if not placeholders else "placeholders allowed"))

    workspace = parse_scalar_values(
        agent_os / "workspace.yaml",
        {"workspace_id", "name", "root", "active_project", "governance_root", "capability_root", "implementation_root"},
    )
    for key in ["workspace_id", "name", "root", "active_project"]:
        results.append(CheckResult(bool(workspace.get(key)), "workspace_schema", f"{key} present"))
    root_value = workspace.get("root", "")
    if root_value and "CHANGE_ME" not in root_value:
        try:
            root_matches = resolve_project_config_path(project_root, root_value) == project_root.resolve()
        except RuntimeError:
            root_matches = False
        results.append(CheckResult(root_matches, "workspace_root", f"root points to {root_value}"))

    project = parse_scalar_values(agent_os / "project.yaml", {"id", "name", "status", "current_phase"})
    for key in ["id", "name", "status", "current_phase"]:
        results.append(CheckResult(bool(project.get(key)), "project_schema", f"{key} present"))

    try:
        specs = load_specs_registry(project_root)
        active_spec = specs.get("active_spec", "")
        spec_items = specs.get("specs", [])
        results.append(CheckResult("active_spec" in parse_scalar_values(agent_os / "specs.yaml", {"active_spec"}), "specs_schema", "active_spec present"))
        results.extend(unique_id_results(spec_items, "spec_ids"))
        if active_spec:
            active_known = any(item.get("id") == active_spec for item in spec_items)
            results.append(CheckResult(active_known, "specs_schema", f"active spec {active_spec} is registered"))
        for spec in spec_items:
            item_id = spec.get("id", "")
            directory = spec_dir(project_root, item_id) if item_id else agent_os / "specs" / "<missing>"
            for name in ["spec.md", "acceptance.md", "non-goals.md", "alignment.md", "change-log.ndjson"]:
                results.append(CheckResult((directory / name).exists(), "spec_files", f"{item_id}/{name}"))
    except (FileNotFoundError, KeyError, ValueError) as exc:
        results.append(CheckResult(False, "specs_schema", str(exc)))

    fabric = parse_scalar_values(
        agent_os / "fabric-link.yaml",
        {"governance_root", "capability_root", "implementation_root", "boot_required", "phase_logging_required", "postflight_required"},
    )
    fabric_paths = {
        "governance_root": fabric.get("governance_root", ""),
        "capability_root": fabric.get("capability_root") or fabric.get("implementation_root", ""),
    }
    for key, value in fabric_paths.items():
        if not value or "CHANGE_ME" in value:
            results.append(CheckResult(skip_external, "fabric_link", f"{key} is unresolved" if not skip_external else f"{key} unresolved allowed"))
            continue
        target = resolve_project_config_path(project_root, value)
        exists = target.exists()
        results.append(CheckResult(skip_external or exists, "fabric_link", f"{key} -> {value}" if exists else f"{key} target missing: {value}"))
    for key in ["boot_required", "phase_logging_required", "postflight_required"]:
        results.append(CheckResult(fabric.get(key) == "true", "runtime_contract", f"{key}=true"))
    if fabric.get("boot_required") == "true":
        results.extend(validate_governance_kernel(project_root, fabric.get("governance_root", ""), skip_external=skip_external))
    if fabric.get("postflight_required") == "true":
        hook = resolve_postflight_hook(project_root, {"governance_root": fabric.get("governance_root", "")})
        hook_ok = bool(hook and hook.exists() and os.access(hook, os.X_OK))
        results.append(
            CheckResult(
                skip_external or hook_ok,
                "postflight_hook",
                f"after-task hook executable: {hook}" if hook_ok else f"after-task hook missing or not executable: {hook}",
            )
        )
    phases = parse_simple_list_sections(agent_os / "fabric-link.yaml", {"phase_keys"}).get("phase_keys", [])
    results.append(CheckResult(phases == EXPECTED_PHASE_KEYS, "phase_keys", f"{phases}"))
    results.extend(validate_phase_policy(project_root))
    results.extend(validate_decision_policy(project_root))
    results.extend(validate_effect_policy(project_root))

    policy = load_write_policy(project_root)
    for section in sorted(WRITE_POLICY_SECTIONS):
        results.append(CheckResult(bool(policy.get(section)), "write_policy", f"{section} has entries"))
    forbidden_patterns = " ".join(policy.get("forbidden_without_human_gate", []))
    for required in [".env", "secret", "reports/final"]:
        results.append(CheckResult(required in forbidden_patterns, "write_guard_risk", f"forbidden policy covers {required}"))
    controlled_patterns = " ".join(policy.get("controlled", []))
    results.append(CheckResult("archive/**" in controlled_patterns, "archive_write_guard", "archive/** is a controlled write zone"))
    results.extend(validate_read_policy(project_root))

    tasks = parse_tasks(agent_os / "tasks.yaml")
    task_outputs = parse_task_list_field(agent_os / "tasks.yaml", "outputs")
    results.append(CheckResult(bool(tasks), "tasks_schema", f"{len(tasks)} task(s) found"))
    results.extend(unique_id_results(tasks, "tasks_ids"))
    for task in tasks:
        task_id = task.get("id", "<missing>")
        for key in ["title", "type", "status"]:
            results.append(CheckResult(bool(task.get(key)), "tasks_schema", f"{task_id}.{key} present"))
        status = task.get("status", "")
        results.append(CheckResult(status in TASK_STATUSES, "tasks_status", f"{task_id} status={status}"))
        if status == "completed":
            outputs = task_outputs.get(task_id, [])
            results.append(CheckResult(bool(outputs), "completed_task_outputs", f"{task_id} declares outputs"))
            for output in outputs:
                ok, detail = output_status(project_root, output)
                results.append(CheckResult(ok, "completed_task_outputs", f"{task_id}: {detail}"))

    runs_root = agent_os / "runs"
    if runs_root.exists():
        for run_yaml in sorted(runs_root.glob("RUN-*/run.yaml")):
            metadata = parse_scalar_values(run_yaml, {"run_id", "task_id", "status"})
            if metadata.get("status") == "completed":
                eval_path = run_yaml.parent / "eval.md"
                run_id = metadata.get("run_id") or run_yaml.parent.name
                results.append(CheckResult(eval_has_passed(eval_path), "completed_run_eval", f"{run_id} eval status passed"))
                results.append(
                    CheckResult(
                        eval_is_knowledgeos_generated(eval_path),
                        "completed_run_eval",
                        f"{run_id} eval generated by knowledgeos eval-task",
                    )
                )
                if run_has_checkpoint_contract_evidence(run_yaml.parent):
                    lifecycle = verify_lifecycle(project_root, metadata.get("task_id", ""), run_id)
                    results.append(CheckResult(lifecycle.get("status") == "passed", "completed_run_lifecycle", f"{run_id} lifecycle status={lifecycle.get('status')}"))
                    context_contract = verify_context_contract(project_root, metadata.get("task_id", ""), run_id, allow_spec_drift=True)
                    results.append(CheckResult(context_contract.get("status") == "passed", "completed_run_context", f"{run_id} context contract status={context_contract.get('status')}"))
                else:
                    results.append(CheckResult(True, "completed_run_lifecycle", f"{run_id} legacy run predates phase ledger"))
                    results.append(CheckResult(True, "completed_run_context", f"{run_id} legacy run predates context contract"))

    decisions = parse_named_blocks(agent_os / "decisions.yaml")
    results.extend(unique_id_results(decisions, "decision_ids"))

    eval_profiles = parse_indented_profile_keys(agent_os / "evals.yaml", "evals")
    results.append(CheckResult(bool(eval_profiles), "evals_schema", f"{len(eval_profiles)} eval profile(s) found"))

    artifacts = parse_named_blocks(agent_os / "artifacts.yaml")
    if artifacts:
        results.extend(unique_id_results(artifacts, "artifact_ids"))
    else:
        results.append(CheckResult(True, "artifact_ids", "no artifacts registered yet"))

    capabilities = parse_scalar_values(agent_os / "capabilities.yaml", {"orchestrator", "execution_mode", "require_role_specific_dispatch"})
    execution_mode = capabilities.get("execution_mode")
    if execution_mode:
        results.append(CheckResult(execution_mode == "ask", "capability_guard", "subagent execution_mode=ask"))
    require_role_specific = capabilities.get("require_role_specific_dispatch")
    if require_role_specific:
        results.append(CheckResult(require_role_specific == "true", "capability_guard", "role-specific dispatch required"))
    capability_lists = parse_simple_list_sections(agent_os / "capabilities.yaml", {"human_gate_for", "forbidden", "deny", "allow", "allow_sources"})
    forbidden = " ".join(capability_lists.get("forbidden", []))
    if forbidden:
        results.append(CheckResult("generic" in forbidden, "capability_guard", "generic unscoped agents are discouraged"))
    human_gate_for = " ".join(capability_lists.get("human_gate_for", []) + capability_lists.get("human_gate", []))
    if human_gate_for:
        for risk in ["browser", "external"]:
            results.append(CheckResult(risk in human_gate_for, "capability_risk", f"human gate mentions {risk}"))

    results.extend(validate_tool_registry(project_root, allow_placeholders=allow_placeholders, check_paths=not skip_external))
    results.extend(validate_dispatch_policy(project_root))

    router_path = agent_os / "workflows" / "router.yaml"
    if router_path.exists():
        profiles = parse_workflow_profiles(router_path)
        results.append(CheckResult(bool(profiles), "workflow_router", f"{len(profiles)} route profile(s) found"))
        task_types = {task.get("type", "") for task in tasks if task.get("type")}
        missing_routes = sorted(task_type for task_type in task_types if task_type not in profiles)
        results.append(CheckResult(not missing_routes, "workflow_router", "all task types are routed" if not missing_routes else f"missing routes for {missing_routes}"))
        for name, profile in sorted(profiles.items()):
            eval_profile = str(profile.get("eval_profile", ""))
            allowed_outputs = profile.get("allowed_outputs", [])
            route_order = profile.get("route_order", [])
            results.append(CheckResult(bool(eval_profile), "workflow_router_eval", f"{name} eval_profile present"))
            if eval_profile:
                results.append(CheckResult(eval_profile in eval_profiles, "workflow_router_eval", f"{name} eval_profile={eval_profile}"))
            results.append(
                CheckResult(
                    isinstance(allowed_outputs, list) and bool(allowed_outputs),
                    "workflow_router_outputs",
                    f"{name} allowed_outputs present",
                )
            )
            if isinstance(route_order, list):
                has_run = any("run-task" in item for item in route_order)
                has_dispatch_event = any("dispatch-task" in item and "--run-id" in item for item in route_order)
                has_context = any("context-pack" in item for item in route_order)
                has_plan = any("plan-task" in item for item in route_order)
                has_phase = any("phase-task" in item for item in route_order)
                has_eval = any("eval-task" in item for item in route_order)
                has_verify_context = any("verify-context" in item for item in route_order)
                has_verify = any("verify-lifecycle" in item for item in route_order)
                has_verify_effects = any("verify-effects" in item for item in route_order)
                has_complete = any("complete-task" in item for item in route_order)
                run_index = next((idx for idx, item in enumerate(route_order) if "run-task" in item), -1)
                dispatch_event_index = next((idx for idx, item in enumerate(route_order) if "dispatch-task" in item and "--run-id" in item), -1)
                context_index = next((idx for idx, item in enumerate(route_order) if "context-pack" in item), -1)
                plan_index = next((idx for idx, item in enumerate(route_order) if "plan-task" in item), -1)
                eval_index = next((idx for idx, item in enumerate(route_order) if "eval-task" in item), -1)
                verify_context_index = next((idx for idx, item in enumerate(route_order) if "verify-context" in item), -1)
                verify_index = next((idx for idx, item in enumerate(route_order) if "verify-lifecycle" in item), -1)
                verify_effects_index = next((idx for idx, item in enumerate(route_order) if "verify-effects" in item), -1)
                complete_index = next((idx for idx, item in enumerate(route_order) if "complete-task" in item), -1)
                results.append(CheckResult(has_run, "workflow_router_lifecycle", f"{name} includes run-task"))
                results.append(CheckResult(has_dispatch_event, "workflow_router_lifecycle", f"{name} includes dispatch-task --run-id"))
                results.append(CheckResult(has_context, "workflow_router_lifecycle", f"{name} includes context-pack"))
                results.append(CheckResult(has_plan, "workflow_router_lifecycle", f"{name} includes plan-task"))
                results.append(CheckResult(has_phase, "workflow_router_lifecycle", f"{name} includes phase-task"))
                results.append(CheckResult(has_eval, "workflow_router_lifecycle", f"{name} includes eval-task"))
                results.append(CheckResult(has_verify_context, "workflow_router_lifecycle", f"{name} includes verify-context"))
                results.append(CheckResult(has_verify, "workflow_router_lifecycle", f"{name} includes verify-lifecycle"))
                results.append(CheckResult(has_verify_effects, "workflow_router_lifecycle", f"{name} includes verify-effects"))
                results.append(CheckResult(has_complete, "workflow_router_lifecycle", f"{name} includes complete-task"))
                results.append(
                    CheckResult(
                        run_index >= 0 and context_index >= 0 and plan_index >= 0 and run_index < context_index < plan_index,
                        "workflow_router_lifecycle",
                        f"{name} run-task before context-pack before plan-task",
                    )
                )
                results.append(
                    CheckResult(
                        run_index >= 0 and dispatch_event_index >= 0 and context_index >= 0 and run_index < dispatch_event_index < context_index,
                        "workflow_router_lifecycle",
                        f"{name} run-task before dispatch-task --run-id before context-pack",
                    )
                )
                results.append(
                    CheckResult(
                        eval_index >= 0 and complete_index >= 0 and eval_index < complete_index,
                        "workflow_router_lifecycle",
                        f"{name} eval-task before complete-task",
                    )
                )
                results.append(
                    CheckResult(
                        verify_context_index >= 0 and complete_index >= 0 and verify_context_index < complete_index,
                        "workflow_router_lifecycle",
                        f"{name} verify-context before complete-task",
                    )
                )
                results.append(
                    CheckResult(
                        verify_index >= 0 and complete_index >= 0 and verify_index < complete_index,
                        "workflow_router_lifecycle",
                        f"{name} verify-lifecycle before complete-task",
                    )
                )
                results.append(
                    CheckResult(
                        verify_effects_index >= 0 and complete_index >= 0 and verify_effects_index < complete_index,
                        "workflow_router_lifecycle",
                        f"{name} verify-effects before complete-task",
                    )
                )
            else:
                results.append(CheckResult(False, "workflow_router_lifecycle", f"{name} route_order is not a list"))
    else:
        results.append(CheckResult(False, "workflow_router", f"missing router file: {router_path}"))

    return results


def build_agent_guide(project_root: Path) -> str:
    bin_path = knowledgeos_root_from_file() / "bin" / "knowledgeos"
    return "\n".join(
        [
            "# KnowledgeOS Agent Guide",
            "",
            "Use this checklist before substantial work.",
            "",
            "0. Start every conversation with a visible KnowledgeOS routing judgment.",
            "   - Relay KOS_DECISION with project state, work class, required flow, and reason.",
            "   - Use answer-only for simple non-mutating replies, but still state the decision.",
            "   - Use task, spec, thread-plan, or full lifecycle when work is substantial.",
            "",
            "1. Read the entry contract.",
            "   - AGENTS.md",
            "",
            "2. Load project control state.",
            "   - .agent-os/workspace.yaml",
            "   - .agent-os/project.yaml",
            "   - .agent-os/tasks.yaml",
            "   - .agent-os/specs.yaml",
            "   - .agent-os/phase-policy.yaml",
            "   - .agent-os/decision-policy.yaml",
            "   - .agent-os/effect-policy.yaml",
            "   - .agent-os/decisions.yaml",
            "   - .agent-os/evals.yaml",
            "   - .agent-os/capabilities.yaml",
            "   - .agent-os/read-policy.yaml",
            "   - .agent-os/write-policy.yaml",
            "",
            "3. Run checks before acting.",
            f"   - {bin_path} doctor --project-root {project_root} --summary",
            f"   - {bin_path} tool-registry --project-root {project_root}",
            f"   - {bin_path} create-spec --project-root {project_root} --title <title>  # when the user asks to create/align spec",
            f"   - {bin_path} align-spec --project-root {project_root} --task-id <task-id>",
            f"   - {bin_path} thread-plan current --project-root {project_root}  # restore the chat-level plan when one exists; relay THREAD_PLAN_OK",
            f"   - {bin_path} thread-plan start --project-root {project_root} --title <natural-language-goal>  # when a long-lived plan/spec starts; relay THREAD_PLAN_OK",
            f"   - {bin_path} create-task --project-root {project_root} --title <title> --type <type> --output <path> --acceptance <check>",
            f"   - {bin_path} route-task --project-root {project_root} --task-id <task-id>",
            f"   - {bin_path} dispatch-task --project-root {project_root} --task-id <task-id>; echo or relay AGENT_DISPATCH_PLAN",
            f"   - {bin_path} check-route-write --project-root {project_root} --task-id <task-id> --path <planned-path>",
            "",
            "4. Start work through a run envelope.",
            f"   - {bin_path} run-task --project-root {project_root} --task-id <task-id>",
            f"   - {bin_path} context-pack --project-root {project_root} --task-id <task-id> --run-id <run-id>",
            f"   - {bin_path} plan-task --project-root {project_root} --task-id <task-id> --run-id <run-id>",
            "",
            "5. Never bypass write guard.",
            "   - immutable paths are denied;",
            "   - human-gated paths require explicit approval;",
            "   - unclassified paths should be triaged before mutation.",
            "   - pause at consultation checkpoints, state your recommendation, and ask before proceeding.",
            "",
            "6. Keep receipts and checkpoint evidence command-generated.",
            f"   - {bin_path} dispatch-task --project-root {project_root} --task-id <task-id> --run-id <run-id>;",
            f"   - {bin_path} trace-step --project-root {project_root} --task-id <task-id> --run-id <run-id> --step <step> --note <public-trace> --evidence <evidence>; echo or relay TRACE_OK;",
            f"   - {bin_path} phase-task --project-root {project_root} --task-id <task-id> --run-id <run-id> --phase <phase> --status completed --note <public-trace> --evidence <evidence>; echo or relay CHECKPOINT_OK;",
            f"   - {bin_path} capability-event --project-root {project_root} --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose <purpose> before/after MCP, skill, plugin/app, browser/Chrome/GitHub/security connector, subagent, orchestrator, shell, file_read, or important script use; echo or relay CAPABILITY_OK;",
            f"   - {bin_path} dispatch-report --project-root {project_root} --task-id <task-id> --run-id <run-id>; echo or relay AGENT_DISPATCH_OK as the full capability dispatch report, not only subagent usage;",
            f"   - {bin_path} decision-event --project-root {project_root} --task-id <task-id> --run-id <run-id> --kind <kind> --title <title> --summary <summary> --reason <reason> --evidence <evidence>; echo or relay DECISION_OK when the plan branches, changes, rolls back, or abandons a route;",
            f"   - {bin_path} thread-plan append --project-root {project_root} --thread-id <thread-id> --kind <plan|phase|branch|decision|progress|change|summary> --text <natural-language-note> when the chat-level plan changes or advances; relay THREAD_PLAN_OK;",
            f"   - {bin_path} thread-plan link-run --project-root {project_root} --thread-id <thread-id> --task-id <task-id> --run-id <run-id> to connect a run to the long-lived plan;",
            f"   - {bin_path} artifact-assert --project-root {project_root} --task-id <task-id> --run-id <run-id> --kind <kind> --path <artifact>; echo or relay EFFECT_OK;",
            f"   - {bin_path} eval-task --project-root {project_root} --task-id <task-id> --run-id <run-id>;",
            f"   - {bin_path} verify-context --project-root {project_root} --task-id <task-id> --run-id <run-id>;",
            f"   - {bin_path} verify-lifecycle --project-root {project_root} --task-id <task-id> --run-id <run-id>;",
            f"   - {bin_path} verify-effects --project-root {project_root} --task-id <task-id> --run-id <run-id>; echo or relay EFFECT_VERIFY_OK;",
            f"   - {bin_path} verify-decisions --project-root {project_root} --task-id <task-id> --run-id <run-id>; echo or relay DECISION_VERIFY_OK;",
            f"   - {bin_path} complete-task --project-root {project_root} --task-id <task-id> --run-id <run-id> --summary <summary>",
            f"   - for medium, high, or complex tasks, include the returned FLOW_OK Mermaid Mission Flow; if needed run {bin_path} flow-summary --project-root {project_root} --run-id <run-id>.",
            "",
            "7. For shared-fabric hosts, finish with canonical postflight.",
            "   - report [SYNC_OK] only after postflight succeeds.",
            "",
            "8. For reset or migration requests, stay reversible first.",
            f"   - {bin_path} reopen-task --project-root {project_root} --task-id <task-id> --reason <reason>  # same-task rerun only",
            f"   - {bin_path} reset-project --project-root {project_root} --mode <soft|hard> --dry-run",
            f"   - {bin_path} migrate-legacy-project --project-root {project_root} --write-plan",
            f"   - {bin_path} archive-legacy-project --project-root {project_root} --write-plan",
            "",
        ]
    )


def build_startup_prompt(project_root: Path) -> str:
    bin_path = knowledgeos_root_from_file() / "bin" / "knowledgeos"
    return "\n".join(
        [
            "# KnowledgeOS Startup Prompt",
            "",
            "Use this workspace's KnowledgeOS control plane.",
            "",
            f"Project root: `{project_root}`",
            "",
            "This prompt is only the session trigger. Durable rules live in `AGENTS.md`, `.agent-os/`, and the linked KnowledgeOS kernel/capability roots.",
            "",
            "Before substantial work:",
            "",
            "0. At the start of every conversation, make a visible KnowledgeOS judgment and relay `KOS_DECISION` with project state (`managed` or `unmanaged`), work class (`simple`, `substantial`, or `blocked`), required flow (`answer-only`, `task`, `spec`, `thread-plan`, or `full lifecycle`), and reason. This is a public routing decision, not hidden reasoning.",
            "1. Read `AGENTS.md`.",
            "2. Read `.agent-os/workspace.yaml`, `.agent-os/project.yaml`, `.agent-os/tasks.yaml`, `.agent-os/specs.yaml`, `.agent-os/phase-policy.yaml`, `.agent-os/decision-policy.yaml`, `.agent-os/effect-policy.yaml`, `.agent-os/decisions.yaml`, `.agent-os/evals.yaml`, `.agent-os/fabric-link.yaml`, `.agent-os/read-policy.yaml`, `.agent-os/write-policy.yaml`, `.agent-os/dispatch-policy.yaml`, and `.agent-os/tool-registry.yaml`.",
            f"3. Run `{bin_path} doctor --project-root {project_root} --summary` and do not proceed if it fails.",
            f"4. If the user says `create spec`, `align spec`, `对齐spec`, or equivalent, run `{bin_path} create-spec --project-root {project_root} --title \"<title>\"` or `{bin_path} align-spec --project-root {project_root} --task-id <task-id>` before execution.",
            f"5. If the user starts a durable plan/spec conversation, run `{bin_path} thread-plan current --project-root {project_root}` or `{bin_path} thread-plan start --project-root {project_root} --title \"<natural language goal>\"`; append natural-language progress with `{bin_path} thread-plan append --project-root {project_root} --thread-id <thread-id> --kind <kind> --text \"<plain note>\"` when the plan changes or advances, and relay `THREAD_PLAN_OK`.",
            f"6. Select or confirm one task id from `.agent-os/tasks.yaml`; if the user asks for new work and no ready task fits, run `{bin_path} create-task --project-root {project_root} --title \"<title>\" --type <type> --output <path> --acceptance \"<check>\"`.",
            f"7. Run `{bin_path} route-task --project-root {project_root} --task-id <task-id>`.",
            f"8. Run `{bin_path} dispatch-task --project-root {project_root} --task-id <task-id>` before invoking subagents, MCP tools, skills, workflows, or scripts; relay `AGENT_DISPATCH_PLAN`.",
            f"9. Before planned mutation, run `{bin_path} check-route-write --project-root {project_root} --task-id <task-id> --path <planned-path>`.",
            f"10. Create run evidence with `{bin_path} run-task --project-root {project_root} --task-id <task-id>`; this writes `spec-snapshot.md` and `context-pack.md`.",
            f"11. Write/update the execution context with `{bin_path} context-pack --project-root {project_root} --task-id <task-id> --run-id <run-id>` and `{bin_path} plan-task --project-root {project_root} --task-id <task-id> --run-id <run-id>`.",
            "12. Pause at consultation checkpoints, state your recommended next move, name the tradeoff, and ask the human whether to proceed.",
            f"13. Record dispatch evidence with `{bin_path} dispatch-task --project-root {project_root} --task-id <task-id> --run-id <run-id>` after the run exists.",
            f"14. Record public operational progress with `{bin_path} trace-step --project-root {project_root} --task-id <task-id> --run-id <run-id> --step <step> --note \"<public trace>\" --evidence \"<command/file/user confirmation>\"`; relay the returned `TRACE_OK` marker.",
            f"15. Record public phase evidence with `{bin_path} phase-task --project-root {project_root} --task-id <task-id> --run-id <run-id> --phase <route|plan|review|dispatch|execute|report> --status completed --note \"<public trace>\" --evidence \"<command/file/user confirmation>\"`; relay the returned `CHECKPOINT_OK` marker.",
            f"16. Record MCP, skill, plugin/app, browser/Chrome/GitHub/security connector, subagent, orchestrator, shell, file_read, or important script use with `{bin_path} capability-event --project-root {project_root} --task-id <task-id> --run-id <run-id> --kind <kind> --id <capability-id> --purpose \"<purpose>\"`; relay the returned `CAPABILITY_OK` marker.",
            f"17. Summarize actual capability dispatch with `{bin_path} dispatch-report --project-root {project_root} --task-id <task-id> --run-id <run-id>`; relay `AGENT_DISPATCH_OK`. Treat it as a full capability report: agents invoked/skipped, MCP, skills, plugins/apps, browser/Chrome/GitHub/security connectors, scripts, shell, file reads, evidence files, and gaps. If no subagent was used, still report `agents=0` and explain why.",
            f"18. Record public decision changes with `{bin_path} decision-event --project-root {project_root} --task-id <task-id> --run-id <run-id> --kind <kind> --title \"<title>\" --summary \"<summary>\" --reason \"<reason>\" --evidence \"<evidence>\"`; relay the returned `DECISION_OK` marker when plans branch, change, roll back, or abandon a route.",
            f"19. Verify real side effects with `{bin_path} artifact-assert --project-root {project_root} --task-id <task-id> --run-id <run-id> --kind <kind> --path <artifact>`; relay the returned `EFFECT_OK` marker.",
            f"20. Run `{bin_path} eval-task --project-root {project_root} --task-id <task-id> --run-id <run-id>`; do not manually append eval status.",
            f"21. Run `{bin_path} verify-context --project-root {project_root} --task-id <task-id> --run-id <run-id>`, `{bin_path} verify-lifecycle --project-root {project_root} --task-id <task-id> --run-id <run-id>`, `{bin_path} verify-effects --project-root {project_root} --task-id <task-id> --run-id <run-id>`, and `{bin_path} verify-decisions --project-root {project_root} --task-id <task-id> --run-id <run-id>`; relay `EFFECT_VERIFY_OK` and `DECISION_VERIFY_OK` before claiming verification success.",
            f"22. Use `{bin_path} complete-task --project-root {project_root} --task-id <task-id> --run-id <run-id> --summary \"<summary>\"`; it must enforce spec/context/plan, lifecycle, capability visibility, effect verification, decision verification, visible dispatch reporting, and required postflight.",
            f"23. For medium, high, or complex tasks, include the returned `FLOW_OK` Mermaid Mission Flow in the final answer; if needed, run `{bin_path} flow-summary --project-root {project_root} --run-id <run-id>`.",
            "24. If a shared-fabric postflight hook is configured, report `[SYNC_OK]` only after `complete-task` returns `sync_status: SYNC_OK`.",
            f"25. For reset requests, run `{bin_path} reset-project --project-root {project_root} --mode <soft|hard> --dry-run` before destructive action.",
            f"26. For old-project reorganization requests, run `{bin_path} migrate-legacy-project --project-root {project_root} --write-plan` before moving files.",
            f"27. For historical/superseded files that should be stored but not read by default, run `{bin_path} archive-legacy-project --project-root {project_root} --write-plan` before moving files into `archive/`.",
            "",
            "Never skip the initial `KOS_DECISION`. Never claim boot, route, dispatch, write safety, spec alignment, thread plan, context pack, plan, trace, checkpoint, capability, agent dispatch, decision, effect, eval, completion, flow, or sync success without command evidence.",
            "",
        ]
    )


def redact_project_path(project_root: Path, path: Path | str, show_paths: bool) -> str:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve()
    if show_paths:
        return str(resolved)
    try:
        relative = resolved.relative_to(project_root.resolve())
    except ValueError:
        return "<EXTERNAL_PATH>"
    return "<PROJECT_ROOT>" if not relative.as_posix() or relative.as_posix() == "." else f"<PROJECT_ROOT>/{relative.as_posix()}"


def redact_config_paths(values: dict[str, str], project_root: Path, show_paths: bool) -> dict[str, str]:
    path_keys = {"root", "governance_root", "capability_root", "implementation_root"}
    redacted: dict[str, str] = {}
    for key, value in values.items():
        if key in path_keys and value and "CHANGE_ME" not in value:
            redacted[key] = redact_project_path(project_root, value, show_paths)
        else:
            redacted[key] = value
    return redacted


def latest_run_state(project_root: Path, show_paths: bool) -> dict[str, Any] | None:
    runs_root = project_root / ".agent-os" / "runs"
    if not runs_root.exists():
        return None
    run_dirs = sorted(path for path in runs_root.glob("RUN-*") if path.is_dir())
    if not run_dirs:
        return None
    latest = run_dirs[-1]
    run_yaml = latest / "run.yaml"
    metadata = parse_scalar_values(run_yaml, {"run_id", "task_id", "status", "eval_profile"}) if run_yaml.exists() else {}
    return {
        "run_id": metadata.get("run_id", latest.name),
        "task_id": metadata.get("task_id", ""),
        "status": metadata.get("status", "unknown"),
        "eval_profile": metadata.get("eval_profile", ""),
        "eval_passed": eval_has_passed(latest / "eval.md"),
        "path": redact_project_path(project_root, latest, show_paths),
    }


def task_board_state(project_root: Path) -> dict[str, Any]:
    tasks = parse_tasks(project_root / ".agent-os" / "tasks.yaml")
    counts: dict[str, int] = {}
    active: list[dict[str, str]] = []
    for task in tasks:
        status = task.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
        if status in {"in_progress", "ready", "blocked"}:
            active.append({key: task.get(key, "") for key in ["id", "title", "type", "status", "complexity", "risk"]})

    def first_with_status(status: str) -> dict[str, str] | None:
        return next((task for task in active if task.get("status") == status), None)

    current = first_with_status("in_progress") or first_with_status("ready") or first_with_status("blocked")
    return {
        "total": len(tasks),
        "counts": counts,
        "current": current,
        "active": active[:12],
    }


RUNTIME_ADAPTER_DEFINITIONS = [
    {
        "id": "mock",
        "label": "Mock Runtime",
        "kind": "builtin",
        "command": "",
        "optional": False,
        "purpose": "Safe default for Workbench monitoring checks.",
    },
    {
        "id": "gemini-cli",
        "label": "Gemini CLI",
        "kind": "cli",
        "command": "gemini",
        "optional": True,
        "purpose": "Local plan-based LLM runtime adapter candidate.",
    },
    {
        "id": "codex-cli",
        "label": "Codex CLI",
        "kind": "cli",
        "command": "codex",
        "optional": True,
        "purpose": "Local development-agent runtime adapter candidate.",
    },
]


def build_runtime_adapters_state(project_root: Path, *, show_paths: bool = False) -> dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    adapters: list[dict[str, Any]] = []
    for definition in RUNTIME_ADAPTER_DEFINITIONS:
        command = definition["command"]
        if definition["kind"] == "builtin":
            status = "available"
            executable = "builtin"
        else:
            found = shutil.which(command)
            status = "available" if found else "missing"
            executable = found if found and show_paths else ("<EXTERNAL_PATH>" if found else "not_found")
        adapters.append(
            {
                **definition,
                "status": status,
                "executable": executable,
                "execution": "not_started",
                "execution_mode": "disabled_by_default",
                "default_cwd": "<APP_RUNTIME>",
                "project_mutation": False,
                "requires_os_route_for_mutation": True,
            }
        )

    runtime_subagents: list[dict[str, Any]] = []
    try:
        registry_entries = load_tool_registry(project_root)
    except FileNotFoundError:
        registry_entries = []
    for entry in registry_entries:
        if entry.get("kind") != "subagent":
            continue
        if entry.get("status") not in ACTIVE_TOOL_STATUSES:
            continue
        if not is_runtime_callable_subagent(entry):
            continue
        runtime_subagents.append(
            {
                "id": entry.get("id", ""),
                "status": "registered",
                "runtime": entry.get("runtime", "codex"),
                "runtime_tool": entry.get("runtime_tool", ""),
                "runtime_agent_type": runtime_agent_type_for_entry(entry),
                "adapter": entry.get("adapter", ""),
                "execution_mode": entry.get("execution_mode", ""),
                "human_gate": entry.get("human_gate", ""),
            }
        )

    missing_required = [item["id"] for item in adapters if item["status"] != "available" and not item["optional"]]
    available_count = sum(1 for item in adapters if item["status"] == "available")
    return {
        "schema_version": "knowledgeos.runtime-adapters.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": redact_project_path(project_root, project_root, show_paths),
        "privacy": {"paths_redacted": not show_paths},
        "status": "ready" if not missing_required else "blocked",
        "available_count": available_count,
        "total": len(adapters),
        "adapters": adapters,
        "runtime_subagents": sorted(runtime_subagents, key=lambda item: item["id"]),
        "policy": {
            "default_runtime": "mock",
            "real_cli_execution": "disabled_until_adapter_phase",
            "native_subagent_execution": "delegated_to_codex_runtime_tool",
            "project_cwd_allowed": False,
            "project_mutation_allowed": False,
            "os_route_required_for_mutation": True,
        },
    }


def maestro_role_spec_path(subagent_id: str) -> Path:
    root = knowledgeos_root_from_file()
    runtime_path = root / "capability-layer" / "subagents" / "maestro" / f"{subagent_id}.yaml"
    if runtime_path.exists():
        return runtime_path
    return root / "templates" / "capability-layer" / "subagents" / "maestro" / f"{subagent_id}.yaml"


def load_maestro_role_spec(subagent_id: str) -> dict[str, str]:
    path = maestro_role_spec_path(subagent_id)
    if not path.exists():
        return {}
    keys = {"id", "display_name", "runtime_agent_type", "default_scope", "write_policy_hint", "role_prompt", "recommended_task_fit"}
    return parse_scalar_values(path, keys)


def build_default_subagent_role_prompt(entry: dict[str, str]) -> str:
    subagent_id = entry.get("id", "")
    runtime_type = runtime_agent_type_for_entry(entry) or "default"
    if subagent_id.startswith("maestro-"):
        readable = subagent_id.removeprefix("maestro-").replace("-", " ")
        return (
            f"Act as the Maestro {readable} adapter. Use the {runtime_type} Codex subagent runtime. "
            "Return concise findings, concrete evidence, and any gaps. Do not mutate files unless the parent task route allows it."
        )
    return (
        f"Act as {subagent_id} through the Codex {runtime_type} subagent runtime. "
        "Return concise findings, concrete evidence, and any gaps."
    )


def build_subagent_adapter(project_root: Path, subagent_id: str, *, task_id: str = "", run_id: str = "", purpose: str = "") -> dict[str, Any]:
    entries = load_tool_registry(project_root)
    entry = next((item for item in entries if item.get("id") == subagent_id), None)
    if not entry:
        raise KeyError(f"unknown subagent id: {subagent_id}")
    if entry.get("kind") != "subagent":
        raise ValueError(f"{subagent_id} is not a subagent entry")
    runtime_type = runtime_agent_type_for_entry(entry)
    if runtime_type not in CODEX_RUNTIME_AGENT_TYPES:
        raise ValueError(f"{subagent_id} does not declare a supported runtime_agent_type")
    runtime_tool = entry.get("runtime_tool", "")
    if runtime_tool != CODEX_RUNTIME_TOOL:
        raise ValueError(f"{subagent_id} is not backed by {CODEX_RUNTIME_TOOL}")
    role_spec = load_maestro_role_spec(subagent_id) if subagent_id.startswith("maestro-") else {}
    role_prompt = role_spec.get("role_prompt") or build_default_subagent_role_prompt(entry)
    capability_event_suggestion = (
        f"knowledgeos capability-event --project-root . --task-id {task_id or '<task-id>'} "
        f"--run-id {run_id or '<run-id>'} --kind subagent --id {subagent_id} "
        f"--purpose \"{purpose or 'Codex runtime subagent delegated work'}\""
    )
    if run_id and task_id:
        run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
        append_command_event(
            run_dir,
            "subagent-adapter",
            task_id,
            run_id,
            status="ready",
            subagent_id=subagent_id,
            runtime_tool=runtime_tool,
            runtime_agent_type=runtime_type,
        )
    return {
        "status": "ready",
        "subagent_adapter_marker": "SUBAGENT_ADAPTER_OK",
        "marker": f"SUBAGENT_ADAPTER_OK id={subagent_id} runtime_agent_type={runtime_type}",
        "id": subagent_id,
        "runtime": entry.get("runtime", "codex"),
        "runtime_tool": runtime_tool,
        "runtime_agent_type": runtime_type,
        "adapter": entry.get("adapter", ""),
        "adapter_role": entry.get("adapter_role", ""),
        "role_prompt": role_prompt,
        "role_spec": f"capability-layer/subagents/maestro/{subagent_id}.yaml" if subagent_id.startswith("maestro-") else "",
        "capability_event_suggestion": capability_event_suggestion,
        "actual_execution": "call Codex runtime tool multi_agent_v1.spawn_agent with runtime_agent_type and role_prompt",
    }


def build_workbench_state(project_root: Path, *, show_paths: bool = False, skip_external_checks: bool = False) -> dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    generated_at = datetime.now(timezone.utc).isoformat()
    state: dict[str, Any] = {
        "schema_version": "knowledgeos.workbench-state.v1",
        "generated_at": generated_at,
        "project_root": redact_project_path(project_root, project_root, show_paths),
        "project_name": project_root.name,
        "privacy": {"paths_redacted": not show_paths},
    }

    agent_os = project_root / ".agent-os"
    if not agent_os.is_dir():
        return {
            **state,
            "managed": False,
            "status": "unmanaged",
            "boot": {"claim": "KOS_UNMANAGED", "doctor": "not_run"},
            "system_black_box": {
                "doctor": {"status": "not_run", "reason": "missing .agent-os control plane"},
                "latest_run": None,
                "latest_receipt": None,
                "current_handoff": None,
            },
            "recommended_actions": [
                "Initialize this folder with KnowledgeOS before route-bound execution.",
                "Proceed in degraded/manual mode only if initialization is not desired.",
            ],
        }

    doctor_results = deep_validate_project(project_root, skip_external=skip_external_checks)
    doctor_summary = summarize_results(doctor_results)
    workspace = parse_scalar_values(
        agent_os / "workspace.yaml",
        {"workspace_id", "name", "root", "active_project", "phase", "last_run", "last_sync_status", "governance_root", "capability_root", "implementation_root"},
    )
    project = parse_scalar_values(agent_os / "project.yaml", {"id", "name", "status", "current_phase"})
    route_profiles = load_workflow_profiles(project_root)

    try:
        registry = summarize_tool_registry(project_root)
        capabilities = {
            "ok": registry["ok"],
            "counts": registry["counts"],
            "entries": [tool_summary(entry) for entry in registry["entries"]],
        }
    except FileNotFoundError as exc:
        capabilities = {"ok": False, "counts": {}, "entries": [], "error": str(exc)}

    latest_receipt = project_root / ".agent-os" / "receipts" / "latest.md"
    current_handoff = project_root / ".agent-os" / "handoffs" / "current.md"
    return {
        **state,
        "managed": True,
        "status": "managed_ok" if doctor_summary["status"] == "ok" else "managed_attention",
        "boot": {"claim": "BOOT_OK" if doctor_summary["status"] == "ok" else "BOOT_BLOCKED", "doctor": doctor_summary["status"]},
        "workspace": redact_config_paths(workspace, project_root, show_paths),
        "project": project,
        "tasks": task_board_state(project_root),
        "routes": {"count": len(route_profiles), "task_types": sorted(route_profiles)},
        "capabilities": capabilities,
        "runtime_adapters": build_runtime_adapters_state(project_root, show_paths=show_paths),
        "system_black_box": {
            "doctor": doctor_summary,
            "latest_run": latest_run_state(project_root, show_paths),
            "latest_receipt": redact_project_path(project_root, latest_receipt, show_paths) if latest_receipt.exists() else None,
            "current_handoff": redact_project_path(project_root, current_handoff, show_paths) if current_handoff.exists() else None,
        },
        "recommended_actions": [] if doctor_summary["status"] == "ok" else ["Open System Black Box and inspect failed doctor checks."],
    }


def latest_run_for_task(project_root: Path, task_id: str, show_paths: bool) -> dict[str, Any] | None:
    runs_root = project_root / ".agent-os" / "runs"
    if not runs_root.exists():
        return None
    matches: list[Path] = []
    for run_dir in sorted(path for path in runs_root.glob("RUN-*") if path.is_dir()):
        run_yaml = run_dir / "run.yaml"
        if not run_yaml.exists():
            continue
        metadata = parse_scalar_values(run_yaml, {"task_id"})
        if metadata.get("task_id") == task_id:
            matches.append(run_dir)
    if not matches:
        return None
    latest = matches[-1]
    metadata = parse_scalar_values(latest / "run.yaml", {"run_id", "task_id", "status", "eval_profile"})
    return {
        "run_id": metadata.get("run_id", latest.name),
        "task_id": metadata.get("task_id", task_id),
        "status": metadata.get("status", "unknown"),
        "eval_profile": metadata.get("eval_profile", ""),
        "eval_passed": eval_has_passed(latest / "eval.md"),
        "eval_generated": eval_is_knowledgeos_generated(latest / "eval.md"),
        "receipt_exists": (latest / "receipt.md").exists(),
        "handoff_exists": (latest / "handoff.md").exists(),
        "path": redact_project_path(project_root, latest, show_paths),
    }


def lifecycle_stage(key: str, label: str, status: str, detail: str, command: str = "", artifact: str | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
        "command": command,
        "artifact": artifact,
    }


def first_incomplete_stage(stages: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((stage for stage in stages if stage.get("status") in {"active", "pending", "blocked"}), None)


def build_workbench_lifecycle(
    project_root: Path,
    *,
    task_id: str | None = None,
    show_paths: bool = False,
    skip_external_checks: bool = False,
) -> dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    state = build_workbench_state(project_root, show_paths=show_paths, skip_external_checks=skip_external_checks)
    generated_at = datetime.now(timezone.utc).isoformat()
    base: dict[str, Any] = {
        "schema_version": "knowledgeos.workbench-lifecycle.v1",
        "generated_at": generated_at,
        "project_root": redact_project_path(project_root, project_root, show_paths),
        "privacy": {"paths_redacted": not show_paths},
        "managed": state.get("managed", False),
    }
    if not state.get("managed"):
        stages = [
            lifecycle_stage("doctor", "Doctor", "blocked", "No .agent-os control plane is present."),
            lifecycle_stage("route", "Route", "pending", "Initialize KnowledgeOS before routing."),
            lifecycle_stage("dispatch", "Dispatch", "pending", "No routed task is available."),
            lifecycle_stage("write_guard", "Write Guard", "pending", "Write policy is unavailable."),
            lifecycle_stage("run", "Run", "pending", "No run evidence exists."),
            lifecycle_stage("eval", "Eval", "pending", "No eval evidence exists."),
            lifecycle_stage("receipt", "Receipt", "pending", "No receipt exists."),
        ]
        return {**base, "status": "unmanaged", "selected_task": None, "stages": stages, "next_action": stages[0]}

    current = state.get("tasks", {}).get("current") or {}
    selected_task_id = task_id or current.get("id")
    selected_task: dict[str, str] | None = None
    route: dict[str, Any] | None = None
    dispatch: dict[str, Any] | None = None
    run_state: dict[str, Any] | None = None
    planned_outputs: list[str] = []
    write_checks: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []

    doctor = state.get("system_black_box", {}).get("doctor", {})
    doctor_ok = doctor.get("status") == "ok"
    stages.append(
        lifecycle_stage(
            "doctor",
            "Doctor",
            "ok" if doctor_ok else "blocked",
            f"{doctor.get('passed', 0)}/{doctor.get('checks', 0)} checks passed",
            "doctor --project-root <PROJECT_ROOT> --summary",
        )
    )

    if selected_task_id:
        try:
            selected_task = find_task(project_root, selected_task_id)
        except (FileNotFoundError, KeyError):
            selected_task = None

    if not selected_task or not selected_task_id:
        stages.extend(
            [
                lifecycle_stage("route", "Route", "pending", "No active task selected."),
                lifecycle_stage("dispatch", "Dispatch", "pending", "Select a task before dispatch."),
                lifecycle_stage("write_guard", "Write Guard", "pending", "No planned outputs to inspect."),
                lifecycle_stage("run", "Run", "pending", "No run evidence exists."),
                lifecycle_stage("eval", "Eval", "pending", "No eval evidence exists."),
                lifecycle_stage("receipt", "Receipt", "pending", "No receipt exists."),
            ]
        )
        return {
            **base,
            "status": "no_task",
            "selected_task": None,
            "stages": stages,
            "next_action": first_incomplete_stage(stages),
        }

    try:
        route = build_task_route(project_root, selected_task_id, None)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        route = {"status": "human_triage_required", "reason": str(exc), "task_id": selected_task_id}
    route_ok = route.get("status") == "routed"
    stages.append(
        lifecycle_stage(
            "route",
            "Route",
            "ok" if route_ok else "blocked",
            route.get("eval_profile") or route.get("reason", "Task route resolved."),
            "route-task --project-root <PROJECT_ROOT> --task-id <TASK_ID>",
        )
    )

    if route_ok:
        try:
            dispatch = build_dispatch_plan(project_root, selected_task_id)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            dispatch = {"status": "human_triage_required", "reason": str(exc)}
    dispatch_ok = bool(dispatch and dispatch.get("status") == "dispatch_ready")
    stages.append(
        lifecycle_stage(
            "dispatch",
            "Dispatch",
            "ok" if dispatch_ok else ("pending" if route_ok else "blocked"),
            f"{len(dispatch.get('steps', [])) if dispatch else 0} dispatch stage(s) available" if dispatch_ok else (dispatch or {}).get("reason", "Waiting for route."),
            "dispatch-task --project-root <PROJECT_ROOT> --task-id <TASK_ID>",
        )
    )

    planned_outputs = task_declared_outputs(project_root, selected_task_id)
    if route_ok and planned_outputs:
        for output in planned_outputs:
            try:
                decision = classify_route_write(project_root, selected_task_id, output)
            except (FileNotFoundError, KeyError, ValueError) as exc:
                decision = {"decision": "blocked", "path": output, "reason": str(exc)}
            write_checks.append(
                {
                    "path": decision.get("path", output),
                    "decision": decision.get("decision", "unknown"),
                    "reason": decision.get("reason", ""),
                }
            )
    if not route_ok:
        write_status = "blocked"
        write_detail = "Route must pass before write guard can inspect outputs."
    elif not planned_outputs:
        write_status = "pending"
        write_detail = "Task has no declared outputs to inspect."
    elif all(item["decision"] == "allow" for item in write_checks):
        write_status = "ok" if selected_task.get("status") == "completed" else "active"
        write_detail = f"{len(write_checks)} planned output(s) allowed by route."
    else:
        write_status = "blocked"
        write_detail = "At least one planned output is outside write policy or route scope."
    stages.append(
        lifecycle_stage(
            "write_guard",
            "Write Guard",
            write_status,
            write_detail,
            "check-route-write --project-root <PROJECT_ROOT> --task-id <TASK_ID> --path <PLANNED_PATH>",
        )
    )

    run_state = latest_run_for_task(project_root, selected_task_id, show_paths)
    run_status = "ok" if run_state else ("pending" if write_status in {"ok", "active"} else "blocked")
    stages.append(
        lifecycle_stage(
            "run",
            "Run",
            run_status,
            f"{run_state['run_id']} status={run_state['status']}" if run_state else "No run evidence for this task yet.",
            "run-task --project-root <PROJECT_ROOT> --task-id <TASK_ID>",
            run_state.get("path") if run_state else None,
        )
    )

    eval_status = "ok" if run_state and run_state.get("eval_passed") else ("pending" if run_state else "pending")
    stages.append(
        lifecycle_stage(
            "eval",
            "Eval",
            eval_status,
            "Eval passed through KnowledgeOS." if eval_status == "ok" else "Waiting for eval-task evidence.",
            "eval-task --project-root <PROJECT_ROOT> --task-id <TASK_ID> --run-id <RUN_ID>",
            run_state.get("path") if run_state else None,
        )
    )

    receipt_ok = bool(run_state and run_state.get("status") == "completed" and run_state.get("receipt_exists"))
    stages.append(
        lifecycle_stage(
            "receipt",
            "Receipt",
            "ok" if receipt_ok else ("pending" if run_state else "pending"),
            "Run receipt and handoff are recorded." if receipt_ok else "Completion receipt is not recorded for this task yet.",
            "complete-task --project-root <PROJECT_ROOT> --task-id <TASK_ID> --run-id <RUN_ID> --summary <SUMMARY>",
            run_state.get("path") if run_state else None,
        )
    )

    return {
        **base,
        "status": "ready" if doctor_ok and route_ok else "attention",
        "selected_task": {key: selected_task.get(key, "") for key in ["id", "title", "type", "status", "complexity", "risk"]},
        "route": route,
        "dispatch": dispatch,
        "planned_outputs": planned_outputs,
        "write_checks": write_checks,
        "latest_run": run_state,
        "stages": stages,
        "next_action": first_incomplete_stage(stages),
    }


def workbench_static_root() -> Path:
    return knowledgeos_root_from_file() / "examples" / "workbench"


MUTATION_INTENT_HINTS = (
    "write",
    "create",
    "edit",
    "modify",
    "delete",
    "remove",
    "move",
    "rename",
    "run",
    "execute",
    "save",
    "生成",
    "创建",
    "写",
    "修改",
    "删除",
    "移动",
    "重命名",
    "运行",
    "执行",
    "保存",
)


def redact_text_project_paths(project_root: Path, text: str, show_paths: bool) -> str:
    if show_paths:
        return text
    return text.replace(str(project_root.resolve()), "<PROJECT_ROOT>")


def intent_recommendation(prompt: str) -> str:
    lowered = prompt.lower()
    return "route_through_os" if any(hint in lowered for hint in MUTATION_INTENT_HINTS) else "stay_in_sandbox"


def build_ask_sandbox_response(project_root: Path, prompt: str, *, runtime: str = "mock", show_paths: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    project_root = project_root.expanduser().resolve()
    clean_prompt = prompt.strip()
    recommendation = intent_recommendation(clean_prompt)
    if recommendation == "route_through_os":
        response = (
            "This looks like it may change project state. The sandbox will not execute it. "
            "Route it through KnowledgeOS with a task id, dispatch plan, write check, run evidence, eval, and completion."
        )
    else:
        response = (
            "Sandbox answer: this intent can stay in read-only exploration for now. "
            "No project files were read beyond control-plane state and no mutation path was opened."
        )
    duration_ms = int((time.monotonic() - started) * 1000)
    return {
        "schema_version": "knowledgeos.ask-sandbox.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_sandbox",
        "runtime": runtime,
        "status": "ok",
        "project_root": redact_project_path(project_root, project_root, show_paths),
        "privacy": {"paths_redacted": not show_paths},
        "prompt": redact_text_project_paths(project_root, clean_prompt, show_paths),
        "response": response,
        "recommended_next_step": recommendation,
        "executed": False,
        "project_mutation": False,
        "recommended_os_commands": [
            "doctor --project-root <PROJECT_ROOT> --summary",
            "route-task --project-root <PROJECT_ROOT> --task-id <TASK_ID>",
            "dispatch-task --project-root <PROJECT_ROOT> --task-id <TASK_ID>",
            "check-route-write --project-root <PROJECT_ROOT> --task-id <TASK_ID> --path <PLANNED_PATH>",
            "run-task --project-root <PROJECT_ROOT> --task-id <TASK_ID>",
            "eval-task --project-root <PROJECT_ROOT> --task-id <TASK_ID> --run-id <RUN_ID>",
            "complete-task --project-root <PROJECT_ROOT> --task-id <TASK_ID> --run-id <RUN_ID> --summary <SUMMARY>",
        ]
        if recommendation == "route_through_os"
        else [],
        "system_black_box": {
            "command": "mock",
            "exit_code": 0,
            "duration_ms": duration_ms,
            "writes_allowed": False,
            "os_execution": "not_started",
        },
    }


def send_json(handler: SimpleHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def build_workbench_preview_handler(
    project_root: Path,
    static_root: Path,
    *,
    show_paths: bool = False,
    skip_linked_checks: bool = False,
) -> type[SimpleHTTPRequestHandler]:
    project_root = project_root.expanduser().resolve()
    static_root = static_root.expanduser().resolve()

    class WorkbenchPreviewHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(static_root), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/workbench-state.json", "/api/workbench-state"}:
                payload = build_workbench_state(project_root, show_paths=show_paths, skip_external_checks=skip_linked_checks)
                send_json(self, 200, payload)
                return
            if parsed.path in {"/workbench-lifecycle.json", "/api/workbench-lifecycle"}:
                query = parse_qs(parsed.query)
                task_id = (query.get("task-id") or query.get("task_id") or [None])[0]
                payload = build_workbench_lifecycle(
                    project_root,
                    task_id=task_id,
                    show_paths=show_paths,
                    skip_external_checks=skip_linked_checks,
                )
                send_json(self, 200, payload)
                return
            if parsed.path == "/healthz":
                body = b"ok\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def do_POST(self) -> None:
            send_json(self, 404, {"status": "error", "reason": "Workbench preview is monitoring-only"})

    return WorkbenchPreviewHandler


def create_run_envelope(project_root: Path, task_id: str, summary: str, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    task = find_task(project_root, task_id)
    task_status = task.get("status", "")
    if task_status not in RUNNABLE_TASK_STATUSES and not force:
        raise ValueError(f"task {task_id} status is {task_status!r}; expected one of {sorted(RUNNABLE_TASK_STATUSES)}")
    route = build_task_route(project_root, task_id, None)
    if route.get("status") != "routed":
        raise ValueError(f"task {task_id} is not runnable because routing failed: {route.get('reason', 'unknown route failure')}")
    run_id = next_run_id(project_root, task_id)
    run_dir = project_root / ".agent-os" / "runs" / run_id
    created = [
        run_dir / "run.yaml",
        run_dir / "prompt.md",
        run_dir / "receipt.md",
        run_dir / "diff_summary.md",
        run_dir / "eval.md",
        run_dir / "handoff.md",
        run_dir / "spec-snapshot.md",
        run_dir / "context-pack.md",
    ]
    if not dry_run:
        run_dir.mkdir(parents=True, exist_ok=False)
        write_text(
            run_dir / "run.yaml",
            "\n".join(
                [
                    f"run_id: {run_id}",
                    f"task_id: {task_id}",
                    f"task_title: {task.get('title', '')}",
                    f"task_type: {task.get('type', '')}",
                    f"task_status_at_start: {task_status}",
                    f"status: started",
                    f"route_status: {route.get('status', '')}",
                    f"eval_profile: {route.get('eval_profile', '')}",
                    f"human_gate: {route.get('human_gate', '')}",
                    f"created_at: {datetime.now(timezone.utc).isoformat()}",
                    "allowed_outputs:",
                    *[f"  - {item}" for item in route.get("allowed_outputs", [])],
                    "",
                ]
            ),
        )
        write_text(run_dir / "prompt.md", f"# Prompt\n\nTask: {task_id}\n\n{summary}\n")
        receipt = f"# Receipt\n\nRun: {run_id}\n\nTask: {task_id}\n\nStatus: started\n\nSummary: {summary}\n"
        write_text(run_dir / "receipt.md", receipt)
        write_text(run_dir / "diff_summary.md", "# Diff Summary\n\nNo mutations recorded yet.\n")
        write_text(run_dir / "eval.md", "# Eval\n\nNo eval has run yet.\n")
        write_text(run_dir / "handoff.md", f"# Handoff\n\nCurrent run: {run_id}\n\nNext agent should inspect `run.yaml` and `receipt.md`.\n")
        append_command_event(run_dir, "run-task", task_id, run_id, status="started", lifecycle_contract="capability-visible-v1")
        write_context_pack(project_root, task_id, run_id, summary=summary)
        write_text(project_root / ".agent-os" / "receipts" / "latest.md", receipt)
        write_text(project_root / ".agent-os" / "handoffs" / "current.md", f"# Current Handoff\n\nCurrent run: {run_id}\n\nTask: {task_id}\n")
    return {"run_id": run_id, "task": task, "route": route, "created": [str(p) for p in created], "dry_run": dry_run}


def next_run_id(project_root: Path, task_id: str) -> str:
    runs_root = project_root / ".agent-os" / "runs"
    base = f"RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(task_id)}"
    for index in range(100):
        candidate = base if index == 0 else f"{base}-{index:02d}"
        if not (runs_root / candidate).exists():
            return candidate
    raise ValueError(f"could not allocate a unique run id for {task_id}")


def ensure_run_belongs_to_task(project_root: Path, task_id: str, run_id: str) -> Path:
    find_task(project_root, task_id)
    run_dir = resolve_run_dir(project_root, run_id)
    if not run_dir.exists():
        raise FileNotFoundError(f"missing run directory: {run_dir}")
    run_yaml = run_dir / "run.yaml"
    if not run_yaml.exists():
        raise FileNotFoundError(f"missing run metadata: {run_yaml}")
    metadata = parse_scalar_values(run_yaml, {"run_id", "task_id", "status"})
    if metadata.get("task_id") != task_id:
        raise ValueError(f"run {run_id} belongs to task {metadata.get('task_id')!r}, not {task_id!r}")
    return run_dir


def record_task_phase(
    project_root: Path,
    task_id: str,
    run_id: str,
    *,
    phase: str,
    status: str,
    note: str,
    evidence: str = "",
    skip_reason: str = "",
) -> dict[str, Any]:
    policy = parse_phase_policy(project_root)
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    allowed_phases = policy["required_phases"]["default"]
    if phase not in allowed_phases:
        raise ValueError(f"invalid phase {phase!r}; expected one of {allowed_phases}")
    if status not in PHASE_STATUSES:
        raise ValueError(f"invalid phase status {status!r}; expected one of {sorted(PHASE_STATUSES)}")
    if status == "skipped" and policy["skip_policy"]["require_skip_reason"] and not skip_reason.strip():
        raise ValueError("skip reason is required when phase status is skipped")
    if not note.strip():
        raise ValueError("--note is required")
    record = {
        "task_id": task_id,
        "run_id": run_id,
        "phase": phase,
        "status": status,
        "note": note.strip(),
        "evidence": evidence.strip(),
        "skip_reason": skip_reason.strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    ledger_path = run_dir / "phases.ndjson"
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    append_command_event(run_dir, "phase-task", task_id, run_id, phase=phase, status=status)
    marker = f"CHECKPOINT_OK phase={phase} status={status} evidence={short_marker_value(evidence or note)}"
    return {"status": "recorded", "checkpoint_marker": "CHECKPOINT_OK", "marker": marker, "ledger": str(ledger_path), "record": record}


def record_dispatch_event(project_root: Path, task_id: str, run_id: str, dispatch: dict[str, Any]) -> dict[str, Any]:
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    required_stages = [step.get("stage", "") for step in dispatch.get("steps", []) if step.get("required")]
    planned_tools: list[dict[str, str]] = []
    for step in dispatch.get("steps", []):
        stage = str(step.get("stage", ""))
        for tool in step.get("tools", []) or []:
            if isinstance(tool, dict):
                planned_tools.append(
                    {
                        "stage": stage,
                        "kind": str(tool.get("kind", "")),
                        "id": str(tool.get("id", "")),
                        "required": str(bool(step.get("required"))).lower(),
                        "runtime_tool": str(tool.get("runtime_tool", "")),
                        "runtime_agent_type": str(tool.get("runtime_agent_type", "")),
                        "runtime_callable": str(bool(tool.get("runtime_callable"))).lower(),
                    }
                )
    append_command_event(
        run_dir,
        "dispatch-task",
        task_id,
        run_id,
        status=str(dispatch.get("status", "")),
        required_stages=required_stages,
        planned_tools=planned_tools,
    )
    return {"run_id": run_id, "required_stages": required_stages, "command_events": str(command_events_path(run_dir))}


def record_capability_event(
    project_root: Path,
    task_id: str,
    run_id: str,
    *,
    kind: str,
    capability_id: str,
    purpose: str,
    status: str = "completed",
    evidence: str = "",
) -> dict[str, Any]:
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    if kind not in CAPABILITY_EVENT_KINDS:
        raise ValueError(f"invalid capability kind {kind!r}; expected one of {sorted(CAPABILITY_EVENT_KINDS)}")
    if not capability_id.strip():
        raise ValueError("--id is required")
    if not purpose.strip():
        raise ValueError("--purpose is required")
    capability_event_id = (
        "CAP-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + safe_slug(f"{kind}-{capability_id.strip()}")[:48]
    )
    record = {
        "capability_event_id": capability_event_id,
        "task_id": task_id,
        "run_id": run_id,
        "kind": kind,
        "id": capability_id.strip(),
        "purpose": purpose.strip(),
        "status": status.strip() or "completed",
        "evidence": evidence.strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    event_path = capability_events_path(run_dir)
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    append_command_event(
        run_dir,
        "capability-event",
        task_id,
        run_id,
        capability_event_id=capability_event_id,
        kind=kind,
        id=capability_id.strip(),
        status=record["status"],
    )
    marker = f"CAPABILITY_OK kind={kind} id={capability_id.strip()} purpose={short_marker_value(purpose)}"
    return {
        "status": "recorded",
        "capability_marker": "CAPABILITY_OK",
        "capability_event_id": capability_event_id,
        "marker": marker,
        "ledger": str(event_path),
        "record": record,
    }


def build_dispatch_report(project_root: Path, task_id: str, run_id: str) -> dict[str, Any]:
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    events = [event for event in load_capability_events(run_dir) if "_invalid_json" not in event]
    invoked_events = [
        event
        for event in events
        if str(event.get("status", "completed")).strip().lower() not in SKIPPED_CAPABILITY_STATUSES
    ]
    skipped_events = [
        event
        for event in events
        if str(event.get("status", "completed")).strip().lower() in SKIPPED_CAPABILITY_STATUSES
    ]
    agent_events = [event for event in invoked_events if str(event.get("kind", "")) in AGENT_CAPABILITY_KINDS]
    skipped_agent_events = [event for event in skipped_events if str(event.get("kind", "")) in AGENT_CAPABILITY_KINDS]
    runtime_gap_events = [
        event
        for event in skipped_agent_events
        if str(event.get("status", "")).strip().lower() in RUNTIME_GAP_CAPABILITY_STATUSES
    ]
    counts_by_kind: dict[str, int] = {kind: 0 for kind in sorted(CAPABILITY_EVENT_KINDS)}
    for event in invoked_events:
        kind = str(event.get("kind", "unknown")) or "unknown"
        counts_by_kind[kind] = counts_by_kind.get(kind, 0) + 1
    skipped_by_kind: dict[str, int] = {kind: 0 for kind in sorted(CAPABILITY_EVENT_KINDS)}
    for event in skipped_events:
        kind = str(event.get("kind", "unknown")) or "unknown"
        skipped_by_kind[kind] = skipped_by_kind.get(kind, 0) + 1
    command_events = load_command_events(run_dir)
    dispatch_events = [
        event
        for event in command_events
        if event.get("generated_by") == "knowledgeos"
        and event.get("event_type") == "dispatch-task"
        and event.get("task_id") == task_id
        and event.get("run_id") == run_id
    ]
    latest_dispatch_event = dispatch_events[-1] if dispatch_events else {}
    required_stages = [str(item) for item in latest_dispatch_event.get("required_stages", []) or []]
    planned_tools = latest_dispatch_event.get("planned_tools", []) or []
    def normalized_token(value: str) -> str:
        return value.strip().lower().replace("_", "-")

    recorded_stage_tokens = {
        normalized_token(str(event.get("kind", "")))
        for event in events
    } | {
        normalized_token(str(event.get("id", "")))
        for event in events
    }
    planned_tools_by_stage: dict[str, list[dict[str, Any]]] = {}
    for item in planned_tools:
        if isinstance(item, dict):
            planned_tools_by_stage.setdefault(str(item.get("stage", "")), []).append(item)
    def required_stage_has_record(stage: str) -> bool:
        normalized_stage = normalized_token(stage)
        if normalized_stage in recorded_stage_tokens:
            return True
        for item in planned_tools_by_stage.get(stage, []):
            if normalized_token(str(item.get("kind", ""))) in recorded_stage_tokens:
                return True
            if normalized_token(str(item.get("id", ""))) in recorded_stage_tokens:
                return True
        return any(normalized_stage in normalized_token(str(event.get("purpose", ""))) for event in events)

    required_without_record = [
        stage
        for stage in required_stages
        if stage and not required_stage_has_record(stage)
    ]
    gaps: list[str] = []
    if not events:
        gaps.append("no capability-event records were written; report no external capability use with an explicit reason")
    if required_without_record:
        gaps.append("required dispatch stages without capability-event or skip reason: " + ", ".join(required_without_record))
    if runtime_gap_events:
        gaps.append(
            "runtime subagent gaps: "
            + ", ".join(
                f"{event.get('id', '')}={event.get('status', '')}"
                for event in runtime_gap_events
            )
        )
    if not gaps:
        gaps.append("none")
    marker = f"AGENT_DISPATCH_OK agents={len(agent_events)} capabilities={len(invoked_events)} skipped_agents={len(skipped_agent_events)} run={run_id}"
    report_path = run_dir / "dispatch-report.md"
    lines = [
        "# Full Capability Dispatch Report",
        "",
        f"Run: {run_id}",
        "",
        f"Task: {task_id}",
        "",
        f"Marker: {marker}",
        "",
        "Meaning: AGENT_DISPATCH_OK summarizes all recorded external and mounted capabilities, not only subagents.",
        "",
        f"Agents Invoked: {len(agent_events)}",
        "",
        f"Agents Skipped Or Gapped: {len(skipped_agent_events)}",
        "",
        f"Capabilities Invoked: {len(invoked_events)}",
        "",
        f"Capabilities Skipped: {len(skipped_events)}",
        "",
        f"Evidence: `{project_relative(project_root, capability_events_path(run_dir))}`, `{project_relative(project_root, command_events_path(run_dir))}`",
        "",
        "## By Kind",
        "",
    ]
    for kind, count in sorted(counts_by_kind.items()):
        skipped = skipped_by_kind.get(kind, 0)
        lines.append(f"- {kind}: used={count}, skipped={skipped}")
    lines.extend(["", "## Used Capabilities", ""])
    if invoked_events:
        for event in invoked_events:
            kind = str(event.get("kind", "unknown"))
            capability_id = str(event.get("id", ""))
            purpose = str(event.get("purpose", ""))
            status = str(event.get("status", "completed"))
            lines.append(f"- {kind}: {capability_id} ({status}) - {purpose}")
    else:
        lines.append("- none")
    lines.extend(["", "## Skipped Or Not Needed", ""])
    if skipped_events:
        for event in skipped_events:
            kind = str(event.get("kind", "unknown"))
            capability_id = str(event.get("id", ""))
            purpose = str(event.get("purpose", ""))
            evidence = str(event.get("evidence", ""))
            suffix = f" Evidence: {evidence}" if evidence else ""
            lines.append(f"- {kind}: {capability_id} - {purpose}.{suffix}")
    else:
        lines.append("- none")
    lines.extend(["", "## Dispatch Plan Evidence", ""])
    if planned_tools:
        for item in planned_tools:
            if isinstance(item, dict):
                lines.append(f"- {item.get('stage', '')}: {item.get('kind', '')}/{item.get('id', '')} required={item.get('required', '')}")
    else:
        lines.append("- no run-bound dispatch plan was recorded")
    lines.extend(["", "## Gaps", ""])
    for gap in gaps:
        lines.append(f"- {gap}")
    write_text(report_path, "\n".join(lines) + "\n")
    append_command_event(
        run_dir,
        "dispatch-report",
        task_id,
        run_id,
        status="reported",
        agent_count=len(agent_events),
        capability_count=len(invoked_events),
        skipped_count=len(skipped_events),
        skipped_agent_count=len(skipped_agent_events),
        runtime_gap_count=len(runtime_gap_events),
    )
    return {
        "status": "reported",
        "dispatch_report_marker": "AGENT_DISPATCH_OK",
        "marker": marker,
        "full_capability_report": True,
        "agent_count": len(agent_events),
        "skipped_agent_count": len(skipped_agent_events),
        "runtime_gap_count": len(runtime_gap_events),
        "capability_count": len(invoked_events),
        "skipped_count": len(skipped_events),
        "counts_by_kind": counts_by_kind,
        "skipped_by_kind": skipped_by_kind,
        "required_stages": required_stages,
        "required_without_record": required_without_record,
        "gaps": gaps,
        "evidence": {
            "capability_events": str(capability_events_path(run_dir)),
            "command_events": str(command_events_path(run_dir)),
            "dispatch_report": str(report_path),
        },
        "agents": [
            {
                "kind": str(event.get("kind", "")),
                "id": str(event.get("id", "")),
                "purpose": str(event.get("purpose", "")),
                "status": str(event.get("status", "completed")),
            }
            for event in agent_events
        ],
        "skipped_agents": [
            {
                "kind": str(event.get("kind", "")),
                "id": str(event.get("id", "")),
                "purpose": str(event.get("purpose", "")),
                "status": str(event.get("status", "skipped")),
                "evidence": str(event.get("evidence", "")),
            }
            for event in skipped_agent_events
        ],
        "runtime_gaps": [
            {
                "kind": str(event.get("kind", "")),
                "id": str(event.get("id", "")),
                "purpose": str(event.get("purpose", "")),
                "status": str(event.get("status", "")),
                "evidence": str(event.get("evidence", "")),
            }
            for event in runtime_gap_events
        ],
        "events": [
            {
                "kind": str(event.get("kind", "")),
                "id": str(event.get("id", "")),
                "purpose": str(event.get("purpose", "")),
                "status": str(event.get("status", "completed")),
            }
            for event in invoked_events
        ],
        "skipped": [
            {
                "kind": str(event.get("kind", "")),
                "id": str(event.get("id", "")),
                "purpose": str(event.get("purpose", "")),
                "status": str(event.get("status", "skipped")),
                "evidence": str(event.get("evidence", "")),
            }
            for event in skipped_events
        ],
        "report": str(report_path),
    }


def record_trace_step(
    project_root: Path,
    task_id: str,
    run_id: str,
    *,
    step: str,
    status: str = "completed",
    note: str = "",
    evidence: str = "",
) -> dict[str, Any]:
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    if step not in OPERATIONAL_TRACE_STEPS:
        raise ValueError(f"invalid step {step!r}; expected one of {OPERATIONAL_TRACE_STEPS}")
    if not note.strip():
        raise ValueError("--note is required")
    record = {
        "task_id": task_id,
        "run_id": run_id,
        "step": step,
        "status": status.strip() or "completed",
        "note": note.strip(),
        "evidence": evidence.strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    event_path = step_events_path(run_dir)
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    append_command_event(run_dir, "trace-step", task_id, run_id, step=step, status=record["status"])
    marker = f"TRACE_OK step={step} status={record['status']} evidence={short_marker_value(evidence or note)}"
    return {"status": "recorded", "trace_marker": "TRACE_OK", "marker": marker, "ledger": str(event_path), "record": record}


def effect_assertion_id_exists(run_dir: Path, assertion_id: str, task_id: str, run_id: str) -> bool:
    return any(
        assertion.get("assertion_id") == assertion_id
        and assertion.get("task_id") == task_id
        and assertion.get("run_id") == run_id
        and assertion.get("status") == "passed"
        for assertion in load_effect_assertions(run_dir)
        if "_invalid_json" not in assertion
    )


def record_decision_event(
    project_root: Path,
    task_id: str,
    run_id: str,
    *,
    kind: str,
    status: str,
    title: str,
    summary: str,
    reason: str,
    evidence: str,
    parent_id: str = "",
    options: list[str] | None = None,
    chosen: str = "",
    linked_step: str = "",
    linked_capability_event_id: str = "",
    linked_effect_assertion_id: str = "",
) -> dict[str, Any]:
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    if kind not in DECISION_EVENT_KINDS:
        raise ValueError(f"invalid decision kind {kind!r}; expected one of {sorted(DECISION_EVENT_KINDS)}")
    if status not in DECISION_EVENT_STATUSES:
        raise ValueError(f"invalid decision status {status!r}; expected one of {sorted(DECISION_EVENT_STATUSES)}")
    for label, value in [("--title", title), ("--summary", summary), ("--reason", reason), ("--evidence", evidence)]:
        if not value.strip():
            raise ValueError(f"{label} is required")
    if linked_step and linked_step not in OPERATIONAL_TRACE_STEPS:
        raise ValueError(f"invalid linked step {linked_step!r}; expected one of {OPERATIONAL_TRACE_STEPS}")
    capability_link = linked_capability_event_id.strip()
    if capability_link and not capability_event_id_exists(run_dir, capability_link, task_id, run_id):
        raise ValueError(f"capability event not found for decision: {capability_link}")
    effect_link = linked_effect_assertion_id.strip()
    if effect_link and not effect_assertion_id_exists(run_dir, effect_link, task_id, run_id):
        raise ValueError(f"effect assertion not found for decision: {effect_link}")

    decision_id = (
        "DEC-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + safe_slug(f"{kind}-{title.strip()}")[:48]
    )
    clean_options = [item.strip() for item in (options or []) if item.strip()]
    record = {
        "decision_id": decision_id,
        "parent_id": parent_id.strip(),
        "task_id": task_id,
        "run_id": run_id,
        "kind": kind,
        "status": status,
        "title": title.strip(),
        "summary": summary.strip(),
        "reason": reason.strip(),
        "options": clean_options,
        "chosen": chosen.strip(),
        "evidence": evidence.strip(),
        "linked_step": linked_step.strip(),
        "linked_capability_event_id": capability_link,
        "linked_effect_assertion_id": effect_link,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    event_path = decision_events_path(run_dir)
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    append_command_event(
        run_dir,
        "decision-event",
        task_id,
        run_id,
        decision_id=decision_id,
        kind=kind,
        status=status,
    )
    marker = f"DECISION_OK kind={kind} status={status} title={short_marker_value(title)}"
    return {
        "status": "recorded",
        "decision_marker": "DECISION_OK",
        "decision_id": decision_id,
        "marker": marker,
        "ledger": str(event_path),
        "record": record,
    }


def query_decision_events(
    project_root: Path,
    *,
    run_id: str,
    task_id: str = "",
    kind: str = "",
    status: str = "",
    parent_id: str = "",
) -> dict[str, Any]:
    run_dir = resolve_run_dir(project_root, run_id)
    events = [event for event in load_decision_events(run_dir) if "_invalid_json" not in event]
    if task_id:
        events = [event for event in events if event.get("task_id") == task_id]
    if kind:
        events = [event for event in events if event.get("kind") == kind]
    if status:
        events = [event for event in events if event.get("status") == status]
    if parent_id:
        events = [event for event in events if event.get("parent_id") == parent_id]
    return {
        "status": "ok",
        "run_id": run_id,
        "count": len(events),
        "events": events,
        "ledger": str(decision_events_path(run_dir)),
    }


def decision_event_has_command_event(run_dir: Path, event: dict[str, Any], task_id: str, run_id: str) -> bool:
    return has_command_event(
        run_dir,
        "decision-event",
        task_id,
        run_id,
        decision_id=str(event.get("decision_id", "")),
        kind=str(event.get("kind", "")),
        status=str(event.get("status", "")),
    )


def build_decision_verify_marker(result: dict[str, Any]) -> str:
    return (
        "DECISION_VERIFY_OK "
        f"status={result.get('status', '')} "
        f"strictness={result.get('strictness', '')} "
        f"decisions={len(result.get('events', []))} "
        f"warnings={len(result.get('warnings', []))} "
        f"errors={len(result.get('errors', []))}"
    )


def verify_decisions(project_root: Path, task_id: str, run_id: str) -> dict[str, Any]:
    policy = parse_decision_policy(project_root)
    strictness = str(policy.get("strictness", "warn"))
    if strictness not in DECISION_STRICTNESS_LEVELS:
        raise ValueError(f"invalid decision strictness: {strictness}")
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if strictness == "off":
        reason = str(policy.get("downgrade_reason", "")).strip()
        if not reason:
            errors.append({"label": "missing_downgrade_reason", "detail": "strictness=off requires downgrade_reason"})
        result = {
            "status": "failed" if errors else "disabled",
            "task_id": task_id,
            "run_id": run_id,
            "strictness": strictness,
            "downgrade_reason": reason,
            "events": [],
            "errors": errors,
            "warnings": warnings,
            "ledger": str(decision_events_path(run_dir)),
        }
        result["decision_verify_marker"] = "DECISION_VERIFY_OK"
        result["marker"] = build_decision_verify_marker(result)
        append_command_event(
            run_dir,
            "verify-decisions",
            task_id,
            run_id,
            status=str(result["status"]),
            strictness=strictness,
            decision_verify_marker=result["decision_verify_marker"],
            marker=result["marker"],
        )
        return result

    raw_events = load_decision_events(run_dir)
    valid_events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    parent_ids: set[str] = set()
    for event in raw_events:
        if "_invalid_json" in event:
            errors.append({"label": "invalid_decision_event", "detail": f"line {event.get('_line')} is not JSON"})
            continue
        if event.get("task_id") != task_id or event.get("run_id") != run_id:
            errors.append({"label": "decision_scope_mismatch", "detail": event})
            continue
        decision_id = str(event.get("decision_id", "")).strip()
        if not decision_id:
            errors.append({"label": "decision_missing_id", "detail": event.get("title", "")})
            continue
        if decision_id in seen_ids:
            duplicate_ids.add(decision_id)
        seen_ids.add(decision_id)
        for field in ["title", "summary", "reason", "evidence"]:
            if not str(event.get(field, "")).strip():
                errors.append({"label": f"decision_missing_{field}", "detail": decision_id})
        kind = str(event.get("kind", ""))
        status = str(event.get("status", ""))
        if kind not in DECISION_EVENT_KINDS:
            errors.append({"label": "invalid_decision_kind", "detail": kind})
        if status not in DECISION_EVENT_STATUSES:
            errors.append({"label": "invalid_decision_status", "detail": status})
        if (kind in DECISION_EXPLANATION_REQUIRED_KINDS or status in {"abandoned", "rolled_back", "superseded"}) and not str(event.get("reason", "")).strip():
            errors.append({"label": "decision_missing_explanation", "detail": decision_id})
        if not decision_event_has_command_event(run_dir, event, task_id, run_id):
            errors.append({"label": "decision_missing_command_event", "detail": decision_id})
        parent = str(event.get("parent_id", "")).strip()
        if parent:
            parent_ids.add(parent)
        valid_events.append(event)
    for decision_id in sorted(duplicate_ids):
        errors.append({"label": "decision_duplicate_id", "detail": decision_id})
    for parent in sorted(parent_ids):
        if parent not in seen_ids:
            errors.append({"label": "decision_orphan_parent", "detail": parent})

    if not valid_events:
        if strictness == "enforce":
            errors.append({"label": "no_decision_events", "detail": "decision-policy strictness=enforce requires decision evidence"})
        else:
            warnings.append({"label": "no_decision_events", "detail": "no decision graph events were recorded"})

    status = "failed" if errors else ("warning" if warnings else "passed")
    result = {
        "status": status,
        "task_id": task_id,
        "run_id": run_id,
        "strictness": strictness,
        "downgrade_reason": str(policy.get("downgrade_reason", "")).strip(),
        "events": valid_events,
        "errors": errors,
        "warnings": warnings,
        "ledger": str(decision_events_path(run_dir)),
    }
    result["decision_verify_marker"] = "DECISION_VERIFY_OK"
    result["marker"] = build_decision_verify_marker(result)
    append_command_event(
        run_dir,
        "verify-decisions",
        task_id,
        run_id,
        status=status,
        strictness=strictness,
        decision_verify_marker=result["decision_verify_marker"],
        marker=result["marker"],
    )
    return result


def get_json_key(data: Any, key_path: str) -> Any:
    current = data
    for part in key_path.split("."):
        if not part:
            raise ValueError("--json-key must not contain empty path segments")
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise ValueError(f"json key not found: {key_path}")
    return current


def html_has_remote_dependency(text: str) -> bool:
    patterns = [
        r"<script\b[^>]*\bsrc\s*=\s*['\"]?\s*(?:https?:)?//",
        r"<link\b[^>]*\bhref\s*=\s*['\"]?\s*(?:https?:)?//",
        r"<img\b[^>]*\bsrc\s*=\s*['\"]?\s*(?:https?:)?//",
        r"@import\s+(?:url\()?['\"]?\s*(?:https?:)?//",
        r"url\(['\"]?\s*(?:https?:)?//",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def run_artifact_assertion(
    project_root: Path,
    task_id: str,
    run_id: str,
    *,
    kind: str,
    target_path: str,
    expect: str = "",
    before_sha: str = "",
    json_key: str = "",
    capability_event_id: str = "",
) -> dict[str, Any]:
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    if kind not in EFFECT_ASSERTION_KINDS:
        raise ValueError(f"invalid artifact assertion kind {kind!r}; expected one of {sorted(EFFECT_ASSERTION_KINDS)}")
    if not target_path.strip():
        raise ValueError("--path is required")
    capability_link = capability_event_id.strip()
    if capability_link and not capability_event_id_exists(run_dir, capability_link, task_id, run_id):
        raise ValueError(f"capability event not found for assertion: {capability_link}")
    target = resolve_project_artifact(project_root, target_path)
    relative = project_relative(project_root, target)
    evidence = ""

    if kind == "file_exists":
        if not target.exists():
            raise ValueError(f"artifact assertion failed: {relative} does not exist")
        evidence = f"{relative} exists"
    elif kind == "file_nonempty":
        if not target.exists() or not target.is_file() or target.stat().st_size <= 0:
            raise ValueError(f"artifact assertion failed: {relative} is missing or empty")
        evidence = f"{relative} size={target.stat().st_size}"
    elif kind == "file_contains":
        if not expect:
            raise ValueError("--expect is required for file_contains")
        if not target.exists() or not target.is_file():
            raise ValueError(f"artifact assertion failed: {relative} is missing")
        text = read_text(target)
        if expect not in text:
            raise ValueError(f"artifact assertion failed: {relative} does not contain expected text")
        evidence = f"{relative} contains {short_marker_value(expect)}"
    elif kind == "file_sha256":
        if not expect:
            raise ValueError("--expect is required for file_sha256")
        if not target.exists() or not target.is_file():
            raise ValueError(f"artifact assertion failed: {relative} is missing")
        digest = sha256_file(target)
        if digest != expect:
            raise ValueError(f"artifact assertion failed: {relative} sha256 {digest} != {expect}")
        evidence = f"{relative} sha256={digest}"
    elif kind == "file_changed":
        if not before_sha:
            raise ValueError("--before-sha is required for file_changed")
        if not target.exists() or not target.is_file():
            raise ValueError(f"artifact assertion failed: {relative} is missing")
        digest = sha256_file(target)
        if digest == before_sha:
            raise ValueError(f"artifact assertion failed: {relative} sha256 unchanged")
        evidence = f"{relative} changed {before_sha[:12]}->{digest[:12]}"
    elif kind == "json_key_equals":
        if not json_key:
            raise ValueError("--json-key is required for json_key_equals")
        if not expect:
            raise ValueError("--expect is required for json_key_equals")
        if not target.exists() or not target.is_file():
            raise ValueError(f"artifact assertion failed: {relative} is missing")
        observed = get_json_key(json.loads(read_text(target)), json_key)
        if str(observed) != expect:
            raise ValueError(f"artifact assertion failed: {relative} {json_key}={observed!r} != {expect!r}")
        evidence = f"{relative} {json_key}={expect}"
    elif kind == "html_self_contained":
        if not target.exists() or not target.is_file():
            raise ValueError(f"artifact assertion failed: {relative} is missing")
        text = read_text(target)
        if html_has_remote_dependency(text):
            raise ValueError(f"artifact assertion failed: {relative} references remote assets")
        evidence = f"{relative} has no remote scripts/fonts/assets"

    assertion_id = "EFFECT-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"-{safe_slug(kind)}"
    record = {
        "assertion_id": assertion_id,
        "task_id": task_id,
        "run_id": run_id,
        "kind": kind,
        "path": relative,
        "expect": expect,
        "before_sha": before_sha,
        "json_key": json_key,
        "capability_event_id": capability_link,
        "status": "passed",
        "evidence": evidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    ledger_path = effect_assertions_path(run_dir)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    append_command_event(
        run_dir,
        "artifact-assert",
        task_id,
        run_id,
        assertion_id=assertion_id,
        kind=kind,
        path=relative,
        status="passed",
        capability_event_id=capability_link,
    )
    marker = f"EFFECT_OK kind={kind} target={relative} evidence={short_marker_value(evidence)}"
    return {"status": "passed", "effect_marker": "EFFECT_OK", "marker": marker, "ledger": str(ledger_path), "record": record}


def capability_event_id_exists(run_dir: Path, capability_event_id: str, task_id: str, run_id: str) -> bool:
    return any(
        event.get("capability_event_id") == capability_event_id
        and event.get("task_id") == task_id
        and event.get("run_id") == run_id
        and event.get("status") == "completed"
        for event in load_capability_events(run_dir)
        if "_invalid_json" not in event
    )


def assertion_has_command_event(run_dir: Path, assertion: dict[str, Any], task_id: str, run_id: str) -> bool:
    return has_command_event(
        run_dir,
        "artifact-assert",
        task_id,
        run_id,
        assertion_id=str(assertion.get("assertion_id", "")),
        kind=str(assertion.get("kind", "")),
        path=str(assertion.get("path", "")),
        status="passed",
    )


def declared_output_effect_targets(project_root: Path, task_id: str) -> list[str]:
    targets: list[str] = []
    for output in task_declared_outputs(project_root, task_id):
        cleaned = output.strip().strip('"').strip("'")
        if not cleaned:
            continue
        if any(char in cleaned for char in "*?[]"):
            matches = sorted(project_root.glob(cleaned))
            targets.extend(project_relative(project_root, match) for match in matches)
            if not matches:
                targets.append(cleaned)
            continue
        targets.append(project_relative(project_root, output_path(project_root, cleaned)))
    return targets


def assertion_covers_target(assertion_path: str, target: str, project_root: Path) -> bool:
    if assertion_path == target:
        return True
    path = project_root / target
    return path.is_dir() and assertion_path.startswith(target.rstrip("/") + "/")


def effect_issue_status(strictness: str, errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    if strictness == "off":
        return "disabled"
    if strictness == "observe":
        return "passed"
    if strictness == "warn":
        return "warning" if errors or warnings else "passed"
    return "failed" if errors else "passed"


def build_effect_verify_marker(result: dict[str, Any]) -> str:
    return (
        "EFFECT_VERIFY_OK "
        f"status={result.get('status', '')} "
        f"strictness={result.get('strictness', '')} "
        f"assertions={len(result.get('assertions', []))} "
        f"warnings={len(result.get('warnings', []))} "
        f"errors={len(result.get('errors', []))}"
    )


def verify_effects(project_root: Path, task_id: str, run_id: str) -> dict[str, Any]:
    policy = parse_effect_policy(project_root)
    strictness = str(policy.get("strictness", "observe"))
    if strictness not in EFFECT_STRICTNESS_LEVELS:
        raise ValueError(f"invalid effect strictness: {strictness}")
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if strictness == "off":
        reason = str(policy.get("downgrade_reason", "")).strip()
        if not reason:
            errors.append({"label": "missing_downgrade_reason", "detail": "strictness=off requires downgrade_reason"})
        result = {
            "status": "failed" if errors else "disabled",
            "task_id": task_id,
            "run_id": run_id,
            "strictness": strictness,
            "downgrade_reason": reason,
            "required_for": policy.get("required_for", []),
            "assertions": [],
            "errors": errors,
            "warnings": warnings,
            "ledger": str(effect_assertions_path(run_dir)),
        }
        result["effect_verify_marker"] = "EFFECT_VERIFY_OK"
        result["marker"] = build_effect_verify_marker(result)
        append_command_event(
            run_dir,
            "verify-effects",
            task_id,
            run_id,
            status=str(result["status"]),
            strictness=strictness,
            effect_verify_marker=result["effect_verify_marker"],
            marker=result["marker"],
        )
        return result

    assertions = load_effect_assertions(run_dir)
    valid_assertions: list[dict[str, Any]] = []
    for assertion in assertions:
        if "_invalid_json" in assertion:
            errors.append({"label": "invalid_effect_assertion", "detail": f"line {assertion.get('_line')} is not JSON"})
            continue
        if assertion.get("task_id") != task_id or assertion.get("run_id") != run_id:
            errors.append({"label": "effect_scope_mismatch", "detail": assertion})
            continue
        if assertion.get("status") != "passed":
            errors.append({"label": "effect_not_passed", "detail": assertion})
            continue
        if str(assertion.get("kind", "")) not in EFFECT_ASSERTION_KINDS:
            errors.append({"label": "invalid_effect_kind", "detail": assertion.get("kind")})
            continue
        if not assertion_has_command_event(run_dir, assertion, task_id, run_id):
            errors.append({"label": "effect_missing_command_event", "detail": assertion.get("assertion_id", assertion.get("path", ""))})
            continue
        capability_link = str(assertion.get("capability_event_id", "")).strip()
        if capability_link and not capability_event_id_exists(run_dir, capability_link, task_id, run_id):
            errors.append({"label": "effect_missing_capability_event", "detail": capability_link})
            continue
        valid_assertions.append(assertion)

    if "declared_outputs" in policy.get("required_for", []):
        for target in declared_output_effect_targets(project_root, task_id):
            if any(assertion_covers_target(str(assertion.get("path", "")), target, project_root) for assertion in valid_assertions):
                continue
            errors.append({"label": "missing_declared_output_effect", "detail": target})

    if not assertions:
        warnings.append({"label": "no_effect_assertions", "detail": "no artifact assertions were recorded"})
    status = effect_issue_status(strictness, errors, warnings)
    result = {
        "status": status,
        "task_id": task_id,
        "run_id": run_id,
        "strictness": strictness,
        "downgrade_reason": str(policy.get("downgrade_reason", "")).strip(),
        "required_for": policy.get("required_for", []),
        "assertions": valid_assertions,
        "errors": [] if strictness in {"observe", "warn"} else errors,
        "warnings": warnings + (errors if strictness in {"observe", "warn"} else []),
        "ledger": str(effect_assertions_path(run_dir)),
    }
    result["effect_verify_marker"] = "EFFECT_VERIFY_OK"
    result["marker"] = build_effect_verify_marker(result)
    append_command_event(
        run_dir,
        "verify-effects",
        task_id,
        run_id,
        status=status,
        strictness=strictness,
        effect_verify_marker=result["effect_verify_marker"],
        marker=result["marker"],
    )
    return result


def load_phase_records(run_dir: Path) -> list[dict[str, Any]]:
    ledger_path = run_dir / "phases.ndjson"
    if not ledger_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(read_text(ledger_path).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            item = {"_invalid_json": raw, "_line": line_number}
        records.append(item)
    return records


def dispatch_record_skips_stage(record: dict[str, Any] | None, stage: str) -> bool:
    if not record:
        return False
    text = " ".join(
        str(record.get(key, ""))
        for key in ["note", "evidence", "skip_reason"]
    ).lower()
    stage_text = stage.lower().replace("_", "-")
    variants = {stage.lower(), stage_text, stage.lower().replace("_", " ")}
    return any(variant in text for variant in variants) and any(token in text for token in ["skip", "skipped", "not needed", "no ", "without"])


def capability_event_matches_stage(event: dict[str, Any], step: dict[str, Any]) -> bool:
    if "_invalid_json" in event:
        return False
    stage = str(step.get("stage", ""))
    kind = str(event.get("kind", ""))
    capability_id = str(event.get("id", ""))
    tool_ids = {str(tool.get("id", "")) for tool in step.get("tools", []) if isinstance(tool, dict)}
    if stage == "branch_builder":
        return capability_id == "branch-builder"
    if stage == "script":
        return kind in {"script", "shell"}
    return kind == stage or bool(capability_id and capability_id in tool_ids)


def verify_dispatch_capability_contract(project_root: Path, task_id: str, run_id: str, dispatch_record: dict[str, Any] | None) -> list[dict[str, Any]]:
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    errors: list[dict[str, Any]] = []
    if not has_command_event(run_dir, "run-task", task_id, run_id, lifecycle_contract="capability-visible-v1"):
        return errors
    dispatch_event_ok = has_command_event(run_dir, "dispatch-task", task_id, run_id, status="dispatch_ready")
    if not dispatch_event_ok:
        errors.append({"label": "missing_dispatch_command_event", "detail": "dispatch-task --run-id command evidence is missing"})
    dispatch = build_dispatch_plan(project_root, task_id)
    if dispatch.get("status") != "dispatch_ready":
        errors.append({"label": "dispatch_not_ready", "detail": dispatch.get("reason", "dispatch plan is not ready")})
        return errors
    required_steps = [step for step in dispatch.get("steps", []) if step.get("required")]
    capability_events = load_capability_events(run_dir)
    invalid_events = [event for event in capability_events if "_invalid_json" in event]
    for event in invalid_events:
        errors.append({"label": "invalid_capability_event", "detail": f"line {event.get('_line')} is not JSON"})
    for step in required_steps:
        stage = str(step.get("stage", ""))
        if any(capability_event_matches_stage(event, step) for event in capability_events):
            continue
        if dispatch_record_skips_stage(dispatch_record, stage):
            continue
        errors.append({"label": "missing_required_capability_event", "detail": stage})
    return errors


def verify_lifecycle(project_root: Path, task_id: str, run_id: str) -> dict[str, Any]:
    policy = parse_phase_policy(project_root)
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    required = policy["required_phases"]["default"]
    require_skip_reason = policy["skip_policy"]["require_skip_reason"]
    records = load_phase_records(run_dir)
    latest_by_phase: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []

    if required != EXPECTED_PHASE_KEYS:
        errors.append({"label": "invalid_phase_policy", "detail": f"default required phases must be {EXPECTED_PHASE_KEYS}, got {required}"})
    if not require_skip_reason:
        errors.append({"label": "invalid_phase_policy", "detail": "skip_policy.require_skip_reason must be true"})

    for record in records:
        if "_invalid_json" in record:
            errors.append({"label": "invalid_phase_record", "detail": f"line {record.get('_line')} is not JSON"})
            continue
        if record.get("task_id") != task_id or record.get("run_id") != run_id:
            errors.append({"label": "phase_scope_mismatch", "detail": record})
            continue
        phase = str(record.get("phase", ""))
        status = str(record.get("status", ""))
        if phase not in required:
            errors.append({"label": "invalid_phase", "detail": phase})
            continue
        if status not in PHASE_STATUSES:
            errors.append({"label": "invalid_phase_status", "detail": {"phase": phase, "status": status}})
            continue
        if status == "skipped" and require_skip_reason and not str(record.get("skip_reason", "")).strip():
            errors.append({"label": "skipped_phase_missing_reason", "detail": phase})
        latest_by_phase[phase] = record

    missing = [phase for phase in required if phase not in latest_by_phase]
    if missing:
        errors.append({"label": "missing_phases", "detail": missing})
    missing_command_events = [
        phase
        for phase in required
        if phase in latest_by_phase
        and not has_command_event(
            run_dir,
            "phase-task",
            task_id,
            run_id,
            phase=phase,
            status=str(latest_by_phase[phase].get("status", "")),
        )
    ]
    if missing_command_events:
        errors.append({"label": "missing_phase_command_events", "detail": missing_command_events})
    errors.extend(verify_dispatch_capability_contract(project_root, task_id, run_id, latest_by_phase.get("dispatch")))

    return {
        "status": "passed" if not errors else "failed",
        "task_id": task_id,
        "run_id": run_id,
        "required_phases": required,
        "observed_phases": sorted(latest_by_phase),
        "errors": errors,
        "ledger": str(run_dir / "phases.ndjson"),
    }


def fabric_contract(project_root: Path) -> dict[str, str]:
    fabric_path = project_root / ".agent-os" / "fabric-link.yaml"
    if not fabric_path.exists():
        return {}
    return parse_scalar_values(
        fabric_path,
        {"governance_root", "postflight_required"},
    )


def resolve_postflight_hook(project_root: Path, fabric: dict[str, str]) -> Path | None:
    governance_root = fabric.get("governance_root", "")
    if not governance_root:
        return None
    if "CHANGE_ME" in governance_root:
        return Path(governance_root) / "hooks" / "after-task.sh"
    root = Path(governance_root).expanduser()
    if not root.is_absolute():
        root = project_root / root
    return root.resolve() / "hooks" / "after-task.sh"


def validate_governance_kernel(project_root: Path, governance_root: str, *, skip_external: bool = False) -> list[CheckResult]:
    if not governance_root or "CHANGE_ME" in governance_root:
        return [CheckResult(skip_external, "boot_kernel", "governance_root unresolved" if not skip_external else "governance_root unresolved allowed")]
    root = resolve_project_config_path(project_root, governance_root)
    results: list[CheckResult] = []
    for rel in REQUIRED_KERNEL_DIRS:
        path = root / rel
        results.append(CheckResult(skip_external or path.is_dir(), "kernel_skeleton", f"{rel}/ present" if path.is_dir() else f"{rel}/ missing: {path}"))
    for rel in REQUIRED_KERNEL_FILES:
        path = root / rel
        if rel.endswith(".sh"):
            ok = path.exists() and os.access(path, os.X_OK)
            detail = f"{rel} executable: {path}" if ok else f"{rel} missing or not executable: {path}"
        else:
            ok = path.exists()
            detail = f"{rel} present" if ok else f"{rel} missing: {path}"
        results.append(CheckResult(skip_external or ok, "boot_kernel", detail))
    return results


def hook_path_for_governance_root(project_root: Path, governance_root: str, hook_name: str) -> Path:
    root = Path(governance_root).expanduser()
    if not root.is_absolute():
        root = project_root / root
    return root.resolve() / "hooks" / hook_name


def default_governance_root(root: Path) -> Path:
    return root / "global-agent-fabric"


def default_capability_root(root: Path) -> Path:
    return root / "capability-layer"


def parse_registry_project_paths(registry: Path) -> list[Path]:
    if not registry.exists():
        return []
    paths: list[Path] = []
    for raw in read_text(registry).splitlines():
        stripped = raw.strip()
        if stripped.startswith("path:"):
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            if value:
                paths.append(Path(value).expanduser())
    return paths


def discover_agent_os_projects(search_roots: list[Path], *, include_templates: bool = False) -> list[Path]:
    projects: set[Path] = set()
    skip_names = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "Library",
        "Applications",
        "System",
        "global-agent-fabric_venv",
    }
    for search_root in search_roots:
        search_root = search_root.expanduser()
        if not search_root.exists():
            continue
        if (search_root / ".agent-os").is_dir():
            projects.add(search_root.resolve())
        for dirpath, dirnames, _filenames in os.walk(search_root):
            current = Path(dirpath)
            dirnames[:] = [
                name
                for name in dirnames
                if name not in skip_names and not (name.startswith(".") and name not in {".agent-os"})
            ]
            if ".agent-os" in dirnames:
                if include_templates or "templates/project-control-plane" not in str(current):
                    projects.add(current.resolve())
                dirnames.remove(".agent-os")
    return sorted(projects, key=lambda item: str(item))


def replace_scalar_line(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^(\s*){re.escape(key)}\s*:\s*.*$", re.MULTILINE)
    return pattern.sub(rf"\1{key}: {value}", text)


def backup_project_file(project_root: Path, path: Path, backup_name: str) -> Path:
    rel = path.relative_to(project_root)
    target = project_root / ".agent-os" / "backups" / backup_name / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return target


def ensure_kernel_hooks(root: Path, governance_root: Path, *, apply: bool) -> list[dict[str, str]]:
    template_hooks = root / "templates" / "governance-core" / "hooks"
    hooks_root = governance_root / "hooks"
    actions: list[dict[str, str]] = []
    for hook_name in ["before-task.sh", "log-phase.sh", "after-task.sh"]:
        source = template_hooks / hook_name
        target = hooks_root / hook_name
        if not source.exists():
            actions.append({"action": "missing_source", "path": str(source)})
            continue
        if target.exists():
            if os.access(target, os.X_OK):
                actions.append({"action": "ok", "path": str(target)})
            else:
                actions.append({"action": "chmod", "path": str(target)})
                if apply:
                    target.chmod(target.stat().st_mode | 0o111)
            continue
        actions.append({"action": "copy", "source": str(source), "path": str(target)})
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            target.chmod(target.stat().st_mode | 0o111)
    return actions


def ensure_kernel_skeleton(root: Path, governance_root: Path, *, apply: bool) -> list[dict[str, str]]:
    template = root / "templates" / "governance-core"
    actions: list[dict[str, str]] = []
    for rel in REQUIRED_KERNEL_DIRS:
        target = governance_root / rel
        if target.is_dir():
            actions.append({"action": "ok", "path": str(target)})
            continue
        actions.append({"action": "mkdir", "path": str(target)})
        if apply:
            target.mkdir(parents=True, exist_ok=True)
    for rel in KERNEL_SKELETON_TEMPLATE_FILES:
        source = template / rel
        target = governance_root / rel
        if target.exists():
            actions.append({"action": "ok", "path": str(target)})
            continue
        if not source.exists():
            actions.append({"action": "missing_source", "path": str(source)})
            continue
        actions.append({"action": "copy", "source": str(source), "path": str(target)})
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return actions


def ensure_capability_layer(root: Path, capability_root: Path, *, apply: bool) -> list[dict[str, str]]:
    template = root / "templates" / "capability-layer"
    actions: list[dict[str, str]] = []
    for rel in ["README.md", "STRUCTURE-CHECK.md"]:
        source = template / rel
        target = capability_root / rel
        if target.exists():
            actions.append({"action": "ok", "path": str(target)})
            continue
        if not source.exists():
            actions.append({"action": "missing_source", "path": str(source)})
            continue
        actions.append({"action": "copy", "source": str(source), "path": str(target)})
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return actions


def template_replacements_for_project(
    project_root: Path,
    root: Path,
    governance_root: Path,
    capability_root: Path,
) -> dict[str, str]:
    return {
        "CHANGE_ME_GLOBAL_AGENT_FABRIC_ROOT": str(governance_root),
        "CHANGE_ME_KNOWLEDGEOS_CAPABILITY_ROOT": str(capability_root),
        "CHANGE_ME_AGENT_FABRIC_IMPLEMENTATION_ROOT": str(capability_root),
        "CHANGE_ME_KNOWLEDGEOS_BIN": str(root / "bin" / "knowledgeos"),
        "CHANGE_ME_PROJECT_NAME": project_root.name,
        "CHANGE_ME_PROJECT_ROOT": str(project_root),
        "CHANGE_ME_WORKSPACE_ID": safe_slug(project_root.name).lower(),
        "CHANGE_ME_DATE": datetime.now().strftime("%Y-%m-%d"),
    }


def fill_missing_control_plane_files(
    project_root: Path,
    root: Path,
    governance_root: Path,
    capability_root: Path,
    *,
    apply: bool,
) -> list[dict[str, str]]:
    template = root / "templates" / "project-control-plane"
    replacements = template_replacements_for_project(project_root, root, governance_root, capability_root)
    actions: list[dict[str, str]] = []
    for rel in REQUIRED_PROJECT_FILES:
        target = project_root / rel
        if target.exists():
            actions.append({"action": "ok", "path": str(target)})
            continue
        source = template / rel
        if not source.exists():
            actions.append({"action": "missing_source", "path": str(source)})
            continue
        text = read_text(source)
        for old, new in replacements.items():
            text = text.replace(old, new)
        actions.append({"action": "write_missing", "source": str(source), "path": str(target)})
        if apply:
            write_text(target, text)
    return actions


def route_order_needs_lifecycle_upgrade(route_order: list[str]) -> bool:
    run_index = next((idx for idx, item in enumerate(route_order) if "run-task" in item), -1)
    dispatch_event_index = next((idx for idx, item in enumerate(route_order) if "dispatch-task" in item and "--run-id" in item), -1)
    context_index = next((idx for idx, item in enumerate(route_order) if "context-pack" in item), -1)
    plan_index = next((idx for idx, item in enumerate(route_order) if "plan-task" in item), -1)
    phase_index = next((idx for idx, item in enumerate(route_order) if "phase-task" in item), -1)
    eval_index = next((idx for idx, item in enumerate(route_order) if "eval-task" in item), -1)
    verify_context_index = next((idx for idx, item in enumerate(route_order) if "verify-context" in item), -1)
    verify_index = next((idx for idx, item in enumerate(route_order) if "verify-lifecycle" in item), -1)
    verify_effects_index = next((idx for idx, item in enumerate(route_order) if "verify-effects" in item), -1)
    complete_index = next((idx for idx, item in enumerate(route_order) if "complete-task" in item), -1)

    required_indices = [
        run_index,
        dispatch_event_index,
        context_index,
        plan_index,
        phase_index,
        eval_index,
        verify_context_index,
        verify_index,
        verify_effects_index,
        complete_index,
    ]
    if any(index < 0 for index in required_indices):
        return True
    if not run_index < dispatch_event_index < context_index < plan_index:
        return True
    return not (
        eval_index < complete_index
        and verify_context_index < complete_index
        and verify_index < complete_index
        and verify_effects_index < complete_index
    )


def normalize_route_order(route_order: list[str]) -> list[str]:
    cleaned = [
        item
        for item in route_order
        if not any(marker in item for marker in LIFECYCLE_COMMAND_MARKERS)
    ]
    run_index = next((idx for idx, item in enumerate(cleaned) if "run-task" in item), -1)
    if run_index < 0:
        cleaned.append("run-task --project-root . --task-id <task-id>")
        run_index = len(cleaned) - 1
    prefix = cleaned[: run_index + 1]
    suffix = cleaned[run_index + 1 :]
    return prefix + LIFECYCLE_ROUTE_COMMANDS[:4] + suffix + LIFECYCLE_ROUTE_COMMANDS[4:]


def render_workflow_profiles(profiles: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# KnowledgeOS workflow router.",
        "# Task classification is open, but lifecycle routing must be explicit.",
        "workflows:",
    ]
    for name, profile in profiles.items():
        lines.append(f"  {name}:")
        route_order = profile.get("route_order", [])
        lines.append("    route_order:")
        for item in route_order if isinstance(route_order, list) else [str(route_order)]:
            lines.append(f"      - {item}")
        for key, value in profile.items():
            if key == "route_order":
                continue
            if isinstance(value, list):
                lines.append(f"    {key}:")
                for item in value:
                    lines.append(f"      - {item}")
            else:
                lines.append(f"    {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def upgrade_workflow_router_file(project_root: Path, *, apply: bool, backup_name: str) -> dict[str, Any] | None:
    path = project_root / ".agent-os" / "workflows" / "router.yaml"
    if not path.exists():
        return None
    profiles = parse_workflow_profiles(path)
    changed = False
    upgraded_profiles: list[str] = []
    for name, profile in profiles.items():
        route_order = profile.get("route_order", [])
        if not isinstance(route_order, list):
            route_order = [str(route_order)]
        if route_order_needs_lifecycle_upgrade(route_order):
            profile["route_order"] = normalize_route_order(route_order)
            changed = True
            upgraded_profiles.append(name)
    if not changed:
        return None
    action: dict[str, Any] = {"action": "upgrade_workflow_router", "path": str(path), "profiles": upgraded_profiles, "backup": ""}
    if apply:
        backup = backup_project_file(project_root, path, backup_name)
        action["backup"] = str(backup)
        write_text(path, render_workflow_profiles(profiles))
    return action


def ensure_archive_write_guard(project_root: Path, *, apply: bool, backup_name: str) -> dict[str, str] | None:
    path = project_root / ".agent-os" / "write-policy.yaml"
    if not path.exists():
        return None
    policy = load_write_policy(project_root)
    if "archive/**" in policy.get("controlled", []):
        return None
    lines = read_text(path).splitlines()
    insert_at: int | None = None
    in_controlled = False
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped == "controlled:":
            in_controlled = True
            insert_at = idx + 1
            continue
        if in_controlled:
            if raw.startswith("  ") and not raw.startswith("    ") and stripped.endswith(":"):
                break
            if stripped.startswith("-"):
                insert_at = idx + 1
    if insert_at is None:
        return None
    action = {"action": "add_archive_write_guard", "path": str(path), "backup": ""}
    if apply:
        backup = backup_project_file(project_root, path, backup_name)
        action["backup"] = str(backup)
        lines.insert(insert_at, "    - archive/**")
        write_text(path, "\n".join(lines).rstrip() + "\n")
    return action


def registry_block_from_entry(entry: dict[str, str]) -> str:
    ordered_keys = [
        "kind",
        "status",
        "scope",
        "invocation",
        "task_fit",
        "capability_fit",
        "runtime",
        "runtime_tool",
        "runtime_agent_type",
        "adapter",
        "adapter_role",
        "human_gate",
        "execution_mode",
        "source_path",
        "notes",
    ]
    lines = [f"  - id: {entry['id']}"]
    for key in ordered_keys:
        value = entry.get(key, "")
        if value != "":
            lines.append(f"    {key}: {value}")
    return "\n".join(lines)


def codex_native_registry_entries() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for item in CODEX_NATIVE_SUBAGENTS:
        entries.append(
            {
                "id": item["id"],
                "kind": "subagent",
                "status": "recommended",
                "scope": item["scope"],
                "invocation": "via_codex_runtime_spawn_agent",
                "task_fit": item["task_fit"],
                "capability_fit": item["capability_fit"],
                "runtime": "codex",
                "runtime_tool": CODEX_RUNTIME_TOOL,
                "runtime_agent_type": item["runtime_agent_type"],
                "human_gate": "true",
                "execution_mode": "ask",
                "source_path": f"codex-runtime:{CODEX_RUNTIME_TOOL}",
                "notes": "Codex native runtime subagent. Dispatch plan generates intent; actual spawn happens through Codex runtime.",
            }
        )
    return entries


def ensure_runtime_native_subagents(project_root: Path, *, apply: bool, backup_name: str) -> dict[str, Any] | None:
    registry_path = project_root / ".agent-os" / "tool-registry.yaml"
    if not registry_path.exists():
        return None
    existing_ids = {entry.get("id", "") for entry in load_tool_registry(project_root)}
    missing = [entry for entry in codex_native_registry_entries() if entry["id"] not in existing_ids]
    if not missing:
        return None
    action: dict[str, Any] = {
        "action": "add_runtime_native_subagents",
        "path": str(registry_path),
        "missing_ids": [entry["id"] for entry in missing],
        "backup": "",
    }
    if apply:
        backup = backup_project_file(project_root, registry_path, backup_name)
        action["backup"] = str(backup)
        addition = "\n\n  # Codex native runtime subagents. Actual spawn is performed by Codex runtime tools.\n" + "\n\n".join(
            registry_block_from_entry(entry) for entry in missing
        )
        current = read_text(registry_path).rstrip()
        write_text(registry_path, current + addition + "\n")
    return action


def audit_project_mount(
    project_root: Path,
    root: Path,
    governance_root: Path,
    capability_root: Path,
    *,
    apply: bool,
    backup_name: str,
) -> dict[str, Any]:
    agent_os = project_root / ".agent-os"
    fabric_path = agent_os / "fabric-link.yaml"
    workspace_path = agent_os / "workspace.yaml"
    issues: list[str] = []
    actions: list[dict[str, str]] = []
    if not agent_os.is_dir():
        return {"project_root": str(project_root), "status": "unmanaged", "issues": ["missing .agent-os"], "actions": []}
    if not fabric_path.exists():
        return {"project_root": str(project_root), "status": "broken", "issues": ["missing .agent-os/fabric-link.yaml"], "actions": []}

    fabric = parse_scalar_values(
        fabric_path,
        {"governance_root", "capability_root", "implementation_root", "postflight_required"},
    )
    current_governance = fabric.get("governance_root", "")
    current_capability = fabric.get("capability_root") or fabric.get("implementation_root", "")
    current_governance_path = Path(current_governance).expanduser() if current_governance else None
    if (
        current_governance_path
        and project_root != root
        and current_governance_path.name == "global-agent-fabric"
        and current_governance_path != governance_root
    ):
        issues.append("legacy_preos_governance_root")
    if current_governance and Path(current_governance).expanduser() != governance_root and project_root != root:
        issues.append("noncanonical_governance_root")
    if current_capability and Path(current_capability).expanduser() != capability_root and project_root != root:
        issues.append("noncanonical_capability_root")
    if fabric.get("postflight_required", "").lower() == "true":
        hook = resolve_postflight_hook(project_root, fabric)
        if not hook or not hook.exists() or not os.access(hook, os.X_OK):
            issues.append("postflight_hook_missing_or_not_executable")

    for required in REQUIRED_PROJECT_FILES:
        if not (project_root / required).exists():
            issues.append(f"missing_control_file:{required}")
    router_action = upgrade_workflow_router_file(project_root, apply=False, backup_name=backup_name)
    if router_action:
        issues.append("workflow_router_lifecycle_drift")
    archive_action = ensure_archive_write_guard(project_root, apply=False, backup_name=backup_name)
    if archive_action:
        issues.append("missing_archive_write_guard")
    native_subagents_action = ensure_runtime_native_subagents(project_root, apply=False, backup_name=backup_name)
    if native_subagents_action:
        issues.append("missing_runtime_native_subagents")

    should_rewrite_mount = project_root != root and (
        "legacy_preos_governance_root" in issues
        or "noncanonical_governance_root" in issues
        or "noncanonical_capability_root" in issues
        or "postflight_hook_missing_or_not_executable" in issues
    )
    if should_rewrite_mount:
        for path in [fabric_path, workspace_path]:
            if not path.exists():
                continue
            original = read_text(path)
            updated = replace_scalar_line(original, "governance_root", str(governance_root))
            updated = replace_scalar_line(updated, "capability_root", str(capability_root))
            updated = replace_scalar_line(updated, "implementation_root", str(capability_root))
            if updated != original:
                action = {"action": "rewrite_mount", "path": str(path), "backup": ""}
                if apply:
                    backup = backup_project_file(project_root, path, backup_name)
                    action["backup"] = str(backup)
                    write_text(path, updated)
                actions.append(action)

    missing_actions = fill_missing_control_plane_files(
        project_root,
        root,
        governance_root,
        capability_root,
        apply=apply,
    )
    actions.extend(action for action in missing_actions if action["action"] != "ok")
    router_action = upgrade_workflow_router_file(project_root, apply=apply, backup_name=backup_name)
    if router_action:
        actions.append(router_action)
    archive_action = ensure_archive_write_guard(project_root, apply=apply, backup_name=backup_name)
    if archive_action:
        actions.append(archive_action)
    native_subagents_action = ensure_runtime_native_subagents(project_root, apply=apply, backup_name=backup_name)
    if native_subagents_action:
        actions.append(native_subagents_action)

    # Re-read after optional repair so the reported final status reflects the
    # actual mount state rather than the pre-repair state.
    if apply:
        return audit_project_mount(
            project_root,
            root,
            governance_root,
            capability_root,
            apply=False,
            backup_name=backup_name,
        ) | {"repair_actions": actions}

    status = "ok" if not issues else "attention"
    return {"project_root": str(project_root), "status": status, "issues": sorted(set(issues)), "actions": actions}


def write_postflight_evidence(run_dir: Path, lines: list[str]) -> None:
    write_text(run_dir / "postflight.md", "\n".join(lines).rstrip() + "\n")


def postflight_environment_for_hook(hook: Path, run_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    template_kernel = knowledgeos_root_from_file() / "templates" / "governance-core"
    try:
        hook.resolve().relative_to(template_kernel.resolve())
    except ValueError:
        return env
    # The source repository uses template hooks for smoke tests. Keep generated
    # postflight ledgers inside the ignored run evidence rather than dirtying
    # the public template files.
    env["KNOWLEDGEOS_KERNEL_ROOT"] = str(run_dir / "kernel-postflight")
    return env


def run_postflight_gate(project_root: Path, run_dir: Path, summary: str, allow_pending_reason: str = "") -> dict[str, Any]:
    fabric = fabric_contract(project_root)
    if fabric and fabric.get("postflight_required", "").lower() != "true":
        raise ValueError("runtime contract requires postflight_required: true before completion")
    required = fabric.get("postflight_required", "").lower() == "true"
    if not required:
        return {"sync_status": "NOT_REQUIRED", "status_marker": "", "postflight": ""}

    hook = resolve_postflight_hook(project_root, fabric)
    if not hook or not hook.exists() or not os.access(hook, os.X_OK):
        detail = f"postflight hook missing or not executable: {hook}"
        if allow_pending_reason.strip():
            write_postflight_evidence(
                run_dir,
                [
                    "# Postflight",
                    "",
                    "Status: pending",
                    f"Reason: {allow_pending_reason.strip()}",
                    f"Detail: {detail}",
                    "",
                ],
            )
            return {
                "sync_status": "PENDING",
                "status_marker": "",
                "postflight": str(run_dir / "postflight.md"),
                "pending_reason": allow_pending_reason.strip(),
            }
        raise ValueError(detail)

    try:
        completed = subprocess.run(
            [str(hook), summary],
            cwd=str(project_root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=60,
            env=postflight_environment_for_hook(hook, run_dir),
        )
    except subprocess.TimeoutExpired as exc:
        if allow_pending_reason.strip():
            write_postflight_evidence(
                run_dir,
                [
                    "# Postflight",
                    "",
                    "Status: pending",
                    f"Reason: {allow_pending_reason.strip()}",
                    f"Detail: postflight hook timed out: {hook}",
                    "",
                ],
            )
            return {
                "sync_status": "PENDING",
                "status_marker": "",
                "postflight": str(run_dir / "postflight.md"),
                "pending_reason": allow_pending_reason.strip(),
            }
        raise ValueError(f"postflight hook timed out: {hook}") from exc
    evidence_lines = [
        "# Postflight",
        "",
        f"Hook: {hook}",
        f"Exit Code: {completed.returncode}",
        "",
        "## Stdout",
        "",
        completed.stdout.rstrip(),
        "",
        "## Stderr",
        "",
        completed.stderr.rstrip(),
        "",
    ]
    if completed.returncode == 0 and "[SYNC_OK]" in completed.stdout:
        write_postflight_evidence(run_dir, evidence_lines + ["Status: SYNC_OK", "Status Marker: [SYNC_OK]", ""])
        return {
            "sync_status": "SYNC_OK",
            "status_marker": "[SYNC_OK]",
            "postflight": str(run_dir / "postflight.md"),
        }
    if allow_pending_reason.strip():
        write_postflight_evidence(
            run_dir,
            evidence_lines
            + [
                "Status: pending",
                f"Reason: {allow_pending_reason.strip()}",
                "",
            ],
        )
        return {
            "sync_status": "PENDING",
            "status_marker": "",
            "postflight": str(run_dir / "postflight.md"),
            "pending_reason": allow_pending_reason.strip(),
        }
    raise ValueError(f"postflight hook failed or did not emit [SYNC_OK]: {hook}")


def complete_task(
    project_root: Path,
    task_id: str,
    run_id: str,
    summary: str,
    allow_missing_eval: bool = False,
    allow_manual_eval: bool = False,
    allow_missing_outputs: bool = False,
    allow_pending_postflight: str = "",
    override_reason: str = "",
) -> dict[str, Any]:
    task = find_task(project_root, task_id)
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    run_yaml = run_dir / "run.yaml"

    override_flags = {
        "allow_missing_eval": allow_missing_eval,
        "allow_manual_eval": allow_manual_eval,
        "allow_missing_outputs": allow_missing_outputs,
    }
    active_overrides = [name for name, enabled in override_flags.items() if enabled]
    if active_overrides and not override_reason.strip():
        raise ValueError("completion overrides require --override-reason")

    eval_path = run_dir / "eval.md"
    if not allow_missing_eval and not eval_has_passed(eval_path):
        raise ValueError("eval.md must contain a line like 'Status: passed' before completion")
    if not allow_missing_eval and not allow_manual_eval and not eval_is_knowledgeos_generated(eval_path):
        raise ValueError("eval.md must be generated by `knowledgeos eval-task` before completion")
    if not (allow_missing_eval or allow_manual_eval) and not has_command_event(run_dir, "eval-task", task_id, run_id, status="passed"):
        raise ValueError("eval.md must have matching `knowledgeos eval-task` command evidence before completion")
    if not allow_missing_outputs:
        missing_outputs = missing_declared_outputs(project_root, task_id)
        if missing_outputs:
            raise ValueError("declared task outputs are missing: " + "; ".join(missing_outputs))

    lifecycle = verify_lifecycle(project_root, task_id, run_id)
    if lifecycle.get("status") != "passed":
        raise ValueError("lifecycle verification failed: " + json.dumps(lifecycle.get("errors", []), ensure_ascii=False))
    context_contract = verify_context_contract(project_root, task_id, run_id)
    if context_contract.get("status") != "passed":
        raise ValueError("context contract verification failed: " + json.dumps(context_contract.get("errors", []), ensure_ascii=False))
    effects = verify_effects(project_root, task_id, run_id)
    if effects.get("status") == "failed":
        raise ValueError("effect verification failed: " + json.dumps(effects.get("errors", []), ensure_ascii=False))
    decisions = verify_decisions(project_root, task_id, run_id)
    if decisions.get("status") == "failed":
        raise ValueError("decision verification failed: " + json.dumps(decisions.get("errors", []), ensure_ascii=False))

    dispatch_report = build_dispatch_report(project_root, task_id, run_id)
    postflight = run_postflight_gate(project_root, run_dir, summary, allow_pending_postflight)
    mission_flow: dict[str, Any] | None = None
    if task.get("complexity", "medium") in MISSION_FLOW_COMPLEXITIES:
        mission_flow = write_mission_flow_markdown(
            project_root,
            task_id,
            run_id,
            sync_status=str(postflight.get("sync_status", "")),
        )
    completed_at = datetime.now(timezone.utc).isoformat()
    receipt_lines = [
        "# Receipt",
        "",
        f"Run: {run_id}",
        "",
        f"Task: {task_id}",
        "",
        "Status: completed",
        "",
        f"Completed At: {completed_at}",
        "",
        f"Summary: {summary}",
        "",
        f"Lifecycle Status: {lifecycle.get('status')}",
        "",
        f"Context Contract Status: {context_contract.get('status')}",
        "",
        f"Effect Verification Status: {effects.get('status')}",
        "",
        f"Effect Verify Marker: {effects.get('marker', '')}",
        "",
        f"Decision Verification Status: {decisions.get('status')}",
        "",
        f"Decision Verify Marker: {decisions.get('marker', '')}",
        "",
        f"Agent Dispatch Status: {dispatch_report.get('dispatch_report_marker', '')}",
        "",
        f"Agent Dispatch Marker: {dispatch_report.get('marker', '')}",
        "",
        f"Agents Invoked: {dispatch_report.get('agent_count', 0)}",
        "",
        f"Capabilities Invoked: {dispatch_report.get('capability_count', 0)}",
        "",
        f"Agent Dispatch Report: {dispatch_report.get('report', '')}",
        "",
        f"Mission Flow Marker: {mission_flow.get('marker', '') if mission_flow else 'not required'}",
        "",
        f"Mission Flow: {mission_flow.get('source', '') if mission_flow else 'not required for simple task'}",
        "",
        f"Sync Status: {postflight.get('sync_status')}",
        "",
    ]
    if effects.get("strictness") == "off":
        receipt_lines.extend(
            [
                "STRICTNESS_DOWNGRADED:",
                "",
                str(effects.get("downgrade_reason", "")),
                "",
            ]
        )
    if effects.get("warnings"):
        receipt_lines.extend(
            [
                "Effect Warnings:",
                "",
                json.dumps(effects.get("warnings", []), ensure_ascii=False),
                "",
            ]
        )
    if decisions.get("strictness") == "off":
        receipt_lines.extend(
            [
                "DECISION_STRICTNESS_DOWNGRADED:",
                "",
                str(decisions.get("downgrade_reason", "")),
                "",
            ]
        )
    if decisions.get("warnings"):
        receipt_lines.extend(
            [
                "Decision Warnings:",
                "",
                json.dumps(decisions.get("warnings", []), ensure_ascii=False),
                "",
            ]
        )
    if postflight.get("status_marker"):
        receipt_lines.extend([f"Status Marker: {postflight['status_marker']}", ""])
    if postflight.get("pending_reason"):
        receipt_lines.extend(["Pending Postflight:", "", str(postflight["pending_reason"]), ""])
    if active_overrides:
        receipt_lines.extend(
            [
                "Completion Override:",
                "",
                f"Flags: {', '.join(active_overrides)}",
                f"Reason: {override_reason.strip()}",
                "",
            ]
        )
    receipt = "\n".join(receipt_lines)
    handoff = "\n".join(
        [
            "# Current Handoff",
            "",
            f"Completed run: {run_id}",
            "",
            f"Task: {task_id}",
            "",
            f"Summary: {summary}",
            "",
            "Next agent should read the latest receipt before starting new work.",
            "",
        ]
    )
    write_text(run_dir / "receipt.md", receipt)
    write_text(run_dir / "handoff.md", handoff)
    write_text(project_root / ".agent-os" / "receipts" / "latest.md", receipt)
    write_text(project_root / ".agent-os" / "handoffs" / "current.md", handoff)
    update_run_status(run_yaml, "completed")
    set_task_status(project_root, task_id, "completed")
    return {
        "task_id": task_id,
        "task_title": task.get("title", ""),
        "run_id": run_id,
        "status": "completed",
        "lifecycle_status": lifecycle.get("status"),
        "context_contract_status": context_contract.get("status"),
        "effect_status": effects.get("status"),
        "effect_verify_marker": effects.get("marker", ""),
        "decision_status": decisions.get("status"),
        "decision_verify_marker": decisions.get("marker", ""),
        "agent_dispatch_status": dispatch_report.get("dispatch_report_marker", ""),
        "agent_dispatch_marker": dispatch_report.get("marker", ""),
        "agents_invoked": dispatch_report.get("agent_count", 0),
        "capabilities_invoked": dispatch_report.get("capability_count", 0),
        "dispatch_report": dispatch_report.get("report", ""),
        "flow_marker": mission_flow.get("flow_marker", "") if mission_flow else "",
        "flow_summary_marker": mission_flow.get("marker", "") if mission_flow else "",
        "flow_mermaid": mission_flow.get("mermaid", "") if mission_flow else "",
        "flow_source": mission_flow.get("source", "") if mission_flow else "",
        "sync_status": postflight.get("sync_status"),
        "status_marker": postflight.get("status_marker", ""),
        "postflight": postflight.get("postflight", ""),
        "receipt": str(run_dir / "receipt.md"),
        "handoff": str(run_dir / "handoff.md"),
    }


HTML_REPORT_KINDS = {"receipt", "handoff", "rich-report", "decision-map", "mission-flow"}
HTML_DEFAULT_THEME = "knowledgeos-default"
HTML_PRESENTATION_MODES = {"default", "minimal", "bare", "fragment"}
HTML_DEFAULT_PRESENTATION = "default"
HTML_SOURCE_TRUTH_NOTICE = "HTML is presentation, not source of truth."
MISSION_FLOW_COMPLEXITIES = {"medium", "high", "complex"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def resolve_project_artifact(project_root: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(f"path must stay inside project root: {value}") from exc
    return resolved


def html_escape(text: Any) -> str:
    return html_lib.escape(str(text), quote=True)


def parse_reporting_policy(project_root: Path) -> dict[str, Any]:
    project_yaml = project_root / ".agent-os" / "project.yaml"
    if not project_yaml.exists():
        return {
            "html_sidecars": True,
            "html_source_of_truth": False,
            "html_presentation_default": HTML_DEFAULT_PRESENTATION,
            "html_required_metadata": True,
        }
    scalars = parse_scalar_values(
        project_yaml,
        {
            "html_sidecars",
            "html_source_of_truth",
            "html_presentation_default",
            "html_required_metadata",
        },
    )
    presentation = (scalars.get("html_presentation_default") or HTML_DEFAULT_PRESENTATION).lower()
    return {
        "html_sidecars": scalars.get("html_sidecars", "true").lower() != "false",
        "html_source_of_truth": scalars.get("html_source_of_truth", "false").lower() == "true",
        "html_presentation_default": presentation,
        "html_required_metadata": scalars.get("html_required_metadata", "true").lower() != "false",
    }


def resolve_html_presentation(project_root: Path, requested: str = "") -> str:
    presentation = (requested or "").strip().lower()
    if not presentation:
        presentation = str(parse_reporting_policy(project_root).get("html_presentation_default") or HTML_DEFAULT_PRESENTATION)
    if presentation not in HTML_PRESENTATION_MODES:
        raise ValueError(f"unsupported HTML presentation mode: {presentation}")
    return presentation


def markdown_heading_anchor(title: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", title.lower()).strip("-")
    if not base:
        base = "section"
    anchor = base
    index = 2
    while anchor in used:
        anchor = f"{base}-{index}"
        index += 1
    used.add(anchor)
    return anchor


def markdown_to_html_fragment(markdown: str, anchor_prefix: str = "") -> tuple[str, str, list[dict[str, Any]]]:
    """Render a safe, small Markdown subset into a composable HTML fragment."""
    lines = markdown.splitlines()
    html_lines: list[str] = []
    sections: list[dict[str, Any]] = []
    title = "KnowledgeOS Report"
    anchors: set[str] = set()
    in_list = False
    in_code = False
    code_lines: list[str] = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html_lines.append("</ul>")
            in_list = False

    def close_code() -> None:
        nonlocal in_code, code_lines
        html_lines.append(f"<pre><code>{html_escape(chr(10).join(code_lines))}</code></pre>")
        code_lines = []
        in_code = False

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                close_code()
            else:
                close_list()
                in_code = True
                code_lines = []
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            close_list()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading:
            close_list()
            level = len(heading.group(1))
            heading_title = heading.group(2).strip()
            if title == "KnowledgeOS Report" and level == 1:
                title = heading_title
            anchor = markdown_heading_anchor(heading_title, anchors)
            if anchor_prefix:
                anchor = f"{anchor_prefix}-{anchor}"
            sections.append({"id": anchor, "title": heading_title, "level": level})
            html_lines.append(
                f'<h{level} id="{html_escape(anchor)}">{html_escape(heading_title)}</h{level}>'
            )
            continue
        if stripped.startswith(("- ", "* ")):
            if not in_list:
                html_lines.append('<ul class="kos-list">')
                in_list = True
            html_lines.append(f"<li>{html_escape(stripped[2:].strip())}</li>")
            continue
        close_list()
        if stripped.startswith(">"):
            html_lines.append(f"<blockquote>{html_escape(stripped.lstrip('> ').strip())}</blockquote>")
        else:
            html_lines.append(f"<p>{html_escape(stripped)}</p>")
    close_list()
    if in_code:
        close_code()
    return "\n".join(html_lines), title, sections


def html_report_css(theme: str) -> str:
    return f"""
:root {{
  --kos-bg: #f5f7fb;
  --kos-ink: #152033;
  --kos-muted: #607089;
  --kos-card: #ffffff;
  --kos-line: #dce5f2;
  --kos-accent: #0f766e;
  --kos-accent-2: #2563eb;
  --kos-warn: #b45309;
  --kos-radius: 20px;
  --kos-shadow: 0 24px 70px rgba(21, 32, 51, 0.12);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  color: var(--kos-ink);
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.14), transparent 36rem),
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.16), transparent 34rem),
    var(--kos-bg);
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.62;
}}
.kos-shell {{ max-width: 1120px; margin: 0 auto; padding: 56px 24px 48px; }}
.kos-hero {{
  padding: 34px;
  border: 1px solid rgba(255,255,255,0.7);
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(236,245,255,0.86));
  box-shadow: var(--kos-shadow);
}}
.kos-eyebrow {{ color: var(--kos-accent); font-size: 0.78rem; font-weight: 800; letter-spacing: 0.16em; text-transform: uppercase; }}
h1 {{ margin: 10px 0 12px; font-size: clamp(2.2rem, 6vw, 4.4rem); line-height: 0.95; letter-spacing: -0.055em; }}
.kos-subtitle {{ max-width: 760px; color: var(--kos-muted); font-size: 1.05rem; }}
.kos-grid {{ display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 22px; margin-top: 24px; align-items: start; }}
.kos-report-fragment, .kos-panel {{
  background: rgba(255,255,255,0.92);
  border: 1px solid var(--kos-line);
  border-radius: var(--kos-radius);
  box-shadow: 0 14px 40px rgba(21, 32, 51, 0.07);
}}
.kos-report-fragment {{ padding: 28px; overflow: hidden; }}
.kos-panel {{ padding: 20px; position: sticky; top: 20px; }}
.kos-report-fragment h1, .kos-report-fragment h2, .kos-report-fragment h3 {{ letter-spacing: -0.025em; line-height: 1.15; }}
.kos-report-fragment h1 {{ font-size: 2.2rem; }}
.kos-report-fragment h2 {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--kos-line); color: #102a43; }}
.kos-report-fragment p, .kos-report-fragment li {{ color: #26364d; }}
.kos-list {{ padding-left: 1.25rem; }}
pre {{ overflow: auto; padding: 16px; border-radius: 16px; background: #101827; color: #e5edf8; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.9em; }}
blockquote {{ margin: 18px 0; padding: 14px 18px; border-left: 4px solid var(--kos-accent-2); background: #eef5ff; border-radius: 12px; }}
.kos-meta {{ display: grid; gap: 10px; margin: 0; }}
.kos-meta div {{ padding: 10px 12px; border-radius: 12px; background: #f4f8fd; border: 1px solid var(--kos-line); overflow-wrap: anywhere; }}
.kos-meta dt {{ color: var(--kos-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; }}
.kos-meta dd {{ margin: 2px 0 0; font-weight: 700; }}
.kos-nav {{ display: grid; gap: 8px; margin-top: 16px; }}
.kos-nav a {{ color: var(--kos-accent-2); text-decoration: none; font-weight: 700; }}
.kos-fragment-meta {{ margin-top: 28px; }}
details {{ margin-top: 20px; padding: 14px 16px; border: 1px solid var(--kos-line); border-radius: 16px; background: #fbfdff; }}
summary {{ cursor: pointer; font-weight: 800; }}
.kos-footer {{ margin-top: 28px; color: var(--kos-muted); font-size: 0.9rem; text-align: center; }}
.kos-notice {{ color: var(--kos-warn); font-weight: 800; }}
.kos-flow {{ display: grid; gap: 14px; margin: 20px 0; }}
.kos-flow-card {{
  border: 1px solid var(--kos-line);
  border-radius: 18px;
  padding: 16px 18px;
  background: #f8fbff;
}}
.kos-flow-card h3 {{ margin: 0 0 6px; }}
.kos-flow-card p {{ margin: 0; }}
.kos-flow-intent {{ background: #e8f3ff; border-color: #b8d9ff; }}
.kos-flow-guard {{ background: #fff7df; border-color: #f3d58a; }}
.kos-flow-work {{ background: #eafbf0; border-color: #b8e7c7; }}
.kos-flow-proof {{ background: #f3e8ff; border-color: #d8b4fe; }}
.kos-flow-done {{ background: #dcfce7; border-color: #86efac; }}
@media (max-width: 860px) {{
  .kos-shell {{ padding: 28px 14px; }}
  .kos-grid {{ grid-template-columns: 1fr; }}
  .kos-panel {{ position: static; }}
  .kos-hero {{ padding: 24px; }}
}}
/* theme: {html_escape(safe_slug(theme))} */
""".strip()


def build_html_fragment(
    *,
    kind: str,
    title: str,
    source_rel: str,
    source_sha: str,
    run_id: str,
    body_html: str,
    sections: list[dict[str, Any]],
    generated_at: str,
    presentation: str = HTML_DEFAULT_PRESENTATION,
) -> str:
    section_items = "\n".join(
        f'<li><a href="#{html_escape(item["id"])}">{html_escape(item["title"])}</a></li>' for item in sections[:12]
    )
    section_nav = f'<ul class="kos-list">{section_items}</ul>' if section_items else "<p>No headings detected.</p>"
    metadata = [
        ("Kind", kind),
        ("Run ID", run_id or "not run-bound"),
        ("Source", source_rel),
        ("Source SHA-256", source_sha),
        ("Generated", generated_at),
    ]
    meta_html = "\n".join(
        f"<div><dt>{html_escape(label)}</dt><dd>{html_escape(value)}</dd></div>" for label, value in metadata
    )
    if presentation != "default":
        return f"""
<section class="kos-fragment kos-fragment-{html_escape(presentation)}" data-kos-fragment="true" data-kind="{html_escape(kind)}" data-source-sha256="{html_escape(source_sha)}">
  {body_html}
  <footer class="kos-evidence-footer">
    <details open>
      <summary>Evidence metadata</summary>
      <dl class="kos-meta">{meta_html}</dl>
      <p class="kos-notice">{HTML_SOURCE_TRUTH_NOTICE}</p>
      <nav class="kos-nav" aria-label="Report sections">{section_nav}</nav>
    </details>
  </footer>
</section>
""".strip()
    return f"""
<article class="kos-report-fragment" data-kos-fragment="true" data-kind="{html_escape(kind)}" data-source-sha256="{html_escape(source_sha)}">
  <div class="kos-eyebrow">{html_escape(kind)}</div>
  {body_html}
  <details class="kos-fragment-meta">
    <summary>Source metadata</summary>
    <dl class="kos-meta">{meta_html}</dl>
    <p class="kos-notice">{HTML_SOURCE_TRUTH_NOTICE}</p>
    <nav class="kos-nav" aria-label="Report sections">{section_nav}</nav>
  </details>
</article>
""".strip()


def build_html_document(
    *,
    title: str,
    kind: str,
    body: str,
    source_rel: str,
    source_sha: str,
    run_id: str,
    generated_at: str,
    theme: str,
    presentation: str = HTML_DEFAULT_PRESENTATION,
) -> str:
    if presentation == "minimal":
        return build_minimal_html_document(
            title=title,
            kind=kind,
            body=body,
            source_rel=source_rel,
            source_sha=source_sha,
            run_id=run_id,
            generated_at=generated_at,
            theme=theme,
        )
    if presentation == "bare":
        return build_bare_html_document(
            title=title,
            kind=kind,
            body=body,
            source_rel=source_rel,
            source_sha=source_sha,
            run_id=run_id,
            generated_at=generated_at,
            theme=theme,
        )
    nav_hint = "Composable sidecar report"
    subtitle = (
        "A self-contained KnowledgeOS HTML sidecar generated from canonical Markdown, YAML, or NDJSON evidence. "
        "Use it for human review; keep source files as the contract."
    )
    meta_rows = [
        ("Kind", kind),
        ("Run ID", run_id or "not run-bound"),
        ("Source", source_rel),
        ("Source SHA-256", source_sha),
        ("Generated", generated_at),
        ("Theme", theme),
    ]
    meta_html = "\n".join(
        f"<div><dt>{html_escape(label)}</dt><dd>{html_escape(value)}</dd></div>" for label, value in meta_rows
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="knowledgeos-source-sha256" content="{html_escape(source_sha)}">
  <meta name="knowledgeos-source-path" content="{html_escape(source_rel)}">
  <title>{html_escape(title)}</title>
  <style>{html_report_css(theme)}</style>
</head>
<body>
  <main class="kos-shell">
    <section class="kos-hero">
      <div class="kos-eyebrow">{html_escape(nav_hint)}</div>
      <h1>{html_escape(title)}</h1>
      <p class="kos-subtitle">{html_escape(subtitle)}</p>
    </section>
    <section class="kos-grid">
      <div>{body}</div>
      <aside class="kos-panel" aria-label="Report metadata">
        <h2>Evidence Metadata</h2>
        <dl class="kos-meta">{meta_html}</dl>
        <p class="kos-notice">{HTML_SOURCE_TRUTH_NOTICE}</p>
      </aside>
    </section>
    <footer class="kos-footer">{HTML_SOURCE_TRUTH_NOTICE}</footer>
  </main>
</body>
</html>
"""


def build_minimal_html_document(
    *,
    title: str,
    kind: str,
    body: str,
    source_rel: str,
    source_sha: str,
    run_id: str,
    generated_at: str,
    theme: str,
) -> str:
    meta_rows = [
        ("Kind", kind),
        ("Run ID", run_id or "not run-bound"),
        ("Source", source_rel),
        ("Source SHA-256", source_sha),
        ("Generated", generated_at),
        ("Theme", theme),
        ("Presentation", "minimal"),
    ]
    meta_html = "\n".join(
        f"<div><dt>{html_escape(label)}</dt><dd>{html_escape(value)}</dd></div>" for label, value in meta_rows
    )
    css = """
* { box-sizing: border-box; }
body { margin: 0; color: #172033; background: #fbfcfe; font-family: Georgia, "Times New Roman", serif; line-height: 1.68; }
main { max-width: 880px; margin: 0 auto; padding: 42px 22px; }
h1, h2, h3 { line-height: 1.18; color: #101827; }
a { color: #155eef; }
pre { overflow: auto; padding: 14px; border: 1px solid #d8dee9; border-radius: 10px; background: #f3f6fb; }
blockquote { margin: 18px 0; padding: 12px 16px; border-left: 4px solid #94a3b8; background: #f8fafc; }
.kos-evidence-footer, .kos-page-evidence { margin-top: 34px; padding-top: 18px; border-top: 1px solid #d8dee9; font-size: 0.92rem; }
.kos-meta { display: grid; gap: 8px; margin: 0; }
.kos-meta div { overflow-wrap: anywhere; }
.kos-meta dt { color: #64748b; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; }
.kos-meta dd { margin: 2px 0 0; font-weight: 700; }
.kos-notice { color: #92400e; font-weight: 700; }
""".strip()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="knowledgeos-source-sha256" content="{html_escape(source_sha)}">
  <meta name="knowledgeos-source-path" content="{html_escape(source_rel)}">
  <meta name="knowledgeos-presentation" content="minimal">
  <title>{html_escape(title)}</title>
  <style>{css}</style>
</head>
<body>
  <main>
    {body}
    <footer class="kos-page-evidence">
      <h2>Evidence Metadata</h2>
      <dl class="kos-meta">{meta_html}</dl>
      <p class="kos-notice">{HTML_SOURCE_TRUTH_NOTICE}</p>
    </footer>
  </main>
</body>
</html>
"""


def build_bare_html_document(
    *,
    title: str,
    kind: str,
    body: str,
    source_rel: str,
    source_sha: str,
    run_id: str,
    generated_at: str,
    theme: str,
) -> str:
    metadata = (
        f"kind={html_escape(kind)} | run={html_escape(run_id or 'not run-bound')} | "
        f"source={html_escape(source_rel)} | sha256={html_escape(source_sha)} | "
        f"generated={html_escape(generated_at)} | theme={html_escape(theme)} | presentation=bare"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="knowledgeos-source-sha256" content="{html_escape(source_sha)}">
  <meta name="knowledgeos-source-path" content="{html_escape(source_rel)}">
  <meta name="knowledgeos-presentation" content="bare">
  <title>{html_escape(title)}</title>
  <style>body{{margin:2rem auto;max-width:76ch;padding:0 1rem;line-height:1.6;font-family:serif}}pre{{overflow:auto}}.kos-evidence-footer,.kos-page-evidence{{border-top:1px solid #ccc;margin-top:2rem;padding-top:1rem;font-size:.9rem}}.kos-notice{{font-weight:700}}</style>
</head>
<body>
  {body}
  <footer class="kos-page-evidence">
    <p>{metadata}</p>
    <p class="kos-notice">{HTML_SOURCE_TRUTH_NOTICE}</p>
  </footer>
</body>
</html>
"""


def render_html_sidecar(
    project_root: Path,
    *,
    kind: str,
    source_path: Path,
    output_path: Path,
    run_id: str = "",
    theme: str = HTML_DEFAULT_THEME,
    presentation: str = HTML_DEFAULT_PRESENTATION,
) -> dict[str, Any]:
    if kind not in HTML_REPORT_KINDS:
        raise ValueError(f"unsupported render kind: {kind}")
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    if source_path.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise ValueError("render-html v1 expects a Markdown or text source")
    markdown = read_text(source_path)
    source_sha = content_fingerprint(markdown)
    anchor_prefix = safe_slug(f"{kind}-{source_sha[:12]}")
    body_html, title, sections = markdown_to_html_fragment(markdown, anchor_prefix=anchor_prefix)
    if kind == "receipt" and run_id:
        title = f"KnowledgeOS Receipt {run_id}"
    elif kind == "handoff" and run_id:
        title = f"KnowledgeOS Handoff {run_id}"
    generated_at = datetime.now(timezone.utc).isoformat()
    source_rel = project_relative(project_root, source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fragment_path = output_path.with_suffix(".fragment.html")
    manifest_path = output_path.with_suffix(".manifest.json")
    fragment_html = build_html_fragment(
        kind=kind,
        title=title,
        source_rel=source_rel,
        source_sha=source_sha,
        run_id=run_id,
        body_html=body_html,
        sections=sections,
        generated_at=generated_at,
        presentation=presentation,
    )
    write_text(fragment_path, fragment_html)
    if presentation == "fragment":
        output_rel = ""
    else:
        full_html = build_html_document(
            title=title,
            kind=kind,
            body=fragment_html,
            source_rel=source_rel,
            source_sha=source_sha,
            run_id=run_id,
            generated_at=generated_at,
            theme=theme,
            presentation=presentation,
        )
        write_text(output_path, full_html)
        output_rel = project_relative(project_root, output_path)
    manifest = {
        "schema_version": "knowledgeos.html-report.v1",
        "kind": kind,
        "title": title,
        "theme": theme,
        "presentation": presentation,
        "run_id": run_id,
        "source": source_rel,
        "source_sha256": source_sha,
        "output": output_rel,
        "fragment": project_relative(project_root, fragment_path),
        "sections": sections,
        "generated_at": generated_at,
        "html_source_of_truth": False,
        "html_required_metadata": True,
        "notice": HTML_SOURCE_TRUTH_NOTICE,
    }
    write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {
        "status": "rendered",
        "kind": kind,
        "title": title,
        "output": str(output_path) if presentation != "fragment" else "",
        "fragment": str(fragment_path),
        "manifest": str(manifest_path),
        "source": str(source_path),
        "source_sha256": source_sha,
        "run_id": run_id,
        "presentation": presentation,
        "html_source_of_truth": False,
    }


def decision_events_to_markdown(run_id: str, events: list[dict[str, Any]]) -> str:
    lines = [
        f"# KnowledgeOS Decision Map {run_id}",
        "",
        "This sidecar summarizes public Decision Graph events. It is not hidden chain-of-thought.",
        "",
        "## Main Path",
        "",
    ]
    main_statuses = {"planned", "active", "selected", "executed"}
    main_events = [event for event in events if str(event.get("status", "")) in main_statuses]
    branch_events = [event for event in events if event not in main_events]
    if not main_events:
        lines.append("- No selected or executed decision path recorded.")
    for event in main_events:
        lines.append(
            f"- {event.get('decision_id', '')}: {event.get('title', '')} "
            f"({event.get('kind', '')}, {event.get('status', '')})"
        )
        if event.get("summary"):
            lines.append(f"- Summary: {event.get('summary')}")
        if event.get("reason"):
            lines.append(f"- Reason: {event.get('reason')}")
        if event.get("chosen"):
            lines.append(f"- Chosen: {event.get('chosen')}")
    lines.extend(["", "## Abandoned Deferred And Recovery Branches", ""])
    if not branch_events:
        lines.append("- No abandoned, deferred, superseded, blocked, or rollback branches recorded.")
    for event in branch_events:
        lines.append(
            f"- {event.get('decision_id', '')}: {event.get('title', '')} "
            f"({event.get('kind', '')}, {event.get('status', '')})"
        )
        if event.get("parent_id"):
            lines.append(f"- Parent: {event.get('parent_id')}")
        if event.get("reason"):
            lines.append(f"- Reason: {event.get('reason')}")
        if event.get("evidence"):
            lines.append(f"- Evidence: {event.get('evidence')}")
    lines.extend(["", "## Full Decision Ledger", ""])
    for event in events:
        options = ", ".join(str(item) for item in event.get("options", []) if str(item).strip())
        lines.append(f"- ID: {event.get('decision_id', '')}")
        lines.append(f"- Parent: {event.get('parent_id', '') or 'root'}")
        lines.append(f"- Title: {event.get('title', '')}")
        lines.append(f"- Kind: {event.get('kind', '')}")
        lines.append(f"- Status: {event.get('status', '')}")
        if options:
            lines.append(f"- Options: {options}")
        if event.get("linked_capability_event_id"):
            lines.append(f"- Linked Capability: {event.get('linked_capability_event_id')}")
        if event.get("linked_effect_assertion_id"):
            lines.append(f"- Linked Effect: {event.get('linked_effect_assertion_id')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_decision_map_sidecar(
    project_root: Path,
    *,
    run_id: str,
    output_path: Path,
    theme: str = HTML_DEFAULT_THEME,
    presentation: str = HTML_DEFAULT_PRESENTATION,
) -> dict[str, Any]:
    run_dir = resolve_run_dir(project_root, run_id)
    source_path = decision_events_path(run_dir)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    events = [event for event in load_decision_events(run_dir) if "_invalid_json" not in event]
    source_sha = sha256_file(source_path)
    markdown = decision_events_to_markdown(run_id, events)
    anchor_prefix = safe_slug(f"decision-map-{source_sha[:12]}")
    body_html, title, sections = markdown_to_html_fragment(markdown, anchor_prefix=anchor_prefix)
    generated_at = datetime.now(timezone.utc).isoformat()
    source_rel = project_relative(project_root, source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fragment_path = output_path.with_suffix(".fragment.html")
    manifest_path = output_path.with_suffix(".manifest.json")
    fragment_html = build_html_fragment(
        kind="decision-map",
        title=title,
        source_rel=source_rel,
        source_sha=source_sha,
        run_id=run_id,
        body_html=body_html,
        sections=sections,
        generated_at=generated_at,
        presentation=presentation,
    )
    write_text(fragment_path, fragment_html)
    if presentation == "fragment":
        output_rel = ""
    else:
        full_html = build_html_document(
            title=title,
            kind="decision-map",
            body=fragment_html,
            source_rel=source_rel,
            source_sha=source_sha,
            run_id=run_id,
            generated_at=generated_at,
            theme=theme,
            presentation=presentation,
        )
        write_text(output_path, full_html)
        output_rel = project_relative(project_root, output_path)
    manifest = {
        "schema_version": "knowledgeos.html-report.v1",
        "kind": "decision-map",
        "title": title,
        "theme": theme,
        "presentation": presentation,
        "run_id": run_id,
        "source": source_rel,
        "source_sha256": source_sha,
        "output": output_rel,
        "fragment": project_relative(project_root, fragment_path),
        "sections": sections,
        "decision_count": len(events),
        "generated_at": generated_at,
        "html_source_of_truth": False,
        "html_required_metadata": True,
        "notice": HTML_SOURCE_TRUTH_NOTICE,
    }
    write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {
        "status": "rendered",
        "kind": "decision-map",
        "title": title,
        "output": str(output_path) if presentation != "fragment" else "",
        "fragment": str(fragment_path),
        "manifest": str(manifest_path),
        "source": str(source_path),
        "source_sha256": source_sha,
        "run_id": run_id,
        "decision_count": len(events),
        "presentation": presentation,
        "html_source_of_truth": False,
    }


def mermaid_label(value: str, limit: int = 58) -> str:
    cleaned = " ".join(str(value).split())
    if len(cleaned) > limit:
        cleaned = cleaned[: max(0, limit - 3)].rstrip() + "..."
    return cleaned.replace('"', "'").replace("[", "(").replace("]", ")")


def latest_phase_records_by_phase(run_dir: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in load_phase_records(run_dir):
        if "_invalid_json" in record:
            continue
        phase = str(record.get("phase", ""))
        if phase:
            latest[phase] = record
    return latest


def count_valid_records(records: list[dict[str, Any]], status: str = "") -> int:
    count = 0
    for record in records:
        if "_invalid_json" in record:
            continue
        if status and str(record.get("status", "")) != status:
            continue
        count += 1
    return count


def mission_flow_stage_summary(project_root: Path, task_id: str, run_id: str, sync_status: str = "") -> dict[str, Any]:
    task = find_task(project_root, task_id)
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    run_meta = parse_scalar_values(run_dir / "run.yaml", {"route_status", "status", "task_title", "task_type"})
    phase_latest = latest_phase_records_by_phase(run_dir)
    phase_done = [phase for phase in EXPECTED_PHASE_KEYS if phase_latest.get(phase, {}).get("status") in {"completed", "skipped"}]
    capability_count = count_valid_records(load_capability_events(run_dir))
    effect_count = count_valid_records(load_effect_assertions(run_dir), status="passed")
    decision_count = count_valid_records(load_decision_events(run_dir))
    has_plan = (run_dir / "plan.md").exists() and (run_dir / "context-pack.md").exists()
    eval_ok = eval_has_passed(run_dir / "eval.md")
    postflight_text = read_text(run_dir / "postflight.md") if (run_dir / "postflight.md").exists() else ""
    synced = sync_status == "SYNC_OK" or "[SYNC_OK]" in postflight_text
    task_title = task.get("title") or run_meta.get("task_title") or task_id
    proof_label = f"{effect_count} real check" + ("" if effect_count == 1 else "s")
    tool_label = f"{capability_count} tool note" + ("" if capability_count == 1 else "s")
    decision_label = f"{decision_count} decision" + ("" if decision_count == 1 else "s")
    checkpoint_label = f"{len(phase_done)}/6 checkpoints"
    return {
        "task": task,
        "run_dir": run_dir,
        "title": task_title,
        "complexity": task.get("complexity", "medium"),
        "stages": [
            {
                "id": "A",
                "name": "Goal",
                "kind": "intent",
                "label": f"Goal: {task_title}",
                "detail": "What the user wanted us to finish.",
                "status": "set",
            },
            {
                "id": "B",
                "name": "Health Check",
                "kind": "guard",
                "label": "Health check: OK",
                "detail": "The project control plane was checked before work.",
                "status": "ok",
            },
            {
                "id": "C",
                "name": "Task & Plan",
                "kind": "intent",
                "label": "Task and plan: ready" if has_plan else "Task and plan: missing",
                "detail": "The run has a context pack and a short working plan." if has_plan else "The run is missing plan/context files.",
                "status": "ok" if has_plan else "attention",
            },
            {
                "id": "D",
                "name": "Safe Writes",
                "kind": "guard",
                "label": "Safe writes: routed" if run_meta.get("route_status") == "routed" else "Safe writes: review needed",
                "detail": "Planned file changes stayed inside the task route.",
                "status": "ok" if run_meta.get("route_status") == "routed" else "attention",
            },
            {
                "id": "E",
                "name": "Work Done",
                "kind": "work",
                "label": "Work done: recorded" if "execute" in phase_done else "Work done: not recorded",
                "detail": "Implementation or analysis steps were recorded as public checkpoints.",
                "status": "ok" if "execute" in phase_done else "attention",
            },
            {
                "id": "F",
                "name": "Tools Used",
                "kind": "work",
                "label": f"Tools used: {tool_label}",
                "detail": "Important shell, script, subagent, MCP, or skill use was made visible.",
                "status": "ok" if capability_count else "quiet",
            },
            {
                "id": "G",
                "name": "Proof",
                "kind": "proof",
                "label": f"Proof: {proof_label}",
                "detail": "Real artifacts were checked after the work landed.",
                "status": "ok" if effect_count else "quiet",
            },
            {
                "id": "H",
                "name": "Decisions",
                "kind": "proof",
                "label": f"Decisions: {decision_label}",
                "detail": "Route changes or important choices were summarized for humans.",
                "status": "ok" if decision_count else "quiet",
            },
            {
                "id": "I",
                "name": "Finish",
                "kind": "done",
                "label": "Finish: synced" if synced else ("Finish: checked" if eval_ok else "Finish: pending"),
                "detail": f"Review status: {'passed' if eval_ok else 'pending'}; {checkpoint_label}.",
                "status": "ok" if synced or eval_ok else "attention",
            },
        ],
        "counts": {
            "capability_events": capability_count,
            "effect_assertions": effect_count,
            "decision_events": decision_count,
            "phases_recorded": len(phase_done),
        },
        "synced": synced,
        "eval_passed": eval_ok,
    }


def build_mission_flow_mermaid(summary: dict[str, Any]) -> str:
    stages = summary["stages"]
    lines = ["flowchart LR"]
    for stage in stages:
        lines.append(f'  {stage["id"]}["{mermaid_label(stage["label"])}"]')
    for left, right in zip(stages, stages[1:]):
        lines.append(f'  {left["id"]} --> {right["id"]}')
    lines.extend(
        [
            "",
            "  classDef intent fill:#E8F3FF,stroke:#2B6CB0,color:#102A43;",
            "  classDef guard fill:#FFF4D6,stroke:#B7791F,color:#3D2B00;",
            "  classDef work fill:#E9FBEF,stroke:#2F855A,color:#123524;",
            "  classDef proof fill:#F3E8FF,stroke:#6B46C1,color:#2D174D;",
            "  classDef done fill:#DCFCE7,stroke:#15803D,color:#052E16;",
        ]
    )
    by_kind: dict[str, list[str]] = {"intent": [], "guard": [], "work": [], "proof": [], "done": []}
    for stage in stages:
        by_kind.setdefault(stage["kind"], []).append(stage["id"])
    for kind, ids in by_kind.items():
        if ids:
            lines.append(f"  class {','.join(ids)} {kind};")
    return "\n".join(lines)


def build_mission_flow_markdown(project_root: Path, task_id: str, run_id: str, sync_status: str = "") -> dict[str, Any]:
    summary = mission_flow_stage_summary(project_root, task_id, run_id, sync_status=sync_status)
    mermaid = build_mission_flow_mermaid(summary)
    lines = [
        f"# Mission Flow {run_id}",
        "",
        "FLOW_OK",
        "",
        "A human-readable map of how this task moved from request to finish.",
        "",
        "## Flow",
        "",
        "```mermaid",
        mermaid,
        "```",
        "",
        "## Plain Summary",
        "",
    ]
    for stage in summary["stages"]:
        lines.append(f"- {stage['name']}: {stage['label']}. {stage['detail']}")
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- Tools made visible: {summary['counts']['capability_events']}",
            f"- Artifact checks: {summary['counts']['effect_assertions']}",
            f"- Decision notes: {summary['counts']['decision_events']}",
            f"- Checkpoints recorded: {summary['counts']['phases_recorded']}/6",
            "",
            "HTML is presentation, not source of truth.",
        ]
    )
    return {
        "status": "generated",
        "flow_marker": "FLOW_OK",
        "marker": f"FLOW_OK run={run_id} stages={len(summary['stages'])} synced={'yes' if summary['synced'] else 'no'}",
        "task_id": task_id,
        "run_id": run_id,
        "complexity": summary["complexity"],
        "mermaid": mermaid,
        "markdown": "\n".join(lines).rstrip() + "\n",
        "counts": summary["counts"],
        "stages": summary["stages"],
    }


def write_mission_flow_markdown(project_root: Path, task_id: str, run_id: str, sync_status: str = "") -> dict[str, Any]:
    result = build_mission_flow_markdown(project_root, task_id, run_id, sync_status=sync_status)
    run_dir = ensure_run_belongs_to_task(project_root, task_id, run_id)
    source_path = run_dir / "mission-flow.md"
    write_text(source_path, result["markdown"])
    result["source"] = str(source_path)
    return result


def mission_flow_cards_html(stages: list[dict[str, Any]]) -> str:
    cards = []
    for stage in stages:
        cards.append(
            '<section class="kos-flow-card kos-flow-{kind}">'
            "<h3>{name}</h3>"
            "<p><strong>{label}</strong></p>"
            "<p>{detail}</p>"
            "</section>".format(
                kind=html_escape(stage["kind"]),
                name=html_escape(stage["name"]),
                label=html_escape(stage["label"]),
                detail=html_escape(stage["detail"]),
            )
        )
    return '<div class="kos-flow">' + "\n".join(cards) + "</div>"


def render_mission_flow_sidecar(
    project_root: Path,
    *,
    task_id: str,
    run_id: str,
    output_path: Path,
    theme: str = HTML_DEFAULT_THEME,
    presentation: str = HTML_DEFAULT_PRESENTATION,
) -> dict[str, Any]:
    flow = write_mission_flow_markdown(project_root, task_id, run_id)
    source_path = Path(flow["source"])
    source_sha = sha256_file(source_path)
    generated_at = datetime.now(timezone.utc).isoformat()
    source_rel = project_relative(project_root, source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fragment_path = output_path.with_suffix(".fragment.html")
    manifest_path = output_path.with_suffix(".manifest.json")
    body_html = "\n".join(
        [
            f"<h1>Mission Flow {html_escape(run_id)}</h1>",
            "<p>A friendly map of how the task moved from request to finish.</p>",
            mission_flow_cards_html(flow["stages"]),
            "<details><summary>Mermaid source</summary>",
            f"<pre><code>{html_escape(flow['mermaid'])}</code></pre>",
            "</details>",
        ]
    )
    sections = [{"id": "mission-flow", "title": "Mission Flow", "level": 1}]
    fragment_html = build_html_fragment(
        kind="mission-flow",
        title=f"Mission Flow {run_id}",
        source_rel=source_rel,
        source_sha=source_sha,
        run_id=run_id,
        body_html=body_html,
        sections=sections,
        generated_at=generated_at,
        presentation=presentation,
    )
    write_text(fragment_path, fragment_html)
    if presentation == "fragment":
        output_rel = ""
    else:
        full_html = build_html_document(
            title=f"Mission Flow {run_id}",
            kind="mission-flow",
            body=fragment_html,
            source_rel=source_rel,
            source_sha=source_sha,
            run_id=run_id,
            generated_at=generated_at,
            theme=theme,
            presentation=presentation,
        )
        write_text(output_path, full_html)
        output_rel = project_relative(project_root, output_path)
    manifest = {
        "schema_version": "knowledgeos.html-report.v1",
        "kind": "mission-flow",
        "title": f"Mission Flow {run_id}",
        "theme": theme,
        "presentation": presentation,
        "run_id": run_id,
        "task_id": task_id,
        "source": source_rel,
        "source_sha256": source_sha,
        "output": output_rel,
        "fragment": project_relative(project_root, fragment_path),
        "sections": sections,
        "generated_at": generated_at,
        "flow_marker": "FLOW_OK",
        "html_source_of_truth": False,
        "html_required_metadata": True,
        "notice": HTML_SOURCE_TRUTH_NOTICE,
    }
    write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {
        "status": "rendered",
        "kind": "mission-flow",
        "title": f"Mission Flow {run_id}",
        "output": str(output_path) if presentation != "fragment" else "",
        "fragment": str(fragment_path),
        "manifest": str(manifest_path),
        "source": str(source_path),
        "source_sha256": source_sha,
        "run_id": run_id,
        "task_id": task_id,
        "flow_marker": "FLOW_OK",
        "presentation": presentation,
        "html_source_of_truth": False,
    }


def resolve_manifest_reference(project_root: Path, manifest_dir: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    project_candidate = (project_root / candidate).resolve()
    if project_candidate.exists():
        return project_candidate
    return (manifest_dir / candidate).resolve()


def compose_html_reports(
    project_root: Path,
    *,
    compose_manifest_path: Path,
    output_path: Path,
    theme: str = HTML_DEFAULT_THEME,
    presentation: str = HTML_DEFAULT_PRESENTATION,
) -> dict[str, Any]:
    if presentation == "fragment":
        raise ValueError("render-html --compose does not support fragment presentation")
    if not compose_manifest_path.exists():
        raise FileNotFoundError(compose_manifest_path)
    compose_manifest = json.loads(read_text(compose_manifest_path))
    if "reports" in compose_manifest:
        report_refs = compose_manifest.get("reports") or []
    elif "fragment" in compose_manifest:
        report_refs = [project_relative(project_root, compose_manifest_path)]
    else:
        raise ValueError("compose manifest must contain reports or fragment")
    if not report_refs:
        raise ValueError("compose manifest reports list is empty")
    generated_at = datetime.now(timezone.utc).isoformat()
    fragments: list[str] = []
    child_manifests: list[dict[str, Any]] = []
    for ref in report_refs:
        child_path = resolve_manifest_reference(project_root, compose_manifest_path.parent, str(ref))
        child = json.loads(read_text(child_path))
        if "fragment" not in child:
            raise ValueError(f"child manifest lacks fragment: {child_path}")
        fragment_path = resolve_manifest_reference(project_root, child_path.parent, str(child["fragment"]))
        if not fragment_path.exists():
            raise FileNotFoundError(fragment_path)
        fragments.append(read_text(fragment_path))
        child_manifests.append(
            {
                "manifest": project_relative(project_root, child_path),
                "fragment": project_relative(project_root, fragment_path),
                "source": child.get("source", ""),
                "source_sha256": child.get("source_sha256", ""),
                "title": child.get("title", ""),
                "kind": child.get("kind", ""),
            }
        )
    compose_source_sha = sha256_file(compose_manifest_path)
    title = str(compose_manifest.get("title") or "KnowledgeOS Combined Report")
    body = "\n".join(fragments)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    full_html = build_html_document(
        title=title,
        kind="composed-report",
        body=body,
        source_rel=project_relative(project_root, compose_manifest_path),
        source_sha=compose_source_sha,
        run_id=str(compose_manifest.get("run_id") or ""),
        generated_at=generated_at,
        theme=str(compose_manifest.get("theme") or theme),
        presentation=presentation,
    )
    write_text(output_path, full_html)
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest = {
        "schema_version": "knowledgeos.html-composition.v1",
        "title": title,
        "theme": str(compose_manifest.get("theme") or theme),
        "presentation": presentation,
        "source": project_relative(project_root, compose_manifest_path),
        "source_sha256": compose_source_sha,
        "output": project_relative(project_root, output_path),
        "report_count": len(child_manifests),
        "reports": child_manifests,
        "generated_at": generated_at,
        "html_source_of_truth": False,
        "html_required_metadata": True,
        "notice": HTML_SOURCE_TRUTH_NOTICE,
    }
    write_text(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {
        "status": "composed",
        "output": str(output_path),
        "manifest": str(manifest_path),
        "report_count": len(child_manifests),
        "source": str(compose_manifest_path),
        "source_sha256": compose_source_sha,
        "presentation": presentation,
        "html_source_of_truth": False,
    }


def emit(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    if isinstance(data, list):
        for item in data:
            if isinstance(item, CheckResult):
                print(f"[{'OK' if item.ok else 'FAIL'}] {item.label}: {item.detail}")
            else:
                print(item)
    elif isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {value}")
    else:
        print(data)


def summarize_results(results: list[CheckResult]) -> dict[str, Any]:
    failed = [item for item in results if not item.ok]
    failed_by_label: dict[str, int] = {}
    for item in failed:
        failed_by_label[item.label] = failed_by_label.get(item.label, 0) + 1
    return {
        "status": "ok" if not failed else "fail",
        "checks": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "failed_by_label": failed_by_label,
        "failed_checks": [item.as_dict() for item in failed[:12]],
        "truncated_failed_checks": max(0, len(failed) - 12),
    }


def emit_summary(summary: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return
    print(f"status: {summary['status']}")
    print(f"checks: {summary['checks']}")
    print(f"passed: {summary['passed']}")
    print(f"failed: {summary['failed']}")
    if summary["failed"]:
        print("failed_by_label:")
        for label, count in sorted(summary["failed_by_label"].items()):
            print(f"- {label}: {count}")
        print("failed_checks:")
        for item in summary["failed_checks"]:
            print(f"- {item['label']}: {item['detail']}")
        if summary["truncated_failed_checks"]:
            print(f"- ... {summary['truncated_failed_checks']} more")
    else:
        print("failed_by_label: none")


def cmd_doctor(args: argparse.Namespace) -> int:
    root = resolve_root(getattr(args, "root", None))
    results: list[CheckResult] = []
    if not getattr(args, "project_only", False):
        results.extend(check_required_files(root, REQUIRED_PUBLIC_FILES, "public_file"))
        results.extend(scan_public_content(root))
    if args.project_root:
        project_root = Path(args.project_root).expanduser().resolve()
        results.extend(
            deep_validate_project(
                project_root,
                allow_placeholders=getattr(args, "allow_placeholders", False) or getattr(args, "template", False),
                skip_external=getattr(args, "skip_external_checks", False) or getattr(args, "template", False),
            )
        )
    if getattr(args, "summary", False):
        emit_summary(summarize_results(results), args.json)
    else:
        emit([r.as_dict() for r in results] if args.json else results, args.json)
    return 0 if all(r.ok for r in results) else 1


def cmd_harness_audit(args: argparse.Namespace) -> int:
    root = resolve_root(getattr(args, "root", None))
    governance_root = Path(args.governance_root).expanduser().resolve() if args.governance_root else default_governance_root(root)
    capability_root = Path(args.capability_root).expanduser().resolve() if args.capability_root else default_capability_root(root)
    search_roots = [Path(item).expanduser() for item in getattr(args, "search_root", [])]
    target_projects = [Path(item).expanduser().resolve() for item in getattr(args, "target_project", [])]
    if not target_projects and not search_roots:
        search_roots = [Path.home() / "Desktop", root]
    if getattr(args, "include_registry", False):
        registry = governance_root / "projects" / "registry.yaml"
        target_projects.extend(path.expanduser().resolve() for path in parse_registry_project_paths(registry) if path.exists())
    discovered = discover_agent_os_projects(search_roots, include_templates=getattr(args, "include_templates", False))
    projects = sorted(set(target_projects + discovered), key=lambda item: str(item))

    backup_name = f"harness-audit-{now_stamp()}"
    kernel_actions = ensure_kernel_hooks(root, governance_root, apply=args.apply)
    kernel_skeleton_actions = ensure_kernel_skeleton(root, governance_root, apply=args.apply)
    capability_actions = ensure_capability_layer(root, capability_root, apply=args.apply)
    reports = [
        audit_project_mount(
            project,
            root,
            governance_root,
            capability_root,
            apply=args.apply,
            backup_name=backup_name,
        )
        for project in projects
        if project.exists()
    ]
    issues = [report for report in reports if report.get("status") not in {"ok", "unmanaged"}]
    payload = {
        "status": "ok" if not issues else "attention",
        "mode": "apply" if args.apply else "dry_run",
        "knowledgeos_root": str(root),
        "governance_root": str(governance_root),
        "capability_root": str(capability_root),
        "kernel_hooks": kernel_actions,
        "kernel_skeleton": kernel_skeleton_actions,
        "capability_layer": capability_actions,
        "project_count": len(reports),
        "issue_count": len(issues),
        "projects": reports,
    }
    emit(payload, args.json)
    return 0 if payload["status"] == "ok" else 1


def load_workflow_profiles(project_root: Path) -> dict[str, dict[str, Any]]:
    router_path = project_root / ".agent-os" / "workflows" / "router.yaml"
    if not router_path.exists():
        raise FileNotFoundError(f"missing workflow router: {router_path}")
    return parse_workflow_profiles(router_path)


def build_task_route(project_root: Path, task_id: str | None, task_type: str | None) -> dict[str, Any]:
    task: dict[str, str] | None = None
    if task_id:
        task = find_task(project_root, task_id)
        task_type = task.get("type")
    if not task_type:
        raise ValueError("route-task requires --task-id or --task-type")

    profiles = load_workflow_profiles(project_root)
    profile = profiles.get(task_type)
    if not profile:
        return {
            "status": "human_triage_required",
            "reason": f"no workflow route profile for task type {task_type!r}",
            "task_id": task_id,
            "task_type": task_type,
            "recommended_action": "add a route profile under .agent-os/workflows/router.yaml before mutation",
        }

    return {
        "status": "routed",
        "task_id": task_id,
        "task_title": task.get("title", "") if task else "",
        "task_type": task_type,
        "route_order": profile.get("route_order", []),
        "eval_profile": profile.get("eval_profile", ""),
        "human_gate": profile.get("human_gate", ""),
        "allow_external_controlled": profile.get("allow_external_controlled", ""),
        "allowed_outputs": profile.get("allowed_outputs", []),
        "notes": profile.get("notes", []),
    }


def cmd_init_project(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    template = root / "templates" / "project-control-plane"
    if not template.exists():
        print(f"missing project template: {template}", file=sys.stderr)
        return 1
    project_root = Path(args.project_root).expanduser().resolve()
    capability_root = args.capability_root or args.implementation_root
    replacements = {
        "CHANGE_ME_GLOBAL_AGENT_FABRIC_ROOT": args.global_root or "CHANGE_ME_GLOBAL_AGENT_FABRIC_ROOT",
        "CHANGE_ME_KNOWLEDGEOS_CAPABILITY_ROOT": capability_root or "CHANGE_ME_KNOWLEDGEOS_CAPABILITY_ROOT",
        "CHANGE_ME_AGENT_FABRIC_IMPLEMENTATION_ROOT": capability_root or "CHANGE_ME_AGENT_FABRIC_IMPLEMENTATION_ROOT",
        "CHANGE_ME_KNOWLEDGEOS_BIN": str(resolve_root(args.root) / "bin" / "knowledgeos"),
        "CHANGE_ME_PROJECT_NAME": args.name or project_root.name,
        "CHANGE_ME_PROJECT_ROOT": str(project_root),
        "CHANGE_ME_WORKSPACE_ID": safe_slug(args.name or project_root.name).lower(),
        "CHANGE_ME_DATE": datetime.now().strftime("%Y-%m-%d"),
    }
    actions = copy_template_tree(template, project_root, replacements, dry_run=args.dry_run, force=args.force)
    emit(actions, args.json)
    return 0


def cmd_init_os(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    governance_template = root / "templates" / "governance-core"
    capability_template = root / "templates" / "capability-layer"
    if not governance_template.exists():
        print(f"missing governance core template: {governance_template}", file=sys.stderr)
        return 1
    if not capability_template.exists():
        print(f"missing capability layer template: {capability_template}", file=sys.stderr)
        return 1

    os_root = Path(args.os_root).expanduser().resolve()
    global_root = Path(args.global_root).expanduser().resolve() if args.global_root else os_root / "global-agent-fabric"
    capability_root = Path(args.capability_root).expanduser().resolve() if args.capability_root else os_root / "capability-layer"
    replacements = {
        "CHANGE_ME_GLOBAL_AGENT_FABRIC_ROOT": str(global_root),
        "CHANGE_ME_KNOWLEDGEOS_CAPABILITY_ROOT": str(capability_root),
    }
    actions: list[dict[str, str]] = []
    actions.extend(copy_template_tree(governance_template, global_root, replacements, dry_run=args.dry_run, force=args.force))
    actions.extend(copy_template_tree(capability_template, capability_root, replacements, dry_run=args.dry_run, force=args.force))
    if not args.dry_run:
        make_kernel_hooks_executable(global_root)
    actions.append({"action": "ready", "global_root": str(global_root), "capability_root": str(capability_root)})
    emit(actions, args.json)
    return 0


def cmd_check_write(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    result = classify_write(project_root, args.path)
    emit(result, args.json)
    decision = result["decision"]
    if decision == "allow":
        return 0
    if decision == "unclassified" and not args.strict:
        return 0
    return 2


def cmd_check_route_write(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = classify_route_write(project_root, args.task_id, args.path)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0 if result.get("decision") == "allow" else 2


def cmd_run_task(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = create_run_envelope(project_root, args.task_id, args.summary, dry_run=args.dry_run, force=args.force)
    except (FileNotFoundError, KeyError, FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_create_task(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = create_task(
            project_root,
            title=args.title,
            task_type=args.type,
            status=args.status,
            complexity=args.complexity,
            risk=args.risk,
            outputs=args.output,
            acceptance=args.acceptance,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_create_spec(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = create_spec(
            project_root,
            title=args.title,
            intent=args.intent or "",
            acceptance=args.acceptance or [],
            non_goal=args.non_goal or [],
            set_active=not args.no_activate,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_align_spec(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = align_spec(project_root, task_id=args.task_id, spec_id=args.spec_id, note=args.note or "")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0 if result.get("status") == "aligned" else 2


def cmd_reopen_task(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = reopen_task(
            project_root,
            args.task_id,
            status=args.status,
            reason=args.reason,
            archive_outputs=args.archive_outputs,
            purge_outputs=args.purge_outputs,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_reset_project(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = reset_project(
            project_root,
            mode=args.mode,
            purge=args.purge,
            reset_tasks=not args.keep_task_status,
            include_agents_md=args.include_agents_md,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_migrate_legacy_project(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = migrate_legacy_project(project_root, write_plan=args.write_plan, apply=args.apply, dry_run=args.dry_run)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(render_migration_plan(project_root, result["plan"]))
        for action in result["actions"]:
            print(action)
    return 0


def cmd_archive_legacy_project(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = archive_legacy_project(
            project_root,
            write_plan=args.write_plan,
            apply=args.apply,
            dry_run=args.dry_run,
            includes=args.include,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(render_archive_plan(project_root, result["plan"]))
        for action in result["actions"]:
            print(action)
    return 0


def cmd_eval_task(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = write_task_eval(project_root, args.task_id, args.run_id, notes=args.notes)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0 if result.get("status") == "passed" else 2


def cmd_phase_task(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = record_task_phase(
            project_root,
            args.task_id,
            args.run_id,
            phase=args.phase,
            status=args.status,
            note=args.note,
            evidence=args.evidence,
            skip_reason=args.skip_reason,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        print(f"ledger: {result['ledger']}")
    return 0


def cmd_capability_event(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = record_capability_event(
            project_root,
            args.task_id,
            args.run_id,
            kind=args.kind,
            capability_id=args.id,
            purpose=args.purpose,
            status=args.status,
            evidence=args.evidence,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        print(f"ledger: {result['ledger']}")
    return 0


def cmd_trace_step(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = record_trace_step(
            project_root,
            args.task_id,
            args.run_id,
            step=args.step,
            status=args.status,
            note=args.note,
            evidence=args.evidence,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        print(f"ledger: {result['ledger']}")
    return 0


def cmd_decision_event(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = record_decision_event(
            project_root,
            args.task_id,
            args.run_id,
            kind=args.kind,
            status=args.status,
            title=args.title,
            summary=args.summary,
            reason=args.reason,
            evidence=args.evidence,
            parent_id=args.parent_id or "",
            options=args.option or [],
            chosen=args.chosen or "",
            linked_step=args.linked_step or "",
            linked_capability_event_id=args.linked_capability_event_id or "",
            linked_effect_assertion_id=args.linked_effect_assertion_id or "",
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        print(f"ledger: {result['ledger']}")
    return 0


def cmd_decision_query(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = query_decision_events(
            project_root,
            run_id=args.run_id,
            task_id=args.task_id or "",
            kind=args.kind or "",
            status=args.status or "",
            parent_id=args.parent_id or "",
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_artifact_assert(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = run_artifact_assertion(
            project_root,
            args.task_id,
            args.run_id,
            kind=args.kind,
            target_path=args.path,
            expect=args.expect or "",
            before_sha=args.before_sha or "",
            json_key=args.json_key or "",
            capability_event_id=args.capability_event_id or "",
        )
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        print(f"ledger: {result['ledger']}")
    return 0


def cmd_context_pack(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = write_context_pack(project_root, args.task_id, args.run_id, summary=args.summary or "")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_plan_task(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = write_task_plan(project_root, args.task_id, args.run_id, summary=args.summary or "")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_verify_context(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = verify_context_contract(project_root, args.task_id, args.run_id)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0 if result.get("status") == "passed" else 2


def cmd_verify_lifecycle(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = verify_lifecycle(project_root, args.task_id, args.run_id)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0 if result.get("status") == "passed" else 2


def cmd_verify_effects(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = verify_effects(project_root, args.task_id, args.run_id)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        print(f"ledger: {result['ledger']}")
        if result.get("warnings"):
            print(f"warnings: {len(result['warnings'])}")
        if result.get("errors"):
            print(f"errors: {len(result['errors'])}")
    return 2 if result.get("status") == "failed" else 0


def cmd_verify_decisions(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = verify_decisions(project_root, args.task_id, args.run_id)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        print(f"ledger: {result['ledger']}")
        if result.get("warnings"):
            print(f"warnings: {len(result['warnings'])}")
        if result.get("errors"):
            print(f"errors: {len(result['errors'])}")
    return 2 if result.get("status") == "failed" else 0


def cmd_complete_task(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = complete_task(
            project_root,
            args.task_id,
            args.run_id,
            args.summary,
            allow_missing_eval=args.allow_missing_eval,
            allow_manual_eval=args.allow_manual_eval,
            allow_missing_outputs=args.allow_missing_outputs,
            allow_pending_postflight=args.allow_pending_postflight or "",
            override_reason=args.override_reason or "",
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_route_task(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = build_task_route(project_root, args.task_id, args.task_type)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0 if result.get("status") == "routed" or args.allow_unrouted else 2


def cmd_tool_registry(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = summarize_tool_registry(project_root, check_paths=args.check_paths)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(f"ok: {result['ok']}")
        for kind, count in sorted(result["counts"].items()):
            print(f"{kind}: {count}")
        failed = [item for item in result["checks"] if not item["ok"]]
        if failed:
            print("failed_checks:")
            for item in failed:
                print(f"- {item['label']}: {item['detail']}")
        else:
            print("checks: all passed")
    return 0 if result.get("ok") else 1


def cmd_dispatch_task(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = build_dispatch_plan(project_root, args.task_id)
        if args.run_id and result.get("status") == "dispatch_ready":
            result["dispatch_event"] = record_dispatch_event(project_root, args.task_id, args.run_id, result)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        if result.get("dispatch_marker"):
            summary = result.get("dispatch_summary", {})
            print(result.get("marker", ""))
            print(f"planned_agents: {summary.get('planned_agents', 0)}")
            print(f"planned_capabilities: {summary.get('planned_capabilities', 0)}")
            if summary.get("planned_agent_ids"):
                print("planned_agent_ids: " + ", ".join(summary.get("planned_agent_ids", [])))
        emit(result, False)
    return 0 if result.get("status") == "dispatch_ready" or args.allow_unrouted else 2


def cmd_dispatch_report(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = build_dispatch_report(project_root, args.task_id, args.run_id)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        print("Full Capability Dispatch Report")
        print(f"agents: {result['agent_count']}")
        print(f"skipped_agents: {result.get('skipped_agent_count', 0)}")
        print(f"runtime_gaps: {result.get('runtime_gap_count', 0)}")
        print(f"capabilities: {result['capability_count']}")
        print(f"skipped: {result.get('skipped_count', 0)}")
        print("by_kind:")
        for kind, count in sorted(result.get("counts_by_kind", {}).items()):
            skipped = result.get("skipped_by_kind", {}).get(kind, 0)
            print(f"- {kind}: used={count}, skipped={skipped}")
        if result.get("events"):
            print("used_capabilities:")
            for event in result["events"]:
                print(f"- {event['kind']}: {event['id']} ({event['status']}) - {event['purpose']}")
        if result.get("skipped"):
            print("skipped_or_not_needed:")
            for event in result["skipped"]:
                print(f"- {event['kind']}: {event['id']} ({event['status']}) - {event['purpose']}")
        if result.get("runtime_gaps"):
            print("runtime_gap_details:")
            for event in result["runtime_gaps"]:
                print(f"- {event['kind']}: {event['id']} ({event['status']}) - {event['evidence']}")
        if result.get("gaps"):
            print("gaps:")
            for gap in result["gaps"]:
                print(f"- {gap}")
        print(f"report: {result['report']}")
    return 0


def cmd_render_html(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        presentation = resolve_html_presentation(project_root, args.presentation)
        if args.compose:
            if not args.output:
                raise ValueError("render-html --compose requires --output")
            result = compose_html_reports(
                project_root,
                compose_manifest_path=resolve_project_artifact(project_root, args.compose),
                output_path=resolve_project_artifact(project_root, args.output),
                theme=args.theme,
                presentation=presentation,
            )
            emit(result, args.json)
            return 0

        if not args.kind:
            raise ValueError("render-html requires --kind unless --compose is used")
        if args.kind in {"receipt", "handoff"}:
            if not args.run_id:
                raise ValueError(f"render-html --kind {args.kind} requires --run-id")
            run_dir = resolve_run_dir(project_root, args.run_id)
            source_path = run_dir / f"{args.kind}.md"
            output_path = resolve_project_artifact(project_root, args.output) if args.output else run_dir / f"{args.kind}.html"
            result = render_html_sidecar(
                project_root,
                kind=args.kind,
                source_path=source_path,
                output_path=output_path,
                run_id=args.run_id,
                theme=args.theme,
                presentation=presentation,
            )
        elif args.kind == "decision-map":
            if not args.run_id:
                raise ValueError("render-html --kind decision-map requires --run-id")
            run_dir = resolve_run_dir(project_root, args.run_id)
            output_path = resolve_project_artifact(project_root, args.output) if args.output else run_dir / "decision-map.html"
            result = render_decision_map_sidecar(
                project_root,
                run_id=args.run_id,
                output_path=output_path,
                theme=args.theme,
                presentation=presentation,
            )
        elif args.kind == "mission-flow":
            if not args.run_id:
                raise ValueError("render-html --kind mission-flow requires --run-id")
            run_dir = resolve_run_dir(project_root, args.run_id)
            task_id = args.task_id or parse_scalar_values(run_dir / "run.yaml", {"task_id"}).get("task_id", "")
            if not task_id:
                raise ValueError("could not resolve task id for mission-flow")
            output_path = resolve_project_artifact(project_root, args.output) if args.output else run_dir / "mission-flow.html"
            result = render_mission_flow_sidecar(
                project_root,
                task_id=task_id,
                run_id=args.run_id,
                output_path=output_path,
                theme=args.theme,
                presentation=presentation,
            )
        elif args.kind == "rich-report":
            if not args.input:
                raise ValueError("render-html --kind rich-report requires --input")
            source_path = resolve_project_artifact(project_root, args.input)
            output_path = resolve_project_artifact(project_root, args.output) if args.output else source_path.with_suffix(".html")
            result = render_html_sidecar(
                project_root,
                kind=args.kind,
                source_path=source_path,
                output_path=output_path,
                theme=args.theme,
                presentation=presentation,
            )
        else:
            raise ValueError(f"unsupported render kind: {args.kind}")
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0


def cmd_flow_summary(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        run_dir = resolve_run_dir(project_root, args.run_id)
        task_id = args.task_id or parse_scalar_values(run_dir / "run.yaml", {"task_id"}).get("task_id", "")
        if not task_id:
            raise ValueError("could not resolve task id for flow-summary")
        result = write_mission_flow_markdown(project_root, task_id, args.run_id)
        append_command_event(
            run_dir,
            "flow-summary",
            task_id,
            args.run_id,
            status="generated",
            source=project_relative(project_root, Path(result["source"])),
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        if args.format == "markdown":
            print(result["markdown"])
        else:
            print("```mermaid")
            print(result["mermaid"])
            print("```")
            print(f"source: {result['source']}")
    return 0


def cmd_thread_plan(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        if args.thread_action == "start":
            result = start_thread_plan(project_root, title=args.title, spec_id=args.spec_id or "")
        elif args.thread_action == "current":
            current = load_current_thread(project_root)
            result = {
                "status": "ok",
                "thread_plan_marker": THREAD_PLAN_MARKER,
                "marker": f"{THREAD_PLAN_MARKER} action=current thread={current['thread_id']}",
                "current": current,
            }
        elif args.thread_action == "append":
            result = append_thread_plan_event(
                project_root,
                thread_id=args.thread_id,
                kind=args.kind,
                text=args.text,
                linked_spec_id=args.spec_id or "",
                linked_task_id=args.task_id or "",
                linked_run_id=args.run_id or "",
                parent_event_id=args.parent_event_id or "",
            )
        elif args.thread_action == "link-run":
            ensure_run_belongs_to_task(project_root, args.task_id, args.run_id)
            text = args.text or f"已关联执行记录：任务 {args.task_id} / 运行 {args.run_id}。"
            result = append_thread_plan_event(
                project_root,
                thread_id=args.thread_id,
                kind="progress",
                text=text,
                linked_task_id=args.task_id,
                linked_run_id=args.run_id,
                event_type="thread-plan link-run",
            )
            result["status"] = "linked"
            result["marker"] = f"{THREAD_PLAN_MARKER} action=link-run thread={args.thread_id} run={args.run_id}"
        elif args.thread_action == "render":
            if args.format == "markdown":
                result = render_thread_plan_markdown(project_root, args.thread_id)
            elif args.format == "html":
                result = render_thread_plan_html(project_root, args.thread_id)
            elif args.format == "mermaid":
                mermaid = render_thread_plan_mermaid(project_root, args.thread_id)
                result = {
                    "status": "rendered",
                    "thread_plan_marker": THREAD_PLAN_MARKER,
                    "marker": f"{THREAD_PLAN_MARKER} action=render thread={args.thread_id} format=mermaid",
                    "thread_id": args.thread_id,
                    "format": "mermaid",
                    "mermaid": mermaid,
                }
            else:
                raise ValueError(f"unsupported thread-plan render format: {args.format}")
            append_thread_command_event(project_root, args.thread_id, "thread-plan render", format=args.format)
        else:
            raise ValueError(f"unsupported thread-plan action: {args.thread_action}")
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result.get("marker", f"{THREAD_PLAN_MARKER} action={args.thread_action}"))
        if args.thread_action == "current":
            current = result.get("current", {})
            print(f"thread_id: {current.get('thread_id', '')}")
            print(f"title: {current.get('title', '')}")
            print(f"spec_id: {current.get('spec_id', '')}")
        elif args.thread_action == "render" and args.format == "mermaid":
            print("```mermaid")
            print(result["mermaid"])
            print("```")
        elif result.get("output"):
            print(f"output: {result['output']}")
        elif result.get("ledger"):
            print(f"ledger: {result['ledger']}")
    return 0


def cmd_receipt(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    receipt_dir = project_root / ".agent-os" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_id = args.receipt_id or f"RECEIPT-{now_stamp()}"
    text = f"# Receipt\n\nReceipt: {receipt_id}\n\nStatus: {args.status}\n\nSummary: {args.summary}\n"
    target = receipt_dir / f"{safe_slug(receipt_id)}.md"
    write_text(target, text)
    write_text(receipt_dir / "latest.md", text)
    emit({"receipt_id": receipt_id, "path": str(target), "latest": str(receipt_dir / "latest.md")}, args.json)
    return 0


def cmd_agent_guide(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    missing = [path for path in REQUIRED_AGENT_GUIDE_FILES if not (project_root / path).exists()]
    if missing:
        print(f"cannot build guide; missing required files: {', '.join(missing)}", file=sys.stderr)
        return 1
    guide = build_agent_guide(project_root)
    if args.output:
        target = Path(args.output).expanduser().resolve()
        write_text(target, guide)
        emit({"path": str(target)}, args.json)
    else:
        print(guide)
    return 0


def cmd_startup_prompt(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    missing = [path for path in REQUIRED_AGENT_GUIDE_FILES if not (project_root / path).exists()]
    if missing:
        print(f"cannot build startup prompt; missing required files: {', '.join(missing)}", file=sys.stderr)
        return 1
    prompt = build_startup_prompt(project_root)
    if args.output:
        target = Path(args.output).expanduser().resolve()
        write_text(target, prompt)
        emit({"path": str(target)}, args.json)
    else:
        print(prompt)
    return 0


def cmd_ask_sandbox(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    prompt = args.prompt if args.prompt is not None else sys.stdin.read()
    if not prompt.strip():
        print("ask-sandbox requires --prompt or stdin content", file=sys.stderr)
        return 1
    result = build_ask_sandbox_response(project_root, prompt, runtime=args.runtime, show_paths=args.show_paths)
    if args.json:
        emit(result, True)
    else:
        print(f"status: {result['status']}")
        print(f"mode: {result['mode']}")
        print(f"runtime: {result['runtime']}")
        print(f"executed: {str(result['executed']).lower()}")
        print(f"project_mutation: {str(result['project_mutation']).lower()}")
        print(f"recommended_next_step: {result['recommended_next_step']}")
        print(f"response: {result['response']}")
    return 0


def cmd_runtime_adapters(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    result = build_runtime_adapters_state(project_root, show_paths=args.show_paths)
    if args.json:
        emit(result, True)
    else:
        print(f"status: {result['status']}")
        print(f"available: {result['available_count']}/{result['total']}")
        print(f"default_runtime: {result['policy']['default_runtime']}")
        print(f"real_cli_execution: {result['policy']['real_cli_execution']}")
        for adapter in result["adapters"]:
            print(f"- {adapter['id']}: {adapter['status']} ({adapter['execution_mode']})")
        if result.get("runtime_subagents"):
            print("runtime_subagents:")
            for item in result["runtime_subagents"]:
                print(f"- {item['id']}: {item['runtime_tool']}({item['runtime_agent_type']})")
    return 0 if result.get("status") == "ready" else 1


def cmd_subagent_adapter(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = build_subagent_adapter(
            project_root,
            args.id,
            task_id=args.task_id or "",
            run_id=args.run_id or "",
            purpose=args.purpose or "",
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(result["marker"])
        print(f"runtime_tool: {result['runtime_tool']}")
        print(f"runtime_agent_type: {result['runtime_agent_type']}")
        print(f"capability_event: {result['capability_event_suggestion']}")
    return 0


def cmd_workbench_state(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = build_workbench_state(project_root, show_paths=args.show_paths, skip_external_checks=args.skip_linked_checks)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        print(f"status: {result['status']}")
        print(f"managed: {str(result['managed']).lower()}")
        print(f"project: {result.get('project', {}).get('name') or result['project_name']}")
        if result.get("managed"):
            print(f"doctor: {result['system_black_box']['doctor']['status']}")
            print(f"tasks: {result['tasks']['total']}")
            current = result["tasks"].get("current")
            print(f"current_task: {current.get('id') if current else 'none'}")
    return 0


def cmd_workbench_lifecycle(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = build_workbench_lifecycle(
            project_root,
            task_id=args.task_id,
            show_paths=args.show_paths,
            skip_external_checks=args.skip_linked_checks,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        emit(result, True)
    else:
        task = result.get("selected_task") or {}
        print(f"status: {result['status']}")
        print(f"managed: {str(result['managed']).lower()}")
        print(f"task: {task.get('id', 'none')}")
        for stage in result.get("stages", []):
            print(f"- {stage['label']}: {stage['status']} ({stage['detail']})")
    return 0 if result.get("status") in {"ready", "no_task", "unmanaged"} else 1


def is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def cmd_workbench_preview(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    if not is_loopback_host(args.host):
        print(
            "workbench-preview only supports loopback hosts (127.0.0.1, ::1, or localhost); "
            f"refusing --host {args.host!r}",
            file=sys.stderr,
        )
        return 2
    static_root = workbench_static_root()
    if not static_root.is_dir():
        print(f"missing Workbench preview files: {static_root}", file=sys.stderr)
        return 1
    handler = build_workbench_preview_handler(
        project_root,
        static_root,
        show_paths=args.show_paths,
        skip_linked_checks=args.skip_linked_checks,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    host, port = server.server_address[:2]
    print(f"KnowledgeOS Workbench preview: http://{host}:{port}")
    print(f"Live state endpoint: http://{host}:{port}/workbench-state.json")
    print("Mode: read-only preview; no project mutation path is exposed.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWorkbench preview stopped.")
    finally:
        server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knowledgeos", description="KnowledgeOS executable control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="validate a KnowledgeOS root and optional project control plane")
    doctor.add_argument("--root", help="KnowledgeOS distribution root")
    doctor.add_argument("--project-root", help="project root to validate")
    doctor.add_argument("--project-only", action="store_true", help="skip distribution checks and validate only the project control plane")
    doctor.add_argument("--template", action="store_true", help="validate a reusable template with placeholders and linked capability paths unresolved")
    doctor.add_argument("--allow-placeholders", action="store_true", help="allow CHANGE_ME placeholders during project validation")
    doctor.add_argument(
        "--skip-linked-checks",
        "--skip-external-checks",
        dest="skip_external_checks",
        action="store_true",
        help="do not require linked kernel/capability paths to exist",
    )
    doctor.add_argument("--strict", action="store_true", help="project validation is strict by default; kept for readable scripts")
    doctor.add_argument("--summary", action="store_true", help="print only aggregate pass/fail counts and failed checks")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    harness = sub.add_parser("harness-audit", help="audit and optionally repair KnowledgeOS mount drift across managed projects")
    harness.add_argument("--root", help="KnowledgeOS distribution root")
    harness.add_argument("--search-root", action="append", default=[], help="directory to scan for .agent-os projects")
    harness.add_argument("--target-project", action="append", default=[], help="specific project root to audit")
    harness.add_argument("--governance-root", help="canonical governance root; defaults to <root>/global-agent-fabric")
    harness.add_argument("--capability-root", help="canonical capability root; defaults to <root>/capability-layer")
    harness.add_argument("--include-registry", action="store_true", help="also scan projects listed in the governance registry")
    harness.add_argument("--include-templates", action="store_true", help="include template project-control-plane directories")
    harness.add_argument("--apply", action="store_true", help="apply safe repairs; default is dry-run audit")
    harness.add_argument("--json", action="store_true")
    harness.set_defaults(func=cmd_harness_audit)

    init_os = sub.add_parser("init-os", help="create a minimal KnowledgeOS kernel and capability layer")
    init_os.add_argument("--root", help="KnowledgeOS distribution root")
    init_os.add_argument("--os-root", required=True, help="target root that will contain global-agent-fabric and capability-layer")
    init_os.add_argument("--global-root", help="override target kernel path")
    init_os.add_argument("--capability-root", help="override target capability layer path")
    init_os.add_argument("--dry-run", action="store_true")
    init_os.add_argument("--force", action="store_true", help="overwrite existing files after backing them up")
    init_os.add_argument("--json", action="store_true")
    init_os.set_defaults(func=cmd_init_os)

    init = sub.add_parser("init-project", help="copy project-control-plane template into a project")
    init.add_argument("--root", help="KnowledgeOS distribution root")
    init.add_argument("--project-root", required=True)
    init.add_argument("--name")
    init.add_argument("--global-root")
    init.add_argument("--capability-root")
    init.add_argument("--implementation-root", help=argparse.SUPPRESS)
    init.add_argument("--dry-run", action="store_true")
    init.add_argument("--force", action="store_true", help="overwrite existing files after backing them up")
    init.add_argument("--json", action="store_true")
    init.set_defaults(func=cmd_init_project)

    check = sub.add_parser("check-write", help="classify a planned write against .agent-os/write-policy.yaml")
    check.add_argument("--project-root", required=True)
    check.add_argument("--path", required=True)
    check.add_argument("--strict", action="store_true", help="treat unclassified project paths as failures")
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=cmd_check_write)

    route_check = sub.add_parser("check-route-write", help="classify a write against both write policy and task route allowed_outputs")
    route_check.add_argument("--project-root", required=True)
    route_check.add_argument("--task-id", required=True)
    route_check.add_argument("--path", required=True)
    route_check.add_argument("--json", action="store_true")
    route_check.set_defaults(func=cmd_check_route_write)

    run = sub.add_parser("run-task", help="create a run envelope for a ready task")
    run.add_argument("--project-root", required=True)
    run.add_argument("--task-id", required=True)
    run.add_argument("--summary", default="Run started through KnowledgeOS control plane.")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--force", action="store_true", help="allow non-ready task status; routing is still required")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=cmd_run_task)

    create = sub.add_parser("create-task", help="append a new task to .agent-os/tasks.yaml")
    create.add_argument("--project-root", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--type", required=True, help="task type to route through .agent-os/workflows/router.yaml")
    create.add_argument("--status", default="ready", choices=sorted(TASK_STATUSES))
    create.add_argument("--complexity", default="medium")
    create.add_argument("--risk", default="normal")
    create.add_argument("--output", action="append", required=True, help="declared task output path; repeat for multiple outputs")
    create.add_argument("--acceptance", action="append", required=True, help="acceptance check; repeat for multiple checks")
    create.add_argument("--dry-run", action="store_true")
    create.add_argument("--json", action="store_true")
    create.set_defaults(func=cmd_create_task)

    create_spec_parser = sub.add_parser("create-spec", help="create a durable spec contract under .agent-os/specs")
    create_spec_parser.add_argument("--project-root", required=True)
    create_spec_parser.add_argument("--title", required=True)
    create_spec_parser.add_argument("--intent", default="")
    create_spec_parser.add_argument("--acceptance", action="append", default=[], help="spec-level acceptance criterion; repeat for multiple checks")
    create_spec_parser.add_argument("--non-goal", action="append", default=[], help="explicit non-goal; repeat for multiple items")
    create_spec_parser.add_argument("--no-activate", action="store_true", help="create the spec without making it active")
    create_spec_parser.add_argument("--dry-run", action="store_true")
    create_spec_parser.add_argument("--json", action="store_true")
    create_spec_parser.set_defaults(func=cmd_create_spec)

    align_spec_parser = sub.add_parser("align-spec", help="align active or selected spec with the current task")
    align_spec_parser.add_argument("--project-root", required=True)
    align_spec_parser.add_argument("--task-id")
    align_spec_parser.add_argument("--spec-id")
    align_spec_parser.add_argument("--note", default="")
    align_spec_parser.add_argument("--json", action="store_true")
    align_spec_parser.set_defaults(func=cmd_align_spec)

    reopen = sub.add_parser("reopen-task", help="reopen a task for rerun and optionally archive/delete declared outputs")
    reopen.add_argument("--project-root", required=True)
    reopen.add_argument("--task-id", required=True)
    reopen.add_argument("--status", default="ready", choices=sorted(TASK_STATUSES - {"completed"}))
    reopen.add_argument("--reason", required=True)
    reopen.add_argument("--archive-outputs", action="store_true", help="archive declared task outputs into .agent-os/backups before reopening")
    reopen.add_argument("--purge-outputs", action="store_true", help="delete declared task outputs instead of archiving them")
    reopen.add_argument("--dry-run", action="store_true")
    reopen.add_argument("--json", action="store_true")
    reopen.set_defaults(func=cmd_reopen_task)

    reset = sub.add_parser("reset-project", help="reset KnowledgeOS project state without guessing user intent")
    reset.add_argument("--project-root", required=True)
    reset.add_argument("--mode", required=True, choices=["soft", "hard"], help="soft archives volatile OS state; hard archives/removes the control plane")
    reset.add_argument("--purge", action="store_true", help="delete instead of archiving; destructive")
    reset.add_argument("--keep-task-status", action="store_true", help="soft reset keeps task statuses unchanged")
    reset.add_argument("--include-agents-md", action="store_true", help="hard reset also archives/removes AGENTS.md")
    reset.add_argument("--dry-run", action="store_true")
    reset.add_argument("--json", action="store_true")
    reset.set_defaults(func=cmd_reset_project)

    migrate = sub.add_parser("migrate-legacy-project", help="plan or apply a conservative legacy-folder reorganization")
    migrate.add_argument("--project-root", required=True)
    migrate.add_argument("--write-plan", action="store_true", help="write .agent-os/inbox/legacy-reorganization-plan.md")
    migrate.add_argument("--apply", action="store_true", help="move only confidently classified top-level entries with no target conflicts")
    migrate.add_argument("--dry-run", action="store_true")
    migrate.add_argument("--json", action="store_true")
    migrate.set_defaults(func=cmd_migrate_legacy_project)

    archive = sub.add_parser("archive-legacy-project", help="plan or apply cold archival of historical or superseded project files")
    archive.add_argument("--project-root", required=True)
    archive.add_argument("--write-plan", action="store_true", help="write .agent-os/inbox/cold-archive-plan.md")
    archive.add_argument("--apply", action="store_true", help="move planned archive candidates into archive/ cold storage")
    archive.add_argument("--include", action="append", default=[], help="explicit relative path to include in the cold archive plan")
    archive.add_argument("--dry-run", action="store_true")
    archive.add_argument("--json", action="store_true")
    archive.set_defaults(func=cmd_archive_legacy_project)

    eval_task_parser = sub.add_parser("eval-task", help="write deterministic run eval evidence for a task")
    eval_task_parser.add_argument("--project-root", required=True)
    eval_task_parser.add_argument("--task-id", required=True)
    eval_task_parser.add_argument("--run-id", required=True)
    eval_task_parser.add_argument("--notes", default="")
    eval_task_parser.add_argument("--json", action="store_true")
    eval_task_parser.set_defaults(func=cmd_eval_task)

    phase_task_parser = sub.add_parser("phase-task", help="append public lifecycle phase evidence for a run")
    phase_task_parser.add_argument("--project-root", required=True)
    phase_task_parser.add_argument("--task-id", required=True)
    phase_task_parser.add_argument("--run-id", required=True)
    phase_task_parser.add_argument("--phase", required=True, choices=EXPECTED_PHASE_KEYS)
    phase_task_parser.add_argument("--status", required=True, choices=sorted(PHASE_STATUSES))
    phase_task_parser.add_argument("--note", required=True, help="public decision trace; do not include hidden chain-of-thought")
    phase_task_parser.add_argument("--evidence", default="", help="command, file, or user confirmation evidence")
    phase_task_parser.add_argument("--skip-reason", default="", help="required when --status skipped")
    phase_task_parser.add_argument("--json", action="store_true")
    phase_task_parser.set_defaults(func=cmd_phase_task)

    capability_event_parser = sub.add_parser("capability-event", help="record an observable mounted capability call")
    capability_event_parser.add_argument("--project-root", required=True)
    capability_event_parser.add_argument("--task-id", required=True)
    capability_event_parser.add_argument("--run-id", required=True)
    capability_event_parser.add_argument("--kind", required=True, choices=sorted(CAPABILITY_EVENT_KINDS))
    capability_event_parser.add_argument("--id", required=True, help="capability id, tool id, script id, or short file-read label")
    capability_event_parser.add_argument("--purpose", required=True, help="public purpose for the capability call")
    capability_event_parser.add_argument("--status", default="completed")
    capability_event_parser.add_argument("--evidence", default="")
    capability_event_parser.add_argument("--json", action="store_true")
    capability_event_parser.set_defaults(func=cmd_capability_event)

    trace_step_parser = sub.add_parser("trace-step", help="record a public operational trace step for a run")
    trace_step_parser.add_argument("--project-root", required=True)
    trace_step_parser.add_argument("--task-id", required=True)
    trace_step_parser.add_argument("--run-id", required=True)
    trace_step_parser.add_argument("--step", required=True, choices=OPERATIONAL_TRACE_STEPS)
    trace_step_parser.add_argument("--status", default="completed")
    trace_step_parser.add_argument("--note", required=True, help="public operational note; do not include hidden chain-of-thought")
    trace_step_parser.add_argument("--evidence", default="", help="command, file, or user confirmation evidence")
    trace_step_parser.add_argument("--json", action="store_true")
    trace_step_parser.set_defaults(func=cmd_trace_step)

    decision_event_parser = sub.add_parser("decision-event", help="record a public Decision Graph event for a run")
    decision_event_parser.add_argument("--project-root", required=True)
    decision_event_parser.add_argument("--task-id", required=True)
    decision_event_parser.add_argument("--run-id", required=True)
    decision_event_parser.add_argument("--kind", required=True, choices=sorted(DECISION_EVENT_KINDS))
    decision_event_parser.add_argument("--status", default="active", choices=sorted(DECISION_EVENT_STATUSES))
    decision_event_parser.add_argument("--title", required=True)
    decision_event_parser.add_argument("--summary", default="")
    decision_event_parser.add_argument("--reason", default="", help="public decision rationale; do not include hidden chain-of-thought")
    decision_event_parser.add_argument("--evidence", default="", help="command, file, or user confirmation evidence")
    decision_event_parser.add_argument("--parent-id", default="")
    decision_event_parser.add_argument("--option", action="append", default=[])
    decision_event_parser.add_argument("--chosen", default="")
    decision_event_parser.add_argument("--linked-step", default="", choices=["", *OPERATIONAL_TRACE_STEPS])
    decision_event_parser.add_argument("--linked-capability-event-id", default="")
    decision_event_parser.add_argument("--linked-effect-assertion-id", default="")
    decision_event_parser.add_argument("--json", action="store_true")
    decision_event_parser.set_defaults(func=cmd_decision_event)

    decision_query_parser = sub.add_parser("decision-query", help="query public Decision Graph events for a run")
    decision_query_parser.add_argument("--project-root", required=True)
    decision_query_parser.add_argument("--run-id", required=True)
    decision_query_parser.add_argument("--task-id", default="")
    decision_query_parser.add_argument("--kind", default="", choices=["", *sorted(DECISION_EVENT_KINDS)])
    decision_query_parser.add_argument("--status", default="", choices=["", *sorted(DECISION_EVENT_STATUSES)])
    decision_query_parser.add_argument("--parent-id", default="")
    decision_query_parser.add_argument("--json", action="store_true")
    decision_query_parser.set_defaults(func=cmd_decision_query)

    artifact_assert_parser = sub.add_parser("artifact-assert", help="verify a real side effect before recording EFFECT_OK evidence")
    artifact_assert_parser.add_argument("--project-root", required=True)
    artifact_assert_parser.add_argument("--task-id", required=True)
    artifact_assert_parser.add_argument("--run-id", required=True)
    artifact_assert_parser.add_argument("--kind", required=True, choices=sorted(EFFECT_ASSERTION_KINDS))
    artifact_assert_parser.add_argument("--path", required=True, help="artifact path inside the project root")
    artifact_assert_parser.add_argument("--expect", default="", help="expected text, sha256, or JSON scalar value for assertion kinds that need it")
    artifact_assert_parser.add_argument("--before-sha", default="", help="previous sha256 for file_changed assertions")
    artifact_assert_parser.add_argument("--json-key", default="", help="dot-separated JSON key path for json_key_equals assertions")
    artifact_assert_parser.add_argument("--capability-event-id", default="", help="optional capability event id this effect proves")
    artifact_assert_parser.add_argument("--json", action="store_true")
    artifact_assert_parser.set_defaults(func=cmd_artifact_assert)

    context_pack_parser = sub.add_parser("context-pack", help="write run context-pack.md and spec-snapshot.md")
    context_pack_parser.add_argument("--project-root", required=True)
    context_pack_parser.add_argument("--task-id", required=True)
    context_pack_parser.add_argument("--run-id", required=True)
    context_pack_parser.add_argument("--summary", default="")
    context_pack_parser.add_argument("--json", action="store_true")
    context_pack_parser.set_defaults(func=cmd_context_pack)

    plan_task_parser = sub.add_parser("plan-task", help="write run plan.md after context pack generation")
    plan_task_parser.add_argument("--project-root", required=True)
    plan_task_parser.add_argument("--task-id", required=True)
    plan_task_parser.add_argument("--run-id", required=True)
    plan_task_parser.add_argument("--summary", default="")
    plan_task_parser.add_argument("--json", action="store_true")
    plan_task_parser.set_defaults(func=cmd_plan_task)

    verify_context_parser = sub.add_parser("verify-context", help="verify run spec snapshot, context pack, and plan evidence")
    verify_context_parser.add_argument("--project-root", required=True)
    verify_context_parser.add_argument("--task-id", required=True)
    verify_context_parser.add_argument("--run-id", required=True)
    verify_context_parser.add_argument("--json", action="store_true")
    verify_context_parser.set_defaults(func=cmd_verify_context)

    verify_lifecycle_parser = sub.add_parser("verify-lifecycle", help="verify a run has all required public lifecycle phases")
    verify_lifecycle_parser.add_argument("--project-root", required=True)
    verify_lifecycle_parser.add_argument("--task-id", required=True)
    verify_lifecycle_parser.add_argument("--run-id", required=True)
    verify_lifecycle_parser.add_argument("--json", action="store_true")
    verify_lifecycle_parser.set_defaults(func=cmd_verify_lifecycle)

    verify_effects_parser = sub.add_parser("verify-effects", help="verify artifact effect assertions for a run")
    verify_effects_parser.add_argument("--project-root", required=True)
    verify_effects_parser.add_argument("--task-id", required=True)
    verify_effects_parser.add_argument("--run-id", required=True)
    verify_effects_parser.add_argument("--json", action="store_true")
    verify_effects_parser.set_defaults(func=cmd_verify_effects)

    verify_decisions_parser = sub.add_parser("verify-decisions", help="verify Decision Graph events and command evidence for a run")
    verify_decisions_parser.add_argument("--project-root", required=True)
    verify_decisions_parser.add_argument("--task-id", required=True)
    verify_decisions_parser.add_argument("--run-id", required=True)
    verify_decisions_parser.add_argument("--json", action="store_true")
    verify_decisions_parser.set_defaults(func=cmd_verify_decisions)

    complete = sub.add_parser("complete-task", help="complete a task only after eval, lifecycle, outputs, and required postflight pass")
    complete.add_argument("--project-root", required=True)
    complete.add_argument("--task-id", required=True)
    complete.add_argument("--run-id", required=True)
    complete.add_argument("--summary", required=True)
    complete.add_argument("--allow-missing-eval", action="store_true", help="manual override; normally eval.md must say Status: passed")
    complete.add_argument("--allow-manual-eval", action="store_true", help="manual override; normally eval.md must be generated by eval-task")
    complete.add_argument("--allow-missing-outputs", action="store_true", help="manual override; normally declared task outputs must exist")
    complete.add_argument("--override-reason", help="required when using eval/output completion override flags")
    complete.add_argument("--allow-pending-postflight", metavar="REASON", help="explicit escape hatch when required postflight cannot complete")
    complete.add_argument("--json", action="store_true")
    complete.set_defaults(func=cmd_complete_task)

    route = sub.add_parser("route-task", help="resolve a task type into the KnowledgeOS workflow route")
    route.add_argument("--project-root", required=True)
    group = route.add_mutually_exclusive_group(required=True)
    group.add_argument("--task-id", help="task id from .agent-os/tasks.yaml")
    group.add_argument("--task-type", help="task type to route without selecting a task")
    route.add_argument("--allow-unrouted", action="store_true", help="return success even when human triage is required")
    route.add_argument("--json", action="store_true")
    route.set_defaults(func=cmd_route_task)

    tools = sub.add_parser("tool-registry", help="inspect and validate MCP, skill, workflow, and subagent configuration")
    tools.add_argument("--project-root", required=True)
    tools.add_argument("--check-paths", action="store_true", help="also verify absolute source_path/path entries exist")
    tools.add_argument("--json", action="store_true")
    tools.set_defaults(func=cmd_tool_registry)

    dispatch = sub.add_parser("dispatch-task", help="build an observable capability dispatch plan for a routed task")
    dispatch.add_argument("--project-root", required=True)
    dispatch.add_argument("--task-id", required=True)
    dispatch.add_argument("--run-id", help="optional run id; when provided, records dispatch command evidence for lifecycle verification")
    dispatch.add_argument("--allow-unrouted", action="store_true", help="return success even when human triage is required")
    dispatch.add_argument("--json", action="store_true")
    dispatch.set_defaults(func=cmd_dispatch_task)

    dispatch_report = sub.add_parser("dispatch-report", help="summarize all actual mounted capability events for a run")
    dispatch_report.add_argument("--project-root", required=True)
    dispatch_report.add_argument("--task-id", required=True)
    dispatch_report.add_argument("--run-id", required=True)
    dispatch_report.add_argument("--json", action="store_true")
    dispatch_report.set_defaults(func=cmd_dispatch_report)

    render_html = sub.add_parser("render-html", help="render Markdown, flow, and Decision Graph evidence into composable static HTML sidecars")
    render_html.add_argument("--project-root", required=True)
    render_html.add_argument("--kind", choices=sorted(HTML_REPORT_KINDS), help="receipt, handoff, rich-report, decision-map, or mission-flow")
    render_html.add_argument("--run-id", help="run id for receipt, handoff, decision-map, or mission-flow rendering")
    render_html.add_argument("--task-id", help="optional task id for mission-flow; defaults from run.yaml")
    render_html.add_argument("--input", help="Markdown source for rich-report")
    render_html.add_argument("--output", help="HTML output path; defaults beside the source")
    render_html.add_argument("--compose", help="compose report manifests into one HTML page")
    render_html.add_argument("--theme", default=HTML_DEFAULT_THEME)
    render_html.add_argument(
        "--presentation",
        choices=sorted(HTML_PRESENTATION_MODES),
        help="presentation shell: default, minimal, bare, or fragment; project reporting policy is used when omitted",
    )
    render_html.add_argument("--json", action="store_true")
    render_html.set_defaults(func=cmd_render_html)

    flow_summary = sub.add_parser("flow-summary", help="print a friendly layered Mermaid mission flow for a run")
    flow_summary.add_argument("--project-root", required=True)
    flow_summary.add_argument("--run-id", required=True)
    flow_summary.add_argument("--task-id", help="optional task id; defaults from run.yaml")
    flow_summary.add_argument("--format", choices=["mermaid", "markdown"], default="mermaid")
    flow_summary.add_argument("--json", action="store_true")
    flow_summary.set_defaults(func=cmd_flow_summary)

    thread_plan = sub.add_parser("thread-plan", help="manage chat-level append-only natural-language plan ledgers")
    thread_sub = thread_plan.add_subparsers(dest="thread_action", required=True)
    thread_start = thread_sub.add_parser("start", help="start a chat-level Thread Plan Ledger")
    thread_start.add_argument("--project-root", required=True)
    thread_start.add_argument("--title", required=True)
    thread_start.add_argument("--spec-id", default="")
    thread_start.add_argument("--json", action="store_true")
    thread_start.set_defaults(func=cmd_thread_plan)

    thread_current = thread_sub.add_parser("current", help="show the current active Thread Plan Ledger")
    thread_current.add_argument("--project-root", required=True)
    thread_current.add_argument("--json", action="store_true")
    thread_current.set_defaults(func=cmd_thread_plan)

    thread_append = thread_sub.add_parser("append", help="append a natural-language plan note")
    thread_append.add_argument("--project-root", required=True)
    thread_append.add_argument("--thread-id", required=True)
    thread_append.add_argument("--kind", required=True, choices=sorted(THREAD_PLAN_EVENT_KINDS))
    thread_append.add_argument("--text", required=True)
    thread_append.add_argument("--spec-id", default="")
    thread_append.add_argument("--task-id", default="")
    thread_append.add_argument("--run-id", default="")
    thread_append.add_argument("--parent-event-id", default="")
    thread_append.add_argument("--json", action="store_true")
    thread_append.set_defaults(func=cmd_thread_plan)

    thread_link = thread_sub.add_parser("link-run", help="link a task run to the current chat-level plan")
    thread_link.add_argument("--project-root", required=True)
    thread_link.add_argument("--thread-id", required=True)
    thread_link.add_argument("--task-id", required=True)
    thread_link.add_argument("--run-id", required=True)
    thread_link.add_argument("--text", default="")
    thread_link.add_argument("--json", action="store_true")
    thread_link.set_defaults(func=cmd_thread_plan)

    thread_render = thread_sub.add_parser("render", help="render a thread plan as Markdown, Mermaid, or HTML")
    thread_render.add_argument("--project-root", required=True)
    thread_render.add_argument("--thread-id", required=True)
    thread_render.add_argument("--format", choices=["markdown", "html", "mermaid"], default="markdown")
    thread_render.add_argument("--json", action="store_true")
    thread_render.set_defaults(func=cmd_thread_plan)

    receipt = sub.add_parser("receipt", help="write a local project receipt")
    receipt.add_argument("--project-root", required=True)
    receipt.add_argument("--summary", required=True)
    receipt.add_argument("--status", default="recorded")
    receipt.add_argument("--receipt-id")
    receipt.add_argument("--json", action="store_true")
    receipt.set_defaults(func=cmd_receipt)

    guide = sub.add_parser("agent-guide", help="print or write an agent onboarding checklist for a project")
    guide.add_argument("--project-root", required=True)
    guide.add_argument("--output", help="write guide to a file instead of stdout")
    guide.add_argument("--json", action="store_true")
    guide.set_defaults(func=cmd_agent_guide)

    startup = sub.add_parser("startup-prompt", help="print or write the short OS entry prompt for a project")
    startup.add_argument("--project-root", required=True)
    startup.add_argument("--output", help="write prompt to a file instead of stdout")
    startup.add_argument("--json", action="store_true")
    startup.set_defaults(func=cmd_startup_prompt)

    workbench = sub.add_parser("workbench-state", help="emit a read-only KnowledgeOS Workbench project-state snapshot")
    workbench.add_argument("--project-root", required=True)
    workbench.add_argument("--show-paths", action="store_true", help="include absolute paths instead of privacy redaction")
    workbench.add_argument("--skip-linked-checks", action="store_true", help="do not require linked kernel/capability paths to exist")
    workbench.add_argument("--json", action="store_true")
    workbench.set_defaults(func=cmd_workbench_state)

    lifecycle = sub.add_parser("workbench-lifecycle", help="emit a read-only Workbench task lifecycle snapshot")
    lifecycle.add_argument("--project-root", required=True)
    lifecycle.add_argument("--task-id", help="task id to inspect; defaults to the current Workbench task")
    lifecycle.add_argument("--show-paths", action="store_true", help="include absolute paths instead of privacy redaction")
    lifecycle.add_argument("--skip-linked-checks", action="store_true", help="do not require linked kernel/capability paths to exist")
    lifecycle.add_argument("--json", action="store_true")
    lifecycle.set_defaults(func=cmd_workbench_lifecycle)

    ask = sub.add_parser("ask-sandbox", help="answer an intent in a read-only local sandbox without project mutation")
    ask.add_argument("--project-root", required=True)
    ask.add_argument("--prompt", help="intent prompt; stdin is used when omitted")
    ask.add_argument("--runtime", default="mock", choices=["mock"], help="sandbox runtime adapter; only mock is enabled")
    ask.add_argument("--show-paths", action="store_true", help="include absolute paths instead of privacy redaction")
    ask.add_argument("--json", action="store_true")
    ask.set_defaults(func=cmd_ask_sandbox)

    runtime_adapters = sub.add_parser("runtime-adapters", help="inspect read-only local runtime adapter readiness")
    runtime_adapters.add_argument("--project-root", required=True)
    runtime_adapters.add_argument("--show-paths", action="store_true", help="include absolute executable paths instead of privacy redaction")
    runtime_adapters.add_argument("--json", action="store_true")
    runtime_adapters.set_defaults(func=cmd_runtime_adapters)

    subagent_adapter = sub.add_parser("subagent-adapter", help="resolve a registered subagent into a Codex runtime adapter call package")
    subagent_adapter.add_argument("--project-root", required=True)
    subagent_adapter.add_argument("--id", required=True, help="registered subagent id, for example codex-explorer or maestro-architect")
    subagent_adapter.add_argument("--task-id", help="optional task id; when paired with --run-id records command evidence")
    subagent_adapter.add_argument("--run-id", help="optional run id; when paired with --task-id records command evidence")
    subagent_adapter.add_argument("--purpose", default="", help="short public purpose for the suggested capability-event")
    subagent_adapter.add_argument("--json", action="store_true")
    subagent_adapter.set_defaults(func=cmd_subagent_adapter)

    preview = sub.add_parser("workbench-preview", help="serve the read-only Workbench preview with live project state")
    preview.add_argument("--project-root", required=True)
    preview.add_argument("--host", default="127.0.0.1")
    preview.add_argument("--port", type=int, default=4173)
    preview.add_argument("--show-paths", action="store_true", help="include absolute paths in the live state endpoint")
    preview.add_argument("--skip-linked-checks", action="store_true", help="do not require linked kernel/capability paths to exist")
    preview.set_defaults(func=cmd_workbench_preview)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
