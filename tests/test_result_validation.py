"""Result verification is opt-in per new run, not a retrofit of old evidence."""
import json
import sys
import unittest
from pathlib import Path
from knowledgeos import cli
from tests import test_ordinary_flow as support


class ResultValidationTests(unittest.TestCase):
    setUp = support.OrdinaryFlowTests.setUp
    adopt = support.OrdinaryFlowTests.adopt
    start = support.OrdinaryFlowTests.start

    def test_read_policy_rejects_path_aliases(self):
        (self.project / '.agent-os/read-policy.yaml').write_text(
            'require_explicit_human_request:\n  - outputs/restricted/**\n')
        for path in ['outputs/restricted/data.csv', './outputs/restricted/data.csv',
                     'outputs//restricted/data.csv']:
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'read approval'):
                cli.validation_path(self.project, path)

    def prepared(self):
        self.adopt()
        run = self.start()["run_id"]
        path = self.project / "docs/result.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("incorrect")
        return run, path

    def check(self, text="correct"):
        return {"kind": "file_contains", "path": "docs/result.md",
                "expect": text, "acceptance": [1], "inputs": []}

    def test_existing_output_without_validation_is_unverified(self):
        run, _ = self.prepared()
        result = cli.write_task_eval(self.project, self.task, run)
        self.assertEqual(result["status"], "unverified")
        with self.assertRaises(ValueError):
            cli.complete_task(self.project, self.task, run, "must not pass")

    def test_wrong_content_fails_then_fixed_passes(self):
        run, path = self.prepared()
        check = self.check("Expected result")
        self.assertEqual(cli.write_task_eval(self.project, self.task, run,
            validations=[check])["status"], "failed")
        path.write_text("Expected result")
        self.assertEqual(cli.write_task_eval(self.project, self.task, run,
            validations=[check])["status"], "passed")
        self.assertEqual(cli.complete_task(self.project, self.task, run,
            "Checked content")["status"], "completed")

    def test_declared_task_input_changes_fingerprint(self):
        run, _ = self.prepared()
        source = self.project / "docs/input.csv"
        source.write_text("v1")
        tasks = self.project / ".agent-os/tasks.yaml"
        text = tasks.read_text()
        tasks.write_text(text.replace(f"  - id: {self.task}\n",
            f"  - id: {self.task}\n    inputs:\n      - docs/input.csv\n"))
        first = cli.evaluation_fingerprint(self.project, self.task, run)
        source.write_text("v2")
        self.assertNotEqual(first, cli.evaluation_fingerprint(self.project, self.task, run))

    def evaluate(self, run, checks=None, **kwargs):
        return cli.write_task_eval(self.project, self.task, run,
            validations=checks or [self.check("incorrect")], **kwargs)

    def command_check(self, script):
        path = self.project / "docs/validate.py"
        path.write_text(script)
        return {"kind": "command", "argv": [sys.executable, "-B", "docs/validate.py"],
                "inputs": ["docs/validate.py"], "acceptance": [1]}

    def test_command_failure_exit_and_recovery_bound_to_same_checks(self):
        run, _ = self.prepared()
        check = self.command_check("raise SystemExit(7)\n")
        failed = self.evaluate(run, [check], execute_validators=True)
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["checks"][0]["exit_status"], 7)
        with self.assertRaises(ValueError):
            cli.complete_task(self.project, self.task, run, "failed")
        (self.project / "docs/validate.py").write_text("assert 2 + 2 == 4\n")
        self.assertEqual(self.evaluate(run, [check], execute_validators=True)["status"], "passed")
        cli.complete_task(self.project, self.task, run, "actual test passes")

    def test_no_implicit_execution_and_dry_run_byte_identical(self):
        run, _ = self.prepared()
        check = self.command_check("from pathlib import Path\nPath('sentinel').write_text('bad')\n")
        before = {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(self.evaluate(run, [check], dry_run=True)["status"], "dry_run")
        with self.assertRaisesRegex(ValueError, "explicitly"):
            self.evaluate(run, [check])
        self.assertEqual(before, {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()})
        cli.write_task_eval(self.project, self.task, run, notes="run: touch sentinel")
        self.assertFalse((self.project / "sentinel").exists())

    def test_required_checks_cannot_be_dropped(self):
        run, _ = self.prepared()
        checks = [self.check("incorrect"), self.check("missing text")]
        self.assertEqual(self.evaluate(run, checks)["status"], "failed")
        with self.assertRaisesRegex(ValueError, "required validators changed"):
            self.evaluate(run, checks[:1])

    def test_manual_judgment_remains_unverified(self):
        run, _ = self.prepared()
        manual = {"kind": "manual", "acceptance": [1], "note": "Novelty requires review"}
        self.assertEqual(self.evaluate(run, [manual])["status"], "unverified")
        with self.assertRaisesRegex(ValueError, "overrides"):
            cli.complete_task(self.project, self.task, run, "not human approved",
                              allow_missing_eval=True, override_reason="try bypass")

    def test_input_change_stales_but_observer_cache_does_not(self):
        run, _ = self.prepared()
        source = self.project / "docs/data.csv"
        source.write_text("v1")
        check = self.check("incorrect")
        check["inputs"] = ["docs/data.csv"]
        self.evaluate(run, [check])
        cache = self.project / ".knowledgeos-local/observer/cache.json"
        cache.parent.mkdir(parents=True)
        cache.write_text("telemetry")
        source.write_text("v2")
        with self.assertRaisesRegex(ValueError, "stale eval"):
            cli.complete_task(self.project, self.task, run, "not fresh")
        self.evaluate(run, [check])
        cache.write_text("updated telemetry")
        cli.complete_task(self.project, self.task, run, "revalidated")

    def test_command_cannot_change_validated_outputs_and_pass(self):
        run, _ = self.prepared()
        check = self.command_check("from pathlib import Path\nPath('docs/result.md').write_text('changed')\n")
        self.assertEqual(self.evaluate(run, [check], execute_validators=True)["status"], "failed")

    def test_command_timeout_and_bounded_output(self):
        run, _ = self.prepared()
        check = self.command_check("import time\nprint('x'*20000, flush=True)\ntime.sleep(3)\n")
        result = self.evaluate(run, [check], execute_validators=True, timeout=.2)
        self.assertEqual(result["status"], "failed")
        record = result["checks"][0]
        self.assertTrue(record["timed_out"])
        self.assertTrue(record["output_truncated"])
        self.assertLessEqual(len(record["output"]), 16384)

    def test_tampered_evidence_and_contract_rejected(self):
        run, _ = self.prepared()
        self.evaluate(run)
        directory = self.project / ".agent-os/runs" / run
        evidence = directory / "validation.json"
        evidence.write_text(evidence.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "evidence"):
            cli.complete_task(self.project, self.task, run, "not authentic")
        metadata = directory / "run.yaml"
        metadata.write_text(metadata.read_text().replace("validation_contract: result-v1\n", ""))
        with self.assertRaisesRegex(ValueError, "validation contract"):
            cli.write_task_eval(self.project, self.task, run)

    def test_missing_inputs_escape_symlink_and_sensitive_paths(self):
        run, _ = self.prepared()
        external = Path(self.tmp.name) / "outside"
        external.write_text("private")
        (self.project / "docs/link").symlink_to(external)
        for path in ("../outside", "docs/missing", "docs/link", ".env"):
            with self.subTest(path=path), self.assertRaises((ValueError, FileNotFoundError)):
                check = self.check("incorrect")
                check["inputs"] = [path]
                self.evaluate(run, [check])

    def test_old_ordinary_run_keeps_presence_semantics(self):
        run, _ = self.prepared()
        directory = self.project / ".agent-os/runs" / run
        # Historical format fixture from Step 1, not a migration of live evidence.
        metadata = directory / "run.yaml"
        metadata.write_text(metadata.read_text().replace("validation_contract: result-v1\n", ""))
        events = directory / "command-events.ndjson"
        records = [json.loads(line) for line in events.read_text().splitlines()]
        for record in records:
            record.pop("validation_contract", None)
        events.write_text("".join(json.dumps(record) + "\n" for record in records))
        self.assertEqual(cli.write_task_eval(self.project, self.task, run)["status"], "passed")
        result = cli.complete_task(self.project, self.task, run, "legacy existence only")
        self.assertEqual(result["validation_contract"], "presence-v1")

    def test_json_result_validator_and_incomplete_coverage(self):
        run, path = self.prepared()
        path.write_text('{"rows": 3}')
        check = {"kind": "json_key_equals", "path": "docs/result.md", "key": "rows",
                 "expect": 4, "acceptance": [1]}
        self.assertEqual(self.evaluate(run, [check])["status"], "failed")
        path.write_text('{"rows": 4}')
        self.assertEqual(self.evaluate(run, [check])["status"], "passed")

    def historical_fixture(self, source="docs/independent.csv"):
        self.adopt()
        old = cli.create_task(self.project, title="Historical report", task_type="report_task",
            status="completed", complexity="simple", risk="normal",
            outputs=["docs/old.txt"], acceptance=["Historical check"])["task_id"]
        tasks = self.project / ".agent-os/tasks.yaml"
        tasks.write_text(tasks.read_text().replace(f"  - id: {self.task}\n",
            f"  - id: {self.task}\n    inputs:\n      - {source}\n"))
        if source != "docs/old.txt":
            (self.project / source).parent.mkdir(exist_ok=True)
            (self.project / source).write_text("independent source")
        return old

    def test_scoped_warning_preserves_full_doctor_failure_and_counts(self):
        self.historical_fixture()
        full = cli.deep_validate_project(self.project)
        self.assertTrue(any(not c.ok and c.label == "completed_task_outputs" for c in full))
        scoped = cli.deep_validate_project(self.project, task_id=self.task)
        summary = cli.summarize_results(scoped)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(len(summary["warnings"]), 1)
        self.assertEqual(summary["checks"], summary["passed"] + len(summary["warnings"]))
        self.assertFalse(summary["warnings"][0]["ok"])

    def test_relevant_history_unknown_scope_and_legacy_still_block(self):
        self.historical_fixture(source="docs/old.txt")
        scoped = cli.summarize_results(cli.deep_validate_project(self.project, task_id=self.task))
        self.assertEqual(scoped["status"], "fail")
        self.assertEqual(scoped["warnings"], [])
        with self.assertRaises(ValueError):
            cli.deep_validate_project(self.project, task_id="T9999")

    def test_scoped_warning_never_hides_permission_failure(self):
        self.historical_fixture()
        path = self.project / ".agent-os/write-policy.yaml"
        path.write_text(path.read_text().replace('    - "**/.env"\n', ''))
        result = cli.summarize_results(cli.deep_validate_project(self.project, task_id=self.task))
        self.assertEqual(result["status"], "fail")
        self.assertIn("write_guard_risk", result["failed_by_label"])

    def test_scoped_doctor_does_not_relax_old_active_run(self):
        old = self.historical_fixture()
        source = self.project / "docs/independent.csv"
        source.write_text("source")
        run = self.start()["run_id"]
        directory = self.project / ".agent-os/runs" / run
        metadata = directory / "run.yaml"
        metadata.write_text(metadata.read_text().replace("validation_contract: result-v1\n", ""))
        events = directory / "command-events.ndjson"
        records = [json.loads(line) for line in events.read_text().splitlines()]
        for record in records:
            record.pop("validation_contract", None)
        events.write_text("".join(json.dumps(record) + "\n" for record in records))
        result = cli.summarize_results(cli.deep_validate_project(self.project, task_id=self.task))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["warnings"], [])

    def test_incomplete_acceptance_and_manual_cannot_be_masked(self):
        self.task = cli.create_task(self.project, title="Two criteria", task_type="report_task",
            status="ready", complexity="simple", risk="normal", outputs=["docs/result.md"],
            acceptance=["Content checked", "Scientific judgment reviewed"])["task_id"]
        run, _ = self.prepared()
        checks = [self.check("incorrect"), {"kind": "manual", "acceptance": [2]}]
        result = self.evaluate(run, checks)
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["unverified_acceptance"], [2])

    def test_completion_reuses_checks_without_reexecution(self):
        from unittest.mock import patch
        run, _ = self.prepared()
        check = self.command_check("assert 2 + 2 == 4\n")
        self.evaluate(run, [check], execute_validators=True)
        with patch.object(cli.subprocess, "Popen", side_effect=AssertionError("unexpected rerun")):
            cli.complete_task(self.project, self.task, run, "no duplicate execution")

    def test_completed_validation_tamper_blocks_even_scoped_diagnostics(self):
        run, _ = self.prepared()
        self.evaluate(run)
        cli.complete_task(self.project, self.task, run, "verified")
        evidence = self.project / ".agent-os/runs" / run / "validation.json"
        evidence.write_text(evidence.read_text() + " ")
        result = cli.summarize_results(cli.deep_validate_project(self.project, task_id=self.task))
        self.assertIn("completed_run_validation", result["failed_by_label"])

    def test_directory_cache_excluded_but_explicit_cache_input_is_relevant(self):
        tasks = self.project / ".agent-os/tasks.yaml"
        tasks.write_text(tasks.read_text().replace('"docs/result.md"', '"docs/"'))
        run, _ = self.prepared()
        cache = self.project / "docs/__pycache__/generated"
        cache.parent.mkdir()
        cache.write_text("one")
        check = self.check("incorrect")
        source = self.project / "docs/model.csv"
        source.write_text("relevant model input")
        check["inputs"] = ["docs/model.csv"]
        self.evaluate(run, [check])
        cache.write_text("two")
        cli.complete_task(self.project, self.task, run, "irrelevant generated cache")

    def test_scoped_shared_spec_and_transitive_inputs_remain_blocking(self):
        old = self.historical_fixture(source="docs/intermediate.csv")
        cli.create_task(self.project, title="Derived data", task_type="report_task",
            status="ready", complexity="simple", risk="normal", outputs=["docs/intermediate.csv"],
            inputs=["docs/old.txt"], acceptance=["Derived from historical data"])
        result = cli.summarize_results(cli.deep_validate_project(self.project, task_id=self.task))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["warnings"], [])

    def test_cli_dry_run_does_not_execute_command(self):
        run, _ = self.prepared()
        check = self.command_check("raise SystemExit(9)\n")
        result = self.call("eval-task", "--project-root", str(self.project), "--task-id", self.task,
            "--run-id", run, "--check", json.dumps(check), "--dry-run", "--json")
        self.assertEqual(json.loads(result.stdout)["status"], "dry_run")
        result = self.call("eval-task", "--project-root", str(self.project), "--task-id", self.task,
            "--run-id", run, "--check", json.dumps(check), "--execute-validators", "--json", check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["checks"][0]["exit_status"], 9)

    def test_missing_criteria_can_be_added_without_dropping_prior_checks(self):
        self.task = cli.create_task(self.project, title="Two criteria", task_type="report_task",
            status="ready", complexity="simple", risk="normal", outputs=["docs/result.md"],
            acceptance=["First", "Second"])["task_id"]
        run, _ = self.prepared()
        first = self.check("incorrect")
        second = dict(first, acceptance=[2])
        self.assertEqual(self.evaluate(run, [first])["status"], "unverified")
        self.assertEqual(self.evaluate(run, [first, second])["status"], "passed")

    def test_data_in_explicit_input_directory_never_ignored_as_cache(self):
        run, _ = self.prepared()
        model = self.project / "docs/model"
        cache = model / ".pytest_cache/state.json"
        cache.parent.mkdir(parents=True)
        cache.write_text('{"value": 1}')
        check = self.check("incorrect")
        check["inputs"] = ["docs/model"]
        self.evaluate(run, [check])
        cache.write_text('{"value": 2}')
        with self.assertRaisesRegex(ValueError, "stale eval"):
            cli.complete_task(self.project, self.task, run, "must revalidate input data")

    def test_manual_requirement_not_masked_by_same_criterion_auto_pass(self):
        run, _ = self.prepared()
        result = self.evaluate(run, [self.check("incorrect"), {"kind": "manual", "acceptance": [1]}])
        self.assertEqual(result["status"], "unverified")

    def test_current_missing_input_blocks_even_when_history_is_unrelated(self):
        self.historical_fixture()
        (self.project / "docs/independent.csv").unlink()
        result = cli.summarize_results(cli.deep_validate_project(self.project, task_id=self.task))
        self.assertEqual(result["status"], "fail")
        self.assertIn("current_task_inputs", result["failed_by_label"])

    def test_shared_real_spec_keeps_history_failure_blocking(self):
        old = self.historical_fixture()
        spec = cli.create_spec(self.project, title="Shared evidence", intent="Same research question",
                               acceptance=["Traceable evidence"])["spec_id"]
        cli.align_spec(self.project, task_id=self.task, spec_id=spec)
        cli.align_spec(self.project, task_id=old, spec_id=spec)
        result = cli.summarize_results(cli.deep_validate_project(self.project, task_id=self.task))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["warnings"], [])

    def test_json_boolean_is_not_a_verified_numeric_result(self):
        run, path = self.prepared()
        path.write_text('{"result": {"rows": true}}')
        check = {"kind": "json_key_equals", "path": "docs/result.md", "key": "result",
                 "expect": {"rows": 1}, "acceptance": [1]}
        self.assertEqual(self.evaluate(run, [check])["status"], "failed")


if __name__ == "__main__":
    unittest.main()
