"""Bounded runtime/authorization contracts; no real host invocation."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

from knowledgeos import cli


ENTRY = {"id": "codex-worker", "kind": "subagent", "status": "enabled",
         "runtime_tool": cli.CODEX_RUNTIME_TOOL, "runtime_agent_type": "worker"}


def snapshot():
    return cli.HostCapabilitySnapshot({"schema_version": "knowledgeos.host-capabilities.v1", "host_id": "host",
            "session_id": "session", "source": "host_bridge", "connected": True,
            "task_invocations": [],
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "tools": [{"name": "spawn_agent", "schema_version": "1", "input_schema": {
                "type": "object", "properties": {"message": {"type": "string"}, "fork_context": {"type": "boolean"}},
                "required": ["message"], "additionalProperties": False}}]},
                attestation="host_attested", evidence="trusted-in-process-test-host")


class RuntimeContractTests(unittest.TestCase):
    def test_history_isolation_is_explicit_and_never_silently_widened(self):
        host = snapshot()
        self.assertIs(cli.runtime_contract(ENTRY, host)['runtime_arguments']['fork_context'], False)
        for value in ('all', '9', '3', ''):
            self.assertFalse(cli.runtime_contract({**ENTRY, 'fork_turns': value}, host)['runtime_callable'])
        del host['tools'][0]['input_schema']['properties']['fork_context']
        self.assertFalse(cli.runtime_contract(ENTRY, host)['runtime_callable'])
        host['tools'][0]['input_schema']['properties']['fork_turns'] = {'type': 'string'}
        self.assertEqual(cli.runtime_contract({**ENTRY, 'fork_turns': '3'}, host)['runtime_arguments']['fork_turns'], '3')

    def test_full_history_requires_specific_command_backed_approval(self):
        root = Path('/project')
        event = {'decision_id': 'D1', 'task_id': 'T1', 'run_id': 'R1', 'kind': 'human_decision',
                 'status': 'executed', 'evidence': 'user message explicitly approving fork_turns=all for codex-worker',
                 'summary': 'Approve fork_turns=all for codex-worker', 'chosen': 'approve_full_history:codex-worker'}
        with patch.object(cli, 'ensure_run_belongs_to_task', return_value=Path('/run')), \
             patch.object(cli, 'load_decision_events', return_value=[event]), \
             patch.object(cli, 'decision_event_has_command_event', return_value=True):
            cli.require_full_history_approval(root, task_id='T1', run_id='R1', decision_id='D1', subagent_id='codex-worker')
            for key, value in [('task_id', 'T2'), ('kind', 'final_decision'), ('evidence', ''), ('summary', 'Approve ordinary work')]:
                changed = {**event, key: value}
                with patch.object(cli, 'load_decision_events', return_value=[changed]), self.assertRaises(ValueError):
                    cli.require_full_history_approval(root, task_id='T1', run_id='R1', decision_id='D1', subagent_id='codex-worker')
            with patch.object(cli, 'decision_event_has_command_event', return_value=False), self.assertRaises(ValueError):
                cli.require_full_history_approval(root, task_id='T1', run_id='R1', decision_id='D1', subagent_id='codex-worker')
            for change in ({'summary': 'Deny fork_turns=all for codex-worker', 'chosen': 'deny'},
                           {'summary': 'Approve fork_turns=all for codex-worker-extra', 'chosen': 'approve_full_history:codex-worker-extra'}):
                with patch.object(cli, 'load_decision_events', return_value=[{**event, **change}]), self.assertRaises(ValueError):
                    cli.require_full_history_approval(root, task_id='T1', run_id='R1', decision_id='D1', subagent_id='codex-worker')

    def test_source_label_alone_is_not_attestation(self):
        self.assertFalse(cli.valid_host_snapshot(dict(snapshot())))

    def test_explicit_import_pins_session_digest_and_is_not_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "host.json"
            path.write_text(json.dumps(snapshot()))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            host = cli.import_host_capability_snapshot(path, host_id="host", session_id="session",
                expected_sha256=digest, evidence="parent-tool-list-1")
            value = cli.tool_summary(ENTRY, host_snapshot=host)
            self.assertTrue(value["host_available"])
            self.assertEqual(value["host_provenance"]["attestation"], "parent_attested")
            self.assertFalse(value["host_provenance"]["authenticated"])
            for overrides in ({"session_id": "other"}, {"expected_sha256": "0" * 64}, {"evidence": ""}):
                options = dict(host_id="host", session_id="session", expected_sha256=digest, evidence="ref")
                options.update(overrides)
                with self.assertRaises(ValueError):
                    cli.import_host_capability_snapshot(path, **options)
            host["authorizations"] = [{"source": "user_message", "evidence_id": "self-authorized",
                "project_root": "/project", "task_id": "T1", "operation": "subagent_read_only",
                "targets": ["codex-worker"], "max_invocations": 3, "used_invocations": [],
                "expires_at": host["expires_at"], "revoked": False}]
            path.write_text(json.dumps(host))
            host = cli.import_host_capability_snapshot(path, host_id="host", session_id="session",
                expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), evidence="parent-tool-list-1")
            self.assertTrue(self.plan(host=host)["approval_required"])

    def test_run_dispatch_reuses_steps_but_rechecks_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"; run.mkdir()
            (root / ".agent-os").mkdir()
            task = {"id": "T1", "type": "engineering_change"}
            host = snapshot()
            with patch.object(cli, "find_task", return_value=task), \
                 patch.object(cli, "build_task_route", return_value={"status": "routed"}), \
                 patch.object(cli, "load_tool_registry", return_value=[ENTRY]), \
                 patch.object(cli, "load_dispatch_policy", return_value={"default_order": ["subagent"]}), \
                 patch.object(cli, "ensure_run_belongs_to_task", return_value=run), \
                 patch.object(cli, "run_spec_binding", return_value={"spec_id": "none", "fingerprint": "none"}):
                first = cli.build_dispatch_plan(root, "T1", run_id="R1", host_snapshot=host, persist=True)
                with patch.object(cli, "select_subagent_candidates", side_effect=AssertionError("must reuse selection")):
                    second = cli.build_dispatch_plan(root, "T1", run_id="R1", host_snapshot=host, persist=True)
                self.assertEqual(first["dispatch_reuse"], "recomputed")
                self.assertEqual(second["dispatch_reuse"], "reused")
                self.assertEqual(first["steps"][0]["tools"][0]["runtime_arguments"], second["steps"][0]["tools"][0]["runtime_arguments"])
                self.assertIn("read-only and non-recursive", second["steps"][0]["tools"][0]["runtime_arguments"]["message"])
                self.assertFalse(second["authorization_is_execution_permit"])
                self.assertNotIn("approval_required", json.loads((run / "dispatch-plan.json").read_text()))
                host["tools"][0]["schema_version"] = "2"
                self.assertEqual(cli.build_dispatch_plan(root, "T1", run_id="R1", host_snapshot=host, persist=True)["dispatch_reuse"], "recomputed")
                (root / ".agent-os" / "write-policy.yaml").write_text("changed: true\n")
                self.assertEqual(cli.build_dispatch_plan(root, "T1", run_id="R1", host_snapshot=host, persist=True)["dispatch_reuse"], "recomputed")
                task["scope"] = "changed"
                self.assertEqual(cli.build_dispatch_plan(root, "T1", run_id="R1", host_snapshot=host, persist=True)["dispatch_reuse"], "recomputed")
                with patch.object(cli, "run_spec_binding", return_value={"spec_id": "S1", "fingerprint": "changed"}):
                    self.assertEqual(cli.build_dispatch_plan(root, "T1", run_id="R1", host_snapshot=host, persist=True)["dispatch_reuse"], "recomputed")
                host["expires_at"] = "2000-01-01T00:00:00+00:00"
                expired = cli.build_dispatch_plan(root, "T1", run_id="R1", host_snapshot=host, persist=True)
                self.assertEqual(expired["dispatch_reuse"], "recomputed")
                self.assertEqual(expired["dispatch_summary"]["runtime_callable_agents"], 0)

    def test_read_only_dispatch_does_not_create_or_rewrite_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / ".agent-os").mkdir()
            with patch.object(cli, "find_task", return_value={"id": "T1", "type": "engineering_change"}), \
                 patch.object(cli, "build_task_route", return_value={"status": "routed"}), \
                 patch.object(cli, "load_tool_registry", return_value=[ENTRY]), \
                 patch.object(cli, "load_dispatch_policy", return_value={"default_order": ["subagent"]}):
                cli.build_dispatch_plan(root, "T1")
                self.assertEqual(list((root / ".agent-os").iterdir()), [])
                self.assertFalse((root / ".knowledgeos-local").exists())
                cli.build_dispatch_plan(root, "T1", persist=True)
                cache = next((root / ".knowledgeos-local" / "dispatch-preflight").glob("*.json"))
                before = (cache.read_bytes(), cache.stat().st_mtime_ns)
                self.assertEqual(cli.build_dispatch_plan(root, "T1")["dispatch_reuse"], "reused")
                self.assertEqual((cache.read_bytes(), cache.stat().st_mtime_ns), before)

    def test_execution_verification_is_scoped_attestation_not_crypto(self):
        host = snapshot()
        host["executions"] = [{"capability_id": "codex-worker", "host_id": "host", "session_id": "session",
            "invocation_id": "actual-1", "terminal_status": "completed", "output_evidence_id": "output-1"}]
        value = cli.tool_summary(ENTRY, host_snapshot=host)
        self.assertTrue(value["execution_verified"])
        self.assertFalse(value["execution_evidence"]["cryptographically_verified"])
        self.assertEqual(value["execution_evidence"]["attestation"], "host_attested")
        for change in ({"session_id": "old-session"}, {"output_evidence_id": ""}, {"terminal_status": "running"}):
            altered = copy.deepcopy(host); altered["executions"][0].update(change)
            self.assertEqual(cli.tool_summary(ENTRY, host_snapshot=altered)["execution_verified"], "unknown")

    def test_real_cli_accepts_explicit_parent_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"; root.mkdir()
            repo = Path(cli.__file__).resolve().parents[1]
            command = [sys.executable, str(repo / "knowledgeos" / "cli.py")]
            initialized = subprocess.run(command + ["init-project", "--root", str(repo), "--project-root", str(root), "--name", "RuntimeTest"], capture_output=True, text=True)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            path = Path(tmp) / "host.json"; path.write_text(json.dumps(snapshot()))
            result = subprocess.run(command + ["dispatch-task", "--project-root", str(root), "--task-id", "T001",
                "--host-snapshot", str(path), "--host-id", "host", "--host-session-id", "session",
                "--host-snapshot-sha256", hashlib.sha256(path.read_bytes()).hexdigest(),
                "--host-attestation-evidence", "parent-tool-list-1", "--json"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertGreater(value["dispatch_summary"]["runtime_callable_agents"], 0)
            options = ["--host-snapshot", str(path), "--host-id", "host", "--host-session-id", "session",
                       "--host-attestation-evidence", "parent-tool-list-1", "--json"]
            started = subprocess.run(command + ["run-task", "--project-root", str(root), "--task-id", "T001"] + options +
                ["--host-snapshot-sha256", hashlib.sha256(path.read_bytes()).hexdigest()], capture_output=True, text=True)
            self.assertEqual(started.returncode, 0, started.stderr)
            bound = json.loads(started.stdout)
            self.assertEqual(bound["dispatch"]["dispatch_reuse"], "reused")
            self.assertGreater(bound["dispatch"]["dispatch_summary"]["runtime_callable_agents"], 0)
            self.assertTrue((root / ".agent-os" / "runs" / bound["run_id"] / "dispatch-plan.json").exists())
            for changes in ({"expires_at": "2000-01-01T00:00:00+00:00"}, {"connected": False}, {"session_id": "different"}):
                payload = dict(snapshot()); payload.update(changes); path.write_text(json.dumps(payload))
                rejected = subprocess.run(command + ["runtime-adapters", "--project-root", str(root)] + options +
                    ["--host-snapshot-sha256", hashlib.sha256(path.read_bytes()).hexdigest()], capture_output=True, text=True)
                self.assertNotEqual(rejected.returncode, 0, rejected.stdout)
            payload = dict(snapshot())
            payload["executions"] = [{"capability_id": "codex-worker", "host_id": "host", "session_id": "session",
                "invocation_id": "actual-1", "terminal_status": "completed", "output_evidence_id": "output-1"}]
            path.write_text(json.dumps(payload))
            imported = subprocess.run(command + ["subagent-adapter", "--project-root", str(root), "--id", "codex-worker"] +
                options + ["--host-snapshot-sha256", hashlib.sha256(path.read_bytes()).hexdigest()], capture_output=True, text=True)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            evidence = json.loads(imported.stdout)
            self.assertTrue(evidence["execution_verified"])
            self.assertEqual(evidence["execution_evidence"]["attestation"], "parent_attested")

    def test_run_bound_command_record_is_reused_not_fake_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan(); plan["dispatch_reuse"] = "reused"
            plan["steps"] = []
            old = {"generated_by": "knowledgeos", "event_type": "dispatch-task", "task_id": "T1", "run_id": "R1",
                   "dispatch_fingerprint": plan["dispatch_fingerprint"], "status": "dispatch_ready",
                   "required_stages": [], "planned_tools": []}
            with patch.object(cli, "ensure_run_belongs_to_task", return_value=root), \
                 patch.object(cli, "load_command_events", return_value=[old]), \
                 patch.object(cli, "record_checkpoint_producer", return_value={}) as checkpoint, \
                 patch.object(cli, "append_command_event") as append:
                record = cli.record_dispatch_event(root, "T1", "R1", plan)
                self.assertEqual(record["record_reuse"], "reused")
                append.assert_not_called()
                checkpoint.assert_called_once()

    def test_registry_is_not_host_evidence(self):
        value = cli.tool_summary(ENTRY)
        self.assertFalse(value["runtime_callable"])
        self.assertTrue(value["registered"])
        self.assertTrue(value["adapter_resolvable"])
        self.assertEqual(value["host_available"], "unknown")
        self.assertEqual(value["execution_verified"], "unknown")

    def test_dispatch_never_infers_host_from_legacy_fields(self):
        self.assertFalse(cli.dispatch_tool_runtime_callable(ENTRY))

    def test_generic_schema_and_provenance(self):
        value = cli.tool_summary(ENTRY, host_snapshot=snapshot())
        self.assertTrue(value["host_available"])
        self.assertEqual(value["runtime_tool"], "spawn_agent")
        self.assertNotIn("agent_type", value["runtime_arguments"])
        self.assertIn("message", value["runtime_arguments"])
        self.assertEqual(value["host_provenance"]["session_id"], "session")
        self.assertEqual(value["execution_verified"], "unknown")

    def test_invalid_snapshots_fail_safe(self):
        for changes in ({"connected": False}, {"schema_version": "unknown"},
                        {"source": "task"}, {"session_id": ""},
                        {"expires_at": "2000-01-01T00:00:00+00:00"},
                        {"tools": [{"name": "spawn_agent"}]}):
            with self.subTest(changes=changes):
                host = snapshot(); host.update(changes)
                value = cli.tool_summary(ENTRY, host_snapshot=host)
                self.assertFalse(value["runtime_callable"])

    def plan(self, entries=None, policy=None, host=None, task=None):
        with patch.object(cli, "find_task", return_value=task or {"id": "T1", "type": "engineering_change"}), \
             patch.object(cli, "build_task_route", return_value={"status": "routed"}), \
             patch.object(cli, "load_tool_registry", return_value=entries or [ENTRY]), \
             patch.object(cli, "load_dispatch_policy", return_value=policy or {"default_order": ["subagent", "orchestrator"]}), \
             patch.object(cli, "load_host_capability_snapshot", return_value=host or {}):
            return cli.build_dispatch_plan(Path('/project'), 'T1')

    def test_no_unconditional_ask_or_fake_permission_for_missing_host(self):
        value = self.plan()
        self.assertFalse(value["approval_required"])
        self.assertFalse(value["agent_opinion_required"])
        self.assertEqual(value["authorization_status"], "capability_unavailable")

    def test_default_maestro_suppressed_custom_preserved(self):
        bare = {"id": "maestro", "kind": "orchestrator", "status": "enabled", "source_path": "external:maestro"}
        value = self.plan(entries=[bare])
        self.assertNotIn("orchestrator", value["dispatch_summary"]["required_stages"])
        legacy_template = {key: value for key, value in bare.items() if key != "source_path"}
        value = self.plan(entries=[legacy_template])
        self.assertNotIn("orchestrator", value["dispatch_summary"]["required_stages"])
        custom = dict(bare, source_path="custom:team")
        value = self.plan(entries=[custom])
        self.assertIn("orchestrator", value["dispatch_summary"]["required_stages"])

    def test_scoped_bridge_authorization_and_revocation(self):
        host = snapshot()
        host["authorizations"] = [{"source": "user_message", "evidence_id": "msg-1",
            "project_root": "/project", "task_id": "T1", "operation": "subagent_read_only",
            "targets": ["codex-worker"], "max_invocations": 3, "used_invocations": [],
            "expires_at": host["expires_at"], "revoked": False}]
        allowed = self.plan(host=host)
        self.assertFalse(allowed["approval_required"])
        self.assertEqual(allowed["authorization_source"], "msg-1")
        for change in ({"revoked": True}, {"task_id": "T2"}, {"targets": ["other"]},
                       {"used_invocations": ["a", "b", "c"]}, {"source": "agent"},
                       {"expires_at": "2000-01-01T00:00:00+00:00"}):
            changed = copy.deepcopy(host); changed["authorizations"][0].update(change)
            self.assertTrue(self.plan(host=changed)["approval_required"])
        gated = self.plan(host=host, policy={"default_order": ["subagent"], "human_gate_for": ["per_task_confirmation"]})
        self.assertTrue(gated["approval_required"])
        host["task_invocations"] = [{"project_root": "/project", "task_id": "T1", "invocation_id": i}
                                    for i in ("one", "two", "three")]
        self.assertTrue(self.plan(host=host)["approval_required"])

    def test_untrusted_task_cannot_self_authorize(self):
        value = self.plan(host=snapshot(), task={"id": "T1", "type": "engineering_change", "authorized": True, "approval_required": False})
        self.assertTrue(value["approval_required"])

    def test_schema_change_changes_fingerprint_and_unknown_requirements_block(self):
        host = snapshot()
        before = self.plan(host=host)
        host["tools"][0]["schema_version"] = "2"
        self.assertNotEqual(before["dispatch_fingerprint"], self.plan(host=host)["dispatch_fingerprint"])
        host["tools"][0]["input_schema"]["required"].append("unknown_option")
        self.assertFalse(cli.tool_summary(ENTRY, host_snapshot=host)["runtime_callable"])
        self.assertEqual(before["dispatch_reuse"], "recomputed")

    def test_adapter_does_not_invent_generic_parameters(self):
        with patch.object(cli, "load_tool_registry", return_value=[ENTRY]), \
             patch.object(cli, "load_host_capability_snapshot", return_value=snapshot()):
            adapter = cli.build_subagent_adapter(Path('/project'), 'codex-worker')
        self.assertEqual(adapter["runtime_tool"], "spawn_agent")
        self.assertEqual(set(adapter["runtime_arguments"]), {"message", "fork_context"})
        self.assertIs(adapter["runtime_arguments"]["fork_context"], False)
        self.assertEqual(adapter["role_binding"], "prompt_only")
        self.assertEqual(adapter["execution_verified"], "unknown")

    def test_native_web_is_not_mcp(self):
        self.assertIn("web", cli.CAPABILITY_EVENT_KINDS)

    def test_invocation_report_dedupes_not_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = [dict(kind="subagent", id="codex-worker", invocation_id=i, status=s)
                      for i, s in [("one", "running"), ("one", "completed"), ("two", "completed")]]
            with patch.object(cli, "ensure_run_belongs_to_task", return_value=root), \
                 patch.object(cli, "load_capability_events", return_value=events), \
                 patch.object(cli, "load_command_events", return_value=[]), \
                 patch.object(cli, "append_command_event"):
                result = cli.build_dispatch_report(root, "T1", "R1")
            self.assertEqual(result["agent_count"], 2)
            self.assertEqual(result["capability_count"], 2)
            self.assertEqual(result["counts_by_kind"]["subagent"], 2)
            self.assertEqual(result["raw_event_count"], 3)
            self.assertEqual(result["invocation_status_counts"], {"completed": 2})

    def test_recovery_requires_same_invocation_and_explicit_evidence(self):
        for invocation, resolved in (("one", 1), ("two", 0)):
            events = [dict(kind="subagent", id="codex-worker", invocation_id="one", status="timed_out",
                           capability_event_id="gap", purpose="review", timestamp="1"),
                      dict(kind="subagent", id="codex-worker", invocation_id=invocation, status="completed",
                           capability_event_id="done", recovers_event_id="gap", purpose="review", timestamp="2")]
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with patch.object(cli, "ensure_run_belongs_to_task", return_value=root), \
                     patch.object(cli, "load_capability_events", return_value=events), \
                     patch.object(cli, "load_command_events", return_value=[]), \
                     patch.object(cli, "append_command_event"):
                    result = cli.build_dispatch_report(root, "T1", "R1")
                self.assertEqual(result["resolved_runtime_gap_count"], resolved)


if __name__ == '__main__':
    unittest.main()
