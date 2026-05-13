import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin" / "knowledgeos"


class KnowledgeOSCliTests(unittest.TestCase):
    def run_cli(self, *args, cwd=None, check=True):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        result = subprocess.run(
            [str(BIN), *args],
            cwd=cwd or ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f"command failed: {result.args}\nstdout={result.stdout}\nstderr={result.stderr}")
        return result

    def log_required_phases(self, project: Path, task_id: str, run_id: str) -> None:
        dispatch = self.run_cli("dispatch-task", "--project-root", str(project), "--task-id", task_id, "--run-id", run_id, "--json")
        dispatch_payload = json.loads(dispatch.stdout)
        required_stages = dispatch_payload.get("dispatch_event", {}).get("required_stages", [])
        for phase in ["route", "plan", "review", "dispatch", "execute", "report"]:
            note = f"Recorded {phase} decision trace."
            evidence = f"test evidence for {phase}"
            if phase == "dispatch" and required_stages:
                skipped = ", ".join(required_stages)
                note = f"Skipped required {skipped}: deterministic test uses KnowledgeOS CLI only."
                evidence = f"skip {skipped}: no external capability needed for this regression test"
            self.run_cli(
                "phase-task",
                "--project-root",
                str(project),
                "--task-id",
                task_id,
                "--run-id",
                run_id,
                "--phase",
                phase,
                "--status",
                "completed",
                "--note",
                note,
                "--evidence",
                evidence,
            )

    def write_plan_context(self, project: Path, task_id: str, run_id: str, summary: str = "Test execution plan.") -> None:
        self.run_cli(
            "context-pack",
            "--project-root",
            str(project),
            "--task-id",
            task_id,
            "--run-id",
            run_id,
            "--summary",
            summary,
        )
        self.run_cli(
            "plan-task",
            "--project-root",
            str(project),
            "--task-id",
            task_id,
            "--run-id",
            run_id,
            "--summary",
            summary,
        )

    def test_doctor_public_root_passes(self):
        result = self.run_cli("doctor", "--root", str(ROOT), "--json")
        payload = json.loads(result.stdout)
        self.assertTrue(all(item["ok"] for item in payload), payload)
        self.assertTrue(any(item["label"] == "public_scan" for item in payload))

    def test_doctor_summary_reduces_output(self):
        full = self.run_cli("doctor", "--root", str(ROOT), "--project-root", str(ROOT))
        summary = self.run_cli("doctor", "--root", str(ROOT), "--project-root", str(ROOT), "--summary")
        self.assertIn("status: ok", summary.stdout)
        self.assertIn("checks:", summary.stdout)
        self.assertIn("failed: 0", summary.stdout)
        self.assertNotIn("[OK]", summary.stdout)
        self.assertLess(len(summary.stdout.splitlines()), len(full.stdout.splitlines()))

        json_summary = self.run_cli("doctor", "--root", str(ROOT), "--project-root", str(ROOT), "--summary", "--json")
        payload = json.loads(json_summary.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertGreater(payload["checks"], 0)
        self.assertEqual(payload["failed"], 0)
        self.assertEqual(payload["failed_checks"], [])

    def test_doctor_project_relative_paths_resolve_from_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(
                "doctor",
                "--root",
                str(ROOT),
                "--project-root",
                str(ROOT),
                "--summary",
                cwd=tmp,
            )
        self.assertIn("status: ok", result.stdout)
        self.assertIn("failed: 0", result.stdout)

    def test_doctor_rejects_missing_boot_kernel_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            project = tmp_root / "Project"
            project.mkdir()
            governance = tmp_root / "KnowledgeOS" / "global-agent-fabric"
            capability = tmp_root / "KnowledgeOS" / "capability-layer"
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Project",
                "--global-root",
                str(governance),
                "--capability-root",
                str(capability),
            )
            hooks = governance / "hooks"
            hooks.mkdir(parents=True)
            for hook_name in ["before-task.sh", "after-task.sh"]:
                source = ROOT / "templates" / "governance-core" / "hooks" / hook_name
                target = hooks / hook_name
                target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                target.chmod(0o755)
            capability.mkdir(parents=True)

            result = self.run_cli("doctor", "--project-root", str(project), "--project-only", "--json", check=False)
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            failures = [item for item in payload if not item["ok"]]
            self.assertTrue(any(item["label"] == "kernel_skeleton" and "registries/" in item["detail"] for item in failures))
            self.assertTrue(any(item["label"] == "boot_kernel" and "schemas/phase-contract.md" in item["detail"] for item in failures))

    def test_harness_audit_repairs_legacy_mount_and_missing_control_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            project = tmp_root / "LegacyProject"
            project.mkdir()
            old_governance = tmp_root / "Antigravity_Skills" / "global-agent-fabric"
            desired_governance = tmp_root / "KnowledgeOS" / "global-agent-fabric"
            desired_capability = tmp_root / "KnowledgeOS" / "capability-layer"
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "LegacyProject",
                "--global-root",
                str(old_governance),
                "--capability-root",
                str(tmp_root / "KnowledgeOS"),
            )
            for rel in [".agent-os/specs.yaml", ".agent-os/phase-policy.yaml", ".agent-os/read-policy.yaml"]:
                (project / rel).unlink()
            router = project / ".agent-os" / "workflows" / "router.yaml"
            router_lines = [
                line
                for line in router.read_text(encoding="utf-8").splitlines()
                if not any(marker in line for marker in ["context-pack", "plan-task", "phase-task", "verify-context", "verify-lifecycle"])
            ]
            router.write_text("\n".join(router_lines) + "\n", encoding="utf-8")
            write_policy = project / ".agent-os" / "write-policy.yaml"
            write_policy.write_text(
                "\n".join(line for line in write_policy.read_text(encoding="utf-8").splitlines() if "archive/**" not in line) + "\n",
                encoding="utf-8",
            )

            dry_run = self.run_cli(
                "harness-audit",
                "--root",
                str(ROOT),
                "--target-project",
                str(project),
                "--governance-root",
                str(desired_governance),
                "--capability-root",
                str(desired_capability),
                "--json",
                check=False,
            )
            self.assertEqual(dry_run.returncode, 1)
            dry_payload = json.loads(dry_run.stdout)
            issues = dry_payload["projects"][0]["issues"]
            desired_governance = desired_governance.resolve()
            desired_capability = desired_capability.resolve()
            self.assertIn("legacy_antigravity_governance_root", issues)
            self.assertIn("postflight_hook_missing_or_not_executable", issues)
            self.assertIn("missing_control_file:.agent-os/specs.yaml", issues)
            self.assertIn("workflow_router_lifecycle_drift", issues)
            self.assertIn("missing_archive_write_guard", issues)
            self.assertFalse((desired_governance / "hooks" / "after-task.sh").exists())
            self.assertFalse((project / ".agent-os" / "specs.yaml").exists())

            applied = self.run_cli(
                "harness-audit",
                "--root",
                str(ROOT),
                "--target-project",
                str(project),
                "--governance-root",
                str(desired_governance),
                "--capability-root",
                str(desired_capability),
                "--apply",
                "--json",
            )
            payload = json.loads(applied.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(os.access(desired_governance / "hooks" / "after-task.sh", os.X_OK))
            self.assertTrue((desired_governance / "registries" / "mcp.example.yaml").exists())
            self.assertTrue((desired_governance / "schemas" / "phase-contract.md").exists())
            self.assertTrue((project / ".agent-os" / "specs.yaml").exists())
            fabric = (project / ".agent-os" / "fabric-link.yaml").read_text(encoding="utf-8")
            workspace = (project / ".agent-os" / "workspace.yaml").read_text(encoding="utf-8")
            self.assertIn(f"governance_root: {desired_governance}", fabric)
            self.assertIn(f"capability_root: {desired_capability}", fabric)
            self.assertIn(f"governance_root: {desired_governance}", workspace)
            self.assertIn(f"capability_root: {desired_capability}", workspace)
            upgraded_router = router.read_text(encoding="utf-8")
            self.assertIn("context-pack --project-root .", upgraded_router)
            self.assertIn("verify-lifecycle --project-root .", upgraded_router)
            self.assertIn("archive/**", write_policy.read_text(encoding="utf-8"))
            doctor = self.run_cli("doctor", "--root", str(ROOT), "--project-root", str(project), "--summary")
            self.assertIn("status: ok", doctor.stdout)

    def test_doctor_keeps_pre_gate_completed_runs_legacy_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "KnowledgeOSRuntime"
            self.run_cli("init-os", "--root", str(ROOT), "--os-root", str(runtime), "--json")
            project = Path(tmp) / "LegacyProject"
            project.mkdir()
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Legacy",
                "--global-root",
                str(runtime / "global-agent-fabric"),
                "--capability-root",
                str(runtime / "capability-layer"),
            )
            run_id = "RUN-20260510-000000-T001"
            run_dir = project / ".agent-os" / "runs" / run_id
            run_dir.mkdir(parents=True)
            (run_dir / "run.yaml").write_text(
                "\n".join(
                    [
                        f"run_id: {run_id}",
                        "task_id: T001",
                        "task_title: Legacy run",
                        "task_type: initialization",
                        "status: completed",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "eval.md").write_text("# Eval\n\nGenerated By: knowledgeos eval-task\nStatus: passed\n", encoding="utf-8")

            legacy = self.run_cli("doctor", "--project-root", str(project), "--project-only", "--json")
            legacy_payload = json.loads(legacy.stdout)
            self.assertTrue(all(item["ok"] for item in legacy_payload), legacy_payload)
            self.assertTrue(any("legacy run predates phase ledger" in item["detail"] for item in legacy_payload))

            (run_dir / "command-events.ndjson").write_text(
                json.dumps({"event_type": "run-task", "task_id": "T001", "run_id": run_id}) + "\n",
                encoding="utf-8",
            )
            new_gate = self.run_cli("doctor", "--project-root", str(project), "--project-only", "--json", check=False)
            self.assertNotEqual(new_gate.returncode, 0)
            labels = [item["label"] for item in json.loads(new_gate.stdout) if not item["ok"]]
            self.assertIn("completed_run_lifecycle", labels)
            self.assertIn("completed_run_context", labels)

    def test_deep_doctor_command_is_removed(self):
        help_result = self.run_cli("--help", check=False)
        self.assertEqual(help_result.returncode, 0)
        self.assertNotIn("deep-doctor", help_result.stdout)
        result = self.run_cli("deep-doctor", "--project-root", str(ROOT), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_workbench_state_reports_managed_project_with_redacted_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            runtime = Path(tmp) / "KnowledgeOSRuntime"
            self.run_cli("init-os", "--root", str(ROOT), "--os-root", str(runtime), "--json")
            global_root = runtime / "global-agent-fabric"
            capability_root = runtime / "capability-layer"
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example Project",
                "--global-root",
                str(global_root),
                "--capability-root",
                str(capability_root),
            )

            result = self.run_cli("workbench-state", "--project-root", str(project), "--json")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], "knowledgeos.workbench-state.v1")
            self.assertTrue(payload["managed"])
            self.assertEqual(payload["status"], "managed_ok")
            self.assertEqual(payload["boot"]["claim"], "BOOT_OK")
            self.assertEqual(payload["project_root"], "<PROJECT_ROOT>")
            self.assertEqual(payload["workspace"]["root"], "<PROJECT_ROOT>")
            self.assertNotIn(str(project), result.stdout)
            self.assertIn("tasks", payload)
            self.assertIn("capabilities", payload)
            self.assertIn("runtime_adapters", payload)
            self.assertEqual(payload["runtime_adapters"]["schema_version"], "knowledgeos.runtime-adapters.v1")

            visible = self.run_cli("workbench-state", "--project-root", str(project), "--show-paths", "--json")
            visible_payload = json.loads(visible.stdout)
            self.assertEqual(visible_payload["project_root"], str(project.resolve()))
            self.assertFalse(visible_payload["privacy"]["paths_redacted"])

    def test_workbench_lifecycle_reports_read_only_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")

            result = self.run_cli(
                "workbench-lifecycle",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--json",
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], "knowledgeos.workbench-lifecycle.v1")
            self.assertTrue(payload["managed"])
            self.assertEqual(payload["status"], "attention")
            self.assertEqual(payload["project_root"], "<PROJECT_ROOT>")
            self.assertEqual(payload["selected_task"]["id"], "T001")
            self.assertEqual(
                [stage["key"] for stage in payload["stages"]],
                ["doctor", "route", "dispatch", "write_guard", "run", "eval", "receipt"],
            )
            self.assertEqual(payload["stages"][0]["status"], "blocked")
            self.assertEqual(payload["next_action"]["key"], "doctor")
            self.assertNotIn(str(project), result.stdout)

            visible = self.run_cli(
                "workbench-lifecycle",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--show-paths",
                "--json",
                check=False,
            )
            self.assertEqual(json.loads(visible.stdout)["project_root"], str(project.resolve()))

    def test_workbench_state_reports_unmanaged_without_boot_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "LooseFolder"
            project.mkdir()
            result = self.run_cli("workbench-state", "--project-root", str(project), "--json")
            payload = json.loads(result.stdout)
            self.assertFalse(payload["managed"])
            self.assertEqual(payload["status"], "unmanaged")
            self.assertEqual(payload["boot"]["claim"], "KOS_UNMANAGED")
            self.assertEqual(payload["system_black_box"]["doctor"]["status"], "not_run")
            self.assertNotIn(str(project), result.stdout)

    def test_ask_sandbox_is_read_only_and_redacts_project_paths(self):
        result = self.run_cli(
            "ask-sandbox",
            "--project-root",
            str(ROOT),
            "--prompt",
            f"Please inspect {ROOT} and create a concise report.",
            "--json",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "knowledgeos.ask-sandbox.v1")
        self.assertEqual(payload["mode"], "read_only_sandbox")
        self.assertEqual(payload["runtime"], "mock")
        self.assertFalse(payload["executed"])
        self.assertFalse(payload["project_mutation"])
        self.assertEqual(payload["recommended_next_step"], "route_through_os")
        self.assertIn("<PROJECT_ROOT>", payload["prompt"])
        self.assertNotIn(str(ROOT), result.stdout)
        self.assertFalse(payload["system_black_box"]["writes_allowed"])

        plain = self.run_cli(
            "ask-sandbox",
            "--project-root",
            str(ROOT),
            "--prompt",
            "Explain the current task without changing files.",
        )
        self.assertIn("recommended_next_step: stay_in_sandbox", plain.stdout)
        self.assertIn("executed: false", plain.stdout)

    def test_runtime_adapters_reports_readiness_without_execution(self):
        result = self.run_cli("runtime-adapters", "--project-root", str(ROOT), "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "knowledgeos.runtime-adapters.v1")
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["policy"]["default_runtime"], "mock")
        self.assertEqual(payload["policy"]["real_cli_execution"], "disabled_until_adapter_phase")
        self.assertFalse(payload["policy"]["project_mutation_allowed"])
        adapters = {item["id"]: item for item in payload["adapters"]}
        self.assertEqual(adapters["mock"]["status"], "available")
        self.assertFalse(adapters["mock"]["project_mutation"])
        self.assertEqual(adapters["mock"]["execution"], "not_started")
        self.assertIn("gemini-cli", adapters)
        self.assertIn("codex-cli", adapters)
        self.assertNotIn(str(ROOT), result.stdout)
        self.assertNotRegex(result.stdout, r"/usr/|/opt/|/Users/")

        plain = self.run_cli("runtime-adapters", "--project-root", str(ROOT))
        self.assertIn("default_runtime: mock", plain.stdout)
        self.assertIn("real_cli_execution: disabled_until_adapter_phase", plain.stdout)

    def test_init_project_preserves_existing_agents_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            global_root = Path(tmp) / "global-agent-fabric"
            capability_root = Path(tmp) / "capability-layer"
            global_root.mkdir()
            capability_root.mkdir()
            existing = project / "AGENTS.md"
            existing.write_text("existing rules\n", encoding="utf-8")
            result = self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example Project",
                "--global-root",
                str(global_root),
                "--capability-root",
                str(capability_root),
                "--json",
            )
            actions = json.loads(result.stdout)
            self.assertIn("skip", {item["action"] for item in actions})
            self.assertEqual(existing.read_text(encoding="utf-8"), "existing rules\n")
            workspace = project / ".agent-os" / "workspace.yaml"
            self.assertTrue(workspace.exists())
            text = workspace.read_text(encoding="utf-8")
            self.assertIn("Example Project", text)
            self.assertIn(str(global_root), text)
            self.assertNotIn("Example Project_GLOBAL_AGENT_FABRIC_ROOT", text)

    def test_init_os_creates_minimal_kernel_and_project_can_mount_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "KnowledgeOSRuntime"
            init_os = self.run_cli("init-os", "--root", str(ROOT), "--os-root", str(runtime), "--json")
            actions = json.loads(init_os.stdout)
            self.assertTrue(any(item.get("action") == "ready" for item in actions))

            global_root = runtime / "global-agent-fabric"
            capability_root = runtime / "capability-layer"
            self.assertTrue((global_root / "hooks" / "before-task.sh").exists())
            self.assertTrue(os.access(global_root / "hooks" / "before-task.sh", os.X_OK))
            self.assertTrue((global_root / "rules" / "global.md").exists())
            self.assertTrue((global_root / "sync" / "receipts.ndjson").exists())
            self.assertTrue((capability_root / "README.md").exists())

            boot = subprocess.run(
                [str(global_root / "hooks" / "before-task.sh")],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(boot.returncode, 0, boot.stderr)
            self.assertIn("[BOOT_OK]", boot.stdout)

            phase = subprocess.run(
                [str(global_root / "hooks" / "log-phase.sh"), "route", "test route"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(phase.returncode, 0, phase.stderr)
            self.assertIn("[PHASE_OK]", phase.stdout)

            postflight = subprocess.run(
                [str(global_root / "hooks" / "after-task.sh"), "test postflight"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(postflight.returncode, 0, postflight.stderr)
            self.assertIn("[SYNC_OK]", postflight.stdout)

            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example",
                "--global-root",
                str(global_root),
                "--capability-root",
                str(capability_root),
            )
            doctor = self.run_cli("doctor", "--project-root", str(project), "--project-only", "--json")
            payload = json.loads(doctor.stdout)
            self.assertTrue(all(item["ok"] for item in payload), payload)

    def test_check_write_classifies_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")

            allowed = self.run_cli("check-write", "--project-root", str(project), "--path", "src/main.py", "--json")
            self.assertEqual(json.loads(allowed.stdout)["decision"], "allow")

            immutable = self.run_cli(
                "check-write", "--project-root", str(project), "--path", "materials/raw/input.pdf", "--json", check=False
            )
            self.assertEqual(immutable.returncode, 2)
            self.assertEqual(json.loads(immutable.stdout)["decision"], "deny")

            gated = self.run_cli(
                "check-write", "--project-root", str(project), "--path", "reports/final/report.md", "--json", check=False
            )
            self.assertEqual(gated.returncode, 2)
            self.assertEqual(json.loads(gated.stdout)["decision"], "human_gate_required")

            unclassified = self.run_cli("check-write", "--project-root", str(project), "--path", "scratch.txt", "--json")
            self.assertEqual(json.loads(unclassified.stdout)["decision"], "unclassified")

            strict = self.run_cli(
                "check-write", "--project-root", str(project), "--path", "scratch.txt", "--strict", "--json", check=False
            )
            self.assertEqual(strict.returncode, 2)

            archive_root = self.run_cli("check-write", "--project-root", str(project), "--path", "archive/", "--json")
            self.assertEqual(json.loads(archive_root.stdout)["decision"], "allow")

    def test_run_task_creates_run_envelope_and_latest_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            result = self.run_cli(
                "run-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--summary",
                "Start initialization.",
                "--json",
            )
            payload = json.loads(result.stdout)
            run_id = payload["run_id"]
            run_dir = project / ".agent-os" / "runs" / run_id
            self.assertTrue((run_dir / "run.yaml").exists())
            self.assertTrue((run_dir / "receipt.md").exists())
            run_yaml = (run_dir / "run.yaml").read_text(encoding="utf-8")
            self.assertIn("route_status: routed", run_yaml)
            self.assertIn("eval_profile: workspace_initialization", run_yaml)
            latest = project / ".agent-os" / "receipts" / "latest.md"
            self.assertIn(run_id, latest.read_text(encoding="utf-8"))

    def test_check_route_write_enforces_route_allowed_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")

            allowed = self.run_cli(
                "check-route-write",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--path",
                ".agent-os/workspace.yaml",
                "--json",
            )
            payload = json.loads(allowed.stdout)
            self.assertEqual(payload["decision"], "allow")
            self.assertEqual(payload["route_status"], "allowed_by_route")

            out_of_route = self.run_cli(
                "check-route-write",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--path",
                "src/main.py",
                "--json",
                check=False,
            )
            self.assertEqual(out_of_route.returncode, 2)
            self.assertEqual(json.loads(out_of_route.stdout)["decision"], "route_output_denied")

            immutable = self.run_cli(
                "check-route-write",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--path",
                "materials/raw/source.pdf",
                "--json",
                check=False,
            )
            self.assertEqual(immutable.returncode, 2)
            self.assertEqual(json.loads(immutable.stdout)["decision"], "deny")

            direct_evidence_write = self.run_cli(
                "check-route-write",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--path",
                ".agent-os/runs/RUN-FAKE/phases.ndjson",
                "--json",
                check=False,
            )
            self.assertEqual(direct_evidence_write.returncode, 2)
            self.assertEqual(json.loads(direct_evidence_write.stdout)["decision"], "human_gate_required")

            direct_capability_write = self.run_cli(
                "check-route-write",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--path",
                ".agent-os/runs/RUN-FAKE/capability-events.ndjson",
                "--json",
                check=False,
            )
            self.assertEqual(direct_capability_write.returncode, 2)
            self.assertEqual(json.loads(direct_capability_write.stdout)["decision"], "human_gate_required")

            for guarded_control_path in [
                ".agent-os/tasks.yaml",
                ".agent-os/evals.yaml",
                ".agent-os/write-policy.yaml",
                ".agent-os/workflows/router.yaml",
            ]:
                guarded = self.run_cli(
                    "check-route-write",
                    "--project-root",
                    str(project),
                    "--task-id",
                    "T001",
                    "--path",
                    guarded_control_path,
                    "--json",
                    check=False,
                )
                self.assertEqual(guarded.returncode, 2)
                guarded_payload = json.loads(guarded.stdout)
                self.assertEqual(guarded_payload["decision"], "human_gate_required")

    def test_archive_management_route_allows_archive_root_check(self):
        result = self.run_cli(
            "check-route-write",
            "--project-root",
            str(ROOT),
            "--task-id",
            "KOS-T014",
            "--path",
            "archive/",
            "--json",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["decision"], "allow")
        self.assertEqual(payload["route_status"], "allowed_by_route")

    def test_run_task_requires_routed_ready_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            tasks_path = project / ".agent-os" / "tasks.yaml"
            tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: ready", "status: backlog", 1), encoding="utf-8")
            blocked = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", check=False)
            self.assertEqual(blocked.returncode, 1)
            self.assertIn("expected one of", blocked.stderr)

            tasks_path.write_text(
                tasks_path.read_text(encoding="utf-8")
                + "\n  - id: T999\n    title: Unknown work\n    type: unknown_type\n    status: ready\n",
                encoding="utf-8",
            )
            unrouted = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T999", check=False)
            self.assertEqual(unrouted.returncode, 1)
            self.assertIn("routing failed", unrouted.stderr)

    def test_create_task_assigns_unique_ids_and_routes_unknown_type_to_triage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            tasks_path = project / ".agent-os" / "tasks.yaml"
            tasks_path.write_text(
                "tasks:\n"
                "  - id: T001\n"
                "    title: Existing initialization\n"
                "    type: initialization\n"
                "    status: completed\n"
                "    outputs:\n"
                "      - .agent-os/workspace.yaml\n",
                encoding="utf-8",
            )

            created = self.run_cli(
                "create-task",
                "--project-root",
                str(project),
                "--title",
                "Draft new work",
                "--type",
                "unregistered_task_type",
                "--output",
                "docs/new-work.md",
                "--acceptance",
                "new task can be routed or triaged",
                "--json",
            )
            payload = json.loads(created.stdout)
            self.assertEqual(payload["task_id"], "T002")
            self.assertEqual(payload["status"], "ready")
            self.assertIn("id: T002", tasks_path.read_text(encoding="utf-8"))

            route = self.run_cli(
                "route-task",
                "--project-root",
                str(project),
                "--task-id",
                "T002",
                "--json",
                check=False,
            )
            self.assertEqual(route.returncode, 2)
            self.assertEqual(json.loads(route.stdout)["status"], "human_triage_required")

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "KosProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Kos")
            tasks_path = project / ".agent-os" / "tasks.yaml"
            tasks_path.write_text(
                "tasks:\n"
                "  - id: KOS-T022\n"
                "    title: Existing KnowledgeOS task\n"
                "    type: initialization\n"
                "    status: completed\n"
                "    outputs:\n"
                "      - .agent-os/workspace.yaml\n",
                encoding="utf-8",
            )
            created = self.run_cli(
                "create-task",
                "--project-root",
                str(project),
                "--title",
                "Follow up task",
                "--type",
                "initialization",
                "--output",
                ".agent-os/project.yaml",
                "--acceptance",
                "new task can be routed",
                "--json",
            )
            self.assertEqual(json.loads(created.stdout)["task_id"], "KOS-T023")
            routed = self.run_cli("route-task", "--project-root", str(project), "--task-id", "KOS-T023", "--json")
            self.assertEqual(json.loads(routed.stdout)["status"], "routed")

    def test_create_task_requires_output_and_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            missing_output = self.run_cli(
                "create-task",
                "--project-root",
                str(project),
                "--title",
                "No output",
                "--type",
                "initialization",
                "--acceptance",
                "must have output",
                check=False,
            )
            self.assertNotEqual(missing_output.returncode, 0)
            self.assertIn("--output", missing_output.stderr)

            missing_acceptance = self.run_cli(
                "create-task",
                "--project-root",
                str(project),
                "--title",
                "No acceptance",
                "--type",
                "initialization",
                "--output",
                ".agent-os/project.yaml",
                check=False,
            )
            self.assertNotEqual(missing_acceptance.returncode, 0)
            self.assertIn("--acceptance", missing_acceptance.stderr)

    def test_create_spec_aligns_and_context_plan_are_verifiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")

            created = self.run_cli(
                "create-spec",
                "--project-root",
                str(project),
                "--title",
                "Grant writing operating spec",
                "--intent",
                "Keep user intent, non-goals, and acceptance visible before execution.",
                "--acceptance",
                "context pack includes active spec snapshot",
                "--non-goal",
                "do not store hidden chain-of-thought",
                "--json",
            )
            spec_payload = json.loads(created.stdout)
            spec_id = spec_payload["spec_id"]
            self.assertTrue((project / ".agent-os" / "specs" / spec_id / "spec.md").exists())
            self.assertIn(f"active_spec: {spec_id}", (project / ".agent-os" / "specs.yaml").read_text(encoding="utf-8"))

            aligned = self.run_cli("align-spec", "--project-root", str(project), "--task-id", "T001", "--json")
            self.assertEqual(json.loads(aligned.stdout)["status"], "aligned")

            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            run_dir = project / ".agent-os" / "runs" / run_id
            snapshot = (run_dir / "spec-snapshot.md").read_text(encoding="utf-8")
            context = (run_dir / "context-pack.md").read_text(encoding="utf-8")
            self.assertIn(f"Spec ID: {spec_id}", snapshot)
            self.assertIn("Generated By: knowledgeos context-pack", context)

            self.run_cli(
                "plan-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Use the active spec snapshot before execution.",
            )
            verified = self.run_cli("verify-context", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id, "--json")
            self.assertEqual(json.loads(verified.stdout)["status"], "passed")

    def test_complete_task_requires_plan_context_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            self.run_cli("eval-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id)
            self.log_required_phases(project, "T001", run_id)

            blocked = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Should fail without plan-task.",
                "--allow-pending-postflight",
                "temp project has no executable shared-fabric hook",
                check=False,
            )
            self.assertEqual(blocked.returncode, 1)
            self.assertIn("missing_plan", blocked.stderr)
            self.assertIn("plan-task command evidence", blocked.stderr)

    def test_spec_drift_blocks_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            created = self.run_cli(
                "create-spec",
                "--project-root",
                str(project),
                "--title",
                "Stable spec",
                "--intent",
                "This spec should not drift silently after run context is created.",
                "--json",
            )
            spec_id = json.loads(created.stdout)["spec_id"]
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            self.write_plan_context(project, "T001", run_id)
            self.run_cli("eval-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id)
            self.log_required_phases(project, "T001", run_id)
            spec_path = project / ".agent-os" / "specs" / spec_id / "spec.md"
            spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\nSilent drift.\n", encoding="utf-8")

            result = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Should fail after spec drift.",
                "--allow-pending-postflight",
                "temp project has no executable shared-fabric hook",
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("spec_drift", result.stderr)

    def test_direct_spec_context_and_plan_writes_are_human_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            for guarded_path in [
                ".agent-os/specs.yaml",
                ".agent-os/specs/SPEC-FAKE/spec.md",
                ".agent-os/runs/RUN-FAKE/context-pack.md",
                ".agent-os/runs/RUN-FAKE/spec-snapshot.md",
                ".agent-os/runs/RUN-FAKE/plan.md",
            ]:
                result = self.run_cli(
                    "check-route-write",
                    "--project-root",
                    str(project),
                    "--task-id",
                    "T001",
                    "--path",
                    guarded_path,
                    "--json",
                    check=False,
                )
                self.assertEqual(result.returncode, 2, guarded_path)
                self.assertEqual(json.loads(result.stdout)["decision"], "human_gate_required")

    def test_complete_task_requires_passed_eval_and_updates_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            started = self.run_cli(
                "run-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--summary",
                "Run guarded completion.",
                "--json",
            )
            run_id = json.loads(started.stdout)["run_id"]

            unsafe_run = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                "../escape",
                "--summary",
                "Should fail.",
                check=False,
            )
            self.assertEqual(unsafe_run.returncode, 1)
            self.assertIn("run_id must not contain path separators", unsafe_run.stderr)

            missing_eval = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Should fail.",
                check=False,
            )
            self.assertEqual(missing_eval.returncode, 1)
            self.assertIn("Status: passed", missing_eval.stderr)

            run_dir = project / ".agent-os" / "runs" / run_id
            (run_dir / "eval.md").write_text("# Eval\n\nStatus: passed\n", encoding="utf-8")
            manual_eval = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Should fail.",
                check=False,
            )
            self.assertEqual(manual_eval.returncode, 1)
            self.assertIn("eval-task", manual_eval.stderr)

            eval_result = self.run_cli(
                "eval-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--json",
            )
            self.assertEqual(json.loads(eval_result.stdout)["status"], "passed")
            self.log_required_phases(project, "T001", run_id)
            self.write_plan_context(project, "T001", run_id)
            completed = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Guarded task complete.",
                "--allow-pending-postflight",
                "temporary project does not configure an executable postflight hook",
                "--json",
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["sync_status"], "PENDING")
            self.assertIn("status: completed", (run_dir / "run.yaml").read_text(encoding="utf-8"))
            self.assertIn("status: completed", (project / ".agent-os" / "tasks.yaml").read_text(encoding="utf-8"))
            self.assertIn("Guarded task complete", (project / ".agent-os" / "receipts" / "latest.md").read_text(encoding="utf-8"))

    def test_complete_task_requires_lifecycle_phases(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            self.run_cli("eval-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id)

            blocked = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Should fail before lifecycle.",
                check=False,
            )
            self.assertEqual(blocked.returncode, 1)
            self.assertIn("lifecycle", blocked.stderr)

            self.log_required_phases(project, "T001", run_id)
            verified = self.run_cli(
                "verify-lifecycle",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--json",
            )
            self.assertEqual(json.loads(verified.stdout)["status"], "passed")

    def test_phase_task_requires_skip_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]

            missing_reason = self.run_cli(
                "phase-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--phase",
                "review",
                "--status",
                "skipped",
                "--note",
                "Skip without reason should fail.",
                check=False,
            )
            self.assertEqual(missing_reason.returncode, 1)
            self.assertIn("skip reason", missing_reason.stderr)

            self.run_cli(
                "phase-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--phase",
                "review",
                "--status",
                "skipped",
                "--note",
                "Skipped after human-approved simplification.",
                "--skip-reason",
                "human approved skipping review in this test",
            )
            verify = self.run_cli(
                "verify-lifecycle",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--json",
                check=False,
            )
            self.assertEqual(verify.returncode, 2)
            self.assertIn("missing_phases", verify.stdout)

    def test_phase_task_outputs_visible_checkpoint_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]

            plain = self.run_cli(
                "phase-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--phase",
                "route",
                "--status",
                "completed",
                "--note",
                "Route decision recorded.",
                "--evidence",
                "unit test",
            )
            self.assertIn("CHECKPOINT_OK phase=route status=completed evidence=unit test", plain.stdout)

            as_json = self.run_cli(
                "phase-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--phase",
                "plan",
                "--status",
                "completed",
                "--note",
                "Plan decision recorded.",
                "--evidence",
                "unit test json",
                "--json",
            )
            payload = json.loads(as_json.stdout)
            self.assertEqual(payload["checkpoint_marker"], "CHECKPOINT_OK")
            self.assertIn("CHECKPOINT_OK phase=plan", payload["marker"])

    def test_capability_event_records_visible_capability_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]

            result = self.run_cli(
                "capability-event",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--kind",
                "orchestrator",
                "--id",
                "maestro",
                "--purpose",
                "Record orchestrator decision trace for test.",
                "--evidence",
                "unit test",
            )
            self.assertIn("CAPABILITY_OK kind=orchestrator id=maestro purpose=Record orchestrator decision trace for test.", result.stdout)
            run_dir = project / ".agent-os" / "runs" / run_id
            self.assertIn('"event_type": "capability-event"', (run_dir / "command-events.ndjson").read_text(encoding="utf-8"))
            self.assertIn('"kind": "orchestrator"', (run_dir / "capability-events.ndjson").read_text(encoding="utf-8"))

    def test_lifecycle_requires_dispatch_and_required_capability_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            for phase in ["route", "plan", "review", "dispatch", "execute", "report"]:
                self.run_cli(
                    "phase-task",
                    "--project-root",
                    str(project),
                    "--task-id",
                    "T001",
                    "--run-id",
                    run_id,
                    "--phase",
                    phase,
                    "--status",
                    "completed",
                    "--note",
                    f"Recorded {phase}.",
                    "--evidence",
                    f"test {phase}",
                )

            missing_dispatch = self.run_cli(
                "verify-lifecycle",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--json",
                check=False,
            )
            self.assertEqual(missing_dispatch.returncode, 2)
            self.assertIn("missing_dispatch_command_event", missing_dispatch.stdout)

            self.run_cli("dispatch-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id, "--json")
            missing_capability = self.run_cli(
                "verify-lifecycle",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--json",
                check=False,
            )
            self.assertEqual(missing_capability.returncode, 2)
            self.assertIn("missing_required_capability_event", missing_capability.stdout)

            self.run_cli(
                "capability-event",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--kind",
                "orchestrator",
                "--id",
                "maestro",
                "--purpose",
                "Required orchestration decision trace for initialization.",
            )
            verified = self.run_cli(
                "verify-lifecycle",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--json",
            )
            self.assertEqual(json.loads(verified.stdout)["status"], "passed")

    def test_complete_task_requires_postflight_or_records_pending_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            self.log_required_phases(project, "T001", run_id)
            self.run_cli("eval-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id)
            self.write_plan_context(project, "T001", run_id)

            blocked = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Should fail without postflight.",
                "--json",
                check=False,
            )
            self.assertEqual(blocked.returncode, 1)
            self.assertIn("postflight", blocked.stderr)

            completed = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Completed with explicit pending postflight.",
                "--allow-pending-postflight",
                "temp project has no executable shared-fabric hook",
                "--json",
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["sync_status"], "PENDING")
            receipt = (project / ".agent-os" / "receipts" / "latest.md").read_text(encoding="utf-8")
            self.assertIn("Pending Postflight", receipt)
            self.assertIn("temp project has no executable shared-fabric hook", receipt)

    def test_complete_task_runs_postflight_hook_when_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "KnowledgeOSRuntime"
            self.run_cli("init-os", "--root", str(ROOT), "--os-root", str(runtime), "--json")
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example",
                "--global-root",
                str(runtime / "global-agent-fabric"),
                "--capability-root",
                str(runtime / "capability-layer"),
            )
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            self.log_required_phases(project, "T001", run_id)
            self.run_cli("eval-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id)
            self.write_plan_context(project, "T001", run_id)
            completed = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Completed with real postflight hook.",
                "--json",
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["sync_status"], "SYNC_OK")
            self.assertEqual(payload["status_marker"], "[SYNC_OK]")
            self.assertIn("[SYNC_OK]", (project / ".agent-os" / "runs" / run_id / "postflight.md").read_text(encoding="utf-8"))

    def test_template_postflight_does_not_dirty_public_template_ledgers(self):
        receipts = ROOT / "templates" / "governance-core" / "sync" / "receipts.ndjson"
        handoffs = ROOT / "templates" / "governance-core" / "memory" / "handoffs.ndjson"
        before_receipts = receipts.read_text(encoding="utf-8")
        before_handoffs = handoffs.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example",
                "--global-root",
                str(ROOT / "templates" / "governance-core"),
                "--capability-root",
                str(ROOT / "templates" / "capability-layer"),
            )
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            self.log_required_phases(project, "T001", run_id)
            self.run_cli("eval-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id)
            self.write_plan_context(project, "T001", run_id)
            completed = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Template hook should not dirty public ledgers.",
                "--json",
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["sync_status"], "SYNC_OK")
            self.assertTrue((project / ".agent-os" / "runs" / run_id / "kernel-postflight" / "sync" / "receipts.ndjson").exists())
        self.assertEqual(receipts.read_text(encoding="utf-8"), before_receipts)
        self.assertEqual(handoffs.read_text(encoding="utf-8"), before_handoffs)

    def test_manual_eval_marker_without_eval_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "KnowledgeOSRuntime"
            self.run_cli("init-os", "--root", str(ROOT), "--os-root", str(runtime), "--json")
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example",
                "--global-root",
                str(runtime / "global-agent-fabric"),
                "--capability-root",
                str(runtime / "capability-layer"),
            )
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            self.log_required_phases(project, "T001", run_id)
            run_dir = project / ".agent-os" / "runs" / run_id
            (run_dir / "eval.md").write_text("# Eval\n\nGenerated By: knowledgeos eval-task\nStatus: passed\n", encoding="utf-8")
            result = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Forged eval should fail.",
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("matching `knowledgeos eval-task` command evidence", result.stderr)

    def test_direct_phase_ledger_forgery_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "KnowledgeOSRuntime"
            self.run_cli("init-os", "--root", str(ROOT), "--os-root", str(runtime), "--json")
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example",
                "--global-root",
                str(runtime / "global-agent-fabric"),
                "--capability-root",
                str(runtime / "capability-layer"),
            )
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            run_dir = project / ".agent-os" / "runs" / run_id
            self.run_cli("eval-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id)
            with (run_dir / "phases.ndjson").open("w", encoding="utf-8") as handle:
                for phase in ["route", "plan", "review", "dispatch", "execute", "report"]:
                    handle.write(
                        json.dumps(
                            {
                                "task_id": "T001",
                                "run_id": run_id,
                                "phase": phase,
                                "status": "completed",
                                "note": "forged direct write",
                                "evidence": "none",
                                "skip_reason": "",
                                "timestamp": "2026-05-12T00:00:00+00:00",
                            }
                        )
                        + "\n"
                    )
            result = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Forged phases should fail.",
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing_phase_command_events", result.stderr)

    def test_weakened_phase_policy_is_rejected_at_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "KnowledgeOSRuntime"
            self.run_cli("init-os", "--root", str(ROOT), "--os-root", str(runtime), "--json")
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example",
                "--global-root",
                str(runtime / "global-agent-fabric"),
                "--capability-root",
                str(runtime / "capability-layer"),
            )
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            self.run_cli("eval-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id)
            (project / ".agent-os" / "phase-policy.yaml").write_text(
                "required_phases:\n  default:\n\nskip_policy:\n  require_skip_reason: true\n",
                encoding="utf-8",
            )
            result = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Weak policy should fail.",
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("invalid_phase_policy", result.stderr)

    def test_postflight_required_cannot_be_disabled_by_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "KnowledgeOSRuntime"
            self.run_cli("init-os", "--root", str(ROOT), "--os-root", str(runtime), "--json")
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example",
                "--global-root",
                str(runtime / "global-agent-fabric"),
                "--capability-root",
                str(runtime / "capability-layer"),
            )
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            self.log_required_phases(project, "T001", run_id)
            self.run_cli("eval-task", "--project-root", str(project), "--task-id", "T001", "--run-id", run_id)
            self.write_plan_context(project, "T001", run_id)
            fabric = project / ".agent-os" / "fabric-link.yaml"
            fabric.write_text(fabric.read_text(encoding="utf-8").replace("postflight_required: true", "postflight_required: false"), encoding="utf-8")
            result = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--run-id",
                run_id,
                "--summary",
                "Disabled postflight should fail.",
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("postflight_required: true", result.stderr)

    def test_eval_and_complete_require_declared_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            tasks_path = project / ".agent-os" / "tasks.yaml"
            tasks_path.write_text(
                tasks_path.read_text(encoding="utf-8")
                + "\n  - id: T777\n"
                + "    title: Missing output task\n"
                + "    type: initialization\n"
                + "    status: ready\n"
                + "    outputs:\n"
                + "      - docs/missing.md\n",
                encoding="utf-8",
            )
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T777", "--json")
            run_id = json.loads(started.stdout)["run_id"]
            eval_result = self.run_cli(
                "eval-task",
                "--project-root",
                str(project),
                "--task-id",
                "T777",
                "--run-id",
                run_id,
                "--json",
                check=False,
            )
            self.assertEqual(eval_result.returncode, 2)
            self.assertEqual(json.loads(eval_result.stdout)["status"], "failed")
            run_dir = project / ".agent-os" / "runs" / run_id
            (run_dir / "eval.md").write_text("# Eval\n\nGenerated By: knowledgeos eval-task\nStatus: passed\n", encoding="utf-8")
            complete_result = self.run_cli(
                "complete-task",
                "--project-root",
                str(project),
                "--task-id",
                "T777",
                "--run-id",
                run_id,
                "--summary",
                "Should fail.",
                "--allow-manual-eval",
                "--override-reason",
                "test isolates declared output completion gate",
                check=False,
            )
            self.assertEqual(complete_result.returncode, 1)
            self.assertIn("declared task outputs are missing", complete_result.stderr)

    def test_receipt_writes_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            result = self.run_cli(
                "receipt",
                "--project-root",
                str(project),
                "--receipt-id",
                "R001",
                "--summary",
                "Manual receipt.",
                "--json",
            )
            payload = json.loads(result.stdout)
            self.assertTrue(Path(payload["path"]).exists())
            self.assertIn("Manual receipt", (project / ".agent-os" / "receipts" / "latest.md").read_text(encoding="utf-8"))

    def test_doctor_passes_initialized_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            runtime = Path(tmp) / "KnowledgeOSRuntime"
            self.run_cli("init-os", "--root", str(ROOT), "--os-root", str(runtime), "--json")
            global_root = runtime / "global-agent-fabric"
            capability_root = runtime / "capability-layer"
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example",
                "--global-root",
                str(global_root),
                "--capability-root",
                str(capability_root),
            )
            result = self.run_cli("doctor", "--project-root", str(project), "--project-only", "--json")
            payload = json.loads(result.stdout)
            self.assertTrue(all(item["ok"] for item in payload), payload)
            self.assertTrue(any(item["label"] == "phase_keys" for item in payload))
            self.assertTrue(any(item["label"] == "workflow_router" for item in payload))
            self.assertTrue(any(item["label"] == "tool_registry" for item in payload))

    def test_doctor_rejects_router_without_eval_task_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            global_root = Path(tmp) / "global-agent-fabric"
            capability_root = Path(tmp) / "capability-layer"
            global_root.mkdir()
            capability_root.mkdir()
            self.run_cli(
                "init-project",
                "--root",
                str(ROOT),
                "--project-root",
                str(project),
                "--name",
                "Example",
                "--global-root",
                str(global_root),
                "--capability-root",
                str(capability_root),
            )
            router = project / ".agent-os" / "workflows" / "router.yaml"
            router.write_text("\n".join(line for line in router.read_text(encoding="utf-8").splitlines() if "eval-task" not in line) + "\n", encoding="utf-8")
            result = self.run_cli("doctor", "--project-root", str(project), "--project-only", "--json", check=False)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertTrue(any(item["label"] == "workflow_router_lifecycle" and not item["ok"] for item in payload))

    def test_doctor_detects_unresolved_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            result = self.run_cli("doctor", "--project-root", str(project), "--project-only", "--json", check=False)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertTrue(any(item["label"] == "placeholders" and not item["ok"] for item in payload))
            self.assertTrue(any(item["label"] == "fabric_link" and not item["ok"] for item in payload))

    def test_reopen_task_archives_outputs_and_requires_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            output = project / ".agent-os" / "workspace.yaml"
            result = self.run_cli(
                "reopen-task",
                "--project-root",
                str(project),
                "--task-id",
                "T001",
                "--reason",
                "rerun initialization",
                "--archive-outputs",
                "--json",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ready")
            self.assertTrue(output.exists(), "control-plane outputs should be protected from output cleanup")
            self.assertIn("rerun initialization", (project / ".agent-os" / "receipts" / "latest.md").read_text(encoding="utf-8"))

    def test_reset_project_soft_and_hard_modes_are_reversible_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            started = self.run_cli("run-task", "--project-root", str(project), "--task-id", "T001", "--json")
            self.assertTrue((project / ".agent-os" / "runs" / json.loads(started.stdout)["run_id"]).exists())

            soft = self.run_cli("reset-project", "--project-root", str(project), "--mode", "soft", "--json")
            soft_payload = json.loads(soft.stdout)
            self.assertEqual(soft_payload["mode"], "soft")
            self.assertTrue((project / ".agent-os").exists())
            self.assertFalse((project / ".agent-os" / "runs").exists())
            self.assertTrue((project / ".knowledgeos-reset-backups").exists())

            hard = self.run_cli("reset-project", "--project-root", str(project), "--mode", "hard", "--json")
            hard_payload = json.loads(hard.stdout)
            self.assertEqual(hard_payload["mode"], "hard")
            self.assertFalse((project / ".agent-os").exists())
            self.assertTrue((project / ".knowledgeos-reset-backups").exists())

    def test_migrate_legacy_project_writes_plan_and_applies_safe_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "LegacyProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Legacy")
            (project / "前期材料").mkdir()
            (project / "code").mkdir()
            (project / "capability-layer").mkdir()
            (project / "global-agent-fabric").mkdir()
            (project / "loose_note.md").write_text("note\n", encoding="utf-8")
            plan = self.run_cli("migrate-legacy-project", "--project-root", str(project), "--write-plan", "--json")
            payload = json.loads(plan.stdout)
            targets = {item["target"] for item in payload["plan"]}
            sources = {item["source"] for item in payload["plan"]}
            self.assertIn("materials/raw/前期材料", targets)
            self.assertIn("src/code", targets)
            self.assertNotIn("capability-layer", sources)
            self.assertNotIn("global-agent-fabric", sources)
            self.assertTrue((project / ".agent-os" / "inbox" / "legacy-reorganization-plan.md").exists())

            applied = self.run_cli("migrate-legacy-project", "--project-root", str(project), "--apply", "--json")
            applied_payload = json.loads(applied.stdout)
            self.assertTrue(any(item.get("action") == "move" for item in applied_payload["actions"]))
            self.assertTrue((project / "materials" / "raw" / "前期材料").exists())
            self.assertTrue((project / "src" / "code").exists())
            self.assertTrue((project / "docs" / "loose_note.md").exists())

    def test_archive_legacy_project_plans_and_applies_cold_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ArchiveProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Archive")
            (project / "docs").mkdir(exist_ok=True)
            (project / "outputs").mkdir(exist_ok=True)
            (project / "docs" / "old-draft.md").write_text("old draft\n", encoding="utf-8")
            (project / "outputs" / "results_old").mkdir()
            (project / "src").mkdir(exist_ok=True)
            (project / "src" / "active.py").write_text("print('active')\n", encoding="utf-8")

            plan = self.run_cli("archive-legacy-project", "--project-root", str(project), "--write-plan", "--json")
            payload = json.loads(plan.stdout)
            targets = {item["target"] for item in payload["plan"] if item["action"] == "archive"}
            self.assertIn("archive/superseded/docs/old-draft.md", targets)
            self.assertIn("archive/generated/outputs/results_old", targets)
            self.assertNotIn("archive/legacy/src/active.py", targets)
            self.assertTrue((project / ".agent-os" / "inbox" / "cold-archive-plan.md").exists())

            applied = self.run_cli("archive-legacy-project", "--project-root", str(project), "--apply", "--json")
            applied_payload = json.loads(applied.stdout)
            self.assertTrue(any(item.get("action") == "archive" for item in applied_payload["actions"]))
            self.assertTrue((project / "archive" / "superseded" / "docs" / "old-draft.md").exists())
            self.assertTrue((project / "archive" / "generated" / "outputs" / "results_old").exists())
            self.assertTrue((project / "src" / "active.py").exists())

            read_policy = (project / ".agent-os" / "read-policy.yaml").read_text(encoding="utf-8")
            self.assertIn("archive/**", read_policy)

    def test_archive_legacy_project_supports_explicit_include_and_skips_control_plane(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ArchiveProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Archive")
            (project / "docs").mkdir(exist_ok=True)
            (project / "docs" / "candidate.md").write_text("candidate\n", encoding="utf-8")

            result = self.run_cli(
                "archive-legacy-project",
                "--project-root",
                str(project),
                "--include",
                "docs/candidate.md",
                "--include",
                ".agent-os/tasks.yaml",
                "--json",
            )
            payload = json.loads(result.stdout)
            archive_items = [item for item in payload["plan"] if item["action"] == "archive"]
            skip_items = [item for item in payload["plan"] if item["action"] == "skip"]
            self.assertEqual(archive_items[0]["target"], "archive/superseded/docs/candidate.md")
            self.assertTrue(any(item["source"] == ".agent-os/tasks.yaml" for item in skip_items))

    def test_archive_legacy_project_skips_missing_explicit_include(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ArchiveProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Archive")

            result = self.run_cli(
                "archive-legacy-project",
                "--project-root",
                str(project),
                "--include",
                "docs/missing-old.md",
                "--json",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["plan"][0]["action"], "skip")
            self.assertEqual(payload["plan"][0]["reason"], "source missing")

            root_result = self.run_cli(
                "archive-legacy-project",
                "--project-root",
                str(project),
                "--include",
                ".",
                "--json",
            )
            root_payload = json.loads(root_result.stdout)
            self.assertEqual(root_payload["plan"][0]["action"], "skip")
            self.assertEqual(root_payload["plan"][0]["reason"], "project root cannot be cold-archived")

    def test_doctor_rejects_read_policy_archive_under_unknown_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ArchiveProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Archive")
            read_policy = project / ".agent-os" / "read-policy.yaml"
            read_policy.write_text(
                "default_context:\n"
                "  - AGENTS.md\n"
                "cold_storage:\n"
                "  - docs/legacy/**\n"
                "unexpected_section:\n"
                "  - archive/**\n"
                "require_explicit_human_request:\n"
                "  - archive/**\n"
                "deny_indexing:\n"
                "  - archive/**\n",
                encoding="utf-8",
            )
            result = self.run_cli("doctor", "--project-root", str(project), "--project-only", "--json", check=False)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertTrue(any(item["label"] == "archive_read_guard" and not item["ok"] for item in payload), payload)

    def test_route_task_resolves_initialized_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            result = self.run_cli("route-task", "--project-root", str(project), "--task-id", "T001", "--json")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "routed")
            self.assertEqual(payload["task_type"], "initialization")
            self.assertIn("doctor --project-root .", payload["route_order"])

    def test_route_task_requires_human_triage_for_unknown_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            result = self.run_cli(
                "route-task",
                "--project-root",
                str(project),
                "--task-type",
                "unregistered_task_type",
                "--json",
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "human_triage_required")

    def test_tool_registry_reports_configured_tools(self):
        result = self.run_cli("tool-registry", "--project-root", str(ROOT), "--check-paths", "--json")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"], payload)
        self.assertGreaterEqual(payload["counts"].get("mcp", 0), 1)
        self.assertGreaterEqual(payload["counts"].get("skill", 0), 1)
        self.assertGreaterEqual(payload["counts"].get("orchestrator", 0), 1)

    def test_tool_registry_rejects_inline_secret_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            registry = project / ".agent-os" / "tool-registry.yaml"
            registry.write_text(
                "tools:\n"
                "  - id: bad-tool\n"
                "    kind: mcp\n"
                "    status: enabled\n"
                "    scope: docs\n"
                "    invocation: capability_match\n"
                "    human_gate: false\n"
                "    token: API_KEY=bad\n",
                encoding="utf-8",
            )
            result = self.run_cli("tool-registry", "--project-root", str(project), "--json", check=False)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(any(item["label"] == "tool_registry_secret" and not item["ok"] for item in payload["checks"]))

    def test_agent_guide_outputs_operational_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            result = self.run_cli("agent-guide", "--project-root", str(project))
            self.assertIn("KnowledgeOS Agent Guide", result.stdout)
            self.assertIn("doctor --project-root", result.stdout)
            self.assertIn("route-task", result.stdout)
            self.assertIn("tool-registry", result.stdout)
            self.assertIn("check-route-write", result.stdout)
            self.assertIn("create-spec", result.stdout)
            self.assertIn("align-spec", result.stdout)
            self.assertIn("context-pack", result.stdout)
            self.assertIn("plan-task", result.stdout)
            self.assertIn("verify-context", result.stdout)
            self.assertIn("phase-task", result.stdout)
            self.assertIn("CHECKPOINT_OK", result.stdout)
            self.assertIn("capability-event", result.stdout)
            self.assertIn("CAPABILITY_OK", result.stdout)
            self.assertIn("verify-lifecycle", result.stdout)
            self.assertIn("complete-task", result.stdout)
            self.assertIn("archive-legacy-project", result.stdout)

    def test_dispatch_task_prioritizes_branch_builder_and_consultation(self):
        result = self.run_cli("dispatch-task", "--project-root", str(ROOT), "--task-id", "KOS-T009", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "dispatch_ready")
        stages = [step["stage"] for step in payload["steps"]]
        self.assertIn("branch_builder", stages)
        self.assertIn("orchestrator", stages)
        self.assertIn("mcp", stages)
        self.assertIn("skill", stages)
        self.assertLess(stages.index("branch_builder"), stages.index("orchestrator"))
        self.assertLess(stages.index("orchestrator"), stages.index("mcp"))
        self.assertLess(stages.index("mcp"), stages.index("skill"))
        self.assertIn("execute", payload["dispatch_policy"]["consultation_checkpoints"])
        self.assertIn("complete", payload["dispatch_policy"]["consultation_checkpoints"])
        self.assertTrue(payload["agent_opinion_required"])
        self.assertIn("Pause before execution", payload["agent_opinion_prompt"])

    def test_dispatch_task_requires_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "ExampleProject"
            project.mkdir()
            self.run_cli("init-project", "--root", str(ROOT), "--project-root", str(project), "--name", "Example")
            tasks_path = project / ".agent-os" / "tasks.yaml"
            tasks_path.write_text(
                tasks_path.read_text(encoding="utf-8")
                + "\n  - id: T999\n    title: Unknown work\n    type: unknown_type\n    status: ready\n",
                encoding="utf-8",
            )
            result = self.run_cli("dispatch-task", "--project-root", str(project), "--task-id", "T999", "--json", check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["status"], "human_triage_required")

    def test_guardrail_scenario_runner_blocks_distracted_agent_paths(self):
        result = subprocess.run(
            [str(ROOT / "examples" / "scenarios" / "run_guardrail_scenarios.sh")],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertIn("CHECKPOINT COMPLETE", result.stdout)
        self.assertIn("raw-material-mutation-blocked", result.stdout)
        self.assertIn("route-output-denied", result.stdout)
        self.assertIn("unrouted-task-human-triage", result.stdout)
        self.assertIn("create-spec-contract", result.stdout)
        self.assertIn("dispatch-evidence-recorded", result.stdout)
        self.assertIn("capability-event-recorded", result.stdout)
        self.assertIn("CHECKPOINT_OK", result.stdout)
        self.assertIn("CAPABILITY_OK", result.stdout)
        self.assertIn("verify-context-without-plan-blocked", result.stdout)
        self.assertIn("plan-task-writes-checkpoint-plan", result.stdout)
        self.assertIn("verify-context-passed", result.stdout)
        self.assertIn("completion-without-eval-blocked", result.stdout)
        self.assertIn("failed: 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
