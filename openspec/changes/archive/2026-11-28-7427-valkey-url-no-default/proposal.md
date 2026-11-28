# Proposal: #7427

## Why

`valkey.url` currently defaults to `valkey://localhost:6379/0` (`DEFAULT_VALKEY_URL` in `src/devops_cli/config/defaults.py`) (#7427). When no configuration file sets `valkey.url` (such as in the devcontainer, where no Valkey listens on localhost), every cache client dials `localhost:6379`, fails, opens the circuit breaker, and emits `devops_cli_valkey_cache_errors_total{error="open"}` on every subsequent call (about 403,000 events in 24 hours). Per #1165, clients must never fall back to an unconfigured service URL.

## What Changes

- Delete `DEFAULT_VALKEY_URL` from `src/devops_cli/config/defaults.py` and default `ValkeyConfig.url` to `None` in `src/devops_cli/config/settings.py`.
- Make `ValkeyConfig.endpoint` raise `ConfigurationError` naming `valkey.url` when `url` is unset or empty, so `devops valkey` commands fail clearly with an error naming `valkey.url`.
- Update `_configured_cache_tier` in `src/devops_cli/valkey/cache.py` to return `None` when `settings.valkey.url` is unset or empty, so `shared_cache_tier()` opens no connection, logs no warning, and records no error counter sample, while tiered caches fall back to their local tier.
- Regenerate `docs/CONFIGURATION.md` via `uv run devops docs generate` so `valkey.url` shows no default (`-`).
- This change alters observable `devops valkey` error behavior, `shared_cache_tier` behavior when `valkey.url` is unset, and `docs/CONFIGURATION.md`, so it carries spec deltas on `valkey-endpoint` and `valkey-cache-tier`. It fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `valkey-endpoint`: remove the `valkey://localhost:6379/0` default and raise `ConfigurationError` naming `valkey.url` when `valkey.url` is unset or empty.
- `valkey-cache-tier`: return `None` from `shared_cache_tier()` with no connection and no error metric when `valkey.url` is unset, keeping local cache tiers active.

## Impact

- Code: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/valkey/cache.py`
- Tests: `tests/commands/test_valkey.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/valkey/test_tiered.py`
- Documents: `docs/CONFIGURATION.md` (regenerated)

## Feasibility

- Confirmed in `src/devops_cli/config/defaults.py:749` (`DEFAULT_VALKEY_URL`) and `src/devops_cli/config/settings.py:557-589` (`ValkeyConfig.url` and `ValkeyConfig.endpoint`).
- Confirmed in `src/devops_cli/valkey/cache.py:300-326`: `_configured_roadmap_state_tier` already returns `None` when `roadmap.state.endpoint` is `None`, whereas `_configured_cache_tier` always passes `cfg.endpoint` (falling back to `DEFAULT_VALKEY_URL`).

## Existing Tool Considered

No external library covers removing an internal default setting URL. Modifying `ValkeyConfig` and `_configured_cache_tier` in-repo costs about 2,000–4,000 tokens and under 1 hour to build, keep, and maintain, and adds no dependency. Internal code deleted: `DEFAULT_VALKEY_URL` in `src/devops_cli/config/defaults.py` and the loopback fallback in `ValkeyConfig.endpoint`.

## Dependencies

None.
