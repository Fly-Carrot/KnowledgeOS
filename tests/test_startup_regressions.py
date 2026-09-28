"""Startup regressions: evidence is not configuration; commands must be executable."""
import re
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from knowledgeos import cli, guidance

ROOT = Path(__file__).resolve().parents[1]


class StartupRegressionTests(unittest.TestCase):
    def test_discovery_ignores_cold_copies_but_keeps_nested_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            active = root / 'Active'
            nested = active / 'packages/child'
            cold = [active / 'archive/old', active / 'outputs/snapshot',
                    active / 'initialization-backups/old', active / 'backups/old',
                    active / 'knowledgeos-init-20260901T000000Z']
            for project in [active, nested, *cold]:
                (project / '.agent-os').mkdir(parents=True)
            self.assertEqual(cli.discover_agent_os_projects([root]), [active, nested])
            self.assertEqual(cli.discover_agent_os_projects([cold[0]]), [cold[0]])

    def test_historical_evidence_does_not_poison_placeholder_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / '.agent-os'
            for relative in ('runs/RUN-1/phases.ndjson', 'runs/RUN-1/spec-snapshot.md',
                             'threads/THREAD-1/thread-plan.ndjson', 'receipts/latest.md',
                             'handoffs/current.md', 'inbox/unclassified.md'):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('rg CHANGE_ME returned no matches\n')
            self.assertEqual(cli.find_placeholder_markers(root), [])

    def test_real_configuration_placeholders_remain_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / '.agent-os'
            for relative in ('workspace.yaml', 'fabric-link.yaml', 'workflows/router.yaml',
                             'custom-policy.yaml'):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('root: CHANGE_ME_REQUIRED_ROOT\n')
            self.assertEqual(len(cli.find_placeholder_markers(root)), 4)

    def test_generated_startup_commands_quote_project_paths(self):
        with tempfile.TemporaryDirectory(prefix='kos startup ') as tmp:
            project = Path(tmp) / "Example Project's"
            result = subprocess.run([str(ROOT / 'bin/knowledgeos'), 'init-project',
                                     '--root', str(ROOT), '--project-root', str(project)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for relative in ('AGENTS.md', '.agent-os/startup-prompt.md'):
                text = (project / relative).read_text()
                self.assertIn(guidance.configuration_fingerprint(project.resolve()), text)
                commands = [value for value in re.findall(r'`([^`]+)`', text)
                            if ' --project-root ' in value]
                self.assertTrue(commands)
                for command in commands:
                    args = shlex.split(command)
                    self.assertEqual(args[args.index('--project-root') + 1], str(project.resolve()))

    def test_init_dry_run_is_non_mutating(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'new project'
            result = subprocess.run([str(ROOT / 'bin/knowledgeos'), 'init-project',
                                     '--root', str(ROOT), '--project-root', str(project), '--dry-run'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(project.exists())

    def test_init_preserves_existing_custom_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            agents = project / 'AGENTS.md'
            agents.write_text('Custom instructions: preserve exactly.\n')
            before = agents.read_bytes()
            result = subprocess.run([str(ROOT / 'bin/knowledgeos'), 'init-project',
                                     '--root', str(ROOT), '--project-root', str(project)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(agents.read_bytes(), before)
