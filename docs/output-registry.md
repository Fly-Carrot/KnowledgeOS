# Output custody registry

The `output-registry` command records explicit relocation or retirement of an
existing completed task's declared `outputs/` artifact. It does not delete files,
cancel tasks, replace task declarations, rewrite old runs, or disable checks.

Registration requires an executed run-bound human decision in a maintenance run,
`--approved`, a reason, and a nonempty exact checksum inventory. Approval is a
parent-attested record, not independent human authentication. The operator must
verify that the human authorization covers the actual operation and paths.

Custody evidence uses `kos-output-custody-v1`, action, task_id, output, target,
artifact_kind (`file` or `directory`), and a files array containing relative_path,
size_bytes and sha256. A single-file inventory uses relative_path `.`.

Relocation requires an absent original and a distinct existing destination. Both
actions verify every current file against the inventory before registration.
Symlinks, raw data, control-plane artifacts, traversal, wildcards, undeclared
outputs, missing approval, missing custody files and repeated retirement fail.

Evidence is copied to `.agent-os/output-registry/evidence/`; events are appended
under an exclusive lock to a hash-linked ledger. Doctor validates the entire
ledger and evidence snapshots, then checks relocated file inventories and hashes
again. Read restrictions apply before file hashing, including dry runs. An
explicit retirement changes the current custody requirement, not the historical
completion result. Retirement registration is **not proof of deletion**; cleanup
must separately verify deletions and preservation. Hashes detect accidental
corruption, not tampering by a party who can rewrite both ledger and evidence.

New task completion/eval rules stay unchanged. The overlay applies only to the
health check of completed historical output declarations. Keep a separate
per-file deletion receipt and retained-model hashes for any actual cleanup.
