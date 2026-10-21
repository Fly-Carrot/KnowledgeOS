# Optional Codex guidance reminder

A small, read-only hook helps existing chats notice updated KnowledgeOS rules.
It is optional: the normal workflow works without it. It does not install or
initialize projects, run doctor, create tasks, change permissions, or replace
active-run contracts. It is independent of codex-trajectory.

## Install

Requirements: macOS or Linux, Python 3.10+, Codex with hooks support, and a stable
KnowledgeOS checkout. Keep the script inside that checkout. The global entry
(`AGENTS.md` in your Codex home) should already point to the intended KnowledgeOS
installation; the hook does not rewrite it.

1. Update or clone this repository. Keep its path stable.
2. Back up your Codex `hooks.json` (normally `~/.codex/hooks.json`; respect
   `CODEX_HOME` if you use a custom home).
3. Add the handler below to `hooks.UserPromptSubmit`. **Merge it with existing
   handlers; do not replace the file or duplicate an already installed reminder.**
   Replace both example paths with absolute paths on your machine. Double quotes
   inside the command preserve paths containing spaces.

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"/absolute/path/to/python3\" -B \"/absolute/path/to/KnowledgeOS/bin/kos-guidance-refresh.py\"",
            "timeout": 2,
            "statusMessage": "KnowledgeOS"
          }
        ]
      }
    ]
  }
}
```

## Trust and check

Codex requires review and trust for new or changed non-managed hook definitions.
Review this handler in the host's hook controls, or use `/hooks` in Codex CLI.
Do not bypass hook trust or edit trust records. Configuration being present does
not prove the host executed it. See the [official hook documentation](https://learn.chatgpt.com/docs/hooks).

After the host loads and trusts the handler, send the next message in a managed
project. It receives a short `KnowledgeOS guidance revision ...` context reminder.
An agent that has not loaded that revision should reread applicable entries and
agent-guide before substantial work. A known revision need not trigger repeated
reads. This is advisory context, not proof that a model complied.

To test the script independently of host loading/trust, run it from a managed
project (replace the script path):

```sh
python3 -c 'import json, os; print(json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": os.getcwd()}))' |
  python3 -B "/absolute/path/to/KnowledgeOS/bin/kos-guidance-refresh.py"
```

JSON with `additionalContext` confirms the handler works for that directory.
Empty output is expected for unmanaged directories; it can also mean a required
file is absent, unreadable, symlinked or oversized. Check paths and hook trust
before assuming another chat refreshed. If your host retains cached hook
configuration, reload it using the host's normal controls when convenient;
do not interrupt active work just to force a reload.

## Boundaries and removal

- Only `UserPromptSubmit` is handled; already-running turns are not interrupted.
- A revision hashes bounded local rule files and the adjacent launcher. File
  contents and paths are not copied into the context message.
- It emits a short reminder per managed prompt, not the entire ruleset. It stores
  no per-chat state, writes no project files, and performs no network calls.
- Missing or malformed input and read failures exit successfully without a
  blocking decision. This never waives existing project safety requirements.
- New eligible runs can use the lean workflow; existing runs keep their original
  progress, permissions and acceptance. No initialization or migration is performed.
- Remove only this handler to uninstall. Keep other hooks and global rules intact.
  Do not restore an old whole-file backup over unrelated later changes.

The hook is distributed as an optional script, not a new kernel gate, plugin,
daemon or required workflow step.
