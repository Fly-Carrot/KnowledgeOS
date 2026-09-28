"""Real temporary-project regressions for stale eval and postflight replay."""
import json
import tempfile
import unittest
from pathlib import Path

from tests import test_knowledgeos_cli as support
import knowledgeos.cli as cli


class CompletionIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "Project"
        self.project.mkdir()
        self.helper = support.KnowledgeOSCliTests()
        self.call = self.helper.run_cli
        self.call("init-project", "--root", str(support.ROOT), "--project-root", str(self.project), "--name", "Test")
        created = self.call("create-task", "--project-root", str(self.project), "--title", "Report",
                            "--type", "report_task", "--output", "docs/result.md", "--acceptance", "Real report", "--json")
        self.task = json.loads(created.stdout)["task_id"]
        self.output = self.project / "docs/result.md"
        self.output.parent.mkdir(exist_ok=True)
        self.output.write_text("verified content\n")
        self.run = json.loads(self.call("run-task", "--project-root", str(self.project), "--task-id", self.task, "--json").stdout)["run_id"]
        self.helper.write_plan_context(self.project, self.task, self.run)
        self.helper.log_required_phases(self.project, self.task, self.run)
        self.run_dir = self.project / ".agent-os/runs" / self.run

    def eval(self):
        cli.write_task_eval(self.project, self.task, self.run)

    def test_changed_output_invalidates_eval(self):
        self.eval()
        self.output.write_text("unreviewed replacement\n")
        with self.assertRaisesRegex(ValueError, "stale eval"):
            cli.complete_task(self.project, self.task, self.run, "done", allow_pending_postflight="isolated test")

    def test_policy_change_invalidates_eval(self):
        self.eval()
        with (self.project / ".agent-os/write-policy.yaml").open("a") as out:
            out.write("\n# boundary updated after evaluation\n")
        with self.assertRaisesRegex(ValueError, "stale eval"):
            cli.complete_task(self.project, self.task, self.run, "done", allow_pending_postflight="isolated test")

    def hook(self, success=True):
        root = self.project / "runtime"
        hook = root / "hooks/after-task.sh"
        hook.parent.mkdir(parents=True)
        hook.write_text("#!/bin/sh\necho call >> calls.txt\n" + ("echo '[SYNC_OK]'\n" if success else "exit 1\n"))
        hook.chmod(0o755)
        (self.project / ".agent-os/fabric-link.yaml").write_text(
            f"shared_fabric:\n  governance_root: {root}\nruntime_contract:\n  postflight_required: true\n")

    def test_repeated_complete_does_not_repeat_hook(self):
        self.hook()
        self.eval()
        first = cli.complete_task(self.project, self.task, self.run, "done")
        second = cli.complete_task(self.project, self.task, self.run, "done")
        self.assertEqual(first["sync_status"], "SYNC_OK")
        self.assertEqual(second["sync_status"], "SYNC_OK")
        self.assertEqual((self.project / "calls.txt").read_text().splitlines(), ["call"])

    def test_failed_hook_cannot_replay_unknown_side_effect(self):
        self.hook(success=False)
        self.eval()
        for _ in range(2):
            with self.assertRaises(ValueError):
                cli.complete_task(self.project, self.task, self.run, "done")
        self.assertEqual((self.project / "calls.txt").read_text().splitlines(), ["call"])

    def test_completion_lock_blocks_concurrent_or_interrupted_attempt(self):
        self.hook()
        self.eval()
        lock = self.run_dir / "completion.lock"
        lock.write_text("another process")
        with self.assertRaisesRegex(ValueError, "already running or interrupted"):
            cli.complete_task(self.project, self.task, self.run, "done")
        self.assertEqual(lock.read_text(), "another process")
        self.assertFalse((self.project / "calls.txt").exists())

    def test_failed_validation_releases_completion_lock(self):
        self.eval()
        self.output.write_text("not evaluated")
        with self.assertRaisesRegex(ValueError, "stale eval"):
            cli.complete_task(self.project, self.task, self.run, "done")
        self.assertFalse((self.run_dir / "completion.lock").exists())

    def test_missing_eval_fingerprint_requires_fresh_evaluation(self):
        self.eval()
        ledger = self.run_dir / "command-events.ndjson"
        events = [json.loads(line) for line in ledger.read_text().splitlines()]
        for event in events:
            event.pop("input_fingerprint", None)
        ledger.write_text("".join(json.dumps(event) + "\n" for event in events))
        with self.assertRaisesRegex(ValueError, "stale eval"):
            cli.complete_task(self.project, self.task, self.run, "done")

    def test_changed_hook_does_not_replay_completed_side_effect(self):
        self.hook()
        self.eval()
        cli.complete_task(self.project, self.task, self.run, "done")
        hook = self.project / "runtime/hooks/after-task.sh"
        hook.write_text(hook.read_text() + "# changed hook\n")
        with self.assertRaisesRegex(ValueError, "reconcile"):
            cli.complete_task(self.project, self.task, self.run, "done")
        self.assertEqual((self.project / "calls.txt").read_text().splitlines(), ["call"])

    def test_effect_is_rechecked_even_after_fresh_eval(self):
        (self.project / ".agent-os/effect-policy.yaml").write_text(
            "effect_policy:\n  strictness: enforce\n  required_for:\n    - declared_outputs\n")
        cli.run_artifact_assertion(self.project, self.task, self.run,
                                  kind="file_contains", target_path="docs/result.md", expect="verified content")
        self.output.write_text("stub\n")
        self.eval()
        with self.assertRaisesRegex(ValueError, "effect verification failed"):
            cli.complete_task(self.project, self.task, self.run, "done", allow_pending_postflight="isolated test")

    def test_lean_run_records_dispatch_without_a_second_command(self):
        result = cli.create_run_envelope(self.project, self.task, "lean path")
        directory = self.project / ".agent-os/runs" / result["run_id"]
        self.assertTrue(cli.has_command_event(directory, "dispatch-task", self.task,
                                              result["run_id"], status="dispatch_ready"))
        self.assertIn("dispatch", [row["phase"] for row in cli.load_phase_records(directory)])

    def test_lean_path_completes_without_separate_verifiers(self):
        self.hook()
        cli.build_dispatch_plan(self.project, self.task, persist=True)
        result = cli.create_run_envelope(self.project, self.task, "lean full path")
        run = result["run_id"]
        cli.write_task_plan(self.project, self.task, run, summary="Verify the existing report")
        cli.record_capability_event(self.project, self.task, run, kind="skill",
            capability_id="branch-builder", purpose="Skipped: a single bounded report needs no virtual branches",
            status="skipped", evidence="one declared output")
        for phase in ("review", "execute", "report"):
            cli.record_task_phase(self.project, self.task, run, phase=phase, status="completed",
                                  note="Checked fixture report", evidence="docs/result.md")
        cli.write_task_eval(self.project, self.task, run)
        completed = cli.complete_task(self.project, self.task, run, "done")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["sync_status"], "SYNC_OK")

    def test_realigning_changed_spec_requires_new_eval(self):
        spec = cli.create_spec(self.project, title="Report contract", intent="Produce a report",
                               acceptance=["Report exists"], non_goal=["No external writes"])
        cli.align_spec(self.project, task_id=self.task, spec_id=spec["spec_id"], run_id=self.run)
        cli.write_task_plan(self.project, self.task, self.run, summary="Initial plan")
        self.eval()
        source = Path(spec["path"]) / "acceptance.md"
        source.write_text(source.read_text() + "\n- Revised acceptance needs reevaluation\n")
        cli.align_spec(self.project, task_id=self.task, spec_id=spec["spec_id"], run_id=self.run)
        cli.write_task_plan(self.project, self.task, self.run, summary="Revised plan")
        with self.assertRaisesRegex(ValueError, "stale eval"):
            cli.complete_task(self.project, self.task, self.run, "done", allow_pending_postflight="isolated test")


if __name__ == "__main__":
    unittest.main()
