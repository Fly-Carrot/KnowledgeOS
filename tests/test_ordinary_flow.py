"""Step 1: real temporary projects, opt-in only, no simulated checkpoints."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from knowledgeos import cli, guidance
from tests import test_knowledgeos_cli as support


class OrdinaryFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        self.call = support.KnowledgeOSCliTests().run_cli
        self.runtime = Path(self.tmp.name) / "runtime"
        self.call("init-os", "--root", str(support.ROOT), "--os-root", str(self.runtime))
        self.call("init-project", "--root", str(support.ROOT),
                  "--project-root", str(self.project), "--name", "Ordinary pilot",
                  "--global-root", str(self.runtime / "global-agent-fabric"),
                  "--capability-root", str(self.runtime / "capability-layer"))
        fabric = self.project / ".agent-os/fabric-link.yaml"
        fabric.write_text(fabric.read_text().replace("postflight_required: true",
                                                   "postflight_required: false"))
        self.task = cli.create_task(self.project, title="Bounded report",
            task_type="report_task", status="ready", complexity="medium", risk="normal",
            outputs=["docs/result.md"], acceptance=["Real report content"])["task_id"]

    def adopt(self):
        path = self.project / ".agent-os/project.yaml"
        path.write_text(path.read_text().replace("project:\n",
            "project:\n  execution_contract: ordinary-v1\n", 1))
        fabric = self.project / ".agent-os/fabric-link.yaml"
        fabric.write_text(fabric.read_text().replace("phase_logging_required: true",
                                                   "phase_logging_required: false"))

    def test_explicit_task_approval_cannot_use_ordinary_shortcut(self):
        self.adopt()
        path = self.project / '.agent-os/dispatch-policy.yaml'
        path.write_text(path.read_text().replace('human_gate_for:',
            'human_gate_for:\n    - per_task_confirmation', 1))
        plan = cli.build_dispatch_plan(self.project, self.task)
        self.assertTrue(plan['approval_required'])
        self.assertFalse(cli.ordinary_eligible(self.project, self.task))

    def start(self):
        return cli.create_run_envelope(self.project, self.task, "Write a checked report")

    def test_short_global_entry_preserves_custom_text(self):
        text = guidance.render_guidance(".", "kos", surface="global")
        self.assertLessEqual(len(text.split()), 240)  # includes generated metadata
        original = "Unchanged prefix\n" + text + "\nUnchanged suffix\n"
        self.assertEqual(guidance.merge_generated(original, text), original)
        self.assertIn("active", text)

    def test_ordinary_three_call_path_without_manual_ledgers(self):
        self.adopt()
        result = self.start()
        self.assertEqual(result.get("execution_contract"), "ordinary-v1")
        run = result["run_id"]
        output = self.project / "docs/result.md"
        output.parent.mkdir(exist_ok=True)
        output.write_text("# Result\n\nSource: deterministic fixture; no scientific claim.\n")
        self.assertIn("Source:", output.read_text())  # actual artifact check
        cli.write_task_eval(self.project, self.task, run, notes="Checked report source statement.",
            validations=[{"kind": "file_contains", "path": "docs/result.md", "expect": "Source:", "acceptance": [1]}])
        completed = cli.complete_task(self.project, self.task, run, "Report checked")
        self.assertEqual(completed["status"], "completed")
        self.assertFalse(completed["flow_marker"])
        run_dir = self.project / ".agent-os/runs" / run
        self.assertFalse((run_dir / "phases.ndjson").exists())
        self.assertFalse((run_dir / "plan.md").exists())
        self.assertNotIn("Use plan.md as the current execution contract", (run_dir / "context-pack.md").read_text())
        failures = [r for r in cli.deep_validate_project(self.project) if not r.ok]
        self.assertEqual([], [(r.label, r.detail) for r in failures])

    def test_required_phase_logging_keeps_legacy(self):
        self.adopt()
        path = self.project / ".agent-os/fabric-link.yaml"
        path.write_text(path.read_text().replace("phase_logging_required: false", "phase_logging_required: true")
                        .replace("postflight_required: false", "postflight_required: true"))
        self.assertEqual(self.start()["execution_contract"], "legacy")

    def test_invalid_contract_and_duplicate_declaration_fail_before_run(self):
        for value in ("fast", "ordinary-v1\n  execution_contract: legacy"):
            path = self.project / ".agent-os/project.yaml"
            old = path.read_text()
            path.write_text(old.replace("project:\n", f"project:\n  execution_contract: {value}\n"))
            before = list((self.project / ".agent-os/runs").glob("*"))
            with self.assertRaises(ValueError):
                self.start()
            self.assertEqual(before, list((self.project / ".agent-os/runs").glob("*")))
            path.write_text(old)

    def test_unknown_or_forged_run_contract_rejected(self):
        result = self.start()
        path = self.project / ".agent-os/runs" / result["run_id"] / "run.yaml"
        path.write_text(path.read_text() + "\nexecution_contract: ordinary-v1\nordinary_scope: forged\n")
        with self.assertRaisesRegex(ValueError, "contract"):
            cli.verify_lifecycle(self.project, self.task, result["run_id"])

    def test_stale_eval_still_fails_and_missing_eval_never_auto_passes(self):
        self.adopt()
        run = self.start()["run_id"]
        out = self.project / "docs/result.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text("checked")
        with self.assertRaisesRegex(ValueError, "eval.md"):
            cli.complete_task(self.project, self.task, run, "not complete")
        cli.write_task_eval(self.project, self.task, run,
            validations=[{"kind": "file_contains", "path": "docs/result.md", "expect": "checked", "acceptance": [1]}])
        out.write_text("unchecked changed result")
        with self.assertRaisesRegex(ValueError, "stale eval"):
            cli.complete_task(self.project, self.task, run, "not complete")

    def test_required_postflight_is_not_skipped(self):
        self.adopt()
        path = self.project / ".agent-os/fabric-link.yaml"
        path.write_text("shared_fabric:\n  governance_root: missing-kernel\n"
                        "runtime_contract:\n  phase_logging_required: false\n  postflight_required: true\n")
        run = self.start()["run_id"]
        out = self.project / "docs/result.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text("checked")
        cli.write_task_eval(self.project, self.task, run,
            validations=[{"kind": "file_contains", "path": "docs/result.md", "expect": "checked", "acceptance": [1]}])
        with self.assertRaisesRegex(ValueError, "postflight hook"):
            cli.complete_task(self.project, self.task, run, "not complete")

    def test_stricter_policy_mid_run_blocks_completion(self):
        self.adopt()
        run = self.start()["run_id"]
        path = self.project / ".agent-os/decision-policy.yaml"
        path.write_text(path.read_text().replace("strictness: warn", "strictness: enforce"))
        with self.assertRaisesRegex(ValueError, "strict"):
            cli.complete_task(self.project, self.task, run, "not complete")

    def test_existing_active_run_not_replaced(self):
        self.start()
        self.adopt()
        with self.assertRaisesRegex(ValueError, "existing active run"):
            self.start()

    def test_ordinary_and_legacy_guidance_remain_accessible(self):
        self.adopt()
        result = self.call("agent-guide", "--project-root", str(self.project))
        self.assertIn("execution_contract: ordinary-v1", result.stdout)
        legacy = self.call("agent-guide", "--project-root", str(self.project), "--legacy")
        self.assertIn("Keep all six lifecycle phases explicit", legacy.stdout)
        self.assertNotIn("execution_contract: ordinary-v1", legacy.stdout)

    def test_adopted_dispatch_does_not_recommend_unavailable_default_maestro(self):
        self.adopt()
        plan = cli.build_dispatch_plan(self.project, self.task, host_snapshot={})
        ids = [tool["id"] for step in plan["steps"] for tool in step["tools"]]
        self.assertFalse(any(value.startswith("maestro") for value in ids))

    def test_high_risk_and_sensitive_outputs_do_not_use_ordinary_shortcut(self):
        self.adopt()
        self.task = cli.create_task(self.project, title="External operation",
            task_type="report_task", status="ready", complexity="simple", risk="external_write",
            outputs=["docs/external.md"], acceptance=["Approved external operation"])["task_id"]
        with self.assertRaisesRegex(ValueError, "requires legacy gates"):
            self.start()
        path = self.project / ".agent-os/fabric-link.yaml"
        path.write_text(path.read_text().replace("postflight_required: false", "postflight_required: true"))
        self.assertEqual(self.start()["execution_contract"], "legacy")

    def test_required_postflight_cannot_be_removed_from_bound_run(self):
        self.adopt()
        path = self.project / ".agent-os/fabric-link.yaml"
        path.write_text(path.read_text().replace("postflight_required: false", "postflight_required: true"))
        run = self.start()["run_id"]
        path.write_text(path.read_text().replace("postflight_required: true", "postflight_required: false"))
        with self.assertRaisesRegex(ValueError, "contract"):
            cli.complete_task(self.project, self.task, run, "not complete")

    def test_matched_fix_and_research_pilots_reduce_management_calls(self):
        import copy
        counts = {}
        hook = self.runtime / "global-agent-fabric/hooks/after-task.sh"
        hook.write_text("#!/bin/sh\necho '[SYNC_OK]'\n")
        hook.chmod(0o755)
        for kind in ("engineering_change", "research_task"):
            for adopted in (False, True):
                project = Path(self.tmp.name) / f"{kind}-{adopted}"
                project.mkdir()
                self.call("init-project", "--root", str(support.ROOT), "--project-root", str(project),
                          "--name", "Matched pilot", "--global-root", str(self.runtime / "global-agent-fabric"),
                          "--capability-root", str(self.runtime / "capability-layer"))
                router = project / ".agent-os/workflows/router.yaml"
                profiles = cli.parse_workflow_profiles(router)
                profiles[kind] = copy.deepcopy(profiles["report_task"])
                router.write_text(cli.render_workflow_profiles(profiles))
                target = "docs/result.py" if kind == "engineering_change" else "docs/report.md"
                task = cli.create_task(project, title="Pilot", task_type=kind, status="ready",
                    complexity="medium", risk="normal", outputs=[target],
                    acceptance=["Verified fixture output"])["task_id"]
                if adopted:
                    path = project / ".agent-os/project.yaml"
                    path.write_text(path.read_text().replace("project:\n", "project:\n  execution_contract: ordinary-v1\n"))
                    path = project / ".agent-os/fabric-link.yaml"
                    path.write_text(path.read_text().replace("phase_logging_required: true", "phase_logging_required: false"))
                commands = []
                def invoke(name, *args):
                    commands.append(name)
                    return self.call(name, "--project-root", str(project), *args)
                if not adopted:
                    invoke("doctor", "--summary")
                    invoke("route-task", "--task-id", task)
                    invoke("dispatch-task", "--task-id", task)
                    invoke("check-route-write", "--task-id", task, "--path", target)
                start = invoke("run-task", "--task-id", task, "--json")
                run = json.loads(start.stdout)["run_id"]
                if not adopted:
                    invoke("context-pack", "--task-id", task, "--run-id", run)
                    invoke("plan-task", "--task-id", task, "--run-id", run, "--summary", "Produce and verify fixture")
                output = project / target
                output.parent.mkdir(exist_ok=True)
                output.write_text("assert sum([1, 2]) == 3\n" if kind == "engineering_change"
                                  else "# Research note\nSource: fixture data v1\nUncertainty: not evidence of causation\n")
                if kind == "engineering_change" and not adopted:
                    checked = subprocess.run([sys.executable, "-B", str(output)], capture_output=True)
                    self.assertEqual(checked.returncode, 0)
                elif kind != "engineering_change":
                    self.assertIn("Uncertainty:", output.read_text())
                if not adopted:
                    for phase in ("review", "execute", "report"):
                        invoke("phase-task", "--task-id", task, "--run-id", run, "--phase", phase,
                               "--status", "completed", "--note", "Verified fixture output", "--evidence", target)
                checks = []
                if adopted:
                    check = ({"kind": "command", "argv": [sys.executable, "-B", target], "inputs": [target],
                              "acceptance": [1]} if kind == "engineering_change" else
                             {"kind": "file_contains", "path": target, "expect": "Uncertainty: not evidence of causation",
                              "acceptance": [1]})
                    checks = ["--check", json.dumps(check), "--execute-validators"]
                invoke("eval-task", "--task-id", task, "--run-id", run, "--notes", "Executed fixture assertions or checked source/uncertainty.", *checks)
                invoke("complete-task", "--task-id", task, "--run-id", run, "--summary", "Verified fixture", "--json")
                counts[(kind, adopted)] = len(commands)
        for kind in ("engineering_change", "research_task"):
            self.assertEqual(counts[(kind, True)], 3)
            self.assertGreaterEqual(counts[(kind, False)], 6)
            self.assertLessEqual(counts[(kind, True)], counts[(kind, False)] / 2)
        print("Matched management calls:", counts)

    def test_legacy_run_stays_legacy_after_adoption(self):
        result = self.start()
        run = result["run_id"]
        self.adopt()
        out = self.project / "docs/result.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text("Report")
        cli.write_task_eval(self.project, self.task, run)
        with self.assertRaisesRegex(ValueError, "lifecycle"):
            cli.complete_task(self.project, self.task, run, "not complete")

    def test_ordinary_dry_run_no_files_changed(self):
        self.adopt()
        before = {str(p): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        result = cli.create_run_envelope(self.project, self.task, "Preview", dry_run=True)
        self.assertEqual(result.get("execution_contract"), "ordinary-v1")
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.project.rglob("*") if p.is_file()})

    def test_raw_data_and_path_escape_cannot_start_ordinary(self):
        self.adopt()
        for output in ("data/raw/source.csv", "../outside.md", ".agent-os/evals.yaml"):
            with self.subTest(output=output):
                tasks = self.project / ".agent-os/tasks.yaml"
                old = tasks.read_text()
                tasks.write_text(old.replace("docs/result.md", output))
                try:
                    with self.assertRaises(ValueError):
                        self.start()
                finally:
                    tasks.write_text(old)

    def test_enforced_project_retains_six_phase_gate(self):
        self.adopt()
        fabric = self.project / ".agent-os/fabric-link.yaml"
        fabric.write_text(fabric.read_text().replace("postflight_required: false", "postflight_required: true"))
        path = self.project / ".agent-os/decision-policy.yaml"
        path.write_text(path.read_text().replace("strictness: warn", "strictness: enforce"))
        result = self.start()
        self.assertNotEqual(result.get("execution_contract"), "ordinary-v1")
        self.assertTrue((self.project / ".agent-os/runs" / result["run_id"] / "phases.ndjson").exists())


if __name__ == "__main__":
    unittest.main()
