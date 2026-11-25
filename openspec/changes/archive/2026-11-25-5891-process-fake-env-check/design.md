# Design

## Decisions
- Call `build_subprocess_env` from `devops_cli.core.process` inside a shared helper on `ProcessFake` for `run`, `run_async`, and `spawn_detached` with `env=env`, `isolate_env=isolate_env`, and `extra_allowed_keys=extra_allowed_env`, letting `SecurityError` propagate directly before returning an answer or child.
- Keep `ProcessCall.env` equal to the raw `env` mapping supplied by the caller so existing assertions on `process_fake.calls[...].env` remain intact.
- Add optional `env: dict[str, str] | None = None` to `ProcessFake.spawn_detached` and extract `isolate_env` and `extra_allowed_env` in `ProcessFake.run_async` (defaulting to `True` and `None`) so all three entry points record both flags on `ProcessCall` identically to `ProcessFake.run`.
- Resolve `build_subprocess_env` via the `devops_cli.core.process` module attribute so tests spying on `devops_cli.core.process.build_subprocess_env` observe every call.

## Rejected alternatives
- **Store the sanitized dict returned by `build_subprocess_env` in `ProcessCall.env`**: rejected because it alters existing `ProcessCall.env` expectations across unrelated tests beyond validating caller overrides and flags.
- **Re-implement the deny list check inside `ProcessFake`**: rejected because duplicating `_is_env_override_refused` in test code would drift from `build_subprocess_env`.
- **Keep `ProcessFake.spawn_detached` without `env`**: rejected because detached launches could not be tested for refused overrides alongside `run` and `run_async`.
