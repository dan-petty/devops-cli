# Design

## Decisions

- **Default `ValkeyConfig.url` to `None` and delete `DEFAULT_VALKEY_URL`**: Matches #1165 ("no client falls back to an unconfigured service URL") and matches `RoadmapStateConfig.url` (`src/devops_cli/config/settings.py:2260`).
- **Raise `ConfigurationError` in `ValkeyConfig.endpoint` when unset or empty**: Direct callers such as `devops valkey` (`_resolve_client`) fail with exit code 1 and a clear message naming `valkey.url` and how to set it (`devops k8s configure-urls` or `devops config set valkey.url <url>`).
- **Return `None` from `_configured_cache_tier` when `not cfg.url`**: Cache callers (`EmbeddingsEngine`, `CloudflareRadarClient`, `TieredMapping`, `library_store`, `listing_shared`) already handle `shared_cache_tier() is None` by using their local tier without opening sockets, logging warnings, or incrementing `devops_cli_valkey_cache_errors_total` (`src/devops_cli/valkey/cache.py:313-326`).

## Rejected alternatives

- **Keep `DEFAULT_VALKEY_URL` on `ValkeyConfig.url`**: Rejected because unconfigured environments (like the devcontainer) dial localhost, trip the breaker, and emit ~403,000 `error="open"` samples per 24 h, masking real cluster errors (#7427).
- **Return `None` from `ValkeyConfig.endpoint`**: Rejected because `devops valkey` commands must fail with `ConfigurationError` naming `valkey.url` rather than turning into silent no-ops.
- **Make `ValkeyCacheTier` accept `None` and suppress errors inside `_send`**: Rejected because `shared_cache_tier()` already returns `None` when disabled (e.g., on an invalid URL) and every cache caller already handles `None`.
