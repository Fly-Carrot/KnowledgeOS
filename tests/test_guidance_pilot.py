"""Bounded deterministic pilots, not model-performance qualification."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from knowledgeos import cli, guidance
from tests import test_knowledgeos_cli as support


class GuidancePilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.helper = support.KnowledgeOSCliTests()
        self.call = self.helper.run_cli
        self.runtime = self.base / 'runtime'
        self.call('init-os', '--root', str(support.ROOT), '--os-root', str(self.runtime))
        hook = self.runtime / 'global-agent-fabric/hooks/after-task.sh'
        hook.write_text("#!/bin/sh\necho sync >> sync-count.txt\necho '[SYNC_OK]'\n")
        hook.chmod(0o755)

    def project(self, name, mode):
        project = self.base / name
        project.mkdir()
        self.call('init-project', '--root', str(support.ROOT), '--project-root', str(project),
                  '--name', name, '--global-root', str(self.runtime / 'global-agent-fabric'),
                  '--capability-root', str(self.runtime / 'capability-layer'))
        config = project / '.agent-os/project.yaml'
        config.write_text(config.read_text().replace('project:\n', f'project:\n  guidance_mode: {mode}\n', 1))
        return project

    def workload(self, project, task_type):
        router = project / '.agent-os/workflows/router.yaml'
        profiles = cli.parse_workflow_profiles(router)
        if task_type == 'engineering_change':
            profiles[task_type] = copy.deepcopy(profiles['report_task'])
            profiles[task_type]['allowed_outputs'].append('src/')
            profiles[task_type]['eval_profile'] = 'engineering_task'
        profile = profiles[task_type]
        profile['lifecycle_contract'] = 'producer-bound-v1'
        profile['route_order'] = [line for line in profile['route_order']
                                  if not line.startswith(('dispatch-task', 'verify-'))]
        router.write_text(cli.render_workflow_profiles(profiles))
        target = 'src/calculation.py' if task_type == 'engineering_change' else 'docs/report.md'
        task = json.loads(self.call('create-task', '--project-root', str(project), '--title', 'Bounded pilot',
                                   '--type', task_type, '--output', target, '--acceptance', 'Verified artifact', '--json').stdout)['task_id']
        self.call('doctor', '--project-root', str(project), '--project-only', '--summary')
        guard = cli.classify_route_write(project, task, target)
        self.assertEqual(guard['decision'], 'allow')
        run = cli.create_run_envelope(project, task, 'Pilot')['run_id']
        cli.write_task_plan(project, task, run, summary='Produce one checked artifact without repeated dispatch or verifiers')
        artifact = project / target
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_text('assert 2 + 2 == 4\n' if task_type == 'engineering_change'
                            else '# Pilot report\n\nSource: deterministic fixture.\nUncertainty: not a scientific inference.\n')
        if task_type == 'engineering_change':
            result = subprocess.run([sys.executable, '-B', str(artifact)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertIn('Uncertainty:', artifact.read_text())
        for phase in ('review', 'execute', 'report'):
            cli.record_task_phase(project, task, run, phase=phase, status='completed',
                                  note='Checked deterministic pilot artifact and actual execution where applicable', evidence=target)
        cli.write_task_eval(project, task, run)
        self.assertEqual(cli.complete_task(project, task, run, 'Pilot complete')['sync_status'], 'SYNC_OK')
        self.assertEqual(cli.complete_task(project, task, run, 'Pilot complete')['sync_status'], 'SYNC_OK')
        events = cli.load_command_events(project / '.agent-os/runs' / run)
        self.assertEqual(len([e for e in events if e.get('event_type') == 'dispatch-task']), 1)
        self.assertEqual((project / 'sync-count.txt').read_text().splitlines(), ['sync'])
        self.assertEqual(len(list((project / '.agent-os/runs').iterdir())), 1)
        return run

    def test_two_project_types_both_modes_keep_real_completion_gates(self):
        for mode in ('guided', 'compact'):
            for task_type in ('report_task', 'engineering_change'):
                with self.subTest(mode=mode, task_type=task_type):
                    project = self.project(mode + '-' + task_type, mode)
                    entry = cli.build_startup_prompt(project)
                    self.assertIn('agent-guide', entry)
                    self.assertIn(f'guidance_mode: {mode}', cli.build_agent_guide(project))
                    self.workload(project, task_type)

    def test_entry_migration_and_rollback_do_not_touch_active_run_history(self):
        project = self.project('existing-project', 'guided')
        task = json.loads(self.call('create-task', '--project-root', str(project), '--title', 'Existing work',
                                   '--type', 'report_task', '--output', 'docs/old.md', '--acceptance', 'Keep run', '--json').stdout)['task_id']
        run = cli.create_run_envelope(project, task, 'Existing work')['run_id']
        cli.write_task_plan(project, task, run, summary='Keep the current run and contract')
        before = {p: p.read_bytes() for p in (project / '.agent-os/runs').rglob('*') if p.is_file()}
        entry = project / 'AGENTS.md'
        original = 'Keep this exact custom restriction.\n' + entry.read_text() + '\nKeep raw data immutable.\n'
        entry.write_text(original)
        updated = guidance.merge_generated(original, guidance.render_guidance(project, support.BIN, surface='entry'))
        entry.write_text(updated)
        self.assertTrue(updated.startswith('Keep this exact custom restriction.\n'))
        self.assertTrue(updated.endswith('\nKeep raw data immutable.\n'))
        self.assertEqual(before, {p: p.read_bytes() for p in (project / '.agent-os/runs').rglob('*') if p.is_file()})
        self.assertEqual(cli.verify_context_contract(project, task, run)['status'], 'passed')
        entry.write_text(original)
        self.assertEqual(entry.read_text(), original)
        self.assertEqual(before, {p: p.read_bytes() for p in (project / '.agent-os/runs').rglob('*') if p.is_file()})

    def test_missing_guide_inputs_and_unmarked_or_ambiguous_rules_fail_closed(self):
        project = self.project('missing-input', 'guided')
        (project / '.agent-os/write-policy.yaml').unlink()
        result = self.call('agent-guide', '--project-root', str(project), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing required files', result.stderr)
        generated = guidance.render_guidance('.', 'kos', surface='global')
        for old in ('unmarked custom instructions', generated + generated,
                    guidance.END + '\ncustom\n' + guidance.BEGIN):
            with self.subTest(old=old[:30]), self.assertRaises(ValueError):
                guidance.merge_generated(old, generated)


if __name__ == '__main__':
    unittest.main()
