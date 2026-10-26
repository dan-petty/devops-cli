# Design

The dry-run check sits at the same place it already does, just before the subprocess runner. The gate widens from `is_dry_run()` to `dry_run or is_dry_run()`, so the command's own `--dry-run` flag previews instead of executing. The check is added in `apply` and in `_apply_template`, the two paths that start `kubectl`.

## Rejected alternatives

- **Call `set_dry_run(dry_run)` at the top of `apply`.** This would make `is_dry_run()` true, but it also sets the `DEVOPS_CLI_DRY_RUN` environment variable, which leaks the dry-run state to later commands in the same process. The flag is per-invocation. The other commands in this file gate on `dry_run or is_dry_run()` instead. Rejected.
- **Remove the `--dry-run=client` flag from the kubectl command.** The preview is a devops-level preview that starts no child process, so the flag is not needed to keep a real run safe. Removing it changes the rendered command the command would run for a non-dry-run call, which is outside this issue. Rejected.
- **Add a shared decorator.** Two functions in one file need the check, and the codebase gates each command inline. A decorator adds code with no second user. Rejected.
