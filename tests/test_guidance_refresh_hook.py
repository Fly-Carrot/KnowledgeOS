import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('refresh', ROOT / 'bin/kos-guidance-refresh.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = self.base / '.codex'
        self.root = self.base / 'project'
        for p in [self.home, self.root / '.agent-os', self.base / 'KnowledgeOS/bin']:
            p.mkdir(parents=True)
        for p in [self.home / 'AGENTS.md', self.root / 'AGENTS.md',
                  self.root / '.agent-os/project.yaml', self.base / 'KnowledgeOS/bin/knowledgeos']:
            p.write_text('fixture\n')
        self.addCleanup(patch.stopall)
        patch.object(refresh.Path, 'home', return_value=self.base).start()
        patch.object(refresh, 'LAUNCHER', self.base / 'KnowledgeOS/bin/knowledgeos').start()
        self.payload = {'hook_event_name': 'UserPromptSubmit', 'cwd': str(self.root)}

    def test_stable_revision_and_changed_rule(self):
        a = refresh.response(self.payload, self.home)
        self.assertEqual(a, refresh.response(self.payload, self.home))
        (self.root / 'AGENTS.md').write_text('changed\n')
        self.assertNotEqual(a, refresh.response(self.payload, self.home))
        text = a['hookSpecificOutput']['additionalContext']
        self.assertIn('preserve existing runs', text)
        self.assertLess(len(text.split()), 90)
        self.assertNotIn('fixture', text)
        self.assertNotIn('decision', a)

    def test_unmanaged_no_hint(self):
        self.payload['cwd'] = str(self.base)
        self.assertEqual({}, refresh.response(self.payload, self.home))

    def test_checkout_need_not_be_in_home_directory(self):
        original = self.base / 'KnowledgeOS/bin/knowledgeos'
        other = self.base / 'checkout with spaces/bin/knowledgeos'
        other.parent.mkdir(parents=True)
        original.rename(other)
        with patch.object(refresh, 'LAUNCHER', other):
            self.assertIn('hookSpecificOutput', refresh.response(self.payload, self.home))

    def test_nested_directory(self):
        child = self.root / 'src'
        child.mkdir()
        self.payload['cwd'] = str(child)
        self.assertIn('hookSpecificOutput', refresh.response(self.payload, self.home))

    def test_wrong_event_and_missing_cwd(self):
        for payload in [[], {}, {'hook_event_name': 'Stop'},
                        {'hook_event_name': 'UserPromptSubmit', 'cwd': '.'}]:
            self.assertEqual({}, refresh.response(payload, self.home))

    def test_main_failure_is_silent_success(self):
        for raw in [b'bad json', b'x' * (refresh.LIMIT + 1), b'[]', json.dumps(self.payload).encode()]:
            with patch.object(refresh.sys, 'stdin') as stdin, patch.object(refresh.sys, 'stdout', new_callable=io.StringIO) as out:
                stdin.buffer = io.BytesIO(raw)
                with patch.object(refresh, 'bounded_read', side_effect=PermissionError):
                    self.assertIsNone(refresh.main())
                self.assertEqual('', out.getvalue())

    def test_large_and_symlink_file_rejected(self):
        file = self.root / 'large'
        file.write_bytes(b'x' * (refresh.LIMIT + 1))
        with self.assertRaises(ValueError):
            refresh.bounded_read(file)
        link = self.root / 'link'
        link.symlink_to(file)
        with self.assertRaises(OSError):
            refresh.bounded_read(link)

    def test_no_project_writes(self):
        before = {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        refresh.response(self.payload, self.home)
        after = {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
