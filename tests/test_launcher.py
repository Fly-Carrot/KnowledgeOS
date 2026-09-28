"""The selected executable must own imports, not the caller's directory."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import test_knowledgeos_cli as support


class LauncherTests(unittest.TestCase):
    def test_real_cli_cannot_be_shadowed_by_cwd_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "knowledgeos"
            package.mkdir()
            (package / "__init__.py").write_text("")
            (package / "__main__.py").write_text('print("SHADOWED_FROM_CWD")\n')
            result = subprocess.run([str(support.BIN), "--help"], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("SHADOWED_FROM_CWD", result.stdout)
            self.assertIn("usage: knowledgeos", result.stdout)

    def test_bootstrap_preserves_cwd_arguments_spaces_and_exit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected checkout"
            caller = root / "caller project"
            (selected / "bin").mkdir(parents=True)
            package = selected / "knowledgeos"
            package.mkdir()
            caller.mkdir()
            shutil.copy2(support.BIN, selected / "bin/knowledgeos")
            (package / "__init__.py").write_text("")
            (package / "__main__.py").write_text(
                'import json, os, sys\nprint(json.dumps({"cwd": os.getcwd(), "args": sys.argv[1:]}))\nsys.exit(7)\n')
            args = ["--project-root", ".", "--summary", "a quoted value", "--", "-literal"]
            result = subprocess.run([str(selected / "bin/knowledgeos"), *args], cwd=caller,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 7, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(Path(payload["cwd"]).resolve(), caller.resolve())
            self.assertEqual(payload["args"], args)


if __name__ == "__main__":
    unittest.main()
