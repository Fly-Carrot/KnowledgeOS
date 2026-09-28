import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledgeos import cli


class CheckpointProducerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        template = Path(cli.__file__).resolve().parent.parent / 'templates/project-control-plane'
        shutil.copytree(template, self.root)
        cli.write_text(self.root / '.agent-os/tasks.yaml', 'tasks:\n  - id: T1\n    title: Test\n    status: ready\n    type: code\n    outputs:\n      - result.txt\n')
        self.route = {'status': 'routed', 'allowed_outputs': ['result.txt']}
        self.dispatch = {'status': 'dispatch_ready', 'steps': []}
        for name, value in [('build_task_route', self.route), ('build_dispatch_plan', self.dispatch),
                            ('run_spec_binding', {})]:
            mock = patch.object(cli, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        def context(root, task, run, **kwargs):
            directory = root / '.agent-os/runs' / run
            cli.write_text(directory / 'context-pack.md', '# Context\n')
            cli.write_text(directory / 'spec-snapshot.md', '# Snapshot\n')
        mock = patch.object(cli, 'write_context_pack', side_effect=context)
        mock.start()
        self.addCleanup(mock.stop)
        self.result = cli.create_run_envelope(self.root, 'T1', 'test')
        self.run = self.result['run_id']
        self.directory = self.root / '.agent-os/runs' / self.run

    def produce(self):
        plan = cli.write_task_plan(self.root, 'T1', self.run, summary='bounded work')
        dispatch = cli.record_dispatch_event(self.root, 'T1', self.run, self.dispatch)
        return plan, dispatch

    def manual(self, phases=('review', 'execute', 'report')):
        for phase in phases:
            cli.record_task_phase(self.root, 'T1', self.run, phase=phase, status='completed',
                                  note='real manual work', evidence='test evidence')

    def verify(self):
        return cli.verify_lifecycle(self.root, 'T1', self.run)

    def test_successful_commands_produce_only_route_plan_dispatch(self):
        plan, dispatch = self.produce()
        results = [self.result, dispatch, plan]
        records = cli.load_phase_records(self.directory)
        self.assertEqual([r['phase'] for r in records], ['route', 'dispatch', 'plan'])
        for record, result in zip(records, results):
            self.assertIn(record['producer'], ('run-task', 'plan-task', 'dispatch-task'))
            self.assertEqual(len(record['input_fingerprint']), 64)
            self.assertTrue(record['idempotency_id'])
            self.assertTrue(record['command_event_id'])
            self.assertIn('CHECKPOINT_OK', result['checkpoint']['marker'])
        self.assertEqual(self.verify()['status'], 'failed')
        self.manual()
        self.assertEqual(self.verify()['status'], 'passed', self.verify())

    def test_retry_deduplicates_and_changed_input_adds_checkpoint(self):
        self.produce()
        self.produce()
        self.assertEqual(len(cli.load_phase_records(self.directory)), 3)
        cli.write_task_plan(self.root, 'T1', self.run, summary='changed work')
        records = cli.load_phase_records(self.directory)
        self.assertEqual(len(records), 4)
        self.assertNotEqual(records[1]['input_fingerprint'], records[-1]['input_fingerprint'])
        self.manual()
        self.assertEqual(self.verify()['status'], 'passed', self.verify())

    def test_forged_producer_cannot_use_legacy_phase_receipt(self):
        self.produce()
        self.manual(cli.EXPECTED_PHASE_KEYS)
        self.assertEqual(self.verify()['status'], 'passed', self.verify())
        path = self.directory / 'phases.ndjson'
        records = cli.load_phase_records(self.directory)
        records[-1]['producer'] = 'plan-task'
        path.write_text(''.join(json.dumps(r) + '\n' for r in records))
        self.assertEqual(self.verify()['status'], 'failed')

    def test_missing_or_changed_command_binding_rejected(self):
        self.produce()
        self.manual()
        self.assertEqual(self.verify()['status'], 'passed', self.verify())
        path = self.directory / 'command-events.ndjson'
        events = cli.load_command_events(self.directory)
        events = [e for e in events if e.get('event_type') != 'plan-task']
        path.write_text(''.join(json.dumps(e) + '\n' for e in events))
        self.assertEqual(self.verify()['status'], 'failed')

    def test_plan_artifact_tampering_rejected(self):
        self.produce()
        self.manual()
        self.assertEqual(self.verify()['status'], 'passed', self.verify())
        (self.directory / 'plan.md').write_text('not the produced plan')
        self.assertEqual(self.verify()['status'], 'failed')

    def test_blocked_dispatch_and_dry_run_do_not_produce(self):
        before = cli.load_phase_records(self.directory)
        cli.record_dispatch_event(self.root, 'T1', self.run, {'status': 'blocked', 'steps': []})
        self.assertEqual(cli.load_phase_records(self.directory), before)
        result = cli.create_run_envelope(self.root, 'T1', 'dry', dry_run=True)
        self.assertFalse((self.root / '.agent-os/runs' / result['run_id']).exists())

    def test_failed_plan_does_not_produce(self):
        before = cli.load_phase_records(self.directory)
        (self.directory / 'context-pack.md').unlink()
        with self.assertRaises(ValueError):
            cli.write_task_plan(self.root, 'T1', self.run)
        self.assertEqual(cli.load_phase_records(self.directory), before)

    def test_legacy_manual_phases_remain_valid(self):
        (self.directory / 'phases.ndjson').write_text('')
        cli.record_dispatch_event(self.root, 'T1', self.run, self.dispatch)
        self.manual(cli.EXPECTED_PHASE_KEYS)
        self.assertEqual(self.verify()['status'], 'passed', self.verify())

    def test_receipt_cannot_survive_changed_source_command(self):
        self.produce()
        self.manual()
        events = cli.load_command_events(self.directory)
        for event in events:
            if event.get('event_type') == 'plan-task':
                event['status'] = 'failed'
        (self.directory / 'command-events.ndjson').write_text(''.join(json.dumps(e) + '\n' for e in events))
        self.assertEqual(self.verify()['status'], 'failed')

    def test_changed_fingerprint_or_id_is_rejected(self):
        self.produce()
        self.manual()
        records = cli.load_phase_records(self.directory)
        for field in ('input_fingerprint', 'idempotency_id', 'command_event_id'):
            with self.subTest(field=field):
                changed = [dict(r) for r in records]
                changed[1][field] = 'forged'
                (self.directory / 'phases.ndjson').write_text(''.join(json.dumps(r) + '\n' for r in changed))
                self.assertEqual(self.verify()['status'], 'failed')

    def test_helper_rejects_review_and_failed_command(self):
        for producer in ('review', 'execute', 'report', 'plan-task'):
            with self.subTest(producer=producer), self.assertRaises(ValueError):
                cli.record_checkpoint_producer(self.root, 'T1', self.run, producer=producer,
                                               inputs={}, evidence_paths=[])

    def test_partial_run_failure_does_not_complete_route(self):
        before = set((self.root / '.agent-os/runs').iterdir())
        with patch.object(cli, 'write_context_pack', side_effect=ValueError('failed context')):
            with self.assertRaises(ValueError):
                cli.create_run_envelope(self.root, 'T1', 'failed')
        for directory in set((self.root / '.agent-os/runs').iterdir()) - before:
            self.assertEqual(cli.load_phase_records(directory), [])


if __name__ == '__main__':
    unittest.main()
