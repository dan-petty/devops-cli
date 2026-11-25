# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for content kinds, pending queue, gauge, client contract, CLI subcommands, and cleanup retention
  - Verification: `$ uv run pytest -n 0 tests/store/ tests/commands/test_store.py tests/core/test_workspace_cleanup.py`
- [x] 1.2 Implement `devops_cli.store`, `StoreConfig`, credentials, exceptions, `STORE_PENDING_UPLOADS` gauge, and `devops store` subcommands
  - Verification: `$ uv run pytest -n 0 tests/store/ tests/commands/test_store.py tests/core/test_workspace_cleanup.py tests/telemetry/test_telemetry_instruments.py tests/commands/test_all_commands_help_dryrun.py tests/commands/test_cli_startup_imports.py`

## 2. Documents

- [x] 2.1 Regenerate CLI, configuration, and error catalog documentation
  - Verification: `$ uv run devops docs generate && uv run devops ci --check --only docs`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
