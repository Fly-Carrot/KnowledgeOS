"""Exercise the actual one-time rollout against disposable managed projects."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

from knowledgeos import cli, guidance
from tests import test_ordinary_flow as support

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if (SCRIPTS / "adopt_future_defaults.py").is_file():
    sys.path.insert(0, str(SCRIPTS))
    import adopt_future_defaults as migration
else:
    migration = None


@unittest.skipIf(migration is None, "Private one-time rollout script not included in runtime-only installation")
class FutureMigrationTests(unittest.TestCase):
    def setUp(self):
        support.OrdinaryFlowTests.setUp(self)
        self.project = self.project.resolve()
        path = self.project / ".agent-os/fabric-link.yaml"
        path.write_text(path.read_text().replace("postflight_required: false", "postflight_required: true"))

    def test_preview_is_read_only_and_apply_preserves_active_and_completed(self):
        run = cli.create_run_envelope(self.project, self.task, "Legacy work")["run_id"]
        history = self.project / ".agent-os/runs/completed-note"
        history.mkdir()
        (history / "receipt.md").write_text("Original completed evidence")
        before = migration.state(self.project)
        fingerprint = cli.evaluation_fingerprint(self.project, self.task, run)
        plan = migration.prepare(self.project, "knowledgeos")
        plan = json.loads(json.dumps(plan))
        self.assertEqual(plan["status"], "ready", plan.get("reason"))
        self.assertEqual(before, migration.state(self.project))
        done = migration.apply(plan, Path(self.tmp.name) / "backups")
        self.assertEqual(done["status"], "adopted")
        self.assertEqual(guidance.execution_contract(self.project), "ordinary-v1")
        self.assertEqual(fingerprint, cli.evaluation_fingerprint(self.project, self.task, run))
        for name, digest in before.items():
            if name not in migration.TARGETS:
                self.assertEqual(digest, migration.state(self.project)[name], name)
        self.assertEqual(migration.prepare(self.project, "knowledgeos")["status"], "already_adopted")

    def test_concurrent_update_rejected(self):
        plan = migration.prepare(self.project, "knowledgeos")
        self.assertEqual(plan["status"], "ready", plan.get("reason"))
        path = self.project / ".agent-os/tasks.yaml"
        path.write_text(path.read_text() + "\n# concurrent work\n")
        with self.assertRaisesRegex(RuntimeError, "concurrent"):
            migration.apply(plan, Path(self.tmp.name) / "backups")
        self.assertFalse((self.project / guidance.FUTURE_DEFAULTS).exists())

    def test_failed_verification_restores_only_own_changes(self):
        plan = migration.prepare(self.project, "knowledgeos")
        self.assertEqual(plan["status"], "ready", plan.get("reason"))
        before = migration.state(self.project)
        with patch.object(migration.base, "diagnostics", return_value=[("new", "failure")]):
            with self.assertRaisesRegex(ValueError, "doctor errors changed"):
                migration.apply(plan, Path(self.tmp.name) / "backups")
        self.assertEqual(migration.state(self.project), before)

    def test_foreign_targets_refused(self):
        plan = migration.prepare(self.project, "knowledgeos")
        plan["changes"][".agent-os/tasks.yaml"] = "tasks: []"
        with self.assertRaisesRegex(ValueError, "approved"):
            migration.apply(plan, Path(self.tmp.name) / "backups")

    def test_preexisting_doctor_failure_is_preserved_not_hidden(self):
        with patch.object(migration.base, "diagnostics", side_effect=ValueError("existing spec drift")):
            plan = json.loads(json.dumps(migration.prepare(self.project, "knowledgeos")))
            self.assertEqual(plan["status"], "ready", plan.get("reason"))
            done = migration.apply(plan, Path(self.tmp.name) / "backups")
            self.assertEqual(done["doctor"], "unchanged_existing_errors")
            self.assertEqual(done["doctor_errors"], [["diagnostic_error", "existing spec drift"]])
