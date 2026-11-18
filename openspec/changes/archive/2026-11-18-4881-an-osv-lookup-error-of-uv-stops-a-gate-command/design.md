# Design

## Decisions
- The check runs where a package can arrive and nowhere else. The steps that install packages
  (`setup-toolchain`'s `Synchronize dependencies`, the devcontainer `postCreateCommand`) set
  `UV_MALWARE_CHECK=1`; every check-only row, hook and interactive shell sets it to `0`.
- `devops ci` sets the switch at its one choke point: `_GATE_ROW_ENV` merges `UV_MALWARE_CHECK=0`
  into the environment of every row command, its dry-run plan, the audit row and the fix commands.
  No row installs a package, so the switch applies to all of them.
- The interactive shells get `0` in the checked-in configs and their templates, because the failure
  happens in the outer `uv run` that starts `devops`, before a row reads its own environment.
- pre-commit 4.7.0 has no hook `env` key, and its maintainer points to the `entry` for a variable
  (pre-commit#2367), so each check hook prefixes its command with the `env` program:
  `entry: env UV_MALWARE_CHECK=0 uv run ...`. The runner image then needs `env`, which joins the
  `_base` tools of `RUNNER_TOOLS`.

## Rejected alternatives
- Set the variable only in the `devops ci` row environment: the reported failures happen in the
  outer `uv run` before `devops` starts, so the row environment is never read.
- Wait for an upstream warning or retry setting: the gate stays broken until uv ships the setting,
  and no such setting is documented.
- Retry the whole command after a failure: the error comes before the command starts, so each retry
  pays the retry delay again and hides the cause.
- Run the gate commands with `uv run --no-sync`: it skips every sync, so a stale environment runs
  with missing packages; the switch keeps the sync.
