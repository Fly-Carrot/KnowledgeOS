import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledgeos import cli, output_registry as registry


class OutputRegistryTests(unittest.TestCase):
    def test_direct_cli_entrypoint_remains_supported(self):
        result = subprocess.run([sys.executable, "-B", cli.__file__, "output-registry", "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--maintenance-run-id", result.stdout)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        agent = self.root / ".agent-os"
        agent.mkdir(parents=True)
        (agent / 'read-policy.yaml').write_text('require_explicit_human_request:\n  - archive/**\n')
        (agent / "tasks.yaml").write_text('tasks:\n  - id: T1\n    title: Test\n    type: test\n    status: completed\n    outputs:\n      - "outputs/old"\n')
        (agent / "write-policy.yaml").write_text('write_policy:\n  immutable:\n    - data/raw/**\n  controlled:\n    - outputs/**\n    - .agent-os/**\n')
        self.run = agent / "runs/RUN-TEST"
        self.run.mkdir(parents=True)
        (self.run / "run.yaml").write_text('task_id: M1\nrun_id: RUN-TEST\nstatus: running\n')
        self.decision = dict(decision_id="D1", task_id="M1", run_id="RUN-TEST", kind="human_decision", status="executed", evidence="explicit user approval")
        (self.run / "decision-events.ndjson").write_text(json.dumps(self.decision) + '\n')
        self.target = self.root / "outputs/new"
        self.target.mkdir(parents=True)
        (self.target / "file").write_bytes(b"preserved artifact")
        self.evidence = self.root / "custody.json"
        self.doc = dict(schema="kos-output-custody-v1", action="relocate", task_id="T1", output="outputs/old", target="outputs/new", artifact_kind="directory", files=[dict(relative_path="file", size_bytes=18, sha256=hashlib.sha256(b"preserved artifact").hexdigest())])
        self.save_doc()
        self.kw = dict(task_id="T1", output="outputs/old", target="outputs/new", action="relocate", evidence=self.evidence, reason="approved maintenance", approved=True, maintenance_root=self.root, maintenance_task_id="M1", maintenance_run_id="RUN-TEST", approval_decision_id="D1")

    def save_doc(self):
        self.evidence.write_text(json.dumps(self.doc))

    def test_restricted_descendant_is_not_hashed_even_in_dry_run(self):
        (self.root / '.agent-os/read-policy.yaml').write_text(
            'require_explicit_human_request:\n  - outputs/new/file\n')
        with patch.object(registry, 'file_digest', side_effect=AssertionError('unauthorized read')):
            with self.assertRaisesRegex(ValueError, 'read approval'):
                self.register(dry_run=True)

    def test_relocated_inventory_is_rechecked_after_registration(self):
        self.register()
        records = registry.load_registry(cli, self.root)
        member = self.target / 'file'
        for content in [b'changed contents', None]:
            if content is None:
                member.unlink()
            else:
                member.write_bytes(content)
            with self.subTest(content=content):
                self.assertFalse(registry.completed_output_status(
                    cli, self.root, 'T1', 'outputs/old', records)[0])

    def register(self, **changes):
        return registry.register(cli, self.root, **(self.kw | changes))

    def test_relocation_preserves_history_and_dry_run(self):
        before = (self.root / '.agent-os/tasks.yaml').read_bytes()
        self.register(dry_run=True)
        self.assertFalse((self.root / '.agent-os/output-registry').exists())
        self.register()
        events = registry.load_registry(cli, self.root)
        self.assertEqual(len(events), 1)
        self.assertTrue(registry.completed_output_status(cli, self.root, 'T1', 'outputs/old', events)[0])
        self.assertEqual(before, (self.root / '.agent-os/tasks.yaml').read_bytes())
        (self.target / 'file').unlink()
        self.target.rmdir()
        self.assertFalse(registry.completed_output_status(cli, self.root, 'T1', 'outputs/old', events)[0])

    def test_retirement_is_not_deletion(self):
        self.register()
        self.doc['action'] = 'retire'; self.save_doc()
        self.register(action='retire')
        events = registry.load_registry(cli, self.root)
        self.assertEqual(len(events), 2)
        self.assertTrue((self.target / 'file').exists())
        (self.target / 'file').unlink(); self.target.rmdir()
        self.assertTrue(registry.completed_output_status(cli, self.root, 'T1', 'outputs/old', events)[0])
        with self.assertRaises(ValueError): self.register(action='retire')

    def test_unknown_completed_output_cannot_be_masked(self):
        self.assertFalse(registry.completed_output_status(cli, self.root, 'T1', 'outputs/unknown', [])[0])
        with self.assertRaises(ValueError): self.register(output='outputs/unknown')

    def test_reject_approval_gaps(self):
        for change in [dict(approved=False), dict(reason=''), dict(approval_decision_id='wrong'), dict(maintenance_task_id='wrong')]:
            with self.subTest(change=change), self.assertRaises(ValueError): self.register(**change)

    def test_reject_path_escape_and_symlinks(self):
        for target in ['../escape', '/tmp/escape', 'outputs/*', 'data/raw/file', 'outputs/../other']:
            with self.subTest(target=target), self.assertRaises(ValueError): self.register(target=target)
        link = self.target / 'link'; link.symlink_to(self.target / 'file')
        with self.assertRaises(ValueError): self.register()

    def test_reject_inventory_drift(self):
        (self.target / 'extra').write_text('not approved')
        with self.assertRaises(ValueError): self.register()
        (self.target / 'extra').unlink()
        (self.target / 'file').write_text('different')
        with self.assertRaises(ValueError): self.register()

    def test_reject_empty_duplicate_and_invalid_inventory(self):
        for rows in [[], self.doc['files'] * 2, [dict(relative_path='../escape', size_bytes=1, sha256='0'*64)], [dict(relative_path='file', size_bytes=-1, sha256='0'*64)]]:
            self.doc['files'] = rows; self.save_doc()
            with self.subTest(rows=rows), self.assertRaises(ValueError): self.register()

    def test_fail_closed_on_ledger_or_evidence_corruption(self):
        self.register()
        p = self.root / '.agent-os/output-registry/events.ndjson'
        original = p.read_text()
        p.write_text(original.replace('approved maintenance', 'changed maintenance'))
        with self.assertRaises(ValueError): registry.load_registry(cli, self.root)
        p.write_text(original)
        evidence = next((p.parent / 'evidence').iterdir()); evidence.write_text('{}')
        with self.assertRaises(ValueError): registry.load_registry(cli, self.root)

    def test_reject_existing_source_and_lock_conflict(self):
        source = self.root / 'outputs/old'; source.mkdir()
        with self.assertRaises(ValueError): self.register()
        source.rmdir()
        base = self.root / '.agent-os/output-registry'; base.mkdir()
        (base / 'registry.lock').write_text('other writer')
        with self.assertRaises(FileExistsError): self.register()

    def test_reject_retirement_of_unrelated_target(self):
        self.doc['action'] = 'retire'; self.save_doc()
        with self.assertRaises(ValueError): self.register(action='retire')

    def test_reject_repeated_relocation(self):
        self.register()
        with self.assertRaises(ValueError): self.register()

    def test_doctor_uses_overlay_but_eval_does_not(self):
        self.register()
        self.assertFalse(cli.output_status(self.root, 'outputs/old')[0])
        self.assertTrue(registry.completed_output_status(cli, self.root, 'T1', 'outputs/old', registry.load_registry(cli, self.root))[0])


if __name__ == '__main__':
    unittest.main()
