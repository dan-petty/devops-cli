# Tasks

## 1. Failing Test

- [x] 1.1 Add `tests/config/test_removed_settings_fields.py` asserting `enabled` and `idp` are off `CloudflareAccessConfig`, that a section that still holds a removed key loads and drops it, and that `telemetry.logfire` stays because it has a reader; verify it fails before the removal. Verification: `uv run pytest tests/config/test_removed_settings_fields.py`.

## 2. Remove the Dead Fields

- [x] 2.1 Remove `enabled` and `idp` from `CloudflareAccessConfig` in `src/devops_cli/config/settings.py`, keeping `telemetry.logfire` because it has a reader and a test.
- [x] 2.2 Remove `enabled: false` and `idp: google` from the `access` section of `config.example.yaml`.
- [x] 2.3 Verify the test passes after the removal. Verification: `uv run pytest tests/config/test_removed_settings_fields.py`.

## 3. Documentation

- [x] 3.1 Regenerate the documentation and the README, dropping the `enabled` and `idp` entries of the `access` row in `docs/CONFIGURATION.md` and keeping the `logfire` row. Verification: `uv run devops docs generate --sync-readme` then `uv run devops docs check`.

## 4. Verification and Quality Gate

- [x] 4.1 Run `uv run devops ci fail-to-pass --base origin/main` to verify the failing test evidence.
- [x] 4.2 Run `uv run devops ci` to ensure all static checks and test suites pass.
- [x] 4.3 Archive the OpenSpec change with `uv run devops openspec archive 2457-remove-dead-settings`.
