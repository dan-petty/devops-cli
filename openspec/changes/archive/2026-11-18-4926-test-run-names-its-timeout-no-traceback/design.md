# Design

## Decisions
- Catch `subprocess.TimeoutExpired` at the one `run_subprocess` call in `run_test_cmd` and raise a
  `DevOpsCLIError`. The one exit seam of `new_typer()` prints the message as one error line and
  exits 1, so the command needs no reporting code of its own.
- Add a `--timeout` option to `devops test run`, default `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`
  (1800 seconds), and pass it to `run_subprocess`. The error line names the effective value, so a
  non-default run reports its own seconds.

## Rejected alternatives
- Let the traceback propagate: it prints 480 lines and names neither the limit nor the option.
- Catch and print the message in `run_test_cmd`: it bypasses the one exit seam and the error exit
  code, which the command-error-exit capability keeps.
- Use a fixed 1800-second limit: a person cannot change the limit for this command.
- Read a config setting with no option: no setting exists, and the error line cannot name a
  concrete control.
