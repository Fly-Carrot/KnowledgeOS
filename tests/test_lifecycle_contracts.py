"""Batch 1: versioned route hints, legacy repair, and lean execution gates."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledgeos import cli
from tests import test_knowledgeos_cli as support
from tests import test_completion_integrity as completion_support


LEAN = "producer-bound-v1"
SHORT_ROUTE = [
    "doctor --project-root .",
    "route-task --project-root . --task-id <task-id>",
    "check-route-write --project-root . --task-id <task-id> --path <planned-path>",
    "run-task --project-root . --task-id <task-id>",
    *[line for line in cli.LIFECYCLE_ROUTE_COMMANDS
      if not line.startswith(("dispatch-task", "verify-"))],
]


class LifecycleContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "Project"
        self.project.mkdir()
        self.helper = support.KnowledgeOSCliTests()
        self.call = self.helper.run_cli
        self.call("init-project", "--root", str(support.ROOT),
                  "--project-root", str(self.project), "--name", "Compatibility",
                  "--global-root", str(Path(self.tmp.name) / "runtime/global-agent-fabric"),
                  "--capability-root", str(Path(self.tmp.name) / "runtime/capability-layer"))
        self.router = self.project / ".agent-os/workflows/router.yaml"
        self.profiles = cli.parse_workflow_profiles(self.router)

    def save_route(self, contract=LEAN, route=None):
        profile = self.profiles["report_task"]
        if contract is None:
            profile.pop("lifecycle_contract", None)
        else:
            profile["lifecycle_contract"] = contract
        profile["route_order"] = list(SHORT_ROUTE if route is None else route)
        self.router.write_text(cli.render_workflow_profiles(self.profiles))

    def lifecycle_failures(self):
        result = self.call("doctor", "--project-root", str(self.project),
                           "--project-only", "--allow-placeholders", "--skip-linked-checks",
                           "--json", check=False)
        return [c for c in json.loads(result.stdout)
                if c["label"] == "workflow_router_lifecycle" and not c["ok"]]

    def test_lean_route_passes_doctor_and_repair_is_noop(self):
        self.save_route()
        before = self.router.read_bytes()
        self.assertEqual(self.lifecycle_failures(), [])
        for apply in (False, True):
            self.assertIsNone(cli.upgrade_workflow_router_file(
                self.project, apply=apply, backup_name="batch1-test"))
            self.assertEqual(self.router.read_bytes(), before)

    def test_legacy_missing_steps_still_repaired_and_dry_run_is_read_only(self):
        self.save_route(contract=None)
        before = self.router.read_bytes()
        self.assertTrue(self.lifecycle_failures())
        proposed = cli.upgrade_workflow_router_file(self.project, apply=False, backup_name="batch1-test")
        self.assertEqual(proposed["action"], "upgrade_workflow_router")
        self.assertEqual(before, self.router.read_bytes())
        cli.upgrade_workflow_router_file(self.project, apply=True, backup_name="batch1-test")
        self.assertEqual(self.lifecycle_failures(), [])
        self.assertEqual(cli.parse_workflow_profiles(self.router)["report_task"]["allowed_outputs"],
                         self.profiles["report_task"]["allowed_outputs"])
        self.assertIsNone(cli.upgrade_workflow_router_file(self.project, apply=True, backup_name="again"))

    def test_harness_cli_preserves_valid_short_route_on_dry_run_and_apply(self):
        self.save_route()
        before = self.router.read_bytes()
        runtime = Path(self.tmp.name) / "runtime"
        args = ["harness-audit", "--root", str(support.ROOT), "--target-project", str(self.project),
                "--governance-root", str(runtime / "global-agent-fabric"),
                "--capability-root", str(runtime / "capability-layer"), "--json"]
        preview = self.call(*args, check=False)
        self.assertNotIn("workflow_router_lifecycle_drift", json.loads(preview.stdout)["projects"][0]["issues"])
        self.assertFalse(runtime.exists())
        self.assertEqual(before, self.router.read_bytes())
        applied = self.call(*args, "--apply")
        self.assertEqual(json.loads(applied.stdout)["status"], "ok")
        self.assertEqual(before, self.router.read_bytes())
        self.call("doctor", "--project-root", str(self.project), "--project-only", "--summary")

    def test_unknown_contract_is_not_silently_repaired_or_routed(self):
        self.save_route(contract="future-v99", route=self.profiles["report_task"]["route_order"])
        before = self.router.read_bytes()
        self.assertTrue(self.lifecycle_failures())
        result = cli.upgrade_workflow_router_file(self.project, apply=True, backup_name="batch1-test")
        self.assertEqual(result["action"], "review_workflow_router")
        self.assertEqual(before, self.router.read_bytes())
        self.assertEqual(cli.build_task_route(self.project, None, "report_task")["status"], "human_triage_required")

    def test_invalid_lean_contract_requires_review_not_legacy_expansion(self):
        for missing in ("run-task", "context-pack", "plan-task", "phase-task", "eval-task", "complete-task"):
            with self.subTest(missing=missing):
                self.save_route(route=[line for line in SHORT_ROUTE if not line.startswith(missing)])
                before = self.router.read_bytes()
                self.assertTrue(self.lifecycle_failures())
                result = cli.upgrade_workflow_router_file(self.project, apply=True, backup_name="batch1-test")
                self.assertEqual(result["action"], "review_workflow_router")
                self.assertEqual(before, self.router.read_bytes())

    def test_phase_after_completion_and_command_mentions_do_not_count(self):
        for route in (
            [line for line in SHORT_ROUTE if not line.startswith("phase-task")] + ["phase-task --phase review"],
            ["echo 'eval-task is documented'" if line.startswith("eval-task") else line for line in SHORT_ROUTE],
        ):
            with self.subTest(route=route):
                self.save_route(route=route)
                self.assertTrue(self.lifecycle_failures())

    def test_mixed_optional_diagnostic_calls_are_accepted(self):
        route = list(SHORT_ROUTE)
        run_index = next(i for i, s in enumerate(route) if s.startswith("run-task"))
        route.insert(run_index + 1, cli.LIFECYCLE_ROUTE_COMMANDS[0])
        route[-1:-1] = [s for s in cli.LIFECYCLE_ROUTE_COMMANDS if s.startswith("verify-")]
        self.save_route(route=route)
        self.assertEqual(self.lifecycle_failures(), [])

    def test_legacy_preflight_dispatch_remains_optional_not_run_evidence(self):
        preflight = "dispatch-task --project-root . --task-id <task-id>"
        legacy = ["run-task --project-root . --task-id <task-id>", *cli.LIFECYCLE_ROUTE_COMMANDS]
        self.save_route(contract=None, route=[preflight, *legacy])
        before = self.router.read_bytes()
        self.assertEqual(self.lifecycle_failures(), [])
        self.assertIsNone(cli.upgrade_workflow_router_file(self.project, apply=True, backup_name="preflight"))
        self.assertEqual(before, self.router.read_bytes())
        self.save_route(contract=None, route=[preflight, *SHORT_ROUTE])
        self.assertTrue(self.lifecycle_failures())
        self.save_route(route=[preflight, *SHORT_ROUTE])
        self.assertEqual(self.lifecycle_failures(), [])

    def test_legacy_interleaved_checkpoints_are_not_rewritten(self):
        route = ["run-task --project-root . --task-id <task-id>"]
        for command in cli.LIFECYCLE_ROUTE_COMMANDS:
            if command.startswith('phase-task'):
                for phase in ('review', 'execute', 'report'):
                    route.append(f'phase-task --phase {phase} --run-id <run-id>')
                continue
            route.append(command)
            phase = 'route' if command.startswith('dispatch-task') else 'plan' if command.startswith('plan-task') else None
            if phase:
                route.append(f'phase-task --phase {phase} --run-id <run-id>')
        for contract in (None, cli.LEGACY_LIFECYCLE_CONTRACT):
            with self.subTest(contract=contract):
                self.save_route(contract=contract, route=route)
                before = self.router.read_bytes()
                self.assertEqual(self.lifecycle_failures(), [])
                self.assertEqual(cli.build_task_route(self.project, None, 'report_task')['status'], 'routed')
                for apply in (False, True):
                    self.assertIsNone(cli.upgrade_workflow_router_file(
                        self.project, apply=apply, backup_name='legacy-interleaved'))
                    self.assertEqual(before, self.router.read_bytes())
        self.save_route(contract=LEAN, route=route)
        self.assertTrue(self.lifecycle_failures(), 'The short contract still requires its documented order')

    def test_legacy_checkpoint_must_stay_inside_execution_envelope(self):
        base = ['run-task --project-root .', *cli.LIFECYCLE_ROUTE_COMMANDS]
        for route in (["phase-task --phase route", *base], [*base, "phase-task --phase report"]):
            with self.subTest(route=route):
                self.save_route(contract=cli.LEGACY_LIFECYCLE_CONTRACT, route=route)
                self.assertTrue(self.lifecycle_failures())

    def test_lean_end_to_end_retains_real_gates_and_idempotent_dispatch(self):
        self.save_route()
        result = self.call("create-task", "--project-root", str(self.project), "--title", "Real report",
                           "--type", "report_task", "--output", "docs/result.md", "--acceptance", "Verified content", "--json")
        task = json.loads(result.stdout)["task_id"]
        run = cli.create_run_envelope(self.project, task, "Batch1 dry run")["run_id"]
        directory = self.project / ".agent-os/runs" / run
        cli.write_task_plan(self.project, task, run, summary="Write and check a real report")
        for _ in range(2):
            dispatch = cli.build_dispatch_plan(self.project, task, run_id=run, persist=True)
            cli.record_dispatch_event(self.project, task, run, dispatch)
        self.assertEqual(len([e for e in cli.load_command_events(directory) if e.get("event_type") == "dispatch-task"]), 1)
        with self.assertRaises(ValueError):
            cli.complete_task(self.project, task, run, "not done")
        output = self.project / "docs/result.md"
        output.parent.mkdir(exist_ok=True)
        output.write_text("Verified content\n")
        cli.write_task_eval(self.project, task, run)
        with self.assertRaisesRegex(ValueError, "lifecycle"):
            cli.complete_task(self.project, task, run, "not reviewed")
        for phase in ("review", "execute", "report"):
            cli.record_task_phase(self.project, task, run, phase=phase, status="completed",
                                  note="Wrote and checked test report", evidence="docs/result.md")
        hook = self.project / "runtime/hooks/after-task.sh"
        hook.parent.mkdir(parents=True)
        hook.write_text("#!/bin/sh\necho sync >> sync-count.txt\necho '[SYNC_OK]'\n")
        hook.chmod(0o755)
        (self.project / ".agent-os/fabric-link.yaml").write_text(
            f"shared_fabric:\n  governance_root: {hook.parent.parent}\nruntime_contract:\n  postflight_required: true\n")
        cli.write_task_eval(self.project, task, run)
        output.write_text("Changed after eval\n")
        with self.assertRaisesRegex(ValueError, "stale eval"):
            cli.complete_task(self.project, task, run, "stale")
        cli.write_task_eval(self.project, task, run)
        for _ in range(2):
            self.assertEqual(cli.complete_task(self.project, task, run, "done")["sync_status"], "SYNC_OK")
        self.assertEqual((self.project / "sync-count.txt").read_text().splitlines(), ["sync"])


class ActiveRunCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = completion_support.CompletionIntegrityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_old_postflight_without_journal_never_replays(self):
        f = self.fixture
        f.hook()
        for content in ("Status: SYNC_OK\n", "Status: pending\nDetail: hook timed out\n"):
            with self.subTest(content=content):
                evidence = f.run_dir / "postflight.md"
                evidence.write_text(content)
                f.eval()
                with self.assertRaisesRegex(ValueError, "reconcile"):
                    cli.complete_task(f.project, f.task, f.run, "legacy attempt")
                self.assertFalse((f.project / "calls.txt").exists())
                result = cli.complete_task(f.project, f.task, f.run, "legacy attempt",
                                          allow_pending_postflight="Human will reconcile old attempt")
                self.assertEqual(result["sync_status"], "PENDING")
                self.assertEqual(evidence.read_text(), content)
                self.assertFalse((f.project / "calls.txt").exists())

    def test_cached_dispatch_retry_recovers_missing_checkpoint(self):
        f = self.fixture
        # Fault injection between the command append and the phase append.
        plan = cli.build_dispatch_plan(f.project, f.task, run_id=f.run, persist=True)
        command_path = f.run_dir / "command-events.ndjson"
        events = [e for e in cli.load_command_events(f.run_dir)
                  if e.get("event_type") != "dispatch-task"
                  and not (e.get("event_type") == "checkpoint-producer"
                           and e.get("checkpoint", {}).get("phase") == "dispatch")
                  and not (e.get("event_type") == "phase-task" and e.get("phase") == "dispatch")]
        command_path.write_text("".join(json.dumps(e) + "\n" for e in events))
        phases = [p for p in cli.load_phase_records(f.run_dir) if p.get("phase") != "dispatch"]
        (f.run_dir / "phases.ndjson").write_text("".join(json.dumps(p) + "\n" for p in phases))
        with patch.object(cli, "record_checkpoint_producer", side_effect=RuntimeError("crash")):
            with self.assertRaisesRegex(RuntimeError, "crash"):
                cli.record_dispatch_event(f.project, f.task, f.run, plan)
        cli.record_dispatch_event(f.project, f.task, f.run, plan)
        self.assertEqual(len([e for e in cli.load_command_events(f.run_dir) if e.get("event_type") == "dispatch-task"]), 1)
        self.assertEqual(cli.verify_lifecycle(f.project, f.task, f.run)["status"], "passed")

    def test_cached_plan_does_not_reuse_failed_dispatch_command(self):
        f = self.fixture
        plan = cli.build_dispatch_plan(f.project, f.task, run_id=f.run, persist=True)
        prior = [e for e in cli.load_command_events(f.run_dir) if e.get("event_type") == "dispatch-task"][-1]
        cli.append_command_event(f.run_dir, "dispatch-task", f.task, f.run, status="failed",
                                 dispatch_fingerprint=plan["dispatch_fingerprint"],
                                 required_stages=prior["required_stages"], planned_tools=prior["planned_tools"])
        cli.record_dispatch_event(f.project, f.task, f.run, plan)
        dispatches = [e for e in cli.load_command_events(f.run_dir) if e.get("event_type") == "dispatch-task"]
        self.assertEqual(dispatches[-1]["status"], "dispatch_ready")
        self.assertEqual(len(dispatches), 3)
        self.assertEqual(cli.verify_lifecycle(f.project, f.task, f.run)["status"], "passed")

    def test_legacy_dispatch_skip_survives_same_plan_but_not_changed_plan(self):
        f = self.fixture
        registry = f.project / ".agent-os/tool-registry.yaml"
        with registry.open("a") as out:
            out.write("\n" + cli.registry_block_from_entry({"id": "branch-builder", "kind": "subagent",
                      "status": "configured", "source_path": "external:branch-builder"}) + "\n")
        policy = f.project / ".agent-os/dispatch-policy.yaml"
        policy.write_text(policy.read_text().replace("  branch_builder_task_types:",
                                                    "  branch_builder_task_types:\n    - report_task"))
        plan = cli.build_dispatch_plan(f.project, f.task, run_id=f.run, persist=True)
        self.assertIn("branch_builder", [s["stage"] for s in plan["steps"] if s.get("required")])
        cli.record_dispatch_event(f.project, f.task, f.run, plan)
        cli.record_task_phase(f.project, f.task, f.run, phase="dispatch", status="completed",
                              note="Skipped branch_builder: one bounded report, no planning branches needed",
                              evidence="Existing report and explicit task scope")
        self.assertEqual(cli.verify_lifecycle(f.project, f.task, f.run)["status"], "passed")
        # A pre-upgrade dispatch command had no cache fingerprint.
        events = [e for e in cli.load_command_events(f.run_dir)
                  if not (e.get("event_type") == "checkpoint-producer"
                          and e.get("checkpoint", {}).get("phase") == "dispatch")]
        phases = [p for p in cli.load_phase_records(f.run_dir)
                  if not (p.get("phase") == "dispatch" and p.get("producer"))]
        (f.run_dir / "phases.ndjson").write_text("".join(json.dumps(p) + "\n" for p in phases))
        for event in events:
            if event.get("event_type") == "dispatch-task":
                event.pop("dispatch_fingerprint", None)
        (f.run_dir / "command-events.ndjson").write_text("".join(json.dumps(e) + "\n" for e in events))
        self.assertEqual(cli.verify_lifecycle(f.project, f.task, f.run)["status"], "passed")
        cli.record_dispatch_event(f.project, f.task, f.run, plan)
        self.assertEqual(cli.verify_lifecycle(f.project, f.task, f.run)["status"], "passed")
        policy.write_text(policy.read_text().replace("  always_consult_before:", "  always_consult_before:\n    - review"))
        changed = cli.build_dispatch_plan(f.project, f.task, run_id=f.run, persist=True)
        cli.record_dispatch_event(f.project, f.task, f.run, changed)
        self.assertEqual(cli.verify_lifecycle(f.project, f.task, f.run)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
