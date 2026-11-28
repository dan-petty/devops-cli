# Tasks

## 1. Remove DEFAULT_VALKEY_URL and disable cache tier when valkey.url is unset

Kind: behavior.

Reads: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/valkey/cache.py`, `tests/commands/test_valkey.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/valkey/test_tiered.py`.

Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/valkey/cache.py`, `tests/commands/test_valkey.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/valkey/test_tiered.py`.

- [x] 1.1 Write failing tests in `tests/commands/test_valkey.py`, `tests/valkey/test_valkey_cache_tier.py`, and `tests/valkey/test_tiered.py` verifying that `DEFAULT_VALKEY_URL` is absent, `ValkeyConfig.url` defaults to `None`, `ValkeyConfig.endpoint` and `devops valkey ping` fail naming `valkey.url` when unset, `shared_cache_tier()` returns `None` with no warning or connection, and `TieredMapping` serves locally with no `devops_cli_valkey_cache_errors_total` error.
  - Verification: `$ uv run devops ci test tests/commands/test_valkey.py tests/valkey/test_valkey_cache_tier.py tests/valkey/test_tiered.py`
- [x] 1.2 Delete `DEFAULT_VALKEY_URL` from `src/devops_cli/config/defaults.py`, default `ValkeyConfig.url` to `None` and raise `ConfigurationError` in `ValkeyConfig.endpoint` when unset/empty, and return `None` from `_configured_cache_tier` when `valkey.url` is unset/empty.
  - Verification: `$ uv run devops ci test tests/commands/test_valkey.py tests/valkey/test_valkey_cache_tier.py tests/valkey/test_tiered.py`

## 2. Regenerate configuration documentation

Kind: documents.

Reads: `docs/CONFIGURATION.md`.

Changes: `docs/CONFIGURATION.md`.

- [x] 2.1 Regenerate generated docs so `docs/CONFIGURATION.md` shows `-` (no default) for `valkey.url`.
  - Verification: `$ uv run devops ci docs`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
