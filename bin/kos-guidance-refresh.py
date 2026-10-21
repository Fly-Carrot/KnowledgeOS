"""Read-only UserPromptSubmit reminder. Never runs KnowledgeOS or blocks work."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

LIMIT = 64 * 1024
LAUNCHER = Path(__file__).resolve().with_name('knowledgeos')


def bounded_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
            raise ValueError('not a bounded regular file')
        data = stream.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError('file grew beyond limit')
        return data


def response(payload, home):
    if not isinstance(payload, dict) or payload.get('hook_event_name') != 'UserPromptSubmit':
        return {}
    cwd = payload.get('cwd')
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        return {}
    directory = Path(cwd).resolve(strict=True)
    if not directory.is_dir():
        return {}
    root = next((p for p in (directory, *directory.parents)
                 if (p / '.agent-os/project.yaml').is_file()), None)
    if root is None:
        return {}
    digest = hashlib.sha256(str(root).encode())
    paths = [home / 'AGENTS.md', LAUNCHER,
             root / '.agent-os/project.yaml']
    # Include applicable entries without copying project-controlled text into a hook message.
    paths += [p / 'AGENTS.md' for p in (*reversed(directory.parents), directory)
              if (p / 'AGENTS.md').exists()]
    startup = root / '.agent-os/startup-prompt.md'
    if startup.exists():
        paths.append(startup)
    for path in paths:
        digest.update(str(path).encode() + b'\0' + bounded_read(path) + b'\0')
    text = (
        f'KnowledgeOS guidance revision {digest.hexdigest()[:16]}. '
        'Before substantial work, if this revision is not loaded in this chat, reread global and applicable '
        'project AGENTS.md and the installed agent-guide. Only eligible new runs use ordinary-v1; preserve '
        'existing runs, permissions and acceptance. Do not initialize or migrate merely to refresh guidance. This reminder adds no '
        'checkpoint; refresh failure must not interrupt unrelated safe work.'
    )
    return {'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': text}}


def main():
    try:
        raw = sys.stdin.buffer.read(LIMIT + 1)
        if len(raw) > LIMIT:
            return
        result = response(json.loads(raw), Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))))
        if result:
            print(json.dumps(result))
    except Exception:
        # Optional reminder: no deny decision, nonzero status, writes or sensitive error text.
        return


if __name__ == '__main__':
    main()
