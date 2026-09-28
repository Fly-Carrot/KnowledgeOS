"""Validate a source distribution without the maintainer's runtime history."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from knowledgeos import cli


ROOT = Path(__file__).resolve().parents[1]


class ReleasePortabilityTests(unittest.TestCase):
    def export(self, target):
        for relative in cli.REQUIRED_PUBLIC_FILES + ['Makefile', 'bin/knowledgeos']:
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for directory in ('knowledgeos', 'templates'):
            shutil.copytree(ROOT / directory, target / directory, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        script = ROOT / 'examples/scenarios/run_release_smoke.sh'
        self.assertTrue(script.is_file(), 'Missing clean-distribution validation entry')
        shutil.copy2(script, target / script.relative_to(ROOT))

    def check_export(self, *, break_distribution=False):
        with tempfile.TemporaryDirectory(prefix='kos release ') as directory:
            root = Path(directory) / 'source with spaces'
            self.export(root)
            self.assertFalse((root / '.agent-os').exists())
            self.assertFalse((root / 'global-agent-fabric').exists())
            self.assertFalse((root / 'capability-layer').exists())
            # A local history record must neither authorize nor poison the release check.
            history = root / '.agent-os/tasks.yaml'
            history.parent.mkdir()
            history.write_text('local history: must stay byte-identical\n')
            if break_distribution:
                (root / 'docs/architecture.md').unlink()
            before = {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in root.rglob('*') if p.is_file()}
            result = subprocess.run(['make', 'release-project'], cwd=root,
                                    env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                    capture_output=True, text=True, timeout=60)
            after = {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before, after, 'Release validation changed the source checkout')
            return result

    def test_clean_export_smoke_preserves_local_history(self):
        result = self.check_export()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('RELEASE_PROJECT_OK', result.stdout)

    def test_missing_public_source_still_fails(self):
        result = self.check_export(break_distribution=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('public_file', result.stdout)
        self.assertNotIn('RELEASE_PROJECT_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
