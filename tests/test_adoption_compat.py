"""Migration must change future defaults, not evidence bound by old runs."""
import hashlib
import json
import unittest
from unittest.mock import patch

from knowledgeos import cli, guidance
from tests import test_ordinary_flow as ordinary_support


class AdoptionCompatTests(unittest.TestCase):
    setUp = ordinary_support.OrdinaryFlowTests.setUp
    start = ordinary_support.OrdinaryFlowTests.start
    adopt = ordinary_support.OrdinaryFlowTests.adopt

    def historical_spec_run(self):
        spec = cli.create_spec(self.project, title='Original method', intent='Preserve originals')
        tasks = self.project / '.agent-os/tasks.yaml'
        tasks.write_text(tasks.read_text().replace(f'  - id: {self.task}\n',
            f'  - id: {self.task}\n    spec_id: {spec["spec_id"]}\n'))
        run = self.start()['run_id']
        directory = self.project / '.agent-os/runs' / run
        binding = (directory / 'spec-binding.json').read_bytes()
        (directory / 'spec-binding.json').unlink()  # Historical snapshot-only fixture.
        meta = directory / 'run.yaml'
        meta.write_text(meta.read_text().replace('status: started', 'status: completed'))
        source = self.project / '.agent-os/specs' / spec['spec_id'] / 'spec.md'
        source.write_text(source.read_text() + '\nChanged future method.\n')
        return run, directory, binding

    def test_completed_legacy_dispatch_uses_verified_archived_spec(self):
        run, directory, _ = self.historical_spec_run()
        self.assertEqual(cli.build_dispatch_plan(self.project, self.task, run_id=run)['status'], 'dispatch_ready')
        snapshot = directory / 'spec-snapshot.md'
        snapshot.write_text(snapshot.read_text() + '\nTampered archive.\n')
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            cli.build_dispatch_plan(self.project, self.task, run_id=run)

    def test_active_and_modern_bindings_do_not_get_historical_exception(self):
        run, directory, binding = self.historical_spec_run()
        (directory / 'spec-binding.json').write_bytes(binding)
        with self.assertRaisesRegex(ValueError, 'spec drift'):
            cli.build_dispatch_plan(self.project, self.task, run_id=run)
        (directory / 'spec-binding.json').unlink()
        meta = directory / 'run.yaml'
        meta.write_text(meta.read_text().replace('status: completed', 'status: started'))
        with self.assertRaisesRegex(ValueError, 'spec drift'):
            cli.build_dispatch_plan(self.project, self.task, run_id=run)

    def test_dispatch_failure_is_a_diagnostic_not_uncaught_exception(self):
        run = self.start()['run_id']
        with patch.object(cli, 'build_dispatch_plan', side_effect=ValueError('spec drift: fixture')):
            errors = cli.verify_dispatch_capability_contract(self.project, self.task, run, None)
        self.assertIn('dispatch_validation_error', [e['label'] for e in errors])

    def receipt(self):
        data = {
            "schema": "knowledgeos.future-defaults.v1",
            "project_root": str(self.project.resolve()),
            "execution_contract": "ordinary-v1",
            "new_runs_only": True,
            "reason": "User authorized future ordinary defaults; retain active contracts.",
            "baseline": {
                name: hashlib.sha256((self.project / ".agent-os" / name).read_bytes()).hexdigest()
                for name in ("project.yaml", "fabric-link.yaml")
            },
        }
        path = self.project / ".knowledgeos-local/future-defaults.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data))
        return path, data

    def test_local_adoption_leaves_old_fingerprint_and_lifecycle_unchanged(self):
        run = self.start()["run_id"]
        before = cli.evaluation_fingerprint(self.project, self.task, run)
        lifecycle = cli.verify_lifecycle(self.project, self.task, run)
        self.receipt()
        self.assertEqual(guidance.execution_contract(self.project), "ordinary-v1")
        self.assertEqual(before, cli.evaluation_fingerprint(self.project, self.task, run))
        self.assertFalse(cli.ordinary_run(self.project, self.task, run))
        self.assertEqual(lifecycle, cli.verify_lifecycle(self.project, self.task, run))

    def test_local_adoption_enables_new_run_without_config_rewrite(self):
        before = {name: (self.project / ".agent-os" / name).read_bytes()
                  for name in ("project.yaml", "fabric-link.yaml")}
        self.receipt()
        result = self.start()
        self.assertEqual(result["execution_contract"], "ordinary-v1")
        for name, data in before.items():
            self.assertEqual(data, (self.project / ".agent-os" / name).read_bytes())
        out = self.project / "docs/result.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text("verified")
        cli.write_task_eval(self.project, self.task, result["run_id"], validations=[
            {"kind": "file_contains", "path": "docs/result.md", "expect": "verified", "acceptance": [1]}])
        self.assertEqual(cli.complete_task(self.project, self.task, result["run_id"], "Checked")["status"],
                         "completed")

    def test_wrong_root_and_changed_baseline_fail_closed(self):
        path, data = self.receipt()
        data["project_root"] = "/not-this-project"
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            guidance.execution_contract(self.project)
        self.receipt()
        config = self.project / ".agent-os/fabric-link.yaml"
        config.write_text(config.read_text() + "\n# A policy change requires review\n")
        with self.assertRaises(ValueError):
            guidance.execution_contract(self.project)

    def test_symlink_and_duplicate_fields_rejected(self):
        path, data = self.receipt()
        target = path.with_suffix(".saved")
        path.rename(target)
        path.symlink_to(target)
        with self.assertRaises(ValueError):
            guidance.execution_contract(self.project)
        path.unlink()
        path.write_text(json.dumps(data)[:-1] + ', "new_runs_only": false}')
        with self.assertRaises(ValueError):
            guidance.execution_contract(self.project)

    def test_new_eval_binds_adoption_receipt(self):
        path, data = self.receipt()
        run = self.start()["run_id"]
        before = cli.evaluation_fingerprint(self.project, self.task, run)
        data["reason"] += " Updated authorization note."
        path.write_text(json.dumps(data))
        self.assertNotEqual(before, cli.evaluation_fingerprint(self.project, self.task, run))

    def test_run_context_and_capability_verifier_use_bound_dispatch(self):
        run = self.start()["run_id"]
        with patch.object(cli, "build_dispatch_plan", wraps=cli.build_dispatch_plan) as dispatch:
            cli.write_context_pack(self.project, self.task, run)
            self.assertEqual(dispatch.call_args.kwargs.get("run_id"), run)
        with patch.object(cli, "build_dispatch_plan", wraps=cli.build_dispatch_plan) as dispatch:
            cli.verify_dispatch_capability_contract(self.project, self.task, run, None)
            self.assertEqual(dispatch.call_args.kwargs.get("run_id"), run)

    def test_receipt_does_not_waive_strict_research_policy(self):
        self.receipt()
        path = self.project / ".agent-os/decision-policy.yaml"
        path.write_text(path.read_text().replace("strictness: warn", "strictness: enforce"))
        self.assertFalse(cli.ordinary_eligible(self.project, self.task))

    def test_receipt_writes_require_explicit_approval(self):
        self.assertEqual(cli.classify_write(self.project, ".knowledgeos-local/future-defaults.json")["decision"],
                         "human_gate_required")

    def test_preexisting_ordinary_run_does_not_rebind_to_later_receipt(self):
        self.adopt()
        run = self.start()["run_id"]
        before = cli.evaluation_fingerprint(self.project, self.task, run)
        self.receipt()
        self.assertEqual(before, cli.evaluation_fingerprint(self.project, self.task, run))
