# Design

## Decisions
- Share the gate's guard as `version_finding` in `src/devops_cli/openspec/gate.py`. The gate owns
  the finding, its message and the lock read, and `check_openspec` and `regenerate` both call it,
  so the rule lives once.
- `regenerate` raises `ToolExecutionError(problem.detail, tool_name=BIN_OPENSPEC)` before
  `regenerate_skills`. `ToolExecutionError` is a `DevOpsCLIError` with exit code 1, and the one exit
  seam of the CLI reports its message, which is the finding's detail.
- The version run goes through `OpenSpecTool.run`, so it carries the same opt-out environment
  (`DO_NOT_TRACK`, `OPENSPEC_TELEMETRY`, `OPENSPEC_NO_UPDATE_CHECK`, `OPEN_SPEC_INTERACTIVE`, the
  isolated `XDG_CONFIG_HOME` and `HOME`) and the same timeout as the gate's version run.
- The guard runs only on a real run. A dry run writes nothing, and `run_subprocess` returns a
  planned result with no output, so a guard there would report a false unreadable version.

## Rejected alternatives
- Copy the guard into `src/devops_cli/commands/openspec.py`: two copies of the version rule drift
  apart, and the issue asks for one function.
- Print the finding and raise `typer.Exit(1)`: it duplicates the check command's print loop and
  bypasses the one exit seam that reports a domain error.
- Run the binary with `subprocess.run`: it drops the opt-out environment and the timeout, and it
  adds a second code path for the same read.
- Run the guard in a dry run too: the dry-run process runner returns a planned result with no
  output, so the version read would raise a false finding.
