# Design

## Decisions

- **Remove `set_dry_run(True)` and its import from `entry.py`**: The root callback in `src/devops_cli/main.py` sets the canonical dry-run state for all commands. Early options (`--version`, `--help`) do not read `is_dry_run()`. Telemetry at exit uses `in_dry_run_invocation()`, which `mark_dry_run_invocation` sets in `entry.py`. Removing `set_dry_run(True)` avoids setting `_ACTIVATED_HERE = True` prematurely.
- **Keep `mark_dry_run_invocation(requested)`**: `mark_dry_run_invocation` accurately records that the command line requested a dry run, which telemetry export checks before making network calls.
- **Add regression tests to `tests/commands/test_entry_point.py`**: Cover the exported environment variable case meeting a command's own `--dry-run` flag, verify early-exit flags with `--dry-run`, and ensure `entry.py` does not import `set_dry_run`.

## Rejected alternatives

- **Keep `set_dry_run(True)` in `entry.main`**: Rejected. Setting `set_dry_run(True)` in `entry.main` sets `_ACTIVATED_HERE = True`, which causes `dry_run_requested_by_environment()` in `main.py` to evaluate to `False` and clear exported `DEVOPS_CLI_DRY_RUN`.
- **Add custom logic in `entry.py` to check `dry_run_requested_by_environment()`**: Rejected. Adding compensating logic to work around a duplicate call introduces unnecessary complexity when the call itself is redundant.
