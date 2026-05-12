import json
import re
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from knowledgeos.cli import build_workbench_preview_handler

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "examples" / "workbench"


class WorkbenchStaticPreviewTests(unittest.TestCase):
    def test_preview_files_exist_and_are_linked(self):
        index = (WORKBENCH / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="styles.css"', index)
        self.assertIn('src="app.js"', index)
        self.assertIn('data-theme="dark"', index)
        self.assertIn('class="launchpad"', index)
        self.assertIn('class="now-shelf"', index)
        self.assertIn('id="command-toggle"', index)
        self.assertIn('id="onboarding-open"', index)
        self.assertIn('id="command-panel"', index)
        self.assertIn('id="ask-sandbox"', index)
        self.assertIn('id="sandbox-result"', index)
        self.assertIn('id="app-window"', index)
        self.assertIn('id="window-close"', index)
        self.assertIn('id="window-body"', index)
        self.assertIn('id="app-window" hidden', index)
        self.assertIn('id="onboarding-screen"', index)
        self.assertIn("Getting Started", index)
        self.assertIn("Start with Mission", index)
        self.assertIn("Choose an app", index)
        self.assertIn("Click any icon to open a focused app window.", index)
        self.assertIn("Preview state", index)
        self.assertIn("Hover or focus an icon to update the Now Shelf", index)
        self.assertIn("Keep work routed", index)
        self.assertIn('Preview Route', index)
        self.assertIn("Mission Draft", index)
        self.assertIn("Terminal Pro", index)
        self.assertIn("Mission", index)
        self.assertIn("Context", index)
        self.assertIn("Evidence", index)
        self.assertIn("Runs", index)
        self.assertIn("Knowledge", index)
        self.assertIn("Settings", index)
        self.assertNotIn('class="brand-mark"', index)
        self.assertNotIn('id="workspace-name"', index)
        self.assertNotIn('data-theme="system"', index)
        self.assertIn('>Dark</button>', index)
        self.assertNotIn('>Theme</button>', index)
        self.assertNotIn("Theme: system", index)
        self.assertNotIn("Open only what matters.", index)
        self.assertNotIn("KnowledgeOS turns project state", index)
        self.assertNotIn('class="hero-card"', index)
        self.assertNotIn('class="app-sheet"', index)
        self.assertNotIn('id="sheet-body"', index)
        self.assertNotIn("Capability Health</p>", index)
        self.assertNotIn("Current Task</p>", index)
        self.assertTrue((WORKBENCH / "styles.css").exists())
        self.assertTrue((WORKBENCH / "app.js").exists())
        self.assertTrue((WORKBENCH / "workbench-state.fixture.json").exists())

    def test_fixture_matches_workbench_state_contract_and_redacts_paths(self):
        raw = (WORKBENCH / "workbench-state.fixture.json").read_text(encoding="utf-8")
        payload = json.loads(raw)
        self.assertEqual(payload["schema_version"], "knowledgeos.workbench-state.v1")
        self.assertTrue(payload["managed"])
        self.assertEqual(payload["boot"]["claim"], "BOOT_OK")
        self.assertEqual(payload["project_root"], "<PROJECT_ROOT>")
        self.assertIn("tasks", payload)
        self.assertIn("capabilities", payload)
        self.assertIn("runtime_adapters", payload)
        self.assertEqual(payload["runtime_adapters"]["schema_version"], "knowledgeos.runtime-adapters.v1")
        self.assertEqual(payload["runtime_adapters"]["policy"]["default_runtime"], "mock")
        self.assertIn("system_black_box", payload)
        self.assertIsNone(re.search(r"/Users/|/private/|/var/folders/", raw), raw)

    def test_preview_has_light_dark_modes_and_no_external_dependencies(self):
        css = (WORKBENCH / "styles.css").read_text(encoding="utf-8")
        js = (WORKBENCH / "app.js").read_text(encoding="utf-8")
        index = (WORKBENCH / "index.html").read_text(encoding="utf-8")
        combined = "\n".join([index, css, js])
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn('knowledgeos-theme', js)
        self.assertIn('const modes = ["dark", "light"]', js)
        self.assertNotIn('const modes = ["system"', js)
        self.assertNotIn('prefers-color-scheme: dark', css)
        self.assertIn('workbench-state.json', js)
        self.assertIn('workbench-lifecycle.json', js)
        self.assertIn('workbench-state.fixture.json', js)
        self.assertIn('shelfCardsFor', js)
        self.assertIn('aria-pressed', js)
        self.assertIn('openAppWindow', js)
        self.assertIn('closeAppWindow', js)
        self.assertIn('setupOnboarding', js)
        self.assertIn('knowledgeos-onboarding-complete', js)
        self.assertIn('closeOnboarding(true)', js)
        self.assertIn('openOnboarding', js)
        self.assertIn('button.addEventListener("click", () => openAppWindow(button.dataset.app))', js)
        self.assertIn('button.addEventListener("mouseenter", () => renderApp(button.dataset.app))', js)
        self.assertIn('button.addEventListener("focus", () => renderApp(button.dataset.app))', js)
        self.assertIn('dblclick', js)
        self.assertIn('event.key === "Enter"', js)
        self.assertIn('event.key !== "Escape"', js)
        self.assertIn('.launchpad', css)
        self.assertIn('grid-template-rows: minmax(max-content, clamp(430px, 45vh, 470px)) auto', css)
        self.assertIn('align-content: start', css)
        self.assertIn('align-items: start', css)
        self.assertIn('align-self: end', css)
        self.assertIn('justify-self: center', css)
        self.assertIn('grid-template-columns: repeat(3, minmax(180px, 1fr))', css)
        self.assertIn('width: 96px', css)
        self.assertIn('height: 96px', css)
        self.assertNotIn('grid-template-columns: repeat(6', css)
        self.assertNotIn('width: 72px', css)
        self.assertNotIn('height: 72px', css)
        self.assertIn('.now-shelf', css)
        self.assertIn('align-self: start', css)
        self.assertIn('justify-self: stretch', css)
        self.assertIn('width: 100%', css)
        self.assertIn('.command-panel', css)
        self.assertIn('.app-window', css)
        self.assertIn('.window-card', css)
        self.assertIn('.window-grid', css)
        self.assertIn('.window-list', css)
        self.assertIn('.onboarding-screen', css)
        self.assertIn('.onboarding-card', css)
        self.assertIn('.onboarding-steps', css)
        self.assertIn('.onboarding-actions', css)
        self.assertIn('#onboarding-open', css)
        self.assertIn('font-weight: 900', css)
        self.assertNotIn('.hero-card', css)
        self.assertNotIn('.app-sheet', css)
        self.assertIn('width: min(1180px, calc(100vw - 64px))', css)
        self.assertIn('margin: 0 auto', css)
        self.assertNotIn('grid-template-columns: 220px minmax(0, 1fr) 300px', css)
        self.assertNotIn('#0a84ff', css)
        self.assertNotIn('#64d2ff', css)
        self.assertNotRegex(combined, r"https?://")
        self.assertNotIn("unpkg", combined)
        self.assertNotIn("cdn", combined.lower())

    def test_live_preview_handler_serves_static_page_and_live_state(self):
        handler = build_workbench_preview_handler(ROOT, WORKBENCH)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            with urlopen(base + "/", timeout=5) as response:
                html = response.read().decode("utf-8")
            self.assertIn("KnowledgeOS Workbench Preview", html)
            self.assertIn("Launchpad", html)
            self.assertIn("Now Shelf", html)

            with urlopen(base + "/workbench-state.json", timeout=5) as response:
                raw = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
            payload = json.loads(raw)
            self.assertEqual(payload["schema_version"], "knowledgeos.workbench-state.v1")
            self.assertTrue(payload["managed"])
            self.assertEqual(payload["project_root"], "<PROJECT_ROOT>")
            self.assertEqual(payload["runtime_adapters"]["schema_version"], "knowledgeos.runtime-adapters.v1")
            self.assertEqual(payload["runtime_adapters"]["policy"]["real_cli_execution"], "disabled_until_adapter_phase")
            self.assertNotIn(str(ROOT), raw)

            with urlopen(base + "/workbench-lifecycle.json", timeout=5) as response:
                lifecycle_raw = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
            lifecycle = json.loads(lifecycle_raw)
            self.assertEqual(lifecycle["schema_version"], "knowledgeos.workbench-lifecycle.v1")
            self.assertEqual(
                [stage["key"] for stage in lifecycle["stages"]],
                ["doctor", "route", "dispatch", "write_guard", "run", "eval", "receipt"],
            )
            self.assertNotIn(str(ROOT), lifecycle_raw)

            with urlopen(base + "/healthz", timeout=5) as response:
                self.assertEqual(response.read().decode("utf-8"), "ok\n")

            request = Request(
                base + "/api/ask-sandbox",
                data=json.dumps({"prompt": f"Please create a report from {ROOT}"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                sandbox_raw = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
            sandbox = json.loads(sandbox_raw)
            self.assertEqual(sandbox["schema_version"], "knowledgeos.ask-sandbox.v1")
            self.assertFalse(sandbox["executed"])
            self.assertFalse(sandbox["project_mutation"])
            self.assertEqual(sandbox["recommended_next_step"], "route_through_os")
            self.assertIn("<PROJECT_ROOT>", sandbox["prompt"])
            self.assertNotIn(str(ROOT), sandbox_raw)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
