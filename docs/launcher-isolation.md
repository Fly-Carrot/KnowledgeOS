# Launcher Isolation

## Reproduced Defect

The former launcher invoked `python3 -m knowledgeos`. Python searches the
working directory before `PYTHONPATH`, so another `knowledgeos` package there
could replace the selected checkout even when the launcher used an absolute
path. This could invalidate candidate-versus-installed comparisons.

`tests/test_launcher.py` first reproduces this with a disposable shadow package.
The test fails on the old launcher because it prints `SHADOWED_FROM_CWD` rather
than the real CLI help. No user files are used as test outputs.

## Repair

The launcher inserts its own resolved root at the beginning of `sys.path` and
uses the standard-library `runpy` entry point. It removes the bootstrap argument
before dispatching the CLI. It does not `chdir`, discard user arguments, or
translate process exit codes. No new dependencies or minimum Python flag
requirements are introduced.

The regression suite covers the real CLI under a shadow package plus a
space-containing installation/caller directory, relative project argument,
quoted values, literal arguments after `--`, and a nonzero exit code.

This pins the selected package; it is not an isolation sandbox for a compromised
Python interpreter or arbitrary environment-level injection. User data,
historical runs and globally installed code are not migrated by this patch.
