"""Approval-gated custody registration for superseded completed outputs.

This is a lifecycle overlay, not a deletion tool or an authentication service.
Approval is a command-backed parent attestation, not independent human identity
verification. Original task declarations and historical run records stay intact.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_inventory(cli, root, destination, doc):
    cli.validation_path(root, destination.relative_to(root).as_posix())
    if not destination.exists():
        raise ValueError("custody target is missing")
    if destination.is_file() != (doc["artifact_kind"] == "file"):
        raise ValueError("artifact kind mismatch")
    paths = [destination] if destination.is_file() else list(destination.rglob("*"))
    # Verify every read before hashing any descendant.
    for path in paths:
        cli.validation_path(root, path.relative_to(root).as_posix())
    actual = {"." if destination.is_file() else p.relative_to(destination).as_posix(): p
              for p in paths if p.is_file()}
    if set(actual) != {r["relative_path"] for r in doc["files"]}:
        raise ValueError("inventory does not exactly cover custody target")
    for row in doc["files"]:
        path = actual[row["relative_path"]]
        if path.stat().st_size != row["size_bytes"] or file_digest(path) != row["sha256"]:
            raise ValueError("custody target differs from inventory")
    return actual


def local_path(root, value):
    p = Path(value)
    if not value or p.is_absolute() or ".." in p.parts or any(c in value for c in "*?[]"):
        raise ValueError("registry paths must be exact project-relative paths")
    if p.parts[0] != "outputs":
        raise ValueError("custody registration is limited to outputs/ artifacts")
    result = root / p
    for q in [result, *result.parents]:
        if q == root:
            break
        if q.is_symlink():
            raise ValueError("symlinks are not eligible for custody registration")
    result.resolve().relative_to(root.resolve())
    return result


def evidence_document(data, action, task_id, output, target):
    doc = json.loads(data)
    for key, expected in (("schema", "kos-output-custody-v1"), ("action", action),
                          ("task_id", task_id), ("output", output), ("target", target)):
        if doc.get(key) != expected:
            raise ValueError(f"custody evidence mismatch: {key}")
    files = doc.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("nonempty exact file inventory required")
    paths = []
    for row in files:
        rel = row.get("relative_path")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError("invalid relative file path")
        sha = row.get("sha256", "")
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("invalid inventory checksum")
        size = row.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("invalid inventory size")
        paths.append(rel)
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate inventory file")
    if doc.get("artifact_kind") not in {"file", "directory"}:
        raise ValueError("artifact_kind must be file or directory")
    if doc["artifact_kind"] == "file" and paths != ["."]:
        raise ValueError("file inventory must use relative_path '.'")
    if doc["artifact_kind"] == "directory" and "." in paths:
        raise ValueError("directory inventory cannot contain '.'")
    return doc


def approval(cli, maintenance_root, task_id, run_id, decision_id):
    run = cli.resolve_run_dir(maintenance_root, run_id)
    meta = cli.parse_scalar_values(run / "run.yaml", {"task_id", "run_id"})
    if meta.get("task_id") != task_id or meta.get("run_id") != run_id:
        raise ValueError("maintenance run binding mismatch")
    records = [json.loads(line) for line in (run / "decision-events.ndjson").read_text().splitlines() if line]
    hits = [r for r in records if r.get("decision_id") == decision_id]
    if len(hits) != 1 or any(hits[0].get(k) != v for k, v in (
        ("task_id", task_id), ("run_id", run_id), ("kind", "human_decision"), ("status", "executed"))):
        raise ValueError("executed run-bound human decision required")
    if not hits[0].get("evidence"):
        raise ValueError("approval requires user evidence")
    return hits[0]


def load_registry(cli, root):
    base = root / ".agent-os/output-registry"
    ledger = base / "events.ndjson"
    if not ledger.exists():
        return []
    if base.is_symlink() or ledger.is_symlink():
        raise ValueError("registry cannot be a symlink")
    previous = ""
    records = []
    states = {}
    declared = cli.parse_task_list_field(root / ".agent-os/tasks.yaml", "outputs")
    for line in ledger.read_text().splitlines():
        if not line:
            raise ValueError("blank registry event")
        event = json.loads(line)
        expected_hash = event.pop("event_sha256")
        actual_hash = digest_bytes(json.dumps(event, sort_keys=True, separators=(",", ":")).encode())
        event["event_sha256"] = expected_hash
        if actual_hash != expected_hash or event.get("previous_sha256") != previous:
            raise ValueError("output registry integrity mismatch")
        task_id, output = event["task_id"], event["output"]
        if output not in declared.get(task_id, []):
            raise ValueError("registry references an undeclared output")
        local_path(root, output)
        local_path(root, event["target"])
        if event["action"] not in {"relocate", "retire"}:
            raise ValueError("unknown custody action")
        prior = states.get((task_id, output))
        if prior and (prior["action"] != "relocate" or event["action"] != "retire" or event["target"] != prior["target"]):
            raise ValueError("invalid custody transition")
        if event["action"] == "retire" and not prior and event["target"] != output:
            raise ValueError("retirement target is not the current output")
        if (base / "evidence").is_symlink():
            raise ValueError("evidence directory cannot be a symlink")
        evidence_path = base / "evidence" / (event["evidence_sha256"] + ".json")
        if evidence_path.is_symlink() or file_digest(evidence_path) != event["evidence_sha256"]:
            raise ValueError("custody evidence checksum mismatch")
        evidence_document(evidence_path.read_bytes(), event["action"], task_id, output, event["target"])
        if not event.get("reason") or not event.get("approval_decision_id") or not event.get("approval_snapshot"):
            raise ValueError("custody event lacks reason or approval")
        bound = event["approval_snapshot"]
        if bound.get("decision_id") != event["approval_decision_id"] or bound.get("kind") != "human_decision" or bound.get("status") != "executed":
            raise ValueError("invalid approval snapshot")
        records.append(event)
        states[(task_id, output)] = event
        previous = expected_hash
    return records


def completed_output_status(cli, root, task_id, output, records):
    hits = [r for r in records if r["task_id"] == task_id and r["output"] == output]
    if not hits:
        return cli.output_status(root, output)
    event = hits[-1]
    if event["action"] == "retire":
        return True, f"{output} explicitly retired; custody={event['event_sha256']} (not a deletion receipt)"
    try:
        evidence = root / '.agent-os/output-registry/evidence' / (event['evidence_sha256'] + '.json')
        cli.validation_path(root, evidence.relative_to(root).as_posix())
        doc = evidence_document(evidence.read_bytes(), 'relocate', task_id, output, event['target'])
        verify_inventory(cli, root, local_path(root, event['target']), doc)
        return True, f"{output} relocated: verified inventory at {event['target']}"
    except (ValueError, OSError) as exc:
        return False, f"{output} relocated: {exc}"


def register(cli, root, *, task_id, output, action, target, evidence,
             reason, approved, maintenance_root, maintenance_task_id,
             maintenance_run_id, approval_decision_id, dry_run=False):
    cli.ensure_safe_project_root(root)
    if not approved or not reason.strip():
        raise ValueError("explicit approval and reason required")
    task = cli.find_task(root, task_id)
    if task.get("status") != "completed" or output not in cli.task_declared_outputs(root, task_id):
        raise ValueError("only declared completed-task outputs can be registered")
    if action not in {"relocate", "retire"}:
        raise ValueError("unknown custody action")
    source = local_path(root, output)
    destination = local_path(root, target)
    records = load_registry(cli, root)
    prior = [r for r in records if r["task_id"] == task_id and r["output"] == output]
    if prior and (prior[-1]["action"] != "relocate" or action != "retire" or target != prior[-1]["target"]):
        raise ValueError("invalid or repeated custody transition")
    if action == "retire" and not prior and target != output:
        raise ValueError("retirement target is not the current output")
    for path in (source, destination):
        if cli.classify_write(root, str(path))["decision"] != "allow":
            raise ValueError("artifact write policy does not permit maintenance")
    bound = approval(cli, maintenance_root, maintenance_task_id, maintenance_run_id, approval_decision_id)
    cli.validation_path(root, evidence.relative_to(root).as_posix())
    raw = evidence.read_bytes()
    doc = evidence_document(raw, action, task_id, output, target)
    if not destination.exists():
        raise ValueError("custody target must exist before registration")
    if action == "relocate" and (source.exists() or source == destination):
        raise ValueError("relocation requires absent original and distinct existing target")
    actual = verify_inventory(cli, root, destination, doc)
    base = root / ".agent-os/output-registry"
    for p in (base, base / "events.ndjson", base / "registry.lock", base / "evidence"):
        if p.is_symlink() or cli.classify_write(root, str(p))["decision"] != "allow":
            raise ValueError("registry writes are not permitted")
    event = dict(action=action, task_id=task_id, output=output, target=target,
                 reason=reason, evidence_sha256=digest_bytes(raw),
                 approval_decision_id=approval_decision_id, approval_snapshot=bound,
                 maintenance_project=str(maintenance_root), maintenance_task_id=maintenance_task_id,
                 maintenance_run_id=maintenance_run_id, timestamp=datetime.now(timezone.utc).isoformat(),
                 previous_sha256=records[-1]["event_sha256"] if records else "")
    if dry_run:
        return {"marker": "OUTPUT_REGISTRY_DRY_RUN", "event": event, "files": len(actual), "dry_run": True}
    base.mkdir(parents=True, exist_ok=True)
    lock = base / "registry.lock"
    with lock.open("x"):
        try:
            current = load_registry(cli, root)
            if current != records:
                raise ValueError("registry changed during verification; retry")
            evidence_dir = base / "evidence"
            evidence_dir.mkdir(exist_ok=True)
            snapshot = evidence_dir / (event["evidence_sha256"] + ".json")
            if snapshot.exists():
                if snapshot.read_bytes() != raw:
                    raise ValueError("existing evidence snapshot differs")
            else:
                with snapshot.open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            event["event_sha256"] = digest_bytes(json.dumps(event, sort_keys=True, separators=(",", ":")).encode())
            with (base / "events.ndjson").open("a") as stream:
                stream.write(json.dumps(event, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            lock.unlink()
    return {"marker": "OUTPUT_REGISTRY_OK", "event": event, "files": len(actual), "dry_run": False}


def add_parser(sub, cli):
    p = sub.add_parser("output-registry", help="register approved relocation or retirement without rewriting completed history")
    p.add_argument("--project-root", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--action", choices=("relocate", "retire"), required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--approved", action="store_true")
    p.add_argument("--maintenance-root", required=True)
    p.add_argument("--maintenance-task-id", required=True)
    p.add_argument("--maintenance-run-id", required=True)
    p.add_argument("--approval-decision-id", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    def execute(args):
        result = register(cli, Path(args.project_root).resolve(), task_id=args.task_id,
                          output=args.output, action=args.action, target=args.target,
                          evidence=Path(args.evidence), reason=args.reason, approved=args.approved,
                          maintenance_root=Path(args.maintenance_root).resolve(),
                          maintenance_task_id=args.maintenance_task_id, maintenance_run_id=args.maintenance_run_id,
                          approval_decision_id=args.approval_decision_id, dry_run=args.dry_run)
        print(json.dumps(result, indent=2) if args.json else result["marker"])
        return 0
    p.set_defaults(func=execute)
