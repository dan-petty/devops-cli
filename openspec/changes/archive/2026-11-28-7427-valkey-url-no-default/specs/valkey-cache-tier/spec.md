## ADDED Requirements

### Requirement: Unset valkey.url disables the shared Valkey cache tier
When `valkey.url` is unset or empty, `shared_cache_tier()` SHALL return `None` without opening a connection, logging a warning, or incrementing `devops_cli_valkey_cache_errors_total`, and tiered caches SHALL serve reads and writes from their local tiers.

#### Scenario: Shared cache tier and local tier with unset valkey.url
- **WHEN** `valkey.url` is unset and a process calls `shared_cache_tier()`, `TieredMapping` read/write, and `EmbeddingsEngine`
- **THEN** `shared_cache_tier()` returns `None`, `TieredMapping` serves from its in-memory tier, no socket connection opens, and `devops_cli_valkey_cache_errors_total` records no error
