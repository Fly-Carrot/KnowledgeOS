import tempfile
import unittest
from pathlib import Path
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from knowledgeos import cli, guidance


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / '.agent-os').mkdir()

    def config(self, text):
        (self.root / '.agent-os/project.yaml').write_text(text)

    def test_default_guided_and_shared_safety(self):
        guided = guidance.render_guidance(self.root, 'kos')
        compact = guidance.render_guidance(self.root, 'kos', mode='compact')
        self.assertIn('guidance_mode: guided', guided)
        self.assertLess(len(compact), len(guided))
        for rule in guidance.SAFETY_RULES:
            self.assertIn(rule, guided)
            self.assertIn(rule, compact)
        self.assertIn(guidance.CONTRACT_VERSION, guided)
        self.assertIn(guidance.CONTRACT_VERSION, compact)

    def test_config_and_model_neutrality(self):
        self.config('project:\n  guidance_mode: compact\n  model: gpt-6-astra\n')
        first = cli.build_agent_guide(self.root)
        self.config('project:\n  guidance_mode: compact\n  model: gpt-5.5\n')
        second = cli.build_agent_guide(self.root)
        self.assertEqual(first.split('## Safety')[1], second.split('## Safety')[1])
        self.assertIn('guidance_mode: compact', second)

    def test_invalid_and_conflicting_modes_rejected_with_source(self):
        for text in ('project:\n  guidance_mode: fast\n',
                     'project:\n  guidance_mode: compact\n  guidance_mode: guided\n'):
            self.config(text)
            with self.assertRaisesRegex(ValueError, 'project.yaml'):
                cli.build_agent_guide(self.root)

    def test_policy_fingerprint_not_history(self):
        first = guidance.configuration_fingerprint(self.root)
        (self.root / '.agent-os/evals.yaml').write_text('old history')
        self.assertEqual(first, guidance.configuration_fingerprint(self.root))
        (self.root / '.agent-os/write-policy.yaml').write_text('immutable: [secret]')
        self.assertNotEqual(first, guidance.configuration_fingerprint(self.root))

    def test_views_share_contract_and_lean_finish(self):
        for view in (cli.build_agent_guide,):
            text = view(self.root)
            normal = text.split('## Normal Path')[1].split('## Contextual Index')[0]
            self.assertIn('eval-task', normal)
            self.assertIn('complete-task', normal)
            self.assertNotIn('verify-context', normal)
            self.assertNotIn('dispatch-report', normal)
            self.assertIn('review and execute require actual evidence', text)
            self.assertIn('reset-project', text)
            self.assertIn('recovered_from=timed_out', text)
        startup = cli.build_startup_prompt(self.root)
        self.assertIn('agent-guide --project-root', startup)
        self.assertIn(guidance.REPORT_RULE, startup)

    def test_normal_path_uses_run_binding_not_repeat_dispatch(self):
        for mode in ('compact', 'guided'):
            text = guidance.render_guidance(self.root, 'kos', mode=mode)
            normal = text.split('## Normal Path')[1].split('## Contextual Index')[0]
            self.assertNotIn('bind dispatch-task --run-id', normal)
            self.assertNotIn('dispatch-task --project-root ' + str(self.root) + ' --task-id <task-id> --run-id', normal)
            self.assertIn('run-bound dispatch evidence', normal)
            self.assertIn('dispatch-task --run-id', text.split('## Contextual Index')[1])

    def test_templates_are_generated(self):
        templates = Path(cli.__file__).resolve().parent.parent / 'templates/project-control-plane'
        for path, surface in (('AGENTS.md', 'entry'), ('.agent-os/startup-prompt.md', 'startup')):
            self.assertEqual((templates / path).read_text(), guidance.render_guidance(
                'CHANGE_ME_PROJECT_ROOT', 'CHANGE_ME_KNOWLEDGEOS_BIN', surface=surface))
        self.assertEqual((templates.parent / 'global-agent-rules.md').read_text(), guidance.render_guidance(
            '.', 'CHANGE_ME_KNOWLEDGEOS_BIN', surface='global'))

    def test_custom_sections_preserved(self):
        generated = guidance.render_guidance(self.root, 'kos')
        existing = 'Custom tone: Chinese.\n' + generated + '\nDo not edit data.\n'
        updated = guidance.merge_generated(existing, guidance.render_guidance(self.root, 'kos', mode='compact'))
        self.assertTrue(updated.startswith('Custom tone: Chinese.\n'))
        self.assertTrue(updated.endswith('\nDo not edit data.\n'))
        with self.assertRaisesRegex(ValueError, 'unmarked'):
            guidance.merge_generated('custom legacy contract', generated)

    def test_handlers_preserve_custom_output_and_report_invalid_config(self):
        for handler in (cli.cmd_agent_guide, cli.cmd_startup_prompt):
            output = self.root / 'custom.md'
            output.write_text('custom legacy contract')
            args = Namespace(project_root=str(self.root), output=str(output), json=False)
            with patch.object(cli, 'REQUIRED_AGENT_GUIDE_FILES', []), redirect_stderr(StringIO()), redirect_stdout(StringIO()):
                self.assertEqual(handler(args), 1)
                self.assertEqual(output.read_text(), 'custom legacy contract')
                output.write_text('Keep Chinese tone.\n' + guidance.render_guidance(self.root, 'kos'))
                self.assertEqual(handler(args), 0)
                self.assertTrue(output.read_text().startswith('Keep Chinese tone.\n'))
                before = output.read_bytes()
                self.config('project:\n  guidance_mode: unsafe\n')
                self.assertEqual(handler(args), 1)
                self.assertEqual(before, output.read_bytes())
            self.config('project:\n  guidance_mode: guided\n')

    def test_render_does_not_mutate_project(self):
        self.config('project:\n  custom_restriction: keep all data\n')
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        cli.build_agent_guide(self.root)
        cli.build_startup_prompt(self.root)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_paths_are_shell_quoted(self):
        text = guidance.render_guidance('/tmp/a project', '/tmp/a bin/kos')
        self.assertIn("'/tmp/a bin/kos' doctor --project-root '/tmp/a project' --summary", text)

    def test_entry_surfaces_load_the_guide_instead_of_repeating_it(self):
        for surface in ('entry', 'startup', 'global'):
            with self.subTest(surface=surface):
                text = guidance.render_guidance('.', 'kos', surface=surface)
                self.assertLess(len(text), 3600)
                self.assertIn('kos agent-guide --project-root .', text)
                self.assertNotIn('### Parameter Examples', text)
                self.assertIn(guidance.REPORT_RULE, text)
                self.assertIn('legacy', text)
                self.assertIn('unavailable', text)
                self.assertIn('in-flight', text)
                self.assertIn('any write/external side effect', text)
                self.assertIn('failed, empty, truncated or incompatible', text)
                for marker in ('KOS_DECISION', 'BOOT_OK', 'CHECKPOINT_OK', 'CAPABILITY_OK',
                               'AGENT_DISPATCH_PLAN', 'AGENT_DISPATCH_OK', 'FLOW_OK', 'SYNC_OK'):
                    self.assertIn(marker, text)

    def test_global_entry_does_not_capture_project_specific_config(self):
        first = guidance.render_guidance(self.root, 'kos', surface='global')
        self.config('project:\n  guidance_mode: invalid\n')
        second = guidance.render_guidance(self.root, 'kos', surface='global')
        self.assertEqual(first, second)
        self.assertNotIn(str(self.root), first)
        self.assertIn('kos agent-guide --project-root .', first)

    def test_route_contract_changes_invalidate_guidance_fingerprint(self):
        before = guidance.configuration_fingerprint(self.root)
        router = self.root / '.agent-os/workflows/router.yaml'
        router.parent.mkdir()
        router.write_text('workflows:\n  report_task:\n    lifecycle_contract: producer-bound-v1\n')
        self.assertNotEqual(before, guidance.configuration_fingerprint(self.root))


if __name__ == '__main__':
    unittest.main()
