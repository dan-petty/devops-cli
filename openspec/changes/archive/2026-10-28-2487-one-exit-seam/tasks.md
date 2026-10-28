# Tasks

## 1. One exit seam for every command

- [x] Add failing tests: a command and an `invoke_without_command` callback that raise a `DevOpsCLIError` with markup exit with its status in one line and no traceback; every registered app is an `OTelTyper`; no command module reports a `DevOpsCLIError` itself
  - Verification: `uv run devops ci test tests/commands/test_command_error_exit.py tests/invariants/test_source_tree.py`
- [x] Report every `DevOpsCLIError` in the `OTelTyper.command` wrapper and in a new `OTelTyper.callback` wrapper, delete `exit_on`, and make `exit_on_error` the private `_report_devops_error`
  - Verification: `uv run devops ci test tests/commands/test_command_error_exit.py`
- [x] Delete the `exit_on=` arguments, the `exit_on_error` blocks and the hand-rolled handlers, and the two error printers they leave without a caller; build the `config` app with `new_typer()`
  - Verification: `uv run devops ci test tests/invariants/test_source_tree.py`
- [x] Assert the one-line report and the exit status in the sandbox and Valkey command tests that read the old report or the escaped error
  - Verification: `uv run devops ci test tests/test_sandbox_lifecycle.py tests/test_sandbox_logs.py tests/test_valkey.py`
- [x] Describe the seam in `ARCHITECTURE.md` and `CONTRIBUTING.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2487-one-exit-seam`

## Workflow follow-up

- #2490: an exception class declares its `error_code` and `exit_code`, and the forwarding `__init__` methods, the unused classes and the `CONST_ERROR_CODE_*` constants go.
- `devops roadmap`'s `_exit_on_failure` exits with status 1, not with the error's `exit_code`. It stays, because a change to it changes exit statuses.
- Pending a person: run a `devops cloudflare` and a `devops valkey` command that fails on a missing token, and check that each prints one error line and exits with the same status as before.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
