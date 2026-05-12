#!/usr/bin/env python3
"""KnowledgeOS executable control plane.

The bootstrap path intentionally uses only the Python standard library. The
parser supports KnowledgeOS' own small YAML-like templates; richer schema
validation can come later without making the bootstrap path fragile.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REQUIRED_PUBLIC_FILES = [
    "README.md",
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
    "docs/reset-and-migration.md",
    "docs/archive-policy.md",
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
    "templates/project-control-plane/AGENTS.md",
    "examples/scenarios/README.md",
    "examples/scenarios/distracted-agent-guardrails.md",
    "examples/scenarios/run_guardrail_scenarios.sh",
    "templates/project-control-plane/.agent-os/workspace.yaml",
    "templates/project-control-plane/.agent-os/project.yaml",
    "templates/project-control-plane/.agent-os/startup-prompt.md",
    "templates/project-control-plane/.agent-os/tasks.yaml",
    "templates/project-control-plane/.agent-os/phase-policy.yaml",
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
READ_POLICY_SECTIONS = {
    "default_context",
    "cold_storage",
    "require_explicit_human_request",
    "deny_indexing",
}

EXPECTED_PHASE_KEYS = ["route", "plan", "review", "dispatch", "execute", "report"]
PHASE_STATUSES = {"completed", "skipped"}
TASK_STATUSES = {"backlog", "ready", "in_progress", "blocked", "completed", "cancelled"}
RUNNABLE_TASK_STATUSES = {"ready", "in_progress"}
TOOL_KINDS = {"mcp", "skill", "workflow", "orchestrator", "subagent", "memory"}
TOOL_STATUSES = {"enabled", "disabled", "optional", "recommended", "configured", "indexed"}
ACTIVE_TOOL_STATUSES = {"enabled", "recommended", "configured", "indexed"}
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


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-.") or "item"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def iter_files(root: Path, relative_paths: Iterable[str]) -> Iterable[Path]:
    for rel in relative_paths:
        yield root / rel


def scan_public_content(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    scan_roots = [root / "README.md", root / "docs", root / "templates"]
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
            current = key if key in allowed_sections else current
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


def tool_summary(entry: dict[str, str]) -> dict[str, Any]:
    return {
        "id": entry.get("id", ""),
        "kind": entry.get("kind", ""),
        "status": entry.get("status", ""),
        "scope": entry.get("scope", ""),
        "invocation": entry.get("invocation", ""),
        "human_gate": entry.get("human_gate", ""),
        "execution_mode": entry.get("execution_mode", ""),
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
        subagents = choose_tools(entries, "subagent", task_type)
        if subagents:
            add_step("subagent", "use role-specific subagent or planning adapter when registered", subagents)

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

    return {
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
    for pattern in patterns:
        normalized = pattern.replace(os.sep, "/")
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


def copy_template_tree(src: Path, dest: Path, replacements: dict[str, str], *, dry_run: bool, force: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for source_path in sorted(p for p in src.rglob("*") if p.is_file()):
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


def command_events_path(run_dir: Path) -> Path:
    return run_dir / "command-events.ndjson"


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
            root_matches = Path(root_value).expanduser().resolve() == project_root.resolve()
        except RuntimeError:
            root_matches = False
        results.append(CheckResult(root_matches, "workspace_root", f"root points to {root_value}"))

    project = parse_scalar_values(agent_os / "project.yaml", {"id", "name", "status", "current_phase"})
    for key in ["id", "name", "status", "current_phase"]:
        results.append(CheckResult(bool(project.get(key)), "project_schema", f"{key} present"))

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
        exists = Path(value).expanduser().exists()
        results.append(CheckResult(skip_external or exists, "fabric_link", f"{key} -> {value}" if exists else f"{key} target missing: {value}"))
    for key in ["boot_required", "phase_logging_required", "postflight_required"]:
        results.append(CheckResult(fabric.get(key) == "true", "runtime_contract", f"{key}=true"))
    phases = parse_simple_list_sections(agent_os / "fabric-link.yaml", {"phase_keys"}).get("phase_keys", [])
    results.append(CheckResult(phases == EXPECTED_PHASE_KEYS, "phase_keys", f"{phases}"))
    results.extend(validate_phase_policy(project_root))

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
                lifecycle = verify_lifecycle(project_root, metadata.get("task_id", ""), run_id)
                results.append(CheckResult(lifecycle.get("status") == "passed", "completed_run_lifecycle", f"{run_id} lifecycle status={lifecycle.get('status')}"))

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
                has_phase = any("phase-task" in item for item in route_order)
                has_eval = any("eval-task" in item for item in route_order)
                has_verify = any("verify-lifecycle" in item for item in route_order)
                has_complete = any("complete-task" in item for item in route_order)
                eval_index = next((idx for idx, item in enumerate(route_order) if "eval-task" in item), -1)
                verify_index = next((idx for idx, item in enumerate(route_order) if "verify-lifecycle" in item), -1)
                complete_index = next((idx for idx, item in enumerate(route_order) if "complete-task" in item), -1)
                results.append(CheckResult(has_run, "workflow_router_lifecycle", f"{name} includes run-task"))
                results.append(CheckResult(has_phase, "workflow_router_lifecycle", f"{name} includes phase-task"))
                results.append(CheckResult(has_eval, "workflow_router_lifecycle", f"{name} includes eval-task"))
                results.append(CheckResult(has_verify, "workflow_router_lifecycle", f"{name} includes verify-lifecycle"))
                results.append(CheckResult(has_complete, "workflow_router_lifecycle", f"{name} includes complete-task"))
                results.append(
                    CheckResult(
                        eval_index >= 0 and complete_index >= 0 and eval_index < complete_index,
                        "workflow_router_lifecycle",
                        f"{name} eval-task before complete-task",
                    )
                )
                results.append(
                    CheckResult(
                        verify_index >= 0 and complete_index >= 0 and verify_index < complete_index,
                        "workflow_router_lifecycle",
                        f"{name} verify-lifecycle before complete-task",
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
            "1. Read the entry contract.",
            "   - AGENTS.md",
            "",
            "2. Load project control state.",
            "   - .agent-os/workspace.yaml",
            "   - .agent-os/project.yaml",
            "   - .agent-os/tasks.yaml",
            "   - .agent-os/phase-policy.yaml",
            "   - .agent-os/decisions.yaml",
            "   - .agent-os/evals.yaml",
            "   - .agent-os/capabilities.yaml",
            "   - .agent-os/read-policy.yaml",
            "   - .agent-os/write-policy.yaml",
            "",
            "3. Run checks before acting.",
            f"   - {bin_path} doctor --project-root {project_root} --summary",
            f"   - {bin_path} tool-registry --project-root {project_root}",
            f"   - {bin_path} create-task --project-root {project_root} --title <title> --type <type> --output <path> --acceptance <check>",
            f"   - {bin_path} route-task --project-root {project_root} --task-id <task-id>",
            f"   - {bin_path} dispatch-task --project-root {project_root} --task-id <task-id>",
            f"   - {bin_path} check-route-write --project-root {project_root} --task-id <task-id> --path <planned-path>",
            "",
            "4. Start work through a run envelope.",
            f"   - {bin_path} run-task --project-root {project_root} --task-id <task-id>",
            "",
            "5. Never bypass write guard.",
            "   - immutable paths are denied;",
            "   - human-gated paths require explicit approval;",
            "   - unclassified paths should be triaged before mutation.",
            "   - pause at consultation checkpoints, state your recommendation, and ask before proceeding.",
            "",
            "6. Keep receipts.",
            "   - update .agent-os/runs/RUN-*/receipt.md;",
            f"   - {bin_path} phase-task --project-root {project_root} --task-id <task-id> --run-id <run-id> --phase <phase> --status completed --note <public-trace> --evidence <evidence>;",
            f"   - {bin_path} eval-task --project-root {project_root} --task-id <task-id> --run-id <run-id>;",
            f"   - {bin_path} verify-lifecycle --project-root {project_root} --task-id <task-id> --run-id <run-id>;",
            "   - update .agent-os/handoffs/current.md.",
            f"   - {bin_path} complete-task --project-root {project_root} --task-id <task-id> --run-id <run-id> --summary <summary>",
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
            "1. Read `AGENTS.md`.",
            "2. Read `.agent-os/workspace.yaml`, `.agent-os/project.yaml`, `.agent-os/tasks.yaml`, `.agent-os/phase-policy.yaml`, `.agent-os/decisions.yaml`, `.agent-os/evals.yaml`, `.agent-os/fabric-link.yaml`, `.agent-os/read-policy.yaml`, `.agent-os/write-policy.yaml`, `.agent-os/dispatch-policy.yaml`, and `.agent-os/tool-registry.yaml`.",
            f"3. Run `{bin_path} doctor --project-root {project_root} --summary` and do not proceed if it fails.",
            f"4. Select or confirm one task id from `.agent-os/tasks.yaml`; if the user asks for new work and no ready task fits, run `{bin_path} create-task --project-root {project_root} --title \"<title>\" --type <type> --output <path> --acceptance \"<check>\"`.",
            f"5. Run `{bin_path} route-task --project-root {project_root} --task-id <task-id>`.",
            f"6. Run `{bin_path} dispatch-task --project-root {project_root} --task-id <task-id>` before invoking subagents, MCP tools, skills, workflows, or scripts.",
            f"7. Before planned mutation, run `{bin_path} check-route-write --project-root {project_root} --task-id <task-id> --path <planned-path>`.",
            f"8. Create run evidence with `{bin_path} run-task --project-root {project_root} --task-id <task-id>`.",
            "9. Pause at consultation checkpoints, state your recommended next move, name the tradeoff, and ask the human whether to proceed.",
            f"10. Record public phase evidence with `{bin_path} phase-task --project-root {project_root} --task-id <task-id> --run-id <run-id> --phase <route|plan|review|dispatch|execute|report> --status completed --note \"<public trace>\" --evidence \"<command/file/user confirmation>\"`.",
            f"11. Run `{bin_path} eval-task --project-root {project_root} --task-id <task-id> --run-id <run-id>`; do not manually append eval status.",
            f"12. Run `{bin_path} verify-lifecycle --project-root {project_root} --task-id <task-id> --run-id <run-id>`.",
            f"13. Use `{bin_path} complete-task --project-root {project_root} --task-id <task-id> --run-id <run-id> --summary \"<summary>\"`; it must enforce lifecycle and required postflight.",
            "14. If a shared-fabric postflight hook is configured, report `[SYNC_OK]` only after `complete-task` returns `sync_status: SYNC_OK`.",
            f"15. For reset requests, run `{bin_path} reset-project --project-root {project_root} --mode <soft|hard> --dry-run` before destructive action.",
            f"16. For old-project reorganization requests, run `{bin_path} migrate-legacy-project --project-root {project_root} --write-plan` before moving files.",
            f"17. For historical/superseded files that should be stored but not read by default, run `{bin_path} archive-legacy-project --project-root {project_root} --write-plan` before moving files into `archive/`.",
            "",
            "Never claim boot, route, dispatch, write safety, eval, or sync success without command evidence.",
            "",
        ]
    )


def create_run_envelope(project_root: Path, task_id: str, summary: str, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    task = find_task(project_root, task_id)
    task_status = task.get("status", "")
    if task_status not in RUNNABLE_TASK_STATUSES and not force:
        raise ValueError(f"task {task_id} status is {task_status!r}; expected one of {sorted(RUNNABLE_TASK_STATUSES)}")
    route = build_task_route(project_root, task_id, None)
    if route.get("status") != "routed":
        raise ValueError(f"task {task_id} is not runnable because routing failed: {route.get('reason', 'unknown route failure')}")
    run_id = f"RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_slug(task_id)}"
    run_dir = project_root / ".agent-os" / "runs" / run_id
    created = [
        run_dir / "run.yaml",
        run_dir / "prompt.md",
        run_dir / "receipt.md",
        run_dir / "diff_summary.md",
        run_dir / "eval.md",
        run_dir / "handoff.md",
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
        append_command_event(run_dir, "run-task", task_id, run_id, status="started")
        write_text(project_root / ".agent-os" / "receipts" / "latest.md", receipt)
        write_text(project_root / ".agent-os" / "handoffs" / "current.md", f"# Current Handoff\n\nCurrent run: {run_id}\n\nTask: {task_id}\n")
    return {"run_id": run_id, "task": task, "route": route, "created": [str(p) for p in created], "dry_run": dry_run}


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
    return {"status": "recorded", "ledger": str(ledger_path), "record": record}


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

    postflight = run_postflight_gate(project_root, run_dir, summary, allow_pending_postflight)
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
        f"Sync Status: {postflight.get('sync_status')}",
        "",
    ]
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
        "sync_status": postflight.get("sync_status"),
        "status_marker": postflight.get("status_marker", ""),
        "postflight": postflight.get("postflight", ""),
        "receipt": str(run_dir / "receipt.md"),
        "handoff": str(run_dir / "handoff.md"),
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
    emit(result, args.json)
    return 0


def cmd_verify_lifecycle(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = verify_lifecycle(project_root, args.task_id, args.run_id)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0 if result.get("status") == "passed" else 2


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
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    emit(result, args.json)
    return 0 if result.get("status") == "dispatch_ready" or args.allow_unrouted else 2


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

    verify_lifecycle_parser = sub.add_parser("verify-lifecycle", help="verify a run has all required public lifecycle phases")
    verify_lifecycle_parser.add_argument("--project-root", required=True)
    verify_lifecycle_parser.add_argument("--task-id", required=True)
    verify_lifecycle_parser.add_argument("--run-id", required=True)
    verify_lifecycle_parser.add_argument("--json", action="store_true")
    verify_lifecycle_parser.set_defaults(func=cmd_verify_lifecycle)

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
    dispatch.add_argument("--allow-unrouted", action="store_true", help="return success even when human triage is required")
    dispatch.add_argument("--json", action="store_true")
    dispatch.set_defaults(func=cmd_dispatch_task)

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
