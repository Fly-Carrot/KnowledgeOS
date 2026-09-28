"""Task-local route recovery never creates permissions or rewrites history."""
import json
import tempfile
import unittest
from pathlib import Path

from knowledgeos import cli
from tests import test_knowledgeos_cli as support


class RouteReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.call = support.KnowledgeOSCliTests().run_cli
        self.call('init-project', '--root', str(support.ROOT), '--project-root', str(self.root))
        result = self.call('create-task', '--project-root', str(self.root), '--title', 'Draft',
                           '--type', 'manuscript', '--output', 'docs/draft.md',
                           '--acceptance', 'Reviewed draft', '--json')
        self.task = json.loads(result.stdout)['task_id']

    def ensure(self, *extra, check=True):
        return self.call('ensure-route', '--project-root', str(self.root),
                         '--task-id', self.task, '--json', *extra, check=check)

    def test_reuses_existing_profile_without_changing_router_or_tasks(self):
        paths = [self.root / '.agent-os/tasks.yaml', self.root / '.agent-os/workflows/router.yaml']
        before = [p.read_bytes() for p in paths]
        self.assertEqual(cli.build_task_route(self.root, self.task, None)['status'], 'human_triage_required')
        dry = json.loads(self.ensure('--dry-run').stdout)
        self.assertEqual(dry['profile'], 'report_task')
        self.assertFalse((self.root / '.agent-os/workflows/task-routes.json').exists())
        result = json.loads(self.ensure().stdout)
        self.assertEqual(result['route_marker'], 'ROUTE_OK')
        route = cli.build_task_route(self.root, self.task, None)
        self.assertEqual(route['status'], 'routed')
        self.assertEqual(route['allowed_outputs'], ['docs/draft.md'])
        self.assertEqual(route['human_gate'], 'final_reading')
        self.assertEqual(cli.classify_route_write(self.root, self.task, 'docs/other.md')['decision'], 'route_output_denied')
        self.assertEqual([p.read_bytes() for p in paths], before)
        state = self.root / '.agent-os/workflows/task-routes.json'
        same = state.read_bytes()
        self.ensure()
        self.assertEqual(state.read_bytes(), same)
        checks = cli.deep_validate_project(self.root, allow_placeholders=True, skip_external=True)
        self.assertFalse([c.detail for c in checks if c.label == 'workflow_router' and not c.ok])

    def test_refuses_unknown_profile_and_protected_outputs(self):
        self.assertNotEqual(self.ensure('--profile', 'invented', check=False).returncode, 0)
        for output in ['data/raw/input.csv', '../escape.md', '.agent-os/tasks.yaml', 'docs/**']:
            tasks = self.root / '.agent-os/tasks.yaml'
            original = tasks.read_text()
            tasks.write_text(original.replace('docs/draft.md', output))
            self.assertNotEqual(self.ensure('--profile', 'report_task', check=False).returncode, 0)
            tasks.write_text(original)

    def test_changed_profile_or_output_invalidates_mapping(self):
        self.ensure()
        router = self.root / '.agent-os/workflows/router.yaml'
        router.write_text(router.read_text().replace('final_reading', 'different_gate'))
        self.assertEqual(cli.build_task_route(self.root, self.task, None)['status'], 'human_triage_required')

    def test_existing_run_cannot_be_rerouted(self):
        self.ensure()
        self.call('run-task', '--project-root', str(self.root), '--task-id', self.task)
        self.assertEqual(json.loads(self.ensure().stdout)['status'], 'reused')
        p = self.root / '.agent-os/workflows/task-routes.json'
        p.unlink()
        self.assertNotEqual(self.ensure(check=False).returncode, 0)

    def test_native_route_wins_and_does_not_create_mapping(self):
        result = self.call('ensure-route', '--project-root', str(self.root), '--task-id', 'T001', '--json')
        self.assertEqual(json.loads(result.stdout)['status'], 'reused')
        self.assertFalse((self.root / '.agent-os/workflows/task-routes.json').exists())

    def test_later_native_profile_does_not_expand_bound_mapping(self):
        self.ensure()
        router = self.root / '.agent-os/workflows/router.yaml'
        original = router.read_text()
        block = original.split('  report_task:', 1)[1].split('  archive_management:', 1)[0]
        router.write_text(original + '\n  manuscript:' + block)
        self.assertEqual(cli.build_task_route(self.root, self.task, None)['allowed_outputs'], ['docs/draft.md'])
        self.assertEqual(cli.classify_route_write(self.root, self.task, 'docs/other.md')['decision'], 'route_output_denied')

    def test_mapping_store_obeys_its_own_write_policy(self):
        policy = self.root / '.agent-os/write-policy.yaml'
        original = policy.read_text()
        for target in ('task-routes.json', 'task-routes.lock', 'task-routes.tmp'):
            policy.write_text(original.replace('  immutable:', '  immutable:\n    - .agent-os/workflows/' + target))
            self.assertNotEqual(self.ensure(check=False).returncode, 0)
            self.assertFalse((self.root / '.agent-os/workflows/task-routes.json').exists())
            self.assertFalse((self.root / '.agent-os/workflows/task-routes.lock').exists())
        policy.write_text(original)
