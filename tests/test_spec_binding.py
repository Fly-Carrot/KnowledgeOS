import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledgeos import cli


class SpecBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.os = self.root / '.agent-os'
        self.os.mkdir()
        cli.write_text(self.os / 'decisions.yaml', 'decisions: []\n')
        cli.write_text(self.os / 'evals.yaml', 'evals: {}\n')
        cli.write_text(self.os / 'tasks.yaml', 'tasks:\n  - id: T1\n    title: Test\n    type: code\n    outputs:\n      - result.txt\n    acceptance:\n      - works\n  - id: T2\n    title: Other\n')
        cli.write_text(self.os / 'specs.yaml', 'active_spec: S2\nspecs:\n  - id: S1\n    status: active\n  - id: S2\n    status: active\n')
        for sid in ['S1', 'S2']:
            for name in ['spec.md', 'acceptance.md', 'non-goals.md']:
                cli.write_text(self.os / 'specs' / sid / name, f'# {sid} {name}\n')
        self.run = self.os / 'runs' / 'R1'
        cli.write_text(self.run / 'run.yaml', 'run_id: R1\ntask_id: T1\n')
        for name, value in [('build_task_route', {}), ('build_dispatch_plan', {})]:
            mock = patch.object(cli, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def pack(self, **kwargs):
        return cli.write_context_pack(self.root, 'T1', 'R1', **kwargs)

    def task_field(self, text):
        path = self.os / 'tasks.yaml'
        cli.write_text(path, cli.read_text(path).replace('    title: Test', text + '\n    title: Test'))

    def test_alignment_survives_unrelated_active(self):
        cli.align_spec(self.root, task_id='T1', spec_id='S1')
        self.assertEqual(self.pack()['spec_id'], 'S1')
        self.assertEqual(self.pack()['binding_source'], 'task')

    def test_new_run_never_inherits_active(self):
        result = self.pack()
        self.assertEqual(result['spec_id'], 'none')
        self.assertEqual(result['binding_status'], 'unbound')

    def test_explicit_none_and_required_policy(self):
        self.task_field('    spec_id: none')
        self.assertEqual(self.pack()['binding_status'], 'none')
        cli.write_text(self.os / 'project.yaml', 'spec_required: true\n')
        with self.assertRaisesRegex(ValueError, 'required'):
            self.pack()

    def test_explicit_thread_not_current(self):
        self.task_field('    thread_id: CHAT1')
        cli.write_text(self.os / 'threads' / 'CHAT1' / 'thread.json', json.dumps({'thread_id': 'CHAT1', 'spec_id': 'S1'}))
        cli.write_text(self.os / 'threads' / 'current.json', json.dumps({'thread_id': 'CHAT2', 'spec_id': 'S2'}))
        self.assertEqual(self.pack()['spec_id'], 'S1')
        cli.write_text(self.os / 'threads' / 'CHAT1' / 'thread.json', json.dumps({'thread_id': 'CHAT1', 'spec_id': 'S2'}))
        self.assertEqual(self.pack()['spec_id'], 'S1')

    def test_invalid_specs_rejected(self):
        for sid in ['MISSING', '../S1', '.']:
            with self.subTest(sid=sid), self.assertRaises((ValueError, KeyError, FileNotFoundError)):
                cli.align_spec(self.root, task_id='T1', spec_id=sid)
        cli.write_text(self.os / 'specs.yaml', 'active_spec: S1\nspecs:\n  - id: S1\n    status: revoked\n')
        with self.assertRaisesRegex(ValueError, 'revoked'):
            cli.align_spec(self.root, task_id='T1', spec_id='S1')

    def test_incomplete_and_cross_project_rejected(self):
        (self.os / 'specs' / 'S1' / 'acceptance.md').unlink()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            cli.align_spec(self.root, task_id='T1', spec_id='S1')
        cli.write_text(self.os / 'specs.yaml', 'specs:\n  - id: S2\n    project_root: /other-project\n')
        with self.assertRaisesRegex(ValueError, 'project'):
            cli.align_spec(self.root, task_id='T1', spec_id='S2')

    def test_duplicate_spec_conflict(self):
        path = self.os / 'specs.yaml'
        cli.write_text(path, cli.read_text(path) + '  - id: S1\n    status: active\n')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            cli.align_spec(self.root, task_id='T1', spec_id='S1')

    def test_relevant_drift_and_realign_preserves_snapshot(self):
        cli.align_spec(self.root, task_id='T1', spec_id='S1')
        self.pack()
        before = cli.read_text(self.run / 'spec-snapshot.md')
        cli.write_text(self.os / 'specs' / 'S2' / 'spec.md', 'unrelated change')
        self.pack()
        cli.write_text(self.os / 'specs' / 'S1' / 'spec.md', 'relevant change')
        with self.assertRaisesRegex(ValueError, 'drift'):
            self.pack()
        cli.align_spec(self.root, task_id='T1', spec_id='S1', run_id='R1')
        self.assertNotEqual(cli.read_text(self.run / 'spec-snapshot.md'), before)
        self.assertTrue(any(p.read_text() == before for p in self.run.rglob('spec-snapshot*.md') if p != self.run / 'spec-snapshot.md'))

    def test_verification_checks_frozen_spec_not_active(self):
        cli.align_spec(self.root, task_id='T1', spec_id='S1')
        self.pack()
        cli.write_task_plan(self.root, 'T1', 'R1')
        self.assertEqual(cli.verify_context_contract(self.root, 'T1', 'R1')['status'], 'passed')
        cli.write_text(self.os / 'specs' / 'S1' / 'spec.md', 'changed')
        result = cli.verify_context_contract(self.root, 'T1', 'R1')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('spec_drift', str(result['errors']))

    def test_task_rebinding_does_not_change_existing_run(self):
        cli.align_spec(self.root, task_id='T1', spec_id='S1')
        self.pack()
        cli.align_spec(self.root, task_id='T1', spec_id='S2')
        self.assertEqual(self.pack()['spec_id'], 'S1')
        cli.write_text(self.os / 'runs' / 'R2' / 'run.yaml', 'run_id: R2\ntask_id: T1\n')
        self.assertEqual(cli.write_context_pack(self.root, 'T1', 'R2')['spec_id'], 'S2')

    def test_legacy_snapshot_is_explicit_and_not_overwritten(self):
        original = '# Spec Snapshot\nSpec ID: S1\nSpec Fingerprint: ' + cli.spec_fingerprint(self.root, 'S1') + '\n\n## Body\nlegacy body\n'
        cli.write_text(self.run / 'spec-snapshot.md', original)
        self.assertEqual(self.pack()['binding_source'], 'legacy_snapshot')
        self.assertEqual(cli.read_text(self.run / 'spec-snapshot.md'), original)

    def test_thread_constraint_cannot_be_overridden(self):
        self.task_field('    thread_id: CHAT1')
        cli.write_text(self.os / 'threads' / 'CHAT1' / 'thread.json', json.dumps({'thread_id': 'CHAT1', 'spec_id': 'S2', 'required_spec_id': 'S2'}))
        with self.assertRaisesRegex(ValueError, 'constraint'):
            cli.align_spec(self.root, task_id='T1', spec_id='S1')

    def test_spec_symlink_escape_is_rejected(self):
        path = self.os / 'specs' / 'S1' / 'spec.md'
        path.unlink()
        cli.write_text(self.root / 'outside.md', 'outside')
        path.symlink_to(self.root / 'outside.md')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            cli.align_spec(self.root, task_id='T1', spec_id='S1')

    def test_duplicate_task_binding_fields_are_conflict(self):
        self.task_field('    spec_id: S1\n    spec_id: S2')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.pack()

    def test_plan_cannot_be_written_after_bound_drift(self):
        cli.align_spec(self.root, task_id='T1', spec_id='S1')
        self.pack()
        cli.write_text(self.os / 'specs' / 'S1' / 'spec.md', 'changed')
        with self.assertRaisesRegex(ValueError, 'drift'):
            cli.write_task_plan(self.root, 'T1', 'R1')

    def test_realign_requires_new_plan(self):
        cli.align_spec(self.root, task_id='T1', spec_id='S1')
        self.pack()
        cli.write_task_plan(self.root, 'T1', 'R1')
        cli.align_spec(self.root, task_id='T1', spec_id='S2', run_id='R1')
        self.assertFalse((self.run / 'plan.md').exists())
        self.assertEqual(cli.verify_context_contract(self.root, 'T1', 'R1')['status'], 'failed')

    def test_project_requirement_is_not_relaxed_by_registry(self):
        cli.write_text(self.os / 'project.yaml', 'spec_required: true\n')
        path = self.os / 'specs.yaml'
        cli.write_text(path, 'spec_required: false\n' + cli.read_text(path))
        with self.assertRaisesRegex(ValueError, 'required'):
            self.pack()

    def test_realign_without_id_keeps_explicit_task_binding(self):
        cli.align_spec(self.root, task_id='T1', spec_id='S1')
        self.assertEqual(cli.align_spec(self.root, task_id='T1')['spec_id'], 'S1')

    def test_new_binding_drift_cannot_use_legacy_waiver(self):
        cli.align_spec(self.root, task_id='T1', spec_id='S1')
        self.pack()
        cli.write_task_plan(self.root, 'T1', 'R1')
        cli.write_text(self.os / 'specs' / 'S1' / 'spec.md', 'changed')
        self.assertEqual(cli.verify_context_contract(self.root, 'T1', 'R1', allow_spec_drift=True)['status'], 'failed')

    def route_write(self, task_id='T1'):
        with patch.object(cli, 'build_task_route', return_value={'status': 'routed', 'allowed_outputs': ['result.txt']}), patch.object(cli, 'classify_write', return_value={'decision': 'allow', 'path': 'result.txt', 'inside_project': True}):
            return cli.classify_route_write(self.root, task_id, 'result.txt')

    def test_route_write_blocks_only_related_unfinished_drift(self):
        cli.align_spec(self.root, task_id='T1', spec_id='S1')
        self.pack()
        cli.write_text(self.os / 'specs' / 'S2' / 'spec.md', 'unrelated')
        self.assertEqual(self.route_write()['decision'], 'allow')
        cli.write_text(self.os / 'specs' / 'S1' / 'spec.md', 'changed')
        blocked = self.route_write()
        self.assertEqual(blocked['decision'], 'spec_drift')
        self.assertIn('R1', str(blocked))
        self.assertEqual(self.route_write('T2')['decision'], 'allow')
        cli.write_text(self.run / 'run.yaml', 'run_id: R1\ntask_id: T1\nstatus: completed\n')
        self.assertEqual(self.route_write()['decision'], 'allow')

    def test_route_write_without_frozen_run_does_not_resolve_spec(self):
        self.task_field('    spec_id: MISSING')
        self.assertEqual(self.route_write()['decision'], 'allow')
        self.assertEqual(self.route_write('T2')['decision'], 'allow')

    def test_invalid_run_binding_leaves_no_partial_envelope(self):
        self.task_field('    status: ready\n    spec_id: MISSING')
        before = set(self.os.rglob('*'))
        with patch.object(cli, 'build_task_route', return_value={'status': 'routed'}):
            with self.assertRaises((ValueError, KeyError)):
                cli.create_run_envelope(self.root, 'T1', 'invalid binding')
        self.assertEqual(set(self.os.rglob('*')), before)

    def test_dry_run_validates_binding_without_writes(self):
        self.task_field('    status: ready\n    spec_id: MISSING')
        before = set(self.os.rglob('*'))
        with patch.object(cli, 'build_task_route', return_value={'status': 'routed'}):
            with self.assertRaises((ValueError, KeyError)):
                cli.create_run_envelope(self.root, 'T1', 'invalid binding', dry_run=True)
        self.assertEqual(set(self.os.rglob('*')), before)


if __name__ == '__main__':
    unittest.main()
